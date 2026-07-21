"""Read-only exact-ID tripinfo parsing and journey joins (VEC-05)."""

from __future__ import annotations

import gzip
import hashlib
import io
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from traffictwin.integration.tos.contract_v2 import OccupancySpan
from traffictwin.integration.vec_identity import VecIdentitySnapshot, trace_fingerprint
from traffictwin.integration.vec_trip_join.models import (
    VecJourneyDurationSummary,
    VecMatchedTrip,
    VecTripExclusion,
    VecTripExclusionKind,
    VecTripJoinDataset,
    VecTripJoinReport,
)
from traffictwin.metrics.statistics import arithmetic_mean, percentile_linear

MAX_COMPRESSED_BYTES = 20_000_000
MAX_UNCOMPRESSED_BYTES = 32_000_000


class VecTripJoinError(ValueError):
    """Raised when trip evidence cannot support an exact, complete join."""


def _safe_source_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffixes[-2:] != [".xml", ".gz"]:
        raise VecTripJoinError("source_path must be a safe relative .xml.gz path")
    return value


def _decompress(payload: bytes) -> bytes:
    if not 1 <= len(payload) <= MAX_COMPRESSED_BYTES:
        raise VecTripJoinError("compressed tripinfo exceeds the admitted size boundary")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as handle:
            raw = handle.read(MAX_UNCOMPRESSED_BYTES + 1)
    except (OSError, EOFError) as exc:
        raise VecTripJoinError("tripinfo is not valid gzip data") from exc
    if len(raw) > MAX_UNCOMPRESSED_BYTES:
        raise VecTripJoinError("uncompressed tripinfo exceeds the admitted size boundary")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise VecTripJoinError("DTD and entity declarations are not admitted")
    return raw


def _parse_trips(raw: bytes, scenario: str) -> dict[str, VecMatchedTrip]:
    records: dict[str, VecMatchedTrip] = {}
    try:
        iterator = ET.iterparse(io.BytesIO(raw), events=("end",))  # noqa: S314 - DTD rejected
        record_number = 0
        for _, element in iterator:
            if element.tag.rsplit("}", 1)[-1] != "tripinfo":
                continue
            record_number += 1
            vehicle_id = element.attrib.get("id", "")
            if not vehicle_id or vehicle_id in records:
                raise VecTripJoinError("tripinfo vehicle IDs must be non-empty and unique")
            try:
                record = VecMatchedTrip(
                    scenario=scenario,
                    source_record=record_number,
                    sumo_vehicle_id=vehicle_id,
                    depart_s=float(element.attrib["depart"]),
                    arrival_s=float(element.attrib["arrival"]),
                    duration_s=float(element.attrib["duration"]),
                    route_length_m=float(element.attrib["routeLength"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise VecTripJoinError(
                    f"tripinfo record {record_number} has invalid required values"
                ) from exc
            records[vehicle_id] = record
            element.clear()
    except ET.ParseError as exc:
        raise VecTripJoinError("tripinfo XML is malformed") from exc
    if not records:
        raise VecTripJoinError("tripinfo contains no trip records")
    return records


def build_trip_join_dataset(
    trace_arrays: Mapping[str, Any],
    identity: VecIdentitySnapshot,
    compressed_tripinfo: bytes,
    *,
    source_path: str,
) -> VecTripJoinDataset:
    """Join exact occupancy IDs and preserve all non-join cases as exclusions."""

    source_path = _safe_source_path(source_path)
    if trace_fingerprint(trace_arrays) != identity.report.trace_fingerprint:
        raise VecTripJoinError("trace does not match the accepted identity snapshot")
    raw = _decompress(compressed_tripinfo)
    records = _parse_trips(raw, identity.report.scenario)
    spans_by_vehicle: dict[str, list[OccupancySpan]] = {}
    for span in identity.spans:
        spans_by_vehicle.setdefault(span.sumo_vehicle_id, []).append(span)
    matched = tuple(
        records[vehicle_id] for vehicle_id in sorted(spans_by_vehicle.keys() & records.keys())
    )
    exclusions: list[VecTripExclusion] = []
    for vehicle_id in sorted(spans_by_vehicle.keys() - records.keys()):
        at_boundary = any(
            span.t_exit == identity.report.trace_steps - 1 for span in spans_by_vehicle[vehicle_id]
        )
        kind = (
            VecTripExclusionKind.RIGHT_CENSORED_AT_TRACE_BOUNDARY
            if at_boundary
            else VecTripExclusionKind.MISSING_BEFORE_TRACE_BOUNDARY
        )
        reason = (
            "No exact tripinfo record; final occupancy span reaches the trace boundary."
            if at_boundary
            else "No exact tripinfo record; final occupancy span ends before the trace boundary."
        )
        exclusions.append(
            VecTripExclusion(
                scenario=identity.report.scenario,
                sumo_vehicle_id=vehicle_id,
                kind=kind,
                reason=reason,
            )
        )
    durations = [record.duration_s for record in matched]
    if not durations:
        raise VecTripJoinError("no occupancy vehicle has an exact complete tripinfo record")
    summary = VecJourneyDurationSummary(
        eligible_count=len(durations),
        mean_s=arithmetic_mean(durations),
        p50_s=percentile_linear(durations, 0.50),
        p95_s=percentile_linear(durations, 0.95),
        min_s=min(durations),
        max_s=max(durations),
    )
    right_censored = sum(
        item.kind is VecTripExclusionKind.RIGHT_CENSORED_AT_TRACE_BOUNDARY for item in exclusions
    )
    report = VecTripJoinReport(
        scenario=identity.report.scenario,
        source_path=source_path,
        identity_snapshot_fingerprint=identity.fingerprint(),
        compressed_sha256=hashlib.sha256(compressed_tripinfo).hexdigest(),
        compressed_size_bytes=len(compressed_tripinfo),
        uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
        uncompressed_size_bytes=len(raw),
        source_trip_count=len(records),
        source_noncohort_trip_count=len(records) - len(matched),
        occupancy_vehicle_count=len(spans_by_vehicle),
        matched_vehicle_count=len(matched),
        right_censored_count=right_censored,
        missing_before_boundary_count=len(exclusions) - right_censored,
        duration_summary=summary,
    )
    return VecTripJoinDataset(report=report, matched=matched, exclusions=tuple(exclusions))
