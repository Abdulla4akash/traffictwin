"""Accepted DfT count-point snapshots to source-separated MAN-08 map layers.

This offline boundary re-verifies an accepted MAN-02 count-point snapshot,
replays its exact parser, applies MAN-07 dual-coordinate admission, and builds
one historical/latest MAN-08 reference layer. It does not acquire data, map raw
counts or AADF values, infer observation time, or claim live road conditions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from traffictwin.integration.manchester.dft import DftCountPointParseReport
from traffictwin.integration.manchester.dft_acquisition import (
    DFT_ATTRIBUTION_TEXT,
    DFT_LICENCE_ID,
    DftAcquisitionError,
    DftAcquisitionResult,
    load_accepted_dft_report,
)
from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    evaluate_source_freshness,
)
from traffictwin.integration.manchester.map_layers import (
    OGL_V3_URI,
    MapLayerRequest,
    MapLayerStatus,
    build_map_layer,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterSnapshotModel,
)
from traffictwin.integration.manchester.scene_publication import (
    HistoricalSceneMode,
    ManchesterScenePublicationReceipt,
    ManchesterScenePublicationRequest,
    publish_historical_scene,
)
from traffictwin.integration.manchester.spatial import (
    SpatialAdmissionReport,
    dft_spatial_evidence,
    evaluate_spatial_batch,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

DFT_SCENE_SCHEMA_VERSION = "1.0"
DFT_SCENE_METHOD_VERSION = "manchester-dft-scene-1.0"
DFT_COUNT_POINT_LAYER_ID = "dft-count-points"


class DftSceneError(RuntimeError):
    """Display-safe refusal from the accepted DfT-to-scene bridge."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class DftCountPointLayerSummary(ManchesterSnapshotModel):
    """Reconciled boundary for one accepted Manchester count-point snapshot."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-02"] = "MAN-02"
    spatial_capability_id: Literal["MAN-07"] = "MAN-07"
    map_capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-dft-scene-1.0"] = "manchester-dft-scene-1.0"
    mode: HistoricalSceneMode
    layer_id: Literal["dft-count-points"] = "dft-count-points"
    snapshot_id: str
    acquisition_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    spatial_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    layer_request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    distinct_count_points: int = Field(ge=0)
    spatial_admitted: int = Field(ge=0)
    spatial_excluded: int = Field(ge=0)
    layer_status: MapLayerStatus
    publication_class: ManchesterPublicationClass
    public_export_available: bool
    synthetic: bool
    evidence_kind: Literal["count_point_reference"] = "count_point_reference"
    raw_count_values_included: Literal[False] = False
    aadf_values_included: Literal[False] = False
    source_time_promoted_to_utc: Literal[False] = False
    live_road_traffic_available: Literal[False] = False
    cross_source_join_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_summary(self) -> DftCountPointLayerSummary:
        if self.distinct_count_points != self.records_accepted:
            raise ValueError("the reference layer requires one record per count-point identity")
        if self.records_accepted != self.spatial_admitted + self.spatial_excluded:
            raise ValueError("spatial counts must reconcile every accepted count point")
        if self.rows_seen < self.records_accepted:
            raise ValueError("accepted records cannot exceed parser rows seen")
        expected_status: MapLayerStatus = (
            "unavailable"
            if not self.spatial_admitted
            else "partial"
            if self.spatial_excluded
            else "available"
        )
        if self.layer_status != expected_status:
            raise ValueError("layer status must reconcile count-point spatial admission")
        expected_export = expected_status != "unavailable" and self.publication_class in {
            ManchesterPublicationClass.REDISTRIBUTABLE_RAW,
            ManchesterPublicationClass.REDISTRIBUTABLE_DERIVED,
        }
        if self.public_export_available != expected_export:
            raise ValueError("public export must follow status and publication class")
        return self


@dataclass(frozen=True, slots=True)
class DftCountPointLayerBuild:
    """Verified in-memory count-point evidence retained for review/composition."""

    summary: DftCountPointLayerSummary
    acquisition: DftAcquisitionResult
    parser_report: DftCountPointParseReport
    spatial_report: SpatialAdmissionReport
    layer_request: MapLayerRequest


@dataclass(frozen=True, slots=True)
class DftScenePublication:
    """The verified DfT layer and its atomic MAN-08 publication receipt."""

    layer: DftCountPointLayerBuild
    publication: ManchesterScenePublicationReceipt


def build_dft_count_point_layer(
    workspace_root: str | Path,
    acquisition: DftAcquisitionResult,
    *,
    mode: HistoricalSceneMode,
    evaluated_at_utc: datetime,
) -> DftCountPointLayerBuild:
    """Replay one accepted count-point product into one historical reference layer."""

    workspace = _validated_v07_workspace(workspace_root)
    admitted = _validated_acquisition(acquisition)
    if admitted.dataset != "count_points":
        raise DftSceneError(
            "DATASET_REFUSED",
            "the map bridge accepts only a DfT count-point reference acquisition",
        )
    report = _read_and_parse_accepted(workspace, admitted)
    count_point_ids = tuple(record.count_point_id for record in report.records)
    if len(set(count_point_ids)) != len(count_point_ids):
        raise DftSceneError(
            "COUNT_POINT_IDENTITY_CONFLICT",
            "the accepted reference set has multiple records for one count-point identity",
        )
    spatial = evaluate_spatial_batch(tuple(dft_spatial_evidence(row) for row in report.records))
    freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="dft_count_points",
            evidence_validation=report.status,
            snapshot_available=True,
            use_mode="historical",
            evaluated_at_utc=evaluated_at_utc,
            synthetic=admitted.synthetic,
        )
    )
    layer_request = MapLayerRequest(
        layer_id=DFT_COUNT_POINT_LAYER_ID,
        title="DfT Manchester road count-point references",
        mode=mode,
        source="dft",
        snapshot_id=admitted.snapshot_id,
        snapshot_fingerprint=admitted.fingerprint(),
        spatial_report=spatial,
        freshness=freshness,
        publication_class=admitted.request.publication_class,
        licence_id=DFT_LICENCE_ID,
        licence_uri=OGL_V3_URI,
        attribution_lines=(DFT_ATTRIBUTION_TEXT,),
        synthetic=admitted.synthetic,
    )
    layer = build_map_layer(layer_request)
    summary = DftCountPointLayerSummary(
        mode=mode,
        snapshot_id=admitted.snapshot_id,
        acquisition_fingerprint=admitted.fingerprint(),
        parser_report_fingerprint=report.fingerprint(),
        spatial_report_fingerprint=spatial.fingerprint(),
        layer_request_fingerprint=layer_request.fingerprint(),
        rows_seen=report.counts.rows_seen,
        records_accepted=report.counts.records_accepted,
        distinct_count_points=len(set(count_point_ids)),
        spatial_admitted=spatial.counts.admitted,
        spatial_excluded=spatial.counts.excluded,
        layer_status=layer.status,
        publication_class=admitted.request.publication_class,
        public_export_available=layer.public_export_available,
        synthetic=admitted.synthetic,
    )
    return DftCountPointLayerBuild(
        summary=summary,
        acquisition=admitted,
        parser_report=report,
        spatial_report=spatial,
        layer_request=layer_request,
    )


def publish_dft_count_point_scene(
    workspace_root: str | Path,
    acquisition: DftAcquisitionResult,
    *,
    mode: HistoricalSceneMode,
    evaluated_at_utc: datetime,
    additional_layer_requests: Sequence[MapLayerRequest] = (),
) -> DftScenePublication:
    """Publish the verified DfT reference layer with optional separate layers."""

    layer = build_dft_count_point_layer(
        workspace_root,
        acquisition,
        mode=mode,
        evaluated_at_utc=evaluated_at_utc,
    )
    requests = tuple(
        sorted((*additional_layer_requests, layer.layer_request), key=lambda item: item.layer_id)
    )
    try:
        request = ManchesterScenePublicationRequest(mode=mode, layer_requests=requests)
    except ValidationError as exc:
        raise DftSceneError(
            "SCENE_COMPOSITION_REFUSED",
            "the requested source-separated scene inventory is invalid",
        ) from exc
    publication = publish_historical_scene(workspace_root, request)
    return DftScenePublication(layer=layer, publication=publication)


def _validated_v07_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise DftSceneError(
            "WORKSPACE_INVALID",
            "configure a valid isolated v0.7 workspace before building a DfT layer",
        ) from exc
    return workspace.resolve(strict=True)


def _validated_acquisition(acquisition: DftAcquisitionResult) -> DftAcquisitionResult:
    try:
        return DftAcquisitionResult.model_validate_json(acquisition.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise DftSceneError(
            "ACQUISITION_INVALID",
            "the supplied DfT acquisition receipt failed internal validation",
        ) from exc


def _read_and_parse_accepted(
    workspace: Path,
    acquisition: DftAcquisitionResult,
) -> DftCountPointParseReport:
    try:
        report = load_accepted_dft_report(workspace, acquisition)
    except DftAcquisitionError as exc:
        code = {
            "ACCEPTED_SNAPSHOT_MISMATCH": "ACCEPTED_SNAPSHOT_MISMATCH",
            "ACCEPTED_PARSER_MISMATCH": "PARSER_REPORT_MISMATCH",
            "ACCEPTED_PARSER_REJECTED": "PARSER_REPLAY_REJECTED",
            "PARSE_INTEGRITY": "PARSER_REPLAY_FAILED",
        }.get(exc.code, "ACCEPTED_SNAPSHOT_INVALID")
        raise DftSceneError(
            code,
            "the accepted DfT evidence could not be reproduced for the map layer",
        ) from exc
    if not isinstance(report, DftCountPointParseReport):
        raise DftSceneError(
            "DATASET_REFUSED",
            "the accepted DfT report is not a count-point reference dataset",
        )
    return report
