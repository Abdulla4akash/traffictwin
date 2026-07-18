from __future__ import annotations

import json
from pathlib import Path

from tests.tos_helpers import write_tos_package
from typer.testing import CliRunner

from traffictwin.cli import app

runner = CliRunner()


def test_release_static_site_cli(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    initialise = runner.invoke(app, ["demo", "initialise", str(workspace)])
    assert initialise.exit_code == 0

    output = tmp_path / "public"
    result = runner.invoke(
        app,
        ["release", "stage-demo-site", str(workspace), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "synthetic: true" in result.stdout
    assert (output / "index.html").exists()


def test_tos_readiness_supervisor_and_publication_gate_cli(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    readiness = runner.invoke(
        app,
        ["integration", "tos", "readiness", str(package), "--format", "json"],
    )
    assert readiness.exit_code == 0
    payload = json.loads(readiness.stdout)
    assert payload["capabilities"]["direct_launch"] == "blocked"

    pack_path = tmp_path / "supervisor"
    pack = runner.invoke(
        app,
        [
            "integration",
            "tos",
            "supervisor-pack",
            str(package),
            "--output",
            str(pack_path),
            "--variation",
            "capscalar_mappo",
        ],
    )
    assert pack.exit_code == 0
    assert "private_research_material" in pack.stdout
    assert (pack_path / "manifest.json").exists()

    blocked = runner.invoke(
        app,
        [
            "integration",
            "tos",
            "stage-public-atlas",
            str(package),
            "--output",
            str(tmp_path / "blocked"),
        ],
    )
    assert blocked.exit_code == 1
    assert "confirm-publication-permission" in blocked.output
