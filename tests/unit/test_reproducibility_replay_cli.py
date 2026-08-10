# ruff: noqa: E501, F401, I001, ANN001, S101
"""CLI tests for reproducibility replay."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.reproducibility_replay.cli import app
from traffictwin.study_capsule import (
    StudyCapsuleEvidenceLabel,
    StudyCapsuleMemberKind,
    StudyCapsulePublicationPolicy,
    StudyCapsuleRequest,
    StudyCapsuleMemberInput,
    _sha256,
    build_study_capsule,
)
from traffictwin.study_capsule import _zip_bytes

runner = CliRunner()


def _build_capsule(tmp_path: Path) -> Path:
    payload = {
        "schema_version": "1.0",
        "report_id": "cli-test-report",
        "spec": {
            "schema_version": "1.0",
            "pre_duration_s": 10,
            "event_duration_s": 10,
            "post_duration_s": 10,
            "bin_width_s": 5,
            "metric_key": "task.completion.rate",
            "metric_version": "1.0",
            "metric_unit": "ratio",
        },
        "accepted_runs": [],
        "metric_points": [],
        "phase_summaries": [],
        "pairwise_deltas": [],
        "warnings": [],
        "limitations": [],
        "fingerprint": "a" * 64,
    }
    content = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    inp = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.DETERMINISTIC_REPORT,
        logical_id="rep-cli",
        fingerprint=_sha256(b"rep-cli"),
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=content,
    )
    req = StudyCapsuleRequest(
        creation_date="2026-08-09",
        study_id="cli-capsule-001",
        capsule_title="CLI Test Capsule",
        members=[inp],
        limitations=["cli test"],
    )
    built = build_study_capsule(req)
    capsule_bytes = _zip_bytes(built.members)
    dest = tmp_path / "cli-capsule.zip"
    dest.write_bytes(capsule_bytes)
    return dest


def test_cli_verify_success(tmp_path: Path) -> None:
    capsule = _build_capsule(tmp_path)
    result = runner.invoke(app, ["verify", str(capsule)])
    assert result.exit_code == 0
    assert "valid: True" in result.stdout


def test_cli_verify_json(tmp_path: Path) -> None:
    capsule = _build_capsule(tmp_path)
    result = runner.invoke(app, ["verify", str(capsule), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["valid"] is True


def test_cli_plan_from_capsule(tmp_path: Path) -> None:
    capsule = _build_capsule(tmp_path)
    result = runner.invoke(app, ["plan", "--capsule", str(capsule)])
    assert result.exit_code == 0
    assert "entries:" in result.stdout or "verification_status" in result.stdout


def test_cli_plan_from_artifact(tmp_path: Path) -> None:
    # Use a more realistic minimal report payload that will be allowlisted
    report_text = Path("tests/fixtures/resource_strategy/synthetic_report_v1.json").read_text(
        encoding="utf-8"
    )
    artifact = tmp_path / "artifact.json"
    artifact.write_text(report_text, encoding="utf-8")
    result = runner.invoke(app, ["plan", "--artifact", str(artifact)])
    assert result.exit_code == 0
    assert "replayable" in result.stdout.lower() or "entries" in result.stdout


def test_cli_run_requires_selection(tmp_path: Path) -> None:
    capsule = _build_capsule(tmp_path)
    result = runner.invoke(app, ["run", str(capsule)])
    assert result.exit_code != 0
    assert (
        "no automatic" in result.stdout.lower()
        or "no automatic" in result.stderr.lower()
        or "provide --select" in result.stdout.lower()
        or "provide --select" in result.stderr.lower()
    )


def test_cli_run_with_selection(tmp_path: Path) -> None:
    # Build a capsule with a real resource strategy report that is replayable
    import json as _json

    report_text = Path("tests/fixtures/resource_strategy/synthetic_report_v1.json").read_text(
        encoding="utf-8"
    )
    report = _json.loads(report_text)
    content = _json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    inp = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.CONSEQUENCE_REPORT,
        logical_id="comp-cli-run",
        fingerprint=_sha256(b"comp-cli-run"),
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=content,
    )
    req = StudyCapsuleRequest(
        creation_date="2026-08-09",
        study_id="cli-run-001",
        capsule_title="CLI Run Capsule",
        members=[inp],
        limitations=["cli run test"],
    )
    built = build_study_capsule(req)
    capsule_bytes = _zip_bytes(built.members)
    capsule = tmp_path / "cli-run-capsule.zip"
    capsule.write_bytes(capsule_bytes)

    # First plan to discover logical_id
    from traffictwin.reproducibility_replay.service import build_replay_plan_from_capsule_bytes

    plan = build_replay_plan_from_capsule_bytes(capsule_bytes)
    replayable = [e for e in plan.entries if e.replayable]
    assert replayable, "need at least one replayable entry"
    spec = f"{replayable[0].artifact_kind.value}:{replayable[0].logical_id}"
    result = runner.invoke(app, ["run", str(capsule), "--select", spec, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "receipt_fingerprint" in data or "receipt_id" in data
    assert data["executed_count"] >= 1


def test_cli_compare_and_show_receipt(tmp_path: Path) -> None:
    import json as _json

    report_text = Path("tests/fixtures/resource_strategy/synthetic_report_v1.json").read_text(
        encoding="utf-8"
    )
    report = _json.loads(report_text)
    content = _json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    inp = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.CONSEQUENCE_REPORT,
        logical_id="comp-show",
        fingerprint=_sha256(b"comp-show"),
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=content,
    )
    req = StudyCapsuleRequest(
        creation_date="2026-08-09",
        study_id="cli-show-001",
        capsule_title="CLI Show Capsule",
        members=[inp],
        limitations=["cli show test"],
    )
    built = build_study_capsule(req)
    capsule_bytes = _zip_bytes(built.members)
    capsule = tmp_path / "cli-show-capsule.zip"
    capsule.write_bytes(capsule_bytes)
    from traffictwin.reproducibility_replay.service import build_replay_plan_from_capsule_bytes

    plan = build_replay_plan_from_capsule_bytes(capsule_bytes)
    replayable = [e for e in plan.entries if e.replayable][0]
    spec = f"{replayable.artifact_kind.value}:{replayable.logical_id}"
    run_result = runner.invoke(app, ["run", str(capsule), "--select", spec, "--json"])
    assert run_result.exit_code == 0
    receipt_data = json.loads(run_result.stdout)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt_data), encoding="utf-8")
    comp_result = runner.invoke(app, ["compare", str(receipt_path)])
    assert comp_result.exit_code == 0
    show_result = runner.invoke(app, ["show-receipt", str(receipt_path)])
    assert show_result.exit_code == 0
    assert "receipt_id" in show_result.stdout or "receipt_fingerprint" in show_result.stdout
