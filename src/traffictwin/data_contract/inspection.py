"""Bounded deterministic schema inspection for tabular samples.

Reuses existing safe readers (CSV, gzip-CSV, Parquet) with explicit row and
byte limits. Never loads an unbounded file to infer a schema.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from traffictwin.data_contract.fingerprint import fingerprint_canonical
from traffictwin.data_contract.models import FieldObservation, LogicalType, SchemaObservation
from traffictwin.ingestion.manifest import FileDeclaration, SourceCompression, SourceFileFormat
from traffictwin.ingestion.tabular import TabularReadError, iter_declared_table_chunks
from traffictwin.validation.codes import ValidationCode

# Default inspection limits – conservative for UI use.
DEFAULT_MAX_ROWS = 5000
DEFAULT_MAX_BYTES = 5_000_000  # 5 MB uncompressed
MAX_CATEGORICAL_VALUES = 20
MAX_CATEGORICAL_VALUE_LENGTH = 64

_TIMESTAMP_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"),
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
]

# Robust numeric patterns
_INT_RE = re.compile(r"^[+-]?\d+$")
# Float with optional exponent: 1., .5, 1.0, 1e5, -2.5e-4 etc. Use Decimal try instead of regex alone.  # noqa: E501
_SCIENTIFIC_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def _infer_logical_type(values: list[str]) -> LogicalType:
    """Infer logical type from bounded sample values (None already filtered)."""
    if not values:
        return LogicalType.STRING
    stripped = [v.strip() for v in values if v.strip() != ""]
    if not stripped:
        return LogicalType.STRING
    # Check boolean (case-insensitive, but not numeric)
    lower = [v.lower() for v in stripped]
    if all(v in {"true", "false", "yes", "no", "t", "f", "y", "n"} for v in lower):
        # Avoid classifying "1"/"0" as boolean when they are numeric; already handled above?
        # If all are 1/0, they could be boolean or integer; prefer boolean for explicit t/f/yes/no
        # but 1/0 alone is ambiguous – treat as integer if not mixed with true/false words
        if any(v in {"true", "false", "yes", "no", "t", "f", "y", "n"} for v in lower):
            return LogicalType.BOOLEAN
        # If only 1/0, treat as integer (less surprising)
        if all(v in {"1", "0"} for v in lower):
            # Could be boolean, but keep integer to avoid false positive
            pass
        else:
            return LogicalType.BOOLEAN
    # Check integer via Decimal exact int
    all_int = True
    for v in stripped:
        if not _INT_RE.fullmatch(v):
            all_int = False
            break
        try:
            iv = int(v)
            if abs(iv) > 2**63 - 1:
                return LogicalType.DECIMAL
        except ValueError:
            all_int = False
            break
    if all_int:
        return LogicalType.INTEGER
    # Check numeric via Decimal (handles scientific notation, 1., .5, etc.)
    all_numeric = True
    has_float = False
    for v in stripped:
        if not _SCIENTIFIC_RE.fullmatch(v):
            all_numeric = False
            break
        try:
            d = Decimal(v)
            if d.is_nan() or d.is_infinite():
                all_numeric = False
                break
            if "." in v or "e" in v.lower():
                has_float = True
                exp = d.as_tuple().exponent
                if isinstance(exp, int) and exp < -6:
                    return LogicalType.DECIMAL
        except InvalidOperation:
            all_numeric = False
            break
    if all_numeric:
        return LogicalType.FLOAT if has_float else LogicalType.INTEGER
    # Check timestamp
    if all(any(p.match(v) for p in _TIMESTAMP_PATTERNS) for v in stripped):
        return LogicalType.TIMESTAMP
    return LogicalType.STRING


def _timestamp_parse_state(values: list[str | None], logical_type: LogicalType) -> str:
    if logical_type is not LogicalType.TIMESTAMP:
        return "not_timestamp"
    non_null = [v for v in values if v is not None and v.strip() != ""]
    if not non_null:
        return "not_timestamp"
    # Count aware vs naive
    aware_count = 0
    naive_count = 0
    parse_ok = 0
    for v in non_null:
        vv = v.strip()
        matches = any(p.match(vv) for p in _TIMESTAMP_PATTERNS)
        if not matches:
            continue
        parse_ok += 1
        has_tz = vv.endswith("Z") or "+" in vv or vv.count(":") >= 3
        # Also consider 'Z' as aware, offset as aware
        if has_tz or vv.endswith("Z"):
            aware_count += 1
        else:
            naive_count += 1
    if parse_ok == 0:
        return "parse_failed"
    if parse_ok != len(non_null):
        return "parse_ambiguous"
    if aware_count > 0 and naive_count > 0:
        return "parse_ambiguous"
    if aware_count > 0:
        return "parsed_with_tz"
    return "parsed_naive"


def _precision_scale(values: list[str], logical_type: LogicalType) -> tuple[int | None, int | None]:
    if logical_type not in {LogicalType.FLOAT, LogicalType.DECIMAL, LogicalType.INTEGER}:
        return None, None
    max_prec: int | None = None
    max_scale: int | None = None
    for v in values:
        vv = v.strip()
        if vv == "":
            continue
        try:
            d = Decimal(vv)
            if d.is_nan() or d.is_infinite():
                continue
            _sign, _digits, _exp = d.as_tuple()
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


def _categorical_structural_evidence(
    values: list[str | None],
) -> tuple[int | None, str | None]:
    """Return (distinct_count, aggregate_hash) without raw values.

    Bounded to MAX_CATEGORICAL_VALUES distinct values and length; otherwise None.
    Hash is SHA256 of sorted distinct values joined by \\0, deterministic.
    """
    non_null = [v for v in values if v is not None and v.strip() != ""]
    if not non_null:
        return None, None
    distinct = sorted(set(non_null))
    if len(distinct) > MAX_CATEGORICAL_VALUES:
        return None, None
    if any(len(v) > MAX_CATEGORICAL_VALUE_LENGTH for v in distinct):
        return None, None
    distinct_count = len(distinct)
    # Aggregate hash over sorted distinct values
    h = hashlib.sha256()
    for v in distinct:
        h.update(v.encode("utf-8"))
        h.update(b"\0")
    aggregate_hash = h.hexdigest()
    return distinct_count, aggregate_hash


# ---------------------------------------------------------------------------
# Workspace containment and suffix allowlist
# ---------------------------------------------------------------------------

_ALLOWED_SUFFIXES = frozenset({".csv", ".parquet"})
_ALLOWED_GZ_SUFFIX = (".csv.gz",)


def _validate_sample_suffix(path: Path) -> None:
    name = path.name.lower()
    if name.endswith(".csv.gz"):
        return
    if path.suffix.lower() in {".csv", ".parquet"}:
        return
    raise TabularReadError(
        ValidationCode.TABULAR_FILE_INVALID,
        f"unsupported sample format for '{path.name}': allowed .csv, .csv.gz, .parquet",
    )


def _resolve_safe_sample_path(path: Path) -> Path:
    """Validate workspace containment and suffix allowlist; return resolved path.

    Approved roots: cwd and system temp (for pytest tmp_path). Refuses absolute
    escapes outside those roots and symlink escapes.
    """
    _validate_sample_suffix(path)
    # Resolve without requiring existence check beyond earlier exists check
    try:
        resolved = path.resolve(strict=False)
    except Exception as exc:
        raise TabularReadError(
            ValidationCode.TABULAR_FILE_INVALID, f"could not resolve sample path: {exc}"
        ) from exc
    # Approved roots
    cwd_root = Path.cwd().resolve()
    tmp_root = Path(tempfile.gettempdir()).resolve()
    allowed_roots = {cwd_root, tmp_root}
    is_under_allowed = any(resolved == root or root in resolved.parents for root in allowed_roots)
    if not is_under_allowed:
        # Also allow if path is under /tmp/traffictwin-data-contract (our worktree) which is under cwd? Actually worktree is /tmp/traffictwin-data-contract, which is under /tmp, so covered.  # noqa: E501
        raise TabularReadError(
            ValidationCode.TABULAR_FILE_INVALID,
            f"sample path escapes approved workspace: {path}",
        )
    # Symlink escape is already handled by resolve + parents check
    return resolved


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
        raise TabularReadError(
            ValidationCode.TABULAR_FILE_INVALID,
            f"sample path does not exist: {path}",
        )
    if path.is_dir():
        raise ValueError("sample path must be a file, not a directory")
    # Workspace containment and suffix allowlist (BLOCKER 10)
    _resolve_safe_sample_path(path)
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
        for row in chunk.rows:
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append(row)
            total_bytes_est += sum(len((v or "").encode("utf-8")) for v in row.values())
            if total_bytes_est > max_bytes:
                truncated = True
                break
        if truncated:
            break
        if len(rows) >= max_rows:
            truncated = True
            break

    if not headers:
        raise TabularReadError(
            ValidationCode.TABULAR_FILE_INVALID,
            "sample has no header row",
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
        logical = _infer_logical_type(non_empty) if non_empty else LogicalType.STRING
        ts_state = _timestamp_parse_state(values, logical)
        # Categorical structural evidence (non-reversible)
        distinct_count: int | None = None
        aggregate_hash: str | None = None
        if logical in {LogicalType.STRING, LogicalType.CATEGORICAL, LogicalType.BOOLEAN}:
            distinct_count, aggregate_hash = _categorical_structural_evidence(values)
        precision, scale = _precision_scale(non_empty, logical)

        obs = FieldObservation(
            field_name=field,
            observed_logical_type=logical,
            nullable=nullable,
            observed_count=total_observed_rows,
            null_count=null_count,
            timestamp_parse_state=ts_state,
            categorical_distinct_count=distinct_count,
            categorical_aggregate_hash=aggregate_hash,
            precision=precision,
            scale=scale,
        )
        field_observations.append(obs)

    # Deterministic fingerprint excludes raw values, paths, clocks; includes field
    # observations, counts, truncated flag, and redacted source label.
    # Portable identity must not contain absolute paths or secrets; use a stable
    # redacted label so fingerprints are path-independent.
    if _is_secret_like(source_label):
        redacted_label = "[REDACTED_SOURCE_LABEL]"
    elif "/" in source_label or "\\" in source_label:
        redacted_label = "local_sample"
    else:
        redacted_label = _safe_label(source_label)

    # Build canonical payload for fingerprint (sorted fields)
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
    name = path.name.lower()
    if name.endswith(".csv.gz"):
        return FileDeclaration(
            path="sample.csv",
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
    if path.suffix.lower() == ".gz":
        return FileDeclaration(
            path="sample.csv",
            format=SourceFileFormat.CSV,
            compression=SourceCompression.GZIP,
        )
    return FileDeclaration(
        path="sample.csv",
        format=SourceFileFormat.CSV,
    )


def _is_secret_like(value: str) -> bool:
    """High-confidence secret detection (prefixes, not substring)."""
    # Only treat high-confidence patterns as secret to avoid false positives on
    # ordinary text like "Secret Garden" or "Token Street".
    patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"ghp_[0-9A-Za-z]{36}"),
        re.compile(r"sk-[0-9A-Za-z]{20,}"),
        re.compile(r"sk-proj-[0-9A-Za-z\-_]{20,}"),
    ]
    return any(p.search(value) for p in patterns)


def _safe_label(label: str) -> str:
    """Redact absolute-path-like labels to avoid leaking paths."""
    if "/" in label or "\\" in label:
        return "local_sample"
    return label[:64] if len(label) > 64 else label
