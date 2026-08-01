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
import statistics
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    materialisation_digest: str
    analytics_version: Literal["incremental-analytics-1.0"] = ANALYTICS_VERSION
    evidence: Literal[False] = False
    idempotent_replay: bool = False


class QualityObservation(MonitorModel):
    rule: str
    rule_version: Literal["1.0"] = "1.0"
    scope: str
    measured: str
    severity: Severity
    source_sha256: str


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
        for line in raw.splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            kind = entry.pop("_kind")
            if kind == "reserve":
                self._reserved.add(entry["work_key"])
            elif kind == "commit":
                receipt = IncrementalAnalyticsReceipt.model_validate_json(json.dumps(entry))
                self._committed[receipt.work_key] = receipt
                self._reserved.discard(receipt.work_key)

    def _append(self, kind: str, payload: dict[str, object]) -> None:
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with self._checkpoint_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"_kind": kind, **payload}, sort_keys=True) + "\n")

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
        self._reserved.add(work.work_key)
        self._append("reserve", {"work_key": work.work_key})
        snapshot = materialise(item)
        receipt = IncrementalAnalyticsReceipt(
            work_key=work.work_key,
            logical_id=work.logical_id,
            materialisation_digest=snapshot.digest(),
        )
        self._materialisations[work.logical_id] = snapshot
        self._logical_digests[work.logical_id] = work.source_sha256
        self._committed[work.work_key] = receipt
        self._reserved.discard(work.work_key)
        self._append("commit", receipt.model_dump(mode="json"))
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


def read_readiness(loaded: tuple[LoadedAggregate, ...], rules: BuildRules) -> dict[str, object]:
    """Forecast-readiness cells via the predictor's own honest report."""

    report = readiness_report(loaded, rules)
    report["standing_note"] = "forecast-readiness is not forecast validity"
    return report
