from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from traffictwin.integration.vec_reproduction import (
    LATENCY_STREAM_TOLERANCE,
    PINNED_CASE_ID,
    PINNED_EXPECTED_FILES,
    PINNED_TOS_DATA_COMMIT,
    SCALAR_TOLERANCE,
    VecComparisonStatus,
    VecRepeatRunEvidence,
    VecReproductionGrade,
    VecReproductionReport,
    VecReproductionRequest,
    VecReproductionSummary,
    service,
    vec_reproduction_contract,
)


def _request() -> VecReproductionRequest:
    return VecReproductionRequest(observed_receipt_sha256="1" * 64)


def test_contract_pins_case_sources_tolerances_and_limits() -> None:
    contract = vec_reproduction_contract()

    assert contract.case_id == PINNED_CASE_ID
    assert contract.expected_commit == PINNED_TOS_DATA_COMMIT
    assert contract.expected_files == PINNED_EXPECTED_FILES
    assert contract.numeric_tolerances == {
        "run.avg_energy_j_per_task": SCALAR_TOLERANCE,
        "per-step.lat_sum": LATENCY_STREAM_TOLERANCE,
    }
    assert contract.excluded_fields == {
        "run.wall_s": "machine-dependent performance metadata, never a scientific endpoint",
        "run.actor basename": (
            "the isolated runner stages the exact actor blob as actor.npz; semantic identity "
            "is verified from the receipt and hash"
        ),
    }
    assert contract.fingerprint() == contract.fingerprint()


def test_reproduction_request_is_strict_and_fingerprinted() -> None:
    request = _request()

    assert request.fingerprint() == request.fingerprint()
    with pytest.raises(ValidationError):
        VecReproductionRequest.model_validate(
            {**request.model_dump(mode="json"), "case_id": "caller-selected"}
        )
    with pytest.raises(ValidationError):
        VecReproductionRequest.model_validate(
            {**request.model_dump(mode="json"), "absolute_tolerance": 100.0}
        )


def test_scalar_tolerance_is_inclusive_and_refuses_broad_drift() -> None:
    exact = service._numeric_scalar_check("run.json", "energy", 0.5, 0.5, SCALAR_TOLERANCE)
    calibrated = service._numeric_scalar_check(
        "run.json", "energy", 0.48600795589620094, 0.48600801619737877, SCALAR_TOLERANCE
    )
    divergent = service._numeric_scalar_check(
        "run.json", "energy", 0.48600795589620094, 0.4861, SCALAR_TOLERANCE
    )

    assert exact.status is VecComparisonStatus.EXACT
    assert calibrated.status is VecComparisonStatus.WITHIN_TOLERANCE
    assert calibrated.max_absolute_error == pytest.approx(6.030117782884759e-8)
    assert divergent.status is VecComparisonStatus.MISMATCH


def test_latency_tolerance_enforces_both_numeric_and_ulp_bounds() -> None:
    expected = np.array([10_000.0], dtype=np.float32)
    three_ulp = expected.copy()
    four_ulp = expected.copy()
    for _ in range(3):
        three_ulp = np.nextafter(three_ulp, np.float32(np.inf))
    for _ in range(4):
        four_ulp = np.nextafter(four_ulp, np.float32(np.inf))

    admitted = service._numeric_array_check(
        "per-step.npz", "lat_sum", expected, three_ulp, LATENCY_STREAM_TOLERANCE
    )
    refused = service._numeric_array_check(
        "per-step.npz", "lat_sum", expected, four_ulp, LATENCY_STREAM_TOLERANCE
    )

    assert admitted.status is VecComparisonStatus.WITHIN_TOLERANCE
    assert admitted.max_ulp_error == 3
    assert refused.status is VecComparisonStatus.MISMATCH
    assert refused.max_ulp_error == 4


def test_report_grade_and_summary_cannot_overstate_evidence() -> None:
    check = service._numeric_scalar_check("run.json", "energy", 1.0, 1.0000001, SCALAR_TOLERANCE)
    payload = {
        "grade": VecReproductionGrade.NUMERICALLY_EQUIVALENT,
        "request": _request(),
        "request_fingerprint": _request().fingerprint(),
        "expected_sources": [],
        "observed_sources": [],
        "runner_receipt_fingerprint": "2" * 64,
        "runtime": {},
        "tolerance_calibration": "calibrated before acceptance",
        "repeat_run": VecRepeatRunEvidence(
            calibration_receipt_sha256="3" * 64,
            acceptance_receipt_sha256="4" * 64,
            same_execution_controls=True,
            scientific_json_exact=True,
            perstep_arrays_exact=True,
            pertask_arrays_exact=True,
        ),
        "checks": [check],
        "summary": VecReproductionSummary(
            exact=0,
            within_tolerance=1,
            mismatch=0,
            excluded=0,
            unavailable=0,
        ),
        "interpretation_limits": ["bounded test"],
    }
    report = VecReproductionReport.model_validate(payload)
    assert report.direct_launch_supported is False

    with pytest.raises(ValidationError):
        VecReproductionReport.model_validate(
            {
                **payload,
                "grade": VecReproductionGrade.EXACT,
            }
        )
    with pytest.raises(ValidationError):
        VecReproductionReport.model_validate(
            {
                **payload,
                "summary": {
                    "exact": 1,
                    "within_tolerance": 0,
                    "mismatch": 0,
                    "excluded": 0,
                    "unavailable": 0,
                },
            }
        )
