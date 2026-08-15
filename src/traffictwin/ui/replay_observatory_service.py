"""Typed UI-facing service for the Replay Observatory.

Thin deterministic wrapper over the immutable Lane 10 event stream and the
Lane 11 deterministic engine. Every public boundary canonical-revalidates its
inputs; no event class is synthesised from aggregate evidence and no execution
RSU/task outcome is manufactured.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from pydantic import ValidationError

from traffictwin.replay_observatory.adapters import (
    MAX_REPLAY_JSON_BYTES,
    ReplayImportError,
    load_aggregate_capability_json,
    load_event_stream_json,
)
from traffictwin.replay_observatory.comparison import (
    CAUSAL_DISCLAIMER as SYNC_CAUSAL_DISCLAIMER,
)
from traffictwin.replay_observatory.comparison import (
    ComparisonAgreementError,
    SideBySideAgreement,
    SideBySideReplay,
    SideBySideState,
)
from traffictwin.replay_observatory.engine import (
    MAX_SPEED_MULTIPLIER,
    MIN_SPEED_MULTIPLIER,
    ReplayControl,
    ReplayControlRequest,
    ReplayCursor,
    ReplayEngine,
    ReplayEngineError,
    ReplayEngineState,
    ReplayReceipt,
)
from traffictwin.replay_observatory.models import (
    EntityIdentity,
    EntityKind,
    EventProvenance,
    EventType,
    EvidenceStanding,
    ReplayEvent,
    ReplayEventStream,
    ReplayModel,
    ScaleActionEvent,
    ScaleActionPayload,
    SimulationTimeEvent,
    SimulationTimePayload,
    SourceCapabilityManifest,
    SourceDataKind,
    SourceIdentity,
    SourceKind,
    TaskIngressEvent,
    TaskIngressPayload,
    TaskOfferedEvent,
    TaskOfferedPayload,
    VehicleStateEvent,
    VehicleStatePayload,
)

# ---------------------------------------------------------------------------
# Fixed disclaimers
# ---------------------------------------------------------------------------

SYNTHETIC_ENGINEERING_DISCLAIMER: str = (
    "SYNTHETIC ENGINEERING — DESIGN-ONLY — This synthetic engineering stream was "
    "built through the real typed immutable event builder. It is not Manchester "
    "observation and not admitted task-level research evidence."
)
SYNCHRONIZED_REPLAY_DISCLAIMER: str = "synchronized visual replay is not causal evidence"
CAUSAL_DISCLAIMER: str = "replay is deterministic; no causality implied"
# Re-export for page/tests.
SYNC_DISCLAIMER: str = SYNC_CAUSAL_DISCLAIMER

# ---------------------------------------------------------------------------
# Revalidation helpers — canonical JSON round-trip
# ---------------------------------------------------------------------------


def _revalidate_stream(stream: ReplayEventStream) -> ReplayEventStream:
    try:
        validated = ReplayEventStream.model_validate_json(stream.model_dump_json())
    except ValidationError as exc:
        raise ReplayEngineError("INVALID_STREAM", f"stream revalidation failed: {exc}") from exc
    return validated


def _revalidate_request(request: ReplayControlRequest) -> ReplayControlRequest:
    try:
        validated = ReplayControlRequest.model_validate_json(request.model_dump_json())
    except ValidationError as exc:
        raise ReplayEngineError("INVALID_REQUEST", f"request revalidation failed: {exc}") from exc
    return validated


def _revalidate_state(state: ReplayEngineState) -> ReplayEngineState:
    try:
        validated = ReplayEngineState.model_validate_json(state.model_dump_json())
    except ValidationError as exc:
        raise ReplayEngineError("INVALID_STATE", f"state revalidation failed: {exc}") from exc
    return validated


def _revalidate_receipt(receipt: ReplayReceipt) -> ReplayReceipt:
    try:
        validated = ReplayReceipt.model_validate_json(receipt.model_dump_json())
    except ValidationError as exc:
        raise ReplayEngineError("INVALID_RECEIPT", f"receipt revalidation failed: {exc}") from exc
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
# Synthetic engineering streams — real typed immutable builder only
# ---------------------------------------------------------------------------

_ARTIFACT_A: str = "c" * 64
_ARTIFACT_B: str = "d" * 64
_AGGREGATE_ARTIFACT: str = "e" * 64


def _source_identity(*, artifact: str, source_id: str) -> SourceIdentity:
    return SourceIdentity(
        source_id=source_id,
        source_kind=SourceKind.SYNTHETIC_FIXTURE,
        artifact_sha256=artifact,
        schema_version="1.0",
    )


def _provenance(*, artifact: str, record: str) -> EventProvenance:
    return EventProvenance(
        source_artifact_sha256=artifact,
        source_record_id=record,
        adapter_id="synthetic-engineering-adapter",
        adapter_version="1.0",
    )


def build_synthetic_engineering_stream(
    *, stream_id: str = "synthetic-engineering-001", artifact: str = _ARTIFACT_A
) -> ReplayEventStream:
    """Build a small deterministic synthetic engineering stream via the real builder.

    The stream is labelled DESIGN-ONLY and carries an explicit disclaimer; it is
    never Manchester observation.
    """

    source = _source_identity(artifact=artifact, source_id="synthetic-eng-001")
    # Events — canonical order (simulator_time_s, sequence, event_id)
    events: list[ReplayEvent] = [
        SimulationTimeEvent(
            event_id="evt-sim-000",
            sequence=0,
            simulator_time_s=0.0,
            entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-sim-000"),
            payload=SimulationTimePayload(step_index=0),
        ),
        VehicleStateEvent(
            event_id="evt-veh-001",
            sequence=1,
            simulator_time_s=1.0,
            entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-veh-001"),
            payload=VehicleStatePayload(x_m=10.0, y_m=20.0, speed_mps=5.0),
        ),
        TaskOfferedEvent(
            event_id="evt-offer-002",
            sequence=2,
            simulator_time_s=2.5,
            entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-offer-002"),
            payload=TaskOfferedPayload(offered_to_entity_id="rsu-001"),
        ),
        TaskIngressEvent(
            event_id="evt-ingress-003",
            sequence=3,
            simulator_time_s=3.0,
            entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-ingress-003"),
            payload=TaskIngressPayload(ingress_resource_id="rsu-001"),
        ),
        VehicleStateEvent(
            event_id="evt-veh-004",
            sequence=4,
            simulator_time_s=4.0,
            entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-002"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-veh-004"),
            payload=VehicleStatePayload(x_m=12.0, y_m=22.0, speed_mps=6.0),
        ),
        SimulationTimeEvent(
            event_id="evt-sim-005",
            sequence=5,
            simulator_time_s=5.0,
            entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-sim-005"),
            payload=SimulationTimePayload(step_index=5),
        ),
        ScaleActionEvent(
            event_id="evt-scale-006",
            sequence=6,
            simulator_time_s=6.0,
            entity=EntityIdentity(kind=EntityKind.RESOURCE, entity_id="rsu-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-scale-006"),
            payload=ScaleActionPayload(
                action_id="act-001",
                target_resource_id="rsu-001",
                source_declared_action="scale_up",
            ),
        ),
    ]
    present = tuple(sorted({e.event_type for e in events}, key=str))
    manifest = SourceCapabilityManifest(
        manifest_id="manifest-synthetic-001",
        source=source,
        source_data_kind=SourceDataKind.EVENT_STREAM,
        evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
        available_event_types=present,
        limitations=(
            "SYNTHETIC ENGINEERING — DESIGN-ONLY",
            "Not Manchester observation",
            "Not admitted task-level research evidence",
            "Bounded fixture for replay controls demonstration",
        ),
    )
    stream = ReplayEventStream(
        stream_id=stream_id,
        capability_manifest=manifest,
        present_event_types=present,
        events=tuple(events),
        limitations=(
            "SYNTHETIC ENGINEERING — DESIGN-ONLY",
            "Not Manchester observation",
            "Not admitted task-level research evidence",
        ),
    )
    return _revalidate_stream(stream)


def build_second_synthetic_stream(
    *, stream_id: str = "synthetic-engineering-002"
) -> ReplayEventStream:
    """Second deterministic stream for side-by-side compatibility demos."""

    artifact = _ARTIFACT_B
    source = _source_identity(artifact=artifact, source_id="synthetic-eng-002")
    events: list[ReplayEvent] = [
        SimulationTimeEvent(
            event_id="evt-sim-100",
            sequence=0,
            simulator_time_s=0.5,
            entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-sim-100"),
            payload=SimulationTimePayload(step_index=0),
        ),
        VehicleStateEvent(
            event_id="evt-veh-101",
            sequence=1,
            simulator_time_s=1.5,
            entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-veh-101"),
            payload=VehicleStatePayload(x_m=11.0, y_m=21.0, speed_mps=4.5),
        ),
        TaskOfferedEvent(
            event_id="evt-offer-102",
            sequence=2,
            simulator_time_s=2.8,
            entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-002"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-offer-102"),
            payload=TaskOfferedPayload(offered_to_entity_id="rsu-001"),
        ),
        TaskIngressEvent(
            event_id="evt-ingress-103",
            sequence=3,
            simulator_time_s=3.2,
            entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-002"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-ingress-103"),
            payload=TaskIngressPayload(ingress_resource_id="rsu-001"),
        ),
        VehicleStateEvent(
            event_id="evt-veh-104",
            sequence=4,
            simulator_time_s=4.5,
            entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-003"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-veh-104"),
            payload=VehicleStatePayload(x_m=13.0, y_m=23.0, speed_mps=5.5),
        ),
        SimulationTimeEvent(
            event_id="evt-sim-105",
            sequence=5,
            simulator_time_s=5.5,
            entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-sim-105"),
            payload=SimulationTimePayload(step_index=5),
        ),
        ScaleActionEvent(
            event_id="evt-scale-106",
            sequence=6,
            simulator_time_s=6.5,
            entity=EntityIdentity(kind=EntityKind.RESOURCE, entity_id="rsu-001"),
            source=source,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
            provenance=_provenance(artifact=artifact, record="rec-scale-106"),
            payload=ScaleActionPayload(
                action_id="act-002",
                target_resource_id="rsu-001",
                source_declared_action="scale_up",
            ),
        ),
    ]
    present = tuple(sorted({e.event_type for e in events}, key=str))
    manifest = SourceCapabilityManifest(
        manifest_id="manifest-synthetic-002",
        source=source,
        source_data_kind=SourceDataKind.EVENT_STREAM,
        evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
        available_event_types=present,
        limitations=(
            "SYNTHETIC ENGINEERING — DESIGN-ONLY",
            "Not Manchester observation",
            "Not admitted task-level research evidence",
            "Second bounded fixture for side-by-side demonstration",
        ),
    )
    stream = ReplayEventStream(
        stream_id=stream_id,
        capability_manifest=manifest,
        present_event_types=present,
        events=tuple(events),
        limitations=(
            "SYNTHETIC ENGINEERING — DESIGN-ONLY",
            "Not Manchester observation",
            "Not admitted task-level research evidence",
        ),
    )
    return _revalidate_stream(stream)


def build_aggregate_only_declaration(*, stream_id: str = "aggregate-only-001") -> ReplayEventStream:
    """Truthful zero-event aggregate declaration — never synthesises telemetry."""

    source = SourceIdentity(
        source_id="research-agg-001",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=_AGGREGATE_ARTIFACT,
        schema_version="1.0",
    )
    manifest = SourceCapabilityManifest(
        manifest_id="manifest-agg-001",
        source=source,
        source_data_kind=SourceDataKind.AGGREGATE_ONLY,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=(),
        limitations=(
            "Aggregate-only research evidence — no event telemetry",
            "Cannot be adapted into replay events",
        ),
    )
    stream = ReplayEventStream(
        stream_id=stream_id,
        capability_manifest=manifest,
        present_event_types=(),
        events=(),
        limitations=("Aggregate-only — no events",),
    )
    return _revalidate_stream(stream)


def build_empty_event_stream(*, stream_id: str = "empty-001") -> ReplayEventStream:
    """Empty but well-formed event-stream (no events, not aggregate)."""

    source = _source_identity(artifact="a" * 64, source_id="empty-src-001")
    manifest = SourceCapabilityManifest(
        manifest_id="manifest-empty-001",
        source=source,
        source_data_kind=SourceDataKind.EVENT_STREAM,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=(),
        limitations=("Empty fixture — no events",),
    )
    stream = ReplayEventStream(
        stream_id=stream_id,
        capability_manifest=manifest,
        present_event_types=(),
        events=(),
        limitations=("Empty fixture",),
    )
    return _revalidate_stream(stream)


# ---------------------------------------------------------------------------
# Engine factory and controls — revalidating boundaries
# ---------------------------------------------------------------------------


def create_engine(
    stream: ReplayEventStream,
    *,
    speed_multiplier: float = 1.0,
    window_duration_s: float | None = None,
    window_start_s: float | None = None,
    window_end_s: float | None = None,
) -> ReplayEngine:
    """Create a deterministic engine over a revalidated stream."""

    validated = _revalidate_stream(stream)
    # Explicit finite checks before delegation (fail-closed)
    if not math.isfinite(speed_multiplier):
        raise ReplayEngineError("INVALID_SPEED", "speed_multiplier must be finite")
    return ReplayEngine(
        validated,
        speed_multiplier=speed_multiplier,
        window_duration_s=window_duration_s,
        window_start_s=window_start_s,
        window_end_s=window_end_s,
    )


def apply_control(engine: ReplayEngine, request: ReplayControlRequest) -> ReplayReceipt:
    """Apply one typed request after revalidating request and engine integrity."""

    validated_req = _revalidate_request(request)
    # Engine integrity is verified inside apply, but pre-check for tamper clarity.
    engine._verify_integrity()  # noqa: SLF001
    receipt = engine.apply(validated_req)
    _revalidate_receipt(receipt)
    # Receipt must verify against the now-mutated engine.
    receipt.verify_against(engine, validated_req)
    return receipt


def apply_play(engine: ReplayEngine, *, speed_multiplier: float | None = None) -> ReplayReceipt:
    req = ReplayControlRequest(control=ReplayControl.PLAY, speed_multiplier=speed_multiplier)
    return apply_control(engine, req)


def apply_pause(engine: ReplayEngine) -> ReplayReceipt:
    req = ReplayControlRequest(control=ReplayControl.PAUSE)
    return apply_control(engine, req)


def apply_step(
    engine: ReplayEngine, *, count: int = 1, direction: Literal["forward", "backward"] = "forward"
) -> ReplayReceipt:
    req = ReplayControlRequest(
        control=ReplayControl.STEP, step_count=count, step_direction=direction
    )
    return apply_control(engine, req)


def apply_seek(engine: ReplayEngine, *, target_time_s: float) -> ReplayReceipt:
    req = ReplayControlRequest(control=ReplayControl.SEEK, target_time_s=target_time_s)
    return apply_control(engine, req)


def apply_speed(engine: ReplayEngine, *, speed_multiplier: float) -> ReplayReceipt:
    # Route through engine.set_speed which preserves playback semantics.
    # Still revalidate via request path for consistency.
    if not math.isfinite(speed_multiplier):
        raise ReplayEngineError("INVALID_SPEED", "speed_multiplier must be finite")
    if speed_multiplier < MIN_SPEED_MULTIPLIER or speed_multiplier > MAX_SPEED_MULTIPLIER:
        raise ReplayEngineError("INVALID_SPEED", "speed_multiplier out of bounds")
    receipt = engine.set_speed(speed_multiplier)
    _revalidate_receipt(receipt)
    receipt.verify_against(engine)
    return receipt


def apply_advance(engine: ReplayEngine, *, delta_s: float) -> ReplayReceipt:
    req = ReplayControlRequest(control=ReplayControl.ADVANCE, advance_delta_s=delta_s)
    return apply_control(engine, req)


def load_time_window(
    engine: ReplayEngine,
    start_s: float,
    end_s: float,
    *,
    max_events: int = 200,
) -> tuple[ReplayEvent, ...]:
    """Bounded window load with revalidation."""

    validated = _revalidate_stream(engine.stream)
    # Ensure engine integrity matches validated stream fingerprint.
    if validated.fingerprint() != engine.stream_fingerprint:
        raise ReplayEngineError("TAMPER_DETECTED", "stream fingerprint mismatch")
    return engine.load_time_window(start_s, end_s, max_events=max_events)


def get_engine_state(engine: ReplayEngine) -> ReplayEngineState:
    """Return a revalidated snapshot of engine state."""

    state = engine.state()
    return _revalidate_state(state)


def verify_receipt_against_engine(receipt: ReplayReceipt, engine: ReplayEngine) -> None:
    """Canonical receipt verification — refuses model_copy forgery."""

    _revalidate_receipt(receipt)
    receipt.verify_against(engine)


def verify_state_against_engine(state: ReplayEngineState, engine: ReplayEngine) -> None:
    """Canonical state verification."""

    _revalidate_state(state)
    state.verify_against_engine(engine)


# ---------------------------------------------------------------------------
# Observatory view model — typed, immutable, truthful
# ---------------------------------------------------------------------------


class ObservatoryView(ReplayModel):
    """Typed read-only snapshot for the UI."""

    stream: ReplayEventStream
    engine_state: ReplayEngineState
    cursor: ReplayCursor
    window_events: tuple[ReplayEvent, ...] = ()
    selected_event: ReplayEvent | None = None
    present_event_types: tuple[EventType, ...] = ()
    unavailable_event_types: tuple[EventType, ...] = ()
    is_empty: bool = False
    is_aggregate_only: bool = False
    bounded_window: tuple[float, float] | None = None
    causal_disclaimer: str = CAUSAL_DISCLAIMER
    synthetic_disclaimer: str = SYNTHETIC_ENGINEERING_DISCLAIMER
    sync_disclaimer: str = SYNC_CAUSAL_DISCLAIMER


def get_observatory_view(
    engine: ReplayEngine,
    *,
    selected_event_id: str | None = None,
    window_start_s: float | None = None,
    window_end_s: float | None = None,
    max_window_events: int = 200,
) -> ObservatoryView:
    """Build a typed view that revalidates stream/state and respects bounded windows."""

    validated_stream = _revalidate_stream(engine.stream)
    state = _revalidate_state(engine.state())
    cursor = state.cursor

    # Determine window events truthfully.
    if window_start_s is not None and window_end_s is not None:
        window_events = engine.load_time_window(
            window_start_s, window_end_s, max_events=max_window_events
        )
        bounded_window: tuple[float, float] | None = (window_start_s, window_end_s)
    elif window_start_s is not None or window_end_s is not None:
        raise ReplayEngineError("INVALID_WINDOW", "both window bounds must be provided together")
    else:
        # Default: next max_window_events from cursor or bounded engine window
        window_events = engine.load_bounded_window(max_events=max_window_events)
        if engine._window_start_s is not None and engine._window_end_s is not None:  # noqa: SLF001
            bounded_window = (engine._window_start_s, engine._window_end_s)  # noqa: SLF001
        else:
            bounded_window = None

    unavailable = tuple(sorted(set(EventType) - set(validated_stream.present_event_types), key=str))

    selected: ReplayEvent | None = None
    if selected_event_id is not None:
        for event in validated_stream.events:
            if event.event_id == selected_event_id:
                selected = event
                break

    is_agg = validated_stream.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY

    view = ObservatoryView(
        stream=validated_stream,
        engine_state=state,
        cursor=cursor,
        window_events=window_events,
        selected_event=selected,
        present_event_types=validated_stream.present_event_types,
        unavailable_event_types=unavailable,
        is_empty=len(validated_stream.events) == 0,
        is_aggregate_only=is_agg,
        bounded_window=bounded_window,
        causal_disclaimer=CAUSAL_DISCLAIMER,
        synthetic_disclaimer=SYNTHETIC_ENGINEERING_DISCLAIMER,
        sync_disclaimer=SYNC_CAUSAL_DISCLAIMER,
    )
    # Revalidate view canonically
    ObservatoryView.model_validate_json(view.model_dump_json())
    return view


# ---------------------------------------------------------------------------
# Side-by-side compatibility — exact agreement only
# ---------------------------------------------------------------------------


def build_side_by_side_agreement(
    *,
    left_stream: ReplayEventStream,
    right_stream: ReplayEventStream,
    window_start_s: float = 0.0,
    window_end_s: float = 10.0,
    identity_namespace: str = "replay-observatory",
    declared_event_types: tuple[EventType, ...] | None = None,
    compatibility_acknowledged: bool = True,
) -> SideBySideAgreement:
    """Build an explicit agreement requiring common basis/unit/schema/namespace."""

    left = _revalidate_stream(left_stream)
    right = _revalidate_stream(right_stream)
    if declared_event_types is None:
        # Declaration must be exactly the intersection present types that is canonical.
        common = set(left.present_event_types) & set(right.present_event_types)
        declared_event_types = tuple(sorted(common, key=str))
    else:
        declared_event_types = tuple(sorted(declared_event_types, key=str))

    agreement = SideBySideAgreement(
        time_basis="simulator_time_s",
        time_units="seconds",
        tolerance_s=0.0,
        window_start_s=window_start_s,
        window_end_s=window_end_s,
        left_stream_fingerprint=left.fingerprint(),
        right_stream_fingerprint=right.fingerprint(),
        identity_namespace=identity_namespace,
        compatibility_acknowledged=compatibility_acknowledged,
        declared_event_types=declared_event_types,
        causal_disclaimer=SYNC_CAUSAL_DISCLAIMER,
    )
    return _revalidate_agreement(agreement)


def create_side_by_side(
    left_stream: ReplayEventStream,
    right_stream: ReplayEventStream,
    agreement: SideBySideAgreement,
) -> SideBySideReplay:
    """Create a side-by-side replay — refuses incompatible pairs."""

    left = _revalidate_stream(left_stream)
    right = _revalidate_stream(right_stream)
    agr = _revalidate_agreement(agreement)
    replay = SideBySideReplay(left, right, agr)
    # Verify integrity immediately (private deterministic check)
    replay._verify_integrity()  # noqa: SLF001
    return replay


def get_side_by_side_state(replay: SideBySideReplay) -> SideBySideState:
    replay._verify_integrity()  # noqa: SLF001
    state = replay.synchronized_state()
    # Revalidate via model
    SideBySideState.model_validate_json(state.model_dump_json())
    state.verify_against(replay._left_stream, replay._right_stream)  # noqa: SLF001
    return state


# ---------------------------------------------------------------------------
# JSON boundaries — no file/path execution
# ---------------------------------------------------------------------------


def load_stream_json(raw: str | bytes) -> ReplayEventStream:
    """Parse bounded JSON via the fail-closed adapter and revalidate."""

    raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(raw_bytes) > MAX_REPLAY_JSON_BYTES:
        raise ReplayImportError("DOCUMENT_TOO_LARGE", "replay JSON exceeds the byte limit")
    stream = load_event_stream_json(raw, max_bytes=MAX_REPLAY_JSON_BYTES)
    return _revalidate_stream(stream)


def load_aggregate_json(raw: str | bytes) -> ReplayEventStream:
    """Parse aggregate-only JSON and revalidate."""

    stream = load_aggregate_capability_json(raw)
    return _revalidate_stream(stream)


def stream_to_canonical_json(stream: ReplayEventStream) -> str:
    validated = _revalidate_stream(stream)
    return json.dumps(
        validated.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def hash_stream(stream: ReplayEventStream) -> str:
    validated = _revalidate_stream(stream)
    return hashlib.sha256(stream_to_canonical_json(validated).encode("utf-8")).hexdigest()
