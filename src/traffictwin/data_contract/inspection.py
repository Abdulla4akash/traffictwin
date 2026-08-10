"""Bounded deterministic schema inspection for tabular samples.

Reuses existing safe readers (CSV, gzip-CSV, Parquet) with explicit row and
byte limits. Never loads an unbounded file to infer a schema.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from traffictwin.data_contract.fingerprint import (
    fingerprint_canonical,
)
from traffictwin.data_contract.models import (
    FieldObservation,
    LogicalType,
    SchemaObservation,
)
from traffictwin.ingestion.manifest import FileDeclaration, SourceCompression, SourceFileFormat
from traffictwin.ingestion.tabular import (
    TabularReadError,
    iter_declared_table_chunks,
)

# Default inspection limits – conservative for UI use.
DEFAULT_MAX_ROWS = 5000
DEFAULT_MAX_BYTES = 5_000_000  # 5 MB uncompressed
MAX_CATEGORICAL_VALUES = 20
MAX_CATEGORICAL_VALUE_LENGTH = 64

_TIMESTAMP_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"),
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
]

# Simple logical-type inference heuristics for observed values
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d*\.\d+$")
_BOOL_VALUES = {"true", "false", "1", "0", "yes", "no", "t", "f", "y", "n"}


def _infer_logical_type(values: list[str]) -> LogicalType:
    """Infer logical type from bounded sample values (None already filtered)."""
    if not values:
        return LogicalType.STRING
    # Check boolean
    lower = [v.strip().lower() for v in values if v.strip() != ""]
    if lower and all(v in _BOOL_VALUES for v in lower):
        return LogicalType.BOOLEAN
    # Check integer
    stripped = [v.strip() for v in values if v.strip() != ""]
    if stripped and all(_INT_RE.fullmatch(v) for v in stripped):
        # If any value too large for 64-bit, treat as decimal
        try:
            for v in stripped:
                iv = int(v)
                if abs(iv) > 2**63 - 1:
                    return LogicalType.DECIMAL
            return LogicalType.INTEGER
        except ValueError:
            return LogicalType.STRING
    if stripped and all(_INT_RE.fullmatch(v) or _FLOAT_RE.fullmatch(v) for v in stripped):
        # Mixed int/float -> float; check decimal precision
        has_float = any(_FLOAT_RE.fullmatch(v) for v in stripped)
        if has_float:
            # Check if decimal with high precision
            for v in stripped:
                if "." in v:
                    try:
                        d = Decimal(v)
                        exp = d.as_tuple().exponent  # type: ignore[assignment]
                        if isinstance(exp, int) and exp < -6:  # type: ignore[operator]
                            return LogicalType.DECIMAL
                    except InvalidOperation:
                        pass
            return LogicalType.FLOAT
    # Check timestamp
    if stripped and all(any(p.match(v) for p in _TIMESTAMP_PATTERNS) for v in stripped):
        return LogicalType.TIMESTAMP
    return LogicalType.STRING


def _timestamp_parse_state(values: list[str | None], logical_type: LogicalType) -> str:
    if logical_type is not LogicalType.TIMESTAMP:
        return "not_timestamp"
    # Try to distinguish UTC vs naive vs failed
    non_null = [v for v in values if v is not None and v.strip() != ""]
    if not non_null:
        return "not_timestamp"
    has_tz = any(
        v.strip().endswith("Z") or "+" in v.strip() or v.strip().count(":") >= 3 for v in non_null
    )
    # Check parse: if all match timestamp pattern
    all_match = all(any(p.match(v.strip()) for p in _TIMESTAMP_PATTERNS) for v in non_null)
    if not all_match:
        return "parse_failed"
    if has_tz:
        return "parsed_with_tz"
    # Heuristic: if contains T and Z or offset -> with_tz, else naive
    if any("T" in v for v in non_null):
        return "parsed_naive"
    return "parsed_naive"


def _precision_scale(values: list[str], logical_type: LogicalType) -> tuple[int | None, int | None]:
    if logical_type not in {LogicalType.FLOAT, LogicalType.DECIMAL, LogicalType.INTEGER}:
        return None, None
    # Compute max precision/scale among decimal-like values
    max_prec: int | None = None
    max_scale: int | None = None
    for v in values:
        vv = v.strip()
        if vv == "" or vv is None:
            continue
        try:
            d = Decimal(vv)
            _sign, _digits, _exp = d.as_tuple()
            # Mypy: exponent can be int or str for special values; guard
            if not isinstance(_exp, int):
                continue
            prec = len(_digits)
            scale = -_exp if _exp < 0 else 0
            if max_prec is None or prec > max_prec:
                max_prec = prec
            if max_scale is None or scale > max_scale:
                max_scale = scale
        except InvalidOperation:
            continue
    return max_prec, max_scale


def _categorical_digest(
    values: list[str | None], field_name: str | None = None
) -> list[str] | None:
    # Secret-bearing fields must not leak raw values via digest
    if field_name is not None and is_secret_like(field_name):
        return None
    non_null = [v for v in values if v is not None and v.strip() != ""]
    if not non_null:
        return None
    # Also redact if any value looks secret-like
    if any(is_secret_like(v) for v in non_null):
        return None
    distinct = sorted(set(non_null))
    # Only emit digest for plausible categoricals (bounded distinct count and length)
    if len(distinct) > MAX_CATEGORICAL_VALUES:
        return None
    if any(len(v) > MAX_CATEGORICAL_VALUE_LENGTH for v in distinct):
        return None
    # Only for string-like or categorical logical; emit anyway if bounded
    # Limit to sorted, truncated list
    return distinct[:MAX_CATEGORICAL_VALUES]


def inspect_tabular_sample(
    path: Path,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    observation_id: str = "obs_001",
    source_label: str = "local_sample",
) -> SchemaObservation:
    """Inspect a bounded tabular sample and return a deterministic SchemaObservation.

    Supports CSV, gzip-CSV, and flat scalar Parquet via the existing
    ``iter_declared_table_chunks`` reader with explicit limits.  The path's
    suffix determines the format; an explicit declaration is synthesized
    internally (no network, no credential access).

    Raises
    ------
    TabularReadError
        When the file is unreadable, exceeds limits, or has an unsupported schema.
    ValueError
        When limits are non-positive or traversal fails.
    """
    if max_rows < 1 or max_bytes < 1:
        raise ValueError("max_rows and max_bytes must be positive")
    if not path.exists():
        from traffictwin.validation.codes import ValidationCode

        raise TabularReadError(
            code=ValidationCode.TABULAR_FILE_INVALID,
            message=f"sample path does not exist: {path}",
        )
    # Path-traversal safety: caller must pass a resolved path; we ensure it is not a
    # directory and has an allowed suffix.
    if path.is_dir():
        raise ValueError("sample path must be a file, not a directory")
    # Reject absolute paths that look like secrets? We redact in portable identity but
    # allow inspection; portable fields will be redacted.
    declaration = _declaration_for_path(path)
    # Bounded read via existing chunk iterator
    headers: list[str] = []
    rows: list[dict[str, str | None]] = []
    total_bytes_est = 0
    truncated = False
    for chunk in iter_declared_table_chunks(
        path,
        declaration,
        chunk_rows=min(max_rows, 1000),
        max_uncompressed_bytes=max_bytes,
        max_chunk_bytes=max_bytes,
    ):
        if not headers:
            headers = chunk.headers
        # headers must be stable across chunks (tabular guarantees)
        for row in chunk.rows:
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append(row)
            # crude byte count
            total_bytes_est += sum(len((v or "").encode("utf-8")) for v in row.values())
            if total_bytes_est > max_bytes:
                truncated = True
                break
        if truncated:
            break
        if len(rows) >= max_rows:
            # If we stopped because we hit the row limit, mark truncated.
            # We cannot know if the file had exactly max_rows rows without
            # peeking further; treat hitting the limit as truncated to avoid
            # silently claiming a complete bounded read.
            truncated = True
            break

    if not headers:
        from traffictwin.validation.codes import ValidationCode

        raise TabularReadError(
            code=ValidationCode.TABULAR_FILE_INVALID,
            message="sample has no header row",
        )

    # Build field observations preserving original header order for drift detection;
    # fingerprint will sort deterministically afterwards.
    field_observations: list[FieldObservation] = []
    total_observed_rows = len(rows)
    for field in headers:
        values: list[str | None] = [row.get(field) for row in rows]
        non_empty = [v for v in values if v is not None and v.strip() != ""]
        null_count = total_observed_rows - len(non_empty)
        nullable = null_count > 0
        # Infer logical type from non-empty sample
        logical = _infer_logical_type(non_empty) if non_empty else LogicalType.STRING
        # Timestamp parse state
        ts_state = _timestamp_parse_state(values, logical)
        # Categorical digest (bounded, secret-redacted)
        cat_digest: list[str] | None = None
        # Only produce categorical digest for string/categorical-like fields
        if (
            logical in {LogicalType.STRING, LogicalType.CATEGORICAL}
            or logical is LogicalType.STRING
        ):
            cat_digest = _categorical_digest(values, field_name=field)
        else:
            # For non-string, only provide digest if small distinct set (e.g., boolean)
            if logical is LogicalType.BOOLEAN:
                cat_digest = _categorical_digest(values, field_name=field)
        # Precision / scale
        precision, scale = _precision_scale(non_empty, logical)

        obs = FieldObservation(
            field_name=field,
            observed_logical_type=logical,
            nullable=nullable,
            observed_count=total_observed_rows,
            null_count=null_count,
            timestamp_parse_state=ts_state,
            categorical_digest=cat_digest,
            precision=precision,
            scale=scale,
        )
        field_observations.append(obs)

    # Deterministic fingerprint excludes raw values, paths, clocks; includes field
    # observations, counts, truncated flag, and redacted source label.
    # Portable identity must not contain absolute paths or secrets; use a stable
    # redacted label so fingerprints are path-independent.
    if is_secret_like(source_label):
        redacted_label = "[REDACTED_SOURCE_LABEL]"
    elif "/" in source_label or "\\" in source_label:
        redacted_label = "local_sample"
    else:
        redacted_label = _safe_label(source_label)

    # Build canonical payload for fingerprint (sorted fields already)
    payload = {
        "schema_version": "1.0",
        "source_label_redacted": redacted_label,
        "total_observed_rows": total_observed_rows,
        "truncated": truncated,
        "field_observations": [
            fo.model_dump(mode="json")
            for fo in sorted(field_observations, key=lambda x: x.field_name)
        ],
    }
    fingerprint = fingerprint_canonical(payload)

    observation = SchemaObservation(
        observation_id=observation_id.strip(),
        source_label_redacted=redacted_label,
        total_observed_rows=total_observed_rows,
        field_observations=field_observations,
        truncated=truncated,
        fingerprint=fingerprint,
    )
    return observation


def _declaration_for_path(path: Path) -> FileDeclaration:
    suffixes = [s.lower() for s in path.suffixes]
    # Detect gzip CSV: .csv.gz or .gz with csv expectation
    if suffixes[-2:] == [".csv", ".gz"] or (
        path.suffix.lower() == ".gz" and ".csv" in "".join(suffixes)
    ):
        return FileDeclaration(
            path="sample.csv",  # dummy relative; not used for identity
            format=SourceFileFormat.CSV,
            compression=SourceCompression.GZIP,
        )
    if path.suffix.lower() == ".csv":
        return FileDeclaration(
            path="sample.csv",
            format=SourceFileFormat.CSV,
        )
    if path.suffix.lower() == ".parquet":
        return FileDeclaration(
            path="sample.parquet",
            format=SourceFileFormat.PARQUET,
        )
    # Fallback: try CSV
    if path.suffix.lower() == ".gz":
        return FileDeclaration(
            path="sample.csv",
            format=SourceFileFormat.CSV,
            compression=SourceCompression.GZIP,
        )
    # Default to CSV; tabular reader will error if mismatch
    return FileDeclaration(
        path="sample.csv",
        format=SourceFileFormat.CSV,
    )


def is_secret_like(value: str) -> bool:
    """Check if a source label looks secret-bearing."""
    lower = value.lower()
    secret_substrings = ("password", "secret", "api_key", "apikey", "token", "credential")
    return any(sub in lower for sub in secret_substrings)


def _safe_label(label: str) -> str:
    """Redact absolute-path-like labels to avoid leaking paths."""
    # Portable identity must be path-independent; any path-like label is normalized.
    if "/" in label or "\\" in label:
        return "local_sample"
    # Truncate to safe length
    return label[:64] if len(label) > 64 else label
