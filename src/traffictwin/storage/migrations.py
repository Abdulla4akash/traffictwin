"""Versioned, ordered, transactional migrations for the TrafficTwin registry."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import cast
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

MIGRATION_SCHEMA_VERSION = "1.0"
MIGRATION_CONTRACT_VERSION = "registry-migrations-v1"
MIGRATION_CAPABILITY_ID = "OPS-01"
CURRENT_REGISTRY_SCHEMA_VERSION = 5
MIGRATION_LEDGER_TABLE = "registry_schema_migrations"


class RegistryMigrationError(RuntimeError):
    """Base error for a registry schema migration or inspection failure."""


class RegistryMigrationRequiredError(RegistryMigrationError):
    """Raised when an operation requires a newer supported registry schema."""


class RegistryFutureSchemaError(RegistryMigrationError):
    """Raised when a registry was written by a newer unsupported TrafficTwin version."""


class RegistrySchemaIntegrityError(RegistryMigrationError):
    """Raised when schema objects or the migration ledger are inconsistent."""


class RegistryMigrationExecutionError(RegistryMigrationError):
    """Raised after a failed migration plan has been rolled back."""


class RegistryMigrationState(StrEnum):
    """Read-only classification of one registry schema."""

    EMPTY = "empty"
    LEGACY_UNVERSIONED = "legacy_unversioned"
    UPGRADE_AVAILABLE = "upgrade_available"
    CURRENT = "current"


class RegistryMigrationDescriptor(BaseModel):
    """Published identity of one immutable ordered migration."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    name: str = Field(min_length=1)
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    creates: list[str]


class RegistryMigrationContract(BaseModel):
    """Published OPS-01 migration boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = MIGRATION_SCHEMA_VERSION
    capability_id: str = MIGRATION_CAPABILITY_ID
    contract_version: str = MIGRATION_CONTRACT_VERSION
    current_registry_schema_version: int
    ordered_migrations: list[RegistryMigrationDescriptor]
    transaction_policy: str
    ledger_policy: list[str]
    legacy_policy: list[str]
    integrity_policy: list[str]
    exclusions: list[str]
    limitations: list[str]

    def canonical_json(self) -> str:
        """Return a byte-stable contract representation."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the exact published migration contract."""

        return _fingerprint(self.canonical_json())


class RegistryMigrationStatus(BaseModel):
    """Read-only registry schema and migration-ledger status."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = MIGRATION_SCHEMA_VERSION
    capability_id: str = MIGRATION_CAPABILITY_ID
    contract_version: str = MIGRATION_CONTRACT_VERSION
    state: RegistryMigrationState
    current_version: int = Field(ge=0)
    latest_version: int = Field(ge=1)
    applied_versions: list[int]
    pending_versions: list[int]
    schema_object_count: int = Field(ge=0)
    ledger_valid: bool
    integrity_check: str
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    def canonical_json(self) -> str:
        """Return a byte-stable status representation."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint this exact schema status."""

        return _fingerprint(self.canonical_json())


class RegistryMigrationResult(BaseModel):
    """Result of one successful atomic registry upgrade plan."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = MIGRATION_SCHEMA_VERSION
    capability_id: str = MIGRATION_CAPABILITY_ID
    contract_version: str = MIGRATION_CONTRACT_VERSION
    initial_version: int = Field(ge=0)
    final_version: int = Field(ge=1)
    target_version: int = Field(ge=1)
    legacy_schema_detected: bool
    applied_migrations: list[RegistryMigrationDescriptor]
    already_at_target: bool
    ledger_valid: bool
    integrity_check: str
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    def canonical_json(self) -> str:
        """Return a byte-stable migration result."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the exact migration outcome."""

        return _fingerprint(self.canonical_json())


@dataclass(frozen=True)
class RegistryMigration:
    """Executable internal definition for one registry schema version."""

    version: int
    name: str
    statements: tuple[str, ...]
    creates: tuple[str, ...]

    @property
    def checksum(self) -> str:
        """Return the immutable checksum of the migration SQL and identity."""

        normalised = [" ".join(statement.split()) for statement in self.statements]
        payload = _canonical_json(
            {"name": self.name, "statements": normalised, "version": self.version}
        )
        return _fingerprint(payload)

    def descriptor(self) -> RegistryMigrationDescriptor:
        """Return the documentation-safe public migration identity."""

        return RegistryMigrationDescriptor(
            version=self.version,
            name=self.name,
            checksum=self.checksum,
            creates=list(self.creates),
        )


REGISTRY_MIGRATIONS: tuple[RegistryMigration, ...] = (
    RegistryMigration(
        version=1,
        name="core_registry",
        creates=(
            "table:registry_schema_migrations",
            "table:seeds",
            "table:experiments",
            "table:runs",
            "trigger:registry_schema_migrations_no_update",
            "trigger:registry_schema_migrations_no_delete",
        ),
        statements=(
            """
            CREATE TABLE IF NOT EXISTS registry_schema_migrations (
                version INTEGER PRIMARY KEY CHECK(version >= 1),
                name TEXT NOT NULL UNIQUE,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """,
            """
            CREATE TRIGGER IF NOT EXISTS registry_schema_migrations_no_update
            BEFORE UPDATE ON registry_schema_migrations
            BEGIN
                SELECT RAISE(ABORT, 'registry migration history is immutable');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS registry_schema_migrations_no_delete
            BEFORE DELETE ON registry_schema_migrations
            BEGIN
                SELECT RAISE(ABORT, 'registry migration history is immutable');
            END
            """,
            """
            CREATE TABLE IF NOT EXISTS seeds (
                seed_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    RegistryMigration(
        version=2,
        name="import_and_analysis_artifacts",
        creates=(
            "table:bundle_imports",
            "table:metric_collections",
            "table:evidence_packs",
        ),
        statements=(
            """
            CREATE TABLE IF NOT EXISTS bundle_imports (
                bundle_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                validation_report_json TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                UNIQUE(run_id),
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS metric_collections (
                run_id TEXT PRIMARY KEY,
                metric_version TEXT NOT NULL,
                source_fingerprint TEXT,
                payload_json TEXT NOT NULL,
                stored_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS evidence_packs (
                pack_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                source_fingerprint TEXT,
                payload_json TEXT NOT NULL,
                stored_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """,
        ),
    ),
    RegistryMigration(
        version=3,
        name="experiment_protocol_tracking",
        creates=(
            "table:experiment_protocols",
            "table:experiment_protocol_slots",
        ),
        statements=(
            """
            CREATE TABLE IF NOT EXISTS experiment_protocols (
                protocol_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS experiment_protocol_slots (
                protocol_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                slot_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                status TEXT NOT NULL,
                expected_run_id TEXT NOT NULL,
                expected_bundle_id TEXT NOT NULL,
                observed_run_id TEXT,
                observed_bundle_id TEXT,
                note TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(protocol_id, slot_id),
                FOREIGN KEY(protocol_id) REFERENCES experiment_protocols(protocol_id)
            )
            """,
        ),
    ),
    RegistryMigration(
        version=4,
        name="experiment_evidence",
        creates=("table:experiment_evidence_packs",),
        statements=(
            """
            CREATE TABLE IF NOT EXISTS experiment_evidence_packs (
                pack_id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                source_fingerprint TEXT,
                payload_json TEXT NOT NULL,
                stored_at TEXT NOT NULL,
                FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id)
            )
            """,
        ),
    ),
    RegistryMigration(
        version=5,
        name="analyst_annotations",
        creates=(
            "table:analyst_annotations",
            "index:analyst_annotations_target_idx",
            "trigger:analyst_annotations_no_update",
            "trigger:analyst_annotations_no_delete",
        ),
        statements=(
            """
            CREATE TABLE IF NOT EXISTS analyst_annotations (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                annotation_id TEXT NOT NULL UNIQUE,
                target_kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_fingerprint TEXT,
                author_label TEXT NOT NULL,
                note TEXT NOT NULL,
                decision_label TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS analyst_annotations_target_idx
            ON analyst_annotations(target_kind, target_id, sequence)
            """,
            """
            CREATE TRIGGER IF NOT EXISTS analyst_annotations_no_update
            BEFORE UPDATE ON analyst_annotations
            BEGIN
                SELECT RAISE(ABORT, 'analyst annotations are append-only');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS analyst_annotations_no_delete
            BEFORE DELETE ON analyst_annotations
            BEGIN
                SELECT RAISE(ABORT, 'analyst annotations are append-only');
            END
            """,
        ),
    ),
)


_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "registry_schema_migrations": frozenset({"version", "name", "checksum", "applied_at"}),
    "seeds": frozenset({"seed_id", "payload", "created_at", "updated_at"}),
    "experiments": frozenset({"experiment_id", "status", "payload", "created_at", "updated_at"}),
    "runs": frozenset({"run_id", "status", "payload", "created_at", "updated_at"}),
    "bundle_imports": frozenset(
        {
            "bundle_id",
            "run_id",
            "source_reference",
            "fingerprint",
            "manifest_json",
            "validation_report_json",
            "imported_at",
        }
    ),
    "metric_collections": frozenset(
        {"run_id", "metric_version", "source_fingerprint", "payload_json", "stored_at"}
    ),
    "evidence_packs": frozenset(
        {"pack_id", "run_id", "source_fingerprint", "payload_json", "stored_at"}
    ),
    "experiment_protocols": frozenset(
        {"protocol_id", "experiment_id", "input_fingerprint", "payload_json", "created_at"}
    ),
    "experiment_protocol_slots": frozenset(
        {
            "protocol_id",
            "experiment_id",
            "slot_id",
            "sequence",
            "status",
            "expected_run_id",
            "expected_bundle_id",
            "observed_run_id",
            "observed_bundle_id",
            "note",
            "updated_at",
        }
    ),
    "experiment_evidence_packs": frozenset(
        {"pack_id", "experiment_id", "source_fingerprint", "payload_json", "stored_at"}
    ),
    "analyst_annotations": frozenset(
        {
            "sequence",
            "annotation_id",
            "target_kind",
            "target_id",
            "target_fingerprint",
            "author_label",
            "note",
            "decision_label",
            "created_at",
        }
    ),
}

_OBJECT_VERSION: dict[str, int] = {
    object_name.split(":", maxsplit=1)[1]: migration.version
    for migration in REGISTRY_MIGRATIONS
    for object_name in migration.creates
}
_OBJECT_TYPES: dict[str, str] = {
    object_name.split(":", maxsplit=1)[1]: object_name.split(":", maxsplit=1)[0]
    for migration in REGISTRY_MIGRATIONS
    for object_name in migration.creates
}
_KNOWN_OBJECTS = frozenset(_OBJECT_VERSION)


def registry_migration_contract() -> RegistryMigrationContract:
    """Return the exact OPS-01 ordered migration contract."""

    _validate_migration_plan(REGISTRY_MIGRATIONS)
    return RegistryMigrationContract(
        current_registry_schema_version=CURRENT_REGISTRY_SCHEMA_VERSION,
        ordered_migrations=[migration.descriptor() for migration in REGISTRY_MIGRATIONS],
        transaction_policy=(
            "All pending ordered migrations and ledger entries run inside one SQLite "
            "BEGIN IMMEDIATE transaction; any failure rolls back the complete upgrade plan."
        ),
        ledger_policy=[
            "PRAGMA user_version is the authoritative integer schema version.",
            "Every applied version has one immutable name/checksum/timestamp ledger row.",
            "Existing ledger names and checksums must match the embedded ordered plan.",
        ],
        legacy_policy=[
            "Empty SQLite databases and known unversioned TrafficTwin additive schemas "
            "are supported.",
            "Known legacy rows and payload bytes are retained; migrations add schema objects only.",
            "Unknown SQLite schema objects or non-SQLite files fail closed before schema changes.",
        ],
        integrity_policy=[
            "Required objects and columns are validated at every version boundary.",
            "SQLite quick_check must return ok before commit and during read-only status "
            "inspection.",
            "Future versions, gaps, checksum drift, and downgrades are rejected.",
        ],
        exclusions=[
            "No destructive downgrade or automatic backup is performed.",
            "No stored scientific payload is rewritten or reinterpreted.",
            "No external database migration framework or network service is required.",
        ],
        limitations=[
            "Version 1 supports the known repository-era additive SQLite shapes only.",
            "Operators remain responsible for independent backups before migrating valuable "
            "registries.",
            "A successful schema migration does not validate the scientific meaning of stored "
            "JSON.",
        ],
    )


def inspect_registry_migrations(path: str | Path) -> RegistryMigrationStatus:
    """Inspect a registry schema through a non-mutating immutable SQLite connection."""

    registry_path = Path(path)
    if not registry_path.is_file():
        raise RegistryMigrationError(f"registry does not exist: {registry_path}")
    uri = f"file:{quote(str(registry_path.resolve()))}?mode=ro&immutable=1"
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            return _status_from_connection(conn)
    except sqlite3.DatabaseError as exc:
        raise RegistrySchemaIntegrityError(f"registry schema inspection failed: {exc}") from exc


def migrate_registry(
    path: str | Path,
    *,
    target_version: int | None = None,
    clock: Callable[[], datetime] | None = None,
) -> RegistryMigrationResult:
    """Apply the complete pending ordered migration plan in one transaction."""

    _validate_migration_plan(REGISTRY_MIGRATIONS)
    target = CURRENT_REGISTRY_SCHEMA_VERSION if target_version is None else target_version
    if not 1 <= target <= CURRENT_REGISTRY_SCHEMA_VERSION:
        raise RegistryMigrationError(
            f"target_version must be between 1 and {CURRENT_REGISTRY_SCHEMA_VERSION}"
        )
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    migration_clock = clock or (lambda: datetime.now(UTC))
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(registry_path, isolation_level=None, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("BEGIN IMMEDIATE")
        initial_version = _read_user_version(conn)
        objects = _user_objects(conn)
        legacy_schema_detected = initial_version == 0 and bool(objects)
        _validate_supported_state(conn, initial_version, objects)
        if target < initial_version:
            raise RegistryMigrationError(
                f"registry downgrade is unsupported: current={initial_version}, target={target}"
            )
        pending = [
            migration
            for migration in REGISTRY_MIGRATIONS
            if initial_version < migration.version <= target
        ]
        for migration in pending:
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                """
                INSERT INTO registry_schema_migrations (version, name, checksum, applied_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    migration.checksum,
                    migration_clock().astimezone(UTC).isoformat(),
                ),
            )
            conn.execute(f"PRAGMA user_version = {migration.version}")
            _validate_required_schema(conn, migration.version)
            _validate_ledger(conn, migration.version)
        final_version = _read_user_version(conn)
        _validate_required_schema(conn, final_version)
        _validate_ledger(conn, final_version)
        integrity = _quick_check(conn)
        schema_fingerprint = _schema_fingerprint(conn)
        conn.execute("COMMIT")
    except RegistryMigrationError:
        if conn is not None and conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        if conn is not None and conn.in_transaction:
            conn.execute("ROLLBACK")
        raise RegistryMigrationExecutionError(
            f"registry migration failed and was rolled back: {exc}"
        ) from exc
    finally:
        if conn is not None:
            conn.close()
    return RegistryMigrationResult(
        initial_version=initial_version,
        final_version=final_version,
        target_version=target,
        legacy_schema_detected=legacy_schema_detected,
        applied_migrations=[migration.descriptor() for migration in pending],
        already_at_target=not pending,
        ledger_valid=True,
        integrity_check=integrity,
        schema_fingerprint=schema_fingerprint,
    )


def require_current_registry_schema(path: str | Path) -> RegistryMigrationStatus:
    """Return status only when an existing registry is at the supported current version."""

    status = inspect_registry_migrations(path)
    if status.current_version != CURRENT_REGISTRY_SCHEMA_VERSION:
        raise RegistryMigrationRequiredError(
            "registry migration required: "
            f"current={status.current_version}, latest={CURRENT_REGISTRY_SCHEMA_VERSION}"
        )
    return status


def _status_from_connection(conn: sqlite3.Connection) -> RegistryMigrationStatus:
    current_version = _read_user_version(conn)
    objects = _user_objects(conn)
    _validate_supported_state(conn, current_version, objects)
    integrity = _quick_check(conn)
    applied_versions = _ledger_versions(conn) if current_version > 0 else []
    pending_versions = [
        migration.version
        for migration in REGISTRY_MIGRATIONS
        if migration.version > current_version
    ]
    if current_version == CURRENT_REGISTRY_SCHEMA_VERSION:
        state = RegistryMigrationState.CURRENT
    elif current_version > 0:
        state = RegistryMigrationState.UPGRADE_AVAILABLE
    elif objects:
        state = RegistryMigrationState.LEGACY_UNVERSIONED
    else:
        state = RegistryMigrationState.EMPTY
    return RegistryMigrationStatus(
        state=state,
        current_version=current_version,
        latest_version=CURRENT_REGISTRY_SCHEMA_VERSION,
        applied_versions=applied_versions,
        pending_versions=pending_versions,
        schema_object_count=len(objects),
        ledger_valid=True,
        integrity_check=integrity,
        schema_fingerprint=_schema_fingerprint(conn),
    )


def _validate_migration_plan(migrations: Sequence[RegistryMigration]) -> None:
    versions = [migration.version for migration in migrations]
    if versions != list(range(1, CURRENT_REGISTRY_SCHEMA_VERSION + 1)):
        raise RegistrySchemaIntegrityError(
            "embedded registry migrations must be contiguous from 1 to "
            f"{CURRENT_REGISTRY_SCHEMA_VERSION}"
        )
    names = [migration.name for migration in migrations]
    if len(set(names)) != len(names):
        raise RegistrySchemaIntegrityError("embedded registry migration names must be unique")


def _validate_supported_state(
    conn: sqlite3.Connection,
    current_version: int,
    objects: dict[str, str],
) -> None:
    if current_version > CURRENT_REGISTRY_SCHEMA_VERSION:
        raise RegistryFutureSchemaError(
            "registry schema is newer than this TrafficTwin build: "
            f"current={current_version}, supported={CURRENT_REGISTRY_SCHEMA_VERSION}"
        )
    unknown = sorted(name for name in objects if name not in _KNOWN_OBJECTS)
    if unknown:
        raise RegistrySchemaIntegrityError(
            "registry contains unknown schema objects and was not modified: " + ", ".join(unknown)
        )
    _validate_existing_known_tables(conn, objects)
    if current_version == 0:
        if MIGRATION_LEDGER_TABLE in objects and _ledger_versions(conn):
            raise RegistrySchemaIntegrityError(
                "unversioned registry has migration ledger rows; manual recovery is required"
            )
        return
    _validate_required_schema(conn, current_version)
    _validate_ledger(conn, current_version)


def _validate_existing_known_tables(
    conn: sqlite3.Connection,
    objects: dict[str, str],
) -> None:
    for table, required_columns in _TABLE_COLUMNS.items():
        if table not in objects:
            continue
        if objects[table] != "table":
            raise RegistrySchemaIntegrityError(f"expected table schema object: {table}")
        actual_columns = _table_columns(conn, table)
        missing = sorted(required_columns - actual_columns)
        if missing:
            raise RegistrySchemaIntegrityError(
                f"registry table {table} is missing required columns: {', '.join(missing)}"
            )


def _validate_required_schema(conn: sqlite3.Connection, version: int) -> None:
    if version == 0:
        return
    objects = _user_objects(conn)
    missing = sorted(
        name
        for name, introduced in _OBJECT_VERSION.items()
        if introduced <= version and name not in objects
    )
    if missing:
        raise RegistrySchemaIntegrityError(
            f"registry schema version {version} is missing objects: {', '.join(missing)}"
        )
    wrong_types = sorted(
        f"{name} (expected {_OBJECT_TYPES[name]}, found {objects[name]})"
        for name, introduced in _OBJECT_VERSION.items()
        if introduced <= version and name in objects and objects[name] != _OBJECT_TYPES[name]
    )
    if wrong_types:
        raise RegistrySchemaIntegrityError(
            "registry schema objects have unexpected types: " + ", ".join(wrong_types)
        )
    _validate_existing_known_tables(conn, objects)


def _validate_ledger(conn: sqlite3.Connection, current_version: int) -> None:
    rows = conn.execute(
        "SELECT version, name, checksum FROM registry_schema_migrations ORDER BY version"
    ).fetchall()
    expected = [
        migration for migration in REGISTRY_MIGRATIONS if migration.version <= current_version
    ]
    if len(rows) != len(expected):
        raise RegistrySchemaIntegrityError(
            "registry migration ledger is not contiguous with PRAGMA user_version"
        )
    for row, migration in zip(rows, expected, strict=True):
        if (
            int(row["version"]) != migration.version
            or cast(str, row["name"]) != migration.name
            or cast(str, row["checksum"]) != migration.checksum
        ):
            raise RegistrySchemaIntegrityError(
                f"registry migration ledger mismatch at version {migration.version}"
            )


def _ledger_versions(conn: sqlite3.Connection) -> list[int]:
    if MIGRATION_LEDGER_TABLE not in _user_objects(conn):
        return []
    rows = conn.execute(
        "SELECT version FROM registry_schema_migrations ORDER BY version"
    ).fetchall()
    return [int(row["version"]) for row in rows]


def _read_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    if row is None:
        raise RegistrySchemaIntegrityError("registry PRAGMA user_version is unavailable")
    return int(row[0])


def _quick_check(conn: sqlite3.Connection) -> str:
    rows = conn.execute("PRAGMA quick_check").fetchall()
    values = [str(row[0]) for row in rows]
    if values != ["ok"]:
        raise RegistrySchemaIntegrityError(
            "registry SQLite quick_check failed: " + "; ".join(values)
        )
    return "ok"


def _user_objects(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT name, type FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    return {cast(str, row["name"]): cast(str, row["type"]) for row in rows}


def _table_columns(conn: sqlite3.Connection, table: str) -> frozenset[str]:
    if table not in _TABLE_COLUMNS:
        raise RegistrySchemaIntegrityError(f"unknown registry table: {table}")
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return frozenset(cast(str, row["name"]) for row in rows)


def _schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """
        SELECT type, name, COALESCE(sql, '') AS sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    payload = {
        "objects": [
            {
                "name": cast(str, row["name"]),
                "sql": " ".join(cast(str, row["sql"]).split()),
                "type": cast(str, row["type"]),
            }
            for row in rows
        ],
        "user_version": _read_user_version(conn),
    }
    return _fingerprint(_canonical_json(payload))


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
