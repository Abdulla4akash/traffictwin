"""Deterministic supervisor-facing executive summaries for REP-04."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from html import escape
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.reporting.diffing import (
    StructuredReportDiffStatus,
    compare_structured_reports,
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

EXECUTIVE_SUMMARY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
EXECUTIVE_SUMMARY_CONTRACT_VERSION: Literal["executive-summary-v1"] = "executive-summary-v1"
EXECUTIVE_SUMMARY_RENDERER_VERSION: Literal["executive-summary-renderer-v1"] = (
    "executive-summary-renderer-v1"
)
MAX_EXECUTIVE_SUMMARY_HIGHLIGHTS = 5
MAX_EXECUTIVE_SUMMARY_SOURCE_WARNINGS = 100
MAX_EXECUTIVE_SUMMARY_LIMITATIONS = 100

EXECUTIVE_SUMMARY_SELECTION_POLICY = (
    "Select at most two triggered rule results, two available comparison results with a "
    "non-unchanged direction, one unavailable claim, and one remaining rule result; then fill "
    "unused positions with available metrics, remaining comparisons, remaining rules, and other "
    "claims. Break every tie by scientific claim key."
)

EXECUTIVE_SUMMARY_BOUNDARY_WARNING = (
    "This bounded summary renders existing typed claims only. It does not calculate metrics, "
    "infer causes, rank desirability, or replace the complete structured report."
)
EXECUTIVE_SUMMARY_SYNTHETIC_WARNING = (
    "Synthetic source mode: these results are software-demonstration evidence, not real-world "
    "validation or live traffic evidence."
)
EXECUTIVE_SUMMARY_IMPORTED_WARNING = (
    "Imported source mode: interpret results only within the source manifest, validation, and "
    "provenance boundaries. No live-data status is implied."
)
EXECUTIVE_SUMMARY_SELECTION_WARNING = (
    "Only the published bounded highlight selection is shown below; availability counts and the "
    "source-report link expose the complete typed claim inventory."
)


class ExecutiveSummaryError(RuntimeError):
    """Raised when a source report cannot be projected safely for REP-04."""


class ExecutiveSummarySourceMode(StrEnum):
    """Closed source-mode labels admitted to executive summaries."""

    SYNTHETIC = "synthetic"
    IMPORTED = "imported"


class ExecutiveSummaryFormat(StrEnum):
    """Supported REP-04 presentation and machine-readable outputs."""

    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"


class ExecutiveSummaryAvailability(BaseModel):
    """Exact availability inventory for all typed claims in the source report."""

    model_config = ConfigDict(extra="forbid")

    total_claims: int = Field(ge=0, le=500)
    available_claims: int = Field(ge=0, le=500)
    unavailable_claims: int = Field(ge=0, le=500)
    by_kind: dict[ReportClaimKind, int]

    @model_validator(mode="after")
    def validate_counts(self) -> ExecutiveSummaryAvailability:
        if self.available_claims + self.unavailable_claims != self.total_claims:
            msg = "executive-summary availability counts must reconcile"
            raise ValueError(msg)
        if sum(self.by_kind.values()) != self.total_claims:
            msg = "executive-summary claim-kind counts must reconcile"
            raise ValueError(msg)
        return self


class ExecutiveSummaryProvenanceLink(BaseModel):
    """One visible link back to the exact source report or selected typed claim."""

    model_config = ConfigDict(extra="forbid")

    reference_id: str = Field(pattern=r"^P[0-5]$")
    label: str = Field(min_length=1, max_length=4_000)
    href: str = Field(min_length=1, max_length=4_000)
    target_kind: str = Field(min_length=1, max_length=128)
    target_id: str = Field(min_length=1, max_length=1_024)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecutiveSummaryHighlight(BaseModel):
    """One selected existing typed claim with no new scientific interpretation."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1, le=MAX_EXECUTIVE_SUMMARY_HIGHLIGHTS)
    claim_id: str = Field(min_length=1, max_length=1_024)
    scientific_key: str = Field(min_length=1, max_length=1_024)
    claim_kind: ReportClaimKind
    label: str = Field(min_length=1, max_length=4_000)
    availability: ReportClaimAvailability
    status: str = Field(min_length=1, max_length=128)
    display_value: str = Field(min_length=1, max_length=256)
    unit: str | None = Field(default=None, max_length=128)
    reason_codes: list[str] = Field(default_factory=list, max_length=100)
    provenance_reference_id: str = Field(pattern=r"^P[1-5]$")
    claim_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecutiveSummary(BaseModel):
    """Bounded renderer projection for one already-computed structured report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = EXECUTIVE_SUMMARY_SCHEMA_VERSION
    contract_version: Literal["executive-summary-v1"] = EXECUTIVE_SUMMARY_CONTRACT_VERSION
    renderer_version: Literal["executive-summary-renderer-v1"] = EXECUTIVE_SUMMARY_RENDERER_VERSION
    summary_id: str = Field(min_length=1, max_length=1_024)
    title: str = Field(min_length=1, max_length=4_000)
    generated_at: str = Field(min_length=1, max_length=128)
    source_mode: ExecutiveSummarySourceMode
    source_report_type: ResearchReportType
    source_report_id: str = Field(min_length=1, max_length=1_024)
    source_report_reference: str = Field(min_length=1, max_length=512)
    source_reference: str = Field(min_length=1, max_length=4_000)
    source_payload_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_scientific_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    availability: ExecutiveSummaryAvailability
    highlights: list[ExecutiveSummaryHighlight] = Field(
        default_factory=list,
        max_length=MAX_EXECUTIVE_SUMMARY_HIGHLIGHTS,
    )
    omitted_claims: int = Field(ge=0, le=500)
    selection_policy: str = EXECUTIVE_SUMMARY_SELECTION_POLICY
    mandatory_warning_count: int = Field(ge=3, le=3)
    source_warning_count: int = Field(
        ge=0,
        le=MAX_EXECUTIVE_SUMMARY_SOURCE_WARNINGS,
    )
    warnings: list[str] = Field(default_factory=list, max_length=103)
    limitations: list[str] = Field(
        min_length=1,
        max_length=MAX_EXECUTIVE_SUMMARY_LIMITATIONS,
    )
    provenance_links: list[ExecutiveSummaryProvenanceLink] = Field(
        min_length=1,
        max_length=MAX_EXECUTIVE_SUMMARY_HIGHLIGHTS + 1,
    )
    analyst_annotations_included: Literal[False] = False
    scientific_recomputation_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_projection(self) -> ExecutiveSummary:
        if len(self.warnings) != self.mandatory_warning_count + self.source_warning_count:
            msg = "executive summary must retain every mandatory and source warning"
            raise ValueError(msg)
        if self.omitted_claims != self.availability.total_claims - len(self.highlights):
            msg = "executive-summary omitted-claim count must reconcile"
            raise ValueError(msg)
        expected_ranks = list(range(1, len(self.highlights) + 1))
        if [item.rank for item in self.highlights] != expected_ranks:
            msg = "executive-summary highlight ranks must be contiguous"
            raise ValueError(msg)
        expected_references = [f"P{index}" for index in range(len(self.provenance_links))]
        if [item.reference_id for item in self.provenance_links] != expected_references:
            msg = "executive-summary provenance references must be contiguous from P0"
            raise ValueError(msg)
        if [item.provenance_reference_id for item in self.highlights] != expected_references[1:]:
            msg = "executive-summary highlights must match their provenance references"
            raise ValueError(msg)
        return self

    def fingerprint(self) -> str:
        """Return a deterministic identity for the complete projection."""

        return _sha256(self.model_dump(mode="json"))


class ExecutiveSummaryContract(BaseModel):
    """Machine-readable REP-04 projection and rendering boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = EXECUTIVE_SUMMARY_SCHEMA_VERSION
    contract_version: Literal["executive-summary-v1"] = EXECUTIVE_SUMMARY_CONTRACT_VERSION
    renderer_version: Literal["executive-summary-renderer-v1"] = EXECUTIVE_SUMMARY_RENDERER_VERSION
    supported_report_types: list[ResearchReportType]
    supported_formats: list[ExecutiveSummaryFormat]
    maximum_highlights: int = MAX_EXECUTIVE_SUMMARY_HIGHLIGHTS
    maximum_source_warnings: int = MAX_EXECUTIVE_SUMMARY_SOURCE_WARNINGS
    maximum_limitations: int = MAX_EXECUTIVE_SUMMARY_LIMITATIONS
    selection_policy: str = EXECUTIVE_SUMMARY_SELECTION_POLICY
    source_warning_policy: Literal["retain_all_or_refuse"] = "retain_all_or_refuse"
    limitation_policy: Literal["retain_all_or_refuse"] = "retain_all_or_refuse"
    pdf_overflow_policy: Literal["fail_closed"] = "fail_closed"
    requires_complete_typed_claim_inventory: Literal[True] = True
    includes_analyst_annotations: Literal[False] = False
    performs_scientific_recomputation: Literal[False] = False
    supports_causal_interpretation: Literal[False] = False

    def fingerprint(self) -> str:
        """Return the deterministic contract fingerprint."""

        return _sha256(self.model_dump(mode="json"))


def executive_summary_contract() -> ExecutiveSummaryContract:
    """Return the closed v1.0 executive-summary contract."""

    return ExecutiveSummaryContract(
        supported_report_types=[
            ResearchReportType.RUN,
            ResearchReportType.DIAGNOSTICS,
            ResearchReportType.COMPARISON,
            ResearchReportType.FULL,
        ],
        supported_formats=list(ExecutiveSummaryFormat),
    )


def project_executive_summary(
    report: ResearchReport,
    *,
    source_report_reference: str | None = None,
) -> ExecutiveSummary:
    """Project one compatible typed report without recomputing its scientific artifacts."""

    validation = compare_structured_reports(report, report)
    if validation.status is not StructuredReportDiffStatus.AVAILABLE:
        codes = ", ".join(item.value for item in validation.compatibility_codes)
        msg = f"source report is unavailable for executive summary: {codes}"
        raise ExecutiveSummaryError(msg)
    if len(report.warnings) > MAX_EXECUTIVE_SUMMARY_SOURCE_WARNINGS:
        msg = (
            "source report contains more than "
            f"{MAX_EXECUTIVE_SUMMARY_SOURCE_WARNINGS} warnings; none were omitted"
        )
        raise ExecutiveSummaryError(msg)

    references = {item.claim_id: item for item in report.claim_references}
    snapshots = {item.claim_id: item for item in report.claim_snapshots}
    pairs = [(references[claim_id], snapshots[claim_id]) for claim_id in references]
    selected = _select_highlights(pairs)
    safe_report_reference = _safe_report_reference(
        source_report_reference or f"{report.report_id}.json"
    )
    source_payload_fingerprint = _sha256(report.model_dump(mode="json"))
    source_scientific_fingerprint = report_scientific_fingerprint(report)
    source_href = quote(safe_report_reference, safe="._-")
    provenance_links = [
        ExecutiveSummaryProvenanceLink(
            reference_id="P0",
            label="Complete structured source report",
            href=source_href,
            target_kind="research_report",
            target_id=report.report_id,
            fingerprint=source_payload_fingerprint,
        )
    ]
    highlights: list[ExecutiveSummaryHighlight] = []
    for rank, (reference, snapshot) in enumerate(selected, start=1):
        reference_id = f"P{rank}"
        claim_fingerprint = _sha256(snapshot.scientific_payload())
        highlights.append(
            ExecutiveSummaryHighlight(
                rank=rank,
                claim_id=reference.claim_id,
                scientific_key=reference.scientific_key,
                claim_kind=reference.claim_kind,
                label=reference.label,
                availability=snapshot.availability,
                status=snapshot.status,
                display_value=_display_value(snapshot),
                unit=snapshot.unit,
                reason_codes=list(snapshot.reason_codes),
                provenance_reference_id=reference_id,
                claim_fingerprint=claim_fingerprint,
            )
        )
        provenance_links.append(
            ExecutiveSummaryProvenanceLink(
                reference_id=reference_id,
                label=reference.label,
                href=f"{source_href}#claim={quote(reference.claim_id, safe='._:-')}",
                target_kind=reference.claim_kind.value,
                target_id=reference.claim_id,
                fingerprint=claim_fingerprint,
            )
        )

    mode = (
        ExecutiveSummarySourceMode.SYNTHETIC
        if report.synthetic
        else ExecutiveSummarySourceMode.IMPORTED
    )
    mode_warning = (
        EXECUTIVE_SUMMARY_SYNTHETIC_WARNING
        if mode is ExecutiveSummarySourceMode.SYNTHETIC
        else EXECUTIVE_SUMMARY_IMPORTED_WARNING
    )
    mandatory_warnings = [
        EXECUTIVE_SUMMARY_BOUNDARY_WARNING,
        mode_warning,
        EXECUTIVE_SUMMARY_SELECTION_WARNING,
    ]
    limitations = _source_limitations(report)
    availability = _availability(report.claim_snapshots)
    return ExecutiveSummary(
        summary_id=f"executive-{report.report_id}",
        title=f"Executive Summary: {report.title}",
        generated_at=report.generated_at.isoformat(),
        source_mode=mode,
        source_report_type=report.report_type,
        source_report_id=report.report_id,
        source_report_reference=safe_report_reference,
        source_reference=_safe_source_display(report.source_reference),
        source_payload_fingerprint=source_payload_fingerprint,
        source_scientific_fingerprint=source_scientific_fingerprint,
        availability=availability,
        highlights=highlights,
        omitted_claims=availability.total_claims - len(highlights),
        mandatory_warning_count=len(mandatory_warnings),
        source_warning_count=len(report.warnings),
        warnings=[*mandatory_warnings, *report.warnings],
        limitations=limitations,
        provenance_links=provenance_links,
    )


def executive_summary_to_markdown(summary: ExecutiveSummary) -> str:
    """Render the bounded projection to accessible Markdown."""

    availability = summary.availability
    lines = [
        f"# {_escape_markdown(summary.title)}",
        "",
        f"- Summary ID: `{_escape_markdown(summary.summary_id)}`",
        f"- Source mode: `{summary.source_mode.value}`",
        f"- Source report type: `{summary.source_report_type.value}`",
        f"- Source report: [{_escape_markdown(summary.source_report_reference)}]"
        f"({_escape_href(summary.provenance_links[0].href)})",
        f"- Source evidence: `{_escape_markdown(summary.source_reference)}`",
        f"- Scientific fingerprint: `{summary.source_scientific_fingerprint}`",
        f"- Summary fingerprint: `{summary.fingerprint()}`",
        "",
        "## Evidence Availability",
        "",
        f"- Total typed claims: `{availability.total_claims}`",
        f"- Available: `{availability.available_claims}`",
        f"- Unavailable: `{availability.unavailable_claims}`",
        f"- Not shown as highlights: `{summary.omitted_claims}`",
        "",
        "## Selected Computed Highlights",
        "",
    ]
    if not summary.highlights:
        lines.extend(["- No typed computed claims were available for selection.", ""])
    for item in summary.highlights:
        unit = f" {item.unit}" if item.unit else ""
        reasons = ", ".join(item.reason_codes) or "none"
        lines.extend(
            [
                f"### {item.rank}. {_escape_markdown(item.label)} [{item.provenance_reference_id}]",
                "",
                f"- Claim: `{_escape_markdown(item.scientific_key)}`",
                f"- Status: `{_escape_markdown(item.status)}` / `{item.availability.value}`",
                f"- Value: `{_escape_markdown(item.display_value)}{_escape_markdown(unit)}`",
                f"- Reason codes: `{_escape_markdown(reasons)}`",
                "",
            ]
        )
    lines.extend(["## Warnings - All Retained", ""])
    for warning in summary.warnings:
        lines.append(f"> {_escape_markdown(warning)}")
        lines.append("")
    lines.extend(["## Limitations - All Retained", ""])
    lines.extend(f"- {_escape_markdown(item)}" for item in summary.limitations)
    lines.extend(["", "## Provenance Links", ""])
    lines.extend(
        f"- **{item.reference_id}:** [{_escape_markdown(item.label)}]"
        f"({_escape_href(item.href)}) - `{item.fingerprint}`"
        for item in summary.provenance_links
    )
    lines.extend(
        [
            "",
            "## Selection Boundary",
            "",
            f"- {_escape_markdown(summary.selection_policy)}",
            "- Analyst annotations included: `false`",
            "- Scientific recomputation performed: `false`",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def executive_summary_to_html(summary: ExecutiveSummary) -> str:
    """Render a self-contained print-oriented HTML executive summary."""

    highlights = "".join(_highlight_html(item) for item in summary.highlights) or (
        '<p class="empty">No typed computed claims were available for selection.</p>'
    )
    warnings = "".join(f"<li>{escape(item)}</li>" for item in summary.warnings)
    limitations = "".join(f"<li>{escape(item)}</li>" for item in summary.limitations)
    links = "".join(
        f"<li><strong>{item.reference_id}</strong> "
        f'<a href="{escape(item.href, quote=True)}">{escape(item.label)}</a> '
        f"<code>{item.fingerprint[:12]}</code></li>"
        for item in summary.provenance_links
    )
    availability = summary.availability
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{escape(summary.title)}</title>\n"
        "<style>"
        "@page{size:A4;margin:12mm}*{box-sizing:border-box}"
        "body{font:12px/1.35 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"
        "color:#17324d;margin:0;background:#fff}main{max-width:186mm;margin:auto}"
        "h1{font-size:21px;margin:0 0 5px}h2{font-size:13px;color:#0b7285;"
        "margin:10px 0 4px;border-bottom:1px solid #bfd7df}"
        ".meta{color:#4d5e6b;font-size:10px}.cards{display:grid;grid-template-columns:"
        "repeat(4,1fr);gap:5px}.card{padding:6px;background:#eef6f8;border-radius:5px}"
        ".card strong{font-size:16px;display:block}.highlight{padding:4px 6px;"
        "margin:3px 0;border-left:3px solid #0b7285;background:#f7fafb}"
        ".highlight p{margin:1px 0}.warning{background:#fff7e6;border:1px solid #d97706;"
        "padding:5px 8px}.limits{background:#f3f4f6;padding:5px 8px}"
        "ul{margin:3px 0;padding-left:18px}li{margin:1px 0}code{font-size:9px}"
        ".boundary{font-size:9px;color:#526473}.empty{font-style:italic}"
        "a{color:#075985;overflow-wrap:anywhere}@media print{main{max-width:none}}"
        "</style>\n</head>\n<body>\n<main>\n"
        f"<h1>{escape(summary.title)}</h1>"
        f'<div class="meta">Source mode: <strong>{summary.source_mode.value}</strong> | '
        f"Report: {escape(summary.source_report_id)} | Generated: "
        f"{escape(summary.generated_at)}<br>Source evidence: "
        f"{escape(summary.source_reference)} | Scientific fingerprint: "
        f"<code>{summary.source_scientific_fingerprint}</code></div>"
        "<h2>Evidence availability</h2>"
        '<div class="cards">'
        f'<div class="card"><strong>{availability.total_claims}</strong>Total claims</div>'
        f'<div class="card"><strong>{availability.available_claims}</strong>Available</div>'
        f'<div class="card"><strong>{availability.unavailable_claims}</strong>Unavailable</div>'
        f'<div class="card"><strong>{summary.omitted_claims}</strong>Beyond highlights</div>'
        "</div>"
        f"<h2>Selected computed highlights</h2>{highlights}"
        f"<h2>Warnings - all retained ({len(summary.warnings)})</h2>"
        f'<div class="warning"><ul>{warnings}</ul></div>'
        f"<h2>Limitations - all retained ({len(summary.limitations)})</h2>"
        f'<div class="limits"><ul>{limitations}</ul></div>'
        f"<h2>Provenance links</h2><ul>{links}</ul>"
        f'<p class="boundary">Selection policy: {escape(summary.selection_policy)} '
        "Analyst annotations included: false. Scientific recomputation performed: false.</p>"
        "</main>\n</body>\n</html>\n"
    )


def _select_highlights(
    pairs: list[tuple[ReportClaimReference, ReportClaimSnapshot]],
) -> list[tuple[ReportClaimReference, ReportClaimSnapshot]]:
    ordered = sorted(pairs, key=lambda pair: pair[0].scientific_key)
    selected: list[tuple[ReportClaimReference, ReportClaimSnapshot]] = []
    selected_ids: set[str] = set()

    def add(
        candidates: list[tuple[ReportClaimReference, ReportClaimSnapshot]],
        limit: int | None = None,
    ) -> None:
        added = 0
        for candidate in candidates:
            if len(selected) >= MAX_EXECUTIVE_SUMMARY_HIGHLIGHTS:
                return
            if candidate[0].claim_id in selected_ids:
                continue
            selected.append(candidate)
            selected_ids.add(candidate[0].claim_id)
            added += 1
            if limit is not None and added >= limit:
                return

    add(
        [
            pair
            for pair in ordered
            if pair[0].claim_kind is ReportClaimKind.RULE_RESULT and pair[1].status == "triggered"
        ],
        2,
    )
    add(
        [
            pair
            for pair in ordered
            if pair[0].claim_kind is ReportClaimKind.METRIC_COMPARISON
            and pair[1].availability is ReportClaimAvailability.AVAILABLE
            and _comparison_direction(pair[1]) != "unchanged"
        ],
        2,
    )
    add(
        [pair for pair in ordered if pair[1].availability is ReportClaimAvailability.UNAVAILABLE],
        1,
    )
    add(
        [pair for pair in ordered if pair[0].claim_kind is ReportClaimKind.RULE_RESULT],
        1,
    )
    add(
        [
            pair
            for pair in ordered
            if pair[0].claim_kind is ReportClaimKind.METRIC_RESULT
            and pair[1].availability is ReportClaimAvailability.AVAILABLE
        ]
    )
    add([pair for pair in ordered if pair[0].claim_kind is ReportClaimKind.METRIC_COMPARISON])
    add([pair for pair in ordered if pair[0].claim_kind is ReportClaimKind.RULE_RESULT])
    add(ordered)
    return selected


def _comparison_direction(snapshot: ReportClaimSnapshot) -> object:
    return snapshot.value.get("direction") if isinstance(snapshot.value, dict) else None


def _display_value(snapshot: ReportClaimSnapshot) -> str:
    if snapshot.availability is ReportClaimAvailability.UNAVAILABLE:
        return "Unavailable"
    value = snapshot.value
    if snapshot.claim_kind is ReportClaimKind.METRIC_COMPARISON and isinstance(value, dict):
        display = (
            f"{_compact_scalar(value.get('baseline'))} -> "
            f"{_compact_scalar(value.get('variation'))}; delta "
            f"{_compact_scalar(value.get('absolute_delta'))}; direction "
            f"{_compact_scalar(value.get('direction'))}"
        )
        return display if len(display) <= 256 else "Comparison value; follow provenance link"
    if isinstance(value, (dict, list)):
        return f"Structured value ({len(value)} entries); follow provenance link"
    rendered = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(rendered) > 240:
        return "Long typed value; follow provenance link"
    return rendered


def _compact_scalar(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _availability(snapshots: list[ReportClaimSnapshot]) -> ExecutiveSummaryAvailability:
    available = sum(item.availability is ReportClaimAvailability.AVAILABLE for item in snapshots)
    by_kind = dict.fromkeys(ReportClaimKind, 0)
    for item in snapshots:
        by_kind[item.claim_kind] += 1
    return ExecutiveSummaryAvailability(
        total_claims=len(snapshots),
        available_claims=available,
        unavailable_claims=len(snapshots) - available,
        by_kind=by_kind,
    )


def _source_limitations(report: ResearchReport) -> list[str]:
    limitations = [
        item
        for title, items in report.sections
        if title.strip().casefold() == "limitations"
        for item in items
    ]
    if len(limitations) > MAX_EXECUTIVE_SUMMARY_LIMITATIONS:
        msg = (
            "source report contains more than "
            f"{MAX_EXECUTIVE_SUMMARY_LIMITATIONS} limitations; none were omitted"
        )
        raise ExecutiveSummaryError(msg)
    if not limitations:
        return ["No explicit limitations section was supplied by the source report."]
    return limitations


def _safe_report_reference(value: str) -> str:
    reference = Path(value.replace("\\", "/")).name
    if not reference or reference in {".", ".."}:
        raise ExecutiveSummaryError("source report reference must name one file")
    return reference


def _safe_source_display(value: str) -> str:
    normalised = value.replace("\\", "/")
    candidate = Path(normalised)
    windows_absolute = len(normalised) >= 3 and normalised[1:3] == ":/"
    return candidate.name if candidate.is_absolute() or windows_absolute else value


def _highlight_html(item: ExecutiveSummaryHighlight) -> str:
    unit = f" {item.unit}" if item.unit else ""
    reasons = ", ".join(item.reason_codes) or "none"
    return (
        '<article class="highlight">'
        f"<strong>{item.rank}. {escape(item.label)} [{item.provenance_reference_id}]</strong>"
        f"<p><code>{escape(item.scientific_key)}</code> | {escape(item.status)} / "
        f"{item.availability.value} | {escape(item.display_value + unit)}</p>"
        f"<p>Reason codes: {escape(reasons)}</p>"
        "</article>"
    )


def _escape_markdown(value: str) -> str:
    escaped = value.replace("\r", " ").replace("\n", " ").replace("\\", "\\\\")
    for character in "`*_{}[]()<>#+-.!|":
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _escape_href(value: str) -> str:
    return value.replace("(", "%28").replace(")", "%29")


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
