from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.ingestion.bundle import BundleValidationResult, validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricCollection
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.evaluation import (
    SyntheticDiagnosticCase,
    SyntheticFixtureSet,
    evidence_pack_from_case,
    load_fixture_set,
)

FIXED_TIME = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
FIXTURES = Path("tests/fixtures/bundles")
DIAGNOSTIC_FIXTURES = Path("tests/fixtures/diagnostics")


def fixed_clock() -> datetime:
    return FIXED_TIME


def bundle_result(name: str) -> BundleValidationResult:
    return validate_bundle(FIXTURES / name)


def metric_collection(name: str) -> MetricCollection:
    return compute_metrics_for_bundle(bundle_result(name), clock=fixed_clock)


def metric_projection(collection: MetricCollection, keys: list[str]) -> dict[str, object]:
    by_key = collection.by_key()
    return {
        "run_id": collection.run_id,
        "metric_version": collection.metric_version,
        "metrics": {
            key: {
                "status": by_key[key].status.value,
                "value": by_key[key].value,
                "unit": by_key[key].unit,
                "reason_codes": [reason.value for reason in by_key[key].reason_codes],
            }
            for key in keys
        },
    }


def assert_json_has_no_nan(value: object) -> None:
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        for item in value.values():
            assert_json_has_no_nan(item)
    elif isinstance(value, list):
        for item in value:
            assert_json_has_no_nan(item)


def diagnostic_fixture_set() -> SyntheticFixtureSet:
    return load_fixture_set(DIAGNOSTIC_FIXTURES / "cases.json")


def diagnostic_case(case_id: str) -> SyntheticDiagnosticCase:
    for case in diagnostic_fixture_set().cases:
        if case.case_id == case_id:
            return case
    raise AssertionError(f"diagnostic case not found: {case_id}")


def diagnostic_report_for_case(case_id: str) -> DiagnosticReport:
    return evaluate_rules(
        evidence_pack_from_case(diagnostic_case(case_id), clock=fixed_clock), clock=fixed_clock
    )


def diagnostic_projection(case_id: str) -> dict[str, object]:
    report = diagnostic_report_for_case(case_id)
    active_rules = set(report.triggered_rule_ids) | set(report.conflicting_rule_ids)
    projection: dict[str, object] = {
        "case_id": case_id,
        "overall_readiness": report.overall_readiness.value,
        "triggered_rule_ids": report.triggered_rule_ids,
        "insufficient_rule_ids": report.insufficient_rule_ids,
        "conflicting_rule_ids": report.conflicting_rule_ids,
        "result_statuses": {result.rule_id: result.status.value for result in report.results},
        "confidences": {result.rule_id: result.confidence.value for result in report.results},
    }
    if report.conflict_observations:
        projection["conflict_observations"] = report.conflict_observations
    active_keys = {
        result.rule_id: result.evidence_keys
        for result in report.results
        if result.rule_id in active_rules
    }
    if active_keys:
        projection["active_evidence_keys"] = active_keys
    return projection
