from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.ingestion.loader import BundleLoadError, open_bundle


def write_zip_from_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def test_zip_bundle_matches_directory_bundle(tmp_path: Path) -> None:
    source = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "baseline.zip"
    write_zip_from_directory(source, zip_path)

    directory_result = validate_bundle(source)
    zip_result = validate_bundle(zip_path)

    assert zip_result.report.status == directory_result.report.status
    assert zip_result.canonical.record_counts() == directory_result.canonical.record_counts()
    assert zip_result.report.findings == directory_result.report.findings


def test_zip_path_traversal_rejected(tmp_path: Path) -> None:
    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../escape.txt", "bad")

    with pytest.raises(BundleLoadError, match="unsafe zip path"), open_bundle(zip_path):
        pass
