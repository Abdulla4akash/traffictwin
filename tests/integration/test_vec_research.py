"""Checked-in real-evidence and rebuild acceptance tests for VEC-12."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, cast

from traffictwin.integration.vec_research import (
    VecEndToEndReceipt,
    create_vec_end_to_end_archive,
    vec_end_to_end_contract,
    verify_vec_end_to_end_archive,
)
from traffictwin.integration.vec_research.models import VEC_RESEARCH_ARCHIVE_NAME

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "docs/reference/generated"
ARCHIVE = GENERATED / VEC_RESEARCH_ARCHIVE_NAME
RECEIPT = GENERATED / "vec_end_to_end_research_artifact_receipt.json"


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_checked_in_archive_receipt_and_contract_are_self_consistent() -> None:
    payload = ARCHIVE.read_bytes()
    receipt = VecEndToEndReceipt.model_validate_json(RECEIPT.read_bytes())
    result = verify_vec_end_to_end_archive(ARCHIVE)

    assert result.valid is True
    assert receipt.archive_sha256 == hashlib.sha256(payload).hexdigest()
    assert receipt.archive_size_bytes == len(payload)
    assert receipt.artifact_id == result.artifact_id
    assert receipt.manifest_fingerprint == result.manifest_fingerprint
    assert receipt.member_count == result.member_count == 27
    assert _read_json(GENERATED / "vec_end_to_end_contract.json") == (
        vec_end_to_end_contract().model_dump(mode="json")
    )


def test_fresh_rebuild_is_byte_identical_to_checked_in_archive(tmp_path: Path) -> None:
    rebuilt = tmp_path / VEC_RESEARCH_ARCHIVE_NAME

    receipt = create_vec_end_to_end_archive(GENERATED, rebuilt)

    assert rebuilt.read_bytes() == ARCHIVE.read_bytes()
    assert receipt.archive_sha256 == hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()


def test_archive_embeds_exact_safe_evidence_and_declares_complete_boundary() -> None:
    with zipfile.ZipFile(ARCHIVE, mode="r") as handle:
        manifest = json.loads(handle.read("manifest.json"))
        assert (
            handle.read("evidence/vec_reproduction_report.json")
            == (GENERATED / "vec_reproduction_report.json").read_bytes()
        )
        assert (
            handle.read("evidence/vec_scientific_admission_report.json")
            == (GENERATED / "vec_scientific_admission_report.json").read_bytes()
        )
        assert (
            handle.read("publication/manifest.json")
            == (GENERATED / "vec_dissertation_pack/manifest.json").read_bytes()
        )
        combined = b"\n".join(handle.read(name) for name in handle.namelist())

    assert manifest["reproduction"]["selected_seed_label"] == ("protocol_seed_not_best_of_seeds")
    assert manifest["scientific"]["selection_label"] == "_s102_best_of_seeds"
    assert len(manifest["capabilities"]) == 11
    assert len(manifest["exclusions"]) == 8
    assert manifest["raw_external_bytes_embedded"] is False
    assert manifest["publication"]["public_hosting_authorized"] is False
    assert b"/Users/" not in combined
    assert b"file://" not in combined
    assert b".npz" in combined  # named only in metadata/limitations; no raw NPZ member exists
    assert not any(
        item["path"].endswith((".npz", ".xml", ".xml.gz")) for item in manifest["inventory"]
    )
