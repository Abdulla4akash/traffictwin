"""Deterministic structured report diffing for REP-03."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from traffictwin.reporting.models import (
    ReportClaimAvailability,
    ReportClaimReference,
    ReportClaimSnapshot,
    ResearchReport,
    ResearchReportType,
)

REPORT_DIFF_SCHEMA_VERSION: Literal["1.0"] = "1.0"
REPORT_DIFF_CONTRACT_VERSION: Literal["structured-report-diff-v1"] = "structured-report-diff-v1"
MAX_REPORT_DIFF_INPUT_BYTES = 2_000_000
MAX_REPORT_DIFF_SECTIONS = 100
MAX_REPORT_DIFF_CLAIMS = 500
MAX_REPORT_DIFF_FIELD_CHANGES = 2_000

REPORT_DIFF_EXCLUDED_FIELDS = [
    "title",
    "generated_at",
    "source_reference",
    "warnings",
    "sections[*].body",
    "claim_references[*].label",
    "claim_exclusions",
    "annotation_targets",
    "analyst_annotations",
]

REPORT_DIFF_WARNING = (
    "Structured differences are descriptive and non-causal. Only typed claim snapshots are "
    "scientific comparison inputs; rendered prose and analyst annotations are excluded."
)

_ClaimType = TypeVar("_ClaimType", ReportClaimReference, ReportClaimSnapshot)


class ReportDiffError(RuntimeError):
    """Raised when a report payload violates the REP-03 input contract."""


class StructuredReportDiffStatus(StrEnum):
    """Whether the two structured payloads were compatible for diffing."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ReportDiffClassification(StrEnum):
    """Closed classification for report sections and typed claims."""

    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNAVAILABLE = "unavailable"


class ReportDiffCompatibilityCode(StrEnum):
    """Stable report-level incompatibility reasons."""

    PAYLOAD_SCHEMA_VERSION_MISMATCH = "PAYLOAD_SCHEMA_VERSION_MISMATCH"
    UNSUPPORTED_PAYLOAD_SCHEMA_VERSION = "UNSUPPORTED_PAYLOAD_SCHEMA_VERSION"
    REPORT_TYPE_MISMATCH = "REPORT_TYPE_MISMATCH"
    SOURCE_MODE_MISMATCH = "SOURCE_MODE_MISMATCH"
    CLAIM_DENOMINATOR_MISMATCH = "CLAIM_DENOMINATOR_MISMATCH"
    UNSUPPORTED_REPORT_TYPE = "UNSUPPORTED_REPORT_TYPE"
    INCOMPLETE_CLAIM_INVENTORY = "INCOMPLETE_CLAIM_INVENTORY"


class ReportSectionUnavailableReason(StrEnum):
    """Stable reasons that a compatible section cannot produce a scientific diff."""

    NO_TYPED_CLAIMS = "NO_TYPED_CLAIMS"
    TYPED_CLAIM_UNAVAILABLE = "TYPED_CLAIM_UNAVAILABLE"


class ReportFieldChange(BaseModel):
    """One exact JSON-pointer change inside a typed claim snapshot."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=1_024)
    baseline_present: bool
    variation_present: bool
    baseline: Any = None
    variation: Any = None


class ReportClaimDiff(BaseModel):
    """Structured comparison of one report-independent typed claim."""

    model_config = ConfigDict(extra="forbid")

    scientific_key: str = Field(min_length=1, max_length=1_024)
    classification: ReportDiffClassification
    baseline_claim_id: str | None = None
    variation_claim_id: str | None = None
    baseline_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    variation_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    field_changes: list[ReportFieldChange] = Field(
        default_factory=list,
        max_length=MAX_REPORT_DIFF_FIELD_CHANGES,
    )


class ReportSectionDiff(BaseModel):
    """One section classified only from structure and typed claim snapshots."""

    model_config = ConfigDict(extra="forbid")

    section: str = Field(min_length=1, max_length=256)
    classification: ReportDiffClassification
    baseline_present: bool
    variation_present: bool
    baseline_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    variation_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    unavailable_reasons: list[ReportSectionUnavailableReason] = Field(default_factory=list)
    claims: list[ReportClaimDiff] = Field(default_factory=list, max_length=MAX_REPORT_DIFF_CLAIMS)


class StructuredReportDiff(BaseModel):
    """Deterministic REP-03 result for two structured report payloads."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = REPORT_DIFF_SCHEMA_VERSION
    contract_version: Literal["structured-report-diff-v1"] = REPORT_DIFF_CONTRACT_VERSION
    status: StructuredReportDiffStatus
    report_type: ResearchReportType | None
    baseline_report_id: str
    variation_report_id: str
    baseline_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    variation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    compatibility_codes: list[ReportDiffCompatibilityCode] = Field(default_factory=list)
    sections: list[ReportSectionDiff] = Field(
        default_factory=list,
        max_length=MAX_REPORT_DIFF_SECTIONS,
    )
    classification_counts: dict[ReportDiffClassification, int] = Field(default_factory=dict)
    excluded_fields: list[str] = Field(default_factory=lambda: list(REPORT_DIFF_EXCLUDED_FIELDS))
    warnings: list[str] = Field(default_factory=lambda: [REPORT_DIFF_WARNING])

    @model_validator(mode="after")
    def validate_status(self) -> StructuredReportDiff:
        if self.status is StructuredReportDiffStatus.AVAILABLE and self.compatibility_codes:
            msg = "available structured report diffs cannot contain compatibility failures"
            raise ValueError(msg)
        if self.status is StructuredReportDiffStatus.UNAVAILABLE and not self.compatibility_codes:
            msg = "unavailable structured report diffs require a compatibility code"
            raise ValueError(msg)
        return self

    def fingerprint(self) -> str:
        """Return a deterministic identity for the complete diff result."""

        return _sha256(self.model_dump(mode="json"))


class ReportDiffContract(BaseModel):
    """Machine-readable REP-03 comparison boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = REPORT_DIFF_SCHEMA_VERSION
    contract_version: Literal["structured-report-diff-v1"] = REPORT_DIFF_CONTRACT_VERSION
    supported_report_types: list[ResearchReportType]
    supported_payload_schema_versions: list[str]
    classifications: list[ReportDiffClassification]
    compatibility_codes: list[ReportDiffCompatibilityCode]
    excluded_fields: list[str]
    maximum_input_bytes: int = MAX_REPORT_DIFF_INPUT_BYTES
    maximum_sections: int = MAX_REPORT_DIFF_SECTIONS
    maximum_claims: int = MAX_REPORT_DIFF_CLAIMS
    maximum_field_changes: int = MAX_REPORT_DIFF_FIELD_CHANGES
    compares_rendered_prose: Literal[False] = False
    compares_analyst_annotations: Literal[False] = False
    causal_interpretation_supported: Literal[False] = False

    def fingerprint(self) -> str:
        """Return the deterministic contract fingerprint."""

        return _sha256(self.model_dump(mode="json"))


@dataclass(frozen=True)
class _ReportInventory:
    sections: list[str]
    snapshots_by_section: dict[str, dict[str, ReportClaimSnapshot]]
    complete: bool
    fingerprint: str


def report_diff_contract() -> ReportDiffContract:
    """Return the closed v1.0 structured report diff contract."""

    return ReportDiffContract(
        supported_report_types=[
            ResearchReportType.RUN,
            ResearchReportType.DIAGNOSTICS,
            ResearchReportType.COMPARISON,
            ResearchReportType.FULL,
        ],
        supported_payload_schema_versions=["1.0"],
        classifications=list(ReportDiffClassification),
        compatibility_codes=list(ReportDiffCompatibilityCode),
        excluded_fields=list(REPORT_DIFF_EXCLUDED_FIELDS),
    )


def parse_research_report_json(payload: str | bytes) -> ResearchReport:
    """Parse one bounded strict structured report JSON payload."""

    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(raw) > MAX_REPORT_DIFF_INPUT_BYTES:
        msg = f"structured report JSON exceeds {MAX_REPORT_DIFF_INPUT_BYTES} bytes"
        raise ReportDiffError(msg)
    try:
        return ResearchReport.model_validate_json(raw)
    except ValidationError as exc:
        msg = f"invalid structured report JSON: {exc}"
        raise ReportDiffError(msg) from exc


def report_scientific_fingerprint(report: ResearchReport) -> str:
    """Fingerprint typed scientific content while excluding prose and annotations."""

    return _build_inventory(report).fingerprint


def compare_structured_reports(
    baseline: ResearchReport,
    variation: ResearchReport,
) -> StructuredReportDiff:
    """Compare compatible reports using only typed claim snapshots and section structure."""

    baseline_inventory = _build_inventory(baseline)
    variation_inventory = _build_inventory(variation)
    compatibility = _compatibility_codes(
        baseline,
        variation,
        baseline_inventory,
        variation_inventory,
    )
    if compatibility:
        return StructuredReportDiff(
            status=StructuredReportDiffStatus.UNAVAILABLE,
            report_type=(
                baseline.report_type if baseline.report_type is variation.report_type else None
            ),
            baseline_report_id=baseline.report_id,
            variation_report_id=variation.report_id,
            baseline_fingerprint=baseline_inventory.fingerprint,
            variation_fingerprint=variation_inventory.fingerprint,
            compatibility_codes=compatibility,
            classification_counts=_empty_counts(),
        )

    sections = _compare_sections(baseline_inventory, variation_inventory)
    counts = _empty_counts()
    for section in sections:
        counts[section.classification] += 1
    return StructuredReportDiff(
        status=StructuredReportDiffStatus.AVAILABLE,
        report_type=baseline.report_type,
        baseline_report_id=baseline.report_id,
        variation_report_id=variation.report_id,
        baseline_fingerprint=baseline_inventory.fingerprint,
        variation_fingerprint=variation_inventory.fingerprint,
        sections=sections,
        classification_counts=counts,
    )


def report_diff_to_markdown(report: StructuredReportDiff) -> str:
    """Render a structured diff without treating presentation text as evidence."""

    lines = [
        "# TrafficTwin Structured Report Diff",
        "",
        f"- Status: `{report.status.value}`",
        f"- Report type: `{report.report_type.value if report.report_type else 'unavailable'}`",
        f"- Baseline report: `{_escape_markdown(report.baseline_report_id)}`",
        f"- Variation report: `{_escape_markdown(report.variation_report_id)}`",
        f"- Baseline scientific fingerprint: `{report.baseline_fingerprint}`",
        f"- Variation scientific fingerprint: `{report.variation_fingerprint}`",
        f"- Diff fingerprint: `{report.fingerprint()}`",
        "",
        f"> {REPORT_DIFF_WARNING}",
        "",
    ]
    if report.compatibility_codes:
        lines.extend(["## Compatibility", ""])
        lines.extend(f"- `{item.value}`" for item in report.compatibility_codes)
        lines.append("")
    if report.sections:
        lines.extend(["## Section Classifications", ""])
        for section in report.sections:
            lines.extend(
                [
                    f"### {_escape_markdown(section.section)}",
                    "",
                    f"- Classification: `{section.classification.value}`",
                    f"- Typed claims: `{len(section.claims)}`",
                ]
            )
            if section.unavailable_reasons:
                reasons = ", ".join(item.value for item in section.unavailable_reasons)
                lines.append(f"- Unavailable reasons: `{reasons}`")
            lines.append("")
            for claim in section.claims:
                lines.extend(
                    [
                        f"#### `{_escape_markdown(claim.scientific_key)}`",
                        "",
                        f"- Classification: `{claim.classification.value}`",
                    ]
                )
                for change in claim.field_changes:
                    lines.append(
                        f"- `{_escape_markdown(change.path)}`: "
                        f"`{_compact_value(change.baseline, change.baseline_present)}` -> "
                        f"`{_compact_value(change.variation, change.variation_present)}`"
                    )
                lines.append("")
    lines.extend(
        [
            "## Excluded From Scientific Diffing",
            "",
            *(f"- `{item}`" for item in report.excluded_fields),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _build_inventory(report: ResearchReport) -> _ReportInventory:
    if len(report.sections) > MAX_REPORT_DIFF_SECTIONS:
        msg = f"report contains more than {MAX_REPORT_DIFF_SECTIONS} sections"
        raise ReportDiffError(msg)
    if len(report.claim_references) > MAX_REPORT_DIFF_CLAIMS:
        msg = f"report contains more than {MAX_REPORT_DIFF_CLAIMS} claim references"
        raise ReportDiffError(msg)
    sections = [title for title, _ in report.sections]
    if any(
        not title
        or len(title) > 256
        or any(ord(character) < 32 or ord(character) == 127 for character in title)
        for title in sections
    ):
        msg = "structured report section titles must be 1 to 256 control-free characters"
        raise ReportDiffError(msg)
    if len(set(sections)) != len(sections):
        msg = "structured report section titles must be unique"
        raise ReportDiffError(msg)

    references = _unique_by_claim_id(report.claim_references, "claim reference")
    snapshots = _unique_by_claim_id(report.claim_snapshots, "claim snapshot")
    reference_keys = [item.scientific_key for item in report.claim_references]
    snapshot_keys = [item.scientific_key for item in report.claim_snapshots]
    if len(set(reference_keys)) != len(reference_keys):
        msg = "structured report claim references contain duplicate scientific keys"
        raise ReportDiffError(msg)
    if len(set(snapshot_keys)) != len(snapshot_keys):
        msg = "structured report claim snapshots contain duplicate scientific keys"
        raise ReportDiffError(msg)
    complete = set(references) == set(snapshots)
    snapshots_by_section: dict[str, dict[str, ReportClaimSnapshot]] = {
        section: {} for section in sections
    }
    scientific_keys: set[str] = set()
    for claim_id in sorted(set(references) & set(snapshots)):
        reference = references[claim_id]
        snapshot = snapshots[claim_id]
        if (
            reference.claim_kind is not snapshot.claim_kind
            or reference.artifact_key != snapshot.artifact_key
            or reference.section != snapshot.section
            or reference.section not in snapshots_by_section
        ):
            complete = False
            continue
        if snapshot.scientific_key in scientific_keys:
            msg = f"duplicate structured report scientific claim: {snapshot.scientific_key}"
            raise ReportDiffError(msg)
        scientific_keys.add(snapshot.scientific_key)
        snapshots_by_section[snapshot.section][snapshot.scientific_key] = snapshot

    fingerprint_payload = {
        "payload_schema_version": report.payload_schema_version,
        "report_type": report.report_type.value,
        "synthetic": report.synthetic,
        "claim_denominator_definition": report.claim_denominator_definition,
        "sections": sections,
        "claims": [
            {
                "scientific_key": snapshot.scientific_key,
                "section": snapshot.section,
                "payload": snapshot.scientific_payload(),
            }
            for snapshot in sorted(report.claim_snapshots, key=lambda item: item.scientific_key)
        ],
    }
    return _ReportInventory(
        sections=sections,
        snapshots_by_section=snapshots_by_section,
        complete=complete,
        fingerprint=_sha256(fingerprint_payload),
    )


def _unique_by_claim_id(
    claims: list[_ClaimType],
    label: str,
) -> dict[str, _ClaimType]:
    result: dict[str, _ClaimType] = {}
    for claim in claims:
        if claim.claim_id in result:
            msg = f"duplicate structured report {label} ID: {claim.claim_id}"
            raise ReportDiffError(msg)
        result[claim.claim_id] = claim
    return result


def _compatibility_codes(
    baseline: ResearchReport,
    variation: ResearchReport,
    baseline_inventory: _ReportInventory,
    variation_inventory: _ReportInventory,
) -> list[ReportDiffCompatibilityCode]:
    codes: list[ReportDiffCompatibilityCode] = []
    if baseline.payload_schema_version != variation.payload_schema_version:
        codes.append(ReportDiffCompatibilityCode.PAYLOAD_SCHEMA_VERSION_MISMATCH)
    if (
        baseline.payload_schema_version
        not in report_diff_contract().supported_payload_schema_versions
        or variation.payload_schema_version
        not in report_diff_contract().supported_payload_schema_versions
    ):
        codes.append(ReportDiffCompatibilityCode.UNSUPPORTED_PAYLOAD_SCHEMA_VERSION)
    if baseline.report_type is not variation.report_type:
        codes.append(ReportDiffCompatibilityCode.REPORT_TYPE_MISMATCH)
    if baseline.synthetic is not variation.synthetic:
        codes.append(ReportDiffCompatibilityCode.SOURCE_MODE_MISMATCH)
    if baseline.claim_denominator_definition != variation.claim_denominator_definition:
        codes.append(ReportDiffCompatibilityCode.CLAIM_DENOMINATOR_MISMATCH)
    if baseline.report_type not in report_diff_contract().supported_report_types:
        codes.append(ReportDiffCompatibilityCode.UNSUPPORTED_REPORT_TYPE)
    if not baseline_inventory.complete or not variation_inventory.complete:
        codes.append(ReportDiffCompatibilityCode.INCOMPLETE_CLAIM_INVENTORY)
    return codes


def _compare_sections(
    baseline: _ReportInventory,
    variation: _ReportInventory,
) -> list[ReportSectionDiff]:
    ordered_sections = list(baseline.sections)
    ordered_sections.extend(
        section for section in variation.sections if section not in baseline.sections
    )
    result: list[ReportSectionDiff] = []
    total_changes = 0
    for section in ordered_sections:
        baseline_present = section in baseline.sections
        variation_present = section in variation.sections
        baseline_claims = baseline.snapshots_by_section.get(section, {})
        variation_claims = variation.snapshots_by_section.get(section, {})
        claim_keys = sorted(set(baseline_claims) | set(variation_claims))
        claim_diffs = [
            _compare_claim(baseline_claims.get(key), variation_claims.get(key))
            for key in claim_keys
        ]
        total_changes += sum(len(item.field_changes) for item in claim_diffs)
        if total_changes > MAX_REPORT_DIFF_FIELD_CHANGES:
            msg = f"structured report diff exceeds {MAX_REPORT_DIFF_FIELD_CHANGES} field changes"
            raise ReportDiffError(msg)
        unavailable_reasons: list[ReportSectionUnavailableReason] = []
        if not baseline_present:
            classification = ReportDiffClassification.ADDED
        elif not variation_present:
            classification = ReportDiffClassification.REMOVED
        elif not claim_diffs:
            classification = ReportDiffClassification.UNAVAILABLE
            unavailable_reasons.append(ReportSectionUnavailableReason.NO_TYPED_CLAIMS)
        elif any(
            item.classification
            in {
                ReportDiffClassification.ADDED,
                ReportDiffClassification.REMOVED,
                ReportDiffClassification.CHANGED,
            }
            for item in claim_diffs
        ):
            classification = ReportDiffClassification.CHANGED
        elif any(
            item.classification is ReportDiffClassification.UNAVAILABLE for item in claim_diffs
        ):
            classification = ReportDiffClassification.UNAVAILABLE
            unavailable_reasons.append(ReportSectionUnavailableReason.TYPED_CLAIM_UNAVAILABLE)
        else:
            classification = ReportDiffClassification.UNCHANGED
        result.append(
            ReportSectionDiff(
                section=section,
                classification=classification,
                baseline_present=baseline_present,
                variation_present=variation_present,
                baseline_fingerprint=_section_fingerprint(baseline_claims, baseline_present),
                variation_fingerprint=_section_fingerprint(variation_claims, variation_present),
                unavailable_reasons=unavailable_reasons,
                claims=claim_diffs,
            )
        )
    return result


def _compare_claim(
    baseline: ReportClaimSnapshot | None,
    variation: ReportClaimSnapshot | None,
) -> ReportClaimDiff:
    snapshot = baseline or variation
    if snapshot is None:  # pragma: no cover - protected by caller union
        raise ReportDiffError("structured claim union unexpectedly contained no claim")
    if baseline is None:
        return ReportClaimDiff(
            scientific_key=snapshot.scientific_key,
            classification=ReportDiffClassification.ADDED,
            variation_claim_id=variation.claim_id if variation else None,
            variation_fingerprint=_snapshot_fingerprint(variation) if variation else None,
        )
    if variation is None:
        return ReportClaimDiff(
            scientific_key=snapshot.scientific_key,
            classification=ReportDiffClassification.REMOVED,
            baseline_claim_id=baseline.claim_id,
            baseline_fingerprint=_snapshot_fingerprint(baseline),
        )
    changes: list[ReportFieldChange] = []
    _diff_values("", baseline.scientific_payload(), variation.scientific_payload(), changes)
    if (
        baseline.availability is ReportClaimAvailability.UNAVAILABLE
        or variation.availability is ReportClaimAvailability.UNAVAILABLE
    ):
        classification = ReportDiffClassification.UNAVAILABLE
    elif changes:
        classification = ReportDiffClassification.CHANGED
    else:
        classification = ReportDiffClassification.UNCHANGED
    return ReportClaimDiff(
        scientific_key=baseline.scientific_key,
        classification=classification,
        baseline_claim_id=baseline.claim_id,
        variation_claim_id=variation.claim_id,
        baseline_fingerprint=_snapshot_fingerprint(baseline),
        variation_fingerprint=_snapshot_fingerprint(variation),
        field_changes=changes,
    )


def _diff_values(
    path: str,
    baseline: object,
    variation: object,
    changes: list[ReportFieldChange],
) -> None:
    if isinstance(baseline, dict) and isinstance(variation, dict):
        for key in sorted(set(baseline) | set(variation)):
            child = f"{path}/{_json_pointer_token(key)}"
            baseline_present = key in baseline
            variation_present = key in variation
            if baseline_present and variation_present:
                _diff_values(child, baseline[key], variation[key], changes)
            else:
                changes.append(
                    ReportFieldChange(
                        path=child,
                        baseline_present=baseline_present,
                        variation_present=variation_present,
                        baseline=baseline.get(key),
                        variation=variation.get(key),
                    )
                )
        return
    if isinstance(baseline, list) and isinstance(variation, list):
        for index in range(max(len(baseline), len(variation))):
            child = f"{path}/{index}"
            baseline_present = index < len(baseline)
            variation_present = index < len(variation)
            if baseline_present and variation_present:
                _diff_values(child, baseline[index], variation[index], changes)
            else:
                changes.append(
                    ReportFieldChange(
                        path=child,
                        baseline_present=baseline_present,
                        variation_present=variation_present,
                        baseline=baseline[index] if baseline_present else None,
                        variation=variation[index] if variation_present else None,
                    )
                )
        return
    if baseline != variation or type(baseline) is not type(variation):
        changes.append(
            ReportFieldChange(
                path=path or "/",
                baseline_present=True,
                variation_present=True,
                baseline=baseline,
                variation=variation,
            )
        )


def _section_fingerprint(
    claims: dict[str, ReportClaimSnapshot],
    present: bool,
) -> str | None:
    if not present:
        return None
    return _sha256(
        [
            {
                "scientific_key": key,
                "payload": claims[key].scientific_payload(),
            }
            for key in sorted(claims)
        ]
    )


def _snapshot_fingerprint(snapshot: ReportClaimSnapshot) -> str:
    return _sha256(snapshot.scientific_payload())


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        msg = f"structured report content is not canonical JSON: {exc}"
        raise ReportDiffError(msg) from exc


def _empty_counts() -> dict[ReportDiffClassification, int]:
    return dict.fromkeys(ReportDiffClassification, 0)


def _json_pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _escape_markdown(value: str) -> str:
    escaped = value.replace("\r", " ").replace("\n", " ").replace("\\", "\\\\")
    for character in "`*_{}[]()<>#+-.!|":
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _compact_value(value: object, present: bool) -> str:
    if not present:
        return "<missing>"
    rendered = _canonical_json(value).replace("`", "\\`")
    if len(rendered) <= 240:
        return rendered
    return rendered[:220] + "... [truncated; use JSON export]"
