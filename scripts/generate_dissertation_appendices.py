"""Generate the dissertation's appendix payload from machine-readable sources.

Two appendices the write-up needs verbatim and should never be retyped by hand:

* **Appendix A — capability catalogue.** Every adapter capability id and its
  three-valued declared support state, read through the public
  :mod:`traffictwin.config.capabilities` API, beside the complete Architecture
  Decision Record register parsed from the committed `docs/decisions/index.md`
  table.
* **Appendix B — software versions and parameters.** The project's declared
  dependency constraints and pinned tool versions from `pyproject.toml`, and the
  resolved versions the environment actually installs from `uv.lock`.

**A join this generator refuses to invent.** The feature brief asks for a
capability table carrying `family` and `ADR refs`. Neither exists in
machine-readable form: `CapabilitySet` declares no family taxonomy, and no
per-capability ADR mapping is recorded anywhere in the repository. Grouping the
capabilities by eye, or guessing which ADR governs which capability, would put
fabricated structure into a dissertation appendix. So Appendix A emits the two
registers it can source honestly, side by side, and states in the document that
the join is unavailable and why. If the owner wants the join, the right fix is to
record it in the manifest — not to have a generator guess it.

Deterministic by construction: no timestamps, no environment paths, every
collection sorted. Re-running on an unchanged tree rewrites identical bytes, so a
regenerated appendix never shows up as spurious churn in a commit.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from traffictwin.config.capabilities import (
    CapabilityManifest,
    default_export_import_manifest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "dissertation_appendices"

CAPABILITY_APPENDIX = "appendix_a_capability_catalogue.md"
VERSION_APPENDIX = "appendix_b_software_versions.md"

#: `| [ADR-001](file.md) | Title | status |`
_ADR_ROW = re.compile(
    r"^\|\s*\[(?P<id>ADR-\d+)\]\((?P<href>[^)]+)\)\s*\|\s*(?P<title>[^|]+?)\s*\|\s*"
    r"(?P<status>[^|]+?)\s*\|\s*$"
)


class AppendixGenerationError(RuntimeError):
    """Raised when a required machine-readable source is missing or unreadable."""


@dataclass(frozen=True)
class AdrEntry:
    """One row of the committed ADR register."""

    adr_id: str
    title: str
    status: str
    href: str


def main(argv: list[str] | None = None) -> int:
    """Write both appendices and report where they landed."""

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory the appendix markdown is written to.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root holding pyproject.toml, uv.lock, and docs/.",
    )
    arguments = parser.parse_args(argv)
    written = generate_appendices(arguments.repo_root, arguments.output_dir)
    for path in written:
        print(f"wrote {path}")
    return 0


def generate_appendices(repo_root: Path, output_dir: Path) -> list[Path]:
    """Render both appendices into ``output_dir`` and return the paths written."""

    output_dir.mkdir(parents=True, exist_ok=True)
    capability_path = output_dir / CAPABILITY_APPENDIX
    version_path = output_dir / VERSION_APPENDIX
    capability_path.write_text(
        render_capability_appendix(default_export_import_manifest(), read_adr_register(repo_root)),
        encoding="utf-8",
    )
    version_path.write_text(
        render_version_appendix(read_pyproject(repo_root), read_lockfile(repo_root)),
        encoding="utf-8",
    )
    return [capability_path, version_path]


def read_adr_register(repo_root: Path) -> list[AdrEntry]:
    """Parse the committed ADR index table into sorted entries."""

    index = repo_root / "docs" / "decisions" / "index.md"
    if not index.is_file():
        raise AppendixGenerationError(f"ADR register not found at {index}")
    entries = []
    for line in index.read_text(encoding="utf-8").splitlines():
        match = _ADR_ROW.match(line)
        if match is None:
            continue
        entries.append(
            AdrEntry(
                adr_id=match.group("id"),
                title=match.group("title"),
                status=match.group("status"),
                href=match.group("href"),
            )
        )
    if not entries:
        raise AppendixGenerationError(f"no ADR rows parsed from {index}")
    return sorted(entries, key=lambda entry: entry.adr_id)


def read_pyproject(repo_root: Path) -> dict[str, object]:
    """Return the parsed ``pyproject.toml``."""

    return _read_toml(repo_root / "pyproject.toml")


def read_lockfile(repo_root: Path) -> dict[str, object]:
    """Return the parsed ``uv.lock``."""

    return _read_toml(repo_root / "uv.lock")


def _read_toml(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise AppendixGenerationError(f"required source not found at {path}")
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise AppendixGenerationError(f"{path} is not readable TOML: {exc}") from exc


def render_capability_appendix(manifest: CapabilityManifest, adrs: list[AdrEntry]) -> str:
    """Render Appendix A from the capability manifest and the ADR register."""

    supports = manifest.supports
    lines = [
        "# Appendix A — Capability catalogue and decision register",
        "",
        "Generated by `scripts/generate_dissertation_appendices.py`. Do not edit by "
        "hand; re-run the generator instead.",
        "",
        "## A.1 Adapter capability catalogue",
        "",
        f"Declared support states for adapter `{manifest.adapter}`, read through the "
        "public capability-manifest API. `unknown` is a real, distinct state: it means "
        "the capability has not been established either way, and it is never collapsed "
        "into `false`.",
        "",
        "| Capability id | Declared support |",
        "|---|---|",
    ]
    for field_name in sorted(type(supports).model_fields):
        support = getattr(supports, field_name)
        lines.append(f"| `{field_name}` | `{support.value}` |")
    lines += [
        "",
        f"Total capabilities: {len(type(supports).model_fields)}.",
        "",
        "### A.1.1 Fields this table deliberately omits",
        "",
        "A capability *family* grouping and a per-capability *ADR reference* are not "
        "recorded in machine-readable form anywhere in the repository: the capability "
        "set declares no family taxonomy, and no capability-to-ADR mapping exists. "
        "Rather than group the rows by eye or guess which decision governs which "
        "capability, this appendix reports the two registers separately and states the "
        "gap. Producing the join requires recording it in the manifest first.",
        "",
        "## A.2 Architecture decision register",
        "",
        "Parsed from the committed `docs/decisions/index.md` table, sorted by ADR identifier.",
        "",
        "| ADR | Title | Status |",
        "|---|---|---|",
    ]
    for entry in adrs:
        lines.append(f"| `{entry.adr_id}` | {entry.title} | {entry.status} |")
    lines += ["", f"Total decision records: {len(adrs)}.", ""]
    return "\n".join(lines)


def render_version_appendix(pyproject: dict[str, object], lockfile: dict[str, object]) -> str:
    """Render Appendix B from the project metadata and the resolved lockfile."""

    project = _mapping(pyproject.get("project"))
    optional = _mapping(project.get("optional-dependencies"))
    lines = [
        "# Appendix B — Software versions and parameters",
        "",
        "Generated by `scripts/generate_dissertation_appendices.py`. Do not edit by "
        "hand; re-run the generator instead.",
        "",
        "## B.1 Project",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Name | `{project.get('name', 'unavailable')}` |",
        f"| Version | `{project.get('version', 'unavailable')}` |",
        f"| Requires Python | `{project.get('requires-python', 'unavailable')}` |",
        "",
        "## B.2 Declared dependency constraints",
        "",
        "The constraints the project declares, exactly as written in `pyproject.toml`. "
        "Pinned entries (`==`) are recorded tool versions that reproduction depends on.",
        "",
        "| Group | Requirement |",
        "|---|---|",
    ]
    for requirement in _string_list(project.get("dependencies")):
        lines.append(f"| `runtime` | `{requirement}` |")
    for group in sorted(optional):
        for requirement in _string_list(optional[group]):
            lines.append(f"| `{group}` | `{requirement}` |")
    packages = _resolved_packages(lockfile)
    lines += [
        "",
        "## B.3 Resolved environment versions",
        "",
        "The exact versions `uv.lock` resolves, which is what an execution actually runs against.",
        "",
        "| Package | Resolved version |",
        "|---|---|",
    ]
    for name, version in packages:
        lines.append(f"| `{name}` | `{version}` |")
    lines += ["", f"Total locked packages: {len(packages)}.", ""]
    return "\n".join(lines)


def _resolved_packages(lockfile: dict[str, object]) -> list[tuple[str, str]]:
    entries = lockfile.get("package")
    if not isinstance(entries, list):
        return []
    resolved: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        version = entry.get("version")
        if isinstance(name, str) and isinstance(version, str):
            resolved.append((name, version))
    return sorted(resolved)


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


if __name__ == "__main__":
    sys.exit(main())
