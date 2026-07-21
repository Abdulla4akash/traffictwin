"""Append-only analyst annotation contracts for typed TrafficTwin artifacts."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ANNOTATION_SCHEMA_VERSION: Literal["1.0"] = "1.0"
ANNOTATION_CONTRACT_VERSION = "analyst-annotations-v1"
MAX_ANNOTATION_NOTE_CHARACTERS = 4_000
MAX_ANNOTATION_AUTHOR_CHARACTERS = 120
MAX_ANNOTATION_TARGET_ID_CHARACTERS = 256
MAX_ANNOTATIONS_PER_PAGE = 500
MAX_ANNOTATIONS_PER_REPORT = 500


class AnalystAnnotationTargetKind(StrEnum):
    """Closed typed-artifact target catalogue for REP-02 v1.0."""

    EXPERIMENT = "experiment"
    RUN = "run"
    BUNDLE_IMPORT = "bundle_import"
    METRIC_COLLECTION = "metric_collection"
    EVIDENCE_PACK = "evidence_pack"
    EXPERIMENT_EVIDENCE_PACK = "experiment_evidence_pack"
    EXPERIMENT_PROTOCOL = "experiment_protocol"
    DIAGNOSTIC_REPORT = "diagnostic_report"
    COMPARISON_REPORT = "comparison_report"
    STATISTICAL_STUDY = "statistical_study"
    RESEARCH_REPORT = "research_report"


class AnalystDecisionLabel(StrEnum):
    """Human-authored annotation classification; never a computed outcome."""

    OBSERVATION = "observation"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    FOLLOW_UP = "follow_up"


class AnalystArtifactReference(BaseModel):
    """Path-free typed reference to an artifact that may be annotated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AnalystAnnotationTargetKind
    artifact_id: str = Field(
        min_length=1,
        max_length=MAX_ANNOTATION_TARGET_ID_CHARACTERS,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:@+\-]*$",
    )
    artifact_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    @property
    def key(self) -> str:
        """Return a stable, path-free display and comparison key."""

        suffix = f"@{self.artifact_fingerprint}" if self.artifact_fingerprint else ""
        return f"{self.kind.value}:{self.artifact_id}{suffix}"


class AnalystAnnotationRequest(BaseModel):
    """Validated analyst-authored content before append-only registration."""

    model_config = ConfigDict(extra="forbid")

    target: AnalystArtifactReference
    author_label: str = Field(min_length=1, max_length=MAX_ANNOTATION_AUTHOR_CHARACTERS)
    note: str = Field(min_length=1, max_length=MAX_ANNOTATION_NOTE_CHARACTERS)
    decision_label: AnalystDecisionLabel = AnalystDecisionLabel.OBSERVATION

    @field_validator("author_label")
    @classmethod
    def validate_author_label(cls, value: str) -> str:
        """Reject blank or control-bearing author labels without rewriting them."""

        if not value.strip():
            raise ValueError("author_label must contain visible text")
        if any(unicodedata.category(character) == "Cc" for character in value):
            raise ValueError("author_label cannot contain control characters")
        return value

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        """Admit multiline notes but reject blank and unsafe control content."""

        if not value.strip():
            raise ValueError("note must contain visible text")
        unsupported_controls = [
            character
            for character in value
            if unicodedata.category(character) == "Cc" and character not in {"\n", "\t"}
        ]
        if unsupported_controls:
            raise ValueError("note cannot contain unsupported control characters")
        return value


class AnalystAnnotation(BaseModel):
    """One immutable, ordered analyst-authored registry record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = ANNOTATION_SCHEMA_VERSION
    sequence: int = Field(ge=1)
    annotation_id: str = Field(pattern=r"^annotation-[0-9a-f]{24}$")
    target: AnalystArtifactReference
    author_label: str = Field(min_length=1, max_length=MAX_ANNOTATION_AUTHOR_CHARACTERS)
    note: str = Field(min_length=1, max_length=MAX_ANNOTATION_NOTE_CHARACTERS)
    decision_label: AnalystDecisionLabel
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Store a canonical UTC timestamp for stable history ordering."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def verify_content_identity(self) -> AnalystAnnotation:
        """Detect payload/identifier drift when records are read back."""

        AnalystAnnotationRequest(
            target=self.target,
            author_label=self.author_label,
            note=self.note,
            decision_label=self.decision_label,
        )
        expected = analyst_annotation_id(
            target=self.target,
            author_label=self.author_label,
            note=self.note,
            decision_label=self.decision_label,
            created_at=self.created_at,
        )
        if self.annotation_id != expected:
            raise ValueError("annotation_id does not match immutable annotation content")
        return self


class AnalystAnnotationHistory(BaseModel):
    """One bounded ordered page from the append-only annotation stream."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = ANNOTATION_SCHEMA_VERSION
    target: AnalystArtifactReference | None = None
    after_sequence: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=MAX_ANNOTATIONS_PER_PAGE)
    annotations: list[AnalystAnnotation] = Field(default_factory=list)
    has_more: bool = False

    @model_validator(mode="after")
    def verify_order_and_scope(self) -> AnalystAnnotationHistory:
        """Require strictly ordered unique history with an exact target scope."""

        sequences = [item.sequence for item in self.annotations]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("annotation history must be strictly ordered by unique sequence")
        annotation_ids = [item.annotation_id for item in self.annotations]
        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError("annotation history must contain unique annotation identifiers")
        if any(sequence <= self.after_sequence for sequence in sequences):
            raise ValueError("annotation history contains a sequence outside the requested page")
        if self.target is not None and any(
            not annotation_target_matches(item.target, self.target) for item in self.annotations
        ):
            raise ValueError("annotation history contains an unrelated target")
        return self

    def fingerprint(self) -> str:
        """Return the exact ordered history-page fingerprint."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AnalystAnnotationContract(BaseModel):
    """Public REP-02 storage, identity, and evidence-separation contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = ANNOTATION_SCHEMA_VERSION
    contract_version: str = ANNOTATION_CONTRACT_VERSION
    supported_target_kinds: list[AnalystAnnotationTargetKind]
    decision_labels: list[AnalystDecisionLabel]
    registry_verified_target_kinds: list[AnalystAnnotationTargetKind]
    maximum_author_characters: int
    maximum_note_characters: int
    maximum_target_id_characters: int
    maximum_page_records: int
    maximum_report_records: int
    ordering_policy: str
    identity_policy: str
    immutability_policy: str
    target_policy: str
    report_policy: str
    scientific_boundary: str

    def fingerprint(self) -> str:
        """Return the stable public contract identity."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


REGISTRY_VERIFIED_ANNOTATION_TARGETS = (
    AnalystAnnotationTargetKind.EXPERIMENT,
    AnalystAnnotationTargetKind.RUN,
    AnalystAnnotationTargetKind.BUNDLE_IMPORT,
    AnalystAnnotationTargetKind.METRIC_COLLECTION,
    AnalystAnnotationTargetKind.EVIDENCE_PACK,
    AnalystAnnotationTargetKind.EXPERIMENT_EVIDENCE_PACK,
    AnalystAnnotationTargetKind.EXPERIMENT_PROTOCOL,
)


def analyst_annotation_contract() -> AnalystAnnotationContract:
    """Return the fixed REP-02 v1.0 contract."""

    return AnalystAnnotationContract(
        supported_target_kinds=list(AnalystAnnotationTargetKind),
        decision_labels=list(AnalystDecisionLabel),
        registry_verified_target_kinds=list(REGISTRY_VERIFIED_ANNOTATION_TARGETS),
        maximum_author_characters=MAX_ANNOTATION_AUTHOR_CHARACTERS,
        maximum_note_characters=MAX_ANNOTATION_NOTE_CHARACTERS,
        maximum_target_id_characters=MAX_ANNOTATION_TARGET_ID_CHARACTERS,
        maximum_page_records=MAX_ANNOTATIONS_PER_PAGE,
        maximum_report_records=MAX_ANNOTATIONS_PER_REPORT,
        ordering_policy=(
            "SQLite-assigned monotonic sequence; reads are ascending and bounded with explicit "
            "pagination."
        ),
        identity_policy=(
            "annotation_id binds the exact target, author label, note, decision label, and UTC "
            "creation timestamp."
        ),
        immutability_policy=(
            "The public API exposes append/read only; SQLite triggers reject UPDATE and DELETE."
        ),
        target_policy=(
            "Registry-resident target kinds must exist before append. Generated report/study "
            "references are explicit detached typed references and do not prove artifact storage."
        ),
        report_policy=(
            "Matching history is rendered in a dedicated analyst-authored non-computed section; "
            "it never enters computed sections or the scientific claim denominator."
        ),
        scientific_boundary=(
            "Annotations cannot change metrics, rules, statistics, fingerprints, provenance, "
            "availability, or computed findings and are not recommendations from TrafficTwin."
        ),
    )


def analyst_annotation_id(
    *,
    target: AnalystArtifactReference,
    author_label: str,
    note: str,
    decision_label: AnalystDecisionLabel,
    created_at: datetime,
) -> str:
    """Derive an immutable annotation identifier from exact authored content."""

    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    payload = {
        "author_label": author_label,
        "created_at": created_at.astimezone(UTC).isoformat(),
        "decision_label": decision_label.value,
        "note": note,
        "target": target.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"annotation-{digest}"


def build_analyst_annotation(
    request: AnalystAnnotationRequest,
    *,
    sequence: int,
    created_at: datetime,
) -> AnalystAnnotation:
    """Build one validated immutable annotation after sequence allocation."""

    timestamp = created_at.astimezone(UTC) if created_at.tzinfo is not None else created_at
    return AnalystAnnotation(
        sequence=sequence,
        annotation_id=analyst_annotation_id(
            target=request.target,
            author_label=request.author_label,
            note=request.note,
            decision_label=request.decision_label,
            created_at=timestamp,
        ),
        target=request.target,
        author_label=request.author_label,
        note=request.note,
        decision_label=request.decision_label,
        created_at=timestamp,
    )


def annotation_target_matches(
    annotation_target: AnalystArtifactReference,
    requested_target: AnalystArtifactReference,
) -> bool:
    """Match identity plus unbound-or-exact fingerprint scope."""

    if (
        annotation_target.kind is not requested_target.kind
        or annotation_target.artifact_id != requested_target.artifact_id
    ):
        return False
    return annotation_target.artifact_fingerprint in {
        None,
        requested_target.artifact_fingerprint,
    }
