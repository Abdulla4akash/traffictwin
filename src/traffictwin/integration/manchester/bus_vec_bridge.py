"""B1 bridge: derived bus trajectories into the shape VEC-06 preprocessing expects.

`bus_trajectory` turns observed bus position fixes into one-second per-vehicle
tracks. VEC-06 preprocessing consumes a dense `(T, maxN)` trace array set beside
an occupancy span table. This module is the join between them, and nothing more:
it assembles the arrays, assigns the slots, writes the spans, and drafts the
preprocessing request the accepted machinery would be asked to run.

**Its output is an input, never a result.** What comes out of here is a proposal
*for* the accepted VEC-06 method — it is not a preprocessing receipt, not an
accepted trace, and not admitted evidence. `vec06_admitted` is a type-level
``False`` on the request draft and there is no code path that can set it
otherwise. The composition labels ride along unchanged from the derivation:
``derived_scenario`` ``True``, ``observed_fcd`` ``False``, ``buses_only``
``True``. Only the fleet *motion* is observation-derived; this is never observed
FCD, and buses are never general traffic.

**What it deliberately does not produce.** The accepted trace bundle also carries
``rsu_xy``, ``window``, and ``sumo_seed``. RSU placement is computed by VEC-06's
own reviewed placement stage from the network and the trace; fabricating
positions here would put invented infrastructure into a scenario and then let it
be mistaken for the accepted stage's output. So the bridge emits the motion
arrays only, names the contract keys it does not emit, and says why. The request
draft carries the declared ``sumo_seed`` and window label so the accepted stage
has what it needs.

**Time base.** Trace rows are offsets from the window start, so ``times`` is
``[0, 1, ..., T-1]``. This is not cosmetic. The accepted contract stores ``times``
as ``float32``, which represents integers exactly only up to 2^24; a derivation
timestamped in epoch seconds (~1.7e9) would silently lose whole seconds if those
values were written directly. The absolute second the window starts at is kept in
``window_start_s`` on both the arrays and the request draft, so the mapping back
to wall-clock is never lost — it is recorded rather than encoded lossily.

**Occupancy spans are row indices, not seconds.** VEC-06's identity
reconciliation reconstructs the mask by indexing ``mask[t_enter : t_exit + 1,
slot]``, so a span's endpoints are positions in the array and the interval is
inclusive at both ends. Emitting absolute seconds here would corrupt every
identity join by exactly ``window_start_s``, which is why the two spaces are kept
visibly separate.

**Slot assignment is deterministic and documented: first free slot, in run
order.** A vehicle's track is split into contiguous runs of seconds — a gap the
derivation dropped ends one run and starts another — and each run is one
occupancy span. Runs are ordered by ``(t_enter, vehicle_key, t_exit)``, and each
is given the lowest slot index not occupied at its start second; a slot whose run
ended at ``t_exit`` becomes free at ``t_exit + 1``. One vehicle can therefore hold
several spans, in different slots, and one slot is reused by unrelated vehicles
across the window — which is exactly why the span table, and not the slot, is the
identity of record.

**Sizes are checked before anything is allocated.** The dense array is
``T x maxN``; a large window over a large fleet is a memory hazard, so the
contract's timestep, concurrency, dense-cell, and observation ceilings are all
tested against the derivation's own counts before a single array is created.

Nothing here reads a file, opens a session artifact, calls BODS, touches a
snapshot, or runs any part of VEC-06. The caller supplies an already-completed
derivation and gets structures back.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from pydantic import Field

from traffictwin.integration.manchester.bus_trajectory import (
    BusTraceDerivation,
    TracePoint,
    VehicleTrack,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.vec_preprocessing.models import (
    MAX_DENSE_TRACE_CELLS,
    MAX_TIMESTEPS,
    MAX_VEHICLE_OBSERVATIONS,
    MAX_VEHICLES_PER_TIMESTEP,
    VecFcdPreprocessRequest,
    VecGreedyUrbanPlacement,
)

BUS_VEC_BRIDGE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
BUS_VEC_BRIDGE_METHOD_VERSION: Literal["manchester-bus-vec-bridge-1.0"] = (
    "manchester-bus-vec-bridge-1.0"
)

#: The accepted VEC-06 trace bundle's keys. The bridge emits the motion subset.
VEC06_TRACE_KEYS: tuple[str, ...] = (
    "pos_x",
    "pos_y",
    "speed",
    "mask",
    "rsu_xy",
    "times",
    "dt",
    "maxN",
    "T",
    "window",
    "sumo_seed",
)

#: Emitted here: the arrays that are a function of the derived motion alone.
BRIDGED_TRACE_KEYS: tuple[str, ...] = (
    "pos_x",
    "pos_y",
    "speed",
    "mask",
    "times",
    "dt",
    "maxN",
    "T",
)

#: Not emitted here, and why. ``rsu_xy`` is VEC-06's reviewed placement stage's
#: output; ``window`` and ``sumo_seed`` are declared on the request, not derived.
UNBRIDGED_TRACE_KEYS: tuple[str, ...] = ("rsu_xy", "window", "sumo_seed")

#: The exact occupancy header the accepted identity reconciliation requires.
OCCUPANCY_HEADER: tuple[str, str, str, str] = (
    "sumo_vehicle_id",
    "slot",
    "t_enter",
    "t_exit",
)

STANDING_BRIDGE_LIMITATIONS = (
    "Construction only: the output is an input for the accepted VEC-06 method, "
    "never a preprocessing receipt, an accepted trace, or admitted evidence.",
    "Derived scenario, not observed FCD. Only the fleet motion is "
    "observation-derived, and buses are never general traffic.",
    "RSU placement is not produced here. Sites come from VEC-06's reviewed "
    "placement stage; none is invented by this bridge.",
    "Slot indices are an array layout, not an identity. The occupancy span table "
    "is the identity of record, and slots are reused across unrelated vehicles.",
    "Assembling a valid trace shape says nothing about whether the derivation "
    "behind it is fit for any scientific purpose.",
)


class BusVecBridgeError(ValueError):
    """Raised when a derivation cannot be assembled into the VEC-06 shape."""


@dataclass(frozen=True, slots=True)
class OccupancySpan:
    """One vehicle's uninterrupted tenancy of one slot, inclusive at both ends.

    ``t_enter`` and ``t_exit`` are **row indices** into the trace arrays, not
    absolute seconds; add ``window_start_s`` to recover wall-clock time.
    """

    sumo_vehicle_id: str
    slot: int
    t_enter: int
    t_exit: int

    def as_row(self) -> tuple[str, str, str, str]:
        """Return this span as the accepted occupancy CSV row."""

        return (self.sumo_vehicle_id, str(self.slot), str(self.t_enter), str(self.t_exit))


@dataclass(frozen=True)
class BusVecTraceArrays:
    """The dense motion arrays in the shape the accepted VEC-06 bundle uses."""

    t_count: int
    max_n: int
    window_start_s: int
    times: npt.NDArray[np.float32]
    pos_x: npt.NDArray[np.float32]
    pos_y: npt.NDArray[np.float32]
    speed: npt.NDArray[np.float32]
    mask: npt.NDArray[np.bool_]

    def as_npz_mapping(self) -> dict[str, Any]:
        """Return the emitted keys under their exact contract names.

        The three contract keys this bridge does not derive are absent rather
        than present-and-empty, so a caller cannot mistake a placeholder for a
        placement.
        """

        return {
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "speed": self.speed,
            "mask": self.mask,
            "times": self.times,
            "dt": np.float32(1.0),
            "maxN": np.int32(self.max_n),
            "T": np.int32(self.t_count),
        }


class BusVecRequestDraft(ManchesterSnapshotModel):
    """A proposed VEC-06 preprocessing request, explicitly not an admission.

    It carries every control the accepted request needs that the derivation
    determines, and none of the ones it cannot know. The two raw-input
    identities — the FCD and network files with their digests — are supplied by
    whoever writes those files, which is why :meth:`to_preprocess_request`
    requires them rather than defaulting them.
    """

    schema_version: Literal["1.0"] = BUS_VEC_BRIDGE_SCHEMA_VERSION
    method_version: Literal["manchester-bus-vec-bridge-1.0"] = BUS_VEC_BRIDGE_METHOD_VERSION

    # Status, fixed in the type. There is no path that sets these otherwise.
    vec06_admitted: Literal[False] = False
    derived_scenario: Literal[True] = True
    observed_fcd: Literal[False] = False
    buses_only: Literal[True] = True
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"

    # Declared controls carried through to the accepted request.
    input_id: str = Field(min_length=1, max_length=200)
    scenario_day: str = Field(min_length=1, max_length=200)
    window_label: str = Field(min_length=1, max_length=200)
    sumo_seed: int = Field(ge=0, le=2_147_483_647)
    placement: VecGreedyUrbanPlacement

    # What the derivation determined, recorded so the draft is self-describing.
    trace_label: str = Field(min_length=1, max_length=200)
    window_start_s: int
    timestep_count: int = Field(ge=1)
    peak_concurrent_vehicles: int = Field(ge=1)
    vehicle_observation_count: int = Field(ge=1)
    unique_vehicle_count: int = Field(ge=1)
    occupancy_span_count: int = Field(ge=1)
    dense_trace_cells: int = Field(ge=1)

    limitations: tuple[str, ...] = STANDING_BRIDGE_LIMITATIONS

    def to_preprocess_request(
        self,
        *,
        fcd_file: str,
        fcd_sha256: str,
        network_file: str,
        network_sha256: str,
    ) -> VecFcdPreprocessRequest:
        """Compose the accepted VEC-06 request from this draft and two raw inputs.

        The digests are the caller's: they identify files this module never
        wrote and cannot hash. Composing the request is still not an admission —
        the accepted preflight decides that, on the real files.
        """

        return VecFcdPreprocessRequest(
            input_id=self.input_id,
            scenario_day=self.scenario_day,
            window_label=self.window_label,
            fcd_file=fcd_file,
            fcd_sha256=fcd_sha256,
            network_file=network_file,
            network_sha256=network_sha256,
            sumo_seed=self.sumo_seed,
            placement=self.placement,
        )


@dataclass(frozen=True)
class BusVecBridgeResult:
    """Everything one derivation yields for the accepted VEC-06 machinery."""

    arrays: BusVecTraceArrays
    spans: tuple[OccupancySpan, ...]
    request_draft: BusVecRequestDraft
    vec06_admitted: Literal[False] = False

    def occupancy_rows(self) -> tuple[tuple[str, str, str, str], ...]:
        """Return the occupancy table body in the accepted header's column order."""

        return tuple(span.as_row() for span in self.spans)


@dataclass(frozen=True, slots=True)
class _Run:
    """One contiguous run of derived seconds for one vehicle."""

    vehicle_key: str
    t_enter: int
    t_exit: int
    points: tuple[TracePoint, ...]


def build_vec06_inputs(
    derivation: BusTraceDerivation,
    *,
    input_id: str,
    scenario_day: str,
    window_label: str,
    sumo_seed: int,
    placement: VecGreedyUrbanPlacement | None = None,
) -> BusVecBridgeResult:
    """Assemble one derivation into the VEC-06 trace shape, spans, and request draft.

    ``placement`` defaults to the accepted request model's own declared default
    rather than to a value chosen here, so the placement controls remain the
    accepted contract's, not this module's.
    """

    runs = _contiguous_runs(derivation.tracks)
    if not runs:
        raise BusVecBridgeError(
            "the derivation contributed no derived seconds; VEC-06 requires at least "
            "one timestep and one vehicle observation"
        )

    window_start_s = min(run.t_enter for run in runs)
    window_end_s = max(run.t_exit for run in runs)
    t_count = window_end_s - window_start_s + 1
    assignments = _assign_slots(runs)
    max_n = 1 + max(slot for _, slot in assignments)
    observation_count = sum(len(run.points) for run in runs)
    _check_contract_limits(
        t_count=t_count,
        max_n=max_n,
        observation_count=observation_count,
    )

    arrays = _dense_arrays(assignments, t_count=t_count, max_n=max_n, offset=window_start_s)
    spans = tuple(
        OccupancySpan(
            sumo_vehicle_id=run.vehicle_key,
            slot=slot,
            t_enter=run.t_enter - window_start_s,
            t_exit=run.t_exit - window_start_s,
        )
        for run, slot in assignments
    )
    draft = BusVecRequestDraft(
        input_id=input_id,
        scenario_day=scenario_day,
        window_label=window_label,
        sumo_seed=sumo_seed,
        placement=placement if placement is not None else VecGreedyUrbanPlacement(),
        trace_label=derivation.report.trace_label,
        window_start_s=window_start_s,
        timestep_count=t_count,
        peak_concurrent_vehicles=max_n,
        vehicle_observation_count=observation_count,
        unique_vehicle_count=len({run.vehicle_key for run in runs}),
        occupancy_span_count=len(spans),
        dense_trace_cells=t_count * max_n,
    )
    return BusVecBridgeResult(
        arrays=BusVecTraceArrays(
            t_count=t_count,
            max_n=max_n,
            window_start_s=window_start_s,
            times=arrays["times"],
            pos_x=arrays["pos_x"],
            pos_y=arrays["pos_y"],
            speed=arrays["speed"],
            mask=arrays["mask"],
        ),
        spans=spans,
        request_draft=draft,
    )


def reconcile_spans_with_mask(spans: Iterable[OccupancySpan], mask: npt.NDArray[np.bool_]) -> None:
    """Raise unless the spans reconstruct the mask exactly, cell for cell.

    The accepted identity boundary refuses an active cell without an identity
    and an identity on an inactive cell. Checking it here means a bridge defect
    surfaces at construction rather than as a rejected VEC-06 admission.
    """

    reconstructed = np.zeros_like(mask, dtype=bool)
    for span in spans:
        if span.t_enter < 0 or span.t_exit >= mask.shape[0]:
            raise BusVecBridgeError(
                f"span for {span.sumo_vehicle_id} falls outside the trace window"
            )
        if span.slot < 0 or span.slot >= mask.shape[1]:
            raise BusVecBridgeError(f"span for {span.sumo_vehicle_id} names an unallocated slot")
        window = reconstructed[span.t_enter : span.t_exit + 1, span.slot]
        if window.any():
            raise BusVecBridgeError(
                f"slot {span.slot} is claimed by more than one span at the same second"
            )
        window[:] = True
    missing = int(np.count_nonzero(mask & ~reconstructed))
    inactive = int(np.count_nonzero(reconstructed & ~mask))
    if missing or inactive:
        raise BusVecBridgeError(
            f"spans do not reconcile with the mask: {missing} active cells without an "
            f"identity, {inactive} identities on inactive cells"
        )


def _contiguous_runs(tracks: Sequence[VehicleTrack]) -> tuple[_Run, ...]:
    """Split every track into runs of consecutive seconds, in derivation order."""

    runs: list[_Run] = []
    for track in tracks:
        if not track.points:
            continue
        ordered = sorted(track.points, key=lambda point: point.time_s)
        for index in range(1, len(ordered)):
            if ordered[index].time_s == ordered[index - 1].time_s:
                raise BusVecBridgeError(
                    f"vehicle {track.vehicle_key} has two derived points at the same second"
                )
        current: list[TracePoint] = [ordered[0]]
        for point in ordered[1:]:
            if point.time_s == current[-1].time_s + 1:
                current.append(point)
                continue
            runs.append(_run(track.vehicle_key, current))
            current = [point]
        runs.append(_run(track.vehicle_key, current))
    return tuple(runs)


def _run(vehicle_key: str, points: Sequence[TracePoint]) -> _Run:
    return _Run(
        vehicle_key=vehicle_key,
        t_enter=points[0].time_s,
        t_exit=points[-1].time_s,
        points=tuple(points),
    )


def _assign_slots(runs: Sequence[_Run]) -> tuple[tuple[_Run, int], ...]:
    """Give every run the lowest slot free at its start second.

    Deterministic by ``(t_enter, vehicle_key, t_exit)`` so two identical
    derivations always produce identical slots — the property that makes a
    bridged trace reproducible.
    """

    ordered = sorted(runs, key=lambda run: (run.t_enter, run.vehicle_key, run.t_exit))
    #: slot index -> the last second that slot stays occupied.
    occupied_until: list[int] = []
    assignments: list[tuple[_Run, int]] = []
    for run in ordered:
        slot = next(
            (index for index, until in enumerate(occupied_until) if until < run.t_enter),
            None,
        )
        if slot is None:
            slot = len(occupied_until)
            occupied_until.append(run.t_exit)
        else:
            occupied_until[slot] = run.t_exit
        assignments.append((run, slot))
    return tuple(assignments)


def _check_contract_limits(*, t_count: int, max_n: int, observation_count: int) -> None:
    """Refuse an over-sized bundle before any dense array is allocated."""

    if t_count > MAX_TIMESTEPS:
        raise BusVecBridgeError(
            f"the derived window spans {t_count} seconds; the accepted contract allows "
            f"{MAX_TIMESTEPS}"
        )
    if max_n > MAX_VEHICLES_PER_TIMESTEP:
        raise BusVecBridgeError(
            f"the derivation needs {max_n} concurrent slots; the accepted contract allows "
            f"{MAX_VEHICLES_PER_TIMESTEP}"
        )
    if t_count * max_n > MAX_DENSE_TRACE_CELLS:
        raise BusVecBridgeError(
            f"a {t_count} x {max_n} dense trace is {t_count * max_n} cells; the accepted "
            f"contract allows {MAX_DENSE_TRACE_CELLS}"
        )
    if observation_count > MAX_VEHICLE_OBSERVATIONS:
        raise BusVecBridgeError(
            f"the derivation carries {observation_count} vehicle observations; the accepted "
            f"contract allows {MAX_VEHICLE_OBSERVATIONS}"
        )


def _dense_arrays(
    assignments: Sequence[tuple[_Run, int]], *, t_count: int, max_n: int, offset: int
) -> dict[str, Any]:
    shape = (t_count, max_n)
    pos_x: npt.NDArray[np.float32] = np.zeros(shape, dtype=np.float32)
    pos_y: npt.NDArray[np.float32] = np.zeros(shape, dtype=np.float32)
    speed: npt.NDArray[np.float32] = np.zeros(shape, dtype=np.float32)
    mask: npt.NDArray[np.bool_] = np.zeros(shape, dtype=bool)
    for run, slot in assignments:
        for point in run.points:
            row = point.time_s - offset
            pos_x[row, slot] = np.float32(point.x_m)
            pos_y[row, slot] = np.float32(point.y_m)
            speed[row, slot] = np.float32(point.speed_mps)
            mask[row, slot] = True
    return {
        "times": np.arange(t_count, dtype=np.float32),
        "pos_x": pos_x,
        "pos_y": pos_y,
        "speed": speed,
        "mask": mask,
    }
