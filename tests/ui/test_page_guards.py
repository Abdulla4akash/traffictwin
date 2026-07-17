from __future__ import annotations

from pathlib import Path

from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.ui.services import validate_bundle_for_ui


def test_rejected_bundle_cannot_enter_analysis_pages() -> None:
    analysis = validate_bundle_for_ui(Path("tests/fixtures/bundles/invalid_rows"))

    assert not analysis.analysis_ready
    assert analysis.metrics is None


def test_direct_launch_is_not_enabled_in_default_ui_capabilities() -> None:
    manifest = default_export_import_manifest()

    assert manifest.supports.direct_launch is CapabilitySupport.FALSE
    assert manifest.supports.asynchronous_launch is CapabilitySupport.FALSE
