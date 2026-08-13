"""Fail-closed JSON boundary for immutable Replay Observatory streams."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from traffictwin.replay_observatory.models import (
    MAX_EVENTS_PER_STREAM,
    ReplayEventStream,
    SourceDataKind,
    SourceKind,
)

MAX_REPLAY_JSON_BYTES = 2 * 1024 * 1024
MAX_JSON_DEPTH = 32


class ReplayImportError(ValueError):
    """Typed refusal for malformed, unsafe, or capability-inflating imports."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _reject_constant(value: str) -> None:
    raise ReplayImportError("INVALID_JSON_NUMBER", f"non-finite JSON number {value!r} refused")


def _unique_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:  # noqa: ANN401
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReplayImportError("DUPLICATE_JSON_KEY", f"duplicate JSON key {key!r} refused")
        result[key] = value
    return result


def _measure_depth(value: object, *, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        raise ReplayImportError("JSON_TOO_DEEP", "replay JSON nesting exceeds the safe limit")
    if isinstance(value, dict):
        for child in value.values():
            _measure_depth(child, depth=depth + 1)
    elif isinstance(value, list):
        for child in value:
            _measure_depth(child, depth=depth + 1)
    return depth


def load_event_stream_json(
    raw: str | bytes,
    *,
    max_bytes: int = MAX_REPLAY_JSON_BYTES,
    max_events: int = MAX_EVENTS_PER_STREAM,
) -> ReplayEventStream:
    """Parse one bounded stream without accepting paths, commands, or dynamic adapters.

    ``raw`` is document content, never a path.  Adapter selection comes solely from
    the discriminated event union in :mod:`models`; there is no import-by-name or
    arbitrary callable surface.
    """

    if isinstance(raw, str):
        try:
            raw_bytes = raw.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ReplayImportError("INVALID_ENCODING", "replay JSON must be UTF-8") from exc
    elif isinstance(raw, bytes):
        raw_bytes = raw
    else:
        raise ReplayImportError("INVALID_INPUT", "replay input must be JSON text or bytes")
    if max_bytes < 1 or max_bytes > MAX_REPLAY_JSON_BYTES:
        raise ReplayImportError("INVALID_LIMIT", "max_bytes exceeds the fixed safety ceiling")
    if max_events < 0 or max_events > MAX_EVENTS_PER_STREAM:
        raise ReplayImportError("INVALID_LIMIT", "max_events exceeds the fixed safety ceiling")
    if len(raw_bytes) > max_bytes:
        raise ReplayImportError("DOCUMENT_TOO_LARGE", "replay JSON exceeds the byte limit")

    try:
        text = raw_bytes.decode("utf-8", errors="strict")
        document = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except ReplayImportError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayImportError("INVALID_JSON", "replay document is not valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise ReplayImportError("INVALID_DOCUMENT", "replay document root must be an object")
    _measure_depth(document)
    events = document.get("events")
    if not isinstance(events, list):
        raise ReplayImportError("INVALID_DOCUMENT", "events must be a JSON array")
    if len(events) > max_events:
        raise ReplayImportError("TOO_MANY_EVENTS", "replay event count exceeds the import limit")

    # Re-encode after duplicate-key and depth checks. JSON-mode strict validation
    # accepts exact enum strings while still rejecting Python-side coercions.
    canonical_input = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    try:
        stream = ReplayEventStream.model_validate_json(canonical_input, strict=True)
    except ValidationError as exc:
        raise ReplayImportError("SCHEMA_REFUSED", str(exc)) from exc

    manifest = stream.capability_manifest
    if (
        manifest.source.source_kind is SourceKind.RESEARCH_AGGREGATE
        or manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
    ) and stream.events:
        # Defensive adapter-level barrier in addition to model coherence.
        raise ReplayImportError(
            "AGGREGATE_EVENT_INVENTION",
            "aggregate research evidence cannot be transformed into event telemetry",
        )
    return stream


def load_aggregate_capability_json(raw: str | bytes) -> ReplayEventStream:
    """Load a truthful zero-event aggregate declaration; never synthesize telemetry."""

    stream = load_event_stream_json(raw, max_events=MAX_EVENTS_PER_STREAM)
    if stream.capability_manifest.source_data_kind is not SourceDataKind.AGGREGATE_ONLY:
        raise ReplayImportError(
            "NOT_AGGREGATE_ONLY", "aggregate boundary requires an aggregate-only manifest"
        )
    if stream.events:
        raise ReplayImportError(
            "TOO_MANY_EVENTS", "aggregate-only declaration must carry no events"
        )
    return stream
