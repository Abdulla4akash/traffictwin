"""Compatible side-by-side replay contract.

Requires an explicit comparison agreement before any synchronized view is
produced.  Synchronization may align clocks but must explicitly state it
is not evidence of causality.  No telemetry is fabricated: unavailable
event types, RSUs, execution targets, or aggregate research streams remain
truthfully unavailable.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from traffictwin.replay_observatory.engine import (
    ReplayEngine,
    ReplayEngineError,
    ReplayEngineState,
)
from traffictwin.replay_observatory.models import (
    EventType,
    ReplayEvent,
    ReplayEventStream,
    ReplayModel,
    SourceDataKind,
)


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


def _revalidate_stream(stream: ReplayEventStream) -> ReplayEventStream:
    try:
        validated = ReplayEventStream.model_validate_json(stream.model_dump_json())
    except ValidationError as exc:
        raise ComparisonAgreementError(
            "INVALID_STREAM", f"stream revalidation failed: {exc}"
        ) from exc
    return validated


def _revalidate_agreement(agreement: SideBySideAgreement) -> SideBySideAgreement:
    try:
        validated = SideBySideAgreement.model_validate_json(agreement.model_dump_json())
    except ValidationError as exc:
        raise ComparisonAgreementError(
            "INVALID_AGREEMENT", f"agreement revalidation failed: {exc}"
        ) from exc
    return validated


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ComparisonAgreementError(ValueError):
    """Typed refusal for incompatible side-by-side agreement."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


# ---------------------------------------------------------------------------
# Agreement and state
# ---------------------------------------------------------------------------


class AlignmentMode(StrEnum):
    CLOCK_ALIGN = "clock_align"
    RAW = "raw"


CAUSAL_DISCLAIMER: Literal["synchronization is not evidence of causality"] = (
    "synchronization is not evidence of causality"
)
MAX_TOLERANCE_S: float = 3600.0
MAX_WINDOW_DURATION_S: float = 86400.0 * 7


class SideBySideAgreement(ReplayModel):
    """Explicit declaration required before any side-by-side replay.

    All fields are frozen, strictly validated, and bounded.  The agreement
    declares the alignment, tolerance, window, time basis, units, identity
    namespace compatibility, and the immutable source fingerprints.  It does
    not itself mutate any stream.
    """

    schema_version: Literal["1.0"] = "1.0"
    time_basis: Literal["simulator_time_s"] = "simulator_time_s"
    time_units: Literal["seconds", "s"] = "seconds"
    alignment: AlignmentMode = AlignmentMode.CLOCK_ALIGN
    tolerance_s: float = Field(ge=0, le=MAX_TOLERANCE_S)
    window_start_s: float = Field(ge=0)
    window_end_s: float = Field(ge=0)
    left_stream_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    right_stream_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_namespace: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    left_identity_namespace: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"
    )
    right_identity_namespace: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"
    )
    compatibility_acknowledged: bool = False
    declared_event_types: tuple[EventType, ...] = ()
    causal_disclaimer: Literal["synchronization is not evidence of causality"] = CAUSAL_DISCLAIMER

    @field_validator("tolerance_s", "window_start_s", "window_end_s")
    @classmethod
    def validate_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        return value

    @model_validator(mode="after")
    def validate_agreement(self) -> SideBySideAgreement:
        if self.window_end_s < self.window_start_s:
            raise ValueError("window_end_s must be >= window_start_s")
        if self.window_end_s - self.window_start_s > MAX_WINDOW_DURATION_S:
            raise ValueError("window duration exceeds bound")
        if tuple(sorted(self.declared_event_types, key=str)) != self.declared_event_types:
            raise ValueError("declared_event_types must use canonical lexical order")
        if len(set(self.declared_event_types)) != len(self.declared_event_types):
            raise ValueError("declared_event_types must not contain duplicates")
        if not self.compatibility_acknowledged:
            raise ValueError("compatibility_acknowledged must be explicitly True")
        # Common identity_namespace must clearly apply to both sources.
        effective_left = self.left_identity_namespace or self.identity_namespace
        effective_right = self.right_identity_namespace or self.identity_namespace
        if effective_left != self.identity_namespace:
            raise ValueError("left_identity_namespace must match identity_namespace")
        if effective_right != self.identity_namespace:
            raise ValueError("right_identity_namespace must match identity_namespace")
        if self.causal_disclaimer != CAUSAL_DISCLAIMER:
            raise ValueError("causal_disclaimer must be exact")
        return self

    def canonical_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def fingerprint(self) -> str:
        return _fingerprint_dict(self.canonical_dict())


class SideBySideState(ReplayModel):
    """Truthful synchronized snapshot of two replay cursors.

    No event/RSU/execution-target telemetry is fabricated.  Unavailable
    capabilities are listed explicitly.  The causal disclaimer is carried on
    every receipt.
    """

    agreement: SideBySideAgreement
    left_state: ReplayEngineState
    right_state: ReplayEngineState
    agreement_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    left_window: tuple[ReplayEvent, ...] = Field(max_length=10000)
    right_window: tuple[ReplayEvent, ...] = Field(max_length=10000)
    unavailable_left_event_types: tuple[EventType, ...] = ()
    unavailable_right_event_types: tuple[EventType, ...] = ()
    aggregate_unavailable: bool = False
    missing_execution_target: bool = False
    causal_disclaimer: Literal["synchronization is not evidence of causality"] = CAUSAL_DISCLAIMER

    @model_validator(mode="after")
    def validate_state(self) -> SideBySideState:
        if (
            tuple(sorted(self.unavailable_left_event_types, key=str))
            != self.unavailable_left_event_types
        ):
            raise ValueError("unavailable_left_event_types must use canonical lexical order")
        if (
            tuple(sorted(self.unavailable_right_event_types, key=str))
            != self.unavailable_right_event_types
        ):
            raise ValueError("unavailable_right_event_types must use canonical lexical order")
        if len(set(self.unavailable_left_event_types)) != len(self.unavailable_left_event_types):
            raise ValueError("duplicate left unavailable")
        if len(set(self.unavailable_right_event_types)) != len(self.unavailable_right_event_types):
            raise ValueError("duplicate right unavailable")
        if self.agreement.fingerprint() != self.agreement_fingerprint:
            raise ValueError("agreement_fingerprint must match agreement fingerprint")
        if self.left_state.stream_fingerprint != self.agreement.left_stream_fingerprint:
            raise ValueError("left_state stream_fingerprint must match agreement")
        if self.right_state.stream_fingerprint != self.agreement.right_stream_fingerprint:
            raise ValueError("right_state stream_fingerprint must match agreement")
        if len(self.left_window) > 10000 or len(self.right_window) > 10000:
            raise ValueError("window exceeds bound")
        # Window bounds: every event must be within agreement window
        for ev in self.left_window:
            if not (
                self.agreement.window_start_s <= ev.simulator_time_s <= self.agreement.window_end_s
            ):
                raise ValueError("left_window event outside agreement window")
        for ev in self.right_window:
            if not (
                self.agreement.window_start_s <= ev.simulator_time_s <= self.agreement.window_end_s
            ):
                raise ValueError("right_window event outside agreement window")
        if self.causal_disclaimer != CAUSAL_DISCLAIMER:
            raise ValueError("causal_disclaimer must be exact")
        return self

    def canonical_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def fingerprint(self) -> str:
        return _fingerprint_dict(self.canonical_dict())

    def verify_against(
        self, left_stream: ReplayEventStream, right_stream: ReplayEventStream
    ) -> None:
        """Structural stream validation (not live freshness).

        Revalidates agreement/streams and checks window, fingerprints,
        unavailable types, aggregate and missing-target truthfulness
        against the supplied streams. Does not assert that this state
        is still the current live state of a SideBySideReplay; use
        verify_against_replay for exact live binding.
        """
        agr = _revalidate_agreement(self.agreement)
        ls = _revalidate_stream(left_stream)
        rs = _revalidate_stream(right_stream)
        if agr.fingerprint() != self.agreement_fingerprint:
            raise ComparisonAgreementError("AGREEMENT_MISMATCH", "agreement fingerprint mismatch")
        if ls.fingerprint() != agr.left_stream_fingerprint:
            raise ComparisonAgreementError("FINGERPRINT_MISMATCH", "left fingerprint mismatch")
        if rs.fingerprint() != agr.right_stream_fingerprint:
            raise ComparisonAgreementError("FINGERPRINT_MISMATCH", "right fingerprint mismatch")
        if self.left_state.stream_fingerprint != ls.fingerprint():
            raise ComparisonAgreementError("STATE_MISMATCH", "left_state fingerprint mismatch")
        if self.right_state.stream_fingerprint != rs.fingerprint():
            raise ComparisonAgreementError("STATE_MISMATCH", "right_state fingerprint mismatch")
        # Exact full bounded windows: no prefix allowance
        expected_left = tuple(
            ev for ev in ls.events if agr.window_start_s <= ev.simulator_time_s <= agr.window_end_s
        )
        expected_right = tuple(
            ev for ev in rs.events if agr.window_start_s <= ev.simulator_time_s <= agr.window_end_s
        )
        if self.left_window != expected_left:
            raise ComparisonAgreementError("WINDOW_MISMATCH", "left_window mismatch")
        if self.right_window != expected_right:
            raise ComparisonAgreementError("WINDOW_MISMATCH", "right_window mismatch")
        if self.causal_disclaimer != CAUSAL_DISCLAIMER:
            raise ComparisonAgreementError("DISCLAIMER_MISMATCH", "causal disclaimer mismatch")
        # Structural cursor coherence (self-consistent, not live freshness).
        # Intentionally structural-only; live freshness is asserted via
        # verify_against_replay / verify_exact_replay.
        try:
            self.left_state.cursor.verify_against_stream(ls)
        except (ComparisonAgreementError, ReplayEngineError, ValidationError) as exc:
            raise ComparisonAgreementError(
                "STATE_MISMATCH", f"left cursor mismatch: {exc}"
            ) from exc
        try:
            self.right_state.cursor.verify_against_stream(rs)
        except (ComparisonAgreementError, ReplayEngineError, ValidationError) as exc:
            raise ComparisonAgreementError(
                "STATE_MISMATCH", f"right cursor mismatch: {exc}"
            ) from exc
        # Recompute unavailable types canonically and compare
        all_types = set(EventType)
        left_present = set(ls.present_event_types)
        right_present = set(rs.present_event_types)
        expected_left_unavail = tuple(sorted(all_types - left_present, key=str))
        expected_right_unavail = tuple(sorted(all_types - right_present, key=str))
        if self.unavailable_left_event_types != expected_left_unavail:
            raise ComparisonAgreementError(
                "UNAVAILABLE_MISMATCH", "unavailable_left_event_types mismatch"
            )
        if self.unavailable_right_event_types != expected_right_unavail:
            raise ComparisonAgreementError(
                "UNAVAILABLE_MISMATCH", "unavailable_right_event_types mismatch"
            )
        # Aggregate truthfulness
        expected_agg = (
            ls.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
            or rs.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
        )
        if self.aggregate_unavailable != expected_agg:
            raise ComparisonAgreementError("AGGREGATE_MISMATCH", "aggregate_unavailable mismatch")
        # Missing execution target precise check
        expected_missing = _compute_missing_execution_target(ls, rs)
        if self.missing_execution_target != expected_missing:
            raise ComparisonAgreementError(
                "MISSING_TARGET_MISMATCH", "missing_execution_target mismatch"
            )
        # Verify left/right states' additional bindings via engine patterns
        # Stream fingerprints already checked; check unavailable via state
        if self.left_state.unavailable_event_types != expected_left_unavail:
            raise ComparisonAgreementError("STATE_MISMATCH", "left_state unavailable mismatch")
        if self.right_state.unavailable_event_types != expected_right_unavail:
            raise ComparisonAgreementError("STATE_MISMATCH", "right_state unavailable mismatch")

    def verify_exact(self, left_stream: ReplayEventStream, right_stream: ReplayEventStream) -> None:
        """Structural alias; see verify_against."""
        self.verify_against(left_stream, right_stream)

    def verify_against_replay(self, replay: SideBySideReplay) -> None:
        """Exact live-state verification against the current replay.

        Canonically compares this state against the replay's exact
        live streams, agreement, left/right engine states/cursors/
        playheads, full windows and truthfulness fields. Fails if
        stale, tampered or otherwise inconsistent. Compares exact
        cursor indices, not merely playhead time.
        """
        try:
            SideBySideState.model_validate_json(self.model_dump_json())
        except ValidationError as exc:
            raise ComparisonAgreementError("INVALID_STATE", str(exc)) from exc
        replay._verify_integrity()
        self.verify_against(replay._left_stream, replay._right_stream)
        # Exact live cursor/index and playhead binding; stale same-timestamp
        # must fail even when playhead time collides.
        if self.left_state.cursor.index != replay.left_engine.cursor_index:
            raise ComparisonAgreementError("STATE_MISMATCH", "left cursor index stale")
        if self.right_state.cursor.index != replay.right_engine.cursor_index:
            raise ComparisonAgreementError("STATE_MISMATCH", "right cursor index stale")
        if self.left_state.playhead_time_s != replay.left_engine._playhead_time_s:
            raise ComparisonAgreementError("STATE_MISMATCH", "left playhead stale")
        if self.right_state.playhead_time_s != replay.right_engine._playhead_time_s:
            raise ComparisonAgreementError("STATE_MISMATCH", "right playhead stale")
        # Delegate to engine verifiers for full live binding (including
        # speed, fingerprint, window, unavailable, etc.).
        try:
            self.left_state.verify_against_engine(replay.left_engine)
        except (ComparisonAgreementError, ReplayEngineError, ValidationError) as exc:
            raise ComparisonAgreementError("STATE_MISMATCH", f"left_state not live: {exc}") from exc
        try:
            self.right_state.verify_against_engine(replay.right_engine)
        except (ComparisonAgreementError, ReplayEngineError, ValidationError) as exc:
            raise ComparisonAgreementError(
                "STATE_MISMATCH", f"right_state not live: {exc}"
            ) from exc
        if self.agreement_fingerprint != replay.agreement.fingerprint():
            raise ComparisonAgreementError("AGREEMENT_MISMATCH", "agreement fingerprint not live")
        if self.agreement.fingerprint() != replay.agreement.fingerprint():
            raise ComparisonAgreementError("AGREEMENT_MISMATCH", "agreement not live")

    def verify_exact_replay(self, replay: SideBySideReplay) -> None:
        """Alias for verify_against_replay (exact live binding)."""
        self.verify_against_replay(replay)


class SideBySideReceipt(ReplayModel):
    agreement: SideBySideAgreement
    agreement_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    resulting_state: SideBySideState
    left_stream_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    right_stream_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    tamper_detected: bool = False
    causal_disclaimer: Literal["synchronization is not evidence of causality"] = CAUSAL_DISCLAIMER

    @model_validator(mode="after")
    def validate_receipt(self) -> SideBySideReceipt:
        if self.agreement.fingerprint() != self.agreement_fingerprint:
            raise ValueError("agreement_fingerprint must match agreement")
        if self.left_stream_fingerprint != self.agreement.left_stream_fingerprint:
            raise ValueError("left_stream_fingerprint must match agreement")
        if self.right_stream_fingerprint != self.agreement.right_stream_fingerprint:
            raise ValueError("right_stream_fingerprint must match agreement")
        if self.resulting_state.agreement_fingerprint != self.agreement_fingerprint:
            raise ValueError("resulting_state agreement_fingerprint mismatch")
        if self.resulting_state.agreement.fingerprint() != self.agreement_fingerprint:
            raise ValueError("resulting_state agreement mismatch")
        if self.resulting_state.left_state.stream_fingerprint != self.left_stream_fingerprint:
            raise ValueError("left_state stream fingerprint mismatch")
        if self.resulting_state.right_state.stream_fingerprint != self.right_stream_fingerprint:
            raise ValueError("right_state stream fingerprint mismatch")
        if self.causal_disclaimer != CAUSAL_DISCLAIMER:
            raise ValueError("causal_disclaimer must be exact")
        if self.resulting_state.causal_disclaimer != CAUSAL_DISCLAIMER:
            raise ValueError("state causal disclaimer mismatch")
        return self

    def fingerprint(self) -> str:
        return _fingerprint_dict(self.model_dump(mode="json"))

    def verify_against(
        self, left_stream: ReplayEventStream, right_stream: ReplayEventStream
    ) -> None:
        """Structural stream validation (not live freshness).

        Revalidates dependencies against the supplied streams and
        checks receipt/state coherence. Does not assert that this
        receipt is still the current live receipt of a
        SideBySideReplay; use verify_against_replay for exact live
        binding.
        """
        try:
            SideBySideReceipt.model_validate_json(self.model_dump_json())
        except ValidationError as exc:
            raise ComparisonAgreementError("INVALID_RECEIPT", str(exc)) from exc
        agr = _revalidate_agreement(self.agreement)
        ls = _revalidate_stream(left_stream)
        rs = _revalidate_stream(right_stream)
        if agr.fingerprint() != self.agreement_fingerprint:
            raise ComparisonAgreementError("RECEIPT_MISMATCH", "agreement fingerprint mismatch")
        if ls.fingerprint() != agr.left_stream_fingerprint:
            raise ComparisonAgreementError("FINGERPRINT_MISMATCH", "left fingerprint mismatch")
        if rs.fingerprint() != agr.right_stream_fingerprint:
            raise ComparisonAgreementError("FINGERPRINT_MISMATCH", "right fingerprint mismatch")
        if self.left_stream_fingerprint != ls.fingerprint():
            raise ComparisonAgreementError("RECEIPT_MISMATCH", "left stream fingerprint mismatch")
        if self.right_stream_fingerprint != rs.fingerprint():
            raise ComparisonAgreementError("RECEIPT_MISMATCH", "right stream fingerprint mismatch")
        self.resulting_state.verify_against(ls, rs)
        if self.tamper_detected:
            raise ComparisonAgreementError("TAMPER_DETECTED", "receipt indicates tamper")

    def verify_exact(self, left_stream: ReplayEventStream, right_stream: ReplayEventStream) -> None:
        """Structural alias; see verify_against."""
        self.verify_against(left_stream, right_stream)

    def verify_against_replay(self, replay: SideBySideReplay) -> None:
        """Exact live-state verification against the current replay.

        Canonically compares this receipt and its resulting_state
        against the replay's exact live streams, agreement, engine
        states/cursors/playheads, full windows and truthfulness.
        Fails if stale, tampered or otherwise inconsistent.
        """
        try:
            SideBySideReceipt.model_validate_json(self.model_dump_json())
        except ValidationError as exc:
            raise ComparisonAgreementError("INVALID_RECEIPT", str(exc)) from exc
        replay._verify_integrity()
        if self.agreement_fingerprint != replay.agreement.fingerprint():
            raise ComparisonAgreementError("RECEIPT_MISMATCH", "agreement fingerprint not live")
        if self.left_stream_fingerprint != replay._left_stream.fingerprint():
            raise ComparisonAgreementError("RECEIPT_MISMATCH", "left stream fingerprint not live")
        if self.right_stream_fingerprint != replay._right_stream.fingerprint():
            raise ComparisonAgreementError("RECEIPT_MISMATCH", "right stream fingerprint not live")
        if self.causal_disclaimer != CAUSAL_DISCLAIMER:
            raise ComparisonAgreementError("DISCLAIMER_MISMATCH", "causal disclaimer mismatch")
        # Delegate live state check to state's verifier.
        self.resulting_state.verify_against_replay(replay)
        if self.tamper_detected:
            raise ComparisonAgreementError("TAMPER_DETECTED", "receipt indicates tamper")

    def verify_exact_replay(self, replay: SideBySideReplay) -> None:
        """Alias for verify_against_replay (exact live binding)."""
        self.verify_against_replay(replay)


# ---------------------------------------------------------------------------
# Compatibility checks
# ---------------------------------------------------------------------------


def _check_compatible_streams(
    left: ReplayEventStream,
    right: ReplayEventStream,
    agreement: SideBySideAgreement,
) -> None:
    left = _revalidate_stream(left)
    right = _revalidate_stream(right)
    agreement = _revalidate_agreement(agreement)
    # Immutable fingerprints must match agreement.
    if left.fingerprint() != agreement.left_stream_fingerprint:
        raise ComparisonAgreementError(
            "FINGERPRINT_MISMATCH", "left fingerprint does not match agreement"
        )
    if right.fingerprint() != agreement.right_stream_fingerprint:
        raise ComparisonAgreementError(
            "FINGERPRINT_MISMATCH", "right fingerprint does not match agreement"
        )
    # Schema version must match.
    if (
        left.capability_manifest.source.schema_version
        != right.capability_manifest.source.schema_version
    ):
        raise ComparisonAgreementError(
            "INCOMPATIBLE_SCHEMA", "source schema_version must be compatible"
        )
    if left.schema_version != right.schema_version:
        raise ComparisonAgreementError("INCOMPATIBLE_SCHEMA", "stream schema_version mismatch")
    # Time basis/units are fixed by agreement; streams share simulator_time_s semantics.
    if agreement.time_basis != "simulator_time_s":
        raise ComparisonAgreementError("INCOMPATIBLE_TIME", "time_basis must be simulator_time_s")
    if agreement.time_units not in ("seconds", "s"):
        raise ComparisonAgreementError("INCOMPATIBLE_TIME", "time_units must be seconds")
    # Compatibility acknowledgement already validated but double-check
    if not agreement.compatibility_acknowledged:
        raise ComparisonAgreementError(
            "COMPATIBILITY_NOT_ACKNOWLEDGED", "compatibility must be explicitly acknowledged"
        )
    # Identity namespace interpretation: common namespace applies to both
    if agreement.left_identity_namespace is not None and (
        agreement.left_identity_namespace != agreement.identity_namespace
    ):
        raise ComparisonAgreementError(
            "NAMESPACE_MISMATCH", "left namespace must match common namespace"
        )
    if agreement.right_identity_namespace is not None and (
        agreement.right_identity_namespace != agreement.identity_namespace
    ):
        raise ComparisonAgreementError(
            "NAMESPACE_MISMATCH", "right namespace must match common namespace"
        )
    # Compatible source kind / event availability: check declared_event_types subset.
    left_avail = set(left.capability_manifest.available_event_types)
    right_avail = set(right.capability_manifest.available_event_types)
    left_present = set(left.present_event_types)
    right_present = set(right.present_event_types)
    declared = set(agreement.declared_event_types)
    # Declared types must be subset of both streams' available if they are event streams.
    # Aggregate-only streams have zero events and are allowed but marked aggregate_unavailable.
    left_is_agg = left.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
    right_is_agg = right.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
    if left_is_agg or right_is_agg:
        # Declared types must be empty for aggregate paths; otherwise incompatible.
        if declared:
            raise ComparisonAgreementError(
                "AGGREGATE_EVENT_INVENTION",
                "research aggregate cannot declare event capabilities",
            )
    else:
        if not declared <= left_avail:
            raise ComparisonAgreementError(
                "INCOMPATIBLE_CAPABILITIES", "declared types not available on left stream"
            )
        if not declared <= right_avail:
            raise ComparisonAgreementError(
                "INCOMPATIBLE_CAPABILITIES", "declared types not available on right stream"
            )
        if not declared <= left_present:
            raise ComparisonAgreementError(
                "INCOMPATIBLE_CAPABILITIES", "declared types not present on left stream"
            )
        if not declared <= right_present:
            raise ComparisonAgreementError(
                "INCOMPATIBLE_CAPABILITIES", "declared types not present on right stream"
            )
    # Identity namespace is explicitly declared in agreement; the agreement's
    # identity_namespace field already enforces a strict pattern and presence.
    # Distinct source_ids are allowed when compatibility is explicitly declared.
    # Window finite already validated.


def _compute_missing_execution_target(
    left_stream: ReplayEventStream, right_stream: ReplayEventStream
) -> bool:
    """Precise per-offered-task check when payload supports entity identity.

    For each TASK_OFFERED event, check for a corresponding EXECUTION_TARGET
    with the same task entity_id. If any offered task lacks a matching
    execution target, report missing. If no offered tasks, not missing.
    Remains conservatively unavailable and never fabricates.
    """

    for stream in (left_stream, right_stream):
        offered_ids: set[str] = set()
        exec_ids: set[str] = set()
        has_offer = False
        has_exec = False
        for ev in stream.events:
            if ev.event_type is EventType.TASK_OFFERED:
                has_offer = True
                try:
                    offered_ids.add(ev.entity.entity_id)
                except (AttributeError, ValueError, TypeError):
                    offered_ids.add(ev.event_id)
            elif ev.event_type is EventType.EXECUTION_TARGET:
                has_exec = True
                try:
                    exec_ids.add(ev.entity.entity_id)
                except (AttributeError, ValueError, TypeError):
                    exec_ids.add(ev.event_id)
        if has_offer and not has_exec:
            return True
        if offered_ids and not offered_ids.issubset(exec_ids):
            return True
        types = set(stream.present_event_types)
        if EventType.TASK_OFFERED in types and EventType.EXECUTION_TARGET not in types:
            return True
    return False


# ---------------------------------------------------------------------------
# Side-by-side engine
# ---------------------------------------------------------------------------


class SideBySideReplay:
    """Deterministic side-by-side cursor over two immutable streams.

    Construction requires an explicit :class:`SideBySideAgreement`.  All
    windows are bounded and no telemetry is synthesised.
    """

    def __init__(
        self,
        left_stream: ReplayEventStream,
        right_stream: ReplayEventStream,
        agreement: SideBySideAgreement,
    ) -> None:
        left_stream = _revalidate_stream(left_stream)
        right_stream = _revalidate_stream(right_stream)
        agreement = _revalidate_agreement(agreement)
        _check_compatible_streams(left_stream, right_stream, agreement)
        # Verify aggregate remains zero-event.
        for stream, label in ((left_stream, "left"), (right_stream, "right")):
            if (
                stream.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
                and len(stream.events) != 0
            ):
                raise ComparisonAgreementError(
                    "AGGREGATE_EVENT_INVENTION", f"{label} aggregate must remain zero-event"
                )
        self._left_stream = left_stream
        self._right_stream = right_stream
        self._agreement = agreement
        self._left_engine = ReplayEngine(left_stream)
        self._right_engine = ReplayEngine(right_stream)
        # Synchronization does not imply causality; disclaimer carried on every state.
        self._causal_disclaimer: Literal["synchronization is not evidence of causality"] = (
            CAUSAL_DISCLAIMER
        )

    def _verify_integrity(self) -> None:
        # Non-mutating integrity check: preserve object identity on success.
        left = _revalidate_stream(self._left_stream)
        right = _revalidate_stream(self._right_stream)
        agr = _revalidate_agreement(self._agreement)
        if left.fingerprint() != agr.left_stream_fingerprint:
            raise ComparisonAgreementError("TAMPER_DETECTED", "left stream tampered")
        if right.fingerprint() != agr.right_stream_fingerprint:
            raise ComparisonAgreementError("TAMPER_DETECTED", "right stream tampered")
        if agr.fingerprint() != self._agreement.fingerprint():
            raise ComparisonAgreementError("TAMPER_DETECTED", "agreement tampered")
        # Also verify underlying engines non-mutatingly
        self._left_engine._verify_integrity()
        self._right_engine._verify_integrity()

    @property
    def agreement(self) -> SideBySideAgreement:
        return self._agreement

    @property
    def left_engine(self) -> ReplayEngine:
        return self._left_engine

    @property
    def right_engine(self) -> ReplayEngine:
        return self._right_engine

    def _compute_unavailable(self) -> tuple[tuple[EventType, ...], tuple[EventType, ...]]:
        all_types = set(EventType)
        left_present = set(self._left_stream.present_event_types)
        right_present = set(self._right_stream.present_event_types)
        left_unavail = tuple(sorted(all_types - left_present, key=str))
        right_unavail = tuple(sorted(all_types - right_present, key=str))
        return left_unavail, right_unavail

    def synchronized_state(self) -> SideBySideState:
        self._verify_integrity()
        left_state = self._left_engine.state()
        right_state = self._right_engine.state()
        left_unavail, right_unavail = self._compute_unavailable()

        # Bounded windows from agreement.
        left_window = self._left_engine.load_time_window(
            self._agreement.window_start_s,
            self._agreement.window_end_s,
        )
        right_window = self._right_engine.load_time_window(
            self._agreement.window_start_s,
            self._agreement.window_end_s,
        )

        # Missing execution target detection: if a task_offered exists without
        # execution_target in stream, we report missing but do not fabricate.
        missing_exec = self._has_missing_execution_target()

        aggregate_unavailable = (
            self._left_stream.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
            or self._right_stream.capability_manifest.source_data_kind
            is SourceDataKind.AGGREGATE_ONLY
        )

        state = SideBySideState(
            agreement=self._agreement,
            left_state=left_state,
            right_state=right_state,
            agreement_fingerprint=self._agreement.fingerprint(),
            left_window=left_window,
            right_window=right_window,
            unavailable_left_event_types=left_unavail,
            unavailable_right_event_types=right_unavail,
            aggregate_unavailable=aggregate_unavailable,
            missing_execution_target=missing_exec,
            causal_disclaimer=self._causal_disclaimer,
        )
        # Verify before return to catch stale/tampered
        state.verify_against(self._left_stream, self._right_stream)
        return state

    def synchronized_receipt(self) -> SideBySideReceipt:
        self._verify_integrity()
        state = self.synchronized_state()
        receipt = SideBySideReceipt(
            agreement=self._agreement,
            agreement_fingerprint=self._agreement.fingerprint(),
            resulting_state=state,
            left_stream_fingerprint=self._left_stream.fingerprint(),
            right_stream_fingerprint=self._right_stream.fingerprint(),
            tamper_detected=False,
            causal_disclaimer=self._causal_disclaimer,
        )
        receipt.verify_against(self._left_stream, self._right_stream)
        return receipt

    def seek_both(self, target_time_s: float) -> SideBySideReceipt:
        self._verify_integrity()
        if not math.isfinite(target_time_s) or target_time_s < 0:
            raise ComparisonAgreementError(
                "INVALID_SEEK", "target_time_s must be finite non-negative"
            )
        self._left_engine.seek(target_time_s)
        self._right_engine.seek(target_time_s)
        self._verify_integrity()
        return self.synchronized_receipt()

    def step_both(
        self, count: int = 1, direction: Literal["forward", "backward"] = "forward"
    ) -> SideBySideReceipt:
        self._verify_integrity()
        self._left_engine.step(count, direction)
        self._right_engine.step(count, direction)
        self._verify_integrity()
        return self.synchronized_receipt()

    def _has_missing_execution_target(self) -> bool:
        return _compute_missing_execution_target(self._left_stream, self._right_stream)
