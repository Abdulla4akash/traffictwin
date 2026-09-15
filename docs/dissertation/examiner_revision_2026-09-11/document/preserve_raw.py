"""Copy-only preservation of inventory-bound files; never claim remote sync."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
INVENTORY = HERE.parent / "joint_confirmation_2026-09-08/evidence/RAW_INVENTORY.json"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def verify(root: Path, records: list[dict[str, object]]) -> None:
    for item in records:
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe inventory path: {relative}")
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Symlink or escaped path refused: {relative}")
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Missing/size-mismatched file: {relative}")
        if digest(path) != item["sha256"]:
            raise ValueError(f"Hash mismatch: {relative}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--approval-reference",
        required=True,
        help="Owner's exact destination-specific approval record",
    )
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    if not args.approval_reference.strip():
        parser.error("A destination-specific approval record is required")
    if not source.is_dir():
        parser.error("Source is not accessible; no transfer attempted")
    if destination.exists() or destination.is_relative_to(source):
        parser.error("Destination must be new and outside the source")
    if not destination.parent.is_dir():
        parser.error("Destination parent must already exist and be approved")
    inventory = json.loads(INVENTORY.read_text())
    records = inventory["files"]
    needed = sum(item["bytes"] for item in records)
    if len(records) != 267 or needed != 8380562432:
        parser.error("Unexpected campaign inventory; inspect rather than silently substitute")
    if shutil.disk_usage(destination.parent).free < needed + 64 * 1024 * 1024:
        parser.error("Insufficient destination space")
    verify(source, records)
    destination.mkdir()
    for item in records:
        relative = Path(item["path"])
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with (source / relative).open("rb") as src, target.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
    verify(destination, records)
    receipt = {
        "source": str(source),
        "destination": str(destination),
        "approval_reference": args.approval_reference,
        "verified_utc": datetime.now(UTC).isoformat(),
        "files": len(records),
        "bytes": needed,
        "inventory_sha256": digest(INVENTORY),
        "source_deleted_or_modified": False,
        "destination_hashes_verified": True,
        "remote_retrieval_verified": False,
        "off_machine_backup_certified": False,
        "next": "Verify the destination with verify_results.py --raw-root, then retrieve and "
        "hash-check the remote copy before certifying off-machine preservation.",
    }
    destination.with_name(destination.name + ".copy-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
