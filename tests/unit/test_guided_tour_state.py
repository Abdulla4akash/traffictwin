"""The Guided Demo tour state machine is deterministic and presentation-only."""

from __future__ import annotations

import pytest

from traffictwin.ui.guided_tour import (
    DEFAULT_TOUR_SPEED_SECONDS,
    HISTORICAL_TOUR_STAGES,
    LIVE_BODS_TOUR_STAGES,
    SYNTHETIC_TOUR_STAGES,
    GuidedDemoMode,
    GuidedTourState,
    advance_tour,
    next_stage,
    pause_tour,
    play_tour,
    previous_stage,
    restart_tour,
    stages_for_mode,
    start_tour,
)


class TestTheStageScripts:
    def test_each_mode_has_its_declared_stage_count(self) -> None:
        assert len(SYNTHETIC_TOUR_STAGES) == 7
        assert len(LIVE_BODS_TOUR_STAGES) == 1
        assert len(HISTORICAL_TOUR_STAGES) == 6

    def test_stage_keys_are_unique_within_each_mode(self) -> None:
        for mode in GuidedDemoMode:
            keys = [stage.key for stage in stages_for_mode(mode)]
            assert len(keys) == len(set(keys))

    def test_every_stage_has_a_title(self) -> None:
        for mode in GuidedDemoMode:
            for stage in stages_for_mode(mode):
                assert stage.title.strip()


class TestStartingATour:
    def test_a_tour_starts_at_the_first_stage_playing(self) -> None:
        state = start_tour(GuidedDemoMode.SYNTHETIC)
        assert state.stage_index == 0
        assert state.playing is True
        assert state.elapsed_in_stage_seconds == 0.0
        assert state.speed_seconds == DEFAULT_TOUR_SPEED_SECONDS

    def test_an_out_of_range_stage_index_is_refused(self) -> None:
        with pytest.raises(ValueError):
            GuidedTourState(mode=GuidedDemoMode.HISTORICAL, stage_index=6)
        with pytest.raises(ValueError):
            GuidedTourState(mode=GuidedDemoMode.SYNTHETIC, stage_index=-1)

    def test_a_non_positive_speed_is_refused(self) -> None:
        with pytest.raises(ValueError):
            GuidedTourState(mode=GuidedDemoMode.SYNTHETIC, speed_seconds=0.0)


class TestAutomaticProgression:
    def test_progression_is_deterministic_tick_by_tick(self) -> None:
        state = start_tour(GuidedDemoMode.SYNTHETIC)
        observed: list[int] = []
        for _ in range(40):
            observed.append(state.stage_index)
            state = advance_tour(state, tick_seconds=1.0)
        replay = start_tour(GuidedDemoMode.SYNTHETIC)
        replayed: list[int] = []
        for _ in range(40):
            replayed.append(replay.stage_index)
            replay = advance_tour(replay, tick_seconds=1.0)
        assert observed == replayed

    def test_a_stage_holds_for_the_declared_speed(self) -> None:
        state = start_tour(GuidedDemoMode.SYNTHETIC)
        for _ in range(3):
            state = advance_tour(state, tick_seconds=1.0)
            assert state.stage_index == 0
        state = advance_tour(state, tick_seconds=1.0)
        assert state.stage_index == 1

    def test_the_final_stage_stops_instead_of_wrapping(self) -> None:
        last = len(HISTORICAL_TOUR_STAGES) - 1
        state = GuidedTourState(mode=GuidedDemoMode.HISTORICAL, stage_index=last)
        for _ in range(8):
            state = advance_tour(state, tick_seconds=1.0)
        assert state.stage_index == last
        assert state.playing is False

    def test_a_full_synthetic_run_visits_every_stage_in_order(self) -> None:
        state = start_tour(GuidedDemoMode.SYNTHETIC)
        visited = [state.stage_index]
        for _ in range(7 * 4 + 4):
            state = advance_tour(state, tick_seconds=1.0)
            if state.stage_index != visited[-1]:
                visited.append(state.stage_index)
        assert visited == list(range(len(SYNTHETIC_TOUR_STAGES)))
        assert state.playing is False

    def test_a_non_positive_tick_is_refused(self) -> None:
        state = start_tour(GuidedDemoMode.SYNTHETIC)
        with pytest.raises(ValueError):
            advance_tour(state, tick_seconds=0.0)


class TestPauseAndPlay:
    def test_pause_stops_automatic_progression(self) -> None:
        state = pause_tour(start_tour(GuidedDemoMode.SYNTHETIC))
        for _ in range(20):
            state = advance_tour(state, tick_seconds=1.0)
        assert state.stage_index == 0
        assert state.playing is False

    def test_play_resumes_from_the_current_stage(self) -> None:
        state = pause_tour(next_stage(start_tour(GuidedDemoMode.SYNTHETIC)))
        state = play_tour(state)
        assert state.playing is True
        assert state.stage_index == 1
        assert state.elapsed_in_stage_seconds == 0.0


class TestManualNavigation:
    def test_next_moves_forward_and_clamps_at_the_end(self) -> None:
        state = start_tour(GuidedDemoMode.HISTORICAL)
        for expected in (1, 2, 3, 4, 5, 5):
            state = next_stage(state)
            assert state.stage_index == expected

    def test_previous_moves_back_and_clamps_at_the_start(self) -> None:
        state = next_stage(next_stage(start_tour(GuidedDemoMode.HISTORICAL)))
        for expected in (1, 0, 0):
            state = previous_stage(state)
            assert state.stage_index == expected

    def test_manual_navigation_works_while_paused(self) -> None:
        state = pause_tour(start_tour(GuidedDemoMode.SYNTHETIC))
        state = next_stage(state)
        assert state.stage_index == 1
        assert state.playing is False

    def test_manual_navigation_resets_the_stage_clock(self) -> None:
        state = advance_tour(start_tour(GuidedDemoMode.SYNTHETIC), tick_seconds=2.5)
        assert state.elapsed_in_stage_seconds == 2.5
        assert next_stage(state).elapsed_in_stage_seconds == 0.0
        assert previous_stage(state).elapsed_in_stage_seconds == 0.0


class TestRestart:
    def test_restart_returns_to_the_first_stage_and_plays(self) -> None:
        state = pause_tour(next_stage(next_stage(start_tour(GuidedDemoMode.SYNTHETIC))))
        state = restart_tour(state)
        assert state.stage_index == 0
        assert state.playing is True
        assert state.elapsed_in_stage_seconds == 0.0
