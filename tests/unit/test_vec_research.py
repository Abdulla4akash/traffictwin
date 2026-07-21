"""Determinism, safety, and refusal tests for the VEC-12 research artifact."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.integration.vec_research import (
    VecEndToEndManifest,
    build_vec_end_to_end_artifact,
    create_vec_end_to_end_archive,
    vec_end_to_end_contract,
    verify_vec_end_to_end_archive,
)
from traffictwin.integration.vec_research.models import (
    VEC_RESEARCH_ALL_PATHS,
    VEC_RESEARCH_ARCHIVE_NAME,
    VEC_RESEARCH_PAYLOAD_PATHS,
)

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "docs/reference/generated"


def _archive(directory: Path) -> Path:
    return directory / VEC_RESEARCH_ARCHIVE_NAME


def test_contract_is_exactly_bounded_and_deterministic() -> None:
    contract = vec_end_to_end_contract()

    assert contract.status == "implemented"
    assert contract.permitted_members == VEC_RESEARCH_ALL_PATHS
    assert len(contract.permitted_members) == 27
    assert contract.fixed_zip_timestamp == (1980, 1, 1, 0, 0, 0)
    assert contract.maximum_total_bytes == 2_000_000
    assert "raw source/execution bytes" in contract.publication_policy
    assert contract.fingerprint() == vec_end_to_end_contract().fingerprint()


def test_builder_reconciles_all_prior_capabilities_and_keeps_runs_distinct() -> None:
    built = build_vec_end_to_end_artifact(GENERATED)
    manifest = built.manifest

    assert tuple(sorted(built.members)) == VEC_RESEARCH_ALL_PATHS
    assert tuple(item.path for item in manifest.inventory) == VEC_RESEARCH_PAYLOAD_PATHS
    assert [item.capability for item in manifest.capabilities] == [
        f"VEC-{index:02d}" for index in range(1, 12)
    ]
    assert manifest.reproduction.case_id == "ukfleettrain-mappo_we_uk2030_fs0"
    assert manifest.reproduction.selected_seed_label == "protocol_seed_not_best_of_seeds"
    assert manifest.scientific.selected_run_label == "fcd_s102_uk2030_we_fs0"
    assert manifest.scientific.selection_label == "_s102_best_of_seeds"
    assert manifest.scientific.available_metric_count == 18
    assert manifest.scientific.unavailable_metric_count == 8
    assert [item.status for item in manifest.scientific.diagnostics] == [
        "blocked",
        "blocked",
        "conditional",
        "blocked",
    ]
    assert all(not item.raw_external_bytes for item in manifest.inventory)
    assert len(manifest.exclusions) == 8


def test_archives_are_byte_identical_offline_verifiable_and_new_only(tmp_path: Path) -> None:
    first = _archive(tmp_path / "first")
    second = _archive(tmp_path / "second")

    first_receipt = create_vec_end_to_end_archive(GENERATED, first)
    second_receipt = create_vec_end_to_end_archive(GENERATED, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_receipt == second_receipt
    verified = verify_vec_end_to_end_archive(first)
    assert verified.valid is True
    assert verified.archive_sha256 == first_receipt.archive_sha256
    assert verified.member_count == 27
    assert verified.checksum_count == 26
    with pytest.raises(FileExistsError):
        create_vec_end_to_end_archive(GENERATED, first)


def test_builder_rejects_stale_generated_evidence(tmp_path: Path) -> None:
    copied = tmp_path / "generated"
    shutil.copytree(GENERATED, copied)
    contract_path = copied / "vec_runner_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["status"] = "planned"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ValueError, match="stale"):
        build_vec_end_to_end_artifact(copied)

    linked = tmp_path / "linked-generated"
    linked.symlink_to(GENERATED, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        build_vec_end_to_end_artifact(linked)

    nested_link = tmp_path / "nested-link"
    shutil.copytree(GENERATED, nested_link)
    shutil.rmtree(nested_link / "vec_dissertation_pack")
    (nested_link / "vec_dissertation_pack").symlink_to(
        GENERATED / "vec_dissertation_pack", target_is_directory=True
    )
    with pytest.raises(ValueError, match="real directory"):
        build_vec_end_to_end_artifact(nested_link)


def test_verifier_rejects_an_extra_member_and_corrupt_bytes(tmp_path: Path) -> None:
    archive = _archive(tmp_path)
    create_vec_end_to_end_archive(GENERATED, archive)
    extra = tmp_path / "extra.zip"
    shutil.copyfile(archive, extra)
    with zipfile.ZipFile(extra, mode="a", compression=zipfile.ZIP_STORED) as handle:
        handle.writestr("raw/source.npz", b"not permitted")
    assert verify_vec_end_to_end_archive(extra).valid is False

    corrupted = tmp_path / "corrupted.zip"
    payload = bytearray(archive.read_bytes())
    payload[len(payload) // 2] ^= 0xFF
    corrupted.write_bytes(payload)
    assert verify_vec_end_to_end_archive(corrupted).valid is False


def test_manifest_cannot_strengthen_permission_or_anonymity_claims() -> None:
    manifest = build_vec_end_to_end_artifact(GENERATED).manifest.model_dump(mode="json")
    manifest["publication"]["public_hosting_authorized"] = True
    manifest["publication"]["anonymity_claimed"] = True

    with pytest.raises(ValidationError):
        VecEndToEndManifest.model_validate(manifest)


def test_cli_exposes_contract_create_and_offline_verify(tmp_path: Path) -> None:
    runner = CliRunner()
    contract = runner.invoke(app, ["integration", "vec", "research-contract", "--format", "json"])
    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["capability"] == "VEC-12"

    archive = _archive(tmp_path)
    created = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "research-create",
            str(GENERATED),
            "--output",
            str(archive),
        ],
    )
    assert created.exit_code == 0, created.output
    verified = runner.invoke(
        app,
        ["integration", "vec", "research-verify", str(archive), "--format", "json"],
    )
    assert verified.exit_code == 0, verified.output
    assert json.loads(verified.output)["valid"] is True
