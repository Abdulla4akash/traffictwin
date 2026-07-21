"""Deterministic expected-versus-observed verification for the VEC-08 case."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import shutil
import subprocess
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

from traffictwin.integration.vec_reproduction.models import (
    LATENCY_STREAM_TOLERANCE,
    PINNED_EXPECTED_FILES,
    PINNED_TOS_DATA_COMMIT,
    SCALAR_TOLERANCE,
    VecComparisonStatus,
    VecNumericTolerance,
    VecRepeatRunEvidence,
    VecReproductionCheck,
    VecReproductionGrade,
    VecReproductionReport,
    VecReproductionRequest,
    VecReproductionSource,
    VecReproductionSummary,
)
from traffictwin.integration.vec_runner import VecExecutionReceipt, VecTerminalStatus

_EXPECTED_JSON = "instrumented/json/ukft_mappo_uk2030_we_fs0.json"
_EXPECTED_PERSTEP = "instrumented/perstep/ukft_mappo_uk2030_we_fs0_perstep.npz"
_EXPECTED_MASTER = "evals/eval_results_master.csv"
_OBSERVED_FILES = ("execution_receipt.json", "run.json", "per-step.npz", "per-task.npz")
_MASTER_FIELDS = (
    "actor",
    "obs_variant",
    "completion",
    "t1_completion",
    "t2_completion",
    "t3_completion",
    "avg_energy_j_per_task",
    "avg_latency_ms_per_task",
    "p_local",
    "p_v2i",
    "p_v2v",
    "fleet_ev_share",
    "T",
    "maxN",
    "trace",
)
_NUMERIC_MASTER_FIELDS = {
    "completion",
    "t1_completion",
    "t2_completion",
    "t3_completion",
    "avg_energy_j_per_task",
    "avg_latency_ms_per_task",
    "p_local",
    "p_v2i",
    "p_v2v",
    "fleet_ev_share",
    "T",
    "maxN",
}


class VecReproductionError(RuntimeError):
    """Raised when VEC-08 evidence cannot be safely admitted."""


def verify_vec_reproduction(
    observed_dir: str | Path,
    calibration_dir: str | Path,
    tos_data_repo: str | Path,
    request: VecReproductionRequest,
) -> VecReproductionReport:
    """Compare one completed VEC-07 result to exact pinned VEC-08 references."""

    observed_root = _safe_observed_directory(Path(observed_dir))
    observed_paths = {name: _safe_file(observed_root, name) for name in _OBSERVED_FILES}
    receipt_bytes = observed_paths["execution_receipt.json"].read_bytes()
    if _sha256(receipt_bytes) != request.observed_receipt_sha256:
        raise VecReproductionError("observed execution receipt SHA-256 does not match the request")
    try:
        receipt = VecExecutionReceipt.model_validate_json(receipt_bytes)
    except ValueError as exc:
        raise VecReproductionError("observed receipt is not a valid VEC-07 receipt") from exc
    _validate_runner_receipt(receipt, observed_paths)
    calibration_root = _safe_observed_directory(Path(calibration_dir))
    calibration_paths = {name: _safe_file(calibration_root, name) for name in _OBSERVED_FILES}
    calibration_receipt_bytes = calibration_paths["execution_receipt.json"].read_bytes()
    try:
        calibration_receipt = VecExecutionReceipt.model_validate_json(calibration_receipt_bytes)
    except ValueError as exc:
        raise VecReproductionError("calibration receipt is not a valid VEC-07 receipt") from exc
    _validate_runner_receipt(calibration_receipt, calibration_paths)
    repeat_run = _compare_repeat_runs(
        calibration_paths,
        observed_paths,
        calibration_receipt,
        receipt,
    )

    expected_blobs = _load_expected_blobs(Path(tos_data_repo))
    expected_sources = [
        VecReproductionSource(
            role="expected",
            path=path,
            sha256=_sha256(blob),
            size_bytes=len(blob),
            commit=PINNED_TOS_DATA_COMMIT,
        )
        for path, blob in sorted(expected_blobs.items())
    ]
    observed_sources = [
        VecReproductionSource(
            role="observed",
            path=name,
            sha256=_sha256(path.read_bytes()),
            size_bytes=path.stat().st_size,
        )
        for name, path in sorted(observed_paths.items())
    ]

    try:
        expected_json = json.loads(expected_blobs[_EXPECTED_JSON])
        observed_json = json.loads(observed_paths["run.json"].read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VecReproductionError("run JSON could not be safely parsed") from exc
    expected_master = _expected_master_row(expected_blobs[_EXPECTED_MASTER])
    checks = _compare_master_to_expected_json(expected_master, expected_json)
    checks.extend(_compare_run_json(expected_json, observed_json, receipt))
    checks.extend(
        _compare_perstep(
            expected_blobs[_EXPECTED_PERSTEP],
            observed_paths["per-step.npz"],
        )
    )
    checks.append(
        VecReproductionCheck(
            artifact="per-task.npz",
            field="expected reference",
            status=VecComparisonStatus.UNAVAILABLE,
            comparison="unavailable",
            element_count=0,
            note=(
                "The pinned package has no per-task artifact for this weekend reference case. "
                "VEC-07 validated the observed four-key schema, but VEC-08 does not compare values."
            ),
        )
    )

    summary = _summary(checks)
    grade = (
        VecReproductionGrade.DIVERGENT
        if summary.mismatch
        else VecReproductionGrade.NUMERICALLY_EQUIVALENT
        if summary.within_tolerance
        else VecReproductionGrade.EXACT
    )
    runtime_payload = receipt.runtime.model_dump(mode="json")
    runtime = {
        key: value
        for key, value in runtime_payload.items()
        if key
        in {
            "python",
            "numpy",
            "jax",
            "jaxlib",
            "jax_backend",
            "jax_device_count",
            "platform",
            "machine",
            "processor",
            "environment_sha256",
        }
    }
    return VecReproductionReport(
        grade=grade,
        request=request,
        request_fingerprint=request.fingerprint(),
        expected_sources=expected_sources,
        observed_sources=observed_sources,
        runner_receipt_fingerprint=receipt.fingerprint(),
        runtime=runtime,
        tolerance_calibration=(
            "Policy 1.0 was frozen from the first full controlled Apple-arm64 CPU calibration "
            "run before the acceptance repeat: every discrete/state output and final deadline, "
            "action, latency, and fleet aggregate matched exactly; only avg_energy_j_per_task "
            "(6.04e-8) and float32 per-step lat_sum (<=0.00390625 ms, <=3 ULP) drifted."
        ),
        repeat_run=repeat_run,
        checks=checks,
        summary=summary,
        interpretation_limits=[
            "This is one protocol-seed weekend case, not scenario-wide equivalence.",
            "The tolerance is calibrated and accepted only for the pinned JAX/JAXLIB 0.4.30 CPU "
            "method.",
            "wall_s is excluded because it is machine-dependent performance metadata.",
            "No expected per-task artifact exists for this case.",
            "The report supports VEC-08 only and does not expose product direct launch.",
        ],
    )


def _compare_repeat_runs(
    calibration_paths: dict[str, Path],
    acceptance_paths: dict[str, Path],
    calibration_receipt: VecExecutionReceipt,
    acceptance_receipt: VecExecutionReceipt,
) -> VecRepeatRunEvidence:
    calibration_controls = calibration_receipt.request.model_dump(mode="json")
    acceptance_controls = acceptance_receipt.request.model_dump(mode="json")
    calibration_controls.pop("run_id")
    acceptance_controls.pop("run_id")
    try:
        calibration_json = json.loads(calibration_paths["run.json"].read_text(encoding="utf-8"))
        acceptance_json = json.loads(acceptance_paths["run.json"].read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VecReproductionError("repeat run JSON could not be safely parsed") from exc
    calibration_json.pop("wall_s", None)
    acceptance_json.pop("wall_s", None)
    return VecRepeatRunEvidence(
        calibration_receipt_sha256=_sha256(
            calibration_paths["execution_receipt.json"].read_bytes()
        ),
        acceptance_receipt_sha256=_sha256(acceptance_paths["execution_receipt.json"].read_bytes()),
        same_execution_controls=calibration_controls == acceptance_controls,
        scientific_json_exact=calibration_json == acceptance_json,
        perstep_arrays_exact=_npz_arrays_exact(
            calibration_paths["per-step.npz"], acceptance_paths["per-step.npz"]
        ),
        pertask_arrays_exact=_npz_arrays_exact(
            calibration_paths["per-task.npz"], acceptance_paths["per-task.npz"]
        ),
    )


def _npz_arrays_exact(left_path: Path, right_path: Path) -> bool:
    np = _numpy()
    try:
        with (
            np.load(left_path, allow_pickle=False) as left,
            np.load(right_path, allow_pickle=False) as right,
        ):
            return set(left.files) == set(right.files) and all(
                bool(np.array_equal(left[key], right[key])) for key in left.files
            )
    except (OSError, ValueError) as exc:
        raise VecReproductionError(f"repeat NPZ could not be compared: {exc}") from exc


def _validate_runner_receipt(
    receipt: VecExecutionReceipt,
    paths: dict[str, Path],
) -> None:
    if receipt.status is not VecTerminalStatus.COMPLETED or not receipt.published:
        raise VecReproductionError("VEC-08 requires a completed published VEC-07 receipt")
    if receipt.external_repositories_modified or receipt.raw_inputs_modified:
        raise VecReproductionError("VEC-07 receipt does not prove source/input immutability")
    run = receipt.request
    expected_request = {
        "trace_sha256": "a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be",
        "actor_id": "ukfleettrain_mappo_model_c_17",
        "evaluator_seed": 0,
        "fleet": "uk2030",
        "fleet_seed": 0,
        "rsu_capacity_per_vehicle": 2.5,
        "max_steps": 32400,
    }
    observed_request = run.model_dump(mode="json")
    if any(observed_request[key] != value for key, value in expected_request.items()):
        raise VecReproductionError("VEC-07 request does not identify the approved VEC-08 case")
    inventory = {item.path: item for item in receipt.outputs}
    for receipt_path, file_name in (
        ("run.json", "run.json"),
        ("per-step.npz", "per-step.npz"),
        ("per-task.npz", "per-task.npz"),
    ):
        evidence = inventory.get(receipt_path)
        content = paths[file_name].read_bytes()
        if (
            evidence is None
            or evidence.sha256 != _sha256(content)
            or evidence.size_bytes != len(content)
        ):
            raise VecReproductionError(f"observed {file_name} does not match its VEC-07 receipt")


def _load_expected_blobs(repo: Path) -> dict[str, bytes]:
    if repo.is_symlink() or not repo.resolve().is_dir():
        raise VecReproductionError("tos-data must be a direct readable Git repository")
    git = shutil.which("git")
    if git is None:
        raise VecReproductionError("git is required to load exact expected blobs")
    resolved = repo.resolve()
    try:
        origin = _git_text(git, resolved, "rev-parse", "refs/remotes/origin/main").strip()
        dirty = _git_text(git, resolved, "status", "--porcelain=v1", "--untracked-files=all")
    except subprocess.SubprocessError as exc:
        raise VecReproductionError("could not inspect tos-data Git state") from exc
    if origin != PINNED_TOS_DATA_COMMIT or dirty:
        raise VecReproductionError("tos-data must be clean with the audited origin/main commit")
    blobs: dict[str, bytes] = {}
    for path, expected_hash in sorted(PINNED_EXPECTED_FILES.items()):
        blob = _git_bytes(git, resolved, "show", f"{PINNED_TOS_DATA_COMMIT}:{path}")
        if _sha256(blob) != expected_hash:
            raise VecReproductionError(f"expected Git blob hash mismatch: {path}")
        blobs[path] = blob
    return blobs


def _expected_master_row(content: bytes) -> dict[str, str]:
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise VecReproductionError("expected master CSV could not be parsed") from exc
    selected = [
        row
        for row in rows
        if row["campaign"] == "ukfleettrain_mappo"
        and row["cell"] == "we"
        and row["eval_fleet"] == "uk2030"
        and row["fleet_seed"] == "0"
    ]
    if len(selected) != 1 or selected[0].get("engine_version") != "v2_post_nrsus_fix":
        raise VecReproductionError("expected master CSV does not contain one approved engine row")
    return selected[0]


def _compare_master_to_expected_json(
    master: dict[str, str],
    expected: dict[str, Any],
) -> list[VecReproductionCheck]:
    mismatches: list[str] = []
    for field in _MASTER_FIELDS:
        observed_value: object = master[field]
        expected_value = expected[field]
        if field in _NUMERIC_MASTER_FIELDS:
            equal = float(str(observed_value)) == float(expected_value)
        else:
            equal = str(observed_value) == str(expected_value)
        if not equal:
            mismatches.append(field)
    return [
        VecReproductionCheck(
            artifact="expected sources",
            field="master row versus instrumented JSON",
            status=(VecComparisonStatus.EXACT if not mismatches else VecComparisonStatus.MISMATCH),
            comparison="exact",
            element_count=len(_MASTER_FIELDS),
            mismatch_count=len(mismatches),
            note=(
                "All source-provided scientific/provenance fields agree exactly."
                if not mismatches
                else "Mismatched fields: " + ", ".join(mismatches)
            ),
        )
    ]


def _compare_run_json(
    expected: dict[str, Any],
    observed: dict[str, Any],
    receipt: VecExecutionReceipt,
) -> list[VecReproductionCheck]:
    checks: list[VecReproductionCheck] = []
    expected_keys = set(expected)
    observed_keys = set(observed)
    checks.append(
        VecReproductionCheck(
            artifact="run.json",
            field="keys",
            status=(
                VecComparisonStatus.EXACT
                if expected_keys == observed_keys
                else VecComparisonStatus.MISMATCH
            ),
            comparison="exact",
            element_count=len(expected_keys | observed_keys),
            mismatch_count=len(expected_keys ^ observed_keys),
            note=(
                "Exact key set." if expected_keys == observed_keys else "Run JSON key set differs."
            ),
        )
    )
    for field in sorted(expected_keys & observed_keys):
        if field == "wall_s":
            checks.append(
                VecReproductionCheck(
                    artifact="run.json",
                    field=field,
                    status=VecComparisonStatus.EXCLUDED,
                    comparison="excluded",
                    expected=float(expected[field]),
                    observed=float(observed[field]),
                    note="Machine-dependent wall time is not a scientific endpoint.",
                )
            )
        elif field == "actor":
            expected_actor = str(expected[field])
            semantic_match = (
                receipt.request.actor_id == "ukfleettrain_mappo_model_c_17"
                and expected_actor
                == "mappo_modelc_17dim_ukfleet2030__envs128__lr3e-3__seed100_actor_params.npz"
                and str(observed[field]) == "actor.npz"
            )
            checks.append(
                VecReproductionCheck(
                    artifact="run.json",
                    field=field,
                    status=(
                        VecComparisonStatus.EXACT
                        if semantic_match
                        else VecComparisonStatus.MISMATCH
                    ),
                    comparison="semantic",
                    expected=expected_actor,
                    observed=str(observed[field]),
                    mismatch_count=0 if semantic_match else 1,
                    note="The exact actor hash/identity is carried by the VEC-07 receipt.",
                )
            )
        elif field == "avg_energy_j_per_task":
            checks.append(
                _numeric_scalar_check(
                    "run.json",
                    field,
                    float(expected[field]),
                    float(observed[field]),
                    SCALAR_TOLERANCE,
                )
            )
        else:
            equal = expected[field] == observed[field]
            checks.append(
                VecReproductionCheck(
                    artifact="run.json",
                    field=field,
                    status=VecComparisonStatus.EXACT if equal else VecComparisonStatus.MISMATCH,
                    comparison="exact",
                    expected=_portable_value(expected[field]),
                    observed=_portable_value(observed[field]),
                    mismatch_count=0 if equal else 1,
                )
            )
    return checks


def _compare_perstep(expected_blob: bytes, observed_path: Path) -> list[VecReproductionCheck]:
    np = _numpy()
    try:
        with (
            np.load(io.BytesIO(expected_blob), allow_pickle=False) as expected,
            np.load(observed_path, allow_pickle=False) as observed,
        ):
            expected_keys = set(expected.files)
            observed_keys = set(observed.files)
            checks = [
                VecReproductionCheck(
                    artifact="per-step.npz",
                    field="keys",
                    status=(
                        VecComparisonStatus.EXACT
                        if expected_keys == observed_keys
                        else VecComparisonStatus.MISMATCH
                    ),
                    comparison="exact",
                    element_count=len(expected_keys | observed_keys),
                    mismatch_count=len(expected_keys ^ observed_keys),
                )
            ]
            for field in sorted(expected_keys & observed_keys):
                left = expected[field]
                right = observed[field]
                same_contract = left.dtype == right.dtype and left.shape == right.shape
                checks.append(
                    VecReproductionCheck(
                        artifact="per-step.npz",
                        field=f"{field}.contract",
                        status=(
                            VecComparisonStatus.EXACT
                            if same_contract
                            else VecComparisonStatus.MISMATCH
                        ),
                        comparison="exact",
                        expected=f"{left.dtype}:{left.shape}",
                        observed=f"{right.dtype}:{right.shape}",
                        mismatch_count=0 if same_contract else 1,
                    )
                )
                if not same_contract:
                    continue
                if field == "lat_sum":
                    checks.append(
                        _numeric_array_check(
                            "per-step.npz",
                            field,
                            left,
                            right,
                            LATENCY_STREAM_TOLERANCE,
                        )
                    )
                else:
                    exact = bool(np.array_equal(left, right))
                    mismatch_count = int(np.count_nonzero(left != right))
                    checks.append(
                        VecReproductionCheck(
                            artifact="per-step.npz",
                            field=field,
                            status=(
                                VecComparisonStatus.EXACT if exact else VecComparisonStatus.MISMATCH
                            ),
                            comparison="exact",
                            element_count=int(left.size),
                            mismatch_count=mismatch_count,
                        )
                    )
            return checks
    except (OSError, ValueError) as exc:
        raise VecReproductionError(f"per-step NPZ comparison failed: {exc}") from exc


def _numeric_scalar_check(
    artifact: str,
    field: str,
    expected: float,
    observed: float,
    tolerance: VecNumericTolerance,
) -> VecReproductionCheck:
    difference = abs(observed - expected)
    relative = difference / abs(expected) if expected else (0.0 if difference == 0 else math.inf)
    accepted = difference <= max(tolerance.absolute, tolerance.relative * abs(expected))
    exact = difference == 0
    return VecReproductionCheck(
        artifact=artifact,
        field=field,
        status=(
            VecComparisonStatus.EXACT
            if exact
            else VecComparisonStatus.WITHIN_TOLERANCE
            if accepted
            else VecComparisonStatus.MISMATCH
        ),
        comparison="numeric",
        expected=expected,
        observed=observed,
        mismatch_count=0 if accepted else 1,
        max_absolute_error=difference,
        max_relative_error=relative,
        tolerance=tolerance,
    )


def _numeric_array_check(
    artifact: str,
    field: str,
    expected: npt.NDArray[np.generic],
    observed: npt.NDArray[np.generic],
    tolerance: VecNumericTolerance,
) -> VecReproductionCheck:
    np = _numpy()
    expected64 = expected.astype(np.float64)
    observed64 = observed.astype(np.float64)
    difference = np.abs(observed64 - expected64)
    bound = np.maximum(tolerance.absolute, tolerance.relative * np.abs(expected64))
    numeric_ok = bool(np.all(difference <= bound))
    relative = difference / np.maximum(np.abs(expected64), np.finfo(np.float64).tiny)
    ulp = _ulp_distance(expected, observed)
    max_ulp = int(ulp.max(initial=0))
    ulp_ok = tolerance.max_ulp is None or max_ulp <= tolerance.max_ulp
    exact = bool(np.array_equal(expected, observed))
    accepted = numeric_ok and ulp_ok
    return VecReproductionCheck(
        artifact=artifact,
        field=field,
        status=(
            VecComparisonStatus.EXACT
            if exact
            else VecComparisonStatus.WITHIN_TOLERANCE
            if accepted
            else VecComparisonStatus.MISMATCH
        ),
        comparison="numeric",
        element_count=int(expected.size),
        mismatch_count=0 if accepted else int(np.count_nonzero(difference > bound) or not ulp_ok),
        max_absolute_error=float(difference.max(initial=0)),
        max_relative_error=float(relative.max(initial=0)),
        max_ulp_error=max_ulp,
        tolerance=tolerance,
        note=f"Raw unequal element count: {int(np.count_nonzero(expected != observed))}.",
    )


def _ulp_distance(
    expected: npt.NDArray[np.generic],
    observed: npt.NDArray[np.generic],
) -> npt.NDArray[np.int64]:
    np = _numpy()
    if expected.dtype == np.float32:
        return np.abs(
            expected.view(np.int32).astype(np.int64) - observed.view(np.int32).astype(np.int64)
        )
    if expected.dtype == np.float64:
        return np.abs(expected.view(np.int64) - observed.view(np.int64))
    raise VecReproductionError("ULP comparison requires float32 or float64 arrays")


def _summary(checks: list[VecReproductionCheck]) -> VecReproductionSummary:
    return VecReproductionSummary(
        exact=sum(check.status is VecComparisonStatus.EXACT for check in checks),
        within_tolerance=sum(
            check.status is VecComparisonStatus.WITHIN_TOLERANCE for check in checks
        ),
        mismatch=sum(check.status is VecComparisonStatus.MISMATCH for check in checks),
        excluded=sum(check.status is VecComparisonStatus.EXCLUDED for check in checks),
        unavailable=sum(check.status is VecComparisonStatus.UNAVAILABLE for check in checks),
    )


def _portable_value(value: object) -> str | int | float | bool | list[int] | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list) and all(isinstance(item, int) for item in value):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _safe_observed_directory(path: Path) -> Path:
    if path.is_symlink() or not path.resolve().is_dir():
        raise VecReproductionError("observed directory must be a direct readable directory")
    return path.resolve()


def _safe_file(root: Path, relative: str) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise VecReproductionError(f"observed file must not be a symlink: {relative}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise VecReproductionError(f"observed file is missing or unsafe: {relative}") from exc
    if not resolved.is_file():
        raise VecReproductionError(f"observed artifact is not a regular file: {relative}")
    return resolved


def _git_text(git: str, repo: Path, *args: str) -> str:
    try:
        return subprocess.run(  # noqa: S603 - fixed read-only Git argv
            [git, "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise VecReproductionError(f"could not inspect expected Git repository: {exc}") from exc


def _git_bytes(git: str, repo: Path, *args: str) -> bytes:
    try:
        return subprocess.run(  # noqa: S603 - fixed read-only Git argv
            [git, "-C", str(repo), *args],
            check=True,
            capture_output=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise VecReproductionError(f"could not load expected Git blob: {exc}") from exc


def _numpy() -> ModuleType:
    import numpy as np

    return np


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
