from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

import traffictwin.ingestion.tabular as tabular
from tests.format_helpers import write_equivalent_bundle
from tests.helpers import FIXTURES
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.ingestion.manifest import (
    FileDeclaration,
    SourceCompression,
    SourceFileFormat,
)
from traffictwin.ingestion.tabular import TabularReadError, read_declared_table
from traffictwin.validation.codes import ValidationCode


def test_file_declaration_defaults_to_plain_csv_and_admits_declared_formats() -> None:
    legacy = FileDeclaration(path="tasks.csv")
    compressed = FileDeclaration(path="tasks.csv.gz", compression="gzip")
    parquet = FileDeclaration(path="tasks.parquet", format="parquet")

    assert legacy.format is SourceFileFormat.CSV
    assert legacy.compression is None
    assert compressed.compression is SourceCompression.GZIP
    assert parquet.format is SourceFileFormat.PARQUET
    with pytest.raises(ValidationError, match="outer compression"):
        FileDeclaration(path="tasks.parquet.gz", format="parquet", compression="gzip")


def test_malformed_gzip_has_stable_validation_code(tmp_path: Path) -> None:
    path = tmp_path / "tasks.csv.gz"
    path.write_bytes(b"not-a-gzip-stream")

    with pytest.raises(TabularReadError) as raised:
        read_declared_table(path, FileDeclaration(path=path.name, compression="gzip"))

    assert raised.value.code is ValidationCode.TABULAR_FILE_INVALID


def test_nested_parquet_schema_is_rejected_and_marks_evidence_invalid(tmp_path: Path) -> None:
    bundle = write_equivalent_bundle(
        FIXTURES / "baseline_valid",
        tmp_path / "parquet",
        "parquet",
    )
    pq.write_table(pa.table({"nested": [[1, 2]]}), bundle / "tasks.parquet")

    result = validate_bundle(bundle)

    assert not result.report.may_import
    assert result.evidence.tasks.value == "invalid"
    assert ValidationCode.FILE_CHECKSUM_MISMATCH in {
        finding.code for finding in result.report.findings
    }
    assert ValidationCode.PARQUET_SCHEMA_UNSUPPORTED in {
        finding.code for finding in result.report.findings
    }


def test_duplicate_csv_columns_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.csv"
    path.write_text("task_id,task_id\nt1,t2\n", encoding="utf-8")

    with pytest.raises(TabularReadError) as raised:
        read_declared_table(path, FileDeclaration(path=path.name))

    assert raised.value.code is ValidationCode.TABULAR_COLUMNS_DUPLICATE


def test_gzip_decoded_size_limit_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "small.csv.gz"
    import gzip

    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("value\n123456789\n")
    monkeypatch.setattr(tabular, "MAX_TABULAR_UNCOMPRESSED_BYTES", 8)

    with pytest.raises(TabularReadError) as raised:
        read_declared_table(path, FileDeclaration(path=path.name, compression="gzip"))

    assert raised.value.code is ValidationCode.TABULAR_SIZE_LIMIT_EXCEEDED
