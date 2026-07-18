from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.tos_helpers import write_tos_package
from traffictwin.integration.tos import (
    audit_tos_package,
    build_evaluation_matrix,
    build_generalisation_matrix,
    build_static_results_atlas,
    build_tos_research_report,
    compare_campaigns,
    list_training_runs,
    load_training_run,
    read_evaluation_runs,
    summarise_rsu_run,
    summarise_task_outcomes,
    summarise_trace,
    write_tos_results_pack,
)
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.ui.tos_replay_state import (
    TosReplayControl,
    advance_replay,
    restart_replay,
    step_replay,
)

FIXED_TIME = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def test_evaluation_matrix_and_paired_comparison_are_deterministic(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    rows = read_evaluation_runs(package)
    matrix = build_evaluation_matrix(rows, package, clock=fixed_clock)
    comparison = compare_campaigns(
        rows,
        package,
        "baseline",
        "capscalar_mappo",
        clock=fixed_clock,
    )

    assert matrix.generated_at == FIXED_TIME
    assert [entry.campaign for entry in matrix.entries] == ["baseline", "capscalar_mappo"]
    assert matrix.entries[0].statistics.mean == pytest.approx(0.9)
    assert matrix.entries[0].statistics.sample_sd is None
    item = comparison.comparisons[0]
    assert item.paired_difference_statistics.n == 1
    assert item.paired_difference_statistics.mean == pytest.approx(0.03)
    assert item.observations[0].relative_delta == pytest.approx(1 / 30)
    assert item.compatibility_findings == ["obs_variant differs: onehot17 vs capscalar13"]
    assert (
        comparison.to_json()
        == compare_campaigns(
            rows,
            package,
            "baseline",
            "capscalar_mappo",
            clock=fixed_clock,
        ).to_json()
    )


def test_generalisation_keeps_unsupported_relationships_unknown(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    matrix = build_generalisation_matrix(read_evaluation_runs(package), package)
    domains = {(entry.campaign, entry.cell): entry for entry in matrix.entries}

    assert domains[("baseline", "wd_am")].evaluation_domain.value == "unknown"
    assert domains[("capscalar_mappo", "wd_am")].evaluation_domain.value == "held_out"
    assert "does not explicitly classify" in domains[("baseline", "wd_am")].evidence_statement


def test_training_reader_preserves_warmup_unavailability(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    summaries = list_training_runs(package)
    run = load_training_run(package, "baseline", max_points=2)

    assert len(summaries) == 2
    assert summaries[0].warmup_unavailable_count == 1
    assert run.downsampled
    assert len(run.points) == 2
    assert run.points[0].mean_completion is None
    assert run.points[-1].mean_completion == pytest.approx(0.9)
    assert run.greedy_evaluation is not None
    assert "NaN" not in run.model_dump_json()


def test_trace_rsu_and_task_summaries_keep_source_semantics(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    key = "baseline_uk2030_wd_am_fs0"
    trace = summarise_trace(package, "trace_wd_am_fullrsu.npz", max_profile_points=2)
    rsu = summarise_rsu_run(package, key)
    tasks = summarise_task_outcomes(package, key)

    assert trace.timeline_point_count == 3
    assert trace.observation_count == 5
    assert trace.speed_mps.mean == pytest.approx(1.0)
    assert len(trace.profile) == 2
    assert rsu.rsus[0].concurrency_pressure_fraction.maximum == pytest.approx(0.4)
    assert rsu.rsus[0].remaining_compute_backlog_ms.maximum == pytest.approx(1200.0)
    assert tasks.task_count == 4
    assert tasks.deadline_success_rate == pytest.approx(0.75)
    assert tasks.latency_ms.p50 == pytest.approx(115.0)
    assert tasks.deadline_consistency_verified
    assert [item.group for item in tasks.by_task_class] == ["T1", "T2", "T3"]
    assert [item.group for item in tasks.by_decision] == ["local", "v2i", "v2v"]


def test_audit_and_exports_are_permission_conscious_and_path_safe(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    source_before = {
        path.relative_to(package): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    }
    audit = audit_tos_package(package, clock=fixed_clock)
    report = build_tos_research_report(
        package, variation_campaign="capscalar_mappo", clock=fixed_clock
    )
    markdown = report_to_markdown(report)
    atlas = build_static_results_atlas(package, clock=fixed_clock)
    pack = write_tos_results_pack(
        package,
        tmp_path / "results",
        variation_campaign="capscalar_mappo",
        clock=fixed_clock,
    )

    assert audit.evaluation_run_count == 2
    assert audit.actor_training_history_match_count == 2
    assert "CHECKPOINT_PAYLOADS_UNAVAILABLE" in {check.code for check in audit.checks}
    assert "imported simulation" in markdown.lower()
    assert "permission" in atlas.lower()
    assert "/Users/" not in markdown + atlas
    assert "NaN" not in atlas
    assert pack.atlas_html.is_file()
    assert pack.audit_json.is_file()
    with pytest.raises(FileExistsError):
        write_tos_results_pack(package, pack.directory, clock=fixed_clock)
    source_after = {
        path.relative_to(package): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file()
    }
    assert source_before == source_after


def test_logical_replay_controls_are_deterministic() -> None:
    playing = TosReplayControl(position=0.0, playing=True, speed=0.5)

    assert advance_replay(playing, 10).position == pytest.approx(0.25)
    assert step_replay(playing, 10, 1) == TosReplayControl(position=1.0, playing=False, speed=0.5)
    assert step_replay(playing, 10, -1).position == 0.0
    assert restart_replay(TosReplayControl(5.0, True, 2.0)).position == 0.0
    assert not advance_replay(TosReplayControl(10.0, True, 5.0), 10).playing
