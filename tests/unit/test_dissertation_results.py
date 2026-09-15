"""Adversarial ingestion checks for the original compact dissertation evidence."""

from __future__ import annotations

import io
import json
import stat
import struct
import warnings
import zipfile
from dataclasses import asdict
from pathlib import Path

import pytest

from traffictwin.integration.dissertation_results import (
    MAX_PACKET_BYTES,
    DissertationResults,
    ResultsImportError,
    load_builtin_results,
    load_results_directory,
    load_results_zip,
)


@pytest.fixture(scope="module")
def study() -> DissertationResults:
    return load_builtin_results()


def _zip(
    files: dict[str, bytes],
    *,
    extra: tuple[str, bytes] | None = None,
    special_name: str | None = None,
    special_mode: int = 0o100644,
    compression: int = zipfile.ZIP_STORED,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.compress_type = compression
            info.external_attr = (special_mode if name == special_name else 0o100644) << 16
            archive.writestr(info, content)
        if extra is not None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(*extra)
    return buffer.getvalue()


def _write_directory(study: DissertationResults, path: Path) -> None:
    for name, data in study.files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def test_original_primary_evidence_and_denominators(study: DissertationResults) -> None:
    assert len(study.cells) == 32
    assert len(study.files) == 72
    assert len(study.receipt_summary) == 32
    assert len({(cell.block, cell.arm) for cell in study.cells}) == 32
    assert [item.mean_pp for item in study.primary] == pytest.approx(
        [4.13689639883791, -3.503967132674223, 0.630522983822198]
    )
    assert study.seal_sha256 == "65028659439a8808fe825e0142e8276c9c293e09085b2db036131434085beca3"
    first = study.cells[0]
    assert first.offered == 1744761
    assert first.successes == 1525913
    assert first.attainment_pct == 100 * first.successes / first.offered
    assert first.attainment_pct != 100 * first.successes / first.admitted
    assert first.terminal_failures + first.admitted == first.offered
    assert first.admitted_misses + first.successes == first.admitted


def test_exports_preserve_original_bytes_and_identity(study: DissertationResults) -> None:
    packet = study.export_zip()
    imported = load_results_zip(packet)
    assert imported.files == study.files
    assert imported.hashes == study.hashes
    assert imported.packet_sha256 == study.packet_sha256
    assert imported.export_zip() == packet
    assert imported.cells == study.cells
    assert imported.primary == study.primary


def test_archive_order_and_compression_do_not_change_evidence(study: DissertationResults) -> None:
    files = dict(reversed(list(study.files.items())))
    imported = load_results_zip(_zip(files, compression=zipfile.ZIP_DEFLATED))
    assert imported.packet_sha256 == study.packet_sha256
    assert imported.export_zip() == study.export_zip()


def test_directory_import_is_relocatable(study: DissertationResults, tmp_path: Path) -> None:
    _write_directory(study, tmp_path)
    (tmp_path / "unrelated_historical_notes.txt").write_text(
        "Original package may contain other files"
    )
    imported = load_results_directory(tmp_path)
    assert imported.files == study.files
    assert imported.packet_sha256 == study.packet_sha256


def test_receipt_limits_claims(study: DissertationResults) -> None:
    receipt = study.validation_receipt()
    assert receipt["status"] == "passed"
    assert receipt["cells"] == 32
    assert receipt["paired_blocks"] == 8
    assert receipt["raw_arrays_checked"] is False
    assert receipt["task_level_validation_repeated"] is False
    assert receipt["research_workloads_launched"] == 0
    assert "All offered tasks" in str(receipt["denominator"])
    assert "equal block weighting" in str(receipt["replication_unit"])
    assert "family=3, df=7" in str(receipt["interval"])
    assert "E3" in str(receipt["limitations"])


@pytest.mark.parametrize(
    "name",
    [
        "evidence/CELL_RESULTS.csv",
        "evidence/CELL_RESULTS.json",
        "evidence/PAIRED_EFFECTS.csv",
        "evidence/ANALYSIS.json",
        "evidence/BLOCK_CONTROLS.json",
        "confirmation/SEALED_EXECUTION.json",
        "evidence/cells/block_01_dla/VALIDATED.json",
        "evidence/cells/block_07_per_task_dla/summary.json",
    ],
)
def test_any_changed_original_is_refused(study: DissertationResults, name: str) -> None:
    changed = dict(study.files)
    changed[name] += b" "
    with pytest.raises(ResultsImportError, match="fingerprint mismatch"):
        load_results_zip(_zip(changed))


def test_self_consistent_fabricated_results_cannot_authorize_themselves(
    study: DissertationResults,
) -> None:
    changed = dict(study.files)
    analysis = json.loads(changed["evidence/ANALYSIS.json"])
    analysis["primary"][0]["mean_pp"] = 99.0
    changed["evidence/ANALYSIS.json"] = json.dumps(analysis).encode()
    receipt = json.dumps({"files": {"evidence/ANALYSIS.json": "invented"}}).encode()
    with pytest.raises(ResultsImportError):
        load_results_zip(_zip(changed, extra=("manifest.json", receipt)))
    with pytest.raises(ResultsImportError, match="fingerprint mismatch"):
        load_results_zip(_zip(changed))


@pytest.mark.parametrize("extra", ["payload.py", "../escape", "/absolute", "evidence\\hidden"])
def test_extra_and_unsafe_members_are_refused(study: DissertationResults, extra: str) -> None:
    with pytest.raises(ResultsImportError):
        load_results_zip(_zip(study.files, extra=(extra, b"not evidence")))


def test_duplicate_member_and_missing_member_are_refused(study: DissertationResults) -> None:
    name = "evidence/ANALYSIS.json"
    with pytest.raises(ResultsImportError):
        load_results_zip(_zip(study.files, extra=(name, study.files[name])))
    missing = dict(study.files)
    missing.pop(name)
    with pytest.raises(ResultsImportError):
        load_results_zip(_zip(missing))
    replacement = dict(study.files)
    replacement.pop("evidence/CLEAN_VERIFICATION.json")
    with pytest.raises(ResultsImportError, match="duplicate"):
        load_results_zip(_zip(replacement, extra=(name, study.files[name])))


@pytest.mark.parametrize("mode", [stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o644])
def test_nonregular_archive_members_are_refused(study: DissertationResults, mode: int) -> None:
    with pytest.raises(ResultsImportError, match="unsafe"):
        load_results_zip(
            _zip(study.files, special_name="evidence/ANALYSIS.json", special_mode=mode)
        )


def test_compressed_and_uncompressed_size_limits(study: DissertationResults) -> None:
    with pytest.raises(ResultsImportError, match="compressed size limit"):
        load_results_zip(b"x" * (MAX_PACKET_BYTES + 1))
    changed = dict(study.files)
    changed["evidence/ANALYSIS.json"] = b"x" * MAX_PACKET_BYTES
    bomb = _zip(changed, compression=zipfile.ZIP_DEFLATED)
    assert len(bomb) < MAX_PACKET_BYTES
    with pytest.raises(ResultsImportError, match="uncompressed size limit"):
        load_results_zip(bomb)


@pytest.mark.parametrize("payload", [b"", b"not a ZIP", b"PK\x03\x04"])
def test_malformed_archive_is_typed_refusal(payload: bytes) -> None:
    with pytest.raises(ResultsImportError):
        load_results_zip(payload)


def test_bad_crc_is_typed_refusal(study: DissertationResults) -> None:
    packet = bytearray(study.export_zip())
    name_length, extra_length = struct.unpack_from("<HH", packet, 26)
    packet[30 + name_length + extra_length] ^= 1
    with pytest.raises(ResultsImportError):
        load_results_zip(bytes(packet))


def test_corrupt_deflate_stream_is_typed_refusal(study: DissertationResults) -> None:
    packet = bytearray(_zip(study.files, compression=zipfile.ZIP_DEFLATED))
    name_length, extra_length = struct.unpack_from("<HH", packet, 26)
    # BTYPE=3 is forbidden in DEFLATE and raises zlib.error before the CRC check.
    packet[30 + name_length + extra_length] = 0xFF
    with pytest.raises(ResultsImportError):
        load_results_zip(bytes(packet))


@pytest.mark.parametrize("kind", ["root", "parent", "file"])
def test_directory_symlinks_are_refused(
    study: DissertationResults, tmp_path: Path, kind: str
) -> None:
    original = tmp_path / "original"
    _write_directory(study, original)
    if kind == "root":
        linked = tmp_path / "linked"
        linked.symlink_to(original, target_is_directory=True)
        source = linked
    elif kind == "parent":
        moved = original / "evidence-real"
        (original / "evidence").rename(moved)
        (original / "evidence").symlink_to(moved, target_is_directory=True)
        source = original
    else:
        target = original / "evidence/ANALYSIS.json"
        moved = original / "analysis-real.json"
        target.rename(moved)
        target.symlink_to(moved)
        source = original
    with pytest.raises(ResultsImportError):
        load_results_directory(source)


def test_missing_and_changed_directory_files_are_refused(
    study: DissertationResults, tmp_path: Path
) -> None:
    _write_directory(study, tmp_path)
    name = tmp_path / "evidence/ANALYSIS.json"
    name.write_bytes(b"{}")
    with pytest.raises(ResultsImportError, match="fingerprint mismatch"):
        load_results_directory(tmp_path)
    name.unlink()
    with pytest.raises(ResultsImportError, match="Missing"):
        load_results_directory(tmp_path)


def test_export_and_receipt_recheck_mutated_file_dictionary(study: DissertationResults) -> None:
    imported = load_results_zip(study.export_zip())
    imported.files["evidence/ANALYSIS.json"] = b"{}"
    with pytest.raises(ResultsImportError, match="fingerprint mismatch"):
        imported.export_zip()
    with pytest.raises(ResultsImportError, match="fingerprint mismatch"):
        imported.validation_receipt()


def test_typed_cell_preserves_every_original_field(study: DissertationResults) -> None:
    original = json.loads(study.files["evidence/CELL_RESULTS.json"])
    assert [asdict(cell) for cell in study.cells] == original
