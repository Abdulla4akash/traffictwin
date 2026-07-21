from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.demo.workspace import (
    _workspace_relative,
    initialise_workspace,
    reset_workspace,
    workspace_status,
)


def test_workspace_relative_handles_equivalent_symlinked_roots(tmp_path: Path) -> None:
    canonical_root = tmp_path / "canonical"
    canonical_root.mkdir()
    alias_root = tmp_path / "alias"
    alias_root.symlink_to(canonical_root, target_is_directory=True)

    relative = _workspace_relative(
        alias_root / "demo",
        canonical_root / "demo" / "bundles" / "baseline",
    )

    assert relative == "bundles/baseline"


def test_workspace_initialise_creates_reproducible_demo(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"

    result = initialise_workspace(workspace)
    status = workspace_status(workspace)

    assert result.bundle_count == 62
    assert status.valid_workspace
    assert status.imported_run_count == 62
    assert status.report_count == 4
    assert (workspace / "reports" / "stressed_full.html").exists()
    assert (workspace / "exports" / "trivial_multi_algorithm_evidence.json").exists()
    assert (workspace / "exports" / "trivial_multi_algorithm_winner_map.json").exists()
    assert (workspace / "exports" / "trivial_n_way_ranking.json").exists()
    assert (workspace / "exports" / "trivial_n_way_ranking.md").exists()
    assert (workspace / "exports" / "trivial_n_way_ranking_audit.csv").exists()
    assert (workspace / "exports" / "synthetic_equivalence_study.json").exists()
    assert (workspace / "exports" / "synthetic_equivalence_study.md").exists()
    assert (workspace / "exports" / "synthetic_equivalence_study_audit.csv").exists()
    assert (workspace / "exports" / "synthetic_regression_golden.json").exists()
    assert (workspace / "exports" / "synthetic_regression_gate.json").exists()
    assert (workspace / "exports" / "synthetic_regression_gate.md").exists()
    assert (workspace / "exports" / "synthetic_regression_gate.csv").exists()
    assert (workspace / "exports" / "synthetic_power_analysis.json").exists()
    assert (workspace / "exports" / "synthetic_power_analysis.md").exists()
    assert (workspace / "exports" / "synthetic_power_analysis.csv").exists()
    assert (
        workspace / "exports" / "compare_baseline_vs_stressed_demand_difference_provenance.json"
    ).exists()
    assert (
        workspace / "exports" / "compare_baseline_vs_stressed_demand_difference_provenance.csv"
    ).exists()
    assert (workspace / "exports" / "baseline_completion_provenance.dot").exists()
    assert (workspace / "exports" / "baseline_completion_provenance.graphml").exists()
    assert (workspace / "exports" / "baseline_provenance_completeness.json").exists()
    assert (workspace / "exports" / "baseline_provenance_completeness.csv").exists()
    assert (
        workspace / "exports" / "compare_baseline_vs_stressed_demand_provenance_completeness.json"
    ).exists()
    assert (workspace / "exports" / "synthetic_portfolio_evaluation.json").exists()
    assert (workspace / "exports" / "synthetic_portfolio_study_winner_map.json").exists()
    assert (workspace / "exports" / "synthetic_portfolio_held_out_study.json").exists()


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

    assert result.imported_run_count == 62
    assert workspace_status(workspace).valid_workspace
