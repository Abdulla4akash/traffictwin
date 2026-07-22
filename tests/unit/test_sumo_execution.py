"""Tests for the controlled one-click SUMO execute-and-import workflow.

The stub executables written here are explicitly synthetic test
infrastructure: tiny shell scripts that imitate SUMO's argv surface to
exercise orchestration mechanics and failure paths. They cannot satisfy real
SUMO acceptance, which requires an actual Eclipse SUMO 1.27.x binary and is
covered by the separate integration acceptance test.
"""

from __future__ import annotations

import hashlib
import shutil
import stat
import subprocess
import threading
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.config.capabilities import CapabilitySupport
from traffictwin.integration.sumo import sumo_results_capability_manifest
from traffictwin.integration.sumo_execution import (
    SumoExecutionError,
    SumoExecutionPreset,
    SumoPreflightStatus,
    SumoWorkflowReceipt,
    SumoWorkflowRequest,
    SumoWorkflowStatus,
    execute_and_import_sumo,
    import_sumo_execution,
    list_imported_sumo_executions,
    load_import_record,
    preflight_sumo_run,
    preset_definition,
    preset_scenario_root,
    sumo_execution_contract,
    sumo_runtime_status,
)
from traffictwin.integration.sumo_execution import service as sumo_service
from traffictwin.integration.sumo_execution.models import (
    SumoImportOutcome,
    SumoRuntimeStatus,
    SumoWorkflowStage,
    SumoWorkflowStageName,
    SumoWorkflowStageState,
)
from traffictwin.storage.registry import Registry, RegistryConflictError

VALID_TRIPINFO = """<?xml version="1.0" encoding="UTF-8"?>
<tripinfos>
    <tripinfo id="synthetic_vehicle_0" depart="0.00" arrival="30.00" duration="30.00"/>
    <tripinfo id="synthetic_vehicle_1" depart="5.00" arrival="36.00" duration="31.00"/>
</tripinfos>
"""
VALID_SUMMARY = """<?xml version="1.0" encoding="UTF-8"?>
<summary>
    <step time="0.00" running="1"/>
    <step time="1.00" running="2"/>
</summary>
"""
VERSION_LINE = "Eclipse SUMO sumo 1.27.0"


def write_stub(
    path: Path,
    *,
    version_line: str = VERSION_LINE,
    body: str = "",
) -> Path:
    """Write a synthetic-test-infrastructure stub imitating the sumo argv surface."""

    script = f"""#!/bin/sh
# Synthetic TrafficTwin test stub; not Eclipse SUMO.
if [ "$1" = "--version" ]; then
  echo "{version_line}"
  exit 0
fi
{body}
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def success_body() -> str:
    return (
        "cat > tripinfo.xml <<'TRIPINFO_EOF'\n"
        + VALID_TRIPINFO
        + "TRIPINFO_EOF\n"
        + "cat > summary.xml <<'SUMMARY_EOF'\n"
        + VALID_SUMMARY
        + "SUMMARY_EOF\n"
        + "exit 0\n"
    )


@pytest.fixture
def stub_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    (tmp_path / "bin").mkdir(exist_ok=True)
    stub = write_stub(tmp_path / "bin" / "sumo", body=success_body())
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: stub)
    return stub


def workflow_request(tmp_path: Path, **overrides: object) -> SumoWorkflowRequest:
    payload: dict[str, object] = {
        "preset": SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE,
        "output_dir": str(tmp_path / "out"),
        "registry_path": str(tmp_path / "registry.sqlite"),
        "timeout_seconds": 30,
    }
    payload.update(overrides)
    return SumoWorkflowRequest(**payload)


# --- presets, contract, capability ---------------------------------------


def test_preset_definition_is_exact_and_deterministic() -> None:
    definition = preset_definition(SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE)

    assert definition.random_seed == 42
    assert definition.begin_s == 0
    assert definition.end_s == 120
    assert definition.vehicle_count == 6
    assert definition.synthetic is True
    assert definition.manchester_traffic is False
    assert definition.randy_vec_evidence is False
    assert [item.name for item in definition.inputs] == [
        "square.net.xml",
        "square.rou.xml",
        "square.sumocfg",
    ]
    assert (
        definition.fingerprint()
        == preset_definition(SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE).fingerprint()
    )


def test_scenario_files_match_pinned_hashes() -> None:
    root = preset_scenario_root()
    for item in preset_definition(SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE).inputs:
        content = (root / item.name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item.sha256
        assert len(content) == item.size_bytes


def test_contract_keeps_generic_launch_false_and_capability_conditional() -> None:
    contract = sumo_execution_contract()
    assert contract.generic_direct_launch is False
    assert contract.capability == "controlled_sumo_execution"
    assert contract.capability_state == "conditional_on_request_specific_preflight"
    assert "--seed" in contract.allowed_arguments
    assert sumo_results_capability_manifest().supports.direct_launch is CapabilitySupport.FALSE


def test_unsupported_preset_and_extra_fields_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SumoWorkflowRequest(
            preset="arbitrary_scenario",
            output_dir=str(tmp_path / "out"),
            registry_path=str(tmp_path / "registry.sqlite"),
        )
    with pytest.raises(ValidationError, match="surprise"):
        workflow_request(tmp_path, surprise=True)


def test_fixed_argv_construction(stub_runtime: Path) -> None:
    report = preflight_sumo_run(workflow_request(stub_runtime.parent.parent))
    assert report.status is SumoPreflightStatus.ACCEPTED
    assert report.request is not None
    argv = sumo_service._build_argv(stub_runtime, report.request)
    assert argv == [
        str(stub_runtime),
        "-c",
        "square.sumocfg",
        "--seed",
        "42",
        "--begin",
        "0",
        "--end",
        "120",
        "--tripinfo-output",
        "tripinfo.xml",
        "--summary-output",
        "summary.xml",
        "--no-step-log",
        "true",
        "--tripinfo-output.write-undeparted",
        "true",
    ]


def test_streaming_hash_matches_reference(tmp_path: Path) -> None:
    payload = b"traffictwin" * 300_000
    target = tmp_path / "large.bin"
    target.write_bytes(payload)
    assert sumo_service._sha256_stream(target) == hashlib.sha256(payload).hexdigest()


# --- runtime discovery ----------------------------------------------------


def test_missing_executable_reports_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: None)
    status = sumo_runtime_status()
    assert status.available is False
    assert status.supported is False
    assert "install Eclipse SUMO" in status.reason


def test_version_probe_accepts_current_and_legacy_sumo_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for index, line in enumerate(("Eclipse SUMO sumo 1.27.1", "Eclipse SUMO sumo Version 1.27.0")):
        stub = write_stub(tmp_path / f"sumo-{index}", version_line=line)
        monkeypatch.setattr(sumo_service, "_discover_executable", lambda stub=stub: stub)
        status = sumo_runtime_status()
        assert status.supported is True
        assert status.version in {"1.27.0", "1.27.1"}


def test_symlinked_executable_resolves_to_regular_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = write_stub(tmp_path / "real-sumo", body=success_body())
    link = tmp_path / "sumo"
    link.symlink_to(real)
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: link)
    status = sumo_runtime_status()
    assert status.available is True
    assert status.supported is True
    assert status.executable_sha256 == hashlib.sha256(real.read_bytes()).hexdigest()


def test_broken_symlinked_executable_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link = tmp_path / "sumo"
    link.symlink_to(tmp_path / "missing-sumo")
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: link)
    status = sumo_runtime_status()
    assert status.available is False
    assert "does not resolve" in status.reason


def test_runtime_identity_change_after_preflight_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = write_stub(tmp_path / "sumo-first", body=success_body())
    second = write_stub(tmp_path / "sumo-second", body=success_body() + "# changed\n")
    discovered = iter((first, second))
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: next(discovered))

    with pytest.raises(SumoExecutionError, match="identity changed"):
        sumo_service.run_sumo(workflow_request(tmp_path))

    assert not (tmp_path / "out").exists()


def test_unsupported_version_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = write_stub(
        tmp_path / "sumo",
        version_line="Eclipse SUMO sumo Version 1.20.0",
        body=success_body(),
    )
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: stub)
    status = sumo_runtime_status()
    assert status.available is True
    assert status.supported is False
    assert "1.27.x" in status.reason

    receipt = execute_and_import_sumo(workflow_request(tmp_path))
    assert receipt.status is SumoWorkflowStatus.PREFLIGHT_UNAVAILABLE
    assert receipt.import_outcome is None


# --- preflight rejection paths -------------------------------------------


def copied_scenario(tmp_path: Path) -> Path:
    target = tmp_path / "scenario"
    shutil.copytree(preset_scenario_root(), target)
    return target


def test_input_hash_mismatch_rejected(
    tmp_path: Path,
    stub_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = copied_scenario(tmp_path)
    (scenario / "square.rou.xml").write_text("<routes/>", encoding="utf-8")
    monkeypatch.setattr(sumo_service, "preset_scenario_root", lambda: scenario)

    report = preflight_sumo_run(workflow_request(tmp_path))
    assert report.status is SumoPreflightStatus.REJECTED
    assert any(item.code == "SUMO_INPUT_HASH_MISMATCH" for item in report.findings)


def test_config_reference_escape_rejected(
    tmp_path: Path,
    stub_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = copied_scenario(tmp_path)
    config = scenario / "square.sumocfg"
    text = config.read_text(encoding="utf-8").replace(
        'route-files value="square.rou.xml"',
        'route-files value="../outside.rou.xml"',
    )
    config.write_text(text, encoding="utf-8")
    definition = preset_definition(SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE)
    updated_inputs = [
        item.model_copy(
            update={
                "sha256": hashlib.sha256((scenario / item.name).read_bytes()).hexdigest(),
                "size_bytes": (scenario / item.name).stat().st_size,
            }
        )
        for item in definition.inputs
    ]
    patched = definition.model_copy(
        update={
            "inputs": updated_inputs,
            "config_sha256": next(
                item.sha256 for item in updated_inputs if item.name == "square.sumocfg"
            ),
        }
    )
    monkeypatch.setattr(sumo_service, "preset_scenario_root", lambda: scenario)
    monkeypatch.setattr(sumo_service, "preset_definition", lambda preset: patched)

    report = preflight_sumo_run(workflow_request(tmp_path))
    assert report.status is SumoPreflightStatus.REJECTED
    assert any(item.code == "SUMO_CONFIG_REFERENCE_NOT_ADMITTED" for item in report.findings)


def test_unsafe_destinations_rejected(tmp_path: Path, stub_runtime: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    report = preflight_sumo_run(workflow_request(tmp_path, output_dir=str(existing)))
    assert any(item.code == "SUMO_OUTPUT_EXISTS" for item in report.findings)

    report = preflight_sumo_run(
        workflow_request(tmp_path, output_dir=str(preset_scenario_root() / "nested"))
    )
    assert any(item.code == "SUMO_OUTPUT_OVERLAPS_INPUTS" for item in report.findings)

    report = preflight_sumo_run(
        workflow_request(
            tmp_path,
            registry_path=str(preset_scenario_root() / "registry.sqlite"),
        )
    )
    assert any(item.code == "SUMO_REGISTRY_DESTINATION_REJECTED" for item in report.findings)

    report = preflight_sumo_run(
        workflow_request(
            tmp_path,
            registry_path=str(tmp_path / "out" / "registry.sqlite"),
        )
    )
    assert any(item.code == "SUMO_REGISTRY_DESTINATION_REJECTED" for item in report.findings)


def test_rejected_preflight_invokes_no_process(
    tmp_path: Path,
    stub_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = copied_scenario(tmp_path)
    (scenario / "square.net.xml").write_text("<net/>", encoding="utf-8")
    monkeypatch.setattr(sumo_service, "preset_scenario_root", lambda: scenario)

    real_popen = subprocess.Popen

    def guarded(*args: object, **kwargs: object) -> object:
        argv = args[0]
        if isinstance(argv, list) and "-c" in argv:
            raise AssertionError("no simulation process may start after a rejected preflight")
        return real_popen(*cast("tuple[Any, ...]", args), **cast("dict[str, Any]", kwargs))

    monkeypatch.setattr(subprocess, "Popen", guarded)
    receipt = execute_and_import_sumo(workflow_request(tmp_path))
    assert receipt.status is SumoWorkflowStatus.PREFLIGHT_REJECTED
    assert receipt.import_outcome is None
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "registry.sqlite").exists()


# --- execution outcomes ---------------------------------------------------


def test_successful_stub_run_publishes_validates_and_imports(
    tmp_path: Path,
    stub_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    popen_calls: list[dict[str, object]] = []
    real_popen = subprocess.Popen

    def spying_popen(*args: object, **kwargs: object) -> object:
        popen_calls.append(dict(kwargs) | {"argv": args[0]})
        return real_popen(*cast("tuple[Any, ...]", args), **cast("dict[str, Any]", kwargs))

    monkeypatch.setattr(subprocess, "Popen", spying_popen)
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)

    assert receipt.status is SumoWorkflowStatus.COMPLETED_IMPORTED, receipt.findings
    assert receipt.import_outcome is not None
    assert receipt.import_outcome.created is True
    assert receipt.import_outcome.metrics_stored is True
    assert receipt.inputs_verified_unchanged is True
    assert [stage.state.value for stage in receipt.stages] == [
        "accepted",
        "completed",
        "accepted",
        "completed",
    ]
    run_calls = [
        call for call in popen_calls if isinstance(call["argv"], list) and "-c" in call["argv"]
    ]
    assert len(run_calls) == 1
    assert run_calls[0].get("shell") is False
    environment = run_calls[0]["env"]
    assert isinstance(environment, dict)
    assert set(environment) <= {"PATH", "HOME", "LC_ALL", "LANG", "SUMO_HOME"}

    output = Path(request.output_dir)
    for name in ("tripinfo.xml", "summary.xml", "sumo-source.yaml", "execution_receipt.json"):
        assert (output / name).is_file()
    record = load_import_record(output)
    assert record is not None
    assert record.synthetic is True
    assert record.manchester_traffic is False
    assert record.bundle_id.startswith("sumo-exec-")

    summaries = list_imported_sumo_executions(request.registry_path)
    assert len(summaries) == 1
    assert summaries[0].synthetic is True
    assert summaries[0].scenario_id == "traffictwin-synthetic-square-smoke"
    run = Registry(request.registry_path).get_run(summaries[0].run_id)
    assert run.environment_version == "1.27.0"


def test_repeated_import_is_idempotent(
    tmp_path: Path,
    stub_runtime: Path,
) -> None:
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)
    assert receipt.status is SumoWorkflowStatus.COMPLETED_IMPORTED

    record, outcome, _ = import_sumo_execution(request.output_dir, request.registry_path)
    assert outcome.created is False
    assert outcome.idempotent is True
    assert record.stable_fingerprint() == receipt.import_record_stable_fingerprint


def test_registry_conflict_fails_visibly(tmp_path: Path, stub_runtime: Path) -> None:
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)
    assert receipt.status is SumoWorkflowStatus.COMPLETED_IMPORTED
    assert receipt.import_outcome is not None

    registry = Registry(request.registry_path)
    with registry._connect() as conn:  # noqa: SLF001 - direct fixture surgery for the conflict case
        conn.execute(
            "UPDATE bundle_imports SET fingerprint = ? WHERE bundle_id = ?",
            ("d" * 64, receipt.import_outcome.bundle_id),
        )
    with pytest.raises(RegistryConflictError):
        import_sumo_execution(request.output_dir, request.registry_path)


def test_nonzero_exit_never_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = write_stub(tmp_path / "sumo", body="exit 3\n")
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: stub)
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)

    assert receipt.status is SumoWorkflowStatus.EXECUTION_FAILED
    assert receipt.import_outcome is None
    assert not Path(request.output_dir).exists()
    assert not Path(request.registry_path).exists()


def test_timeout_never_imports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stub = write_stub(tmp_path / "sumo", body="sleep 30\n")
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: stub)
    request = workflow_request(tmp_path, timeout_seconds=1)
    receipt = execute_and_import_sumo(request)

    assert receipt.status is SumoWorkflowStatus.EXECUTION_TIMED_OUT
    assert receipt.import_outcome is None
    assert not Path(request.output_dir).exists()


def test_cancellation_never_imports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stub = write_stub(tmp_path / "sumo", body="sleep 30\n")
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: stub)
    cancellation = threading.Event()
    timer = threading.Timer(0.5, cancellation.set)
    timer.start()
    try:
        receipt = execute_and_import_sumo(
            workflow_request(tmp_path),
            cancellation_event=cancellation,
        )
    finally:
        timer.cancel()
    assert receipt.status is SumoWorkflowStatus.EXECUTION_CANCELLED
    assert receipt.import_outcome is None


@pytest.mark.parametrize(
    ("body", "expectation"),
    [
        ("cat > tripinfo.xml <<'X'\n" + VALID_TRIPINFO + "X\nexit 0\n", "missing"),
        (
            "echo 'not xml' > tripinfo.xml\necho 'not xml' > summary.xml\nexit 0\n",
            "malformed",
        ),
        (
            "printf '' > tripinfo.xml\nprintf '' > summary.xml\nexit 0\n",
            "empty",
        ),
    ],
)
def test_partial_missing_or_malformed_outputs_never_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    expectation: str,
) -> None:
    stub = write_stub(tmp_path / "sumo", body=body)
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: stub)
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)

    assert receipt.status is SumoWorkflowStatus.EXECUTION_FAILED, expectation
    assert receipt.import_outcome is None
    assert not Path(request.output_dir).exists()
    assert not Path(request.registry_path).exists()


def test_input_mutation_after_execution_blocks_publication(
    tmp_path: Path,
    stub_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    real_evidence = sumo_service._input_evidence

    def drifting_evidence(root: Path, request: object) -> list[object]:
        calls["count"] += 1
        evidence = real_evidence(root, request)  # type: ignore[arg-type]
        if calls["count"] > 1:
            evidence[0] = evidence[0].model_copy(update={"sha256": "e" * 64})
        return evidence  # type: ignore[return-value]

    monkeypatch.setattr(sumo_service, "_input_evidence", drifting_evidence)
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)

    assert receipt.status is SumoWorkflowStatus.EXECUTION_FAILED
    assert "source inputs changed" in receipt.findings[0]
    assert receipt.import_outcome is None
    assert not Path(request.output_dir).exists()


def test_output_symlink_substitution_refused_at_import(
    tmp_path: Path,
    stub_runtime: Path,
) -> None:
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)
    assert receipt.status is SumoWorkflowStatus.COMPLETED_IMPORTED

    output = Path(request.output_dir)
    output.chmod(0o755)
    original = output / "summary.xml"
    moved = output / "summary-moved.xml"
    original.rename(moved)
    original.symlink_to(moved)
    with pytest.raises(SumoExecutionError, match="missing or unsafe"):
        import_sumo_execution(output, tmp_path / "second-registry.sqlite")


def test_result_directory_symlink_refused_at_import(
    tmp_path: Path,
    stub_runtime: Path,
) -> None:
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)
    assert receipt.status is SumoWorkflowStatus.COMPLETED_IMPORTED

    result_link = tmp_path / "result-link"
    result_link.symlink_to(Path(request.output_dir), target_is_directory=True)
    with pytest.raises(SumoExecutionError, match="non-symlink directory"):
        import_sumo_execution(result_link, tmp_path / "second-registry.sqlite")


def test_receipt_must_name_exact_required_outputs(
    tmp_path: Path,
    stub_runtime: Path,
) -> None:
    request = workflow_request(tmp_path)
    receipt = sumo_service.run_sumo(request)
    incomplete = receipt.model_copy(update={"outputs": receipt.outputs[:1]})

    with pytest.raises(SumoExecutionError, match="exact required outputs"):
        sumo_service._verify_outputs_on_disk(Path(request.output_dir), incomplete)


def test_tampered_published_output_refused_at_import(
    tmp_path: Path,
    stub_runtime: Path,
) -> None:
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)
    assert receipt.status is SumoWorkflowStatus.COMPLETED_IMPORTED

    output = Path(request.output_dir)
    output.chmod(0o755)
    (output / "tripinfo.xml").chmod(0o644)
    (output / "tripinfo.xml").write_text("<tripinfos/>", encoding="utf-8")
    with pytest.raises(SumoExecutionError, match="does not match its receipt identity"):
        import_sumo_execution(output, tmp_path / "second-registry.sqlite")


# --- UI gating ------------------------------------------------------------


def test_one_click_sumo_ui_gating() -> None:
    from traffictwin.ui.pages.sumo_import import one_click_sumo_ready

    assert one_click_sumo_ready("out", "registry.sqlite", True)
    assert not one_click_sumo_ready("", "registry.sqlite", True)
    assert not one_click_sumo_ready("out", " ", True)
    assert not one_click_sumo_ready("out", "registry.sqlite", False)


# --- CLI ------------------------------------------------------------------


def test_cli_execute_and_import_blocked_runtime_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sumo_service, "_discover_executable", lambda: None)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "integration",
            "sumo",
            "execute-and-import",
            "--preset",
            "synthetic_square_smoke",
            "--output",
            str(tmp_path / "out"),
            "--registry",
            str(tmp_path / "registry.sqlite"),
        ],
    )
    assert result.exit_code == 1
    assert "sumo_available: False" in result.output
    assert "workflow: preflight_unavailable" in result.output


def test_cli_execute_and_import_success_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = SumoRuntimeStatus(
        available=True,
        executable_name="sumo",
        executable_sha256="a" * 64,
        version="1.27.0",
        supported=True,
        reason="SUMO 1.27.0 discovered and supported",
    )
    success = SumoWorkflowReceipt(
        status=SumoWorkflowStatus.COMPLETED_IMPORTED,
        preset=SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE,
        stages=[
            SumoWorkflowStage(
                stage=SumoWorkflowStageName.IMPORT,
                state=SumoWorkflowStageState.COMPLETED,
                detail="new registry record sumo-exec-abc",
            )
        ],
        runtime=runtime,
        request_fingerprint="1" * 64,
        preflight_fingerprint="2" * 64,
        receipt_fingerprint="3" * 64,
        output_fingerprint="4" * 64,
        inputs_verified_unchanged=True,
        import_outcome=SumoImportOutcome(
            created=True,
            idempotent=False,
            bundle_id="sumo-exec-abc",
            run_id="sumo-exec-abc",
            adapter_status="accepted",
            metrics_stored=True,
            registry_reference="registry.sqlite",
        ),
        import_record_stable_fingerprint="5" * 64,
    )
    monkeypatch.setattr("traffictwin.cli.execute_and_import_sumo", lambda workflow: success)
    monkeypatch.setattr("traffictwin.cli.sumo_runtime_status", lambda: runtime)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "integration",
            "sumo",
            "execute-and-import",
            "--preset",
            "synthetic_square_smoke",
            "--output",
            str(tmp_path / "out"),
            "--registry",
            str(tmp_path / "registry.sqlite"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "workflow: completed_imported" in result.output
    assert "import_created: True" in result.output


def test_cli_import_result_success_and_failure(
    tmp_path: Path,
    stub_runtime: Path,
) -> None:
    request = workflow_request(tmp_path)
    receipt = execute_and_import_sumo(request)
    assert receipt.status is SumoWorkflowStatus.COMPLETED_IMPORTED
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "integration",
            "sumo",
            "import-result",
            "--result-dir",
            request.output_dir,
            "--registry",
            request.registry_path,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "import_idempotent: True" in result.output
    assert "synthetic: True" in result.output

    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(
        app,
        [
            "integration",
            "sumo",
            "import-result",
            "--result-dir",
            str(empty),
            "--registry",
            request.registry_path,
        ],
    )
    assert result.exit_code == 1
    assert "missing or unsafe" in result.output
