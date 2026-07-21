from __future__ import annotations

import csv
import hashlib
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

import traffictwin.experiments.scenario_mutation as mutation_module
from traffictwin.config.capabilities import CapabilitySupport
from traffictwin.config.seed_io import load_seed
from traffictwin.experiments.scenario_mutation import (
    MutationOperator,
    MutationTableKind,
    RowDropoutMutation,
    RsuRemovalMutation,
    ScenarioMutationError,
    ScenarioMutationRequest,
    TimestampJitterMutation,
    execute_scenario_mutation,
    load_scenario_mutation_request,
    plan_scenario_mutation,
    scenario_mutation_contract,
    scenario_mutation_request_to_yaml,
)
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.integration.sumo.contract import sumo_results_capability_manifest
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest

FIXTURE = Path("tests/fixtures/bundles/baseline_valid")
FIXED_TIME = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def _dropout_request() -> ScenarioMutationRequest:
    return ScenarioMutationRequest(
        mutation_id="mutation-dropout",
        title="Task evidence dropout",
        description="Deterministic robustness fixture",
        mutation=RowDropoutMutation(
            table_kind=MutationTableKind.TASKS,
            drop_fraction=0.25,
            random_seed=17,
        ),
    )


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_row_dropout_is_exact_deterministic_and_does_not_mutate_parent(tmp_path: Path) -> None:
    request = _dropout_request()
    parent_hashes = _file_hashes(FIXTURE)

    first_plan = plan_scenario_mutation(FIXTURE, request)
    second_plan = plan_scenario_mutation(FIXTURE, request)

    assert first_plan == second_plan
    assert first_plan.fingerprint() == first_plan.plan_fingerprint
    assert first_plan.changed_row_count == 1
    assert first_plan.row_changes[0].action == "dropped"
    assert first_plan.raw_source_mutated is False
    assert first_plan.synthetic_evaluation is True
    assert first_plan.parent_bundle_fingerprint == validate_bundle(FIXTURE).fingerprint

    first = execute_scenario_mutation(
        FIXTURE,
        request,
        tmp_path / "first",
        clock=lambda: FIXED_TIME,
    )
    second = execute_scenario_mutation(
        FIXTURE,
        request,
        tmp_path / "second",
        clock=lambda: datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )

    assert first.mutation_fingerprint == second.mutation_fingerprint
    assert first.derived_bundle_fingerprint == second.derived_bundle_fingerprint
    assert first.fingerprint() == first.mutation_fingerprint
    assert first.validation_may_import
    assert first.validation_status == "accepted"
    assert (
        len(_csv_rows(tmp_path / "first" / "bundle" / "tasks.csv"))
        == len(_csv_rows(FIXTURE / "tasks.csv")) - 1
    )
    assert _file_hashes(FIXTURE) == parent_hashes
    assert (tmp_path / "first" / "mutation_manifest.json").is_file()
    assert (tmp_path / "first" / "request.yaml").is_file()


def test_timestamp_jitter_is_bounded_and_preserves_within_row_time_differences(
    tmp_path: Path,
) -> None:
    request = ScenarioMutationRequest(
        mutation_id="mutation-jitter",
        title="Task timestamp jitter",
        mutation=TimestampJitterMutation(
            table_kind=MutationTableKind.TASKS,
            max_absolute_jitter_s=2.0,
            random_seed=91,
        ),
    )

    result = execute_scenario_mutation(FIXTURE, request, tmp_path / "jitter")
    parent_rows = _csv_rows(FIXTURE / "tasks.csv")
    derived_rows = _csv_rows(tmp_path / "jitter" / "bundle" / "tasks.csv")

    assert result.changed_row_count >= 1
    assert len(parent_rows) == len(derived_rows)
    for before, after in zip(parent_rows, derived_rows, strict=True):
        arrival_delta = float(after["arrival_time"]) - float(before["arrival_time"])
        assert abs(arrival_delta) <= 2.0
        if before["completion_time"]:
            completion_delta = float(after["completion_time"]) - float(before["completion_time"])
            assert completion_delta == pytest.approx(arrival_delta, abs=1e-6)
        assert float(after["arrival_time"]) >= 0
    assert all(
        change.row_fingerprint_after is not None and change.field_changes
        for change in result.row_changes
    )


def test_rsu_removal_updates_seed_but_does_not_invent_task_rerouting(tmp_path: Path) -> None:
    request = ScenarioMutationRequest(
        mutation_id="mutation-rsu-removal",
        title="Remove RSU 2",
        mutation=RsuRemovalMutation(rsu_id="rsu-2"),
    )

    result = execute_scenario_mutation(FIXTURE, request, tmp_path / "removed")
    bundle = tmp_path / "removed" / "bundle"
    seed = load_seed(bundle / "seed.yaml")

    assert result.changed_row_count == 2
    assert {row["rsu_id"] for row in _csv_rows(bundle / "infra_state.csv")} == {"rsu-1"}
    assert (bundle / "tasks.csv").read_bytes() == (FIXTURE / "tasks.csv").read_bytes()
    assert "rsu-2" in seed.infrastructure.failed_rsus
    assert seed.infrastructure.rsu_count == 1
    assert seed.parent_seed_id == "s1-gridlock-baseline"
    assert any("did not invent task rerouting" in warning for warning in result.warnings)
    assert result.validation_may_import


def test_request_round_trip_and_contract_publish_closed_safety_boundary(tmp_path: Path) -> None:
    request = _dropout_request()
    request_path = tmp_path / "request.yaml"
    request_path.write_text(scenario_mutation_request_to_yaml(request), encoding="utf-8")

    assert load_scenario_mutation_request(request_path) == request
    contract = scenario_mutation_contract()
    assert contract.supported_operators == list(MutationOperator)
    assert contract.max_changed_rows == 20_000
    assert contract.exact_change_ledger
    assert contract.raw_source_mutation_supported is False
    assert contract.direct_launch_supported is False
    assert "rerouting" in contract.rsu_removal_policy


def test_invalid_parameters_absent_targets_and_missing_tables_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RowDropoutMutation(table_kind=MutationTableKind.TASKS, drop_fraction=0.0)
    with pytest.raises(ValidationError):
        TimestampJitterMutation(
            table_kind=MutationTableKind.TASKS,
            max_absolute_jitter_s=3_601,
        )
    absent = ScenarioMutationRequest(
        mutation_id="mutation-missing-rsu",
        title="Missing RSU",
        mutation=RsuRemovalMutation(rsu_id="rsu-99"),
    )
    with pytest.raises(ScenarioMutationError, match="absent"):
        plan_scenario_mutation(FIXTURE, absent)
    missing_table = ScenarioMutationRequest(
        mutation_id="mutation-missing-table",
        title="Missing table",
        mutation=RowDropoutMutation(
            table_kind=MutationTableKind.VEHICLE_STATE,
            drop_fraction=0.1,
        ),
    )
    with pytest.raises(ScenarioMutationError, match="does not declare"):
        plan_scenario_mutation(FIXTURE, missing_table)


def test_non_synthetic_parent_is_rejected_without_output(tmp_path: Path) -> None:
    parent = tmp_path / "imported"
    shutil.copytree(FIXTURE, parent)
    manifest_path = parent / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["bundle"]["source"] = "imported_real_evidence"
    manifest["environment"]["name"] = "external"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    with pytest.raises(ScenarioMutationError, match="not explicitly labelled"):
        execute_scenario_mutation(parent, _dropout_request(), tmp_path / "not-written")

    assert not (tmp_path / "not-written").exists()


def test_change_limit_is_checked_before_destination_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mutation_module, "MAX_CHANGED_ROWS", 1)
    request = ScenarioMutationRequest(
        mutation_id="mutation-too-many",
        title="Too many changes",
        mutation=TimestampJitterMutation(
            table_kind=MutationTableKind.TASKS,
            max_absolute_jitter_s=1.0,
            random_seed=2,
        ),
    )

    with pytest.raises(ScenarioMutationError, match="maximum is 1"):
        execute_scenario_mutation(FIXTURE, request, tmp_path / "not-written")

    assert not (tmp_path / "not-written").exists()


def test_protected_and_symbolic_destinations_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ScenarioMutationError, match="current directory"):
        execute_scenario_mutation(FIXTURE.resolve(), _dropout_request(), ".", overwrite=True)
    with pytest.raises(ScenarioMutationError, match="must not be empty"):
        execute_scenario_mutation(FIXTURE.resolve(), _dropout_request(), "", overwrite=True)

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ScenarioMutationError, match="symbolic link"):
        execute_scenario_mutation(FIXTURE.resolve(), _dropout_request(), link, overwrite=True)

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert not list(target.iterdir())


def test_overwrite_is_explicit_and_zip_parent_has_equal_plan(tmp_path: Path) -> None:
    destination = tmp_path / "mutation"
    first = execute_scenario_mutation(FIXTURE, _dropout_request(), destination)
    with pytest.raises(FileExistsError):
        execute_scenario_mutation(FIXTURE, _dropout_request(), destination)
    replaced = execute_scenario_mutation(
        FIXTURE,
        _dropout_request(),
        destination,
        overwrite=True,
    )
    assert replaced.mutation_fingerprint == first.mutation_fingerprint

    archive = tmp_path / "parent.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for path in sorted(FIXTURE.iterdir()):
            output.write(path, path.name)
    assert plan_scenario_mutation(archive, _dropout_request()) == plan_scenario_mutation(
        FIXTURE, _dropout_request()
    )


def test_source_destination_overlap_and_failed_publish_preserve_existing_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "parent"
    shutil.copytree(FIXTURE, parent)
    with pytest.raises(ScenarioMutationError, match="overlap the parent bundle"):
        execute_scenario_mutation(parent, _dropout_request(), parent, overwrite=True)
    with pytest.raises(ScenarioMutationError, match="overlap the parent bundle"):
        execute_scenario_mutation(parent, _dropout_request(), parent / "derived")
    with pytest.raises(ScenarioMutationError, match="overlap the parent bundle"):
        execute_scenario_mutation(parent, _dropout_request(), tmp_path, overwrite=True)

    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    replace = Path.replace

    def fail_payload_publish(source: Path, target: Path) -> Path:
        if source.name == "payload":
            raise OSError("simulated publish failure")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_payload_publish)
    with pytest.raises(OSError, match="simulated publish failure"):
        execute_scenario_mutation(parent, _dropout_request(), destination, overwrite=True)

    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_source_specific_adapters_do_not_claim_mutation_support() -> None:
    assert (
        sumo_results_capability_manifest().supports.scenario_mutation_operators
        is CapabilitySupport.FALSE
    )
    assert (
        tos_data_capability_manifest().supports.scenario_mutation_operators
        is CapabilitySupport.FALSE
    )
