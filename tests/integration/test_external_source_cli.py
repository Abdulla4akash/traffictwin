from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from tests.tos_helpers import write_tos_package
from typer.testing import CliRunner

from traffictwin.cli import app

SUMO_FIXTURE = Path("tests/fixtures/sumo/square_public")


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_external_cli_contract_discovery_and_sumo_inspection_are_portable(
    tmp_path: Path,
) -> None:
    package = tmp_path / "sumo"
    shutil.copytree(SUMO_FIXTURE, package)
    before = _hashes(package)
    runner = CliRunner()

    catalogue = runner.invoke(
        app,
        ["integration", "external", "contract", "--format", "json"],
    )
    contract = runner.invoke(
        app,
        [
            "integration",
            "external",
            "contract",
            "--adapter",
            "sumo_results_v1",
            "--format",
            "json",
        ],
    )
    discovery = runner.invoke(
        app,
        ["integration", "external", "discover", str(package), "--format", "json"],
    )
    inspection = runner.invoke(
        app,
        ["integration", "external", "inspect", str(package), "--format", "json"],
    )

    assert catalogue.exit_code == 0, catalogue.output
    assert contract.exit_code == 0, contract.output
    assert discovery.exit_code == 0, discovery.output
    assert inspection.exit_code == 0, inspection.output
    assert json.loads(catalogue.output)["capability_id"] == "OPS-05"
    assert json.loads(contract.output)["conversion"]["level"] == "partial_canonical"
    assert json.loads(discovery.output)["candidate_adapter_ids"] == ["sumo_results_v1"]
    payload = json.loads(inspection.output)
    assert payload["validation"]["outcome"] == "accepted_with_warnings"
    assert payload["validation"]["output_counts"]["canonical_trips"] == 127
    assert payload["conversion"]["level"] == "partial_canonical"
    assert str(package.resolve()) not in inspection.output
    assert before == _hashes(package)


def test_external_cli_inspects_tos_as_aggregate_summary_with_unknown_rights(
    tmp_path: Path,
) -> None:
    package = write_tos_package(tmp_path / "tos")

    result = CliRunner().invoke(
        app,
        [
            "integration",
            "external",
            "inspect",
            str(package),
            "--deep",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["adapter_id"] == "tos_data_read_only"
    assert payload["conversion"]["level"] == "aggregate_summary"
    provenance = {item["key"]: item for item in payload["observed_provenance"]}
    assert provenance["licence_statement"]["status"] == "unknown"
    assert provenance["redistribution_permission"]["status"] == "unknown"


def test_external_cli_fails_closed_for_unknown_and_ambiguous_sources(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown"
    unknown.mkdir()
    runner = CliRunner()

    discovery = runner.invoke(
        app,
        ["integration", "external", "discover", str(unknown), "--format", "json"],
    )
    inspection = runner.invoke(
        app,
        ["integration", "external", "inspect", str(unknown), "--format", "json"],
    )

    assert discovery.exit_code == 1
    assert json.loads(discovery.output)["status"] == "no_match"
    assert inspection.exit_code == 1
    assert "no registered external-source adapter" in inspection.output

    ambiguous = tmp_path / "ambiguous"
    shutil.copytree(SUMO_FIXTURE, ambiguous)
    (ambiguous / "evals").mkdir()
    (ambiguous / "evals/eval_results_master.csv").write_text("unparsed\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["integration", "external", "inspect", str(ambiguous)],
    )
    assert result.exit_code == 1
    assert "multiple external-source adapters matched" in result.output
