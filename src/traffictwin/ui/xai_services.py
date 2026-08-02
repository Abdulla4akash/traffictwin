"""Fixed-source read-only service for the synthetic XAI Decision Audit page."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.platform.xai_instrumentation import (
    XaiAuditBundle,
    build_synthetic_xai_audit_bundle,
    iter_bundle_text,
)

SOURCE_BASE = "https://github.com/Abdulla4akash/traffictwin/blob/main/"
RESEARCH_DIRECTIONS_REF = "docs/research_directions_v2.md"
PRODUCER_CITATION_REF = "docs/producer_citation_requirements.md"
_MAX_SOURCE_BYTES = 2_000_000
_PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "\\Users\\",
    "password",
    "credential",
    "api_key",
    "participant_id",
    "vehicle_id",
    "task_id",
)


class XaiConsoleError(RuntimeError):
    pass


class ConsoleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class XaiSourceLink(ConsoleModel):
    label: str
    url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    binding: str


class XaiConsole(ConsoleModel):
    bundle: XaiAuditBundle
    source_links: tuple[XaiSourceLink, ...]
    read_only: bool = True
    external_requests: bool = False
    creates_evidence: bool = False


def _read_fixed_source(repository_root: Path, relative: str) -> tuple[bytes, str]:
    root = repository_root.resolve()
    target = repository_root / relative
    if target.is_symlink() or not target.is_file():
        raise XaiConsoleError("SOURCE_UNAVAILABLE")
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise XaiConsoleError("SOURCE_OUTSIDE_REPOSITORY") from error
    size = resolved.stat().st_size
    if size <= 0 or size > _MAX_SOURCE_BYTES:
        raise XaiConsoleError("SOURCE_SIZE_REFUSED")
    content = resolved.read_bytes()
    return content, hashlib.sha256(content).hexdigest()


def _screen_console(console: XaiConsole) -> None:
    text = " ".join(iter_bundle_text(console.bundle))
    text += " " + " ".join(link.url for link in console.source_links)
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in _PRIVATE_MARKERS):
        raise XaiConsoleError("PRIVATE_CONTENT_REFUSED")


def load_xai_console(repository_root: Path) -> XaiConsole:
    """Load two exact repository sources and build one immutable synthetic fixture."""

    _, research_digest = _read_fixed_source(repository_root, RESEARCH_DIRECTIONS_REF)
    _, citation_digest = _read_fixed_source(repository_root, PRODUCER_CITATION_REF)
    bundle = build_synthetic_xai_audit_bundle(
        research_directions_digest=research_digest,
        producer_citation_digest=citation_digest,
    )
    console = XaiConsole(
        bundle=bundle,
        source_links=(
            XaiSourceLink(
                label="Future Research Directions v2",
                url=f"{SOURCE_BASE}{RESEARCH_DIRECTIONS_REF}",
                sha256=research_digest,
                binding="exact repository bytes; project context only",
            ),
            XaiSourceLink(
                label="Producer citation requirements",
                url=f"{SOURCE_BASE}{PRODUCER_CITATION_REF}",
                sha256=citation_digest,
                binding="exact repository bytes; provenance contract only",
            ),
        ),
    )
    _screen_console(console)
    return console
