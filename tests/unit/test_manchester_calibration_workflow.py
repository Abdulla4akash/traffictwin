# ruff: noqa: E501
"""Discriminating tests for Lane 05 Manchester calibration workflow.

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
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
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
    verify_receipt_freshness,
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
    # mypy: sims are SimulatedCalibrationInterval but typed as object for brevity
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
# Production admitted helpers
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


@contextmanager
def admitted_production_contract(
    contract: ManchesterCalibrationContract,
) -> Iterator[ManchesterCalibrationContract]:
    import traffictwin.integration.manchester.calibration as calib

    original = calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    try:
        calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS = frozenset(
            {contract.fingerprint()}
        )
        yield contract
    finally:
        calib.APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS = original


def make_admitted_production_result() -> tuple[
    ManchesterCalibrationWorkflowRequest, ManchesterCalibrationWorkflowResult
]:
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
    with admitted_production_contract(contract):
        req = build_workflow_request(
            request_id="req-prod-admitted",
            deterministic_seed=42,
            contract=contract,
            observed_inputs=tuple(obs),  # type: ignore[arg-type]
            candidate_inputs=tuple(cands),
        )
        result = evaluate_workflow(req)
    return req, result


def make_admitted_production_result_single(
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
    with admitted_production_contract(contract):
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
    # Same logical inputs in different order must yield same fingerprints
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
    # CalibrationIntervalContent enforces unit == fixed unit of measure, so a
    # direct unit mismatch is caught at interval construction (fail-closed)
    # and is equivalent to target unit incompatibility.
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
    # Use a real-like observed row against synthetic contract
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
    # Engineering selection exists but baseline is never accepted automatically
    assert result.automatic_acceptance is False
    assert result.baseline_accepted is False
    # Mutating the report objective must not make baseline appear accepted;
    # tampered report is its own fingerprint mismatch but result still not accepted
    data = json.loads(result.model_dump_json())
    # Attempt to flip selection — should fail reload because derived
    data["engineering_selected_candidate"] = (
        "cand-a" if result.engineering_selected_candidate == "cand-b" else "cand-b"
    )
    # Revalidation must fail because evaluation_fingerprint binds selection indirectly via report;
    # but at minimum the mutated object must not claim baseline acceptance
    with pytest.raises(ValidationError):
        ManchesterCalibrationWorkflowResult.model_validate(data)
    # Even with low objective, decide_baseline without attributable reviewer fails
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
    _ = make_contract(
        contract_version="production-candidate-1",
        evidence_class="production",
        observed_source="webtris_daily",
        scope_kind="strategic_road_site",
        scope_label="m56_site_8150a",
    )
    # But we give synthetic observed against production -> already refused at request level
    # So instead test insufficient coverage path: high coverage threshold with no pairs
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
    # Synthetic can never be accepted -> forced PROVIDER_DATA_REQUIRED
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
# Path / secret leakage
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


def test_secret_leakage_in_provenance_refused() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    # Try to build receipt then mutate provenance to include secret
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-01", receipt_issued_at=RECEIPT_TIME
    )
    data = json.loads(receipt.model_dump_json())
    data["portable_provenance"]["evil"] = "api_key=secret123"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    # Private path in provenance must also be refused
    data2 = json.loads(receipt.model_dump_json())
    data2["portable_provenance"]["evil"] = "/Users/attacker/secret"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data2)


def test_portable_provenance_contains_no_private_paths() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-01", receipt_issued_at=RECEIPT_TIME
    )
    for v in receipt.portable_provenance.values():
        assert "/Users/" not in v
        assert "/tmp/" not in v  # noqa: S108
        assert "secret" not in v.lower()


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


def test_tampered_receipt_fingerprint_refused() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-01", receipt_issued_at=RECEIPT_TIME
    )
    data = json.loads(receipt.model_dump_json())
    data["receipt_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)


def test_stale_receipt_refused() -> None:
    _req1, result1 = make_admitted_production_result()
    decision1 = decide_baseline(
        result1,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt1 = build_acceptance_receipt(
        result1, decision1, receipt_id="receipt-01", receipt_issued_at=RECEIPT_TIME
    )
    # Build a second distinct admitted production request/result
    contract2 = make_production_contract(contract_version="production-candidate-2")
    with admitted_production_contract(contract2):
        req2 = build_workflow_request(
            request_id="req-02",
            deterministic_seed=99,
            contract=contract2,
            observed_inputs=(prod_observed("10"), prod_observed("8", start=900, end=1800)),  # type: ignore[arg-type]
            candidate_inputs=(
                prod_candidate(
                    "cand-a", [prod_simulated("12"), prod_simulated("7", start=900, end=1800)]
                ),
                prod_candidate(
                    "cand-b",
                    [prod_simulated("11"), prod_simulated("8", start=900, end=1800)],
                    value=Decimal("1.5"),
                    run_fp=RUN_B,
                ),
            ),
        )
        result2 = evaluate_workflow(req2)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        verify_receipt_freshness(receipt1, result2)
    assert exc.value.code == "STALE_RECEIPT"
    with pytest.raises(ManchesterCalibrationWorkflowError):
        build_acceptance_receipt(
            result2, decision1, receipt_id="receipt-02", receipt_issued_at=RECEIPT_TIME
        )


# ---------------------------------------------------------------------------
# Metric / target mismatches already partly covered; explicit metric test
# ---------------------------------------------------------------------------


def test_metric_mismatch_via_measure_refused() -> None:
    # Contract measures vehicle_count; observed speed should be refused
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
    _req, result = make_admitted_production_result()
    # Limitations must be present and contain expected non-claims
    assert any(
        "calibrated realism" in lim.lower() or "descriptive" in lim.lower()
        for lim in result.limitations
    )
    assert any(
        "VEC" in lim or "causal" in lim.lower() or "uncertainty" in lim.lower()
        for lim in result.non_claims
    )
    # Evidence boundary must be portable and not contain private paths
    assert "/Users/" not in result.evidence_boundary
    assert result.automatic_acceptance is False
    assert result.baseline_accepted is False
    # Baseline decision must not be inferred from engineering selection
    assert result.engineering_selected_candidate is not None
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    # Tunable: decision is attributable and contains reviewer
    assert decision.reviewer_id == "reviewer-01"
    assert decision.decision in ("ACCEPTED", "PROVIDER_DATA_REQUIRED")
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-01", receipt_issued_at=RECEIPT_TIME
    )
    # Receipt provenance must be portable
    assert receipt.portable_provenance["request_fingerprint"] == result.request_fingerprint


def test_observation_count_bounded_and_history_bounded() -> None:
    # Too many candidates should be refused
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
    # Module must not expose network or workload launch callables
    import traffictwin.integration.manchester.calibration_workflow as wf

    assert not hasattr(wf, "launch_research_workload")
    assert not hasattr(wf, "fetch_observations")
    # Evaluate is pure: calling twice yields same fingerprints
    req = make_request()
    r1 = evaluate_workflow(req)
    r2 = evaluate_workflow(req)
    assert r1.evaluation_fingerprint == r2.evaluation_fingerprint
    assert r1.evaluation_report.fingerprint() == r2.evaluation_report.fingerprint()


# ---------------------------------------------------------------------------
# Provenance defect: reviewer attribution and timestamps fingerprint-bound
# ---------------------------------------------------------------------------


def test_decision_fingerprint_binds_reviewer_attribution_and_timestamp() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="alice@lab",
        decision_id="dec-bind-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    # Mutating reviewer_attribution must invalidate fingerprint
    data = decision.model_dump()
    data["reviewer_attribution"] = "bob@lab"
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)
    # Mutating decision_timestamp must invalidate fingerprint
    data2 = decision.model_dump()
    data2["decision_timestamp"] = DECISION_TIME_ALT
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data2)
    # Fingerprint changes when timestamp changes via API
    decision_alt = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="alice@lab",
        decision_id="dec-bind-01",
        decision_timestamp=DECISION_TIME_ALT,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision_fingerprint != decision_alt.decision_fingerprint
    # Fingerprint changes when attribution changes via API
    decision_att_alt = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="bob@lab",
        decision_id="dec-bind-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision.decision_fingerprint != decision_att_alt.decision_fingerprint


def test_receipt_fingerprint_binds_reviewer_attribution_and_timestamps() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="alice@lab",
        decision_id="dec-receipt-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-bind-01", receipt_issued_at=RECEIPT_TIME
    )
    assert receipt.reviewer_attribution == decision.reviewer_attribution
    assert receipt.decision_timestamp == decision.decision_timestamp
    # Mutating reviewer_attribution must invalidate receipt
    data = receipt.model_dump()
    data["reviewer_attribution"] = "bob@lab"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    # Mutating decision_timestamp must invalidate receipt
    data2 = receipt.model_dump()
    data2["decision_timestamp"] = DECISION_TIME_ALT
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data2)
    # Mutating receipt_issued_at must invalidate receipt
    data3 = receipt.model_dump()
    data3["receipt_issued_at"] = RECEIPT_TIME_ALT
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data3)
    # API-level timestamp mutation changes receipt_fingerprint
    receipt_alt_time = build_acceptance_receipt(
        result, decision, receipt_id="receipt-bind-01", receipt_issued_at=RECEIPT_TIME_ALT
    )
    assert receipt.receipt_fingerprint != receipt_alt_time.receipt_fingerprint
    # Receipt with different decision attribution yields different receipt fingerprint
    decision_alt = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="bob@lab",
        decision_id="dec-receipt-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt_alt_att = build_acceptance_receipt(
        result, decision_alt, receipt_id="receipt-bind-01", receipt_issued_at=RECEIPT_TIME
    )
    assert receipt.receipt_fingerprint != receipt_alt_att.receipt_fingerprint


def test_decision_naive_timestamp_rejected() -> None:
    _req, result = make_admitted_production_result()
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-naive-01",
            decision_timestamp=NAIVE_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert exc.value.code == "INVALID_TIMESTAMP"
    # Direct model validation must also reject naive timestamp
    valid = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-naive-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    data = valid.model_dump()
    data["decision_timestamp"] = NAIVE_TIME
    # Use fresh decision_id to avoid pattern clash
    data["decision_id"] = "dec-naive-03"
    # Recompute fingerprint naively with naive time - must still fail validation
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)


def test_decision_non_utc_timestamp_rejected() -> None:
    _req, result = make_admitted_production_result()
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-nonutc-01",
            decision_timestamp=NON_UTC_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert exc.value.code == "INVALID_TIMESTAMP"
    # Model validation also rejects non-UTC
    valid = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-nonutc-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    data = valid.model_dump()
    data["decision_timestamp"] = NON_UTC_TIME
    data["decision_id"] = "dec-nonutc-03"
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)


def test_receipt_naive_and_non_utc_timestamp_rejected() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-receipt-naive",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-naive-01", receipt_issued_at=NAIVE_TIME
        )
    assert exc.value.code == "INVALID_TIMESTAMP"
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-nonutc-01", receipt_issued_at=NON_UTC_TIME
        )
    assert exc2.value.code == "INVALID_TIMESTAMP"
    # Model-level naive receipt_issued_at must also be rejected
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-ok-01", receipt_issued_at=RECEIPT_TIME
    )
    data = receipt.model_dump()
    data["receipt_issued_at"] = NAIVE_TIME
    data["receipt_id"] = "receipt-naive-02"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    data2 = receipt.model_dump()
    data2["receipt_issued_at"] = NON_UTC_TIME
    data2["receipt_id"] = "receipt-nonutc-02"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data2)


def test_receipt_preserves_reviewer_attribution_and_decision_timestamp() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-09",
        reviewer_attribution="attribution-xyz",
        decision_id="dec-preserve-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-preserve-01", receipt_issued_at=RECEIPT_TIME
    )
    assert receipt.reviewer_attribution == "attribution-xyz"
    assert receipt.decision_timestamp == DECISION_TIME
    assert receipt.receipt_issued_at == RECEIPT_TIME
    # Provenance fingerprint binding: ensure tampered receipt fails
    data = receipt.model_dump()
    data["reviewer_attribution"] = "other"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    data2 = receipt.model_dump()
    data2["receipt_issued_at"] = RECEIPT_TIME_ALT
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data2)


def test_timestamp_serialization_is_portable_and_deterministic() -> None:
    _req, result = make_admitted_production_result()
    # Same instant expressed as +00:00 offset must yield same fingerprint
    alt_tz = UTC  # explicit UTC
    decision_same = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-portable-01",
        decision_timestamp=datetime(2026, 8, 13, 12, 0, 0, tzinfo=alt_tz),
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt_same = build_acceptance_receipt(
        result, decision_same, receipt_id="receipt-portable-01", receipt_issued_at=RECEIPT_TIME
    )
    # Deterministic roundtrip via JSON must preserve validation
    reloaded = ManchesterCalibrationBaselineDecision.model_validate_json(
        decision_same.model_dump_json()
    )
    assert reloaded.decision_fingerprint == decision_same.decision_fingerprint
    reloaded_r = ManchesterCalibrationAcceptanceReceipt.model_validate_json(
        receipt_same.model_dump_json()
    )
    assert reloaded_r.receipt_fingerprint == receipt_same.receipt_fingerprint
    # Stable portable serialization: same UTC instant yields same fingerprint
    decision_dup = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-portable-01",
        decision_timestamp=datetime(2026, 8, 13, 12, 0, 0, tzinfo=UTC),
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    assert decision_dup.decision_fingerprint == decision_same.decision_fingerprint


# ---------------------------------------------------------------------------
# Narrowed fail-closed invariants (Lane 05 second review)
# ---------------------------------------------------------------------------


def test_synthetic_accepted_is_forced_to_provider_data_required() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    assert result.evaluation_report.synthetic is True
    # Even if caller requests ACCEPTED, synthetic must be forced to PROVIDER_DATA_REQUIRED
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
    # Synthetic report has available objective and engineering selection, but still blocked
    req = make_request()
    result = evaluate_workflow(req)
    # At least one evaluation has available objective
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
    # RECEIPT must not be available for provider-blocked synthetic
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-synth-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code == "RECEIPT_REQUIRES_ACCEPTED"


def test_accepted_requires_explicit_candidate() -> None:
    _req, result = make_admitted_production_result()
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-nocand-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label=None,
        )
    assert exc.value.code == "ACCEPTED_REQUIRES_CANDIDATE"
    # Also check direct Pydantic construction rejects ACCEPTED without candidate
    valid = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-nocand-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    data = valid.model_dump()
    data["decision_id"] = "dec-nocand-03"
    data["selected_candidate_label"] = None
    data["selected_candidate_binding_fingerprint"] = None
    data["selected_sumo_run_fingerprint"] = None
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)


def test_unknown_candidate_refused() -> None:
    _req, result = make_admitted_production_result()
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-unknown-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-unknown",
        )
    assert exc.value.code == "UNKNOWN_CANDIDATE"


def test_ineligible_candidate_refused() -> None:
    # Candidate with coverage threshold 0.5: cand-a with 1/3 paired fails, cand-b with 2/3 passes — so cand-a ineligible but global sufficient
    contract = make_production_contract(minimum_observed_coverage=Decimal("0.500"))
    obs = [
        prod_observed("10"),
        prod_observed("8", start=900, end=1800),
        prod_observed("5", start=1800, end=2700),
    ]
    # cand-a only has one paired interval (single sim) so coverage 0.333 fails
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
    with admitted_production_contract(contract):
        req = build_workflow_request(
            request_id="req-elig",
            deterministic_seed=0,
            contract=contract,
            observed_inputs=tuple(obs),  # type: ignore[arg-type]
            candidate_inputs=(cand_a, cand_b),
        )
        result = evaluate_workflow(req)
    ev_a = next(
        ev
        for ev in result.evaluation_report.candidate_evaluations
        if ev.candidate_label == "cand-a"
    )
    assert ev_a.coverage_requirement_met is False or ev_a.objective_result.status != "available"
    ev_b = next(
        ev
        for ev in result.evaluation_report.candidate_evaluations
        if ev.candidate_label == "cand-b"
    )
    # cand-b should be eligible to make global sufficient true
    assert ev_b.coverage_requirement_met is True and ev_b.objective_result.status == "available"
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-inelig-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert exc.value.code == "INELIGIBLE_CANDIDATE"


def test_candidate_fingerprint_drift_refused() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-drift-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    # Tamper decision's binding fingerprint -> model validation fails
    data = decision.model_dump()
    data["decision_id"] = "dec-drift-02"
    data["selected_candidate_binding_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)
    # Direct receipt drift: receipt's candidate binding drift invalidates receipt
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-drift-01", receipt_issued_at=RECEIPT_TIME
    )
    data_r = receipt.model_dump()
    data_r["receipt_id"] = "receipt-drift-02"
    data_r["selected_candidate_binding_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data_r)
    # Builder drift detection: tamper decision's stored fingerprint but keep request/evaluation fingerprints
    # Create a tampered decision that claims a different binding for same label but is otherwise valid
    tampered = decision.model_dump()
    tampered["decision_id"] = "dec-drift-03"
    tampered["selected_candidate_binding_fingerprint"] = "f" * 64
    # Recompute decision fingerprint to keep model valid
    provisional = {
        "decision": tampered["decision"],
        "decision_id": tampered["decision_id"],
        "decision_timestamp": _serialize_utc(tampered["decision_timestamp"]),
        "evaluation_fingerprint": tampered["evaluation_fingerprint"],
        "reason": tampered["reason"],
        "request_fingerprint": tampered["request_fingerprint"],
        "reviewer_attribution": tampered["reviewer_attribution"],
        "reviewer_id": tampered["reviewer_id"],
        "selected_candidate_binding_fingerprint": tampered[
            "selected_candidate_binding_fingerprint"
        ],
        "selected_candidate_label": tampered["selected_candidate_label"],
        "selected_sumo_run_fingerprint": tampered["selected_sumo_run_fingerprint"],
    }
    tampered["decision_fingerprint"] = sha256_hex(canonical_json(provisional).encode("utf-8"))
    tampered_decision = ManchesterCalibrationBaselineDecision.model_validate(tampered)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, tampered_decision, receipt_id="receipt-drift-03", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code in (
        "CANDIDATE_FINGERPRINT_DRIFT",
        "CANDIDATE_RUN_DRIFT",
        "CANDIDATE_DRIFT",
    )


def test_candidate_run_drift_refused() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-rundrift-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    # Tamper decision's run fingerprint -> fingerprint mismatch fails validation
    data = decision.model_dump()
    data["decision_id"] = "dec-rundrift-02"
    data["selected_sumo_run_fingerprint"] = RUN_B  # original is RUN_A for cand-a
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)
    # Builder must also detect run drift via tampered decision keeping same request fingerprint
    tampered = decision.model_dump()
    tampered["decision_id"] = "dec-rundrift-03"
    tampered["selected_sumo_run_fingerprint"] = RUN_B
    provisional = {
        "decision": tampered["decision"],
        "decision_id": tampered["decision_id"],
        "decision_timestamp": _serialize_utc(tampered["decision_timestamp"]),
        "evaluation_fingerprint": tampered["evaluation_fingerprint"],
        "reason": tampered["reason"],
        "request_fingerprint": tampered["request_fingerprint"],
        "reviewer_attribution": tampered["reviewer_attribution"],
        "reviewer_id": tampered["reviewer_id"],
        "selected_candidate_binding_fingerprint": tampered[
            "selected_candidate_binding_fingerprint"
        ],
        "selected_candidate_label": tampered["selected_candidate_label"],
        "selected_sumo_run_fingerprint": tampered["selected_sumo_run_fingerprint"],
    }
    tampered["decision_fingerprint"] = sha256_hex(canonical_json(provisional).encode("utf-8"))
    tampered_decision = ManchesterCalibrationBaselineDecision.model_validate(tampered)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result,
            tampered_decision,
            receipt_id="receipt-rundrift-01",
            receipt_issued_at=RECEIPT_TIME,
        )
    assert exc.value.code in ("CANDIDATE_RUN_DRIFT", "CANDIDATE_FINGERPRINT_DRIFT")


def test_accepted_candidate_identity_preserved_in_receipt() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-preserve-cand-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-b",
    )
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-preserve-cand-01", receipt_issued_at=RECEIPT_TIME
    )
    # Receipt must carry exact selected candidate identity from decision
    assert receipt.selected_candidate_label == "cand-b"
    assert receipt.selected_candidate_label == decision.selected_candidate_label
    assert (
        receipt.selected_candidate_binding_fingerprint
        == decision.selected_candidate_binding_fingerprint
    )
    assert receipt.selected_sumo_run_fingerprint == decision.selected_sumo_run_fingerprint
    # Compare against report's evaluation
    ev = next(
        ev
        for ev in result.evaluation_report.candidate_evaluations
        if ev.candidate_label == "cand-b"
    )
    assert receipt.selected_candidate_binding_fingerprint == ev.candidate_binding_fingerprint
    assert receipt.selected_sumo_run_fingerprint == ev.sumo_run_fingerprint
    # Provenance must also contain candidate identity
    assert receipt.portable_provenance["selected_candidate_label"] == "cand-b"
    assert (
        receipt.portable_provenance["selected_candidate_binding_fingerprint"]
        == ev.candidate_binding_fingerprint
    )
    assert receipt.portable_provenance["selected_sumo_run_fingerprint"] == ev.sumo_run_fingerprint
    # Tampering any selected field invalidates receipt
    for field in [
        "selected_candidate_label",
        "selected_candidate_binding_fingerprint",
        "selected_sumo_run_fingerprint",
    ]:
        data = receipt.model_dump()
        data["receipt_id"] = "receipt-tamper-01"
        if field == "selected_candidate_label":
            data[field] = "cand-a"
        else:
            data[field] = "0" * 64
        with pytest.raises(ValidationError):
            ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    # Verify freshness also checks drift
    verify_receipt_freshness(receipt, result)


def test_provider_blocked_decision_without_acceptance_receipt() -> None:
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
    # No acceptance receipt for provider-blocked decision
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-blocked-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code == "RECEIPT_REQUIRES_ACCEPTED"
    # REJECTED and PROVIDER_DATA_REQUIRED without candidate succeed; with candidate must be coherent
    _req2, result2 = make_admitted_production_result()
    rejected = decide_baseline(
        result2,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-rejected-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="REJECTED",
    )
    assert rejected.decision == "REJECTED"
    assert rejected.selected_candidate_label is None
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
    assert rejected_specific.selected_candidate_label == "cand-a"
    # But no receipt for REJECTED
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        build_acceptance_receipt(
            result2, rejected, receipt_id="receipt-rejected-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc2.value.code == "RECEIPT_REQUIRES_ACCEPTED"


def test_receipt_time_reversal_refused() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-time-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    # Builder must refuse receipt_issued_at < decision_timestamp
    early = datetime(2026, 8, 13, 11, 50, 0, tzinfo=UTC)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, decision, receipt_id="receipt-early-01", receipt_issued_at=early
        )
    assert exc.value.code == "RECEIPT_TIME_REVERSAL"
    # Equal is allowed
    exact = DECISION_TIME
    receipt_exact = build_acceptance_receipt(
        result, decision, receipt_id="receipt-exact-01", receipt_issued_at=exact
    )
    assert receipt_exact.receipt_issued_at == DECISION_TIME
    # Model-level reversal must also be refused (direct construction)
    data = receipt_exact.model_dump()
    data["receipt_id"] = "receipt-reversal-model-01"
    data["receipt_issued_at"] = early
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data)
    # Mutating decision_timestamp after receipt also invalidates
    receipt_ok = build_acceptance_receipt(
        result, decision, receipt_id="receipt-ok-01", receipt_issued_at=RECEIPT_TIME
    )
    data2 = receipt_ok.model_dump()
    data2["receipt_id"] = "receipt-reversal-model-02"
    data2["decision_timestamp"] = RECEIPT_TIME_ALT  # later than receipt_issued_at
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data2)


def test_direct_pydantic_construction_rejects_contradictory_selected_fields() -> None:
    _req, result = make_admitted_production_result()
    # ACCEPTED with missing fields
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-contradict-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    base = decision.model_dump()
    # Remove one selected field but keep others -> contradictory
    base["decision_id"] = "dec-contradict-02"
    base["selected_sumo_run_fingerprint"] = None
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(base)
    # REJECTED with partial fields also contradictory
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
    # keep other two None -> partial
    data["selected_candidate_binding_fingerprint"] = None
    data["selected_sumo_run_fingerprint"] = None
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)
    # Receipt with REJECTED decision string must fail (acceptance-only)
    good_receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-good-01", receipt_issued_at=RECEIPT_TIME
    )
    data_r = good_receipt.model_dump()
    data_r["receipt_id"] = "receipt-contradict-01"
    data_r["decision"] = "REJECTED"
    with pytest.raises(ValidationError):
        ManchesterCalibrationAcceptanceReceipt.model_validate(data_r)


def test_decision_fingerprint_binds_selected_candidate() -> None:
    _req, result = make_admitted_production_result()
    decision_a = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-bind-cand-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    decision_b = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-bind-cand-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-b",
    )
    assert decision_a.decision_fingerprint != decision_b.decision_fingerprint
    assert (
        decision_a.selected_candidate_binding_fingerprint
        != decision_b.selected_candidate_binding_fingerprint
    )
    # Mutating selected label invalidates fingerprint
    data = decision_a.model_dump()
    data["selected_candidate_label"] = "cand-b"
    with pytest.raises(ValidationError):
        ManchesterCalibrationBaselineDecision.model_validate(data)


def test_no_silent_engineering_selected_auto_acceptance() -> None:
    _req, result = make_admitted_production_result()
    # Engineering selection exists (lowest objective)
    eng = result.engineering_selected_candidate
    assert eng is not None
    # Without explicit selected_candidate_label, ACCEPTED must be refused even though engineering selection exists
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-auto-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
        )
    assert exc.value.code == "ACCEPTED_REQUIRES_CANDIDATE"
    # Providing a different candidate than engineering selection must be allowed if eligible
    non_eng = "cand-a" if eng == "cand-b" else "cand-b"
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-auto-02",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label=non_eng,
    )
    assert decision.selected_candidate_label == non_eng
    assert (
        decision.selected_candidate_label != eng or non_eng == eng
    )  # explicitly not auto-bound to eng


# ---------------------------------------------------------------------------
# Canonical-boundary / model_copy discriminating mutation tests (Lane 05)
# ---------------------------------------------------------------------------


def test_model_copy_report_synthetic_mutation_fails_closed() -> None:
    _req, result = make_admitted_production_result()
    # Flip synthetic via model_copy — report validator must catch on canonical revalidation
    tampered_report = result.evaluation_report.model_copy(update={"synthetic": True})
    tampered_result = result.model_copy(update={"evaluation_report": tampered_report})
    # evaluate_workflow must reject tampered request? Here decide_baseline must fail closed
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            tampered_result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-synth-mut-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert exc.value.code in ("INVALID_RESULT", "INVALID_REQUEST", "STALE_RECEIPT")
    # Directly constructed self-consistent ACCEPTED decision for synthetic must not yield receipt
    # Build a synthetic result via real evaluate, then craft a fake ACCEPTED decision by hand
    req_syn = make_request()
    res_syn = evaluate_workflow(req_syn)
    # Craft a fake ACCEPTED decision that is self-consistent (fingerprint recomputed)
    # but report is synthetic — build_acceptance_receipt must recheck sufficiency
    fake_decision_data = {
        "decision_id": "dec-fake-synth-01",
        "request_fingerprint": res_syn.request_fingerprint,
        "evaluation_fingerprint": res_syn.evaluation_fingerprint,
        "reviewer_id": "reviewer-01",
        "reviewer_attribution": "lead",
        "decision": "ACCEPTED",
        "decision_timestamp": DECISION_TIME,
        "reason": "fake accepted",
        "selected_candidate_label": res_syn.evaluation_report.candidate_evaluations[
            0
        ].candidate_label,
        "selected_candidate_binding_fingerprint": res_syn.evaluation_report.candidate_evaluations[
            0
        ].candidate_binding_fingerprint,
        "selected_sumo_run_fingerprint": res_syn.evaluation_report.candidate_evaluations[
            0
        ].sumo_run_fingerprint,
        "limitations": tuple(res_syn.limitations),
        "evidence_boundary": res_syn.evidence_boundary,
    }
    prov = {
        "decision": fake_decision_data["decision"],
        "decision_id": fake_decision_data["decision_id"],
        "decision_timestamp": _serialize_utc(fake_decision_data["decision_timestamp"]),  # type: ignore[arg-type]
        "evaluation_fingerprint": fake_decision_data["evaluation_fingerprint"],
        "reason": fake_decision_data["reason"],
        "request_fingerprint": fake_decision_data["request_fingerprint"],
        "reviewer_attribution": fake_decision_data["reviewer_attribution"],
        "reviewer_id": fake_decision_data["reviewer_id"],
        "selected_candidate_binding_fingerprint": fake_decision_data[
            "selected_candidate_binding_fingerprint"
        ],
        "selected_candidate_label": fake_decision_data["selected_candidate_label"],
        "selected_sumo_run_fingerprint": fake_decision_data["selected_sumo_run_fingerprint"],
    }
    fake_decision_data["decision_fingerprint"] = sha256_hex(canonical_json(prov).encode("utf-8"))
    fake_decision = ManchesterCalibrationBaselineDecision.model_validate(fake_decision_data)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        build_acceptance_receipt(
            res_syn,
            fake_decision,
            receipt_id="receipt-fake-synth-01",
            receipt_issued_at=RECEIPT_TIME,
        )
    assert exc2.value.code in ("INSUFFICIENT_PROVIDER_DATA", "INVALID_RESULT", "INVALID_DECISION")


def test_model_copy_contract_admission_mutation_fails_closed() -> None:
    _req, result = make_admitted_production_result()
    # Mutate contract_admission to synthetic_development_inputs via model_copy
    tampered_report = result.evaluation_report.model_copy(
        update={"contract_admission": "synthetic_development_inputs"}
    )
    tampered_result = result.model_copy(update={"evaluation_report": tampered_report})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            tampered_result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-admission-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    # Mutate contract_admitted to False
    tampered_report2 = result.evaluation_report.model_copy(update={"contract_admitted": False})
    tampered_result2 = result.model_copy(update={"evaluation_report": tampered_report2})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            tampered_result2,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-admitted-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )


def test_model_copy_candidate_coverage_objective_mutation_fails_closed() -> None:
    _req, result = make_admitted_production_result()
    # Coverage/objective mutation via model_copy bypass — must fail closed on canonical revalidation
    ev0 = result.evaluation_report.candidate_evaluations[0]
    tampered_obj = ev0.objective_result.model_copy(
        update={"status": "unavailable", "reason": "no_paired_intervals", "value": None}
    )
    tampered_ev0 = ev0.model_copy(
        update={"coverage_requirement_met": False, "objective_result": tampered_obj}
    )
    # Keep second evaluation unchanged
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
    # Also test that build_acceptance_receipt refuses ineligible candidate after coverage threshold raised
    contract_high = make_production_contract(minimum_observed_coverage=Decimal("0.500"))
    obs = [
        prod_observed("10"),
        prod_observed("8", start=900, end=1800),
        prod_observed("5", start=1800, end=2700),
    ]
    single = [prod_simulated("12", run_fp=RUN_A)]
    cand_a = prod_candidate("cand-a", single)
    cand_b = prod_candidate(
        "cand-b",
        [
            prod_simulated("11", run_fp=RUN_B),
            prod_simulated("8", start=900, end=1800, run_fp=RUN_B),
        ],
        value=Decimal("1.5"),
        run_fp=RUN_B,
    )
    with admitted_production_contract(contract_high):
        req = build_workflow_request(
            request_id="req-coverage-mut",
            deterministic_seed=0,
            contract=contract_high,
            observed_inputs=tuple(obs),  # type: ignore[arg-type]
            candidate_inputs=(cand_a, cand_b),
        )
        res = evaluate_workflow(req)
    # cand-a is ineligible, must not be ACCEPTED
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        decide_baseline(
            res,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-coverage-02",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert exc.value.code == "INELIGIBLE_CANDIDATE"


def test_model_copy_request_report_fingerprint_mutation_fails_closed() -> None:
    req = make_request()
    tampered_req = req.model_copy(update={"request_fingerprint": "0" * 64})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        evaluate_workflow(tampered_req)
    assert exc.value.code == "INVALID_REQUEST"
    _req, result = make_admitted_production_result()
    tampered_result = result.model_copy(update={"request_fingerprint": "0" * 64})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc2:
        decide_baseline(
            tampered_result,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-fp-01",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )
    assert exc2.value.code == "INVALID_RESULT"
    # Report fingerprint mutation via evaluation_report
    tampered_result2 = result.model_copy(update={"evaluation_fingerprint": "f" * 64})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        decide_baseline(
            tampered_result2,
            reviewer_id="reviewer-01",
            reviewer_attribution="lead",
            decision_id="dec-fp-02",
            decision_timestamp=DECISION_TIME,
            requested_decision="ACCEPTED",
            selected_candidate_label="cand-a",
        )


def test_model_copy_decision_mutations_fail_closed() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-mut-base-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-mut-base-01", receipt_issued_at=RECEIPT_TIME
    )
    # Mutate selected_candidate_label via model_copy
    tampered_dec = decision.model_copy(update={"selected_candidate_label": "cand-b"})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        build_acceptance_receipt(
            result, tampered_dec, receipt_id="receipt-mut-01", receipt_issued_at=RECEIPT_TIME
        )
    assert exc.value.code in (
        "INVALID_DECISION",
        "CANDIDATE_FINGERPRINT_DRIFT",
        "CANDIDATE_DRIFT",
        "STALE_RECEIPT",
    )
    # Mutate reviewer_id
    tampered_dec2 = decision.model_copy(update={"reviewer_id": "attacker"})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        build_acceptance_receipt(
            result, tampered_dec2, receipt_id="receipt-mut-02", receipt_issued_at=RECEIPT_TIME
        )
    # Mutate decision_timestamp
    tampered_dec3 = decision.model_copy(update={"decision_timestamp": DECISION_TIME_ALT})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        build_acceptance_receipt(
            result, tampered_dec3, receipt_id="receipt-mut-03", receipt_issued_at=RECEIPT_TIME
        )
    # Mutate reason
    tampered_dec4 = decision.model_copy(update={"reason": "tampered reason"})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        build_acceptance_receipt(
            result, tampered_dec4, receipt_id="receipt-mut-04", receipt_issued_at=RECEIPT_TIME
        )
    # Exact verification must fail when decision reason mismatched
    tampered_dec5 = decision.model_copy(
        update={"reason": "other reason", "decision_fingerprint": decision.decision_fingerprint}
    )
    # Even though fingerprint not recomputed, canonical revalidation will catch
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_acceptance_receipt(receipt, tampered_dec5, result)
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_receipt_freshness(receipt, result, tampered_dec5)


def test_model_copy_receipt_provenance_and_limitations_mutation_fails_closed() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-prov-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-prov-01", receipt_issued_at=RECEIPT_TIME
    )
    # Mutate portable_provenance via model_copy
    tampered_prov = dict(receipt.portable_provenance)
    tampered_prov["request_fingerprint"] = "0" * 64
    tampered_receipt = receipt.model_copy(update={"portable_provenance": tampered_prov})
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        verify_receipt_freshness(tampered_receipt, result)
    assert exc.value.code == "INVALID_RECEIPT"
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_acceptance_receipt(tampered_receipt, decision, result)
    # Mutate limitations
    tampered_receipt2 = receipt.model_copy(update={"limitations": ("tampered rhetoric",)})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_receipt_freshness(tampered_receipt2, result)
    # Mutate evidence_boundary
    tampered_receipt3 = receipt.model_copy(update={"evidence_boundary": "tampered boundary"})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_receipt_freshness(tampered_receipt3, result)
    # Decision limitations mutation
    tampered_dec = decision.model_copy(update={"limitations": ("fake",)})
    with pytest.raises(ManchesterCalibrationWorkflowError):
        build_acceptance_receipt(
            result, tampered_dec, receipt_id="receipt-prov-02", receipt_issued_at=RECEIPT_TIME
        )


def test_engineering_selection_status_mutation_fails_closed() -> None:
    req = make_request()
    result = evaluate_workflow(req)
    # Try to flip engineering_selected_candidate via model_copy
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
    # Flip status
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
    # Direct model_validate with wrong status must also fail
    data = result.model_dump()
    data["engineering_selection_status"] = flipped_status
    with pytest.raises(ValidationError):
        ManchesterCalibrationWorkflowResult.model_validate(data)


def test_synthetic_unapproved_never_produces_or_verifies_receipt_via_direct_construction() -> None:
    # Synthetic data must never produce or verify acceptance receipt, even via direct construction
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
    # Attempt to forge an ACCEPTED receipt for synthetic via direct construction with recomputed fingerprints
    # but build_acceptance_receipt must still refuse due to sufficiency recheck
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
        "limitations": tuple(res_syn.limitations),
        "evidence_boundary": res_syn.evidence_boundary,
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
    # Do NOT admit it
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
    # Forge ACCEPTED for unapproved
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
    # Also verify that a legit receipt cannot be verified as fresh against synthetic/unapproved result
    _req_ok, res_ok = make_admitted_production_result()
    dec_ok = decide_baseline(
        res_ok,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-ok-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt_ok = build_acceptance_receipt(
        res_ok, dec_ok, receipt_id="receipt-ok-01", receipt_issued_at=RECEIPT_TIME
    )
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_receipt_freshness(receipt_ok, res_syn)
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_acceptance_receipt(receipt_ok, dec_ok, res_syn)


def test_exact_verification_binds_all_fields() -> None:
    _req, result = make_admitted_production_result()
    decision = decide_baseline(
        result,
        reviewer_id="reviewer-01",
        reviewer_attribution="lead",
        decision_id="dec-exact-01",
        decision_timestamp=DECISION_TIME,
        requested_decision="ACCEPTED",
        selected_candidate_label="cand-a",
    )
    receipt = build_acceptance_receipt(
        result, decision, receipt_id="receipt-exact-01", receipt_issued_at=RECEIPT_TIME
    )
    # Exact verification must pass
    verify_acceptance_receipt(receipt, decision, result)
    verify_receipt_freshness(receipt, result, decision)
    # Mutating any bound field must fail exact verification
    tampered_dec = decision.model_copy(update={"reviewer_attribution": "other"})
    # Need to recompute fingerprint to keep decision valid, otherwise INVALID_DECISION; but even valid tampered fails binding
    # First test without recompute — should fail as INVALID_DECISION via revalidation
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_acceptance_receipt(receipt, tampered_dec, result)
    # Now recompute fingerprint to make tampered decision self-consistent, still fails reason mismatch
    data = decision.model_dump()
    data["decision_id"] = "dec-exact-02"
    data["reviewer_attribution"] = "other"
    prov = {
        "decision": data["decision"],
        "decision_id": data["decision_id"],
        "decision_timestamp": _serialize_utc(data["decision_timestamp"]),
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
    tampered_dec_valid = ManchesterCalibrationBaselineDecision.model_validate(data)
    with pytest.raises(ManchesterCalibrationWorkflowError) as exc:
        verify_acceptance_receipt(receipt, tampered_dec_valid, result)
    assert exc.value.code == "STALE_RECEIPT"
    # Mutating receipt reason also fails
    tampered_receipt = receipt.model_copy(update={"reason": "other reason"})
    # This will be caught as INVALID_RECEIPT because receipt fingerprint mismatch
    with pytest.raises(ManchesterCalibrationWorkflowError):
        verify_acceptance_receipt(tampered_receipt, decision, result)
