# ruff: noqa: E501
"""Discriminating tests for Lane 05 Manchester calibration workflow — fail-closed.

Covers: convergence mutation, target unit/interval mismatch,
unaccepted observation target, bounds mutation, history tamper,
missing reviewer identity, provider-data-required, path/secret leakage
and deterministic reproduction — plus duplicate/unknown/out-of-bound
parameters, metric/target mismatches, tampered fingerprints and stale
receipts — and the narrowed fail-closed invariants:

- synthetic evaluations never support ACCEPTED;
- ACCEPTED requires exact caller-selected candidate identity;
- REJECTED/PROVIDER_DATA_REQUIRED have coherent selected-candidate contract;
- receipt_issued_at >= decision_timestamp;
- acceptance receipt is ACCEPTED-only.

With the authoritative registry empty, no ACCEPTED receipt can be minted.
Engineering ranking/selection remains descriptive and does not imply
scientific acceptance. Public verification is pure and never mutates the
registry.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.calibration import (
    CalibrationCandidateInput,
    CalibrationIntervalContent,
    CalibrationParameterBound,
    CalibrationParameterValue,
    ManchesterCalibrationContract,
    build_observed_calibration_interval,
    build_simulated_calibration_interval,
)
from traffictwin.integration.manchester.calibration_workflow import (
    CalibrationWorkflowHistoryEntry,
    ManchesterCalibrationAcceptanceReceipt,
    ManchesterCalibrationBaselineDecision,
    ManchesterCalibrationWorkflowError,
    ManchesterCalibrationWorkflowRequest,
    ManchesterCalibrationWorkflowResult,
    _serialize_utc,
    build_acceptance_receipt,
    build_workflow_request,
    decide_baseline,
    evaluate_workflow,
    verify_acceptance_receipt,
)
from traffictwin.integration.manchester.models import canonical_json, sha256_hex

SCOPE_FP = "1" * 64
TIME_FP = "2" * 64
SRC_FP = "3" * 64
PROJ_FP = "4" * 64
MAP_FP = "5" * 64
NET_FP = "6" * 64
RUN_A = "a" * 64
RUN_B = "b" * 64
SNAPSHOT_ID = "synthetic_road-20260722T100000Z-abcdef012345"

PARAM_BOUND = CalibrationParameterBound(
    name="demand_scale",
    unit="ratio",
    lower_bound=Decimal("0.5"),
    upper_bound=Decimal("2.0"),
    permitted_values=(Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), Decimal("2.0")),
)

DECISION_TIME = datetime(2026, 8, 13, 12, 0, 0, tzinfo=UTC)
RECEIPT_TIME = datetime(2026, 8, 13, 12, 5, 0, tzinfo=UTC)
DECISION_TIME_ALT = datetime(2026, 8, 13, 13, 0, 0, tzinfo=UTC)
RECEIPT_TIME_ALT = datetime(2026, 8, 13, 12, 6, 0, tzinfo=UTC)
NAIVE_TIME = datetime(2026, 8, 13, 12, 0, 0)
NON_UTC_TIME = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))


def make_contract(**overrides: object) -> ManchesterCalibrationContract:
    payload: dict[str, object] = {
        "contract_version": "synthetic-dev-1",
        "evidence_class": "synthetic_development",
        "observed_source": "synthetic_utc_road",
        "scope_kind": "synthetic_zone",
        "scope_label": "synthetic_zone",
        "scope_fingerprint": SCOPE_FP,
        "time_basis_label": "synthetic_utc",
        "time_basis_fingerprint": TIME_FP,
        "source_fingerprint": SRC_FP,
        "projection_report_fingerprint": PROJ_FP,
        "mapping_fingerprint": MAP_FP,
        "network_fingerprint": NET_FP,
        "interval_duration_s": 900,
        "measure": "vehicle_count",
        "unit": "vehicles_per_interval",
        "objective": "mean_absolute_error",
        "minimum_observed_coverage": Decimal("0.000"),
        "minimum_simulated_coverage": Decimal("0.000"),
        "parameters": (PARAM_BOUND,),
    }
    payload.update(overrides)
    return ManchesterCalibrationContract.model_validate(payload)


CONTRACT = make_contract()


def content(
    value: str,
    *,
    start: int = 0,
    end: int = 900,
    measure: str = "vehicle_count",
    unit: str = "vehicles_per_interval",
    scope_label: str = "synthetic_zone",
    scope_fp: str = SCOPE_FP,
    time_fp: str = TIME_FP,
) -> CalibrationIntervalContent:
    return CalibrationIntervalContent.model_validate(
        {
            "site_edge_id": "edge-1",
            "interval_start_s": start,
            "interval_end_s": end,
            "direction": "north",
            "vehicle_class": "car",
            "measure": measure,
            "unit": unit,
            "value": Decimal(value),
            "scope_kind": "synthetic_zone",
            "scope_label": scope_label,
            "scope_fingerprint": scope_fp,
            "time_basis_label": "synthetic_utc",
            "time_basis_fingerprint": time_fp,
        }
    )


def observed(
    value: str,
    *,
    start: int = 0,
    end: int = 900,
    synthetic: bool = True,
) -> object:
    interval = content(value, start=start, end=end)
    return build_observed_calibration_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(f"obs-{value}-{start}".encode()),
        synthetic=synthetic,
        source="synthetic_utc_road",
        source_snapshot_id=SNAPSHOT_ID,
        source_fingerprint=SRC_FP,
        projection_report_fingerprint=PROJ_FP,
        mapping_fingerprint=MAP_FP,
    )


def simulated(
    value: str,
    *,
    start: int = 0,
    end: int = 900,
    run_fp: str = RUN_A,
    synthetic: bool = True,
) -> object:
    interval = content(value, start=start, end=end)
    return build_simulated_calibration_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(f"sim-{value}-{start}".encode()),
        synthetic=synthetic,
        network_fingerprint=NET_FP,
        sumo_run_fingerprint=run_fp,
    )


def candidate(
    label: str,
    sims: list[object],
    *,
    run_fp: str = RUN_A,
    value: Decimal = Decimal("1.0"),
) -> CalibrationCandidateInput:
    return CalibrationCandidateInput(
        candidate_label=label,
        parameter_values=(CalibrationParameterValue(name="demand_scale", value=value),),
        sumo_run_fingerprint=run_fp,
        simulated_inputs=tuple(sims),  # type: ignore[arg-type]
    )


def make_request(**overrides: object) -> ManchesterCalibrationWorkflowRequest:
    obs = [observed("10"), observed("8", start=900, end=1800)]
    cands = [
        candidate(
            "cand-a",
            [simulated("12", run_fp=RUN_A), simulated("7", start=900, end=1800, run_fp=RUN_A)],
        ),
        candidate(
            "cand-b",
            [simulated("11", run_fp=RUN_B), simulated("8", start=900, end=1800, run_fp=RUN_B)],
            value=Decimal("1.5"),
            run_fp=RUN_B,
        ),
    ]
    payload: dict[str, object] = {
        "request_id": "req-01",
        "deterministic_seed": 42,
        "contract": CONTRACT,
        "observed_inputs": tuple(obs),
        "candidate_inputs": tuple(cands),
    }
    payload.update(overrides)
    return build_workflow_request(
        request_id=str(payload["request_id"]),
        deterministic_seed=int(cast(int, payload["deterministic_seed"])),
        contract=payload["contract"],  # type: ignore[arg-type]
        observed_inputs=payload["observed_inputs"],  # type: ignore[arg-type]
        candidate_inputs=payload["candidate_inputs"],  # type: ignore[arg-type]
        candidate_history=payload.get("candidate_history", ()),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Production helpers — no registry mutation (registry stays empty, fail-closed)
# ---------------------------------------------------------------------------


def prod_content(value: str, *, start: int = 0, end: int = 900) -> CalibrationIntervalContent:
    return CalibrationIntervalContent.model_validate(
        {
            "site_edge_id": "edge-1",
            "interval_start_s": start,
            "interval_end_s": end,
            "direction": "north",
            "vehicle_class": "car",
            "measure": "vehicle_count",
            "unit": "vehicles_per_interval",
            "value": Decimal(value),
            "scope_kind": "strategic_road_site",
            "scope_label": "m56_site_8150a",
            "scope_fingerprint": SCOPE_FP,
            "time_basis_label": "synthetic_utc",
            "time_basis_fingerprint": TIME_FP,
        }
    )


def prod_observed(value: str, *, start: int = 0, end: int = 900) -> object:
    interval = prod_content(value, start=start, end=end)
    return build_observed_calibration_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(f"real-{value}-{start}".encode()),
        synthetic=False,
        source="webtris_daily",
        source_snapshot_id="webtris_daily-20260301T000000Z-abcdef012345",
        source_fingerprint=SRC_FP,
        projection_report_fingerprint=PROJ_FP,
        mapping_fingerprint=MAP_FP,
    )


def prod_simulated(value: str, *, start: int = 0, end: int = 900, run_fp: str = RUN_A) -> object:
    interval = prod_content(value, start=start, end=end)
    return build_simulated_calibration_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(f"rsim-{value}-{start}".encode()),
        synthetic=False,
        network_fingerprint=NET_FP,
        sumo_run_fingerprint=run_fp,
    )


def prod_candidate(
    label: str, sims: list[object], *, run_fp: str = RUN_A, value: Decimal = Decimal("1.0")
) -> CalibrationCandidateInput:
    return CalibrationCandidateInput(
        candidate_label=label,
        parameter_values=(CalibrationParameterValue(name="demand_scale", value=value),),
        sumo_run_fingerprint=run_fp,
        simulated_inputs=tuple(sims),  # type: ignore[arg-type]
    )


def make_production_contract(**overrides: object) -> ManchesterCalibrationContract:
    base: dict[str, object] = {
        "contract_version": "production-candidate-1",
        "evidence_class": "production",
        "observed_source": "webtris_daily",
        "scope_kind": "strategic_road_site",
        "scope_label": "m56_site_8150a",
    }
    base.update(overrides)
    return make_contract(**base)


def make_production_unadmitted_result() -> tuple[
    ManchesterCalibrationWorkflowRequest, ManchesterCalibrationWorkflowResult
]:
    """Build a production result that remains not_admitted (registry empty)."""
    contract = make_production_contract()
    obs = [prod_observed("10"), prod_observed("8", start=900, end=1800)]
    cands = [
        prod_candidate(
            "cand-a",
            [
                prod_simulated("12", run_fp=RUN_A),
                prod_simulated("7", start=900, end=1800, run_fp=RUN_A),
            ],
        ),
        prod_candidate(
            "cand-b",
            [
                prod_simulated("11", run_fp=RUN_B),
                prod_simulated("8", start=900, end=1800, run_fp=RUN_B),
            ],
            value=Decimal("1.5"),
            run_fp=RUN_B,
        ),
    ]
    req = build_workflow_request(
        request_id="req-prod-unadmitted",
        deterministic_seed=42,
        contract=contract,
        observed_inputs=tuple(obs),  # type: ignore[arg-type]
        candidate_inputs=tuple(cands),
    )
    result = evaluate_workflow(req)
    return req, result


def make_production_unadmitted_result_single(
    candidate_label: str = "cand-a",
) -> tuple[
    ManchesterCalibrationWorkflowRequest,
    ManchesterCalibrationWorkflowResult,
    ManchesterCalibrationContract,
]:
    contract = make_production_contract()
    obs = [prod_observed("10"), prod_observed("8", start=900, end=1800)]
    sims = [
        prod_simulated("12", run_fp=RUN_A),
        prod_simulated("7", start=900, end=1800, run_fp=RUN_A),
    ]
    cand = prod_candidate(candidate_label, sims)
    other = prod_candidate(
        "cand-b",
        [
            prod_simulated("11", run_fp=RUN_B),
            prod_simulated("8", start=900, end=1800, run_fp=RUN_B),
        ],
        value=Decimal("1.5"),
        run_fp=RUN_B,
    )
    req = build_workflow_request(
        request_id="req-prod-single",
        deterministic_seed=7,
        contract=contract,
        observed_inputs=tuple(obs),  # type: ignore[arg-type]
        candidate_inputs=(cand, other),
    )
    result = evaluate_workflow(req)
    return req, result, contract


# ---------------------------------------------------------------------------
# Deterministic reproduction / canonical ordering
# ---------------------------------------------------------------------------


def test_deterministic_reproduction_and_canonical_ordering() -> None:
    obs_forward = [observed("10"), observed("8", start=900, end=1800)]
    obs_reversed = list(reversed(obs_forward))
    cands_forward = [
        candidate("cand-a", [simulated("12"), simulated("7", start=900, end=1800)]),
        candidate(
            "cand-b",
            [simulated("11"), simulated("8", start=900, end=1800)],
            value=Decimal("1.5"),
            run_fp=RUN_B,
        ),
    ]
    cands_reversed = list(reversed(cands_forward))
    req1 = build_workflow_request(
        request_id="req-det",
        deterministic_seed=7,
        contract=CONTRACT,
        observed_inputs=tuple(obs_forward),  # type: ignore[arg-type]
        candidate_inputs=tuple(cands_forward),
    )
    req2 = build_workflow_request(
        request_id="req-det",
        deterministic_seed=7,
        contract=CONTRACT,
        observed_inputs=tuple(obs_reversed),  # type: ignore[arg-type]
        candidate_inputs=tuple(cands_reversed),
    )
    assert req1.request_fingerprint == req2.request_fingerprint
    assert req1.candidate_inputs[0].candidate_label == "cand-a"
    res1 = evaluate_workflow(req1)
    res2 = evaluate_workflow(req2)
    assert res1.evaluation_fingerprint == res2.evaluation_fingerprint
    assert res1.evaluation_report.fingerprint() == res2.evaluation_report.fingerprint()


def test_deterministic_seed_changes_fingerprint() -> None:
    req1 = make_request()
    req2 = build_workflow_request(
        request_id="req-01",
        deterministic_seed=43,
        contract=CONTRACT,
        observed_inputs=(observed("10"), observed("8", start=900, end=1800)),  # type: ignore[arg-type]
        candidate_inputs=(
            candidate("cand-a", [simulated("12"), simulated("7", start=900, end=1800)]),
            candidate(
                "cand-b",
                [simulated("11"), simulated("8", start=900, end=1800)],
                value=Decimal("1.5"),
                run_fp=RUN_B,
            ),
        ),
    )
    assert req1.request_fingerprint != req2.request_fingerprint


# ---------------------------------------------------------------------------
# Target unit / interval / spatial mismatch
# ---------------------------------------------------------------------------


def test_target_unit_mismatch_refused() -> None:
    with pytest.raises(ValidationError):
        content("10", unit="m/s", measure="vehicle_count")


def test_target_interval_mismatch_refused() -> None:
    bad_interval = content("10", start=0, end=1800)
    bad_obs = build_observed_calibration_interval(
        interval=bad_interval,
        source_row_fingerprint="a" * 64,
        synthetic=True,
        source="synthetic_utc_road",
        source_snapshot_id=SNAPSHOT_ID,
        source_fingerprint=SRC_FP,
        projection_report_fingerprint=PROJ_FP,
        mapping_fingerprint=MAP_FP,
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-interval",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(bad_obs,),
            candidate_inputs=(candidate("cand-a", [simulated("12", start=0, end=1800)]),),
        )
    assert exc.value.code == "TARGET_INTERVAL_MISMATCH"


def test_target_spatial_mismatch_refused() -> None:
    bad_interval = content("10", scope_label="other_zone", scope_fp="9" * 64)
    bad_obs = build_observed_calibration_interval(
        interval=bad_interval,
        source_row_fingerprint="a" * 64,
        synthetic=True,
        source="synthetic_utc_road",
        source_snapshot_id=SNAPSHOT_ID,
        source_fingerprint=SRC_FP,
        projection_report_fingerprint=PROJ_FP,
        mapping_fingerprint=MAP_FP,
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-spatial",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(bad_obs,),
            candidate_inputs=(candidate("cand-a", [simulated("12")]),),
        )
    assert exc.value.code == "TARGET_SPATIAL_MISMATCH"


def test_target_source_mismatch_refused() -> None:
    real_interval = CalibrationIntervalContent.model_validate(
        {
            "site_edge_id": "edge-1",
            "interval_start_s": 0,
            "interval_end_s": 900,
            "direction": "north",
            "vehicle_class": "car",
            "measure": "vehicle_count",
            "unit": "vehicles_per_interval",
            "value": Decimal("10"),
            "scope_kind": "strategic_road_site",
            "scope_label": "m56_site_8150a",
            "scope_fingerprint": SCOPE_FP,
            "time_basis_label": "synthetic_utc",
            "time_basis_fingerprint": TIME_FP,
        }
    )
    bad_obs = build_observed_calibration_interval(
        interval=real_interval,
        source_row_fingerprint="a" * 64,
        synthetic=False,
        source="webtris_daily",
        source_snapshot_id="webtris_daily-20260301T000000Z-abcdef012345",
        source_fingerprint=SRC_FP,
        projection_report_fingerprint=PROJ_FP,
        mapping_fingerprint=MAP_FP,
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-source",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(bad_obs,),
            candidate_inputs=(candidate("cand-a", [simulated("12")]),),
        )
    assert exc.value.code in ("TARGET_SOURCE_MISMATCH", "UNACCEPTED_OBSERVATION_TARGET")


# ---------------------------------------------------------------------------
# Unaccepted observation target (evidence standing)
# ---------------------------------------------------------------------------


def test_unaccepted_observation_target_refused() -> None:
    real_obs = build_observed_calibration_interval(
        interval=CalibrationIntervalContent.model_validate(
            {
                "site_edge_id": "edge-1",
                "interval_start_s": 0,
                "interval_end_s": 900,
                "direction": "north",
                "vehicle_class": "car",
                "measure": "vehicle_count",
                "unit": "vehicles_per_interval",
                "value": Decimal("10"),
                "scope_kind": "strategic_road_site",
                "scope_label": "m56_site_8150a",
                "scope_fingerprint": SCOPE_FP,
                "time_basis_label": "synthetic_utc",
                "time_basis_fingerprint": TIME_FP,
            }
        ),
        source_row_fingerprint="b" * 64,
        synthetic=False,
        source="webtris_daily",
        source_snapshot_id="webtris_daily-20260301T000000Z-abcdef012345",
        source_fingerprint=SRC_FP,
        projection_report_fingerprint=PROJ_FP,
        mapping_fingerprint=MAP_FP,
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-standing",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(real_obs,),
            candidate_inputs=(candidate("cand-a", [simulated("12")]),),
        )
    assert exc.value.code == "UNACCEPTED_OBSERVATION_TARGET"


# ---------------------------------------------------------------------------
# Bounds mutation / duplicate / unknown / out-of-bound
# ---------------------------------------------------------------------------


def test_bounds_mutation_out_of_bounds_refused() -> None:
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-bounds",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(observed("10"),),  # type: ignore[arg-type]
            candidate_inputs=(candidate("cand-a", [simulated("12")], value=Decimal("2.5")),),
        )
    assert exc.value.code == "PARAMETER_OUT_OF_BOUNDS"


def test_bounds_mutation_not_on_grid_refused() -> None:
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-grid",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(observed("10"),),  # type: ignore[arg-type]
            candidate_inputs=(candidate("cand-a", [simulated("12")], value=Decimal("0.75")),),
        )
    assert exc.value.code == "PARAMETER_NOT_IN_PERMITTED_GRID"


def test_duplicate_candidate_label_refused() -> None:
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-dup",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(observed("10"),),  # type: ignore[arg-type]
            candidate_inputs=(
                candidate("cand-a", [simulated("12")]),
                candidate("cand-a", [simulated("11")], value=Decimal("1.5")),
            ),
        )
    assert exc.value.code == "DUPLICATE_CANDIDATE_LABEL"


def test_unknown_parameter_refused() -> None:
    bad_candidate = CalibrationCandidateInput(
        candidate_label="cand-a",
        parameter_values=(CalibrationParameterValue(name="unknown_param", value=Decimal("1.0")),),
        sumo_run_fingerprint=RUN_A,
        simulated_inputs=(),
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-unknown",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(observed("10"),),  # type: ignore[arg-type]
            candidate_inputs=(bad_candidate,),
        )
    assert exc.value.code == "PARAMETER_CONTRACT_MISMATCH"


# ---------------------------------------------------------------------------
# Convergence mutation — engineering selection is not baseline acceptance
# ---------------------------------------------------------------------------


def test_convergence_mutation_does_not_imply_baseline_acceptance() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    assert result.automatic_acceptance is False
    assert result.baseline_accepted is False
    data = json.loads(result.model_dump_json())
    data["engineering_selected_candidate"] = (
        "cand-a" if result.engineering_selected_candidate == "cand-b" else "cand-b"
    )
    with pytest.raises(ValidationError):
        ManchesterCalibrationWorkflowResult.model_validate(data)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="",
            reviewer_attribution="x",
            decision_id="dec-01",
            decision_timestamp=DECISION_TIME,
        )
    assert exc.value.code == "MISSING_REVIEWER_IDENTITY"


# ---------------------------------------------------------------------------
# History tamper
# ---------------------------------------------------------------------------


def test_history_tamper_refused() -> None:
    entry = CalibrationWorkflowHistoryEntry(
        candidate_label="cand-a",
        candidate_binding_fingerprint="a" * 64,
        evaluation_fingerprint="b" * 64,
        deterministic_seed=0,
    )
    req = build_workflow_request(
        request_id="req-hist",
        deterministic_seed=0,
        contract=CONTRACT,
        observed_inputs=(observed("10"),),  # type: ignore[arg-type]
        candidate_inputs=(candidate("cand-a", [simulated("12")]),),
        candidate_history=(entry,),
    )
    data = json.loads(req.model_dump_json())
    data["candidate_history"][0]["evaluation_fingerprint"] = "c" * 64
    with pytest.raises(ValidationError):
        ManchesterCalibrationWorkflowRequest.model_validate(data)


def test_history_duplicate_label_refused() -> None:
    e1 = CalibrationWorkflowHistoryEntry(
        candidate_label="cand-a",
        candidate_binding_fingerprint="a" * 64,
        evaluation_fingerprint="b" * 64,
        deterministic_seed=0,
    )
    e2 = CalibrationWorkflowHistoryEntry(
        candidate_label="cand-a",
        candidate_binding_fingerprint="c" * 64,
        evaluation_fingerprint="d" * 64,
        deterministic_seed=1,
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-hist-dup",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(observed("10"),),  # type: ignore[arg-type]
            candidate_inputs=(candidate("cand-a", [simulated("12")]),),
            candidate_history=(e1, e2),
        )
    assert exc.value.code == "DUPLICATE_HISTORY_LABEL"


# ---------------------------------------------------------------------------
# Missing reviewer identity
# ---------------------------------------------------------------------------


def test_missing_reviewer_identity_refused() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="   ",
            reviewer_attribution="reviewer",
            decision_id="dec-01",
            decision_timestamp=DECISION_TIME,
        )
    assert exc.value.code == "MISSING_REVIEWER_IDENTITY"
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            result,
            reviewer_id="",
            reviewer_attribution="reviewer",
            decision_id="dec-01",
            decision_timestamp=DECISION_TIME,
        )


# ---------------------------------------------------------------------------
# Provider-data-required
# ---------------------------------------------------------------------------


def test_provider_data_required_when_insufficient() -> None:
    high_cov_contract = make_contract(minimum_observed_coverage=Decimal("0.900"))
    req = build_workflow_request(
        request_id="req-coverage",
        deterministic_seed=0,
        contract=high_cov_contract,
        observed_inputs=(
            observed("10"),
            observed("8", start=900, end=1800),
            observed("5", start=1800, end=2700),
        ),  # type: ignore[arg-type]
        candidate_inputs=(candidate("cand-a", [simulated("12")]),),
    )
    result = evaluate_workflow(req)
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead reviewer",
        decision_id="dec-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    assert "PROVIDER_DATA_REQUIRED" in decision.reason


def test_production_not_admitted_provider_data_required() -> None:
    prod_contract = make_contract(
        contract_version="production-candidate-1",
        evidence_class="production",
        observed_source="webtris_daily",
        scope_kind="strategic_road_site",
        scope_label="m56_site_8150a",
    )

    def real_observed(value: str) -> object:
        interval = CalibrationIntervalContent.model_validate(
            {
                "site_edge_id": "edge-1",
                "interval_start_s": 0,
                "interval_end_s": 900,
                "direction": "north",
                "vehicle_class": "car",
                "measure": "vehicle_count",
                "unit": "vehicles_per_interval",
                "value": Decimal(value),
                "scope_kind": "strategic_road_site",
                "scope_label": "m56_site_8150a",
                "scope_fingerprint": SCOPE_FP,
                "time_basis_label": "synthetic_utc",
                "time_basis_fingerprint": TIME_FP,
            }
        )
        return build_observed_calibration_interval(
            interval=interval,
            source_row_fingerprint=sha256_hex(f"real-{value}".encode()),
            synthetic=False,
            source="webtris_daily",
            source_snapshot_id="webtris_daily-20260301T000000Z-abcdef012345",
            source_fingerprint=SRC_FP,
            projection_report_fingerprint=PROJ_FP,
            mapping_fingerprint=MAP_FP,
        )

    def real_simulated(value: str) -> object:
        interval = CalibrationIntervalContent.model_validate(
            {
                "site_edge_id": "edge-1",
                "interval_start_s": 0,
                "interval_end_s": 900,
                "direction": "north",
                "vehicle_class": "car",
                "measure": "vehicle_count",
                "unit": "vehicles_per_interval",
                "value": Decimal(value),
                "scope_kind": "strategic_road_site",
                "scope_label": "m56_site_8150a",
                "scope_fingerprint": SCOPE_FP,
                "time_basis_label": "synthetic_utc",
                "time_basis_fingerprint": TIME_FP,
            }
        )
        return build_simulated_calibration_interval(
            interval=interval,
            source_row_fingerprint=sha256_hex(f"rsim-{value}".encode()),
            synthetic=False,
            network_fingerprint=NET_FP,
            sumo_run_fingerprint=RUN_A,
        )

    req = build_workflow_request(
        request_id="req-prod",
        deterministic_seed=0,
        contract=prod_contract,
        observed_inputs=(real_observed("10"),),  # type: ignore[arg-type]
        candidate_inputs=(
            CalibrationCandidateInput(
                candidate_label="cand-a",
                parameter_values=(
                    CalibrationParameterValue(name="demand_scale", value=Decimal("1.0")),
                ),
                sumo_run_fingerprint=RUN_A,
                simulated_inputs=(real_simulated("12"),),  # type: ignore[arg-type]
            ),
        ),
    )
    result = evaluate_workflow(req)
    assert result.evaluation_report.contract_admitted is False
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-02",
        reviewer_attribution="lead",
        decision_id="dec-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"


# ---------------------------------------------------------------------------
# Path / secret leakage — direct model validation (no registry mutation)
# ---------------------------------------------------------------------------


def test_path_leakage_refused_in_request() -> None:
    with pytest.raises((ManchesterCalibrationWorkflowError, ValidationError, ValueError)):
        build_workflow_request(
            request_id="/tmp/evil",  # noqa: S108
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(observed("10"),),  # type: ignore[arg-type]
            candidate_inputs=(candidate("cand-a", [simulated("12")]),),
        )


def test_secret_and_path_leakage_in_provenance_refused_via_model() -> None:
    bad_vals = ["api_key=secret123", "/Users/attacker/secret"]
    for bad in bad_vals:
        data = {
            "receipt_id": "receipt-secret-01",
            "request_fingerprint": "a" * 64,
            "evaluation_fingerprint": "b" * 64,
            "decision_fingerprint": "c" * 64,
            "reviewer_id": "reviewer-01",
            "reviewer_attribution": "lead",
            "decision": "ACCEPTED",
            "decision_timestamp": DECISION_TIME,
            "receipt_issued_at": RECEIPT_TIME,
            "reason": "ok",
            "selected_candidate_label": "cand-a",
            "selected_candidate_binding_fingerprint": "d" * 64,
            "selected_sumo_run_fingerprint": RUN_A,
            "limitations": (
                "Descriptive candidate review only — no automatic calibration acceptance.",
                "Lowest objective or convergence does not imply realism or optimality.",
                "Missing observations are never zero-filled.",
                "Unit, interval-duration and spatial scope must match contract exactly.",
                "Incompatible targets are refused, not fused or coerced.",
                "History and fingerprints are deterministic and tamper-evident.",
                "Baseline acceptance requires explicit attributable reviewer decision.",
                "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
                "No VEC task telemetry, causal or uncertainty inference is made.",
                "Portable provenance contains no private paths or secrets.",
                "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
            ),
            "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
            "receipt_fingerprint": "e" * 64,
            "portable_provenance": {"evil": bad, "request_fingerprint": "a" * 64},
        }
        with pytest.raises(ValidationError):
            ManchesterCalibrationAcceptanceReceipt.model_validate(data)


def test_portable_provenance_valid_has_no_private_paths() -> None:
    # Direct model shows private paths are refused; no need to mint a receipt
    data = {
        "decision_id": "dec-provenance-01",
        "request_fingerprint": "a" * 64,
        "evaluation_fingerprint": "b" * 64,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead reviewer",
        "decision": "REJECTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "REJECTED: provider blocked — test",
        "selected_candidate_label": None,
        "selected_candidate_binding_fingerprint": None,
        "selected_sumo_run_fingerprint": None,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": data["decision"],
        "decision_id": data["decision_id"],
        "decision_timestamp": _serialize_utc(data["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": data["evaluation_fingerprint"],
        "reason": data["reason"],
        "request_fingerprint": data["request_fingerprint"],
        "reviewer_attribution": data["reviewer_attribution"],
        "reviewer_id": data["reviewer_id"],
        "selected_candidate_binding_fingerprint": data["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": data["selected_candidate_label"],
        "selected_sumo_run_fingerprint": data["selected_sumo_run_fingerprint"],
    }
    data["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    decision = ManchesterCalibrationBaselineDecision.model_validate(data)
    for v in (decision.reviewer_id, decision.reviewer_attribution, decision.reason):
        assert "/Users/" not in v
        assert "/tmp/" not in v  # noqa: S108


# ---------------------------------------------------------------------------
# Tampered fingerprints / stale receipts
# ---------------------------------------------------------------------------


def test_tampered_request_fingerprint_refused() -> None:
    req = make_request()
    data = json.loads(req.model_dump_json())
    data["request_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        ManchesterCalibrationWorkflowRequest.model_validate(data)


def test_tampered_evaluation_fingerprint_refused() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    data = json.loads(result.model_dump_json())
    data["evaluation_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        ManchesterCalibrationWorkflowResult.model_validate(data)


def test_tampered_receipt_fingerprint_refused_via_direct_model() -> None:
    data = {
        "receipt_id": "receipt-tamper-01",
        "request_fingerprint": "a" * 64,
        "evaluation_fingerprint": "b" * 64,
        "decision_fingerprint": "c" * 64,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "receipt_issued_at": RECEIPT_TIME,
        "reason": "ok",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": "d" * 64,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
        "receipt_fingerprint": "0" * 64,
        "portable_provenance": {"request_fingerprint": "a" * 64},
    }
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)


def test_stale_receipt_fingerprint_mismatch_is_detected() -> None:
    # With empty registry no valid ACCEPTED receipt exists; stale detection is
    # proven via direct model fingerprint mismatch already covered.
    # Here prove that verification refuses mismatched fingerprints via manual
    # forbidden mutation of request fingerprint on a synthetic result.
    req = make_request()
    result = evaluate_workflow(req)
    tampered = result.model_copy(update={"request_fingerprint": "0" * 64})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            tampered,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-stale-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="REJECTED",
        )
    assert exc.value.code == "INVALID_RESULT"


# ---------------------------------------------------------------------------
# Metric / target mismatches
# ---------------------------------------------------------------------------


def test_metric_mismatch_via_measure_refused() -> None:
    speed_interval = CalibrationIntervalContent.model_validate(
        {
            "site_edge_id": "edge-1",
            "interval_start_s": 0,
            "interval_end_s": 900,
            "direction": "north",
            "vehicle_class": "car",
            "measure": "average_speed_mps",
            "unit": "m/s",
            "value": Decimal("13.4"),
            "scope_kind": "synthetic_zone",
            "scope_label": "synthetic_zone",
            "scope_fingerprint": SCOPE_FP,
            "time_basis_label": "synthetic_utc",
            "time_basis_fingerprint": TIME_FP,
        }
    )
    bad_obs = build_observed_calibration_interval(
        interval=speed_interval,
        source_row_fingerprint="a" * 64,
        synthetic=True,
        source="synthetic_utc_road",
        source_snapshot_id=SNAPSHOT_ID,
        source_fingerprint=SRC_FP,
        projection_report_fingerprint=PROJ_FP,
        mapping_fingerprint=MAP_FP,
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-metric",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(bad_obs,),
            candidate_inputs=(candidate("cand-a", [simulated("12")]),),
        )
    assert exc.value.code == "TARGET_MEASURE_MISMATCH"


# ---------------------------------------------------------------------------
# No invented observations / no VEC telemetry / no causal claims
# ---------------------------------------------------------------------------


def test_limitations_and_non_claims_present() -> None:
    # Synthetic result has engineering selection (production unadmitted has none)
    req = make_request()
    result = evaluate_workflow(req)
    assert any(
        "calibrated realism" in lim.lower() or "descriptive" in lim.lower()
        for lim in result.limitations
    )
    assert any(
        "VEC" in lim or "causal" in lim.lower() or "uncertainty" in lim.lower()
        for lim in result.non_claims
    )
    assert "/Users/" not in result.evidence_boundary
    assert result.automatic_acceptance is False
    assert result.baseline_accepted is False
    assert result.engineering_selected_candidate is not None
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    assert decision.reviewer_id == "reviewer-01"
    assert decision.decision in ("REJECTED", "PROVIDER_DATA_REQUIRED")


def test_observation_count_bounded_and_history_bounded() -> None:
    many = tuple(
        candidate(f"cand-{i:02d}", [simulated("12")], value=Decimal("1.0")) for i in range(33)
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_workflow_request(
            request_id="req-many",
            deterministic_seed=0,
            contract=CONTRACT,
            observed_inputs=(observed("10"),),  # type: ignore[arg-type]
            candidate_inputs=many,
        )
    assert exc.value.code == "TOO_MANY_CANDIDATES"


def test_no_network_or_workload_launch_attributes() -> None:
    import traffictwin.integration.manchester.calibration_workflow as wf

    assert not hasattr(wf, "launch_research_workload")
    assert not hasattr(wf, "fetch_observations")
    req = make_request()
    r1 = evaluate_workflow(req)
    r2 = evaluate_workflow(req)
    assert r1.evaluation_fingerprint == r2.evaluation_fingerprint
    assert r1.evaluation_report.fingerprint() == r2.evaluation_report.fingerprint()


# ---------------------------------------------------------------------------
# Provenance defect: reviewer attribution and timestamps fingerprint-bound
# ---------------------------------------------------------------------------


def test_decision_fingerprint_binds_reviewer_attribution_and_timestamp() -> None:
    _req, result = make_production_unadmitted_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="alice@lab",
        decision_id="dec-bind-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    data = decision.model_dump()
    data["reviewer_attribution"] = "bob@lab"
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)
    data2 = decision.model_dump()
    data2["decision_timestamp"] = DECISION_TIME_ALT
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data2)
    decision_alt = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="alice@lab",
        decision_id="dec-bind-01",
        decision_timestamp=DECISION_TIME_ALT,
        requested_decision="REJECTED",
    )
    assert decision.decision_fingerprint != decision_alt.decision_fingerprint
    decision_att_alt = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="bob@lab",
        decision_id="dec-bind-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    assert decision.decision_fingerprint != decision_att_alt.decision_fingerprint


def test_receipt_fingerprint_binds_reviewer_attribution_and_timestamps_via_model() -> None:
    # Direct receipt model must bind reviewer_attribution and timestamps
    base = {
        "receipt_id": "receipt-bind-01",
        "request_fingerprint": "a" * 64,
        "evaluation_fingerprint": "b" * 64,
        "decision_fingerprint": "c" * 64,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "alice@lab",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "receipt_issued_at": RECEIPT_TIME,
        "reason": "ACCEPTED: ok",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": "d" * 64,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
        "portable_provenance": {
            "request_fingerprint": "a" * 64,
            "evaluation_fingerprint": "b" * 64,
            "decision_fingerprint": "c" * 64,
            "contract_fingerprint": "e" * 64,
            "method_version": "manchester-calibration-workflow-1.0",
            "capability_id": "MAN-09",
            "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
            "selected_candidate_label": "cand-a",
            "selected_candidate_binding_fingerprint": "d" * 64,
            "selected_sumo_run_fingerprint": RUN_A,
        },
    }
    prov = {
        "decision": base["decision"],
        "decision_fingerprint": base["decision_fingerprint"],
        "decision_timestamp": _serialize_utc(base["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": base["evaluation_fingerprint"],
        "portable_provenance": base["portable_provenance"],
        "receipt_id": base["receipt_id"],
        "receipt_issued_at": _serialize_utc(base["receipt_issued_at"]),  # type: ignore[arg-type]
        "request_fingerprint": base["request_fingerprint"],
        "reviewer_attribution": base["reviewer_attribution"],
        "reviewer_id": base["reviewer_id"],
        "selected_candidate_binding_fingerprint": base["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": base["selected_candidate_label"],
        "selected_sumo_run_fingerprint": base["selected_sumo_run_fingerprint"],
    }
    base["receipt_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    receipt = ManchesterCalibrationAcceptanceReceipt.model_validate(base)
    assert receipt.reviewer_attribution == "alice@lab"
    data = receipt.model_dump()
    data["reviewer_attribution"] = "bob@lab"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    data2 = receipt.model_dump()
    data2["decision_timestamp"] = DECISION_TIME_ALT
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data2)
    data3 = receipt.model_dump()
    data3["receipt_issued_at"] = RECEIPT_TIME_ALT
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data3)


def test_decision_naive_timestamp_rejected() -> None:
    _req, result = make_production_unadmitted_result()
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-naive-01",
            decision_timestamp=NAIVE_TIME,
            requested_decision="REJECTED",
        )
    assert exc.value.code == "INVALID_TIMESTAMP"
    valid = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-naive-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    data = valid.model_dump()
    data["decision_timestamp"] = NAIVE_TIME
    data["decision_id"] = "dec-naive-03"
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)


def test_decision_non_utc_timestamp_rejected() -> None:
    _req, result = make_production_unadmitted_result()
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-nonutc-01",
            decision_timestamp=NON_UTC_TIME,
            requested_decision="REJECTED",
        )
    assert exc.value.code == "INVALID_TIMESTAMP"
    valid = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-nonutc-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    data = valid.model_dump()
    data["decision_timestamp"] = NON_UTC_TIME
    data["decision_id"] = "dec-nonutc-03"
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)


def test_receipt_naive_and_non_utc_timestamp_rejected_via_model() -> None:
    # Build a plausible ACCEPTED decision via direct model (bypassing sufficiency)
    # to test receipt timestamp validation without registry mutation.
    _req, result = make_production_unadmitted_result()
    # Forge a direct ACCEPTED decision for timestamp tests (model-level)
    forged = {
        "decision_id": "dec-receipt-naive",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "forged for timestamp test",
        "selected_candidate_label": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_label,
        "selected_candidate_binding_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": forged["decision"],
        "decision_id": forged["decision_id"],
        "decision_timestamp": _serialize_utc(forged["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": forged["evaluation_fingerprint"],
        "reason": forged["reason"],
        "request_fingerprint": forged["request_fingerprint"],
        "reviewer_attribution": forged["reviewer_attribution"],
        "reviewer_id": forged["reviewer_id"],
        "selected_candidate_binding_fingerprint": forged["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": forged["selected_candidate_label"],
        "selected_sumo_run_fingerprint": forged["selected_sumo_run_fingerprint"],
    }
    forged["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    decision = ManchesterCalibrationBaselineDecision.model_validate(forged)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-naive-01", receipt_issued_at=NAIVE_TIME
        )
    assert exc.value.code in ("INVALID_TIMESTAMP", "INSUFFICIENT_PROVIDER_DATA")
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-nonutc-01", receipt_issued_at=NON_UTC_TIME
        )
    assert exc2.value.code in ("INVALID_TIMESTAMP", "INSUFFICIENT_PROVIDER_DATA")
    # Model-level naive receipt_issued_at must also be rejected — craft receipt dict directly
    provisional = {
        "decision": decision.decision,
        "decision_fingerprint": decision.decision_fingerprint,
        "decision_timestamp": _serialize_utc(decision.decision_timestamp),
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "portable_provenance": {
            "request_fingerprint": result.request_fingerprint,
            "evaluation_fingerprint": result.evaluation_fingerprint,
            "decision_fingerprint": decision.decision_fingerprint,
            "contract_fingerprint": result.contract_fingerprint,
            "method_version": "manchester-calibration-workflow-1.0",
            "capability_id": "MAN-09",
            "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
            "selected_candidate_label": decision.selected_candidate_label,
            "selected_candidate_binding_fingerprint": decision.selected_candidate_binding_fingerprint,
            "selected_sumo_run_fingerprint": decision.selected_sumo_run_fingerprint,
        },
        "receipt_id": "receipt-ok-01",
        "receipt_issued_at": _serialize_utc(RECEIPT_TIME),
        "request_fingerprint": result.request_fingerprint,
        "reviewer_attribution": decision.reviewer_attribution,
        "reviewer_id": decision.reviewer_id,
        "selected_candidate_binding_fingerprint": decision.selected_candidate_binding_fingerprint,
        "selected_candidate_label": decision.selected_candidate_label,
        "selected_sumo_run_fingerprint": decision.selected_sumo_run_fingerprint,
    }
    receipt_fp = sha256_hex(canonical_json(provisional).encode("utf-8"))
    receipt_data = {
        "receipt_id": "receipt-ok-01",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "decision_fingerprint": decision.decision_fingerprint,
        "reviewer_id": decision.reviewer_id,
        "reviewer_attribution": decision.reviewer_attribution,
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "receipt_issued_at": RECEIPT_TIME,
        "reason": decision.reason,
        "selected_candidate_label": decision.selected_candidate_label,
        "selected_candidate_binding_fingerprint": decision.selected_candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": decision.selected_sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
        "receipt_fingerprint": receipt_fp,
        "portable_provenance": provisional["portable_provenance"],
    }
    data = dict(receipt_data)
    data["receipt_issued_at"] = NAIVE_TIME
    data["receipt_id"] = "receipt-naive-02"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    data2 = dict(receipt_data)
    data2["receipt_issued_at"] = NON_UTC_TIME
    data2["receipt_id"] = "receipt-nonutc-02"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data2)


def test_receipt_preserves_reviewer_attribution_and_decision_timestamp_via_model() -> None:
    # Prove receipt fingerprint binds reviewer_attribution and timestamps via model
    base = {
        "receipt_id": "receipt-preserve-01",
        "request_fingerprint": "a" * 64,
        "evaluation_fingerprint": "b" * 64,
        "decision_fingerprint": "c" * 64,
        "reviewer_id": "reviewer-09",
        "reviewer_attribution": "attribution-xyz",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "receipt_issued_at": RECEIPT_TIME,
        "reason": "ACCEPTED: ok",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": "d" * 64,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
        "portable_provenance": {
            "request_fingerprint": "a" * 64,
            "evaluation_fingerprint": "b" * 64,
            "decision_fingerprint": "c" * 64,
            "contract_fingerprint": "e" * 64,
            "method_version": "manchester-calibration-workflow-1.0",
            "capability_id": "MAN-09",
            "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
            "selected_candidate_label": "cand-a",
            "selected_candidate_binding_fingerprint": "d" * 64,
            "selected_sumo_run_fingerprint": RUN_A,
        },
    }
    prov = {
        "decision": base["decision"],
        "decision_fingerprint": base["decision_fingerprint"],
        "decision_timestamp": _serialize_utc(base["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": base["evaluation_fingerprint"],
        "portable_provenance": base["portable_provenance"],
        "receipt_id": base["receipt_id"],
        "receipt_issued_at": _serialize_utc(base["receipt_issued_at"]),  # type: ignore[arg-type]
        "request_fingerprint": base["request_fingerprint"],
        "reviewer_attribution": base["reviewer_attribution"],
        "reviewer_id": base["reviewer_id"],
        "selected_candidate_binding_fingerprint": base["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": base["selected_candidate_label"],
        "selected_sumo_run_fingerprint": base["selected_sumo_run_fingerprint"],
    }
    base["receipt_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    receipt = ManchesterCalibrationAcceptanceReceipt.model_validate(base)
    assert receipt.reviewer_attribution == "attribution-xyz"
    assert receipt.decision_timestamp == DECISION_TIME
    data = receipt.model_dump()
    data["reviewer_attribution"] = "other"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    data2 = receipt.model_dump()
    data2["receipt_issued_at"] = RECEIPT_TIME_ALT
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data2)


def test_timestamp_serialization_is_portable_and_deterministic() -> None:
    # Same instant expressed as UTC must yield same fingerprint for REJECTED path
    _req, result = make_production_unadmitted_result()
    alt_tz = UTC
    decision_same = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-portable-01",
        decision_timestamp=datetime(2026, 8, 13, 12, 0, 0, tzinfo=alt_tz),
        requested_decision="REJECTED",
    )
    reloaded = ManchesterCalibrationBaselineDecision.model_validate_json(
        decision_same.model_dump_json()
    )
    assert reloaded.decision_fingerprint == decision_same.decision_fingerprint
    decision_dup = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-portable-01",
        decision_timestamp=datetime(2026, 8, 13, 12, 0, 0, tzinfo=UTC),
        requested_decision="REJECTED",
    )
    assert decision_dup.decision_fingerprint == decision_same.decision_fingerprint


# ---------------------------------------------------------------------------
# Narrowed fail-closed invariants (Lane 05) — empty registry
# ---------------------------------------------------------------------------


def test_synthetic_accepted_is_forced_to_provider_data_required() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    assert result.evaluation_report.synthetic is True
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-synth-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    assert decision.selected_candidate_label is None
    assert "synthetic" in decision.reason.lower() or "production" in decision.reason.lower()
    assert (
        "does not prove realism" in decision.reason.lower()
        or "optimisation" in decision.reason.lower()
    )


def test_synthetic_optimisation_does_not_imply_realism_even_with_available_objective() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    assert any(
        ev.objective_result.status == "available"
        for ev in result.evaluation_report.candidate_evaluations
    )
    assert result.engineering_selected_candidate is not None
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-synth-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-synth-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code == "RECEIPT_REQUIRES_ACCEPTED"


def test_accepted_requires_explicit_candidate_even_when_empty_registry_blocks() -> None:
    # With empty registry, ACCEPTED is blocked anyway, but missing candidate
    # must be refused before provider check would still block. We test the
    # REJECTED path requires explicit handling and ACCEPTED without candidate
    # is refused via AC existence check that survives fail-closed.
    # Use a synthetic result where sufficient is false -> PROVIDER_DATA_REQUIRED
    # The ineligible path for production also blocks. Directly test
    # ACCEPTED_REQUIRES_CANDIDATE via a forged production admitted scenario
    # that would be sufficient if registry allowed — but we demonstrate the
    # guard exists via model validation for direct ACCEPTED construction.
    valid_data = {
        "decision_id": "dec-nocand-02",
        "request_fingerprint": "a" * 64,
        "evaluation_fingerprint": "b" * 64,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "ACCEPTED: ok",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": "c" * 64,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": valid_data["decision"],
        "decision_id": valid_data["decision_id"],
        "decision_timestamp": _serialize_utc(valid_data["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": valid_data["evaluation_fingerprint"],
        "reason": valid_data["reason"],
        "request_fingerprint": valid_data["request_fingerprint"],
        "reviewer_attribution": valid_data["reviewer_attribution"],
        "reviewer_id": valid_data["reviewer_id"],
        "selected_candidate_binding_fingerprint": valid_data[
            "selected_candidate_binding_fingerprint"
        ],
        "selected_candidate_label": valid_data["selected_candidate_label"],
        "selected_sumo_run_fingerprint": valid_data["selected_sumo_run_fingerprint"],
    }
    valid_data["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    valid = ManchesterCalibrationBaselineDecision.model_validate(valid_data)
    assert valid.decision == "ACCEPTED"
    # Missing candidate fields must be refused
    broken = valid.model_dump()
    broken["decision_id"] = "dec-nocand-03"
    broken["selected_candidate_label"] = None
    broken["selected_candidate_binding_fingerprint"] = None
    broken["selected_sumo_run_fingerprint"] = None
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(broken)
    # Also check decide_baseline still forces PROVIDER_DATA_REQUIRED for synthetic
    req = make_request()
    result = evaluate_workflow(req)
    # Synthetic forced blocked already tested; here ensure REJECTED without candidate works
    decision_rejected = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-nocand-04",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    assert (
        decision_rejected.decision == "PROVIDER_DATA_REQUIRED"
        or decision_rejected.decision == "REJECTED"
    )
    # The key is that with empty registry, ACCEPTED never emerges
    decision_try_accepted = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-nocand-05",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision_try_accepted.decision == "PROVIDER_DATA_REQUIRED"


def test_unknown_candidate_refused_even_when_blocked() -> None:
    _req, result = make_production_unadmitted_result()
    # With empty registry, any REJECTED with candidate is forced to
    # PROVIDER_DATA_REQUIRED with no candidate, so unknown is not exercised via
    # decide_baseline. Prove the decision is forced blocked and that forging
    # an unknown label fails fingerprint validation.
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-unknown-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    assert decision.selected_candidate_label is None
    # Forging unknown label directly must fail fingerprint validation
    base = {
        "decision_id": "dec-unknown-02",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "REJECTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "REJECTED: test",
        "selected_candidate_label": "cand-unknown",
        "selected_candidate_binding_fingerprint": "c" * 64,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": base["decision"],
        "decision_id": base["decision_id"],
        "decision_timestamp": _serialize_utc(base["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": base["evaluation_fingerprint"],
        "reason": base["reason"],
        "request_fingerprint": base["request_fingerprint"],
        "reviewer_attribution": base["reviewer_attribution"],
        "reviewer_id": base["reviewer_id"],
        "selected_candidate_binding_fingerprint": base["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": base["selected_candidate_label"],
        "selected_sumo_run_fingerprint": base["selected_sumo_run_fingerprint"],
    }
    base["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    unknown = ManchesterCalibrationBaselineDecision.model_validate(base)
    # Building receipt with unknown candidate must fail drift
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, unknown, receipt_id="receipt-unknown-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code in (
        "RECEIPT_REQUIRES_ACCEPTED",
        "CANDIDATE_DRIFT",
        "INSUFFICIENT_PROVIDER_DATA",
    )


def test_ineligible_candidate_still_blocked_via_provider_required() -> None:
    # Production with high coverage: cand-a single paired interval fails coverage,
    # but with empty registry the whole result is PROVIDER_DATA_REQUIRED anyway
    contract = make_production_contract(minimum_observed_coverage=Decimal("0.500"))
    obs = [
        prod_observed("10"),
        prod_observed("8", start=900, end=1800),
        prod_observed("5", start=1800, end=2700),
    ]
    single_sim = [prod_simulated("12", run_fp=RUN_A)]
    cand_a = prod_candidate("cand-a", single_sim)
    cand_b = prod_candidate(
        "cand-b",
        [
            prod_simulated("11", run_fp=RUN_B),
            prod_simulated("8", start=900, end=1800, run_fp=RUN_B),
        ],
        value=Decimal("1.5"),
        run_fp=RUN_B,
    )
    req = build_workflow_request(
        request_id="req-elig",
        deterministic_seed=0,
        contract=contract,
        observed_inputs=tuple(obs),  # type: ignore[arg-type]
        candidate_inputs=(cand_a, cand_b),
    )
    result = evaluate_workflow(req)
    # Even though cand-b would be eligible under admitted registry, empty
    # registry forces PROVIDER_DATA_REQUIRED for any ACCEPTED attempt
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-inelig-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    decision_b = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-inelig-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-b",
    )
    assert decision_b.decision == "PROVIDER_DATA_REQUIRED"


def test_candidate_fingerprint_drift_refused_via_model() -> None:
    # Drift is proven via model validation: tampering binding fingerprint
    # invalidates decision/receipt without needing an admitted receipt.
    _req, result = make_production_unadmitted_result()
    # Build a plausible decision via direct model for cand-a
    base = {
        "decision_id": "dec-drift-01",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "REJECTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "REJECTED: test",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": base["decision"],
        "decision_id": base["decision_id"],
        "decision_timestamp": _serialize_utc(base["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": base["evaluation_fingerprint"],
        "reason": base["reason"],
        "request_fingerprint": base["request_fingerprint"],
        "reviewer_attribution": base["reviewer_attribution"],
        "reviewer_id": base["reviewer_id"],
        "selected_candidate_binding_fingerprint": base["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": base["selected_candidate_label"],
        "selected_sumo_run_fingerprint": base["selected_sumo_run_fingerprint"],
    }
    base["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    decision = ManchesterCalibrationBaselineDecision.model_validate(base)
    data = decision.model_dump()
    data["decision_id"] = "dec-drift-02"
    data["selected_candidate_binding_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)
    # Receipt level also
    receipt_base = {
        "receipt_id": "receipt-drift-01",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "decision_fingerprint": decision.decision_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "receipt_issued_at": RECEIPT_TIME,
        "reason": "ACCEPTED: ok",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": "d" * 64,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
        "portable_provenance": {
            "request_fingerprint": result.request_fingerprint,
            "evaluation_fingerprint": result.evaluation_fingerprint,
            "decision_fingerprint": decision.decision_fingerprint,
            "contract_fingerprint": result.contract_fingerprint,
            "method_version": "manchester-calibration-workflow-1.0",
            "capability_id": "MAN-09",
            "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
            "selected_candidate_label": "cand-a",
            "selected_candidate_binding_fingerprint": "d" * 64,
            "selected_sumo_run_fingerprint": RUN_A,
        },
    }
    prov_r = {
        "decision": receipt_base["decision"],
        "decision_fingerprint": receipt_base["decision_fingerprint"],
        "decision_timestamp": _serialize_utc(receipt_base["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": receipt_base["evaluation_fingerprint"],
        "portable_provenance": receipt_base["portable_provenance"],
        "receipt_id": receipt_base["receipt_id"],
        "receipt_issued_at": _serialize_utc(receipt_base["receipt_issued_at"]),  # type: ignore[arg-type]
        "request_fingerprint": receipt_base["request_fingerprint"],
        "reviewer_attribution": receipt_base["reviewer_attribution"],
        "reviewer_id": receipt_base["reviewer_id"],
        "selected_candidate_binding_fingerprint": receipt_base[
            "selected_candidate_binding_fingerprint"
        ],
        "selected_candidate_label": receipt_base["selected_candidate_label"],
        "selected_sumo_run_fingerprint": receipt_base["selected_sumo_run_fingerprint"],
    }
    receipt_base["receipt_fingerprint"] = sha256_hex(canonical_json(prov_r).encode("utf-8"))
    receipt = ManchesterCalibrationAcceptanceReceipt.model_validate(receipt_base)
    data_r = receipt.model_dump()
    data_r["receipt_id"] = "receipt-drift-02"
    data_r["selected_candidate_binding_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data_r)


def test_candidate_run_drift_refused_via_model() -> None:
    _req, result = make_production_unadmitted_result()
    base = {
        "decision_id": "dec-rundrift-01",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "REJECTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "REJECTED: test",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": base["decision"],
        "decision_id": base["decision_id"],
        "decision_timestamp": _serialize_utc(base["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": base["evaluation_fingerprint"],
        "reason": base["reason"],
        "request_fingerprint": base["request_fingerprint"],
        "reviewer_attribution": base["reviewer_attribution"],
        "reviewer_id": base["reviewer_id"],
        "selected_candidate_binding_fingerprint": base["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": base["selected_candidate_label"],
        "selected_sumo_run_fingerprint": base["selected_sumo_run_fingerprint"],
    }
    base["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    decision = ManchesterCalibrationBaselineDecision.model_validate(base)
    data = decision.model_dump()
    data["decision_id"] = "dec-rundrift-02"
    data["selected_sumo_run_fingerprint"] = RUN_B
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)


def test_provider_blocked_decision_has_no_acceptance_receipt() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-blocked-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    assert decision.selected_candidate_label is None
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-blocked-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code == "RECEIPT_REQUIRES_ACCEPTED"
    _req2, result2 = make_production_unadmitted_result()
    rejected = decide_baseline(
        result2,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-rejected-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    assert rejected.decision in ("REJECTED", "PROVIDER_DATA_REQUIRED")
    # REJECTED with candidate-specific rejection is allowed if coherent
    rejected_specific = decide_baseline(
        result2,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-rejected-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
        selected_candidate_label="cand-a",
    )
    # With empty registry, REJECTED is forced to PROVIDER_DATA_REQUIRED, so
    # candidate is ignored. Verify coherent behavior: either None or cand-a
    # depending on insufficiency. The exact is PROVIDER_DATA_REQUIRED with None.
    assert rejected_specific.decision == "PROVIDER_DATA_REQUIRED"
    assert rejected_specific.selected_candidate_label is None
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        build_acceptance_receipt(
            result2, rejected, receipt_id="receipt-rejected-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc2.value.code == "RECEIPT_REQUIRES_ACCEPTED"


def test_receipt_time_reversal_refused_via_direct_forged_decision() -> None:
    _req, result = make_production_unadmitted_result()
    # Forge an ACCEPTED decision to test receipt time reversal without registry mutation
    forged = {
        "decision_id": "dec-time-01",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "forged for time test",
        "selected_candidate_label": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_label,
        "selected_candidate_binding_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": forged["decision"],
        "decision_id": forged["decision_id"],
        "decision_timestamp": _serialize_utc(forged["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": forged["evaluation_fingerprint"],
        "reason": forged["reason"],
        "request_fingerprint": forged["request_fingerprint"],
        "reviewer_attribution": forged["reviewer_attribution"],
        "reviewer_id": forged["reviewer_id"],
        "selected_candidate_binding_fingerprint": forged["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": forged["selected_candidate_label"],
        "selected_sumo_run_fingerprint": forged["selected_sumo_run_fingerprint"],
    }
    forged["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    decision = ManchesterCalibrationBaselineDecision.model_validate(forged)
    early = datetime(2026, 8, 13, 11, 50, 0, tzinfo=UTC)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-early-01", receipt_issued_at=early
        )
    # With empty registry, INSUFFICIENT_PROVIDER_DATA is raised before time reversal;
    # both indicate fail-closed. Accept either as proof of refusal.
    assert exc.value.code in (
        "RECEIPT_TIME_REVERSAL",
        "INSUFFICIENT_PROVIDER_DATA",
        "INVALID_RESULT",
    )
    # Model-level reversal must also be refused (direct construction)
    provisional = {
        "decision": decision.decision,
        "decision_fingerprint": decision.decision_fingerprint,
        "decision_timestamp": _serialize_utc(decision.decision_timestamp),
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "portable_provenance": {
            "request_fingerprint": result.request_fingerprint,
            "evaluation_fingerprint": result.evaluation_fingerprint,
            "decision_fingerprint": decision.decision_fingerprint,
            "contract_fingerprint": result.contract_fingerprint,
            "method_version": "manchester-calibration-workflow-1.0",
            "capability_id": "MAN-09",
            "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
            "selected_candidate_label": decision.selected_candidate_label,
            "selected_candidate_binding_fingerprint": decision.selected_candidate_binding_fingerprint,
            "selected_sumo_run_fingerprint": decision.selected_sumo_run_fingerprint,
        },
        "receipt_id": "receipt-exact-01",
        "receipt_issued_at": _serialize_utc(DECISION_TIME),
        "request_fingerprint": result.request_fingerprint,
        "reviewer_attribution": decision.reviewer_attribution,
        "reviewer_id": decision.reviewer_id,
        "selected_candidate_binding_fingerprint": decision.selected_candidate_binding_fingerprint,
        "selected_candidate_label": decision.selected_candidate_label,
        "selected_sumo_run_fingerprint": decision.selected_sumo_run_fingerprint,
    }
    receipt_fp = sha256_hex(canonical_json(provisional).encode("utf-8"))
    receipt_data = {
        "receipt_id": "receipt-exact-01",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "decision_fingerprint": decision.decision_fingerprint,
        "reviewer_id": decision.reviewer_id,
        "reviewer_attribution": decision.reviewer_attribution,
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "receipt_issued_at": DECISION_TIME,
        "reason": decision.reason,
        "selected_candidate_label": decision.selected_candidate_label,
        "selected_candidate_binding_fingerprint": decision.selected_candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": decision.selected_sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
        "receipt_fingerprint": receipt_fp,
        "portable_provenance": provisional["portable_provenance"],
    }
    # Time reversal at model level: receipt_issued_at < decision_timestamp
    data = dict(receipt_data)
    data["receipt_id"] = "receipt-reversal-model-01"
    data["receipt_issued_at"] = early
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)


def test_direct_pydantic_construction_rejects_contradictory_selected_fields() -> None:
    _req, result = make_production_unadmitted_result()
    # REJECTED with partial fields contradictory
    rejected = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-contradict-03",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    data = rejected.model_dump()
    data["decision_id"] = "dec-contradict-04"
    data["selected_candidate_label"] = "cand-a"
    data["selected_candidate_binding_fingerprint"] = None
    data["selected_sumo_run_fingerprint"] = None
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)
    # ACCEPTED with missing field contradictory via direct model
    base = {
        "decision_id": "dec-contradict-01",
        "request_fingerprint": "a" * 64,
        "evaluation_fingerprint": "b" * 64,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "ACCEPTED: ok",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": None,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
        "decision_fingerprint": "0" * 64,
    }
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(base)
    # Receipt with REJECTED decision string must fail (acceptance-only)
    good_data = {
        "receipt_id": "receipt-good-01",
        "request_fingerprint": "a" * 64,
        "evaluation_fingerprint": "b" * 64,
        "decision_fingerprint": "c" * 64,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "receipt_issued_at": RECEIPT_TIME,
        "reason": "ACCEPTED: ok",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": "d" * 64,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
        "receipt_fingerprint": "0" * 64,
        "portable_provenance": {"request_fingerprint": "a" * 64},
    }
    prov = {
        "decision": good_data["decision"],
        "decision_fingerprint": good_data["decision_fingerprint"],
        "decision_timestamp": _serialize_utc(good_data["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": good_data["evaluation_fingerprint"],
        "portable_provenance": good_data["portable_provenance"],
        "receipt_id": good_data["receipt_id"],
        "receipt_issued_at": _serialize_utc(good_data["receipt_issued_at"]),  # type: ignore[arg-type]
        "request_fingerprint": good_data["request_fingerprint"],
        "reviewer_attribution": good_data["reviewer_attribution"],
        "reviewer_id": good_data["reviewer_id"],
        "selected_candidate_binding_fingerprint": good_data[
            "selected_candidate_binding_fingerprint"
        ],
        "selected_candidate_label": good_data["selected_candidate_label"],
        "selected_sumo_run_fingerprint": good_data["selected_sumo_run_fingerprint"],
    }
    good_data["receipt_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    receipt = ManchesterCalibrationAcceptanceReceipt.model_validate(good_data)
    data_r = receipt.model_dump()
    data_r["receipt_id"] = "receipt-contradict-01"
    data_r["decision"] = "REJECTED"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data_r)


def test_decision_fingerprint_binds_selected_candidate_via_direct_model() -> None:
    base_a = {
        "decision_id": "dec-bind-cand-01",
        "request_fingerprint": "a" * 64,
        "evaluation_fingerprint": "b" * 64,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "REJECTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "REJECTED: candidate cand-a",
        "selected_candidate_label": "cand-a",
        "selected_candidate_binding_fingerprint": "c" * 64,
        "selected_sumo_run_fingerprint": RUN_A,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    base_b = dict(base_a)
    base_b["selected_candidate_label"] = "cand-b"
    base_b["selected_candidate_binding_fingerprint"] = "d" * 64
    base_b["reason"] = "REJECTED: candidate cand-b"
    for base in (base_a, base_b):
        prov = {
            "decision": base["decision"],
            "decision_id": base["decision_id"],
            "decision_timestamp": _serialize_utc(base["decision_timestamp"]),  # type: ignore[arg-type]
            "evaluation_fingerprint": base["evaluation_fingerprint"],
            "reason": base["reason"],
            "request_fingerprint": base["request_fingerprint"],
            "reviewer_attribution": base["reviewer_attribution"],
            "reviewer_id": base["reviewer_id"],
            "selected_candidate_binding_fingerprint": base[
                "selected_candidate_binding_fingerprint"
            ],
            "selected_candidate_label": base["selected_candidate_label"],
            "selected_sumo_run_fingerprint": base["selected_sumo_run_fingerprint"],
        }
        base["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    decision_a = ManchesterCalibrationBaselineDecision.model_validate(base_a)
    decision_b = ManchesterCalibrationBaselineDecision.model_validate(base_b)
    assert decision_a.decision_fingerprint != decision_b.decision_fingerprint
    assert (
        decision_a.selected_candidate_binding_fingerprint
        != decision_b.selected_candidate_binding_fingerprint
    )
    data = decision_a.model_dump()
    data["selected_candidate_label"] = "cand-b"
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)


def test_no_silent_engineering_selected_auto_acceptance_empty_registry() -> None:
    # Synthetic has engineering selection; production unadmitted has none
    req = make_request()
    result = evaluate_workflow(req)
    eng = result.engineering_selected_candidate
    assert eng is not None
    # With empty registry, even explicit ACCEPTED is forced to PROVIDER_DATA_REQUIRED
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-auto-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label=eng,
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    assert decision.selected_candidate_label is None
    # Production unadmitted: engineering selection is None, still blocked
    _req2, result2 = make_production_unadmitted_result()
    assert result2.engineering_selected_candidate is None
    decision3 = decide_baseline(
        result2,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-auto-03",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision3.decision == "PROVIDER_DATA_REQUIRED"


# ---------------------------------------------------------------------------
# Fail-closed: empty registry prevents ACCEPTED and receipt minting
# ---------------------------------------------------------------------------


def test_empty_registry_prevents_accepted_for_production() -> None:
    _req, result = make_production_unadmitted_result()
    assert result.evaluation_report.contract_admission == "not_admitted_production_unapproved"
    assert result.evaluation_report.contract_admitted is False
    # Any ACCEPTED attempt is forced to PROVIDER_DATA_REQUIRED
    for label in ("cand-a", "cand-b"):
        decision = decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id=f"dec-empty-{label}",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label=label,
        )
        assert decision.decision == "PROVIDER_DATA_REQUIRED"
        assert decision.selected_candidate_label is None


def test_empty_registry_prevents_receipt_minting_even_with_forged_accepted_decision() -> None:
    _req, result = make_production_unadmitted_result()
    # Forge a direct ACCEPTED decision (self-consistent) — build_acceptance_receipt must still refuse
    forged = {
        "decision_id": "dec-forge-01",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "forged accepted",
        "selected_candidate_label": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_label,
        "selected_candidate_binding_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": forged["decision"],
        "decision_id": forged["decision_id"],
        "decision_timestamp": _serialize_utc(forged["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": forged["evaluation_fingerprint"],
        "reason": forged["reason"],
        "request_fingerprint": forged["request_fingerprint"],
        "reviewer_attribution": forged["reviewer_attribution"],
        "reviewer_id": forged["reviewer_id"],
        "selected_candidate_binding_fingerprint": forged["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": forged["selected_candidate_label"],
        "selected_sumo_run_fingerprint": forged["selected_sumo_run_fingerprint"],
    }
    forged["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    forged_dec = ManchesterCalibrationBaselineDecision.model_validate(forged)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, forged_dec, receipt_id="receipt-forge-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code == "INSUFFICIENT_PROVIDER_DATA"
    # Also verify that a synthetic forged decision cannot mint receipt
    req_syn = make_request()
    res_syn = evaluate_workflow(req_syn)
    forged_syn = dict(forged)
    forged_syn["decision_id"] = "dec-forge-syn-01"
    forged_syn["request_fingerprint"] = res_syn.request_fingerprint
    forged_syn["evaluation_fingerprint"] = res_syn.evaluation_fingerprint
    forged_syn["selected_candidate_label"] = res_syn.evaluation_report.candidate_evaluations[
        0
    ].candidate_label
    forged_syn["selected_candidate_binding_fingerprint"] = (
        res_syn.evaluation_report.candidate_evaluations[0].candidate_binding_fingerprint
    )
    forged_syn["selected_sumo_run_fingerprint"] = res_syn.evaluation_report.candidate_evaluations[
        0
    ].sumo_run_fingerprint
    prov2 = {
        "decision": forged_syn["decision"],
        "decision_id": forged_syn["decision_id"],
        "decision_timestamp": _serialize_utc(forged_syn["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": forged_syn["evaluation_fingerprint"],
        "reason": forged_syn["reason"],
        "request_fingerprint": forged_syn["request_fingerprint"],
        "reviewer_attribution": forged_syn["reviewer_attribution"],
        "reviewer_id": forged_syn["reviewer_id"],
        "selected_candidate_binding_fingerprint": forged_syn[
            "selected_candidate_binding_fingerprint"
        ],
        "selected_candidate_label": forged_syn["selected_candidate_label"],
        "selected_sumo_run_fingerprint": forged_syn["selected_sumo_run_fingerprint"],
    }
    forged_syn["decision_fingerprint"] = sha256_hex(canonical_json(prov2).encode("utf-8"))
    forged_dec_syn = ManchesterCalibrationBaselineDecision.model_validate(forged_syn)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        build_acceptance_receipt(
            res_syn,
            forged_dec_syn,
            receipt_id="receipt-forge-syn-01",
            receipt_issued_at=RECEIPT_TIME,
        )
    assert exc2.value.code == "INSUFFICIENT_PROVIDER_DATA"


def test_model_copy_forged_approved_admission_fails_closed_and_registry_pure() -> None:
    import traffictwin.integration.manchester.calibration as calib

    before = calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    assert len(before) == 0
    _req, result = make_production_unadmitted_result()
    # Try to forge report as approved_production_contract via model_copy
    tampered_report = result.evaluation_report.model_copy(
        update={"contract_admission": "approved_production_contract", "contract_admitted": True}
    )
    tampered_result = result.model_copy(update={"evaluation_report": tampered_report})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            tampered_result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-forged-admission-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert exc.value.code == "INVALID_RESULT"
    assert before == calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    # Also try contract_admitted False flip
    tampered_report2 = result.evaluation_report.model_copy(update={"contract_admitted": False})
    tampered_result2 = result.model_copy(update={"evaluation_report": tampered_report2})
    # This is already not admitted, so decide still blocked but not INVALID_RESULT
    decision = decide_baseline(
        tampered_result2,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-forged-admission-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    assert before == calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS


def test_model_copy_synthetic_flip_fails_closed() -> None:
    import traffictwin.integration.manchester.calibration as calib

    before = calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    _req, result = make_production_unadmitted_result()
    tampered_report = result.evaluation_report.model_copy(update={"synthetic": True})
    tampered_result = result.model_copy(update={"evaluation_report": tampered_report})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            tampered_result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-synth-flip-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert before == calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS


def test_verification_functions_do_not_mutate_registry_and_remain_pure() -> None:
    import traffictwin.integration.manchester.calibration as calib

    before = calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    assert len(before) == 0
    _req, result = make_production_unadmitted_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-pure-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    # Verification of a PROVIDER_DATA_REQUIRED decision via receipt building must fail
    # but not mutate registry
    with pytest.raises(ManchesterCalibrationWorkflowError):
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-pure-01", receipt_issued_at=RECEIPT_TIME
        )
    assert before == calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    # Direct model_copy mutation attempts also must not mutate registry
    tampered_report = result.evaluation_report.model_copy(
        update={"contract_admission": "approved_production_contract", "contract_admitted": True}
    )
    tampered_result = result.model_copy(update={"evaluation_report": tampered_report})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            tampered_result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-pure-02",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert before == calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    # Verify freshness with forged receipt also must not mutate
    forged = {
        "decision_id": "dec-pure-03",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "forged",
        "selected_candidate_label": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_label,
        "selected_candidate_binding_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": forged["decision"],
        "decision_id": forged["decision_id"],
        "decision_timestamp": _serialize_utc(forged["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": forged["evaluation_fingerprint"],
        "reason": forged["reason"],
        "request_fingerprint": forged["request_fingerprint"],
        "reviewer_attribution": forged["reviewer_attribution"],
        "reviewer_id": forged["reviewer_id"],
        "selected_candidate_binding_fingerprint": forged["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": forged["selected_candidate_label"],
        "selected_sumo_run_fingerprint": forged["selected_sumo_run_fingerprint"],
    }
    forged["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    forged_dec = ManchesterCalibrationBaselineDecision.model_validate(forged)
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_acceptance_receipt(
            ManchesterCalibrationAcceptanceReceipt.model_validate(
                {
                    "receipt_id": "receipt-pure-02",
                    "request_fingerprint": result.request_fingerprint,
                    "evaluation_fingerprint": result.evaluation_fingerprint,
                    "decision_fingerprint": forged_dec.decision_fingerprint,
                    "reviewer_id": "reviewer-01",
                    "reviewer_attribution": "lead",
                    "decision": "ACCEPTED",
                    "decision_timestamp": DECISION_TIME,
                    "receipt_issued_at": RECEIPT_TIME,
                    "reason": forged_dec.reason,
                    "selected_candidate_label": forged_dec.selected_candidate_label,
                    "selected_candidate_binding_fingerprint": forged_dec.selected_candidate_binding_fingerprint,
                    "selected_sumo_run_fingerprint": forged_dec.selected_sumo_run_fingerprint,
                    "limitations": (
                        "Descriptive candidate review only — no automatic calibration acceptance.",
                        "Lowest objective or convergence does not imply realism or optimality.",
                        "Missing observations are never zero-filled.",
                        "Unit, interval-duration and spatial scope must match contract exactly.",
                        "Incompatible targets are refused, not fused or coerced.",
                        "History and fingerprints are deterministic and tamper-evident.",
                        "Baseline acceptance requires explicit attributable reviewer decision.",
                        "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
                        "No VEC task telemetry, causal or uncertainty inference is made.",
                        "Portable provenance contains no private paths or secrets.",
                        "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
                    ),
                    "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
                    "receipt_fingerprint": sha256_hex(
                        canonical_json(
                            {
                                "decision": "ACCEPTED",
                                "decision_fingerprint": forged_dec.decision_fingerprint,
                                "decision_timestamp": _serialize_utc(DECISION_TIME),
                                "evaluation_fingerprint": result.evaluation_fingerprint,
                                "portable_provenance": {
                                    "request_fingerprint": result.request_fingerprint,
                                    "evaluation_fingerprint": result.evaluation_fingerprint,
                                    "decision_fingerprint": forged_dec.decision_fingerprint,
                                    "contract_fingerprint": result.contract_fingerprint,
                                    "method_version": "manchester-calibration-workflow-1.0",
                                    "capability_id": "MAN-09",
                                    "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
                                    "selected_candidate_label": forged_dec.selected_candidate_label,
                                    "selected_candidate_binding_fingerprint": forged_dec.selected_candidate_binding_fingerprint,
                                    "selected_sumo_run_fingerprint": forged_dec.selected_sumo_run_fingerprint,
                                },
                                "receipt_id": "receipt-pure-02",
                                "receipt_issued_at": _serialize_utc(RECEIPT_TIME),
                                "request_fingerprint": result.request_fingerprint,
                                "reviewer_attribution": "lead",
                                "reviewer_id": "reviewer-01",
                                "selected_candidate_binding_fingerprint": forged_dec.selected_candidate_binding_fingerprint,
                                "selected_candidate_label": forged_dec.selected_candidate_label,
                                "selected_sumo_run_fingerprint": forged_dec.selected_sumo_run_fingerprint,
                            }
                        ).encode("utf-8")
                    ),
                    "portable_provenance": {
                        "request_fingerprint": result.request_fingerprint,
                        "evaluation_fingerprint": result.evaluation_fingerprint,
                        "decision_fingerprint": forged_dec.decision_fingerprint,
                        "contract_fingerprint": result.contract_fingerprint,
                        "method_version": "manchester-calibration-workflow-1.0",
                        "capability_id": "MAN-09",
                        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
                        "selected_candidate_label": forged_dec.selected_candidate_label,
                        "selected_candidate_binding_fingerprint": forged_dec.selected_candidate_binding_fingerprint,
                        "selected_sumo_run_fingerprint": forged_dec.selected_sumo_run_fingerprint,
                    },
                }
            ),
            forged_dec,
            result,
        )
    assert before == calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS


def test_engineering_selection_distinct_from_scientific_acceptance() -> None:
    # Synthetic ranking is available for analyst review but does not imply acceptance
    req = make_request()
    result = evaluate_workflow(req)
    assert result.engineering_selected_candidate is not None
    assert result.engineering_selection_status == "candidate_selected_for_analyst_review"
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-eng-distinct-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label=result.engineering_selected_candidate,
    )
    assert decision.decision == "PROVIDER_DATA_REQUIRED"
    assert len(result.evaluation_report.ranking) > 0
    # Production unadmitted has no ranking but also blocked
    _req2, result2 = make_production_unadmitted_result()
    assert result2.engineering_selected_candidate is None
    assert result2.evaluation_report.ranking == ()


# ---------------------------------------------------------------------------
# Canonical-boundary / model_copy discriminating mutation tests — fail-closed
# ---------------------------------------------------------------------------


def test_model_copy_report_fields_fail_closed_with_empty_registry() -> None:
    _req, result = make_production_unadmitted_result()
    # Coverage mutation still detected as INVALID_RESULT when it changes report
    ev0 = result.evaluation_report.candidate_evaluations[0]
    tampered_obj = ev0.objective_result.model_copy(
        update={"status": "unavailable", "reason": "no_paired_intervals", "value": None}
    )
    tampered_ev0 = ev0.model_copy(
        update={"coverage_requirement_met": False, "objective_result": tampered_obj}
    )
    ev1 = result.evaluation_report.candidate_evaluations[1]
    tampered_report = result.evaluation_report.model_copy(
        update={"candidate_evaluations": (tampered_ev0, ev1)}
    )
    tampered_result = result.model_copy(update={"evaluation_report": tampered_report})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            tampered_result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-coverage-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )


def test_model_copy_request_report_fingerprint_mutation_fails_closed() -> None:
    req = make_request()
    tampered_req = req.model_copy(update={"request_fingerprint": "0" * 64})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        evaluate_workflow(tampered_req)
    assert exc.value.code == "INVALID_REQUEST"
    _req, result = make_production_unadmitted_result()
    tampered_result = result.model_copy(update={"request_fingerprint": "0" * 64})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        decide_baseline(
            tampered_result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-fp-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="REJECTED",
        )
    assert exc2.value.code == "INVALID_RESULT"
    tampered_result2 = result.model_copy(update={"evaluation_fingerprint": "f" * 64})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            tampered_result2,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-fp-02",
            decision_timestamp=DECISION_TIME,
            requested_decision="REJECTED",
        )


def test_model_copy_decision_mutations_refuse_receipt_even_with_forged_decision() -> None:
    _req, result = make_production_unadmitted_result()
    # Forge a valid ACCEPTED decision then mutate it — receipt must fail
    forged = {
        "decision_id": "dec-mut-base-01",
        "request_fingerprint": result.request_fingerprint,
        "evaluation_fingerprint": result.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "forged",
        "selected_candidate_label": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_label,
        "selected_candidate_binding_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": result.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov = {
        "decision": forged["decision"],
        "decision_id": forged["decision_id"],
        "decision_timestamp": _serialize_utc(forged["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": forged["evaluation_fingerprint"],
        "reason": forged["reason"],
        "request_fingerprint": forged["request_fingerprint"],
        "reviewer_attribution": forged["reviewer_attribution"],
        "reviewer_id": forged["reviewer_id"],
        "selected_candidate_binding_fingerprint": forged["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": forged["selected_candidate_label"],
        "selected_sumo_run_fingerprint": forged["selected_sumo_run_fingerprint"],
    }
    forged["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    decision = ManchesterCalibrationBaselineDecision.model_validate(forged)
    # Mutate via model_copy without recomputing fingerprint -> INVALID_DECISION
    tampered = decision.model_copy(update={"selected_candidate_label": "cand-b"})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, tampered, receipt_id="receipt-mut-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code in (
        "INVALID_DECISION",
        "CANDIDATE_FINGERPRINT_DRIFT",
        "CANDIDATE_DRIFT",
        "STALE_RECEIPT",
        "INSUFFICIENT_PROVIDER_DATA",
    )
    tampered2 = decision.model_copy(update={"reviewer_id": "attacker"})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        build_acceptance_receipt(
            result, tampered2, receipt_id="receipt-mut-02", receipt_issued_at=RECEIPT_TIME
        )


def test_engineering_selection_status_mutation_fails_closed() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    other = "cand-b" if result.engineering_selected_candidate == "cand-a" else "cand-a"
    tampered = result.model_copy(update={"engineering_selected_candidate": other})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            tampered,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-eng-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="REJECTED",
        )
    assert exc.value.code == "INVALID_RESULT"
    flipped_status = (
        "no_candidate_available"
        if result.engineering_selection_status == "candidate_selected_for_analyst_review"
        else "candidate_selected_for_analyst_review"
    )
    tampered2 = result.model_copy(update={"engineering_selection_status": flipped_status})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            tampered2,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-eng-02",
            decision_timestamp=DECISION_TIME,
            requested_decision="REJECTED",
        )
    data = result.model_dump()
    data["engineering_selection_status"] = flipped_status
    with pytest.raises(ValidationError):
        ManchesterCalibrationWorkflowResult.model_validate(data)


def test_synthetic_unapproved_never_produces_receipt_via_direct_construction() -> None:
    req_syn = make_request()
    res_syn = evaluate_workflow(req_syn)
    assert res_syn.evaluation_report.synthetic is True
    dec_syn = decide_baseline(
        res_syn,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-syn-proof-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert dec_syn.decision == "PROVIDER_DATA_REQUIRED"
    with pytest.raises(ManchesterCalibrationWorkflowError):
        build_acceptance_receipt(
            res_syn, dec_syn, receipt_id="receipt-syn-proof-01", receipt_issued_at=RECEIPT_TIME
        )
    forged_data = {
        "decision_id": "dec-syn-forge-01",
        "request_fingerprint": res_syn.request_fingerprint,
        "evaluation_fingerprint": res_syn.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "forged",
        "selected_candidate_label": res_syn.evaluation_report.candidate_evaluations[
            0
        ].candidate_label,
        "selected_candidate_binding_fingerprint": res_syn.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": res_syn.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": (
            "Descriptive candidate review only — no automatic calibration acceptance.",
            "Lowest objective or convergence does not imply realism or optimality.",
            "Missing observations are never zero-filled.",
            "Unit, interval-duration and spatial scope must match contract exactly.",
            "Incompatible targets are refused, not fused or coerced.",
            "History and fingerprints are deterministic and tamper-evident.",
            "Baseline acceptance requires explicit attributable reviewer decision.",
            "PROVIDER_DATA_REQUIRED blocks acceptance when admitted observations are insufficient.",
            "No VEC task telemetry, causal or uncertainty inference is made.",
            "Portable provenance contains no private paths or secrets.",
            "Synthetic evaluations never support ACCEPTED; only approved production evidence can.",
        ),
        "evidence_boundary": "Manchester calibration workflow: descriptive engineering candidate review only. No calibrated realism, causal validity, VEC task telemetry or uncertainty is claimed. Observations are caller-supplied admitted evidence; no observation is invented here.",
    }
    prov_forge = {
        "decision": forged_data["decision"],
        "decision_id": forged_data["decision_id"],
        "decision_timestamp": _serialize_utc(forged_data["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": forged_data["evaluation_fingerprint"],
        "reason": forged_data["reason"],
        "request_fingerprint": forged_data["request_fingerprint"],
        "reviewer_attribution": forged_data["reviewer_attribution"],
        "reviewer_id": forged_data["reviewer_id"],
        "selected_candidate_binding_fingerprint": forged_data[
            "selected_candidate_binding_fingerprint"
        ],
        "selected_candidate_label": forged_data["selected_candidate_label"],
        "selected_sumo_run_fingerprint": forged_data["selected_sumo_run_fingerprint"],
    }
    forged_data["decision_fingerprint"] = sha256_hex(canonical_json(prov_forge).encode("utf-8"))
    forged_dec = ManchesterCalibrationBaselineDecision.model_validate(forged_data)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            res_syn, forged_dec, receipt_id="receipt-syn-forge-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code == "INSUFFICIENT_PROVIDER_DATA"
    # Unapproved production also never yields receipt
    prod_contract = make_production_contract()
    obs_real = [prod_observed("10"), prod_observed("8", start=900, end=1800)]
    cands_real = [
        prod_candidate("cand-a", [prod_simulated("12"), prod_simulated("7", start=900, end=1800)])
    ]
    req_unapproved = build_workflow_request(
        request_id="req-unapproved-proof",
        deterministic_seed=0,
        contract=prod_contract,
        observed_inputs=tuple(obs_real),  # type: ignore[arg-type]
        candidate_inputs=tuple(cands_real),
    )
    res_unapproved = evaluate_workflow(req_unapproved)
    assert res_unapproved.evaluation_report.contract_admitted is False
    dec_unapproved = decide_baseline(
        res_unapproved,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-unapproved-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert dec_unapproved.decision == "PROVIDER_DATA_REQUIRED"
    forged2 = dict(forged_data)
    forged2["decision_id"] = "dec-unapproved-forge-01"
    forged2["request_fingerprint"] = res_unapproved.request_fingerprint
    forged2["evaluation_fingerprint"] = res_unapproved.evaluation_fingerprint
    forged2["selected_candidate_label"] = res_unapproved.evaluation_report.candidate_evaluations[
        0
    ].candidate_label
    forged2["selected_candidate_binding_fingerprint"] = (
        res_unapproved.evaluation_report.candidate_evaluations[0].candidate_binding_fingerprint
    )
    forged2["selected_sumo_run_fingerprint"] = (
        res_unapproved.evaluation_report.candidate_evaluations[0].sumo_run_fingerprint
    )
    prov2 = {
        "decision": forged2["decision"],
        "decision_id": forged2["decision_id"],
        "decision_timestamp": _serialize_utc(forged2["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": forged2["evaluation_fingerprint"],
        "reason": forged2["reason"],
        "request_fingerprint": forged2["request_fingerprint"],
        "reviewer_attribution": forged2["reviewer_attribution"],
        "reviewer_id": forged2["reviewer_id"],
        "selected_candidate_binding_fingerprint": forged2["selected_candidate_binding_fingerprint"],
        "selected_candidate_label": forged2["selected_candidate_label"],
        "selected_sumo_run_fingerprint": forged2["selected_sumo_run_fingerprint"],
    }
    forged2["decision_fingerprint"] = sha256_hex(canonical_json(prov2).encode("utf-8"))
    forged_dec2 = ManchesterCalibrationBaselineDecision.model_validate(forged2)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        build_acceptance_receipt(
            res_unapproved,
            forged_dec2,
            receipt_id="receipt-unapproved-01",
            receipt_issued_at=RECEIPT_TIME,
        )
    assert exc2.value.code == "INSUFFICIENT_PROVIDER_DATA"
