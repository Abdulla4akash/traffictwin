"""Deterministic pure replay engine over immutable ReplayEventStream.

This module is a pure, deterministic cursor engine.  It never sleeps,
never performs wall-clock waiting, never mutates or synthesises events,
and never fabricates missing telemetry.  All controls are typed,
frozen, strictly validated, and bounded.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from traffictwin.replay_observatory.models import (
    MAX_EVENTS_PER_STREAM,
    EventType,
    ReplayEvent,
    ReplayEventStream,
    ReplayModel,
    SourceDataKind,
)

# ---------------------------------------------------------------------------
# Constants and canonical helpers
# ---------------------------------------------------------------------------

MIN_SPEED_MULTIPLIER: float = 0.125
MAX_SPEED_MULTIPLIER: float = 16.0
MAX_WINDOW_DURATION_S: float = 86400.0 * 7  # one week bound
MAX_WINDOW_EVENTS: int = MAX_EVENTS_PER_STREAM
MAX_STEP_COUNT: int = MAX_EVENTS_PER_STREAM

# Keep fingerprint helper local to avoid importing adapter internals.


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fingerprint_dict(data: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class ReplayEngineError(ValueError):
    """Typed fail-closed error for the replay engine."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# ---------------------------------------------------------------------------
# Enums and typed request / state / receipt
# ---------------------------------------------------------------------------


class PlaybackState(StrEnum):
    PAUSED = "paused"
    PLAYING = "playing"
    ENDED = "ended"


class ReplayControl(StrEnum):
    PLAY = "play"
    PAUSE = "pause"
    STEP = "step"
    SEEK = "seek"


class ReplayControlRequest(ReplayModel):
    """Immutable strict request for one engine transition."""

    control: ReplayControl
    target_time_s: float | None = None
    step_count: int | None = None
    step_direction: Literal["forward", "backward"] | None = None
    speed_multiplier: float | None = None
    expected_stream_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("target_time_s", "speed_multiplier")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        return value

    @model_validator(mode="after")
    def validate_request(self) -> ReplayControlRequest:
        if self.speed_multiplier is not None:
            if (
                self.speed_multiplier < MIN_SPEED_MULTIPLIER
                or self.speed_multiplier > MAX_SPEED_MULTIPLIER
            ):
                raise ValueError(
                    f"speed_multiplier must be within "
                    f"[{MIN_SPEED_MULTIPLIER},{MAX_SPEED_MULTIPLIER}]"
                )
            if self.speed_multiplier <= 0:
                raise ValueError("speed_multiplier must be positive")
        if self.control is ReplayControl.SEEK:
            if self.target_time_s is None:
                raise ValueError("seek requires target_time_s")
            if self.target_time_s < 0:
                raise ValueError("target_time_s must be non-negative")
            if self.step_count is not None or self.step_direction is not None:
                raise ValueError("seek must not carry step fields")
        elif self.control is ReplayControl.STEP:
            if self.step_count is None:
                raise ValueError("step requires step_count")
            if self.step_count < 1 or self.step_count > MAX_STEP_COUNT:
                raise ValueError(f"step_count must be within [1,{MAX_STEP_COUNT}]")
            if self.step_direction is None:
                raise ValueError("step requires step_direction")
            if self.target_time_s is not None and self.speed_multiplier is not None:
                # speed on step is allowed but target_time must not be present
                pass
            if self.target_time_s is not None:
                raise ValueError("step must not carry target_time_s")
        elif self.control in (ReplayControl.PLAY, ReplayControl.PAUSE):
            if self.target_time_s is not None:
                raise ValueError(f"{self.control.value} must not carry target_time_s")
            if self.step_count is not None or self.step_direction is not None:
                raise ValueError(f"{self.control.value} must not carry step fields")
        return self

    def canonical_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def fingerprint(self) -> str:
        return _fingerprint_dict(self.canonical_dict())


class ReplayCursor(ReplayModel):
    index: int = Field(ge=0)
    simulator_time_s: float = Field(ge=0)
    event_id: str | None = None
    is_empty: bool
    is_at_end: bool
    total_events: int = Field(ge=0, le=MAX_EVENTS_PER_STREAM)


class ReplayEngineState(ReplayModel):
    playback_state: PlaybackState
    cursor: ReplayCursor
    speed_multiplier: float = Field(ge=MIN_SPEED_MULTIPLIER, le=MAX_SPEED_MULTIPLIER)
    stream_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    window_start_s: float | None = Field(default=None, ge=0)
    window_end_s: float | None = Field(default=None, ge=0)
    unavailable_event_types: tuple[EventType, ...] = ()
    end_of_stream: bool
    empty_stream: bool

    @model_validator(mode="after")
    def validate_window(self) -> ReplayEngineState:
        if (
            self.window_start_s is not None
            and self.window_end_s is not None
            and self.window_end_s < self.window_start_s
        ):
            raise ValueError("window_end_s must be >= window_start_s")
        if tuple(sorted(self.unavailable_event_types, key=str)) != self.unavailable_event_types:
            raise ValueError("unavailable_event_types must use canonical lexical order")
        return self

    def canonical_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def fingerprint(self) -> str:
        return _fingerprint_dict(self.canonical_dict())


class ReplayReceipt(ReplayModel):
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    resulting_state: ReplayEngineState
    stream_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    tamper_detected: bool
    error_code: str | None = None
    causal_disclaimer: str = "replay is deterministic; no causality implied"

    def canonical_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def fingerprint(self) -> str:
        return _fingerprint_dict(self.canonical_dict())


# ---------------------------------------------------------------------------
# Pure engine
# ---------------------------------------------------------------------------


class ReplayEngine:
    """Deterministic cursor engine over an immutable ReplayEventStream.

    The engine holds a reference to the immutable stream and a cursor index.
    All operations are pure with respect to the event sequence: equal-time
    events remain ordered by (simulator_time_s, sequence, event_id) as stored,
    and no method mutates or synthesises events.
    """

    def __init__(
        self,
        stream: ReplayEventStream,
        *,
        window_duration_s: float | None = None,
        speed_multiplier: float = 1.0,
        window_start_s: float | None = None,
        window_end_s: float | None = None,
    ) -> None:
        if not math.isfinite(speed_multiplier):
            raise ReplayEngineError("INVALID_SPEED", "speed_multiplier must be finite")
        if speed_multiplier < MIN_SPEED_MULTIPLIER or speed_multiplier > MAX_SPEED_MULTIPLIER:
            raise ReplayEngineError(
                "INVALID_SPEED",
                f"speed_multiplier must be within [{MIN_SPEED_MULTIPLIER},{MAX_SPEED_MULTIPLIER}]",
            )
        if window_duration_s is not None:
            if not math.isfinite(window_duration_s):
                raise ReplayEngineError("INVALID_WINDOW", "window_duration_s must be finite")
            if window_duration_s < 0 or window_duration_s > MAX_WINDOW_DURATION_S:
                raise ReplayEngineError(
                    "INVALID_WINDOW",
                    f"window_duration_s must be within [0,{MAX_WINDOW_DURATION_S}]",
                )
        if window_start_s is not None and (not math.isfinite(window_start_s) or window_start_s < 0):
            raise ReplayEngineError("INVALID_WINDOW", "window_start_s must be finite non-negative")
        if window_end_s is not None and (not math.isfinite(window_end_s) or window_end_s < 0):
            raise ReplayEngineError("INVALID_WINDOW", "window_end_s must be finite non-negative")
        if (
            window_start_s is not None
            and window_end_s is not None
            and window_end_s < window_start_s
        ):
            raise ReplayEngineError("INVALID_WINDOW", "window_end_s must be >= window_start_s")
        # Defensive tamper check: stream fingerprint must be computable.
        try:
            fp = stream.fingerprint()
        except Exception as exc:
            raise ReplayEngineError("INVALID_STREAM", "stream fingerprint failed") from exc

        self._stream: ReplayEventStream = stream
        self._stream_fingerprint: str = fp
        self._speed_multiplier: float = speed_multiplier
        self._window_duration_s: float | None = window_duration_s
        self._window_start_s: float | None = window_start_s
        self._window_end_s: float | None = window_end_s

        # Cursor initialisation: empty stream starts at end, otherwise at 0 paused.
        if len(stream.events) == 0:
            self._cursor_index: int = 0
            self._playback_state: PlaybackState = PlaybackState.ENDED
        else:
            self._cursor_index = 0
            self._playback_state = PlaybackState.PAUSED

        # Derive unavailable event types from capability manifest vs present.
        all_types = set(EventType)
        present = set(stream.present_event_types)
        unavailable = sorted(all_types - present, key=str)
        self._unavailable_event_types: tuple[EventType, ...] = tuple(unavailable)

        # Validate that we are not hiding a tampered stream that invented events.
        if (
            stream.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
            and len(stream.events) != 0
        ):
            raise ReplayEngineError(
                "AGGREGATE_EVENT_INVENTION",
                "aggregate-only source must remain zero-event",
            )

    # -- properties ----------------------------------------------------------

    @property
    def stream(self) -> ReplayEventStream:
        return self._stream

    @property
    def stream_fingerprint(self) -> str:
        return self._stream_fingerprint

    @property
    def speed_multiplier(self) -> float:
        return self._speed_multiplier

    @property
    def cursor_index(self) -> int:
        return self._cursor_index

    @property
    def playback_state(self) -> PlaybackState:
        return self._playback_state

    def is_empty(self) -> bool:
        return len(self._stream.events) == 0

    def is_at_end(self) -> bool:
        if self.is_empty():
            return True
        return self._cursor_index >= len(self._stream.events)

    def current_event(self) -> ReplayEvent | None:
        if self.is_empty() or self.is_at_end():
            return None
        return self._stream.events[self._cursor_index]

    def peek(self, count: int = 1) -> tuple[ReplayEvent, ...]:
        if count < 0 or count > MAX_EVENTS_PER_STREAM:
            raise ReplayEngineError("INVALID_WINDOW", "peek count out of bounds")
        if self.is_empty() or self.is_at_end():
            return ()
        end = min(len(self._stream.events), self._cursor_index + count)
        return tuple(self._stream.events[self._cursor_index : end])

    # -- bounded window loading ---------------------------------------------

    def load_time_window(
        self,
        start_s: float,
        end_s: float,
        *,
        max_events: int = MAX_WINDOW_EVENTS,
    ) -> tuple[ReplayEvent, ...]:
        """Return events within [start_s, end_s] without mutating the stream.

        Order is the stream's canonical (simulator_time_s, sequence, event_id).
        No events are synthesised; an empty result is truthful unavailable.
        """
        if not math.isfinite(start_s) or not math.isfinite(end_s):
            raise ReplayEngineError("INVALID_WINDOW", "window bounds must be finite")
        if start_s < 0 or end_s < 0:
            raise ReplayEngineError("INVALID_WINDOW", "window bounds must be non-negative")
        if end_s < start_s:
            raise ReplayEngineError("INVALID_WINDOW", "end_s must be >= start_s")
        if end_s - start_s > MAX_WINDOW_DURATION_S:
            raise ReplayEngineError(
                "INVALID_WINDOW",
                f"window duration exceeds bound {MAX_WINDOW_DURATION_S}",
            )
        if max_events < 0 or max_events > MAX_WINDOW_EVENTS:
            raise ReplayEngineError("INVALID_WINDOW", "max_events out of bounds")
        # Verify integrity before loading.
        self._verify_integrity()
        result: list[ReplayEvent] = []
        for ev in self._stream.events:
            if start_s <= ev.simulator_time_s <= end_s:
                result.append(ev)
                if len(result) >= max_events:
                    break
        # result is already in canonical order because stream is.
        return tuple(result)

    def load_bounded_window(
        self,
        *,
        max_events: int = MAX_WINDOW_EVENTS,
    ) -> tuple[ReplayEvent, ...]:
        """Load the engine's configured bounded window if set, else full slice."""
        self._verify_integrity()
        if self._window_start_s is not None and self._window_end_s is not None:
            return self.load_time_window(
                self._window_start_s, self._window_end_s, max_events=max_events
            )
        if self._window_duration_s is not None:
            # Window from current cursor time outward.
            cur_time = 0.0
            if not self.is_empty() and not self.is_at_end():
                cur_time = float(self._stream.events[self._cursor_index].simulator_time_s)
            elif not self.is_empty():
                cur_time = float(self._stream.events[-1].simulator_time_s)
            return self.load_time_window(
                cur_time, cur_time + self._window_duration_s, max_events=max_events
            )
        # No window bound: return up to max_events from cursor.
        if self.is_empty() or self.is_at_end():
            return ()
        end = min(len(self._stream.events), self._cursor_index + max_events)
        return tuple(self._stream.events[self._cursor_index : end])

    # -- integrity ----------------------------------------------------------

    def _verify_integrity(self) -> None:
        current_fp = self._stream.fingerprint()
        if current_fp != self._stream_fingerprint:
            raise ReplayEngineError("TAMPER_DETECTED", "stream fingerprint mismatch")

    def verify_integrity(self, expected_fingerprint: str | None = None) -> bool:
        fp = self._stream.fingerprint()
        if expected_fingerprint is not None:
            return fp == expected_fingerprint
        return fp == self._stream_fingerprint

    # -- state snapshot -----------------------------------------------------

    def _cursor_snapshot(self) -> ReplayCursor:
        total = len(self._stream.events)
        if self.is_empty():
            return ReplayCursor(
                index=0,
                simulator_time_s=0.0,
                event_id=None,
                is_empty=True,
                is_at_end=True,
                total_events=total,
            )
        if self.is_at_end():
            last_time = float(self._stream.events[-1].simulator_time_s) if total else 0.0
            return ReplayCursor(
                index=self._cursor_index,
                simulator_time_s=last_time,
                event_id=None,
                is_empty=False,
                is_at_end=True,
                total_events=total,
            )
        ev = self._stream.events[self._cursor_index]
        return ReplayCursor(
            index=self._cursor_index,
            simulator_time_s=float(ev.simulator_time_s),
            event_id=ev.event_id,
            is_empty=False,
            is_at_end=False,
            total_events=total,
        )

    def state(self) -> ReplayEngineState:
        self._verify_integrity()
        cursor = self._cursor_snapshot()
        end_of_stream = cursor.is_at_end
        # Map ended cursor to ENDED playback state for snapshots.
        playback = self._playback_state
        if end_of_stream and playback is not PlaybackState.ENDED:
            # Keep paused/playing label until explicit; snapshot reflects cursor.
            pass
        if self.is_empty():
            playback = PlaybackState.ENDED
        return ReplayEngineState(
            playback_state=playback,
            cursor=cursor,
            speed_multiplier=self._speed_multiplier,
            stream_fingerprint=self._stream_fingerprint,
            window_start_s=self._window_start_s,
            window_end_s=self._window_end_s,
            unavailable_event_types=self._unavailable_event_types,
            end_of_stream=end_of_stream,
            empty_stream=self.is_empty(),
        )

    # -- controls -----------------------------------------------------------

    def apply(self, request: ReplayControlRequest) -> ReplayReceipt:
        """Apply one typed request deterministically and return a receipt.

        Validation is fail-closed: invalid fields, tamper, negative/nonfinite
        values, or aggregate violations produce a typed error.
        """
        # Tamper check before transition.
        if (
            request.expected_stream_fingerprint is not None
            and request.expected_stream_fingerprint != self._stream_fingerprint
        ):
            raise ReplayEngineError(
                "TAMPER_DETECTED",
                "expected_stream_fingerprint does not match stream",
            )
        self._verify_integrity()

        # Speed update is allowed on any control if present; validate already done.
        if request.speed_multiplier is not None:
            self._speed_multiplier = request.speed_multiplier

        if request.control is ReplayControl.PLAY:
            if self.is_empty():
                self._playback_state = PlaybackState.ENDED
            elif self.is_at_end():
                # At end, PLAY stays ENDED; seek required to move.
                self._playback_state = PlaybackState.ENDED
            else:
                self._playback_state = PlaybackState.PLAYING

        elif request.control is ReplayControl.PAUSE:
            if self.is_empty() or self.is_at_end():
                self._playback_state = PlaybackState.ENDED
            else:
                self._playback_state = PlaybackState.PAUSED

        elif request.control is ReplayControl.SEEK:
            assert request.target_time_s is not None
            # Seek is bounded: find first event with time >= target.
            # Empty stream stays at end.
            if self.is_empty():
                self._playback_state = PlaybackState.ENDED
            else:
                idx = self._find_seek_index(request.target_time_s)
                self._cursor_index = idx
                if self.is_at_end():
                    self._playback_state = PlaybackState.ENDED
                else:
                    self._playback_state = PlaybackState.PAUSED

        elif request.control is ReplayControl.STEP:
            assert request.step_count is not None and request.step_direction is not None
            if self.is_empty():
                self._playback_state = PlaybackState.ENDED
            else:
                if request.step_direction == "forward":
                    self._cursor_index = min(
                        len(self._stream.events),
                        self._cursor_index + request.step_count,
                    )
                else:
                    self._cursor_index = max(0, self._cursor_index - request.step_count)
                if self.is_at_end():
                    self._playback_state = PlaybackState.ENDED
                else:
                    self._playback_state = PlaybackState.PAUSED
        else:
            raise ReplayEngineError("INVALID_CONTROL", f"unknown control {request.control}")

        resulting_state = self.state()
        receipt = ReplayReceipt(
            request_fingerprint=request.fingerprint(),
            resulting_state=resulting_state,
            stream_fingerprint=self._stream_fingerprint,
            tamper_detected=False,
            error_code=None,
        )
        return receipt

    def _find_seek_index(self, target_time_s: float) -> int:
        # Deterministic: first event where simulator_time_s >= target.
        # Equal-time events remain ordered by sequence, so the first of
        # that time is the seek landing point.
        for idx, ev in enumerate(self._stream.events):
            if ev.simulator_time_s >= target_time_s:
                return idx
        return len(self._stream.events)

    # Convenience wrappers that build typed requests.

    def play(self, speed_multiplier: float | None = None) -> ReplayReceipt:
        return self.apply(
            ReplayControlRequest(control=ReplayControl.PLAY, speed_multiplier=speed_multiplier)
        )

    def pause(self) -> ReplayReceipt:
        return self.apply(ReplayControlRequest(control=ReplayControl.PAUSE))

    def seek(self, target_time_s: float) -> ReplayReceipt:
        return self.apply(
            ReplayControlRequest(control=ReplayControl.SEEK, target_time_s=target_time_s)
        )

    def step(
        self, count: int = 1, direction: Literal["forward", "backward"] = "forward"
    ) -> ReplayReceipt:
        return self.apply(
            ReplayControlRequest(
                control=ReplayControl.STEP, step_count=count, step_direction=direction
            )
        )

    def set_speed(self, speed_multiplier: float) -> ReplayReceipt:
        # Speed alone preserves pause/ended semantics; use current playback paused.
        if self.is_empty():
            # Still validate speed, but state stays ended.
            if not math.isfinite(speed_multiplier):
                raise ReplayEngineError("INVALID_SPEED", "speed_multiplier must be finite")
            if speed_multiplier < MIN_SPEED_MULTIPLIER or speed_multiplier > MAX_SPEED_MULTIPLIER:
                raise ReplayEngineError("INVALID_SPEED", "speed_multiplier out of bounds")
            self._speed_multiplier = speed_multiplier
            return ReplayReceipt(
                request_fingerprint=ReplayControlRequest(
                    control=ReplayControl.PAUSE, speed_multiplier=speed_multiplier
                ).fingerprint(),
                resulting_state=self.state(),
                stream_fingerprint=self._stream_fingerprint,
                tamper_detected=False,
            )
        # If playing, keep playing; otherwise pause.
        control = (
            self._playback_state
            if self._playback_state is PlaybackState.PLAYING
            else ReplayControl.PAUSE
        )
        # Map PLAYING enum to control; fallback to pause if ended.
        if control is PlaybackState.PLAYING:
            req_control = ReplayControl.PLAY
        else:
            req_control = ReplayControl.PAUSE
        return self.apply(
            ReplayControlRequest(control=req_control, speed_multiplier=speed_multiplier)
        )
