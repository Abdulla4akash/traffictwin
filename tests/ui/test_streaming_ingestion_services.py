from __future__ import annotations

from pathlib import Path

from traffictwin.ingestion.bundle import StreamingBundleImportResult
from traffictwin.ingestion.streaming import StreamingBundleValidationResult
from traffictwin.storage.registry import Registry
from traffictwin.ui.services import (
    ServiceError,
    import_bundle_streaming_for_ui,
    validate_bundle_streaming_for_ui,
)


def test_streaming_validation_service_returns_typed_summary() -> None:
    result = validate_bundle_streaming_for_ui(
        "tests/fixtures/bundles/baseline_valid",
        chunk_rows=1,
    )

    assert isinstance(result, StreamingBundleValidationResult)
    assert result.report.may_import
    assert result.streaming.chunk_count == 11


def test_streaming_import_service_registers_metadata(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    result = import_bundle_streaming_for_ui(
        "tests/fixtures/bundles/baseline_valid",
        registry_path,
        chunk_rows=2,
    )

    assert not isinstance(result, ServiceError)
    assert isinstance(result, StreamingBundleImportResult)
    assert result.registry.created
    assert Registry(registry_path).inspect().bundle_import_count == 1
