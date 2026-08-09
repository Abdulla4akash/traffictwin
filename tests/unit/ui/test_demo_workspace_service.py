"""Thin service over demo workspace creation."""

from __future__ import annotations

from pathlib import Path

from traffictwin.ui.demo_workspace_service import (
    DEFAULT_DEMO_WORKSPACE_PATH,
    ensure_demo_workspace,
    inspect_demo_workspace,
)


def test_ensure_creates_deterministic_demo_with_counts(tmp_path: Path) -> None:
    workspace = tmp_path / "demo-a"

    result = ensure_demo_workspace(workspace)

    assert result.status == "created"
    assert result.reason == "created"
    assert result.workspace_valid
    assert result.scenario_count == 62
    assert result.imported_run_count == 62
    assert result.comparison_count == 3
    assert (workspace / "workspace.yaml").exists()
    assert (workspace / "registry.sqlite").exists()
    assert "synthetic" in result.message.lower()


def test_ensure_is_idempotent_on_existing_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "demo-b"
    first = ensure_demo_workspace(workspace)
    assert first.status == "created"

    second = ensure_demo_workspace(workspace)

    assert second.status == "already_exists"
    assert second.reason == "already_exists"
    assert second.workspace_valid
    assert second.scenario_count == first.scenario_count
    assert "already exists" in second.message.lower()


def test_ensure_refuses_non_empty_without_marker(tmp_path: Path) -> None:
    workspace = tmp_path / "occupied"
    workspace.mkdir()
    (workspace / "user.txt").write_text("keep me", encoding="utf-8")

    result = ensure_demo_workspace(workspace)

    assert result.status == "failed"
    assert result.reason == "non_empty_without_force"
    assert not result.workspace_valid


def test_ensure_rejects_unsafe_paths(tmp_path: Path) -> None:
    for unsafe in [Path("/"), Path.home(), Path.cwd()]:
        result = ensure_demo_workspace(unsafe)

        assert result.status == "failed"
        assert result.reason == "unsafe_path"


def test_ensure_rejects_none_and_empty_string() -> None:
    for bad in [None, "", "   "]:
        result = ensure_demo_workspace(bad)

        assert result.status == "failed"
        assert result.reason == "invalid_path"


def test_ensure_accepts_string_path(tmp_path: Path) -> None:
    workspace = tmp_path / "string-path"

    result = ensure_demo_workspace(str(workspace))

    assert result.status == "created"
    assert result.workspace_valid


def test_ensure_trims_whitespace(tmp_path: Path) -> None:
    workspace = tmp_path / "trimmed"

    result = ensure_demo_workspace(f"  {workspace}  ")

    assert result.status == "created"


def test_inspect_reports_ready_for_existing(tmp_path: Path) -> None:
    workspace = tmp_path / "inspect-ready"
    ensure_demo_workspace(workspace)

    result = inspect_demo_workspace(workspace)

    assert result.status == "ready"
    assert result.reason == "ready"
    assert result.workspace_valid
    assert result.scenario_count == 62


def test_inspect_reports_failed_for_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "does-not-exist"

    result = inspect_demo_workspace(workspace)

    assert result.status == "failed"
    assert not result.workspace_valid


def test_default_path_is_repo_relative() -> None:
    assert Path(".traffictwin-demo") == DEFAULT_DEMO_WORKSPACE_PATH
