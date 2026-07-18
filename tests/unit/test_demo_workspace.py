from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.demo.workspace import initialise_workspace, reset_workspace, workspace_status


def test_workspace_initialise_creates_reproducible_demo(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"

    result = initialise_workspace(workspace)
    status = workspace_status(workspace)

    assert result.bundle_count == 15
    assert status.valid_workspace
    assert status.imported_run_count == 15
    assert status.report_count == 4
    assert (workspace / "reports" / "stressed_full.html").exists()
    assert (workspace / "exports" / "trivial_multi_algorithm_evidence.json").exists()


def test_workspace_initialise_refuses_non_empty_path(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"
    workspace.mkdir()
    (workspace / "note.txt").write_text("user content", encoding="utf-8")

    with pytest.raises(FileExistsError):
        initialise_workspace(workspace)


def test_workspace_reset_requires_confirmation(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)

    with pytest.raises(PermissionError):
        reset_workspace(workspace)


def test_workspace_reset_regenerates_marked_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)

    result = reset_workspace(workspace, yes=True)

    assert result.imported_run_count == 15
    assert workspace_status(workspace).valid_workspace
