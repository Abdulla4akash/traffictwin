from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import fixed_clock
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.rules.config import RuleSetConfig
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def test_nearest_flip_cli_emits_verified_bundle_result_and_text_export(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")

    result = CliRunner().invoke(
        app,
        ["diagnose", "nearest-flip", str(bundle), "R8", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["capability"] == "DIA-05"
    assert payload["status"] == "available"
    assert payload["source_status"] == "not_triggered"
    assert payload["candidate_status"] == "triggered"
    assert payload["candidates"][0]["parameter_path"] == ("r8.minimum_energy_per_completed_task_j")
    assert payload["evidence_pack_fingerprint"]
    assert payload["current_result_fingerprint"]
    assert payload["candidate_result_fingerprint"]

    output = tmp_path / "nearest-flip.txt"
    text = CliRunner().invoke(
        app,
        [
            "diagnose",
            "nearest-flip",
            str(bundle),
            "R8",
            "--format",
            "text",
            "--output",
            str(output),
        ],
    )
    assert text.exit_code == 0
    assert "nearest-flip analysis written" in text.stdout
    rendered = output.read_text(encoding="utf-8")
    assert "status: available" in rendered
    assert "candidate: r8.minimum_energy_per_completed_task_j" in rendered
    assert "delta=" in rendered


def test_nearest_flip_cli_accepts_saved_evidence_pack(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    validation = validate_bundle(bundle)
    collection = compute_metrics_for_bundle(validation, clock=fixed_clock)
    pack = build_evidence_pack(validation, collection, clock=fixed_clock)
    pack_path = tmp_path / "evidence.json"
    pack_path.write_text(pack.to_json(), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["diagnose", "nearest-flip", str(pack_path), "R8", "--format", "json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "available"


def test_nearest_flip_cli_reports_discrete_constraint_and_unsupported_rule(
    tmp_path: Path,
) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    config_path = tmp_path / "rules.json"
    config_path.write_text(
        RuleSetConfig.model_validate({"r8": {"minimum_completed_tasks": 100}}).model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    constrained = CliRunner().invoke(
        app,
        [
            "diagnose",
            "nearest-flip",
            str(bundle),
            "R8",
            "--rule-config",
            str(config_path),
        ],
    )
    unsupported = CliRunner().invoke(
        app,
        ["diagnose", "nearest-flip", str(bundle), "R4"],
    )

    assert constrained.exit_code == 0
    constrained_payload = json.loads(constrained.stdout)
    assert constrained_payload["reason_code"] == "DISCRETE_CONSTRAINT_UNMET"
    assert constrained_payload["constraints"][0]["mutable_by_analysis"] is False
    assert unsupported.exit_code == 0
    assert json.loads(unsupported.stdout)["status"] == "unsupported"


def test_nearest_flip_cli_rejects_invalid_format(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")

    result = CliRunner().invoke(
        app,
        ["diagnose", "nearest-flip", str(bundle), "R8", "--format", "yaml"],
    )

    assert result.exit_code == 1
    assert "only --format text or json is supported" in result.stderr
