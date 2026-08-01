"""Owner-delegated local persistence for the aggregate historical store.

The Phase-147 engine-neutral contract remains authoritative.  This module adds
one conservative adapter: a local SQLite catalogue plus immutable
content-addressed aggregate JSON beneath an owner workspace.  Runtime state is
never written to the repository, registered content is never automatically
deleted, and every public result omits the private workspace path.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator

from traffictwin.platform.historical_store import (
    AuthoritativeSourceRecord,
    CatalogueQuery,
    DatasetRegistrationCandidate,
    DatasetSchemaContract,
    FeatureDefinition,
    FeatureMaterialisationRequest,
    FeatureReceipt,
    FeatureSnapshot,
    FeatureSnapshotCandidate,
    HistoricalDatasetRecord,
    InMemoryHistoricalStore,
    MigrationDryRunReport,
    ProvenanceWalk,
    StoreModel,
    StoreReceipt,
    StoreRefusal,
)

PERSISTENCE_METHOD_VERSION: Literal["aggregate-historical-store-sqlite-1.0"] = (
    "aggregate-historical-store-sqlite-1.0"
)
SQLITE_SCHEMA_VERSION = 1
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_json(value: object) -> str:
    return _digest_bytes(_canonical_json(value).encode("utf-8"))


class PersistentRefusalCode(StrEnum):
    WORKSPACE_INSIDE_REPOSITORY = "WORKSPACE_INSIDE_REPOSITORY"
    WORKSPACE_UNAVAILABLE = "WORKSPACE_UNAVAILABLE"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    CATALOGUE_CORRUPT = "CATALOGUE_CORRUPT"
    PAYLOAD_MISSING = "PAYLOAD_MISSING"
    PAYLOAD_CORRUPT = "PAYLOAD_CORRUPT"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    BACKUP_LABEL_INVALID = "BACKUP_LABEL_INVALID"


class LicenceAllowlistPolicy(StoreModel):
    """Exact, versioned and fail-closed; private permission text is never stored."""

    policy_version: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    allowed_classes: tuple[str, ...] = Field(min_length=1)
    matching: Literal["exact"] = "exact"
    fail_closed: Literal[True] = True
    private_permission_text_stored: Literal[False] = False

    @field_validator("allowed_classes")
    @classmethod
    def validate_classes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("licence classes must be unique")
        if any(not value.strip() or value != value.strip() for value in values):
            raise ValueError("licence classes must be non-empty canonical strings")
        return values

    @property
    def policy_digest(self) -> str:
        return self.fingerprint()


class PersistentStoragePolicy(StoreModel):
    method_version: Literal["aggregate-historical-store-sqlite-1.0"] = PERSISTENCE_METHOD_VERSION
    catalogue_engine: Literal["sqlite"] = "sqlite"
    sqlite_journal_mode: Literal["delete"] = "delete"
    sqlite_synchronous: Literal["full"] = "full"
    payload_format: Literal["aggregate_json"] = "aggregate_json"
    workspace_layout: Literal[
        "historical-store/{catalogue.sqlite,payloads/sha256,staging,backups}"
    ] = "historical-store/{catalogue.sqlite,payloads/sha256,staging,backups}"
    retention: Literal["owner_confirmed_digest_only"] = "owner_confirmed_digest_only"
    automatic_deletion: Literal[False] = False
    preserve_catalogue_tombstones: Literal[True] = True
    backup: Literal["explicit_integrity_verified"] = "explicit_integrity_verified"
    runtime_catalogue_committed: Literal[False] = False
    network_service: Literal[False] = False
    evidence: Literal[False] = False
    production_ready: Literal[False] = False


class PersistentStoreRefusal(StoreModel):
    operation: Literal[
        "open",
        "register_dataset",
        "register_feature",
        "materialise_snapshot",
        "create_backup",
    ]
    code: PersistentRefusalCode
    message: str
    subject_id: str
    state_changed: Literal[False] = False
    path_exposed: Literal[False] = False
    evidence: Literal[False] = False


class RecoveryReport(StoreModel):
    method_version: Literal["aggregate-historical-store-sqlite-1.0"] = PERSISTENCE_METHOD_VERSION
    catalogue_integrity: Literal["ok"] = "ok"
    referenced_payload_count: int = Field(ge=0)
    orphan_payload_digests: tuple[str, ...]
    missing_payload_digests: tuple[str, ...]
    corrupt_payload_digests: tuple[str, ...]
    staged_file_count: int = Field(ge=0)
    unexpected_file_count: int = Field(ge=0)
    automatic_deletion_performed: Literal[False] = False
    safe_to_open: bool
    evidence: Literal[False] = False


class BackupReceipt(StoreModel):
    method_version: Literal["aggregate-historical-store-sqlite-1.0"] = PERSISTENCE_METHOD_VERSION
    backup_handle: str = Field(pattern=r"^backups/[a-z0-9][a-z0-9._-]*$")
    backup_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalogue_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_count: int = Field(ge=0)
    manifest_verified: Literal[True] = True
    catalogue_integrity_verified: Literal[True] = True
    automatic_deletion: Literal[False] = False
    idempotent_retry: bool
    evidence: Literal[False] = False
    production_ready: Literal[False] = False


@dataclass(frozen=True, repr=False)
class SQLiteStoreConfig:
    """Private local paths are configuration, never catalogue/output fields."""

    owner_workspace: Path
    repository_root: Path


@dataclass(frozen=True, repr=False)
class _Layout:
    root: Path
    catalogue: Path
    payloads: Path
    staging: Path
    backups: Path

    @classmethod
    def create(cls, config: SQLiteStoreConfig) -> _Layout:
        repository = config.repository_root.resolve()
        root = (config.owner_workspace.resolve() / "historical-store").resolve()
        try:
            root.relative_to(repository)
        except ValueError:
            pass
        else:
            raise ValueError("workspace must remain outside the repository")
        payloads = root / "payloads" / "sha256"
        staging = root / "staging"
        backups = root / "backups"
        for directory in (root, payloads, staging, backups):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        return cls(
            root=root,
            catalogue=root / "catalogue.sqlite",
            payloads=payloads,
            staging=staging,
            backups=backups,
        )


class _OpenError(RuntimeError):
    def __init__(self, code: PersistentRefusalCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


class SQLiteHistoricalStore:
    """Local persistent adapter over the Phase-147 engine-neutral contract."""

    policy = PersistentStoragePolicy()

    def __init__(
        self,
        *,
        layout: _Layout,
        connection: sqlite3.Connection,
        schemas: tuple[DatasetSchemaContract, ...],
        authoritative_sources: tuple[AuthoritativeSourceRecord, ...],
        licence_policy: LicenceAllowlistPolicy,
        fault_hook: Callable[[str, str], None] | None,
        recovery_report: RecoveryReport,
        core: InMemoryHistoricalStore,
    ) -> None:
        self._layout = layout
        self._connection = connection
        self._schemas = schemas
        self._authoritative_sources = authoritative_sources
        self._licence_policy = licence_policy
        self._fault_hook = fault_hook
        self._recovery_report = recovery_report
        self._core = core
        self._lock = threading.RLock()

    @classmethod
    def open(
        cls,
        *,
        config: SQLiteStoreConfig,
        schemas: Sequence[DatasetSchemaContract],
        authoritative_sources: Sequence[AuthoritativeSourceRecord],
        licence_policy: LicenceAllowlistPolicy,
        fault_hook: Callable[[str, str], None] | None = None,
    ) -> Self | PersistentStoreRefusal:
        try:
            layout = _Layout.create(config)
        except ValueError:
            return PersistentStoreRefusal(
                operation="open",
                code=PersistentRefusalCode.WORKSPACE_INSIDE_REPOSITORY,
                message="persistent workspace must remain outside the repository",
                subject_id="historical-store",
            )
        except OSError:
            return PersistentStoreRefusal(
                operation="open",
                code=PersistentRefusalCode.WORKSPACE_UNAVAILABLE,
                message="persistent workspace is unavailable",
                subject_id="historical-store",
            )
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                layout.catalogue,
                isolation_level=None,
                check_same_thread=False,
                timeout=30.0,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA trusted_schema = OFF")
            cls._initialize_catalogue(connection)
            with suppress(OSError):
                layout.catalogue.chmod(0o600)
            schema_tuple = tuple(schemas)
            source_tuple = tuple(authoritative_sources)
            cls._bind_or_verify_contract(
                connection,
                schemas=schema_tuple,
                authoritative_sources=source_tuple,
                licence_policy=licence_policy,
            )
            recovery = cls._inspect_recovery(connection, layout)
            if recovery.missing_payload_digests:
                raise _OpenError(
                    PersistentRefusalCode.PAYLOAD_MISSING,
                    "one or more registered aggregate payloads are missing",
                )
            if recovery.corrupt_payload_digests or recovery.unexpected_file_count:
                raise _OpenError(
                    PersistentRefusalCode.PAYLOAD_CORRUPT,
                    "persistent payload integrity validation failed",
                )
            core = cls._load_core(
                connection,
                layout,
                schemas=schema_tuple,
                authoritative_sources=source_tuple,
                licence_policy=licence_policy,
            )
            return cls(
                layout=layout,
                connection=connection,
                schemas=schema_tuple,
                authoritative_sources=source_tuple,
                licence_policy=licence_policy,
                fault_hook=fault_hook,
                recovery_report=recovery,
                core=core,
            )
        except _OpenError as exc:
            if connection is not None:
                connection.close()
            return PersistentStoreRefusal(
                operation="open",
                code=exc.code,
                message=exc.safe_message,
                subject_id="historical-store",
            )
        except (OSError, sqlite3.DatabaseError, ValueError):
            if connection is not None:
                connection.close()
            return PersistentStoreRefusal(
                operation="open",
                code=PersistentRefusalCode.CATALOGUE_CORRUPT,
                message="persistent catalogue could not be opened safely",
                subject_id="historical-store",
            )

    @staticmethod
    def _initialize_catalogue(connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version == SQLITE_SCHEMA_VERSION:
            return
        if version != 0:
            raise _OpenError(
                PersistentRefusalCode.CONTRACT_MISMATCH,
                "persistent catalogue schema version is incompatible",
            )
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            ) STRICT;
            CREATE TABLE IF NOT EXISTS payloads (
                payload_digest TEXT PRIMARY KEY,
                relative_handle TEXT NOT NULL UNIQUE,
                byte_count INTEGER NOT NULL CHECK (byte_count >= 0)
            ) STRICT;
            CREATE TABLE IF NOT EXISTS datasets (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL UNIQUE,
                record_digest TEXT NOT NULL,
                payload_digest TEXT NOT NULL REFERENCES payloads(payload_digest),
                record_json TEXT NOT NULL
            ) STRICT;
            CREATE TABLE IF NOT EXISTS features (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                feature_name TEXT NOT NULL,
                definition_version INTEGER NOT NULL,
                definition_digest TEXT NOT NULL,
                definition_json TEXT NOT NULL,
                UNIQUE(feature_name, definition_version)
            ) STRICT;
            CREATE TABLE IF NOT EXISTS snapshots (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id TEXT NOT NULL UNIQUE,
                snapshot_digest TEXT NOT NULL,
                values_digest TEXT NOT NULL REFERENCES payloads(payload_digest),
                request_json TEXT NOT NULL,
                snapshot_json TEXT NOT NULL
            ) STRICT;
            CREATE TABLE IF NOT EXISTS receipts (
                operation TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                result_digest TEXT NOT NULL,
                result_json TEXT NOT NULL,
                PRIMARY KEY(operation, subject_id)
            ) STRICT;
            PRAGMA user_version = 1;
            COMMIT;
            """
        )

    @staticmethod
    def _bundle_digest(records: Sequence[StoreModel]) -> str:
        payload = [
            item.model_dump(mode="json")
            for item in sorted(records, key=lambda value: value.fingerprint())
        ]
        return _digest_json(payload)

    @classmethod
    def _bind_or_verify_contract(
        cls,
        connection: sqlite3.Connection,
        *,
        schemas: tuple[DatasetSchemaContract, ...],
        authoritative_sources: tuple[AuthoritativeSourceRecord, ...],
        licence_policy: LicenceAllowlistPolicy,
    ) -> None:
        expected = {
            "method_version": PERSISTENCE_METHOD_VERSION,
            "storage_policy_digest": cls.policy.fingerprint(),
            "schema_bundle_digest": cls._bundle_digest(schemas),
            "source_bundle_digest": cls._bundle_digest(authoritative_sources),
            "licence_policy_digest": licence_policy.policy_digest,
            "licence_policy_json": licence_policy.canonical_json(),
        }
        observed = {
            str(row["key"]): str(row["value"])
            for row in connection.execute("SELECT key, value FROM metadata")
        }
        if not observed:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.executemany(
                    "INSERT INTO metadata(key, value) VALUES (?, ?)",
                    tuple(sorted(expected.items())),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            return
        if observed.get("licence_policy_digest") != expected["licence_policy_digest"]:
            raise _OpenError(
                PersistentRefusalCode.POLICY_MISMATCH,
                "licence allowlist policy does not match the bound workspace policy",
            )
        if observed != expected:
            raise _OpenError(
                PersistentRefusalCode.CONTRACT_MISMATCH,
                "schemas, sources or storage policy do not match the bound workspace contract",
            )

    @staticmethod
    def _payload_handle(digest: str) -> str:
        if _DIGEST_RE.fullmatch(digest) is None:
            raise _OpenError(
                PersistentRefusalCode.CATALOGUE_CORRUPT,
                "catalogue contains an invalid payload digest",
            )
        return f"payloads/sha256/{digest[:2]}/{digest}.json"

    @classmethod
    def _payload_path(cls, layout: _Layout, digest: str) -> Path:
        return layout.root / cls._payload_handle(digest)

    @classmethod
    def _inspect_recovery(
        cls,
        connection: sqlite3.Connection,
        layout: _Layout,
    ) -> RecoveryReport:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise _OpenError(
                PersistentRefusalCode.CATALOGUE_CORRUPT,
                "SQLite catalogue integrity check failed",
            )
        payload_rows = tuple(
            connection.execute("SELECT payload_digest, relative_handle, byte_count FROM payloads")
        )
        referenced = {str(row["payload_digest"]) for row in payload_rows}
        observed: set[str] = set()
        corrupt: set[str] = set()
        unexpected = 0
        for row in payload_rows:
            digest = str(row["payload_digest"])
            if (
                _DIGEST_RE.fullmatch(digest) is None
                or str(row["relative_handle"]) != cls._payload_handle(digest)
                or int(row["byte_count"]) < 0
            ):
                corrupt.add(digest)
        for path in sorted(layout.payloads.rglob("*")):
            if not path.is_file() and not path.is_symlink():
                continue
            if path.is_symlink():
                unexpected += 1
                continue
            relative_parts = path.relative_to(layout.payloads).parts
            digest = path.stem
            if (
                len(relative_parts) != 2
                or path.suffix != ".json"
                or _DIGEST_RE.fullmatch(digest) is None
                or path.parent.name != digest[:2]
            ):
                unexpected += 1
                continue
            try:
                payload = path.read_bytes()
            except OSError:
                corrupt.add(digest)
                continue
            observed.add(digest)
            expected_size = next(
                (
                    int(row["byte_count"])
                    for row in payload_rows
                    if str(row["payload_digest"]) == digest
                ),
                len(payload),
            )
            if _digest_bytes(payload) != digest or len(payload) != expected_size:
                corrupt.add(digest)
        missing = referenced - observed
        orphans = observed - referenced
        staged_count = sum(1 for path in layout.staging.iterdir() if path.is_file())
        return RecoveryReport(
            referenced_payload_count=len(referenced),
            orphan_payload_digests=tuple(sorted(orphans)),
            missing_payload_digests=tuple(sorted(missing)),
            corrupt_payload_digests=tuple(sorted(corrupt)),
            staged_file_count=staged_count,
            unexpected_file_count=unexpected,
            safe_to_open=not missing and not corrupt and unexpected == 0,
        )

    @classmethod
    def _read_payload(cls, layout: _Layout, digest: str) -> bytes:
        try:
            payload = cls._payload_path(layout, digest).read_bytes()
        except OSError as exc:
            raise _OpenError(
                PersistentRefusalCode.PAYLOAD_MISSING,
                "registered aggregate payload is missing",
            ) from exc
        if _digest_bytes(payload) != digest:
            raise _OpenError(
                PersistentRefusalCode.PAYLOAD_CORRUPT,
                "registered aggregate payload digest validation failed",
            )
        return payload

    @classmethod
    def _load_core(
        cls,
        connection: sqlite3.Connection,
        layout: _Layout,
        *,
        schemas: tuple[DatasetSchemaContract, ...],
        authoritative_sources: tuple[AuthoritativeSourceRecord, ...],
        licence_policy: LicenceAllowlistPolicy,
    ) -> InMemoryHistoricalStore:
        core = InMemoryHistoricalStore(
            schemas=schemas,
            authoritative_sources=authoritative_sources,
            licence_allowlist=frozenset(licence_policy.allowed_classes),
        )
        for row in connection.execute(
            "SELECT record_json, record_digest, payload_digest FROM datasets ORDER BY sequence"
        ):
            record = HistoricalDatasetRecord.model_validate_json(
                str(row["record_json"]), strict=True
            )
            if record.fingerprint() != str(row["record_digest"]):
                raise _OpenError(
                    PersistentRefusalCode.CATALOGUE_CORRUPT,
                    "stored dataset record digest validation failed",
                )
            payload = cls._read_payload(layout, str(row["payload_digest"]))
            dataset_result = core.register_dataset(
                DatasetRegistrationCandidate(record=record, payload=payload)
            )
            if isinstance(dataset_result, StoreRefusal):
                raise _OpenError(
                    PersistentRefusalCode.CATALOGUE_CORRUPT,
                    "stored dataset cannot be replayed under its bound contract",
                )
        for row in connection.execute("SELECT definition_json FROM features ORDER BY sequence"):
            definition = FeatureDefinition.model_validate_json(
                str(row["definition_json"]), strict=True
            )
            feature_result = core.register_feature(definition)
            if isinstance(feature_result, StoreRefusal):
                raise _OpenError(
                    PersistentRefusalCode.CATALOGUE_CORRUPT,
                    "stored feature cannot be replayed under its bound contract",
                )
        for row in connection.execute(
            "SELECT request_json, snapshot_json, values_digest FROM snapshots ORDER BY sequence"
        ):
            request = FeatureMaterialisationRequest.model_validate_json(
                str(row["request_json"]), strict=True
            )
            expected = FeatureSnapshot.model_validate_json(str(row["snapshot_json"]), strict=True)
            payload = cls._read_payload(layout, str(row["values_digest"]))
            snapshot_result = core.materialise_snapshot(
                FeatureSnapshotCandidate(request=request, values_payload=payload)
            )
            if isinstance(snapshot_result, StoreRefusal) or snapshot_result != expected:
                raise _OpenError(
                    PersistentRefusalCode.CATALOGUE_CORRUPT,
                    "stored feature snapshot cannot be replayed exactly",
                )
        return core

    def _reload_core(self) -> InMemoryHistoricalStore:
        return self._load_core(
            self._connection,
            self._layout,
            schemas=self._schemas,
            authoritative_sources=self._authoritative_sources,
            licence_policy=self._licence_policy,
        )

    @classmethod
    def _ensure_payload(cls, layout: _Layout, digest: str, payload: bytes) -> tuple[Path, bool]:
        if _digest_bytes(payload) != digest:
            raise _OpenError(
                PersistentRefusalCode.PAYLOAD_CORRUPT,
                "aggregate payload digest changed before persistence",
            )
        destination = cls._payload_path(layout, digest)
        if destination.exists():
            if destination.read_bytes() != payload:
                raise _OpenError(
                    PersistentRefusalCode.PAYLOAD_CORRUPT,
                    "content-addressed payload conflicts with existing bytes",
                )
            return destination, False
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f"{digest}.", suffix=".tmp", dir=layout.staging
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, destination)
            directory_descriptor = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return destination, True

    def _persistent_refusal(
        self,
        operation: Literal["register_dataset", "register_feature", "materialise_snapshot"],
        subject_id: str,
    ) -> PersistentStoreRefusal:
        with suppress(Exception):
            self._core = self._reload_core()
        return PersistentStoreRefusal(
            operation=operation,
            code=PersistentRefusalCode.PERSISTENCE_FAILURE,
            message="persistent transaction aborted before catalogue publication",
            subject_id=subject_id,
        )

    def _begin_with_fresh_core(self) -> InMemoryHistoricalStore:
        self._connection.execute("BEGIN IMMEDIATE")
        return self._reload_core()

    def register_dataset(
        self,
        candidate: DatasetRegistrationCandidate,
    ) -> StoreReceipt | StoreRefusal | PersistentStoreRefusal:
        with self._lock:
            created_path: Path | None = None
            try:
                core = self._begin_with_fresh_core()
                result = core.register_dataset(candidate)
                if isinstance(result, StoreRefusal) or result.idempotent_retry:
                    self._connection.execute("ROLLBACK")
                    self._core = core
                    return result
                created_path, created = self._ensure_payload(
                    self._layout, candidate.record.payload_digest, candidate.payload
                )
                handle = self._payload_handle(candidate.record.payload_digest)
                self._connection.execute(
                    "INSERT OR IGNORE INTO payloads(payload_digest, relative_handle, byte_count) "
                    "VALUES (?, ?, ?)",
                    (candidate.record.payload_digest, handle, len(candidate.payload)),
                )
                self._connection.execute(
                    "INSERT INTO datasets(dataset_id, record_digest, payload_digest, record_json) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        candidate.record.dataset_id,
                        candidate.record.fingerprint(),
                        candidate.record.payload_digest,
                        candidate.record.canonical_json(),
                    ),
                )
                self._connection.execute(
                    "INSERT INTO receipts(operation, subject_id, result_digest, result_json) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        "register_dataset",
                        candidate.record.dataset_id,
                        result.fingerprint(),
                        result.canonical_json(),
                    ),
                )
                if self._fault_hook is not None:
                    self._fault_hook("before_catalogue_commit", "register_dataset")
                self._connection.execute("COMMIT")
                self._core = core
                return result
            except Exception:
                with suppress(sqlite3.DatabaseError):
                    self._connection.execute("ROLLBACK")
                if created_path is not None and created:
                    created_path.unlink(missing_ok=True)
                return self._persistent_refusal("register_dataset", candidate.record.dataset_id)

    def register_feature(
        self,
        definition: FeatureDefinition,
    ) -> FeatureReceipt | StoreRefusal | PersistentStoreRefusal:
        subject_id = f"{definition.feature_name}@{definition.definition_version}"
        with self._lock:
            try:
                core = self._begin_with_fresh_core()
                result = core.register_feature(definition)
                if isinstance(result, StoreRefusal) or result.idempotent_retry:
                    self._connection.execute("ROLLBACK")
                    self._core = core
                    return result
                self._connection.execute(
                    "INSERT INTO features(feature_name, definition_version, definition_digest, "
                    "definition_json) VALUES (?, ?, ?, ?)",
                    (
                        definition.feature_name,
                        definition.definition_version,
                        definition.definition_digest,
                        definition.canonical_json(),
                    ),
                )
                self._connection.execute(
                    "INSERT INTO receipts(operation, subject_id, result_digest, result_json) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        "register_feature",
                        subject_id,
                        result.fingerprint(),
                        result.canonical_json(),
                    ),
                )
                if self._fault_hook is not None:
                    self._fault_hook("before_catalogue_commit", "register_feature")
                self._connection.execute("COMMIT")
                self._core = core
                return result
            except Exception:
                with suppress(sqlite3.DatabaseError):
                    self._connection.execute("ROLLBACK")
                return self._persistent_refusal("register_feature", subject_id)

    def materialise_snapshot(
        self,
        candidate: FeatureSnapshotCandidate,
    ) -> FeatureSnapshot | StoreRefusal | PersistentStoreRefusal:
        subject_id = candidate.request.snapshot_id
        with self._lock:
            created_path: Path | None = None
            try:
                core = self._begin_with_fresh_core()
                result = core.materialise_snapshot(candidate)
                if isinstance(result, StoreRefusal):
                    self._connection.execute("ROLLBACK")
                    self._core = core
                    return result
                existing = self._connection.execute(
                    "SELECT snapshot_digest FROM snapshots WHERE snapshot_id = ?",
                    (subject_id,),
                ).fetchone()
                if existing is not None:
                    self._connection.execute("ROLLBACK")
                    self._core = core
                    return result
                created_path, created = self._ensure_payload(
                    self._layout, candidate.request.values_digest, candidate.values_payload
                )
                handle = self._payload_handle(candidate.request.values_digest)
                self._connection.execute(
                    "INSERT OR IGNORE INTO payloads(payload_digest, relative_handle, byte_count) "
                    "VALUES (?, ?, ?)",
                    (candidate.request.values_digest, handle, len(candidate.values_payload)),
                )
                self._connection.execute(
                    "INSERT INTO snapshots(snapshot_id, snapshot_digest, values_digest, "
                    "request_json, snapshot_json) VALUES (?, ?, ?, ?, ?)",
                    (
                        result.snapshot_id,
                        result.snapshot_digest,
                        result.values_digest,
                        candidate.request.canonical_json(),
                        result.canonical_json(),
                    ),
                )
                self._connection.execute(
                    "INSERT INTO receipts(operation, subject_id, result_digest, result_json) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        "materialise_snapshot",
                        subject_id,
                        result.fingerprint(),
                        result.canonical_json(),
                    ),
                )
                if self._fault_hook is not None:
                    self._fault_hook("before_catalogue_commit", "materialise_snapshot")
                self._connection.execute("COMMIT")
                self._core = core
                return result
            except Exception:
                with suppress(sqlite3.DatabaseError):
                    self._connection.execute("ROLLBACK")
                if created_path is not None and created:
                    created_path.unlink(missing_ok=True)
                return self._persistent_refusal("materialise_snapshot", subject_id)

    def get_dataset(
        self,
        dataset_id: str,
        expected_digest: str,
    ) -> HistoricalDatasetRecord | StoreRefusal:
        with self._lock:
            self._core = self._reload_core()
            return self._core.get_dataset(dataset_id, expected_digest)

    def query_catalogue(self, query: CatalogueQuery) -> tuple[HistoricalDatasetRecord, ...]:
        with self._lock:
            self._core = self._reload_core()
            return self._core.query_catalogue(query)

    def provenance_walk(self, snapshot_id: str) -> ProvenanceWalk | StoreRefusal:
        with self._lock:
            self._core = self._reload_core()
            return self._core.provenance_walk(snapshot_id)

    def dry_run_migration(
        self,
        candidates: Sequence[DatasetRegistrationCandidate],
    ) -> MigrationDryRunReport:
        with self._lock:
            self._core = self._reload_core()
            return self._core.dry_run_migration(candidates)

    def recovery_report(self) -> RecoveryReport:
        with self._lock:
            self._recovery_report = self._inspect_recovery(self._connection, self._layout)
            return self._recovery_report

    def create_verified_backup(self, label: str) -> BackupReceipt | PersistentStoreRefusal:
        if _LABEL_RE.fullmatch(label) is None:
            return PersistentStoreRefusal(
                operation="create_backup",
                code=PersistentRefusalCode.BACKUP_LABEL_INVALID,
                message="backup label must use the safe lowercase label grammar",
                subject_id="historical-store",
            )
        with self._lock:
            temporary = Path(
                tempfile.mkdtemp(prefix=f"{label}.", suffix=".backup.tmp", dir=self._layout.staging)
            )
            try:
                catalogue_copy = temporary / "catalogue.sqlite"
                target = sqlite3.connect(catalogue_copy)
                try:
                    self._connection.backup(target)
                    target.commit()
                    integrity = str(target.execute("PRAGMA integrity_check").fetchone()[0])
                finally:
                    target.close()
                if integrity != "ok":
                    raise sqlite3.DatabaseError("backup integrity check failed")
                catalogue_copy.chmod(0o600)
                catalogue_digest = _digest_bytes(catalogue_copy.read_bytes())
                payload_entries: list[dict[str, object]] = []
                for row in self._connection.execute(
                    "SELECT payload_digest, byte_count FROM payloads ORDER BY payload_digest"
                ):
                    payload_digest = str(row["payload_digest"])
                    payload = self._read_payload(self._layout, payload_digest)
                    payload_copy = temporary / self._payload_handle(payload_digest)
                    payload_copy.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    payload_copy.write_bytes(payload)
                    payload_copy.chmod(0o600)
                    payload_entries.append(
                        {
                            "payload_digest": payload_digest,
                            "byte_count": int(row["byte_count"]),
                        }
                    )
                manifest = {
                    "method_version": PERSISTENCE_METHOD_VERSION,
                    "sqlite_schema_version": SQLITE_SCHEMA_VERSION,
                    "storage_policy_digest": self.policy.fingerprint(),
                    "licence_policy_digest": self._licence_policy.policy_digest,
                    "catalogue_digest": catalogue_digest,
                    "payloads": payload_entries,
                    "automatic_deletion": False,
                }
                manifest_bytes = _canonical_json(manifest).encode("utf-8")
                backup_digest = _digest_bytes(manifest_bytes)
                manifest_path = temporary / "manifest.json"
                manifest_path.write_bytes(manifest_bytes)
                manifest_path.chmod(0o600)
                self._verify_backup_bundle(temporary, manifest_bytes)
                name = f"{label}-{backup_digest[:12]}"
                destination = self._layout.backups / name
                idempotent = destination.exists()
                if idempotent:
                    self._verify_backup_bundle(destination, manifest_bytes)
                    shutil.rmtree(temporary)
                else:
                    os.replace(temporary, destination)
                return BackupReceipt(
                    backup_handle=f"backups/{name}",
                    backup_digest=backup_digest,
                    catalogue_digest=catalogue_digest,
                    payload_count=len(payload_entries),
                    idempotent_retry=idempotent,
                )
            except Exception:
                if temporary.exists():
                    with suppress(OSError):
                        shutil.rmtree(temporary)
                return PersistentStoreRefusal(
                    operation="create_backup",
                    code=PersistentRefusalCode.PERSISTENCE_FAILURE,
                    message="verified local backup could not be created",
                    subject_id="historical-store",
                )

    @classmethod
    def _verify_backup_bundle(cls, root: Path, expected_manifest: bytes) -> None:
        if (root / "manifest.json").read_bytes() != expected_manifest:
            raise sqlite3.DatabaseError("backup manifest does not match")
        manifest = json.loads(expected_manifest)
        if not isinstance(manifest, dict):
            raise sqlite3.DatabaseError("backup manifest is invalid")
        catalogue = root / "catalogue.sqlite"
        if _digest_bytes(catalogue.read_bytes()) != manifest.get("catalogue_digest"):
            raise sqlite3.DatabaseError("backup catalogue digest does not match")
        connection = sqlite3.connect(catalogue)
        try:
            if str(connection.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise sqlite3.DatabaseError("backup catalogue integrity check failed")
        finally:
            connection.close()
        payloads = manifest.get("payloads")
        if not isinstance(payloads, list):
            raise sqlite3.DatabaseError("backup payload manifest is invalid")
        for entry in payloads:
            if not isinstance(entry, dict):
                raise sqlite3.DatabaseError("backup payload entry is invalid")
            digest = entry.get("payload_digest")
            byte_count = entry.get("byte_count")
            if not isinstance(digest, str) or not isinstance(byte_count, int):
                raise sqlite3.DatabaseError("backup payload entry is invalid")
            payload = (root / cls._payload_handle(digest)).read_bytes()
            if len(payload) != byte_count or _digest_bytes(payload) != digest:
                raise sqlite3.DatabaseError("backup payload verification failed")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
