"""Read-only preflight and isolated execution for the audited VEC evaluator."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from types import ModuleType
from typing import Literal

from traffictwin.integration.tos.contract_v2 import (
    validate_perstep_arrays,
    validate_pertask_arrays,
    validate_trace_arrays,
)
from traffictwin.integration.vec_preprocessing.models import VecFcdPreprocessReceipt
from traffictwin.integration.vec_runner.models import (
    PINNED_ACTORS,
    PINNED_EVALUATOR_FILES,
    PINNED_REVIEWED_TRACES,
    PINNED_TOS_DATA_COMMIT,
    PINNED_VEC_ENV_COMMIT,
    VecExecutionReceipt,
    VecRepositoryEvidence,
    VecRunnerFileEvidence,
    VecRunnerFinding,
    VecRunnerPreflightReport,
    VecRunnerPreflightStatus,
    VecRunnerSeverity,
    VecRunRequest,
    VecRuntimeEvidence,
    VecTerminalStatus,
    output_fingerprint,
)

_LOG_LIMIT_BYTES = 256_000
_OUTPUT_LIMIT_BYTES = 2_000_000_000
_ACTOR_SHAPES = {
    "Dense_0.bias": ((64,), "float32"),
    "Dense_0.kernel": ((17, 64), "float32"),
    "Dense_1.bias": ((64,), "float32"),
    "Dense_1.kernel": ((64, 64), "float32"),
    "Dense_2.bias": ((3,), "float32"),
    "Dense_2.kernel": ((64, 3), "float32"),
}


class VecRunnerError(RuntimeError):
    """Raised when VEC-07 refuses or cannot complete a run."""

    def __init__(
        self,
        message: str,
        *,
        preflight: VecRunnerPreflightReport | None = None,
        receipt: VecExecutionReceipt | None = None,
    ) -> None:
        super().__init__(message)
        self.preflight = preflight
        self.receipt = receipt


@dataclass(frozen=True)
class _RepositoryState:
    name: Literal["vec_env", "tos-data"]
    audited_commit: str
    head: str
    origin_main: str
    clean: bool
    blobs: dict[str, bytes]
    files: tuple[VecRunnerFileEvidence, ...]


@dataclass(frozen=True)
class _InputState:
    root: Path
    trace: Path
    receipt: Path | None
    evidence: tuple[VecRunnerFileEvidence, ...]
    trace_steps: int
    trace_slots: int


def preflight_vec_run(
    input_root: str | Path,
    vec_repo: str | Path,
    tos_data_repo: str | Path,
    request: VecRunRequest,
) -> VecRunnerPreflightReport:
    """Perform complete VEC-07 admission without creating an output directory."""

    repositories: list[VecRepositoryEvidence] = []
    findings: list[VecRunnerFinding] = []
    inputs: _InputState | None = None
    runtime: VecRuntimeEvidence | None = None
    dependency_unavailable = False
    try:
        vec_state = _inspect_repository(
            Path(vec_repo),
            "vec_env",
            PINNED_VEC_ENV_COMMIT,
            PINNED_EVALUATOR_FILES,
        )
        actor_path, actor_sha = PINNED_ACTORS[request.actor_id]
        tos_state = _inspect_repository(
            Path(tos_data_repo),
            "tos-data",
            PINNED_TOS_DATA_COMMIT,
            {actor_path: actor_sha},
        )
        _validate_actor(tos_state.blobs[actor_path])
        repositories = [_repository_evidence(vec_state), _repository_evidence(tos_state)]
        for state in (vec_state, tos_state):
            if not state.clean:
                findings.append(_finding("VEC_SOURCE_DIRTY", f"{state.name} must be clean"))
            if state.origin_main != state.audited_commit:
                findings.append(
                    _finding(
                        "VEC_SOURCE_REF_MISMATCH",
                        f"{state.name} origin/main does not identify the audited commit",
                    )
                )
    except VecRunnerError as exc:
        findings.append(_finding("VEC_SOURCE_AUDIT_FAILED", str(exc)))

    try:
        inputs = _inspect_inputs(Path(input_root), request)
    except VecRunnerError as exc:
        findings.append(_finding("VEC_INPUT_REJECTED", str(exc), request.trace_file))

    try:
        runtime = _inspect_runtime()
    except VecRunnerError as exc:
        dependency_unavailable = True
        findings.append(_finding("VEC_RUNTIME_UNAVAILABLE", str(exc)))

    if not findings:
        findings.extend(
            [
                _finding(
                    "VEC_PINNED_SOURCES_CONFIRMED",
                    "all executable blobs match Gate A",
                    severity=VecRunnerSeverity.INFO,
                ),
                _finding(
                    "VEC_TRACE_CONTRACT_CONFIRMED",
                    "trace passes the exact VEC-02 schema",
                    severity=VecRunnerSeverity.INFO,
                ),
                _finding(
                    "VEC_ACTOR_ARCHITECTURE_CONFIRMED",
                    "actor is the audited 17-64-64-3 Model-C checkpoint",
                    severity=VecRunnerSeverity.INFO,
                ),
                _finding(
                    "VEC_CPU_RUNTIME_CONFIRMED",
                    "JAX/JAXLIB 0.4.30 CPU runtime is available",
                    severity=VecRunnerSeverity.INFO,
                ),
            ]
        )
    has_error = any(item.severity is VecRunnerSeverity.ERROR for item in findings)
    status = (
        VecRunnerPreflightStatus.UNAVAILABLE
        if dependency_unavailable
        and has_error
        and len([f for f in findings if f.severity is VecRunnerSeverity.ERROR]) == 1
        else VecRunnerPreflightStatus.REJECTED
        if has_error
        else VecRunnerPreflightStatus.ACCEPTED
    )
    return VecRunnerPreflightReport(
        status=status,
        request=request,
        request_fingerprint=request.fingerprint(),
        repositories=repositories,
        inputs=list(inputs.evidence) if inputs else [],
        runtime=runtime,
        trace_steps=inputs.trace_steps if inputs else None,
        trace_slots=inputs.trace_slots if inputs else None,
        findings=findings,
    )


def run_vec_evaluator(
    input_root: str | Path,
    vec_repo: str | Path,
    tos_data_repo: str | Path,
    output_dir: str | Path,
    request: VecRunRequest,
    *,
    cancellation_event: threading.Event | None = None,
) -> VecExecutionReceipt:
    """Run exact audited blobs in a private workspace and atomically publish success."""

    input_root_path = Path(input_root)
    vec_repo_path = Path(vec_repo).resolve()
    tos_repo_path = Path(tos_data_repo).resolve()
    preflight = preflight_vec_run(input_root_path, vec_repo_path, tos_repo_path, request)
    if preflight.status is not VecRunnerPreflightStatus.ACCEPTED or preflight.runtime is None:
        raise VecRunnerError(f"VEC-07 preflight is {preflight.status.value}", preflight=preflight)
    inputs = _inspect_inputs(input_root_path, request)
    destination = _validate_destination(
        Path(output_dir),
        inputs.root,
        vec_repo_path,
        tos_repo_path,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-vec-run-", dir=destination.parent)
    )
    payload = temporary_root / "payload"
    runtime_root = temporary_root / "runtime"
    logs_root = payload / "logs"
    payload.mkdir()
    logs_root.mkdir()
    runtime_root.mkdir()

    started_at = _utc_now()
    started_monotonic = time.monotonic()
    status = VecTerminalStatus.FAILED
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    findings: list[VecRunnerFinding] = []
    repositories_after: list[VecRepositoryEvidence] = []
    inputs_after: list[VecRunnerFileEvidence] = []
    repositories_modified = False
    inputs_modified = False
    argv_receipt: list[str] = []
    process: subprocess.Popen[str] | None = None
    try:
        vec_before = _inspect_repository(
            vec_repo_path, "vec_env", PINNED_VEC_ENV_COMMIT, PINNED_EVALUATOR_FILES
        )
        actor_path, actor_hash = PINNED_ACTORS[request.actor_id]
        tos_before = _inspect_repository(
            tos_repo_path, "tos-data", PINNED_TOS_DATA_COMMIT, {actor_path: actor_hash}
        )
        _assert_preflight_repositories(preflight, vec_before, tos_before)
        evaluator = runtime_root / "evaluator.py"
        env_module = runtime_root / "jaxmarl" / "env" / "vec_jax.py"
        actor = runtime_root / "actor.npz"
        env_module.parent.mkdir(parents=True)
        evaluator.write_bytes(vec_before.blobs["eval/eval_sumo_stage1_mc.py"])
        env_module.write_bytes(vec_before.blobs["jaxmarl/env/vec_jax.py"])
        actor.write_bytes(tos_before.blobs[actor_path])
        for file in (evaluator, env_module, actor):
            file.chmod(0o444)

        run_json = payload / "run.json"
        per_step = payload / "per-step.npz"
        per_task = payload / "per-task.npz"
        argv = [
            sys.executable,
            str(evaluator),
            "--trace",
            str(inputs.trace),
            "--actor",
            str(actor),
            "--rsu-cap-per-veh",
            format(request.rsu_capacity_per_vehicle, ".12g"),
            "--max-steps",
            str(request.max_steps),
            "--seed",
            str(request.evaluator_seed),
            "--fleet",
            request.fleet.value,
            "--fleet-seed",
            str(request.fleet_seed),
            "--per-step-out",
            str(per_step),
            "--per-task-out",
            str(per_task),
            "--out-json",
            str(run_json),
        ]
        argv_receipt = _redacted_argv(argv, evaluator, inputs.trace, actor, payload)
        process = subprocess.Popen(  # noqa: S603 - fixed audited script and allowlisted argv
            argv,
            cwd=runtime_root,
            env=_controlled_environment(runtime_root / "jaxmarl"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + request.timeout_seconds
        while process.poll() is None:
            if cancellation_event is not None and cancellation_event.is_set():
                status = VecTerminalStatus.CANCELLED
                findings.append(_finding("VEC_RUN_CANCELLED", "cancellation was requested"))
                _terminate_process_group(process)
                break
            if time.monotonic() >= deadline:
                status = VecTerminalStatus.TIMED_OUT
                findings.append(
                    _finding("VEC_RUN_TIMED_OUT", f"run exceeded {request.timeout_seconds} seconds")
                )
                _terminate_process_group(process)
                break
            time.sleep(0.05)
        stdout, stderr = process.communicate(timeout=10)
        exit_code = process.returncode
        if status not in {VecTerminalStatus.CANCELLED, VecTerminalStatus.TIMED_OUT}:
            if exit_code != 0:
                status = VecTerminalStatus.FAILED
                findings.append(
                    _finding("VEC_EVALUATOR_FAILED", f"evaluator exited with {exit_code}")
                )
            else:
                _validate_outputs(inputs.trace, run_json, per_step, per_task, request.max_steps)
                status = VecTerminalStatus.COMPLETED

        vec_after = _inspect_repository(
            vec_repo_path, "vec_env", PINNED_VEC_ENV_COMMIT, PINNED_EVALUATOR_FILES
        )
        tos_after = _inspect_repository(
            tos_repo_path, "tos-data", PINNED_TOS_DATA_COMMIT, {actor_path: actor_hash}
        )
        inputs_after = list(_inspect_inputs(input_root_path, request).evidence)
        _assert_immutable(preflight, vec_after, tos_after, inputs_after)
        repositories_after = [
            _repository_evidence(vec_before, vec_after),
            _repository_evidence(tos_before, tos_after),
        ]
        if status is VecTerminalStatus.COMPLETED:
            findings.append(
                _finding(
                    "VEC_RUN_COMPLETED",
                    "isolated evaluator completed and outputs passed structural validation",
                    severity=VecRunnerSeverity.INFO,
                )
            )
    except (OSError, ValueError, subprocess.SubprocessError, VecRunnerError) as exc:
        if process is not None and process.poll() is None:
            _terminate_process_group(process)
        if not findings:
            findings.append(_finding("VEC_RUN_FAILED", str(exc)))
        status = VecTerminalStatus.FAILED
    finally:
        _write_log(
            logs_root / "stdout.txt",
            stdout,
            temporary_root,
            inputs.root,
            vec_repo_path,
            tos_repo_path,
        )
        _write_log(
            logs_root / "stderr.txt",
            stderr,
            temporary_root,
            inputs.root,
            vec_repo_path,
            tos_repo_path,
        )

    finished_at = _utc_now()
    log_evidence = _inventory(logs_root, prefix="logs")
    stdout_excerpt = (logs_root / "stdout.txt").read_text(encoding="utf-8")
    stderr_excerpt = (logs_root / "stderr.txt").read_text(encoding="utf-8")
    if not repositories_after:
        try:
            actor_path, actor_hash = PINNED_ACTORS[request.actor_id]
            vec_after = _inspect_repository(
                vec_repo_path, "vec_env", PINNED_VEC_ENV_COMMIT, PINNED_EVALUATOR_FILES
            )
            tos_after = _inspect_repository(
                tos_repo_path, "tos-data", PINNED_TOS_DATA_COMMIT, {actor_path: actor_hash}
            )
            before_by_name = {item.repository: item for item in preflight.repositories}
            repositories_after = []
            for state in (vec_after, tos_after):
                before = before_by_name[state.name]
                repositories_modified |= (
                    state.head != before.worktree_head_before
                    or state.origin_main != before.origin_main_before
                    or not state.clean
                )
                repositories_after.append(
                    VecRepositoryEvidence(
                        **{
                            **before.model_dump(mode="python"),
                            "worktree_head_after": state.head,
                            "origin_main_after": state.origin_main,
                            "clean_after": state.clean,
                        }
                    )
                )
        except (KeyError, VecRunnerError) as exc:
            repositories_modified = True
            repositories_after = preflight.repositories
            findings.append(_finding("VEC_SOURCE_POST_AUDIT_FAILED", str(exc)))
    if not inputs_after:
        try:
            inputs_after = list(_inspect_inputs(input_root_path, request).evidence)
            inputs_modified = inputs_after != preflight.inputs
        except VecRunnerError as exc:
            inputs_modified = True
            inputs_after = []
            findings.append(_finding("VEC_INPUT_POST_AUDIT_FAILED", str(exc)))
    if repositories_modified or inputs_modified:
        status = VecTerminalStatus.FAILED
        findings.append(
            _finding(
                "VEC_IMMUTABILITY_VIOLATION", "source or input identity changed during execution"
            )
        )
    outputs = (
        _inventory(payload, exclude={"logs/stdout.txt", "logs/stderr.txt"})
        if status is VecTerminalStatus.COMPLETED
        else []
    )
    receipt = VecExecutionReceipt(
        status=status,
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint=preflight.fingerprint(),
        argv=argv_receipt,
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        elapsed_seconds=round(time.monotonic() - started_monotonic, 6),
        exit_code=exit_code,
        timed_out=status is VecTerminalStatus.TIMED_OUT,
        cancellation_requested=status is VecTerminalStatus.CANCELLED,
        runtime=preflight.runtime,
        repositories=repositories_after,
        inputs_before=preflight.inputs,
        inputs_after=inputs_after,
        logs=log_evidence,
        stdout_excerpt=stdout_excerpt,
        stderr_excerpt=stderr_excerpt,
        outputs=outputs,
        findings=findings,
        output_fingerprint=output_fingerprint(outputs) if outputs else None,
        external_repositories_modified=repositories_modified,
        raw_inputs_modified=inputs_modified,
        published=status is VecTerminalStatus.COMPLETED,
    )
    if status is VecTerminalStatus.COMPLETED:
        receipt_path = payload / "execution_receipt.json"
        receipt_path.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
        _make_read_only(payload)
        payload.replace(destination)
        destination.chmod(0o555)
        shutil.rmtree(temporary_root, ignore_errors=True)
        return receipt
    shutil.rmtree(temporary_root, ignore_errors=True)
    raise VecRunnerError(f"VEC-07 run ended as {status.value}", receipt=receipt)


def _inspect_repository(
    repo: Path,
    name: Literal["vec_env", "tos-data"],
    commit: str,
    files: dict[str, str],
) -> _RepositoryState:
    if repo.is_symlink() or not repo.resolve().is_dir():
        raise VecRunnerError(f"{name} must be a direct readable directory")
    git = shutil.which("git")
    if git is None:
        raise VecRunnerError("git is required for audited blob inspection")
    resolved = repo.resolve()
    head = _git_text(git, resolved, "rev-parse", "HEAD").strip()
    origin = _git_text(git, resolved, "rev-parse", "refs/remotes/origin/main").strip()
    clean = not _git_text(git, resolved, "status", "--porcelain=v1", "--untracked-files=all")
    _git_text(git, resolved, "cat-file", "-e", f"{commit}^{{commit}}")
    blobs: dict[str, bytes] = {}
    evidence: list[VecRunnerFileEvidence] = []
    for path, expected in sorted(files.items()):
        blob = _git_bytes(git, resolved, "show", f"{commit}:{path}")
        digest = _sha256_bytes(blob)
        if digest != expected:
            raise VecRunnerError(f"audited blob hash mismatch for {name}:{path}")
        blobs[path] = blob
        evidence.append(_file_evidence(f"source/{name}/{path}", blob, read_only=True))
    return _RepositoryState(name, commit, head, origin, clean, blobs, tuple(evidence))


def _repository_evidence(
    before: _RepositoryState,
    after: _RepositoryState | None = None,
) -> VecRepositoryEvidence:
    return VecRepositoryEvidence(
        repository=before.name,
        audited_commit=before.audited_commit,
        worktree_head_before=before.head,
        worktree_head_after=after.head if after else None,
        origin_main_before=before.origin_main,
        origin_main_after=after.origin_main if after else None,
        clean_before=before.clean,
        clean_after=after.clean if after else None,
        source_files=list(before.files),
    )


def _inspect_inputs(root: Path, request: VecRunRequest) -> _InputState:
    if root.is_symlink() or not root.resolve().is_dir():
        raise VecRunnerError("input root must be a direct readable directory")
    resolved = root.resolve()
    trace = _safe_file(resolved, request.trace_file)
    trace_bytes = trace.read_bytes()
    if len(trace_bytes) > _OUTPUT_LIMIT_BYTES or _sha256_bytes(trace_bytes) != request.trace_sha256:
        raise VecRunnerError("trace size or SHA-256 does not match the request")
    receipt_path: Path | None = None
    evidence = [_file_evidence(f"inputs/{request.trace_file}", trace_bytes, read_only=True)]
    if request.preprocessing_receipt_file is None:
        reviewed_path = PINNED_REVIEWED_TRACES.get(request.trace_sha256)
        if reviewed_path is None:
            raise VecRunnerError("trace is neither reviewed nor backed by a VEC-06 receipt")
    else:
        receipt_path = _safe_file(resolved, request.preprocessing_receipt_file)
        receipt_bytes = receipt_path.read_bytes()
        if _sha256_bytes(receipt_bytes) != request.preprocessing_receipt_sha256:
            raise VecRunnerError("preprocessing receipt SHA-256 does not match")
        try:
            receipt = VecFcdPreprocessReceipt.model_validate_json(receipt_bytes)
        except ValueError as exc:
            raise VecRunnerError("preprocessing receipt is not a valid VEC-06 receipt") from exc
        trace_output = next((item for item in receipt.outputs if item.path == "trace.npz"), None)
        if trace_output is None or trace_output.sha256 != request.trace_sha256:
            raise VecRunnerError("VEC-06 receipt does not identify the requested trace")
        evidence.append(
            _file_evidence(
                f"inputs/{request.preprocessing_receipt_file}", receipt_bytes, read_only=True
            )
        )
    np = _numpy()
    try:
        with np.load(io.BytesIO(trace_bytes), allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        report = validate_trace_arrays(arrays)
        if report.status != "accepted":
            raise VecRunnerError(
                "trace fails VEC-02: " + "; ".join(f.detail for f in report.findings)
            )
        steps = int(arrays["T"])
        slots = int(arrays["maxN"])
    except (OSError, ValueError) as exc:
        if isinstance(exc, VecRunnerError):
            raise
        raise VecRunnerError(f"trace NPZ could not be safely read: {exc}") from exc
    if request.max_steps > steps:
        raise VecRunnerError("max_steps cannot exceed the admitted trace length")
    return _InputState(resolved, trace, receipt_path, tuple(evidence), steps, slots)


def _inspect_runtime() -> VecRuntimeEvidence:
    try:
        import jax
        import numpy
    except ImportError as exc:
        raise VecRunnerError("optional vec-runner dependencies are unavailable") from exc
    jaxlib_version = version("jaxlib")
    if jax.__version__ != "0.4.30" or jaxlib_version != "0.4.30":
        raise VecRunnerError("VEC-07 requires jax==0.4.30 and jaxlib==0.4.30")
    backend = str(jax.default_backend())
    if backend != "cpu":
        raise VecRunnerError("VEC-07 accepts only the CPU JAX backend")
    env_identity = {
        "JAX_PLATFORMS": "cpu",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
    }
    return VecRuntimeEvidence(
        python=platform.python_version(),
        numpy=numpy.__version__,
        jax=jax.__version__,
        jaxlib=jaxlib_version,
        jax_backend=backend,
        jax_device_count=len(jax.devices("cpu")),
        platform=platform.system(),
        machine=platform.machine() or "unknown",
        processor=platform.processor() or "unknown",
        environment_sha256=_sha256_bytes(
            json.dumps(env_identity, sort_keys=True, separators=(",", ":")).encode()
        ),
    )


def _validate_actor(content: bytes) -> None:
    np = _numpy()
    try:
        with np.load(io.BytesIO(content), allow_pickle=False) as archive:
            if set(archive.files) != set(_ACTOR_SHAPES):
                raise VecRunnerError("actor keys do not match the audited architecture")
            for key, (shape, dtype) in _ACTOR_SHAPES.items():
                if archive[key].shape != shape or str(archive[key].dtype) != dtype:
                    raise VecRunnerError(
                        f"actor tensor {key} does not match the audited architecture"
                    )
                if not bool(np.all(np.isfinite(archive[key]))):
                    raise VecRunnerError(f"actor tensor {key} contains non-finite values")
    except (OSError, ValueError) as exc:
        if isinstance(exc, VecRunnerError):
            raise
        raise VecRunnerError(f"actor checkpoint could not be safely read: {exc}") from exc


def _validate_outputs(
    trace_path: Path,
    run_json_path: Path,
    per_step_path: Path,
    per_task_path: Path,
    max_steps: int,
) -> None:
    for path in (run_json_path, per_step_path, per_task_path):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _OUTPUT_LIMIT_BYTES:
            raise VecRunnerError(f"required evaluator output is missing or unsafe: {path.name}")
    np = _numpy()
    try:
        run_summary = json.loads(run_json_path.read_text(encoding="utf-8"))
        with np.load(trace_path, allow_pickle=False) as source:
            trace = {key: source[key] for key in source.files}
        if max_steps < int(trace["T"]):
            trace = dict(trace)
            for key in ("pos_x", "pos_y", "speed", "mask"):
                trace[key] = trace[key][:max_steps]
            trace["times"] = trace["times"][:max_steps]
            trace["T"] = np.asarray(max_steps, dtype=np.int32)
        with np.load(per_step_path, allow_pickle=False) as source:
            per_step = {key: source[key] for key in source.files}
        with np.load(per_task_path, allow_pickle=False) as source:
            per_task = {key: source[key] for key in source.files}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise VecRunnerError(f"evaluator outputs could not be safely parsed: {exc}") from exc
    trace_report = validate_trace_arrays(trace)
    step_report = validate_perstep_arrays(per_step, trace, run_summary)
    task_report = validate_pertask_arrays(per_task, trace)
    rejected = [r for r in (trace_report, step_report, task_report) if r.status != "accepted"]
    if rejected:
        details = "; ".join(f.detail for report in rejected for f in report.findings)
        raise VecRunnerError(f"evaluator output contract failed: {details}")


def _assert_preflight_repositories(
    preflight: VecRunnerPreflightReport,
    vec: _RepositoryState,
    tos: _RepositoryState,
) -> None:
    current = {item.repository: item for item in preflight.repositories}
    for state in (vec, tos):
        observed = current.get(state.name)
        if observed is None or observed.worktree_head_before != state.head or not state.clean:
            raise VecRunnerError(f"{state.name} changed after preflight")


def _assert_immutable(
    preflight: VecRunnerPreflightReport,
    vec: _RepositoryState,
    tos: _RepositoryState,
    inputs_after: list[VecRunnerFileEvidence],
) -> None:
    _assert_preflight_repositories(preflight, vec, tos)
    if preflight.inputs != inputs_after:
        raise VecRunnerError("raw inputs changed during evaluator execution")


def _validate_destination(destination: Path, *protected_roots: Path) -> Path:
    unresolved = destination.expanduser()
    if unresolved.exists() or unresolved.is_symlink():
        raise VecRunnerError("VEC-07 output directory must not already exist")
    if _has_symlink_component(unresolved.parent):
        raise VecRunnerError("VEC-07 output parent must not contain symbolic links")
    resolved = unresolved.resolve(strict=False)
    broad = (Path.cwd().resolve(), Path.home().resolve(), Path("/").resolve())
    if any(resolved == item or resolved in item.parents for item in broad):
        raise VecRunnerError("VEC-07 output directory is too broad")
    for root in protected_roots:
        root = root.resolve()
        if resolved == root or resolved in root.parents or root in resolved.parents:
            raise VecRunnerError("VEC-07 output must not overlap inputs or external repositories")
    return resolved


def _safe_file(root: Path, relative: str) -> Path:
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise VecRunnerError("symbolic-link inputs are not accepted")
    try:
        resolved = (root / relative).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise VecRunnerError("input path is missing or escapes the input root") from exc
    if not resolved.is_file():
        raise VecRunnerError("input must be a regular file")
    return resolved


def _controlled_environment(python_path: Path) -> dict[str, str]:
    return {
        "JAX_PLATFORMS": "cpu",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.defpath,
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(python_path),
    }


def _redacted_argv(
    argv: list[str], evaluator: Path, trace: Path, actor: Path, payload: Path
) -> list[str]:
    replacements = {
        sys.executable: "{python}",
        str(evaluator): "{PINNED_EVALUATOR}",
        str(trace): "{TRACE}",
        str(actor): "{PINNED_ACTOR}",
        str(payload / "run.json"): "outputs/run.json",
        str(payload / "per-step.npz"): "outputs/per-step.npz",
        str(payload / "per-task.npz"): "outputs/per-task.npz",
    }
    return [replacements.get(value, value) for value in argv]


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        with suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)


def _write_log(path: Path, value: str, *redact_paths: Path) -> None:
    redacted = value
    for index, raw in enumerate(redact_paths):
        redacted = redacted.replace(str(raw), f"{{PATH_{index}}}")
    encoded = redacted.encode("utf-8", errors="replace")
    if len(encoded) > _LOG_LIMIT_BYTES:
        marker = b"\n[TrafficTwin log truncated]\n"
        encoded = encoded[: _LOG_LIMIT_BYTES - len(marker)] + marker
    path.write_bytes(encoded)


def _inventory(
    root: Path,
    *,
    prefix: str | None = None,
    exclude: set[str] | None = None,
) -> list[VecRunnerFileEvidence]:
    evidence: list[VecRunnerFileEvidence] = []
    excluded = exclude or set()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        portable = f"{prefix}/{relative}" if prefix else relative
        if portable in excluded:
            continue
        evidence.append(_file_evidence(portable, path.read_bytes(), read_only=True))
    return evidence


def _file_evidence(path: str, content: bytes, *, read_only: bool) -> VecRunnerFileEvidence:
    suffix = Path(path).suffix.lower()
    media_type = {
        ".json": "application/json",
        ".npz": "application/x-npz",
        ".py": "text/x-python",
        ".txt": "text/plain",
    }.get(suffix, "application/octet-stream")
    return VecRunnerFileEvidence(
        path=path,
        sha256=_sha256_bytes(content),
        size_bytes=len(content),
        media_type=media_type,
        read_only=read_only,
    )


def _make_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)


def _has_symlink_component(path: Path) -> bool:
    current = path
    while current != current.parent:
        if current.exists() and current.is_symlink():
            return True
        current = current.parent
    return current.is_symlink()


def _git_text(git: str, repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(  # noqa: S603 - resolved git and fixed read-only argv
            [git, "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VecRunnerError(f"could not inspect Git state: {exc}") from exc
    return result.stdout


def _git_bytes(git: str, repo: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(  # noqa: S603 - resolved git and fixed read-only argv
            [git, "-C", str(repo), *args],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VecRunnerError(f"could not load audited Git blob: {exc}") from exc
    return result.stdout


def _finding(
    code: str,
    message: str,
    artifact: str | None = None,
    *,
    severity: VecRunnerSeverity = VecRunnerSeverity.ERROR,
) -> VecRunnerFinding:
    return VecRunnerFinding(
        code=code, severity=severity, message=message[:1_000], artifact=artifact
    )


def _numpy() -> ModuleType:
    import numpy as np

    return np


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
