"""Contract and fail-closed tests for the VEC-10 thin interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.integration.vec_interface import (
    VecInterfaceError,
    VecInterfaceSnapshot,
    VecOperationStatus,
    VecRepositorySnapshot,
    load_run_request,
    vec_interface_contract,
)


def test_contract_exposes_only_typed_foreground_operations() -> None:
    contract = vec_interface_contract()

    assert contract.capability_id == "VEC-10"
    assert contract.execution_mode == "foreground_current_process_only"
    assert "run_foreground" in contract.operations
    assert "arbitrary command or flags" in contract.prohibited_controls
    assert "background or persistent asynchronous queue" in contract.prohibited_controls
    assert contract.fingerprint() == vec_interface_contract().fingerprint()


def test_repository_and_operation_catalogues_fail_closed() -> None:
    repository = VecRepositorySnapshot(
        repository="vec_env",
        audited_commit="a" * 40,
        worktree_head="b" * 40,
        origin_main="a" * 40,
        clean=True,
        audited_commit_available=True,
        ready_for_exact_blob_access=True,
    )
    with pytest.raises(ValidationError, match="readiness"):
        repository.model_copy(update={"clean": False}).model_validate(
            repository.model_copy(update={"clean": False}).model_dump()
        )
    with pytest.raises(ValidationError, match="repository snapshots"):
        VecInterfaceSnapshot(
            repositories=(repository, repository),
            operations=tuple(
                VecOperationStatus(operation=name, availability="ready", reason="tested")
                for name in (
                    "snapshot",
                    "validate",
                    "preprocess",
                    "run",
                    "monitor_current_process",
                    "inspect",
                    "compare",
                    "export",
                )
            ),
        )


def test_request_loader_rejects_arbitrary_or_extra_fields(tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "run_id": "unsafe",
                "trace_file": "trace.npz",
                "trace_sha256": "a" * 64,
                "actor_id": "baseline_model_c_17",
                "shell_command": "python anything.py",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(VecInterfaceError, match="shell_command"):
        load_run_request(request)
