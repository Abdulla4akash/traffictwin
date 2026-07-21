from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

import traffictwin.ingestion.tabular as tabular
from tests.helpers import FIXTURES
from traffictwin.ingestion.bundle import (
    collect_bundle_streaming,
    validate_bundle,
    validate_bundle_streaming,
)
from traffictwin.ingestion.streaming import (
    CanonicalChunk,
    StreamingCanonicalisationConfig,
    StreamingConsumerError,
)
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.windowed import (
    WindowedMetricConfig,
    compute_windowed_metrics_for_bundle,
)
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.report import ValidationReport


def test_streaming_config_rejects_inconsistent_bounds() -> None:
    with pytest.raises(ValidationError, match="max_chunk_bytes"):
        StreamingCanonicalisationConfig(
            max_chunk_bytes=2_048,
            max_table_uncompressed_bytes=1_024,
        )
    with pytest.raises(ValidationError, match="max_table_uncompressed_bytes"):
        StreamingCanonicalisationConfig(
            max_table_uncompressed_bytes=4_096,
            max_bundle_uncompressed_bytes=2_048,
        )


@pytest.mark.parametrize("chunk_rows", [1, 2, 3, 50])
def test_chunk_boundaries_do_not_change_canonical_metrics_or_reports(chunk_rows: int) -> None:
    path = FIXTURES / "baseline_valid"
    ordinary = validate_bundle(path)
    collected = collect_bundle_streaming(
        path,
        config=StreamingCanonicalisationConfig(
            chunk_rows=chunk_rows,
            max_chunk_bytes=1_024,
        ),
    )

    assert collected.validation.canonical == ordinary.canonical
    assert collected.validation.evidence == ordinary.evidence
    assert _stable_report(collected.validation.report) == _stable_report(ordinary.report)

    def clock() -> datetime:
        return datetime(2026, 7, 20, tzinfo=UTC)

    assert compute_metrics_for_bundle(
        collected.validation,
        clock=clock,
    ) == compute_metrics_for_bundle(ordinary, clock=clock)
    assert compute_windowed_metrics_for_bundle(
        collected.validation,
        WindowedMetricConfig(width_s=60),
        clock=clock,
    ) == compute_windowed_metrics_for_bundle(
        ordinary,
        WindowedMetricConfig(width_s=60),
        clock=clock,
    )


def test_streaming_consumer_receives_bounded_ordered_chunks() -> None:
    chunks: list[CanonicalChunk] = []
    config = StreamingCanonicalisationConfig(chunk_rows=1, max_chunk_bytes=1_024)

    result = validate_bundle_streaming(
        FIXTURES / "baseline_valid", config=config, consumer=chunks.append
    )

    assert result.report.may_import
    assert result.streaming.chunk_count == 11
    assert result.streaming.max_observed_chunk_source_rows == 1
    assert result.streaming.max_observed_chunk_decoded_bytes <= config.max_chunk_bytes
    assert [chunk.start_source_row for chunk in chunks if chunk.source_kind == "tasks"] == [2, 3, 4]
    assert sum(chunk.canonical_record_count for chunk in chunks) == 11


def test_consumer_failure_propagates_without_becoming_a_source_finding() -> None:
    def fail_consumer(chunk: CanonicalChunk) -> None:
        del chunk
        raise OSError("downstream staging failed")

    with pytest.raises(StreamingConsumerError, match="tasks.csv chunk 1") as exc_info:
        validate_bundle_streaming(
            FIXTURES / "baseline_valid",
            config=StreamingCanonicalisationConfig(chunk_rows=1, max_chunk_bytes=1_024),
            consumer=fail_consumer,
        )

    assert isinstance(exc_info.value.__cause__, OSError)


def test_global_duplicate_check_is_equivalent_across_chunks(tmp_path: Path) -> None:
    bundle = tmp_path / "duplicate"
    shutil.copytree(FIXTURES / "baseline_valid", bundle)
    tasks = bundle / "tasks.csv"
    with tasks.open("a", encoding="utf-8") as handle:
        handle.write("t1,veh-4,T1,9,100,local,true,9.050,50,\n")

    ordinary = validate_bundle(bundle)
    streamed = collect_bundle_streaming(
        bundle,
        config=StreamingCanonicalisationConfig(chunk_rows=1, max_chunk_bytes=1_024),
    )

    assert streamed.validation.canonical == ordinary.canonical
    assert _stable_report(streamed.validation.report) == _stable_report(ordinary.report)
    assert ValidationCode.TASK_ID_DUPLICATE in {
        finding.code for finding in streamed.validation.report.findings
    }


def test_global_rsu_reference_check_is_equivalent_across_chunks(tmp_path: Path) -> None:
    bundle = tmp_path / "unknown-rsu"
    shutil.copytree(FIXTURES / "baseline_valid", bundle)
    tasks = bundle / "tasks.csv"
    tasks.write_text(
        tasks.read_text(encoding="utf-8").replace("rsu-1\n", "rsu-missing\n"),
        encoding="utf-8",
    )

    ordinary = validate_bundle(bundle)
    streamed = collect_bundle_streaming(
        bundle,
        config=StreamingCanonicalisationConfig(chunk_rows=1, max_chunk_bytes=1_024),
    )

    assert _stable_report(streamed.validation.report) == _stable_report(ordinary.report)
    assert ValidationCode.UNKNOWN_RSU_REFERENCE in {
        finding.code for finding in streamed.validation.report.findings
    }


def test_streaming_path_can_admit_table_above_ordinary_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "larger"
    shutil.copytree(FIXTURES / "baseline_valid", bundle)
    tasks = bundle / "tasks.csv"
    header = tasks.read_text(encoding="utf-8").splitlines()[0]
    rows = [
        f"large-{index},veh-{index},T1,{index},100,local,true,{index + 0.05},50,"
        for index in range(40)
    ]
    tasks.write_text("\n".join([header, *rows, ""]), encoding="utf-8")
    monkeypatch.setattr(tabular, "MAX_TABULAR_UNCOMPRESSED_BYTES", 512)

    ordinary = validate_bundle(bundle)
    streamed = validate_bundle_streaming(
        bundle,
        config=StreamingCanonicalisationConfig(
            chunk_rows=4,
            max_chunk_bytes=1_024,
            max_table_uncompressed_bytes=100_000,
            max_bundle_uncompressed_bytes=200_000,
        ),
    )

    assert not ordinary.report.may_import
    assert ValidationCode.TABULAR_SIZE_LIMIT_EXCEEDED in {
        finding.code for finding in ordinary.report.findings
    }
    assert streamed.report.may_import
    assert streamed.streaming.canonical_record_counts["tasks"] == 40


def test_one_row_above_chunk_byte_limit_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "oversized-row"
    shutil.copytree(FIXTURES / "baseline_valid", bundle)
    tasks = bundle / "tasks.csv"
    header = tasks.read_text(encoding="utf-8").splitlines()[0]
    tasks.write_text(
        f"{header}\nrow-1,{'v' * 2_000},T1,0,100,local,true,0.05,50,\n",
        encoding="utf-8",
    )

    result = validate_bundle_streaming(
        bundle,
        config=StreamingCanonicalisationConfig(
            chunk_rows=10,
            max_chunk_bytes=1_024,
            max_table_uncompressed_bytes=100_000,
            max_bundle_uncompressed_bytes=200_000,
        ),
    )

    assert not result.report.may_import
    assert ValidationCode.TABULAR_CHUNK_SIZE_EXCEEDED in {
        finding.code for finding in result.report.findings
    }
    assert "tasks.csv" in result.streaming.files_processed
    assert result.streaming.canonical_record_counts["tasks"] == 0


def _stable_report(report: ValidationReport) -> dict[str, object]:
    return report.model_dump(mode="json", exclude={"import_timestamp"})
