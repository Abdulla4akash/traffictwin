"""Unit coverage for the derived per-RSU load measures behind the RSU Monitor."""

from __future__ import annotations

import pytest

from traffictwin.integration.tos.models import TosRsuReplayPoint
from traffictwin.ui.rsu_monitor_services import (
    RsuMonitorError,
    build_rsu_monitor_view,
    unavailable_measurements,
)

SOURCE = "instrumented/perstep/run_perstep.npz"


def _point(
    *,
    index: int,
    reference: str,
    rsu_index: int,
    active: int,
    backlog: float,
    maximum: int = 4,
) -> TosRsuReplayPoint:
    return TosRsuReplayPoint(
        index=index,
        timestamp_s=float(index),
        rsu_reference=reference,
        rsu_index=rsu_index,
        active_task_count=active,
        remaining_compute_backlog_ms=backlog,
        max_concurrent_tasks=maximum,
        concurrency_pressure_fraction=active / maximum,
        source_file=SOURCE,
    )


def _window() -> list[TosRsuReplayPoint]:
    """Two RSUs over three steps; RSU_1 is deliberately the overwhelmed one."""

    return [
        _point(index=0, reference="RSU_0", rsu_index=0, active=1, backlog=100.0),
        _point(index=0, reference="RSU_1", rsu_index=1, active=4, backlog=900.0),
        _point(index=1, reference="RSU_0", rsu_index=0, active=1, backlog=120.0),
        _point(index=1, reference="RSU_1", rsu_index=1, active=4, backlog=1500.0),
        _point(index=2, reference="RSU_0", rsu_index=0, active=0, backlog=0.0),
        _point(index=2, reference="RSU_1", rsu_index=1, active=2, backlog=700.0),
    ]


def test_empty_history_is_an_explicit_error_not_an_empty_view() -> None:
    outcome = build_rsu_monitor_view([], "run-a")

    assert isinstance(outcome, RsuMonitorError)
    assert "no RSU history points" in outcome.message


def test_mixed_source_files_are_refused_as_not_one_window() -> None:
    points = _window()
    points[-1] = points[-1].model_copy(update={"source_file": "instrumented/other.npz"})

    outcome = build_rsu_monitor_view(points, "run-a")

    assert isinstance(outcome, RsuMonitorError)
    assert "more than one source file" in outcome.message


def test_window_identity_records_the_run_and_its_exact_bounds() -> None:
    view = build_rsu_monitor_view(_window(), "baseline_uk2030_wd_am_fs0", stride=10)

    assert not isinstance(view, RsuMonitorError)
    identity = view.identity
    assert identity.run_key == "baseline_uk2030_wd_am_fs0"
    assert identity.source_file == SOURCE
    assert identity.first_timestamp_s == 0.0
    assert identity.last_timestamp_s == 2.0
    assert identity.window_duration_s == 2.0
    assert identity.point_count == 6
    assert identity.rsu_count == 2
    assert identity.stride == 10


def test_profiles_are_ordered_busiest_first_and_carry_peak_timestamps() -> None:
    view = build_rsu_monitor_view(_window(), "run-a")

    assert not isinstance(view, RsuMonitorError)
    assert view.rsu_references == ("RSU_1", "RSU_0")
    busiest = view.profiles[0]
    assert busiest.rsu_reference == "RSU_1"
    assert busiest.observation_count == 3
    assert busiest.mean_pressure == pytest.approx((1.0 + 1.0 + 0.5) / 3)
    assert busiest.peak_pressure == pytest.approx(1.0)
    assert busiest.peak_active_task_count == 4
    assert busiest.mean_active_task_count == pytest.approx(10 / 3)
    assert busiest.peak_backlog_ms == pytest.approx(1500.0)
    assert busiest.peak_backlog_timestamp_s == 1.0
    assert busiest.mean_backlog_ms == pytest.approx((900.0 + 1500.0 + 700.0) / 3)


def test_saturation_counts_observations_at_the_recorded_maximum() -> None:
    view = build_rsu_monitor_view(_window(), "run-a")

    assert not isinstance(view, RsuMonitorError)
    busiest = view.profile_for("RSU_1")
    quietest = view.profile_for("RSU_0")
    assert busiest is not None
    assert quietest is not None
    assert busiest.saturated_observation_count == 2
    assert busiest.saturated_share == pytest.approx(2 / 3)
    assert quietest.saturated_observation_count == 0
    assert quietest.saturated_share == 0.0


def test_unknown_rsu_reference_returns_none_rather_than_a_default() -> None:
    view = build_rsu_monitor_view(_window(), "run-a")

    assert not isinstance(view, RsuMonitorError)
    assert view.profile_for("RSU_9") is None


def test_asymmetry_names_the_busiest_rsu_and_quantifies_the_imbalance() -> None:
    view = build_rsu_monitor_view(_window(), "run-a")

    assert not isinstance(view, RsuMonitorError)
    asymmetry = view.asymmetry
    assert asymmetry.rsu_count == 2
    assert asymmetry.busiest_rsu_reference == "RSU_1"
    assert asymmetry.quietest_rsu_reference == "RSU_0"
    assert asymmetry.highest_mean_pressure == pytest.approx(2.5 / 3)
    assert asymmetry.lowest_mean_pressure == pytest.approx(0.5 / 3)
    assert asymmetry.mean_pressure_spread == pytest.approx(2.0 / 3)
    # RSU_1 carries 10 of the 12 in-flight task-observations in the window.
    assert asymmetry.busiest_share_of_active_task_time == pytest.approx(10 / 12)
    assert asymmetry.even_share == pytest.approx(0.5)
    assert asymmetry.busiest_share_ratio_to_even == pytest.approx((10 / 12) / 0.5)
    assert asymmetry.saturated_rsu_count == 1


def test_a_perfectly_even_window_reports_no_spread() -> None:
    points = [
        _point(index=0, reference="RSU_0", rsu_index=0, active=2, backlog=50.0),
        _point(index=0, reference="RSU_1", rsu_index=1, active=2, backlog=50.0),
    ]

    view = build_rsu_monitor_view(points, "run-a")

    assert not isinstance(view, RsuMonitorError)
    assert view.asymmetry.mean_pressure_spread == pytest.approx(0.0)
    assert view.asymmetry.busiest_share_of_active_task_time == pytest.approx(0.5)
    assert view.asymmetry.busiest_share_ratio_to_even == pytest.approx(1.0)
    assert view.asymmetry.saturated_rsu_count == 0


def test_a_single_rsu_window_carries_the_whole_share() -> None:
    points = [_point(index=0, reference="RSU_0", rsu_index=0, active=1, backlog=10.0)]

    view = build_rsu_monitor_view(points, "run-a")

    assert not isinstance(view, RsuMonitorError)
    assert view.asymmetry.rsu_count == 1
    assert view.asymmetry.busiest_share_of_active_task_time == pytest.approx(1.0)
    assert view.asymmetry.even_share == pytest.approx(1.0)
    assert view.asymmetry.mean_pressure_spread == pytest.approx(0.0)


def test_an_idle_window_reports_zero_share_without_dividing_by_zero() -> None:
    points = [
        _point(index=0, reference="RSU_0", rsu_index=0, active=0, backlog=0.0),
        _point(index=0, reference="RSU_1", rsu_index=1, active=0, backlog=0.0),
    ]

    view = build_rsu_monitor_view(points, "run-a")

    assert not isinstance(view, RsuMonitorError)
    assert view.asymmetry.busiest_share_of_active_task_time == 0.0
    assert view.asymmetry.busiest_share_ratio_to_even == 0.0


def test_energy_and_processed_tasks_stay_typed_unavailable() -> None:
    view = build_rsu_monitor_view(_window(), "run-a")

    assert not isinstance(view, RsuMonitorError)
    assert view.unavailable == unavailable_measurements()
    measurements = {item.measurement: item for item in view.unavailable}
    assert set(measurements) == {
        "per-RSU energy over the window",
        "per-RSU processed-task count",
    }
    assert all(item.status == "unavailable" for item in view.unavailable)
    assert "whole-run average per task" in measurements["per-RSU energy over the window"].reason
    assert "no RSU attribution" in measurements["per-RSU processed-task count"].reason
