from __future__ import annotations

import zipfile
from pathlib import Path

from traffictwin.ingestion.bundle import collect_bundle_streaming, import_bundle, validate_bundle
from traffictwin.ingestion.streaming import StreamingCanonicalisationConfig
from traffictwin.storage.registry import Registry


def write_zip_from_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def test_zip_bundle_validate_and_import(tmp_path: Path) -> None:
    source = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "baseline.zip"
    registry_path = tmp_path / "registry.sqlite"
    write_zip_from_directory(source, zip_path)

    validation = validate_bundle(zip_path)
    imported = import_bundle(zip_path, registry_path)

    assert validation.report.may_import
    assert imported.created
    assert Registry(registry_path).inspect().bundle_import_count == 1


def test_zip_streaming_matches_ordinary_bundle_validation(tmp_path: Path) -> None:
    source = Path("tests/fixtures/bundles/baseline_valid")
    zip_path = tmp_path / "baseline.zip"
    write_zip_from_directory(source, zip_path)

    ordinary = validate_bundle(zip_path)
    streamed = collect_bundle_streaming(
        zip_path,
        config=StreamingCanonicalisationConfig(
            chunk_rows=1,
            max_chunk_bytes=1_024,
        ),
    )

    assert streamed.validation.canonical == ordinary.canonical
    assert streamed.validation.evidence == ordinary.evidence
    volatile_fields = {"validated_at", "import_timestamp"}
    assert streamed.validation.report.model_dump(exclude=volatile_fields) == (
        ordinary.report.model_dump(exclude=volatile_fields)
    )
