#!/usr/bin/env python3
"""Validate public-repository structure, evidence checksums, JSON and privacy gates."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "README.md",
    "CITATION.cff",
    "LICENSE",
    "docs/WEEKLY_RESEARCH_PROGRESS.md",
    "docs/METHODOLOGY.md",
    "docs/PROVENANCE.md",
    "data/cumulative_experiment_summary.csv",
    "data/cumulative_primary_results.csv",
    "figures/research_timeline.png",
    "figures/research_timeline.pdf",
    "figures/e1_capacity_result.png",
    "figures/e2b_factorial.png",
    "figures/e2c_replication.png",
    "figures/e2d_direction_reversal.png",
    "figures/execution_balance_comparison.png",
}
PRIVATE_PATTERNS = {
    "absolute user path": re.compile("/" + "Users/" + "akashx" + "|" + "Anti" + "gravity" + "Test"),
    "GitHub classic token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "GitHub fine-grained token": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)|!\[[^\]]*\]\(([^)]+)\)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_required() -> int:
    missing = sorted(path for path in REQUIRED if not (ROOT / path).exists())
    if missing:
        raise AssertionError(f"Missing required files: {missing}")
    return len(REQUIRED)


def check_json() -> int:
    count = 0
    for path in ROOT.rglob("*.json"):
        with path.open(encoding="utf-8") as handle:
            json.load(handle)
        count += 1
    return count


def check_evidence_ledgers() -> tuple[int, int]:
    ledgers = 0
    members = 0
    for ledger in ROOT.glob("experiments/*/evidence/checksums.sha256"):
        ledgers += 1
        for line in ledger.read_text(encoding="utf-8").splitlines():
            expected, relative = line.split(maxsplit=1)
            relative = relative.lstrip("* ")
            path = ledger.parent / relative
            if sha256(path) != expected:
                raise AssertionError(f"Checksum mismatch: {path.relative_to(ROOT)}")
            members += 1
    if ledgers != 6:
        raise AssertionError(f"Expected 6 evidence ledgers, found {ledgers}")
    return ledgers, members


def check_privacy() -> int:
    checked = 0
    for path in ROOT.rglob("*"):
        excluded_directories = {".git", ".venv", ".ruff_cache", ".mypy_cache", ".pytest_cache"}
        if (
            not path.is_file()
            or excluded_directories.intersection(path.parts)
            or path.suffix.lower() in {".png", ".pdf"}
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in PRIVATE_PATTERNS.items():
            if pattern.search(text):
                raise AssertionError(f"{label} found in {path.relative_to(ROOT)}")
        checked += 1
    forbidden = [
        path
        for path in ROOT.rglob("*")
        if path.suffix.lower() in {".npz", ".npy"} and ".venv" not in path.parts
    ]
    if forbidden:
        raise AssertionError(f"Raw array files found: {forbidden}")
    return checked


def check_markdown_links() -> int:
    checked = 0
    for document in ROOT.rglob("*.md"):
        content = document.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(content):
            target = match.group(1) or match.group(2)
            target = target.split("#", maxsplit=1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (document.parent / target).resolve().exists():
                raise AssertionError(f"Broken link in {document.relative_to(ROOT)}: {target}")
            checked += 1
    return checked


def main() -> None:
    required = check_required()
    json_files = check_json()
    ledgers, members = check_evidence_ledgers()
    privacy_files = check_privacy()
    links = check_markdown_links()
    print(
        "PASS: publication validation "
        f"({required} required files, {json_files} JSON files, "
        f"{ledgers} ledgers/{members} members, {privacy_files} privacy-scanned files, "
        f"{links} local links)"
    )


if __name__ == "__main__":
    main()
