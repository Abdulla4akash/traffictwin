"""Memory-bounded canonicalisation over declared tabular bundle files."""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.adapters.generic_csv import GenericTabularAdapter
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.enums import Decision
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.availability import EvidenceAvailability
from traffictwin.evidence.insufficient import InsufficientEvidenceSummary
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.findings import Severity, ValidationFinding
from traffictwin.validation.report import ValidationReport

STREAMING_SCHEMA_VERSION: Literal["1.0"] = "1.0"
DEFAULT_STREAM_CHUNK_ROWS = 1_000
DEFAULT_STREAM_MAX_CHUNK_BYTES = 4_000_000
DEFAULT_STREAM_MAX_TABLE_BYTES = 1_000_000_000
DEFAULT_STREAM_MAX_BUNDLE_BYTES = 2_000_000_000

SourceTableKind: TypeAlias = Literal[
    "tasks",
    "infra_state",
    "vehicle_state",
    "traffic_obs",
    "trips",
    "incidents",
]


class StreamingModel(BaseModel):
    """Strict base model for streaming artifacts."""

    model_config = ConfigDict(extra="forbid")


class StreamingCanonicalisationConfig(StreamingModel):
    """Explicit safety and working-set bounds for streaming canonicalisation."""

    schema_version: Literal["1.0"] = STREAMING_SCHEMA_VERSION
    chunk_rows: int = Field(default=DEFAULT_STREAM_CHUNK_ROWS, ge=1, le=100_000)
    max_chunk_bytes: int = Field(
        default=DEFAULT_STREAM_MAX_CHUNK_BYTES,
        ge=1_024,
        le=64_000_000,
    )
    max_table_uncompressed_bytes: int = Field(
        default=DEFAULT_STREAM_MAX_TABLE_BYTES,
        ge=1_024,
        le=10_000_000_000,
    )
    max_bundle_uncompressed_bytes: int = Field(
        default=DEFAULT_STREAM_MAX_BUNDLE_BYTES,
        ge=1_024,
        le=20_000_000_000,
    )

    @model_validator(mode="after")
    def validate_nested_bounds(self) -> StreamingCanonicalisationConfig:
        if self.max_chunk_bytes > self.max_table_uncompressed_bytes:
            raise ValueError("max_chunk_bytes must not exceed max_table_uncompressed_bytes")
        if self.max_table_uncompressed_bytes > self.max_bundle_uncompressed_bytes:
            raise ValueError(
                "max_table_uncompressed_bytes must not exceed max_bundle_uncompressed_bytes"
            )
        return self


class CanonicalChunk(StreamingModel):
    """One synchronously consumed, provisional canonical output chunk."""

    schema_version: Literal["1.0"] = STREAMING_SCHEMA_VERSION
    source_kind: SourceTableKind
    source_file: str
    chunk_index: int = Field(ge=1)
    start_source_row: int = Field(ge=2)
    end_source_row: int | None = Field(default=None, ge=2)
    source_row_count: int = Field(ge=0)
    estimated_decoded_bytes: int = Field(ge=0)
    canonical: CanonicalTables

    @property
    def canonical_record_count(self) -> int:
        """Return the number of accepted records in this chunk."""

        return sum(self.canonical.record_counts().values())


class StreamingCanonicalisationSummary(StreamingModel):
    """Deterministic description of one completed chunked canonicalisation."""

    schema_version: Literal["1.0"] = STREAMING_SCHEMA_VERSION
    config: StreamingCanonicalisationConfig
    chunk_count: int = Field(ge=0)
    files_processed: list[str]
    source_row_counts: dict[str, int]
    canonical_record_counts: dict[str, int]
    max_observed_chunk_source_rows: int = Field(ge=0)
    max_observed_chunk_canonical_records: int = Field(ge=0)
    max_observed_chunk_decoded_bytes: int = Field(ge=0)
    disk_backed_global_checks: bool = True
    chunks_are_provisional_until_validation_completes: bool = True


class StreamingBundleValidationResult(StreamingModel):
    """Complete validation artifact without retaining all canonical rows in memory."""

    schema_version: Literal["1.0"] = STREAMING_SCHEMA_VERSION
    source: Path
    fingerprint: str | None
    manifest: BundleManifest | None
    seed: ScenarioSeed | None
    streaming: StreamingCanonicalisationSummary
    evidence: EvidenceAvailability
    insufficient_evidence: InsufficientEvidenceSummary
    report: ValidationReport

    def to_json(self) -> str:
        """Return deterministic formatted JSON apart from recorded validation time."""

        return self.model_dump_json(indent=2)


CanonicalChunkConsumer: TypeAlias = Callable[[CanonicalChunk], None]


class StreamingConsumerError(RuntimeError):
    """Raised when a caller-owned canonical chunk consumer fails."""


def canonicalise_bundle_streaming(
    root: Path,
    manifest: BundleManifest,
    report: ValidationReport,
    *,
    config: StreamingCanonicalisationConfig | None = None,
    consumer: CanonicalChunkConsumer | None = None,
) -> StreamingCanonicalisationSummary:
    """Canonicalise a bundle through bounded chunks and disk-backed global checks."""

    active_config = config or StreamingCanonicalisationConfig()
    output_consumer = consumer or _discard_chunk
    source_row_counts = dict.fromkeys(_SOURCE_KINDS, 0)
    canonical_counts = CanonicalTables().record_counts()
    chunk_count = 0
    max_source_rows = 0
    max_canonical_records = 0
    max_decoded_bytes = 0

    with _StreamingReconciliationIndex() as index:

        def emit(
            kind: str,
            source_file: str,
            chunk_index: int,
            start_source_row: int,
            source_row_count: int,
            estimated_decoded_bytes: int,
            tables: CanonicalTables,
        ) -> None:
            nonlocal chunk_count, max_source_rows, max_canonical_records, max_decoded_bytes
            source_kind = _source_kind(kind)
            source_row_counts[source_kind] += source_row_count
            counts = tables.record_counts()
            for table_name, count in counts.items():
                canonical_counts[table_name] += count
            end_source_row = start_source_row + source_row_count - 1 if source_row_count else None
            chunk = CanonicalChunk(
                source_kind=source_kind,
                source_file=source_file,
                chunk_index=chunk_index,
                start_source_row=start_source_row,
                end_source_row=end_source_row,
                source_row_count=source_row_count,
                estimated_decoded_bytes=estimated_decoded_bytes,
                canonical=tables,
            )
            index.add(chunk)
            try:
                output_consumer(chunk)
            except Exception as exc:
                raise StreamingConsumerError(
                    f"canonical chunk consumer failed for {source_file} chunk {chunk_index}"
                ) from exc
            chunk_count += 1
            max_source_rows = max(max_source_rows, source_row_count)
            max_canonical_records = max(max_canonical_records, chunk.canonical_record_count)
            max_decoded_bytes = max(max_decoded_bytes, estimated_decoded_bytes)

        GenericTabularAdapter().canonicalise_streaming(
            root,
            manifest,
            report,
            emit,
            chunk_rows=active_config.chunk_rows,
            max_table_uncompressed_bytes=active_config.max_table_uncompressed_bytes,
            max_chunk_bytes=active_config.max_chunk_bytes,
        )
        index.add_findings(report)

    return StreamingCanonicalisationSummary(
        config=active_config,
        chunk_count=chunk_count,
        files_processed=list(report.files_inspected),
        source_row_counts=source_row_counts,
        canonical_record_counts=canonical_counts,
        max_observed_chunk_source_rows=max_source_rows,
        max_observed_chunk_canonical_records=max_canonical_records,
        max_observed_chunk_decoded_bytes=max_decoded_bytes,
    )


class _StreamingReconciliationIndex:
    """Disk-backed exact state for cross-chunk and cross-table validation."""

    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="traffictwin-stream-state-")
        self._connection = sqlite3.connect(Path(self._temporary.name) / "state.sqlite")
        self._connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            PRAGMA temp_store=FILE;
            PRAGMA cache_size=-2048;
            CREATE TABLE task_ids (task_id TEXT PRIMARY KEY);
            CREATE TABLE duplicate_tasks (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                source_file TEXT NOT NULL,
                source_row INTEGER NOT NULL
            );
            CREATE TABLE task_refs (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                target_id TEXT,
                source_file TEXT NOT NULL,
                source_row INTEGER NOT NULL
            );
            CREATE TABLE vehicle_ids (vehicle_id TEXT PRIMARY KEY);
            CREATE TABLE rsu_ids (rsu_id TEXT PRIMARY KEY);
            """
        )

    def __enter__(self) -> _StreamingReconciliationIndex:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._connection.close()
        self._temporary.cleanup()

    def add(self, chunk: CanonicalChunk) -> None:
        for task in chunk.canonical.tasks:
            try:
                self._connection.execute("INSERT INTO task_ids VALUES (?)", (task.task_id,))
            except sqlite3.IntegrityError:
                self._connection.execute(
                    "INSERT INTO duplicate_tasks (task_id, source_file, source_row) "
                    "VALUES (?, ?, ?)",
                    (task.task_id, task.source_file, task.source_row),
                )
            self._connection.execute(
                "INSERT INTO task_refs "
                "(vehicle_id, decision, target_id, source_file, source_row) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    task.vehicle_id,
                    task.decision.value,
                    task.target_id,
                    task.source_file,
                    task.source_row,
                ),
            )
        self._connection.executemany(
            "INSERT OR IGNORE INTO vehicle_ids VALUES (?)",
            ((record.vehicle_id,) for record in chunk.canonical.vehicles),
        )
        self._connection.executemany(
            "INSERT OR IGNORE INTO rsu_ids VALUES (?)",
            ((record.rsu_id,) for record in chunk.canonical.infrastructure),
        )
        self._connection.commit()

    def add_findings(self, report: ValidationReport) -> None:
        self._add_duplicate_findings(report)
        self._add_unknown_vehicle_findings(report)
        self._add_unknown_rsu_findings(report)

    def _add_duplicate_findings(self, report: ValidationReport) -> None:
        rows = self._connection.execute(
            "SELECT task_id, source_file, source_row FROM duplicate_tasks ORDER BY seq"
        )
        for task_id, source_file, source_row in rows:
            report.add(
                ValidationFinding(
                    code=ValidationCode.TASK_ID_DUPLICATE,
                    severity=Severity.ERROR,
                    message="task_id must be unique within a run",
                    file=str(source_file),
                    row=int(source_row),
                    field="task_id",
                    value=str(task_id),
                    may_continue=False,
                )
            )

    def _add_unknown_vehicle_findings(self, report: ValidationReport) -> None:
        if not self._has_rows("vehicle_ids"):
            return
        rows = self._connection.execute(
            """
            SELECT t.vehicle_id, t.source_file, t.source_row
            FROM task_refs AS t
            LEFT JOIN vehicle_ids AS v ON v.vehicle_id = t.vehicle_id
            WHERE v.vehicle_id IS NULL
            ORDER BY t.seq
            """
        )
        for vehicle_id, source_file, source_row in rows:
            report.add(
                ValidationFinding(
                    code=ValidationCode.UNKNOWN_VEHICLE_REFERENCE,
                    severity=Severity.WARNING,
                    message="task vehicle_id is not present in vehicle_state records",
                    file=str(source_file),
                    row=int(source_row),
                    field="vehicle_id",
                    value=str(vehicle_id),
                    may_continue=True,
                    affected_capabilities=["vehicle_task_reconciliation"],
                )
            )

    def _add_unknown_rsu_findings(self, report: ValidationReport) -> None:
        if not self._has_rows("rsu_ids"):
            return
        rows = self._connection.execute(
            """
            SELECT t.target_id, t.source_file, t.source_row
            FROM task_refs AS t
            LEFT JOIN rsu_ids AS r ON r.rsu_id = t.target_id
            WHERE t.decision = ?
              AND t.target_id IS NOT NULL
              AND t.target_id != ''
              AND r.rsu_id IS NULL
            ORDER BY t.seq
            """,
            (Decision.V2I.value,),
        )
        for target_id, source_file, source_row in rows:
            report.add(
                ValidationFinding(
                    code=ValidationCode.UNKNOWN_RSU_REFERENCE,
                    severity=Severity.WARNING,
                    message="v2i task target_id is not present in infra_state records",
                    file=str(source_file),
                    row=int(source_row),
                    field="target_id",
                    value=str(target_id),
                    may_continue=True,
                    affected_capabilities=["infrastructure_task_reconciliation"],
                )
            )

    def _has_rows(self, table: Literal["vehicle_ids", "rsu_ids"]) -> bool:
        query = (
            "SELECT 1 FROM vehicle_ids LIMIT 1"
            if table == "vehicle_ids"
            else "SELECT 1 FROM rsu_ids LIMIT 1"
        )
        row = self._connection.execute(query).fetchone()
        return row is not None


def _source_kind(kind: str) -> SourceTableKind:
    if kind not in _SOURCE_KINDS:
        raise ValueError(f"unsupported streaming source kind: {kind}")
    return kind


def _discard_chunk(chunk: CanonicalChunk) -> None:
    del chunk


_SOURCE_KINDS: tuple[SourceTableKind, ...] = (
    "tasks",
    "infra_state",
    "vehicle_state",
    "traffic_obs",
    "trips",
    "incidents",
)
