"""Derived per-RSU load measures for the additive RSU Monitor page.

The page-independent half of the Study Case 1 question "which RSU is
overwhelmed, and how overwhelmed". Everything here is a deterministic function
over the *already accepted* RSU replay history that
:func:`traffictwin.ui.services.load_tos_rsu_series_for_ui` returns — no raw
artifact is parsed, no accepted loader is modified, and no value is invented.

Two absences are measured facts about the source arrays rather than gaps to
fill, so they are returned as typed unavailable reasons and never estimated:

* **Per-RSU energy.** The RSU history carries in-flight task count, remaining
  compute backlog, and the concurrency-pressure fraction. ``avg_energy_j_per_task``
  exists only as a whole-run summary field, so no per-RSU energy series can be
  derived without inventing an attribution rule.
* **Per-RSU processed tasks.** The per-task showcase arrays carry no RSU
  attribution, so completed-task counts exist per run, never per RSU.

Concurrency pressure is in-flight tasks divided by the recorded maximum
concurrent tasks. It is not CPU utilisation, and none of this is live
monitoring: every view is labelled with the run key, source file, and the
window bounds it was read from.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from traffictwin.integration.tos.models import TosRsuReplayPoint

#: Reason strings for the two measured absences, kept as literals so a caller
#: cannot silently substitute a different explanation.
RSU_ENERGY_UNAVAILABLE_REASON = (
    "Per-RSU energy is not recorded in the source RSU history. Energy exists "
    "only as a whole-run average per task, which cannot be attributed to one "
    "RSU without inventing an attribution rule."
)
RSU_PROCESSED_TASKS_UNAVAILABLE_REASON = (
    "Per-RSU processed-task counts are not recorded. The per-task arrays carry "
    "no RSU attribution, so completed-task totals exist for the run only."
)

MeasurementStatus = Literal["available", "unavailable"]


@dataclass(frozen=True)
class RsuMonitorError:
    """User-facing monitor error with optional technical detail."""

    message: str
    detail: str | None = None


@dataclass(frozen=True)
class RsuUnavailableMeasurement:
    """One measurement that the accepted source arrays genuinely do not carry."""

    measurement: str
    status: MeasurementStatus
    reason: str


@dataclass(frozen=True)
class RsuWindowIdentity:
    """The exact run and trace window a set of per-RSU series was read from."""

    run_key: str
    source_file: str
    first_timestamp_s: float
    last_timestamp_s: float
    point_count: int
    rsu_count: int
    stride: int
    semantics_evidence_commit: str

    @property
    def window_duration_s(self) -> float:
        """Return the span the series covers, in simulation seconds."""

        return self.last_timestamp_s - self.first_timestamp_s


@dataclass(frozen=True)
class RsuLoadPoint:
    """One timestamped load observation for a single RSU."""

    timestamp_s: float
    active_task_count: int
    remaining_compute_backlog_ms: float
    concurrency_pressure_fraction: float


@dataclass(frozen=True)
class RsuLoadProfile:
    """Derived load measures for one RSU over one window."""

    rsu_reference: str
    rsu_index: int
    max_concurrent_tasks: int
    observation_count: int
    points: tuple[RsuLoadPoint, ...]
    mean_pressure: float
    peak_pressure: float
    peak_pressure_timestamp_s: float
    mean_active_task_count: float
    peak_active_task_count: int
    mean_backlog_ms: float
    peak_backlog_ms: float
    peak_backlog_timestamp_s: float
    saturated_observation_count: int

    @property
    def saturated_share(self) -> float:
        """Return the share of observations at full recorded concurrency."""

        if self.observation_count == 0:
            return 0.0
        return self.saturated_observation_count / self.observation_count


@dataclass(frozen=True)
class RsuLoadAsymmetry:
    """How unevenly in-flight load is spread across the RSUs of one window."""

    rsu_count: int
    busiest_rsu_reference: str
    quietest_rsu_reference: str
    highest_mean_pressure: float
    lowest_mean_pressure: float
    mean_pressure_spread: float
    busiest_share_of_active_task_time: float
    even_share: float
    saturated_rsu_count: int

    @property
    def busiest_share_ratio_to_even(self) -> float:
        """Return the busiest RSU's load share relative to an even split."""

        if self.even_share == 0:
            return 0.0
        return self.busiest_share_of_active_task_time / self.even_share


@dataclass(frozen=True)
class RsuMonitorView:
    """Everything the RSU Monitor page renders for one imported run."""

    identity: RsuWindowIdentity
    profiles: tuple[RsuLoadProfile, ...]
    asymmetry: RsuLoadAsymmetry
    unavailable: tuple[RsuUnavailableMeasurement, ...]

    def profile_for(self, rsu_reference: str) -> RsuLoadProfile | None:
        """Return one RSU's profile, or ``None`` when it is not in this window."""

        for profile in self.profiles:
            if profile.rsu_reference == rsu_reference:
                return profile
        return None

    @property
    def rsu_references(self) -> tuple[str, ...]:
        """Return every RSU reference in this window, busiest first."""

        return tuple(profile.rsu_reference for profile in self.profiles)


def unavailable_measurements() -> tuple[RsuUnavailableMeasurement, ...]:
    """Return the measured absences the page must state rather than fill."""

    return (
        RsuUnavailableMeasurement(
            measurement="per-RSU energy over the window",
            status="unavailable",
            reason=RSU_ENERGY_UNAVAILABLE_REASON,
        ),
        RsuUnavailableMeasurement(
            measurement="per-RSU processed-task count",
            status="unavailable",
            reason=RSU_PROCESSED_TASKS_UNAVAILABLE_REASON,
        ),
    )


def build_rsu_monitor_view(
    points: list[TosRsuReplayPoint],
    run_key: str,
    *,
    stride: int = 1,
) -> RsuMonitorView | RsuMonitorError:
    """Derive every per-RSU and cross-RSU measure for one loaded window.

    ``points`` is the accepted loader's output verbatim: one interpreted point
    per RSU per sampled step. Ordering of the returned profiles is deterministic
    — descending mean pressure, then ascending RSU index — so the page's
    selection control is stable across reruns.
    """

    if not points:
        return RsuMonitorError(
            "The selected run has no RSU history points, so no RSU load can be shown."
        )
    source_files = {point.source_file for point in points}
    if len(source_files) != 1:
        return RsuMonitorError(
            "The RSU history mixes more than one source file; it is not one window."
        )
    grouped: dict[str, list[TosRsuReplayPoint]] = {}
    for point in points:
        grouped.setdefault(point.rsu_reference, []).append(point)

    profiles = [_profile(reference, group) for reference, group in grouped.items()]
    profiles.sort(key=lambda profile: (-profile.mean_pressure, profile.rsu_index))
    timestamps = [point.timestamp_s for point in points]
    identity = RsuWindowIdentity(
        run_key=run_key,
        source_file=next(iter(source_files)),
        first_timestamp_s=min(timestamps),
        last_timestamp_s=max(timestamps),
        point_count=len(points),
        rsu_count=len(profiles),
        stride=stride,
        semantics_evidence_commit=points[0].semantics_evidence_commit,
    )
    return RsuMonitorView(
        identity=identity,
        profiles=tuple(profiles),
        asymmetry=_asymmetry(profiles),
        unavailable=unavailable_measurements(),
    )


def _profile(rsu_reference: str, group: list[TosRsuReplayPoint]) -> RsuLoadProfile:
    ordered = sorted(group, key=lambda point: (point.timestamp_s, point.index))
    pressures = [point.concurrency_pressure_fraction for point in ordered]
    actives = [point.active_task_count for point in ordered]
    backlogs = [point.remaining_compute_backlog_ms for point in ordered]
    peak_pressure_at = max(ordered, key=lambda point: (point.concurrency_pressure_fraction,))
    peak_backlog_at = max(ordered, key=lambda point: (point.remaining_compute_backlog_ms,))
    # Saturation is an exact comparison against the recorded maximum rather
    # than a tolerance, because both sides are integers in the source arrays.
    saturated = sum(1 for point in ordered if point.active_task_count >= point.max_concurrent_tasks)
    return RsuLoadProfile(
        rsu_reference=rsu_reference,
        rsu_index=ordered[0].rsu_index,
        max_concurrent_tasks=ordered[0].max_concurrent_tasks,
        observation_count=len(ordered),
        points=tuple(
            RsuLoadPoint(
                timestamp_s=point.timestamp_s,
                active_task_count=point.active_task_count,
                remaining_compute_backlog_ms=point.remaining_compute_backlog_ms,
                concurrency_pressure_fraction=point.concurrency_pressure_fraction,
            )
            for point in ordered
        ),
        mean_pressure=_mean(pressures),
        peak_pressure=max(pressures),
        peak_pressure_timestamp_s=peak_pressure_at.timestamp_s,
        mean_active_task_count=_mean([float(value) for value in actives]),
        peak_active_task_count=max(actives),
        mean_backlog_ms=_mean(backlogs),
        peak_backlog_ms=max(backlogs),
        peak_backlog_timestamp_s=peak_backlog_at.timestamp_s,
        saturated_observation_count=saturated,
    )


def _asymmetry(profiles: list[RsuLoadProfile]) -> RsuLoadAsymmetry:
    means = [profile.mean_pressure for profile in profiles]
    busiest = max(profiles, key=lambda profile: (profile.mean_pressure, -profile.rsu_index))
    quietest = min(profiles, key=lambda profile: (profile.mean_pressure, profile.rsu_index))
    # Share of in-flight task time, using each RSU's own observation count so a
    # partially observed RSU cannot look busier than it was recorded to be.
    task_time = {
        profile.rsu_reference: profile.mean_active_task_count * profile.observation_count
        for profile in profiles
    }
    total_task_time = sum(task_time.values())
    busiest_share = (
        task_time[busiest.rsu_reference] / total_task_time if total_task_time > 0 else 0.0
    )
    return RsuLoadAsymmetry(
        rsu_count=len(profiles),
        busiest_rsu_reference=busiest.rsu_reference,
        quietest_rsu_reference=quietest.rsu_reference,
        highest_mean_pressure=max(means),
        lowest_mean_pressure=min(means),
        mean_pressure_spread=max(means) - min(means),
        busiest_share_of_active_task_time=busiest_share,
        even_share=1.0 / len(profiles),
        saturated_rsu_count=sum(
            1 for profile in profiles if profile.saturated_observation_count > 0
        ),
    )


def _mean(values: list[float]) -> float:
    total = math.fsum(values)
    return total / len(values)
