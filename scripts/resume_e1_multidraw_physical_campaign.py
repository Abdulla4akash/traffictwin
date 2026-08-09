#!/usr/bin/env python3
"""Append-only serial executor for the remaining frozen E1 campaign cells.

The predeclared runner creates a fresh campaign root.  This controller is a
no-overwrite adapter for the accepted seed-1 checkpoint: it delegates every
scientific run and validation to the manifest-pinned runner, and permits only
fleet seeds 2--4 in the manifest order.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from scripts.analyze_e1_multidraw_physical_campaign import _file_evidence, _metrics
from scripts.compare_e1_seed_three_cap import build_seed_comparison
from scripts.run_e1_multidraw_physical_campaign import (
    _common_stream_check,
    _identity_preflight,
    _run_once,
    _validate_full,
    _validate_smoke_pair,
    sha256_file,
)

MANIFEST_SHA256 = "0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d"
FROZEN_RUNNER_SHA256 = "2e82f9d557dd584712e9ddf67f17bc10ee39cf2b786122333ad94032e1a53a09"
ACCEPTED_SEED1_INDEX_SHA256 = "f7b9cdbc7f74a465a06bf2f0f11e1792eb9b97b286669eb67280fbd4fad045df"
REMAINING_SEEDS = (2, 3, 4)
CAP_LABELS = ("0p75", "2p5", "40x")
EVENTS_NAME = "remaining_campaign_events_2026-08-08.jsonl"
STATUS_NAME = "remaining_campaign_status_2026-08-08.json"


def _json_new(path: Path, value: Any) -> None:  # noqa: ANN401
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _append_event(path: Path, value: dict[str, Any]) -> None:
    record = {"recorded_at_unix_s": time.time(), **value}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()


def _run_with_heartbeat(
    run: Callable[[], dict[str, Any]], *, label: str, interval_s: float = 45.0
) -> dict[str, Any]:
    stopped = threading.Event()
    started = time.monotonic()

    def heartbeat() -> None:
        while not stopped.wait(interval_s):
            elapsed = time.monotonic() - started
            print(f"HEARTBEAT {label} elapsed_s={elapsed:.1f}", flush=True)

    worker = threading.Thread(target=heartbeat, name="campaign-heartbeat", daemon=True)
    print(f"START {label}", flush=True)
    worker.start()
    try:
        result = run()
    finally:
        stopped.set()
        worker.join()
    elapsed = time.monotonic() - started
    print(f"FINISH {label} elapsed_s={elapsed:.1f}", flush=True)
    return result


def _require_authority(manifest: dict[str, Any], manifest_path: Path, traffic_twin: Path) -> None:
    if sha256_file(manifest_path) != MANIFEST_SHA256:
        raise ValueError("frozen campaign manifest SHA-256 mismatch")
    backend = manifest.get("backend_decision", {})
    if backend.get("selected_backend") != "macos_arm64_cpu_jax_0_4_30":
        raise ValueError("frozen macOS CPU backend is not selected")
    if backend.get("campaign_execution_allowed") is not True:
        raise ValueError("campaign execution is disabled by the manifest")
    if manifest["compute_plan"]["concurrency_limit"] != 1:
        raise ValueError("campaign concurrency must remain one")
    if tuple(manifest["seeds"]["new_full_fleet_seeds"]) != (1, 2, 3, 4):
        raise ValueError("manifest fleet-seed matrix differs from the frozen contract")
    if tuple(item["label"] for item in manifest["cap_grid"]) != CAP_LABELS:
        raise ValueError("manifest cap order differs from the frozen contract")
    if manifest["scope"]["smoke_steps"] != 10 or manifest["scope"]["full_steps"] != 3600:
        raise ValueError("manifest step counts differ from the frozen contract")
    runner_path = traffic_twin / manifest["execution"]["runner"]
    if sha256_file(runner_path) != FROZEN_RUNNER_SHA256:
        raise ValueError("manifest-pinned campaign runner identity mismatch")
    expected_order = [
        f"fleet_seed_{seed}/cap_{cap}" for seed in REMAINING_SEEDS for cap in CAP_LABELS
    ]
    observed_order = [
        item
        for item in manifest["execution"]["full_run_order"]
        if not item.startswith("fleet_seed_1/")
    ]
    if observed_order != expected_order:
        raise ValueError("remaining execution order differs from the frozen manifest")


def _require_accepted_seed1(output_root: Path) -> None:
    index = output_root / "evidence_checksums_seed1_complete.sha256"
    if not index.is_file() or sha256_file(index) != ACCEPTED_SEED1_INDEX_SHA256:
        raise ValueError("accepted seed-1 evidence index identity mismatch")
    for seed in REMAINING_SEEDS:
        target = output_root / f"fleet_seed_{seed}"
        if target.exists():
            raise FileExistsError(f"refusing to reuse or overwrite {target}")
    for control_file in (EVENTS_NAME, STATUS_NAME):
        target = output_root / control_file
        if target.exists():
            raise FileExistsError(f"refusing to reuse or overwrite {target}")


def _preflight(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    return _identity_preflight(
        manifest,
        traffic_twin=args.traffic_twin,
        vec_env=args.vec_env,
        tos_data=args.tos_data,
        python=args.python,
        adapter_root=args.adapter_root,
        output_parent=args.output_parent,
    )


def _require_preflight(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    destination: Path,
) -> dict[str, Any]:
    preflight = _preflight(args, manifest)
    _json_new(destination, preflight)
    if not preflight["passed"]:
        failed = sorted(name for name, passed in preflight["checks"].items() if not passed)
        raise RuntimeError(f"mandatory preflight failed: {failed}")
    return preflight


def _seed_evidence(seed_root: Path, logical_root: str) -> dict[str, Any]:
    files = {
        str(path.relative_to(seed_root)): {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(seed_root.rglob("*"))
        if path.is_file() and path.name != "seed_evidence_index.json"
    }
    return {
        "schema_version": "traffictwin.e1-seed-raw-evidence-index.v1",
        "raw_output_locator": f"{logical_root}/{seed_root.name}",
        "file_count": len(files),
        "files": files,
    }


def run_remaining(args: argparse.Namespace) -> int:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    _require_authority(manifest, args.manifest, args.traffic_twin)
    output_root = args.output_parent / manifest["output"]["directory_name"]
    if not output_root.is_dir():
        raise FileNotFoundError(f"accepted campaign root is unavailable: {output_root}")
    _require_accepted_seed1(output_root)

    events_path = output_root / EVENTS_NAME
    events_path.touch(exist_ok=False)
    completed: list[dict[str, Any]] = []
    _append_event(
        events_path,
        {
            "event": "remaining_campaign_authority_accepted",
            "manifest_sha256": MANIFEST_SHA256,
            "seeds": list(REMAINING_SEEDS),
            "caps": list(CAP_LABELS),
            "backend": "macos_arm64_cpu_jax_0_4_30",
            "concurrency": 1,
        },
    )
    try:
        _require_preflight(args, manifest, output_root / "remaining_campaign_preflight.json")
        for fleet_seed in REMAINING_SEEDS:
            smoke_records: list[dict[str, Any]] = []
            full_records: list[dict[str, Any]] = []
            seed_root = output_root / f"fleet_seed_{fleet_seed}"
            for cap_label in CAP_LABELS:
                cell_root = seed_root / f"cap_{cap_label}"
                if cell_root.exists():
                    raise FileExistsError(f"refusing to reuse or overwrite {cell_root}")
                cell_root.mkdir(parents=True, exist_ok=False)
                _append_event(
                    events_path,
                    {"event": "cell_started", "fleet_seed": fleet_seed, "cap": cap_label},
                )
                _require_preflight(args, manifest, cell_root / "pre_smoke_preflight.json")
                smoke_dirs = [cell_root / "smoke" / f"run_{repeat}" for repeat in (1, 2)]
                for repeat, run_dir in enumerate(smoke_dirs, start=1):
                    _run_with_heartbeat(
                        partial(
                            _run_once,
                            manifest,
                            python=args.python,
                            vec_env=args.vec_env,
                            tos_data=args.tos_data,
                            run_dir=run_dir,
                            fleet_seed=fleet_seed,
                            cap_label=cap_label,
                            max_steps=manifest["scope"]["smoke_steps"],
                        ),
                        label=f"seed={fleet_seed} cap={cap_label} smoke={repeat}",
                    )
                smoke = _validate_smoke_pair(
                    manifest,
                    run_1=smoke_dirs[0],
                    run_2=smoke_dirs[1],
                    fleet_seed=fleet_seed,
                    cap_label=cap_label,
                )
                _json_new(cell_root / "smoke_validation.json", smoke)
                if not smoke["passed"]:
                    raise RuntimeError(
                        f"repeated-smoke gate failed for seed {fleet_seed} cap {cap_label}"
                    )
                smoke_records.append({"run": smoke["runs"][0]})
                smoke_stream = _common_stream_check(smoke_records)
                _json_new(cell_root / "smoke_stream_check_through_cap.json", smoke_stream)
                if not smoke_stream["passed"]:
                    raise RuntimeError(
                        f"cross-cap smoke stream mismatch for seed {fleet_seed} cap {cap_label}"
                    )

                _require_preflight(args, manifest, cell_root / "pre_full_preflight.json")
                full_run_dir = cell_root / "full" / "run_1"
                _run_with_heartbeat(
                    partial(
                        _run_once,
                        manifest,
                        python=args.python,
                        vec_env=args.vec_env,
                        tos_data=args.tos_data,
                        run_dir=full_run_dir,
                        fleet_seed=fleet_seed,
                        cap_label=cap_label,
                        max_steps=manifest["scope"]["full_steps"],
                    ),
                    label=f"seed={fleet_seed} cap={cap_label} full=1",
                )
                full = _validate_full(
                    manifest,
                    run_dir=full_run_dir,
                    fleet_seed=fleet_seed,
                    cap_label=cap_label,
                )
                _json_new(cell_root / "full_validation.json", full)
                if not full["passed"]:
                    raise RuntimeError(
                        f"full validation failed for seed {fleet_seed} cap {cap_label}"
                    )
                _json_new(cell_root / "cell_metrics.json", _metrics(full_run_dir, full["run"]))
                _json_new(cell_root / "cell_evidence_index.json", _file_evidence(full_run_dir))
                full_records.append(full)
                full_stream = _common_stream_check(full_records)
                _json_new(cell_root / "full_stream_check_through_cap.json", full_stream)
                if not full_stream["passed"]:
                    raise RuntimeError(
                        f"cross-cap full stream mismatch for seed {fleet_seed} cap {cap_label}"
                    )
                completed.append({"fleet_seed": fleet_seed, "cap_label": cap_label})
                _append_event(
                    events_path,
                    {
                        "event": "cell_passed",
                        "fleet_seed": fleet_seed,
                        "cap": cap_label,
                        "full_validation_sha256": sha256_file(cell_root / "full_validation.json"),
                    },
                )

            _json_new(seed_root / "smoke_stream_check.json", _common_stream_check(smoke_records))
            _json_new(seed_root / "full_stream_check.json", _common_stream_check(full_records))
            validation, comparison = build_seed_comparison(
                args.manifest, seed_root, args.seed0_comparison
            )
            _json_new(seed_root / "within_seed_validation.json", validation)
            _json_new(seed_root / "within_seed_comparison.json", comparison)
            if not validation["passed"]:
                raise RuntimeError(f"within-seed comparison failed for fleet seed {fleet_seed}")
            _json_new(
                seed_root / "seed_evidence_index.json",
                _seed_evidence(seed_root, manifest["output"]["logical_locator"]),
            )
            _append_event(
                events_path,
                {
                    "event": "fleet_seed_passed",
                    "fleet_seed": fleet_seed,
                    "within_seed_validation_sha256": sha256_file(
                        seed_root / "within_seed_validation.json"
                    ),
                },
            )

        status = {
            "status": "all_remaining_authorised_cells_passed",
            "manifest_sha256": MANIFEST_SHA256,
            "completed_cells": completed,
            "planned_cells": len(REMAINING_SEEDS) * len(CAP_LABELS),
            "failed_cells": 0,
        }
        _json_new(output_root / STATUS_NAME, status)
        _append_event(events_path, {"event": "remaining_campaign_passed"})
        print(json.dumps(status, indent=2, sort_keys=True), flush=True)
        return 0
    except BaseException as error:
        status = {
            "status": "stopped_on_mandatory_gate",
            "manifest_sha256": MANIFEST_SHA256,
            "completed_cells": completed,
            "error_type": type(error).__name__,
            "error": str(error),
        }
        if not (output_root / STATUS_NAME).exists():
            _json_new(output_root / STATUS_NAME, status)
        _append_event(events_path, {"event": "remaining_campaign_stopped", **status})
        print(json.dumps(status, indent=2, sort_keys=True), flush=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--traffic-twin", required=True, type=Path)
    parser.add_argument("--vec-env", required=True, type=Path)
    parser.add_argument("--tos-data", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--adapter-root", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    parser.add_argument("--seed0-comparison", required=True, type=Path)
    return run_remaining(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
