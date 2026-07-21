from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.integration.sumo.contract import sumo_results_capability_manifest
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
from traffictwin.reporting.builder import build_comparison_report, build_run_report
from traffictwin.reporting.executive import (
    EXECUTIVE_SUMMARY_BOUNDARY_WARNING,
    ExecutiveSummaryError,
    ExecutiveSummarySourceMode,
    executive_summary_contract,
    executive_summary_to_html,
    executive_summary_to_markdown,
    project_executive_summary,
)
from traffictwin.reporting.executive_pdf import (
    ExecutiveSummaryLayoutError,
    executive_summary_to_pdf_bytes,
)
from traffictwin.reporting.models import ReportClaimAvailability, ReportClaimKind

BASELINE = Path("tests/fixtures/bundles/baseline_valid")
VARIATION = Path("tests/fixtures/bundles/variation_valid")
NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def test_executive_summary_contract_and_capabilities_are_closed() -> None:
    contract = executive_summary_contract()

    assert contract.contract_version == "executive-summary-v1"
    assert contract.maximum_highlights == 5
    assert contract.source_warning_policy == "retain_all_or_refuse"
    assert contract.pdf_overflow_policy == "fail_closed"
    assert contract.performs_scientific_recomputation is False
    assert contract.includes_analyst_annotations is False
    assert contract.fingerprint() == executive_summary_contract().fingerprint()
    assert (
        default_export_import_manifest().supports.one_page_executive_summary
        is CapabilitySupport.TRUE
    )
    assert (
        sumo_results_capability_manifest().supports.one_page_executive_summary
        is CapabilitySupport.FALSE
    )
    assert (
        tos_data_capability_manifest().supports.one_page_executive_summary
        is CapabilitySupport.FALSE
    )


def test_projection_retains_warnings_limitations_availability_and_links() -> None:
    report = build_run_report(BASELINE, clock=lambda: NOW).model_copy(
        update={"warnings": ["Source warning A", "Source warning B"]}
    )

    summary = project_executive_summary(
        report,
        source_report_reference="saved-baseline.json",
    )

    assert summary.source_mode is ExecutiveSummarySourceMode.SYNTHETIC
    assert summary.availability.total_claims == 33
    assert summary.availability.available_claims == 13
    assert summary.availability.unavailable_claims == 20
    assert sum(summary.availability.by_kind.values()) == 33
    assert len(summary.highlights) == 5
    assert summary.omitted_claims == 28
    assert any(
        item.claim_kind is ReportClaimKind.METRIC_RESULT
        and item.availability is ReportClaimAvailability.AVAILABLE
        for item in summary.highlights
    )
    assert summary.warnings[0] == EXECUTIVE_SUMMARY_BOUNDARY_WARNING
    assert summary.warnings[-2:] == ["Source warning A", "Source warning B"]
    assert summary.source_warning_count == 2
    assert summary.limitations == next(
        items for title, items in report.sections if title == "Limitations"
    )
    assert [item.reference_id for item in summary.provenance_links] == [
        "P0",
        "P1",
        "P2",
        "P3",
        "P4",
        "P5",
    ]
    assert summary.analyst_annotations_included is False
    assert summary.scientific_recomputation_performed is False
    assert (
        summary.fingerprint()
        == project_executive_summary(
            report,
            source_report_reference="saved-baseline.json",
        ).fingerprint()
    )


def test_renderers_escape_authored_text_and_retain_every_warning() -> None:
    report = build_run_report(BASELINE, clock=lambda: NOW)
    references = list(report.claim_references)
    references[0] = references[0].model_copy(update={"label": "<script>alert(1)</script>"})
    report = report.model_copy(
        update={
            "claim_references": references,
            "warnings": ["First <warning>", "Final warning"],
        }
    )
    summary = project_executive_summary(report, source_report_reference="source report.json")

    markdown = executive_summary_to_markdown(summary)
    html = executive_summary_to_html(summary)

    assert "First \\<warning\\>" in markdown
    assert "Final warning" in markdown
    assert "<script>" not in html
    assert "&lt;script&gt;" in html or "&lt;warning&gt;" in html
    assert summary.source_report_reference == "source report.json"
    assert "%20" in summary.provenance_links[0].href


def test_pdf_is_deterministic_a4_single_page_with_all_boundaries() -> None:
    summary = project_executive_summary(
        build_run_report(BASELINE, clock=lambda: NOW),
        source_report_reference="baseline.json",
    )

    first = executive_summary_to_pdf_bytes(summary)
    second = executive_summary_to_pdf_bytes(summary)
    document = PdfReader(BytesIO(first))
    text = "\n".join(page.extract_text() or "" for page in document.pages)

    assert first == second
    assert len(document.pages) == 1
    assert float(document.pages[0].mediabox.width) == pytest.approx(595.276, abs=0.01)
    assert float(document.pages[0].mediabox.height) == pytest.approx(841.89, abs=0.01)
    assert "Warnings - all retained (3)" in text
    assert "Limitations - all retained (3)" in text
    assert "Provenance links" in text
    assert "Page 1 of 1" in text


def test_comparison_highlight_restates_existing_delta_and_direction() -> None:
    report = build_comparison_report(BASELINE, VARIATION, clock=lambda: NOW)
    summary = project_executive_summary(report, source_report_reference="comparison.json")
    comparison = next(
        item
        for item in summary.highlights
        if item.claim_kind is ReportClaimKind.METRIC_COMPARISON
        and item.availability is ReportClaimAvailability.AVAILABLE
    )
    snapshot = next(item for item in report.claim_snapshots if item.claim_id == comparison.claim_id)

    assert isinstance(snapshot.value, dict)
    assert str(snapshot.value["absolute_delta"]) in comparison.display_value
    assert str(snapshot.value["direction"]) in comparison.display_value


def test_pdf_refuses_overflow_without_omitting_source_warnings() -> None:
    final_warning = "FINAL-WARNING-MUST-NOT-BE-OMITTED " + "z" * 900
    warnings = [f"warning-{index} " + "x" * 900 for index in range(30)] + [final_warning]
    report = build_run_report(BASELINE, clock=lambda: NOW).model_copy(update={"warnings": warnings})
    summary = project_executive_summary(report)

    assert summary.warnings[-1] == final_warning
    assert "z" * 900 in executive_summary_to_markdown(summary)
    with pytest.raises(ExecutiveSummaryLayoutError, match="one-page export refused"):
        executive_summary_to_pdf_bytes(summary)


def test_projection_rejects_incomplete_inventory_and_redacts_absolute_source_path() -> None:
    report = build_run_report(BASELINE, clock=lambda: NOW)
    incomplete = report.model_copy(update={"claim_snapshots": []})
    absolute = report.model_copy(update={"source_reference": "/private/user/secret/bundle"})

    with pytest.raises(ExecutiveSummaryError, match="INCOMPLETE_CLAIM_INVENTORY"):
        project_executive_summary(incomplete)
    assert project_executive_summary(absolute).source_reference == "bundle"
