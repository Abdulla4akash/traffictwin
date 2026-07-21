from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.ingestion.manifest_inference import (
    ConfirmationMode,
    apply_canonicalisation_to_template,
    bundle_manifest_to_yaml,
    confirm_manifest_inference,
    infer_manifest,
    load_canonicalisation_manifest,
)

FIXTURE = Path("tests/fixtures/manifest_inference/value_patterns")


def test_confirmed_inference_applies_to_bundle_and_validates(tmp_path: Path) -> None:
    draft = infer_manifest(FIXTURE)
    confirmed = confirm_manifest_inference(
        draft,
        FIXTURE,
        confirmed_by="integration-test",
        accept_suggestions=True,
    )
    template = yaml.safe_load((FIXTURE / "manifest-template.yaml").read_text(encoding="utf-8"))
    manifest = apply_canonicalisation_to_template(confirmed, template)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    shutil.copy2(FIXTURE / "external_tasks.csv", bundle / "external_tasks.csv")
    shutil.copy2(FIXTURE / "seed.yaml", bundle / "seed.yaml")
    (bundle / "manifest.yaml").write_text(bundle_manifest_to_yaml(manifest), encoding="utf-8")

    result = validate_bundle(bundle)

    assert result.report.may_import
    assert result.manifest is not None
    assert result.manifest.canonicalisation is not None
    assert result.manifest.canonicalisation.confirmation_state == "accepted_suggestions"
    assert len(result.canonical.tasks) == 3
    assert result.canonical.tasks[0].task_class.value == "T1"
    assert result.canonical.tasks[0].latency_ms == 80
    assert result.canonical.tasks[2].completed is False

    raw = manifest.model_dump(mode="json")
    raw["files"]["tasks"]["column_map"]["task_id"] = "VehicleID"
    with pytest.raises(ValidationError, match="confirmation fingerprint"):
        type(manifest).model_validate(raw)


def test_manifest_inference_cli_draft_confirm_apply_and_reload(tmp_path: Path) -> None:
    runner = CliRunner()
    draft_path = tmp_path / "draft.yaml"
    canonicalisation_path = tmp_path / "canonicalisation.yaml"
    manifest_path = tmp_path / "manifest.yaml"

    contract = runner.invoke(app, ["manifest", "contract", "--format", "json"])

    inferred = runner.invoke(
        app,
        [
            "manifest",
            "infer",
            str(FIXTURE),
            "--format",
            "yaml",
            "--output",
            str(draft_path),
        ],
    )
    confirmed = runner.invoke(
        app,
        [
            "manifest",
            "confirm",
            str(draft_path),
            str(FIXTURE),
            "--accept-suggestions",
            "--confirmed-by",
            "cli-test",
            "--output",
            str(canonicalisation_path),
        ],
    )
    applied = runner.invoke(
        app,
        [
            "manifest",
            "apply",
            str(canonicalisation_path),
            str(FIXTURE / "manifest-template.yaml"),
            "--output",
            str(manifest_path),
        ],
    )
    files = runner.invoke(
        app,
        ["manifest", "files", str(canonicalisation_path), "--format", "json"],
    )

    assert contract.exit_code == 0, contract.output
    assert '"confirmation_policy"' in contract.output
    assert inferred.exit_code == 0, inferred.output
    assert confirmed.exit_code == 0, confirmed.output
    assert "analysis_ready: true" in confirmed.output
    assert applied.exit_code == 0, applied.output
    assert manifest_path.is_file()
    assert files.exit_code == 0, files.output
    loaded = load_canonicalisation_manifest(canonicalisation_path)
    assert loaded.confirmation_state is ConfirmationMode.ACCEPTED_SUGGESTIONS


def test_manifest_inference_cli_requires_edit_for_ambiguity(tmp_path: Path) -> None:
    runner = CliRunner()
    source = Path("tests/fixtures/manifest_inference/ambiguous")
    draft_path = tmp_path / "draft.yaml"
    output = tmp_path / "confirmed.yaml"
    inferred = runner.invoke(
        app,
        ["manifest", "infer", str(source), "--format", "yaml", "--output", str(draft_path)],
    )

    rejected = runner.invoke(
        app,
        [
            "manifest",
            "confirm",
            str(draft_path),
            str(source),
            "--accept-suggestions",
            "--confirmed-by",
            "cli-test",
            "--output",
            str(output),
        ],
    )
    edited = runner.invoke(
        app,
        [
            "manifest",
            "confirm",
            str(draft_path),
            str(source),
            "--confirmed-by",
            "cli-test",
            "--kind",
            "entity.csv=traffic_obs",
            "--unit",
            "entity.csv:timestamp=s",
            "--output",
            str(output),
        ],
    )

    assert inferred.exit_code == 0, inferred.output
    assert rejected.exit_code == 1
    assert "ambiguous or unresolved" in rejected.output
    assert edited.exit_code == 0, edited.output
    assert "confirmation_state: edited" in edited.output


def test_manifest_confirmation_cli_cannot_overwrite_raw_csv(tmp_path: Path) -> None:
    runner = CliRunner()
    source = tmp_path / "source"
    shutil.copytree(FIXTURE, source)
    draft_path = tmp_path / "draft.yaml"
    inferred = runner.invoke(
        app,
        ["manifest", "infer", str(source), "--format", "yaml", "--output", str(draft_path)],
    )
    raw_path = source / "external_tasks.csv"
    before = raw_path.read_bytes()

    result = runner.invoke(
        app,
        [
            "manifest",
            "confirm",
            str(draft_path),
            str(source),
            "--accept-suggestions",
            "--confirmed-by",
            "cli-test",
            "--output",
            str(raw_path),
            "--overwrite",
        ],
    )

    assert inferred.exit_code == 0, inferred.output
    assert result.exit_code == 1
    assert "cannot overwrite" in result.output
    assert raw_path.read_bytes() == before
