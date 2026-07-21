"""Deterministic dissertation-ready LaTeX tables and static figures."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from collections.abc import Iterable
from enum import StrEnum
from html import escape as xml_escape
from io import BytesIO
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.experiments.statistical_study import StatisticalStudy
from traffictwin.metrics.comparison import ComparisonReport
from traffictwin.metrics.results import MetricCollection, MetricStatus

LATEX_EXPORT_SCHEMA_VERSION: Literal["1.0"] = "1.0"
LATEX_RENDERER_VERSION: Literal["latex-fragment-v1"] = "latex-fragment-v1"
FIGURE_RENDERER_VERSION: Literal["static-figure-v1"] = "static-figure-v1"
MAX_TABLE_ROWS = 200
MAX_TABLE_COLUMNS = 8
MAX_CELL_CHARACTERS = 160
MAX_FIGURE_ENTRIES = 64
FIGURE_WIDTH = 1000
FIGURE_ROW_HEIGHT = 38


class _CanvasLike(Protocol):
    def setStrokeColor(self, colour: object) -> None: ...  # noqa: N802

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None: ...

    def setFillColor(self, colour: object) -> None: ...  # noqa: N802

    def setFont(self, font_name: str, font_size: float) -> None: ...  # noqa: N802

    def drawString(self, x: float, y: float, text: str) -> None: ...  # noqa: N802

    def drawRightString(self, x: float, y: float, text: str) -> None: ...  # noqa: N802

    def drawCentredString(self, x: float, y: float, text: str) -> None: ...  # noqa: N802

    def rect(
        self, x: float, y: float, width: float, height: float, *, fill: int, stroke: int
    ) -> None: ...

    def roundRect(  # noqa: N802
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        radius: float,
        *,
        fill: int,
        stroke: int,
    ) -> None: ...


class ResearchExportKind(StrEnum):
    """Typed artifact projections supported by REP-01."""

    METRICS = "metrics"
    COMPARISON = "comparison"
    STATISTICAL_STUDY = "statistical_study"
    RULES = "rules"


class ResearchFigureFormat(StrEnum):
    """Static figure encodings supported by REP-01."""

    SVG = "svg"
    PDF = "pdf"


class ResearchFigureEntry(BaseModel):
    """One exact scalar or categorical item rendered in a static figure."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=MAX_CELL_CHARACTERS)
    numeric_value: float | None = None
    category: str | None = Field(default=None, max_length=MAX_CELL_CHARACTERS)

    @model_validator(mode="after")
    def validate_value(self) -> ResearchFigureEntry:
        if (self.numeric_value is None) == (self.category is None):
            raise ValueError("figure entry requires exactly one numeric value or category")
        if self.numeric_value is not None and not math.isfinite(self.numeric_value):
            raise ValueError("figure numeric values must be finite")
        return self


class ResearchExportProjection(BaseModel):
    """Closed table/figure projection over one already-computed artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = LATEX_EXPORT_SCHEMA_VERSION
    kind: ResearchExportKind
    source_id: str = Field(min_length=1, max_length=MAX_CELL_CHARACTERS)
    title: str = Field(min_length=1, max_length=MAX_CELL_CHARACTERS)
    caption: str = Field(min_length=1, max_length=MAX_CELL_CHARACTERS)
    columns: list[str] = Field(min_length=1, max_length=MAX_TABLE_COLUMNS)
    rows: list[list[str]] = Field(max_length=MAX_TABLE_ROWS)
    figure_entries: list[ResearchFigureEntry] = Field(max_length=MAX_FIGURE_ENTRIES)
    synthetic: bool | None
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > MAX_CELL_CHARACTERS for value in values):
            raise ValueError("projection columns must be non-empty and bounded")
        if len(values) != len(set(values)):
            raise ValueError("projection columns must be unique")
        return values

    @model_validator(mode="after")
    def validate_rows(self) -> ResearchExportProjection:
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError("every projection row must match the column count")
            if any(len(cell) > MAX_CELL_CHARACTERS for cell in row):
                raise ValueError("projection cells must be bounded")
        figure_modes = {entry.numeric_value is not None for entry in self.figure_entries}
        if len(figure_modes) > 1:
            raise ValueError("projection figure entries must all use one rendering mode")
        return self

    def fingerprint(self) -> str:
        """Return the stable identity shared by every rendering."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResearchExportFile(BaseModel):
    """One published export without exposing its absolute local path."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    format: Literal["tex", "svg", "pdf"]
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1)


class ResearchExportReceipt(BaseModel):
    """Deterministic publication receipt for one projection."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = LATEX_EXPORT_SCHEMA_VERSION
    projection_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: list[ResearchExportFile] = Field(min_length=1, max_length=2)


class LatexExportContract(BaseModel):
    """Public REP-01 renderer and safety contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = LATEX_EXPORT_SCHEMA_VERSION
    latex_renderer_version: Literal["latex-fragment-v1"] = LATEX_RENDERER_VERSION
    figure_renderer_version: Literal["static-figure-v1"] = FIGURE_RENDERER_VERSION
    supported_artifacts: list[ResearchExportKind]
    figure_formats: list[ResearchFigureFormat]
    maximum_table_rows: int
    maximum_table_columns: int
    maximum_cell_characters: int
    maximum_figure_entries: int
    latex_environment: str
    escaping_policy: str
    source_mode_policy: str
    path_policy: str
    deterministic_policy: str
    scientific_boundary: str
    limitations: list[str]

    def fingerprint(self) -> str:
        """Return the stable contract identity."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def latex_export_contract() -> LatexExportContract:
    """Return the closed REP-01 rendering contract."""

    return LatexExportContract(
        supported_artifacts=list(ResearchExportKind),
        figure_formats=list(ResearchFigureFormat),
        maximum_table_rows=MAX_TABLE_ROWS,
        maximum_table_columns=MAX_TABLE_COLUMNS,
        maximum_cell_characters=MAX_CELL_CHARACTERS,
        maximum_figure_entries=MAX_FIGURE_ENTRIES,
        latex_environment="self-contained table fragment using only LaTeX2e tabular and hline",
        escaping_policy=(
            "Escape every LaTeX control character and XML metacharacter after collapsing "
            "whitespace and redacting absolute local path tokens."
        ),
        source_mode_policy=(
            "Every table and figure states synthetic, imported/non-synthetic, or unresolved."
        ),
        path_policy=(
            "Rendered content and receipts contain artifact identifiers and basenames only; "
            "absolute local input/output paths are never embedded."
        ),
        deterministic_policy=(
            "Tables and figures render one fingerprinted projection with fixed ordering, "
            "formatting, geometry, colours, fonts, and timestamp-free metadata."
        ),
        scientific_boundary=(
            "REP-01 renders already-computed typed artifacts and performs no metric, comparison, "
            "statistical, diagnostic, ranking, or causal calculation."
        ),
        limitations=[
            "Figures are compact deterministic publication aids, not interactive charts.",
            "Numeric figures use a shared signed linear scale and do not imply favourability.",
            "Rule figures show categorical statuses and do not convert confidence into "
            "probability.",
            "Long cells and non-scalar values are bounded for dissertation table readability.",
            "Final dissertation layout and captions still require researcher review.",
        ],
    )


def project_metric_collection(collection: MetricCollection) -> ResearchExportProjection:
    """Project a metric collection without recomputing any metric."""

    results = sorted(collection.results, key=lambda item: item.metric_key)
    rows = [
        [
            _bounded_text(result.metric_key),
            result.status.value,
            _format_value(result.value),
            _bounded_text(result.unit),
            _bounded_text(result.scope),
        ]
        for result in results[:MAX_TABLE_ROWS]
    ]
    figure_entries = [
        ResearchFigureEntry(
            label=_bounded_text(result.metric_key),
            numeric_value=float(cast(float | int, result.value)),
        )
        for result in results
        if result.status in {MetricStatus.AVAILABLE, MetricStatus.PARTIAL}
        and _finite_number(result.value)
    ][:MAX_FIGURE_ENTRIES]
    synthetic_values = {result.synthetic for result in results}
    synthetic = next(iter(synthetic_values)) if len(synthetic_values) == 1 else None
    warnings = _projection_warnings(
        synthetic,
        truncated=len(results) > MAX_TABLE_ROWS,
        figure_truncated=len(figure_entries) < _numeric_result_count(results),
    )
    return ResearchExportProjection(
        kind=ResearchExportKind.METRICS,
        source_id=_bounded_text(collection.run_id),
        title="TrafficTwin Metric Results",
        caption=f"Deterministic metric results for {_bounded_text(collection.run_id)}.",
        columns=["Metric", "Status", "Value", "Unit", "Scope"],
        rows=rows,
        figure_entries=figure_entries,
        synthetic=synthetic,
        warnings=warnings,
    )


def project_comparison_report(report: ComparisonReport) -> ResearchExportProjection:
    """Project one already-computed pairwise comparison."""

    comparisons = sorted(
        [*report.comparable_metrics, *report.unavailable_comparisons],
        key=lambda item: item.metric_key,
    )
    rows = [
        [
            _bounded_text(item.metric_key),
            item.status.value,
            _format_value(item.baseline),
            _format_value(item.variation),
            _format_value(item.absolute_delta),
            _bounded_text(item.unit or "unavailable"),
        ]
        for item in comparisons[:MAX_TABLE_ROWS]
    ]
    figure_candidates = [item for item in comparisons if _finite_number(item.absolute_delta)]
    figure_entries = [
        ResearchFigureEntry(
            label=_bounded_text(item.metric_key),
            numeric_value=float(cast(float, item.absolute_delta)),
        )
        for item in figure_candidates[:MAX_FIGURE_ENTRIES]
    ]
    baseline_id = _bounded_text(str(report.baseline_context.get("run_id", "baseline")))
    variation_id = _bounded_text(str(report.variation_context.get("run_id", "variation")))
    synthetic = _combined_synthetic(
        report.baseline_context.get("synthetic"),
        report.variation_context.get("synthetic"),
    )
    warnings = [
        *_projection_warnings(
            synthetic,
            truncated=len(comparisons) > MAX_TABLE_ROWS,
            figure_truncated=len(figure_candidates) > MAX_FIGURE_ENTRIES,
        ),
        *(_bounded_text(item) for item in report.warnings[:10]),
    ]
    return ResearchExportProjection(
        kind=ResearchExportKind.COMPARISON,
        source_id=_bounded_text(f"{baseline_id}-vs-{variation_id}"),
        title="TrafficTwin Metric Comparison",
        caption=f"Deterministic comparison of {baseline_id} and {variation_id}.",
        columns=["Metric", "Status", "Baseline", "Variation", "Delta", "Unit"],
        rows=rows,
        figure_entries=figure_entries,
        synthetic=synthetic,
        warnings=warnings[:20],
    )


def project_statistical_study(study: StatisticalStudy) -> ResearchExportProjection:
    """Project one completed or unavailable paired study without recalculation."""

    estimate = study.estimate
    interval = study.bootstrap_interval
    randomisation = study.randomisation_test
    effects = study.effect_sizes
    rows = [
        ["Study status", study.status.value, study.status.value, study.study_id],
        ["Primary metric", "declared", study.config.metric_key, study.metric_unit or "unavailable"],
        ["Eligible pairs", "observed", str(study.pairing_audit.eligible_pair_count), "random_seed"],
        [
            "Mean paired difference",
            estimate.status.value,
            _format_value(estimate.mean_paired_difference),
            estimate.unit or "unavailable",
        ],
        [
            "Bootstrap interval",
            interval.status.value,
            _format_interval(interval.lower, interval.upper),
            f"{_format_value(interval.confidence_level)}; {interval.method}",
        ],
        [
            "Randomisation p-value",
            randomisation.status.value,
            _format_value(randomisation.p_value),
            randomisation.method,
        ],
        ["Cohen dz", effects.status.value, _format_value(effects.cohen_dz), "secondary effect"],
        [
            "Matched-pairs rank-biserial",
            effects.status.value,
            _format_value(effects.matched_pairs_rank_biserial),
            "secondary effect",
        ],
    ]
    figure_entries = [
        ResearchFigureEntry(
            label=f"seed {observation.random_seed}",
            numeric_value=observation.paired_difference,
        )
        for observation in sorted(study.observations, key=lambda item: item.random_seed)[
            :MAX_FIGURE_ENTRIES
        ]
    ]
    warnings = [
        *_projection_warnings(
            study.synthetic,
            truncated=False,
            figure_truncated=len(study.observations) > MAX_FIGURE_ENTRIES,
        ),
        *(_bounded_text(item) for item in study.warnings[:10]),
    ]
    return ResearchExportProjection(
        kind=ResearchExportKind.STATISTICAL_STUDY,
        source_id=_bounded_text(study.study_id),
        title="TrafficTwin Paired Statistical Study",
        caption=f"Predeclared paired study {_bounded_text(study.study_id)}.",
        columns=["Measure", "Status", "Value", "Method or unit"],
        rows=rows,
        figure_entries=figure_entries,
        synthetic=study.synthetic,
        warnings=warnings[:20],
    )


def project_diagnostic_report(report: DiagnosticReport) -> ResearchExportProjection:
    """Project deterministic rule results without changing their status or confidence."""

    source_id = _bounded_text(report.evidence_pack_id)
    results = sorted(report.results, key=lambda item: item.rule_id)
    rows = [
        [
            _bounded_text(result.rule_id),
            _bounded_text(result.title),
            result.status.value,
            result.confidence.value,
            str(len(result.evidence_keys)),
            str(len(result.missing_evidence)),
        ]
        for result in results[:MAX_TABLE_ROWS]
    ]
    figure_entries = [
        ResearchFigureEntry(
            label=_bounded_text(result.rule_id),
            category=result.status.value,
        )
        for result in results[:MAX_FIGURE_ENTRIES]
    ]
    warnings = [
        *_projection_warnings(
            report.synthetic,
            truncated=len(results) > MAX_TABLE_ROWS,
            figure_truncated=len(results) > MAX_FIGURE_ENTRIES,
        ),
        *(_bounded_text(item) for item in report.warnings[:10]),
    ]
    return ResearchExportProjection(
        kind=ResearchExportKind.RULES,
        source_id=source_id,
        title="TrafficTwin Diagnostic Rule Results",
        caption=f"Deterministic diagnostic results for {source_id}.",
        columns=["Rule", "Title", "Status", "Confidence", "Evidence", "Missing"],
        rows=rows,
        figure_entries=figure_entries,
        synthetic=report.synthetic,
        warnings=warnings[:20],
    )


def projection_to_latex_fragment(projection: ResearchExportProjection) -> str:
    """Render a standalone-compilable escaped LaTeX table fragment."""

    fingerprint = projection.fingerprint()
    label = f"tab:traffictwin-{projection.kind.value.replace('_', '-')}-{fingerprint[:12]}"
    column_spec = "l" * len(projection.columns)
    lines = [
        "% TrafficTwin deterministic LaTeX fragment",
        f"% renderer: {LATEX_RENDERER_VERSION}",
        f"% projection-fingerprint: {fingerprint}",
        "{",
        r"\begin{table}[htbp]",
        r"\centering",
        f"\\caption{{{escape_latex(projection.caption)}}}",
        f"\\label{{{label}}}",
        r"\small",
        r"\renewcommand{\arraystretch}{1.15}",
        f"\\begin{{tabular}}{{{column_spec}}}",
        r"\hline",
        " & ".join(escape_latex(item) for item in projection.columns) + r" \\",
        r"\hline",
    ]
    if projection.rows:
        lines.extend(
            " & ".join(escape_latex(cell) for cell in row) + r" \\" for row in projection.rows
        )
    else:
        empty = ["No entries available", *([""] * (len(projection.columns) - 1))]
        lines.append(" & ".join(escape_latex(cell) for cell in empty) + r" \\")
    lines.extend(
        [
            r"\hline",
            r"\end{tabular}",
            r"\par\footnotesize",
            f"Source mode: {escape_latex(_source_mode(projection.synthetic))}.",
            "Rendered from projection " + escape_latex(fingerprint[:12]) + ".",
        ]
    )
    if projection.warnings:
        lines.append(" Warnings: " + escape_latex("; ".join(projection.warnings)) + ".")
    lines.extend([r"\end{table}", "}"])
    return "\n".join(lines) + "\n"


def projection_to_svg(projection: ResearchExportProjection) -> str:
    """Render a deterministic self-contained SVG figure."""

    entries = projection.figure_entries
    height = max(220, 150 + max(1, len(entries)) * FIGURE_ROW_HEIGHT)
    fingerprint = projection.fingerprint()
    title = xml_escape(_safe_text(projection.title), quote=True)
    source = xml_escape(_safe_text(projection.source_id), quote=True)
    mode = xml_escape(_source_mode(projection.synthetic), quote=True)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{FIGURE_WIDTH}" '
            f'height="{height}" viewBox="0 0 {FIGURE_WIDTH} {height}" role="img">'
        ),
        f"  <title>{title}</title>",
        (
            "  <desc>Deterministic TrafficTwin figure; source mode "
            f"{mode}; projection {fingerprint[:12]}.</desc>"
        ),
        '  <rect x="0" y="0" width="1000" height="100%" fill="#ffffff"/>',
        f'  <text x="40" y="42" font-family="Helvetica,Arial,sans-serif" font-size="24" '
        f'font-weight="700" fill="#17324d">{title}</text>',
        f'  <text x="40" y="70" font-family="Helvetica,Arial,sans-serif" font-size="13" '
        f'fill="#526473">Source: {source} | Mode: {mode} | Projection: '
        f"{fingerprint[:12]}</text>",
    ]
    if not entries:
        lines.append(
            '  <text x="40" y="125" font-family="Helvetica,Arial,sans-serif" '
            'font-size="16" fill="#526473">No finite scalar or categorical entries '
            "available.</text>"
        )
    elif entries[0].numeric_value is not None:
        lines.extend(_numeric_svg_rows(entries))
        lines.append(
            '  <text x="40" y="100" font-family="Helvetica,Arial,sans-serif" '
            'font-size="12" fill="#526473">Signed linear scale; direction does not imply '
            "favourability.</text>"
        )
    else:
        lines.extend(_categorical_svg_rows(entries))
        lines.append(
            '  <text x="40" y="100" font-family="Helvetica,Arial,sans-serif" '
            'font-size="12" fill="#526473">Categorical rule status; no probability is '
            "calculated.</text>"
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def projection_to_pdf(projection: ResearchExportProjection) -> bytes:
    """Render a deterministic multi-page PDF figure from the same projection."""

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen.canvas import Canvas

    output = BytesIO()
    page_width, page_height = landscape(A4)
    canvas = Canvas(
        output,
        pagesize=(page_width, page_height),
        invariant=1,
        pageCompression=0,
    )
    canvas.setTitle(_pdf_text(projection.title))
    canvas.setAuthor("TrafficTwin")
    canvas.setSubject("Deterministic REP-01 static research figure")
    entries = projection.figure_entries
    pages = [entries[index : index + 14] for index in range(0, len(entries), 14)] or [[]]
    numeric_scale = _numeric_scale(entries)
    for page_number, page_entries in enumerate(pages, start=1):
        canvas.setFillColor(colors.HexColor("#17324D"))
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawString(36, page_height - 42, _pdf_text(projection.title))
        canvas.setFillColor(colors.HexColor("#526473"))
        canvas.setFont("Helvetica", 8.5)
        canvas.drawString(
            36,
            page_height - 60,
            _pdf_text(
                f"Source: {projection.source_id} | Mode: {_source_mode(projection.synthetic)} | "
                f"Projection: {projection.fingerprint()[:12]}"
            ),
        )
        canvas.drawRightString(
            page_width - 36,
            24,
            f"Page {page_number} of {len(pages)}",
        )
        if not page_entries:
            canvas.setFont("Helvetica", 12)
            canvas.drawString(
                36, page_height - 105, "No finite scalar or categorical entries available."
            )
        else:
            _draw_pdf_entries(canvas, page_entries, page_height, numeric_scale)
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def write_projection_exports(
    projection: ResearchExportProjection,
    table_path: str | Path,
    *,
    figure_path: str | Path | None = None,
    overwrite: bool = False,
) -> ResearchExportReceipt:
    """Publish one LaTeX fragment and optional SVG/PDF figure with atomic file writes."""

    table = Path(table_path)
    if table.suffix.lower() != ".tex":
        raise ValueError("table output must use the .tex suffix")
    payloads: list[tuple[Path, bytes, Literal["tex", "svg", "pdf"]]] = [
        (table, projection_to_latex_fragment(projection).encode("utf-8"), "tex")
    ]
    if figure_path is not None:
        figure = Path(figure_path)
        suffix = figure.suffix.lower()
        if suffix == ".svg":
            figure_payload = projection_to_svg(projection).encode("utf-8")
            figure_format: Literal["svg", "pdf"] = "svg"
        elif suffix == ".pdf":
            figure_payload = projection_to_pdf(projection)
            figure_format = "pdf"
        else:
            raise ValueError("figure output must use the .svg or .pdf suffix")
        if figure.resolve() == table.resolve():
            raise ValueError("table and figure outputs must be different files")
        payloads.append((figure, figure_payload, figure_format))
    _publish_payloads(payloads, overwrite=overwrite)
    return ResearchExportReceipt(
        projection_fingerprint=projection.fingerprint(),
        files=[
            ResearchExportFile(
                name=target.name,
                format=output_format,
                checksum_sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
            )
            for target, payload, output_format in payloads
        ],
    )


def escape_latex(value: str) -> str:
    """Escape one already-bounded text value for ordinary LaTeX2e text mode."""

    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
        "|": r"\textbar{}",
    }
    return "".join(replacements.get(character, character) for character in _safe_text(value))


def _publish_payloads(
    payloads: list[tuple[Path, bytes, Literal["tex", "svg", "pdf"]]],
    *,
    overwrite: bool,
) -> None:
    targets = [target for target, _, _ in payloads]
    if len({target.resolve() for target in targets}) != len(targets):
        raise ValueError("export output paths must be unique")
    for target in targets:
        if target.is_symlink():
            raise ValueError(f"refusing symbolic-link output: {target}")
        if target.exists() and not target.is_file():
            raise ValueError(f"export output is not a regular file: {target}")
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    try:
        for target, payload, _ in payloads:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            staged.append((temporary, target))
        for temporary, target in staged:
            os.replace(temporary, target)
    finally:
        for temporary, _ in staged:
            if temporary.exists():
                temporary.unlink()


def _numeric_svg_rows(entries: list[ResearchFigureEntry]) -> list[str]:
    low, high = _numeric_scale(entries)
    chart_x = 420.0
    chart_width = 500.0
    zero_x = chart_x + ((0.0 - low) / (high - low)) * chart_width
    lines = [
        f'  <line x1="{zero_x:.2f}" y1="115" x2="{zero_x:.2f}" '
        f'y2="{125 + len(entries) * FIGURE_ROW_HEIGHT}" stroke="#526473" stroke-width="1"/>'
    ]
    for index, entry in enumerate(entries):
        assert entry.numeric_value is not None
        value = float(entry.numeric_value)
        y = 122 + index * FIGURE_ROW_HEIGHT
        value_x = chart_x + ((value - low) / (high - low)) * chart_width
        x = min(zero_x, value_x)
        width = max(1.0, abs(value_x - zero_x))
        colour = "#0b7285" if value > 0 else "#d97706" if value < 0 else "#7a8b99"
        label = xml_escape(_safe_text(entry.label), quote=True)
        lines.extend(
            [
                f'  <text x="40" y="{y + 15}" font-family="Helvetica,Arial,sans-serif" '
                f'font-size="12" fill="#243444">{label}</text>',
                f'  <rect x="{x:.2f}" y="{y}" width="{width:.2f}" height="20" '
                f'fill="{colour}" rx="2"/>',
                f'  <text x="930" y="{y + 15}" font-family="Helvetica,Arial,sans-serif" '
                f'font-size="12" text-anchor="end" fill="#243444">{_format_number(value)}</text>',
            ]
        )
    return lines


def _categorical_svg_rows(entries: list[ResearchFigureEntry]) -> list[str]:
    lines: list[str] = []
    for index, entry in enumerate(entries):
        y = 122 + index * FIGURE_ROW_HEIGHT
        category = _safe_text(entry.category or "unavailable")
        colour = _category_colour(category)
        label = xml_escape(_safe_text(entry.label), quote=True)
        category_text = xml_escape(category, quote=True)
        lines.extend(
            [
                f'  <text x="40" y="{y + 15}" font-family="Helvetica,Arial,sans-serif" '
                f'font-size="13" fill="#243444">{label}</text>',
                f'  <rect x="420" y="{y}" width="300" height="22" fill="{colour}" rx="4"/>',
                f'  <text x="570" y="{y + 15}" font-family="Helvetica,Arial,sans-serif" '
                f'font-size="12" text-anchor="middle" fill="#ffffff">{category_text}</text>',
            ]
        )
    return lines


def _draw_pdf_entries(
    canvas: _CanvasLike,
    entries: list[ResearchFigureEntry],
    page_height: float,
    numeric_scale: tuple[float, float],
) -> None:
    from reportlab.lib import colors

    low, high = numeric_scale
    chart_x = 330.0
    chart_width = 430.0
    zero_x = chart_x + ((0.0 - low) / (high - low)) * chart_width
    numeric = entries[0].numeric_value is not None
    if numeric:
        canvas.setStrokeColor(colors.HexColor("#526473"))
        canvas.line(zero_x, page_height - 90, zero_x, 47)
    for index, entry in enumerate(entries):
        y = page_height - 105 - index * 32
        canvas.setFillColor(colors.HexColor("#243444"))
        canvas.setFont("Helvetica", 8.5)
        canvas.drawString(36, y + 5, _pdf_text(entry.label)[:54])
        if numeric:
            assert entry.numeric_value is not None
            value = float(entry.numeric_value)
            value_x = chart_x + ((value - low) / (high - low)) * chart_width
            x = min(zero_x, value_x)
            width = max(1.0, abs(value_x - zero_x))
            colour = "#0B7285" if value > 0 else "#D97706" if value < 0 else "#7A8B99"
            canvas.setFillColor(colors.HexColor(colour))
            canvas.rect(x, y, width, 14, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#243444"))
            canvas.drawRightString(805, y + 4, _format_number(value))
        else:
            category = _safe_text(entry.category or "unavailable")
            canvas.setFillColor(colors.HexColor(_category_colour(category)))
            canvas.roundRect(330, y - 1, 250, 17, 3, fill=1, stroke=0)
            canvas.setFillColor(colors.white)
            canvas.drawCentredString(455, y + 4, _pdf_text(category))


def _numeric_scale(entries: Iterable[ResearchFigureEntry]) -> tuple[float, float]:
    values = [float(entry.numeric_value) for entry in entries if entry.numeric_value is not None]
    if not values:
        return (-1.0, 1.0)
    low = min(0.0, min(values))
    high = max(0.0, max(values))
    if low == high:
        return (-1.0, 1.0)
    if low == 0.0:
        low = -high * 0.04
    if high == 0.0:
        high = abs(low) * 0.04
    return (low, high)


def _category_colour(category: str) -> str:
    return {
        "triggered": "#b42318",
        "not_triggered": "#16794b",
        "insufficient_evidence": "#667085",
        "conflicting_evidence": "#b54708",
        "invalid": "#7a5af8",
    }.get(category, "#526473")


def _projection_warnings(
    synthetic: bool | None,
    *,
    truncated: bool,
    figure_truncated: bool,
) -> list[str]:
    warnings: list[str] = []
    if synthetic is True:
        warnings.append("Synthetic evidence; not real-world validation")
    elif synthetic is None:
        warnings.append("Source mode is unresolved")
    if truncated:
        warnings.append(f"Table limited to {MAX_TABLE_ROWS} rows")
    if figure_truncated:
        warnings.append(f"Figure limited to {MAX_FIGURE_ENTRIES} entries")
    return warnings


def _numeric_result_count(results: Iterable[object]) -> int:
    return sum(
        1
        for result in results
        if getattr(result, "status", None) in {MetricStatus.AVAILABLE, MetricStatus.PARTIAL}
        and _finite_number(getattr(result, "value", None))
    )


def _combined_synthetic(baseline: object, variation: object) -> bool | None:
    if isinstance(baseline, bool) and isinstance(variation, bool) and baseline == variation:
        return baseline
    return None


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _format_interval(lower: float | None, upper: float | None) -> str:
    if lower is None or upper is None:
        return "unavailable"
    return f"[{_format_number(lower)}, {_format_number(upper)}]"


def _format_value(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _format_number(value) if math.isfinite(value) else "unavailable"
    if isinstance(value, str):
        return _bounded_text(value)
    safe_value = _sanitize_json_value(value)
    try:
        rendered = json.dumps(safe_value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        rendered = str(safe_value)
    return _bounded_text(rendered)


def _sanitize_json_value(value: object) -> object:
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            _safe_text(str(key)): _sanitize_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return value


def _format_number(value: float) -> str:
    if value == 0:
        return "0"
    return f"{value:.6g}"


def _source_mode(synthetic: bool | None) -> str:
    if synthetic is True:
        return "synthetic"
    if synthetic is False:
        return "imported or non-synthetic"
    return "unresolved"


_POSIX_ABSOLUTE_PATH = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)+[^\s,;:)\]}]+")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)\b[A-Z]:\\(?:[^\\\s]+\\)+[^\s,;:)\]}]+")


def _safe_text(value: str) -> str:
    text = " ".join(str(value).replace("\x00", "").split())
    text = _POSIX_ABSOLUTE_PATH.sub(_redacted_path, text)
    text = _WINDOWS_ABSOLUTE_PATH.sub(_redacted_path, text)
    return text


def _redacted_path(match: re.Match[str]) -> str:
    value = match.group(0).replace("\\", "/")
    basename = value.rstrip("/").rsplit("/", 1)[-1] or "path"
    return f"[local-path:{basename}]"


def _bounded_text(value: str) -> str:
    text = _safe_text(value)
    if len(text) <= MAX_CELL_CHARACTERS:
        return text
    return text[: MAX_CELL_CHARACTERS - 3].rstrip() + "..."


def _pdf_text(value: str) -> str:
    safe = _safe_text(value)
    return safe.encode("latin-1", "replace").decode("latin-1")
