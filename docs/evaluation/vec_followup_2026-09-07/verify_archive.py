"""Read-only checks of the private archive; never launches an evaluator."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-local-arrays", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    inventory = json.loads((root / "ARCHIVE_INVENTORY.json").read_text())
    checked = {"git": 0, "local_npz": 0, "ledger": 0}
    failures = []
    for entry in inventory["files"]:
        if entry["storage"] == "local_npz" and not args.check_local_arrays:
            continue
        path = (root / entry["path"] if entry["storage"] == "git"
                else Path(entry["source_path"]))
        if (not path.is_file() or path.stat().st_size != entry["bytes"]
                or sha256(path) != entry["sha256"]):
            failures.append(str(path))
        checked[entry["storage"]] += 1
    for line in (root / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = root / name
        if not path.is_file() or sha256(path) != expected:
            failures.append(str(path))
        checked["ledger"] += 1
    print(json.dumps({"status": "failed" if failures else "passed",
                      "checked": checked, "failures": failures}, indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
