from __future__ import annotations

import hashlib
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collections,
)
from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.experiments.statistical_study import evaluate_paired_statistical_study
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.integration.sumo.contract import sumo_results_capability_manifest
from traffictwin.integration.tos.capabilities import tos_data_capability_manifest
from traffictwin.metrics.comparison import compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.reporting.latex import (
    MAX_CELL_CHARACTERS,
    ResearchExportKind,
    ResearchExportProjection,
    ResearchFigureEntry,
    escape_latex,
    latex_export_contract,
    project_comparison_report,
    project_diagnostic_report,
    project_metric_collection,
    project_statistical_study,
    projection_to_latex_fragment,
    projection_to_pdf,
    projection_to_svg,
    write_projection_exports,
)
from traffictwin.rules.engine import evaluate_rules

FIXED_TIME = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
BASELINE = Path("tests/fixtures/bundles/baseline_valid")
VARIATION = Path("tests/fixtures/bundles/variation_valid")


def _metric_projection() -> ResearchExportProjection:
    validation = validate_bundle(BASELINE)
    metrics = compute_metrics_for_bundle(validation, clock=lambda: FIXED_TIME)
    return project_metric_collection(metrics)


def _diagnostic_report() -> DiagnosticReport:
    validation = validate_bundle(BASELINE)
    metrics = compute_metrics_for_bundle(validation, clock=lambda: FIXED_TIME)
    evidence = build_evidence_pack(validation, metrics, clock=lambda: FIXED_TIME)
    return evaluate_rules(evidence, clock=lambda: FIXED_TIME)


def _special_projection() -> ResearchExportProjection:
    return ResearchExportProjection(
        kind=ResearchExportKind.METRICS,
        source_id="/Users/researcher/private/run.json",
        title="Special & unsafe_looking title",
        caption="100% escaped #1 {table}",
        columns=["Metric", "Value"],
        rows=[["plugin.a&b_1", "/Users/researcher/private/value_$5"]],
        figure_entries=[ResearchFigureEntry(label="plugin.a&b_1", numeric_value=-5.0)],
        synthetic=False,
        warnings=["Never infer x > y"],
    )


def test_contract_closes_artifacts_formats_bounds_and_scientific_boundary() -> None:
    contract = latex_export_contract()

    assert contract.supported_artifacts == list(ResearchExportKind)
    assert [item.value for item in contract.figure_formats] == ["svg", "pdf"]
    assert contract.maximum_table_rows == 200
    assert contract.maximum_figure_entries == 64
    assert "performs no metric" in contract.scientific_boundary
    assert len(contract.fingerprint()) == 64
    assert default_export_import_manifest().supports.latex_research_export is CapabilitySupport.TRUE
    assert (
        sumo_results_capability_manifest().supports.latex_research_export is CapabilitySupport.FALSE
    )
    assert tos_data_capability_manifest().supports.latex_research_export is CapabilitySupport.FALSE


def test_latex_escaping_and_absolute_path_redaction_are_deterministic() -> None:
    projection = _special_projection()
    first = projection_to_latex_fragment(projection)
    second = projection_to_latex_fragment(projection)

    assert first == second
    assert "\\&" in first
    assert "\\_" in first
    assert "\\%" in first
    assert "\\#" in first
    assert "\\{" in first
    assert "\\$" in first
    assert "/Users/" not in first
    assert "local-path:value" in first
    assert escape_latex("a_b&c") == r"a\_b\&c"
    assert "https://example.com/data/file.csv" in escape_latex("https://example.com/data/file.csv")


def test_diagnostic_projection_uses_stable_evidence_identity() -> None:
    first_report = _diagnostic_report()
    second_report = first_report.model_copy(update={"report_id": "diagnostic-later-clock"})

    first = project_diagnostic_report(first_report)
    second = project_diagnostic_report(second_report)

    assert first.source_id == first_report.evidence_pack_id
    assert first == second
    assert first.fingerprint() == second.fingerprint()


def test_projection_rejects_invalid_rows_mixed_figure_modes_and_unbounded_cells() -> None:
    base = _special_projection().model_dump(mode="json")

    with pytest.raises(ValidationError, match="column count"):
        ResearchExportProjection.model_validate({**base, "rows": [["one"]]})
    with pytest.raises(ValidationError, match="one rendering mode"):
        ResearchExportProjection.model_validate(
            {
                **base,
                "figure_entries": [
                    {"label": "numeric", "numeric_value": 1.0},
                    {"label": "category", "category": "triggered"},
                ],
            }
        )
    with pytest.raises(ValidationError):
        ResearchExportProjection.model_validate(
            {**base, "rows": [["metric", "x" * (MAX_CELL_CHARACTERS + 1)]]}
        )


def test_all_four_typed_artifacts_project_without_recalculation() -> None:
    baseline_validation = validate_bundle(BASELINE)
    variation_validation = validate_bundle(VARIATION)
    baseline = compute_metrics_for_bundle(baseline_validation, clock=lambda: FIXED_TIME)
    variation = compute_metrics_for_bundle(variation_validation, clock=lambda: FIXED_TIME)
    comparison = compare_metric_collections(baseline, variation, clock=lambda: FIXED_TIME)
    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0, 3.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    diagnostics = _diagnostic_report()

    metrics_projection = project_metric_collection(baseline)
    comparison_projection = project_comparison_report(comparison)
    study_projection = project_statistical_study(study)
    rules_projection = project_diagnostic_report(diagnostics)

    assert metrics_projection.kind is ResearchExportKind.METRICS
    assert comparison_projection.kind is ResearchExportKind.COMPARISON
    assert study_projection.kind is ResearchExportKind.STATISTICAL_STUDY
    assert rules_projection.kind is ResearchExportKind.RULES
    assert len(metrics_projection.rows) == len(baseline.results)
    assert len(comparison_projection.rows) == len(
        comparison.comparable_metrics + comparison.unavailable_comparisons
    )
    assert study_projection.rows[3][2] == "2"
    assert [row[0] for row in rules_projection.rows] == sorted(
        result.rule_id for result in diagnostics.results
    )
    assert baseline == compute_metrics_for_bundle(
        baseline_validation,
        clock=lambda: FIXED_TIME,
    )


def test_svg_is_valid_self_contained_xml_with_projection_identity() -> None:
    projection = _metric_projection()

    first = projection_to_svg(projection)
    second = projection_to_svg(projection)
    root = ET.fromstring(first)  # noqa: S314 - parses our own bounded renderer output

    assert first == second
    assert root.tag.endswith("svg")
    assert projection.fingerprint()[:12] in first
    assert "http://www.w3.org/2000/svg" in first
    assert "<script" not in first.lower()
    assert "/Users/" not in projection_to_svg(_special_projection())


def test_pdf_is_byte_deterministic_parseable_and_contains_no_local_path() -> None:
    projection = _special_projection()

    first = projection_to_pdf(projection)
    second = projection_to_pdf(projection)
    reader = PdfReader(BytesIO(first))

    assert first == second
    assert first.startswith(b"%PDF")
    assert len(reader.pages) == 1
    assert "/Users/" not in first.decode("latin-1")


def test_writer_publishes_checksums_and_refuses_unapproved_overwrite(tmp_path: Path) -> None:
    projection = _metric_projection()
    table = tmp_path / "metrics.tex"
    figure = tmp_path / "metrics.svg"

    receipt = write_projection_exports(projection, table, figure_path=figure)

    assert [item.name for item in receipt.files] == ["metrics.tex", "metrics.svg"]
    assert receipt.projection_fingerprint == projection.fingerprint()
    assert receipt.files[0].checksum_sha256 == hashlib.sha256(table.read_bytes()).hexdigest()
    assert receipt.files[1].checksum_sha256 == hashlib.sha256(figure.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        write_projection_exports(projection, table, figure_path=figure)

    overwritten = write_projection_exports(
        projection,
        table,
        figure_path=figure,
        overwrite=True,
    )
    assert overwritten == receipt


def test_writer_rejects_bad_suffix_duplicate_and_symbolic_link_targets(tmp_path: Path) -> None:
    projection = _metric_projection()

    with pytest.raises(ValueError, match=".tex"):
        write_projection_exports(projection, tmp_path / "table.txt")
    with pytest.raises(ValueError, match=".svg or .pdf"):
        write_projection_exports(
            projection,
            tmp_path / "table.tex",
            figure_path=tmp_path / "figure.png",
        )
    target = tmp_path / "real.tex"
    target.write_text("user content", encoding="utf-8")
    alias = tmp_path / "alias.tex"
    alias.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic-link"):
        write_projection_exports(projection, alias, overwrite=True)


def test_latex_fragment_compiles_in_a_minimal_document(tmp_path: Path) -> None:
    compiler = shutil.which("tectonic")
    if compiler is None:
        pytest.skip("tectonic is not installed")
    document = tmp_path / "document.tex"
    document.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        + projection_to_latex_fragment(_special_projection())
        + "\\end{document}\n",
        encoding="utf-8",
    )

    completed = subprocess.run(  # noqa: S603
        [compiler, "--outdir", str(tmp_path), str(document)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (tmp_path / "document.pdf").exists()
