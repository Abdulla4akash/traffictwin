"""File hashing helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_fingerprint(paths: list[Path], root: Path) -> str:
    """Return a deterministic fingerprint for a set of bundle files."""

    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def fingerprint_workspace(root: Path) -> str:
    """Fingerprint an already opened bundle workspace root."""

    files = [child for child in root.rglob("*") if child.is_file()]
    return bundle_fingerprint(files, root)


def fingerprint_bundle_source(path: str | Path) -> str | None:
    """Return the current logical bundle fingerprint for *path*, or ``None``.

    This is the authoritative lightweight current-bundle identity that mirrors
    ``BundleValidationResult.fingerprint``: it opens the bundle workspace
    (handling both directory and ``.zip`` inputs via :func:`open_bundle`) and
    fingerprints the logical bundle files with :func:`bundle_fingerprint`.

    Returns ``None`` when the fingerprint cannot be established
    (missing path, unreadable, :class:`BundleLoadError`, ``OSError``)
    so callers can fail closed.  An empty bundle returns the fingerprint
    of an empty file set (matching ordinary validation).

    The implementation intentionally follows the same file-discovery semantics
    as ordinary validation (``Path.rglob`` over the opened workspace).  If the
    filesystem silently hides an unreadable subdirectory, both validation and
    this helper observe the same visible subset — no stronger traversal
    guarantee is claimed than validation itself provides.
    """

    from traffictwin.ingestion.loader import BundleLoadError, open_bundle

    src = Path(path)
    try:
        if not src.exists():
            return None
    except OSError:
        return None
    try:
        with open_bundle(src) as workspace:
            return fingerprint_workspace(workspace.root)
    except (BundleLoadError, OSError):
        return None
