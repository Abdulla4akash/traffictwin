"""Read-only, secret-free source-health projection for one durable v0.7 workspace."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.integration.manchester.bods_auto_refresh import (
    BodsAutoRefreshStatus,
    bods_auto_refresh_status,
)
from traffictwin.integration.manchester.bods_live import BodsLiveRefreshSummary
from traffictwin.integration.manchester.bods_live_control import (
    BodsLiveControlError,
    load_bods_live_control_state,
    project_bods_live_scene_for_display,
)
from traffictwin.integration.manchester.freshness import (
    NATIONAL_HIGHWAYS_NEAR_LIVE_AGE_SECONDS,
)
from traffictwin.integration.manchester.map_layers import ManchesterMapScene
from traffictwin.integration.manchester.national_highways_auto_refresh import (
    NationalHighwaysAutoRefreshStatus,
    national_highways_auto_refresh_status,
)
from traffictwin.integration.manchester.national_highways_live import (
    NationalHighwaysLiveError,
    NationalHighwaysRefreshSummary,
    load_national_highways_control_state,
)
from traffictwin.integration.manchester.operational_history import (
    ManchesterOperationalHistoryError,
    load_operational_journal,
)
from traffictwin.release.real_workspace_run import (
    V07RealWorkspaceRunError,
    V07SourceRunPreflight,
    preflight_real_v07_workspace_run,
)

SOURCE_HEALTH_SCHEMA_VERSION: Literal["1.0"] = "1.0"
SOURCE_HEALTH_METHOD_VERSION: Literal["source-health-1.0"] = "source-health-1.0"
SOURCE_HEALTH_SCENE_MAX_BYTES = 8 * 1024 * 1024


class SourceHealthError(RuntimeError):
    """Display-safe failure with no credential or private path."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class SourceHealthModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class SourceHealthRow(SourceHealthModel):
    source: Literal["BODS", "National Highways"]
    scope: str
    evidence_role: Literal["live_transit_positions", "near_live_operational_road_events"]
    time_basis: Literal["documented_source_utc"] = "documented_source_utc"
    freshness_policy: str
    capability_status: Literal["planned"] = "planned"
    configuration_status: Literal["configured", "disabled", "not_configured", "invalid"]
    credential_present: bool
    request_scope_status: Literal["valid", "missing", "not_applicable", "invalid"]
    worker_status: Literal[
        "disabled", "not_configured", "starting", "running", "degraded", "stopped"
    ]
    conservative_interval_seconds: int | None = Field(default=None, ge=60, le=540)
    provider_limit_status: Literal["provider_limit_unknown"] = "provider_limit_unknown"
    last_attempt_at_utc: datetime | None = None
    last_success_at_utc: datetime | None = None
    next_locally_eligible_at_utc: datetime | None = None
    last_source_time_utc: datetime | None = None
    truth_state: Literal["never", "live", "near_live", "stale", "unavailable", "failed", "invalid"]
    safe_failure_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,96}$")
    hot_history_entries: int = Field(ge=0, le=240)
    long_term_journal_records: int = Field(ge=0)
    long_term_integrity: Literal["absent_valid", "valid", "invalid"]
    retention_decision: Literal["owner_policy_required"] = "owner_policy_required"
    licence_status: Literal["documented_source_terms_project_review_required"] = (
        "documented_source_terms_project_review_required"
    )
    identifier_publication_status: Literal["not_approved"] = "not_approved"
    public_hosting_status: Literal["unavailable"] = "unavailable"
    operational_blockers: tuple[str, ...]
    policy_blockers: tuple[str, ...]
    operations_route: Literal["manchester"] = "manchester"
    decision_record: str

    @model_validator(mode="after")
    def validate_health(self) -> SourceHealthRow:
        if not self.credential_present and self.configuration_status == "configured":
            raise ValueError("configured source requires credential presence")
        if self.next_locally_eligible_at_utc is not None and self.last_attempt_at_utc is None:
            raise ValueError("next eligibility requires a prior attempt")
        return self


class SourceHealthReport(SourceHealthModel):
    schema_version: Literal["1.0"] = SOURCE_HEALTH_SCHEMA_VERSION
    method_version: Literal["source-health-1.0"] = SOURCE_HEALTH_METHOD_VERSION
    evaluated_at_utc: datetime
    workspace_status: Literal["verified_durable"] = "verified_durable"
    sources: tuple[SourceHealthRow, SourceHealthRow]
    aggregate_journal_records: int = Field(ge=0)
    aggregate_journal_integrity: Literal["absent_valid", "valid", "invalid"]
    metadata_download_available: Literal[True] = True
    network_request_performed: Literal[False] = False
    workspace_mutated: Literal[False] = False
    credential_presence_only: Literal[True] = True
    credential_value_persisted: Literal[False] = False
    credential_hash_present: Literal[False] = False
    private_path_present: Literal[False] = False
    raw_identifier_present: Literal[False] = False
    public_hosting_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_sources(self) -> SourceHealthReport:
        if tuple(item.source for item in self.sources) != ("BODS", "National Highways"):
            raise ValueError("source health rows must use stable source order")
        return self

    def download_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )


def load_source_health(
    workspace_path: str | Path,
    *,
    environment: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SourceHealthReport:
    """Read only local validated metadata; never make a source or credential test request."""

    evaluated = (clock or (lambda: datetime.now(UTC)))()
    if evaluated.tzinfo is None or evaluated.utcoffset() != timedelta(0):
        raise SourceHealthError("SOURCE_HEALTH_TIME_INVALID", "health clock must be UTC")
    try:
        preflight = preflight_real_v07_workspace_run(
            workspace_path,
            environment=environment,
            port_probe=lambda _host, _port: True,
        )
    except V07RealWorkspaceRunError as exc:
        raise SourceHealthError(
            "SOURCE_HEALTH_WORKSPACE_INVALID", "a verified durable workspace is required"
        ) from exc
    workspace = Path(workspace_path)
    journal_records, journal_integrity = _journal_health(workspace)
    bods = _bods_row(preflight.bods, workspace, evaluated, journal_records, journal_integrity)
    highways = _national_highways_row(
        preflight.national_highways,
        workspace,
        evaluated,
        journal_records,
        journal_integrity,
    )
    return SourceHealthReport(
        evaluated_at_utc=evaluated,
        sources=(bods, highways),
        aggregate_journal_records=journal_records,
        aggregate_journal_integrity=journal_integrity,
    )


def _journal_health(workspace: Path) -> tuple[int, Literal["absent_valid", "valid", "invalid"]]:
    try:
        report = load_operational_journal(workspace).report
    except ManchesterOperationalHistoryError:
        return 0, "invalid"
    return report.record_count, "valid" if report.journal_present else "absent_valid"


def _bods_row(
    source: V07SourceRunPreflight,
    workspace: Path,
    evaluated_at_utc: datetime,
    journal_records: int,
    journal_integrity: Literal["absent_valid", "valid", "invalid"],
) -> SourceHealthRow:
    worker = bods_auto_refresh_status(workspace)
    try:
        control = load_bods_live_control_state(workspace)
    except (BodsLiveControlError, OSError, ValueError):
        return _invalid_row(source, "BODS", journal_records, journal_integrity, "GA-BODS-RETENTION")
    last_success = control.history[-1] if control.history else None
    worker_status = _worker_status(source, None if worker is None else worker.running, worker)
    return SourceHealthRow(
        source="BODS",
        scope="caller-declared transit-position request box",
        evidence_role="live_transit_positions",
        freshness_policy=source.contracts.freshness,
        configuration_status=source.configuration_status,
        credential_present=source.credential_present,
        request_scope_status=source.request_scope_status,
        worker_status=worker_status,
        conservative_interval_seconds=source.interval_seconds,
        last_attempt_at_utc=control.last_attempt_at_utc,
        last_success_at_utc=None if last_success is None else last_success.evaluated_at_utc,
        next_locally_eligible_at_utc=_next_eligible(
            control.last_attempt_at_utc, source.interval_seconds
        ),
        # The accepted BODS control summary does not retain source timestamps.
        last_source_time_utc=None,
        truth_state=_bods_truth_state(
            source,
            control.last_attempt_status,
            last_success,
            workspace,
            evaluated_at_utc,
        ),
        safe_failure_code=control.last_failure_code,
        hot_history_entries=control.history_entry_count,
        long_term_journal_records=journal_records,
        long_term_integrity=journal_integrity,
        operational_blockers=source.operational_blockers,
        policy_blockers=source.policy_blockers,
        decision_record="GA-BODS-6 and aggregate-retention owner decision",
    )


def _national_highways_row(
    source: V07SourceRunPreflight,
    workspace: Path,
    evaluated_at_utc: datetime,
    journal_records: int,
    journal_integrity: Literal["absent_valid", "valid", "invalid"],
) -> SourceHealthRow:
    worker = national_highways_auto_refresh_status(workspace)
    try:
        control = load_national_highways_control_state(workspace)
    except (NationalHighwaysLiveError, OSError, ValueError):
        return _invalid_row(
            source,
            "National Highways",
            journal_records,
            journal_integrity,
            "NH source terms",
        )
    last_success = control.history[-1] if control.history else None
    worker_status = _worker_status(source, None if worker is None else worker.running, worker)
    source_time = None
    if last_success is not None and last_success.products:
        source_time = max(item.publication_time_utc for item in last_success.products)
    return SourceHealthRow(
        source="National Highways",
        scope="strategic-road closures, restrictions and VMS",
        evidence_role="near_live_operational_road_events",
        freshness_policy=source.contracts.freshness,
        configuration_status=source.configuration_status,
        credential_present=source.credential_present,
        request_scope_status=source.request_scope_status,
        worker_status=worker_status,
        conservative_interval_seconds=source.interval_seconds,
        last_attempt_at_utc=control.last_attempt_at_utc,
        last_success_at_utc=None if last_success is None else last_success.evaluated_at_utc,
        next_locally_eligible_at_utc=_next_eligible(
            control.last_attempt_at_utc, source.interval_seconds
        ),
        last_source_time_utc=source_time,
        truth_state=_national_highways_truth_state(
            source, control.last_attempt_status, last_success, evaluated_at_utc
        ),
        safe_failure_code=control.last_failure_code,
        hot_history_entries=control.history_entry_count,
        long_term_journal_records=journal_records,
        long_term_integrity=journal_integrity,
        operational_blockers=source.operational_blockers,
        policy_blockers=source.policy_blockers,
        decision_record="National Highways source terms and public-hosting review",
    )


def _invalid_row(
    source: V07SourceRunPreflight,
    name: Literal["BODS", "National Highways"],
    journal_records: int,
    journal_integrity: Literal["absent_valid", "valid", "invalid"],
    decision_record: str,
) -> SourceHealthRow:
    return SourceHealthRow(
        source=name,
        scope=(
            "caller-declared transit-position request box"
            if name == "BODS"
            else "strategic-road closures, restrictions and VMS"
        ),
        evidence_role=(
            "live_transit_positions" if name == "BODS" else "near_live_operational_road_events"
        ),
        freshness_policy=source.contracts.freshness,
        configuration_status=source.configuration_status,
        credential_present=source.credential_present,
        request_scope_status=source.request_scope_status,
        worker_status="degraded",
        conservative_interval_seconds=source.interval_seconds,
        truth_state="invalid",
        hot_history_entries=0,
        long_term_journal_records=journal_records,
        long_term_integrity=journal_integrity,
        operational_blockers=tuple(sorted({*source.operational_blockers, "CONTROL_INVALID"})),
        policy_blockers=source.policy_blockers,
        decision_record=decision_record,
    )


def _worker_status(
    source: V07SourceRunPreflight,
    running: bool | None,
    worker: BodsAutoRefreshStatus | NationalHighwaysAutoRefreshStatus | None,
) -> Literal["disabled", "not_configured", "starting", "running", "degraded", "stopped"]:
    if source.configuration_status == "disabled":
        return "disabled"
    if source.configuration_status == "not_configured":
        return "not_configured"
    if source.configuration_status == "invalid":
        return "degraded"
    if worker is None:
        return "stopped"
    if worker.last_failure_code is not None:
        return "degraded"
    if running:
        return "starting" if worker.attempts_in_process == 0 else "running"
    return "stopped"


def _next_eligible(last: datetime | None, interval: int | None) -> datetime | None:
    return None if last is None or interval is None else last + timedelta(seconds=interval)


def _terminal_truth_state(
    source: V07SourceRunPreflight,
    terminal: str,
    has_success: bool,
) -> Literal["never", "stale", "failed", "invalid"] | None:
    if source.control_integrity == "invalid" or source.scene_status == "invalid":
        return "invalid"
    if terminal == "failed":
        return "stale" if has_success else "failed"
    if terminal in {"never", "in_progress"}:
        return "never" if not has_success else "stale"
    return None


def _bods_truth_state(
    source: V07SourceRunPreflight,
    terminal: str,
    last_success: BodsLiveRefreshSummary | None,
    workspace: Path,
    evaluated_at_utc: datetime,
) -> Literal["never", "live", "stale", "unavailable", "failed", "invalid"]:
    terminal_state = _terminal_truth_state(source, terminal, last_success is not None)
    if terminal_state is not None:
        return terminal_state
    if last_success is None:
        return "invalid"
    try:
        relative_path = Path(last_success.scene_relative_path)
        expected_sha256 = last_success.scene_file_sha256
        expected_fingerprint = last_success.scene_fingerprint
        expected_layers = last_success.layer_count
        scene = _load_exact_bods_scene(workspace, relative_path, expected_sha256)
        if scene.fingerprint() != expected_fingerprint or len(scene.layers) != expected_layers:
            return "invalid"
        projected = project_bods_live_scene_for_display(scene, evaluated_at_utc=evaluated_at_utc)
    except (BodsLiveControlError, OSError, TypeError, ValueError):
        return "invalid"
    states = tuple(
        layer.request.freshness.truth_state
        for layer in projected.layers
        if layer.request.source == "bods_siri_vm" and layer.request.freshness is not None
    )
    if "live_vehicle" in states:
        return "live"
    if "stale" in states:
        return "stale"
    return "unavailable"


def _load_exact_bods_scene(
    workspace: Path, relative_path: Path, expected_sha256: str
) -> ManchesterMapScene:
    if relative_path != Path("manchester/scenes/live_vehicles.json"):
        raise ValueError("unexpected scene path")
    target = workspace / relative_path
    if target.is_symlink() or not target.is_file():
        raise ValueError("scene unavailable")
    size = target.stat().st_size
    if size == 0 or size > SOURCE_HEALTH_SCENE_MAX_BYTES:
        raise ValueError("scene size invalid")
    payload = target.read_bytes()
    if len(payload) != size or sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("scene integrity invalid")
    scene = ManchesterMapScene.model_validate_json(payload)
    if scene.mode != "live_vehicles" or scene.canonical_json().encode("utf-8") != payload:
        raise ValueError("scene contract invalid")
    return scene


def _national_highways_truth_state(
    source: V07SourceRunPreflight,
    terminal: str,
    last_success: NationalHighwaysRefreshSummary | None,
    evaluated_at_utc: datetime,
) -> Literal["never", "near_live", "stale", "failed", "invalid"]:
    terminal_state = _terminal_truth_state(source, terminal, last_success is not None)
    if terminal_state is not None:
        return terminal_state
    if last_success is None:
        return "invalid"
    publication_times = tuple(item.publication_time_utc for item in last_success.products)
    if not publication_times:
        return "invalid"
    ages = tuple((evaluated_at_utc - item).total_seconds() for item in publication_times)
    if any(age < 0 or age > NATIONAL_HIGHWAYS_NEAR_LIVE_AGE_SECONDS for age in ages):
        return "stale"
    return "near_live"
