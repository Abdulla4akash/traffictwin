"""Deterministic, bounded mutations over copied synthetic/evaluation bundles.

EXP-02 never edits its parent bundle.  It admits a closed set of mutations over
explicitly labelled synthetic/evaluation fixtures, writes a derived ordinary
bundle, and records every changed source row plus the parent fingerprint.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import Field, field_validator

from traffictwin.config.seed_io import dump_seed
from traffictwin.domain.enums import ExecutionMode
from traffictwin.domain.scenario import ScenarioSeed, StrictModel, _validate_identifier
from traffictwin.ingestion.bundle import BundleValidationResult, validate_bundle
from traffictwin.ingestion.loader import BundleLoadError, open_bundle
from traffictwin.ingestion.manifest import (
    BundleManifest,
    FileDeclaration,
    SourceFileFormat,
)
from traffictwin.ingestion.tabular import TabularData, read_declared_table

MUTATION_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MUTATION_METHOD_VERSION: Literal["1.0"] = "1.0"
DETERMINISTIC_MUTATION_CREATED_AT = "2026-07-21T00:00:00Z"
MAX_SOURCE_FILES = 64
MAX_SOURCE_BYTES = 25_000_000
MAX_SOURCE_ROWS_PER_TABLE = 100_000
MAX_CHANGED_ROWS = 20_000
MAX_JITTER_SECONDS = 3_600.0
MAX_REQUEST_BYTES = 1_000_000


class MutationTableKind(StrEnum):
    """Closed tabular targets admitted by EXP-02."""

    TASKS = "tasks"
    INFRA_STATE = "infra_state"
    VEHICLE_STATE = "vehicle_state"
    TRAFFIC_OBS = "traffic_obs"
    TRIPS = "trips"
    INCIDENTS = "incidents"


class MutationOperator(StrEnum):
    """Closed v1 mutation operators."""

    ROW_DROPOUT = "row_dropout"
    TIMESTAMP_JITTER = "timestamp_jitter"
    RSU_REMOVAL = "rsu_removal"


class RowDropoutMutation(StrictModel):
    """Drop an exact deterministic subset of one declared table."""

    operator: Literal[MutationOperator.ROW_DROPOUT] = MutationOperator.ROW_DROPOUT
    table_kind: MutationTableKind
    drop_fraction: float = Field(gt=0.0, le=1.0)
    random_seed: int = Field(default=0, ge=0, le=2_147_483_647)


class TimestampJitterMutation(StrictModel):
    """Shift all absolute timestamps in each selected row by one bounded delta."""

    operator: Literal[MutationOperator.TIMESTAMP_JITTER] = MutationOperator.TIMESTAMP_JITTER
    table_kind: MutationTableKind
    max_absolute_jitter_s: float = Field(gt=0.0, le=MAX_JITTER_SECONDS)
    random_seed: int = Field(default=0, ge=0, le=2_147_483_647)


class RsuRemovalMutation(StrictModel):
    """Remove infrastructure observations for one exact declared RSU identifier."""

    operator: Literal[MutationOperator.RSU_REMOVAL] = MutationOperator.RSU_REMOVAL
    rsu_id: str

    @field_validator("rsu_id")
    @classmethod
    def validate_rsu_id(cls, value: str) -> str:
        return _validate_identifier(value, "rsu_id") or value


MutationSpec = Annotated[
    RowDropoutMutation | TimestampJitterMutation | RsuRemovalMutation,
    Field(discriminator="operator"),
]


class ScenarioMutationRequest(StrictModel):
    """One complete deterministic mutation declaration."""

    schema_version: Literal["1.0"] = MUTATION_SCHEMA_VERSION
    mutation_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    mutation: MutationSpec

    @field_validator("mutation_id")
    @classmethod
    def validate_mutation_id(cls, value: str) -> str:
        return _validate_identifier(value, "mutation_id") or value


class MutationFieldChange(StrictModel):
    """One exact scalar field edit in a retained source row."""

    canonical_field: str
    source_field: str
    before: str
    after: str


class MutationRowChange(StrictModel):
    """One exact changed parent row."""

    table_kind: MutationTableKind
    source_file: str
    parent_source_row: int = Field(ge=2)
    action: Literal["dropped", "updated"]
    row_fingerprint_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_fingerprint_after: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    field_changes: list[MutationFieldChange] = Field(default_factory=list)


class MutationFileChange(StrictModel):
    """Checksum and row-count reconciliation for one changed file."""

    path: str
    table_kind: MutationTableKind | None = None
    change_kind: Literal["tabular_rows", "derived_seed", "derived_manifest"]
    checksum_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    checksum_after: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows_before: int | None = Field(default=None, ge=0)
    rows_after: int | None = Field(default=None, ge=0)
    changed_rows: int | None = Field(default=None, ge=0)


class ScenarioMutationPlan(StrictModel):
    """Pure, complete mutation projection before destination materialisation."""

    schema_version: Literal["1.0"] = MUTATION_SCHEMA_VERSION
    method_version: Literal["1.0"] = MUTATION_METHOD_VERSION
    mutation_id: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_bundle_id: str
    parent_run_id: str
    parent_seed_id: str
    parent_bundle_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_bundle_id: str
    derived_run_id: str
    derived_seed_id: str
    derived_bundle_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    mutation: MutationSpec
    changed_row_count: int = Field(ge=1, le=MAX_CHANGED_ROWS)
    row_changes: list[MutationRowChange] = Field(min_length=1, max_length=MAX_CHANGED_ROWS)
    file_changes: list[MutationFileChange] = Field(min_length=3)
    synthetic_evaluation: Literal[True] = True
    raw_source_mutated: Literal[False] = False
    direct_launch_supported: Literal[False] = False
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def fingerprint(self) -> str:
        """Recompute the stable plan fingerprint."""

        payload = self.model_dump(mode="json")
        payload["plan_fingerprint"] = ""
        return _fingerprint(payload)


class ScenarioMutationResult(StrictModel):
    """Materialised mutation manifest and ordinary bundle-validation outcome."""

    schema_version: Literal["1.0"] = MUTATION_SCHEMA_VERSION
    method_version: Literal["1.0"] = MUTATION_METHOD_VERSION
    mutation_id: str
    title: str
    generated_at: datetime
    status: Literal["validated_mutated_bundle"] = "validated_mutated_bundle"
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    mutation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_bundle_id: str
    parent_run_id: str
    parent_seed_id: str
    parent_bundle_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_bundle_id: str
    derived_run_id: str
    derived_seed_id: str
    derived_bundle_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    mutation: MutationSpec
    changed_row_count: int = Field(ge=1, le=MAX_CHANGED_ROWS)
    row_changes: list[MutationRowChange] = Field(min_length=1, max_length=MAX_CHANGED_ROWS)
    file_changes: list[MutationFileChange] = Field(min_length=3)
    validation_status: str
    validation_may_import: Literal[True] = True
    validation_finding_codes: list[str] = Field(default_factory=list)
    bundle_relative_path: Literal["bundle"] = "bundle"
    synthetic_evaluation: Literal[True] = True
    raw_source_mutated: Literal[False] = False
    direct_launch_supported: Literal[False] = False
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def canonical_json(self) -> str:
        """Return timestamp-independent canonical result JSON."""

        payload = self.model_dump(mode="json")
        payload["generated_at"] = "<normalised>"
        payload["mutation_fingerprint"] = ""
        return _canonical_json(payload)

    def fingerprint(self) -> str:
        """Recompute the stable result fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ScenarioMutationContract(StrictModel):
    """Machine-readable EXP-02 method and safety boundary."""

    schema_version: Literal["1.0"] = MUTATION_SCHEMA_VERSION
    method_version: Literal["1.0"] = MUTATION_METHOD_VERSION
    supported_operators: list[MutationOperator]
    supported_tables: list[MutationTableKind]
    admitted_parent_labels: list[str]
    max_source_files: int = MAX_SOURCE_FILES
    max_source_bytes: int = MAX_SOURCE_BYTES
    max_source_rows_per_table: int = MAX_SOURCE_ROWS_PER_TABLE
    max_changed_rows: int = MAX_CHANGED_ROWS
    max_absolute_jitter_s: float = MAX_JITTER_SECONDS
    direct_launch_supported: Literal[False] = False
    exact_change_ledger: Literal[True] = True
    raw_source_mutation_supported: Literal[False] = False
    output_format_boundary: str
    rsu_removal_policy: str
    timestamp_policy: str
    dropout_policy: str
    limitations: list[str]


class ScenarioMutationError(RuntimeError):
    """Raised when an EXP-02 request cannot be planned or materialised safely."""


@dataclass(frozen=True)
class _PreparedMutation:
    plan: ScenarioMutationPlan
    bundle_files: dict[str, bytes]


_ADMITTED_PARENT_LABELS = ("synthetic_fixture", "synthetic_mutation", "synthetic_evaluation")
_TIMESTAMP_FIELDS: dict[MutationTableKind, tuple[str, ...]] = {
    MutationTableKind.TASKS: ("arrival_time", "completion_time"),
    MutationTableKind.INFRA_STATE: ("timestamp",),
    MutationTableKind.VEHICLE_STATE: ("timestamp",),
    MutationTableKind.TRAFFIC_OBS: ("timestamp",),
    MutationTableKind.TRIPS: ("departure_time", "arrival_time"),
    MutationTableKind.INCIDENTS: ("timestamp",),
}


def scenario_mutation_contract() -> ScenarioMutationContract:
    """Return the closed bounded EXP-02 contract."""

    return ScenarioMutationContract(
        supported_operators=list(MutationOperator),
        supported_tables=list(MutationTableKind),
        admitted_parent_labels=list(_ADMITTED_PARENT_LABELS),
        output_format_boundary=(
            "Only a targeted declared uncompressed CSV table is rewritten. Other parent bundle "
            "files are copied byte-for-byte; compressed CSV and Parquet targets are unsupported."
        ),
        rsu_removal_policy=(
            "Remove exact matching infrastructure rows and mark the derived seed; retain task "
            "targets unchanged because TrafficTwin cannot invent rerouting behavior."
        ),
        timestamp_policy=(
            "Apply one deterministic delta per row to every present absolute timestamp field, "
            "clamped only to keep the earliest timestamp non-negative."
        ),
        dropout_policy=(
            "Drop max(1, floor(row_count * fraction)) rows selected by stable seeded SHA-256 "
            "ordering; never sample from mutable process state."
        ),
        limitations=_limitations(),
    )


def load_scenario_mutation_request(path: str | Path) -> ScenarioMutationRequest:
    """Load a strict bounded YAML/JSON mutation request."""

    source = Path(path)
    try:
        if source.stat().st_size > MAX_REQUEST_BYTES:
            raise ScenarioMutationError(
                f"scenario-mutation request exceeds {MAX_REQUEST_BYTES:,} bytes"
            )
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except ScenarioMutationError:
        raise
    except (OSError, yaml.YAMLError) as exc:
        raise ScenarioMutationError(f"could not read scenario-mutation request: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScenarioMutationError("scenario-mutation request must be a mapping")
    try:
        return ScenarioMutationRequest.model_validate(payload)
    except ValueError as exc:
        raise ScenarioMutationError(f"invalid scenario-mutation request: {exc}") from exc


def scenario_mutation_request_to_yaml(request: ScenarioMutationRequest) -> str:
    """Serialise an EXP-02 request without inferred values."""

    return yaml.safe_dump(
        request.model_dump(mode="json", exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )


def plan_scenario_mutation(
    parent_bundle: str | Path,
    request: ScenarioMutationRequest,
) -> ScenarioMutationPlan:
    """Validate and project every exact change without writing a destination."""

    return _prepare_mutation(parent_bundle, request).plan


def execute_scenario_mutation(
    parent_bundle: str | Path,
    request: ScenarioMutationRequest,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
    clock: Callable[[], datetime] | None = None,
) -> ScenarioMutationResult:
    """Materialise one derived bundle transactionally and validate it ordinarily."""

    destination = _validated_destination(output_dir)
    _reject_source_destination_overlap(parent_bundle, destination)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"scenario-mutation destination already exists: {destination}")
    if destination.exists() and not destination.is_dir():
        raise ScenarioMutationError(
            f"scenario-mutation destination is not a directory: {destination}"
        )
    prepared = _prepare_mutation(parent_bundle, request)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-mutation-", dir=destination.parent)
    )
    working = temporary_root / "payload"
    bundle_path = working / "bundle"
    bundle_path.mkdir(parents=True)
    try:
        for relative, content in sorted(prepared.bundle_files.items()):
            target = bundle_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        validation = validate_bundle(bundle_path)
        if not validation.report.may_import or validation.manifest is None:
            raise ScenarioMutationError(
                "derived bundle failed ordinary validation; destination was not replaced"
            )
        if validation.fingerprint != prepared.plan.derived_bundle_fingerprint:
            raise ScenarioMutationError(
                "derived bundle fingerprint does not match the planned file inventory"
            )
        generated_at = (clock or _utc_now)()
        result = _result_from_plan(prepared.plan, request, validation, generated_at)
        (working / "request.yaml").write_text(
            scenario_mutation_request_to_yaml(request),
            encoding="utf-8",
        )
        (working / "mutation_manifest.json").write_text(
            result.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        _publish_transactionally(working, destination, temporary_root)
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise
    shutil.rmtree(temporary_root, ignore_errors=True)
    return result


def _prepare_mutation(
    parent_bundle: str | Path,
    request: ScenarioMutationRequest,
) -> _PreparedMutation:
    if Path(parent_bundle).is_symlink():
        raise ScenarioMutationError("parent bundle path must not be a symbolic link")
    validation = validate_bundle(parent_bundle)
    manifest, seed, parent_fingerprint = _admit_parent(validation)
    request_fingerprint = _fingerprint(request.model_dump(mode="json"))
    identity = _fingerprint(
        {
            "method_version": MUTATION_METHOD_VERSION,
            "request_fingerprint": request_fingerprint,
            "parent_bundle_fingerprint": parent_fingerprint,
        }
    )
    suffix = identity[:12]
    derived_bundle_id = f"{manifest.bundle.bundle_id}-mut-{suffix}"
    derived_run_id = f"{manifest.run.run_id}-mut-{suffix}"
    derived_seed_id = f"{seed.seed_id}-mut-{suffix}"
    try:
        with open_bundle(parent_bundle, max_uncompressed_bytes=MAX_SOURCE_BYTES) as workspace:
            bundle_files = _read_source_inventory(workspace.root)
            parent_bundle_files = dict(bundle_files)
            row_changes, target_kind, target_path, rows_before, rows_after = _apply_operator(
                request.mutation,
                manifest,
                workspace.root,
                bundle_files,
            )
    except (BundleLoadError, OSError, ValueError) as exc:
        raise ScenarioMutationError(f"could not prepare scenario mutation: {exc}") from exc
    if len(row_changes) > MAX_CHANGED_ROWS:
        raise ScenarioMutationError(
            f"mutation changes {len(row_changes):,} rows; maximum is {MAX_CHANGED_ROWS:,}"
        )
    if not row_changes:
        raise ScenarioMutationError("mutation would not change any source row")

    parent_seed_bytes = bundle_files["seed.yaml"]
    parent_manifest_bytes = bundle_files["manifest.yaml"]
    derived_seed = _derived_seed(seed, request, derived_seed_id)
    bundle_files["seed.yaml"] = dump_seed(derived_seed).encode("utf-8")
    derived_manifest = _derived_manifest(
        manifest,
        request,
        parent_fingerprint,
        derived_bundle_id,
        derived_run_id,
        derived_seed_id,
        bundle_files,
    )
    bundle_files["manifest.yaml"] = yaml.safe_dump(
        derived_manifest.model_dump(mode="json", exclude_none=False),
        sort_keys=False,
        allow_unicode=False,
    ).encode("utf-8")
    derived_fingerprint = _bundle_file_map_fingerprint(bundle_files)
    file_changes = [
        MutationFileChange(
            path=target_path,
            table_kind=target_kind,
            change_kind="tabular_rows",
            checksum_before=sha256_file_bytes(parent_bundle_files[target_path]),
            checksum_after=sha256_file_bytes(bundle_files[target_path]),
            rows_before=rows_before,
            rows_after=rows_after,
            changed_rows=len(row_changes),
        ),
        MutationFileChange(
            path="seed.yaml",
            change_kind="derived_seed",
            checksum_before=sha256_file_bytes(parent_seed_bytes),
            checksum_after=sha256_file_bytes(bundle_files["seed.yaml"]),
        ),
        MutationFileChange(
            path="manifest.yaml",
            change_kind="derived_manifest",
            checksum_before=sha256_file_bytes(parent_manifest_bytes),
            checksum_after=sha256_file_bytes(bundle_files["manifest.yaml"]),
        ),
    ]
    plan_payload: dict[str, Any] = {
        "mutation_id": request.mutation_id,
        "request_fingerprint": request_fingerprint,
        "plan_fingerprint": "",
        "parent_bundle_id": manifest.bundle.bundle_id,
        "parent_run_id": manifest.run.run_id,
        "parent_seed_id": seed.seed_id,
        "parent_bundle_fingerprint": parent_fingerprint,
        "derived_bundle_id": derived_bundle_id,
        "derived_run_id": derived_run_id,
        "derived_seed_id": derived_seed_id,
        "derived_bundle_fingerprint": derived_fingerprint,
        "mutation": request.mutation.model_dump(mode="json"),
        "changed_row_count": len(row_changes),
        "row_changes": [change.model_dump(mode="json") for change in row_changes],
        "file_changes": [change.model_dump(mode="json") for change in file_changes],
        "schema_version": MUTATION_SCHEMA_VERSION,
        "method_version": MUTATION_METHOD_VERSION,
        "synthetic_evaluation": True,
        "raw_source_mutated": False,
        "direct_launch_supported": False,
        "warnings": _warnings(request.mutation),
        "limitations": _limitations(),
    }
    plan_payload["plan_fingerprint"] = _fingerprint(plan_payload)
    plan = ScenarioMutationPlan.model_validate(plan_payload)
    return _PreparedMutation(plan=plan, bundle_files=bundle_files)


def _admit_parent(
    validation: BundleValidationResult,
) -> tuple[BundleManifest, ScenarioSeed, str]:
    if (
        not validation.report.may_import
        or validation.manifest is None
        or validation.seed is None
        or validation.fingerprint is None
    ):
        raise ScenarioMutationError("parent bundle must pass ordinary validation before mutation")
    manifest = validation.manifest
    if (
        manifest.bundle.source not in _ADMITTED_PARENT_LABELS
        and manifest.run.execution_mode is not ExecutionMode.SYNTHETIC
    ):
        raise ScenarioMutationError(
            "parent bundle is not explicitly labelled synthetic/evaluation; raw imported evidence "
            "cannot be mutated"
        )
    if manifest.canonicalisation is not None:
        raise ScenarioMutationError(
            "confirmation-gated canonicalisation manifests cannot be rewritten by EXP-02"
        )
    return manifest, validation.seed, validation.fingerprint


def _read_source_inventory(root: Path) -> dict[str, bytes]:
    paths = sorted(path for path in root.rglob("*") if path.is_file() or path.is_symlink())
    if any(path.is_symlink() for path in paths):
        raise ScenarioMutationError("parent bundle must not contain symbolic links")
    files = [path for path in paths if path.is_file()]
    if len(files) > MAX_SOURCE_FILES:
        raise ScenarioMutationError(
            f"parent bundle contains {len(files)} files; maximum is {MAX_SOURCE_FILES}"
        )
    total_bytes = sum(path.stat().st_size for path in files)
    if total_bytes > MAX_SOURCE_BYTES:
        raise ScenarioMutationError(
            f"parent bundle contains {total_bytes:,} bytes; maximum is {MAX_SOURCE_BYTES:,}"
        )
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in files}


def _apply_operator(
    mutation: MutationSpec,
    manifest: BundleManifest,
    root: Path,
    bundle_files: dict[str, bytes],
) -> tuple[list[MutationRowChange], MutationTableKind, str, int, int]:
    table_kind = (
        MutationTableKind.INFRA_STATE
        if isinstance(mutation, RsuRemovalMutation)
        else mutation.table_kind
    )
    declaration = _target_declaration(manifest, table_kind)
    table = read_declared_table(root / declaration.path, declaration)
    if len(table.rows) > MAX_SOURCE_ROWS_PER_TABLE:
        raise ScenarioMutationError(
            f"target table contains {len(table.rows):,} rows; maximum is "
            f"{MAX_SOURCE_ROWS_PER_TABLE:,}"
        )
    if isinstance(mutation, RowDropoutMutation):
        rows, changes = _row_dropout(table, table_kind, declaration, mutation)
    elif isinstance(mutation, TimestampJitterMutation):
        rows, changes = _timestamp_jitter(table, table_kind, declaration, mutation)
    else:
        rows, changes = _rsu_removal(table, declaration, mutation)
    if len(changes) > MAX_CHANGED_ROWS:
        raise ScenarioMutationError(
            f"mutation changes {len(changes):,} rows; maximum is {MAX_CHANGED_ROWS:,}"
        )
    bundle_files[declaration.path] = _table_to_csv_bytes(table.headers, rows)
    return changes, table_kind, declaration.path, len(table.rows), len(rows)


def _target_declaration(
    manifest: BundleManifest,
    table_kind: MutationTableKind,
) -> FileDeclaration:
    declaration = manifest.files.get(table_kind.value)
    if declaration is None:
        raise ScenarioMutationError(f"parent bundle does not declare {table_kind.value}")
    if declaration.format is not SourceFileFormat.CSV or declaration.compression is not None:
        raise ScenarioMutationError(
            "EXP-02 v1 targets only declared uncompressed CSV tables; other files remain copied "
            "byte-for-byte"
        )
    return declaration


def _row_dropout(
    table: TabularData,
    table_kind: MutationTableKind,
    declaration: FileDeclaration,
    mutation: RowDropoutMutation,
) -> tuple[list[dict[str, str | None]], list[MutationRowChange]]:
    if not table.rows:
        raise ScenarioMutationError("row dropout requires a non-empty target table")
    drop_count = min(
        len(table.rows),
        max(1, math.floor(len(table.rows) * mutation.drop_fraction)),
    )
    if drop_count > MAX_CHANGED_ROWS:
        raise ScenarioMutationError(
            f"row dropout selects {drop_count:,} rows; maximum is {MAX_CHANGED_ROWS:,}"
        )
    ranked = sorted(
        range(len(table.rows)),
        key=lambda index: _selection_score(
            mutation.random_seed,
            table_kind,
            index + 2,
            table.rows[index],
        ),
    )
    dropped = set(ranked[:drop_count])
    retained = [row for index, row in enumerate(table.rows) if index not in dropped]
    changes = [
        MutationRowChange(
            table_kind=table_kind,
            source_file=declaration.path,
            parent_source_row=index + 2,
            action="dropped",
            row_fingerprint_before=_fingerprint(table.rows[index]),
        )
        for index in sorted(dropped)
    ]
    return retained, changes


def _timestamp_jitter(
    table: TabularData,
    table_kind: MutationTableKind,
    declaration: FileDeclaration,
    mutation: TimestampJitterMutation,
) -> tuple[list[dict[str, str | None]], list[MutationRowChange]]:
    canonical_fields = _TIMESTAMP_FIELDS[table_kind]
    source_fields: list[tuple[str, str]] = []
    for canonical_field in canonical_fields:
        source_field = declaration.source_column_for(canonical_field)
        if source_field in table.headers:
            if declaration.units.get(canonical_field) != "s":
                raise ScenarioMutationError(
                    f"timestamp jitter requires explicit seconds for {table_kind.value}."
                    f"{canonical_field}"
                )
            source_fields.append((canonical_field, source_field))
    if not source_fields:
        raise ScenarioMutationError("target table has no declared absolute timestamp field")
    if len(table.rows) > MAX_CHANGED_ROWS:
        raise ScenarioMutationError(
            f"timestamp jitter would change {len(table.rows):,} rows; maximum is "
            f"{MAX_CHANGED_ROWS:,}"
        )
    output: list[dict[str, str | None]] = []
    changes: list[MutationRowChange] = []
    for index, original in enumerate(table.rows, start=2):
        present: list[tuple[str, str, float]] = []
        for canonical_field, source_field in source_fields:
            raw = original.get(source_field)
            if raw not in {None, ""}:
                present.append((canonical_field, source_field, _finite_float(raw, source_field)))
        if not present:
            output.append(dict(original))
            continue
        raw_delta = _jitter_delta(
            mutation.random_seed,
            table_kind,
            index,
            original,
            mutation.max_absolute_jitter_s,
        )
        delta = max(raw_delta, -min(value for _, _, value in present))
        delta = round(delta, 6)
        updated = dict(original)
        field_changes: list[MutationFieldChange] = []
        for canonical_field, source_field, value in present:
            after = _format_float(max(0.0, value + delta))
            before = str(original[source_field])
            updated[source_field] = after
            if after != before:
                field_changes.append(
                    MutationFieldChange(
                        canonical_field=canonical_field,
                        source_field=source_field,
                        before=before,
                        after=after,
                    )
                )
        if not field_changes:
            output.append(dict(original))
            continue
        output.append(updated)
        changes.append(
            MutationRowChange(
                table_kind=table_kind,
                source_file=declaration.path,
                parent_source_row=index,
                action="updated",
                row_fingerprint_before=_fingerprint(original),
                row_fingerprint_after=_fingerprint(updated),
                field_changes=field_changes,
            )
        )
    if not changes:
        raise ScenarioMutationError("timestamp jitter found no populated timestamps")
    return output, changes


def _rsu_removal(
    table: TabularData,
    declaration: FileDeclaration,
    mutation: RsuRemovalMutation,
) -> tuple[list[dict[str, str | None]], list[MutationRowChange]]:
    source_field = declaration.source_column_for("rsu_id")
    if source_field not in table.headers:
        raise ScenarioMutationError("infra_state does not contain the declared rsu_id field")
    selected = [
        (index, row)
        for index, row in enumerate(table.rows, start=2)
        if row.get(source_field) == mutation.rsu_id
    ]
    if not selected:
        raise ScenarioMutationError(f"RSU {mutation.rsu_id!r} is absent from infra_state")
    if len(selected) > MAX_CHANGED_ROWS:
        raise ScenarioMutationError(
            f"RSU removal changes {len(selected):,} rows; maximum is {MAX_CHANGED_ROWS:,}"
        )
    retained = [row for row in table.rows if row.get(source_field) != mutation.rsu_id]
    changes = [
        MutationRowChange(
            table_kind=MutationTableKind.INFRA_STATE,
            source_file=declaration.path,
            parent_source_row=index,
            action="dropped",
            row_fingerprint_before=_fingerprint(row),
        )
        for index, row in selected
    ]
    return retained, changes


def _derived_seed(
    parent: ScenarioSeed,
    request: ScenarioMutationRequest,
    derived_seed_id: str,
) -> ScenarioSeed:
    payload = parent.model_dump(mode="python", by_alias=False)
    payload.update(
        {
            "seed_id": derived_seed_id,
            "name": f"{parent.name} — mutation {request.mutation_id}",
            "description": (
                f"{parent.description} Deterministic synthetic/evaluation mutation "
                f"{request.mutation_id}; see mutation_manifest.json for exact row changes."
            ).strip(),
            "parent_seed_id": parent.seed_id,
            "compare_against": parent.seed_id,
            "provenance": {
                "created_by": "TrafficTwin deterministic scenario mutation service",
                "source": f"EXP-02 mutation of {parent.seed_id}",
            },
        }
    )
    if isinstance(request.mutation, RsuRemovalMutation):
        infrastructure = dict(payload["infrastructure"])
        failed = list(infrastructure.get("failed_rsus", []))
        if request.mutation.rsu_id not in failed:
            failed.append(request.mutation.rsu_id)
        infrastructure["failed_rsus"] = failed
        count = infrastructure.get("rsu_count")
        if isinstance(count, int):
            infrastructure["rsu_count"] = max(0, count - 1)
        payload["infrastructure"] = infrastructure
    return ScenarioSeed.model_validate(payload)


def _derived_manifest(
    parent: BundleManifest,
    request: ScenarioMutationRequest,
    parent_fingerprint: str,
    derived_bundle_id: str,
    derived_run_id: str,
    derived_seed_id: str,
    bundle_files: dict[str, bytes],
) -> BundleManifest:
    payload = parent.model_dump(mode="json", exclude_none=False)
    payload["bundle"].update(
        {
            "bundle_id": derived_bundle_id,
            "created_at": DETERMINISTIC_MUTATION_CREATED_AT,
            "source": "synthetic_mutation",
        }
    )
    payload["run"].update(
        {
            "run_id": derived_run_id,
            "seed_id": derived_seed_id,
            "execution_mode": ExecutionMode.SYNTHETIC.value,
            "started_at": None,
            "completed_at": None,
        }
    )
    payload["environment"] = {
        "name": "traffictwin_mutation",
        "version": MUTATION_METHOD_VERSION,
        "commit": None,
    }
    payload["provenance"] = {
        "producer": "TrafficTwin deterministic scenario mutation service",
        "notes": (
            f"SYNTHETIC EVALUATION mutation={request.mutation.operator.value}; "
            f"mutation_id={request.mutation_id}; parent_fingerprint={parent_fingerprint}; raw "
            "parent unchanged."
        ),
    }
    for declaration in payload["files"].values():
        path = declaration["path"]
        declaration["checksum_sha256"] = sha256_file_bytes(bundle_files[path])
    payload["canonicalisation"] = None
    return BundleManifest.model_validate(payload)


def _result_from_plan(
    plan: ScenarioMutationPlan,
    request: ScenarioMutationRequest,
    validation: BundleValidationResult,
    generated_at: datetime,
) -> ScenarioMutationResult:
    payload: dict[str, Any] = {
        **plan.model_dump(mode="json"),
        "title": request.title,
        "generated_at": generated_at.isoformat(),
        "status": "validated_mutated_bundle",
        "mutation_fingerprint": "",
        "validation_status": validation.report.status.value,
        "validation_may_import": True,
        "validation_finding_codes": [finding.code.value for finding in validation.report.findings],
        "bundle_relative_path": "bundle",
    }
    payload.pop("plan_fingerprint", None)
    payload["plan_fingerprint"] = plan.plan_fingerprint
    payload["mutation_fingerprint"] = _fingerprint(
        {**payload, "generated_at": "<normalised>", "mutation_fingerprint": ""}
    )
    return ScenarioMutationResult.model_validate(payload)


def _table_to_csv_bytes(
    headers: list[str],
    rows: list[dict[str, str | None]],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {header: "" if row.get(header) is None else row.get(header) for header in headers}
        )
    return output.getvalue().encode("utf-8")


def _selection_score(
    random_seed: int,
    table_kind: MutationTableKind,
    source_row: int,
    row: dict[str, str | None],
) -> str:
    return _fingerprint(
        {
            "method": "seeded_sha256_row_order_v1",
            "random_seed": random_seed,
            "table_kind": table_kind.value,
            "source_row": source_row,
            "row": row,
        }
    )


def _jitter_delta(
    random_seed: int,
    table_kind: MutationTableKind,
    source_row: int,
    row: dict[str, str | None],
    maximum: float,
) -> float:
    digest = _selection_score(random_seed, table_kind, source_row, row)
    fraction = int(digest[:16], 16) / ((1 << 64) - 1)
    return (2.0 * fraction - 1.0) * maximum


def _finite_float(value: str, field: str) -> float:
    try:
        numeric = float(value)
    except ValueError as exc:
        raise ScenarioMutationError(f"{field} contains a non-numeric timestamp: {value!r}") from exc
    if not math.isfinite(numeric):
        raise ScenarioMutationError(f"{field} contains a non-finite timestamp")
    return numeric


def _format_float(value: float) -> str:
    rounded = round(value, 6)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.6f}".rstrip("0").rstrip(".") or "0"


def _validated_destination(output_dir: str | Path) -> Path:
    raw = str(output_dir)
    if not raw.strip():
        raise ScenarioMutationError("scenario-mutation destination must not be empty")
    unresolved = Path(output_dir).expanduser()
    if unresolved.is_symlink():
        raise ScenarioMutationError(
            f"scenario-mutation destination must not be a symbolic link: {unresolved}"
        )
    destination = unresolved.resolve(strict=False)
    protected = (Path.cwd().resolve(), Path.home().resolve())
    if any(destination == item or item.is_relative_to(destination) for item in protected):
        raise ScenarioMutationError(
            "scenario-mutation destination must not be the current directory, home directory, "
            "filesystem root, or one of their ancestors"
        )
    return destination


def _reject_source_destination_overlap(
    parent_bundle: str | Path,
    destination: Path,
) -> None:
    source = Path(parent_bundle).expanduser().resolve(strict=False)
    overlaps = (
        source == destination or source in destination.parents or destination in source.parents
    )
    if overlaps:
        raise ScenarioMutationError(
            "scenario-mutation destination must not overlap the parent bundle"
        )


def _publish_transactionally(
    working: Path,
    destination: Path,
    temporary_root: Path,
) -> None:
    previous: Path | None = None
    if destination.exists():
        previous = temporary_root / "previous-destination"
        destination.replace(previous)
    try:
        working.replace(destination)
    except Exception:
        if previous is not None and previous.exists() and not destination.exists():
            previous.replace(destination)
        raise


def _bundle_file_map_fingerprint(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, content in sorted(files.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file_bytes(content).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_file_bytes(content: bytes) -> str:
    """Return SHA-256 for already bounded in-memory file content."""

    return hashlib.sha256(content).hexdigest()


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _warnings(mutation: MutationSpec) -> list[str]:
    warnings = [
        "The derived bundle is synthetic/mutated evaluation evidence, not real-world or external "
        "validation."
    ]
    if isinstance(mutation, RsuRemovalMutation):
        warnings.append(
            "Task target IDs are retained unchanged; TrafficTwin did not invent task rerouting "
            "after RSU removal."
        )
    return warnings


def _limitations() -> list[str]:
    return [
        "Only explicitly labelled synthetic/evaluation parent bundles are admitted.",
        "The parent bundle is read-only; the derived output is a separate copied bundle.",
        "Only one closed mutation operator is applied per request.",
        "Target mutation supports declared uncompressed CSV only; gzip and Parquet targets are "
        "unsupported in v1.",
        "Mutation behavior is deterministic software robustness evidence, not a physical sensor, "
        "traffic, network, failure, or simulator model.",
        "RSU removal does not infer rerouting, rescheduling, retraining, or policy response.",
        "No mode launches SUMO, Randy VEC/TOS, training, or another external simulator.",
        "Empty, symbolic-link, current/home/root, and current/home ancestor destinations are "
        "rejected before materialisation.",
        "A destination must not equal, contain, or sit inside its parent bundle; failed overwrite "
        "publication restores the previous destination.",
    ]


def _utc_now() -> datetime:
    return datetime.now(UTC)
