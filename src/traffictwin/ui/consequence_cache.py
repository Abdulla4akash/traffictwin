"""Small session-level cache for bundle validation on the Consequence page.

Caches ``BundleAnalysis`` before the expensive ``validate_bundle_for_ui`` work.
The cache key contains LOCAL cache-only state (resolved path + content-based
freshness token) that never enters the ConsequenceLensReport fingerprint or
portable export.

Freshness token is a bounded deterministic content witness over all
validator-relevant bundle files: sorted relative paths + SHA-256 of each
file's bytes (via ``bundle_fingerprint``). Any change to evidence bytes —
including same-size rewrites with restored mtime, atomic replacements,
additions, deletions, or renames — invalidates the cached analysis.

Ambiguous freshness (missing path, stat/read error, partial traversal,
unreadable child, malformed entry, resolver failure) fails closed:
it is a miss and is never stored as an ordinary token.

Cache is bounded (FIFO 32) and deep-copy isolated so callers cannot poison
cached state. Cleanup is a single clear.

The module-level cache is used by tests and as a fallback; the page also
mirrors to ``st.session_state`` for Streamlit session scope. Both share the
same token logic.

Content hashing is measured to remain cheaper than full validation
(canonicalisation + evidence building) while closing the metadata-only
collision.
"""

from __future__ import annotations

import copy
from pathlib import Path

from traffictwin.ingestion.hashes import bundle_fingerprint, sha256_file
from traffictwin.ui.services import validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis

_MAX_BUNDLE_CACHE = 32

# Module-level cache for unit tests and non-Streamlit callers.
# Structure: resolved_path_str -> (freshness_token, BundleAnalysis deep copy)
_BUNDLE_CACHE: dict[str, tuple[str, BundleAnalysis]] = {}
_BUNDLE_CACHE_ORDER: list[str] = []


def _bundle_freshness_token(path: Path) -> str | None:
    """Content-based freshness token for a bundle path (fail-closed).

    For directories: deterministic ``bundle_fingerprint`` over all files
    (sorted relative path + SHA-256 of each file's bytes). Any byte change —
    even same-size with restored mtime — changes the token. For single files
    (e.g., ZIP bundles): SHA-256 of the file's bytes.

    Returns ``None`` on any ambiguous state (missing path, stat/read error,
    unreadable child, partial traversal, resolver failure). ``None`` is
    treated as a miss and is never stored.
    """

    p = Path(path)
    try:
        if not p.exists():
            return None
        if p.is_file():
            try:
                return sha256_file(p)
            except OSError:
                return None
        # Directory bundle: collect all files deterministically
        files: list[Path] = []
        try:
            for child in sorted(p.rglob("*"), key=lambda x: x.as_posix()):
                if child.is_file():
                    # Ensure file is readable; any unreadable child → ambiguous
                    try:
                        # Quick readability check: try to stat and open
                        child.stat()
                        # Verify we can hash it (will raise OSError if unreadable)
                        # We do not hash yet here to avoid double hashing;
                        # we just collect and let bundle_fingerprint hash
                        files.append(child)
                    except OSError:
                        return None
        except OSError:
            return None
        if not files:
            # Empty directory: treat as ambiguous (no validator-relevant evidence)
            return None
        try:
            return bundle_fingerprint(files, p)
        except OSError:
            return None
    except OSError:
        return None


def _resolved_path_str(path: Path) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(path)


def get_cached_bundle(path: Path) -> BundleAnalysis | None:
    """Return deep copy from module cache if token matches, else None."""

    resolved = _resolved_path_str(path)
    token = _bundle_freshness_token(path)
    if token is None:
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
    if token is None:
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
    On miss, validates, caches (if path exists and validation succeeded),
    and returns a deep copy. Failed validation or exceptions are never cached
    (fail-closed).
    """

    cached = get_cached_bundle(path)
    if cached is not None:
        return cached
    try:
        analysis = validate_bundle_for_ui(path)
    except Exception:
        # Exception → never cached, propagate
        raise
    # Only cache successful (analysis_ready) analyses; failed validation is not cached
    if Path(path).exists() and getattr(analysis, "analysis_ready", False):
        put_cached_bundle(path, analysis)
    # Return deep copy so caller mutation cannot poison cache
    return copy.deepcopy(analysis)


# Session-level helpers (for the page, using st.session_state dict)


def _session_cache_get(
    cache_dict: dict[str, tuple[str, BundleAnalysis]], path: Path
) -> BundleAnalysis | None:
    resolved = _resolved_path_str(path)
    token = _bundle_freshness_token(path)
    if token is None:
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
    if token is None:
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
    try:
        analysis = validate_bundle_for_ui(path)
    except Exception:
        raise
    if Path(path).exists() and getattr(analysis, "analysis_ready", False):
        _session_cache_put(cache_dict, path, analysis)
    return copy.deepcopy(analysis)
