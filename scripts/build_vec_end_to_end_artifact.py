#!/usr/bin/env python3
"""Build and record the deterministic offline-verifiable VEC-12 artifact."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from traffictwin.integration.vec_research import create_vec_end_to_end_archive


def _write_new_receipt(path: Path, payload: str) -> None:
    destination = path.absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"receipt already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o444)
        os.link(temporary, destination)
        temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    if args.receipt.absolute() == args.output.absolute():
        raise SystemExit("archive and receipt paths must differ")
    receipt = create_vec_end_to_end_archive(args.generated_root, args.output)
    try:
        _write_new_receipt(args.receipt, receipt.model_dump_json(indent=2) + "\n")
    except BaseException:
        args.output.unlink(missing_ok=True)
        raise
    print(
        f"VEC-12 accepted: {receipt.member_count} deterministic members, "
        f"archive sha256 {receipt.archive_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
