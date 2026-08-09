"""Small session-level cache for bundle validation on the Consequence page.

Caches ``BundleAnalysis`` before the expensive ``validate_bundle_for_ui`` work.
The cache key contains LOCAL cache-only state (resolved path + lightweight
freshness token) that never enters the ConsequenceLensReport fingerprint or
portable export.

Freshness token is a bounded deterministic metadata token over bundle files:
sorted relative paths + size + st_mtime_ns, hashed to a short digest.
It detects meaningful file changes without rereading the full artifact.

Cache is bounded (FIFO 32) and deep-copy isolated so callers cannot poison
cached state. Cleanup is a single clear.

The module-level cache is used by tests and as a fallback; the page also
mirrors to ``st.session_state`` for Streamlit session scope. Both share the
same token logic.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from traffictwin.ui.services import validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis

_MAX_BUNDLE_CACHE = 32

# Module-level cache for unit tests and non-Streamlit callers.
# Structure: resolved_path_str -> (freshness_token, BundleAnalysis deep copy)
_BUNDLE_CACHE: dict[str, tuple[str, BundleAnalysis]] = {}
_BUNDLE_CACHE_ORDER: list[str] = []


def _bundle_freshness_token(path: Path) -> str:
    """Lightweight freshness token for a bundle path.

    For directories: sorted ``rel_path:size:mtime_ns`` for every file under
    the bundle, hashed to 16 hex chars. For single files: ``name:size:mtime``.
    Missing paths return ``"missing"`` so they are never considered a hit.
    """

    p = Path(path)
    try:
        if not p.exists():
            return "missing"
        if p.is_file():
            stat = p.stat()
            return f"{p.name}:{stat.st_size}:{stat.st_mtime_ns}"
        # Directory bundle
        entries: list[str] = []
        # Use rglob to capture all files, sorted for determinism
        for child in sorted(p.rglob("*"), key=lambda x: x.as_posix()):
            if child.is_file():
                try:
                    stat = child.stat()
                    rel = child.relative_to(p).as_posix()
                    entries.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
                except OSError:
                    continue
        if not entries:
            try:
                stat = p.stat()
                return f"empty:{stat.st_mtime_ns}"
            except OSError:
                return "empty"
        joined = "|".join(entries)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
    except OSError:
        return "error"


def _resolved_path_str(path: Path) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(path)


def get_cached_bundle(path: Path) -> BundleAnalysis | None:
    """Return deep copy from module cache if token matches, else None."""

    resolved = _resolved_path_str(path)
    token = _bundle_freshness_token(path)
    if token == "missing":  # noqa: S105
        return None
    entry = _BUNDLE_CACHE.get(resolved)
    if entry is None:
        return None
    cached_token, cached_analysis = entry
    if cached_token != token:
        return None
    return copy.deepcopy(cached_analysis)


def put_cached_bundle(path: Path, analysis: BundleAnalysis) -> None:
    """Store deep copy bounded FIFO; only for existing paths."""

    p = Path(path)
    if not p.exists():
        return
    resolved = _resolved_path_str(p)
    token = _bundle_freshness_token(p)
    if token == "missing":  # noqa: S105
        return
    # Evict oldest if at capacity and this is a new key
    if resolved not in _BUNDLE_CACHE and len(_BUNDLE_CACHE) >= _MAX_BUNDLE_CACHE:
        oldest = _BUNDLE_CACHE_ORDER.pop(0)
        _BUNDLE_CACHE.pop(oldest, None)
    _BUNDLE_CACHE[resolved] = (token, copy.deepcopy(analysis))
    if resolved in _BUNDLE_CACHE_ORDER:
        _BUNDLE_CACHE_ORDER.remove(resolved)
    _BUNDLE_CACHE_ORDER.append(resolved)


def clear_bundle_cache() -> None:
    """Clear module cache (for tests)."""

    _BUNDLE_CACHE.clear()
    _BUNDLE_CACHE_ORDER.clear()


def validate_bundle_cached(path: Path) -> BundleAnalysis:
    """Cached wrapper around ``validate_bundle_for_ui``.

    On hit, returns a deep copy without calling the expensive validator.
    On miss, validates, caches (if path exists), and returns a deep copy.
    """

    cached = get_cached_bundle(path)
    if cached is not None:
        return cached
    analysis = validate_bundle_for_ui(path)
    # Only cache when the path exists; missing/invalid paths are cheap to re-check
    # via exists() before validation, but we still cache successful analyses.
    if Path(path).exists():
        put_cached_bundle(path, analysis)
    # Return deep copy so caller mutation cannot poison cache
    return copy.deepcopy(analysis)


# Session-level helpers (for the page, using st.session_state dict)


def _session_cache_get(
    cache_dict: dict[str, tuple[str, BundleAnalysis]], path: Path
) -> BundleAnalysis | None:
    resolved = _resolved_path_str(path)
    token = _bundle_freshness_token(path)
    if token == "missing":  # noqa: S105
        return None
    entry = cache_dict.get(resolved)
    if entry is None:
        return None
    # Entry is stored as (token, analysis_dict_or_obj)
    try:
        cached_token, cached_analysis = entry
    except (TypeError, ValueError):
        return None
    if cached_token != token:
        return None
    return copy.deepcopy(cached_analysis)


def _session_cache_put(
    cache_dict: dict[str, tuple[str, BundleAnalysis]], path: Path, analysis: BundleAnalysis
) -> None:
    p = Path(path)
    if not p.exists():
        return
    resolved = _resolved_path_str(p)
    token = _bundle_freshness_token(p)
    if token == "missing":  # noqa: S105
        return
    # Bounded FIFO via insertion order; Python 3.7+ dict preserves order
    if resolved not in cache_dict and len(cache_dict) >= _MAX_BUNDLE_CACHE:
        # Remove oldest
        oldest = next(iter(cache_dict))
        cache_dict.pop(oldest, None)
    cache_dict[resolved] = (token, copy.deepcopy(analysis))


def session_validate_bundle(path: Path, session_state: dict[str, object]) -> BundleAnalysis:
    """Session-scoped cached validation using ``session_state`` dict.

    The cache lives in ``session_state["_consequence_bundle_cache"]``.
    """

    raw_cache = session_state.get("_consequence_bundle_cache")
    if not isinstance(raw_cache, dict):
        cache_dict: dict[str, tuple[str, BundleAnalysis]] = {}
        session_state["_consequence_bundle_cache"] = cache_dict
    else:
        cache_dict = raw_cache
    cached = _session_cache_get(cache_dict, path)
    if cached is not None:
        return cached
    analysis = validate_bundle_for_ui(path)
    if Path(path).exists():
        _session_cache_put(cache_dict, path, analysis)
    return copy.deepcopy(analysis)
