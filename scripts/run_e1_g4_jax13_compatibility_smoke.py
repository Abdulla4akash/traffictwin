#!/usr/bin/env python3
"""Run the predeclared G4 JAX/CUDA-13 compatibility smoke.

The runner permits only a primitive compilation gate followed by two serial
ten-step evaluator processes. It cannot launch a full E1 campaign cell.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

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


def _run_command(argv: list[str]) -> dict[str, Any]:
    result = subprocess.run(  # noqa: S603 - fixed hardware-probe argv
        argv,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "argv": argv,
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _hardware_probe(allocation_hardware: str) -> tuple[dict[str, Any], Any]:
    nvidia_binary = shutil.which("nvidia-smi")
    if nvidia_binary is None:
        raise RuntimeError("nvidia-smi is unavailable")
    nvidia_query = _run_command(
        [
            nvidia_binary,
            "--query-gpu=name,compute_cap,driver_version,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    nvidia_full = _run_command([nvidia_binary])
    nvcc_binary = shutil.which("nvcc")
    nvcc = _run_command([nvcc_binary, "--version"]) if nvcc_binary else None

    import jax  # noqa: PLC0415

    devices = jax.devices()
    backend = jax.default_backend()
    try:
        platform_version = jax.extend.backend.get_backend().platform_version
    except (AttributeError, RuntimeError):
        platform_version = None
    record = {
        "requested_accelerator": "G4",
        "allocation_status_hardware": allocation_hardware,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "jax_backend": backend,
        "jax_devices": [str(device) for device in devices],
        "jax_device_kinds": [device.device_kind for device in devices],
        "jax_platform_version": platform_version,
        "nvidia_query": nvidia_query,
        "nvidia_smi": nvidia_full,
        "nvcc": nvcc,
    }
    genuine = allocation_hardware == "G4" and backend == "gpu" and bool(devices)
    if not genuine:
        raise RuntimeError("runtime is not the requested genuine G4 JAX GPU allocation")
    return record, jax


def _primitive_gate(jax: Any) -> dict[str, Any]:  # noqa: ANN401
    import jax.numpy as jnp  # type: ignore[import-not-found]  # noqa: PLC0415

    started = time.monotonic()
    key = jax.random.PRNGKey(0)
    key.block_until_ready()
    prng_wall_s = time.monotonic() - started

    started = time.monotonic()
    value = jax.device_put(jnp.arange(4, dtype=jnp.float32))
    value.block_until_ready()
    array_wall_s = time.monotonic() - started

    operation = jax.jit(lambda item: item * 2.0 + 1.0)
    started = time.monotonic()
    first = operation(value)
    first.block_until_ready()
    first_jit_wall_s = time.monotonic() - started
    started = time.monotonic()
    second = operation(value)
    second.block_until_ready()
    warmed_jit_wall_s = time.monotonic() - started

    output = np.asarray(second).tolist()
    devices = sorted(str(device) for device in second.devices())
    passed = output == [1.0, 3.0, 5.0, 7.0] and bool(devices)
    return {
        "passed": passed,
        "prng_key": np.asarray(key).tolist(),
        "output": output,
        "output_devices": devices,
        "timing_s": {
            "prng_key": prng_wall_s,
            "small_array": array_wall_s,
            "first_jit_compile_and_execute": first_jit_wall_s,
            "warmed_jit_execute": warmed_jit_wall_s,
        },
        "synchronized": True,
    }


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
    status = {"exit_code": result.returncode, "runner_wall_s": runner_wall_s}
    _write_json(run_dir / "runner_status.json", status)
    return status


def _array_sha256(value: np.ndarray) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii"))
    digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def _compare_array(cpu: np.ndarray, g4: np.ndarray, *, rtol: float, atol: float) -> dict[str, Any]:
    shape_equal = cpu.shape == g4.shape
    dtype_equal = cpu.dtype == g4.dtype
    if not shape_equal:
        return {
            "shape_equal": False,
            "dtype_equal": dtype_equal,
            "cpu_shape": list(cpu.shape),
            "g4_shape": list(g4.shape),
            "exact": False,
            "allclose": False,
        }
    exact = dtype_equal and np.array_equal(cpu, g4, equal_nan=False)
    numeric = np.issubdtype(cpu.dtype, np.number) and np.issubdtype(g4.dtype, np.number)
    allclose = exact
    differing = int(np.count_nonzero(cpu != g4))
    max_absolute_difference: float | None = None
    max_relative_difference: float | None = None
    if numeric:
        left: Any = cpu.astype(np.float64, copy=False)
        right: Any = g4.astype(np.float64, copy=False)
        allclose = bool(np.allclose(left, right, rtol=rtol, atol=atol, equal_nan=False))
        absolute = np.abs(right - left)
        max_absolute_difference = float(absolute.max(initial=0.0))
        denominator = np.abs(left)
        relative = np.divide(
            absolute,
            denominator,
            out=np.zeros_like(absolute),
            where=denominator != 0.0,
        )
        max_relative_difference = float(relative.max(initial=0.0))
    return {
        "shape_equal": shape_equal,
        "dtype_equal": dtype_equal,
        "cpu_shape": list(cpu.shape),
        "g4_shape": list(g4.shape),
        "cpu_dtype": str(cpu.dtype),
        "g4_dtype": str(g4.dtype),
        "cpu_sha256": _array_sha256(cpu),
        "g4_sha256": _array_sha256(g4),
        "exact": exact,
        "allclose": allclose,
        "differing_elements": differing,
        "max_absolute_difference": max_absolute_difference,
        "max_relative_difference": max_relative_difference,
    }


def _compare_npz(
    cpu_path: Path,
    g4_path: Path,
    *,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    with np.load(cpu_path, allow_pickle=False) as source:
        cpu = {name: source[name] for name in source.files}
    with np.load(g4_path, allow_pickle=False) as source:
        g4 = {name: source[name] for name in source.files}
    names = sorted(set(cpu) | set(g4))
    arrays = {
        name: (
            _compare_array(cpu[name], g4[name], rtol=rtol, atol=atol)
            if name in cpu and name in g4
            else {"present_in_cpu": name in cpu, "present_in_g4": name in g4, "exact": False}
        )
        for name in names
    }
    return {"same_array_names": set(cpu) == set(g4), "arrays": arrays}


def _scientific_close(
    cpu: Any,  # noqa: ANN401
    g4: Any,  # noqa: ANN401
    *,
    rtol: float,
    atol: float,
    field: str = "",
) -> tuple[bool, list[dict[str, Any]]]:
    if isinstance(cpu, dict) and isinstance(g4, dict):
        differences: list[dict[str, Any]] = []
        passed = set(cpu) == set(g4)
        for key in sorted(set(cpu) | set(g4)):
            child = f"{field}.{key}" if field else key
            child_passed, child_differences = _scientific_close(
                cpu.get(key), g4.get(key), rtol=rtol, atol=atol, field=child
            )
            passed = passed and child_passed
            differences.extend(child_differences)
        return passed, differences
    if isinstance(cpu, list) and isinstance(g4, list):
        if len(cpu) != len(g4):
            return False, [{"field": field, "cpu": cpu, "g4": g4}]
        differences = []
        passed = True
        for index, pair in enumerate(zip(cpu, g4, strict=True)):
            left: Any = pair[0]
            right: Any = pair[1]
            child_passed, child_differences = _scientific_close(
                left, right, rtol=rtol, atol=atol, field=f"{field}[{index}]"
            )
            passed = passed and child_passed
            differences.extend(child_differences)
        return passed, differences
    numeric = (
        isinstance(cpu, (int, float))
        and not isinstance(cpu, bool)
        and isinstance(g4, (int, float))
        and not isinstance(g4, bool)
    )
    if numeric:
        left = float(cpu)
        right = float(g4)
        close = math.isclose(left, right, rel_tol=rtol, abs_tol=atol)
        if left == right:
            return True, []
        return close, [
            {
                "field": field,
                "cpu": cpu,
                "g4": g4,
                "g4_minus_cpu": right - left,
                "relative_difference": (right - left) / left if left != 0.0 else None,
                "within_tolerance": close,
            }
        ]
    equal = cpu == g4
    return equal, [] if equal else [{"field": field, "cpu": cpu, "g4": g4}]


def _cross_backend_comparison(
    manifest: dict[str, Any],
    cpu_root: Path,
    g4_root: Path,
    validation: dict[str, Any],
) -> dict[str, Any]:
    tolerance = manifest["comparison_contract"]["floating_tolerance"]
    rtol = float(tolerance["rtol"])
    atol = float(tolerance["atol"])
    per_step = _compare_npz(
        cpu_root / "per_step.npz", g4_root / "per_step.npz", rtol=rtol, atol=atol
    )
    per_task = _compare_npz(
        cpu_root / "per_task.npz", g4_root / "per_task.npz", rtol=rtol, atol=atol
    )
    exact_fields = manifest["comparison_contract"]["exact_array_fields"]
    exact_checks = {
        f"{group}.{name}": (per_step if group == "per_step" else per_task)["arrays"][name]["exact"]
        for group, names in exact_fields.items()
        for name in names
    }
    all_array_tolerances = all(
        item.get("exact", False) if "allclose" not in item else item["allclose"]
        for group in (per_step, per_task)
        for item in group["arrays"].values()
    )
    cpu_validation = json.loads(
        (cpu_root.parent / "e0_validation_v1.json").read_text(encoding="utf-8")
    )
    cpu_summary = cpu_validation["runs"][0]["scientific_summary"]
    g4_summary = validation["runs"][0]["scientific_summary"]
    summary_close, summary_differences = _scientific_close(
        cpu_summary, g4_summary, rtol=rtol, atol=atol
    )
    exact_count_fields = manifest["comparison_contract"]["exact_count_fields"]
    exact_counts = {field: cpu_summary[field] == g4_summary[field] for field in exact_count_fields}
    cpu_deadline = cpu_validation["runs"][0]["observed"]["deadline_met"]
    g4_deadline = validation["runs"][0]["observed"]["deadline_met"]
    exact_counts["deadline_met"] = cpu_deadline == g4_deadline
    passed = (
        per_step["same_array_names"]
        and per_task["same_array_names"]
        and all(exact_checks.values())
        and all(exact_counts.values())
        and all_array_tolerances
        and summary_close
    )
    return {
        "passed": passed,
        "exact_array_checks": exact_checks,
        "exact_count_checks": exact_counts,
        "all_numeric_arrays_within_tolerance": all_array_tolerances,
        "scientific_summary_within_tolerance": summary_close,
        "scientific_summary_differences": summary_differences,
        "per_step": per_step,
        "per_task": per_task,
    }


def build_compatibility_report(
    manifest_path: Path,
    bundle_root: Path,
    output_root: Path,
    allocation_hardware: str,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "schema_version": "traffictwin.e1-g4-jax13-compatibility-smoke-result.v1",
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "passed": False,
        "campaign_launched": False,
        "full_steps_executed": 0,
    }

    paths = manifest["bundle_paths"]
    files = {
        "runner": bundle_root / paths["runner"],
        "evaluator": bundle_root / paths["evaluator"],
        "actor": bundle_root / paths["actor"],
        "trace": bundle_root / paths["trace"],
        "vec_jax": bundle_root / paths["vec_jax"],
        "adapter_initializer": bundle_root / paths["adapter_initializer"],
        "cpu_validation": bundle_root / paths["cpu_validation"],
        "cpu_summary": bundle_root / paths["cpu_summary"],
        "cpu_per_step": bundle_root / paths["cpu_per_step"],
        "cpu_per_task": bundle_root / paths["cpu_per_task"],
        "requirements_lock": bundle_root / paths["requirements_lock"],
    }
    identity_checks = {
        name: sha256_file(path) == manifest["identities"][f"{name}_sha256"]
        for name, path in files.items()
    }
    required_packages = manifest["software_intervention"]["resolved_packages"]
    observed_packages = {name: _package_version(name) for name in required_packages}
    package_checks = {
        name: observed_packages[name] == version for name, version in required_packages.items()
    }
    report["input_identity"] = {
        "passed": all(identity_checks.values()),
        "checks": identity_checks,
    }
    report["package_identity"] = {
        "passed": all(package_checks.values()),
        "checks": package_checks,
        "observed": observed_packages,
    }
    if not all(identity_checks.values()) or not all(package_checks.values()):
        report["status"] = "failed_preflight_identity_or_package"
        return report

    os.environ.update(manifest["execution"]["environment_variables"])
    try:
        hardware, jax = _hardware_probe(allocation_hardware)
        report["hardware"] = hardware
    except Exception as error:  # noqa: BLE001 - retain hardware initialization evidence
        report["status"] = "failed_g4_hardware_probe"
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        return report

    try:
        primitive = _primitive_gate(jax)
        report["primitive_gate"] = primitive
    except Exception as error:  # noqa: BLE001 - mandatory retained primitive failure
        report["status"] = "failed_primitive_compilation_gate"
        report["primitive_gate"] = {
            "passed": False,
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        return report
    if not primitive["passed"]:
        report["status"] = "failed_primitive_compilation_gate"
        return report

    _adapter(files["adapter_initializer"], files["vec_jax"], Path.home())
    environment = dict(manifest["execution"]["environment_variables"])
    run_dirs = [output_root / f"run_{index}" for index in (1, 2)]
    statuses = []
    for index, run_dir in enumerate(run_dirs, start=1):
        status = _run_once(
            evaluator=files["evaluator"],
            actor=files["actor"],
            trace=files["trace"],
            run_dir=run_dir,
            environment=environment,
        )
        statuses.append(status)
        if status["exit_code"] != 0:
            report["status"] = f"failed_evaluator_repeat_{index}"
            report["evaluator_statuses"] = statuses
            return report
    report["evaluator_statuses"] = statuses

    validation = build_report(
        manifest_path, run_dirs[0], run_dirs[1], files["actor"], files["trace"]
    )
    _write_json(output_root / "g4_repeat_validation.json", validation)
    report["g4_repeat_validation"] = validation
    cpu_root = files["cpu_summary"].parent
    comparison = _cross_backend_comparison(manifest, cpu_root, run_dirs[0], validation)
    _write_json(output_root / "cpu_g4_comparison.json", comparison)
    report["cpu_g4_comparison"] = comparison

    cpu_wall = [float(value) for value in manifest["macos_cpu_baseline"]["evaluator_wall_s"]]
    g4_wall = [
        float(run["observed"]["wall_s_excluded_from_repeat_verdict"]) for run in validation["runs"]
    ]
    cpu_median = statistics.median(cpu_wall)
    g4_median = statistics.median(g4_wall)
    speedup = cpu_median / g4_median
    threshold = float(manifest["performance_rule"]["minimum_material_speedup"])
    performance = {
        "macos_cpu_evaluator_wall_s": cpu_wall,
        "g4_evaluator_wall_s": g4_wall,
        "macos_cpu_median_wall_s": cpu_median,
        "g4_median_wall_s": g4_median,
        "speedup_cpu_over_g4": speedup,
        "minimum_material_speedup": threshold,
        "materially_faster": speedup >= threshold,
        "g4_15_cell_runtime_estimate_hours": (
            manifest["performance_rule"]["macos_per_cell_full_runtime_hours"] * 15 / speedup
        ),
        "estimate_limitation": (
            "The ten-step processes include fresh-process compilation; the 15-cell estimate is "
            "provisional until a separately authorised full-cell timing exists."
        ),
    }
    report["performance"] = performance
    scientifically_acceptable = (
        validation["passed"] and validation["repeat"]["passed"] and comparison["passed"]
    )
    report["scientifically_acceptable"] = scientifically_acceptable
    report["passed"] = scientifically_acceptable
    report["status"] = (
        "compatibility_smoke_passed" if scientifically_acceptable else "scientific_gate_failed"
    )
    report["recommendation"] = (
        "recommend_g4_for_separate_campaign_backend_freeze"
        if scientifically_acceptable and performance["materially_faster"]
        else "recommend_macos_cpu_no_campaign_launched"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--bundle-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--allocation-hardware", required=True, choices=("G4",))
    args = parser.parse_args()
    report = build_compatibility_report(
        args.manifest, args.bundle_root, args.output_root, args.allocation_hardware
    )
    _write_json(args.output_root / "g4_jax13_compatibility_report.json", report)
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "passed": report["passed"],
                "recommendation": report.get("recommendation"),
                "campaign_launched": report["campaign_launched"],
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
