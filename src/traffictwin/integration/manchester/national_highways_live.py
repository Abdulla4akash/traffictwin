"""Explicit three-product National Highways refresh, scene, and aggregate history."""

from __future__ import annotations

import fcntl
import os
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    FreshnessSource,
    evaluate_source_freshness,
)
from traffictwin.integration.manchester.map_layers import (
    NATIONAL_HIGHWAYS_ATTRIBUTION,
    NATIONAL_HIGHWAYS_TERMS_URI,
    ManchesterMapLayerManifest,
    ManchesterMapScene,
    MapLayerRequest,
    MapMode,
    build_map_layer,
    build_map_scene,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterSnapshotModel,
    ManchesterValidationState,
    sha256_hex,
)
from traffictwin.integration.manchester.national_highways import (
    NationalHighwaysProduct,
    NationalHighwaysRecord,
    default_manchester_operational_envelope,
)
from traffictwin.integration.manchester.national_highways_acquisition import (
    NationalHighwaysAcquisition,
    NationalHighwaysAcquisitionRequest,
    acquire_national_highways_snapshot,
)
from traffictwin.integration.manchester.spatial import (
    GeometryMeaning,
    ManchesterSpatialPointEvidence,
    SpatialSource,
    evaluate_spatial_batch,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

NATIONAL_HIGHWAYS_CONTROL_VERSION = "national-highways-live-control-1.0"
NATIONAL_HIGHWAYS_CONTROL_RELATIVE_PATH = Path(
    "manchester/live/national-highways-refresh-state.json"
)
NATIONAL_HIGHWAYS_LOCK_RELATIVE_PATH = Path("manchester/live/.national-highways-refresh.lock")
NATIONAL_HIGHWAYS_LATEST_OVERLAY = Path("manchester/scenes/national_highways_latest_available.json")
NATIONAL_HIGHWAYS_LIVE_OVERLAY = Path("manchester/scenes/national_highways_live_vehicles.json")
NATIONAL_HIGHWAYS_MINIMUM_INTERVAL_SECONDS = 60
NATIONAL_HIGHWAYS_HISTORY_MAX_ENTRIES = 240
NATIONAL_HIGHWAYS_STATE_MAX_BYTES = 2 * 1024 * 1024


class NationalHighwaysLiveError(RuntimeError):
    """Typed control, history, or scene refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NationalHighwaysProductSummary(ManchesterSnapshotModel):
    """One source-separated product summary for a complete refresh."""

    product: NationalHighwaysProduct
    snapshot_id: str
    publication_time_utc: datetime
    source_items_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    outside_envelope: int = Field(ge=0)
    coordinates_missing: int = Field(ge=0)
    exact_duplicates_collapsed: int = Field(ge=0)
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_counts(self) -> NationalHighwaysProductSummary:
        if self.source_items_seen != (
            self.records_accepted
            + self.outside_envelope
            + self.coordinates_missing
            + self.exact_duplicates_collapsed
        ):
            raise ValueError("product summary counts must reconcile")
        return self


class NationalHighwaysRefreshSummary(ManchesterSnapshotModel):
    """Secret-free aggregate receipt for one controlled three-call refresh."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["national-highways-live-control-1.0"] = (
        "national-highways-live-control-1.0"
    )
    evaluated_at_utc: datetime
    products: tuple[NationalHighwaysProductSummary, ...]
    total_records_accepted: int = Field(ge=0)
    latest_scene_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    live_overlay_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_count: Literal[3] = 3
    operator_triggered: bool = True
    automatic_polling_performed: bool = False
    subscription_key_persisted: Literal[False] = False
    source_fusion_performed: Literal[False] = False
    strategic_road_network_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_summary(self) -> NationalHighwaysRefreshSummary:
        expected = ("closures", "speed_limits", "vms")
        if tuple(item.product for item in self.products) != expected:
            raise ValueError("refresh summary must contain the three products in stable order")
        if self.total_records_accepted != sum(item.records_accepted for item in self.products):
            raise ValueError("refresh total must reconcile product records")
        if self.operator_triggered == self.automatic_polling_performed:
            raise ValueError("exactly one refresh trigger must be recorded")
        return self


class NationalHighwaysControlState(ManchesterSnapshotModel):
    """Bounded aggregate-only operational refresh history."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["national-highways-live-control-1.0"] = (
        "national-highways-live-control-1.0"
    )
    attempts_total: int = Field(ge=0)
    successes_total: int = Field(ge=0)
    failures_total: int = Field(ge=0)
    last_attempt_at_utc: datetime | None = None
    last_attempt_status: Literal["never", "succeeded", "failed"] = "never"
    last_failure_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,96}$")
    history: tuple[NationalHighwaysRefreshSummary, ...] = ()
    history_entry_count: int = Field(ge=0, le=NATIONAL_HIGHWAYS_HISTORY_MAX_ENTRIES)
    automatic_polling_available: bool = False
    raw_payloads_in_history: Literal[False] = False

    @model_validator(mode="after")
    def validate_state(self) -> NationalHighwaysControlState:
        if self.attempts_total != self.successes_total + self.failures_total:
            raise ValueError("control attempt totals must reconcile")
        if self.history_entry_count != len(self.history):
            raise ValueError("history count must match embedded summaries")
        if self.successes_total < len(self.history):
            raise ValueError("bounded history cannot exceed lifetime successes")
        keys = tuple(item.evaluated_at_utc for item in self.history)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("history must be sorted by unique evaluation time")
        if (self.last_attempt_status == "failed") != (self.last_failure_code is not None):
            raise ValueError("failure code must exist exactly for a failed attempt")
        if self.last_attempt_status == "never" and (
            self.last_attempt_at_utc is not None or self.attempts_total
        ):
            raise ValueError("never-attempted state cannot contain attempt evidence")
        return self


def initial_national_highways_control_state() -> NationalHighwaysControlState:
    return NationalHighwaysControlState(
        attempts_total=0,
        successes_total=0,
        failures_total=0,
        history_entry_count=0,
    )


def load_national_highways_control_state(
    workspace_root: str | Path,
) -> NationalHighwaysControlState:
    """Load the canonical aggregate-only history without network access."""

    workspace = _workspace(workspace_root)
    target = workspace / NATIONAL_HIGHWAYS_CONTROL_RELATIVE_PATH
    _validate_private_target(workspace, target, code="CONTROL_STATE_INVALID")
    if not target.exists():
        return initial_national_highways_control_state()
    if (
        target.is_symlink()
        or not target.is_file()
        or target.stat().st_size > NATIONAL_HIGHWAYS_STATE_MAX_BYTES
    ):
        raise NationalHighwaysLiveError("CONTROL_STATE_INVALID", "control state is unsafe")
    payload = target.read_bytes()
    try:
        state = NationalHighwaysControlState.model_validate_json(payload)
    except ValueError as exc:
        raise NationalHighwaysLiveError(
            "CONTROL_STATE_INVALID", "control state is invalid"
        ) from exc
    if state.canonical_json().encode("utf-8") != payload:
        raise NationalHighwaysLiveError(
            "CONTROL_STATE_NON_CANONICAL", "control state must use canonical JSON"
        )
    return state


def coordinated_national_highways_refresh(
    workspace_root: str | Path,
    *,
    subscription_key: str,
    event_type: Literal["planned", "unplanned"] = "unplanned",
    utc_now: Callable[[], datetime] | None = None,
    http_client: httpx.Client | None = None,
    synthetic: bool = False,
    trigger: Literal["operator", "automatic"] = "operator",
) -> NationalHighwaysRefreshSummary:
    """Perform one controlled three-product refresh and atomically publish both overlays."""

    workspace = _workspace(workspace_root)
    clock: Callable[[], datetime] = (lambda: datetime.now(UTC)) if utc_now is None else utc_now
    evaluated_at = clock()
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() != timedelta(0):
        raise NationalHighwaysLiveError("TIME_INVALID", "refresh clock must be UTC")
    descriptor = _acquire_lock(workspace)
    try:
        previous = load_national_highways_control_state(workspace)
        if previous.last_attempt_at_utc is not None:
            elapsed = (evaluated_at - previous.last_attempt_at_utc).total_seconds()
            if elapsed < 0:
                raise NationalHighwaysLiveError("CLOCK_REGRESSION", "refresh clock moved backwards")
            if elapsed < NATIONAL_HIGHWAYS_MINIMUM_INTERVAL_SECONDS:
                raise NationalHighwaysLiveError(
                    "REFRESH_TOO_SOON",
                    "wait at least "
                    f"{NATIONAL_HIGHWAYS_MINIMUM_INTERVAL_SECONDS - int(elapsed)} seconds",
                )
        envelope = default_manchester_operational_envelope()
        acquisitions: list[NationalHighwaysAcquisition] = []
        try:
            for product in cast(
                tuple[NationalHighwaysProduct, ...],
                ("closures", "speed_limits", "vms"),
            ):
                request = NationalHighwaysAcquisitionRequest(
                    product=product,
                    envelope=envelope,
                    event_type=None if product == "vms" else event_type,
                    window_start_utc=(
                        None if product == "vms" else evaluated_at - timedelta(hours=6)
                    ),
                    window_end_utc=None if product == "vms" else evaluated_at,
                    synthetic=synthetic,
                )
                acquisitions.append(
                    acquire_national_highways_snapshot(
                        workspace,
                        request,
                        subscription_key=subscription_key,
                        http_client=http_client,
                        utc_now=utc_now,
                    )
                )
            latest = build_national_highways_scene(
                acquisitions,
                mode="latest_available",
                evaluated_at_utc=evaluated_at,
            )
            live = build_national_highways_scene(
                acquisitions,
                mode="live_vehicles",
                evaluated_at_utc=evaluated_at,
            )
            latest_sha = _publish_scene(
                workspace,
                workspace / NATIONAL_HIGHWAYS_LATEST_OVERLAY,
                latest,
            )
            live_sha = _publish_scene(
                workspace,
                workspace / NATIONAL_HIGHWAYS_LIVE_OVERLAY,
                live,
            )
            summary = NationalHighwaysRefreshSummary(
                evaluated_at_utc=evaluated_at,
                products=tuple(_product_summary(item) for item in acquisitions),
                total_records_accepted=sum(item.result.records_accepted for item in acquisitions),
                latest_scene_sha256=latest_sha,
                live_overlay_sha256=live_sha,
                operator_triggered=trigger == "operator",
                automatic_polling_performed=trigger == "automatic",
            )
        except Exception as exc:
            failed = NationalHighwaysControlState(
                attempts_total=previous.attempts_total + 1,
                successes_total=previous.successes_total,
                failures_total=previous.failures_total + 1,
                last_attempt_at_utc=evaluated_at,
                last_attempt_status="failed",
                last_failure_code=_failure_code(exc),
                history=previous.history,
                history_entry_count=len(previous.history),
                automatic_polling_available=(
                    previous.automatic_polling_available or trigger == "automatic"
                ),
            )
            _store_state(workspace, failed)
            raise
        history = _bounded_history(previous.history + (summary,), evaluated_at)
        succeeded = NationalHighwaysControlState(
            attempts_total=previous.attempts_total + 1,
            successes_total=previous.successes_total + 1,
            failures_total=previous.failures_total,
            last_attempt_at_utc=evaluated_at,
            last_attempt_status="succeeded",
            history=history,
            history_entry_count=len(history),
            automatic_polling_available=(
                previous.automatic_polling_available or trigger == "automatic"
            ),
        )
        _store_state(workspace, succeeded)
        return summary
    finally:
        _release_lock(workspace, descriptor)


def build_national_highways_scene(
    acquisitions: Sequence[NationalHighwaysAcquisition],
    *,
    mode: MapMode,
    evaluated_at_utc: datetime,
    source_outage: bool = False,
) -> ManchesterMapScene:
    """Build three distinct map layers; no cross-product totals or joins."""

    by_product = {item.result.request.product: item for item in acquisitions}
    expected: tuple[NationalHighwaysProduct, ...] = ("closures", "speed_limits", "vms")
    if set(by_product) != set(expected):
        raise NationalHighwaysLiveError(
            "PRODUCT_SET_INVALID", "scene requires one acquisition for each operational product"
        )
    layers = tuple(
        _build_layer(
            by_product[product],
            mode=mode,
            evaluated_at_utc=evaluated_at_utc,
            source_outage=source_outage,
        )
        for product in expected
    )
    return build_map_scene(mode, layers)


def project_national_highways_scene_for_display(
    scene: ManchesterMapScene,
    *,
    evaluated_at_utc: datetime,
    source_outage: bool,
) -> ManchesterMapScene:
    """Re-evaluate cached operational layers without mutating stored evidence."""

    layers: list[ManchesterMapLayerManifest] = []
    for layer in scene.layers:
        if not layer.request.source.startswith("national_highways_"):
            layers.append(layer)
            continue
        original = layer.request.freshness
        if original is None or original.observed_at_utc is None:
            raise NationalHighwaysLiveError(
                "FRESHNESS_INVALID", "operational layer is missing publication-time evidence"
            )
        refreshed = evaluate_source_freshness(
            FreshnessEvaluationRequest(
                source=original.source,
                evidence_validation=ManchesterValidationState.ACCEPTED,
                snapshot_available=True,
                use_mode="live",
                evaluated_at_utc=evaluated_at_utc,
                observed_at_utc=original.observed_at_utc,
                synthetic=layer.request.synthetic,
                service_state="forced_unavailable" if source_outage else "normal",
                service_notice_id="latest_refresh_failed" if source_outage else None,
                using_cached_snapshot=source_outage,
            )
        )
        layers.append(
            build_map_layer(
                layer.request.model_copy(
                    update={"freshness": refreshed},
                )
            )
        )
    return build_map_scene(scene.mode, layers)


def national_highways_history_rows(
    state: NationalHighwaysControlState,
) -> tuple[dict[str, object], ...]:
    """Return source-separated aggregate rows for a small local chart."""

    return tuple(
        {
            "Retrieved at": item.evaluated_at_utc,
            **{
                {
                    "closures": "Closures/incidents",
                    "speed_limits": "Temporary speed restrictions",
                    "vms": "VMS signs",
                }[product.product]: product.records_accepted
                for product in item.products
            },
        }
        for item in state.history
    )


def overlay_relative_path(mode: MapMode) -> Path | None:
    if mode == "latest_available":
        return NATIONAL_HIGHWAYS_LATEST_OVERLAY
    if mode == "live_vehicles":
        return NATIONAL_HIGHWAYS_LIVE_OVERLAY
    return None


def _build_layer(
    acquisition: NationalHighwaysAcquisition,
    *,
    mode: MapMode,
    evaluated_at_utc: datetime,
    source_outage: bool,
) -> ManchesterMapLayerManifest:
    result = acquisition.result
    report = acquisition.report
    source = cast(SpatialSource, result.source_id)
    geometry = cast(
        GeometryMeaning,
        {
            "closures": "road_closure_position",
            "speed_limits": "temporary_speed_restriction_position",
            "vms": "variable_message_sign_position",
        }[result.request.product],
    )
    evidence = tuple(
        ManchesterSpatialPointEvidence(
            source=source,
            source_record_fingerprint=record.fingerprint(),
            point_id=f"nh:{record.product}:{record.record_token}",
            coordinate_kind="wgs84",
            longitude_epsg4326=record.longitude,
            latitude_epsg4326=record.latitude,
            geographic_scope="national_highways_manchester_envelope",
            scope_basis="national_highways_request_envelope",
            scope_evidence_fingerprint=report.envelope_fingerprint,
            geometry_meaning=geometry,
            source_record_state="eligible",
            uncertainty_basis="source_not_stated",
            synthetic=record.synthetic,
        )
        for record in report.records
    )
    spatial = evaluate_spatial_batch(evidence)
    freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source=cast(FreshnessSource, result.source_id),
            evidence_validation=ManchesterValidationState.ACCEPTED,
            snapshot_available=True,
            use_mode="historical" if mode == "historical_replay" else "live",
            evaluated_at_utc=evaluated_at_utc,
            observed_at_utc=report.publication_time_utc,
            synthetic=result.synthetic,
            service_state="forced_unavailable" if source_outage else "normal",
            service_notice_id="latest_refresh_failed" if source_outage else None,
            using_cached_snapshot=source_outage,
        )
    )
    labels = tuple(
        sorted((record.fingerprint(), _record_label(record)) for record in report.records)
    )
    return build_map_layer(
        MapLayerRequest(
            layer_id=f"nh-{result.request.product.replace('_', '-')}",
            title={
                "closures": "National Highways closures and incidents",
                "speed_limits": "National Highways temporary speed restrictions",
                "vms": "National Highways digital VMS",
            }[result.request.product],
            mode=mode,
            source=source,
            snapshot_id=result.snapshot_id,
            snapshot_fingerprint=result.raw_fingerprint,
            spatial_report=spatial,
            freshness=freshness,
            publication_class=ManchesterPublicationClass.PRIVATE,
            licence_id="NH-Transport-Data-Feeds",
            licence_uri=NATIONAL_HIGHWAYS_TERMS_URI,
            attribution_lines=(NATIONAL_HIGHWAYS_ATTRIBUTION,),
            synthetic=result.synthetic,
            point_labels=labels,
        )
    )


def _record_label(record: NationalHighwaysRecord) -> str:
    road = record.road_name or "Strategic Road Network"
    location = record.location_description
    operational = record.operational_type
    speed = record.temporary_speed_limit_kph
    reason = record.vms_reason_for_setting
    detail = operational
    if speed is not None:
        detail = f"{speed} km/h imposed temporary limit; {operational}"
    elif reason is not None:
        detail = f"{operational}; {reason}"
    return f"{road}; {location}; {detail}"[:320]


def _product_summary(item: NationalHighwaysAcquisition) -> NationalHighwaysProductSummary:
    result = item.result
    return NationalHighwaysProductSummary(
        product=result.request.product,
        snapshot_id=result.snapshot_id,
        publication_time_utc=result.publication_time_utc,
        source_items_seen=result.source_items_seen,
        records_accepted=result.records_accepted,
        outside_envelope=result.outside_envelope,
        coordinates_missing=result.coordinates_missing,
        exact_duplicates_collapsed=result.exact_duplicates_collapsed,
        raw_sha256=result.raw_sha256,
        report_fingerprint=result.parser_report_fingerprint,
    )


def _publish_scene(workspace: Path, target: Path, scene: ManchesterMapScene) -> str:
    _prepare_private_target(workspace, target, code="SCENE_PATH_INVALID")
    payload = scene.canonical_json().encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return sha256_hex(payload)


def _bounded_history(
    history: tuple[NationalHighwaysRefreshSummary, ...], evaluated_at: datetime
) -> tuple[NationalHighwaysRefreshSummary, ...]:
    cutoff = evaluated_at - timedelta(hours=24)
    retained = tuple(item for item in history if item.evaluated_at_utc >= cutoff)
    return retained[-NATIONAL_HIGHWAYS_HISTORY_MAX_ENTRIES:]


def _store_state(workspace: Path, state: NationalHighwaysControlState) -> None:
    target = workspace / NATIONAL_HIGHWAYS_CONTROL_RELATIVE_PATH
    _prepare_private_target(workspace, target, code="CONTROL_STATE_INVALID")
    payload = state.canonical_json().encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _acquire_lock(workspace: Path) -> int:
    target = workspace / NATIONAL_HIGHWAYS_LOCK_RELATIVE_PATH
    _prepare_private_target(workspace, target, code="LOCK_PATH_INVALID")
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, os.O_CREAT | os.O_RDWR | no_follow, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise NationalHighwaysLiveError(
            "REFRESH_IN_PROGRESS", "another operational refresh is already running"
        ) from exc
    return descriptor


def _release_lock(workspace: Path, descriptor: int) -> None:
    try:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
    _ = workspace


def _failure_code(exc: Exception) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value.isupper() and len(value) <= 96:
        return value
    return "NATIONAL_HIGHWAYS_REFRESH_FAILED"


def _prepare_private_target(workspace: Path, target: Path, *, code: str) -> None:
    """Create a fixed parent path without following workspace-internal symlinks."""

    _validate_private_target(workspace, target, code=code)
    relative = target.relative_to(workspace)
    cursor = workspace
    for part in relative.parts[:-1]:
        cursor /= part
        cursor.mkdir(exist_ok=True)
    _validate_private_target(workspace, target, code=code)


def _validate_private_target(workspace: Path, target: Path, *, code: str) -> None:
    """Refuse path escape or symlinks without mutating a read-only lookup."""

    try:
        relative = target.relative_to(workspace)
    except ValueError as exc:
        raise NationalHighwaysLiveError(code, "private target escapes the workspace") from exc
    cursor = workspace
    for part in relative.parts[:-1]:
        cursor /= part
        if cursor.is_symlink():
            raise NationalHighwaysLiveError(code, "private target parent is a symlink")
        if cursor.exists() and not cursor.is_dir():
            raise NationalHighwaysLiveError(code, "private target parent is not a directory")
        if not cursor.exists():
            return
    if target.is_symlink():
        raise NationalHighwaysLiveError(code, "private target is a symlink")
    try:
        target.parent.resolve(strict=True).relative_to(workspace)
    except (OSError, ValueError) as exc:
        raise NationalHighwaysLiveError(code, "private target parent is unsafe") from exc


def _workspace(value: str | Path) -> Path:
    workspace = Path(value)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise NationalHighwaysLiveError(
            "WORKSPACE_INVALID", "an isolated TrafficTwin v0.7 workspace is required"
        ) from exc
    return workspace.resolve(strict=True)
