"""Policy-gated, identifier-free operational history beyond the hot controls.

This module implements the NEXT-03 contracts without activating collection in
an owner workspace. Journal and immutable day writes require an exact approved
policy fingerprint plus a caller-supplied authority validator. Read-only
integrity and deterministic compaction need neither and never open raw source
quarantine.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.platform.historical_store import (
    AdmissionStatus,
    AuthoritativeSourceRecord,
    CatalogueNamespace,
    CitationEntry,
    ContentScope,
    DatasetRegistrationCandidate,
    DatasetSchemaContract,
    EvidenceRole,
    EvidenceStanding,
    HistoricalDatasetRecord,
    PayloadClass,
    SchemaLiteral,
    SourceBinding,
    SourceKind,
    SupportCount,
)
from traffictwin.release.compatibility import V07CompatibilityError, inspect_v07_workspace
from traffictwin.release.durable_workspace import (
    V07DurableWorkspaceError,
    load_durable_workspace_receipt,
)

OPERATIONAL_HISTORY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
OPERATIONAL_HISTORY_METHOD_VERSION: Literal["manchester-operational-history-1.0"] = (
    "manchester-operational-history-1.0"
)
OPERATIONAL_HISTORY_RELATIVE_DIRECTORY = Path("manchester/operational_history")
OPERATIONAL_JOURNAL_RELATIVE_PATH = OPERATIONAL_HISTORY_RELATIVE_DIRECTORY / "journal-v1.jsonl"
OPERATIONAL_JOURNAL_LOCK_RELATIVE_PATH = OPERATIONAL_HISTORY_RELATIVE_DIRECTORY / ".journal-v1.lock"
OPERATIONAL_DAY_DIRECTORY = OPERATIONAL_HISTORY_RELATIVE_DIRECTORY / "days"
OPERATIONAL_JOURNAL_MAX_BYTES = 128 * 1024 * 1024
OPERATIONAL_JOURNAL_MAX_RECORDS = 200_000
OPERATIONAL_JOURNAL_MAX_LINE_BYTES = 64 * 1024
OPERATIONAL_DAY_MAX_BYTES = 2 * 1024 * 1024
GENESIS_CHAIN_SHA256 = "0" * 64
LONDON_TIMEZONE = ZoneInfo("Europe/London")

OperationalSource = Literal["bods", "national_highways"]
OperationalTrigger = Literal["automatic", "operator"]
OperationalTerminalStatus = Literal["succeeded", "failed"]
PolicyAuthorityValidator = Callable[["ManchesterAggregateRetentionPolicy"], bool]
FaultHook = Callable[[str], None]

_ALLOWLISTED_FAILURE_CODES = frozenset(
    {
        "AUTO_REFRESH_CONFIG_CONFLICT",
        "AUTO_REFRESH_INTERVAL_INVALID",
        "BODS_AUTO_REFRESH_CONFIG_CONFLICT",
        "BODS_AUTO_REFRESH_FAILED",
        "BODS_AUTO_REFRESH_INTERVAL_INVALID",
        "BODS_AUTO_REFRESH_SCOPE_INVALID",
        "CLOCK_REGRESSION",
        "CONTROL_LOCK_FAILED",
        "CONTROL_PATH_UNSAFE",
        "CONTROL_STATE_INVALID",
        "CONTROL_STATE_NON_CANONICAL",
        "HTTP_STATUS_REFUSED",
        "NATIONAL_HIGHWAYS_AUTO_REFRESH_FAILED",
        "NATIONAL_HIGHWAYS_REFRESH_FAILED",
        "REFRESH_BUSY",
        "REFRESH_IN_PROGRESS",
        "REFRESH_TOO_SOON",
        "REQUEST_FAILED",
        "SCENE_INVALID",
        "SNAPSHOT_REJECTED",
        "UNCLASSIFIED_SAFE_FAILURE",
        "WORKSPACE_INVALID",
    }
)


class ManchesterOperationalHistoryError(RuntimeError):
    """Typed path-free journal, compaction, or authority refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class OperationalHistoryModel(BaseModel):
    """Strict immutable base for identifier-free operational-history artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _sha256_bytes(self.canonical_json().encode("utf-8"))


class ManchesterAggregateRetentionPolicy(OperationalHistoryModel):
    """Owner decision boundary required before any long-term local mutation."""

    schema_version: Literal["1.0"] = OPERATIONAL_HISTORY_SCHEMA_VERSION
    method_version: Literal["manchester-operational-history-1.0"] = (
        OPERATIONAL_HISTORY_METHOD_VERSION
    )
    policy_version: Literal["manchester-aggregate-retention-v1"] = (
        "manchester-aggregate-retention-v1"
    )
    decision_status: Literal["proposed", "owner_approved"] = "proposed"
    owner_decision_id: str | None = Field(default=None, pattern=r"^decision-[0-9a-f]{16}$")
    decided_at_utc: datetime | None = None
    private_retention_days: int = Field(default=30, ge=1, le=3660)
    backup_cadence_hours: int = Field(default=24, ge=1, le=168)
    disk_ceiling_bytes: int = Field(default=536_870_912, ge=8_388_608)
    compaction_delay_hours: int = Field(default=24, ge=1, le=168)
    public_output_class: Literal["private_only", "aggregated_anonymised"] = "private_only"
    deletion_authority: Literal["owner_only"] = "owner_only"
    raw_snapshot_policy_changed: Literal[False] = False
    automatic_deletion_enabled: Literal[False] = False

    @field_validator("decided_at_utc")
    @classmethod
    def validate_decision_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and not _is_utc(value):
            raise ValueError("retention decision time must be UTC")
        return value

    @model_validator(mode="after")
    def validate_authority_state(self) -> ManchesterAggregateRetentionPolicy:
        approved = self.decision_status == "owner_approved"
        if approved != (self.owner_decision_id is not None and self.decided_at_utc is not None):
            raise ValueError("approved policy requires an opaque owner decision and UTC time")
        return self


class ManchesterOperationalAttemptRecord(OperationalHistoryModel):
    """One hash-chained, identifier-free terminal source attempt."""

    record_type: Literal["manchester_operational_attempt"] = "manchester_operational_attempt"
    schema_version: Literal["1.0"] = OPERATIONAL_HISTORY_SCHEMA_VERSION
    method_version: Literal["manchester-operational-history-1.0"] = (
        OPERATIONAL_HISTORY_METHOD_VERSION
    )
    source: OperationalSource
    source_contract_version: str = Field(min_length=1, max_length=96)
    trigger: OperationalTrigger
    attempted_at_utc: datetime
    terminal_at_utc: datetime
    terminal_status: OperationalTerminalStatus
    failure_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,96}$")
    request_scope_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    accepted_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    source_clock_skew_count: Literal[0, 1]
    source_time_start_utc: datetime | None = None
    source_time_end_utc: datetime | None = None
    terminal_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    prior_chain_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    aggregates_only: Literal[True] = True
    raw_identifiers_persisted: Literal[False] = False
    vehicle_or_journey_identity_present: Literal[False] = False
    credential_value_persisted: Literal[False] = False
    private_path_persisted: Literal[False] = False
    public_export_available: Literal[False] = False

    @field_validator(
        "attempted_at_utc", "terminal_at_utc", "source_time_start_utc", "source_time_end_utc"
    )
    @classmethod
    def validate_utc_times(cls, value: datetime | None) -> datetime | None:
        if value is not None and not _is_utc(value):
            raise ValueError("operational-history timestamps must be UTC")
        return value

    @model_validator(mode="after")
    def validate_attempt(self) -> ManchesterOperationalAttemptRecord:
        if self.terminal_at_utc < self.attempted_at_utc:
            raise ValueError("terminal time precedes attempted time")
        if (self.terminal_status == "failed") != (self.failure_code is not None):
            raise ValueError("failure code exists exactly for failed attempts")
        if self.failure_code is not None and self.failure_code not in _ALLOWLISTED_FAILURE_CODES:
            raise ValueError("failure code is not allowlisted")
        if self.stale_count > self.accepted_count:
            raise ValueError("stale count cannot exceed accepted count")
        if (self.source_time_start_utc is None) != (self.source_time_end_utc is None):
            raise ValueError("source time range must be complete or absent")
        if (
            self.source_time_start_utc is not None
            and self.source_time_end_utc is not None
            and self.source_time_end_utc < self.source_time_start_utc
        ):
            raise ValueError("source time range is reversed")
        expected_skew = int(
            self.source_time_end_utc is not None and self.source_time_end_utc > self.terminal_at_utc
        )
        if self.source_clock_skew_count != expected_skew:
            raise ValueError("clock-skew count must reflect the source time range")
        if self.source == "bods" and not self.request_scope_fingerprint:
            raise ValueError("BODS attempts require an explicit request-scope fingerprint")
        return self


class ManchesterOperationalJournalReport(OperationalHistoryModel):
    """Path-free integrity result for the complete append-only chain."""

    schema_version: Literal["1.0"] = OPERATIONAL_HISTORY_SCHEMA_VERSION
    method_version: Literal["manchester-operational-history-1.0"] = (
        OPERATIONAL_HISTORY_METHOD_VERSION
    )
    journal_present: bool
    record_count: int = Field(ge=0, le=OPERATIONAL_JOURNAL_MAX_RECORDS)
    journal_size_bytes: int = Field(ge=0, le=OPERATIONAL_JOURNAL_MAX_BYTES)
    journal_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tail_chain_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_attempted_at_utc: datetime | None = None
    last_terminal_at_utc: datetime | None = None
    bods_records: int = Field(ge=0)
    national_highways_records: int = Field(ge=0)
    duplicate_terminal_receipts: Literal[0] = 0
    canonical_chain_verified: Literal[True] = True
    aggregates_only: Literal[True] = True
    network_request_performed: Literal[False] = False
    workspace_mutated: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> ManchesterOperationalJournalReport:
        if self.record_count != self.bods_records + self.national_highways_records:
            raise ValueError("source record counts must reconcile")
        if self.journal_present != (self.record_count > 0):
            raise ValueError("journal presence must match record count")
        if self.record_count == 0:
            if self.journal_size_bytes or self.journal_file_sha256 != GENESIS_CHAIN_SHA256:
                raise ValueError("absent journal must use the empty digest state")
            if self.tail_chain_sha256 != GENESIS_CHAIN_SHA256:
                raise ValueError("empty chain must use the genesis digest")
        return self


@dataclass(frozen=True, slots=True)
class ManchesterOperationalJournal:
    """Private in-memory records plus their safe report."""

    records: tuple[ManchesterOperationalAttemptRecord, ...]
    report: ManchesterOperationalJournalReport


class ManchesterOperationalAppendReceipt(OperationalHistoryModel):
    """Safe result of one authority-gated exact journal append."""

    schema_version: Literal["1.0"] = OPERATIONAL_HISTORY_SCHEMA_VERSION
    method_version: Literal["manchester-operational-history-1.0"] = (
        OPERATIONAL_HISTORY_METHOD_VERSION
    )
    terminal_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    retention_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_report: ManchesterOperationalJournalReport
    idempotent_retry: bool
    append_completed: Literal[True] = True
    raw_snapshot_changed: Literal[False] = False
    public_export_performed: Literal[False] = False
    private_path_persisted: Literal[False] = False


class ManchesterOperationalCadenceExpectation(OperationalHistoryModel):
    """Explicit automatic-attempt denominator for one UTC day and source."""

    source: OperationalSource
    configuration_status: Literal["enabled", "disabled", "not_configured"]
    interval_seconds: int | None = Field(default=None, ge=60, le=540)
    expected_automatic_attempts: int = Field(ge=0, le=1440)
    denominator_authority: Literal["caller_declared_preview"] = "caller_declared_preview"

    @model_validator(mode="after")
    def validate_expectation(self) -> ManchesterOperationalCadenceExpectation:
        if self.configuration_status == "enabled":
            if self.interval_seconds is None or not self.expected_automatic_attempts:
                raise ValueError("enabled cadence requires interval and a positive denominator")
        elif self.interval_seconds is not None or self.expected_automatic_attempts:
            raise ValueError("inactive cadence must have a zero denominator and no interval")
        if (
            self.source == "bods"
            and self.interval_seconds is not None
            and not 60 <= self.interval_seconds <= 300
        ):
            raise ValueError("BODS cadence interval is outside its worker bounds")
        return self


class ManchesterOperationalSourceDayAggregate(OperationalHistoryModel):
    """One source's reconciled UTC-day totals and cadence denominator."""

    source: OperationalSource
    attempts: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    automatic_attempts: int = Field(ge=0)
    operator_attempts: int = Field(ge=0)
    expected_automatic_attempts: int = Field(ge=0)
    missing_cadence_attempts: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    source_clock_skew_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_totals(self) -> ManchesterOperationalSourceDayAggregate:
        if self.attempts != self.succeeded + self.failed:
            raise ValueError("day terminal totals do not reconcile")
        if self.attempts != self.automatic_attempts + self.operator_attempts:
            raise ValueError("day trigger totals do not reconcile")
        expected_missing = max(0, self.expected_automatic_attempts - self.automatic_attempts)
        if self.missing_cadence_attempts != expected_missing:
            raise ValueError("missing cadence does not reconcile its denominator")
        if self.stale_count > self.accepted_count:
            raise ValueError("stale total cannot exceed accepted total")
        return self


class ManchesterOperationalHourAggregate(OperationalHistoryModel):
    """One source's aggregate-only terminal attempts in one UTC hour."""

    source: OperationalSource
    hour_start_utc: datetime
    attempts: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    automatic_attempts: int = Field(ge=0)
    operator_attempts: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    source_clock_skew_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_hour(self) -> ManchesterOperationalHourAggregate:
        clock_parts = (
            self.hour_start_utc.minute,
            self.hour_start_utc.second,
            self.hour_start_utc.microsecond,
        )
        if not _is_utc(self.hour_start_utc) or any(clock_parts):
            raise ValueError("hour bucket must start on an exact UTC hour")
        if self.attempts != self.succeeded + self.failed:
            raise ValueError("hour terminal totals do not reconcile")
        if self.attempts != self.automatic_attempts + self.operator_attempts:
            raise ValueError("hour trigger totals do not reconcile")
        return self


class ManchesterOperationalDayAggregate(OperationalHistoryModel):
    """Immutable identifier-free aggregate partition for one complete UTC day."""

    record_type: Literal["manchester_operational_day_aggregate"] = (
        "manchester_operational_day_aggregate"
    )
    schema_version: Literal["1.0"] = OPERATIONAL_HISTORY_SCHEMA_VERSION
    method_version: Literal["manchester-operational-history-1.0"] = (
        OPERATIONAL_HISTORY_METHOD_VERSION
    )
    utc_date: date
    day_start_utc: datetime
    day_end_utc: datetime
    partition_time_basis: Literal["UTC"] = "UTC"
    expectations: tuple[ManchesterOperationalCadenceExpectation, ...]
    source_aggregates: tuple[ManchesterOperationalSourceDayAggregate, ...]
    utc_hours: tuple[ManchesterOperationalHourAggregate, ...]
    journal_record_count: int = Field(ge=0)
    journal_record_fingerprints: tuple[str, ...]
    journal_first_prior_chain_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_tail_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    aggregates_only: Literal[True] = True
    raw_identifiers_present: Literal[False] = False
    vehicle_or_journey_identity_present: Literal[False] = False
    public_export_available: Literal[False] = False
    retention_activation_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_day(self) -> ManchesterOperationalDayAggregate:
        expected_start, expected_end = _utc_day_bounds(self.utc_date)
        if self.day_start_utc != expected_start or self.day_end_utc != expected_end:
            raise ValueError("day bounds must be the exact UTC partition")
        expected_sources = ("bods", "national_highways")
        if tuple(item.source for item in self.expectations) != expected_sources:
            raise ValueError("cadence expectations must contain both sources in order")
        if tuple(item.source for item in self.source_aggregates) != expected_sources:
            raise ValueError("day aggregates must contain both sources in order")
        if len(self.utc_hours) != 48:
            raise ValueError("day partition must contain 24 UTC hours for both sources")
        expected_hour_keys = tuple(
            (source, expected_start + timedelta(hours=hour))
            for hour in range(24)
            for source in expected_sources
        )
        observed_hour_keys = tuple((item.source, item.hour_start_utc) for item in self.utc_hours)
        if observed_hour_keys != expected_hour_keys:
            raise ValueError("UTC hour buckets are incomplete or out of order")
        if self.journal_record_count != len(self.journal_record_fingerprints):
            raise ValueError("journal record count does not match bound fingerprints")
        if len(set(self.journal_record_fingerprints)) != len(self.journal_record_fingerprints):
            raise ValueError("day record fingerprints must be unique")
        for aggregate in self.source_aggregates:
            hours = tuple(item for item in self.utc_hours if item.source == aggregate.source)
            for field in (
                "attempts",
                "succeeded",
                "failed",
                "automatic_attempts",
                "operator_attempts",
                "accepted_count",
                "excluded_count",
                "stale_count",
                "source_clock_skew_count",
            ):
                if getattr(aggregate, field) != sum(getattr(item, field) for item in hours):
                    raise ValueError(f"source day total does not match UTC hours: {field}")
        return self


class ManchesterLondonHourAggregate(OperationalHistoryModel):
    """Display-time London projection retaining UTC offset and fold."""

    source: OperationalSource
    hour_start_utc: datetime
    london_local_date: date
    london_hour: int = Field(ge=0, le=23)
    utc_offset_minutes: int = Field(ge=-720, le=840)
    fold: Literal[0, 1]
    attempts: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)


class ManchesterOperationalDayPublicationReceipt(OperationalHistoryModel):
    """Policy-bound proof of immutable private UTC-day publication."""

    schema_version: Literal["1.0"] = OPERATIONAL_HISTORY_SCHEMA_VERSION
    method_version: Literal["manchester-operational-history-1.0"] = (
        OPERATIONAL_HISTORY_METHOD_VERSION
    )
    utc_date: date
    day_aggregate_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retention_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    journal_tail_chain_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotent_retry: bool
    immutable_publication_completed: Literal[True] = True
    owner_only_permissions: Literal[True] = True
    public_export_performed: Literal[False] = False
    raw_snapshot_changed: Literal[False] = False


def proposed_aggregate_retention_policy() -> ManchesterAggregateRetentionPolicy:
    """Return the non-authoritative proposal; it cannot enable mutation."""

    return ManchesterAggregateRetentionPolicy()


def build_operational_attempt_record(
    *,
    source: OperationalSource,
    source_contract_version: str,
    trigger: OperationalTrigger,
    attempted_at_utc: datetime,
    terminal_at_utc: datetime,
    terminal_status: OperationalTerminalStatus,
    failure_code: str | None,
    request_scope_fingerprint: str,
    accepted_count: int,
    excluded_count: int,
    stale_count: int,
    source_time_start_utc: datetime | None,
    source_time_end_utc: datetime | None,
    terminal_receipt_fingerprint: str,
    prior_chain_sha256: str,
) -> ManchesterOperationalAttemptRecord:
    """Build one safe chain record and collapse unknown failures to an allowlisted code."""

    safe_failure = None
    if terminal_status == "failed":
        safe_failure = (
            failure_code
            if failure_code in _ALLOWLISTED_FAILURE_CODES
            else "UNCLASSIFIED_SAFE_FAILURE"
        )
    source_clock_skew_count: Literal[0, 1] = (
        1 if source_time_end_utc is not None and source_time_end_utc > terminal_at_utc else 0
    )
    return ManchesterOperationalAttemptRecord(
        source=source,
        source_contract_version=source_contract_version,
        trigger=trigger,
        attempted_at_utc=attempted_at_utc,
        terminal_at_utc=terminal_at_utc,
        terminal_status=terminal_status,
        failure_code=safe_failure,
        request_scope_fingerprint=request_scope_fingerprint,
        accepted_count=accepted_count,
        excluded_count=excluded_count,
        stale_count=stale_count,
        source_clock_skew_count=source_clock_skew_count,
        source_time_start_utc=source_time_start_utc,
        source_time_end_utc=source_time_end_utc,
        terminal_receipt_fingerprint=terminal_receipt_fingerprint,
        prior_chain_sha256=prior_chain_sha256,
    )


def load_operational_journal(path: str | Path) -> ManchesterOperationalJournal:
    """Read and verify the complete canonical chain without mutation or network access."""

    try:
        workspace = _validated_durable_workspace(path)
        return _load_operational_journal(workspace)
    except ManchesterOperationalHistoryError:
        raise
    except (OSError, V07CompatibilityError, V07DurableWorkspaceError) as exc:
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_JOURNAL_READ_FAILED", "operational journal could not be verified"
        ) from exc


def append_operational_attempt(
    path: str | Path,
    record: ManchesterOperationalAttemptRecord,
    *,
    policy: ManchesterAggregateRetentionPolicy,
    expected_policy_fingerprint: str,
    authority_validator: PolicyAuthorityValidator,
    fault_hook: FaultHook | None = None,
) -> ManchesterOperationalAppendReceipt:
    """Append exactly once after explicit policy confirmation and authority validation."""

    _require_policy_authority(policy, expected_policy_fingerprint, authority_validator)
    try:
        workspace = _validated_durable_workspace(path)
        return _append_operational_attempt(workspace, record, policy, fault_hook=fault_hook)
    except ManchesterOperationalHistoryError:
        raise
    except (OSError, V07CompatibilityError, V07DurableWorkspaceError) as exc:
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_JOURNAL_WRITE_FAILED", "operational journal append could not complete"
        ) from exc


def compact_operational_utc_day(
    records: Sequence[ManchesterOperationalAttemptRecord],
    utc_date: date,
    expectations: Sequence[ManchesterOperationalCadenceExpectation],
) -> ManchesterOperationalDayAggregate:
    """Pure deterministic compaction into 24 UTC hours and two source denominators."""

    _validate_record_sequence(records)
    ordered_expectations = tuple(expectations)
    if tuple(item.source for item in ordered_expectations) != ("bods", "national_highways"):
        raise ManchesterOperationalHistoryError(
            "CADENCE_EXPECTATIONS_INVALID", "both source expectations are required in order"
        )
    start, end = _utc_day_bounds(utc_date)
    selected = tuple(record for record in records if start <= record.terminal_at_utc < end)
    fingerprints = tuple(record.fingerprint() for record in selected)
    sources: tuple[OperationalSource, OperationalSource] = ("bods", "national_highways")
    hours = tuple(
        _hour_aggregate(
            selected,
            source=source,
            hour_start=start + timedelta(hours=hour),
        )
        for hour in range(24)
        for source in sources
    )
    source_aggregates = tuple(
        _source_day_aggregate(
            selected,
            source=source,
            expectation=ordered_expectations[index],
        )
        for index, source in enumerate(sources)
    )
    return ManchesterOperationalDayAggregate(
        utc_date=utc_date,
        day_start_utc=start,
        day_end_utc=end,
        expectations=ordered_expectations,
        source_aggregates=source_aggregates,
        utc_hours=hours,
        journal_record_count=len(selected),
        journal_record_fingerprints=fingerprints,
        journal_first_prior_chain_sha256=(
            GENESIS_CHAIN_SHA256 if not selected else selected[0].prior_chain_sha256
        ),
        journal_tail_record_sha256=(
            GENESIS_CHAIN_SHA256 if not selected else selected[-1].fingerprint()
        ),
    )


def preview_operational_utc_day(
    path: str | Path,
    utc_date: date,
    expectations: Sequence[ManchesterOperationalCadenceExpectation],
) -> ManchesterOperationalDayAggregate:
    """Read the journal and compact one day without publishing a partition."""

    journal = load_operational_journal(path)
    return compact_operational_utc_day(journal.records, utc_date, expectations)


def project_operational_day_to_london(
    day: ManchesterOperationalDayAggregate,
) -> tuple[ManchesterLondonHourAggregate, ...]:
    """Project UTC buckets at display time while retaining DST offset and fold."""

    projected = []
    for item in day.utc_hours:
        local = item.hour_start_utc.astimezone(LONDON_TIMEZONE)
        offset = local.utcoffset()
        if offset is None:
            raise ManchesterOperationalHistoryError(
                "LONDON_TIME_PROJECTION_FAILED", "London UTC offset is unavailable"
            )
        projected.append(
            ManchesterLondonHourAggregate(
                source=item.source,
                hour_start_utc=item.hour_start_utc,
                london_local_date=local.date(),
                london_hour=local.hour,
                utc_offset_minutes=int(offset.total_seconds() // 60),
                fold=1 if local.fold else 0,
                attempts=item.attempts,
                succeeded=item.succeeded,
                failed=item.failed,
                accepted_count=item.accepted_count,
                excluded_count=item.excluded_count,
                stale_count=item.stale_count,
            )
        )
    return tuple(projected)


def publish_operational_utc_day(
    path: str | Path,
    day: ManchesterOperationalDayAggregate,
    *,
    policy: ManchesterAggregateRetentionPolicy,
    expected_policy_fingerprint: str,
    authority_validator: PolicyAuthorityValidator,
    clock: Callable[[], datetime] | None = None,
) -> ManchesterOperationalDayPublicationReceipt:
    """Publish one complete private partition new-only after policy and journal reconciliation."""

    _require_policy_authority(policy, expected_policy_fingerprint, authority_validator)
    now = (clock or (lambda: datetime.now(UTC)))()
    if not _is_utc(now):
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_HISTORY_CLOCK_INVALID", "partition publication requires a UTC clock"
        )
    available_at = day.day_end_utc + timedelta(hours=policy.compaction_delay_hours)
    if now < available_at:
        raise ManchesterOperationalHistoryError(
            "COMPACTION_DELAY_ACTIVE", "the approved compaction delay has not elapsed"
        )
    try:
        workspace = _validated_durable_workspace(path)
        journal = _load_operational_journal(workspace)
        rebuilt = compact_operational_utc_day(journal.records, day.utc_date, day.expectations)
        if rebuilt != day:
            raise ManchesterOperationalHistoryError(
                "DAY_RECONCILIATION_FAILED", "day aggregate does not match the current journal"
            )
        target = workspace / OPERATIONAL_DAY_DIRECTORY / f"{day.utc_date.isoformat()}.json"
        payload = day.canonical_json().encode("utf-8")
        if len(payload) > OPERATIONAL_DAY_MAX_BYTES:
            raise ManchesterOperationalHistoryError(
                "DAY_PARTITION_TOO_LARGE", "day aggregate exceeds its private size limit"
            )
        retry = _publish_immutable_file(workspace, target, payload)
        return ManchesterOperationalDayPublicationReceipt(
            utc_date=day.utc_date,
            day_aggregate_fingerprint=day.fingerprint(),
            partition_sha256=_sha256_bytes(payload),
            retention_policy_fingerprint=policy.fingerprint(),
            journal_tail_chain_sha256=journal.report.tail_chain_sha256,
            idempotent_retry=retry,
        )
    except ManchesterOperationalHistoryError:
        raise
    except (OSError, V07CompatibilityError, V07DurableWorkspaceError) as exc:
        raise ManchesterOperationalHistoryError(
            "DAY_PUBLICATION_FAILED", "immutable day publication could not complete"
        ) from exc


def operational_day_store_schema() -> DatasetSchemaContract:
    """Return the one closed SAFE_ANALYSIS_SUMMARY schema admitted by this adapter."""

    keys = tuple(ManchesterOperationalDayAggregate.model_fields)
    return DatasetSchemaContract(
        schema_name="manchester.operational.day",
        schema_version=1,
        payload_class=PayloadClass.SAFE_ANALYSIS_SUMMARY,
        required_top_level_keys=keys,
        allowed_top_level_keys=keys,
        required_literals=(
            SchemaLiteral(field="record_type", value="manchester_operational_day_aggregate"),
            SchemaLiteral(field="schema_version", value="1.0"),
            SchemaLiteral(field="aggregates_only", value=True),
            SchemaLiteral(field="raw_identifiers_present", value=False),
            SchemaLiteral(field="public_export_available", value=False),
        ),
    )


def build_operational_day_store_candidate(
    day: ManchesterOperationalDayAggregate,
    source: AuthoritativeSourceRecord,
    *,
    licence_class: str,
) -> DatasetRegistrationCandidate:
    """Build a closed historical-store candidate; arbitrary JSON cannot enter this path."""

    expected_standing = EvidenceStanding(
        evidence_role=EvidenceRole.DESCRIPTIVE,
        admission_status=AdmissionStatus.NOT_APPLICABLE,
        evidence=False,
    )
    if (
        source.schema_name != "manchester.operational.journal"
        or source.schema_version != 1
        or source.payload_class is not PayloadClass.SAFE_ANALYSIS_SUMMARY
        or source.standing != expected_standing
        or source.sparse64
        or source.metadata_only
        or source.payload_digest != day.journal_tail_record_sha256
    ):
        raise ManchesterOperationalHistoryError(
            "DAY_SOURCE_CONTRACT_MISMATCH",
            "authoritative journal source does not bind the closed day adapter",
        )
    schema = operational_day_store_schema()
    payload = day.canonical_json().encode("utf-8")
    payload_digest = _sha256_bytes(payload)
    attempts = sum(item.attempts for item in day.source_aggregates)
    missing = sum(item.missing_cadence_attempts for item in day.source_aggregates)
    record = HistoricalDatasetRecord(
        dataset_id=f"dataset:manchester-operational-day:{day.utc_date.isoformat()}",
        logical_source_id="logical:manchester-operational-day",
        payload_class=PayloadClass.SAFE_ANALYSIS_SUMMARY,
        schema_name=schema.schema_name,
        schema_version=schema.schema_version,
        schema_digest=schema.fingerprint(),
        payload_digest=payload_digest,
        payload_handle=f"sha256:{payload_digest}",
        source_bindings=(
            SourceBinding(
                source_kind=SourceKind.AUTHORITATIVE_RECORD,
                source_id=source.source_record_id,
                expected_record_digest=source.record_digest,
                expected_payload_digest=source.payload_digest,
            ),
        ),
        created_at_utc=day.day_end_utc,
        event_time_start_utc=day.day_start_utc,
        event_time_end_utc=day.day_end_utc,
        local_service_dates=(day.utc_date.isoformat(),),
        timezone="UTC",
        support=(
            SupportCount(name="journal_records", value=day.journal_record_count),
            SupportCount(name="attempts", value=attempts),
            SupportCount(name="missing_cadence_attempts", value=missing),
        ),
        exclusions=(
            "raw_source_rows",
            "vehicle_and_journey_identifiers",
            "credentials_and_private_paths",
            "public_export",
        ),
        standing=expected_standing,
        citation_bundle=(
            CitationEntry(
                key="source",
                value="TrafficTwin private identifier-free operational aggregate journal",
            ),
        ),
        licence_class=licence_class,
        namespace=CatalogueNamespace.GENERAL,
        content_scope=ContentScope.AGGREGATE_PAYLOAD,
    )
    return DatasetRegistrationCandidate(record=record, payload=payload)


def _validated_durable_workspace(path: str | Path) -> Path:
    workspace = Path(path).resolve(strict=True)
    inspection = inspect_v07_workspace(workspace)
    receipt = load_durable_workspace_receipt(workspace)
    if receipt.manifest_sha256 != inspection.manifest_sha256:
        raise ManchesterOperationalHistoryError(
            "DURABLE_WORKSPACE_MISMATCH", "durable workspace manifest changed"
        )
    return workspace


def _load_operational_journal(workspace: Path) -> ManchesterOperationalJournal:
    target = workspace / OPERATIONAL_JOURNAL_RELATIVE_PATH
    _validate_history_path(workspace, target, allow_absent=True)
    if not os.path.lexists(target):
        report = ManchesterOperationalJournalReport(
            journal_present=False,
            record_count=0,
            journal_size_bytes=0,
            journal_file_sha256=GENESIS_CHAIN_SHA256,
            tail_chain_sha256=GENESIS_CHAIN_SHA256,
            bods_records=0,
            national_highways_records=0,
        )
        return ManchesterOperationalJournal(records=(), report=report)
    if not _private_regular_file(target):
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_JOURNAL_UNSAFE", "journal is not a private regular file"
        )
    size = target.stat().st_size
    if not size or size > OPERATIONAL_JOURNAL_MAX_BYTES:
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_JOURNAL_SIZE_INVALID", "journal size is outside its bounds"
        )
    payload = target.read_bytes()
    if not payload.endswith(b"\n"):
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_JOURNAL_PARTIAL", "journal ends with a partial record"
        )
    lines = payload.splitlines(keepends=True)
    if len(lines) > OPERATIONAL_JOURNAL_MAX_RECORDS:
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_JOURNAL_RECORD_LIMIT", "journal record limit was exceeded"
        )
    records: list[ManchesterOperationalAttemptRecord] = []
    prior = GENESIS_CHAIN_SHA256
    receipts: set[str] = set()
    for line in lines:
        if len(line) > OPERATIONAL_JOURNAL_MAX_LINE_BYTES:
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_JOURNAL_LINE_TOO_LARGE", "journal record exceeds its size limit"
            )
        try:
            record = ManchesterOperationalAttemptRecord.model_validate_json(line[:-1])
        except ValueError as exc:
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_JOURNAL_RECORD_INVALID", "journal record failed strict validation"
            ) from exc
        if record.canonical_json().encode("utf-8") + b"\n" != line:
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_JOURNAL_NON_CANONICAL", "journal record is not canonical JSON"
            )
        if record.prior_chain_sha256 != prior:
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_JOURNAL_CHAIN_DIVERGED", "journal hash chain is divergent"
            )
        if record.terminal_receipt_fingerprint in receipts:
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_JOURNAL_DUPLICATE_RECEIPT",
                "journal contains a duplicate terminal receipt",
            )
        receipts.add(record.terminal_receipt_fingerprint)
        records.append(record)
        prior = record.fingerprint()
    first_attempted = min(item.attempted_at_utc for item in records)
    last_terminal = max(item.terminal_at_utc for item in records)
    report = ManchesterOperationalJournalReport(
        journal_present=True,
        record_count=len(records),
        journal_size_bytes=len(payload),
        journal_file_sha256=_sha256_bytes(payload),
        tail_chain_sha256=prior,
        first_attempted_at_utc=first_attempted,
        last_terminal_at_utc=last_terminal,
        bods_records=sum(item.source == "bods" for item in records),
        national_highways_records=sum(item.source == "national_highways" for item in records),
    )
    return ManchesterOperationalJournal(records=tuple(records), report=report)


def _append_operational_attempt(
    workspace: Path,
    record: ManchesterOperationalAttemptRecord,
    policy: ManchesterAggregateRetentionPolicy,
    *,
    fault_hook: FaultHook | None,
) -> ManchesterOperationalAppendReceipt:
    history = _prepare_history_directory(workspace)
    lock_path = workspace / OPERATIONAL_JOURNAL_LOCK_RELATIVE_PATH
    descriptor = _acquire_history_lock(lock_path)
    try:
        current = _load_operational_journal(workspace)
        for existing in current.records:
            if existing.terminal_receipt_fingerprint != record.terminal_receipt_fingerprint:
                continue
            if existing != record:
                raise ManchesterOperationalHistoryError(
                    "OPERATIONAL_RECEIPT_CONFLICT",
                    "terminal receipt already binds a different journal record",
                )
            return ManchesterOperationalAppendReceipt(
                terminal_receipt_fingerprint=record.terminal_receipt_fingerprint,
                attempt_record_fingerprint=record.fingerprint(),
                retention_policy_fingerprint=policy.fingerprint(),
                journal_report=current.report,
                idempotent_retry=True,
            )
        if record.prior_chain_sha256 != current.report.tail_chain_sha256:
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_APPEND_CHAIN_MISMATCH",
                "attempt record does not extend the current journal tail",
            )
        partition = (
            workspace
            / OPERATIONAL_DAY_DIRECTORY
            / (f"{record.terminal_at_utc.date().isoformat()}.json")
        )
        if os.path.lexists(partition):
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_DAY_ALREADY_COMPACTED",
                "a terminal attempt cannot be appended after immutable day publication",
            )
        target = workspace / OPERATIONAL_JOURNAL_RELATIVE_PATH
        previous = b"" if not target.exists() else target.read_bytes()
        payload = previous + record.canonical_json().encode("utf-8") + b"\n"
        if len(payload) > min(policy.disk_ceiling_bytes, OPERATIONAL_JOURNAL_MAX_BYTES):
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_JOURNAL_DISK_CEILING",
                "approved journal disk ceiling would be exceeded",
            )
        if fault_hook is not None:
            fault_hook("before_journal_publication")
        _atomic_replace_private(target, payload)
        _fsync_directory(history)
        verified = _load_operational_journal(workspace)
        if verified.report.tail_chain_sha256 != record.fingerprint():
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_APPEND_VERIFICATION_FAILED",
                "published journal tail did not reconcile",
            )
        return ManchesterOperationalAppendReceipt(
            terminal_receipt_fingerprint=record.terminal_receipt_fingerprint,
            attempt_record_fingerprint=record.fingerprint(),
            retention_policy_fingerprint=policy.fingerprint(),
            journal_report=verified.report,
            idempotent_retry=False,
        )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _validate_record_sequence(records: Sequence[ManchesterOperationalAttemptRecord]) -> None:
    receipts: set[str] = set()
    prior: ManchesterOperationalAttemptRecord | None = None
    for record in records:
        if record.terminal_receipt_fingerprint in receipts:
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_SEQUENCE_DUPLICATE_RECEIPT",
                "compaction input contains a duplicate terminal receipt",
            )
        if prior is not None and record.prior_chain_sha256 != prior.fingerprint():
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_SEQUENCE_REORDERED",
                "compaction input is not in verified journal-chain order",
            )
        receipts.add(record.terminal_receipt_fingerprint)
        prior = record


def _source_day_aggregate(
    records: Sequence[ManchesterOperationalAttemptRecord],
    *,
    source: OperationalSource,
    expectation: ManchesterOperationalCadenceExpectation,
) -> ManchesterOperationalSourceDayAggregate:
    selected = tuple(item for item in records if item.source == source)
    automatic = sum(item.trigger == "automatic" for item in selected)
    return ManchesterOperationalSourceDayAggregate(
        source=source,
        attempts=len(selected),
        succeeded=sum(item.terminal_status == "succeeded" for item in selected),
        failed=sum(item.terminal_status == "failed" for item in selected),
        automatic_attempts=automatic,
        operator_attempts=len(selected) - automatic,
        expected_automatic_attempts=expectation.expected_automatic_attempts,
        missing_cadence_attempts=max(0, expectation.expected_automatic_attempts - automatic),
        accepted_count=sum(item.accepted_count for item in selected),
        excluded_count=sum(item.excluded_count for item in selected),
        stale_count=sum(item.stale_count for item in selected),
        source_clock_skew_count=sum(item.source_clock_skew_count for item in selected),
    )


def _hour_aggregate(
    records: Sequence[ManchesterOperationalAttemptRecord],
    *,
    source: OperationalSource,
    hour_start: datetime,
) -> ManchesterOperationalHourAggregate:
    end = hour_start + timedelta(hours=1)
    selected = tuple(
        item
        for item in records
        if item.source == source and hour_start <= item.terminal_at_utc < end
    )
    automatic = sum(item.trigger == "automatic" for item in selected)
    return ManchesterOperationalHourAggregate(
        source=source,
        hour_start_utc=hour_start,
        attempts=len(selected),
        succeeded=sum(item.terminal_status == "succeeded" for item in selected),
        failed=sum(item.terminal_status == "failed" for item in selected),
        automatic_attempts=automatic,
        operator_attempts=len(selected) - automatic,
        accepted_count=sum(item.accepted_count for item in selected),
        excluded_count=sum(item.excluded_count for item in selected),
        stale_count=sum(item.stale_count for item in selected),
        source_clock_skew_count=sum(item.source_clock_skew_count for item in selected),
    )


def _require_policy_authority(
    policy: ManchesterAggregateRetentionPolicy,
    expected_fingerprint: str,
    validator: PolicyAuthorityValidator,
) -> None:
    if policy.fingerprint() != expected_fingerprint:
        raise ManchesterOperationalHistoryError(
            "RETENTION_POLICY_MISMATCH", "exact retention policy was not confirmed"
        )
    if policy.decision_status != "owner_approved":
        raise ManchesterOperationalHistoryError(
            "RETENTION_POLICY_UNAPPROVED", "owner-approved retention policy is required"
        )
    try:
        authorised = validator(policy)
    except Exception as exc:
        raise ManchesterOperationalHistoryError(
            "RETENTION_POLICY_AUTHORITY_INVALID", "retention authority validation failed"
        ) from exc
    if not authorised:
        raise ManchesterOperationalHistoryError(
            "RETENTION_POLICY_AUTHORITY_INVALID", "retention authority was not validated"
        )


def _prepare_history_directory(workspace: Path) -> Path:
    history = workspace / OPERATIONAL_HISTORY_RELATIVE_DIRECTORY
    cursor = workspace
    for part in OPERATIONAL_HISTORY_RELATIVE_DIRECTORY.parts:
        cursor /= part
        if cursor.is_symlink() or (cursor.exists() and not cursor.is_dir()):
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_HISTORY_PATH_UNSAFE", "history directory is unsafe"
            )
        cursor.mkdir(mode=0o700, exist_ok=True)
        cursor.chmod(0o700)
    return history


def _validate_history_path(workspace: Path, target: Path, *, allow_absent: bool) -> None:
    try:
        relative = target.relative_to(workspace)
    except ValueError as exc:
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_HISTORY_PATH_UNSAFE", "history path escaped the workspace"
        ) from exc
    cursor = workspace
    for part in relative.parts[:-1]:
        cursor /= part
        if cursor.is_symlink() or (cursor.exists() and not cursor.is_dir()):
            raise ManchesterOperationalHistoryError(
                "OPERATIONAL_HISTORY_PATH_UNSAFE", "history path parent is unsafe"
            )
        if not cursor.exists() and allow_absent:
            return
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_HISTORY_PATH_UNSAFE", "history target is unsafe"
        )


def _acquire_history_lock(path: Path) -> int:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_HISTORY_LOCK_UNSAFE", "journal lock path is unsafe"
        )
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.fchmod(descriptor, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise ManchesterOperationalHistoryError(
            "OPERATIONAL_HISTORY_BUSY", "another journal writer is active"
        ) from exc
    return descriptor


def _atomic_replace_private(target: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".journal-v1-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        target.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _publish_immutable_file(workspace: Path, target: Path, payload: bytes) -> bool:
    _validate_history_path(workspace, target, allow_absent=True)
    if os.path.lexists(target):
        if not _private_regular_file(target):
            raise ManchesterOperationalHistoryError(
                "DAY_PARTITION_UNSAFE", "existing day partition is unsafe"
            )
        if target.read_bytes() == payload:
            return True
        raise ManchesterOperationalHistoryError(
            "DAY_PARTITION_CONFLICT", "immutable day partition already differs"
        )
    parent = target.parent
    cursor = workspace
    for part in parent.relative_to(workspace).parts:
        cursor /= part
        if cursor.is_symlink() or (cursor.exists() and not cursor.is_dir()):
            raise ManchesterOperationalHistoryError(
                "DAY_PARTITION_UNSAFE", "day partition parent is unsafe"
            )
        cursor.mkdir(mode=0o700, exist_ok=True)
        cursor.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".day-v1-", dir=parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target, follow_symlinks=False)
        except FileExistsError:
            if _private_regular_file(target) and target.read_bytes() == payload:
                return True
            raise ManchesterOperationalHistoryError(
                "DAY_PARTITION_CONFLICT", "immutable day partition appeared with other content"
            ) from None
        target.chmod(0o600)
        _fsync_directory(parent)
        return False
    finally:
        temporary.unlink(missing_ok=True)


def _private_regular_file(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    details = path.stat()
    return details.st_uid == os.getuid() and stat.S_IMODE(details.st_mode) == 0o600


def _utc_day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _is_utc(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
