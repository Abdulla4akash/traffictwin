"""Deterministic occupancy identity construction and mobility joins (VEC-03)."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any

import numpy as np

from traffictwin.integration.tos.contract_v2 import (
    OccupancySpan,
    parse_occupancy_rows,
    reconcile_occupancy_spans,
    validate_trace_arrays,
)
from traffictwin.integration.vec_identity.models import (
    VecIdentityCoverageReport,
    VecIdentityFinding,
    VecIdentityFindingCode,
    VecIdentitySnapshot,
    VecVehicleMobilityObservation,
)


class VecIdentityError(ValueError):
    """Raised when a caller attempts a join outside an accepted identity boundary."""


def _array_fingerprint(arrays: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in sorted(arrays):
        value = np.ascontiguousarray(np.asarray(arrays[key]))
        digest.update(key.encode())
        digest.update(b"\0")
        digest.update(value.dtype.str.encode())
        digest.update(b"\0")
        digest.update(str(value.shape).encode())
        digest.update(b"\0")
        digest.update(value.tobytes())
    return digest.hexdigest()


def _occupancy_fingerprint(spans: Sequence[OccupancySpan]) -> str:
    digest = hashlib.sha256()
    for span in sorted(
        spans,
        key=lambda item: (
            item.scenario,
            item.slot,
            item.t_enter,
            item.t_exit,
            item.sumo_vehicle_id,
        ),
    ):
        digest.update(span.canonical_json().encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _ordered_findings(findings: Iterable[VecIdentityFinding]) -> tuple[VecIdentityFinding, ...]:
    return tuple(sorted(findings, key=lambda finding: (finding.code.value, finding.detail)))


def build_vehicle_identity_snapshot(
    trace_arrays: Mapping[str, Any],
    occupancy_header: Sequence[str],
    occupancy_rows: Sequence[Sequence[str]],
    *,
    scenario: str,
) -> VecIdentitySnapshot:
    """Build an exact span index after complete trace-mask reconciliation.

    Rejected inputs raise ``VecIdentityError`` and never return a partially usable
    index. No identity is inferred from a neighbouring second or a recycled slot.
    """

    trace_report = validate_trace_arrays(trace_arrays)
    if trace_report.status != "accepted":
        codes = ", ".join(finding.code.value for finding in trace_report.findings)
        raise VecIdentityError(f"upstream trace is invalid: {codes}")

    t_count = int(np.asarray(trace_arrays["T"]).item())
    max_n = int(np.asarray(trace_arrays["maxN"]).item())
    mask = np.asarray(trace_arrays["mask"], dtype=bool)
    spans, parse_findings = parse_occupancy_rows(occupancy_header, occupancy_rows, scenario)
    if parse_findings:
        codes = ", ".join(finding.code.value for finding in parse_findings)
        raise VecIdentityError(f"occupancy rows are invalid: {codes}")

    reconciliation = reconcile_occupancy_spans(
        spans,
        t_count=t_count,
        max_n=max_n,
        mask_true_count=int(mask.sum()),
    )
    if reconciliation.status != "accepted":
        codes = ", ".join(finding.code.value for finding in reconciliation.findings)
        raise VecIdentityError(f"occupancy spans are invalid: {codes}")

    identity_mask = np.zeros_like(mask)
    for span in spans:
        identity_mask[span.t_enter : span.t_exit + 1, span.slot] = True
    missing = int(np.count_nonzero(mask & ~identity_mask))
    inactive = int(np.count_nonzero(identity_mask & ~mask))
    findings: list[VecIdentityFinding] = []
    if missing:
        findings.append(
            VecIdentityFinding(
                code=VecIdentityFindingCode.ACTIVE_CELL_WITHOUT_IDENTITY,
                detail=f"{missing} active trace cells have no exact occupancy identity",
            )
        )
    if inactive:
        findings.append(
            VecIdentityFinding(
                code=VecIdentityFindingCode.INACTIVE_CELL_WITH_IDENTITY,
                detail=f"{inactive} occupancy identity cells are inactive in the trace",
            )
        )
    if findings:
        ordered = _ordered_findings(findings)
        raise VecIdentityError("identity coverage rejected: " + ", ".join(x.code for x in ordered))

    ordered_spans = tuple(
        sorted(
            spans,
            key=lambda item: (item.slot, item.t_enter, item.t_exit, item.sumo_vehicle_id),
        )
    )
    report = VecIdentityCoverageReport(
        scenario=scenario,
        status="accepted",
        trace_steps=t_count,
        max_slots=max_n,
        span_count=len(ordered_spans),
        distinct_vehicle_count=len({span.sumo_vehicle_id for span in ordered_spans}),
        active_trace_cells=int(mask.sum()),
        identity_cells=int(identity_mask.sum()),
        missing_identity_cells=0,
        inactive_identity_cells=0,
        trace_fingerprint=_array_fingerprint(trace_arrays),
        occupancy_fingerprint=_occupancy_fingerprint(ordered_spans),
    )
    return VecIdentitySnapshot(report=report, spans=ordered_spans)


def _spans_by_slot(snapshot: VecIdentitySnapshot) -> dict[int, tuple[OccupancySpan, ...]]:
    grouped: dict[int, list[OccupancySpan]] = {}
    for span in snapshot.spans:
        grouped.setdefault(span.slot, []).append(span)
    return {slot: tuple(spans) for slot, spans in grouped.items()}


def resolve_vehicle_identity(
    snapshot: VecIdentitySnapshot,
    *,
    time_index: int,
    slot: int,
) -> str | None:
    """Resolve an exact ID inside an inclusive span, otherwise return ``None``."""

    if not 0 <= time_index < snapshot.report.trace_steps:
        raise VecIdentityError("time_index is outside the trace")
    if not 0 <= slot < snapshot.report.max_slots:
        raise VecIdentityError("slot is outside the trace")
    for span in _spans_by_slot(snapshot).get(slot, ()):
        if span.t_enter <= time_index <= span.t_exit:
            return span.sumo_vehicle_id
    return None


def iter_vehicle_mobility(
    trace_arrays: Mapping[str, Any],
    snapshot: VecIdentitySnapshot,
    *,
    cells: Iterable[tuple[int, int]] | None = None,
) -> Iterator[VecVehicleMobilityObservation]:
    """Yield mobility evidence only for cells admitted by the bound identity index.

    With no explicit cells, observations are emitted in deterministic span/second
    order without constructing a multi-million-row materialisation.
    """

    if _array_fingerprint(trace_arrays) != snapshot.report.trace_fingerprint:
        raise VecIdentityError("trace fingerprint does not match the identity snapshot")
    times = np.asarray(trace_arrays["times"])
    pos_x = np.asarray(trace_arrays["pos_x"])
    pos_y = np.asarray(trace_arrays["pos_y"])
    speed = np.asarray(trace_arrays["speed"])
    mask = np.asarray(trace_arrays["mask"], dtype=bool)

    requested: Iterator[tuple[int, int, str]]
    if cells is None:
        requested = (
            (time_index, span.slot, span.sumo_vehicle_id)
            for span in snapshot.spans
            for time_index in range(span.t_enter, span.t_exit + 1)
        )
    else:
        resolved: list[tuple[int, int, str]] = []
        for time_index, slot in cells:
            vehicle_id = resolve_vehicle_identity(snapshot, time_index=time_index, slot=slot)
            if vehicle_id is None or not bool(mask[time_index, slot]):
                raise VecIdentityError(
                    f"cell ({time_index}, {slot}) is not inside an active occupancy span"
                )
            resolved.append((time_index, slot, vehicle_id))
        requested = iter(resolved)

    for time_index, slot, vehicle_id in requested:
        yield VecVehicleMobilityObservation(
            scenario=snapshot.report.scenario,
            time_index=time_index,
            trace_time_s=float(times[time_index]),
            slot=slot,
            sumo_vehicle_id=vehicle_id,
            pos_x_m=float(pos_x[time_index, slot]),
            pos_y_m=float(pos_y[time_index, slot]),
            speed_mps=float(speed[time_index, slot]),
        )


def trace_fingerprint(trace_arrays: Mapping[str, Any]) -> str:
    """Return the exact fingerprint used to bind an identity snapshot."""

    return _array_fingerprint(trace_arrays)
