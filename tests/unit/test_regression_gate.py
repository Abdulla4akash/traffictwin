from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest
from pydantic import ValidationError

from tests.statistical_helpers import (
    FIXED_STUDY_TIME,
    fixed_study_clock,
    paired_study_config,
    study_collection,
    study_collections,
)
from traffictwin.experiments.regression_gate import (
    GoldenApprovalStatus,
    RegressionAssertion,
    RegressionCheckStatus,
    RegressionGateStatus,
    RegressionGoldenContract,
    RegressionReasonCode,
    RegressionToleranceSpec,
    SourceIdentityPolicy,
    StudyRegressionField,
    build_regression_golden_contract,
    evaluate_regression_gate,
    parse_regression_golden_contract_json,
    regression_gate_method_contract,
    regression_gate_to_csv,
    regression_gate_to_markdown,
)
from traffictwin.experiments.statistical_study import evaluate_paired_statistical_study
from traffictwin.metrics.results import MetricCollection, MetricStatus


def _spec(
    selector: str = "task.completion.rate",
    absolute: float = 0.01,
    relative: float = 0.0,
) -> RegressionToleranceSpec:
    return RegressionToleranceSpec(
        selector=selector,
        absolute_tolerance=absolute,
        relative_tolerance=relative,
    )


def _approved_contract(
    subject: MetricCollection,
    *,
    tolerances: list[RegressionToleranceSpec] | None = None,
    source_policy: SourceIdentityPolicy = SourceIdentityPolicy.EXACT,
) -> RegressionGoldenContract:
    return build_regression_golden_contract(
        subject,
        contract_id="completion-regression",
        contract_version="1.0.0",
        description="Approved synthetic completion regression boundary",
        tolerances=tolerances or [_spec()],
        source_identity_policy=source_policy,
        approval_status=GoldenApprovalStatus.APPROVED,
        approved_by="test-owner",
        approval_note="Approved only for deterministic software verification",
    )


def _value_subject(
    value: object,
    *,
    metric_status: MetricStatus = MetricStatus.AVAILABLE,
    unit: str = "fraction",
    implementation_version: str = "1.0",
    algorithm: str = "policy-a",
    input_fingerprint: str | None = None,
) -> MetricCollection:
    return study_collection(
        "baseline",
        1,
        value,
        metric_status=metric_status,
        unit=unit,
        implementation_version=implementation_version,
        algorithm=algorithm,
        input_fingerprint=input_fingerprint,
    )


def test_method_contract_pins_subjects_formula_and_exit_codes() -> None:
    contract = regression_gate_method_contract()

    assert contract.tolerance_method == "max_absolute_or_relative_v1"
    assert "max(absolute_tolerance" in contract.tolerance_formula
    assert contract.ci_exit_codes == {"passed": 0, "failed": 1, "unavailable": 2}
    assert StudyRegressionField.MEAN_PAIRED_DIFFERENCE in contract.study_fields
    assert len(contract.fingerprint()) == 64


def test_metric_gate_passes_exact_and_inclusive_absolute_boundary() -> None:
    golden_subject = _value_subject(0.80)
    contract = _approved_contract(golden_subject, tolerances=[_spec(absolute=0.02)])
    exact = evaluate_regression_gate(golden_subject, contract, clock=fixed_study_clock)
    boundary = evaluate_regression_gate(
        _value_subject(0.82),
        contract,
        clock=fixed_study_clock,
    )

    assert exact.status is RegressionGateStatus.PASSED
    assert exact.checks[0].absolute_error == 0.0
    assert boundary.status is RegressionGateStatus.PASSED
    assert boundary.checks[0].absolute_error == pytest.approx(0.02)
    assert boundary.checks[0].allowed_error == 0.02
    assert boundary.passed_count == 1


def test_metric_gate_uses_larger_relative_boundary_and_fails_outside_it() -> None:
    golden_subject = _value_subject(100.0)
    contract = _approved_contract(
        golden_subject,
        tolerances=[_spec(absolute=1.0, relative=0.05)],
    )
    relative_boundary = evaluate_regression_gate(
        _value_subject(105.0),
        contract,
        clock=fixed_study_clock,
    )
    failed = evaluate_regression_gate(
        _value_subject(105.01),
        contract,
        clock=fixed_study_clock,
    )

    assert relative_boundary.status is RegressionGateStatus.PASSED
    assert relative_boundary.checks[0].allowed_error == 5.0
    assert failed.status is RegressionGateStatus.FAILED
    assert failed.failed_count == 1
    assert failed.checks[0].reason_code is RegressionReasonCode.TOLERANCE_EXCEEDED


def test_zero_expected_value_requires_absolute_tolerance() -> None:
    golden_subject = _value_subject(0.0)
    exact_contract = _approved_contract(
        golden_subject,
        tolerances=[_spec(absolute=0.0, relative=1.0)],
    )
    absolute_contract = _approved_contract(
        golden_subject,
        tolerances=[_spec(absolute=0.1, relative=1.0)],
    )

    failed = evaluate_regression_gate(_value_subject(0.01), exact_contract)
    passed = evaluate_regression_gate(_value_subject(0.1), absolute_contract)

    assert failed.status is RegressionGateStatus.FAILED
    assert failed.checks[0].relative_error is None
    assert failed.checks[0].allowed_error == 0.0
    assert passed.status is RegressionGateStatus.PASSED


@pytest.mark.parametrize(
    ("subject", "reason"),
    [
        (
            _value_subject(None, metric_status=MetricStatus.UNAVAILABLE),
            RegressionReasonCode.ASSERTION_VALUE_UNAVAILABLE,
        ),
        (
            _value_subject({"group": 0.8}),
            RegressionReasonCode.ASSERTION_VALUE_NOT_FINITE_SCALAR,
        ),
        (
            _value_subject(float("nan")),
            RegressionReasonCode.ASSERTION_VALUE_NOT_FINITE_SCALAR,
        ),
        (
            _value_subject(0.8, unit="percent"),
            RegressionReasonCode.ASSERTION_UNIT_MISMATCH,
        ),
        (
            _value_subject(0.8, implementation_version="2.0"),
            RegressionReasonCode.ASSERTION_IMPLEMENTATION_VERSION_MISMATCH,
        ),
    ],
)
def test_missing_or_incompatible_metric_evidence_is_unavailable(
    subject: MetricCollection,
    reason: RegressionReasonCode,
) -> None:
    contract = _approved_contract(_value_subject(0.8))
    report = evaluate_regression_gate(subject, contract, clock=fixed_study_clock)

    assert report.status is RegressionGateStatus.UNAVAILABLE
    assert report.checks[0].status is RegressionCheckStatus.UNAVAILABLE
    assert report.checks[0].reason_code is reason


def test_context_and_exact_source_mismatch_are_blocking_not_numerical_failures() -> None:
    golden = _value_subject(0.8)
    contract = _approved_contract(golden)
    changed_context = _value_subject(0.8, algorithm="policy-b")
    changed_source = _value_subject(
        0.8,
        input_fingerprint="different-source-fingerprint",
    )

    context_report = evaluate_regression_gate(changed_context, contract)
    source_report = evaluate_regression_gate(changed_source, contract)

    assert context_report.status is RegressionGateStatus.UNAVAILABLE
    assert context_report.blocking_findings[0].code is RegressionReasonCode.SUBJECT_CONTEXT_MISMATCH
    assert source_report.status is RegressionGateStatus.UNAVAILABLE
    assert source_report.blocking_findings[0].code is RegressionReasonCode.SOURCE_IDENTITY_MISMATCH


def test_compatible_context_policy_allows_new_source_identity() -> None:
    golden = _value_subject(0.8)
    contract = _approved_contract(
        golden,
        source_policy=SourceIdentityPolicy.COMPATIBLE_CONTEXT,
    )
    actual = _value_subject(0.805, input_fingerprint="new-compatible-source")

    report = evaluate_regression_gate(actual, contract, clock=fixed_study_clock)

    assert report.status is RegressionGateStatus.PASSED
    assert any("source identities to differ" in warning for warning in report.warnings)


def test_candidate_contract_is_unavailable_and_cannot_self_approve() -> None:
    subject = _value_subject(0.8)
    candidate = build_regression_golden_contract(
        subject,
        contract_id="candidate-completion",
        contract_version="1.0.0",
        description="Candidate completion regression boundary",
        tolerances=[_spec()],
    )

    report = evaluate_regression_gate(subject, candidate)

    assert report.status is RegressionGateStatus.UNAVAILABLE
    assert report.blocking_findings[0].code is RegressionReasonCode.GOLDEN_CONTRACT_NOT_APPROVED
    with pytest.raises(ValidationError, match="approved_by"):
        RegressionGoldenContract.model_validate(
            {
                **candidate.model_dump(mode="json"),
                "approval_status": "approved",
            }
        )


def test_paired_study_fields_pass_and_component_unavailability_is_retained() -> None:
    golden_study = evaluate_paired_statistical_study(
        study_collections([-0.1, 0.0, 0.2]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    contract = build_regression_golden_contract(
        golden_study,
        contract_id="paired-study-regression",
        contract_version="1.0.0",
        description="Approved synthetic paired-study regression boundary",
        tolerances=[
            _spec(StudyRegressionField.ELIGIBLE_PAIR_COUNT.value, 0.0, 0.0),
            _spec(StudyRegressionField.MEAN_PAIRED_DIFFERENCE.value, 0.05, 0.0),
            _spec(StudyRegressionField.COHEN_DZ.value, 0.5, 0.0),
        ],
        source_identity_policy=SourceIdentityPolicy.COMPATIBLE_CONTEXT,
        approval_status=GoldenApprovalStatus.APPROVED,
        approved_by="test-owner",
        approval_note="Approved only for deterministic software verification",
    )
    passing = evaluate_regression_gate(golden_study, contract, clock=fixed_study_clock)
    zero_variance_study = evaluate_paired_statistical_study(
        study_collections([0.1, 0.1, 0.1]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    unavailable = evaluate_regression_gate(zero_variance_study, contract)

    assert passing.status is RegressionGateStatus.PASSED
    assert passing.passed_count == 3
    assert unavailable.status is RegressionGateStatus.UNAVAILABLE
    cohen = next(
        check for check in unavailable.checks if check.selector == StudyRegressionField.COHEN_DZ
    )
    assert cohen.reason_code is RegressionReasonCode.ASSERTION_VALUE_UNAVAILABLE


def test_input_immutability_timestamp_stability_and_exports() -> None:
    subject = _value_subject(0.8)
    contract = _approved_contract(subject)
    subject_snapshot = deepcopy(subject)
    contract_snapshot = deepcopy(contract)
    shifted = subject.model_copy(
        update={
            "generated_at": FIXED_STUDY_TIME + timedelta(hours=1),
            "results": [
                subject.results[0].model_copy(
                    update={"computed_at": FIXED_STUDY_TIME + timedelta(hours=1)}
                )
            ],
        }
    )
    first = evaluate_regression_gate(subject, contract, clock=fixed_study_clock)
    second = evaluate_regression_gate(
        shifted,
        contract,
        clock=lambda: FIXED_STUDY_TIME + timedelta(hours=2),
    )

    assert subject == subject_snapshot
    assert contract == contract_snapshot
    assert first.fingerprint() == second.fingerprint()
    assert parse_regression_golden_contract_json(contract.to_json()) == contract
    assert "# TrafficTwin Regression Gate" in regression_gate_to_markdown(first)
    assert "ASSERTION_PASSED" in regression_gate_to_csv(first)


@pytest.mark.parametrize(
    "update",
    [
        {"contract_id": "bad id"},
        {"contract_version": "latest"},
        {"description": "too short"},
        {"assertions": []},
        {
            "assertions": [
                RegressionAssertion(
                    selector="task.completion.rate",
                    expected_value=0.8,
                    unit="fraction",
                    implementation_version="1.0",
                    absolute_tolerance=0.01,
                    relative_tolerance=0.0,
                )
            ]
            * 2
        },
    ],
)
def test_golden_contract_rejects_unversioned_or_ambiguous_content(
    update: dict[str, object],
) -> None:
    contract = _approved_contract(_value_subject(0.8))

    with pytest.raises(ValidationError):
        RegressionGoldenContract.model_validate({**contract.model_dump(mode="json"), **update})


def test_bounded_json_parser_rejects_oversized_contract() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        parse_regression_golden_contract_json(b"{}", maximum_bytes=1)
