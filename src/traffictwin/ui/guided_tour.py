"""Framework-free state machine for the Guided Demo mode tour.

The tour is a presentation device only. A tour step is a slide in a scripted
walkthrough of evidence that already exists. Advancing a step never runs a
simulation, never acquires provider data, never records workflow progress,
and never changes evidence. The cadence is presentation time, not simulation
or provider time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

DEFAULT_TOUR_SPEED_SECONDS = 4.0
TOUR_TICK_SECONDS = 1.0


class GuidedDemoMode(StrEnum):
    """The three Guided Demo modes offered by the launcher."""

    SYNTHETIC = "synthetic"
    LIVE_BODS = "live_bods"
    HISTORICAL = "historical"


@dataclass(frozen=True)
class GuidedTourStage:
    """One presentation stage of a mode tour."""

    key: str
    title: str


SYNTHETIC_TOUR_STAGES: tuple[GuidedTourStage, ...] = (
    GuidedTourStage(key="baseline", title="Meet the baseline scenario"),
    GuidedTourStage(key="variation", title="Introduce the stressed variation"),
    GuidedTourStage(key="compatibility", title="Confirm the pair is comparable"),
    GuidedTourStage(key="traffic", title="Traffic consequences"),
    GuidedTourStage(key="vec", title="VEC consequences"),
    GuidedTourStage(key="provenance", title="Comparison and provenance"),
    GuidedTourStage(key="takeaway", title="Takeaway"),
)

LIVE_BODS_TOUR_STAGES: tuple[GuidedTourStage, ...] = (
    GuidedTourStage(key="live-scene", title="Latest accepted BODS bus positions"),
)

HISTORICAL_TOUR_STAGES: tuple[GuidedTourStage, ...] = (
    GuidedTourStage(key="source", title="Identify the historical source"),
    GuidedTourStage(key="context", title="Location and network context"),
    GuidedTourStage(key="observations", title="Traffic observations"),
    GuidedTourStage(key="temporal", title="Temporal behaviour"),
    GuidedTourStage(key="lineage", title="Provenance and lineage"),
    GuidedTourStage(key="interpretation", title="Interpretation"),
)

_STAGES_BY_MODE: dict[GuidedDemoMode, tuple[GuidedTourStage, ...]] = {
    GuidedDemoMode.SYNTHETIC: SYNTHETIC_TOUR_STAGES,
    GuidedDemoMode.LIVE_BODS: LIVE_BODS_TOUR_STAGES,
    GuidedDemoMode.HISTORICAL: HISTORICAL_TOUR_STAGES,
}


def stages_for_mode(mode: GuidedDemoMode) -> tuple[GuidedTourStage, ...]:
    """Return the ordered presentation stages for one mode."""
    return _STAGES_BY_MODE[mode]


@dataclass(frozen=True)
class GuidedTourState:
    """Presentation position inside one mode tour.

    ``elapsed_in_stage_seconds`` accumulates declared ticks, never wall-clock
    reads, so the machine stays deterministic under test.
    """

    mode: GuidedDemoMode
    stage_index: int = 0
    playing: bool = True
    elapsed_in_stage_seconds: float = 0.0
    speed_seconds: float = DEFAULT_TOUR_SPEED_SECONDS

    def __post_init__(self) -> None:
        stage_count = len(stages_for_mode(self.mode))
        if not 0 <= self.stage_index < stage_count:
            raise ValueError(f"stage_index {self.stage_index} outside 0..{stage_count - 1}")
        if self.elapsed_in_stage_seconds < 0:
            raise ValueError("elapsed_in_stage_seconds must not be negative")
        if self.speed_seconds <= 0:
            raise ValueError("speed_seconds must be positive")


def start_tour(mode: GuidedDemoMode) -> GuidedTourState:
    """Start a mode tour at its first stage, playing."""
    return GuidedTourState(mode=mode)


def advance_tour(
    state: GuidedTourState, *, tick_seconds: float = TOUR_TICK_SECONDS
) -> GuidedTourState:
    """Advance presentation time by one declared tick.

    A paused tour never advances. A tour that reaches its final stage stops
    on it instead of wrapping.
    """
    if tick_seconds <= 0:
        raise ValueError("tick_seconds must be positive")
    if not state.playing:
        return state
    elapsed = state.elapsed_in_stage_seconds + tick_seconds
    if elapsed < state.speed_seconds:
        return replace(state, elapsed_in_stage_seconds=elapsed)
    last_index = len(stages_for_mode(state.mode)) - 1
    if state.stage_index >= last_index:
        return replace(state, playing=False, elapsed_in_stage_seconds=0.0)
    return replace(state, stage_index=state.stage_index + 1, elapsed_in_stage_seconds=0.0)


def next_stage(state: GuidedTourState) -> GuidedTourState:
    """Move one stage forward; the final stage clamps."""
    last_index = len(stages_for_mode(state.mode)) - 1
    return replace(
        state,
        stage_index=min(state.stage_index + 1, last_index),
        elapsed_in_stage_seconds=0.0,
    )


def previous_stage(state: GuidedTourState) -> GuidedTourState:
    """Move one stage back; the first stage clamps."""
    return replace(
        state,
        stage_index=max(state.stage_index - 1, 0),
        elapsed_in_stage_seconds=0.0,
    )


def pause_tour(state: GuidedTourState) -> GuidedTourState:
    """Stop automatic progression; manual navigation stays available."""
    return replace(state, playing=False)


def play_tour(state: GuidedTourState) -> GuidedTourState:
    """Resume automatic progression from the current stage."""
    return replace(state, playing=True, elapsed_in_stage_seconds=0.0)


def restart_tour(state: GuidedTourState) -> GuidedTourState:
    """Return to the first stage and play again."""
    return replace(state, stage_index=0, playing=True, elapsed_in_stage_seconds=0.0)
