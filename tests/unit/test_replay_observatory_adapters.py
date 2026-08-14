"""Fail-closed adapter boundary tests for replay observatory JSON imports."""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from traffictwin.replay_observatory.adapters import (
    MAX_REPLAY_JSON_BYTES,
    ReplayImportError,
    load_aggregate_capability_json,
    load_event_stream_json,
)
from traffictwin.replay_observatory.models import (
    EventProvenance,
    EventType,
    EvidenceStanding,
    SourceDataKind,
    SourceIdentity,
    SourceKind,
)

ARTIFACT = "c" * 64
ARTIFACT2 = "d" * 64


def _source(
    *, artifact: str = ARTIFACT, kind: SourceKind = SourceKind.SYNTHETIC_FIXTURE
) -> SourceIdentity:
    return SourceIdentity(
        source_id="src-001", source_kind=kind, artifact_sha256=artifact, schema_version="1.0"
    )


def _provenance(*, artifact: str = ARTIFACT) -> EventProvenance:
    return EventProvenance(
        source_artifact_sha256=artifact,
        source_record_id="rec-001",
        adapter_id="adapter-v1",
        adapter_version="1.0",
    )


def _valid_stream_dict(
    *,
    source: SourceIdentity | None = None,
    standing: EvidenceStanding = EvidenceStanding.SYNTHETIC_DATA,
    present: list[str] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    src = source or _source()
    if events is None:
        events = [
            {
                "event_id": "evt-001",
                "sequence": 0,
                "simulator_time_s": 0.0,
                "entity": {"kind": "simulation", "entity_id": "sim-001"},
                "source": src.model_dump(mode="json"),
                "evidence_standing": standing.value,
                "provenance": _provenance(artifact=src.artifact_sha256).model_dump(mode="json"),
                "event_type": "simulation_time",
                "payload": {"step_index": 0},
            }
        ]
    if present is None:
        present = ["simulation_time"]
    return {
        "schema_version": "1.0",
        "stream_id": "stream-001",
        "capability_manifest": {
            "schema_version": "1.0",
            "manifest_id": "manifest-001",
            "source": src.model_dump(mode="json"),
            "source_data_kind": "event_stream",
            "evidence_standing": standing.value,
            "available_event_types": sorted(present),
            "limitations": ["Synthetic only"],
        },
        "present_event_types": sorted(present),
        "events": events,
        "limitations": ["Synthetic only"],
    }


def test_load_valid_synthetic_fixture() -> None:
    path = pathlib.Path("tests/fixtures/replay_observatory/synthetic_event_stream_v1.json")
    raw = path.read_text()
    stream = load_event_stream_json(raw)
    assert stream.stream_id == "synthetic-v1"
    assert stream.capability_manifest.evidence_standing is EvidenceStanding.SYNTHETIC_DATA
    assert len(stream.events) == 11
    stream2 = load_event_stream_json(raw)
    assert stream.fingerprint() == stream2.fingerprint()


def test_load_rejects_duplicate_json_keys() -> None:
    # explicit duplicate JSON string exercises duplicate-key rejection
    raw2 = (
        '{"stream_id":"s1","stream_id":"s2","schema_version":"1.0",'
        '"capability_manifest":{"schema_version":"1.0","manifest_id":"m1",'
        '"source":{"source_id":"src-001","source_kind":"synthetic_fixture",'
        '"artifact_sha256":"' + ARTIFACT + '","schema_version":"1.0"}'
        ',"source_data_kind":"event_stream","evidence_standing":"SYNTHETIC DATA",'
        '"available_event_types":[],"limitations":["a"]},'
        '"present_event_types":[],"events":[],"limitations":["a"]}'
    )
    with pytest.raises(ReplayImportError, match="DUPLICATE_JSON_KEY"):
        load_event_stream_json(raw2)


def test_load_rejects_non_finite_numbers() -> None:
    raw = (
        '{"schema_version":"1.0","stream_id":"s1","capability_manifest":'
        '{"schema_version":"1.0","manifest_id":"m1","source":{"source_id":"src-001",'
        '"source_kind":"synthetic_fixture",'
        '"artifact_sha256":"' + ARTIFACT + '","schema_version":"1.0"}'
        ',"source_data_kind":"event_stream","evidence_standing":"SYNTHETIC DATA",'
        '"available_event_types":["simulation_time"],"limitations":["a"]},'
        '"present_event_types":["simulation_time"],"events":[{"event_id":"evt-001",'
        '"sequence":0,"simulator_time_s":Infinity,"entity":{"kind":"simulation",'
        '"entity_id":"sim-001"},"source":{"source_id":"src-001",'
        '"source_kind":"synthetic_fixture",'
        '"artifact_sha256":"' + ARTIFACT + '","schema_version":"1.0"}'
        ',"evidence_standing":"SYNTHETIC DATA","provenance":'
        '{"source_artifact_sha256":"' + ARTIFACT + '","source_record_id":"rec-001",'
        '"adapter_id":"a1","adapter_version":"1.0"},"event_type":"simulation_time",'
        '"payload":{"step_index":0}}],"limitations":["a"]}'
    )
    with pytest.raises(ReplayImportError, match="INVALID_JSON_NUMBER"):
        load_event_stream_json(raw)


def test_load_rejects_too_large_document() -> None:
    data = _valid_stream_dict()
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="DOCUMENT_TOO_LARGE"):
        load_event_stream_json(raw, max_bytes=10)


def test_load_rejects_too_many_events() -> None:
    events: list[dict[str, Any]] = []
    for i in range(5):
        events.append(
            {
                "event_id": f"evt-{i:03d}",
                "sequence": i,
                "simulator_time_s": float(i),
                "entity": {"kind": "simulation", "entity_id": "sim-001"},
                "source": _source().model_dump(mode="json"),
                "evidence_standing": "SYNTHETIC DATA",
                "provenance": _provenance().model_dump(mode="json"),
                "event_type": "simulation_time",
                "payload": {"step_index": i},
            }
        )
    data = _valid_stream_dict(events=events, present=["simulation_time"])
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="TOO_MANY_EVENTS"):
        load_event_stream_json(raw, max_events=2)


def test_load_rejects_invented_undeclared_event() -> None:
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    data["events"][0]["event_type"] = "vehicle_state"
    data["events"][0]["payload"] = {"x_m": 0.0, "y_m": 0.0, "speed_mps": 1.0}
    data["events"][0]["entity"] = {"kind": "vehicle", "entity_id": "veh-001"}
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="SCHEMA_REFUSED"):
        load_event_stream_json(raw)


def test_load_rejects_mismatched_source_identity() -> None:
    src = _source(artifact=ARTIFACT)
    other_src = SourceIdentity(
        source_id="other-src",
        source_kind=SourceKind.SUMO,
        artifact_sha256=ARTIFACT2,
        schema_version="1.0",
    )
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    data["events"][0]["source"] = other_src.model_dump(mode="json")
    data["events"][0]["provenance"]["source_artifact_sha256"] = ARTIFACT2
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="SCHEMA_REFUSED"):
        load_event_stream_json(raw)


def test_load_rejects_mismatched_provenance_fingerprint() -> None:
    src = _source(artifact=ARTIFACT)
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    data["events"][0]["provenance"]["source_artifact_sha256"] = ARTIFACT2
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="SCHEMA_REFUSED"):
        load_event_stream_json(raw)


def test_load_rejects_private_path() -> None:
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    data["limitations"] = ["/tmp/evil/path"]  # noqa: S108
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="SCHEMA_REFUSED"):
        load_event_stream_json(raw)


def test_load_rejects_secret_value() -> None:
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    data["events"][0]["payload"] = {
        "step_index": 0,
        "extra_secret": "api_key: sk_test_1234567890123",
    }
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="SCHEMA_REFUSED"):
        load_event_stream_json(raw)
    data2 = _valid_stream_dict(source=src, present=["simulation_time"])
    data2["limitations"] = ["bearer abcdefghijklmnopqrstuvwxyz012345"]
    raw2 = json.dumps(data2)
    with pytest.raises(ReplayImportError, match="SCHEMA_REFUSED"):
        load_event_stream_json(raw2)


def test_load_rejects_deep_nesting() -> None:
    deep: dict[str, Any] = {}
    cur: dict[str, Any] = deep
    for _ in range(35):
        nxt: dict[str, Any] = {"a": {}}
        cur["a"] = nxt
        cur = nxt
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    raw = json.dumps(
        {
            "a": deep,
            "schema_version": "1.0",
            "stream_id": "s1",
            "capability_manifest": data["capability_manifest"],
            "present_event_types": [],
            "events": [],
            "limitations": ["a"],
        }
    )
    with pytest.raises(ReplayImportError, match="JSON_TOO_DEEP"):
        load_event_stream_json(raw)


def test_load_rejects_aggregate_event_invention() -> None:
    src = SourceIdentity(
        source_id="src-agg",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=ARTIFACT,
        schema_version="1.0",
    )
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "manifest_id": "m1",
        "source": src.model_dump(mode="json"),
        "source_data_kind": "aggregate_only",
        "evidence_standing": "SYNTHETIC DATA",
        "available_event_types": [],
        "limitations": ["a"],
    }
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "stream_id": "s1",
        "capability_manifest": manifest,
        "present_event_types": ["simulation_time"],
        "events": [
            {
                "event_id": "evt-001",
                "sequence": 0,
                "simulator_time_s": 0.0,
                "entity": {"kind": "simulation", "entity_id": "sim-001"},
                "source": src.model_dump(mode="json"),
                "evidence_standing": "SYNTHETIC DATA",
                "provenance": _provenance().model_dump(mode="json"),
                "event_type": "simulation_time",
                "payload": {"step_index": 0},
            }
        ],
        "limitations": ["a"],
    }
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError) as exc:
        load_event_stream_json(raw)
    assert exc.value.code in ("SCHEMA_REFUSED", "AGGREGATE_EVENT_INVENTION")


def test_load_aggregate_boundary_zero_events() -> None:
    src = SourceIdentity(
        source_id="src-agg",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=ARTIFACT,
        schema_version="1.0",
    )
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "stream_id": "agg-001",
        "capability_manifest": {
            "schema_version": "1.0",
            "manifest_id": "m1",
            "source": src.model_dump(mode="json"),
            "source_data_kind": "aggregate_only",
            "evidence_standing": "SYNTHETIC DATA",
            "available_event_types": [],
            "limitations": ["Aggregate only"],
        },
        "present_event_types": [],
        "events": [],
        "limitations": ["Aggregate only"],
    }
    raw = json.dumps(data)
    stream = load_aggregate_capability_json(raw)
    assert stream.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
    assert len(stream.events) == 0


def test_load_aggregate_rejects_event_stream_kind() -> None:
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="NOT_AGGREGATE_ONLY"):
        load_aggregate_capability_json(raw)


def test_load_aggregate_rejects_with_events() -> None:
    src = SourceIdentity(
        source_id="src-agg",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=ARTIFACT,
        schema_version="1.0",
    )
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "stream_id": "agg-001",
        "capability_manifest": {
            "schema_version": "1.0",
            "manifest_id": "m1",
            "source": src.model_dump(mode="json"),
            "source_data_kind": "aggregate_only",
            "evidence_standing": "SYNTHETIC DATA",
            "available_event_types": [],
            "limitations": ["a"],
        },
        "present_event_types": [],
        "events": [],
        "limitations": ["a"],
    }
    data_with_event: dict[str, Any] = dict(data)
    data_with_event["events"] = [
        {
            "event_id": "evt-001",
            "sequence": 0,
            "simulator_time_s": 0.0,
            "entity": {"kind": "simulation", "entity_id": "sim-001"},
            "source": src.model_dump(mode="json"),
            "evidence_standing": "SYNTHETIC DATA",
            "provenance": _provenance().model_dump(mode="json"),
            "event_type": "simulation_time",
            "payload": {"step_index": 0},
        }
    ]
    data_with_event["present_event_types"] = ["simulation_time"]
    raw = json.dumps(data_with_event)
    with pytest.raises(ReplayImportError):
        load_aggregate_capability_json(raw)


def test_load_rejects_e2_aggregate_becoming_task_events() -> None:
    src = SourceIdentity(
        source_id="e2-aggregate",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=ARTIFACT,
        schema_version="1.0",
    )
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "stream_id": "e2-stream",
        "capability_manifest": {
            "schema_version": "1.0",
            "manifest_id": "m1",
            "source": src.model_dump(mode="json"),
            "source_data_kind": "aggregate_only",
            "evidence_standing": "SYNTHETIC DATA",
            "available_event_types": [],
            "limitations": ["E2 aggregate only"],
        },
        "present_event_types": ["task_offered"],
        "events": [
            {
                "event_id": "evt-001",
                "sequence": 0,
                "simulator_time_s": 0.0,
                "entity": {"kind": "task", "entity_id": "task-001"},
                "source": src.model_dump(mode="json"),
                "evidence_standing": "SYNTHETIC DATA",
                "provenance": _provenance().model_dump(mode="json"),
                "event_type": "task_offered",
                "payload": {"offered_to_entity_id": "r1"},
            }
        ],
        "limitations": ["E2 aggregate only"],
    }
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError):
        load_event_stream_json(raw)


def test_load_fails_on_mismatched_evidence_standing() -> None:
    src = _source()
    data = _valid_stream_dict(
        source=src, standing=EvidenceStanding.SYNTHETIC_DATA, present=["simulation_time"]
    )
    data["events"][0]["evidence_standing"] = "SIMULATION OUTPUT"
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="SCHEMA_REFUSED"):
        load_event_stream_json(raw)


def test_load_fails_on_invented_event_type_string() -> None:
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    data["events"][0]["event_type"] = "invented_event"
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="SCHEMA_REFUSED"):
        load_event_stream_json(raw)


def test_load_bytes_input_and_invalid_input() -> None:
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    raw_bytes = json.dumps(data).encode("utf-8")
    stream = load_event_stream_json(raw_bytes)
    assert stream.stream_id == "stream-001"
    with pytest.raises(ReplayImportError, match="INVALID_INPUT"):
        load_event_stream_json(123)  # type: ignore[arg-type]


def test_load_rejects_invalid_json() -> None:
    with pytest.raises(ReplayImportError, match="INVALID_JSON"):
        load_event_stream_json("{bad json")


def test_load_rejects_non_object_root() -> None:
    with pytest.raises(ReplayImportError, match="INVALID_DOCUMENT"):
        load_event_stream_json("[]")


def test_load_rejects_events_not_array() -> None:
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    data["events"] = {"not": "array"}
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="INVALID_DOCUMENT"):
        load_event_stream_json(raw)


def test_load_scale_action_generic_allowed() -> None:
    src = _source()
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "stream_id": "scale-stream",
        "capability_manifest": {
            "schema_version": "1.0",
            "manifest_id": "m1",
            "source": src.model_dump(mode="json"),
            "source_data_kind": "event_stream",
            "evidence_standing": "SYNTHETIC DATA",
            "available_event_types": ["scale_action"],
            "limitations": ["Generic scale representation only"],
        },
        "present_event_types": ["scale_action"],
        "events": [
            {
                "event_id": "evt-scale-001",
                "sequence": 0,
                "simulator_time_s": 1.0,
                "entity": {"kind": "resource", "entity_id": "res-001"},
                "source": src.model_dump(mode="json"),
                "evidence_standing": "SYNTHETIC DATA",
                "provenance": _provenance().model_dump(mode="json"),
                "event_type": "scale_action",
                "payload": {
                    "action_id": "scale-001",
                    "target_resource_id": "res-001",
                    "source_declared_action": "scale_up",
                },
            }
        ],
        "limitations": ["Generic scale representation only"],
    }
    raw = json.dumps(data)
    stream = load_event_stream_json(raw)
    assert stream.events[0].event_type == EventType.SCALE_ACTION
    payload = stream.events[0].payload
    assert hasattr(payload, "source_declared_action")
    assert not hasattr(payload, "e3_policy")


def test_load_bounded_json_size_enforced() -> None:
    src = _source()
    data = _valid_stream_dict(source=src, present=["simulation_time"])
    raw = json.dumps(data)
    with pytest.raises(ReplayImportError, match="DOCUMENT_TOO_LARGE"):
        load_event_stream_json(raw, max_bytes=5)
    with pytest.raises(ReplayImportError, match="INVALID_LIMIT"):
        load_event_stream_json(raw, max_bytes=MAX_REPLAY_JSON_BYTES + 1)
    with pytest.raises(ReplayImportError, match="INVALID_LIMIT"):
        load_event_stream_json(raw, max_events=100000)


def test_synthetic_fixture_is_synthetic_data_only() -> None:
    path = pathlib.Path("tests/fixtures/replay_observatory/synthetic_event_stream_v1.json")
    stream = load_event_stream_json(path.read_text())
    assert stream.capability_manifest.evidence_standing is EvidenceStanding.SYNTHETIC_DATA
    for evt in stream.events:
        assert evt.evidence_standing is EvidenceStanding.SYNTHETIC_DATA
    raw = path.read_text()
    assert "REAL MANCHESTER DATA" not in raw
    assert "REAL EXTERNAL" not in raw
