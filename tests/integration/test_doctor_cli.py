from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.helpers import fixed_clock
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.storage.migrations import migrate_registry


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_doctor_cli_reports_default_health_and_the_versioned_contract() -> None:
    report = CliRunner().invoke(app, ["doctor", "--format", "json"])
    contract = CliRunner().invoke(
        app,
        ["doctor", "--contract", "--format", "json"],
    )

    assert report.exit_code == 0, report.output
    payload = json.loads(report.output)
    assert payload["capability_id"] == "OPS-03"
    assert payload["overall_status"] == "healthy"
    assert payload["read_only"] is True
    assert payload["mutations_performed"] is False
    assert len(payload["report_fingerprint"]) == 64
    assert contract.exit_code == 0, contract.output
    contract_payload = json.loads(contract.output)
    assert contract_payload["contract_version"] == "traffictwin-doctor-v1"
    assert contract_payload["command"] == "traffictwin doctor"
    assert len(contract_payload["fingerprint"]) == 64


def test_doctor_cli_healthy_registry_is_read_only(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    migrate_registry(registry, clock=fixed_clock)
    before_hash = _sha256(registry)
    before_mtime = registry.stat().st_mtime_ns

    result = CliRunner().invoke(
        app,
        ["doctor", "--registry", str(registry), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["overall_status"] == "healthy"
    assert payload["registries"][0]["migration"]["state"] == "current"
    assert _sha256(registry) == before_hash
    assert registry.stat().st_mtime_ns == before_mtime


def test_doctor_cli_returns_nonzero_for_corrupt_registry_without_changing_it(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "corrupt.sqlite"
    registry.write_bytes(b"corrupt registry copy")
    before_hash = _sha256(registry)

    result = CliRunner().invoke(
        app,
        ["doctor", "--registry", str(registry), "--format", "json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["overall_status"] == "blocked"
    assert payload["blocking_check_ids"] == ["registry.target-1.integrity"]
    assert _sha256(registry) == before_hash


def test_doctor_cli_rejects_invalid_format_before_inspection(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    registry.write_bytes(b"untouched")
    before_hash = _sha256(registry)

    result = CliRunner().invoke(
        app,
        ["doctor", "--registry", str(registry), "--format", "yaml"],
    )

    assert result.exit_code == 1
    assert "only --format text or json" in result.output
    assert _sha256(registry) == before_hash
