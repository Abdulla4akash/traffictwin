"""Real bounded acceptance test for the controlled one-click SUMO workflow.

Runs only when a genuine supported Eclipse SUMO binary is discoverable. The
synthetic-stub unit tests deliberately cannot satisfy this gate.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from traffictwin.integration.sumo import validate_sumo_results
from traffictwin.integration.sumo_execution import (
    SumoExecutionPreset,
    SumoWorkflowRequest,
    SumoWorkflowStatus,
    execute_and_import_sumo,
    import_sumo_execution,
    preset_definition,
    preset_scenario_root,
    sumo_runtime_status,
)
from traffictwin.storage.registry import Registry


def _scenario_hashes() -> dict[str, str]:
    root = preset_scenario_root()
    return {
        item.name: hashlib.sha256((root / item.name).read_bytes()).hexdigest()
        for item in preset_definition(SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE).inputs
    }


def test_real_sumo_smoke_preset_executes_validates_imports_and_reimports(
    tmp_path: Path,
) -> None:
    runtime = sumo_runtime_status()
    if not runtime.supported:
        pytest.skip(f"real SUMO runtime unavailable: {runtime.reason}")

    inputs_before = _scenario_hashes()
    request = SumoWorkflowRequest(
        preset=SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE,
        output_dir=str(tmp_path / "real-smoke"),
        registry_path=str(tmp_path / "registry.sqlite"),
    )
    receipt = execute_and_import_sumo(request)

    assert receipt.status is SumoWorkflowStatus.COMPLETED_IMPORTED, receipt.findings
    assert receipt.import_outcome is not None
    assert receipt.import_outcome.created is True
    assert receipt.inputs_verified_unchanged is True

    output = Path(request.output_dir)
    validation = validate_sumo_results(output)
    assert validation.report.may_import
    assert validation.manifest is not None
    assert validation.manifest.source.synthetic is True
    assert validation.manifest.source.sumo_version == runtime.version
    assert {item.path for item in receipt.outputs} == {"summary.xml", "tripinfo.xml"}

    record, second, _ = import_sumo_execution(request.output_dir, request.registry_path)
    assert second.idempotent is True
    assert record.stable_fingerprint() == receipt.import_record_stable_fingerprint

    run = Registry(request.registry_path).get_run(receipt.import_outcome.run_id)
    assert run.status.value == "imported"

    assert _scenario_hashes() == inputs_before
