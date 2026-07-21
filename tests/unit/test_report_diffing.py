from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.integration.sumo.contract import sumo_results_capability_manifest
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
from traffictwin.reporting.builder import build_diagnostics_report, build_run_report
from traffictwin.reporting.diffing import (
    MAX_REPORT_DIFF_INPUT_BYTES,
    ReportDiffClassification,
    ReportDiffCompatibilityCode,
    ReportDiffError,
    StructuredReportDiffStatus,
    compare_structured_reports,
    parse_research_report_json,
    report_diff_contract,
    report_diff_to_markdown,
    report_scientific_fingerprint,
)
from traffictwin.reporting.models import (
    ReportClaimAvailability,
    ReportClaimKind,
    ReportClaimReference,
    ReportClaimSnapshot,
    ResearchReport,
    ResearchReportType,
)

BASELINE = Path("tests/fixtures/bundles/baseline_valid")
VARIATION = Path("tests/fixtures/bundles/variation_valid")
NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def test_report_diff_contract_and_capability_are_closed_and_deterministic() -> None:
    contract = report_diff_contract()

    assert contract.contract_version == "structured-report-diff-v1"
    assert contract.supported_report_types == [
        ResearchReportType.RUN,
        ResearchReportType.DIAGNOSTICS,
        ResearchReportType.COMPARISON,
        ResearchReportType.FULL,
    ]
    assert contract.compares_rendered_prose is False
    assert contract.compares_analyst_annotations is False
    assert contract.fingerprint() == report_diff_contract().fingerprint()
    assert (
        default_export_import_manifest().supports.structured_report_diffing
        is CapabilitySupport.TRUE
    )
    assert (
        sumo_results_capability_manifest().supports.structured_report_diffing
        is CapabilitySupport.FALSE
    )
    assert (
        tos_data_capability_manifest().supports.structured_report_diffing is CapabilitySupport.FALSE
    )


def test_report_builders_emit_complete_prose_free_claim_snapshots() -> None:
    report = build_run_report(BASELINE, clock=lambda: NOW)

    assert len(report.claim_snapshots) == len(report.claim_references) == 33
    assert {item.claim_id for item in report.claim_snapshots} == {
        item.claim_id for item in report.claim_references
    }
    rule = next(
        item for item in report.claim_snapshots if item.claim_kind is ReportClaimKind.RULE_RESULT
    )
    assert "hypothesis" not in rule.value
    assert "recommendations" not in rule.value
    assert "statement" not in str(rule.value)


def test_diff_ignores_narrative_identity_timestamps_and_annotations() -> None:
    baseline = build_run_report(BASELINE, clock=lambda: NOW)
    variation = baseline.model_copy(
        deep=True,
        update={
            "report_id": "another-report-id",
            "title": "A different presentation title",
            "generated_at": NOW + timedelta(days=1),
            "source_reference": "another/source",
            "warnings": ["Presentation-only warning"],
            "sections": [
                (title, [f"changed narrative {index}"])
                for index, (title, _items) in enumerate(baseline.sections)
            ],
        },
    )

    result = compare_structured_reports(baseline, variation)

    assert result.status is StructuredReportDiffStatus.AVAILABLE
    assert result.baseline_fingerprint == result.variation_fingerprint
    assert report_scientific_fingerprint(baseline) == report_scientific_fingerprint(variation)
    assert all(
        section.classification
        in {ReportDiffClassification.UNCHANGED, ReportDiffClassification.UNAVAILABLE}
        for section in result.sections
    )
    assert "changed narrative" not in result.model_dump_json()


def test_diff_classifies_real_typed_metric_changes_without_prose() -> None:
    baseline = build_run_report(BASELINE, clock=lambda: NOW)
    variation = build_run_report(VARIATION, clock=lambda: NOW)

    result = compare_structured_reports(baseline, variation)
    metrics = next(item for item in result.sections if item.section == "Metrics")

    assert result.status is StructuredReportDiffStatus.AVAILABLE
    assert metrics.classification is ReportDiffClassification.CHANGED
    completion = next(
        item
        for item in metrics.claims
        if item.scientific_key == "metric_result:task.completion.rate"
    )
    assert completion.classification is ReportDiffClassification.CHANGED
    assert any(change.path == "/value" for change in completion.field_changes)
    markdown = report_diff_to_markdown(result)
    assert "descriptive and non-causal" in markdown
    assert "sections[*].body" in markdown
    assert "Reproduction Commands:" not in markdown


def test_diff_classifies_added_removed_and_unavailable_sections() -> None:
    baseline = _minimal_report(
        "baseline",
        sections=[("Metrics", ["secret baseline prose"]), ("Removed", ["do not diff"])],
        value=1.0,
    )
    variation = _minimal_report(
        "variation",
        sections=[("Metrics", ["secret variation prose"]), ("Added", ["do not diff"])],
        value=2.0,
    )

    result = compare_structured_reports(baseline, variation)
    by_section = {item.section: item for item in result.sections}

    assert by_section["Metrics"].classification is ReportDiffClassification.CHANGED
    assert by_section["Removed"].classification is ReportDiffClassification.REMOVED
    assert by_section["Added"].classification is ReportDiffClassification.ADDED
    assert "secret baseline prose" not in result.model_dump_json()

    unavailable = _minimal_report(
        "unavailable",
        sections=[("Metrics", ["ignored"])],
        value=None,
        availability=ReportClaimAvailability.UNAVAILABLE,
        status="unavailable",
    )
    unavailable_result = compare_structured_reports(unavailable, unavailable)
    assert unavailable_result.sections[0].classification is ReportDiffClassification.UNAVAILABLE


def test_diff_returns_typed_unavailable_result_for_incompatible_reports() -> None:
    baseline = build_run_report(BASELINE, clock=lambda: NOW)
    diagnostics = build_diagnostics_report(BASELINE, clock=lambda: NOW)
    imported = baseline.model_copy(update={"synthetic": False})
    future_schema = baseline.model_copy(update={"payload_schema_version": "2.0"})

    type_result = compare_structured_reports(baseline, diagnostics)
    mode_result = compare_structured_reports(baseline, imported)
    schema_result = compare_structured_reports(baseline, future_schema)

    assert type_result.status is StructuredReportDiffStatus.UNAVAILABLE
    assert ReportDiffCompatibilityCode.REPORT_TYPE_MISMATCH in type_result.compatibility_codes
    assert type_result.sections == []
    assert mode_result.status is StructuredReportDiffStatus.UNAVAILABLE
    assert ReportDiffCompatibilityCode.SOURCE_MODE_MISMATCH in mode_result.compatibility_codes
    assert (
        ReportDiffCompatibilityCode.PAYLOAD_SCHEMA_VERSION_MISMATCH
        in schema_result.compatibility_codes
    )
    assert (
        ReportDiffCompatibilityCode.UNSUPPORTED_PAYLOAD_SCHEMA_VERSION
        in schema_result.compatibility_codes
    )


def test_report_json_parser_enforces_bounds_and_inventory_consistency() -> None:
    report = _minimal_report("baseline", sections=[("Metrics", ["ignored"])], value=1.0)
    parsed = parse_research_report_json(report.model_dump_json())
    duplicate = parsed.model_copy(
        update={"claim_snapshots": [*parsed.claim_snapshots, parsed.claim_snapshots[0]]}
    )

    assert parsed == report
    with pytest.raises(ReportDiffError, match="duplicate structured report claim snapshot ID"):
        compare_structured_reports(duplicate, report)
    with pytest.raises(ReportDiffError, match="exceeds"):
        parse_research_report_json(b" " * (MAX_REPORT_DIFF_INPUT_BYTES + 1))


def _minimal_report(
    report_id: str,
    *,
    sections: list[tuple[str, list[str]]],
    value: float | None,
    availability: ReportClaimAvailability = ReportClaimAvailability.AVAILABLE,
    status: str = "available",
) -> ResearchReport:
    claim_id = f"{report_id}:metric:task.completion.rate"
    reference = ReportClaimReference(
        claim_id=claim_id,
        claim_kind=ReportClaimKind.METRIC_RESULT,
        artifact_key="task.completion.rate",
        section="Metrics",
        label="Completion rate",
    )
    snapshot = ReportClaimSnapshot(
        claim_id=claim_id,
        claim_kind=ReportClaimKind.METRIC_RESULT,
        artifact_key="task.completion.rate",
        section="Metrics",
        availability=availability,
        status=status,
        value=value,
        unit="ratio",
        details={"implementation_version": "1.0", "scope": "run", "dimensions": {}},
    )
    return ResearchReport(
        report_id=report_id,
        title="Minimal typed report",
        generated_at=NOW,
        source_reference="fixture",
        synthetic=True,
        sections=sections,
        report_type=ResearchReportType.RUN,
        claim_references=[reference],
        claim_snapshots=[snapshot],
    )
