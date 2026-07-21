from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import FIXTURES
from typer.testing import CliRunner

from traffictwin.cli import app


def test_canonical_cache_cli_contract_cold_warm_and_status(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    bundle = FIXTURES / "baseline_valid"

    contract = CliRunner().invoke(app, ["bundle", "cache-contract", "--format", "json"])
    before = CliRunner().invoke(
        app,
        [
            "bundle",
            "cache-status",
            str(bundle),
            "--cache-root",
            str(cache_root),
            "--format",
            "json",
        ],
    )
    cold = CliRunner().invoke(
        app,
        [
            "bundle",
            "cache-validate",
            str(bundle),
            "--cache-root",
            str(cache_root),
            "--format",
            "json",
        ],
    )
    warm = CliRunner().invoke(
        app,
        [
            "bundle",
            "cache-validate",
            str(bundle),
            "--cache-root",
            str(cache_root),
            "--format",
            "json",
        ],
    )

    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["capability_id"] == "OPS-02"
    assert before.exit_code == 0, before.output
    assert json.loads(before.output)["state"] == "miss"
    assert cold.exit_code == 0, cold.output
    assert json.loads(cold.output)["cache"]["state"] == "written"
    assert warm.exit_code == 0, warm.output
    warm_payload = json.loads(warm.output)
    assert warm_payload["cache"]["state"] == "hit"
    assert warm_payload["validation"]["canonical_record_counts"] == {
        "tasks": 3,
        "infrastructure": 4,
        "vehicles": 0,
        "traffic": 2,
        "trips": 2,
        "incidents": 0,
    }


def test_canonical_cache_cli_refuses_raw_bundle_overlap(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()

    result = CliRunner().invoke(
        app,
        ["bundle", "cache-status", str(bundle), "--cache-root", str(bundle / ".cache")],
    )

    assert result.exit_code == 1
    assert "outside the raw directory bundle" in result.output


def test_canonical_cache_cli_rejects_format_before_writing(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"

    result = CliRunner().invoke(
        app,
        [
            "bundle",
            "cache-validate",
            str(FIXTURES / "baseline_valid"),
            "--cache-root",
            str(cache_root),
            "--format",
            "yaml",
        ],
    )

    assert result.exit_code == 1
    assert "only --format text or json" in result.output
    assert not cache_root.exists()
