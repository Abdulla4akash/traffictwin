from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

import traffictwin.storage.migrations as registry_migrations
from tests.helpers import fixed_clock
from traffictwin.config.capabilities import (
    CapabilitySupport,
    default_export_import_manifest,
)
from traffictwin.integration.sumo import sumo_results_capability_manifest
from traffictwin.integration.tos import tos_data_capability_manifest
from traffictwin.storage.migrations import (
    CURRENT_REGISTRY_SCHEMA_VERSION,
    REGISTRY_MIGRATIONS,
    RegistryFutureSchemaError,
    RegistryMigration,
    RegistryMigrationError,
    RegistryMigrationExecutionError,
    RegistryMigrationState,
    RegistrySchemaIntegrityError,
    inspect_registry_migrations,
    migrate_registry,
    registry_migration_contract,
)


def _database_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_core_registry(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE seeds (
                seed_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE experiments (
                experiment_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO seeds VALUES (
                'legacy-seed', '{"seed_id":"legacy-seed","marker":"exact bytes"}',
                '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00'
            );
            INSERT INTO experiments VALUES (
                'legacy-experiment', 'planned', '{"marker":"legacy experiment"}',
                '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00'
            );
            INSERT INTO runs VALUES (
                'legacy-run', 'registered', '{"marker":"legacy run"}',
                '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00'
            );
            """
        )


def _payload_rows(path: Path) -> tuple[tuple[str, str], ...]:
    with sqlite3.connect(path) as conn:
        return tuple(
            (str(row[0]), str(row[1]))
            for query in (
                "SELECT seed_id, payload FROM seeds",
                "SELECT experiment_id, payload FROM experiments",
                "SELECT run_id, payload FROM runs",
            )
            for row in conn.execute(query)
        )


def test_migration_contract_is_contiguous_checksummed_and_explicit() -> None:
    contract = registry_migration_contract()

    assert contract.capability_id == "OPS-01"
    assert contract.contract_version == "registry-migrations-v1"
    assert contract.current_registry_schema_version == CURRENT_REGISTRY_SCHEMA_VERSION == 5
    assert [item.version for item in contract.ordered_migrations] == [1, 2, 3, 4, 5]
    assert len({item.checksum for item in contract.ordered_migrations}) == 5
    assert "BEGIN IMMEDIATE" in contract.transaction_policy
    assert "rolls back the complete upgrade plan" in contract.transaction_policy
    assert len(contract.fingerprint()) == 64


def test_known_unversioned_registry_upgrades_without_changing_payloads(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    _legacy_core_registry(path)
    before_rows = _payload_rows(path)
    before_hash = _database_hash(path)

    status = inspect_registry_migrations(path)

    assert status.state is RegistryMigrationState.LEGACY_UNVERSIONED
    assert status.current_version == 0
    assert status.pending_versions == [1, 2, 3, 4, 5]
    assert _database_hash(path) == before_hash

    result = migrate_registry(path, clock=fixed_clock)

    assert result.initial_version == 0
    assert result.final_version == 5
    assert result.legacy_schema_detected
    assert [item.version for item in result.applied_migrations] == [1, 2, 3, 4, 5]
    assert _payload_rows(path) == before_rows
    assert inspect_registry_migrations(path).state is RegistryMigrationState.CURRENT


@pytest.mark.parametrize("starting_version", [1, 2, 3, 4])
def test_every_representative_versioned_schema_upgrades_and_preserves_rows(
    tmp_path: Path,
    starting_version: int,
) -> None:
    path = tmp_path / f"registry-v{starting_version}.sqlite"
    migrate_registry(path, target_version=starting_version, clock=fixed_clock)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO seeds VALUES (?, ?, ?, ?)",
            (
                f"seed-v{starting_version}",
                f'{{"historical_version":{starting_version}}}',
                "2025-01-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
            ),
        )
        if starting_version >= 2:
            conn.execute(
                "INSERT INTO metric_collections VALUES (?, ?, ?, ?, ?)",
                (
                    f"run-v{starting_version}",
                    "metrics-v1",
                    "source-fingerprint",
                    f'{{"historical_version":{starting_version}}}',
                    "2025-01-01T00:00:00+00:00",
                ),
            )
        if starting_version >= 3:
            conn.execute(
                "INSERT INTO experiment_protocols VALUES (?, ?, ?, ?, ?)",
                (
                    f"protocol-v{starting_version}",
                    f"experiment-v{starting_version}",
                    "input-fingerprint",
                    f'{{"historical_version":{starting_version}}}',
                    "2025-01-01T00:00:00+00:00",
                ),
            )
        if starting_version >= 4:
            conn.execute(
                "INSERT INTO experiment_evidence_packs VALUES (?, ?, ?, ?, ?)",
                (
                    f"pack-v{starting_version}",
                    f"experiment-v{starting_version}",
                    "source-fingerprint",
                    f'{{"historical_version":{starting_version}}}',
                    "2025-01-01T00:00:00+00:00",
                ),
            )
    with sqlite3.connect(path) as conn:
        before = tuple(
            conn.execute("SELECT seed_id, payload FROM seeds ORDER BY seed_id").fetchall()
        )

    result = migrate_registry(path, clock=fixed_clock)

    assert result.initial_version == starting_version
    assert result.final_version == 5
    assert [item.version for item in result.applied_migrations] == list(
        range(starting_version + 1, 6)
    )
    with sqlite3.connect(path) as conn:
        assert (
            tuple(conn.execute("SELECT seed_id, payload FROM seeds ORDER BY seed_id").fetchall())
            == before
        )
        if starting_version >= 2:
            assert conn.execute("SELECT COUNT(*) FROM metric_collections").fetchone() == (1,)
        if starting_version >= 3:
            assert conn.execute("SELECT COUNT(*) FROM experiment_protocols").fetchone() == (1,)
        if starting_version >= 4:
            assert conn.execute("SELECT COUNT(*) FROM experiment_evidence_packs").fetchone() == (1,)


def test_current_migration_is_byte_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    first = migrate_registry(path, clock=fixed_clock)
    before_hash = _database_hash(path)
    with sqlite3.connect(path) as conn:
        before_ledger = tuple(
            conn.execute(
                "SELECT version, name, checksum, applied_at "
                "FROM registry_schema_migrations ORDER BY version"
            ).fetchall()
        )

    second = migrate_registry(path, clock=fixed_clock)

    assert not first.already_at_target
    assert second.already_at_target
    assert second.applied_migrations == []
    assert _database_hash(path) == before_hash
    with sqlite3.connect(path) as conn:
        assert (
            tuple(
                conn.execute(
                    "SELECT version, name, checksum, applied_at "
                    "FROM registry_schema_migrations ORDER BY version"
                ).fetchall()
            )
            == before_ledger
        )


def test_failed_plan_rolls_back_every_statement_and_version_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "registry.sqlite"
    migrate_registry(path, target_version=1, clock=fixed_clock)
    migration_two = REGISTRY_MIGRATIONS[1]
    failing_two = replace(
        migration_two,
        statements=(
            migration_two.statements[0],
            "INSERT INTO missing_migration_test_table VALUES (1)",
        ),
    )
    monkeypatch.setattr(
        registry_migrations,
        "REGISTRY_MIGRATIONS",
        (REGISTRY_MIGRATIONS[0], failing_two, *REGISTRY_MIGRATIONS[2:]),
    )

    with pytest.raises(RegistryMigrationExecutionError, match="rolled back"):
        migrate_registry(path, target_version=2, clock=fixed_clock)

    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone() == (1,)
        assert conn.execute("SELECT COUNT(*) FROM registry_schema_migrations").fetchone() == (1,)
        assert (
            conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'bundle_imports'").fetchone()
            is None
        )


def test_unknown_legacy_schema_is_rejected_without_mutation(tmp_path: Path) -> None:
    path = tmp_path / "not-traffictwin.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE unrelated_application_data (value TEXT)")
        conn.execute("INSERT INTO unrelated_application_data VALUES ('retain me')")
    before_hash = _database_hash(path)

    with pytest.raises(RegistrySchemaIntegrityError, match="unknown schema objects"):
        migrate_registry(path, clock=fixed_clock)

    assert _database_hash(path) == before_hash


def test_future_and_inconsistent_schemas_fail_closed(tmp_path: Path) -> None:
    future_path = tmp_path / "future.sqlite"
    migrate_registry(future_path, clock=fixed_clock)
    with sqlite3.connect(future_path) as conn:
        conn.execute("PRAGMA user_version = 99")

    with pytest.raises(RegistryFutureSchemaError, match="newer"):
        inspect_registry_migrations(future_path)

    malformed_path = tmp_path / "malformed.sqlite"
    with sqlite3.connect(malformed_path) as conn:
        conn.execute("CREATE TABLE seeds (seed_id TEXT PRIMARY KEY)")

    with pytest.raises(RegistrySchemaIntegrityError, match="missing required columns"):
        migrate_registry(malformed_path, clock=fixed_clock)


def test_downgrade_is_rejected_without_mutation(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    migrate_registry(path, target_version=3, clock=fixed_clock)
    before_hash = _database_hash(path)

    with pytest.raises(RegistryMigrationError, match="downgrade is unsupported"):
        migrate_registry(path, target_version=2, clock=fixed_clock)

    assert _database_hash(path) == before_hash


def test_ledger_checksum_drift_is_detected_read_only(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    migrate_registry(path, clock=fixed_clock)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TRIGGER registry_schema_migrations_no_update")
        conn.execute(
            "UPDATE registry_schema_migrations SET checksum = ? WHERE version = 3",
            ("0" * 64,),
        )
        conn.execute(
            """
            CREATE TRIGGER registry_schema_migrations_no_update
            BEFORE UPDATE ON registry_schema_migrations
            BEGIN
                SELECT RAISE(ABORT, 'registry migration history is immutable');
            END
            """
        )
    before_hash = _database_hash(path)

    with pytest.raises(RegistrySchemaIntegrityError, match="ledger mismatch at version 3"):
        inspect_registry_migrations(path)

    assert _database_hash(path) == before_hash


def test_migration_ledger_cannot_be_updated_or_deleted(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    migrate_registry(path, clock=fixed_clock)

    with sqlite3.connect(path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="history is immutable"):
            conn.execute("UPDATE registry_schema_migrations SET name = 'changed' WHERE version = 1")
        with pytest.raises(sqlite3.IntegrityError, match="history is immutable"):
            conn.execute("DELETE FROM registry_schema_migrations WHERE version = 1")


def test_migration_definition_checksum_changes_with_sql() -> None:
    original = REGISTRY_MIGRATIONS[0]
    changed = RegistryMigration(
        version=original.version,
        name=original.name,
        statements=(*original.statements, "SELECT 1"),
        creates=original.creates,
    )

    assert changed.checksum != original.checksum


def test_registry_migration_capability_is_local_not_source_adapter_support() -> None:
    assert (
        default_export_import_manifest().supports.registry_schema_migrations
        is CapabilitySupport.TRUE
    )
    assert (
        sumo_results_capability_manifest().supports.registry_schema_migrations
        is CapabilitySupport.FALSE
    )
    assert (
        tos_data_capability_manifest().supports.registry_schema_migrations
        is CapabilitySupport.FALSE
    )
