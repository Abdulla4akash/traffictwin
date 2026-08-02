"""Incremental analytics and data-quality monitor (post-v1 A-1, prototype path).

Implements ``docs/platform/incremental_analytics_monitor_design.md``:
deterministic micro-batch materialisation over the aggregate archive, with
visible quality checks. This is the design's PROTOTYPE dependency path — an
explicit list of digest-pinned activity aggregates in, and no parallel
persistent catalogue invented (the historical store is the lead's surface).

Guarantees, structurally:

- each accepted aggregate is processed EXACTLY once per analytics version:
  work items are keyed by (source digest, schema version, analytics
  version); reservation and commit are separate checkpoint lines, so a
  crash before commit stays retryable and a repeated identical item returns
  its existing receipt; changed bytes under the same logical id refuse;
- materialisations are the declared small set only, computed
  order-independently — ``vehicles_linked_across_snapshots`` is never
  substituted for concurrency, progression is never renamed traffic speed,
  and declared local-time metadata is retained rather than re-derived;
- quality observations carry rule version and OPERATIONAL severity (info /
  warning / refusal) — never scientific confidence; drift wording is
  descriptive; missing is never shown as zero;
- outputs inherit the weakest standing of their inputs: everything is
  ``evidence: false`` at the ``owner_approved_candidate`` ceiling, and any
  attempt to label an output stronger refuses (``STANDING_ESCALATION``);
- the monitor never opens raw quarantine, never creates a salt, never joins
  identities, and cannot start the runner.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from traffictwin.platform.bus_prediction import (
    BuildRules,
    LoadedAggregate,
    readiness_report,
)

ANALYTICS_VERSION: Literal["incremental-analytics-1.0"] = "incremental-analytics-1.0"
DESIGN_REFERENCE: Literal["docs/platform/incremental_analytics_monitor_design.md"] = (
    "docs/platform/incremental_analytics_monitor_design.md"
)

Severity = Literal["info", "warning", "refusal"]

_LOCAL_SERVICE_ZONE = ZoneInfo("Europe/London")


class AnalyticsMonitorError(RuntimeError):
    """Typed refusal; the monitor fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class MonitorModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class AnalyticsWorkItem(MonitorModel):
    """One immutable unit of work, keyed for exactly-once processing."""

    work_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    logical_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str
    analytics_version: Literal["incremental-analytics-1.0"] = ANALYTICS_VERSION


class HourlyMaterialisation(MonitorModel):
    hour_local: int = Field(ge=0, le=23)
    snapshot_count: int = Field(ge=0)
    concurrency_median: float | None
    concurrency_max: int | None
    progression_speed_mps_median: float | None
    progression_segment_count: int | None


class MaterialisationSnapshot(MonitorModel):
    """The declared measures for one session aggregate — nothing more."""

    logical_id: str
    session_kind: Literal["scheduled", "attended"]
    concurrency_source: str
    session_date_local: str
    day_type: str
    hourly: tuple[HourlyMaterialisation, ...]
    progression_available: bool
    progression_note: str | None
    evidence: Literal[False] = False
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class IncrementalAnalyticsReceipt(MonitorModel):
    work_key: str
    logical_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_schema_version: str
    materialisation_digest: str
    analytics_version: Literal["incremental-analytics-1.0"] = ANALYTICS_VERSION
    evidence: Literal[False] = False
    idempotent_replay: bool = False


class QualityObservation(MonitorModel):
    rule: str
    rule_version: Literal["1.0", "2.0"] = "1.0"
    scope: str
    measured: str
    severity: Severity
    source_sha256: str
    support: int | None = Field(default=None, ge=0)
    first_occurrence_utc: datetime | None = None
    last_occurrence_utc: datetime | None = None


class DataQualityReport(MonitorModel):
    """Accepted / warned / refused / not-observed — missing is never zero."""

    analytics_version: Literal["incremental-analytics-1.0"] = ANALYTICS_VERSION
    design_reference: Literal["docs/platform/incremental_analytics_monitor_design.md"] = (
        DESIGN_REFERENCE
    )
    evidence: Literal[False] = False
    accepted: tuple[str, ...]
    warned: tuple[QualityObservation, ...]
    refused: tuple[QualityObservation, ...]
    not_observed: tuple[str, ...]
    standing_note: str
    informational: tuple[QualityObservation, ...] = ()
    generated_at_utc: datetime | None = None
    operational_policy_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    notification_surface: tuple[str, ...] = ()
    retention_policy: str | None = None

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AnalyticsOperationalPolicy(MonitorModel):
    """Owner-selected local micro-batch and alert policy."""

    policy_version: Literal["analytics-operations-2026-08-02"] = "analytics-operations-2026-08-02"
    cadence_minutes: Literal[15] = 15
    freshness_warning_minutes: Literal[30] = 30
    freshness_refusal_minutes: Literal[60] = 60
    completeness_warning_ratio: float = Field(default=0.95, ge=0.0, le=1.0)
    completeness_refusal_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    exclusion_warning_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    exclusion_refusal_ratio: float = Field(default=0.25, ge=0.0, le=1.0)
    overlap_is_refusal: Literal[True] = True
    unknown_schema_is_refusal: Literal[True] = True
    supported_schema_versions: tuple[str, ...] = ("1.0",)
    local_dashboard_alerts: Literal[True] = True
    local_report_receipts: Literal[True] = True
    external_notifications: Literal[False] = False
    retention: Literal["indefinite"] = "indefinite"
    automatic_deletion: Literal[False] = False

    @model_validator(mode="after")
    def validate_threshold_order(self) -> AnalyticsOperationalPolicy:
        if not self.supported_schema_versions:
            raise ValueError("at least one schema version must be supported")
        if self.freshness_warning_minutes >= self.freshness_refusal_minutes:
            raise ValueError("freshness warning must precede refusal")
        if self.completeness_refusal_ratio >= self.completeness_warning_ratio:
            raise ValueError("completeness refusal must be below warning")
        if self.exclusion_warning_ratio >= self.exclusion_refusal_ratio:
            raise ValueError("exclusion warning must precede refusal")
        return self

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class SourceQualityContext(MonitorModel):
    """Digest-bound scheduling facts supplied beside one aggregate."""

    logical_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_stream: str
    source_schema_version: str
    first_snapshot_at_utc: datetime
    last_snapshot_at_utc: datetime
    expected_snapshot_count: int = Field(ge=1)
    progression_segments_total: int = Field(default=0, ge=0)
    progression_segments_excluded: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_times_and_counts(self) -> SourceQualityContext:
        for label, value in (
            ("first_snapshot_at_utc", self.first_snapshot_at_utc),
            ("last_snapshot_at_utc", self.last_snapshot_at_utc),
        ):
            if value.utcoffset() != timedelta(0):
                raise ValueError(f"{label} must be timezone-aware UTC")
        if self.last_snapshot_at_utc < self.first_snapshot_at_utc:
            raise ValueError("last snapshot precedes first snapshot")
        if self.progression_segments_excluded > self.progression_segments_total:
            raise ValueError("excluded progression segments exceed total segments")
        return self


class ScheduledReadinessCell(MonitorModel):
    """One UTC-driven schedule cell with explicit Europe/London DST metadata."""

    scheduled_at_utc: datetime
    service_date_local: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    hour_local: int = Field(ge=0, le=23)
    minute_local: int = Field(ge=0, le=59)
    utc_offset_seconds: int
    fold: Literal[0, 1]


class LocalQualityReportReceipt(MonitorModel):
    """Immutable publication receipt consumed by a local dashboard."""

    report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    operational_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_name: str = Field(pattern=r"^[0-9a-f]{64}\.json$")
    idempotent_replay: bool = False
    evidence: Literal[False] = False


def plan_increment(item: LoadedAggregate) -> AnalyticsWorkItem:
    """Derive the exactly-once work key for one accepted aggregate."""

    aggregate = item.aggregate
    key = hashlib.sha256(
        f"{item.sha256}:{aggregate.schema_version}:{ANALYTICS_VERSION}".encode()
    ).hexdigest()
    return AnalyticsWorkItem(
        work_key=key,
        logical_id=item.logical_id,
        source_sha256=item.sha256,
        schema_version=aggregate.schema_version,
    )


class IncrementalAnalyticsMonitor:
    """Exactly-once micro-batch processor over one explicit checkpoint file."""

    def __init__(self, checkpoint_path: Path) -> None:
        self._checkpoint_path = checkpoint_path
        self._committed: dict[str, IncrementalAnalyticsReceipt] = {}
        self._reserved: set[str] = set()
        self._logical_digests: dict[str, str] = {}
        self._materialisations: dict[str, MaterialisationSnapshot] = {}
        if checkpoint_path.exists():
            self._replay(checkpoint_path.read_text(encoding="utf-8"))

    def _replay(self, raw: str) -> None:
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                kind = entry.pop("_kind")
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise AnalyticsMonitorError(
                    "CHECKPOINT_CONFLICT",
                    f"checkpoint line {line_number} is incomplete or invalid",
                ) from exc
            if kind == "reserve":
                work_key = entry.get("work_key")
                if not isinstance(work_key, str):
                    raise AnalyticsMonitorError(
                        "CHECKPOINT_CONFLICT",
                        f"checkpoint reservation at line {line_number} has no work key",
                    )
                self._reserved.add(work_key)
            elif kind == "commit":
                try:
                    receipt = IncrementalAnalyticsReceipt.model_validate_json(
                        json.dumps(entry["receipt"])
                    )
                    snapshot = MaterialisationSnapshot.model_validate_json(
                        json.dumps(entry["materialisation"])
                    )
                except (KeyError, ValidationError) as exc:
                    raise AnalyticsMonitorError(
                        "CHECKPOINT_CONFLICT",
                        "a committed checkpoint lacks the source and materialisation state "
                        "needed for deterministic replay",
                    ) from exc
                expected_work_key = hashlib.sha256(
                    (
                        f"{receipt.source_sha256}:{receipt.source_schema_version}:"
                        f"{receipt.analytics_version}"
                    ).encode()
                ).hexdigest()
                if expected_work_key != receipt.work_key:
                    raise AnalyticsMonitorError(
                        "CHECKPOINT_CONFLICT",
                        f"commit at line {line_number} has an invalid work key",
                    )
                if snapshot.logical_id != receipt.logical_id or snapshot.digest() != (
                    receipt.materialisation_digest
                ):
                    raise AnalyticsMonitorError(
                        "CHECKPOINT_CONFLICT",
                        f"commit at line {line_number} does not bind its materialisation",
                    )
                known = self._logical_digests.get(receipt.logical_id)
                if known is not None and known != receipt.source_sha256:
                    raise AnalyticsMonitorError(
                        "DUPLICATE_LOGICAL_SOURCE",
                        f"checkpoint contains conflicting bytes for '{receipt.logical_id}'",
                    )
                self._committed[receipt.work_key] = receipt
                self._logical_digests[receipt.logical_id] = receipt.source_sha256
                self._materialisations[receipt.logical_id] = snapshot
                self._reserved.discard(receipt.work_key)
            else:
                raise AnalyticsMonitorError(
                    "CHECKPOINT_CONFLICT",
                    f"checkpoint line {line_number} has unknown kind '{kind}'",
                )

    def _append(self, kind: str, payload: dict[str, object]) -> None:
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with self._checkpoint_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"_kind": kind, **payload}, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def retryable_reservations(self) -> tuple[str, ...]:
        """Reserved-but-uncommitted keys — a crash left these retryable."""

        return tuple(sorted(self._reserved - set(self._committed)))

    def apply_increment(self, item: LoadedAggregate) -> IncrementalAnalyticsReceipt:
        work = plan_increment(item)
        existing = self._committed.get(work.work_key)
        if existing is not None:
            return existing.model_copy(update={"idempotent_replay": True})
        known_digest = self._logical_digests.get(work.logical_id)
        if known_digest is not None and known_digest != work.source_sha256:
            raise AnalyticsMonitorError(
                "DUPLICATE_LOGICAL_SOURCE",
                f"logical id '{work.logical_id}' was processed with different bytes; "
                "changed sources refuse rather than silently supersede",
            )
        self._append("reserve", {"work_key": work.work_key})
        self._reserved.add(work.work_key)
        snapshot = materialise(item)
        receipt = IncrementalAnalyticsReceipt(
            work_key=work.work_key,
            logical_id=work.logical_id,
            source_sha256=work.source_sha256,
            source_schema_version=work.schema_version,
            materialisation_digest=snapshot.digest(),
        )
        self._append(
            "commit",
            {
                "receipt": receipt.model_dump(mode="json"),
                "materialisation": snapshot.model_dump(mode="json"),
            },
        )
        self._materialisations[work.logical_id] = snapshot
        self._logical_digests[work.logical_id] = work.source_sha256
        self._committed[work.work_key] = receipt
        self._reserved.discard(work.work_key)
        return receipt

    def materialisation(self, logical_id: str) -> MaterialisationSnapshot | None:
        return self._materialisations.get(logical_id)

    def materialisation_digests(self) -> dict[str, str]:
        return {
            logical_id: snapshot.digest()
            for logical_id, snapshot in sorted(self._materialisations.items())
        }

    def label_output(self, standing: str) -> str:
        """Outputs inherit the weakest standing; escalation refuses."""

        if standing != "owner_approved_candidate":
            raise AnalyticsMonitorError(
                "STANDING_ESCALATION",
                f"analytics outputs cannot carry standing '{standing}'; a data-quality "
                "pass does not admit a source and the ceiling is owner_approved_candidate",
            )
        return standing


def materialise(item: LoadedAggregate) -> MaterialisationSnapshot:
    """Compute ONLY the declared measures for one aggregate, deterministically."""

    aggregate = item.aggregate
    counts_by_hour: dict[int, list[int]] = {}
    missing_hours = 0
    for row in aggregate.per_snapshot_live_vehicle:
        if row.hour_local is None:
            missing_hours += 1
            continue
        counts_by_hour.setdefault(row.hour_local, []).append(row.live_vehicle)
    if aggregate.per_snapshot_live_vehicle and missing_hours == len(
        aggregate.per_snapshot_live_vehicle
    ):
        raise AnalyticsMonitorError(
            "LOCAL_TIME_METADATA_MISSING",
            f"'{item.logical_id}' declares no local hour on any snapshot; UTC hours "
            "are never reinterpreted as local service hours",
        )
    progression_by_hour = {row.hour_local: row for row in aggregate.hourly_progression}
    hours = sorted(set(counts_by_hour) | set(progression_by_hour))
    hourly = []
    for hour in hours:
        counts = counts_by_hour.get(hour)
        progression = progression_by_hour.get(hour)
        hourly.append(
            HourlyMaterialisation(
                hour_local=hour,
                snapshot_count=len(counts) if counts else 0,
                concurrency_median=(float(statistics.median(counts)) if counts else None),
                concurrency_max=(max(counts) if counts else None),
                progression_speed_mps_median=(
                    progression.speed_mps_median if progression else None
                ),
                progression_segment_count=(progression.segment_count if progression else None),
            )
        )
    return MaterialisationSnapshot(
        logical_id=item.logical_id,
        session_kind=aggregate.session_kind,
        concurrency_source=aggregate.concurrency_source,
        session_date_local=aggregate.session_date_local,
        day_type=aggregate.day_type,
        hourly=tuple(hourly),
        progression_available=aggregate.progression_available,
        progression_note=aggregate.progression_unavailable_reason,
    )


def build_quality_report(
    monitor: IncrementalAnalyticsMonitor,
    loaded: tuple[LoadedAggregate, ...],
    rules: BuildRules,
) -> DataQualityReport:
    """Separate accepted, warned, refused, and not-observed — never zeroes."""

    accepted: list[str] = []
    warned: list[QualityObservation] = []
    refused: list[QualityObservation] = []
    not_observed: list[str] = []
    for item in loaded:
        aggregate = item.aggregate
        snapshot = monitor.materialisation(item.logical_id)
        if snapshot is None:
            not_observed.append(
                f"{item.logical_id}: not processed yet — absence of a materialisation is not a zero"
            )
            continue
        accepted.append(item.logical_id)
        if aggregate.snapshot_count < rules.min_snapshots_per_session:
            warned.append(
                QualityObservation(
                    rule="incomplete_session_window",
                    scope=item.logical_id,
                    measured=(
                        f"{aggregate.snapshot_count} snapshots < declared "
                        f"{rules.min_snapshots_per_session}"
                    ),
                    severity="warning",
                    source_sha256=item.sha256,
                )
            )
        if not aggregate.progression_available:
            warned.append(
                QualityObservation(
                    rule="progression_unavailable",
                    scope=item.logical_id,
                    measured=str(aggregate.progression_unavailable_reason),
                    severity="warning",
                    source_sha256=item.sha256,
                )
            )
    return DataQualityReport(
        accepted=tuple(accepted),
        warned=tuple(warned),
        refused=tuple(refused),
        not_observed=tuple(not_observed),
        standing_note=(
            "operational severity only, never scientific confidence; a data-quality "
            "pass does not admit a source, and forecast-readiness is not forecast "
            "validity"
        ),
    )


def _as_utc(value: datetime, *, field: str) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise AnalyticsMonitorError(
            "LOCAL_TIME_METADATA_MISSING",
            f"{field} must be an explicit timezone-aware UTC timestamp",
        )
    return value.astimezone(UTC)


def next_scheduled_run(
    after_utc: datetime,
    policy: AnalyticsOperationalPolicy,
) -> ScheduledReadinessCell:
    """Return the next strict 15-minute UTC cell, rendered in local service time."""

    current = _as_utc(after_utc, field="after_utc")
    cadence_seconds = policy.cadence_minutes * 60
    current_seconds = int(current.timestamp())
    next_seconds = ((current_seconds // cadence_seconds) + 1) * cadence_seconds
    scheduled = datetime.fromtimestamp(next_seconds, tz=UTC)
    local = scheduled.astimezone(_LOCAL_SERVICE_ZONE)
    return ScheduledReadinessCell(
        scheduled_at_utc=scheduled,
        service_date_local=local.date().isoformat(),
        hour_local=local.hour,
        minute_local=local.minute,
        utc_offset_seconds=int((local.utcoffset() or timedelta()).total_seconds()),
        fold=1 if local.fold else 0,
    )


def scheduled_readiness_cells(
    start_utc: datetime,
    end_utc: datetime,
    policy: AnalyticsOperationalPolicy,
) -> tuple[ScheduledReadinessCell, ...]:
    """Enumerate strict UTC schedule cells without inventing or dropping DST hours."""

    start = _as_utc(start_utc, field="start_utc")
    end = _as_utc(end_utc, field="end_utc")
    if end <= start:
        raise AnalyticsMonitorError(
            "CHECKPOINT_CONFLICT", "schedule end must be later than schedule start"
        )
    cells: list[ScheduledReadinessCell] = []
    cursor = start
    while True:
        cell = next_scheduled_run(cursor, policy)
        if cell.scheduled_at_utc > end:
            break
        cells.append(cell)
        cursor = cell.scheduled_at_utc
    return tuple(cells)


def _quality_observation(
    *,
    rule: str,
    context: SourceQualityContext,
    measured: str,
    severity: Severity,
    support: int | None = None,
) -> QualityObservation:
    return QualityObservation(
        rule=rule,
        rule_version="2.0",
        scope=context.logical_id,
        measured=measured,
        severity=severity,
        source_sha256=context.source_sha256,
        support=support,
        first_occurrence_utc=context.first_snapshot_at_utc,
        last_occurrence_utc=context.last_snapshot_at_utc,
    )


def build_operational_quality_report(
    monitor: IncrementalAnalyticsMonitor,
    loaded: tuple[LoadedAggregate, ...],
    contexts: tuple[SourceQualityContext, ...],
    rules: BuildRules,
    *,
    as_of_utc: datetime,
    policy: AnalyticsOperationalPolicy | None = None,
) -> DataQualityReport:
    """Apply the owner-selected operational policy to safe aggregate metadata."""

    selected = policy or AnalyticsOperationalPolicy()
    as_of = _as_utc(as_of_utc, field="as_of_utc")
    base = build_quality_report(monitor, loaded, rules)
    context_by_id: dict[str, SourceQualityContext] = {}
    for quality_context in contexts:
        if quality_context.logical_id in context_by_id:
            raise AnalyticsMonitorError(
                "DUPLICATE_LOGICAL_SOURCE",
                f"quality context '{quality_context.logical_id}' appears more than once",
            )
        context_by_id[quality_context.logical_id] = quality_context

    warned = list(base.warned)
    refused = list(base.refused)
    informational = list(base.informational)
    not_observed = list(base.not_observed)
    refused_ids: set[str] = set()
    loaded_by_id = {item.logical_id: item for item in loaded}

    for item in loaded:
        item_context = context_by_id.get(item.logical_id)
        if item_context is None:
            not_observed.append(
                f"{item.logical_id}: scheduling metadata unavailable — freshness, gaps, "
                "overlap and exclusion share were not inferred"
            )
            continue
        if item_context.source_sha256 != item.sha256:
            refused.append(
                _quality_observation(
                    rule="digest_mismatch",
                    context=item_context,
                    measured="quality context digest does not match the aggregate",
                    severity="refusal",
                )
            )
            refused_ids.add(item.logical_id)
        if (
            item.aggregate.schema_version not in selected.supported_schema_versions
            or item_context.source_schema_version != item.aggregate.schema_version
        ):
            refused.append(
                _quality_observation(
                    rule="unexpected_schema_version",
                    context=item_context,
                    measured=(
                        f"aggregate={item.aggregate.schema_version}; "
                        f"context={item_context.source_schema_version}; "
                        f"supported={','.join(selected.supported_schema_versions)}"
                    ),
                    severity="refusal",
                )
            )
            refused_ids.add(item.logical_id)
        else:
            informational.append(
                _quality_observation(
                    rule="schema_version_observed",
                    context=item_context,
                    measured=item.aggregate.schema_version,
                    severity="info",
                    support=item.aggregate.snapshot_count,
                )
            )

        age_minutes = (as_of - item_context.last_snapshot_at_utc).total_seconds() / 60.0
        if age_minutes < 0:
            refused.append(
                _quality_observation(
                    rule="future_snapshot_time",
                    context=item_context,
                    measured=f"last snapshot is {-age_minutes:.1f} minutes after report time",
                    severity="refusal",
                )
            )
            refused_ids.add(item.logical_id)
        elif age_minutes >= selected.freshness_refusal_minutes:
            refused.append(
                _quality_observation(
                    rule="source_stale",
                    context=item_context,
                    measured=f"{age_minutes:.1f} minutes old >= 60-minute refusal",
                    severity="refusal",
                )
            )
            refused_ids.add(item.logical_id)
        elif age_minutes >= selected.freshness_warning_minutes:
            warned.append(
                _quality_observation(
                    rule="source_stale",
                    context=item_context,
                    measured=f"{age_minutes:.1f} minutes old >= 30-minute warning",
                    severity="warning",
                )
            )

        completeness = min(
            1.0, item.aggregate.snapshot_count / item_context.expected_snapshot_count
        )
        missing_snapshots = max(
            0, item_context.expected_snapshot_count - item.aggregate.snapshot_count
        )
        if completeness < selected.completeness_refusal_ratio:
            severity: Severity = "refusal"
            refused_ids.add(item.logical_id)
        elif completeness < selected.completeness_warning_ratio:
            severity = "warning"
        else:
            severity = "info"
        observation = _quality_observation(
            rule="session_completeness",
            context=item_context,
            measured=(
                f"{completeness:.3f} ({item.aggregate.snapshot_count}/"
                f"{item_context.expected_snapshot_count}); missing={missing_snapshots}"
            ),
            severity=severity,
            support=item.aggregate.snapshot_count,
        )
        if severity == "refusal":
            refused.append(observation)
        elif severity == "warning":
            warned.append(observation)
        else:
            informational.append(observation)

        if item_context.progression_segments_total == 0:
            not_observed.append(
                f"{item.logical_id}: progression exclusion share unavailable — no segments"
            )
        else:
            exclusion_share = (
                item_context.progression_segments_excluded / item_context.progression_segments_total
            )
            if exclusion_share > selected.exclusion_refusal_ratio:
                severity = "refusal"
                refused_ids.add(item.logical_id)
            elif exclusion_share > selected.exclusion_warning_ratio:
                severity = "warning"
            else:
                severity = "info"
            exclusion = _quality_observation(
                rule="progression_exclusion_share",
                context=item_context,
                measured=(
                    f"{exclusion_share:.3f} "
                    f"({item_context.progression_segments_excluded}/"
                    f"{item_context.progression_segments_total})"
                ),
                severity=severity,
                support=item_context.progression_segments_total,
            )
            if severity == "refusal":
                refused.append(exclusion)
            elif severity == "warning":
                warned.append(exclusion)
            else:
                informational.append(exclusion)

    by_stream: dict[str, list[SourceQualityContext]] = {}
    for context in contexts:
        if context.logical_id in loaded_by_id:
            by_stream.setdefault(context.source_stream, []).append(context)
    for stream, stream_contexts in sorted(by_stream.items()):
        ordered = sorted(
            stream_contexts,
            key=lambda entry: (entry.first_snapshot_at_utc, entry.logical_id),
        )
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.first_snapshot_at_utc <= previous.last_snapshot_at_utc:
                refused.append(
                    _quality_observation(
                        rule="session_overlap",
                        context=current,
                        measured=(
                            f"stream '{stream}' overlaps '{previous.logical_id}' from "
                            f"{current.first_snapshot_at_utc.isoformat()} through "
                            f"{previous.last_snapshot_at_utc.isoformat()}"
                        ),
                        severity="refusal",
                    )
                )
                refused_ids.add(current.logical_id)
                refused_ids.add(previous.logical_id)

    accepted = tuple(logical_id for logical_id in base.accepted if logical_id not in refused_ids)
    return DataQualityReport(
        accepted=accepted,
        warned=tuple(warned),
        refused=tuple(refused),
        not_observed=tuple(dict.fromkeys(not_observed)),
        standing_note=base.standing_note,
        informational=tuple(informational),
        generated_at_utc=as_of,
        operational_policy_digest=selected.digest(),
        notification_surface=("local_dashboard", "local_report_receipt"),
        retention_policy="indefinite; no automatic deletion",
    )


class LocalQualityReportStore:
    """Atomic, immutable local publication surface; no deletion API exists."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def publish(
        self,
        report: DataQualityReport,
        policy: AnalyticsOperationalPolicy,
    ) -> LocalQualityReportReceipt:
        if report.operational_policy_digest != policy.digest():
            raise AnalyticsMonitorError(
                "CHECKPOINT_CONFLICT",
                "report is not bound to the selected operational policy",
            )
        digest = report.digest()
        report_name = f"{digest}.json"
        destination = self._directory / report_name
        payload = (
            json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        self._directory.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != payload:
                raise AnalyticsMonitorError(
                    "CHECKPOINT_CONFLICT",
                    "an existing local report does not match its content digest",
                )
            return LocalQualityReportReceipt(
                report_digest=digest,
                operational_policy_digest=policy.digest(),
                report_name=report_name,
                idempotent_replay=True,
            )
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{digest}.",
                suffix=".tmp",
                dir=self._directory,
                delete=False,
            ) as handle:
                temporary_name = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        return LocalQualityReportReceipt(
            report_digest=digest,
            operational_policy_digest=policy.digest(),
            report_name=report_name,
        )

    def reports(self) -> tuple[DataQualityReport, ...]:
        if not self._directory.exists():
            return ()
        reports: list[DataQualityReport] = []
        for path in sorted(self._directory.glob("[0-9a-f]" * 64 + ".json")):
            try:
                report = DataQualityReport.model_validate_json(path.read_bytes())
            except (OSError, ValidationError) as exc:
                raise AnalyticsMonitorError(
                    "CHECKPOINT_CONFLICT", "a local quality report is unreadable or invalid"
                ) from exc
            if report.digest() != path.stem:
                raise AnalyticsMonitorError(
                    "CHECKPOINT_CONFLICT", "a local quality report digest does not match its name"
                )
            reports.append(report)
        return tuple(reports)

    def retention_candidates(self) -> tuple[str, ...]:
        """The approved indefinite policy never nominates automatic deletions."""

        return ()


def read_readiness(loaded: tuple[LoadedAggregate, ...], rules: BuildRules) -> dict[str, object]:
    """Forecast-readiness cells via the predictor's own honest report."""

    report = readiness_report(loaded, rules)
    report["standing_note"] = "forecast-readiness is not forecast validity"
    return report
