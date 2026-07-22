"""Tests for the one-click VEC execute-and-import orchestration."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.integration.vec_orchestration import (
    VecEvidenceGrade,
    VecExecutionImportRecord,
    VecExecutionPreset,
    VecImportOutcome,
    VecOrchestrationError,
    VecWorkflowReceipt,
    VecWorkflowRequest,
    VecWorkflowStage,
    VecWorkflowStageName,
    VecWorkflowStageState,
    VecWorkflowStatus,
    build_preset_request,
    execute_and_import,
    import_vec_execution,
    list_imported_vec_executions,
    match_preset,
    preset_evidence_grade,
    preset_workload,
    vec_orchestration_contract,
)
from traffictwin.integration.vec_orchestration import service as orchestration_service
from traffictwin.integration.vec_runner import (
    PINNED_TOS_DATA_COMMIT,
    PINNED_VEC_ENV_COMMIT,
    VecExecutionReceipt,
    VecRepositoryEvidence,
    VecRunnerError,
    VecRunnerFileEvidence,
    VecRunnerPreflightReport,
    VecRunnerPreflightStatus,
    VecRuntimeEvidence,
    VecTerminalStatus,
)
from traffictwin.integration.vec_runner.models import output_fingerprint
from traffictwin.storage.registry import Registry, RegistryConflictError

FIXED_TIME = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
FAKE_HEAD = "1" * 40


def fixed_clock() -> datetime:
    return FIXED_TIME


def make_runtime() -> VecRuntimeEvidence:
    return VecRuntimeEvidence(
        python="3.12.0",
        numpy="1.26.4",
        jax="0.4.30",
        jaxlib="0.4.30",
        jax_backend="cpu",
        jax_device_count=1,
        platform="TestOS",
        machine="test64",
        processor="test",
        environment_sha256="0" * 64,
    )


def make_repository(name: str) -> VecRepositoryEvidence:
    commit = PINNED_VEC_ENV_COMMIT if name == "vec_env" else PINNED_TOS_DATA_COMMIT
    return VecRepositoryEvidence(
        repository=name,
        audited_commit=commit,
        worktree_head_before=FAKE_HEAD,
        worktree_head_after=FAKE_HEAD,
        origin_main_before=commit,
        origin_main_after=commit,
        clean_before=True,
        clean_after=True,
        source_files=[],
    )


def file_evidence(path: str, content: bytes) -> VecRunnerFileEvidence:
    return VecRunnerFileEvidence(
        path=path,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type="application/octet-stream",
        read_only=True,
    )


def make_completed_receipt(
    result_dir: Path,
    *,
    preset: VecExecutionPreset = VecExecutionPreset.SMOKE_TWO_STEP,
) -> VecExecutionReceipt:
    """Write a synthetic published result directory and matching completed receipt."""

    result_dir.mkdir(parents=True, exist_ok=True)
    contents = {
        "run.json": b'{"completion": 1.0, "total_tasks": 1}',
        "per-step.npz": b"synthetic per-step bytes",
        "per-task.npz": b"synthetic per-task bytes",
    }
    outputs = []
    for name, payload in sorted(contents.items()):
        (result_dir / name).write_bytes(payload)
        outputs.append(file_evidence(name, payload))
    request = build_preset_request(preset)
    receipt = VecExecutionReceipt(
        status=VecTerminalStatus.COMPLETED,
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint="2" * 64,
        argv=["python", "eval_sumo_stage1_mc.py"],
        started_at_utc=FIXED_TIME.isoformat(),
        finished_at_utc=FIXED_TIME.isoformat(),
        elapsed_seconds=1.5,
        exit_code=0,
        timed_out=False,
        cancellation_requested=False,
        runtime=make_runtime(),
        repositories=[make_repository("vec_env"), make_repository("tos-data")],
        inputs_before=[],
        inputs_after=[],
        logs=[],
        stdout_excerpt="",
        stderr_excerpt="",
        outputs=outputs,
        findings=[],
        output_fingerprint=output_fingerprint(outputs),
        external_repositories_modified=False,
        raw_inputs_modified=False,
        published=True,
    )
    (result_dir / "execution_receipt.json").write_text(
        receipt.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return receipt


def make_failed_receipt(result_dir: Path) -> VecExecutionReceipt:
    result_dir.mkdir(parents=True, exist_ok=True)
    request = build_preset_request(VecExecutionPreset.SMOKE_TWO_STEP)
    receipt = VecExecutionReceipt(
        status=VecTerminalStatus.FAILED,
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint="2" * 64,
        argv=["python", "eval_sumo_stage1_mc.py"],
        started_at_utc=FIXED_TIME.isoformat(),
        finished_at_utc=FIXED_TIME.isoformat(),
        elapsed_seconds=0.5,
        exit_code=1,
        timed_out=False,
        cancellation_requested=False,
        runtime=make_runtime(),
        repositories=[make_repository("vec_env"), make_repository("tos-data")],
        inputs_before=[],
        inputs_after=[],
        logs=[],
        stdout_excerpt="",
        stderr_excerpt="boom",
        outputs=[],
        findings=[],
        output_fingerprint=None,
        external_repositories_modified=False,
        raw_inputs_modified=False,
        published=False,
    )
    (result_dir / "execution_receipt.json").write_text(
        receipt.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return receipt


# --- presets and contract -------------------------------------------------


def test_preset_requests_are_exact_and_deterministic() -> None:
    smoke = build_preset_request(VecExecutionPreset.SMOKE_TWO_STEP)
    full = build_preset_request(VecExecutionPreset.FULL_REPRODUCTION)

    assert smoke.max_steps == 2
    assert full.max_steps == 32_400
    for request in (smoke, full):
        assert request.trace_file == "traces/trace_we_fullrsu.npz"
        assert request.actor_id == "ukfleettrain_mappo_model_c_17"
        assert request.evaluator_seed == 0
        assert request.fleet.value == "uk2030"
        assert request.fleet_seed == 0
    assert (
        smoke.fingerprint() == build_preset_request(VecExecutionPreset.SMOKE_TWO_STEP).fingerprint()
    )
    assert smoke.fingerprint() != full.fingerprint()


def test_match_preset_requires_exact_fingerprint() -> None:
    smoke = build_preset_request(VecExecutionPreset.SMOKE_TWO_STEP)
    assert match_preset(smoke) is VecExecutionPreset.SMOKE_TWO_STEP
    modified = smoke.model_copy(update={"evaluator_seed": 7})
    assert match_preset(modified) is None


def test_preset_workload_is_factual() -> None:
    workload = preset_workload(VecExecutionPreset.FULL_REPRODUCTION)
    assert workload.evaluator_steps == 32_400
    assert workload.foreground_only is True
    assert workload.background_execution is False
    assert "_s102" in workload.description
    assert (
        preset_evidence_grade(VecExecutionPreset.SMOKE_TWO_STEP)
        is VecEvidenceGrade.STRUCTURAL_SMOKE_EXECUTION
    )
    assert (
        preset_evidence_grade(VecExecutionPreset.FULL_REPRODUCTION)
        is VecEvidenceGrade.FULL_PROTOCOL_EXECUTION_UNVERIFIED_REPRODUCTION
    )


def test_contract_lists_refusals_and_limits() -> None:
    contract = vec_orchestration_contract()
    assert len(contract.presets) == 2
    assert any("never per-task energy" in item for item in contract.interpretation_limits)
    assert contract.fingerprint() == vec_orchestration_contract().fingerprint()


def test_workflow_request_requires_full_run_confirmation(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="confirm_full_run"):
        VecWorkflowRequest(
            preset=VecExecutionPreset.FULL_REPRODUCTION,
            input_root=str(tmp_path),
            vec_repo=str(tmp_path),
            tos_data_repo=str(tmp_path),
            output_dir=str(tmp_path / "out"),
            registry_path=str(tmp_path / "registry.sqlite"),
        )
    with pytest.raises(ValidationError, match="surprise"):
        VecWorkflowRequest(
            preset=VecExecutionPreset.SMOKE_TWO_STEP,
            input_root=str(tmp_path),
            vec_repo=str(tmp_path),
            tos_data_repo=str(tmp_path),
            output_dir=str(tmp_path / "out"),
            registry_path=str(tmp_path / "registry.sqlite"),
            surprise=True,  # type: ignore[call-arg]
        )


# --- import contract ------------------------------------------------------


def test_import_completed_receipt_creates_exactly_once(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    receipt = make_completed_receipt(result_dir)
    registry_path = tmp_path / "registry.sqlite"

    record, outcome = import_vec_execution(result_dir, registry_path, clock=fixed_clock)

    assert outcome.created is True
    assert outcome.idempotent is False
    assert outcome.registry_run_id == f"vec:exec:{receipt.fingerprint()[:16]}"
    assert record.preset is VecExecutionPreset.SMOKE_TWO_STEP
    assert record.evidence_grade is VecEvidenceGrade.STRUCTURAL_SMOKE_EXECUTION
    assert record.scientific_admission_status == "unavailable"
    assert "vec09_admission_binds_audited_source_run_only" in record.scientific_admission_reasons
    assert record.deadline_success_is_physical_completion is False
    assert record.action_selection_is_confirmed_transfer is False
    assert record.aggregate_energy_is_per_task_energy is False

    registry = Registry(registry_path)
    run = registry.get_run(outcome.registry_run_id)
    assert run.status.value == "completed"
    assert run.environment_commit == PINNED_VEC_ENV_COMMIT

    stored = json.loads(
        Registry(registry_path)
        ._connect()
        .execute(
            "SELECT manifest_json FROM bundle_imports WHERE bundle_id = ?",
            (outcome.registry_bundle_id,),
        )
        .fetchone()["manifest_json"]
    )
    assert stored["evidence_grade"] == "structural_smoke_execution"
    assert stored["publication_status"] == "not_authorised_by_execution"


def test_repeated_import_is_idempotent_by_stable_fingerprint(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    make_completed_receipt(result_dir)
    registry_path = tmp_path / "registry.sqlite"

    first_record, first = import_vec_execution(result_dir, registry_path, clock=fixed_clock)
    later = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)
    second_record, second = import_vec_execution(
        result_dir,
        registry_path,
        clock=lambda: later,
    )

    assert first.created is True
    assert second.created is False
    assert second.idempotent is True
    assert first.stable_fingerprint == second.stable_fingerprint
    assert first_record.stable_fingerprint() == second_record.stable_fingerprint()
    assert first_record.imported_at_utc != second_record.imported_at_utc


def test_imported_execution_catalog_revalidates_registry_identity(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    make_completed_receipt(result_dir)
    registry_path = tmp_path / "registry.sqlite"
    record, _ = import_vec_execution(result_dir, registry_path, clock=fixed_clock)

    assert list_imported_vec_executions(registry_path) == [record]

    with Registry(registry_path)._connect() as conn:  # noqa: SLF001 - corrupt-record fixture
        conn.execute(
            "UPDATE bundle_imports SET fingerprint = ? WHERE bundle_id = ?",
            ("d" * 64, record.registry_bundle_id),
        )
    with pytest.raises(VecOrchestrationError, match="identity mismatch"):
        list_imported_vec_executions(registry_path)


def test_tampered_or_missing_outputs_never_import(tmp_path: Path) -> None:
    tampered = tmp_path / "tampered"
    make_completed_receipt(tampered)
    (tampered / "per-step.npz").chmod(0o644)
    (tampered / "per-step.npz").write_bytes(b"mutated bytes")
    registry_path = tmp_path / "registry.sqlite"
    with pytest.raises(VecOrchestrationError, match="does not match its receipt identity"):
        import_vec_execution(tampered, registry_path, clock=fixed_clock)

    missing = tmp_path / "missing"
    make_completed_receipt(missing)
    (missing / "run.json").unlink()
    with pytest.raises(VecOrchestrationError, match="missing or unsafe"):
        import_vec_execution(missing, registry_path, clock=fixed_clock)

    assert not registry_path.exists()


def test_result_directory_and_output_symlinks_never_import(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    make_completed_receipt(result_dir)
    registry_path = tmp_path / "registry.sqlite"

    result_link = tmp_path / "result-link"
    result_link.symlink_to(result_dir, target_is_directory=True)
    with pytest.raises(VecOrchestrationError, match="non-symlink directory"):
        import_vec_execution(result_link, registry_path, clock=fixed_clock)

    original = result_dir / "per-step.npz"
    replacement = result_dir / "per-step-copy.npz"
    replacement.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(replacement.name)
    with pytest.raises(VecOrchestrationError, match="missing or unsafe"):
        import_vec_execution(result_dir, registry_path, clock=fixed_clock)

    assert not registry_path.exists()


def test_failed_receipt_and_malformed_receipt_never_import(tmp_path: Path) -> None:
    failed = tmp_path / "failed"
    make_failed_receipt(failed)
    registry_path = tmp_path / "registry.sqlite"
    with pytest.raises(VecOrchestrationError, match="only completed executions"):
        import_vec_execution(failed, registry_path, clock=fixed_clock)

    malformed = tmp_path / "malformed"
    malformed.mkdir()
    (malformed / "execution_receipt.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(VecOrchestrationError, match="not valid"):
        import_vec_execution(malformed, registry_path, clock=fixed_clock)

    absent = tmp_path / "absent"
    absent.mkdir()
    with pytest.raises(VecOrchestrationError, match="missing or unsafe"):
        import_vec_execution(absent, registry_path, clock=fixed_clock)

    assert not registry_path.exists()


def test_non_preset_request_is_refused(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    receipt = make_completed_receipt(result_dir)
    request = receipt.request.model_copy(update={"evaluator_seed": 9})
    altered = receipt.model_copy(
        update={"request": request, "request_fingerprint": request.fingerprint()}
    )
    (result_dir / "execution_receipt.json").chmod(0o644)
    (result_dir / "execution_receipt.json").write_text(
        altered.model_dump_json(indent=2), encoding="utf-8"
    )
    with pytest.raises(VecOrchestrationError, match="closed execution preset"):
        import_vec_execution(result_dir, tmp_path / "registry.sqlite", clock=fixed_clock)


def test_unsafe_registry_destinations_are_refused(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    make_completed_receipt(result_dir)

    with pytest.raises(VecOrchestrationError, match="must not live inside"):
        import_vec_execution(result_dir, result_dir / "registry.sqlite", clock=fixed_clock)
    with pytest.raises(VecOrchestrationError, match="not a directory"):
        import_vec_execution(result_dir, tmp_path, clock=fixed_clock)
    with pytest.raises(VecOrchestrationError, match="parent directory"):
        import_vec_execution(
            result_dir,
            tmp_path / "does-not-exist" / "registry.sqlite",
            clock=fixed_clock,
        )


def test_registry_identity_conflict_fails_visibly(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    make_completed_receipt(result_dir)
    registry_path = tmp_path / "registry.sqlite"
    registry = Registry(registry_path)
    _, outcome = import_vec_execution(result_dir, registry_path, clock=fixed_clock)

    with registry._connect() as conn:  # noqa: SLF001 - direct fixture surgery for the conflict case
        conn.execute(
            "UPDATE bundle_imports SET fingerprint = ? WHERE bundle_id = ?",
            ("d" * 64, outcome.registry_bundle_id),
        )
    with pytest.raises(RegistryConflictError):
        import_vec_execution(result_dir, registry_path, clock=fixed_clock)


def test_import_record_semantic_guards_are_literal(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    make_completed_receipt(result_dir)
    record, _ = import_vec_execution(result_dir, tmp_path / "registry.sqlite", clock=fixed_clock)
    payload = record.model_dump(mode="json")

    payload["deadline_success_is_physical_completion"] = True
    with pytest.raises(ValidationError, match="deadline_success_is_physical_completion"):
        VecExecutionImportRecord.model_validate(payload)

    payload["deadline_success_is_physical_completion"] = False
    payload["scientific_admission_status"] = "available"
    with pytest.raises(ValidationError, match="scientific_admission_status"):
        VecExecutionImportRecord.model_validate(payload)

    payload["scientific_admission_status"] = "unavailable"
    payload["scientific_admission_reasons"] = ["something else"]
    with pytest.raises(ValidationError, match="standing codes"):
        VecExecutionImportRecord.model_validate(payload)

    payload["scientific_admission_reasons"] = record.scientific_admission_reasons
    payload["evidence_grade"] = "full_protocol_execution_unverified_reproduction"
    with pytest.raises(ValidationError, match="requires evidence grade"):
        VecExecutionImportRecord.model_validate(payload)


# --- workflow gating ------------------------------------------------------


def workflow_request(tmp_path: Path, **overrides: object) -> VecWorkflowRequest:
    payload: dict[str, object] = {
        "preset": VecExecutionPreset.SMOKE_TWO_STEP,
        "input_root": str(tmp_path / "inputs"),
        "vec_repo": str(tmp_path / "vec_env"),
        "tos_data_repo": str(tmp_path / "tos-data"),
        "output_dir": str(tmp_path / "out"),
        "registry_path": str(tmp_path / "registry.sqlite"),
    }
    payload.update(overrides)
    for key in ("input_root", "vec_repo", "tos_data_repo"):
        Path(str(payload[key])).mkdir(parents=True, exist_ok=True)
    return VecWorkflowRequest(**payload)


def accepted_preflight(preset: VecExecutionPreset) -> VecRunnerPreflightReport:
    request = build_preset_request(preset)
    return VecRunnerPreflightReport(
        status=VecRunnerPreflightStatus.ACCEPTED,
        request=request,
        request_fingerprint=request.fingerprint(),
        repositories=[make_repository("vec_env"), make_repository("tos-data")],
        inputs=[],
        runtime=make_runtime(),
        trace_steps=2,
        trace_slots=139,
        findings=[],
    )


def rejected_preflight(preset: VecExecutionPreset) -> VecRunnerPreflightReport:
    request = build_preset_request(preset)
    return VecRunnerPreflightReport(
        status=VecRunnerPreflightStatus.REJECTED,
        request=request,
        request_fingerprint=request.fingerprint(),
        repositories=[],
        inputs=[],
        runtime=None,
        findings=[
            {
                "code": "VEC_TRACE_MISSING",
                "severity": "error",
                "message": "trace not present",
            }
        ],
    )


def test_rejected_preflight_performs_no_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = workflow_request(tmp_path)

    monkeypatch.setattr(
        orchestration_service,
        "preflight_vec_run",
        lambda *args, **kwargs: rejected_preflight(VecExecutionPreset.SMOKE_TWO_STEP),
    )

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("execution must not run after rejected preflight")

    monkeypatch.setattr(orchestration_service, "run_vec_evaluator", forbidden)
    receipt = execute_and_import(request)

    assert receipt.status is VecWorkflowStatus.PREFLIGHT_REJECTED
    assert receipt.import_outcome is None
    assert "VEC_TRACE_MISSING" in receipt.findings[0]
    assert not Path(request.registry_path).exists()
    assert not Path(request.output_dir).exists()


def test_unavailable_preflight_performs_no_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = workflow_request(tmp_path)

    def unavailable(*args: object, **kwargs: object) -> object:
        raise OSError("repository unavailable")

    monkeypatch.setattr(orchestration_service, "preflight_vec_run", unavailable)
    monkeypatch.setattr(
        orchestration_service,
        "run_vec_evaluator",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not execute")),
    )
    receipt = execute_and_import(request)
    assert receipt.status is VecWorkflowStatus.PREFLIGHT_UNAVAILABLE
    assert receipt.import_outcome is None


def test_unsafe_registry_rejected_before_any_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = workflow_request(
        tmp_path,
        registry_path=str(tmp_path / "vec_env" / "registry.sqlite"),
    )
    monkeypatch.setattr(
        orchestration_service,
        "preflight_vec_run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("preflight must not run")),
    )
    receipt = execute_and_import(request)
    assert receipt.status is VecWorkflowStatus.PREFLIGHT_REJECTED
    assert "registry destination rejected before execution" in receipt.findings[0]


def test_failed_execution_never_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = workflow_request(tmp_path)
    monkeypatch.setattr(
        orchestration_service,
        "preflight_vec_run",
        lambda *a, **k: accepted_preflight(VecExecutionPreset.SMOKE_TWO_STEP),
    )
    terminal = make_failed_receipt(tmp_path / "scratch")

    def failing_run(*args: object, **kwargs: object) -> object:
        raise VecRunnerError("evaluator exited with 1", receipt=terminal)

    monkeypatch.setattr(orchestration_service, "run_vec_evaluator", failing_run)
    receipt = execute_and_import(request)

    assert receipt.status is VecWorkflowStatus.EXECUTION_FAILED
    assert receipt.import_outcome is None
    assert [stage.stage for stage in receipt.stages][-1] is VecWorkflowStageName.IMPORT
    assert receipt.stages[-1].state is VecWorkflowStageState.SKIPPED
    assert not Path(request.registry_path).exists()


def test_completed_workflow_imports_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = workflow_request(tmp_path)
    monkeypatch.setattr(
        orchestration_service,
        "preflight_vec_run",
        lambda *a, **k: accepted_preflight(VecExecutionPreset.SMOKE_TWO_STEP),
    )

    def fake_run(
        input_root: object,
        vec_repo: object,
        tos_repo: object,
        output_dir: object,
        run_request: object,
    ) -> VecExecutionReceipt:
        return make_completed_receipt(Path(str(output_dir)))

    monkeypatch.setattr(orchestration_service, "run_vec_evaluator", fake_run)
    monkeypatch.setattr(orchestration_service, "_verify_repository_state", lambda *a, **k: None)
    monkeypatch.setattr(orchestration_service, "_verify_raw_trace", lambda *a, **k: None)

    receipt = execute_and_import(request, clock=fixed_clock)

    assert receipt.status is VecWorkflowStatus.COMPLETED_IMPORTED
    assert receipt.import_outcome is not None
    assert receipt.import_outcome.created is True
    assert receipt.external_repositories_verified_unchanged is True
    assert receipt.raw_inputs_verified_unchanged is True
    assert [stage.state.value for stage in receipt.stages] == [
        "accepted",
        "completed",
        "accepted",
        "completed",
    ]
    assert len(receipt.outputs) == 3

    registry = Registry(request.registry_path)
    assert registry.get_run(receipt.import_outcome.registry_run_id) is not None


def test_mutated_output_after_execution_blocks_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = workflow_request(tmp_path)
    monkeypatch.setattr(
        orchestration_service,
        "preflight_vec_run",
        lambda *a, **k: accepted_preflight(VecExecutionPreset.SMOKE_TWO_STEP),
    )

    def fake_run(*args: object, **kwargs: object) -> VecExecutionReceipt:
        output_dir = Path(str(args[3]))
        receipt = make_completed_receipt(output_dir)
        (output_dir / "run.json").chmod(0o644)
        (output_dir / "run.json").write_text("{}", encoding="utf-8")
        return receipt

    monkeypatch.setattr(orchestration_service, "run_vec_evaluator", fake_run)
    receipt = execute_and_import(request, clock=fixed_clock)

    assert receipt.status is VecWorkflowStatus.IMPORT_REJECTED
    assert receipt.import_outcome is None
    assert not Path(request.registry_path).exists()


# --- source verification helpers -----------------------------------------


def make_git_repo(path: Path) -> str:
    git = shutil.which("git")
    assert git is not None
    path.mkdir(parents=True)
    for args in (
        ("init", "--quiet"),
        ("config", "user.email", "test@example.invalid"),
        ("config", "user.name", "Test"),
        ("commit", "--quiet", "--allow-empty", "-m", "initial"),
    ):
        subprocess.run(  # noqa: S603 - fixed test-local Git argv
            [git, "-C", str(path), *args],
            check=True,
            capture_output=True,
        )
    return subprocess.run(  # noqa: S603 - fixed test-local Git argv
        [git, "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_repository_state_verification_detects_drift(tmp_path: Path) -> None:
    head = make_git_repo(tmp_path / "repo")
    result_dir = tmp_path / "result"
    receipt = make_completed_receipt(result_dir)
    evidence = make_repository("vec_env").model_copy(
        update={
            "worktree_head_before": head,
            "worktree_head_after": head,
            "origin_main_before": head,
            "origin_main_after": head,
        }
    )
    git = shutil.which("git")
    assert git is not None
    subprocess.run(  # noqa: S603 - fixed test-local Git argv
        [git, "-C", str(tmp_path / "repo"), "update-ref", "refs/remotes/origin/main", head],
        check=True,
        capture_output=True,
    )
    receipt = receipt.model_copy(update={"repositories": [evidence, make_repository("tos-data")]})

    orchestration_service._verify_repository_state(tmp_path / "repo", receipt, "vec_env")

    (tmp_path / "repo" / "dirty.txt").write_text("drift", encoding="utf-8")
    with pytest.raises(VecOrchestrationError, match="does not match the verified post-run"):
        orchestration_service._verify_repository_state(tmp_path / "repo", receipt, "vec_env")


def test_raw_trace_verification_detects_change(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    trace = input_root / "traces" / "trace_we_fullrsu.npz"
    trace.parent.mkdir(parents=True)
    trace.write_bytes(b"trace bytes")
    request = build_preset_request(VecExecutionPreset.SMOKE_TWO_STEP).model_copy(
        update={"trace_sha256": hashlib.sha256(b"trace bytes").hexdigest()}
    )
    orchestration_service._verify_raw_trace(input_root, request)

    trace.write_bytes(b"changed bytes")
    with pytest.raises(VecOrchestrationError, match="hash changed"):
        orchestration_service._verify_raw_trace(input_root, request)


def test_raw_trace_verification_rejects_symlink_replacement(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    trace = input_root / "traces" / "trace_we_fullrsu.npz"
    trace.parent.mkdir(parents=True)
    replacement = trace.parent / "replacement.npz"
    replacement.write_bytes(b"trace bytes")
    trace.symlink_to(replacement.name)
    request = build_preset_request(VecExecutionPreset.SMOKE_TWO_STEP).model_copy(
        update={"trace_sha256": hashlib.sha256(b"trace bytes").hexdigest()}
    )

    with pytest.raises(VecOrchestrationError, match="missing or unsafe"):
        orchestration_service._verify_raw_trace(input_root, request)


# --- CLI ------------------------------------------------------------------


def test_cli_import_result_success_and_idempotency(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    make_completed_receipt(result_dir)
    registry_path = tmp_path / "registry.sqlite"
    runner = CliRunner()

    first = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "import-result",
            "--result-dir",
            str(result_dir),
            "--registry",
            str(registry_path),
        ],
    )
    assert first.exit_code == 0, first.output
    assert "import_created: True" in first.output

    second = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "import-result",
            "--result-dir",
            str(result_dir),
            "--registry",
            str(registry_path),
        ],
    )
    assert second.exit_code == 0, second.output
    assert "import_idempotent: True" in second.output


def test_cli_import_result_refuses_tampered_outputs(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    make_completed_receipt(result_dir)
    (result_dir / "per-task.npz").chmod(0o644)
    (result_dir / "per-task.npz").write_bytes(b"mutated")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "import-result",
            "--result-dir",
            str(result_dir),
            "--registry",
            str(tmp_path / "registry.sqlite"),
        ],
    )
    assert result.exit_code == 1
    assert "does not match its receipt identity" in result.output


def test_cli_execute_and_import_requires_full_confirmation(tmp_path: Path) -> None:
    for name in ("inputs", "vec_env", "tos-data"):
        (tmp_path / name).mkdir()
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "execute-and-import",
            "--preset",
            "full_reproduction",
            "--input-root",
            str(tmp_path / "inputs"),
            "--vec-repo",
            str(tmp_path / "vec_env"),
            "--tos-data-repo",
            str(tmp_path / "tos-data"),
            "--output",
            str(tmp_path / "out"),
            "--registry",
            str(tmp_path / "registry.sqlite"),
        ],
    )
    assert result.exit_code == 1
    assert "confirm_full_run" in result.output


def test_cli_execute_and_import_prints_stages_and_fails_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("inputs", "vec_env", "tos-data"):
        (tmp_path / name).mkdir()

    request = build_preset_request(VecExecutionPreset.SMOKE_TWO_STEP)
    failure = VecWorkflowReceipt(
        status=VecWorkflowStatus.PREFLIGHT_REJECTED,
        preset=VecExecutionPreset.SMOKE_TWO_STEP,
        request_fingerprint=request.fingerprint(),
        stages=[
            VecWorkflowStage(
                stage=VecWorkflowStageName.PREFLIGHT,
                state=VecWorkflowStageState.REJECTED,
                detail="preflight rejected: trace missing",
            )
        ],
        external_repositories_verified_unchanged=False,
        raw_inputs_verified_unchanged=False,
        findings=["VEC_TRACE_MISSING: trace missing"],
    )
    monkeypatch.setattr("traffictwin.cli.execute_and_import", lambda workflow: failure)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "execute-and-import",
            "--preset",
            "smoke_two_step",
            "--input-root",
            str(tmp_path / "inputs"),
            "--vec-repo",
            str(tmp_path / "vec_env"),
            "--tos-data-repo",
            str(tmp_path / "tos-data"),
            "--output",
            str(tmp_path / "out"),
            "--registry",
            str(tmp_path / "registry.sqlite"),
        ],
    )
    assert result.exit_code == 1
    assert "preflight: rejected" in result.output
    assert "workflow: preflight_rejected" in result.output

    success = failure.model_copy(
        update={
            "status": VecWorkflowStatus.COMPLETED_IMPORTED,
            "stages": [
                VecWorkflowStage(
                    stage=VecWorkflowStageName.IMPORT,
                    state=VecWorkflowStageState.COMPLETED,
                    detail="new registry record vec:exec:abc",
                )
            ],
            "preflight_fingerprint": "3" * 64,
            "receipt_fingerprint": "4" * 64,
            "output_fingerprint": "5" * 64,
            "external_repositories_verified_unchanged": True,
            "raw_inputs_verified_unchanged": True,
            "import_outcome": VecImportOutcome(
                created=True,
                idempotent=False,
                registry_run_id="vec:exec:abc",
                registry_bundle_id="vec-exec:abc",
                stable_fingerprint="6" * 64,
                registry_reference="registry.sqlite",
            ),
            "import_record_stable_fingerprint": "6" * 64,
            "findings": [],
        }
    )
    monkeypatch.setattr("traffictwin.cli.execute_and_import", lambda workflow: success)
    result = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "execute-and-import",
            "--preset",
            "smoke_two_step",
            "--input-root",
            str(tmp_path / "inputs"),
            "--vec-repo",
            str(tmp_path / "vec_env"),
            "--tos-data-repo",
            str(tmp_path / "tos-data"),
            "--output",
            str(tmp_path / "out"),
            "--registry",
            str(tmp_path / "registry.sqlite"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "workflow: completed_imported" in result.output
    assert "import_created: True" in result.output
