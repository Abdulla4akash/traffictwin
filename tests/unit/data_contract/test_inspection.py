"""Tests for bounded deterministic inspection."""

from __future__ import annotations

import csv
import gzip
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.models import LogicalType


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_gzip_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _write_parquet(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    # All string columns for scalar parquet
    table = pa.table({h: [r[i] for r in rows] for i, h in enumerate(headers)})
    pq.write_table(table, path)


def test_deterministic_inspection_across_row_order(tmp_path: Path) -> None:
    # Two CSVs with same rows in different order should produce same fingerprint
    # Fingerprint is deterministic because field_observations are canonically sorted
    # for hashing, even though original header order is preserved for drift detection.
    headers = ["timestamp", "vehicle_id", "speed"]
    rows_a = [["2024-01-01T00:00:00Z", "veh1", "10.5"], ["2024-01-01T00:01:00Z", "veh2", "20.1"]]
    rows_b = [["2024-01-01T00:01:00Z", "veh2", "20.1"], ["2024-01-01T00:00:00Z", "veh1", "10.5"]]
    p_a = tmp_path / "a.csv"
    p_b = tmp_path / "b.csv"
    _write_csv(p_a, headers, rows_a)
    _write_csv(p_b, headers, rows_b)
    obs_a = inspect_tabular_sample(
        p_a, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    obs_b = inspect_tabular_sample(
        p_b, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    # Fingerprints should match because categorical digest and counts are order-independent
    assert obs_a.fingerprint == obs_b.fingerprint
    # Header order is preserved in field_observations (for drift column-reorder detection)
    assert [f.field_name for f in obs_a.field_observations] == headers
    assert [f.field_name for f in obs_b.field_observations] == headers


def test_csv_gzip_parquet_equivalence_where_schemas_match(tmp_path: Path) -> None:
    headers = ["id", "value", "flag"]
    rows = [["1", "hello", "true"], ["2", "world", "false"]]
    csv_p = tmp_path / "sample.csv"
    gz_p = tmp_path / "sample.csv.gz"
    pq_p = tmp_path / "sample.parquet"
    _write_csv(csv_p, headers, rows)
    _write_gzip_csv(gz_p, headers, rows)
    _write_parquet(pq_p, headers, rows)
    obs_csv = inspect_tabular_sample(
        csv_p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    obs_gz = inspect_tabular_sample(
        gz_p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    obs_pq = inspect_tabular_sample(
        pq_p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    # All should have same logical types and field names
    for obs in (obs_csv, obs_gz, obs_pq):
        assert {fo.field_name for fo in obs.field_observations} == set(headers)
    # Fingerprints should match across formats when content same (since we normalize)
    assert obs_csv.fingerprint == obs_gz.fingerprint == obs_pq.fingerprint


def test_bounded_reads_truncate_and_respect_limits(tmp_path: Path) -> None:
    headers = ["a", "b"]
    rows = [[str(i), str(i * 2)] for i in range(100)]
    p = tmp_path / "big.csv"
    _write_csv(p, headers, rows)
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    assert obs.total_observed_rows == 10
    assert obs.truncated is True
    assert all(fo.observed_count == 10 for fo in obs.field_observations)


def test_bounded_bytes_limit_raises(tmp_path: Path) -> None:
    headers = ["a"]
    rows = [["x" * 1000] for _ in range(10)]
    p = tmp_path / "big2.csv"
    _write_csv(p, headers, rows)
    # Very small byte limit should trigger size error via tabular reader
    with pytest.raises(Exception, match="exceeds"):
        inspect_tabular_sample(
            p, max_rows=100, max_bytes=100, observation_id="obs_001", source_label="local"
        )


def test_nullable_detection(tmp_path: Path) -> None:
    headers = ["id", "optional"]
    rows = [["1", "a"], ["2", ""], ["3", "c"]]
    p = tmp_path / "null.csv"
    _write_csv(p, headers, rows)
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    opt = next(fo for fo in obs.field_observations if fo.field_name == "optional")
    assert opt.nullable is True
    assert opt.null_count == 1
    assert opt.observed_count == 3


def test_secret_and_path_redaction_in_observation(tmp_path: Path) -> None:
    headers = ["api_key", "value"]
    rows = [["sk-123", "hello"]]
    p = tmp_path / "secret.csv"
    _write_csv(p, headers, rows)
    obs = inspect_tabular_sample(
        p,
        max_rows=10,
        max_bytes=1_000_000,
        observation_id="obs_001",
        source_label="/absolute/path/to/secret/api_key_file.csv",
    )
    # Portable fingerprint must not contain absolute path
    assert "/absolute" not in obs.fingerprint
    # Source label is redacted (path-independent, secret-aware)
    assert obs.source_label_redacted in ("local_sample", "[REDACTED_SOURCE_LABEL]")
    # No raw values in observation fingerprint payload (hash-based, not raw)
    assert "sk-123" not in obs.fingerprint
    assert "sk-123" not in obs.model_dump_json()
    # Categorical evidence is aggregate hash + count, never raw members
    api_key_obs = next(fo for fo in obs.field_observations if fo.field_name == "api_key")
    assert api_key_obs.categorical_distinct_count == 1
    assert api_key_obs.categorical_aggregate_hash is not None
    assert "sk-123" not in (api_key_obs.categorical_aggregate_hash or "")
    value_obs = next(fo for fo in obs.field_observations if fo.field_name == "value")
    assert value_obs.categorical_distinct_count == 1
    assert value_obs.categorical_aggregate_hash is not None
    assert "hello" not in (value_obs.categorical_aggregate_hash or "")


def test_precision_and_categorical_digest(tmp_path: Path) -> None:
    headers = ["price", "category"]
    rows = [["10.123456", "A"], ["20.123", "B"], ["30.1", "A"]]
    p = tmp_path / "prec.csv"
    _write_csv(p, headers, rows)
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    price = next(fo for fo in obs.field_observations if fo.field_name == "price")
    assert price.precision is not None
    assert price.scale is not None
    cat = next(fo for fo in obs.field_observations if fo.field_name == "category")
    assert cat.categorical_distinct_count == 2
    assert cat.categorical_aggregate_hash is not None
    # Raw values never appear in hash
    assert (
        "A" not in (cat.categorical_aggregate_hash or "")
        or len(cat.categorical_aggregate_hash or "") == 64
    )
    # Distinct count reflects bounded domain
    assert cat.categorical_distinct_count == 2


def test_timestamp_parse_state(tmp_path: Path) -> None:
    headers = ["ts"]
    rows = [["2024-01-01T00:00:00Z"], ["2024-01-02T00:00:00Z"]]
    p = tmp_path / "ts.csv"
    _write_csv(p, headers, rows)
    obs = inspect_tabular_sample(
        p, max_rows=10, max_bytes=1_000_000, observation_id="obs_001", source_label="local"
    )
    ts = next(fo for fo in obs.field_observations if fo.field_name == "ts")
    assert ts.observed_logical_type == LogicalType.TIMESTAMP
    assert ts.timestamp_parse_state == "parsed_with_tz"
