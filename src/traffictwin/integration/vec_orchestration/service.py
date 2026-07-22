"""One-click VEC execute-and-import orchestration over accepted services.

The orchestration composes, in order: registry-destination admission, the
read-only VEC-07 preflight, the allowlisted foreground evaluator execution,
receipt/output revalidation from disk, source-immutability verification, and
one idempotent registry import through the existing ``register_bundle_import``
pathway. Every stage is typed; no stage constructs commands, computes metrics,
or widens permission. A failed, rejected, timed-out, cancelled, or mutated
execution never imports anything.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.domain.enums import ExecutionMode, RunStatus, ValidationStatus
from traffictwin.domain.run import Run
from traffictwin.integration.vec_orchestration.models import (
    FULL_RUN_ID,
    REVIEWED_WEEKEND_TRACE_FILE,
    REVIEWED_WEEKEND_TRACE_SHA256,
    REVIEWED_WEEKEND_TRACE_STEPS,
    SCIENTIFIC_ADMISSION_REASONS,
    SMOKE_MAX_STEPS,
    SMOKE_RUN_ID,
    VecEvidenceGrade,
    VecExecutionImportRecord,
    VecExecutionPreset,
    VecImportOutcome,
    VecOrchestrationContract,
    VecPresetWorkload,
    VecWorkflowReceipt,
    VecWorkflowRequest,
    VecWorkflowStage,
    VecWorkflowStageName,
    VecWorkflowStageState,
    VecWorkflowStatus,
)
from traffictwin.integration.vec_runner import (
    PINNED_ACTORS,
    VecExecutionReceipt,
    VecFleet,
    VecRunnerError,
    VecRunnerPreflightStatus,
    VecRunRequest,
    VecTerminalStatus,
    preflight_vec_run,
    run_vec_evaluator,
)
from traffictwin.storage.registry import Registry, RegistryConflictError

_RECEIPT_FILE = "execution_receipt.json"
_RECEIPT_LIMIT_BYTES = 8_000_000
_HASH_CHUNK_BYTES = 1024 * 1024
_MAX_STAGE_ERRORS = 5

_TERMINAL_TO_WORKFLOW = {
    VecTerminalStatus.FAILED: VecWorkflowStatus.EXECUTION_FAILED,
    VecTerminalStatus.TIMED_OUT: VecWorkflowStatus.EXECUTION_TIMED_OUT,
    VecTerminalStatus.CANCELLED: VecWorkflowStatus.EXECUTION_CANCELLED,
    VecTerminalStatus.REJECTED: VecWorkflowStatus.EXECUTION_REJECTED,
}


class VecOrchestrationError(RuntimeError):
    """Raised when an import or workflow input cannot be admitted safely."""


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def build_preset_request(preset: VecExecutionPreset) -> VecRunRequest:
    """Return the exact closed request for one repository-defined preset."""

    if preset is VecExecutionPreset.SMOKE_TWO_STEP:
        return VecRunRequest(
            run_id=SMOKE_RUN_ID,
            trace_file=REVIEWED_WEEKEND_TRACE_FILE,
            trace_sha256=REVIEWED_WEEKEND_TRACE_SHA256,
            actor_id="ukfleettrain_mappo_model_c_17",
            evaluator_seed=0,
            fleet=VecFleet.UK_2030,
            fleet_seed=0,
            rsu_capacity_per_vehicle=2.5,
            max_steps=SMOKE_MAX_STEPS,
            timeout_seconds=600,
        )
    return VecRunRequest(
        run_id=FULL_RUN_ID,
        trace_file=REVIEWED_WEEKEND_TRACE_FILE,
        trace_sha256=REVIEWED_WEEKEND_TRACE_SHA256,
        actor_id="ukfleettrain_mappo_model_c_17",
        evaluator_seed=0,
        fleet=VecFleet.UK_2030,
        fleet_seed=0,
        rsu_capacity_per_vehicle=2.5,
        max_steps=REVIEWED_WEEKEND_TRACE_STEPS,
        timeout_seconds=7_200,
    )


def preset_evidence_grade(preset: VecExecutionPreset) -> VecEvidenceGrade:
    """Return the only evidence grade a preset execution may claim."""

    if preset is VecExecutionPreset.SMOKE_TWO_STEP:
        return VecEvidenceGrade.STRUCTURAL_SMOKE_EXECUTION
    return VecEvidenceGrade.FULL_PROTOCOL_EXECUTION_UNVERIFIED_REPRODUCTION


def preset_workload(preset: VecExecutionPreset) -> VecPresetWorkload:
    """Return factual request properties for user review; never a runtime promise."""

    request = build_preset_request(preset)
    if preset is VecExecutionPreset.SMOKE_TWO_STEP:
        description = (
            "Two evaluator steps over the reviewed weekend trace with the audited "
            "UK-2030 Model-C actor. Structural execution evidence only; never "
            "scientific reproduction or dissertation performance evidence."
        )
    else:
        description = (
            "The exact accepted VEC-08 protocol-seed run over all "
            f"{REVIEWED_WEEKEND_TRACE_STEPS} weekend trace steps. A long foreground "
            "operation; reproduction remains unverified until VEC-08 grading, and "
            "the protocol seed is distinct from the _s102 best-of-seeds evidence."
        )
    return VecPresetWorkload(
        preset=preset,
        evaluator_steps=request.max_steps,
        trace_file=request.trace_file,
        timeout_seconds_bound=request.timeout_seconds,
        description=description,
    )


def match_preset(request: VecRunRequest) -> VecExecutionPreset | None:
    """Return the closed preset matching a request fingerprint exactly, if any."""

    fingerprint = request.fingerprint()
    for preset in VecExecutionPreset:
        if build_preset_request(preset).fingerprint() == fingerprint:
            return preset
    return None


def import_vec_execution(
    result_dir: str | Path,
    registry_path: str | Path,
    *,
    vec_repo: str | Path | None = None,
    tos_data_repo: str | Path | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> tuple[VecExecutionImportRecord, VecImportOutcome]:
    """Validate one published preset execution and import it idempotently.

    The receipt and every listed output are re-verified byte-for-byte from
    disk. Only a ``completed`` receipt for one exact closed preset is
    admissible; anything else raises :class:`VecOrchestrationError` and writes
    nothing. A registry identity conflict raises ``RegistryConflictError``.
    """

    supplied_root = Path(result_dir)
    if supplied_root.is_symlink():
        raise VecOrchestrationError("result directory must be an existing non-symlink directory")
    root = supplied_root.resolve(strict=False)
    if not root.is_dir():
        raise VecOrchestrationError("result directory must be an existing non-symlink directory")
    receipt = _load_receipt(root)
    if receipt.status is not VecTerminalStatus.COMPLETED:
        raise VecOrchestrationError(
            f"only completed executions may be imported; receipt status is {receipt.status.value}"
        )
    if receipt.external_repositories_modified or receipt.raw_inputs_modified:
        raise VecOrchestrationError("receipt reports mutated sources or inputs; import refused")
    preset = match_preset(receipt.request)
    if preset is None:
        raise VecOrchestrationError(
            "receipt request does not match any closed execution preset; import refused"
        )
    _verify_outputs_on_disk(root, receipt)
    if vec_repo is not None:
        _verify_repository_state(Path(vec_repo), receipt, "vec_env")
    if tos_data_repo is not None:
        _verify_repository_state(Path(tos_data_repo), receipt, "tos-data")
    registry_file = _admit_registry_path(registry_path, root)

    receipt_fingerprint = receipt.fingerprint()
    if receipt.output_fingerprint is None:
        raise VecOrchestrationError("completed receipt is missing its output fingerprint")
    run_id = f"vec:exec:{receipt_fingerprint[:16]}"
    bundle_id = f"vec-exec:{receipt_fingerprint}"
    record = VecExecutionImportRecord(
        preset=preset,
        evidence_grade=preset_evidence_grade(preset),
        request=receipt.request,
        request_fingerprint=receipt.request_fingerprint,
        preflight_fingerprint=receipt.preflight_fingerprint,
        receipt_file_sha256=_sha256_file(root / _RECEIPT_FILE),
        receipt_fingerprint=receipt_fingerprint,
        output_fingerprint=receipt.output_fingerprint,
        runtime=receipt.runtime,
        outputs=list(receipt.outputs),
        started_at_utc=receipt.started_at_utc,
        finished_at_utc=receipt.finished_at_utc,
        elapsed_seconds=receipt.elapsed_seconds,
        imported_at_utc=clock().isoformat(),
        registry_run_id=run_id,
        registry_bundle_id=bundle_id,
        scientific_admission_reasons=list(SCIENTIFIC_ADMISSION_REASONS),
        limitations=_record_limitations(preset),
    )
    now = clock()
    run = Run(
        run_id=run_id,
        experiment_id=None,
        seed_id=f"vec-seed:we_fullrsu:{receipt.request.fleet.value}",
        algorithm=receipt.request.actor_id,
        checkpoint=PINNED_ACTORS[receipt.request.actor_id][0],
        random_seed=receipt.request.evaluator_seed,
        environment_version=None,
        environment_commit=record.vec_env_commit,
        started_at=datetime.fromisoformat(receipt.started_at_utc),
        ended_at=datetime.fromisoformat(receipt.finished_at_utc),
        execution_mode=ExecutionMode.DIRECT_LAUNCH,
        status=RunStatus.COMPLETED,
        source_bundle=bundle_id,
        validation_status=ValidationStatus.VALID,
        created_at=now,
        updated_at=now,
    )
    registry = Registry(registry_file)
    result = registry.register_bundle_import(
        run=run,
        bundle_id=bundle_id,
        source_reference=f"vec-oneclick:{preset.value}",
        fingerprint=record.stable_fingerprint(),
        manifest_json=record.model_dump_json(),
        validation_report_json=_validation_report_json(record),
    )
    outcome = VecImportOutcome(
        created=result.created,
        idempotent=result.idempotent,
        registry_run_id=result.run_id,
        registry_bundle_id=result.bundle_id,
        stable_fingerprint=record.stable_fingerprint(),
        registry_reference=registry_file.name,
    )
    return record, outcome


def list_imported_vec_executions(
    registry_path: str | Path,
) -> list[VecExecutionImportRecord]:
    """Load and revalidate persisted one-click VEC records for UI inspection."""

    supplied = Path(registry_path)
    if not supplied.exists():
        return []
    if supplied.is_symlink() or not supplied.is_file():
        raise VecOrchestrationError("registry must be an existing non-symlink SQLite file")
    try:
        rows = Registry(supplied).list_bundle_import_records()
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        raise VecOrchestrationError(f"registry records could not be read: {exc}") from exc

    records: list[VecExecutionImportRecord] = []
    for row in rows:
        if not row.source_reference.startswith("vec-oneclick:"):
            continue
        try:
            record = VecExecutionImportRecord.model_validate_json(row.manifest_json)
        except ValueError as exc:
            raise VecOrchestrationError(
                f"stored VEC execution record is invalid: {row.bundle_id}"
            ) from exc
        expected_source = f"vec-oneclick:{record.preset.value}"
        if (
            row.source_reference != expected_source
            or row.bundle_id != record.registry_bundle_id
            or row.run_id != record.registry_run_id
            or row.fingerprint != record.stable_fingerprint()
        ):
            raise VecOrchestrationError(
                f"stored VEC execution record identity mismatch: {row.bundle_id}"
            )
        records.append(record)
    return records


def execute_and_import(
    workflow: VecWorkflowRequest,
    *,
    clock: Callable[[], datetime] = _utc_now,
) -> VecWorkflowReceipt:
    """Run the complete one-click preflight, execution, validation, import pipeline."""

    request = build_preset_request(workflow.preset)
    stages: list[VecWorkflowStage] = []
    findings: list[str] = []

    registry_guard = _registry_guard_error(workflow)
    if registry_guard is not None:
        stages.append(_stage(VecWorkflowStageName.PREFLIGHT, "rejected", registry_guard))
        return _receipt(
            VecWorkflowStatus.PREFLIGHT_REJECTED,
            workflow,
            request,
            stages,
            findings=[registry_guard],
        )

    try:
        preflight = preflight_vec_run(
            workflow.input_root,
            workflow.vec_repo,
            workflow.tos_data_repo,
            request,
        )
    except (OSError, VecRunnerError) as exc:
        detail = f"preflight could not run: {exc}"
        stages.append(_stage(VecWorkflowStageName.PREFLIGHT, "failed", detail))
        return _receipt(
            VecWorkflowStatus.PREFLIGHT_UNAVAILABLE,
            workflow,
            request,
            stages,
            findings=[detail],
        )
    preflight_fingerprint = preflight.fingerprint()
    if preflight.status is not VecRunnerPreflightStatus.ACCEPTED:
        errors = [
            f"{item.code}: {item.message}"
            for item in preflight.findings
            if item.severity.value == "error"
        ][:_MAX_STAGE_ERRORS]
        detail = f"preflight {preflight.status.value}: " + ("; ".join(errors) or "no detail")
        stages.append(_stage(VecWorkflowStageName.PREFLIGHT, "rejected", detail))
        status = (
            VecWorkflowStatus.PREFLIGHT_REJECTED
            if preflight.status is VecRunnerPreflightStatus.REJECTED
            else VecWorkflowStatus.PREFLIGHT_UNAVAILABLE
        )
        return _receipt(
            status,
            workflow,
            request,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            findings=errors or [detail],
        )
    stages.append(
        _stage(
            VecWorkflowStageName.PREFLIGHT,
            "accepted",
            f"request-specific preflight accepted ({preflight_fingerprint[:12]})",
        )
    )

    try:
        receipt = run_vec_evaluator(
            workflow.input_root,
            workflow.vec_repo,
            workflow.tos_data_repo,
            workflow.output_dir,
            request,
        )
    except VecRunnerError as exc:
        terminal = exc.receipt
        status = (
            _TERMINAL_TO_WORKFLOW.get(terminal.status, VecWorkflowStatus.EXECUTION_FAILED)
            if terminal is not None
            else VecWorkflowStatus.EXECUTION_FAILED
        )
        detail = f"execution did not complete: {exc}"
        stages.append(_stage(VecWorkflowStageName.EXECUTION, "failed", detail))
        stages.append(_stage(VecWorkflowStageName.IMPORT, "skipped", "nothing to import"))
        return _receipt(
            status,
            workflow,
            request,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            receipt_fingerprint=terminal.fingerprint() if terminal is not None else None,
            findings=[detail],
        )
    stages.append(
        _stage(
            VecWorkflowStageName.EXECUTION,
            "completed",
            f"evaluator completed in {receipt.elapsed_seconds:.3f}s",
        )
    )

    try:
        _verify_outputs_on_disk(Path(workflow.output_dir).resolve(), receipt)
        _verify_repository_state(Path(workflow.vec_repo), receipt, "vec_env")
        _verify_repository_state(Path(workflow.tos_data_repo), receipt, "tos-data")
        _verify_raw_trace(Path(workflow.input_root), request)
    except VecOrchestrationError as exc:
        detail = f"post-execution validation failed: {exc}"
        stages.append(_stage(VecWorkflowStageName.VALIDATION, "rejected", detail))
        stages.append(_stage(VecWorkflowStageName.IMPORT, "skipped", "validation refused import"))
        return _receipt(
            VecWorkflowStatus.IMPORT_REJECTED,
            workflow,
            request,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            receipt_fingerprint=receipt.fingerprint(),
            output_fingerprint=receipt.output_fingerprint,
            findings=[detail],
        )
    stages.append(
        _stage(
            VecWorkflowStageName.VALIDATION,
            "accepted",
            "receipt, outputs, sources, and raw inputs re-verified unchanged",
        )
    )

    try:
        record, outcome = import_vec_execution(
            workflow.output_dir,
            workflow.registry_path,
            vec_repo=workflow.vec_repo,
            tos_data_repo=workflow.tos_data_repo,
            clock=clock,
        )
    except RegistryConflictError as exc:
        detail = f"registry identity conflict: {exc}"
        stages.append(_stage(VecWorkflowStageName.IMPORT, "rejected", detail))
        return _receipt(
            VecWorkflowStatus.IMPORT_CONFLICT,
            workflow,
            request,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            receipt_fingerprint=receipt.fingerprint(),
            output_fingerprint=receipt.output_fingerprint,
            findings=[detail],
        )
    except VecOrchestrationError as exc:
        detail = f"import refused: {exc}"
        stages.append(_stage(VecWorkflowStageName.IMPORT, "rejected", detail))
        return _receipt(
            VecWorkflowStatus.IMPORT_REJECTED,
            workflow,
            request,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            receipt_fingerprint=receipt.fingerprint(),
            output_fingerprint=receipt.output_fingerprint,
            findings=[detail],
        )
    import_kind = "idempotent re-import" if outcome.idempotent else "new registry record"
    stages.append(
        _stage(
            VecWorkflowStageName.IMPORT,
            "completed",
            f"{import_kind} {outcome.registry_run_id}",
        )
    )
    return VecWorkflowReceipt(
        status=VecWorkflowStatus.COMPLETED_IMPORTED,
        preset=workflow.preset,
        request_fingerprint=request.fingerprint(),
        stages=stages,
        preflight_fingerprint=preflight_fingerprint,
        receipt_fingerprint=receipt.fingerprint(),
        output_fingerprint=receipt.output_fingerprint,
        external_repositories_verified_unchanged=True,
        raw_inputs_verified_unchanged=True,
        import_outcome=outcome,
        import_record_stable_fingerprint=record.stable_fingerprint(),
        outputs=list(receipt.outputs),
        findings=findings,
    )


def vec_orchestration_contract() -> VecOrchestrationContract:
    """Return the machine-readable one-click workflow boundary."""

    return VecOrchestrationContract(
        presets=[preset_workload(preset) for preset in VecExecutionPreset],
        operations=[
            "build_preset_request",
            "preset_workload",
            "execute_and_import",
            "import_vec_execution",
            "list_imported_vec_executions",
        ],
        import_bindings=[
            "typed request and request fingerprint",
            "preflight fingerprint",
            "execution-receipt fingerprint and receipt file SHA-256",
            "output fingerprint plus per-file hashes and sizes",
            "exact audited vec_env and tos-data commits",
            "runtime evidence",
            "execution preset and evidence grade",
            "import timestamp and importer version",
        ],
        refusals=[
            "non-preset requests, arbitrary executables, flags, or command text",
            "failed, cancelled, timed-out, rejected, partial, or malformed executions",
            "mutated external repositories or raw inputs",
            "unsafe result, registry, or symlinked paths",
            "registry identity conflicts (visible RegistryConflictError)",
        ],
        interpretation_limits=[
            "imported executions are structural evidence; VEC-09 scientific admission "
            "remains unavailable because it binds the audited source run only",
            "deadline success is never physical completion",
            "action selection and eligible targets are never confirmed transfer",
            "aggregate energy is never per-task energy",
            "smoke output is never a scientific finding",
            "the protocol-seed run is distinct from the _s102 best-of-seeds evidence",
            "import grants no publication permission",
        ],
    )


def _record_limitations(preset: VecExecutionPreset) -> list[str]:
    limitations = [
        "Imported execution evidence is structural; scientific metric admission and "
        "publication permission are separate, unavailable decisions.",
        "Deadline success, action selection, and aggregate energy retain their audited "
        "source meanings.",
    ]
    if preset is VecExecutionPreset.SMOKE_TWO_STEP:
        limitations.append(
            "A two-step smoke run demonstrates safe execution only and must not be "
            "presented as reproduction or dissertation performance evidence."
        )
    else:
        limitations.append(
            "The full protocol-seed run is not graded reproduction until VEC-08 "
            "verification, and the accepted CPU/JAX tolerance is not generalised to "
            "other platforms, policies, or scenarios."
        )
    return limitations


def _stage(stage: VecWorkflowStageName, state: str, detail: str) -> VecWorkflowStage:
    return VecWorkflowStage(
        stage=stage,
        state=VecWorkflowStageState(state),
        detail=detail[:2_000],
    )


def _receipt(
    status: VecWorkflowStatus,
    workflow: VecWorkflowRequest,
    request: VecRunRequest,
    stages: list[VecWorkflowStage],
    *,
    preflight_fingerprint: str | None = None,
    receipt_fingerprint: str | None = None,
    output_fingerprint: str | None = None,
    findings: list[str] | None = None,
) -> VecWorkflowReceipt:
    return VecWorkflowReceipt(
        status=status,
        preset=workflow.preset,
        request_fingerprint=request.fingerprint(),
        stages=stages,
        preflight_fingerprint=preflight_fingerprint,
        receipt_fingerprint=receipt_fingerprint,
        output_fingerprint=output_fingerprint,
        external_repositories_verified_unchanged=False,
        raw_inputs_verified_unchanged=False,
        findings=(findings or [])[:32],
    )


def _registry_guard_error(workflow: VecWorkflowRequest) -> str | None:
    try:
        _admit_registry_path(
            workflow.registry_path,
            Path(workflow.output_dir).resolve(strict=False),
            vec_repo=Path(workflow.vec_repo).resolve(strict=False),
            tos_data_repo=Path(workflow.tos_data_repo).resolve(strict=False),
            require_parent=True,
        )
    except VecOrchestrationError as exc:
        return f"registry destination rejected before execution: {exc}"
    return None


def _admit_registry_path(
    registry_path: str | Path,
    result_dir: Path,
    *,
    vec_repo: Path | None = None,
    tos_data_repo: Path | None = None,
    require_parent: bool = True,
) -> Path:
    registry_file = Path(registry_path).resolve(strict=False)
    if registry_file.is_dir():
        raise VecOrchestrationError("registry path must name a SQLite file, not a directory")
    if registry_file.exists() and Path(registry_path).is_symlink():
        raise VecOrchestrationError("registry path must not be a symbolic link")
    parent = registry_file.parent
    if require_parent and not parent.is_dir():
        raise VecOrchestrationError("registry parent directory must already exist")
    protected = [result_dir]
    if vec_repo is not None:
        protected.append(vec_repo)
    if tos_data_repo is not None:
        protected.append(tos_data_repo)
    for root in protected:
        if registry_file == root or root in registry_file.parents:
            raise VecOrchestrationError(
                "registry must not live inside the result directory or either external repository"
            )
    return registry_file


def _load_receipt(root: Path) -> VecExecutionReceipt:
    receipt_path = root / _RECEIPT_FILE
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise VecOrchestrationError("execution_receipt.json is missing or unsafe")
    if receipt_path.stat().st_size > _RECEIPT_LIMIT_BYTES:
        raise VecOrchestrationError("execution receipt exceeds the bounded size")
    try:
        return VecExecutionReceipt.model_validate_json(receipt_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VecOrchestrationError(f"execution receipt is not valid: {exc}") from exc


def _verify_outputs_on_disk(root: Path, receipt: VecExecutionReceipt) -> None:
    for evidence in receipt.outputs:
        try:
            path = _safe_file_under(root, evidence.path, label="published output")
            size = path.stat().st_size
            digest = _sha256_file(path)
        except OSError as exc:
            raise VecOrchestrationError(
                f"published output could not be read safely: {evidence.path}"
            ) from exc
        if size != evidence.size_bytes or digest != evidence.sha256:
            raise VecOrchestrationError(
                f"published output does not match its receipt identity: {evidence.path}"
            )


def _verify_repository_state(
    repo: Path,
    receipt: VecExecutionReceipt,
    name: str,
) -> None:
    evidence = next(
        (item for item in receipt.repositories if item.repository == name),
        None,
    )
    if (
        evidence is None
        or evidence.worktree_head_after is None
        or evidence.origin_main_after is None
        or evidence.clean_after is not True
    ):
        raise VecOrchestrationError(f"receipt lacks verified post-run state for {name}")
    if repo.is_symlink() or not repo.is_dir():
        raise VecOrchestrationError(f"current {name} repository path is missing or unsafe")
    git = shutil.which("git")
    if git is None:
        raise VecOrchestrationError("git executable is required to verify repository state")
    try:
        head = _git_text(git, repo, "rev-parse", "HEAD")
        origin_main = _git_text(git, repo, "rev-parse", "refs/remotes/origin/main")
        status = _git_text(git, repo, "status", "--porcelain=v1", "--untracked-files=all")
    except (OSError, subprocess.SubprocessError) as exc:
        raise VecOrchestrationError(f"current {name} repository state could not be read") from exc
    if head != evidence.worktree_head_after or origin_main != evidence.origin_main_after or status:
        raise VecOrchestrationError(
            f"current {name} state does not match the verified post-run receipt state"
        )


def _verify_raw_trace(input_root: Path, request: VecRunRequest) -> None:
    if input_root.is_symlink() or not input_root.is_dir():
        raise VecOrchestrationError("raw input root is missing or unsafe")
    try:
        trace = _safe_file_under(input_root.resolve(), request.trace_file, label="raw input trace")
        digest = _sha256_file(trace)
    except OSError as exc:
        raise VecOrchestrationError("raw input trace could not be read safely") from exc
    if digest != request.trace_sha256:
        raise VecOrchestrationError("raw input trace hash changed after execution")


def _safe_file_under(root: Path, relative_path: str, *, label: str) -> Path:
    """Resolve one existing regular file while rejecting every symlink component."""

    candidate = root
    for part in Path(relative_path).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise VecOrchestrationError(f"{label} is missing or unsafe: {relative_path}")
    resolved = candidate.resolve(strict=False)
    if root not in resolved.parents or not resolved.is_file():
        raise VecOrchestrationError(f"{label} is missing or unsafe: {relative_path}")
    return resolved


def _validation_report_json(record: VecExecutionImportRecord) -> str:
    checks = {
        "receipt_status": "completed",
        "outputs_reverified_on_disk": True,
        "external_repositories_modified": False,
        "raw_inputs_modified": False,
        "preset": record.preset.value,
        "evidence_grade": record.evidence_grade.value,
        "scientific_admission_status": record.scientific_admission_status,
    }
    return json.dumps(checks, sort_keys=True, separators=(",", ":"))


def _git_text(git: str, repo: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603 - resolved Git executable and fixed read-only argv
        [git, "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
