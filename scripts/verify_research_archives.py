"""Check frozen, compact research files without executing or importing their code.

The explicit manifest replaces Ruff checks only for the named historical packages.
Unexpected files are failures, so new maintained code cannot silently enter an
excluded tree. Python caches are not evidence and are ignored. This is a local
file-integrity check, not a raw-data audit, backup or scientific revalidation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path, PurePosixPath

MANIFEST = Path("docs/quality/immutable_research_archives_2026-09-09.json")


def _relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValueError(f"Non-canonical relative archive path: {value}")
    return path


def verify(root: Path, manifest_path: Path) -> dict[str, object]:
    """Return exact missing/changed/additional-file failures; never rewrite inputs."""
    root = root.resolve()
    manifest = json.loads(manifest_path.read_text())
    roots = manifest["roots"]
    records = manifest["files"]
    if manifest["schema_version"] != 1 or not roots or not records:
        raise ValueError("Unsupported or empty archive manifest")
    if len(set(roots)) != len(roots):
        raise ValueError("Duplicate archive roots")
    archive_paths = [_relative_path(name) for name in roots]
    for path in archive_paths:
        if len(path.parts) != 3 or path.parts[:2] not in (
            ("docs", "dissertation"),
            ("docs", "evaluation"),
        ):
            raise ValueError(f"Archive exclusions must name exact dated packages: {path}")
        if re.search(r"_2026-\d{2}-\d{2}$", path.name) is None:
            raise ValueError(f"Archive root is not a dated package: {path}")
    for name, record in records.items():
        path = _relative_path(name)
        if not any(path.is_relative_to(archive) for archive in archive_paths):
            raise ValueError(f"File outside declared archive roots: {name}")
        if record["bytes"] < 0 or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None:
            raise ValueError(f"Invalid integrity record: {name}")
    config = tomllib.loads((root / "pyproject.toml").read_text())
    exclusions = config["tool"]["ruff"].get("extend-exclude", [])
    failures = []
    if sorted(exclusions) != sorted(roots):
        failures.append("Ruff exclusions differ from the exact archive roots")
    actual: set[str] = set()
    for name in roots:
        directory = root / name
        if directory.is_symlink():
            failures.append(f"Symlink archive root: {name}")
            continue
        if not directory.is_dir():
            failures.append(f"Missing archive root: {name}")
            continue
        for path in directory.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                failures.append(f"Symlink inside archive: {relative}")
            elif "__pycache__" not in path.parts and path.name != ".DS_Store" and path.is_file():
                actual.add(relative)
    expected = set(records)
    failures.extend(f"Missing file: {name}" for name in sorted(expected - actual))
    failures.extend(f"Unexpected file: {name}" for name in sorted(actual - expected))
    checked = 0
    checked_bytes = 0
    for name in sorted(expected & actual):
        path = root / name
        # Reject a symlink at any parent boundary, including docs/ itself.
        if not path.resolve().is_relative_to(root) or any(
            parent.is_symlink() for parent in path.parents if parent != root
        ):
            failures.append(f"Non-local archive path: {name}")
            continue
        data = path.read_bytes()
        record = records[name]
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            failures.append(f"Changed file: {name}")
        checked += 1
        checked_bytes += len(data)
    return {
        "status": "failed" if failures else "passed",
        "baseline_commit": manifest["baseline_commit"],
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "archive_roots": len(roots),
        "checked_files": checked,
        "checked_bytes": checked_bytes,
        "failures": failures,
        "scope": "File integrity only; no code execution, raw-array analysis or backup",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = verify(args.root, args.root / MANIFEST)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
