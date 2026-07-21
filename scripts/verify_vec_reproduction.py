#!/usr/bin/env python3
"""Generate the permission-safe VEC-08 aggregate/hash acceptance report."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from pathlib import Path

from traffictwin.integration.vec_reproduction import (
    VecReproductionGrade,
    VecReproductionRequest,
    verify_vec_reproduction,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--tos-data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    """Verify two full runs and atomically write only an accepted portable report."""

    args = _parser().parse_args()
    receipt = args.observed / "execution_receipt.json"
    request = VecReproductionRequest(
        observed_receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest()
    )
    report = verify_vec_reproduction(
        args.observed,
        args.calibration,
        args.tos_data,
        request,
    )
    if report.grade not in {
        VecReproductionGrade.EXACT,
        VecReproductionGrade.NUMERICALLY_EQUIVALENT,
    }:
        raise SystemExit(f"refusing to publish VEC-08 grade {report.grade.value}")
    output = args.output.resolve(strict=False)
    if output.exists() and output.is_symlink():
        raise SystemExit("output must not be a symbolic link")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(report.model_dump_json(indent=2) + "\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        f"VEC-08 {report.grade.value}: {report.summary.exact} exact, "
        f"{report.summary.within_tolerance} within tolerance, "
        f"{report.summary.mismatch} mismatches"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
