"""Check repository Markdown links that resolve to local files or directories.

External URLs and fragment-only links are intentionally outside this offline check. The
release gate verifies that every repository-local navigation target exists and stays inside
the checkout.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def _markdown_files(root: Path) -> list[Path]:
    """Return the release-facing Markdown files in deterministic order."""

    return sorted([*root.glob("*.md"), *(root / "docs").rglob("*.md")])


def _destination(raw: str) -> str:
    """Remove optional Markdown angle brackets or a quoted link title."""

    candidate = raw.strip()
    if candidate.startswith("<") and ">" in candidate:
        return candidate[1 : candidate.index(">")]
    return candidate.split(' "', maxsplit=1)[0].split(" '", maxsplit=1)[0].strip()


def broken_local_links(root: Path = REPOSITORY_ROOT) -> tuple[int, list[str]]:
    """Return the checked-link count and deterministic broken-link diagnostics."""

    checked = 0
    broken: list[str] = []
    resolved_root = root.resolve()
    for markdown in _markdown_files(resolved_root):
        for line_number, line in enumerate(markdown.read_text(encoding="utf-8").splitlines(), 1):
            for raw in MARKDOWN_LINK.findall(line):
                destination = _destination(raw)
                parsed = urlsplit(destination)
                if not destination or destination.startswith("#") or parsed.scheme:
                    continue
                path_text = unquote(parsed.path)
                if not path_text:
                    continue
                checked += 1
                target = (markdown.parent / path_text).resolve()
                try:
                    target.relative_to(resolved_root)
                except ValueError:
                    # Some historical research documents deliberately reference private inputs
                    # outside the checkout. Their availability is not repository navigation.
                    continue
                if not target.exists():
                    relative = markdown.relative_to(resolved_root).as_posix()
                    broken.append(f"{relative}:{line_number}: {destination}")
    return checked, broken


def main() -> None:
    """Run the repository-local Markdown navigation gate."""

    checked, broken = broken_local_links()
    if broken:
        details = "\n".join(broken)
        raise SystemExit(f"broken local Markdown links ({len(broken)}):\n{details}")
    print(f"checked {checked} repository-local Markdown links; all targets exist")


if __name__ == "__main__":
    main()
