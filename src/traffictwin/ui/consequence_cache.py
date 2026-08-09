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

Fail-closed: if the current logical fingerprint cannot be established
(missing path, ``BundleLoadError``, ``OSError``) the cache is bypassed,
ordinary validation runs, and nothing is stored.  Failed validation
(``analysis_ready is False``) or a missing ``validation.fingerprint`` is
never stored.  The cache never stores ``None`` as an ordinary token.

Race safety: the cache binds ``BundleAnalysis`` to the fingerprint of the
evidence that produced that analysis (``analysis.validation.fingerprint``),
never to a fingerprint recomputed after validation.  If evidence mutates
while the validator is reading it, the cached entry remains bound to the
older fingerprint and the next rerender recomputes the current logical
fingerprint, misses, and self-heals — no sticky stale analysis.

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
from pathlib import Path

from traffictwin.ingestion.hashes import fingerprint_bundle_source
from traffictwin.ui.services import validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis

_MAX_BUNDLE_CACHE = 32


def _resolved_path_str(path: Path) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(path)


def _bundle_freshness_token(path: Path) -> str | None:
    """Deprecated alias for :func:`fingerprint_bundle_source`.

    Retained for backward compatibility with tests that import the old name.
    Forwards to the authoritative logical bundle fingerprint.  Prefer
    :func:`fingerprint_bundle_source` directly.
    """

    return fingerprint_bundle_source(path)


# ---------------------------------------------------------------------------
# Session cache helpers
# ---------------------------------------------------------------------------


def _session_cache_get(
    cache_dict: dict[str, tuple[str, BundleAnalysis]],
    path: Path,
    current_fingerprint: str,
) -> BundleAnalysis | None:
    resolved = _resolved_path_str(path)
    entry = cache_dict.get(resolved)
    if entry is None:
        return None
    try:
        cached_token, cached_analysis = entry
    except (TypeError, ValueError):
        return None
    if not isinstance(cached_token, str):
        return None
    if cached_token != current_fingerprint:
        return None
    # Defensive: ensure cached_analysis looks like BundleAnalysis
    if not hasattr(cached_analysis, "validation"):
        return None
    return copy.deepcopy(cached_analysis)


def _session_cache_put(
    cache_dict: dict[str, tuple[str, BundleAnalysis]],
    path: Path,
    validation_fingerprint: str,
    analysis: BundleAnalysis,
) -> None:
    p = Path(path)
    try:
        if not p.exists():
            return
    except OSError:
        return
    resolved = _resolved_path_str(p)
    # Bounded FIFO via insertion order (Python 3.7+ dict preserves order)
    if resolved not in cache_dict and len(cache_dict) >= _MAX_BUNDLE_CACHE:
        oldest = next(iter(cache_dict))
        cache_dict.pop(oldest, None)
    cache_dict[resolved] = (validation_fingerprint, copy.deepcopy(analysis))


def session_validate_bundle(path: Path, session_state: dict[str, object]) -> BundleAnalysis:
    """Session-scoped cached validation using ``session_state`` dict.

    The cache lives in ``session_state["_consequence_bundle_cache"]`` and is
    bounded to 32 entries (FIFO).  See module docstring for the full
    invariant.
    """

    raw_cache = session_state.get("_consequence_bundle_cache")
    if not isinstance(raw_cache, dict):
        cache_dict: dict[str, tuple[str, BundleAnalysis]] = {}
        session_state["_consequence_bundle_cache"] = cache_dict
    else:
        cache_dict = raw_cache

    # A. Obtain CURRENT logical source fingerprint for cache lookup.
    # B. If unavailable → fail closed, bypass cache.
    current_fp = fingerprint_bundle_source(path)
    if current_fp is None:
        # Fail closed: bypass cache, run ordinary validation, do not store.
        try:
            analysis = validate_bundle_for_ui(path)
        except Exception:
            raise
        return copy.deepcopy(analysis)

    # C. Check cache for same resolved source + same logical fingerprint.
    cached = _session_cache_get(cache_dict, path, current_fp)
    if cached is not None:
        return cached

    # D. On miss: run validation.
    try:
        analysis = validate_bundle_for_ui(path)
    except Exception:
        raise

    # E. Never store failed or fingerprint-less analyses.
    if not getattr(analysis, "analysis_ready", False):
        return copy.deepcopy(analysis)
    validation_fp = getattr(analysis.validation, "fingerprint", None)
    if not isinstance(validation_fp, str) or validation_fp is None:
        return copy.deepcopy(analysis)
    # Additional guard: ensure path still exists before storing.
    try:
        if not Path(path).exists():
            return copy.deepcopy(analysis)
    except OSError:
        return copy.deepcopy(analysis)

    # F. Store using the fingerprint of the evidence that produced the
    # analysis, NOT a fresh post-validation rehash.
    _session_cache_put(cache_dict, path, validation_fp, analysis)
    return copy.deepcopy(analysis)


# ---------------------------------------------------------------------------
# Deprecated module-level cache (removed)
# ---------------------------------------------------------------------------

# The module-level cache (_BUNDLE_CACHE, _BUNDLE_CACHE_ORDER,
# get_cached_bundle, put_cached_bundle, validate_bundle_cached) had no
# production caller — the Consequence page uses only session_validate_bundle.
# It has been removed to avoid duplicate cache architecture and redundant
# hashing.  ``clear_bundle_cache`` is retained as a no-op for backward
# compatibility with tests that import it.


def clear_bundle_cache() -> None:
    """Deprecated no-op: module-level cache has been removed.

    Retained for backward compatibility with tests that call it.  The active
    cache is session-local in ``st.session_state["_consequence_bundle_cache"]``.
    """

    return None
