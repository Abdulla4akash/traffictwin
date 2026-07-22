"""Bounded real two-step acceptance test for the one-click execute-and-import workflow."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from traffictwin.integration.vec_orchestration import (
    VecExecutionPreset,
    VecWorkflowRequest,
    VecWorkflowStatus,
    execute_and_import,
    import_vec_execution,
)
from traffictwin.integration.vec_orchestration.models import REVIEWED_WEEKEND_TRACE_SHA256
from traffictwin.storage.registry import Registry

VEC_REPO = Path("../external/vec_env")
TOS_REPO = Path("../external/tos-data")
TRACE = TOS_REPO / "traces" / "trace_we_fullrsu.npz"


def _repository_state(repo: Path) -> tuple[str, str, str]:
    git = shutil.which("git")
    assert git is not None
    results = []
    for args in (
        ("rev-parse", "HEAD"),
        ("rev-parse", "refs/remotes/origin/main"),
        ("status", "--porcelain=v1", "--untracked-files=all"),
    ):
        results.append(
            subprocess.run(  # noqa: S603 - resolved Git and fixed read-only argv
                [git, "-C", str(repo), *args],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    return results[0], results[1], results[2]


def test_real_smoke_preset_executes_imports_and_reimports_idempotently(
    tmp_path: Path,
) -> None:
    if not VEC_REPO.is_dir() or not TOS_REPO.is_dir() or not TRACE.is_file():
        pytest.skip("the reviewed external VEC repositories are not available")
    if hashlib.sha256(TRACE.read_bytes()).hexdigest() != REVIEWED_WEEKEND_TRACE_SHA256:
        pytest.skip("the reviewed trace is not available at the audited identity")
    pytest.importorskip("jax")

    source_before = (_repository_state(VEC_REPO), _repository_state(TOS_REPO))
    output_dir = tmp_path / "one-click-smoke"
    registry_path = tmp_path / "registry.sqlite"
    workflow = VecWorkflowRequest(
        preset=VecExecutionPreset.SMOKE_TWO_STEP,
        input_root=str(TOS_REPO),
        vec_repo=str(VEC_REPO),
        tos_data_repo=str(TOS_REPO),
        output_dir=str(output_dir),
        registry_path=str(registry_path),
    )

    receipt = execute_and_import(workflow)

    assert receipt.status is VecWorkflowStatus.COMPLETED_IMPORTED, receipt.findings
    assert receipt.import_outcome is not None
    assert receipt.import_outcome.created is True
    assert receipt.external_repositories_verified_unchanged is True
    assert receipt.raw_inputs_verified_unchanged is True
    assert {stage.stage.value for stage in receipt.stages} == {
        "preflight",
        "execution",
        "validation",
        "import",
    }
    assert (output_dir / "execution_receipt.json").is_file()
    assert (output_dir / "run.json").is_file()

    registry = Registry(registry_path)
    run = registry.get_run(receipt.import_outcome.registry_run_id)
    assert run.status.value == "completed"
    assert run.algorithm == "ukfleettrain_mappo_model_c_17"

    record, second = import_vec_execution(
        output_dir,
        registry_path,
        vec_repo=VEC_REPO,
        tos_data_repo=TOS_REPO,
    )
    assert second.idempotent is True
    assert second.stable_fingerprint == receipt.import_record_stable_fingerprint
    assert record.scientific_admission_status == "unavailable"
    assert record.smoke_output_is_scientific_finding is False

    assert (_repository_state(VEC_REPO), _repository_state(TOS_REPO)) == source_before
    assert hashlib.sha256(TRACE.read_bytes()).hexdigest() == REVIEWED_WEEKEND_TRACE_SHA256
