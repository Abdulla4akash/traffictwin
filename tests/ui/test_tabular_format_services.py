from __future__ import annotations

from pathlib import Path

import pytest
from tests.format_helpers import write_equivalent_bundle
from tests.helpers import FIXTURES

from traffictwin.ui.services import validate_bundle_for_ui


@pytest.mark.parametrize("representation", ["gzip", "parquet"])
def test_ui_service_builds_analysis_for_declared_tabular_format(
    tmp_path: Path,
    representation: str,
) -> None:
    bundle = write_equivalent_bundle(
        FIXTURES / "baseline_valid",
        tmp_path / representation,
        representation,
    )

    analysis = validate_bundle_for_ui(bundle)

    assert analysis.analysis_ready
    assert analysis.metrics is not None
    assert analysis.metrics.by_key()["task.completion.rate"].value == 1.0
