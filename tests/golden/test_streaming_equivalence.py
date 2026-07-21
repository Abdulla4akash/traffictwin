from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.format_helpers import write_equivalent_bundle
from tests.helpers import FIXTURES

from traffictwin.ingestion.bundle import (
    collect_bundle_streaming,
    validate_bundle,
    validate_bundle_streaming,
)
from traffictwin.ingestion.streaming import StreamingCanonicalisationConfig
from traffictwin.metrics.engine import compute_metrics_for_bundle

EXPECTED = Path("tests/golden/expected/streaming_baseline_summary.json")


def test_streaming_baseline_summary_matches_golden() -> None:
    result = validate_bundle_streaming(
        FIXTURES / "baseline_valid",
        config=StreamingCanonicalisationConfig(chunk_rows=2, max_chunk_bytes=1_024),
    )

    assert result.streaming.model_dump(mode="json") == json.loads(
        EXPECTED.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("representation", ["gzip", "parquet"])
@pytest.mark.parametrize("chunk_rows", [1, 2, 7])
def test_streaming_matches_ordinary_for_declared_formats_and_boundaries(
    tmp_path: Path,
    representation: str,
    chunk_rows: int,
) -> None:
    bundle = write_equivalent_bundle(
        FIXTURES / "baseline_valid",
        tmp_path / f"{representation}-{chunk_rows}",
        representation,
    )
    ordinary = validate_bundle(bundle)
    streamed = collect_bundle_streaming(
        bundle,
        config=StreamingCanonicalisationConfig(
            chunk_rows=chunk_rows,
            max_chunk_bytes=1_024,
        ),
    )

    def clock() -> datetime:
        return datetime(2026, 7, 20, tzinfo=UTC)

    assert streamed.validation.canonical == ordinary.canonical
    assert streamed.validation.report.model_dump(
        mode="json", exclude={"import_timestamp"}
    ) == ordinary.report.model_dump(mode="json", exclude={"import_timestamp"})
    assert compute_metrics_for_bundle(
        streamed.validation,
        clock=clock,
    ) == compute_metrics_for_bundle(ordinary, clock=clock)
