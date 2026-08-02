"""Static integrity gates for the Phase-184 Manchester decision-support pack."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from traffictwin.integration.manchester.calibration import (
    APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS,
)
from traffictwin.integration.manchester.observation_review import ReviewDecisionKind

ROOT = Path(__file__).resolve().parents[2]
RECORD = (
    ROOT / "docs" / "integration" / "evidence" / "manchester_gate_d_decision_support_20260802.json"
)


def _record() -> dict[str, Any]:
    payload: object = json.loads(RECORD.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_every_source_binding_is_exact_and_repository_relative() -> None:
    record = _record()
    bindings = record["source_bindings"]
    assert isinstance(bindings, list)
    assert len(bindings) == 15
    for binding in bindings:
        assert isinstance(binding, dict)
        relative = Path(str(binding["path"]))
        assert not relative.is_absolute()
        source = ROOT / relative
        assert source.is_file()
        assert not source.is_symlink()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == binding["sha256"]


def test_review_inventory_and_actions_match_the_sealed_ledger_contract() -> None:
    review = _record()["analyst_review"]
    assert isinstance(review, dict)
    assert review["owner_policy_accepted_total"] + review["queued_total"] == 305
    assert (
        review["awaiting_manual_review_total"] + review["no_suitable_candidate_preserved_total"]
        == 174
    )
    assert review["decided_total"] == 0
    assert review["pending_total"] == review["queued_total"]
    assert set(review["permitted_decision_kinds"]) == {kind.value for kind in ReviewDecisionKind}
    assert review["named_person_required"] is True
    assert review["bulk_operation_permitted"] is False
    assert review["decision_records_embedded"] is False


def test_calibration_choices_remain_open_and_production_registry_empty() -> None:
    calibration = _record()["calibration"]
    assert isinstance(calibration, dict)
    assert [item["id"] for item in calibration["open_decisions"]] == [
        "C1",
        "C2",
        "C3",
        "C4",
        "C5",
        "C6",
    ]
    assert frozenset() == APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    for field in (
        "contract_registered",
        "objective_selected",
        "parameters_selected",
        "uncertainty_selected",
    ):
        assert calibration[field] is False


def test_temporal_profile_denominators_reconcile_without_zero_filling() -> None:
    calibration = _record()["calibration"]
    assert isinstance(calibration, dict)
    profile = calibration["source_profile"]
    fixed = calibration["fixed_contract"]
    assert profile["development_sites"] + profile["held_out_sites"] == profile["sites"]
    assert profile["development_cells"] + profile["held_out_cells"] == profile["observed_cells"]
    assert fixed["time_basis"] == "local_clock_hour"
    assert fixed["utc_projection_available"] is False
    assert fixed["missing_as_zero"] is False


def test_demand_lineages_stay_distinct_and_the_gridlock_stays_refused() -> None:
    demand = _record()["demand"]
    assert isinstance(demand, dict)
    original = demand["original_lineage"]
    committed = demand["committed_lineage"]
    difference = demand["unresolved_difference"]
    assert committed["counted_edges"] - original["counted_edges"] == difference["counted_edges"]
    assert committed["cells"] - original["cells"] == difference["cells"]
    assert (
        committed["observed_vehicles"] - original["observed_vehicles"]
        == difference["observed_vehicles"]
    )
    assert original["measured_zero_cells"] == committed["measured_zero_cells"] == 11
    assert difference["decomposable_by_removing_one_committed_edge"] is False
    assert demand["gridlock_refusal"]["accepted_as_viable"] is False


def test_coverage_targeted_variant_is_design_only_and_fail_closed() -> None:
    demand = _record()["demand"]
    assert isinstance(demand, dict)
    diagnosis = demand["reachability_diagnosis"]
    variant = demand["coverage_targeted_variant_contract"]
    assert diagnosis["zero_coverage_edges"] == 4
    assert diagnosis["edges_with_coverage_at_most_two"] == 6
    assert diagnosis["unmet_vehicles_on_those_edges"] == 122235
    assert variant["fail_closed_below_declared_support"] is True
    assert variant["routes_are_observed_journeys"] is False
    assert variant["support_threshold_selected"] is False
    assert variant["protocol_amended"] is False
    assert variant["variant_executed"] is False


def test_no_decision_execution_or_evidence_standing_is_manufactured() -> None:
    record = _record()
    standing = record["standing"]
    assert isinstance(standing, dict)
    assert standing
    assert not any(standing.values())
    rendered = json.dumps(record, sort_keys=True).lower()
    for forbidden in ("/users/", "api_key", "access_token", "password", "private workspace/"):
        assert forbidden not in rendered
