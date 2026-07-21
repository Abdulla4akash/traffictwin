#!/usr/bin/env python3
"""Publish the permission-safe VEC-10 thin-interface acceptance record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from traffictwin.integration.vec_interface import (
    compare_vec_admissions,
    export_vec_admission,
    inspect_vec_artifact,
    inspect_vec_interface,
    load_scientific_admission,
    vec_interface_contract,
)


def verify(vec_repo: Path, tos_data_repo: Path, scientific_report: Path) -> dict[str, Any]:
    """Exercise all non-executing interface paths over accepted real evidence."""

    before = inspect_vec_interface(vec_repo, tos_data_repo)
    if not all(item.ready_for_exact_blob_access for item in before.repositories):
        raise RuntimeError("both audited repositories must be ready for exact blob access")
    report = load_scientific_admission(scientific_report)
    inspection = inspect_vec_artifact(scientific_report)
    comparison = compare_vec_admissions(report, report)
    if not comparison.comparable_metrics or any(
        item.variation_minus_baseline != 0 for item in comparison.comparable_metrics
    ):
        raise RuntimeError("self-comparison must contain exact zero scalar differences")
    exports = {name: export_vec_admission(report, name) for name in ("json", "csv", "markdown")}
    after = inspect_vec_interface(vec_repo, tos_data_repo)
    if after != before:
        raise RuntimeError("external repository state changed during VEC-10 verification")
    contract = vec_interface_contract()
    return {
        "schema_version": "1.0",
        "capability": "VEC-10",
        "status": "accepted",
        "contract_fingerprint": contract.fingerprint(),
        "snapshot": before.model_dump(mode="json"),
        "scientific_report_fingerprint": report.fingerprint(),
        "artifact_inspection": inspection.model_dump(mode="json"),
        "self_comparison": {
            "fingerprint": comparison.fingerprint(),
            "comparable_metric_count": len(comparison.comparable_metrics),
            "unavailable_or_incompatible_count": len(
                comparison.unavailable_or_incompatible_metrics
            ),
            "all_scalar_differences_zero": True,
            "causal_interpretation": False,
        },
        "exports": {
            name: {
                "sha256": hashlib.sha256(payload.encode()).hexdigest(),
                "size_bytes": len(payload.encode()),
            }
            for name, payload in sorted(exports.items())
        },
        "foreground_execution_delegates_to_accepted_vec07": True,
        "direct_launch": "conditional_on_request_specific_preflight",
        "persistent_async_queue": False,
        "external_source_unchanged": True,
        "private_paths_published": False,
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vec-repo", type=Path, required=True)
    parser.add_argument("--tos-data-repo", type=Path, required=True)
    parser.add_argument("--scientific-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = verify(args.vec_repo, args.tos_data_repo, args.scientific_report)
    _write(args.output, record)
    print(
        f"VEC-10 accepted: {record['self_comparison']['comparable_metric_count']} "
        "scalar metrics and all thin-interface operations verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
