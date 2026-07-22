"""Controlled one-click SUMO execution, validation, and automatic import.

The service composes, in order: registry/output admission, controlled runtime
discovery, read-only scenario preflight, a fixed-argv foreground SUMO run in a
private staged workspace, byte-exact input immutability verification, atomic
read-only publication, validation through the existing import-only SUMO
adapter, and one idempotent registry import through the existing
``import_sumo_results`` service. Nothing here parses XML into metrics itself,
accepts arbitrary executables or flags, or claims scenario realism.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml

from traffictwin.config.capabilities import CapabilitySupport
from traffictwin.integration.sumo import (
    SumoResultManifest,
    SumoValidationResult,
    import_sumo_results,
    sumo_results_capability_manifest,
    validate_sumo_results,
)
from traffictwin.integration.sumo_execution.models import (
    EXPECTED_OUTPUT_FILES,
    IMPORT_BUNDLE_PREFIX,
    RESULT_IMPORT_RECORD_FILE,
    RESULT_MANIFEST_FILE,
    RESULT_RECEIPT_FILE,
    SCENARIO_CONFIG_FILE,
    SCENARIO_DIRECTORY,
    SCENARIO_NET_FILE,
    SCENARIO_ROUTE_FILE,
    SUPPORTED_SUMO_VERSION_PREFIX,
    SYNTHETIC_LIMITATIONS,
    SumoExecutionImportRecord,
    SumoExecutionPreset,
    SumoExecutionReceipt,
    SumoFileEvidence,
    SumoFinding,
    SumoImportedExecutionSummary,
    SumoImportOutcome,
    SumoPreflightReport,
    SumoPreflightStatus,
    SumoRunnerContract,
    SumoRunPreset,
    SumoRunRequest,
    SumoRuntimeStatus,
    SumoScenarioInput,
    SumoTerminalStatus,
    SumoWorkflowReceipt,
    SumoWorkflowRequest,
    SumoWorkflowStage,
    SumoWorkflowStageName,
    SumoWorkflowStageState,
    SumoWorkflowStatus,
    sumo_output_fingerprint,
)
from traffictwin.storage.registry import Registry, RegistryConflictError

_HASH_CHUNK_BYTES = 1_048_576
_LOG_LIMIT_BYTES = 64_000
_OUTPUT_LIMIT_BYTES = 50_000_000
_RECEIPT_LIMIT_BYTES = 2_000_000
_CONFIG_LIMIT_BYTES = 1_000_000
_VERSION_PROBE_TIMEOUT_S = 15
_MAX_STAGE_ERRORS = 5
_SUMO_VERSION_PATTERN = re.compile(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b")

_ALLOWED_ARGUMENTS = (
    "-c",
    "--seed",
    "--begin",
    "--end",
    "--tripinfo-output",
    "--summary-output",
    "--no-step-log",
    "--tripinfo-output.write-undeparted",
)

_TERMINAL_TO_WORKFLOW = {
    SumoTerminalStatus.FAILED: SumoWorkflowStatus.EXECUTION_FAILED,
    SumoTerminalStatus.TIMED_OUT: SumoWorkflowStatus.EXECUTION_TIMED_OUT,
    SumoTerminalStatus.CANCELLED: SumoWorkflowStatus.EXECUTION_CANCELLED,
    SumoTerminalStatus.REJECTED: SumoWorkflowStatus.EXECUTION_REJECTED,
}

_PINNED_INPUTS = {
    SCENARIO_CONFIG_FILE: (
        "f63508af4ac0aa9c83baaab4670cb46e6ea2f7757f523d6378f87cdf465c8a1d",
        538,
    ),
    SCENARIO_NET_FILE: (
        "9dba208715f894606119533ab3c6d3d95133cabe32a910eecc96fd1a47d52126",
        1_048,
    ),
    SCENARIO_ROUTE_FILE: (
        "377e955571566c625c82ee43b5c2e63e55a595960a46491dfbb14d540b6ec4a1",
        1_048,
    ),
}


class SumoExecutionError(RuntimeError):
    """Raised when the controlled workflow refuses or cannot complete a step."""

    def __init__(self, message: str, *, receipt: SumoExecutionReceipt | None = None) -> None:
        super().__init__(message)
        self.receipt = receipt


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def preset_definition(preset: SumoExecutionPreset) -> SumoRunPreset:
    """Return the immutable definition of one closed preset."""

    return SumoRunPreset(
        preset=preset,
        config_sha256=_PINNED_INPUTS[SCENARIO_CONFIG_FILE][0],
        inputs=[
            SumoScenarioInput(name=name, sha256=digest, size_bytes=size)
            for name, (digest, size) in sorted(_PINNED_INPUTS.items())
        ],
        random_seed=42,
        begin_s=0,
        end_s=120,
        vehicle_count=6,
        expected_outputs=list(EXPECTED_OUTPUT_FILES),
        provenance=(
            "Original TrafficTwin-authored synthetic scenario: one edge tracing a 100 m "
            "square perimeter with six deterministic vehicles. Not derived from Eclipse "
            "SUMO scenario files."
        ),
        licence_statement=(
            "TrafficTwin repository licence is unspecified; generated results are not "
            "redistributable beyond the repository boundary."
        ),
        description=(
            "Two-minute synthetic smoke run proving controlled local SUMO execution "
            "only; never Manchester traffic, Randy/VEC evidence, or real-world "
            "validation."
        ),
    )


def preset_scenario_root() -> Path:
    """Return the repository-owned scenario directory for the closed preset."""

    return Path(__file__).resolve().parent / SCENARIO_DIRECTORY


def _discover_executable() -> Path | None:
    """Controlled discovery: the PATH-resolved ``sumo`` binary only."""

    located = shutil.which("sumo")
    if located is None:
        return None
    return Path(located)


def _probe_version(executable: Path) -> str | None:
    try:
        result = subprocess.run(  # noqa: S603 - fixed read-only argv, never a shell
            [str(executable), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for token_source in (result.stdout, result.stderr):
        for line in token_source.splitlines():
            lowered = line.lower()
            if "sumo" not in lowered:
                continue
            match = _SUMO_VERSION_PATTERN.search(line)
            if match is not None:
                return match.group(1)
    return None


def _runtime() -> tuple[SumoRuntimeStatus, Path | None]:
    discovered = _discover_executable()
    if discovered is None:
        return (
            SumoRuntimeStatus(
                available=False,
                supported=False,
                reason=(
                    "no `sumo` executable was found on PATH; install Eclipse SUMO "
                    f"{SUPPORTED_SUMO_VERSION_PREFIX}x to enable controlled execution"
                ),
            ),
            None,
        )
    try:
        executable = discovered.resolve(strict=True)
    except OSError:
        return (
            SumoRuntimeStatus(
                available=False,
                supported=False,
                reason="the discovered `sumo` path does not resolve to an existing file",
            ),
            None,
        )
    if executable.is_symlink() or not executable.is_file():
        return (
            SumoRuntimeStatus(
                available=False,
                supported=False,
                reason="the discovered `sumo` path does not resolve to a regular file",
            ),
            None,
        )
    version = _probe_version(executable)
    if version is None:
        return (
            SumoRuntimeStatus(
                available=True,
                executable_name=executable.name,
                executable_sha256=_sha256_stream(executable),
                supported=False,
                reason="the discovered `sumo` executable did not report a parseable version",
            ),
            None,
        )
    if not version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
        return (
            SumoRuntimeStatus(
                available=True,
                executable_name=executable.name,
                executable_sha256=_sha256_stream(executable),
                version=version,
                supported=False,
                reason=(
                    f"SUMO {version} is not supported; the adapter contract requires "
                    f"{SUPPORTED_SUMO_VERSION_PREFIX}x"
                ),
            ),
            None,
        )
    return (
        SumoRuntimeStatus(
            available=True,
            executable_name=executable.name,
            executable_sha256=_sha256_stream(executable),
            version=version,
            supported=True,
            reason=f"SUMO {version} discovered and supported",
        ),
        executable,
    )


def sumo_runtime_status() -> SumoRuntimeStatus:
    """Return portable SUMO runtime readiness for display."""

    status, _ = _runtime()
    return status


def preflight_sumo_run(workflow: SumoWorkflowRequest) -> SumoPreflightReport:
    """Run the complete read-only admission decision for one closed preset."""

    findings: list[SumoFinding] = []
    preset = preset_definition(workflow.preset)
    runtime, executable = _runtime()
    if not runtime.supported or executable is None:
        findings.append(_finding("SUMO_RUNTIME_UNAVAILABLE", "error", runtime.reason))
        return SumoPreflightReport(
            status=SumoPreflightStatus.UNAVAILABLE,
            preset=workflow.preset,
            runtime=runtime,
            request=None,
            findings=findings,
        )

    root = preset_scenario_root()
    _check_scenario_inputs(preset, root, findings)
    _check_config_references(preset, root, findings)
    _check_destinations(workflow, root, findings)
    if sumo_results_capability_manifest().supports.run_bundle_import is not CapabilitySupport.TRUE:
        findings.append(
            _finding(
                "SUMO_ADAPTER_CAPABILITY_MISSING",
                "error",
                "the import-only SUMO adapter does not report bundle import support",
            )
        )

    if any(item.severity == "error" for item in findings):
        return SumoPreflightReport(
            status=SumoPreflightStatus.REJECTED,
            preset=workflow.preset,
            runtime=runtime,
            request=None,
            findings=findings,
        )
    assert runtime.version is not None and runtime.executable_sha256 is not None
    assert runtime.executable_name is not None
    request = SumoRunRequest(
        preset=workflow.preset,
        config_file=preset.config_file,
        config_sha256=preset.config_sha256,
        inputs=list(preset.inputs),
        sumo_executable_name=runtime.executable_name,
        sumo_executable_sha256=runtime.executable_sha256,
        sumo_version=runtime.version,
        random_seed=preset.random_seed,
        begin_s=preset.begin_s,
        end_s=preset.end_s,
        timeout_seconds=workflow.timeout_seconds,
    )
    findings.append(
        _finding(
            "SUMO_PREFLIGHT_ACCEPTED",
            "info",
            "scenario inventory, configuration references, runtime, and destinations verified",
        )
    )
    return SumoPreflightReport(
        status=SumoPreflightStatus.ACCEPTED,
        preset=workflow.preset,
        runtime=runtime,
        request=request,
        request_fingerprint=request.fingerprint(),
        findings=findings,
    )


def run_sumo(
    workflow: SumoWorkflowRequest,
    *,
    cancellation_event: threading.Event | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> SumoExecutionReceipt:
    """Execute the accepted preset in a private staged workspace and publish atomically."""

    preflight = preflight_sumo_run(workflow)
    if preflight.status is not SumoPreflightStatus.ACCEPTED or preflight.request is None:
        raise SumoExecutionError(f"SUMO preflight is {preflight.status.value}")
    request = preflight.request
    preflight_fingerprint = preflight.fingerprint()
    runtime, executable = _runtime()
    if executable is None or not _runtime_matches_request(runtime, request):
        raise SumoExecutionError(
            "SUMO runtime identity changed between preflight and execution; nothing was run"
        )
    root = preset_scenario_root()
    destination = Path(workflow.output_dir).resolve(strict=False)
    if destination.exists():
        raise SumoExecutionError("output directory must not already exist")
    destination.parent.mkdir(parents=True, exist_ok=True)

    inputs_before = _input_evidence(root, request)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-sumo-run-", dir=destination.parent)
    )
    payload = temporary_root / "payload"
    logs_root = payload / "logs"
    payload.mkdir()
    logs_root.mkdir()
    started_at = clock().isoformat()
    started_monotonic = time.monotonic()
    argv: list[str] = []
    status = SumoTerminalStatus.FAILED
    exit_code: int | None = None
    timed_out = False
    cancelled = False
    stdout_text = ""
    stderr_text = ""
    try:
        for item in request.inputs:
            staged = payload / item.name
            staged.write_bytes((root / item.name).read_bytes())
            if _sha256_stream(staged) != item.sha256:
                raise SumoExecutionError("staged input hash mismatch; refusing to execute")
        argv = _build_argv(executable, request)
        environment = _controlled_environment(executable, payload)
        stdout_path = logs_root / "stdout.txt"
        stderr_path = logs_root / "stderr.txt"
        with (
            stdout_path.open("w", encoding="utf-8") as out,
            stderr_path.open("w", encoding="utf-8") as err,
        ):
            process = subprocess.Popen(  # noqa: S603 - fixed allowlisted argv, never a shell
                argv,
                cwd=payload,
                env=environment,
                stdout=out,
                stderr=err,
                text=True,
                shell=False,
                start_new_session=True,
            )
            deadline = started_monotonic + request.timeout_seconds
            while True:
                if cancellation_event is not None and cancellation_event.is_set():
                    cancelled = True
                    _terminate_process_group(process)
                    break
                try:
                    exit_code = process.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() > deadline:
                        timed_out = True
                        _terminate_process_group(process)
                        break
            if exit_code is None:
                exit_code = process.wait()
        stdout_text = _bounded_text(stdout_path)
        stderr_text = _bounded_text(stderr_path)

        if cancelled:
            status = SumoTerminalStatus.CANCELLED
        elif timed_out:
            status = SumoTerminalStatus.TIMED_OUT
        elif exit_code != 0:
            status = SumoTerminalStatus.FAILED
        else:
            outputs = _validate_runner_outputs(payload)
            inputs_after = _input_evidence(root, request)
            if inputs_after != inputs_before:
                receipt = _terminal_receipt(
                    SumoTerminalStatus.FAILED,
                    request,
                    preflight_fingerprint,
                    argv,
                    started_at,
                    clock,
                    started_monotonic,
                    exit_code,
                    timed_out,
                    cancelled,
                    inputs_before,
                    inputs_after,
                    stdout_text,
                    stderr_text,
                    inputs_modified=True,
                )
                raise SumoExecutionError(
                    "source inputs changed during execution; nothing was published",
                    receipt=receipt,
                )
            output_fp = sumo_output_fingerprint(outputs)
            _write_manifest(payload, request, outputs, output_fp, clock)
            receipt = SumoExecutionReceipt(
                status=SumoTerminalStatus.COMPLETED,
                request=request,
                request_fingerprint=request.fingerprint(),
                preflight_fingerprint=preflight_fingerprint,
                argv=[executable.name, *argv[1:]],
                started_at_utc=started_at,
                finished_at_utc=clock().isoformat(),
                elapsed_seconds=time.monotonic() - started_monotonic,
                exit_code=exit_code,
                timed_out=False,
                cancellation_requested=False,
                inputs_before=inputs_before,
                inputs_after=inputs_after,
                stdout_excerpt=stdout_text,
                stderr_excerpt=stderr_text,
                outputs=outputs,
                output_fingerprint=output_fp,
                inputs_modified=False,
                published=True,
                limitations=list(SYNTHETIC_LIMITATIONS),
            )
            (payload / RESULT_RECEIPT_FILE).write_text(
                receipt.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
            _make_read_only(payload)
            if destination.exists():
                raise SumoExecutionError("output directory appeared during execution")
            payload.rename(destination)
            return receipt
    except SumoExecutionError:
        raise
    except OSError as exc:
        raise SumoExecutionError(f"controlled SUMO execution failed: {exc}") from exc
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)

    inputs_after = _input_evidence(root, request)
    receipt = _terminal_receipt(
        status,
        request,
        preflight_fingerprint,
        argv,
        started_at,
        clock,
        started_monotonic,
        exit_code,
        timed_out,
        cancelled,
        inputs_before,
        inputs_after,
        stdout_text,
        stderr_text,
        inputs_modified=inputs_after != inputs_before,
    )
    raise SumoExecutionError(
        f"SUMO execution terminated as {status.value}; nothing was published",
        receipt=receipt,
    )


def import_sumo_execution(
    result_dir: str | Path,
    registry_path: str | Path,
    *,
    clock: Callable[[], datetime] = _utc_now,
) -> tuple[SumoExecutionImportRecord, SumoImportOutcome, SumoValidationResult]:
    """Revalidate one published controlled run and import it idempotently."""

    requested_root = Path(result_dir)
    if requested_root.is_symlink():
        raise SumoExecutionError("result directory must be an existing non-symlink directory")
    root = requested_root.resolve(strict=False)
    if not root.is_dir():
        raise SumoExecutionError("result directory must be an existing non-symlink directory")
    receipt = _load_receipt(root)
    if receipt.status is not SumoTerminalStatus.COMPLETED:
        raise SumoExecutionError(
            f"only completed executions may be imported; receipt status is {receipt.status.value}"
        )
    _verify_outputs_on_disk(root, receipt)
    registry_file = _admit_registry_path(registry_path, root, preset_scenario_root())

    validation = validate_sumo_results(root)
    if validation.fingerprint is None or not validation.report.may_import:
        raise SumoExecutionError(
            "the existing SUMO adapter did not accept the generated result; import refused"
        )
    adapter_result = import_sumo_results(root, registry_file, validation_result=validation)
    if adapter_result.status == "rejected":
        raise SumoExecutionError("the existing SUMO adapter rejected the import")

    record = SumoExecutionImportRecord(
        preset=receipt.request.preset,
        request=receipt.request,
        request_fingerprint=receipt.request_fingerprint,
        preflight_fingerprint=receipt.preflight_fingerprint,
        receipt_file_sha256=_sha256_stream(root / RESULT_RECEIPT_FILE),
        receipt_fingerprint=receipt.fingerprint(),
        output_fingerprint=receipt.output_fingerprint or "",
        sumo_version=receipt.request.sumo_version,
        validation_bundle_fingerprint=validation.fingerprint,
        validation_report_sha256=hashlib.sha256(validation.report.to_json().encode()).hexdigest(),
        bundle_id=adapter_result.bundle_id or "",
        run_id=adapter_result.run_id or "",
        imported_at_utc=clock().isoformat(),
        limitations=list(SYNTHETIC_LIMITATIONS),
    )
    _persist_import_record(root, record)
    outcome = SumoImportOutcome(
        created=adapter_result.created,
        idempotent=adapter_result.idempotent,
        bundle_id=adapter_result.bundle_id or "",
        run_id=adapter_result.run_id or "",
        adapter_status=adapter_result.status,
        metrics_stored=adapter_result.metrics_stored,
        registry_reference=registry_file.name,
    )
    return record, outcome, validation


def execute_and_import_sumo(
    workflow: SumoWorkflowRequest,
    *,
    cancellation_event: threading.Event | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> SumoWorkflowReceipt:
    """Run the complete one-click preflight, execution, validation, import pipeline."""

    stages: list[SumoWorkflowStage] = []
    runtime = sumo_runtime_status()

    registry_guard = _registry_guard_error(workflow)
    if registry_guard is not None:
        stages.append(_stage(SumoWorkflowStageName.PREFLIGHT, "rejected", registry_guard))
        return _receipt(
            SumoWorkflowStatus.PREFLIGHT_REJECTED,
            workflow,
            runtime,
            stages,
            findings=[registry_guard],
        )

    preflight = preflight_sumo_run(workflow)
    preflight_fingerprint = preflight.fingerprint()
    if preflight.status is not SumoPreflightStatus.ACCEPTED:
        errors = [
            f"{item.code}: {item.message}"
            for item in preflight.findings
            if item.severity == "error"
        ][:_MAX_STAGE_ERRORS]
        detail = f"preflight {preflight.status.value}: " + ("; ".join(errors) or "no detail")
        stages.append(_stage(SumoWorkflowStageName.PREFLIGHT, "rejected", detail))
        status = (
            SumoWorkflowStatus.PREFLIGHT_UNAVAILABLE
            if preflight.status is SumoPreflightStatus.UNAVAILABLE
            else SumoWorkflowStatus.PREFLIGHT_REJECTED
        )
        return _receipt(
            status,
            workflow,
            preflight.runtime,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            findings=errors or [detail],
        )
    stages.append(
        _stage(
            SumoWorkflowStageName.PREFLIGHT,
            "accepted",
            f"request-specific preflight accepted ({preflight_fingerprint[:12]})",
        )
    )

    try:
        receipt = run_sumo(workflow, cancellation_event=cancellation_event, clock=clock)
    except SumoExecutionError as exc:
        terminal = exc.receipt
        status = (
            _TERMINAL_TO_WORKFLOW.get(terminal.status, SumoWorkflowStatus.EXECUTION_FAILED)
            if terminal is not None
            else SumoWorkflowStatus.EXECUTION_FAILED
        )
        detail = f"execution did not complete: {exc}"
        stages.append(_stage(SumoWorkflowStageName.EXECUTION, "failed", detail))
        stages.append(_stage(SumoWorkflowStageName.IMPORT, "skipped", "nothing to import"))
        return _receipt(
            status,
            workflow,
            preflight.runtime,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            receipt_fingerprint=terminal.fingerprint() if terminal is not None else None,
            findings=[detail],
        )
    stages.append(
        _stage(
            SumoWorkflowStageName.EXECUTION,
            "completed",
            f"SUMO completed in {receipt.elapsed_seconds:.3f}s",
        )
    )

    try:
        record, outcome, validation = import_sumo_execution(
            workflow.output_dir,
            workflow.registry_path,
            clock=clock,
        )
    except RegistryConflictError as exc:
        detail = f"registry identity conflict: {exc}"
        stages.append(_stage(SumoWorkflowStageName.VALIDATION, "accepted", "outputs revalidated"))
        stages.append(_stage(SumoWorkflowStageName.IMPORT, "rejected", detail))
        return _receipt(
            SumoWorkflowStatus.IMPORT_CONFLICT,
            workflow,
            preflight.runtime,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            receipt_fingerprint=receipt.fingerprint(),
            output_fingerprint=receipt.output_fingerprint,
            findings=[detail],
        )
    except SumoExecutionError as exc:
        detail = f"validation or import refused: {exc}"
        stages.append(_stage(SumoWorkflowStageName.VALIDATION, "rejected", detail))
        stages.append(_stage(SumoWorkflowStageName.IMPORT, "skipped", "nothing was imported"))
        return _receipt(
            SumoWorkflowStatus.VALIDATION_REJECTED,
            workflow,
            preflight.runtime,
            stages,
            preflight_fingerprint=preflight_fingerprint,
            receipt_fingerprint=receipt.fingerprint(),
            output_fingerprint=receipt.output_fingerprint,
            findings=[detail],
        )
    stages.append(
        _stage(
            SumoWorkflowStageName.VALIDATION,
            "accepted",
            "existing SUMO adapter accepted the generated result "
            f"({validation.report.status.value})",
        )
    )
    import_kind = "idempotent re-import" if outcome.idempotent else "new registry record"
    stages.append(
        _stage(SumoWorkflowStageName.IMPORT, "completed", f"{import_kind} {outcome.run_id}")
    )
    return SumoWorkflowReceipt(
        status=SumoWorkflowStatus.COMPLETED_IMPORTED,
        preset=workflow.preset,
        stages=stages,
        runtime=preflight.runtime,
        request_fingerprint=receipt.request_fingerprint,
        preflight_fingerprint=preflight_fingerprint,
        receipt_fingerprint=receipt.fingerprint(),
        output_fingerprint=receipt.output_fingerprint,
        inputs_verified_unchanged=True,
        import_outcome=outcome,
        import_record_stable_fingerprint=record.stable_fingerprint(),
        outputs=list(receipt.outputs),
    )


def list_imported_sumo_executions(
    registry_path: str | Path,
) -> list[SumoImportedExecutionSummary]:
    """List controlled-execution imports from the registry for persistent inspection."""

    registry_file = Path(registry_path)
    if not registry_file.is_file():
        return []
    summaries: list[SumoImportedExecutionSummary] = []
    for record in Registry(registry_file).list_bundle_import_records():
        if not record.bundle_id.startswith(IMPORT_BUNDLE_PREFIX):
            continue
        try:
            manifest = SumoResultManifest.model_validate_json(record.manifest_json)
        except ValueError:
            continue
        summaries.append(
            SumoImportedExecutionSummary(
                bundle_id=record.bundle_id,
                run_id=record.run_id,
                imported_at=record.imported_at,
                source_reference=record.source_reference,
                scenario_id=manifest.source.scenario_id,
                sumo_version=manifest.source.sumo_version,
                synthetic=manifest.source.synthetic,
            )
        )
    return summaries


def load_import_record(result_dir: str | Path) -> SumoExecutionImportRecord | None:
    """Load the persisted typed import record from a published result directory."""

    path = Path(result_dir) / RESULT_IMPORT_RECORD_FILE
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _RECEIPT_LIMIT_BYTES:
        return None
    try:
        return SumoExecutionImportRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def sumo_execution_contract() -> SumoRunnerContract:
    """Return the machine-readable controlled-execution boundary."""

    return SumoRunnerContract(
        presets=[preset_definition(preset) for preset in SumoExecutionPreset],
        operations=[
            "sumo_runtime_status",
            "preflight_sumo_run",
            "run_sumo",
            "import_sumo_execution",
            "execute_and_import_sumo",
            "list_imported_sumo_executions",
        ],
        allowed_arguments=list(_ALLOWED_ARGUMENTS),
        refusals=[
            "arbitrary executables, shell text, sumo-gui, scripts, flags, environment "
            "variables, URLs, or dynamic modules",
            "remote execution, background queues, SLURM, package installation, Git "
            "operations, live feeds, or Randy/VEC controls",
            "non-preset scenarios, symlinked or mutated inputs, unsafe destinations, and "
            "existing output directories",
            "failed, timed-out, cancelled, malformed, or input-mutating executions never import",
        ],
        security_controls=[
            "controlled PATH discovery resolved to a regular sumo binary with a supported "
            "1.27.x version, with identity rechecked immediately before execution",
            "read-only preflight with streaming SHA-256 verification of the pinned "
            "scenario inventory and configuration references",
            "fixed allowlisted argv with shell=False, a private staged workspace, a "
            "controlled environment, bounded logs, timeout, and process-group cancellation",
            "byte-identical input verification after execution and atomic read-only "
            "publication to a new destination only",
            "validation and import exclusively through the existing import-only SUMO "
            "adapter and registry conventions",
        ],
        interpretation_limits=list(SYNTHETIC_LIMITATIONS)
        + [
            "generic direct_launch remains false; controlled_sumo_execution is "
            "conditional on request-specific preflight",
        ],
    )


# --- internal helpers -----------------------------------------------------


def _finding(code: str, severity: str, message: str) -> SumoFinding:
    return SumoFinding(code=code, severity=severity, message=message[:1_000])


def _stage(stage: SumoWorkflowStageName, state: str, detail: str) -> SumoWorkflowStage:
    return SumoWorkflowStage(
        stage=stage,
        state=SumoWorkflowStageState(state),
        detail=detail[:2_000],
    )


def _receipt(
    status: SumoWorkflowStatus,
    workflow: SumoWorkflowRequest,
    runtime: SumoRuntimeStatus,
    stages: list[SumoWorkflowStage],
    *,
    preflight_fingerprint: str | None = None,
    receipt_fingerprint: str | None = None,
    output_fingerprint: str | None = None,
    findings: list[str] | None = None,
) -> SumoWorkflowReceipt:
    return SumoWorkflowReceipt(
        status=status,
        preset=workflow.preset,
        stages=stages,
        runtime=runtime,
        preflight_fingerprint=preflight_fingerprint,
        receipt_fingerprint=receipt_fingerprint,
        output_fingerprint=output_fingerprint,
        inputs_verified_unchanged=False,
        findings=(findings or [])[:32],
    )


def _check_scenario_inputs(
    preset: SumoRunPreset,
    root: Path,
    findings: list[SumoFinding],
) -> None:
    if root.is_symlink() or not root.is_dir():
        findings.append(
            _finding(
                "SUMO_SCENARIO_ROOT_INVALID",
                "error",
                "the repository-owned scenario directory is missing or unsafe",
            )
        )
        return
    for item in preset.inputs:
        path = root / item.name
        if path.is_symlink() or not path.is_file():
            findings.append(
                _finding(
                    "SUMO_INPUT_NOT_REGULAR",
                    "error",
                    f"scenario input is missing or not a regular file: {item.name}",
                )
            )
            continue
        if path.resolve().parent != root.resolve():
            findings.append(
                _finding(
                    "SUMO_INPUT_ESCAPES_ROOT",
                    "error",
                    f"scenario input escapes the approved preset root: {item.name}",
                )
            )
            continue
        size = path.stat().st_size
        digest = _sha256_stream(path)
        if size != item.size_bytes or digest != item.sha256:
            findings.append(
                _finding(
                    "SUMO_INPUT_HASH_MISMATCH",
                    "error",
                    f"scenario input does not match its pinned identity: {item.name}",
                )
            )


def _check_config_references(
    preset: SumoRunPreset,
    root: Path,
    findings: list[SumoFinding],
) -> None:
    config = root / preset.config_file
    if not config.is_file() or config.stat().st_size > _CONFIG_LIMIT_BYTES:
        return
    payload = config.read_bytes()
    if b"<!DOCTYPE" in payload or b"<!ENTITY" in payload:
        findings.append(
            _finding(
                "SUMO_CONFIG_UNSAFE_XML",
                "error",
                "the configuration contains DTD or entity declarations",
            )
        )
        return
    try:
        tree = ElementTree.fromstring(  # noqa: S314 - declaration-guarded pinned local file
            payload.decode("utf-8")
        )
    except (UnicodeDecodeError, ElementTree.ParseError):
        findings.append(
            _finding("SUMO_CONFIG_MALFORMED", "error", "the configuration is not well-formed XML")
        )
        return
    admitted = {item.name for item in preset.inputs}
    for element in tree.iter():
        if element.tag not in {"net-file", "route-files", "additional-files"}:
            continue
        value = element.get("value", "")
        for reference in value.split(","):
            reference = reference.strip()
            if not reference:
                continue
            if "/" in reference or "\\" in reference or reference not in admitted:
                findings.append(
                    _finding(
                        "SUMO_CONFIG_REFERENCE_NOT_ADMITTED",
                        "error",
                        f"configuration references a non-admitted file: {reference}",
                    )
                )


def _check_destinations(
    workflow: SumoWorkflowRequest,
    root: Path,
    findings: list[SumoFinding],
) -> None:
    destination = Path(workflow.output_dir).resolve(strict=False)
    scenario = root.resolve()
    if destination.exists():
        findings.append(
            _finding(
                "SUMO_OUTPUT_EXISTS",
                "error",
                "the output directory must not already exist",
            )
        )
    if (
        destination == scenario
        or scenario in destination.parents
        or (destination in scenario.parents)
    ):
        findings.append(
            _finding(
                "SUMO_OUTPUT_OVERLAPS_INPUTS",
                "error",
                "the output directory must not overlap the scenario inputs",
            )
        )
    if not destination.parent.is_dir():
        findings.append(
            _finding(
                "SUMO_OUTPUT_PARENT_MISSING",
                "error",
                "the output parent directory must already exist",
            )
        )
    try:
        _admit_registry_path(workflow.registry_path, destination, scenario)
    except SumoExecutionError as exc:
        findings.append(_finding("SUMO_REGISTRY_DESTINATION_REJECTED", "error", str(exc)))


def _registry_guard_error(workflow: SumoWorkflowRequest) -> str | None:
    try:
        _admit_registry_path(
            workflow.registry_path,
            Path(workflow.output_dir).resolve(strict=False),
            preset_scenario_root().resolve(),
        )
    except SumoExecutionError as exc:
        return f"registry destination rejected before execution: {exc}"
    return None


def _admit_registry_path(
    registry_path: str | Path,
    result_dir: Path,
    scenario_root: Path,
) -> Path:
    registry_file = Path(registry_path).resolve(strict=False)
    if registry_file.is_dir():
        raise SumoExecutionError("registry path must name a SQLite file, not a directory")
    if registry_file.exists() and Path(registry_path).is_symlink():
        raise SumoExecutionError("registry path must not be a symbolic link")
    if not registry_file.parent.is_dir():
        raise SumoExecutionError("registry parent directory must already exist")
    for protected in (result_dir, scenario_root):
        if registry_file == protected or protected in registry_file.parents:
            raise SumoExecutionError(
                "registry must not live inside the result directory or the scenario inputs"
            )
    return registry_file


def _input_evidence(root: Path, request: SumoRunRequest) -> list[SumoFileEvidence]:
    return [
        SumoFileEvidence(
            path=item.name,
            sha256=_sha256_stream(root / item.name),
            size_bytes=(root / item.name).stat().st_size,
        )
        for item in request.inputs
    ]


def _runtime_matches_request(runtime: SumoRuntimeStatus, request: SumoRunRequest) -> bool:
    """Return whether a fresh runtime observation matches the accepted request exactly."""

    return (
        runtime.supported
        and runtime.executable_name == request.sumo_executable_name
        and runtime.executable_sha256 == request.sumo_executable_sha256
        and runtime.version == request.sumo_version
    )


def _build_argv(executable: Path, request: SumoRunRequest) -> list[str]:
    return [
        str(executable),
        "-c",
        request.config_file,
        "--seed",
        str(request.random_seed),
        "--begin",
        str(request.begin_s),
        "--end",
        str(request.end_s),
        "--tripinfo-output",
        "tripinfo.xml",
        "--summary-output",
        "summary.xml",
        "--no-step-log",
        "true",
        "--tripinfo-output.write-undeparted",
        "true",
    ]


def _controlled_environment(executable: Path, workspace: Path) -> dict[str, str]:
    environment = {
        "PATH": f"{executable.parent}:/usr/bin:/bin",
        "HOME": str(workspace),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    sumo_home = executable.parent.parent / "share" / "sumo"
    if sumo_home.is_dir():
        environment["SUMO_HOME"] = str(sumo_home)
    return environment


def _validate_runner_outputs(payload: Path) -> list[SumoFileEvidence]:
    outputs: list[SumoFileEvidence] = []
    expected_roots = {"summary.xml": "summary", "tripinfo.xml": "tripinfos"}
    for name in EXPECTED_OUTPUT_FILES:
        path = payload / name
        if path.is_symlink() or not path.is_file():
            raise SumoExecutionError(f"required SUMO output is missing or unsafe: {name}")
        size = path.stat().st_size
        if size == 0 or size > _OUTPUT_LIMIT_BYTES:
            raise SumoExecutionError(f"required SUMO output is empty or out of bounds: {name}")
        content = path.read_bytes()
        if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
            raise SumoExecutionError(f"SUMO output contains unsafe XML declarations: {name}")
        try:
            root = ElementTree.fromstring(  # noqa: S314 - declaration-guarded generated file
                content.decode("utf-8")
            )
        except (UnicodeDecodeError, ElementTree.ParseError) as exc:
            raise SumoExecutionError(f"SUMO output is malformed: {name}") from exc
        if root.tag != expected_roots[name]:
            raise SumoExecutionError(f"SUMO output has an unexpected root element: {name}")
        outputs.append(SumoFileEvidence(path=name, sha256=_sha256_bytes(content), size_bytes=size))
    return outputs


def _write_manifest(
    payload: Path,
    request: SumoRunRequest,
    outputs: list[SumoFileEvidence],
    output_fingerprint: str,
    clock: Callable[[], datetime],
) -> None:
    by_name = {item.path: item for item in outputs}
    identity = f"{IMPORT_BUNDLE_PREFIX}{output_fingerprint[:16]}"
    now = clock()
    manifest = SumoResultManifest.model_validate(
        {
            "schema_version": "1.0",
            "adapter": "sumo_results",
            "bundle": {"bundle_id": identity, "created_at": now.isoformat()},
            "source": {
                "scenario_id": "traffictwin-synthetic-square-smoke",
                "scenario_url": (
                    "repository:src/traffictwin/integration/sumo_execution/"
                    "scenario_synthetic_square"
                ),
                "sumo_version": request.sumo_version,
                "source_commit": None,
                "licence_spdx": "LicenseRef-TrafficTwin-Repository-Unspecified",
                "retrieval_date": now.date().isoformat(),
                "redistribution_allowed": False,
                "restrictions": [
                    "TrafficTwin repository licence is unspecified; do not redistribute "
                    "generated results beyond the repository boundary.",
                ],
                "synthetic": True,
            },
            "run": {
                "run_id": identity,
                "experiment_id": "sumo-oneclick-synthetic-square",
                "seed_id": f"sumo-seed-square-{request.random_seed}",
                "algorithm": "sumo-default-traffic-models",
                "random_seed": request.random_seed,
            },
            "files": {
                "tripinfo": {
                    "path": "tripinfo.xml",
                    "checksum_sha256": by_name["tripinfo.xml"].sha256,
                },
                "summary": {
                    "path": "summary.xml",
                    "checksum_sha256": by_name["summary.xml"].sha256,
                },
            },
        }
    )
    (payload / RESULT_MANIFEST_FILE).write_text(
        yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )


def _terminal_receipt(
    status: SumoTerminalStatus,
    request: SumoRunRequest,
    preflight_fingerprint: str,
    argv: list[str],
    started_at: str,
    clock: Callable[[], datetime],
    started_monotonic: float,
    exit_code: int | None,
    timed_out: bool,
    cancelled: bool,
    inputs_before: list[SumoFileEvidence],
    inputs_after: list[SumoFileEvidence],
    stdout_text: str,
    stderr_text: str,
    *,
    inputs_modified: bool,
) -> SumoExecutionReceipt:
    return SumoExecutionReceipt(
        status=status,
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint=preflight_fingerprint,
        argv=[Path(argv[0]).name, *argv[1:]] if argv else ["sumo", "-c"],
        started_at_utc=started_at,
        finished_at_utc=clock().isoformat(),
        elapsed_seconds=time.monotonic() - started_monotonic,
        exit_code=exit_code,
        timed_out=timed_out,
        cancellation_requested=cancelled,
        inputs_before=inputs_before,
        inputs_after=inputs_after,
        stdout_excerpt=stdout_text,
        stderr_excerpt=stderr_text,
        outputs=[],
        output_fingerprint=None,
        inputs_modified=inputs_modified,
        published=False,
        limitations=list(SYNTHETIC_LIMITATIONS),
    )


def _load_receipt(root: Path) -> SumoExecutionReceipt:
    receipt_path = root / RESULT_RECEIPT_FILE
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise SumoExecutionError("execution_receipt.json is missing or unsafe")
    if receipt_path.stat().st_size > _RECEIPT_LIMIT_BYTES:
        raise SumoExecutionError("execution receipt exceeds the bounded size")
    try:
        return SumoExecutionReceipt.model_validate_json(receipt_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SumoExecutionError(f"execution receipt is not valid: {exc}") from exc


def _verify_outputs_on_disk(root: Path, receipt: SumoExecutionReceipt) -> None:
    output_names = [evidence.path for evidence in receipt.outputs]
    if len(output_names) != len(set(output_names)) or set(output_names) != set(
        EXPECTED_OUTPUT_FILES
    ):
        raise SumoExecutionError("execution receipt does not contain the exact required outputs")
    for evidence in receipt.outputs:
        path = root / evidence.path
        if path.is_symlink() or not path.is_file():
            raise SumoExecutionError(f"published output is missing or unsafe: {evidence.path}")
        if path.stat().st_size != evidence.size_bytes or _sha256_stream(path) != evidence.sha256:
            raise SumoExecutionError(
                f"published output does not match its receipt identity: {evidence.path}"
            )


def _persist_import_record(root: Path, record: SumoExecutionImportRecord) -> None:
    path = root / RESULT_IMPORT_RECORD_FILE
    if path.exists():
        existing = load_import_record(root)
        if existing is not None and existing.stable_fingerprint() == record.stable_fingerprint():
            return
        raise RegistryConflictError(
            "a different import record already exists for this result directory"
        )
    root.chmod(0o755)
    try:
        path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
        path.chmod(0o444)
    finally:
        root.chmod(0o555)


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait(timeout=5)
    except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
        pass


def _bounded_text(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            return handle.read(_LOG_LIMIT_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return ""


def _make_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)


def _sha256_stream(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
