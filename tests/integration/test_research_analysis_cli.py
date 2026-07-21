from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.experiments.tracking import ProtocolTracker


def test_cli_exports_research_analysis_and_tracks_protocol_slots(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    registry = workspace / "registry.sqlite"
    runner = CliRunner()

    winner = runner.invoke(
        app,
        [
            "experiment",
            "winner-map",
            "--registry",
            str(registry),
            "--experiment-id",
            "exp-standalone-trivial",
        ],
    )
    assert winner.exit_code == 0, winner.output
    assert len(json.loads(winner.output)["entries"]) == 1

    portfolio = runner.invoke(
        app,
        [
            "experiment",
            "portfolio",
            "--registry",
            str(registry),
            "--experiment-id",
            "exp-standalone-trivial",
        ],
    )
    assert portfolio.exit_code == 0, portfolio.output
    assert json.loads(portfolio.output)["available_seed_count"] == 1

    evidence = runner.invoke(
        app,
        [
            "experiment",
            "evidence",
            "--registry",
            str(registry),
            "--experiment-id",
            "exp-standalone-trivial",
        ],
    )
    assert evidence.exit_code == 0, evidence.output
    assert json.loads(evidence.output)["run_context"]["experiment_id"] == ("exp-standalone-trivial")

    paired_evidence = runner.invoke(
        app,
        [
            "experiment",
            "evidence",
            "--registry",
            str(registry),
            "--experiment-id",
            "exp-synthetic-portfolio-study",
            "--training-run",
            "run-portfolio-under_offloading-always-local-1-1",
            "--validation-run",
            "run-portfolio-s5_stadium_event_siting-always-local-1-1",
            "--training-run",
            "run-portfolio-under_offloading-always-local-2-2",
            "--validation-run",
            "run-portfolio-s6_road_clearing_corridor-always-local-2-2",
        ],
    )
    assert paired_evidence.exit_code == 0, paired_evidence.output
    paired_payload = json.loads(paired_evidence.output)
    pair_count = next(
        metric
        for metric in paired_payload["metric_collection"]["results"]
        if metric["metric_key"] == "experiment.training_validation.pair_count"
    )
    assert pair_count["value"] == 2

    portfolio_study = runner.invoke(
        app,
        [
            "experiment",
            "portfolio-study",
            "--registry",
            str(registry),
            "--experiment-id",
            "exp-synthetic-portfolio-study",
        ],
    )
    assert portfolio_study.exit_code == 0, portfolio_study.output
    study_payload = json.loads(portfolio_study.output)
    assert len(study_payload["development_seed_ids"]) == 3
    assert len(study_payload["held_out_seed_ids"]) == 2
    assert len(study_payload["held_out_constituents"]) == 3

    tracking = runner.invoke(
        app,
        [
            "experiment",
            "track-init",
            "--registry",
            str(registry),
            "--experiment-id",
            "exp-standalone-demo",
        ],
    )
    assert tracking.exit_code == 0, tracking.output
    protocol_id = ProtocolTracker(registry).list_protocol_ids()[0]
    update = runner.invoke(
        app,
        [
            "experiment",
            "track-update",
            "--registry",
            str(registry),
            "--protocol-id",
            protocol_id,
            "--slot-id",
            "slot-0001",
            "--status",
            "received",
        ],
    )
    assert update.exit_code == 0, update.output
    listed = runner.invoke(
        app,
        [
            "experiment",
            "track-list",
            "--registry",
            str(registry),
            "--protocol-id",
            protocol_id,
            "--format",
            "json",
        ],
    )
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["slots"][0]["status"] == "received"
