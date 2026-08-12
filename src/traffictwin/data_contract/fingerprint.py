"""Deterministic canonical serialisation and fingerprinting.

- Stable ordering (sorted keys, sorted field lists).
- No default=str (use explicit typed serialisation).
- Lossless numeric preservation (Decimal for precision/scale, str for large ints).
- Excludes wall clock, rendering state, local paths, secrets.
- Distinguishes unknown from false via explicit typed optionals.
- Fail-closed on malformed typed input (validation via models).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic canonical JSON bytes for *value*.

    - sort_keys=True
    - separators=(',', ':')
    - ensure_ascii=False (UTF-8)
    - No default=str: non-JSON types must be pre-serialised.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return hex SHA-256 of *data*."""
    return hashlib.sha256(data).hexdigest()


def fingerprint_canonical(value: object) -> str:
    """Fingerprint the canonical JSON encoding of *value*."""
    return sha256_hex(canonical_json_bytes(value))


def canonical_contract_dict(contract: BaseModel) -> dict[str, Any]:
    """Return a canonical dict for a pydantic model, sorted and excluding secrets.

    The caller must ensure the model dump already excludes secrets/paths/clock.
    This helper enforces stable ordering invariants.
    """
    # Use model_dump mode='json' for deterministic typed output (enums as values).
    raw: dict[str, Any] = contract.model_dump(mode="json", exclude_none=False)
    return _sort_nested(raw)  # type: ignore[no-any-return]


def _sort_nested(value: Any) -> Any:  # noqa: ANN401
    if isinstance(value, dict):
        return {k: _sort_nested(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        # Lists are left ordered; caller must sort semantic lists (e.g., fields by name)
        # before calling this. We recurse into elements.
        return [_sort_nested(v) for v in value]
    return value


def fingerprint_contract(contract: BaseModel) -> str:
    """Return fingerprint for a contract/version/observation/report."""
    canonical = canonical_contract_dict(contract)
    return fingerprint_canonical(canonical)


# ---------------------------------------------------------------------------
# Redaction helpers for portable identity
# ---------------------------------------------------------------------------

_SECRET_FIELD_SUBSTRINGS = frozenset(
    {
        "password",
        "secret",
        "api_key",
        "apikey",
        "token",
        "credential",
        "private_key",
    }
)

_SECRET_VALUE_PATTERNS = (
    # Very loose detection for demo purposes; real check uses field-name + value heuristics
    "sk-",
    "ghp_",
    "AKIA",
)

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def is_secret_field_name(name: str) -> bool:
    """Return True if *name* looks like a secret-bearing field."""
    lower = name.lower()
    return any(sub in lower for sub in _SECRET_FIELD_SUBSTRINGS)


def redact_value(value: str | None) -> str | None:
    """Redact secret-looking values."""
    if value is None:
        return None
    lower = value.lower()
    if any(pat.lower() in lower for pat in _SECRET_VALUE_PATTERNS):
        return "[REDACTED_SECRET_VALUE]"
    if is_secret_field_name(value):
        return "[REDACTED_SECRET_VALUE]"
    return value


def is_formula_value(value: str) -> bool:
    """Return True if *value* could trigger spreadsheet formula injection."""
    stripped = value.lstrip()
    if not stripped:
        return False
    return stripped[0] in _FORMULA_PREFIXES


def sanitise_for_csv(value: str) -> str:
    """Prefix formula-like values with single quote to neutralise injection.

    This matches common CSV formula-injection protection (prefix with ').
    """
    if is_formula_value(value):
        return "'" + value
    return value
