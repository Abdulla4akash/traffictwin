"""Search and About services."""

from __future__ import annotations

import sys
from pathlib import Path

from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.registry_search import (
    RegistrySearchError,
    RegistrySearchResult,
    SearchCategory,
    search_registry,
)
from traffictwin.release.metadata import current_release_metadata
from traffictwin.synthetic.config import (
    SYNTHETIC_GENERATOR_VERSION,
)
from traffictwin.ui.services.models import AboutInfo, ServiceError


def search_for_ui(
    query: str,
    registry_path: str | Path,
    workspace_path: str | Path | None = None,
    *,
    categories: list[SearchCategory | str] | None = None,
    limit: int = 50,
) -> RegistrySearchResult | ServiceError:
    """Run bounded REP-05 search through the tested read-only library boundary."""

    try:
        return search_registry(
            registry_path,
            query,
            workspace_path=workspace_path,
            categories=categories,
            limit=limit,
        )
    except (OSError, RegistrySearchError) as exc:
        return ServiceError("Registry search could not be completed.", str(exc))


def about_info_for_ui() -> AboutInfo:
    """Return project metadata for the About page."""

    metadata = current_release_metadata()
    return AboutInfo(
        package_version=metadata.version,
        generator_version=SYNTHETIC_GENERATOR_VERSION,
        metric_version=MetricEngineConfig().metric_version,
        diagnostic_version="ruleset-1.3",
        provenance_version="1.0",
        python_version=sys.version.split()[0],
        licence=metadata.licence_status,
        commit_hash=_git_commit_hash(),
    )


def _git_commit_hash() -> str | None:
    git_marker = Path(".git")
    git_dir = _resolve_git_directory(git_marker)
    if git_dir is None:
        return None
    head = _read_git_text(git_dir / "HEAD")
    if head is None:
        return None
    if head.startswith("ref: "):
        ref_name = head.removeprefix("ref: ").strip()
        common_dir = _resolve_git_common_directory(git_dir)
        for root in dict.fromkeys((git_dir, common_dir)):
            value = _read_git_text(root / ref_name)
            if value:
                return value[:12]
        packed_refs = _read_git_text(common_dir / "packed-refs")
        if packed_refs is not None:
            suffix = f" {ref_name}"
            for line in packed_refs.splitlines():
                if not line.startswith(("#", "^")) and line.endswith(suffix):
                    return line.split(" ", maxsplit=1)[0][:12]
        return None
    return head[:12] if head else None


def _resolve_git_directory(marker: Path) -> Path | None:
    """Resolve a normal ``.git`` directory or a linked-worktree marker."""

    if marker.is_dir():
        return marker
    content = _read_git_text(marker)
    if content is None or not content.startswith("gitdir: "):
        return None
    candidate = Path(content.removeprefix("gitdir: ").strip())
    if not candidate.is_absolute():
        candidate = marker.parent / candidate
    return candidate.resolve() if candidate.is_dir() else None


def _resolve_git_common_directory(git_dir: Path) -> Path:
    """Return the shared Git directory for a linked worktree when present."""

    content = _read_git_text(git_dir / "commondir")
    if content is None:
        return git_dir
    candidate = Path(content)
    if not candidate.is_absolute():
        candidate = git_dir / candidate
    resolved = candidate.resolve()
    return resolved if resolved.is_dir() else git_dir


def _read_git_text(path: Path) -> str | None:
    """Read small Git metadata defensively for optional About-page display."""

    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
