from __future__ import annotations

import csv
import shutil
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.tos_helpers import write_tos_package
from traffictwin.config.capabilities import CapabilitySupport
from traffictwin.domain.enums import TaskClass
from traffictwin.integration.tos import (
    build_tos_evidence_pack,
    build_tos_metric_trace,
    get_evaluation_source_row,
    list_instrumented_runs,
    load_replay_frame,
    load_replay_series,
    load_rsu_replay_series,
    load_task_sample,
    metric_collection_from_evaluation,
    read_evaluation_runs,
    read_npz_headers,
    tos_data_capability_manifest,
    tos_source_contract,
    validate_tos_package,
)
from traffictwin.integration.tos.models import (
    TOS_SOURCE_METRIC_VERSION,
    TOS_VEC_ENV_EVIDENCE_COMMIT,
)
from traffictwin.integration.tos.readers import TosPackageError, safe_package_path
from traffictwin.metrics.results import MetricStatus, UnavailableReason
from traffictwin.provenance.graph_export import (
    build_provenance_graph_view,
    provenance_graph_to_graphml,
)
from traffictwin.provenance.models import ProvenanceNodeType, ProvenanceStatus
from traffictwin.rules.engine import evaluate_rules

FIXED_TIME = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def test_tos_models_and_capabilities_are_conservative(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    rows = read_evaluation_runs(package)
    manifest = tos_data_capability_manifest()

    assert len(rows) == 2
    assert rows[0].run_id == "tos:baseline:wd_am:uk2030:fs0"
    assert rows[0].completion == 0.9
    assert manifest.supports.direct_launch is CapabilitySupport.FALSE
    assert manifest.supports.run_bundle_import is CapabilitySupport.FALSE
    assert manifest.supports.streaming_canonicalisation is CapabilitySupport.FALSE
    assert manifest.supports.canonical_table_caching is CapabilitySupport.FALSE
    assert manifest.supports.environment_doctor is CapabilitySupport.FALSE
    assert manifest.supports.ro_crate_archival_export is CapabilitySupport.FALSE
    assert manifest.supports.generalised_external_source_contract is CapabilitySupport.TRUE
    assert manifest.supports.time_windowed_metrics is CapabilitySupport.FALSE
    assert manifest.supports.latency_percentile_family is CapabilitySupport.FALSE
    assert manifest.supports.energy_metric_family is CapabilitySupport.FALSE
    assert manifest.supports.fairness_metric_family is CapabilitySupport.FALSE
    assert manifest.supports.spatial_rsu_metric_family is CapabilitySupport.FALSE
    assert manifest.supports.custom_metric_plugin_api is CapabilitySupport.FALSE
    assert manifest.supports.declarative_rule_authoring is CapabilitySupport.TRUE
    assert manifest.supports.fairness_disparity_diagnosis is CapabilitySupport.FALSE
    assert manifest.supports.energy_anomaly_diagnosis is CapabilitySupport.FALSE
    assert manifest.supports.nearest_flip_analysis is CapabilitySupport.FALSE
    assert manifest.supports.threshold_sensitivity_sweep is CapabilitySupport.FALSE
    assert manifest.supports.cross_rule_reasoning is CapabilitySupport.FALSE
    assert manifest.supports.paired_statistical_study is CapabilitySupport.FALSE
    assert manifest.supports.n_way_policy_ranking is CapabilitySupport.FALSE
    assert manifest.supports.equivalence_testing is CapabilitySupport.FALSE
    assert manifest.supports.difference_provenance is CapabilitySupport.FALSE
    assert manifest.supports.provenance_graph_export is CapabilitySupport.TRUE
    assert manifest.supports.provenance_completeness_score is CapabilitySupport.FALSE
    assert manifest.supports.rsu_capacity is CapabilitySupport.UNKNOWN


def test_tos_package_validation_and_npz_headers(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    report = validate_tos_package(package, deep=True, clock=fixed_clock)
    headers = read_npz_headers(
        package / "instrumented/perstep/baseline_uk2030_wd_am_fs0_perstep.npz"
    )

    assert report.may_import_summaries
    assert report.inventory.evaluation_rows == 2
    assert report.inventory.perstep_files == 2
    assert report.inventory.pertask_files == 1
    assert report.inspected_at == FIXED_TIME
    codes = {item.code for item in report.findings}
    assert "TOS_RSU_SEMANTICS_CONFIRMED" in codes
    assert "TOS_TRACE_UNITS_CONFIRMED" in codes
    assert "TOS_INSTRUMENTED_WRITER_UNAVAILABLE" in codes
    assert report.semantics_source_commit == TOS_VEC_ENV_EVIDENCE_COMMIT
    assert {header.name for header in headers} >= {"times", "rsu_load", "veh_action"}


def test_tos_validation_rejects_unsupported_engine(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    master = package / "evals/eval_results_master.csv"
    rows = list(csv.DictReader(master.open(encoding="utf-8")))
    rows[0]["engine_version"] = "superseded"
    with master.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = validate_tos_package(package, deep=False, clock=fixed_clock)

    assert not report.may_import_summaries
    assert "TOS_ENGINE_VERSION_UNSUPPORTED" in {item.code for item in report.findings}


def test_tos_validation_rejects_duplicate_run_identifier(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    master = package / "evals/eval_results_master.csv"
    rows = list(csv.DictReader(master.open(encoding="utf-8")))
    rows.append(dict(rows[0]))
    with master.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = validate_tos_package(package, deep=False, clock=fixed_clock)

    assert not report.may_import_summaries
    assert "TOS_RUN_ID_DUPLICATE" in {item.code for item in report.findings}


def test_tos_path_and_npz_member_safety(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    with pytest.raises(TosPackageError, match="escapes"):
        safe_package_path(package, "../outside")
    malicious = tmp_path / "unsafe.npz"
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("../unsafe.npy", b"not-an-array")
    with pytest.raises(TosPackageError, match="unsafe NPZ member"):
        read_npz_headers(malicious)


def test_invalid_instrumented_archive_disables_replay_capability(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    source = package / "instrumented/perstep/baseline_uk2030_wd_am_fs0_perstep.npz"
    source.write_bytes(b"not an NPZ archive")

    report = validate_tos_package(package, deep=True, clock=fixed_clock)

    assert report.may_import_summaries
    assert not report.capabilities.instrumented_historical_replay
    assert "TOS_PERSTEP_INVALID" in {item.code for item in report.findings}


def test_source_summary_metrics_and_partial_diagnostics(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    report = validate_tos_package(package, deep=False, clock=fixed_clock)
    row = read_evaluation_runs(package)[0]
    assert report.package_fingerprint is not None
    collection = metric_collection_from_evaluation(
        row,
        report.package_fingerprint,
        clock=fixed_clock,
    )
    by_key = collection.by_key()

    assert collection.metric_version == TOS_SOURCE_METRIC_VERSION
    assert by_key["tos.task.deadline_success.rate"].value == 0.9
    assert by_key["task.completion.rate"].status.value == "unavailable"
    assert by_key["task.offload.rate"].value == 0.5
    assert by_key["task.incomplete.rate"].status is MetricStatus.UNAVAILABLE
    assert by_key["infra.utilisation.mean"].status is MetricStatus.UNAVAILABLE
    assert by_key["task.energy.per_completed_j"].metadata["source_energy_j_per_arrival"] == 0.4
    assert by_key["spatial.rsu.task.count_by_target"].reason_codes == [
        UnavailableReason.TASK_RSU_TARGET_CONTRACT_UNAVAILABLE
    ]
    assert by_key["spatial.vehicle.observation_count_by_grid_cell"].reason_codes == [
        UnavailableReason.VEHICLE_SPATIAL_GRID_CONTRACT_UNAVAILABLE
    ]

    pack = build_tos_evidence_pack(row, report, collection, clock=fixed_clock)
    diagnosis = evaluate_rules(pack, clock=fixed_clock)
    statuses = {item.rule_id: item.status.value for item in diagnosis.results}
    assert statuses == {
        "R0": "triggered",
        "R1": "insufficient_evidence",
        "R2": "insufficient_evidence",
        "R3": "insufficient_evidence",
        "R4": "insufficient_evidence",
        "R5": "insufficient_evidence",
        "R6": "insufficient_evidence",
        "R7": "insufficient_evidence",
        "R8": "insufficient_evidence",
    }


def test_tos_replay_and_task_samples_are_source_views(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    key = "baseline_uk2030_wd_am_fs0"
    series = load_replay_series(package, key)
    frame = load_replay_frame(package, key, 0, max_vehicles=1)
    rsu_series = load_rsu_replay_series(package, key)
    sample = load_task_sample(package, key, limit=3)

    assert len(series) == 3
    assert series[1].deadline_met == 0
    assert frame.total_active_vehicle_slots == 2
    assert len(frame.vehicles) == 1
    assert frame.vehicles[0].slot_reference == "slot:0@time-index:0"
    assert frame.vehicles[0].position_unit == "m"
    assert frame.vehicles[0].speed_unit == "m/s"
    assert frame.rsus[0].semantics_status == "confirmed_from_vec_env_source"
    assert frame.rsus[0].load_pressure_fraction == pytest.approx(0.2)
    assert len(rsu_series) == 3
    assert rsu_series[1].active_task_count == 2
    assert rsu_series[1].remaining_compute_backlog_ms == pytest.approx(1200.0)
    assert rsu_series[1].concurrency_pressure_fraction == pytest.approx(0.4)
    assert sample.total_active_entries == 4
    assert sample.deadline_consistency_verified
    assert [item.task_class for item in sample.observations] == [
        TaskClass.T1,
        TaskClass.T2,
        TaskClass.T3,
    ]
    assert [item.arrival_time_s for item in sample.observations] == [0.0, 0.0, 1.0]
    assert [item.decision for item in sample.observations] == ["local", "v2i", "local"]
    assert sample.observations[0].decision_source_index == "[0,0]"


def test_tos_source_contract_records_evidence_and_launch_blockers() -> None:
    contract = tos_source_contract()
    by_field = {item.field: item for item in contract.fields}

    assert contract.evidence_commit == TOS_VEC_ENV_EVIDENCE_COMMIT
    assert contract.execution.direct_launch is CapabilitySupport.FALSE
    assert by_field["rsu_load"].meaning == "Number of in-flight tasks assigned to an RSU."
    assert by_field["speed"].unit == "m/s"
    assert any("checkpoint" in blocker.lower() for blocker in contract.execution.blockers)
    assert "trip or journey-time records" in contract.unavailable_outputs


def test_tos_metric_trace_and_source_row_are_explicitly_aggregate(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    report = validate_tos_package(package, deep=False, clock=fixed_clock)
    row = read_evaluation_runs(package)[0]
    assert report.package_fingerprint is not None
    collection = metric_collection_from_evaluation(
        row,
        report.package_fingerprint,
        clock=fixed_clock,
    )
    trace = build_tos_metric_trace(
        row,
        collection,
        report,
        "tos.task.deadline_success.rate",
        clock=fixed_clock,
    )
    graph_view = build_provenance_graph_view(trace)
    preview = get_evaluation_source_row(package, 2, report)

    assert trace.completeness.overall.value == "partial"
    assert any(node.node_type is ProvenanceNodeType.SOURCE_ROW for node in trace.nodes)
    canonical = next(
        node for node in trace.nodes if node.node_type is ProvenanceNodeType.CANONICAL_TABLE
    )
    assert canonical.status is ProvenanceStatus.UNAVAILABLE
    assert "/Users/" not in trace.to_json()
    assert graph_view.root_node_id == trace.root_node_id
    assert graph_view.omitted_node_count == 0
    assert "<graphml" in provenance_graph_to_graphml(graph_view)
    assert preview.status is ProvenanceStatus.AVAILABLE
    assert preview.inclusion_status == "included_as_source_summary"
    assert preview.canonical_record_type is None


def test_instrumented_run_listing_is_stable(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")

    assert list_instrumented_runs(package) == [
        "baseline_uk2030_wd_am_fs0",
        "caps_mappo_uk2030_wd_am_fs0",
    ]


def test_package_git_commit_stays_off_the_forking_spawn_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The git lookup must keep CPython on ``posix_spawn`` rather than ``fork``.

    This asserts the call shape rather than an outcome, deliberately. The defect
    it guards (``docs/integration/tos_reader_fork_diagnosis.md``) faults a
    transient child process on macOS while the parent survives with its normal
    return value, so there is no behavioural assertion that can catch a
    regression — only the spawn conditions that cause it.
    """

    from traffictwin.integration.tos import readers

    recorded: dict[str, object] = {}
    completed = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout=f"{'a' * 40}\n", stderr=""
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded["command"] = command
        recorded.update(kwargs)
        return completed

    # ``readers`` calls ``subprocess.run`` through the module, so patching the
    # stdlib attribute reaches it without asserting on a private binding.
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert readers.package_git_commit(tmp_path) == "a" * 40

    # CPython's posix_spawn conditions (subprocess.py, Popen._execute_child):
    # close_fds false, no preexec_fn, no pass_fds, no cwd, and an executable
    # carrying a directory component.
    assert recorded["close_fds"] is False
    assert "preexec_fn" not in recorded
    assert "pass_fds" not in recorded
    assert "cwd" not in recorded
    command = recorded["command"]
    assert isinstance(command, list)
    assert Path(command[0]).is_absolute()
    # The package is addressed with `git -C`, never by changing directory.
    assert command[1:] == ["-C", str(tmp_path.resolve()), "rev-parse", "HEAD"]


def test_package_git_commit_return_values_are_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both branches still answer exactly as they did before the spawn repair."""

    from traffictwin.integration.tos import readers

    def refusing_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(128, command)

    monkeypatch.setattr(subprocess, "run", refusing_run)
    assert readers.package_git_commit(tmp_path) is None

    def noisy_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="not-a-sha\n")

    monkeypatch.setattr(subprocess, "run", noisy_run)
    assert readers.package_git_commit(tmp_path) is None

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert readers.package_git_commit(tmp_path) is None
