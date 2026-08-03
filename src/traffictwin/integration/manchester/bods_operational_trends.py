"""Identifier-free BODS operational attempts, windows, and UTC-day rollups."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from traffictwin.integration.manchester.bods import LiveTransitVehicleObservation
from traffictwin.integration.manchester.bods_live import BodsLiveRefresh
from traffictwin.integration.manchester.models import ManchesterSnapshotModel

BODS_OPERATIONAL_TREND_SCHEMA_VERSION: Literal["1.0"] = "1.0"
BODS_OPERATIONAL_TREND_METHOD_VERSION: Literal["bods-operational-trends-1.0"] = (
    "bods-operational-trends-1.0"
)
MAX_TREND_ATTEMPTS = 200_000

_SAFE_FAILURE_CODES = frozenset(
    {
        "BODS_AUTO_REFRESH_FAILED",
        "BODS_LIVE_REFRESH_FAILED",
        "CREDENTIAL_INVALID",
        "HTTP_STATUS_REFUSED",
        "REFRESH_TOO_SOON",
        "REQUEST_FAILED",
        "SNAPSHOT_REJECTED",
        "UNCLASSIFIED_SAFE_FAILURE",
    }
)


class BodsOperationalTrendError(RuntimeError):
    """Safe failure for a mismatched refresh or invalid trend sequence."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BodsSourceAgeDistribution(ManchesterSnapshotModel):
    denominator: int = Field(ge=0)
    minimum_age_ms: int | None = None
    median_age_ms: int | None = None
    p95_age_ms: int | None = None
    maximum_age_ms: int | None = None
    negative_age_count: int = Field(ge=0)
    earliest_source_time_utc: datetime | None = None
    latest_source_time_utc: datetime | None = None

    @model_validator(mode="after")
    def validate_distribution(self) -> BodsSourceAgeDistribution:
        values = (
            self.minimum_age_ms,
            self.median_age_ms,
            self.p95_age_ms,
            self.maximum_age_ms,
        )
        if self.denominator == 0:
            if any(value is not None for value in values) or any(
                value is not None
                for value in (self.earliest_source_time_utc, self.latest_source_time_utc)
            ):
                raise ValueError("empty age distribution cannot contain values")
        elif any(value is None for value in values) or self.earliest_source_time_utc is None:
            raise ValueError("non-empty age distribution must be complete")
        if self.negative_age_count > self.denominator:
            raise ValueError("clock-skew count cannot exceed its denominator")
        return self


class BodsOperationalAttemptAggregate(ManchesterSnapshotModel):
    schema_version: Literal["1.0"] = BODS_OPERATIONAL_TREND_SCHEMA_VERSION
    method_version: Literal["bods-operational-trends-1.0"] = BODS_OPERATIONAL_TREND_METHOD_VERSION
    attempted_at_utc: datetime
    terminal_at_utc: datetime
    trigger: Literal["automatic", "operator"]
    terminal_status: Literal["succeeded", "failed"]
    safe_failure_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,96}$")
    source_response_available: bool
    acquisition_contract_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_report_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    bee_policy_version: str | None = Field(default=None, max_length=96)
    bee_policy_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    activities_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    live_at_fetch: int = Field(ge=0)
    stale_at_fetch: int = Field(ge=0)
    synthetic_records: int = Field(ge=0)
    historical_records: int = Field(ge=0)
    outside_box: int = Field(ge=0)
    malformed_or_refused: int = Field(ge=0)
    exact_duplicates_collapsed: int = Field(ge=0)
    conflicting_duplicates: int = Field(ge=0)
    verified_bee_rows: int = Field(ge=0)
    other_or_unknown_rows: int = Field(ge=0)
    missing_membership_identifier: int = Field(ge=0)
    ambiguous_membership_identifier: int = Field(ge=0)
    distinct_operator_count: int = Field(ge=0)
    source_age: BodsSourceAgeDistribution
    previous_success_source_cadence_ms: int | None = None
    response_count_denominator_complete: Literal[True] = True
    membership_count_denominator_complete: Literal[True] = True
    identifiers_present: Literal[False] = False
    pseudonymised_identifiers_present: Literal[False] = False
    coordinates_present: Literal[False] = False
    road_speed_available: Literal[False] = False
    trajectory_available: Literal[False] = False
    complete_fleet_coverage_available: Literal[False] = False
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_attempt(self) -> BodsOperationalAttemptAggregate:
        if self.terminal_at_utc < self.attempted_at_utc:
            raise ValueError("terminal time precedes attempt time")
        failed = self.terminal_status == "failed"
        if (
            failed != (self.safe_failure_code is not None)
            or failed == self.source_response_available
        ):
            raise ValueError("failure and source-response states do not reconcile")
        if self.records_accepted != (
            self.live_at_fetch
            + self.stale_at_fetch
            + self.synthetic_records
            + self.historical_records
        ):
            raise ValueError("freshness counts must partition accepted rows")
        if self.records_accepted != self.verified_bee_rows + self.other_or_unknown_rows:
            raise ValueError("membership counts must partition accepted rows")
        if self.source_age.denominator != self.records_accepted:
            raise ValueError("source-age denominator must match accepted rows")
        if failed and any(
            (
                self.activities_seen,
                self.records_accepted,
                self.outside_box,
                self.malformed_or_refused,
                self.exact_duplicates_collapsed,
                self.conflicting_duplicates,
                self.distinct_operator_count,
            )
        ):
            raise ValueError("failed attempts cannot invent response counts")
        return self


class BodsOperationalTrendWindow(ManchesterSnapshotModel):
    window_start_utc: datetime
    window_end_utc: datetime
    expected_automatic_attempts: int = Field(ge=0)
    observed_attempts: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    automatic_attempts: int = Field(ge=0)
    operator_attempts: int = Field(ge=0)
    missing_automatic_attempts: int = Field(ge=0)
    accepted_rows: int = Field(ge=0)
    live_rows: int = Field(ge=0)
    stale_rows: int = Field(ge=0)
    verified_bee_rows: int = Field(ge=0)
    other_or_unknown_rows: int = Field(ge=0)
    source_clock_skew_rows: int = Field(ge=0)
    failure_counts: tuple[tuple[str, int], ...]
    trend_available: bool
    trend_unavailable_reason: Literal["single_or_no_success", "available"]
    denominator_authority: Literal["caller_declared"] = "caller_declared"
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_window(self) -> BodsOperationalTrendWindow:
        if self.window_start_utc >= self.window_end_utc:
            raise ValueError("trend window must increase")
        if self.observed_attempts != self.succeeded + self.failed:
            raise ValueError("terminal attempt counts must reconcile")
        if self.observed_attempts != self.automatic_attempts + self.operator_attempts:
            raise ValueError("trigger counts must reconcile")
        if self.missing_automatic_attempts != max(
            0, self.expected_automatic_attempts - self.automatic_attempts
        ):
            raise ValueError("missing cadence must use the declared denominator")
        if self.trend_available != (self.trend_unavailable_reason == "available"):
            raise ValueError("trend availability and reason differ")
        return self


class BodsOperationalDayRollup(ManchesterSnapshotModel):
    utc_date: date
    day_start_utc: datetime
    day_end_utc: datetime
    window: BodsOperationalTrendWindow
    attempt_fingerprints: tuple[str, ...]
    aggregates_only: Literal[True] = True
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_day(self) -> BodsOperationalDayRollup:
        start = datetime.combine(self.utc_date, time.min, tzinfo=UTC)
        if self.day_start_utc != start or self.day_end_utc != start + timedelta(days=1):
            raise ValueError("day rollup must use exact UTC bounds")
        if self.window.window_start_utc != self.day_start_utc:
            raise ValueError("day window start differs")
        if self.window.window_end_utc != self.day_end_utc:
            raise ValueError("day window end differs")
        return self


def successful_bods_operational_attempt(
    refresh: BodsLiveRefresh,
    *,
    attempted_at_utc: datetime,
    terminal_at_utc: datetime,
    trigger: Literal["automatic", "operator"],
    previous_success: BodsOperationalAttemptAggregate | None = None,
) -> BodsOperationalAttemptAggregate:
    """Discard row identities while deriving exact operational aggregates in memory."""

    report = refresh.report
    membership = refresh.membership
    summary = refresh.summary
    if (
        summary.parser_report_fingerprint != report.fingerprint()
        or membership.source_report_fingerprint != report.fingerprint()
        or summary.bee_network_membership_report_fingerprint != membership.fingerprint()
        or summary.records_accepted != len(report.records)
    ):
        raise BodsOperationalTrendError(
            "BODS_TREND_BINDING_MISMATCH", "live refresh components do not exactly bind"
        )
    ages = tuple(_age_ms(terminal_at_utc, item.recorded_at_utc) for item in report.records)
    operators = {item.operator_ref for item in report.records}
    latest_source = max((item.recorded_at_utc for item in report.records), default=None)
    previous_latest = (
        None if previous_success is None else previous_success.source_age.latest_source_time_utc
    )
    cadence = (
        None
        if latest_source is None or previous_latest is None
        else _duration_ms(latest_source - previous_latest)
    )
    counts = report.counts
    return BodsOperationalAttemptAggregate(
        attempted_at_utc=attempted_at_utc,
        terminal_at_utc=terminal_at_utc,
        trigger=trigger,
        terminal_status="succeeded",
        source_response_available=True,
        acquisition_contract_fingerprint=refresh.acquisition.fingerprint(),
        parser_report_fingerprint=report.fingerprint(),
        bee_policy_version=membership.policy.policy_version,
        bee_policy_fingerprint=membership.policy_fingerprint,
        activities_seen=counts.activities_seen,
        records_accepted=counts.records_accepted,
        live_at_fetch=counts.live_vehicle,
        stale_at_fetch=counts.stale,
        synthetic_records=counts.synthetic,
        historical_records=counts.historical,
        outside_box=counts.outside_bounds,
        malformed_or_refused=counts.malformed,
        exact_duplicates_collapsed=counts.duplicate_collapsed,
        conflicting_duplicates=counts.conflicting_duplicates,
        verified_bee_rows=membership.counts.bee_network_franchised,
        other_or_unknown_rows=membership.counts.non_franchised_or_unknown,
        missing_membership_identifier=membership.counts.missing_identifier,
        ambiguous_membership_identifier=membership.counts.ambiguous_identifier,
        distinct_operator_count=len(operators),
        source_age=_age_distribution(ages, report.records),
        previous_success_source_cadence_ms=cadence,
    )


def failed_bods_operational_attempt(
    *,
    attempted_at_utc: datetime,
    terminal_at_utc: datetime,
    trigger: Literal["automatic", "operator"],
    failure_code: str,
    acquisition_contract_fingerprint: str,
) -> BodsOperationalAttemptAggregate:
    """Create a zero-response failure using only an allowlisted safe code."""

    safe = failure_code if failure_code in _SAFE_FAILURE_CODES else "UNCLASSIFIED_SAFE_FAILURE"
    return BodsOperationalAttemptAggregate(
        attempted_at_utc=attempted_at_utc,
        terminal_at_utc=terminal_at_utc,
        trigger=trigger,
        terminal_status="failed",
        safe_failure_code=safe,
        source_response_available=False,
        acquisition_contract_fingerprint=acquisition_contract_fingerprint,
        activities_seen=0,
        records_accepted=0,
        live_at_fetch=0,
        stale_at_fetch=0,
        synthetic_records=0,
        historical_records=0,
        outside_box=0,
        malformed_or_refused=0,
        exact_duplicates_collapsed=0,
        conflicting_duplicates=0,
        verified_bee_rows=0,
        other_or_unknown_rows=0,
        missing_membership_identifier=0,
        ambiguous_membership_identifier=0,
        distinct_operator_count=0,
        source_age=BodsSourceAgeDistribution(denominator=0, negative_age_count=0),
    )


def build_bods_trend_window(
    attempts: Sequence[BodsOperationalAttemptAggregate],
    *,
    window_start_utc: datetime,
    window_end_utc: datetime,
    expected_automatic_attempts: int,
) -> BodsOperationalTrendWindow:
    """Aggregate one explicit UTC window without inventing a cadence denominator."""

    if len(attempts) > MAX_TREND_ATTEMPTS:
        raise BodsOperationalTrendError("BODS_TREND_LIMIT", "attempt sequence exceeds its bound")
    ordered = tuple(sorted(attempts, key=lambda item: (item.terminal_at_utc, item.fingerprint())))
    if len({item.fingerprint() for item in ordered}) != len(ordered):
        raise BodsOperationalTrendError(
            "BODS_TREND_DUPLICATE_ATTEMPT", "attempt sequence contains an exact duplicate"
        )
    selected = tuple(
        item for item in ordered if window_start_utc <= item.terminal_at_utc < window_end_utc
    )
    successes = tuple(item for item in selected if item.terminal_status == "succeeded")
    automatic = sum(item.trigger == "automatic" for item in selected)
    failures = Counter(
        item.safe_failure_code for item in selected if item.safe_failure_code is not None
    )
    trend_available = len(successes) >= 2
    return BodsOperationalTrendWindow(
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        expected_automatic_attempts=expected_automatic_attempts,
        observed_attempts=len(selected),
        succeeded=len(successes),
        failed=len(selected) - len(successes),
        automatic_attempts=automatic,
        operator_attempts=len(selected) - automatic,
        missing_automatic_attempts=max(0, expected_automatic_attempts - automatic),
        accepted_rows=sum(item.records_accepted for item in selected),
        live_rows=sum(item.live_at_fetch for item in selected),
        stale_rows=sum(item.stale_at_fetch for item in selected),
        verified_bee_rows=sum(item.verified_bee_rows for item in selected),
        other_or_unknown_rows=sum(item.other_or_unknown_rows for item in selected),
        source_clock_skew_rows=sum(item.source_age.negative_age_count for item in selected),
        failure_counts=tuple(sorted((code, count) for code, count in failures.items())),
        trend_available=trend_available,
        trend_unavailable_reason="available" if trend_available else "single_or_no_success",
    )


def build_bods_utc_day_rollup(
    attempts: Sequence[BodsOperationalAttemptAggregate],
    utc_date: date,
    *,
    expected_automatic_attempts: int,
) -> BodsOperationalDayRollup:
    """Build a stable identifier-free UTC-day rollup."""

    start = datetime.combine(utc_date, time.min, tzinfo=UTC)
    end = start + timedelta(days=1)
    selected = tuple(item for item in attempts if start <= item.terminal_at_utc < end)
    ordered = tuple(sorted(selected, key=lambda item: (item.terminal_at_utc, item.fingerprint())))
    return BodsOperationalDayRollup(
        utc_date=utc_date,
        day_start_utc=start,
        day_end_utc=end,
        window=build_bods_trend_window(
            ordered,
            window_start_utc=start,
            window_end_utc=end,
            expected_automatic_attempts=expected_automatic_attempts,
        ),
        attempt_fingerprints=tuple(item.fingerprint() for item in ordered),
    )


def _age_distribution(
    ages: Sequence[int], records: Sequence[LiveTransitVehicleObservation]
) -> BodsSourceAgeDistribution:
    if not ages:
        return BodsSourceAgeDistribution(denominator=0, negative_age_count=0)
    ordered = tuple(sorted(ages))
    source_times = tuple(item.recorded_at_utc for item in records)
    return BodsSourceAgeDistribution(
        denominator=len(ordered),
        minimum_age_ms=ordered[0],
        median_age_ms=_nearest_rank(ordered, Decimal("0.5")),
        p95_age_ms=_nearest_rank(ordered, Decimal("0.95")),
        maximum_age_ms=ordered[-1],
        negative_age_count=sum(value < 0 for value in ordered),
        earliest_source_time_utc=min(source_times),
        latest_source_time_utc=max(source_times),
    )


def _nearest_rank(values: Sequence[int], probability: Decimal) -> int:
    rank = int((Decimal(len(values)) * probability).to_integral_value(rounding="ROUND_CEILING"))
    return values[max(0, rank - 1)]


def _age_ms(terminal: datetime, source_time: datetime) -> int:
    return _duration_ms(terminal - source_time)


def _duration_ms(value: timedelta) -> int:
    return (value.days * 86_400_000) + (value.seconds * 1_000) + (value.microseconds // 1_000)
