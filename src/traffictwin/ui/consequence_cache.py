"""Session-local BundleAnalysis cache for the Consequence page.

Caches ``BundleAnalysis`` (validation + metrics + evidence + diagnostics) in
``st.session_state`` to avoid repeated canonicalisation/metric work across
Streamlit rerenders.  The cache key is LOCAL, session-only state
(resolved path + logical bundle fingerprint) that never enters
``ConsequenceLensReport`` fingerprint or portable export.

Freshness uses the authoritative ingestion helper
``fingerprint_bundle_source`` which opens the bundle workspace (handling both
directory and ``.zip`` inputs) and fingerprints the logical bundle files via
``bundle_fingerprint``/``fingerprint_workspace``.  Any change to evidence
bytes — including same-size rewrites with restored mtime, atomic
replacements, additions, deletions, or renames — changes the logical
fingerprint and invalidates the cached analysis.

For ``.zip`` sources, warm unchanged lookups avoid extraction: the cache
stores both the raw archive witness (``sha256_file`` of the ``.zip`` bytes)
and the logical validation fingerprint.  On warm, only the raw witness is
recomputed (one ``sha256_file``); if it matches the stored raw, the archive
bytes are identical and the cached ``BundleAnalysis`` is returned without
extraction or validator invocation.  The raw witness is local-only and never
replaces logical bundle identity in reports or exports.

Fail-closed: if the current logical fingerprint (directory) or raw witness
(ZIP) cannot be established (missing path, ``BundleLoadError``, ``OSError``)
the cache is bypassed, ordinary validation runs, and nothing is stored.
Failed validation (``analysis_ready is False``) or a missing
``validation.fingerprint`` is never stored.

Race safety: the cache binds ``BundleAnalysis`` to the fingerprint of the
evidence that produced that analysis (``analysis.validation.fingerprint``),
never to a fingerprint recomputed after validation.  For ZIP, also binds to
the raw witness observed before validation and only caches when
``raw_before == raw_after``; if the archive mutates during validation, the
next access misses and self-heals — no sticky stale analysis.

Bounded FIFO (32) with deep-copy isolation on store and retrieval so
callers cannot poison cached state.  Malformed legacy entries are treated as
misses, never crashes.  The cache is session-local and O(evidence bytes)
on every access because it must read evidence to establish freshness; it
avoids repeated canonicalisation/metric/evidence work but is NOT O(1) with
respect to bundle size and is not universally "cheap" for large artifacts.

Traversal contract: explicit fingerprint/open/read failures return no
cacheable fingerprint.  Cache freshness follows the same opened-workspace
file-discovery semantics as ordinary bundle validation
(``Path.rglob`` over the opened workspace).  If the filesystem silently
hides an unreadable subdirectory, both validation and this helper observe the
same visible subset — no stronger filesystem guarantee is claimed than
validation itself provides.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

from traffictwin.ingestion.hashes import fingerprint_bundle_source, sha256_file
from traffictwin.ui.services import validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis

_MAX_BUNDLE_CACHE = 32


@dataclass(frozen=True)
class _SessionCacheEntry:
    raw: str | None
    logical: str
    analysis: BundleAnalysis


def _resolved_path_str(path: Path) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(path)


def _is_zip_source(path: Path) -> bool:
    try:
        return path.is_file() and path.suffix.lower() == ".zip"
    except OSError:
        return False


def _raw_zip_witness(path: Path) -> str | None:
    """Raw archive witness for ZIP sources, else ``None``."""
    if not _is_zip_source(path):
        return None
    try:
        if not path.exists():
            return None
        return sha256_file(path)
    except OSError:
        return None


def _parse_entry(value: object) -> _SessionCacheEntry | None:
    """Validate an untrusted cache value and return a typed entry or ``None``.

    Supports:
    * current 3-tuple ``(raw, logical, analysis)`` where ``raw`` is ``str|None``,
      ``logical`` is ``str``, ``analysis`` is ``BundleAnalysis``;
    * legacy 2-tuple ``(logical, analysis)`` where ``logical`` is ``str`` and
      ``analysis`` is ``BundleAnalysis`` (treated as directory entry with
      ``raw=None`` for backwards compatibility; new writes always use 3-tuple).

    Malformed entries return ``None`` and are treated as a miss, never a crash.
    """

    if not isinstance(value, tuple):
        return None
    if len(value) == 2:
        logical, analysis = value
        raw: str | None = None
        if not isinstance(logical, str):
            return None
        if not isinstance(analysis, BundleAnalysis):
            return None
        return _SessionCacheEntry(raw=raw, logical=logical, analysis=analysis)
    if len(value) == 3:
        raw, logical, analysis = value
        if raw is not None and not isinstance(raw, str):
            return None
        if not isinstance(logical, str):
            return None
        if not isinstance(analysis, BundleAnalysis):
            return None
        return _SessionCacheEntry(raw=raw, logical=logical, analysis=analysis)
    return None


def _session_cache_get(
    cache_dict: dict[str, object],
    path: Path,
    *,
    is_zip: bool,
    current_raw: str | None,
    current_logical: str | None,
) -> BundleAnalysis | None:
    resolved = _resolved_path_str(path)
    raw_entry = cache_dict.get(resolved)
    entry = _parse_entry(raw_entry)
    if entry is None:
        return None
    if is_zip:
        if entry.raw is None or current_raw is None:
            return None
        if entry.raw != current_raw:
            return None
        return copy.deepcopy(entry.analysis)
    if current_logical is None or entry.logical != current_logical:
        return None
    return copy.deepcopy(entry.analysis)


def _session_cache_put(
    cache_dict: dict[str, object],
    path: Path,
    *,
    is_zip: bool,
    raw_witness: str | None,
    logical_fingerprint: str,
    analysis: BundleAnalysis,
) -> None:
    p = Path(path)
    try:
        if not p.exists():
            return
    except OSError:
        return
    resolved = _resolved_path_str(p)
    if resolved not in cache_dict and len(cache_dict) >= _MAX_BUNDLE_CACHE:
        oldest = next(iter(cache_dict))
        cache_dict.pop(oldest, None)
    if is_zip:
        if raw_witness is None:
            return
        cache_dict[resolved] = (raw_witness, logical_fingerprint, copy.deepcopy(analysis))
    else:
        cache_dict[resolved] = (None, logical_fingerprint, copy.deepcopy(analysis))


def session_validate_bundle(path: Path, session_state: dict[str, object]) -> BundleAnalysis:
    """Session-scoped cached validation using ``session_state`` dict.

    The cache lives in ``session_state["_consequence_bundle_cache"]`` and is
    bounded to 32 entries (FIFO).  See module docstring for the full
    invariant.
    """

    raw_cache = session_state.get("_consequence_bundle_cache")
    if not isinstance(raw_cache, dict):
        cache_dict: dict[str, object] = {}
        session_state["_consequence_bundle_cache"] = cache_dict
    else:
        cache_dict = raw_cache

    is_zip = _is_zip_source(Path(path))

    if is_zip:
        current_raw = _raw_zip_witness(Path(path))
        if current_raw is None:
            analysis = validate_bundle_for_ui(path)
            return copy.deepcopy(analysis)
        cached = _session_cache_get(
            cache_dict, Path(path), is_zip=True, current_raw=current_raw, current_logical=None
        )
        if cached is not None:
            return cached
        analysis = validate_bundle_for_ui(path)
        if not analysis.analysis_ready:
            return copy.deepcopy(analysis)
        validation_fp = analysis.validation.fingerprint
        if not isinstance(validation_fp, str):
            return copy.deepcopy(analysis)
        try:
            if not Path(path).exists():
                return copy.deepcopy(analysis)
        except OSError:
            return copy.deepcopy(analysis)
        raw_after = _raw_zip_witness(Path(path))
        if raw_after is None or raw_after != current_raw:
            return copy.deepcopy(analysis)
        _session_cache_put(
            cache_dict,
            Path(path),
            is_zip=True,
            raw_witness=current_raw,
            logical_fingerprint=validation_fp,
            analysis=analysis,
        )
        return copy.deepcopy(analysis)
    current_fp = fingerprint_bundle_source(path)
    if current_fp is None:
        analysis = validate_bundle_for_ui(path)
        return copy.deepcopy(analysis)
    cached = _session_cache_get(
        cache_dict, Path(path), is_zip=False, current_raw=None, current_logical=current_fp
    )
    if cached is not None:
        return cached
    analysis = validate_bundle_for_ui(path)
    if not analysis.analysis_ready:
        return copy.deepcopy(analysis)
    validation_fp = analysis.validation.fingerprint
    if not isinstance(validation_fp, str):
        return copy.deepcopy(analysis)
    try:
        if not Path(path).exists():
            return copy.deepcopy(analysis)
    except OSError:
        return copy.deepcopy(analysis)
    _session_cache_put(
        cache_dict,
        Path(path),
        is_zip=False,
        raw_witness=None,
        logical_fingerprint=validation_fp,
        analysis=analysis,
    )
    return copy.deepcopy(analysis)
