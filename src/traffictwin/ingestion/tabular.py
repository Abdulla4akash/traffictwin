"""Deterministic readers for declared generic tabular source files."""

from __future__ import annotations

import csv
import gzip
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO, cast

import pyarrow as pa
import pyarrow.parquet as pq

from traffictwin.ingestion.manifest import (
    FileDeclaration,
    SourceCompression,
    SourceFileFormat,
)
from traffictwin.validation.codes import ValidationCode

MAX_TABULAR_UNCOMPRESSED_BYTES = 10_000_000

TabularRow = dict[str, str | None]


@dataclass(frozen=True)
class TabularData:
    """Headers and scalar text rows admitted by the generic adapter."""

    headers: list[str]
    rows: list[TabularRow]


@dataclass(frozen=True)
class TabularChunk:
    """One bounded ordered group of logical tabular records."""

    headers: list[str]
    start_source_row: int
    rows: list[TabularRow]
    estimated_decoded_bytes: int


class TabularReadError(ValueError):
    """Raised with a stable validation code when a declared table cannot be read."""

    def __init__(self, code: ValidationCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def read_declared_table(path: Path, declaration: FileDeclaration) -> TabularData:
    """Read one explicitly declared CSV, gzip-CSV, or Parquet source table."""

    headers: list[str] = []
    rows: list[TabularRow] = []
    for chunk in iter_declared_table_chunks(path, declaration):
        headers = chunk.headers
        rows.extend(chunk.rows)
    return TabularData(headers=headers, rows=rows)


def iter_declared_table_chunks(
    path: Path,
    declaration: FileDeclaration,
    *,
    chunk_rows: int = 10_000,
    max_uncompressed_bytes: int | None = None,
    max_chunk_bytes: int | None = None,
) -> Iterator[TabularChunk]:
    """Yield bounded logical row chunks for one explicitly declared table."""

    if chunk_rows < 1:
        raise ValueError("chunk_rows must be at least 1")
    table_limit = (
        MAX_TABULAR_UNCOMPRESSED_BYTES if max_uncompressed_bytes is None else max_uncompressed_bytes
    )
    chunk_limit = table_limit if max_chunk_bytes is None else max_chunk_bytes
    if table_limit < 1 or chunk_limit < 1:
        raise ValueError("tabular byte limits must be positive")

    try:
        if declaration.format is SourceFileFormat.CSV:
            if declaration.compression is SourceCompression.GZIP:
                yield from _iter_gzip_csv_chunks(
                    path,
                    chunk_rows=chunk_rows,
                    max_uncompressed_bytes=table_limit,
                    max_chunk_bytes=chunk_limit,
                )
                return
            yield from _iter_csv_chunks(
                path,
                chunk_rows=chunk_rows,
                max_uncompressed_bytes=table_limit,
                max_chunk_bytes=chunk_limit,
            )
            return
        if declaration.format is SourceFileFormat.PARQUET:
            yield from _iter_parquet_chunks(
                path,
                chunk_rows=chunk_rows,
                max_uncompressed_bytes=table_limit,
                max_chunk_bytes=chunk_limit,
            )
            return
    except TabularReadError:
        raise
    except (csv.Error, EOFError, OSError, UnicodeError, pa.ArrowException) as exc:
        raise TabularReadError(
            ValidationCode.TABULAR_FILE_INVALID,
            f"declared {declaration.format.value} file could not be decoded: {exc}",
        ) from exc
    raise TabularReadError(
        ValidationCode.TABULAR_FILE_INVALID,
        f"unsupported declared tabular format: {declaration.format}",
    )


def _iter_csv_chunks(
    path: Path,
    *,
    chunk_rows: int,
    max_uncompressed_bytes: int,
    max_chunk_bytes: int,
) -> Iterator[TabularChunk]:
    if path.stat().st_size > max_uncompressed_bytes:
        raise _size_limit_error(max_uncompressed_bytes)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        yield from _parse_csv_chunks(
            handle,
            chunk_rows=chunk_rows,
            max_chunk_bytes=max_chunk_bytes,
        )


def _iter_gzip_csv_chunks(
    path: Path,
    *,
    chunk_rows: int,
    max_uncompressed_bytes: int,
    max_chunk_bytes: int,
) -> Iterator[TabularChunk]:
    with gzip.open(path, mode="rt", newline="", encoding="utf-8-sig") as handle:
        yield from _parse_csv_chunks(
            _bounded_lines(handle, max_uncompressed_bytes),
            chunk_rows=chunk_rows,
            max_chunk_bytes=max_chunk_bytes,
        )


def _bounded_lines(handle: TextIO, max_uncompressed_bytes: int) -> Iterable[str]:
    decoded_bytes = 0
    for line in handle:
        decoded_bytes += len(line.encode("utf-8"))
        if decoded_bytes > max_uncompressed_bytes:
            raise _size_limit_error(max_uncompressed_bytes)
        yield line


def _parse_csv_chunks(
    lines: Iterable[str],
    *,
    chunk_rows: int,
    max_chunk_bytes: int,
) -> Iterator[TabularChunk]:
    reader = csv.DictReader(lines)
    headers = list(reader.fieldnames or [])
    _validate_unique_headers(headers)
    rows: list[TabularRow] = []
    chunk_bytes = 0
    chunk_start = 2
    saw_row = False
    for source_row, row in enumerate(reader, start=2):
        saw_row = True
        if None in row:
            raise TabularReadError(
                ValidationCode.TABULAR_FILE_INVALID,
                "CSV row has more values than declared headers",
            )
        decoded = {header: row.get(header) for header in headers}
        row_bytes = _estimated_row_bytes(decoded)
        if row_bytes > max_chunk_bytes:
            raise _chunk_limit_error(max_chunk_bytes)
        if rows and (len(rows) >= chunk_rows or chunk_bytes + row_bytes > max_chunk_bytes):
            yield TabularChunk(headers, chunk_start, rows, chunk_bytes)
            rows = []
            chunk_bytes = 0
            chunk_start = source_row
        rows.append(decoded)
        chunk_bytes += row_bytes
    if rows:
        yield TabularChunk(headers, chunk_start, rows, chunk_bytes)
    elif not saw_row:
        yield TabularChunk(headers, 2, [], 0)


def _iter_parquet_chunks(
    path: Path,
    *,
    chunk_rows: int,
    max_uncompressed_bytes: int,
    max_chunk_bytes: int,
) -> Iterator[TabularChunk]:
    parquet = pq.ParquetFile(path)
    headers = list(parquet.schema_arrow.names)
    _validate_unique_headers(headers)
    _validate_parquet_schema(parquet.schema_arrow)
    uncompressed_bytes = sum(
        parquet.metadata.row_group(index).total_byte_size
        for index in range(parquet.metadata.num_row_groups)
    )
    if uncompressed_bytes > max_uncompressed_bytes:
        raise _size_limit_error(max_uncompressed_bytes)
    source_row = 2
    saw_batch = False
    for batch in parquet.iter_batches(batch_size=chunk_rows):
        saw_batch = True
        for bounded in _bounded_record_batches(batch, max_chunk_bytes):
            raw_rows = cast(list[dict[str, Any]], bounded.to_pylist())
            rows = [
                {header: _parquet_scalar_to_text(row.get(header)) for header in headers}
                for row in raw_rows
            ]
            yield TabularChunk(headers, source_row, rows, bounded.nbytes)
            source_row += len(rows)
    if not saw_batch:
        yield TabularChunk(headers, 2, [], 0)


def _bounded_record_batches(
    batch: pa.RecordBatch,
    max_chunk_bytes: int,
) -> Iterator[pa.RecordBatch]:
    if batch.nbytes <= max_chunk_bytes:
        yield batch
        return
    if batch.num_rows <= 1:
        raise _chunk_limit_error(max_chunk_bytes)
    midpoint = batch.num_rows // 2
    yield from _bounded_record_batches(batch.slice(0, midpoint), max_chunk_bytes)
    yield from _bounded_record_batches(
        batch.slice(midpoint, batch.num_rows - midpoint),
        max_chunk_bytes,
    )


def _estimated_row_bytes(row: TabularRow) -> int:
    return sum(
        len(key.encode("utf-8")) + (0 if value is None else len(value.encode("utf-8")))
        for key, value in row.items()
    )


def _validate_unique_headers(headers: list[str]) -> None:
    if len(headers) != len(set(headers)):
        raise TabularReadError(
            ValidationCode.TABULAR_COLUMNS_DUPLICATE,
            "tabular source column names must be unique",
        )


def _validate_parquet_schema(schema: pa.Schema) -> None:
    unsupported = [
        f"{field.name}:{field.type}"
        for field in schema
        if not _is_supported_parquet_type(field.type)
    ]
    if unsupported:
        raise TabularReadError(
            ValidationCode.PARQUET_SCHEMA_UNSUPPORTED,
            "Parquet columns must use scalar string, boolean, integer, floating-point, "
            f"or decimal values; unsupported columns: {', '.join(unsupported)}",
        )


def _is_supported_parquet_type(data_type: pa.DataType) -> bool:
    if pa.types.is_dictionary(data_type):
        return _is_supported_parquet_type(data_type.value_type)
    return bool(
        pa.types.is_null(data_type)
        or pa.types.is_string(data_type)
        or pa.types.is_large_string(data_type)
        or pa.types.is_boolean(data_type)
        or pa.types.is_integer(data_type)
        or pa.types.is_floating(data_type)
        or pa.types.is_decimal(data_type)
    )


def _parquet_scalar_to_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float, Decimal)):
        return str(value)
    raise TabularReadError(
        ValidationCode.PARQUET_SCHEMA_UNSUPPORTED,
        f"Parquet value type is unsupported: {type(value).__name__}",
    )


def _size_limit_error(limit: int) -> TabularReadError:
    return TabularReadError(
        ValidationCode.TABULAR_SIZE_LIMIT_EXCEEDED,
        f"tabular source exceeds the {limit}-byte uncompressed ingestion limit",
    )


def _chunk_limit_error(limit: int) -> TabularReadError:
    return TabularReadError(
        ValidationCode.TABULAR_CHUNK_SIZE_EXCEEDED,
        f"one decoded tabular chunk or row exceeds the {limit}-byte streaming chunk limit",
    )
