"""Framework-independent logical controls for TOS historical replay."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TosReplayControl:
    """Deterministic logical replay state."""

    position: float = 0.0
    playing: bool = False
    speed: float = 1.0


def advance_replay(
    state: TosReplayControl,
    maximum_index: int,
    *,
    tick_seconds: float = 0.5,
) -> TosReplayControl:
    """Advance logical time without wall-clock sleeps."""

    if maximum_index < 0 or tick_seconds <= 0:
        raise ValueError("maximum_index and tick_seconds must be valid")
    if not state.playing:
        return state
    position = min(float(maximum_index), state.position + state.speed * tick_seconds)
    return replace(state, position=position, playing=position < maximum_index)


def step_replay(state: TosReplayControl, maximum_index: int, direction: int) -> TosReplayControl:
    """Step by one source index and pause."""

    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    position = min(float(maximum_index), max(0.0, float(int(state.position) + direction)))
    return replace(state, position=position, playing=False)


def restart_replay(state: TosReplayControl) -> TosReplayControl:
    """Return to the first source index and pause."""

    return replace(state, position=0.0, playing=False)
