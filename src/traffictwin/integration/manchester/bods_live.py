"""Controlled BODS acquisition-to-map workflow for the Manchester live-vehicle view.

The workflow is deliberately narrow: one explicitly triggered authenticated BODS
request is admitted through MAN-05, its accepted private XML is re-read through the
same parser, every privacy-safe bus position passes MAN-07 spatial admission, and one
bounded MAN-08 scene atomically replaces the local ``live_vehicles`` view. It never
polls in the background and never describes transit positions as general road traffic.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.bods import (
    MAX_SIRI_BYTES,
    BodsBoundingBox,
    BodsMemberRef,
    BodsParseReport,
    BodsParseScope,
    FreshnessState,
    LiveTransitVehicleObservation,
    parse_bods_siri_vm,
)
from traffictwin.integration.manchester.bods_acquisition import (
    BODS_ATTRIBUTION_TEXT,
    BODS_FEED_MEMBER_PATH,
    BODS_LICENCE_ID,
    BodsAcquisitionRequest,
    BodsAcquisitionResult,
    acquire_bods_snapshot,
)
from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    SourceFreshnessEvaluation,
    evaluate_source_freshness,
)
from traffictwin.integration.manchester.map_layers import (
    ManchesterMapLayerManifest,
    ManchesterMapScene,
    MapLayerRequest,
    build_map_layer,
    build_map_scene,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterSnapshotModel,
    ManchesterSnapshotPolicy,
)
from traffictwin.integration.manchester.scene_publication import (
    ManchesterScenePublicationError,
    publish_map_scene_file,
)
from traffictwin.integration.manchester.snapshots import (
    ACCEPTED_DIRECTORY_NAME,
    read_manchester_member,
)
from traffictwin.integration.manchester.spatial import (
    bods_spatial_evidence,
    evaluate_spatial_batch,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

BODS_LIVE_WORKFLOW_SCHEMA_VERSION = "1.0"
BODS_LIVE_WORKFLOW_METHOD_VERSION = "manchester-bods-live-scene-1.0"
BODS_LIVE_SCENE_RELATIVE_PATH = Path("manchester/scenes/live_vehicles.json")
BODS_LIVE_SCENE_MAX_BYTES = 8 * 1024 * 1024

_LIVE_SNAPSHOT_POLICY = ManchesterSnapshotPolicy(
    max_member_count=1,
    max_member_bytes=MAX_SIRI_BYTES,
    max_total_bytes=MAX_SIRI_BYTES,
)
_ADMITTED_WARNING_CODES = ("DUPLICATE_ACTIVITY", "OUTSIDE_BOUNDING_BOX")
_STATE_LAYER: dict[FreshnessState, tuple[str, str]] = {
    "live_vehicle": ("bods-live-vehicles", "Live transit vehicles"),
    "stale": ("bods-stale-vehicles", "Stale transit observations"),
    "historical": ("bods-historical-vehicles", "Historical transit observations"),
    "synthetic": ("bods-synthetic-vehicles", "Synthetic transit fixtures"),
}


class BodsLiveWorkflowError(RuntimeError):
    """Display-safe live-workflow failure without credentials or private paths."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BodsLiveRefreshSummary(ManchesterSnapshotModel):
    """Small secret-free UI summary for one published live-vehicle scene."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    map_capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-bods-live-scene-1.0"] = "manchester-bods-live-scene-1.0"
    snapshot_id: str
    evaluated_at_utc: datetime
    acquisition_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scene_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scene_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scene_relative_path: Literal["manchester/scenes/live_vehicles.json"] = (
        "manchester/scenes/live_vehicles.json"
    )
    records_accepted: int = Field(ge=0)
    live_vehicle: int = Field(ge=0)
    stale: int = Field(ge=0)
    synthetic_records: int = Field(ge=0)
    layer_count: int = Field(ge=1, le=4)
    transit_live_available: bool
    road_traffic_live_available: Literal[False] = False
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_summary(self) -> BodsLiveRefreshSummary:
        if self.records_accepted != self.live_vehicle + self.stale + self.synthetic_records:
            raise ValueError("live refresh counts must partition accepted acquisition records")
        if self.transit_live_available != (self.live_vehicle > 0):
            raise ValueError("transit-live availability must match the live record count")
        return self


@dataclass(frozen=True, slots=True)
class BodsLiveRefresh:
    """In-memory result retaining the verified evidence used by the thin UI."""

    summary: BodsLiveRefreshSummary
    acquisition: BodsAcquisitionResult
    report: BodsParseReport
    scene: ManchesterMapScene


def refresh_bods_live_scene(
    workspace_root: str | Path,
    bounding_box: BodsBoundingBox,
    *,
    api_key: str,
    synthetic: bool = False,
    http_client: httpx.Client | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> BodsLiveRefresh:
    """Fetch once, validate, build, and atomically publish the local live-bus scene.

    ``http_client`` and ``utc_now`` are fixture seams only. The underlying MAN-05
    boundary refuses either seam whenever ``synthetic`` is false.
    """

    workspace = _validated_v07_workspace(workspace_root)
    request = BodsAcquisitionRequest(
        bounding_box=bounding_box,
        policy=_LIVE_SNAPSHOT_POLICY,
        admitted_warning_codes=_ADMITTED_WARNING_CODES,
        synthetic=synthetic,
    )
    acquisition = acquire_bods_snapshot(
        workspace,
        request,
        api_key=api_key,
        http_client=http_client,
        utc_now=utc_now,
    )
    report = _reparse_accepted_snapshot(workspace, acquisition)
    scene = build_bods_live_scene(acquisition, report)
    scene_bytes = scene.canonical_json().encode("utf-8")
    scene_sha256 = _publish_live_scene(workspace, scene_bytes)
    summary = BodsLiveRefreshSummary(
        snapshot_id=acquisition.snapshot_id,
        evaluated_at_utc=acquisition.evaluated_at_utc,
        acquisition_receipt_fingerprint=acquisition.fingerprint(),
        parser_report_fingerprint=report.fingerprint(),
        scene_fingerprint=scene.fingerprint(),
        scene_file_sha256=scene_sha256,
        records_accepted=report.counts.records_accepted,
        live_vehicle=report.counts.live_vehicle,
        stale=report.counts.stale,
        synthetic_records=report.counts.synthetic,
        layer_count=len(scene.layers),
        transit_live_available=report.counts.live_vehicle > 0,
    )
    return BodsLiveRefresh(
        summary=summary,
        acquisition=acquisition,
        report=report,
        scene=scene,
    )


def build_bods_live_scene(
    acquisition: BodsAcquisitionResult,
    report: BodsParseReport,
) -> ManchesterMapScene:
    """Convert one exactly bound MAN-05 report into state-separated MAN-08 layers."""

    _bind_report(acquisition, report)
    groups: dict[FreshnessState, list[LiveTransitVehicleObservation]] = {}
    for record in report.records:
        groups.setdefault(record.freshness_state, []).append(record)
    layers = tuple(
        _build_state_layer(acquisition, state, tuple(groups[state]))
        for state in _STATE_LAYER
        if groups.get(state)
    )
    if not layers:
        layers = (_build_state_layer(acquisition, "live_vehicle", ()),)
    return build_map_scene("live_vehicles", layers)


def _reparse_accepted_snapshot(
    workspace: Path,
    acquisition: BodsAcquisitionResult,
) -> BodsParseReport:
    accepted_dir = workspace / ACCEPTED_DIRECTORY_NAME / acquisition.snapshot_id
    payload = read_manchester_member(accepted_dir, BODS_FEED_MEMBER_PATH)
    report = parse_bods_siri_vm(
        (
            BodsMemberRef(
                snapshot_id=acquisition.snapshot_id,
                member_path=BODS_FEED_MEMBER_PATH,
                member_sha256=acquisition.feed_sha256,
                synthetic=acquisition.synthetic,
            ),
            payload,
        ),
        BodsParseScope(
            evaluated_at_utc=acquisition.evaluated_at_utc,
            mode="live",
            bounding_box=acquisition.request.bounding_box,
        ),
    )
    _bind_report(acquisition, report)
    return report


def _bind_report(acquisition: BodsAcquisitionResult, report: BodsParseReport) -> None:
    if report.fingerprint() != acquisition.parser_report_fingerprint:
        raise BodsLiveWorkflowError(
            "PARSER_REPORT_MISMATCH",
            "accepted BODS bytes no longer reproduce the acquisition parser report",
        )
    if (
        report.source.snapshot_id != acquisition.snapshot_id
        or report.source.member_sha256 != acquisition.feed_sha256
        or report.source.synthetic != acquisition.synthetic
        or report.scope.mode != "live"
        or report.scope.evaluated_at_utc != acquisition.evaluated_at_utc
        or report.scope.bounding_box != acquisition.request.bounding_box
    ):
        raise BodsLiveWorkflowError(
            "ACQUISITION_REPORT_MISMATCH",
            "BODS parser evidence does not match the admitted acquisition",
        )
    expected_counts = (
        acquisition.records_accepted,
        acquisition.live_vehicle,
        acquisition.stale,
        acquisition.synthetic_records,
    )
    observed_counts = (
        report.counts.records_accepted,
        report.counts.live_vehicle,
        report.counts.stale,
        report.counts.synthetic,
    )
    if observed_counts != expected_counts:
        raise BodsLiveWorkflowError(
            "ACQUISITION_COUNT_MISMATCH",
            "BODS parser counts do not match the admitted acquisition",
        )


def _build_state_layer(
    acquisition: BodsAcquisitionResult,
    state: FreshnessState,
    records: Sequence[LiveTransitVehicleObservation],
) -> ManchesterMapLayerManifest:
    layer_id, title = _STATE_LAYER[state]
    request_bounds_fingerprint = acquisition.request.bounding_box.fingerprint()
    spatial = evaluate_spatial_batch(
        tuple(
            bods_spatial_evidence(
                record,
                request_bounds_fingerprint=request_bounds_fingerprint,
            )
            for record in records
        )
    )
    freshness = _layer_freshness(acquisition, state, records)
    return build_map_layer(
        MapLayerRequest(
            layer_id=layer_id,
            title=title,
            mode="live_vehicles",
            source="bods_siri_vm",
            snapshot_id=acquisition.snapshot_id,
            snapshot_fingerprint=acquisition.fingerprint(),
            spatial_report=spatial,
            freshness=freshness,
            publication_class=ManchesterPublicationClass.PRIVATE,
            licence_id=BODS_LICENCE_ID,
            attribution_lines=(BODS_ATTRIBUTION_TEXT,),
            synthetic=acquisition.synthetic,
        )
    )


def _layer_freshness(
    acquisition: BodsAcquisitionResult,
    state: FreshnessState,
    records: Sequence[LiveTransitVehicleObservation],
) -> SourceFreshnessEvaluation:
    representative = records[0] if records else None
    freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="bods_siri_vm",
            evidence_validation=acquisition.parser_status,
            snapshot_available=True,
            use_mode="live",
            evaluated_at_utc=acquisition.evaluated_at_utc,
            observed_at_utc=(None if representative is None else representative.recorded_at_utc),
            valid_until_utc=(None if representative is None else representative.valid_until_utc),
            synthetic=acquisition.synthetic,
        )
    )
    expected_state = "unavailable" if representative is None else state
    if freshness.truth_state != expected_state:
        raise BodsLiveWorkflowError(
            "FRESHNESS_RECONCILIATION_FAILED",
            "layer freshness does not match the admitted BODS records",
        )
    return freshness


def _validated_v07_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise BodsLiveWorkflowError(
            "WORKSPACE_INVALID",
            "configure a valid isolated v0.7 workspace before acquiring live evidence",
        ) from exc
    return workspace.resolve(strict=True)


def _publish_live_scene(workspace: Path, payload: bytes) -> str:
    if not payload or len(payload) > BODS_LIVE_SCENE_MAX_BYTES:
        raise BodsLiveWorkflowError(
            "SCENE_SIZE_REFUSED",
            "the live-vehicle scene is empty or exceeds the bounded local display size",
        )
    try:
        scene = ManchesterMapScene.model_validate_json(payload)
    except ValueError as exc:
        raise BodsLiveWorkflowError(
            "SCENE_INVALID",
            "the live-scene payload is not a valid Manchester map scene",
        ) from exc
    if scene.mode != "live_vehicles" or scene.canonical_json().encode("utf-8") != payload:
        raise BodsLiveWorkflowError(
            "SCENE_INVALID",
            "the payload must be the canonical live-vehicle scene representation",
        )
    try:
        publication = publish_map_scene_file(workspace, scene)
    except ManchesterScenePublicationError as exc:
        raise BodsLiveWorkflowError(
            exc.code,
            "the validated live scene could not be published to the local workspace",
        ) from exc
    return publication.file_sha256
