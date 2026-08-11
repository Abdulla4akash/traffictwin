from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_e2d_per_task_placement_robustness as runner  # noqa: E402
from analyze_e2d_per_task_placement_robustness import (  # noqa: E402
    paired_summary,
    substep_mechanism,
)
from run_e2d_per_task_placement_robustness import (  # noqa: E402
    initialise_or_verify_campaign_root,
    remaining_projection,
    required_free_bytes,
    run_full_cell,
    run_smoke_gate,
    storage_gate_passes,
    validate_manifest_contract,
    verify_all_smoke_evidence,
    verify_prior_full_cell_order,
    verify_review_gate,
    write_json_new,
)
from run_e2d_per_task_placement_robustness import (  # noqa: E402
    main as runner_main,
)
from validate_e2d_per_task_placement_robustness import (  # noqa: E402
    format_command,
    reference_record,
    sha256,
    verify_reference_record,
)

MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/evaluation/e2d/e2d_per_task_placement_robustness_manifest_v1.json"
)


def authorised_manifest() -> dict:
    return {
        "full_cell_order": [
            {"cell_index": seed, "fleet_seed": seed, "arm": "per_task_dla"} for seed in (1, 2, 3, 4)
        ],
        "existing_mode_replay_order": [
            {"replay_index": index, "fleet_seed": seed, "arm": arm}
            for index, (seed, arm) in enumerate(
                (
                    (1, "ingress_dla"),
                    (1, "dla"),
                    (2, "ingress_dla"),
                    (2, "dla"),
                    (3, "ingress_dla"),
                    (3, "dla"),
                    (4, "ingress_dla"),
                    (4, "dla"),
                ),
                start=1,
            )
        ],
        "smoke_gate": {
            "steps": 10,
            "total_new_arm_runs": 8,
            "order": [
                {
                    "smoke_index": index,
                    "cell_index": seed,
                    "fleet_seed": seed,
                    "arm": "per_task_dla",
                    "repeat": repeat,
                }
                for index, (seed, repeat) in enumerate(
                    ((seed, repeat) for seed in (1, 2, 3, 4) for repeat in (1, 2)),
                    start=1,
                )
            ],
        },
        "arms": {
            "ingress_dla": {"rsu_lb": "ingress_dla"},
            "dla": {"rsu_lb": "dla"},
            "per_task_dla": {"rsu_lb": "per_task_dla"},
        },
        "command_template": [
            "python",
            "evaluator",
            "--max-steps",
            "{MAX_STEPS}",
            "--fleet-seed",
            "{FLEET_SEED}",
            "--rsu-lb",
            "{ARM}",
            "--rsu-backhaul-ms",
            "0.0",
            "--k8s-scale",
            "off",
            "--out-json",
            "{RUN_DIR}/summary.json",
        ],
        "design": {"smoke_steps": 10, "steps": 3600, "fleet_seeds": [1, 2, 3, 4]},
        "compute_and_storage": {
            "projected_ten_step_wall_seconds": 35.0,
            "projected_per_task_full_wall_seconds": 17802.4,
            "projected_ten_step_output_bytes": 700000,
            "projected_per_task_full_output_bytes": 210000000,
        },
    }


def execution_manifest(tmp_path: Path) -> dict:
    manifest = authorised_manifest()
    manifest["outputs"] = {"raw_root": str(tmp_path / "raw")}
    manifest["cross_arm_contract"] = {"logit_diagnostic": {"absolute_tolerance": 0.00001}}
    manifest["e2c_reuse"] = {"by_seed": {}}
    return manifest


def write_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def mark_replay_gate_passed(manifest: dict) -> None:
    write_status(
        Path(manifest["outputs"]["raw_root"]) / "replay_gate_status.json",
        {"status": "passed", "replays_planned": 8, "replays_passed": 8},
    )


def successful_validation(run_dir: Path, cell: dict) -> dict:
    return {"status": "passed", "run_dir": str(run_dir), "run": cell, "summary": {}}


def install_smoke_validation_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "compare_repeats", lambda left, right: {"pass": True})
    monkeypatch.setattr(
        runner,
        "compare_identity_to_reference",
        lambda candidate, reference, manifest: {"pass": True},
    )
    monkeypatch.setattr(runner, "reference_record", lambda *args: {})


def test_primary_negative_direction_label() -> None:
    result = paired_summary([-0.02, -0.021, -0.019, -0.022], primary=True)
    assert (
        result["decision"]
        == "directional_deficit_persists_under_per_task_placement_within_bounded_draws"
    )
    assert result["sign_counts"] == {"negative": 4, "zero": 0, "positive": 0}
    assert result["confidence_interval"]["upper"] < 0.0
    assert result["tasks_used_as_independent_replicates"] is False


def test_primary_direction_mutations_cannot_reuse_negative_label() -> None:
    positive = paired_summary([0.02, 0.021, 0.019, 0.022], primary=True)
    mixed = paired_summary([-0.02, 0.02, -0.01, 0.01], primary=True)
    assert (
        positive["decision"] == "directional_advantage_for_per_task_placement_within_bounded_draws"
    )
    assert mixed["decision"] == "inconclusive_at_this_replication_size"


def test_paired_summary_requires_exactly_four_fleet_draws() -> None:
    with pytest.raises(ValueError, match="exactly four"):
        paired_summary([-0.1, -0.2, -0.3], primary=True)


def test_substep_mechanism_uses_candidate_order_for_switches() -> None:
    task = {
        "task_ingress_rsu": np.asarray([[[0, -1, 0, 0]]], dtype=np.int16),
        "task_selected_execution_rsu": np.asarray([[[0, -1, 1, 0]]], dtype=np.int16),
    }
    result = substep_mechanism(task)
    assert result["total_active_v2i_candidates"] == 3
    assert result["maximum_unique_selected_targets_in_one_substep"] == 2
    assert result["total_target_switches_in_candidate_order"] == 2
    assert result["maximum_candidates_sent_to_one_target_in_one_substep"] == 2


def test_candidate_order_permutation_changes_switch_sensitive_fixture() -> None:
    forward = {
        "task_ingress_rsu": np.asarray([[[0, 0, 0, 0]]], dtype=np.int16),
        "task_selected_execution_rsu": np.asarray([[[0, 0, 1, 1]]], dtype=np.int16),
    }
    permuted = {
        "task_ingress_rsu": forward["task_ingress_rsu"],
        "task_selected_execution_rsu": np.asarray([[[0, 1, 0, 1]]], dtype=np.int16),
    }
    assert substep_mechanism(forward)["total_target_switches_in_candidate_order"] == 1
    assert substep_mechanism(permuted)["total_target_switches_in_candidate_order"] == 3
    assert not np.array_equal(
        forward["task_selected_execution_rsu"],
        permuted["task_selected_execution_rsu"],
    )


def test_manifest_allows_only_four_new_per_task_cells() -> None:
    manifest = authorised_manifest()
    validate_manifest_contract(manifest)
    assert {cell["arm"] for cell in manifest["full_cell_order"]} == {"per_task_dla"}
    assert {cell["fleet_seed"] for cell in manifest["full_cell_order"]} == {1, 2, 3, 4}


def test_manifest_enforces_exact_global_smoke_order() -> None:
    manifest = authorised_manifest()
    validate_manifest_contract(manifest)
    observed = [(item["fleet_seed"], item["repeat"]) for item in manifest["smoke_gate"]["order"]]
    assert observed == [
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
        (3, 1),
        (3, 2),
        (4, 1),
        (4, 2),
    ]
    manifest["smoke_gate"]["order"][2:4] = reversed(manifest["smoke_gate"]["order"][2:4])
    with pytest.raises(RuntimeError, match="smoke order"):
        validate_manifest_contract(manifest)


def test_compute_projection_preserves_eight_replays_eight_smokes_four_fulls() -> None:
    manifest = authorised_manifest()
    replay = remaining_projection(manifest, phase="replay_gate", cell_index=None)
    smoke = remaining_projection(manifest, phase="smoke_gate", cell_index=None)
    first_full = remaining_projection(manifest, phase="full_cell", cell_index=1)
    ten_step_wall = manifest["compute_and_storage"]["projected_ten_step_wall_seconds"]
    full_wall = manifest["compute_and_storage"]["projected_per_task_full_wall_seconds"]
    assert replay["wall_seconds"] == 16 * ten_step_wall + 4 * full_wall
    assert smoke["wall_seconds"] == 8 * ten_step_wall + 4 * full_wall
    assert first_full["wall_seconds"] == 4 * full_wall


def test_smoke_gate_refuses_without_global_replay_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    called: list[str] = []
    monkeypatch.setattr(runner, "preflight", lambda *args, **kwargs: called.append("preflight"))
    monkeypatch.setattr(runner, "run_once", lambda *args, **kwargs: called.append("run"))
    with pytest.raises(RuntimeError, match="global replay gate is absent"):
        run_smoke_gate(tmp_path / "manifest.json", manifest)
    assert called == []


def test_replay_command_runs_only_eight_ten_step_existing_mode_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    monkeypatch.setattr(
        runner,
        "preflight",
        lambda *args, **kwargs: {"identities": {"approved": True}},
    )
    monkeypatch.setattr(
        runner,
        "compare_exact_to_reference",
        lambda candidate, reference: {"pass": True},
    )
    monkeypatch.setattr(runner, "reference_record", lambda *args: {})
    calls: list[tuple[int, str, int, str]] = []

    def fake_replay(
        manifest: dict,
        replay: dict,
        run_dir: Path,
        *,
        max_steps: int,
        phase: str,
        repeat: int,
        identities: dict,
    ) -> dict:
        calls.append((int(replay["fleet_seed"]), str(replay["arm"]), max_steps, phase))
        return successful_validation(run_dir, replay)

    monkeypatch.setattr(runner, "run_once", fake_replay)
    result = runner.run_replay_gate(tmp_path / "manifest.json", manifest)
    assert result["replays_planned"] == result["replays_passed"] == 8
    assert calls == [
        (seed, arm, 10, "existing_mode_no_effect_replay")
        for seed in (1, 2, 3, 4)
        for arm in ("ingress_dla", "dla")
    ]
    assert not (tmp_path / "raw" / "cells").exists()


def test_global_smoke_gate_runs_exactly_eight_ten_step_runs_and_no_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    mark_replay_gate_passed(manifest)
    install_smoke_validation_stubs(monkeypatch)
    calls: list[tuple[int, int, str, int]] = []
    monkeypatch.setattr(
        runner,
        "preflight",
        lambda *args, **kwargs: {"identities": {"approved": True}},
    )

    def fake_run_once(
        manifest: dict,
        cell: dict,
        run_dir: Path,
        *,
        max_steps: int,
        phase: str,
        repeat: int,
        identities: dict,
    ) -> dict:
        calls.append((int(cell["fleet_seed"]), repeat, phase, max_steps))
        return successful_validation(run_dir, cell)

    monkeypatch.setattr(runner, "run_once", fake_run_once)
    result = run_smoke_gate(tmp_path / "manifest.json", manifest)
    assert result["status"] == "passed"
    assert result["smokes_planned"] == result["smokes_passed"] == 8
    assert calls == [
        (seed, repeat, "new_arm_smoke", 10) for seed in (1, 2, 3, 4) for repeat in (1, 2)
    ]
    assert not list((tmp_path / "raw" / "cells").rglob("full"))


def test_smoke_failure_stops_later_smokes_and_blocks_every_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    mark_replay_gate_passed(manifest)
    install_smoke_validation_stubs(monkeypatch)
    monkeypatch.setattr(
        runner,
        "preflight",
        lambda *args, **kwargs: {"identities": {"approved": True}},
    )
    calls = 0

    def fail_third(
        manifest: dict,
        cell: dict,
        run_dir: Path,
        *,
        max_steps: int,
        phase: str,
        repeat: int,
        identities: dict,
    ) -> dict:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("synthetic smoke failure")
        return successful_validation(run_dir, cell)

    monkeypatch.setattr(runner, "run_once", fail_third)
    with pytest.raises(RuntimeError, match="synthetic smoke failure"):
        run_smoke_gate(tmp_path / "manifest.json", manifest)
    assert calls == 3
    raw_root = tmp_path / "raw"
    assert (raw_root / "smoke_gate_failure.json").is_file()
    assert not (raw_root / "smoke_gate_status.json").exists()
    monkeypatch.setattr(
        runner, "preflight", lambda *args, **kwargs: pytest.fail("preflight called")
    )
    for cell in manifest["full_cell_order"]:
        with pytest.raises(RuntimeError, match="global smoke gate is absent"):
            run_full_cell(tmp_path / "manifest.json", manifest, cell)


def test_global_smoke_gate_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    mark_replay_gate_passed(manifest)
    write_status(tmp_path / "raw" / "smoke_gate_status.json", {"status": "passed"})
    monkeypatch.setattr(runner, "run_once", lambda *args, **kwargs: pytest.fail("run called"))
    with pytest.raises(FileExistsError, match="smoke-gate evidence"):
        run_smoke_gate(tmp_path / "manifest.json", manifest)


def test_full_cell_refuses_when_replay_gate_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    monkeypatch.setattr(runner, "run_once", lambda *args, **kwargs: pytest.fail("run called"))
    with pytest.raises(RuntimeError, match="global replay gate is absent"):
        run_full_cell(tmp_path / "manifest.json", manifest, manifest["full_cell_order"][0])


def test_full_cell_refuses_when_smoke_gate_is_absent_or_failed(tmp_path: Path) -> None:
    manifest = execution_manifest(tmp_path)
    mark_replay_gate_passed(manifest)
    with pytest.raises(RuntimeError, match="global smoke gate is absent"):
        run_full_cell(tmp_path / "manifest.json", manifest, manifest["full_cell_order"][0])
    write_status(tmp_path / "raw" / "smoke_gate_status.json", {"status": "failed"})
    with pytest.raises(RuntimeError, match="global smoke gate has not passed"):
        run_full_cell(tmp_path / "manifest.json", manifest, manifest["full_cell_order"][0])


def test_full_cell_requires_all_eight_smoke_records(tmp_path: Path) -> None:
    manifest = execution_manifest(tmp_path)
    mark_replay_gate_passed(manifest)
    write_status(
        tmp_path / "raw" / "smoke_gate_status.json",
        {"status": "passed", "smokes_planned": 8, "smokes_passed": 8, "records": []},
    )
    with pytest.raises(RuntimeError, match="smoke validation"):
        verify_all_smoke_evidence(manifest)


def test_all_eight_smokes_are_revalidated_before_full_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    mark_replay_gate_passed(manifest)
    install_smoke_validation_stubs(monkeypatch)
    validation_calls: list[Path] = []
    records = []
    for cell in manifest["full_cell_order"]:
        root = runner.cell_root(manifest, cell)
        write_status(root / "smoke_validation.json", {"status": "passed", "cell": cell})
        for repeat in (1, 2):
            (root / "smoke" / f"run_{repeat}").mkdir(parents=True)
        records.append(
            {
                "cell": cell,
                "smoke_validation": str(root / "smoke_validation.json"),
                "smokes_passed": 2,
            }
        )

    def fake_validate(run_dir: Path, *, manifest: dict, run: dict, expected_steps: int) -> dict:
        validation_calls.append(run_dir)
        return successful_validation(run_dir, run)

    monkeypatch.setattr(runner, "validate_run", fake_validate)
    write_status(
        tmp_path / "raw" / "smoke_gate_status.json",
        {
            "status": "passed",
            "smokes_planned": 8,
            "smokes_passed": 8,
            "records": records,
        },
    )
    assert verify_all_smoke_evidence(manifest)["status"] == "passed"
    assert len(validation_calls) == 8


def test_second_full_cell_requires_first_full_cell_pass(tmp_path: Path) -> None:
    manifest = execution_manifest(tmp_path)
    with pytest.raises(RuntimeError, match="prior E2d cell did not pass"):
        verify_prior_full_cell_order(manifest, 2)
    first = manifest["full_cell_order"][0]
    write_status(runner.cell_root(manifest, first) / "cell_status.json", {"status": "passed"})
    verify_prior_full_cell_order(manifest, 2)


def test_full_cell_is_full_only_and_preserves_smokes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    cell = manifest["full_cell_order"][0]
    root = runner.cell_root(manifest, cell)
    smoke_marker = root / "smoke" / "run_1" / "marker"
    smoke_marker.parent.mkdir(parents=True)
    smoke_marker.write_text("immutable smoke", encoding="utf-8")
    monkeypatch.setattr(runner, "verify_all_smoke_evidence", lambda manifest: {"status": "passed"})
    monkeypatch.setattr(
        runner,
        "preflight",
        lambda *args, **kwargs: {"identities": {"approved": True}},
    )
    monkeypatch.setattr(
        runner,
        "compare_identity_to_reference",
        lambda candidate, reference, manifest: {"pass": True},
    )
    monkeypatch.setattr(runner, "reference_record", lambda *args: {})
    monkeypatch.setattr(
        runner,
        "validate_cell",
        lambda manifest, cell: {"status": "passed", "cell": cell},
    )
    calls: list[tuple[str, int]] = []

    def fake_full(
        manifest: dict,
        cell: dict,
        run_dir: Path,
        *,
        max_steps: int,
        phase: str,
        repeat: int,
        identities: dict,
    ) -> dict:
        calls.append((phase, max_steps))
        return {
            "status": "passed",
            "run_dir": str(run_dir),
            "summary": {"wall_s": 1.0},
        }

    monkeypatch.setattr(runner, "run_once", fake_full)
    result = run_full_cell(tmp_path / "manifest.json", manifest, cell)
    assert result["status"] == "passed"
    assert calls == [("new_arm_full", 3600)]
    assert smoke_marker.read_text(encoding="utf-8") == "immutable smoke"


def test_full_cell_refuses_to_overwrite_existing_full_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = execution_manifest(tmp_path)
    cell = manifest["full_cell_order"][0]
    root = runner.cell_root(manifest, cell)
    (root / "full").mkdir(parents=True)
    monkeypatch.setattr(runner, "verify_all_smoke_evidence", lambda manifest: {"status": "passed"})
    with pytest.raises(FileExistsError, match="full-cell evidence"):
        run_full_cell(tmp_path / "manifest.json", manifest, cell)


def test_runner_exposes_only_three_phase_interfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(authorised_manifest()), encoding="utf-8")
    calls: list[tuple[str, int | None]] = []
    monkeypatch.setattr(
        runner,
        "run_replay_gate",
        lambda path, manifest: calls.append(("replay", None)) or {"status": "passed"},
    )
    monkeypatch.setattr(
        runner,
        "run_smoke_gate",
        lambda path, manifest: calls.append(("smoke", None)) or {"status": "passed"},
    )
    monkeypatch.setattr(
        runner,
        "run_full_cell",
        lambda path, manifest, cell: (
            calls.append(("full", int(cell["cell_index"]))) or {"status": "passed"}
        ),
    )
    for option in ("--run-replay-gate", "--run-smoke-gate"):
        monkeypatch.setattr(sys, "argv", ["runner", "--manifest", str(manifest_path), option])
        assert runner_main() == 0
    monkeypatch.setattr(
        sys,
        "argv",
        ["runner", "--manifest", str(manifest_path), "--full-cell-index", "3"],
    )
    assert runner_main() == 0
    assert calls == [("replay", None), ("smoke", None), ("full", 3)]
    monkeypatch.setattr(
        sys,
        "argv",
        ["runner", "--manifest", str(manifest_path), "--cell-index", "1"],
    )
    with pytest.raises(SystemExit):
        runner_main()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"cell_index": 1, "fleet_seed": 0, "arm": "per_task_dla"}, "full-cell"),
        ({"cell_index": 1, "fleet_seed": 1, "arm": "off"}, "full-cell"),
        ({"cell_index": 1, "fleet_seed": 1, "arm": "dla"}, "full-cell"),
    ],
)
def test_manifest_rejects_seed0_and_prohibited_full_arms(mutation: dict, message: str) -> None:
    manifest = authorised_manifest()
    manifest["full_cell_order"][0] = mutation
    with pytest.raises(RuntimeError, match=message):
        validate_manifest_contract(manifest)


def test_format_command_binds_only_declared_run(tmp_path: Path) -> None:
    manifest = authorised_manifest()
    run = manifest["full_cell_order"][2]
    command = format_command(manifest, run, tmp_path / "run", max_steps=3600)
    assert command[command.index("--rsu-lb") + 1] == "per_task_dla"
    assert command[command.index("--fleet-seed") + 1] == "3"
    assert command[command.index("--max-steps") + 1] == "3600"


def test_storage_ratio_gate_fails_below_twice_projection() -> None:
    projected = 850_000_000
    required = required_free_bytes(projected)
    assert required == 1_700_000_000
    assert storage_gate_passes(required, projected)
    assert not storage_gate_passes(required - 1, projected)


def test_write_json_new_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    write_json_new(path, {"first": True})
    with pytest.raises(FileExistsError):
        write_json_new(path, {"first": False})
    assert json.loads(path.read_text()) == {"first": True}


def test_review_gate_requires_exact_approve_and_all_three_identities(
    tmp_path: Path,
) -> None:
    review = tmp_path / "review.json"
    identities = {"traffictwin_commit": "t" * 40, "vec_env_commit": "v" * 40}
    review.write_text(
        json.dumps(
            {
                "verdict": "APPROVE",
                "traffictwin_commit": identities["traffictwin_commit"],
                "vec_env_commit": identities["vec_env_commit"],
                "manifest_sha256": "m" * 64,
            }
        )
    )
    assert verify_review_gate(review, identities, "m" * 64)["verdict"] == "APPROVE"
    review.write_text(
        json.dumps(
            {
                "verdict": "APPROVE_WITH_MINOR_FIXES",
                "traffictwin_commit": identities["traffictwin_commit"],
                "vec_env_commit": identities["vec_env_commit"],
                "manifest_sha256": "m" * 64,
            }
        )
    )
    with pytest.raises(RuntimeError, match="APPROVE identity mismatch"):
        verify_review_gate(review, identities, "m" * 64)


def test_superseded_approval_and_manifest_cannot_authorise_corrected_package(
    tmp_path: Path,
) -> None:
    old_review = tmp_path / "claude_review_verdict.json"
    old_review.write_text(
        json.dumps(
            {
                "verdict": "APPROVE",
                "traffictwin_commit": "6443b936064dba2766dcb8dee9146b246bc769bf",
                "vec_env_commit": "2f63706f46319433a2ba3af1df97afd0e56a95d1",
                "manifest_sha256": (
                    "b2d04fa31ae40fb0519ebd019817599be428392bf6b1ee98656740ea509aa420"
                ),
            }
        ),
        encoding="utf-8",
    )
    corrected = {
        "traffictwin_commit": "n" * 40,
        "vec_env_commit": "2f63706f46319433a2ba3af1df97afd0e56a95d1",
    }
    with pytest.raises(RuntimeError, match="APPROVE identity mismatch"):
        verify_review_gate(old_review, corrected, "m" * 64)


def test_campaign_initialisation_preserves_versioned_historical_review_receipt(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"version": 2}), encoding="utf-8")
    raw_root = tmp_path / "raw"
    old_review = raw_root / "independent_review" / "claude_review_verdict.json"
    write_status(old_review, {"verdict": "APPROVE", "historical": True})
    old_bytes = old_review.read_bytes()
    initialise_or_verify_campaign_root(
        manifest_path,
        {"outputs": {"raw_root": str(raw_root)}},
        initialise=True,
    )
    assert old_review.read_bytes() == old_bytes
    assert (raw_root / "manifest_snapshot.json").read_bytes() == manifest_path.read_bytes()


def test_reference_hash_verification_detects_mutation(tmp_path: Path) -> None:
    payloads = {
        "summary.json": b"{}\n",
        "per_step.npz": b"step",
        "per_task.npz": b"task",
        "checksums.sha256": b"ledger",
    }
    for name, payload in payloads.items():
        (tmp_path / name).write_bytes(payload)
    import hashlib

    record = {
        "root": str(tmp_path),
        "summary_sha256": hashlib.sha256(payloads["summary.json"]).hexdigest(),
        "per_step_sha256": hashlib.sha256(payloads["per_step.npz"]).hexdigest(),
        "per_task_sha256": hashlib.sha256(payloads["per_task.npz"]).hexdigest(),
        "checksums_sha256": hashlib.sha256(payloads["checksums.sha256"]).hexdigest(),
    }
    assert verify_reference_record(record)["pass"]
    (tmp_path / "per_task.npz").write_bytes(b"changed")
    assert not verify_reference_record(record)["pass"]


def test_decision_record_preserves_construct_and_claim_boundaries() -> None:
    record = (
        Path(__file__).resolve().parents[1]
        / "docs/evaluation/e2d/e2d_per_task_placement_robustness_decision_record_2026-08-11.md"
    ).read_text()
    for phrase in (
        "per-task sequential least-busy",
        "shortest-workload placement",
        "all configured RSUs",
        "lowest RSU index",
        "Individual tasks are never statistical replicates",
        "not confirmed physical task-result return",
        "exact `APPROVE`",
    ):
        assert phrase in record


def test_frozen_manifest_sidecar_and_authorised_inventory() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    sidecar = MANIFEST_PATH.with_suffix(".sha256")
    assert sidecar.read_text().split()[0] == sha256(MANIFEST_PATH)
    validate_manifest_contract(manifest)
    assert manifest["design"]["seed0_authorised"] is False
    assert manifest["analysis"]["task_level_pseudoreplication_allowed"] is False
    assert manifest["review_gate"]["required_verdict"] == "APPROVE"
    assert manifest["compute_and_storage"]["projected_total_evaluator_wall_seconds"] < 108000
    assert (
        manifest["compute_and_storage"]["initial_observed_free_bytes"]
        >= manifest["compute_and_storage"]["minimum_initial_free_bytes"]
    )


def test_all_reused_e2c_reference_hashes_are_bound_and_verify() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    checked = 0
    for seed in (1, 2, 3, 4):
        for arm in ("ingress_dla", "dla"):
            for phase in ("smoke", "full"):
                assert verify_reference_record(reference_record(manifest, seed, arm, phase))["pass"]
                checked += 1
    assert checked == 16


def test_manifest_binds_exact_source_and_input_hashes() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert (
        sha256(Path(manifest["paths"]["evaluator"]))
        == manifest["repositories"]["vec_env"]["evaluator_sha256"]
    )
    assert (
        sha256(Path(manifest["paths"]["per_task_placement_helper"]))
        == manifest["repositories"]["vec_env"]["per_task_helper_sha256"]
    )
    assert (
        sha256(Path(manifest["inputs"]["actor"]["path"])) == manifest["inputs"]["actor"]["sha256"]
    )
    assert (
        sha256(Path(manifest["inputs"]["trace"]["path"])) == manifest["inputs"]["trace"]["sha256"]
    )
