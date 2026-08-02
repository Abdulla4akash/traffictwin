#!/usr/bin/env python3
"""Export or exercise the bounded benchmark execution package locally."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from traffictwin.platform.benchmark_execution import (
    BenchmarkExecutionError,
    build_default_execution_package,
    build_resource_plan,
    export_local_artifact,
    export_planned_job_pack,
    render_resource_plan,
    render_synthetic_receipts,
    run_synthetic_pack,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export the unsigned 2,400-job benchmark plan, estimate-only resource plan, or "
            "21-job synthetic engineering receipts. No command dispatches scientific work."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, default_name in (
        ("export-job-pack", "benchmark-planned-jobs.ndjson"),
        ("export-resource-plan", "benchmark-resource-plan.json"),
        ("synthetic-dry-run", "benchmark-synthetic-receipts.ndjson"),
    ):
        child = subparsers.add_parser(command)
        child.add_argument("--output-root", required=True, type=Path)
        child.add_argument("--filename", default=default_name)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        protocol, manifests, planned_pack, synthetic_pack = build_default_execution_package()
        if args.command == "export-job-pack":
            receipt = export_planned_job_pack(planned_pack, args.output_root, args.filename)
        elif args.command == "export-resource-plan":
            plan = build_resource_plan(protocol, planned_pack)
            receipt = export_local_artifact(
                args.output_root,
                args.filename,
                render_resource_plan(plan),
                artifact_kind="resource_plan",
                record_count=1,
            )
        else:
            receipts = run_synthetic_pack(protocol, manifests, synthetic_pack)
            receipt = export_local_artifact(
                args.output_root,
                args.filename,
                render_synthetic_receipts(receipts),
                artifact_kind="synthetic_receipts",
                record_count=len(receipts),
            )
    except BenchmarkExecutionError as error:
        print(json.dumps({"status": "refused", "code": error.code}, sort_keys=True))
        return 2
    print(receipt.model_dump_json())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
