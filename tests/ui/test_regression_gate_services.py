from __future__ import annotations

from pathlib import Path

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collection,
    study_collections,
)

from traffictwin.experiments.regression_gate import (
    GoldenApprovalStatus,
    RegressionGateReport,
    RegressionGateStatus,
    RegressionGoldenContract,
    RegressionToleranceSpec,
    build_regression_golden_contract,
)
from traffictwin.experiments.statistical_study import evaluate_paired_statistical_study
from traffictwin.storage.registry import Registry
from traffictwin.ui.services import (
    ServiceError,
    evaluate_metric_regression_gate_for_ui,
    evaluate_statistical_regression_gate_for_ui,
    parse_regression_golden_for_ui,
    regression_metric_runs_for_ui,
)


def _approved_metric_contract() -> RegressionGoldenContract:
    subject = study_collection("baseline", 1, 0.8)
    return build_regression_golden_contract(
        subject,
        contract_id="ui-service-regression",
        contract_version="1.0.0",
        description="Approved synthetic UI service regression boundary",
        tolerances=[
            RegressionToleranceSpec(
                selector="task.completion.rate",
                absolute_tolerance=0.01,
                relative_tolerance=0.0,
            )
        ],
        approval_status=GoldenApprovalStatus.APPROVED,
        approved_by="ui-test-owner",
        approval_note="Approved only for deterministic UI service verification",
    )


def test_metric_regression_ui_service_loads_and_evaluates_registered_subject(
    tmp_path: Path,
) -> None:
    path = tmp_path / "registry.sqlite"
    collection = study_collection("baseline", 1, 0.8)
    Registry(path).store_metric_collection(
        run_id=collection.run_id,
        metric_version=collection.metric_version,
        source_fingerprint=collection.input_fingerprint,
        payload_json=collection.model_dump_json(),
    )
    contract = _approved_metric_contract()
    runs = regression_metric_runs_for_ui(path)
    parsed = parse_regression_golden_for_ui(contract.to_json().encode("utf-8"))
    assert not isinstance(parsed, ServiceError)
    result = evaluate_metric_regression_gate_for_ui(path, collection.run_id, parsed)

    assert runs == [collection.run_id]
    assert isinstance(result, RegressionGateReport)
    assert result.status is RegressionGateStatus.PASSED


def test_regression_ui_services_reject_invalid_json_and_wrong_subject_kind(
    tmp_path: Path,
) -> None:
    invalid = parse_regression_golden_for_ui(b"not-json")
    study = evaluate_paired_statistical_study(
        study_collections([-0.1, 0.0, 0.2]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    wrong_kind = evaluate_statistical_regression_gate_for_ui(
        study,
        _approved_metric_contract(),
    )

    assert isinstance(invalid, ServiceError)
    assert isinstance(wrong_kind, ServiceError)
    assert "does not target" in wrong_kind.message
