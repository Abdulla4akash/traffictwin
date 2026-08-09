#!/usr/bin/env python3
"""Run and compare the predeclared Colab GPU backend smoke.

This script is intended to run inside an ephemeral Google Colab GPU runtime
after the permission-safe upload bundle has been extracted. It refuses CPU
fallback, validates two ten-step repeats, and compares them with the checked-in
macOS CPU E0 contract without authorising a full campaign.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from scripts.validate_e0_smoke import build_report, sha256_file
except ModuleNotFoundError:  # direct script execution
    from validate_e0_smoke import (  # type: ignore[no-redef,import-not-found]
        build_report,
        sha256_file,
    )


def _write_json(path: Path, value: Any) -> None:  # noqa: ANN401
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _array_hashes_equal(left: dict[str, Any], right: dict[str, Any]) -> dict[str, bool]:
    names = sorted(set(left) | set(right))
    return {name: left.get(name) == right.get(name) for name in names}


def _numeric_differences(
    cpu: Any,  # noqa: ANN401
    colab: Any,  # noqa: ANN401
    *,
    prefix: str = "",
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    if isinstance(cpu, dict) and isinstance(colab, dict):
        for key in sorted(set(cpu) | set(colab)):
            name = f"{prefix}.{key}" if prefix else key
            differences.extend(_numeric_differences(cpu.get(key), colab.get(key), prefix=name))
        return differences
    if (
        isinstance(cpu, (int, float))
        and not isinstance(cpu, bool)
        and isinstance(colab, (int, float))
        and not isinstance(colab, bool)
    ):
        cpu_value = float(cpu)
        colab_value = float(colab)
        absolute = colab_value - cpu_value
        relative = absolute / cpu_value if cpu_value != 0.0 else None
        if absolute != 0.0:
            differences.append(
                {
                    "field": prefix,
                    "cpu": cpu,
                    "colab": colab,
                    "colab_minus_cpu": absolute,
                    "relative_difference": relative,
                }
            )
        return differences
    if cpu != colab:
        differences.append({"field": prefix, "cpu": cpu, "colab": colab})
    return differences


def _adapter(adapter_source: Path, vec_jax_source: Path, runtime_home: Path) -> Path:
    adapter_root = runtime_home / "scratch" / "vec-offloading-jaxmarl-fullport"
    env_dir = adapter_root / "env"
    env_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(adapter_source, env_dir / "__init__.py")
    (env_dir / "vec_jax.py").symlink_to(vec_jax_source.resolve())
    return adapter_root


def _run_once(
    *,
    evaluator: Path,
    actor: Path,
    trace: Path,
    run_dir: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=False)
    argv = [
        sys.executable,
        str(evaluator),
        "--trace",
        str(trace),
        "--actor",
        str(actor),
        "--max-steps",
        "10",
        "--seed",
        "0",
        "--fleet",
        "uk2030",
        "--fleet-seed",
        "0",
        "--rsu-cap-per-veh",
        "2.5",
        "--lambda-arrival",
        "1.5",
        "--rsu-service-mult",
        "1.0",
        "--rsu-lb",
        "off",
        "--rsu-backhaul-ms",
        "0.0",
        "--substep-queue",
        "sequential",
        "--substep-queue-iters",
        "3",
        "--veh-queue",
        "conserved",
        "--rsu-cap-mode",
        "reject",
        "--k8s-scale",
        "off",
        "--out-json",
        str(run_dir / "summary.json"),
        "--per-step-out",
        str(run_dir / "per_step.npz"),
        "--per-task-out",
        str(run_dir / "per_task.npz"),
    ]
    _write_json(run_dir / "command.json", {"argv": argv, "environment": environment})
    process_environment = os.environ.copy()
    process_environment.update(environment)
    started = time.monotonic()
    with (run_dir / "stdout_stderr.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(  # noqa: S603 - predeclared evaluator argv
            argv,
            check=False,
            env=process_environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    runner_wall_s = time.monotonic() - started
    _write_json(
        run_dir / "runner_status.json",
        {"exit_code": result.returncode, "runner_wall_s": runner_wall_s},
    )
    if result.returncode != 0:
        raise RuntimeError(f"Colab evaluator exited {result.returncode}; retained {run_dir}")
    return {"argv": argv, "runner_wall_s": runner_wall_s}


def build_backend_report(
    manifest_path: Path,
    bundle_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)

    paths = manifest["bundle_paths"]
    evaluator = bundle_root / paths["evaluator"]
    actor = bundle_root / paths["actor"]
    trace = bundle_root / paths["trace"]
    vec_jax = bundle_root / paths["vec_jax"]
    adapter_initializer = bundle_root / paths["adapter_initializer"]
    cpu_validation_path = bundle_root / paths["cpu_validation"]
    expected_inputs = manifest["identities"]
    observed_inputs = {
        "evaluator_sha256": sha256_file(evaluator),
        "actor_sha256": sha256_file(actor),
        "trace_sha256": sha256_file(trace),
        "vec_jax_sha256": sha256_file(vec_jax),
        "adapter_initializer_sha256": sha256_file(adapter_initializer),
        "cpu_validation_sha256": sha256_file(cpu_validation_path),
    }
    identity_checks = {key: observed_inputs[key] == expected_inputs[key] for key in observed_inputs}

    required_packages = manifest["colab_environment"]["required_packages"]
    observed_packages = {name: _package_version(name) for name in required_packages}
    package_checks = {
        name: observed_packages[name] == version for name, version in required_packages.items()
    }

    nvidia_binary = shutil.which("nvidia-smi")
    nvidia = (
        subprocess.run(  # noqa: S603
            [
                nvidia_binary,
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if nvidia_binary is not None
        else None
    )
    os.environ.update(manifest["execution"]["environment_variables"])
    backend: str | None = None
    devices: list[Any] = []
    backend_probe_error: str | None = None
    if all(package_checks.values()):
        try:
            import jax  # noqa: PLC0415

            devices = jax.devices()
            backend = jax.default_backend()
        except Exception as error:  # noqa: BLE001 - retain backend-initialization failure evidence
            backend_probe_error = f"{type(error).__name__}: {error}"
    else:
        backend_probe_error = "not attempted because exact package identity failed"
    gpu_check = backend == "gpu" and bool(devices)
    backend_record = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "jax_backend": backend,
        "jax_devices": [str(device) for device in devices],
        "jax_device_kinds": [device.device_kind for device in devices],
        "jax_probe_error": backend_probe_error,
        "nvidia_smi": (
            nvidia.stdout.strip() if nvidia is not None and nvidia.returncode == 0 else None
        ),
        "packages": observed_packages,
    }
    preflight = {
        "passed": all(identity_checks.values()) and all(package_checks.values()) and gpu_check,
        "input_identity_checks": identity_checks,
        "package_identity_checks": package_checks,
        "gpu_genuine": gpu_check,
        "backend": backend_record,
    }
    _write_json(output_root / "colab_preflight.json", preflight)
    if not preflight["passed"]:
        return {
            "schema_version": "traffictwin.e1-colab-backend-smoke-report.v1",
            "manifest_id": manifest["manifest_id"],
            "manifest_sha256": sha256_file(manifest_path),
            "passed": False,
            "backend": backend_record,
            "input_identity": {
                "passed": all(identity_checks.values()),
                "checks": identity_checks,
                "observed": observed_inputs,
            },
            "package_identity": {
                "passed": all(package_checks.values()),
                "checks": package_checks,
            },
            "gpu_genuine": gpu_check,
            "smoke_started": False,
            "speed": None,
            "recommendation": "do_not_select_colab_gpu_preflight_failed",
            "campaign_launched": False,
            "backend_decision_requires_repository_update_before_full_run": True,
        }

    _adapter(adapter_initializer, vec_jax, Path.home())
    environment = dict(manifest["execution"]["environment_variables"])
    run_dirs = [output_root / f"run_{index}" for index in (1, 2)]
    runner_records = [
        _run_once(
            evaluator=evaluator,
            actor=actor,
            trace=trace,
            run_dir=run_dir,
            environment=environment,
        )
        for run_dir in run_dirs
    ]
    validation = build_report(manifest_path, run_dirs[0], run_dirs[1], actor, trace)
    _write_json(output_root / "colab_validation.json", validation)

    cpu_validation = json.loads(cpu_validation_path.read_text(encoding="utf-8"))
    cpu_run = cpu_validation["runs"][0]
    colab_run = validation["runs"][0]
    cpu_summary = cpu_run["scientific_summary"]
    colab_summary = colab_run["scientific_summary"]
    scientific_differences = _numeric_differences(cpu_summary, colab_summary)
    per_step_equality = _array_hashes_equal(
        cpu_run["array_sha256"]["per_step"], colab_run["array_sha256"]["per_step"]
    )
    per_task_equality = _array_hashes_equal(
        cpu_run["array_sha256"]["per_task"], colab_run["array_sha256"]["per_task"]
    )
    task_stream_identity = {name: per_task_equality[name] for name in ("task_active", "task_type")}
    count_fields = manifest["comparison_contract"]["exact_count_fields"]
    count_equality = {field: cpu_summary[field] == colab_summary[field] for field in count_fields}

    cpu_wall_values = manifest["macos_cpu_baseline"]["evaluator_wall_s"]
    colab_wall_values = [float(run["scientific_summary"]["wall_s"]) for run in validation["runs"]]
    cpu_median = statistics.median(cpu_wall_values)
    colab_median = statistics.median(colab_wall_values)
    speedup = cpu_median / colab_median
    threshold = manifest["speed_decision"]["minimum_material_speedup"]
    materially_faster = speedup >= threshold
    estimated_hours = manifest["speed_decision"]["macos_projected_campaign_hours"] / speedup
    repeat_passed = validation["repeat"]["passed"]
    all_valid = (
        all(identity_checks.values())
        and all(package_checks.values())
        and gpu_check
        and validation["passed"]
        and repeat_passed
        and all(task_stream_identity.values())
        and all(count_equality.values())
    )
    recommendation = (
        "select_colab_gpu_and_rerun_seed0_on_colab"
        if all_valid and materially_faster
        else "do_not_select_colab_gpu_from_this_smoke"
    )
    return {
        "schema_version": "traffictwin.e1-colab-backend-smoke-report.v1",
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "passed": all_valid,
        "backend": backend_record,
        "input_identity": {
            "passed": all(identity_checks.values()),
            "checks": identity_checks,
            "observed": observed_inputs,
        },
        "package_identity": {
            "passed": all(package_checks.values()),
            "checks": package_checks,
        },
        "gpu_genuine": gpu_check,
        "colab_validation": validation,
        "runner_wall_s": [record["runner_wall_s"] for record in runner_records],
        "cross_backend_comparison": {
            "task_stream_identity": task_stream_identity,
            "exact_count_equality": count_equality,
            "scientific_summary_exact": cpu_summary == colab_summary,
            "scientific_differences": scientific_differences,
            "per_step_array_sha256_equal": per_step_equality,
            "per_task_array_sha256_equal": per_task_equality,
            "all_instrumentation_arrays_exact": all(per_step_equality.values())
            and all(per_task_equality.values()),
        },
        "speed": {
            "macos_cpu_evaluator_wall_s": cpu_wall_values,
            "colab_gpu_evaluator_wall_s": colab_wall_values,
            "macos_cpu_median_wall_s": cpu_median,
            "colab_gpu_median_wall_s": colab_median,
            "speedup_cpu_over_colab": speedup,
            "minimum_material_speedup": threshold,
            "materially_faster": materially_faster,
            "estimated_12_cell_campaign_hours_from_smoke_ratio": estimated_hours,
            "estimate_limitation": (
                "A ten-step run is JIT/startup dominated; this extrapolation is a planning "
                "estimate, not a measured full-hour Colab runtime."
            ),
        },
        "recommendation": recommendation,
        "campaign_launched": False,
        "backend_decision_requires_repository_update_before_full_run": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--bundle-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    report = build_backend_report(args.manifest, args.bundle_root, args.output_root)
    _write_json(args.output_root / "colab_backend_smoke_report.json", report)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "recommendation": report["recommendation"],
                "speed": report.get("speed"),
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
