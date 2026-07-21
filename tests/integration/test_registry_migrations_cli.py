from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app


def test_registry_migration_cli_upgrades_and_reports_json(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE seeds (
                seed_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO seeds VALUES ('seed-cli', '{\"preserved\":true}', 'a', 'b')")

    migration = CliRunner().invoke(
        app,
        ["registry", "migrate", str(path), "--format", "json"],
    )
    status = CliRunner().invoke(
        app,
        ["registry", "migration-status", str(path), "--format", "json"],
    )

    assert migration.exit_code == 0, migration.output
    migration_payload = json.loads(migration.output)
    assert migration_payload["capability_id"] == "OPS-01"
    assert migration_payload["initial_version"] == 0
    assert migration_payload["final_version"] == 5
    assert migration_payload["legacy_schema_detected"] is True
    assert [item["version"] for item in migration_payload["applied_migrations"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert status.exit_code == 0, status.output
    status_payload = json.loads(status.output)
    assert status_payload["state"] == "current"
    assert status_payload["applied_versions"] == [1, 2, 3, 4, 5]
    assert status_payload["pending_versions"] == []
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT payload FROM seeds WHERE seed_id = 'seed-cli'").fetchone() == (
            '{"preserved":true}',
        )


def test_registry_migration_cli_noop_is_byte_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    path.touch()
    first = CliRunner().invoke(app, ["registry", "migrate", str(path)])
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    second = CliRunner().invoke(app, ["registry", "migrate", str(path), "--format", "json"])
    after = hashlib.sha256(path.read_bytes()).hexdigest()

    assert first.exit_code == 0, first.output
    assert "applied_migrations: 1, 2, 3, 4, 5" in first.output
    assert second.exit_code == 0, second.output
    assert json.loads(second.output)["already_at_target"] is True
    assert before == after


def test_registry_migration_contract_and_future_schema_failure(tmp_path: Path) -> None:
    contract = CliRunner().invoke(app, ["registry", "migration-contract", "--format", "json"])
    assert contract.exit_code == 0, contract.output
    contract_payload = json.loads(contract.output)
    assert contract_payload["contract_version"] == "registry-migrations-v1"
    assert contract_payload["current_registry_schema_version"] == 5

    path = tmp_path / "future.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version = 99")
    failed = CliRunner().invoke(app, ["registry", "migrate", str(path)])

    assert failed.exit_code == 1
    assert "newer than this TrafficTwin build" in failed.output
