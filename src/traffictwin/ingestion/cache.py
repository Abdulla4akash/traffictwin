"""Content-addressed, fail-closed canonical-table caching for generic bundles."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from traffictwin.adapters.generic_csv import (
    GENERIC_TABULAR_ADAPTER_ID,
    GENERIC_TABULAR_ADAPTER_VERSION,
)
from traffictwin.canonical.records import (
    CanonicalRecord,
    IncidentRecord,
    InfrastructureRecord,
    TaskRecord,
    TrafficObservationRecord,
    TripRecord,
    VehicleStateRecord,
)
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.availability import EvidenceAvailability
from traffictwin.evidence.insufficient import (
    InsufficientEvidenceSummary,
    build_insufficient_evidence_summary,
)
from traffictwin.ingestion.hashes import sha256_file
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.validation.report import VALIDATOR_VERSION, ValidationReport

CACHE_CAPABILITY_ID = "OPS-02"
CACHE_SCHEMA_VERSION = "1.0"
CACHE_CONTRACT_VERSION = "canonical-parquet-cache-v1"
CACHE_FORMAT_VERSION = "parquet-v1"
CACHE_ENTRY_FILENAME = "entry.json"
CACHE_METADATA_FILENAME = "validation.json"
MAX_CACHE_ENTRY_BYTES = 512_000_000
MAX_CACHE_DECODED_BYTES = 1_000_000_000
MAX_CACHE_TABLE_ROWS = 5_000_000
MAX_CACHE_METADATA_BYTES = 50_000_000


class CanonicalCacheError(RuntimeError):
    """Base class for visible canonical-cache failures."""


class CanonicalCacheConfigurationError(CanonicalCacheError):
    """Raised when the cache could mutate or overlap raw evidence."""


class CanonicalCacheCorruptError(CanonicalCacheError):
    """Raised when a cache entry fails its checksums or typed payload checks."""


class CanonicalCacheStaleError(CanonicalCacheError):
    """Raised when a cache entry does not match the requested raw/mapping identity."""


class CanonicalCacheIncompatibleError(CanonicalCacheError):
    """Raised when an entry was produced for an incompatible cache or code contract."""


class CacheModel(BaseModel):
    """Strict model base for cache operational artifacts."""

    model_config = ConfigDict(extra="forbid")


class CanonicalCacheState(StrEnum):
    """Observable state of one expected content-addressed cache entry."""

    HIT = "hit"
    MISS = "miss"
    WRITTEN = "written"
    STALE = "stale"
    INCOMPATIBLE = "incompatible"
    CORRUPT = "corrupt"
    UNAVAILABLE = "unavailable"
    WRITE_FAILED = "write_failed"


class CanonicalCacheKey(CacheModel):
    """Every semantic identity component required before cache reuse."""

    schema_version: str = CACHE_SCHEMA_VERSION
    cache_format_version: str = CACHE_FORMAT_VERSION
    raw_bundle_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    adapter_id: str
    adapter_version: str
    validator_version: str
    manifest_mapping_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    def canonical_json(self) -> str:
        """Return the byte-stable key representation."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the content-addressed cache entry identifier."""

        return _fingerprint(self.canonical_json().encode("utf-8"))


class CanonicalCacheFile(CacheModel):
    """Checksummed payload file descriptor."""

    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    table_name: str | None = None
    row_count: int | None = Field(default=None, ge=0)
    record_model: str | None = None


class CanonicalCacheEntry(CacheModel):
    """Self-describing manifest published after all payload files are complete."""

    schema_version: str = CACHE_SCHEMA_VERSION
    capability_id: str = CACHE_CAPABILITY_ID
    contract_version: str = CACHE_CONTRACT_VERSION
    entry_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    key: CanonicalCacheKey
    files: list[CanonicalCacheFile]

    def canonical_json(self) -> str:
        """Return a deterministic on-disk entry manifest."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete entry manifest."""

        return _fingerprint(self.canonical_json().encode("utf-8"))


class CanonicalCacheMetadata(CacheModel):
    """Non-table validation state needed to reproduce an accepted cold result."""

    schema_version: str = CACHE_SCHEMA_VERSION
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest: BundleManifest
    seed: ScenarioSeed
    evidence: EvidenceAvailability
    insufficient_evidence: InsufficientEvidenceSummary
    report: ValidationReport


class CanonicalCacheStatus(CacheModel):
    """Read-only or write receipt for one requested cache identity."""

    schema_version: str = CACHE_SCHEMA_VERSION
    capability_id: str = CACHE_CAPABILITY_ID
    contract_version: str = CACHE_CONTRACT_VERSION
    state: CanonicalCacheState
    cache_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cache_entry: str | None = None
    detail: str
    verified_files: int = Field(default=0, ge=0)
    record_counts: dict[str, int] = Field(default_factory=dict)
    entry_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class CanonicalCacheContract(CacheModel):
    """Machine-readable OPS-02 cache boundary."""

    schema_version: str = CACHE_SCHEMA_VERSION
    capability_id: str = CACHE_CAPABILITY_ID
    contract_version: str = CACHE_CONTRACT_VERSION
    adapter_id: str = GENERIC_TABULAR_ADAPTER_ID
    adapter_version: str = GENERIC_TABULAR_ADAPTER_VERSION
    validator_version: str = VALIDATOR_VERSION
    cache_format: str = "Apache Parquet 2.6 with strict Pydantic revalidation"
    cache_format_version: str = CACHE_FORMAT_VERSION
    canonical_schema_fingerprint: str
    key_components: list[str]
    canonical_tables: list[str]
    maximum_entry_bytes: int = MAX_CACHE_ENTRY_BYTES
    maximum_decoded_bytes_per_table: int = MAX_CACHE_DECODED_BYTES
    maximum_rows_per_table: int = MAX_CACHE_TABLE_ROWS
    raw_evidence_policy: str
    invalidation_policy: str
    publication_policy: str

    def canonical_json(self) -> str:
        """Return a byte-stable public contract."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the public contract."""

        return _fingerprint(self.canonical_json().encode("utf-8"))


@dataclass(frozen=True)
class CanonicalCachePayload:
    """Verified cached state used to reconstruct one validation result."""

    metadata: CanonicalCacheMetadata
    canonical: CanonicalTables


@dataclass(frozen=True)
class CanonicalCacheProbe:
    """One fail-closed cache probe and its optional verified payload."""

    status: CanonicalCacheStatus
    payload: CanonicalCachePayload | None = None


@dataclass(frozen=True)
class _TableSpec:
    name: str
    model: type[CanonicalRecord]
    schema: pa.Schema

    @property
    def filename(self) -> str:
        return f"{self.name}.parquet"


def _field(name: str, type_: pa.DataType, *, nullable: bool = True) -> pa.Field:
    return pa.field(name, type_, nullable=nullable)


_PROVENANCE_FIELDS = (
    _field("source_file", pa.string(), nullable=False),
    _field("source_row", pa.int64(), nullable=False),
)

_TABLE_SPECS: tuple[_TableSpec, ...] = (
    _TableSpec(
        "tasks",
        TaskRecord,
        pa.schema(
            [
                *_PROVENANCE_FIELDS,
                _field("task_id", pa.string(), nullable=False),
                _field("vehicle_id", pa.string(), nullable=False),
                _field("task_class", pa.string(), nullable=False),
                _field("arrival_time_s", pa.float64(), nullable=False),
                _field("deadline_ms", pa.float64(), nullable=False),
                _field("decision", pa.string(), nullable=False),
                _field("completed", pa.bool_(), nullable=False),
                _field("completion_time_s", pa.float64()),
                _field("latency_ms", pa.float64()),
                _field("target_id", pa.string()),
                _field("workload_cycles", pa.float64()),
                _field("data_size_bytes", pa.float64()),
                _field("energy_j", pa.float64()),
                _field("drop_reason", pa.string()),
            ]
        ),
    ),
    _TableSpec(
        "infrastructure",
        InfrastructureRecord,
        pa.schema(
            [
                *_PROVENANCE_FIELDS,
                _field("timestamp_s", pa.float64(), nullable=False),
                _field("rsu_id", pa.string(), nullable=False),
                _field("queue_length", pa.float64()),
                _field("utilisation_fraction", pa.float64()),
                _field("arrivals", pa.int64()),
                _field("active_tasks", pa.int64()),
                _field("drops", pa.int64()),
                _field("capacity", pa.float64()),
            ]
        ),
    ),
    _TableSpec(
        "vehicles",
        VehicleStateRecord,
        pa.schema(
            [
                *_PROVENANCE_FIELDS,
                _field("timestamp_s", pa.float64(), nullable=False),
                _field("vehicle_id", pa.string(), nullable=False),
                _field("x", pa.float64()),
                _field("y", pa.float64()),
                _field("speed_mps", pa.float64()),
                _field("lane", pa.string()),
                _field("tier", pa.string()),
            ]
        ),
    ),
    _TableSpec(
        "traffic",
        TrafficObservationRecord,
        pa.schema(
            [
                *_PROVENANCE_FIELDS,
                _field("timestamp_s", pa.float64(), nullable=False),
                _field("sensor_id", pa.string(), nullable=False),
                _field("count", pa.int64()),
                _field("average_speed_mps", pa.float64()),
                _field("location", pa.string()),
            ]
        ),
    ),
    _TableSpec(
        "trips",
        TripRecord,
        pa.schema(
            [
                *_PROVENANCE_FIELDS,
                _field("trip_id", pa.string(), nullable=False),
                _field("vehicle_id", pa.string()),
                _field("departure_time_s", pa.float64(), nullable=False),
                _field("arrival_time_s", pa.float64()),
                _field("duration_s", pa.float64()),
                _field("route_id", pa.string()),
            ]
        ),
    ),
    _TableSpec(
        "incidents",
        IncidentRecord,
        pa.schema(
            [
                *_PROVENANCE_FIELDS,
                _field("incident_id", pa.string(), nullable=False),
                _field("timestamp_s", pa.float64(), nullable=False),
                _field("incident_type", pa.string(), nullable=False),
                _field("location", pa.string()),
                _field("severity", pa.string()),
                _field("duration_s", pa.float64()),
                _field("lanes_closed", pa.int64()),
                _field("demand_multiplier", pa.float64()),
                _field("vehicles_involved", pa.list_(pa.string()), nullable=False),
            ]
        ),
    ),
)


def canonical_cache_contract() -> CanonicalCacheContract:
    """Return the current generic-bundle canonical-cache contract."""

    return CanonicalCacheContract(
        canonical_schema_fingerprint=canonical_schema_fingerprint(),
        key_components=[
            "raw_bundle_fingerprint",
            "adapter_id",
            "adapter_version",
            "validator_version",
            "manifest_mapping_fingerprint",
            "canonical_schema_fingerprint",
            "cache_format_version",
        ],
        canonical_tables=[spec.name for spec in _TABLE_SPECS],
        raw_evidence_policy=(
            "Cache roots must remain outside directory bundles. Every lookup reopens and "
            "fingerprints raw evidence; cached files never replace or modify it."
        ),
        invalidation_policy=(
            "Any raw, adapter, validator, confirmed mapping, canonical schema, or cache-format "
            "identity change produces a miss; stale, incompatible, corrupt, or symlinked entries "
            "are never used."
        ),
        publication_policy=(
            "Only accepted validation results are written to a private temporary directory, "
            "checksummed, verified, and atomically renamed. Existing entries are not rewritten."
        ),
    )


def canonical_schema_fingerprint() -> str:
    """Fingerprint exact canonical Pydantic and Arrow table schemas."""

    payload = {
        spec.name: {
            "model": spec.model.__name__,
            "pydantic_schema": spec.model.model_json_schema(),
            "arrow_schema": [
                {
                    "name": field.name,
                    "nullable": field.nullable,
                    "type": str(field.type),
                }
                for field in spec.schema
            ],
        }
        for spec in _TABLE_SPECS
    }
    return _fingerprint(_canonical_json(payload).encode("utf-8"))


def manifest_mapping_fingerprint(manifest: BundleManifest) -> str:
    """Fingerprint every declaration and confirmation datum used for canonical mapping."""

    mapping = {
        "schema_version": manifest.schema_version,
        "files": {
            kind: declaration.model_dump(mode="json")
            for kind, declaration in sorted(manifest.files.items())
        },
        "canonicalisation": (
            manifest.canonicalisation.model_dump(mode="json")
            if manifest.canonicalisation is not None
            else None
        ),
        "energy_contract": (
            manifest.energy_contract.model_dump(mode="json")
            if manifest.energy_contract is not None
            else None
        ),
        "task_rsu_target_contract": (
            manifest.task_rsu_target_contract.model_dump(mode="json")
            if manifest.task_rsu_target_contract is not None
            else None
        ),
        "vehicle_spatial_grid_contract": (
            manifest.vehicle_spatial_grid_contract.model_dump(mode="json")
            if manifest.vehicle_spatial_grid_contract is not None
            else None
        ),
    }
    return _fingerprint(_canonical_json(mapping).encode("utf-8"))


def canonical_cache_key(
    raw_bundle_fingerprint: str,
    manifest: BundleManifest,
    *,
    adapter_id: str = GENERIC_TABULAR_ADAPTER_ID,
    adapter_version: str = GENERIC_TABULAR_ADAPTER_VERSION,
    validator_version: str = VALIDATOR_VERSION,
    schema_fingerprint: str | None = None,
    cache_format_version: str = CACHE_FORMAT_VERSION,
) -> CanonicalCacheKey:
    """Build the complete key for one raw bundle and canonicalisation contract."""

    return CanonicalCacheKey(
        cache_format_version=cache_format_version,
        raw_bundle_fingerprint=raw_bundle_fingerprint,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        validator_version=validator_version,
        manifest_mapping_fingerprint=manifest_mapping_fingerprint(manifest),
        canonical_schema_fingerprint=schema_fingerprint or canonical_schema_fingerprint(),
    )


def validate_cache_location(source: Path, cache_root: Path) -> Path:
    """Resolve a cache root and reject raw-bundle overlap or symbolic-link roots."""

    if cache_root.is_symlink():
        raise CanonicalCacheConfigurationError(
            f"cache root must not be a symbolic link: {cache_root}"
        )
    resolved_cache = cache_root.expanduser().resolve(strict=False)
    resolved_source = source.expanduser().resolve(strict=False)
    if source.is_dir() and (
        resolved_cache == resolved_source or resolved_cache.is_relative_to(resolved_source)
    ):
        raise CanonicalCacheConfigurationError(
            "cache root must be outside the raw directory bundle"
        )
    if resolved_cache.exists() and not resolved_cache.is_dir():
        raise CanonicalCacheConfigurationError(f"cache root must be a directory: {resolved_cache}")
    return resolved_cache


def probe_canonical_cache(
    cache_root: Path,
    key: CanonicalCacheKey,
    *,
    manifest: BundleManifest,
) -> CanonicalCacheProbe:
    """Verify and read one exact cache entry without modifying cache state."""

    entry_path = cache_root / key.fingerprint()
    if not entry_path.exists():
        return CanonicalCacheProbe(
            status=_status(
                CanonicalCacheState.MISS,
                key,
                entry_path,
                "no entry exists for the complete current cache key",
            )
        )
    try:
        payload, entry = _load_entry(entry_path, key, manifest)
    except CanonicalCacheStaleError as exc:
        return CanonicalCacheProbe(
            status=_status(CanonicalCacheState.STALE, key, entry_path, str(exc))
        )
    except CanonicalCacheIncompatibleError as exc:
        return CanonicalCacheProbe(
            status=_status(CanonicalCacheState.INCOMPATIBLE, key, entry_path, str(exc))
        )
    except CanonicalCacheCorruptError as exc:
        return CanonicalCacheProbe(
            status=_status(CanonicalCacheState.CORRUPT, key, entry_path, str(exc))
        )
    except OSError as exc:
        return CanonicalCacheProbe(
            status=_status(
                CanonicalCacheState.CORRUPT,
                key,
                entry_path,
                f"cache entry could not be read safely: {exc}",
            )
        )
    return CanonicalCacheProbe(
        status=_status(
            CanonicalCacheState.HIT,
            key,
            entry_path,
            "entry checksums, typed rows, and identities verified",
            verified_files=len(entry.files),
            record_counts=payload.canonical.record_counts(),
            entry_fingerprint=entry.fingerprint(),
        ),
        payload=payload,
    )


def write_canonical_cache(
    cache_root: Path,
    key: CanonicalCacheKey,
    *,
    manifest: BundleManifest,
    seed: ScenarioSeed,
    canonical: CanonicalTables,
    evidence: EvidenceAvailability,
    insufficient_evidence: InsufficientEvidenceSummary,
    report: ValidationReport,
) -> CanonicalCacheProbe:
    """Atomically publish one accepted validation result, or reuse an existing valid entry."""

    _validate_write_payload(key, manifest, canonical, report)
    cache_root.mkdir(parents=True, exist_ok=True)
    if cache_root.is_symlink() or not cache_root.is_dir():
        raise CanonicalCacheConfigurationError(f"unsafe cache root: {cache_root}")
    existing = probe_canonical_cache(cache_root, key, manifest=manifest)
    if existing.status.state is CanonicalCacheState.HIT:
        return existing
    if existing.status.state is not CanonicalCacheState.MISS:
        raise CanonicalCacheError(
            "refusing to overwrite an existing non-valid cache entry: "
            f"{existing.status.state.value}: {existing.status.detail}"
        )

    entry_id = key.fingerprint()
    temporary = Path(tempfile.mkdtemp(prefix=f".{entry_id}.tmp-", dir=cache_root))
    entry_path = cache_root / entry_id
    try:
        descriptors = _write_payload_files(
            temporary,
            key,
            manifest,
            seed,
            canonical,
            evidence,
            insufficient_evidence,
            report,
        )
        entry = CanonicalCacheEntry(entry_id=entry_id, key=key, files=descriptors)
        _write_bytes(
            temporary / CACHE_ENTRY_FILENAME,
            (entry.canonical_json() + "\n").encode("utf-8"),
        )
        _sync_directory(temporary)
        verified, _ = _load_entry(
            temporary,
            key,
            manifest,
            enforce_directory_identity=False,
        )
        if verified.canonical != canonical:
            raise CanonicalCacheCorruptError("written canonical tables failed exact verification")
        try:
            temporary.rename(entry_path)
        except OSError as exc:
            if not entry_path.exists():
                raise
            concurrent = probe_canonical_cache(cache_root, key, manifest=manifest)
            if concurrent.status.state is CanonicalCacheState.HIT:
                shutil.rmtree(temporary, ignore_errors=True)
                return concurrent
            raise CanonicalCacheError(
                "a concurrent writer published an invalid cache entry"
            ) from exc
        _sync_directory(cache_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    published = probe_canonical_cache(cache_root, key, manifest=manifest)
    if published.payload is None:
        raise CanonicalCacheCorruptError("published cache entry could not be verified")
    status = published.status.model_copy(
        update={
            "state": CanonicalCacheState.WRITTEN,
            "detail": "accepted canonical tables were verified and atomically published",
        }
    )
    return CanonicalCacheProbe(status=status, payload=published.payload)


def unavailable_cache_status(
    detail: str,
    key: CanonicalCacheKey | None = None,
) -> CanonicalCacheStatus:
    """Build an explicit status for a bundle that cannot use the cache."""

    return CanonicalCacheStatus(
        state=CanonicalCacheState.UNAVAILABLE,
        cache_key=key.fingerprint() if key is not None else None,
        detail=detail,
    )


def write_failed_cache_status(
    detail: str,
    cache_root: Path,
    key: CanonicalCacheKey,
) -> CanonicalCacheStatus:
    """Build a visible failed-write receipt while retaining the cold validation result."""

    return _status(
        CanonicalCacheState.WRITE_FAILED,
        key,
        cache_root / key.fingerprint(),
        detail,
    )


def _write_payload_files(
    destination: Path,
    key: CanonicalCacheKey,
    manifest: BundleManifest,
    seed: ScenarioSeed,
    canonical: CanonicalTables,
    evidence: EvidenceAvailability,
    insufficient_evidence: InsufficientEvidenceSummary,
    report: ValidationReport,
) -> list[CanonicalCacheFile]:
    descriptors: list[CanonicalCacheFile] = []
    for spec in _TABLE_SPECS:
        records = list(getattr(canonical, spec.name))
        rows = [record.model_dump(mode="json") for record in records]
        table = pa.Table.from_pylist(rows, schema=spec.schema)
        path = destination / spec.filename
        pq.write_table(
            table,
            path,
            version="2.6",
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        _sync_file(path)
        descriptors.append(
            CanonicalCacheFile(
                filename=spec.filename,
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
                table_name=spec.name,
                row_count=len(records),
                record_model=spec.model.__name__,
            )
        )

    metadata = CanonicalCacheMetadata(
        source_fingerprint=key.raw_bundle_fingerprint,
        manifest=manifest,
        seed=seed,
        evidence=evidence,
        insufficient_evidence=insufficient_evidence,
        report=report,
    )
    metadata_path = destination / CACHE_METADATA_FILENAME
    _write_bytes(
        metadata_path,
        (_canonical_json(metadata.model_dump(mode="json")) + "\n").encode("utf-8"),
    )
    descriptors.append(
        CanonicalCacheFile(
            filename=CACHE_METADATA_FILENAME,
            sha256=sha256_file(metadata_path),
            size_bytes=metadata_path.stat().st_size,
        )
    )
    return descriptors


def _load_entry(
    entry_path: Path,
    expected_key: CanonicalCacheKey,
    expected_manifest: BundleManifest,
    *,
    enforce_directory_identity: bool = True,
) -> tuple[CanonicalCachePayload, CanonicalCacheEntry]:
    if entry_path.is_symlink() or not entry_path.is_dir():
        raise CanonicalCacheCorruptError("cache entry must be a direct, non-symlink directory")
    manifest_path = entry_path / CACHE_ENTRY_FILENAME
    raw_entry = _read_json_object(manifest_path, maximum_bytes=1_000_000)
    if raw_entry.get("contract_version") != CACHE_CONTRACT_VERSION:
        raise CanonicalCacheIncompatibleError("cache contract version does not match this build")
    if raw_entry.get("schema_version") != CACHE_SCHEMA_VERSION:
        raise CanonicalCacheIncompatibleError("cache schema version does not match this build")
    try:
        entry = CanonicalCacheEntry.model_validate(raw_entry)
    except ValidationError as exc:
        raise CanonicalCacheCorruptError(f"cache entry manifest is invalid: {exc}") from exc
    if enforce_directory_identity and entry.entry_id != entry_path.name:
        raise CanonicalCacheStaleError("entry directory name does not match its declared identity")
    if entry.key != expected_key or entry.entry_id != expected_key.fingerprint():
        if _incompatible_key(entry.key, expected_key):
            raise CanonicalCacheIncompatibleError(
                "entry adapter, validator, schema, or format identity is incompatible"
            )
        raise CanonicalCacheStaleError("entry raw fingerprint or manifest mapping is stale")

    expected_files = {CACHE_METADATA_FILENAME, *(spec.filename for spec in _TABLE_SPECS)}
    described_files = [descriptor.filename for descriptor in entry.files]
    if len(set(described_files)) != len(described_files) or set(described_files) != expected_files:
        raise CanonicalCacheCorruptError("cache payload inventory is incomplete or duplicated")
    actual_files = {path.name for path in entry_path.iterdir() if path.name != CACHE_ENTRY_FILENAME}
    if actual_files != expected_files:
        raise CanonicalCacheCorruptError("cache directory contains missing or unexpected payloads")
    if sum(descriptor.size_bytes for descriptor in entry.files) > MAX_CACHE_ENTRY_BYTES:
        raise CanonicalCacheCorruptError("cache entry exceeds the published byte limit")
    for descriptor in entry.files:
        _verify_file(entry_path, descriptor)

    metadata_descriptor = next(
        item for item in entry.files if item.filename == CACHE_METADATA_FILENAME
    )
    if metadata_descriptor.size_bytes > MAX_CACHE_METADATA_BYTES:
        raise CanonicalCacheCorruptError("cache validation metadata exceeds the published limit")
    raw_metadata = _read_json_object(
        entry_path / CACHE_METADATA_FILENAME,
        maximum_bytes=MAX_CACHE_METADATA_BYTES,
    )
    try:
        metadata = CanonicalCacheMetadata.model_validate(raw_metadata)
    except ValidationError as exc:
        raise CanonicalCacheCorruptError(f"cached validation metadata is invalid: {exc}") from exc
    if metadata.source_fingerprint != expected_key.raw_bundle_fingerprint:
        raise CanonicalCacheStaleError("cached validation source fingerprint is stale")
    if metadata.manifest != expected_manifest:
        raise CanonicalCacheStaleError("cached manifest is not the current raw manifest")
    if metadata.seed.seed_id != expected_manifest.run.seed_id:
        raise CanonicalCacheCorruptError("cached seed identity does not match the manifest")
    if metadata.report.validator_version != expected_key.validator_version:
        raise CanonicalCacheIncompatibleError("cached validation report version is incompatible")
    derived_report = metadata.report.model_copy(deep=True)
    derived_report.finalise()
    if (
        derived_report.status != metadata.report.status
        or derived_report.may_import != metadata.report.may_import
        or derived_report.counts_by_severity != metadata.report.counts_by_severity
    ):
        raise CanonicalCacheCorruptError("cached validation report summary is inconsistent")
    if not metadata.report.may_import:
        raise CanonicalCacheCorruptError("rejected validation state is not cache-admissible")
    if metadata.report.available_evidence_categories != metadata.evidence.available_categories():
        raise CanonicalCacheCorruptError("cached available-evidence summary is inconsistent")
    if (
        metadata.report.unavailable_evidence_categories
        != metadata.evidence.unavailable_categories()
    ):
        raise CanonicalCacheCorruptError("cached unavailable-evidence summary is inconsistent")
    if metadata.insufficient_evidence != build_insufficient_evidence_summary(
        metadata.report,
        metadata.evidence,
    ):
        raise CanonicalCacheCorruptError("cached insufficient-evidence summary is inconsistent")

    table_payload: dict[str, Any] = {}
    for spec in _TABLE_SPECS:
        descriptor = next(item for item in entry.files if item.table_name == spec.name)
        if descriptor.record_model != spec.model.__name__:
            raise CanonicalCacheIncompatibleError(
                f"cached {spec.name} record model is incompatible"
            )
        if descriptor.row_count is None or descriptor.row_count > MAX_CACHE_TABLE_ROWS:
            raise CanonicalCacheCorruptError(f"cached {spec.name} row count exceeds the limit")
        table_payload[spec.name] = _read_table(entry_path / spec.filename, descriptor, spec)
    try:
        canonical = CanonicalTables.model_validate(table_payload)
    except ValidationError as exc:
        raise CanonicalCacheCorruptError(f"cached canonical tables are invalid: {exc}") from exc
    counts = canonical.record_counts()
    if counts != metadata.report.canonical_record_counts:
        raise CanonicalCacheCorruptError(
            "cached canonical counts do not match the validation report"
        )
    return CanonicalCachePayload(metadata=metadata, canonical=canonical), entry


def _read_table(
    path: Path,
    descriptor: CanonicalCacheFile,
    spec: _TableSpec,
) -> list[CanonicalRecord]:
    try:
        parquet = pq.ParquetFile(path)
        metadata_rows = parquet.metadata.num_rows
        if metadata_rows != descriptor.row_count:
            raise CanonicalCacheCorruptError(
                f"cached {spec.name} Parquet row count does not match its manifest"
            )
        decoded_bytes = sum(
            parquet.metadata.row_group(index).total_byte_size
            for index in range(parquet.metadata.num_row_groups)
        )
        if decoded_bytes > MAX_CACHE_DECODED_BYTES:
            raise CanonicalCacheCorruptError(
                f"cached {spec.name} decoded size exceeds the published limit"
            )
        table = parquet.read()
    except CanonicalCacheCorruptError:
        raise
    except Exception as exc:
        raise CanonicalCacheCorruptError(
            f"cached {spec.name} Parquet payload is unreadable: {exc}"
        ) from exc
    if not table.schema.equals(spec.schema, check_metadata=False):
        raise CanonicalCacheIncompatibleError(f"cached {spec.name} Arrow schema is incompatible")
    records: list[CanonicalRecord] = []
    try:
        for row in table.to_pylist():
            records.append(spec.model.model_validate(row))
    except ValidationError as exc:
        raise CanonicalCacheCorruptError(f"cached {spec.name} row is invalid: {exc}") from exc
    return records


def _validate_write_payload(
    key: CanonicalCacheKey,
    manifest: BundleManifest,
    canonical: CanonicalTables,
    report: ValidationReport,
) -> None:
    current_key = canonical_cache_key(key.raw_bundle_fingerprint, manifest)
    if key != current_key:
        raise CanonicalCacheIncompatibleError(
            "cache writes require the current adapter, validator, schema, mapping, and format key"
        )
    if not report.may_import:
        raise CanonicalCacheError("rejected validation results are never cached")
    if canonical.record_counts() != report.canonical_record_counts:
        raise CanonicalCacheError("canonical counts do not match the accepted validation report")
    if any(count > MAX_CACHE_TABLE_ROWS for count in canonical.record_counts().values()):
        raise CanonicalCacheError("canonical table exceeds the published cache row limit")


def _verify_file(entry_path: Path, descriptor: CanonicalCacheFile) -> None:
    if Path(descriptor.filename).name != descriptor.filename:
        raise CanonicalCacheCorruptError("cache payload filename is not a safe basename")
    path = entry_path / descriptor.filename
    if path.is_symlink() or not path.is_file():
        raise CanonicalCacheCorruptError(
            f"cache payload must be a direct, non-symlink file: {descriptor.filename}"
        )
    actual_size = path.stat().st_size
    if actual_size != descriptor.size_bytes:
        raise CanonicalCacheCorruptError(f"cache payload size mismatch: {descriptor.filename}")
    if sha256_file(path) != descriptor.sha256:
        raise CanonicalCacheCorruptError(f"cache payload checksum mismatch: {descriptor.filename}")


def _incompatible_key(actual: CanonicalCacheKey, expected: CanonicalCacheKey) -> bool:
    return any(
        actual_value != expected_value
        for actual_value, expected_value in (
            (actual.schema_version, expected.schema_version),
            (actual.cache_format_version, expected.cache_format_version),
            (actual.adapter_id, expected.adapter_id),
            (actual.adapter_version, expected.adapter_version),
            (actual.validator_version, expected.validator_version),
            (actual.canonical_schema_fingerprint, expected.canonical_schema_fingerprint),
        )
    )


def _status(
    state: CanonicalCacheState,
    key: CanonicalCacheKey,
    entry_path: Path,
    detail: str,
    *,
    verified_files: int = 0,
    record_counts: dict[str, int] | None = None,
    entry_fingerprint: str | None = None,
) -> CanonicalCacheStatus:
    return CanonicalCacheStatus(
        state=state,
        cache_key=key.fingerprint(),
        cache_entry=str(entry_path),
        detail=detail,
        verified_files=verified_files,
        record_counts=record_counts or {},
        entry_fingerprint=entry_fingerprint,
    )


def _read_json_object(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CanonicalCacheCorruptError(
            f"cache metadata file is missing or symlinked: {path.name}"
        )
    if path.stat().st_size > maximum_bytes:
        raise CanonicalCacheCorruptError(f"cache metadata file is too large: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CanonicalCacheCorruptError(f"cache metadata file is unreadable: {path.name}") from exc
    if not isinstance(value, dict):
        raise CanonicalCacheCorruptError(f"cache metadata must be a JSON object: {path.name}")
    return value


def _write_bytes(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _sync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _sync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fingerprint(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
