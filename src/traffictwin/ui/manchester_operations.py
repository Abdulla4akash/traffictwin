"""Thin local-data helpers for the candidate Manchester Operations page.

The UI boundary deliberately accepts only a validated ``ManchesterMapScene``
stored at a fixed path below the configured workspace. It performs no network
access, coordinate projection, source joins, or scientific calculation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, TypeAlias

import pydeck as pdk
from pydantic import ValidationError

from traffictwin.integration.manchester.bods import BodsBoundingBox
from traffictwin.integration.manchester.boundary_reference import (
    ManchesterBoundaryFeature,
    load_boundary_features,
)
from traffictwin.integration.manchester.dft import DirectionCode
from traffictwin.integration.manchester.dft_acquisition import (
    DftAcceptedSnapshotCatalogue,
    DftAcceptedSnapshotSummary,
    DftAcquisitionError,
    catalogue_accepted_dft_snapshots,
)
from traffictwin.integration.manchester.dft_survey_view import (
    DftSurveyFilterOptions,
    DftSurveyView,
    DftSurveyViewError,
    DftSurveyViewQuery,
    DftVehicleClass,
    build_dft_survey_view_from_snapshot,
    dft_survey_filter_options_from_snapshot,
)
from traffictwin.integration.manchester.freshness import FreshnessTruthState
from traffictwin.integration.manchester.map_layers import (
    ManchesterMapLayerManifest,
    ManchesterMapPoint,
    ManchesterMapScene,
    MapMode,
    build_map_scene,
)
from traffictwin.integration.manchester.models import sha256_hex
from traffictwin.integration.manchester.national_highways_live import overlay_relative_path
from traffictwin.integration.manchester.randy import (
    RandyManchesterBridgeReport,
    load_randy_manchester_bridge,
)
from traffictwin.integration.manchester.spatial import GeographicScope
from traffictwin.integration.manchester.webtris_acquisition import (
    WebtrisAcceptedSnapshotCatalogue,
    WebtrisAcceptedSnapshotSummary,
    WebtrisAcquisitionError,
    catalogue_accepted_webtris_snapshots,
    open_accepted_webtris_snapshot,
)
from traffictwin.integration.manchester.webtris_timeseries import (
    WebtrisMeasurementState,
    WebtrisTimeseriesError,
    WebtrisTimeseriesFilter,
    WebtrisTimeseriesResult,
    build_webtris_chart_series,
    build_webtris_timeseries_from_accepted_snapshots,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

MANCHESTER_SCENE_DIRECTORY = Path("manchester/scenes")
MANCHESTER_SCENE_MAX_BYTES = 8 * 1024 * 1024

SceneLoadStatus = Literal["available", "unavailable", "rejected"]
RandyCaseStudyStatus = Literal["available", "unconfigured", "rejected"]
SceneFreshnessState: TypeAlias = FreshnessTruthState | Literal["not_applicable"]
LiveAcquisitionStatus = Literal[
    "ready",
    "workspace_unconfigured",
    "workspace_invalid",
    "api_key_missing",
]
WebtrisHistoryStatus = Literal["available", "unavailable", "rejected"]
WebtrisHistoryReason = Literal[
    "ready",
    "workspace_unconfigured",
    "no_accepted_daily_reports",
    "measurement_filter_empty",
    "accepted_evidence_rejected",
]
DftSurveyStatus = Literal["available", "unavailable", "rejected"]
DftSurveyReason = Literal[
    "ready",
    "workspace_unconfigured",
    "no_accepted_raw_counts",
    "filter_selection_empty",
    "accepted_evidence_rejected",
]
SceneLoadReason = Literal[
    "ready",
    "workspace_unconfigured",
    "scene_missing",
    "scene_path_escaped",
    "scene_symlink_refused",
    "scene_empty",
    "scene_too_large",
    "scene_read_failed",
    "scene_invalid",
    "scene_mode_mismatch",
]

_SCENE_FILENAMES: dict[MapMode, str] = {
    "historical_replay": "historical_replay.json",
    "latest_available": "latest_available.json",
    "live_vehicles": "live_vehicles.json",
}
_SYMBOL_GLYPHS = {
    "circle": "●",
    "square": "■",
    "diamond": "◆",
    "triangle": "▲",
    "cross": "✚",
}


@dataclass(frozen=True, slots=True)
class LocalManchesterScene:
    """Display-safe result of loading one fixed local scene artifact."""

    status: SceneLoadStatus
    reason: SceneLoadReason
    message: str
    scene: ManchesterMapScene | None = None
    artifact_sha256: str | None = None
    byte_size: int | None = None


@dataclass(frozen=True, slots=True)
class LiveAcquisitionReadiness:
    """Secret-free readiness state for the explicit BODS fetch form."""

    status: LiveAcquisitionStatus
    message: str
    ready: bool


@dataclass(frozen=True, slots=True)
class LocalRandyCaseStudy:
    """Display-safe state for one optional verified VEC-11 pack."""

    status: RandyCaseStudyStatus
    message: str
    report: RandyManchesterBridgeReport | None = None


@dataclass(frozen=True, slots=True)
class LocalWebtrisCatalogue:
    """Display-safe state for the bounded offline accepted WebTRIS catalogue."""

    status: WebtrisHistoryStatus
    reason: WebtrisHistoryReason
    message: str
    catalogue: WebtrisAcceptedSnapshotCatalogue | None = None


@dataclass(frozen=True, slots=True)
class LocalWebtrisTimeseries:
    """Display-safe state for one locally rebuilt accepted WebTRIS site-day."""

    status: WebtrisHistoryStatus
    reason: WebtrisHistoryReason
    message: str
    result: WebtrisTimeseriesResult | None = None


@dataclass(frozen=True, slots=True)
class LocalDftCatalogue:
    """Display-safe state for the bounded offline accepted DfT catalogue."""

    status: DftSurveyStatus
    reason: DftSurveyReason
    message: str
    catalogue: DftAcceptedSnapshotCatalogue | None = None


@dataclass(frozen=True, slots=True)
class LocalDftSurveyOptions:
    """Display-safe exact filter inventory for one accepted DfT raw-count snapshot."""

    status: DftSurveyStatus
    reason: DftSurveyReason
    message: str
    options: DftSurveyFilterOptions | None = None


@dataclass(frozen=True, slots=True)
class LocalDftSurveyView:
    """Display-safe deterministic view over one accepted DfT raw-count snapshot."""

    status: DftSurveyStatus
    reason: DftSurveyReason
    message: str
    view: DftSurveyView | None = None


@dataclass(frozen=True, slots=True)
class SceneFilterOptions:
    """Exact display filters available in the selected local layers."""

    geographic_scopes: tuple[GeographicScope, ...]
    freshness_states: tuple[SceneFreshnessState, ...]


@dataclass(frozen=True, slots=True)
class FilteredManchesterLayer:
    """One layer plus its display-only point subset and reconciliation."""

    manifest: ManchesterMapLayerManifest
    points: tuple[ManchesterMapPoint, ...]
    hidden_by_scope: int
    hidden_by_freshness: int

    @property
    def hidden_by_filters(self) -> int:
        """Return the exact number of admitted points hidden by UI filters."""

        return self.hidden_by_scope + self.hidden_by_freshness


@dataclass(frozen=True, slots=True)
class FilteredManchesterScene:
    """Display-only view over a validated scene; the source scene is unchanged."""

    scene: ManchesterMapScene
    layers: tuple[FilteredManchesterLayer, ...]
    selected_geographic_scopes: tuple[GeographicScope, ...]
    selected_freshness_states: tuple[SceneFreshnessState, ...]

    @property
    def has_displayed_points(self) -> bool:
        """Report whether any layer renders without creating a cross-source total."""

        return any(layer.points for layer in self.layers)

    @property
    def attributions(self) -> tuple[str, ...]:
        """Return attribution for source layers that currently render points."""

        return tuple(
            sorted(
                {
                    line
                    for layer in self.layers
                    if layer.points
                    for line in layer.manifest.request.attribution_lines
                }
            )
        )

    @property
    def visible_scopes(self) -> tuple[GeographicScope, ...]:
        """Return scopes represented by the currently displayed point subset."""

        return tuple(
            sorted({point.geographic_scope for layer in self.layers for point in layer.points})
        )


def load_local_randy_case_study(
    pack_path: str | Path | None,
) -> LocalRandyCaseStudy:
    """Load the accepted sanitised pack without retaining or displaying its path."""

    if pack_path is None or not str(pack_path).strip():
        return LocalRandyCaseStudy(
            status="unconfigured",
            message=(
                "Set TRAFFICTWIN_RANDY_PACK_PATH to the accepted VEC-11 dissertation pack "
                "to enable this optional local case study."
            ),
        )
    try:
        report = load_randy_manchester_bridge(Path(pack_path))
    except (OSError, ValueError):
        return LocalRandyCaseStudy(
            status="rejected",
            message=(
                "The configured Randy/TOS case-study pack failed its accepted VEC-11 "
                "integrity and permission contract."
            ),
        )
    return LocalRandyCaseStudy(
        status="available",
        message="Accepted sanitised Randy/TOS case-study evidence loaded locally.",
        report=report,
    )


def randy_sample_rows(report: RandyManchesterBridgeReport) -> list[dict[str, object]]:
    """Return only the explicitly sanitised sample fields approved by VEC-11."""

    return [
        {
            "Sample": sample.sample_id,
            "Scenario": sample.scenario,
            "Task class": sample.task_class.value,
            "Deadline met": sample.deadline_met,
            "Latency (rounded 10 ms)": sample.latency_ms_rounded_10,
            "Slot tier": sample.slot_tier,
            "EV slot": sample.slot_is_ev,
            "Decision": sample.action.value,
            "Target availability": sample.target_availability.value,
            "Trip duration (rounded 10 s)": sample.trip_duration_s_rounded_10,
            "Route length (rounded 100 m)": sample.trip_route_length_m_rounded_100,
        }
        for sample in report.samples
    ]


def randy_metric_rows(report: RandyManchesterBridgeReport) -> list[dict[str, object]]:
    """Render available and unavailable aggregate states without filling missing values."""

    return [
        {
            "Metric": metric.metric_key,
            "Status": metric.status,
            "Value": (
                "unavailable"
                if metric.value is None
                else json.dumps(metric.value, sort_keys=True, separators=(",", ":"))
            ),
            "Unit": metric.unit,
            "Scope": metric.scope,
            "Missing evidence": "; ".join(metric.missing_evidence),
        }
        for metric in report.metrics
    ]


def load_local_webtris_catalogue(
    workspace_path: str | Path | None,
) -> LocalWebtrisCatalogue:
    """Verify and inventory accepted WebTRIS snapshots without network access."""

    if workspace_path is None:
        return LocalWebtrisCatalogue(
            status="unavailable",
            reason="workspace_unconfigured",
            message="Configure an isolated TrafficTwin v0.7 workspace to inspect WebTRIS data.",
        )
    try:
        catalogue = catalogue_accepted_webtris_snapshots(workspace_path)
    except (WebtrisAcquisitionError, OSError, ValueError):
        return LocalWebtrisCatalogue(
            status="rejected",
            reason="accepted_evidence_rejected",
            message="The local accepted WebTRIS catalogue failed its integrity contract.",
        )
    if not accepted_webtris_daily_options(catalogue):
        return LocalWebtrisCatalogue(
            status="unavailable",
            reason="no_accepted_daily_reports",
            message="No accepted local WebTRIS daily reports are available yet.",
            catalogue=catalogue,
        )
    return LocalWebtrisCatalogue(
        status="available",
        reason="ready",
        message="Accepted local WebTRIS daily reports are ready for historical replay.",
        catalogue=catalogue,
    )


def load_local_dft_catalogue(
    workspace_path: str | Path | None,
) -> LocalDftCatalogue:
    """Verify and inventory accepted DfT snapshots without network access."""

    if workspace_path is None:
        return LocalDftCatalogue(
            status="unavailable",
            reason="workspace_unconfigured",
            message="Configure an isolated TrafficTwin v0.7 workspace to inspect DfT surveys.",
        )
    try:
        catalogue = catalogue_accepted_dft_snapshots(workspace_path)
    except (DftAcquisitionError, OSError, ValueError):
        return LocalDftCatalogue(
            status="rejected",
            reason="accepted_evidence_rejected",
            message="The local accepted DfT catalogue failed its integrity contract.",
        )
    if not accepted_dft_raw_count_options(catalogue):
        return LocalDftCatalogue(
            status="unavailable",
            reason="no_accepted_raw_counts",
            message="No accepted local DfT raw-count snapshots are available yet.",
            catalogue=catalogue,
        )
    return LocalDftCatalogue(
        status="available",
        reason="ready",
        message="Accepted local DfT raw-count snapshots are ready for historical inspection.",
        catalogue=catalogue,
    )


def accepted_dft_raw_count_options(
    catalogue: DftAcceptedSnapshotCatalogue,
) -> tuple[DftAcceptedSnapshotSummary, ...]:
    """Return accepted raw-count snapshots newest-first for an exact catalogue."""

    return tuple(
        reversed(tuple(item for item in catalogue.snapshots if item.dataset == "raw_counts"))
    )


def dft_snapshot_label(summary: DftAcceptedSnapshotSummary) -> str:
    """Return a disambiguated source label without exposing a local path."""

    evidence_class = "synthetic" if summary.synthetic else "source"
    source_filter = (
        "all source rows" if summary.filter_id is None else f"source filter {summary.filter_id}"
    )
    return (
        f"DfT raw counts · {source_filter} · {summary.records_accepted} records · "
        f"{evidence_class} · {summary.snapshot_id[-12:]}"
    )


def load_local_dft_survey_options(
    workspace_path: str | Path | None,
    snapshot_id: str,
) -> LocalDftSurveyOptions:
    """Derive exact survey controls from one accepted raw-count snapshot."""

    if workspace_path is None:
        return LocalDftSurveyOptions(
            status="unavailable",
            reason="workspace_unconfigured",
            message="Configure an isolated TrafficTwin v0.7 workspace to inspect DfT surveys.",
        )
    try:
        options = dft_survey_filter_options_from_snapshot(workspace_path, snapshot_id)
    except (DftSurveyViewError, DftAcquisitionError, ValidationError, OSError, ValueError):
        return LocalDftSurveyOptions(
            status="rejected",
            reason="accepted_evidence_rejected",
            message="The selected DfT snapshot failed exact local survey replay.",
        )
    return LocalDftSurveyOptions(
        status="available",
        reason="ready",
        message="Exact DfT survey filter values rebuilt from accepted local evidence.",
        options=options,
    )


def load_local_dft_survey_view(
    workspace_path: str | Path | None,
    snapshot_id: str,
    *,
    count_point_id: int,
    directions: tuple[DirectionCode, ...],
    count_date: date,
    hours: tuple[int, ...],
    vehicle_class: DftVehicleClass,
) -> LocalDftSurveyView:
    """Build one exact non-aggregated survey view from accepted local evidence."""

    if workspace_path is None:
        return LocalDftSurveyView(
            status="unavailable",
            reason="workspace_unconfigured",
            message="Configure an isolated TrafficTwin v0.7 workspace to inspect DfT surveys.",
        )
    selected_directions = tuple(sorted(set(directions)))
    selected_hours = tuple(sorted(set(hours)))
    if not selected_directions or not selected_hours:
        return LocalDftSurveyView(
            status="unavailable",
            reason="filter_selection_empty",
            message="Select at least one direction and survey-hour label.",
        )
    try:
        options = dft_survey_filter_options_from_snapshot(workspace_path, snapshot_id)
        query = DftSurveyViewQuery(
            source_report_fingerprint=options.source_report_fingerprint,
            count_point_ids=(count_point_id,),
            directions=selected_directions,
            count_dates=(count_date,),
            hours=selected_hours,
            vehicle_class=vehicle_class,
        )
        view = build_dft_survey_view_from_snapshot(
            workspace_path,
            snapshot_id,
            query,
        )
    except (DftSurveyViewError, DftAcquisitionError, ValidationError, OSError, ValueError):
        return LocalDftSurveyView(
            status="rejected",
            reason="accepted_evidence_rejected",
            message="The selected DfT survey filters failed exact local replay.",
        )
    return LocalDftSurveyView(
        status="available",
        reason="ready",
        message="DfT survey rows rebuilt from immutable accepted local evidence.",
        view=view,
    )


def dft_survey_chart_rows(view: DftSurveyView) -> list[dict[str, object]]:
    """Project discrete source rows for grouped bars; null values stay absent."""

    return [
        {
            "Source survey hour": f"{row.count_date.isoformat()} {row.hour:02d}:00",
            "Direction": row.direction,
            "Count": row.count,
        }
        for row in view.rows
    ]


def dft_survey_table_rows(view: DftSurveyView) -> list[dict[str, object]]:
    """Project source evidence without technical lineage or hidden identifiers."""

    return [
        {
            "Count point": row.count_point_id,
            "Road": row.road_name or "unreported",
            "Direction": row.direction,
            "Source date": row.count_date.isoformat(),
            "Local-clock hour": row.hour,
            "Vehicle class": row.vehicle_class.replace("_", " "),
            "Count": row.count,
            "Value state": "missing" if row.selected_value_missing else "present",
        }
        for row in view.rows
    ]


def accepted_webtris_daily_options(
    catalogue: WebtrisAcceptedSnapshotCatalogue,
) -> tuple[WebtrisAcceptedSnapshotSummary, ...]:
    """Return replayable daily reports newest-first for the exact local catalogue."""

    return tuple(
        reversed(
            tuple(
                item
                for item in catalogue.snapshots
                if item.product == "daily_report" and item.parser_replay_state == "reproduced"
            )
        )
    )


def webtris_snapshot_label(summary: WebtrisAcceptedSnapshotSummary) -> str:
    """Return a disambiguated source label without a local path or invented scope."""

    site_name = summary.site_name or "site name unavailable"
    report_date = summary.report_date.isoformat() if summary.report_date else "date unavailable"
    evidence_class = "synthetic" if summary.synthetic else "source"
    return (
        f"{site_name} · site {summary.site_id} · {report_date} · {evidence_class} · "
        f"{summary.snapshot_id[-12:]}"
    )


def load_local_webtris_timeseries(
    workspace_path: str | Path | None,
    snapshot_id: str,
    measurement_states: tuple[WebtrisMeasurementState, ...],
) -> LocalWebtrisTimeseries:
    """Reopen one accepted daily snapshot and build its exact local chart rows."""

    if workspace_path is None:
        return LocalWebtrisTimeseries(
            status="unavailable",
            reason="workspace_unconfigured",
            message="Configure an isolated TrafficTwin v0.7 workspace to inspect WebTRIS data.",
        )
    states = tuple(sorted(set(measurement_states)))
    if not states:
        return LocalWebtrisTimeseries(
            status="unavailable",
            reason="measurement_filter_empty",
            message="Select at least one measurement state to display historical intervals.",
        )
    try:
        opened = open_accepted_webtris_snapshot(workspace_path, snapshot_id)
        summary = opened.summary
        if summary.product != "daily_report" or summary.report_date is None:
            raise ValueError("selected snapshot is not a replayable daily report")
        interval_filter = WebtrisTimeseriesFilter(
            site_ids=(summary.site_id,),
            start_date=summary.report_date,
            end_date=summary.report_date,
            measurement_states=states,
        )
        result = build_webtris_timeseries_from_accepted_snapshots(
            workspace_path,
            (summary.snapshot_id,),
            interval_filter=interval_filter,
        )
    except (WebtrisAcquisitionError, WebtrisTimeseriesError, ValidationError, OSError, ValueError):
        return LocalWebtrisTimeseries(
            status="rejected",
            reason="accepted_evidence_rejected",
            message="The selected WebTRIS daily report failed exact local replay.",
        )
    return LocalWebtrisTimeseries(
        status="available",
        reason="ready",
        message="Accepted WebTRIS historical intervals rebuilt from immutable local evidence.",
        result=result,
    )


def webtris_chart_rows(result: WebtrisTimeseriesResult) -> list[dict[str, object]]:
    """Project non-aggregated chart points; missing measurements remain gaps."""

    series = build_webtris_chart_series(result)
    return [
        {
            "Source interval": f"{point.report_date.isoformat()} {point.time_period_ending_raw}",
            "Volume": point.total_volume,
            "Average speed (mph)": (
                None if point.average_speed_mph is None else float(point.average_speed_mph)
            ),
            "Measurement state": point.measurement_state,
        }
        for item in series
        for point in item.points
    ]


def assess_live_acquisition_readiness(
    workspace_path: str | Path | None,
    *,
    api_key_available: bool,
) -> LiveAcquisitionReadiness:
    """Check local prerequisites without reading or retaining a credential."""

    if workspace_path is None:
        return LiveAcquisitionReadiness(
            status="workspace_unconfigured",
            message="Configure an isolated TrafficTwin v0.7 workspace first.",
            ready=False,
        )
    try:
        inspect_v07_workspace(workspace_path)
    except V07WorkspaceError:
        return LiveAcquisitionReadiness(
            status="workspace_invalid",
            message="The configured workspace is not a valid isolated v0.7 workspace.",
            ready=False,
        )
    if not api_key_available:
        return LiveAcquisitionReadiness(
            status="api_key_missing",
            message="Set BODS_API_KEY in the app environment, then restart Streamlit.",
            ready=False,
        )
    return LiveAcquisitionReadiness(
        status="ready",
        message="Ready for one controlled BODS bus-position fetch.",
        ready=True,
    )


def assess_national_highways_acquisition_readiness(
    workspace_path: str | Path | None,
    *,
    subscription_key_available: bool,
) -> LiveAcquisitionReadiness:
    """Check operational-feed prerequisites without reading or retaining the key."""

    if workspace_path is None:
        return LiveAcquisitionReadiness(
            status="workspace_unconfigured",
            message="Configure an isolated TrafficTwin v0.7 workspace first.",
            ready=False,
        )
    try:
        inspect_v07_workspace(workspace_path)
    except V07WorkspaceError:
        return LiveAcquisitionReadiness(
            status="workspace_invalid",
            message="The configured workspace is not a valid isolated v0.7 workspace.",
            ready=False,
        )
    if not subscription_key_available:
        return LiveAcquisitionReadiness(
            status="api_key_missing",
            message=(
                "Set NATIONAL_HIGHWAYS_API_KEY in the app environment, then restart Streamlit."
            ),
            ready=False,
        )
    return LiveAcquisitionReadiness(
        status="ready",
        message="Ready for one controlled three-product National Highways refresh.",
        ready=True,
    )


def parse_bods_bounding_box(value: str) -> BodsBoundingBox:
    """Parse an explicit four-value request scope without inventing Manchester bounds."""

    parts = tuple(part.strip() for part in value.split(","))
    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError(
            "Enter four comma-separated values: min longitude, min latitude, "
            "max longitude, max latitude."
        )
    try:
        values = tuple(Decimal(part) for part in parts)
        return BodsBoundingBox(
            min_longitude=values[0],
            min_latitude=values[1],
            max_longitude=values[2],
            max_latitude=values[3],
        )
    except (InvalidOperation, ValidationError) as exc:
        raise ValueError(
            "The bounding box must contain valid ordered geographic coordinates."
        ) from exc


def scene_relative_path(mode: MapMode) -> Path:
    """Return the fixed workspace-relative scene path for one mode."""

    return MANCHESTER_SCENE_DIRECTORY / _SCENE_FILENAMES[mode]


def load_local_manchester_scene(
    workspace_path: str | Path | None,
    mode: MapMode,
) -> LocalManchesterScene:
    """Load and validate one bounded scene without exposing private paths."""

    if workspace_path is None:
        return _unavailable(
            "workspace_unconfigured",
            "Configure a TrafficTwin workspace to inspect local Manchester evidence.",
        )

    workspace = Path(workspace_path)
    base = _load_scene_artifact(workspace, workspace / scene_relative_path(mode), mode)
    overlay_path = overlay_relative_path(mode)
    if overlay_path is None:
        return base
    overlay = _load_scene_artifact(workspace, workspace / overlay_path, mode)
    if base.scene is None and overlay.scene is None:
        return overlay if overlay.status == "rejected" else base
    if base.scene is None:
        return overlay
    if overlay.scene is None:
        if overlay.status == "rejected":
            return LocalManchesterScene(
                status="available",
                reason="ready",
                message=(
                    "Validated base Manchester scene loaded; the National Highways overlay "
                    "failed integrity checks and was isolated."
                ),
                scene=base.scene,
                artifact_sha256=base.artifact_sha256,
                byte_size=base.byte_size,
            )
        return base
    try:
        scene = build_map_scene(mode, base.scene.layers + overlay.scene.layers)
    except ValueError:
        return _rejected(
            "scene_invalid",
            "The base scene and National Highways overlay could not be composed safely.",
        )
    payload = scene.canonical_json().encode("utf-8")
    return LocalManchesterScene(
        status="available",
        reason="ready",
        message="Validated local Manchester scene and National Highways overlay loaded.",
        scene=scene,
        artifact_sha256=sha256_hex(payload),
        byte_size=(base.byte_size or 0) + (overlay.byte_size or 0),
    )


def _load_scene_artifact(
    workspace: Path,
    candidate: Path,
    mode: MapMode,
) -> LocalManchesterScene:
    """Load one fixed scene member so independent sources can fail in isolation."""

    try:
        resolved_workspace = workspace.resolve()
        resolved_candidate = candidate.resolve(strict=True)
    except FileNotFoundError:
        return _unavailable(
            "scene_missing",
            "No accepted local scene is available for this evidence mode.",
        )
    except OSError:
        return _rejected("scene_read_failed", "The local scene could not be inspected safely.")

    if not resolved_candidate.is_relative_to(resolved_workspace):
        return _rejected("scene_path_escaped", "The local scene resolved outside the workspace.")
    if candidate.is_symlink():
        return _rejected(
            "scene_symlink_refused",
            "Symlinked Manchester scene artifacts are not accepted.",
        )
    if not resolved_candidate.is_file():
        return _unavailable(
            "scene_missing",
            "No accepted local scene is available for this evidence mode.",
        )

    try:
        size = resolved_candidate.stat().st_size
    except OSError:
        return _rejected("scene_read_failed", "The local scene could not be inspected safely.")
    if size == 0:
        return _rejected("scene_empty", "The local scene artifact is empty.")
    if size > MANCHESTER_SCENE_MAX_BYTES:
        return _rejected(
            "scene_too_large",
            "The local scene exceeds the bounded Manchester UI artifact size.",
        )

    try:
        payload = resolved_candidate.read_bytes()
    except OSError:
        return _rejected("scene_read_failed", "The local scene could not be read safely.")
    if len(payload) != size:
        return _rejected(
            "scene_read_failed",
            "The local scene changed while it was being read; refresh after publication completes.",
        )
    try:
        scene = ManchesterMapScene.model_validate_json(payload)
    except (ValidationError, ValueError):
        return _rejected(
            "scene_invalid",
            "The local scene failed the MAN-08 integrity contract.",
        )
    if scene.mode != mode:
        return _rejected(
            "scene_mode_mismatch",
            "The local scene does not match the selected evidence mode.",
        )
    return LocalManchesterScene(
        status="available",
        reason="ready",
        message="Validated local Manchester scene loaded.",
        scene=scene,
        artifact_sha256=sha256_hex(payload),
        byte_size=len(payload),
    )


def visible_layer_ids(scene: ManchesterMapScene) -> tuple[str, ...]:
    """Return renderable visible layer IDs in the scene's stable order."""

    return tuple(
        layer.request.layer_id
        for layer in scene.layers
        if layer.visible and layer.local_rendering_available
    )


def selected_layers(
    scene: ManchesterMapScene,
    layer_ids: tuple[str, ...],
) -> tuple[ManchesterMapLayerManifest, ...]:
    """Return an exact visible subset, rejecting unknown or unavailable IDs."""

    if len(set(layer_ids)) != len(layer_ids):
        raise ValueError("selected Manchester layer IDs must be unique")
    available = {layer.request.layer_id: layer for layer in scene.layers if layer.visible}
    unknown = sorted(set(layer_ids) - set(available))
    if unknown:
        raise ValueError(f"selected Manchester layers are unavailable: {unknown}")
    return tuple(available[layer_id] for layer_id in layer_ids)


def scene_filter_options(
    scene: ManchesterMapScene,
    layer_ids: tuple[str, ...],
) -> SceneFilterOptions:
    """Return only filter values evidenced by the exact selected layer subset."""

    layers = selected_layers(scene, layer_ids)
    return SceneFilterOptions(
        geographic_scopes=tuple(
            sorted({point.geographic_scope for layer in layers for point in layer.points})
        ),
        freshness_states=tuple(sorted({_freshness_state(layer) for layer in layers})),
    )


def filter_manchester_scene(
    scene: ManchesterMapScene,
    layer_ids: tuple[str, ...],
    *,
    geographic_scopes: tuple[GeographicScope, ...],
    freshness_states: tuple[SceneFreshnessState, ...],
) -> FilteredManchesterScene:
    """Apply exact display-only filters without mutating or aggregating evidence."""

    options = scene_filter_options(scene, layer_ids)
    _validate_filter_values(
        "geographic scopes",
        geographic_scopes,
        options.geographic_scopes,
    )
    _validate_filter_values(
        "freshness states",
        freshness_states,
        options.freshness_states,
    )
    scope_set = set(geographic_scopes)
    freshness_set = set(freshness_states)
    filtered_layers: list[FilteredManchesterLayer] = []
    for layer in selected_layers(scene, layer_ids):
        if _freshness_state(layer) not in freshness_set:
            filtered_layers.append(
                FilteredManchesterLayer(
                    manifest=layer,
                    points=(),
                    hidden_by_scope=0,
                    hidden_by_freshness=len(layer.points),
                )
            )
            continue
        points = tuple(point for point in layer.points if point.geographic_scope in scope_set)
        filtered_layers.append(
            FilteredManchesterLayer(
                manifest=layer,
                points=points,
                hidden_by_scope=len(layer.points) - len(points),
                hidden_by_freshness=0,
            )
        )
    return FilteredManchesterScene(
        scene=scene,
        layers=tuple(filtered_layers),
        selected_geographic_scopes=geographic_scopes,
        selected_freshness_states=freshness_states,
    )


def build_manchester_deck(
    scene: ManchesterMapScene,
    layer_ids: tuple[str, ...],
) -> pdk.Deck:
    """Build a no-basemap PyDeck view from display-safe admitted points only."""

    options = scene_filter_options(scene, layer_ids)
    filtered = filter_manchester_scene(
        scene,
        layer_ids,
        geographic_scopes=options.geographic_scopes,
        freshness_states=options.freshness_states,
    )
    return build_filtered_manchester_deck(filtered)


def build_boundary_layers(
    features: tuple[ManchesterBoundaryFeature, ...] | None = None,
) -> list[pdk.Layer]:
    """Return the authoritative official boundary layers.

    The two ONS December 2025 boundaries are display-only context. This is the
    single authoritative construction; callers must not duplicate colours, widths,
    or GeoJsonLayer parameters.
    """

    if features is None:
        features = load_boundary_features()
    boundary_styles: dict[str, tuple[list[int], int]] = {
        "greater_manchester_combined_authority": ([92, 104, 120, 190], 2),
        "manchester_local_authority": ([36, 78, 116, 230], 4),
    }
    layers: list[pdk.Layer] = []
    for boundary in features:
        line_colour, line_width = boundary_styles[boundary.reference.scope]
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                id=f"ons-boundary-{boundary.reference.scope}",
                data=boundary.geojson(),
                stroked=True,
                filled=False,
                get_line_color=line_colour,
                get_line_width=line_width,
                line_width_units="pixels",
                pickable=True,
            )
        )
    return layers


def build_filtered_manchester_deck(filtered: FilteredManchesterScene) -> pdk.Deck:
    """Build an offline deck with pinned official boundary context and admitted points."""

    _validate_filtered_scene(filtered)
    deck_layers: list[pdk.Layer] = build_boundary_layers()
    for filtered_layer in filtered.layers:
        layer = filtered_layer.manifest
        glyph = _SYMBOL_GLYPHS[layer.style.symbol]
        rows = [
            {
                "position": [float(point.longitude), float(point.latitude)],
                "symbol": glyph,
                "accessible_label": point.accessible_label,
                "source": layer.request.source,
                "scope": point.geographic_scope,
                "uncertainty_m": (
                    None
                    if point.coordinate_uncertainty_m is None
                    else float(point.coordinate_uncertainty_m)
                ),
            }
            for point in filtered_layer.points
        ]
        deck_layers.append(
            pdk.Layer(
                "TextLayer",
                id=f"manchester-{layer.request.layer_id}",
                data=rows,
                get_position="position",
                get_text="symbol",
                get_color=list(layer.style.fill_rgba),
                get_size=layer.style.radius_pixels * 3,
                size_units="pixels",
                get_text_anchor="middle",
                get_alignment_baseline="center",
                pickable=True,
            )
        )

    longitude, latitude, zoom = _filtered_view_state(filtered)
    return pdk.Deck(
        layers=deck_layers,
        map_provider=None,
        map_style=None,
        initial_view_state=pdk.ViewState(
            longitude=longitude,
            latitude=latitude,
            zoom=zoom,
            min_zoom=5,
            max_zoom=17,
            pitch=0,
            bearing=0,
        ),
        tooltip={
            "text": "{accessible_label}\nSource: {source}\nScope: {scope}\n"
            "Coordinate uncertainty: {uncertainty_m} m"
        },
        description=(
            "Offline Manchester evidence map. Pinned ONS boundaries provide display context; "
            "symbols identify source families. No basemap, road network, source fusion, map "
            "matching, or continuity inference is used."
        ),
    )


def filtered_source_summary_rows(
    filtered: FilteredManchesterScene,
) -> list[dict[str, object]]:
    """Return separate per-source display reconciliation without cross-source totals."""

    _validate_filtered_scene(filtered)
    return [
        {
            "Layer": layer.manifest.request.title,
            "Source": layer.manifest.request.source,
            "Evidence state": layer.manifest.status,
            "Freshness": _freshness_state(layer.manifest),
            "Accepted map points": layer.manifest.counts.points_rendered,
            "Displayed map points": len(layer.points),
            "Hidden by filters": layer.hidden_by_filters,
            "Source exclusions": layer.manifest.counts.points_excluded,
            "Displayed scope": (
                ", ".join(sorted({point.geographic_scope for point in layer.points})) or "none"
            ),
            "Publication": layer.manifest.request.publication_class.value,
            "Snapshot": layer.manifest.request.snapshot_id or "unavailable",
        }
        for layer in filtered.layers
    ]


def layer_summary_rows(scene: ManchesterMapScene) -> list[dict[str, object]]:
    """Return browser-safe layer reconciliation rows without point identifiers."""

    return [
        {
            "Layer": layer.request.title,
            "Source": layer.request.source,
            "Status": layer.status,
            "Reason": layer.reason,
            "Freshness": layer.freshness_truth_state or "not applicable",
            "Rendered points": layer.counts.points_rendered,
            "Excluded points": layer.counts.points_excluded,
            "Scope": ", ".join(sorted({point.geographic_scope for point in layer.points}))
            or "unavailable",
            "Publication": layer.request.publication_class.value,
            "Snapshot": layer.request.snapshot_id or "unavailable",
        }
        for layer in scene.layers
    ]


def _view_state(
    layers: tuple[ManchesterMapLayerManifest, ...],
) -> tuple[float, float, float]:
    bounds = tuple(layer.bounds for layer in layers if layer.bounds is not None)
    if not bounds:
        return -2.2426, 53.4808, 9.0
    minimum_longitude = min(float(item.min_longitude) for item in bounds)
    maximum_longitude = max(float(item.max_longitude) for item in bounds)
    minimum_latitude = min(float(item.min_latitude) for item in bounds)
    maximum_latitude = max(float(item.max_latitude) for item in bounds)
    span = max(maximum_longitude - minimum_longitude, maximum_latitude - minimum_latitude)
    zoom = 13.0 if span <= 0.02 else 11.0 if span <= 0.1 else 9.0 if span <= 0.5 else 7.0
    return (
        (minimum_longitude + maximum_longitude) / 2,
        (minimum_latitude + maximum_latitude) / 2,
        zoom,
    )


def _filtered_view_state(
    filtered: FilteredManchesterScene,
) -> tuple[float, float, float]:
    points = tuple(point for layer in filtered.layers for point in layer.points)
    if not points:
        return -2.2426, 53.4808, 9.0
    minimum_longitude = min(float(point.longitude) for point in points)
    maximum_longitude = max(float(point.longitude) for point in points)
    minimum_latitude = min(float(point.latitude) for point in points)
    maximum_latitude = max(float(point.latitude) for point in points)
    span = max(maximum_longitude - minimum_longitude, maximum_latitude - minimum_latitude)
    zoom = 13.0 if span <= 0.02 else 11.0 if span <= 0.1 else 9.0 if span <= 0.5 else 7.0
    return (
        (minimum_longitude + maximum_longitude) / 2,
        (minimum_latitude + maximum_latitude) / 2,
        zoom,
    )


def _freshness_state(layer: ManchesterMapLayerManifest) -> SceneFreshnessState:
    return layer.freshness_truth_state or "not_applicable"


def _validate_filter_values(
    label: str,
    selected: tuple[object, ...],
    available: tuple[object, ...],
) -> None:
    if len(set(selected)) != len(selected):
        raise ValueError(f"selected Manchester {label} must be unique")
    available_values = set(available)
    unknown = tuple(str(value) for value in selected if value not in available_values)
    if unknown:
        raise ValueError(f"selected Manchester {label} are unavailable: {unknown}")


def _validate_filtered_scene(filtered: FilteredManchesterScene) -> None:
    layer_ids = tuple(layer.manifest.request.layer_id for layer in filtered.layers)
    expected = filter_manchester_scene(
        filtered.scene,
        layer_ids,
        geographic_scopes=filtered.selected_geographic_scopes,
        freshness_states=filtered.selected_freshness_states,
    )
    if filtered != expected:
        raise ValueError("filtered Manchester scene must be exactly re-derived from its source")


def _unavailable(reason: SceneLoadReason, message: str) -> LocalManchesterScene:
    return LocalManchesterScene(status="unavailable", reason=reason, message=message)


def _rejected(reason: SceneLoadReason, message: str) -> LocalManchesterScene:
    return LocalManchesterScene(status="rejected", reason=reason, message=message)
