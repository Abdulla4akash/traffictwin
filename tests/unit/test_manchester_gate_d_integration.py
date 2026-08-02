"""Gate-D integration, lineage, privacy and refusal tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.gate_d_integration import (
    ManchesterGateDIntegrationPacket,
    build_sensitivity_tables,
)
from traffictwin.integration.manchester.owner_candidate_contracts import (
    comparison_contract_fingerprint,
    comparison_contract_is_registered,
)
from traffictwin.ui.manchester_gate_d_services import (
    SOURCE_REFS,
    ManchesterGateDConsoleError,
    load_manchester_gate_d_console,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _packet() -> ManchesterGateDIntegrationPacket:
    return load_manchester_gate_d_console(REPO_ROOT).packet


def test_packet_is_deterministic_complete_and_changes_no_capability_truth() -> None:
    packet = _packet()
    assert packet.digest() == _packet().digest()
    assert packet.capability_ids == ("MAN-09", "MAN-10", "MAN-11")
    assert packet.capability_status == "planned"
    assert packet.gate_d_state == "foundation_only"
    assert packet.maximum_policy_ceiling == "owner_approved_candidate"
    assert packet.performs_network_access is False
    assert packet.performs_private_artifact_access is False
    assert packet.performs_review is False
    assert packet.performs_execution is False
    assert packet.registers_contract is False
    assert packet.creates_baseline is False
    assert packet.creates_comparison_result is False
    assert packet.creates_scientific_evidence is False


def test_source_bindings_are_exact_role_separated_and_not_llm_output() -> None:
    packet = _packet()
    assert tuple(item.repository_ref for item in packet.source_bindings) == SOURCE_REFS
    assert len({item.sha256 for item in packet.source_bindings}) == len(SOURCE_REFS)
    assert {item.role for item in packet.source_bindings} == {
        "decision_worksheet",
        "candidate_measurement",
        "accepted_source_derived_candidate",
        "restoration_receipt",
    }
    assert all(item.llm_output is False for item in packet.source_bindings)
    assert all(item.creates_evidence is False for item in packet.source_bindings)


def test_both_measured_sensitivity_populations_retain_exact_denominators() -> None:
    tables = _packet().sensitivity_tables
    assert tuple(item.population for item in tables) == (742, 305)
    assert all(tuple(row.radius_m for row in item.rows) == (10, 20, 30, 50, 100) for item in tables)
    known, real = tables
    assert [row.median_candidates for row in known.rows] == [6, 8, 12, 23, 61]
    assert [row.sites_with_candidate for row in real.rows] == [298, 304, 305, 305, 305]
    assert real.rows[-1].max_candidates == 460
    assert all(item.threshold_selected_by_table is False for item in tables)
    assert all(item.scientific_validation is False for item in tables)


def test_sensitivity_is_bound_to_the_exact_worksheet_digest() -> None:
    packet = _packet()
    digest = packet.source_bindings[0].sha256
    assert packet.sensitivity_tables == build_sensitivity_tables(digest)
    payload: dict[str, Any] = json.loads(packet.canonical_json())
    payload["sensitivity_tables"][1]["rows"][0]["sites_with_candidate"] = 299
    with pytest.raises(ValidationError, match="re-derived from the fixed worksheet"):
        ManchesterGateDIntegrationPacket.model_validate_json(json.dumps(payload))


def test_map_policy_reconciles_all_305_sites_without_promoting_acceptance() -> None:
    mapping = _packet().mapping_policy
    assert mapping.observations == 305
    assert mapping.owner_policy_accepted == 131
    assert mapping.awaiting_manual_review == 165
    assert mapping.no_suitable_candidate == 9
    assert mapping.unavailable_missing_evidence == 0
    assert mapping.strict_acceptances == 106
    assert mapping.override_acceptances == 25
    assert mapping.override_applied_edges == 51
    assert mapping.readmitted_edges == 51
    assert mapping.refused_edges == 1339
    assert mapping.automatic_acceptance is False
    assert mapping.analyst_accepted is False
    assert mapping.human_accepted is False
    assert mapping.supervisor_approved is False


def test_map_policy_refuses_a_coherently_rebalanced_but_unrecorded_population() -> None:
    packet = _packet()
    payload: dict[str, Any] = json.loads(packet.canonical_json())
    payload["mapping_policy"]["owner_policy_accepted"] = 130
    payload["mapping_policy"]["awaiting_manual_review"] = 166
    with pytest.raises(ValidationError, match="committed 305-site measurement"):
        ManchesterGateDIntegrationPacket.model_validate_json(json.dumps(payload))


def test_analyst_review_keeps_every_row_pending_and_no_candidate_rows_visible() -> None:
    review = _packet().analyst_review
    assert review.queue_total == 174
    assert review.decided_total == 0
    assert review.pending_total == 174
    assert review.awaiting_manual_review == 165
    assert review.no_candidate_preserved_total == 9
    assert review.review_state == "pending_named_person_review"
    assert review.decision_records_embedded is False
    assert review.bulk_operation is False


def test_temporal_profile_retains_source_clock_missingness_and_partition_accounting() -> None:
    profile = _packet().temporal_profile
    assert profile.evidence_class == "accepted_real_snapshot_derived_candidate"
    assert profile.time_basis == "local_clock_hour"
    assert profile.utc_instant_available is False
    assert profile.interval_seconds == 3600
    assert profile.missing_as_zero is False
    assert profile.offered_rows == profile.admitted_rows == 39_072
    assert profile.excluded_rows == profile.missing_cells == 0
    assert profile.observed_cells == 39_072
    assert profile.measured_zero_cells == 166
    assert profile.coverage == 1
    assert tuple(item.sites for item in profile.partitions) == (238, 67)
    assert tuple(item.observed_cells for item in profile.partitions) == (30_528, 8_544)
    assert profile.dft_time_semantics_blocker == "GA-DFT-1"
    assert profile.webtris_time_semantics_blocker == "GA-WT-1"
    assert profile.calibration_use_available is False
    assert profile.baseline_available is False


def test_calibration_orchestration_connects_exact_intervals_but_remains_blocked() -> None:
    calibration = _packet().calibration
    assert calibration.interval_adapter == "one_hour_cell_to_exact_3600_second_interval"
    assert calibration.output_unit == "vehicles_per_interval"
    assert calibration.resampling is False
    assert calibration.timezone_conversion is False
    assert calibration.source_fusion is False
    assert calibration.interpolation is False
    assert calibration.missing_filled_with_zero is False
    assert tuple(item.dependency_id for item in calibration.dependencies) == (
        "temporal_profile",
        "human_mapping_review",
        "projection_and_mapping_binding",
        "calibration_method_contract",
        "viable_demand_and_candidate_runs",
        "calibration_contract_registration",
    )
    assert calibration.dependencies[0].satisfied_for_downstream is True
    assert all(not item.satisfied_for_downstream for item in calibration.dependencies[1:])
    assert calibration.calibration_executed is False
    assert calibration.objective_available is False


def test_baseline_candidate_workflow_is_versioned_and_cannot_manufacture_a_candidate() -> None:
    baseline = _packet().baseline
    assert baseline.state == "unavailable_missing_inputs"
    assert baseline.candidate_fingerprint is None
    assert len(baseline.required_order) == 6
    assert len(baseline.missing_requirements) == 5
    assert baseline.baseline_created is False
    assert baseline.baseline_accepted is False
    assert baseline.sumo_executed is False
    assert baseline.automatic_acceptance is False
    assert baseline.scientific_evidence is False


def test_comparison_workflow_reuses_exact_unregistered_contract_with_no_values() -> None:
    workflow = _packet().comparison
    contract = workflow.contract
    assert workflow.contract_fingerprint == comparison_contract_fingerprint()
    assert comparison_contract_is_registered() is False
    assert workflow.registration_state == "candidate_unregistered"
    assert workflow.contract_registered is False
    assert contract.observed_source == "dft_raw_count"
    assert contract.scope_label == "manchester-local-authority"
    assert contract.time_basis_label == "local-clock-hour"
    assert contract.interval_duration_s == 3600
    assert contract.missing_policy == "exclude_unpaired_never_zero"
    assert str(contract.minimum_observed_coverage) == "0.800"
    assert tuple(item.metric for item in workflow.metrics) == ("mae", "rmse")
    assert all(item.value is None and item.status == "unavailable" for item in workflow.metrics)
    assert workflow.geh_in_contract is False
    assert workflow.geh_threshold_available is False
    assert workflow.comparison_executed is False
    assert workflow.result_available is False
    assert workflow.model_validity_established is False


def test_lineage_preserves_independent_candidate_stage_and_every_downstream_gap() -> None:
    lineage = _packet().lineage
    assert tuple(item.position for item in lineage) == tuple(range(1, 8))
    assert tuple(item.stage for item in lineage) == (
        "observation_source",
        "mapping_candidate",
        "human_mapping_review",
        "temporal_profile",
        "calibration",
        "baseline_candidate",
        "observed_simulated_comparison",
    )
    assert [item.state for item in lineage[:4]] == [
        "candidate_available",
        "candidate_available",
        "blocked_human_review",
        "candidate_available",
    ]
    assert all(
        item.artifact_fingerprint is not None for item in (lineage[0], lineage[1], lineage[3])
    )
    assert all(item.waits_on for item in lineage if item.state != "candidate_available")
    assert all(item.accepted_capability is False for item in lineage)


def test_fixed_source_service_hashes_only_allowlisted_records(tmp_path: Path) -> None:
    for relative in SOURCE_REFS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    console = load_manchester_gate_d_console(tmp_path)
    assert console.read_only is True
    assert console.external_requests is False
    assert console.private_artifact_access is False
    assert console.creates_evidence is False
    for link, relative in zip(console.source_links, SOURCE_REFS, strict=True):
        assert link.sha256 == hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
    assert str(tmp_path) not in console.model_dump_json()


def test_fixed_source_service_refuses_symlink_and_changed_measurement(tmp_path: Path) -> None:
    for relative in SOURCE_REFS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO_ROOT / relative).read_bytes())
    worksheet = tmp_path / SOURCE_REFS[0]
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    worksheet.unlink()
    worksheet.symlink_to(outside)
    with pytest.raises(ManchesterGateDConsoleError, match="SOURCE_UNAVAILABLE"):
        load_manchester_gate_d_console(tmp_path)

    worksheet.unlink()
    worksheet.write_bytes((REPO_ROOT / SOURCE_REFS[0]).read_bytes())
    v11_path = tmp_path / SOURCE_REFS[2]
    v11 = json.loads(v11_path.read_text(encoding="utf-8"))
    v11["reconciliation_v1_0_versus_v1_1"]["v1_1"]["awaiting_manual_review"] = 164
    v11_path.write_text(json.dumps(v11), encoding="utf-8")
    with pytest.raises(ManchesterGateDConsoleError, match="MAP_POLICY_SOURCE_REFUSED"):
        load_manchester_gate_d_console(tmp_path)


def test_gate_d_sources_have_no_network_write_execution_or_private_artifact_loader() -> None:
    paths = (
        REPO_ROOT / "src" / "traffictwin" / "integration" / "manchester" / "gate_d_integration.py",
        REPO_ROOT / "src" / "traffictwin" / "ui" / "manchester_gate_d_services.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "import requests",
        "import httpx",
        "urlopen",
        "subprocess",
        "open_real_raw_count_evidence",
        "open_accepted_dft_snapshot",
        "match_results_v11",
        ".write_text(",
        ".write_bytes(",
        "def execute(",
        "def register(",
        "def accept(",
    ):
        assert forbidden not in source
