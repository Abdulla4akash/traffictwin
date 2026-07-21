from __future__ import annotations

from pathlib import Path

from traffictwin.storage.registry import Registry
from traffictwin.ui.services import (
    import_bundle_batch_for_ui,
    validate_bundle_batch_for_ui,
)


def test_batch_validation_service_returns_consolidated_outcomes() -> None:
    summary = validate_bundle_batch_for_ui(
        [
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/invalid_manifest",
        ]
    )

    assert summary.overall_status.value == "partial"
    assert summary.accepted_count == 1
    assert summary.rejected_count == 1


def test_batch_import_service_keeps_valid_neighbours(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"

    summary = import_bundle_batch_for_ui(
        [
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/invalid_manifest",
            "tests/fixtures/bundles/variation_valid",
        ],
        registry_path,
    )

    assert summary.created_count == 2
    assert summary.rejected_count == 1
    assert Registry(registry_path).inspect().bundle_import_count == 2
