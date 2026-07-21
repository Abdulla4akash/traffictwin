"""Deterministic, confirmation-gated CSV manifest inference."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from traffictwin.adapters.generic_csv import (
    SUPPORTED_FIELDS,
    UNIT_DIMENSIONS,
    supported_units_for_field,
)
from traffictwin.ingestion.hashes import bundle_fingerprint, sha256_file
from traffictwin.ingestion.manifest import (
    BundleManifest,
    CanonicalisationEvidence,
    FileDeclaration,
    canonicalisation_confirmation_fingerprint,
)
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.findings import Severity, ValidationFinding

INFERENCE_SCHEMA_VERSION = "1.0"
INFERENCE_VERSION = "1.0"
MAX_INFERENCE_FILES = 32
MAX_INFERENCE_COLUMNS = 128
MAX_INFERENCE_SAMPLE_ROWS = 100
MAX_INFERENCE_VALUE_CHARACTERS = 256

FILE_KINDS = tuple(SUPPORTED_FIELDS)
ModelT = TypeVar("ModelT", bound=BaseModel)
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "tasks": (
        "task_id",
        "vehicle_id",
        "task_class",
        "arrival_time",
        "deadline_ms",
        "decision",
        "completed",
    ),
    "infra_state": ("timestamp", "rsu_id"),
    "vehicle_state": ("timestamp", "vehicle_id"),
    "traffic_obs": ("timestamp", "sensor_id"),
    "trips": ("trip_id", "departure_time"),
    "incidents": ("incident_id", "timestamp", "incident_type"),
}

ALIASES: dict[str, dict[str, set[str]]] = {
    "tasks": {
        "task_id": {"taskid", "job_id", "request_id"},
        "vehicle_id": {"vehicleid", "veh_id", "car_id"},
        "task_class": {"class", "job_class", "workload_class", "service_class"},
        "arrival_time": {
            "arrival",
            "arrival_ts",
            "arrival_time_s",
            "arrival_time_seconds",
            "generated_at",
            "generation_time",
            "release_time",
        },
        "deadline_ms": {"deadline", "deadline_milliseconds", "latency_budget_ms"},
        "decision": {"action", "offload_action", "offload_decision", "placement"},
        "completed": {"success", "is_completed", "completion_status"},
        "completion_time": {
            "finish_time",
            "finish_time_s",
            "finish_time_seconds",
            "finished_at",
            "completion_time_s",
        },
        "latency_ms": {"delay_ms", "response_time_ms", "latency_milliseconds"},
        "target_id": {"target", "destination_id", "server_id"},
        "workload_cycles": {"cycles", "cpu_cycles"},
        "data_size_bytes": {"payload_bytes", "input_bytes", "data_bytes"},
        "energy_j": {"energy", "energy_joules"},
        "drop_reason": {"failure_reason", "reason"},
    },
    "infra_state": {
        "timestamp": {"time", "time_s", "time_seconds", "timestamp_s"},
        "rsu_id": {"rsu", "roadside_unit_id", "entity_id"},
        "queue_length": {"queue", "backlog", "queue_size"},
        "utilisation": {"utilization", "utilisation_fraction", "utilization_fraction"},
        "arrivals": {"arrival_count"},
        "active_tasks": {"active", "running_tasks"},
        "drops": {"dropped", "drop_count"},
        "capacity": {"service_capacity"},
    },
    "vehicle_state": {
        "timestamp": {"time", "time_s", "time_seconds", "timestamp_s"},
        "vehicle_id": {"vehicle", "veh_id", "car_id", "entity_id"},
        "x": {"x_position", "position_x"},
        "y": {"y_position", "position_y"},
        "speed": {"speed_mps", "speed_kmh", "velocity"},
        "lane": {"lane_id"},
        "tier": {"vehicle_tier", "class_tier"},
    },
    "traffic_obs": {
        "timestamp": {"time", "time_s", "time_seconds", "timestamp_s"},
        "sensor_id": {"sensor", "detector_id", "counter_id", "entity_id"},
        "count": {"vehicle_count", "flow_count", "volume"},
        "average_speed": {"avg_speed", "mean_speed", "mean_speed_kmh", "mean_speed_mps"},
        "location": {"site", "sensor_location"},
    },
    "trips": {
        "trip_id": {"trip", "journey_id"},
        "vehicle_id": {"vehicle", "veh_id", "car_id"},
        "departure_time": {
            "depart",
            "departure",
            "depart_time",
            "departure_time_s",
            "departure_time_seconds",
        },
        "arrival_time": {"arrival", "arrive", "arrival_time_s", "arrival_time_seconds"},
        "duration": {"travel_time", "duration_s", "duration_seconds"},
        "route_id": {"route", "path_id"},
    },
    "incidents": {
        "incident_id": {"event_id", "incident"},
        "timestamp": {"time", "time_s", "time_seconds", "timestamp_s"},
        "incident_type": {"event_type", "incident_category"},
        "location": {"site", "incident_location"},
        "severity": {"level", "severity_level"},
        "duration": {"duration_s", "duration_seconds"},
        "lanes_closed": {"closed_lanes", "lane_closures"},
        "demand_multiplier": {"demand_factor"},
        "vehicles_involved": {"vehicle_ids", "involved_vehicles"},
    },
}


class InferenceModel(BaseModel):
    """Strict base model for inference artifacts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class InferenceMethod(StrEnum):
    """Deterministic evidence used for a candidate mapping."""

    EXACT_HEADER = "exact_header"
    HEADER_ALIAS = "header_alias"
    VALUE_PATTERN = "value_pattern"


class SuggestionStatus(StrEnum):
    """Resolution state of a file or field suggestion."""

    SUGGESTED = "suggested"
    AMBIGUOUS = "ambiguous"
    UNMAPPED = "unmapped"


class ConfirmationMode(StrEnum):
    """How a user confirmed a mapping draft."""

    ACCEPTED_SUGGESTIONS = "accepted_suggestions"
    EDITED = "edited"


class ColumnCandidate(InferenceModel):
    """One candidate source column for a canonical field."""

    source_column: str
    precedence: int = Field(ge=0)
    methods: list[InferenceMethod]


class FieldSuggestion(InferenceModel):
    """Deterministic candidates for one canonical field."""

    canonical_field: str
    required: bool
    status: SuggestionStatus
    suggested_source_column: str | None = None
    candidates: list[ColumnCandidate] = Field(default_factory=list)
    unit_dimension: str | None = None
    suggested_unit: str | None = None
    supported_units: list[str] = Field(default_factory=list)


class FileKindCandidate(InferenceModel):
    """Mapping evidence for treating a CSV as one supported file kind."""

    kind: str
    eligible: bool
    score: int = Field(ge=0)
    required_fields: list[str]
    required_fields_mapped: list[str]
    fields: list[FieldSuggestion]

    def by_field(self) -> dict[str, FieldSuggestion]:
        """Index field suggestions by canonical name."""

        return {field.canonical_field: field for field in self.fields}


class CsvFileInference(InferenceModel):
    """Bounded profile and candidate mappings for one immutable CSV file."""

    path: str
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    headers: list[str]
    sampled_rows: int = Field(ge=0)
    status: SuggestionStatus
    suggested_kind: str | None = None
    kind_candidates: list[FileKindCandidate]

    def by_kind(self) -> dict[str, FileKindCandidate]:
        """Index candidates by supported file kind."""

        return {candidate.kind: candidate for candidate in self.kind_candidates}


class InferenceLimits(InferenceModel):
    """Published bounds used by the inference algorithm."""

    max_files: int = MAX_INFERENCE_FILES
    max_columns_per_file: int = MAX_INFERENCE_COLUMNS
    max_sample_rows_per_file: int = MAX_INFERENCE_SAMPLE_ROWS
    max_value_characters: int = MAX_INFERENCE_VALUE_CHARACTERS


class InferenceMethodDefinition(InferenceModel):
    """Published meaning and precedence of one inference method."""

    method: InferenceMethod
    precedence: int = Field(ge=0)
    meaning: str


class ManifestInferenceContract(InferenceModel):
    """Machine-readable boundary of the deterministic inference algorithm."""

    schema_version: Literal["1.0"] = "1.0"
    inference_version: str = INFERENCE_VERSION
    limits: InferenceLimits = Field(default_factory=InferenceLimits)
    methods: list[InferenceMethodDefinition]
    required_fields: dict[str, list[str]]
    supported_fields: dict[str, list[str]]
    aliases: dict[str, dict[str, list[str]]]
    distinctive_value_patterns: dict[str, list[str]]
    score_semantics: str
    unit_policy: str
    confirmation_policy: str
    unsupported: list[str]

    def to_json(self) -> str:
        """Return stable formatted JSON."""

        return self.model_dump_json(indent=2)

    def to_yaml(self) -> str:
        """Return stable formatted YAML."""

        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False)


class ManifestInferenceDraft(InferenceModel):
    """Non-executable mapping suggestions that always require confirmation."""

    schema_version: Literal["1.0"] = "1.0"
    inference_version: str = INFERENCE_VERSION
    source_fingerprint: str | None = None
    draft_fingerprint: str | None = None
    source_label: str
    limits: InferenceLimits = Field(default_factory=InferenceLimits)
    files: list[CsvFileInference] = Field(default_factory=list)
    findings: list[ValidationFinding] = Field(default_factory=list)
    confirmation_required: Literal[True] = True
    analysis_ready: Literal[False] = False

    @model_validator(mode="after")
    def validate_draft_fingerprint(self) -> ManifestInferenceDraft:
        if self.draft_fingerprint is not None and self.draft_fingerprint != _draft_fingerprint(
            self
        ):
            raise ValueError("draft fingerprint does not match inference content")
        return self

    def to_json(self) -> str:
        """Return stable formatted JSON."""

        return self.model_dump_json(indent=2)

    def to_yaml(self) -> str:
        """Return stable YAML without local absolute paths."""

        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False)


class FileSelection(InferenceModel):
    """User-selected treatment for one inferred CSV file."""

    include: bool = True
    kind: str | None = None
    column_map: dict[str, str] = Field(default_factory=dict)
    unmapped_fields: list[str] = Field(default_factory=list)
    units: dict[str, str] = Field(default_factory=dict)


class ManifestInferenceSelections(InferenceModel):
    """Explicit edits or exclusions applied while confirming a draft."""

    files: dict[str, FileSelection] = Field(default_factory=dict)


class ConfirmedFileMapping(InferenceModel):
    """One explicitly confirmed CSV-to-canonical mapping."""

    path: str
    kind: str
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_columns: list[str]
    column_map: dict[str, str]
    units: dict[str, str] = Field(default_factory=dict)


class CanonicalisationManifest(InferenceModel):
    """Executable mapping contract created only by explicit confirmation."""

    schema_version: Literal["1.0"] = "1.0"
    inference_version: str = INFERENCE_VERSION
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_state: ConfirmationMode
    confirmed_by: str = Field(min_length=1)
    mappings: list[ConfirmedFileMapping]
    excluded_files: list[str] = Field(default_factory=list)
    analysis_ready: Literal[True] = True

    @model_validator(mode="after")
    def validate_unique_kinds(self) -> CanonicalisationManifest:
        kinds = [mapping.kind for mapping in self.mappings]
        if len(kinds) != len(set(kinds)):
            raise ValueError("only one CSV file may be confirmed for each manifest file kind")
        expected = canonicalisation_confirmation_fingerprint(
            inference_version=self.inference_version,
            source_fingerprint=self.source_fingerprint,
            draft_fingerprint=self.draft_fingerprint,
            confirmation_state=self.confirmation_state.value,
            confirmed_by=self.confirmed_by,
            mappings=[mapping.model_dump(mode="json") for mapping in self.mappings],
            excluded_files=self.excluded_files,
        )
        if self.confirmation_fingerprint != expected:
            raise ValueError("confirmation fingerprint does not match selected mappings")
        return self

    def to_json(self) -> str:
        """Return stable formatted JSON."""

        return self.model_dump_json(indent=2)

    def to_yaml(self) -> str:
        """Return stable YAML without local absolute paths."""

        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False)

    def file_declarations(self) -> dict[str, FileDeclaration]:
        """Convert confirmed mappings into ordinary bundle file declarations."""

        return {
            mapping.kind: FileDeclaration(
                path=mapping.path,
                required_columns=mapping.required_columns,
                column_map=mapping.column_map,
                units=mapping.units,
                checksum_sha256=mapping.checksum_sha256,
                required=True,
            )
            for mapping in self.mappings
        }


class ManifestInferenceError(ValueError):
    """Raised when a draft cannot be inferred, confirmed, or applied safely."""


def manifest_inference_contract() -> ManifestInferenceContract:
    """Return the versioned inference methods, catalogue, bounds, and safety policy."""

    return ManifestInferenceContract(
        methods=[
            InferenceMethodDefinition(
                method=InferenceMethod.EXACT_HEADER,
                precedence=_method_precedence(InferenceMethod.EXACT_HEADER),
                meaning="normalised source header equals the canonical field",
            ),
            InferenceMethodDefinition(
                method=InferenceMethod.HEADER_ALIAS,
                precedence=_method_precedence(InferenceMethod.HEADER_ALIAS),
                meaning="normalised source header is in the documented field alias catalogue",
            ),
            InferenceMethodDefinition(
                method=InferenceMethod.VALUE_PATTERN,
                precedence=_method_precedence(InferenceMethod.VALUE_PATTERN),
                meaning="all sampled non-empty values fit one distinctive closed vocabulary",
            ),
        ],
        required_fields={kind: list(fields) for kind, fields in REQUIRED_FIELDS.items()},
        supported_fields={kind: sorted(fields) for kind, fields in SUPPORTED_FIELDS.items()},
        aliases={
            kind: {field: sorted(values) for field, values in sorted(fields.items())}
            for kind, fields in ALIASES.items()
        },
        distinctive_value_patterns={
            "task_class": ["t1", "t2", "t3"],
            "decision": ["local", "v2i", "v2v"],
            "completed": ["true", "false", "yes", "no", "1", "0"],
        },
        score_semantics=(
            "sum of selected field-method precedences used only for deterministic ordering; "
            "not a probability or confidence"
        ),
        unit_policy=(
            "suggest only from a supported explicit header suffix/word; otherwise require user "
            "selection"
        ),
        confirmation_policy=(
            "drafts are analysis_ready=false; source fingerprint recheck and explicit acceptance "
            "or edit are required"
        ),
        unsupported=[
            "unit inference from numeric magnitude",
            "bundle/run/environment/provenance metadata inference",
            "automatic resolution of tied file kinds or fields",
            "analysis or import of an inference draft",
            "more than one CSV per current canonical file kind",
            "Parquet, gzip, batch, and streaming admission",
        ],
    )


def infer_manifest(source: str | Path) -> ManifestInferenceDraft:
    """Inspect bounded CSV headers/samples and return non-executable suggestions."""

    root = Path(source).resolve()
    findings: list[ValidationFinding] = []
    if not root.is_dir():
        return _failed_draft(
            root.name or "source",
            ValidationCode.MANIFEST_INFERENCE_SOURCE_INVALID,
            "manifest inference source must be a readable directory",
        )
    paths = sorted(
        (path for path in root.rglob("*.csv") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not paths:
        return _failed_draft(
            root.name,
            ValidationCode.MANIFEST_INFERENCE_NO_CSV,
            "manifest inference source contains no CSV files",
        )
    if len(paths) > MAX_INFERENCE_FILES:
        return _failed_draft(
            root.name,
            ValidationCode.MANIFEST_INFERENCE_LIMIT_EXCEEDED,
            f"manifest inference accepts at most {MAX_INFERENCE_FILES} CSV files",
        )

    file_results: list[CsvFileInference] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not _stays_within_root(path, root):
            findings.append(
                _finding(
                    ValidationCode.MANIFEST_INFERENCE_SOURCE_INVALID,
                    Severity.ERROR,
                    "CSV symlinks or paths outside the source directory are not accepted",
                    file=relative,
                    may_continue=False,
                )
            )
            continue
        try:
            headers, columns, sampled_rows = _sample_csv(path)
        except (OSError, UnicodeError, csv.Error, ManifestInferenceError) as exc:
            findings.append(
                _finding(
                    ValidationCode.MANIFEST_INFERENCE_CSV_INVALID,
                    Severity.ERROR,
                    f"CSV could not be profiled: {exc}",
                    file=relative,
                    may_continue=False,
                )
            )
            continue
        file_result = _infer_file(relative, sha256_file(path), headers, columns, sampled_rows)
        file_results.append(file_result)
        if file_result.status is SuggestionStatus.AMBIGUOUS:
            findings.append(
                _finding(
                    ValidationCode.MANIFEST_INFERENCE_FILE_AMBIGUOUS,
                    Severity.WARNING,
                    "multiple file kinds have equally supported mappings; select one explicitly",
                    file=relative,
                    value=[
                        candidate.kind
                        for candidate in file_result.kind_candidates
                        if candidate.eligible
                        and candidate.score
                        == max(item.score for item in file_result.kind_candidates if item.eligible)
                    ],
                    may_continue=False,
                )
            )
        elif file_result.status is SuggestionStatus.UNMAPPED:
            findings.append(
                _finding(
                    ValidationCode.MANIFEST_INFERENCE_FILE_UNRESOLVED,
                    Severity.WARNING,
                    "no file kind has all required fields; edit or exclude this file",
                    file=relative,
                    may_continue=False,
                )
            )
            best_candidate = max(
                file_result.kind_candidates,
                key=lambda candidate: (candidate.score, candidate.kind),
            )
            for field in best_candidate.fields:
                if not field.required or field.status is SuggestionStatus.SUGGESTED:
                    continue
                code = (
                    ValidationCode.MANIFEST_INFERENCE_FIELD_AMBIGUOUS
                    if field.status is SuggestionStatus.AMBIGUOUS
                    else ValidationCode.MANIFEST_INFERENCE_FIELD_UNMAPPED
                )
                findings.append(
                    _finding(
                        code,
                        Severity.WARNING,
                        f"required {best_candidate.kind} field needs an explicit mapping: "
                        f"{field.canonical_field}",
                        file=relative,
                        field=field.canonical_field,
                        value=[candidate.source_column for candidate in field.candidates],
                        may_continue=False,
                    )
                )
    findings.append(
        _finding(
            ValidationCode.MANIFEST_INFERENCE_CONFIRMATION_REQUIRED,
            Severity.INFO,
            "inference output is a draft and cannot enter analysis until explicitly confirmed",
            may_continue=False,
            affected_capabilities=["manifest_inference"],
        )
    )
    fingerprint_paths = [root / file.path for file in file_results]
    source_fingerprint = bundle_fingerprint(fingerprint_paths, root)
    draft = ManifestInferenceDraft(
        source_fingerprint=source_fingerprint,
        source_label=root.name,
        files=file_results,
        findings=findings,
    )
    return draft.model_copy(update={"draft_fingerprint": _draft_fingerprint(draft)})


def confirm_manifest_inference(
    draft: ManifestInferenceDraft,
    source: str | Path,
    *,
    confirmed_by: str,
    accept_suggestions: bool = False,
    selections: ManifestInferenceSelections | None = None,
) -> CanonicalisationManifest:
    """Create an executable mapping artifact after explicit acceptance or edits."""

    if not confirmed_by.strip():
        raise ManifestInferenceError("confirmed_by must identify the confirming analyst or role")
    if not accept_suggestions and (selections is None or not selections.files):
        raise ManifestInferenceError(
            "explicit confirmation is required: accept suggestions or provide mapping edits"
        )
    if draft.source_fingerprint is None or draft.draft_fingerprint is None:
        raise ManifestInferenceError("the inference draft has no valid source fingerprint")
    if draft.inference_version != INFERENCE_VERSION:
        raise ManifestInferenceError(
            f"unsupported inference version: {draft.inference_version}; "
            f"expected {INFERENCE_VERSION}"
        )
    blocking_codes = {
        ValidationCode.MANIFEST_INFERENCE_SOURCE_INVALID,
        ValidationCode.MANIFEST_INFERENCE_NO_CSV,
        ValidationCode.MANIFEST_INFERENCE_LIMIT_EXCEEDED,
        ValidationCode.MANIFEST_INFERENCE_CSV_INVALID,
    }
    blocking = [finding for finding in draft.findings if finding.code in blocking_codes]
    if blocking:
        raise ManifestInferenceError(
            "inference source errors must be fixed before confirmation: "
            + ", ".join(finding.code.value for finding in blocking)
        )
    current = infer_manifest(source)
    if current.source_fingerprint != draft.source_fingerprint:
        raise ManifestInferenceError(
            f"{ValidationCode.MANIFEST_INFERENCE_STALE_SOURCE.value}: source CSV files changed"
        )
    if current.draft_fingerprint != draft.draft_fingerprint:
        raise ManifestInferenceError(
            f"{ValidationCode.MANIFEST_INFERENCE_STALE_SOURCE.value}: inference draft no longer "
            "matches the current algorithm output"
        )
    selection_map = selections.files if selections is not None else {}
    known_paths = {file.path for file in draft.files}
    unknown_selections = sorted(set(selection_map) - known_paths)
    if unknown_selections:
        raise ManifestInferenceError(f"unknown selected CSV paths: {', '.join(unknown_selections)}")

    mappings: list[ConfirmedFileMapping] = []
    excluded: list[str] = []
    edited = False
    for file in draft.files:
        selection = selection_map.get(file.path, FileSelection())
        if not selection.include:
            excluded.append(file.path)
            edited = True
            continue
        kind = selection.kind or file.suggested_kind
        if kind is None:
            raise ManifestInferenceError(
                f"{file.path}: file kind is ambiguous or unresolved; select a supported kind"
            )
        candidate = file.by_kind().get(kind)
        if candidate is None:
            raise ManifestInferenceError(f"{file.path}: unsupported file kind: {kind}")
        proposed_map = {
            field.canonical_field: field.suggested_source_column
            for field in candidate.fields
            if field.suggested_source_column is not None
        }
        unsupported_unmaps = sorted(set(selection.unmapped_fields) - SUPPORTED_FIELDS[kind])
        if unsupported_unmaps:
            raise ManifestInferenceError(
                f"{file.path}: unsupported fields cannot be unmapped: "
                + ", ".join(unsupported_unmaps)
            )
        column_map = {**proposed_map, **selection.column_map}
        for field in selection.unmapped_fields:
            column_map.pop(field, None)
        _validate_column_map(file, kind, column_map)
        required = list(REQUIRED_FIELDS[kind])
        missing = [field for field in required if field not in column_map]
        if missing:
            raise ManifestInferenceError(
                f"{file.path}: required mappings are unresolved: {', '.join(missing)}"
            )
        proposed_units = {
            field.canonical_field: field.suggested_unit
            for field in candidate.fields
            if field.suggested_unit is not None and field.canonical_field in column_map
        }
        units = {**proposed_units, **selection.units}
        units = {field: unit for field, unit in units.items() if field in column_map}
        _validate_units(file.path, column_map, units)
        if selection.kind is not None and selection.kind != file.suggested_kind:
            edited = True
        if any(proposed_map.get(field) != value for field, value in selection.column_map.items()):
            edited = True
        if selection.unmapped_fields:
            edited = True
        if any(proposed_units.get(field) != value for field, value in selection.units.items()):
            edited = True
        mappings.append(
            ConfirmedFileMapping(
                path=file.path,
                kind=kind,
                checksum_sha256=file.checksum_sha256,
                required_columns=required,
                column_map=dict(sorted(column_map.items())),
                units=dict(sorted(units.items())),
            )
        )
    if not mappings:
        raise ManifestInferenceError("at least one CSV mapping must be confirmed")
    kinds = [mapping.kind for mapping in mappings]
    if len(kinds) != len(set(kinds)):
        raise ManifestInferenceError("only one CSV file may be mapped to each file kind")
    mode = ConfirmationMode.EDITED if edited else ConfirmationMode.ACCEPTED_SUGGESTIONS
    mapping_payloads = [mapping.model_dump(mode="json") for mapping in mappings]
    confirmation_fingerprint = canonicalisation_confirmation_fingerprint(
        inference_version=draft.inference_version,
        source_fingerprint=draft.source_fingerprint,
        draft_fingerprint=draft.draft_fingerprint,
        confirmation_state=mode.value,
        confirmed_by=confirmed_by.strip(),
        mappings=mapping_payloads,
        excluded_files=excluded,
    )
    return CanonicalisationManifest(
        inference_version=draft.inference_version,
        source_fingerprint=draft.source_fingerprint,
        draft_fingerprint=draft.draft_fingerprint,
        confirmation_fingerprint=confirmation_fingerprint,
        confirmation_state=mode,
        confirmed_by=confirmed_by.strip(),
        mappings=mappings,
        excluded_files=excluded,
    )


def apply_canonicalisation_to_template(
    canonicalisation: CanonicalisationManifest,
    template: BundleManifest | dict[str, Any],
) -> BundleManifest:
    """Merge confirmed mappings into a complete bundle-manifest metadata template."""

    raw = (
        template.model_dump(mode="json", exclude_none=False)
        if isinstance(template, BundleManifest)
        else dict(template)
    )
    raw["files"] = {
        kind: declaration.model_dump(mode="json", exclude_none=True)
        for kind, declaration in canonicalisation.file_declarations().items()
    }
    raw["canonicalisation"] = CanonicalisationEvidence(
        inference_version=canonicalisation.inference_version,
        source_fingerprint=canonicalisation.source_fingerprint,
        draft_fingerprint=canonicalisation.draft_fingerprint,
        confirmation_fingerprint=canonicalisation.confirmation_fingerprint,
        confirmation_state=canonicalisation.confirmation_state.value,
        confirmed_by=canonicalisation.confirmed_by,
        excluded_files=canonicalisation.excluded_files,
    ).model_dump(mode="json")
    try:
        return BundleManifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestInferenceError(f"bundle manifest template is invalid: {exc}") from exc


def load_inference_draft(path: str | Path) -> ManifestInferenceDraft:
    """Load a JSON or YAML inference draft."""

    return _load_model(path, ManifestInferenceDraft)


def load_canonicalisation_manifest(path: str | Path) -> CanonicalisationManifest:
    """Load a confirmed JSON or YAML canonicalisation manifest."""

    return _load_model(path, CanonicalisationManifest)


def bundle_manifest_to_yaml(manifest: BundleManifest) -> str:
    """Render a validated bundle manifest deterministically."""

    return yaml.safe_dump(manifest.model_dump(mode="json", exclude_none=False), sort_keys=False)


def _sample_csv(path: Path) -> tuple[list[str], dict[str, list[str]], int]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        if not headers or any(not header.strip() for header in headers):
            raise ManifestInferenceError("CSV requires a non-empty header row")
        if len(headers) > MAX_INFERENCE_COLUMNS:
            raise ManifestInferenceError(
                f"CSV exceeds the {MAX_INFERENCE_COLUMNS}-column inference bound"
            )
        if len(headers) != len(set(headers)):
            raise ManifestInferenceError("CSV headers must be unique")
        columns: dict[str, list[str]] = {header: [] for header in headers}
        sampled_rows = 0
        for row in reader:
            if sampled_rows >= MAX_INFERENCE_SAMPLE_ROWS:
                break
            sampled_rows += 1
            for header in headers:
                value = row.get(header)
                raw = value if isinstance(value, str) else ""
                columns[header].append(raw[:MAX_INFERENCE_VALUE_CHARACTERS])
    return headers, columns, sampled_rows


def _infer_file(
    path: str,
    checksum: str,
    headers: list[str],
    columns: dict[str, list[str]],
    sampled_rows: int,
) -> CsvFileInference:
    candidates = [_infer_kind(kind, headers, columns) for kind in FILE_KINDS]
    eligible = [candidate for candidate in candidates if candidate.eligible]
    if not eligible:
        status = SuggestionStatus.UNMAPPED
        suggested_kind = None
    else:
        top_score = max(candidate.score for candidate in eligible)
        top = [candidate for candidate in eligible if candidate.score == top_score]
        if len(top) == 1:
            status = SuggestionStatus.SUGGESTED
            suggested_kind = top[0].kind
        else:
            status = SuggestionStatus.AMBIGUOUS
            suggested_kind = None
    return CsvFileInference(
        path=path,
        checksum_sha256=checksum,
        headers=headers,
        sampled_rows=sampled_rows,
        status=status,
        suggested_kind=suggested_kind,
        kind_candidates=candidates,
    )


def _infer_kind(
    kind: str,
    headers: list[str],
    columns: dict[str, list[str]],
) -> FileKindCandidate:
    required = REQUIRED_FIELDS[kind]
    fields = [
        _infer_field(kind, field, field in required, headers, columns)
        for field in sorted(SUPPORTED_FIELDS[kind])
    ]
    _mark_source_reuse_ambiguous(fields)
    required_mapped = [
        field.canonical_field
        for field in fields
        if field.required and field.status is SuggestionStatus.SUGGESTED
    ]
    eligible = set(required_mapped) == set(required)
    score = sum(
        field.candidates[0].precedence
        for field in fields
        if field.status is SuggestionStatus.SUGGESTED and field.candidates
    )
    return FileKindCandidate(
        kind=kind,
        eligible=eligible,
        score=score,
        required_fields=list(required),
        required_fields_mapped=required_mapped,
        fields=fields,
    )


def _infer_field(
    kind: str,
    field: str,
    required: bool,
    headers: list[str],
    columns: dict[str, list[str]],
) -> FieldSuggestion:
    candidates: list[ColumnCandidate] = []
    for header in headers:
        normalised = _normalise_header(header)
        methods: list[InferenceMethod] = []
        if normalised == field:
            methods.append(InferenceMethod.EXACT_HEADER)
        if normalised in ALIASES.get(kind, {}).get(field, set()):
            methods.append(InferenceMethod.HEADER_ALIAS)
        if _matches_value_pattern(field, columns[header]):
            methods.append(InferenceMethod.VALUE_PATTERN)
        if not methods:
            continue
        precedence = max(_method_precedence(method) for method in methods)
        candidates.append(
            ColumnCandidate(
                source_column=header,
                precedence=precedence,
                methods=sorted(methods, key=_method_precedence, reverse=True),
            )
        )
    candidates.sort(key=lambda item: (-item.precedence, item.source_column.casefold()))
    if not candidates:
        status = SuggestionStatus.UNMAPPED
        suggested = None
    else:
        top = [item for item in candidates if item.precedence == candidates[0].precedence]
        if len(top) == 1:
            status = SuggestionStatus.SUGGESTED
            suggested = top[0].source_column
        else:
            status = SuggestionStatus.AMBIGUOUS
            suggested = None
    dimension = UNIT_DIMENSIONS.get(field)
    suggested_unit = _suggest_unit(suggested, field) if dimension is not None else None
    return FieldSuggestion(
        canonical_field=field,
        required=required,
        status=status,
        suggested_source_column=suggested,
        candidates=candidates,
        unit_dimension=dimension,
        suggested_unit=suggested_unit,
        supported_units=list(supported_units_for_field(field)),
    )


def _mark_source_reuse_ambiguous(fields: list[FieldSuggestion]) -> None:
    by_source: dict[str, list[FieldSuggestion]] = {}
    for field in fields:
        if field.suggested_source_column is not None:
            by_source.setdefault(field.suggested_source_column, []).append(field)
    for conflicting in by_source.values():
        if len(conflicting) < 2:
            continue
        for field in conflicting:
            field.status = SuggestionStatus.AMBIGUOUS
            field.suggested_source_column = None
            field.suggested_unit = None


def _matches_value_pattern(field: str, values: list[str]) -> bool:
    non_empty = [value.strip().casefold() for value in values if value.strip()]
    if not non_empty:
        return False
    observed = set(non_empty)
    if field == "task_class":
        return observed <= {"t1", "t2", "t3"}
    if field == "decision":
        return observed <= {"local", "v2i", "v2v"}
    if field == "completed":
        return observed <= {"true", "false", "yes", "no", "1", "0"}
    return False


def _normalise_header(header: str) -> str:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", header.strip())
    normalised = re.sub(r"[^a-z0-9]+", "_", separated.casefold()).strip("_")
    return re.sub(r"_+", "_", normalised)


def _suggest_unit(source_column: str | None, canonical_field: str) -> str | None:
    if source_column is None:
        return None
    header = _normalise_header(source_column)
    supported = set(supported_units_for_field(canonical_field))
    candidates: list[str] = []
    if header.endswith(("_milliseconds", "_millisecond", "_ms")):
        candidates.append("ms")
    if header.endswith(("_seconds", "_second", "_secs", "_sec", "_s")):
        candidates.append("s")
    if header.endswith(("_minutes", "_minute", "_mins", "_min")):
        candidates.append("min")
    if header.endswith(("_kmh", "_kph", "_km_per_h")):
        candidates.append("km/h")
    if header.endswith(("_mps", "_m_per_s")):
        candidates.append("m/s")
    if header.endswith(("_kilobytes", "_kb")):
        candidates.append("KB")
    if header.endswith(("_bytes", "_byte")):
        candidates.append("bytes")
    if header.endswith(("_joules", "_joule", "_j")):
        candidates.append("J")
    if header.endswith(("_cycles", "_cycle")):
        candidates.append("cycles")
    if header.endswith(("_fraction", "_ratio")):
        candidates.append("fraction")
    return next((unit for unit in candidates if unit in supported), None)


def _validate_column_map(file: CsvFileInference, kind: str, column_map: dict[str, str]) -> None:
    unsupported_fields = sorted(set(column_map) - SUPPORTED_FIELDS[kind])
    if unsupported_fields:
        raise ManifestInferenceError(
            f"{file.path}: unsupported canonical fields for {kind}: "
            + ", ".join(unsupported_fields)
        )
    unknown_columns = sorted(set(column_map.values()) - set(file.headers))
    if unknown_columns:
        raise ManifestInferenceError(
            f"{file.path}: selected source columns do not exist: {', '.join(unknown_columns)}"
        )
    values = list(column_map.values())
    if len(values) != len(set(values)):
        raise ManifestInferenceError(
            f"{file.path}: one source column cannot map to multiple canonical fields"
        )


def _validate_units(path: str, column_map: dict[str, str], units: dict[str, str]) -> None:
    extra_units = sorted(set(units) - set(column_map))
    if extra_units:
        raise ManifestInferenceError(
            f"{path}: units were supplied for unmapped fields: {', '.join(extra_units)}"
        )
    for field in column_map:
        supported = supported_units_for_field(field)
        if not supported:
            continue
        unit = units.get(field)
        if unit is None:
            raise ManifestInferenceError(
                f"{path}: unit for {field} is not evidenced by the header; select one explicitly"
            )
        if unit not in supported:
            raise ManifestInferenceError(
                f"{path}: unsupported unit for {field}: {unit}; supported: {', '.join(supported)}"
            )


def _draft_fingerprint(draft: ManifestInferenceDraft) -> str:
    payload = draft.model_dump(mode="json", exclude={"draft_fingerprint", "source_label"})
    return _json_fingerprint(payload)


def _json_fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _method_precedence(method: InferenceMethod) -> int:
    return {
        InferenceMethod.EXACT_HEADER: 30,
        InferenceMethod.HEADER_ALIAS: 20,
        InferenceMethod.VALUE_PATTERN: 10,
    }[method]


def _stays_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (FileNotFoundError, OSError, ValueError):
        return False
    return True


def _failed_draft(
    source_label: str,
    code: ValidationCode,
    message: str,
) -> ManifestInferenceDraft:
    draft = ManifestInferenceDraft(
        source_label=source_label,
        findings=[_finding(code, Severity.FATAL, message, may_continue=False)],
    )
    return draft.model_copy(update={"draft_fingerprint": _draft_fingerprint(draft)})


def _load_model(path: str | Path, model: type[ModelT]) -> ModelT:
    source = Path(path)
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        return model.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ManifestInferenceError(f"could not load {model.__name__}: {exc}") from exc


def _finding(
    code: ValidationCode,
    severity: Severity,
    message: str,
    *,
    file: str | None = None,
    field: str | None = None,
    value: object = None,
    may_continue: bool,
    affected_capabilities: list[str] | None = None,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=severity,
        message=message,
        file=file,
        field=field,
        value=value,
        may_continue=may_continue,
        affected_capabilities=affected_capabilities or [],
    )
