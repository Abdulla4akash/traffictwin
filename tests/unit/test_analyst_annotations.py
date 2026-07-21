from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from tests.unit.test_registry import make_run
from traffictwin.annotations import (
    AnalystAnnotationRequest,
    AnalystAnnotationTargetKind,
    AnalystArtifactReference,
    AnalystDecisionLabel,
    analyst_annotation_contract,
    build_analyst_annotation,
)
from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.integration.sumo.contract import sumo_results_capability_manifest
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
from traffictwin.reporting.annotation_rendering import (
    ReportAnnotationError,
    attach_analyst_annotations,
)
from traffictwin.reporting.builder import build_run_report
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.pdf import report_to_pdf_bytes
from traffictwin.storage.registry import Registry, RegistryNotFoundError

FIRST_TIME = datetime(2026, 7, 21, 9, 0, tzinfo=UTC)
SECOND_TIME = datetime(2026, 7, 21, 9, 5, tzinfo=UTC)


def _request(
    target: AnalystArtifactReference,
    note: str = "Review the missing-energy warning before publication.",
    *,
    label: AnalystDecisionLabel = AnalystDecisionLabel.FOLLOW_UP,
) -> AnalystAnnotationRequest:
    return AnalystAnnotationRequest(
        target=target,
        author_label="S. M. Abdulla Al Mamun",
        note=note,
        decision_label=label,
    )


def test_annotation_contract_is_closed_and_deterministic() -> None:
    contract = analyst_annotation_contract()

    assert contract.contract_version == "analyst-annotations-v1"
    assert AnalystAnnotationTargetKind.RUN in contract.registry_verified_target_kinds
    assert (
        AnalystAnnotationTargetKind.RESEARCH_REPORT not in contract.registry_verified_target_kinds
    )
    assert contract.maximum_note_characters == 4_000
    assert contract.fingerprint() == analyst_annotation_contract().fingerprint()
    assert "cannot change metrics" in contract.scientific_boundary
    assert default_export_import_manifest().supports.analyst_annotations is CapabilitySupport.TRUE
    assert (
        sumo_results_capability_manifest().supports.analyst_annotations is CapabilitySupport.FALSE
    )
    assert tos_data_capability_manifest().supports.analyst_annotations is CapabilitySupport.FALSE


def test_annotation_inputs_reject_paths_controls_and_blank_notes() -> None:
    with pytest.raises(ValidationError, match="artifact_id"):
        AnalystArtifactReference(kind="run", artifact_id="/absolute/private/run")
    with pytest.raises(ValidationError, match="visible text"):
        _request(AnalystArtifactReference(kind="run", artifact_id="run-001"), "   ")
    with pytest.raises(ValidationError, match="control"):
        _request(AnalystArtifactReference(kind="run", artifact_id="run-001"), "unsafe\x00note")


def test_registry_appends_orders_filters_and_reads_annotations(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.add_run(make_run())
    unbound = AnalystArtifactReference(kind="run", artifact_id="run-001")
    exact = AnalystArtifactReference(
        kind="run",
        artifact_id="run-001",
        artifact_fingerprint="a" * 64,
    )

    first = registry.append_analyst_annotation(_request(unbound), clock=lambda: FIRST_TIME)
    second = registry.append_analyst_annotation(
        _request(exact, "Decision recorded.", label=AnalystDecisionLabel.ACCEPTED),
        clock=lambda: SECOND_TIME,
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert registry.get_analyst_annotation(first.annotation_id) == first
    assert registry.inspect().analyst_annotation_count == 2
    assert [item.sequence for item in registry.list_analyst_annotations(limit=10).annotations] == [
        1,
        2,
    ]
    assert [
        item.sequence
        for item in registry.list_analyst_annotations(target=unbound, limit=10).annotations
    ] == [1]
    exact_history = registry.list_analyst_annotations(target=exact, limit=1)
    assert [item.sequence for item in exact_history.annotations] == [1]
    assert exact_history.has_more
    second_page = registry.list_analyst_annotations(
        target=exact,
        after_sequence=1,
        limit=10,
    )
    assert [item.sequence for item in second_page.annotations] == [2]
    assert second_page.fingerprint() == second_page.fingerprint()


def test_registry_requires_stored_targets_and_database_rejects_mutation(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    registry = Registry(path)
    target = AnalystArtifactReference(kind="run", artifact_id="run-missing")

    with pytest.raises(RegistryNotFoundError, match="annotation target not found"):
        registry.append_analyst_annotation(_request(target), clock=lambda: FIRST_TIME)

    detached = AnalystArtifactReference(kind="research_report", artifact_id="report-run-001")
    annotation = registry.append_analyst_annotation(_request(detached), clock=lambda: FIRST_TIME)
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE analyst_annotations SET note = 'changed' WHERE annotation_id = ?",
                (annotation.annotation_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM analyst_annotations WHERE annotation_id = ?",
                (annotation.annotation_id,),
            )


def test_report_attachment_is_distinct_safe_and_claim_neutral() -> None:
    report = build_run_report(
        "tests/fixtures/bundles/baseline_valid",
        clock=lambda: FIRST_TIME,
    )
    target = next(
        item
        for item in report.annotation_targets
        if item.kind is AnalystAnnotationTargetKind.RESEARCH_REPORT
    )
    annotation = build_analyst_annotation(
        _request(target, "<script>alert('x')</script>\n# not a heading"),
        sequence=7,
        created_at=SECOND_TIME,
    )

    attached = attach_analyst_annotations(report, [annotation])
    markdown = report_to_markdown(attached)
    html = report_to_html(attached)
    pdf = report_to_pdf_bytes(attached)
    pdf_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)

    assert attached.sections == report.sections
    assert attached.claim_references == report.claim_references
    assert len(attached.claim_references) == len(report.claim_references)
    assert attached.analyst_annotations == [annotation]
    assert "Analyst Annotations — Non-computed" in markdown
    assert "\\# not a heading" in markdown
    assert "<script>" not in html
    assert 'class="analyst-annotations"' in html
    assert "Analyst Annotations - Non-computed" in pdf_text
    assert any(item.category == "analyst_annotations" for item in attached.claim_exclusions)


def test_report_rejects_unrelated_annotation() -> None:
    report = build_run_report(
        "tests/fixtures/bundles/baseline_valid",
        clock=lambda: FIRST_TIME,
    )
    unrelated = build_analyst_annotation(
        _request(AnalystArtifactReference(kind="research_report", artifact_id="another-report")),
        sequence=1,
        created_at=FIRST_TIME,
    )

    with pytest.raises(ReportAnnotationError, match="unrelated target"):
        attach_analyst_annotations(report, [unrelated])
