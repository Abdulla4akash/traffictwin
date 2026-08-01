"""Bus prediction layer (platform P-2 — the producer-independent study).

Implements the REVIEWED ``docs/platform/bus_prediction_design.md``: a
forecasting model trained ONLY on this project's own aggregate BODS session
measurements and validated on held-out local service dates under the house
predeclaration discipline. Zero VEC producer data, code, parameters or
results enter this module — it deliberately imports nothing from the VEC
surfaces, and a test pins that.

What it predicts, per (day-type, local hour) over the fixed GM box:

- **fleet concurrency** — median/max per-snapshot ``live_vehicle`` (the
  honest concurrency measure; never ``vehicles_linked_across_snapshots``,
  which grows with session length — the 28-July metric-trap lesson);
- **bus progression speed** — the hourly ``measure_session_progression``
  aggregate (never displacement / interval, and never labelled general
  road-traffic speed).

The model is a climatology + persistence blend
``y(h+1) = a * y(h) * r(h->h+1) + (1-a) * mu(h+1, d)`` with ``a`` fitted by
least squares and clamped to [0, 1]. Cells with a zero/unsupported ratio
denominator refuse rather than divide or borrow another day type. Intervals
are per-cell empirical residual quantiles once at least five support dates
exist; before that the cell reports ``insufficient_support`` rather than an
interval. Forecast records are typed ``forecast: true`` /
``evidence: false`` / ``causal: false`` — a forecast never gains standing
merely because code ran.

Inputs are ``bods_session_activity_aggregate`` artifacts only (the §4
boundary the scheduled runner now writes): schema-validated, digest-recorded,
screened for private paths and raw identifiers, refused on duplicates. The
fit never reopens raw BODS data and never sees a salt.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

METHOD_VERSION: Literal["bods-bus-forecast-1.0"] = "bods-bus-forecast-1.0"
DESIGN_REFERENCE: Literal["docs/platform/bus_prediction_design.md"] = (
    "docs/platform/bus_prediction_design.md"
)

TARGET_CONCURRENCY_MEDIAN = "concurrency_median"
TARGET_CONCURRENCY_MAX = "concurrency_max"
TARGET_PROGRESSION_SPEED = "progression_speed_mps"
ALL_TARGETS = (TARGET_CONCURRENCY_MEDIAN, TARGET_CONCURRENCY_MAX, TARGET_PROGRESSION_SPEED)

DAY_TYPES = ("weekday", "weekend")

#: Substrings whose presence in a source file refuses it outright: aggregate
#: inputs must never carry private paths, raw identifiers, or session tokens.
_PRIVATE_CONTENT_MARKERS = (
    "/Users/",
    "/home/",
    "OperatorRef",
    "VehicleRef",
    "vehicle_ref",
    "session_token",
    "raw_ref",
)


class BusPredictionError(RuntimeError):
    """Typed refusal; the forecaster fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ForecastModel(BaseModel):
    """Strict, frozen, finite base for forecast artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class SnapshotConcurrencyRow(ForecastModel):
    snapshot_id: str
    hour_utc: int | None = None
    hour_local: int | None = None
    live_vehicle: int = Field(ge=0)


class ProgressionRow(ForecastModel):
    hour_utc: int = Field(ge=0, le=23)
    hour_local: int = Field(ge=0, le=23)
    segment_count: int = Field(ge=0)
    speed_mps_median: float = Field(ge=0.0)
    speed_mps_p90: float = Field(ge=0.0)
    vehicles_contributing: int = Field(ge=0)


class SessionActivityAggregate(ForecastModel):
    """The §4 boundary artifact — the ONLY input this layer accepts."""

    record_type: Literal["bods_session_activity_aggregate"]
    schema_version: Literal["1.0"]
    design_reference: str
    session_kind: Literal["scheduled", "attended"]
    label: str
    session_date_local: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    utc_offset_seconds_applied: int
    timezone_note: str
    schedule_digest: str | None = None
    snapshot_count: int = Field(ge=0)
    concurrency_source: Literal["parser_live_vehicle", "extracted_observation_count"]
    per_snapshot_live_vehicle: tuple[SnapshotConcurrencyRow, ...]
    progression_available: bool
    progression_unavailable_reason: str | None = None
    hourly_progression: tuple[ProgressionRow, ...] = ()
    aggregates_only: Literal[True]
    raw_identifiers_published: Literal[False]
    bus_progression_only: Literal[True]
    road_traffic_speed_available: Literal[False] = False
    session_salt_discarded: Literal[True]

    @property
    def service_date(self) -> date:
        return date.fromisoformat(self.session_date_local)

    @property
    def day_type(self) -> str:
        return "weekend" if self.service_date.weekday() >= 5 else "weekday"


@dataclass(frozen=True)
class LoadedAggregate:
    """One accepted source: the aggregate plus its content digest."""

    aggregate: SessionActivityAggregate
    sha256: str
    logical_id: str


def load_activity_aggregates(paths: Sequence[Path]) -> tuple[LoadedAggregate, ...]:
    """Read, screen, validate and de-duplicate aggregate sources."""

    loaded: list[LoadedAggregate] = []
    seen_ids: set[str] = set()
    seen_snapshots: set[str] = set()
    for path in paths:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise BusPredictionError(
                "AGGREGATE_UNREADABLE", f"aggregate {path.name} could not be read"
            ) from exc
        text = raw.decode("utf-8", errors="replace")
        for marker in _PRIVATE_CONTENT_MARKERS:
            if marker in text:
                raise BusPredictionError(
                    "PRIVATE_CONTENT_REFUSED",
                    f"aggregate {path.name} contains '{marker}'; inputs must be "
                    "aggregate-only with no private paths or raw identifiers",
                )
        try:
            aggregate = SessionActivityAggregate.model_validate_json(raw)
        except ValidationError as exc:
            raise BusPredictionError(
                "AGGREGATE_INVALID",
                f"aggregate {path.name} is not a valid session activity aggregate",
            ) from exc
        logical_id = f"{aggregate.session_date_local}/{aggregate.label}"
        if logical_id in seen_ids:
            raise BusPredictionError(
                "DUPLICATE_SESSION", f"session {logical_id} appears more than once"
            )
        snapshot_ids = {row.snapshot_id for row in aggregate.per_snapshot_live_vehicle}
        overlap = snapshot_ids & seen_snapshots
        if overlap:
            raise BusPredictionError(
                "DUPLICATE_SESSION",
                f"session {logical_id} shares snapshots with an earlier source "
                f"(e.g. {sorted(overlap)[0]}); sessions must not overlap",
            )
        seen_ids.add(logical_id)
        seen_snapshots.update(snapshot_ids)
        loaded.append(
            LoadedAggregate(
                aggregate=aggregate,
                sha256=hashlib.sha256(raw).hexdigest(),
                logical_id=logical_id,
            )
        )
    return tuple(loaded)


class BuildRules(ForecastModel):
    """Declared eligibility and support rules, recorded into the fit."""

    min_snapshots_per_session: int = Field(default=10, ge=1)
    min_interval_support_dates: int = Field(default=5, ge=2)


class SourceRecord(ForecastModel):
    logical_id: str
    sha256: str
    session_kind: Literal["scheduled", "attended"]
    concurrency_source: Literal["parser_live_vehicle", "extracted_observation_count"]
    snapshot_count: int = Field(ge=0)
    eligible: bool
    exclusion_reason: str | None = None


class CellFit(ForecastModel):
    """One (target, day-type, hour) climatology cell with its raw support."""

    target: str
    day_type: str
    hour_local: int = Field(ge=0, le=23)
    mean: float
    support_dates: int = Field(ge=1)
    dates: tuple[str, ...]
    values: tuple[float, ...]


class BusForecastFit(ForecastModel):
    """The fit artifact: rules, sources, cells, ratios and blend weights."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["bods-bus-forecast-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/bus_prediction_design.md"] = DESIGN_REFERENCE
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    evidence: Literal[False] = False
    generated_at_utc: str
    rules: BuildRules
    targets: tuple[str, ...]
    sources: tuple[SourceRecord, ...]
    fit_dates: tuple[str, ...]
    cells: tuple[CellFit, ...]
    alpha_by_target: dict[str, float | None]
    alpha_pair_counts: dict[str, int]

    def cell(self, target: str, day_type: str, hour_local: int) -> CellFit | None:
        for entry in self.cells:
            if (
                entry.target == target
                and entry.day_type == day_type
                and entry.hour_local == hour_local
            ):
                return entry
        return None


class BusForecastRecord(ForecastModel):
    """One forecast. Typed so it can never masquerade as evidence."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["bods-bus-forecast-1.0"] = METHOD_VERSION
    forecast: Literal[True] = True
    evidence: Literal[False] = False
    causal: Literal[False] = False
    kind: Literal["climatology", "nowcast"]
    target: str
    day_type: str
    hour_local: int = Field(ge=0, le=23)
    value: float | None
    interval_low: float | None
    interval_high: float | None
    support_dates: int = Field(ge=0)
    insufficient_support: bool
    insufficient_reason: str | None
    fit_digest: str
    basis: str


def fit_digest(fit: BusForecastFit) -> str:
    payload = json.dumps(fit.model_dump(mode="json"), sort_keys=True, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- dataset -----------------------------------------------------------------


@dataclass(frozen=True)
class _Observation:
    service_date: str
    day_type: str
    hour_local: int
    value: float


def _observations(
    loaded: Sequence[LoadedAggregate], rules: BuildRules
) -> tuple[dict[str, list[_Observation]], list[SourceRecord]]:
    """Per-target observation rows keyed by the DECLARED local date/hours.

    The builder trusts the aggregate's declared local service date and local
    hours and never re-derives them from UTC — whole-local-date splitting and
    the no-UTC-hour-leak rule depend on that.
    """

    rows: dict[str, list[_Observation]] = {target: [] for target in ALL_TARGETS}
    sources: list[SourceRecord] = []
    pooled: dict[tuple[str, str, int], list[int]] = {}
    speed_pool: dict[tuple[str, str, int], list[tuple[float, int]]] = {}
    for item in loaded:
        aggregate = item.aggregate
        eligible = aggregate.snapshot_count >= rules.min_snapshots_per_session
        reason = (
            None
            if eligible
            else (
                f"{aggregate.snapshot_count} snapshots < declared minimum "
                f"{rules.min_snapshots_per_session}"
            )
        )
        sources.append(
            SourceRecord(
                logical_id=item.logical_id,
                sha256=item.sha256,
                session_kind=aggregate.session_kind,
                concurrency_source=aggregate.concurrency_source,
                snapshot_count=aggregate.snapshot_count,
                eligible=eligible,
                exclusion_reason=reason,
            )
        )
        if not eligible:
            continue
        day_type = aggregate.day_type
        for row in aggregate.per_snapshot_live_vehicle:
            if row.hour_local is None:
                continue
            key = (aggregate.session_date_local, day_type, row.hour_local)
            pooled.setdefault(key, []).append(row.live_vehicle)
        for progression in aggregate.hourly_progression:
            key = (
                aggregate.session_date_local,
                day_type,
                progression.hour_local,
            )
            speed_pool.setdefault(key, []).append(
                (progression.speed_mps_median, progression.segment_count)
            )
    for (service_date, day_type, hour_local), counts in pooled.items():
        rows[TARGET_CONCURRENCY_MEDIAN].append(
            _Observation(service_date, day_type, hour_local, float(statistics.median(counts)))
        )
        rows[TARGET_CONCURRENCY_MAX].append(
            _Observation(service_date, day_type, hour_local, float(max(counts)))
        )
    for (service_date, day_type, hour_local), speed_rows in speed_pool.items():
        total_segments = sum(segments for _, segments in speed_rows)
        if total_segments <= 0:
            continue
        weighted = sum(speed * segments for speed, segments in speed_rows) / total_segments
        rows[TARGET_PROGRESSION_SPEED].append(
            _Observation(service_date, day_type, hour_local, weighted)
        )
    return rows, sources


# --- fit ---------------------------------------------------------------------


def fit_bus_forecast(
    loaded: Sequence[LoadedAggregate],
    rules: BuildRules,
    *,
    generated_at_utc: str,
    targets: tuple[str, ...] = ALL_TARGETS,
) -> BusForecastFit:
    """Fit climatology and the blend weight from eligible aggregates only."""

    for target in targets:
        if target not in ALL_TARGETS:
            raise BusPredictionError("TARGET_UNKNOWN", f"unknown target '{target}'")
    rows, sources = _observations(loaded, rules)
    if TARGET_PROGRESSION_SPEED in targets and not rows[TARGET_PROGRESSION_SPEED]:
        raise BusPredictionError(
            "PROGRESSION_AGGREGATES_MISSING",
            "no eligible source carries hourly progression rows — only cadence-era "
            "(Phase-139) artifacts exist. The scheduled runner's activity-aggregate "
            "boundary must produce progression aggregates before the speed target "
            "can be fitted; concurrency targets remain fittable",
        )
    fit_dates = sorted(
        {observation.service_date for target in targets for observation in rows[target]}
    )
    if not fit_dates:
        raise BusPredictionError(
            "NO_ELIGIBLE_DATA", "no eligible observations exist for the requested targets"
        )
    cells: list[CellFit] = []
    for target in targets:
        grouped: dict[tuple[str, int], list[_Observation]] = {}
        for observation in rows[target]:
            grouped.setdefault((observation.day_type, observation.hour_local), []).append(
                observation
            )
        for (day_type, hour_local), observations in sorted(grouped.items()):
            by_date = sorted(observations, key=lambda item: item.service_date)
            cells.append(
                CellFit(
                    target=target,
                    day_type=day_type,
                    hour_local=hour_local,
                    mean=statistics.fmean(item.value for item in by_date),
                    support_dates=len({item.service_date for item in by_date}),
                    dates=tuple(item.service_date for item in by_date),
                    values=tuple(item.value for item in by_date),
                )
            )
    fit = BusForecastFit(
        generated_at_utc=generated_at_utc,
        rules=rules,
        targets=tuple(targets),
        sources=tuple(sources),
        fit_dates=tuple(fit_dates),
        cells=tuple(cells),
        alpha_by_target=dict.fromkeys(targets),
        alpha_pair_counts=dict.fromkeys(targets, 0),
    )
    alpha_by_target: dict[str, float | None] = {}
    alpha_pairs: dict[str, int] = {}
    for target in targets:
        alpha, pairs = _fit_alpha(fit, rows[target], target)
        alpha_by_target[target] = alpha
        alpha_pairs[target] = pairs
    return fit.model_copy(
        update={"alpha_by_target": alpha_by_target, "alpha_pair_counts": alpha_pairs}
    )


def climatology_ratio(
    fit: BusForecastFit, target: str, day_type: str, hour_local: int
) -> float | None:
    """r(h -> h+1) for one day type; None when the denominator is unsupported.

    Refusing here is the design's rule: never divide by a zero/unsupported
    climatology and never borrow the other day type.
    """

    if hour_local >= 23:
        return None
    current = fit.cell(target, day_type, hour_local)
    following = fit.cell(target, day_type, hour_local + 1)
    if current is None or following is None:
        return None
    if current.mean <= 0.0:
        return None
    return following.mean / current.mean


def _fit_alpha(
    fit: BusForecastFit, observations: Sequence[_Observation], target: str
) -> tuple[float | None, int]:
    by_date_hour = {
        (observation.service_date, observation.hour_local): observation
        for observation in observations
    }
    numerator = 0.0
    denominator = 0.0
    pairs = 0
    for observation in observations:
        following = by_date_hour.get((observation.service_date, observation.hour_local + 1))
        if following is None:
            continue
        ratio = climatology_ratio(fit, target, observation.day_type, observation.hour_local)
        following_cell = fit.cell(target, observation.day_type, observation.hour_local + 1)
        if ratio is None or following_cell is None:
            continue
        persistence = observation.value * ratio
        numerator += (following.value - following_cell.mean) * (persistence - following_cell.mean)
        denominator += (persistence - following_cell.mean) ** 2
        pairs += 1
    if pairs == 0 or denominator == 0.0:
        return None, pairs
    return max(0.0, min(1.0, numerator / denominator)), pairs


# --- predict -----------------------------------------------------------------


def _interval(
    cell: CellFit, rules: BuildRules
) -> tuple[float | None, float | None, bool, str | None]:
    if cell.support_dates < rules.min_interval_support_dates:
        return (
            None,
            None,
            True,
            f"{cell.support_dates} support date(s) < "
            f"{rules.min_interval_support_dates} required for an empirical interval",
        )
    residuals = sorted(value - cell.mean for value in cell.values)
    low = residuals[max(0, int(0.1 * (len(residuals) - 1)))]
    high = residuals[min(len(residuals) - 1, int(round(0.9 * (len(residuals) - 1))))]
    return cell.mean + low, cell.mean + high, False, None


def forecast_climatology(
    fit: BusForecastFit,
    target: str,
    day_type: str,
    hour_local: int,
    *,
    rules: BuildRules,
) -> BusForecastRecord:
    digest = fit_digest(fit)
    cell = fit.cell(target, day_type, hour_local)
    if cell is None:
        return BusForecastRecord(
            kind="climatology",
            target=target,
            day_type=day_type,
            hour_local=hour_local,
            value=None,
            interval_low=None,
            interval_high=None,
            support_dates=0,
            insufficient_support=True,
            insufficient_reason="no eligible observation exists for this cell",
            fit_digest=digest,
            basis="empty cell — thin cells stay visibly thin, never smoothed over",
        )
    low, high, thin, reason = _interval(cell, rules)
    return BusForecastRecord(
        kind="climatology",
        target=target,
        day_type=day_type,
        hour_local=hour_local,
        value=cell.mean,
        interval_low=low,
        interval_high=high,
        support_dates=cell.support_dates,
        insufficient_support=thin,
        insufficient_reason=reason,
        fit_digest=digest,
        basis=(
            f"climatology mean over {cell.support_dates} local service date(s); "
            "interval = empirical residual quantiles at >=5 support dates"
        ),
    )


def forecast_nowcast(
    fit: BusForecastFit,
    target: str,
    day_type: str,
    hour_local: int,
    current_value: float,
    *,
    rules: BuildRules,
) -> BusForecastRecord:
    """Next-hour blend given the current hour's observation."""

    digest = fit_digest(fit)

    def _refused(reason: str) -> BusForecastRecord:
        return BusForecastRecord(
            kind="nowcast",
            target=target,
            day_type=day_type,
            hour_local=hour_local,
            value=None,
            interval_low=None,
            interval_high=None,
            support_dates=0,
            insufficient_support=True,
            insufficient_reason=reason,
            fit_digest=digest,
            basis="refused rather than divide, borrow a day type, or cross midnight",
        )

    if hour_local >= 23:
        return _refused(
            "the nowcast horizon crosses the local-midnight day boundary; no "
            "cross-date ratio is fitted"
        )
    ratio = climatology_ratio(fit, target, day_type, hour_local)
    if ratio is None:
        return _refused(
            "the hour-to-hour climatology ratio is unsupported for this cell "
            "(zero or missing denominator); refusing rather than dividing"
        )
    alpha = fit.alpha_by_target.get(target)
    following = fit.cell(target, day_type, hour_local + 1)
    if alpha is None or following is None:
        return _refused(
            "the blend weight has no supported consecutive-hour fit pairs for this target"
        )
    value = alpha * current_value * ratio + (1.0 - alpha) * following.mean
    low, high, thin, reason = _interval(following, rules)
    return BusForecastRecord(
        kind="nowcast",
        target=target,
        day_type=day_type,
        hour_local=hour_local + 1,
        value=value,
        interval_low=low,
        interval_high=high,
        support_dates=following.support_dates,
        insufficient_support=thin,
        insufficient_reason=reason,
        fit_digest=digest,
        basis=(
            f"blend a*y(h)*r + (1-a)*mu with a={alpha:.3f} "
            f"({fit.alpha_pair_counts.get(target, 0)} fit pairs)"
        ),
    )


# --- validation --------------------------------------------------------------


class CellEvaluation(ForecastModel):
    target: str
    day_type: str
    hour_local: int = Field(ge=0, le=23)
    support_pairs: int = Field(ge=1)
    mae_blend: float
    mae_persistence: float
    mae_climatology: float


class HeldOutEvaluation(ForecastModel):
    """A held-out scoring artifact — never evidence by mere execution."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["bods-bus-forecast-1.0"] = METHOD_VERSION
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    evidence: Literal[False] = False
    confirmatory: Literal[False] = False
    fit_digest: str
    fit_dates: tuple[str, ...]
    held_out_dates: tuple[str, ...]
    cells: tuple[CellEvaluation, ...]
    verdict_by_target: dict[str, str]
    verdict_rule: str


_VERDICT_RULE = (
    "per target, over all evaluable held-out consecutive-hour pairs: mean absolute "
    "error of the blend strictly below the persistence baseline => "
    "BLEND_BEATS_PERSISTENCE; otherwise NULL_PERSISTENCE_NOT_BEATEN (a complete, "
    "publishable outcome); no evaluable pairs => NOT_EVALUABLE"
)


def evaluate_held_out(
    fit: BusForecastFit,
    held_out: Sequence[LoadedAggregate],
    rules: BuildRules,
) -> HeldOutEvaluation:
    """Score the blend against its baselines on strictly later service dates."""

    rows, _ = _observations(held_out, rules)
    held_out_dates = sorted(
        {observation.service_date for target in fit.targets for observation in rows[target]}
    )
    if not held_out_dates:
        raise BusPredictionError("NO_ELIGIBLE_DATA", "no eligible held-out observations exist")
    overlap = set(held_out_dates) & set(fit.fit_dates)
    if overlap:
        raise BusPredictionError(
            "DATE_OVERLAP",
            f"held-out dates {sorted(overlap)} already appear in the fit; whole "
            "local service dates stay on one side of the split",
        )
    latest_fit = max(fit.fit_dates)
    early = [item for item in held_out_dates if item <= latest_fit]
    if early:
        raise BusPredictionError(
            "SPLIT_VIOLATION",
            f"held-out dates {early} are not strictly after the last fit date "
            f"{latest_fit}; the split is chronological by whole local dates",
        )
    errors: dict[tuple[str, str, int], list[tuple[float, float, float]]] = {}
    for target in fit.targets:
        by_date_hour = {
            (observation.service_date, observation.hour_local): observation
            for observation in rows[target]
        }
        for observation in rows[target]:
            following = by_date_hour.get((observation.service_date, observation.hour_local + 1))
            if following is None:
                continue
            ratio = climatology_ratio(fit, target, observation.day_type, observation.hour_local)
            following_cell = fit.cell(target, observation.day_type, observation.hour_local + 1)
            alpha = fit.alpha_by_target.get(target)
            if ratio is None or following_cell is None or alpha is None:
                continue
            blend = alpha * observation.value * ratio + (1.0 - alpha) * following_cell.mean
            key = (target, observation.day_type, observation.hour_local + 1)
            errors.setdefault(key, []).append(
                (
                    abs(following.value - blend),
                    abs(following.value - observation.value),
                    abs(following.value - following_cell.mean),
                )
            )
    cells: list[CellEvaluation] = []
    pooled_by_target: dict[str, list[tuple[float, float, float]]] = {}
    for (target, day_type, hour_local), triples in sorted(errors.items()):
        pooled_by_target.setdefault(target, []).extend(triples)
        cells.append(
            CellEvaluation(
                target=target,
                day_type=day_type,
                hour_local=hour_local,
                support_pairs=len(triples),
                mae_blend=statistics.fmean(item[0] for item in triples),
                mae_persistence=statistics.fmean(item[1] for item in triples),
                mae_climatology=statistics.fmean(item[2] for item in triples),
            )
        )
    verdicts: dict[str, str] = {}
    for target in fit.targets:
        triples = pooled_by_target.get(target, [])
        if not triples:
            verdicts[target] = "NOT_EVALUABLE"
            continue
        mae_blend = statistics.fmean(item[0] for item in triples)
        mae_persistence = statistics.fmean(item[1] for item in triples)
        verdicts[target] = (
            "BLEND_BEATS_PERSISTENCE"
            if mae_blend < mae_persistence
            else "NULL_PERSISTENCE_NOT_BEATEN"
        )
    return HeldOutEvaluation(
        fit_digest=fit_digest(fit),
        fit_dates=fit.fit_dates,
        held_out_dates=tuple(held_out_dates),
        cells=tuple(cells),
        verdict_by_target=verdicts,
        verdict_rule=_VERDICT_RULE,
    )


class SelfTestOutcome(ForecastModel):
    """The verdict machinery exercised on fit dates only (design §3)."""

    passed: bool
    detail: str
    pseudo_held_out_date: str | None = None
    verdict_by_target: dict[str, str] = Field(default_factory=dict)


def verdict_self_test(
    loaded: Sequence[LoadedAggregate],
    rules: BuildRules,
    *,
    generated_at_utc: str,
    targets: tuple[str, ...] = ALL_TARGETS,
) -> SelfTestOutcome:
    """Run the whole fit-and-score chain with the LAST fit date held back.

    This is the design's committed self-test: it proves the verdict code end
    to end using fit dates only, before any real held-out date exists.
    """

    try:
        all_dates = sorted({item.aggregate.session_date_local for item in loaded})
        if len(all_dates) < 2:
            return SelfTestOutcome(
                passed=False,
                detail=(
                    f"self-test needs at least two distinct local service dates; "
                    f"{len(all_dates)} present"
                ),
            )
        pseudo = all_dates[-1]
        earlier = [item for item in loaded if item.aggregate.session_date_local != pseudo]
        later = [item for item in loaded if item.aggregate.session_date_local == pseudo]
        fit = fit_bus_forecast(earlier, rules, generated_at_utc=generated_at_utc, targets=targets)
        evaluation = evaluate_held_out(fit, later, rules)
    except BusPredictionError as error:
        return SelfTestOutcome(passed=False, detail=str(error))
    return SelfTestOutcome(
        passed=True,
        detail=(
            "fit-and-score chain ran end to end on fit dates only; "
            f"{len(evaluation.cells)} cell(s) scored"
        ),
        pseudo_held_out_date=pseudo,
        verdict_by_target=dict(evaluation.verdict_by_target),
    )


# --- readiness ---------------------------------------------------------------


def readiness_report(loaded: Sequence[LoadedAggregate], rules: BuildRules) -> dict[str, object]:
    """Honest readiness: distinct eligible dates and per-target availability.

    Readiness is counted in eligible, distinct local service dates and
    per-cell support after refusals — never wall-clock days of operation.
    """

    rows, sources = _observations(loaded, rules)
    eligible = [source for source in sources if source.eligible]
    dates_by_day_type: dict[str, set[str]] = {day_type: set() for day_type in DAY_TYPES}
    for observation in rows[TARGET_CONCURRENCY_MEDIAN]:
        dates_by_day_type[observation.day_type].add(observation.service_date)
    progression_rows = len(rows[TARGET_PROGRESSION_SPEED])
    return {
        "record_type": "bus_forecast_readiness_report",
        "design_reference": DESIGN_REFERENCE,
        "sources_total": len(sources),
        "sources_eligible": len(eligible),
        "exclusions": [
            {"logical_id": source.logical_id, "reason": source.exclusion_reason}
            for source in sources
            if not source.eligible
        ],
        "eligible_dates_by_day_type": {
            day_type: sorted(dates) for day_type, dates in dates_by_day_type.items()
        },
        "interval_support_threshold_dates": rules.min_interval_support_dates,
        "progression_target_available": progression_rows > 0,
        "progression_note": (
            None
            if progression_rows > 0
            else (
                "no progression rows in any eligible source — only cadence-era "
                "artifacts exist; the speed target cannot be fitted yet"
            )
        ),
        "honesty_note": (
            "readiness is eligible distinct local service dates and per-cell "
            "support after refusals, never wall-clock days; weekend cells need "
            "their own support dates"
        ),
    }
