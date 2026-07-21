from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import fixed_study_clock, study_collection

from traffictwin.experiments.regression_gate import (
    GoldenApprovalStatus,
    RegressionToleranceSpec,
    build_regression_golden_contract,
    evaluate_regression_gate,
)


def test_regression_failure_matches_golden_projection() -> None:
    golden_subject = study_collection("baseline", 1, 0.8)
    contract = build_regression_golden_contract(
        golden_subject,
        contract_id="golden-completion-regression",
        contract_version="1.0.0",
        description="Approved synthetic golden regression test boundary",
        tolerances=[
            RegressionToleranceSpec(
                selector="task.completion.rate",
                absolute_tolerance=0.01,
                relative_tolerance=0.0,
            )
        ],
        approval_status=GoldenApprovalStatus.APPROVED,
        approved_by="golden-test-owner",
        approval_note="Approved only for deterministic golden test verification",
    )
    report = evaluate_regression_gate(
        study_collection("baseline", 1, 0.82),
        contract,
        clock=fixed_study_clock,
    )
    projection = {
        "gate_id": report.gate_id,
        "status": report.status.value,
        "contract_fingerprint": report.contract_fingerprint,
        "subject_fingerprint": report.subject_fingerprint,
        "source_identity_fingerprint": report.source_identity_fingerprint,
        "counts": {
            "checks": report.check_count,
            "passed": report.passed_count,
            "failed": report.failed_count,
            "unavailable": report.unavailable_count,
            "ignored": report.ignored_subject_field_count,
        },
        "blocking_findings": [
            finding.model_dump(mode="json") for finding in report.blocking_findings
        ],
        "checks": [check.model_dump(mode="json") for check in report.checks],
        "warnings": report.warnings,
        "limitations": report.limitations,
    }
    expected = json.loads(
        (Path(__file__).parent / "expected" / "regression_gate_known_failure.json").read_text(
            encoding="utf-8"
        )
    )

    assert projection == expected
