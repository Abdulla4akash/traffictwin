"""Accepted WebTRIS site snapshots to source-separated MAN-08 map layers.

This module is an offline orchestration boundary. It re-verifies one accepted
MAN-03 site snapshot, replays the existing site parser, binds the returned site
identity to the selected endpoint identity, applies MAN-07 spatial admission,
and builds one historical/latest MAN-08 layer. It never acquires data, turns a
retrieval instant into an observation instant, or places daily traffic values
on a point that was obtained from a separate response.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

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
    MANIFEST_FILE_NAME,
    ManchesterPublicationClass,
    ManchesterSnapshotManifest,
    ManchesterSnapshotModel,
    ManchesterValidationState,
    sha256_hex,
)
from traffictwin.integration.manchester.scene_publication import (
    HistoricalSceneMode,
    ManchesterScenePublicationReceipt,
    ManchesterScenePublicationRequest,
    publish_historical_scene,
)
from traffictwin.integration.manchester.snapshots import (
    ACCEPTED_DIRECTORY_NAME,
    ManchesterSnapshotError,
    read_manchester_member,
    verify_manchester_snapshot,
)
from traffictwin.integration.manchester.spatial import (
    SpatialAdmissionReport,
    evaluate_spatial_batch,
    webtris_spatial_evidence,
)
from traffictwin.integration.manchester.webtris import (
    WebtrisAdapterError,
    WebtrisMemberRef,
    WebtrisSiteParseReport,
    parse_webtris_site,
)
from traffictwin.integration.manchester.webtris_acquisition import (
    WEBTRIS_ATTRIBUTION_TEXT,
    WEBTRIS_LICENCE_ID,
    WebtrisAcquisitionResult,
    decode_webtris_http_payload,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

WEBTRIS_SCENE_SCHEMA_VERSION = "1.0"
WEBTRIS_SCENE_METHOD_VERSION = "manchester-webtris-scene-1.0"
WEBTRIS_SITE_MEMBER_PATH = "site/site.json"


class WebtrisSceneError(RuntimeError):
    """Display-safe refusal from the accepted WebTRIS-to-scene bridge."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class WebtrisSiteLayerSummary(ManchesterSnapshotModel):
    """Reconciled scientific boundary for one selected strategic-road site."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-03"] = "MAN-03"
    spatial_capability_id: Literal["MAN-07"] = "MAN-07"
    map_capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-webtris-scene-1.0"] = "manchester-webtris-scene-1.0"
    mode: HistoricalSceneMode
    site_id: str = Field(pattern=r"^[1-9][0-9]{0,9}$")
    layer_id: str = Field(pattern=r"^webtris-site-[1-9][0-9]{0,9}$")
    snapshot_id: str
    acquisition_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    spatial_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    layer_request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    spatial_admitted: int = Field(ge=0)
    spatial_excluded: int = Field(ge=0)
    layer_status: MapLayerStatus
    publication_class: ManchesterPublicationClass
    public_export_available: bool
    synthetic: bool
    evidence_kind: Literal["strategic_road_site_reference"] = "strategic_road_site_reference"
    daily_traffic_values_included: Literal[False] = False
    source_time_promoted_to_utc: Literal[False] = False
    live_road_traffic_available: Literal[False] = False
    cross_source_join_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_summary(self) -> WebtrisSiteLayerSummary:
        if self.layer_id != f"webtris-site-{self.site_id}":
            raise ValueError("layer ID must bind the selected WebTRIS site")
        if self.records_accepted != 1:
            raise ValueError("one selected-site layer requires exactly one accepted site record")
        if self.records_accepted != self.spatial_admitted + self.spatial_excluded:
            raise ValueError("spatial counts must reconcile the selected site record")
        if self.rows_seen < self.records_accepted:
            raise ValueError("accepted records cannot exceed parser rows seen")
        expected_status: MapLayerStatus = (
            "available" if self.spatial_admitted == 1 else "unavailable"
        )
        if self.layer_status != expected_status:
            raise ValueError("layer status must reconcile selected-site spatial admission")
        expected_export = expected_status == "available" and self.publication_class in {
            ManchesterPublicationClass.REDISTRIBUTABLE_RAW,
            ManchesterPublicationClass.REDISTRIBUTABLE_DERIVED,
        }
        if self.public_export_available != expected_export:
            raise ValueError("public export must follow status and publication class")
        return self


@dataclass(frozen=True, slots=True)
class WebtrisSiteLayerBuild:
    """Verified in-memory evidence retained for composition and review."""

    summary: WebtrisSiteLayerSummary
    acquisition: WebtrisAcquisitionResult
    parser_report: WebtrisSiteParseReport
    spatial_report: SpatialAdmissionReport
    layer_request: MapLayerRequest


@dataclass(frozen=True, slots=True)
class WebtrisScenePublication:
    """All verified WebTRIS site layers and their atomic scene receipt."""

    layers: tuple[WebtrisSiteLayerBuild, ...]
    publication: ManchesterScenePublicationReceipt


def build_webtris_site_layer(
    workspace_root: str | Path,
    acquisition: WebtrisAcquisitionResult,
    *,
    mode: HistoricalSceneMode,
    evaluated_at_utc: datetime,
) -> WebtrisSiteLayerBuild:
    """Replay one accepted site product into one source-separated map layer."""

    workspace = _validated_v07_workspace(workspace_root)
    admitted = _validated_acquisition(acquisition)
    if admitted.product != "site":
        raise WebtrisSceneError(
            "PRODUCT_REFUSED",
            "the map bridge accepts only a WebTRIS site-reference acquisition",
        )
    report = _read_and_parse_accepted(workspace, admitted)
    if len(report.records) != 1 or report.records[0].site_id != admitted.request.site_id:
        raise WebtrisSceneError(
            "SITE_SCOPE_MISMATCH",
            "the accepted site response does not contain exactly the selected site ID",
        )
    selection_fingerprint = admitted.request.fingerprint()
    spatial = evaluate_spatial_batch(
        (
            webtris_spatial_evidence(
                report.records[0],
                selection_fingerprint=selection_fingerprint,
            ),
        )
    )
    freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="webtris_daily",
            evidence_validation=report.status,
            snapshot_available=True,
            use_mode="historical",
            evaluated_at_utc=evaluated_at_utc,
            synthetic=admitted.synthetic,
        )
    )
    layer_id = f"webtris-site-{admitted.request.site_id}"
    layer_request = MapLayerRequest(
        layer_id=layer_id,
        title=f"WebTRIS strategic-road site {admitted.request.site_id}",
        mode=mode,
        source="webtris",
        snapshot_id=admitted.snapshot_id,
        snapshot_fingerprint=admitted.fingerprint(),
        spatial_report=spatial,
        freshness=freshness,
        publication_class=admitted.request.publication_class,
        licence_id=WEBTRIS_LICENCE_ID,
        licence_uri=OGL_V3_URI,
        attribution_lines=(WEBTRIS_ATTRIBUTION_TEXT,),
        synthetic=admitted.synthetic,
    )
    layer = build_map_layer(layer_request)
    summary = WebtrisSiteLayerSummary(
        mode=mode,
        site_id=admitted.request.site_id,
        layer_id=layer_id,
        snapshot_id=admitted.snapshot_id,
        acquisition_fingerprint=admitted.fingerprint(),
        parser_report_fingerprint=report.fingerprint(),
        spatial_report_fingerprint=spatial.fingerprint(),
        layer_request_fingerprint=layer_request.fingerprint(),
        rows_seen=report.counts.rows_seen,
        records_accepted=report.counts.records_accepted,
        spatial_admitted=spatial.counts.admitted,
        spatial_excluded=spatial.counts.excluded,
        layer_status=layer.status,
        publication_class=admitted.request.publication_class,
        public_export_available=layer.public_export_available,
        synthetic=admitted.synthetic,
    )
    return WebtrisSiteLayerBuild(
        summary=summary,
        acquisition=admitted,
        parser_report=report,
        spatial_report=spatial,
        layer_request=layer_request,
    )


def publish_webtris_site_scene(
    workspace_root: str | Path,
    acquisitions: Sequence[WebtrisAcquisitionResult],
    *,
    mode: HistoricalSceneMode,
    evaluated_at_utc: datetime,
    additional_layer_requests: Sequence[MapLayerRequest] = (),
) -> WebtrisScenePublication:
    """Publish one or more independently replayed site layers without fusion."""

    if not acquisitions:
        raise WebtrisSceneError("NO_SITES", "at least one accepted site acquisition is required")
    layers = tuple(
        sorted(
            (
                build_webtris_site_layer(
                    workspace_root,
                    acquisition,
                    mode=mode,
                    evaluated_at_utc=evaluated_at_utc,
                )
                for acquisition in acquisitions
            ),
            key=lambda item: item.summary.layer_id,
        )
    )
    site_ids = tuple(layer.summary.site_id for layer in layers)
    if len(set(site_ids)) != len(site_ids):
        raise WebtrisSceneError(
            "DUPLICATE_SITE",
            "each WebTRIS site may appear at most once in one scene",
        )
    requests = tuple(
        sorted(
            (*additional_layer_requests, *(layer.layer_request for layer in layers)),
            key=lambda item: item.layer_id,
        )
    )
    try:
        publication_request = ManchesterScenePublicationRequest(
            mode=mode,
            layer_requests=requests,
        )
    except ValidationError as exc:
        raise WebtrisSceneError(
            "SCENE_COMPOSITION_REFUSED",
            "the requested source-separated scene inventory is invalid",
        ) from exc
    publication = publish_historical_scene(workspace_root, publication_request)
    return WebtrisScenePublication(layers=layers, publication=publication)


def _validated_v07_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise WebtrisSceneError(
            "WORKSPACE_INVALID",
            "configure a valid isolated v0.7 workspace before building a WebTRIS layer",
        ) from exc
    return workspace.resolve(strict=True)


def _validated_acquisition(acquisition: WebtrisAcquisitionResult) -> WebtrisAcquisitionResult:
    try:
        return WebtrisAcquisitionResult.model_validate_json(acquisition.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise WebtrisSceneError(
            "ACQUISITION_INVALID",
            "the supplied WebTRIS acquisition receipt failed internal validation",
        ) from exc


def _read_and_parse_accepted(
    workspace: Path,
    acquisition: WebtrisAcquisitionResult,
) -> WebtrisSiteParseReport:
    accepted = workspace / ACCEPTED_DIRECTORY_NAME / acquisition.snapshot_id
    try:
        snapshot_receipt = verify_manchester_snapshot(accepted)
        snapshot_manifest = ManchesterSnapshotManifest.model_validate_json(
            (accepted / MANIFEST_FILE_NAME).read_bytes()
        )
        payload = read_manchester_member(accepted, WEBTRIS_SITE_MEMBER_PATH)
    except (ManchesterSnapshotError, ValidationError, OSError) as exc:
        raise WebtrisSceneError(
            "ACCEPTED_SNAPSHOT_INVALID",
            "the accepted WebTRIS snapshot could not be re-verified",
        ) from exc
    if (
        snapshot_receipt.fingerprint() != acquisition.snapshot_receipt_fingerprint
        or snapshot_manifest.snapshot_id != acquisition.snapshot_id
        or snapshot_manifest.source.source_id != acquisition.source_id
        or snapshot_manifest.raw_fingerprint != acquisition.raw_fingerprint
        or snapshot_manifest.members != acquisition.members
        or snapshot_manifest.publication_class != acquisition.request.publication_class
        or snapshot_manifest.licence_id != WEBTRIS_LICENCE_ID
        or snapshot_manifest.attribution_text != WEBTRIS_ATTRIBUTION_TEXT
        or snapshot_manifest.synthetic != acquisition.synthetic
    ):
        raise WebtrisSceneError(
            "ACCEPTED_SNAPSHOT_MISMATCH",
            "the accepted snapshot receipt does not match the acquisition receipt",
        )
    member = acquisition.members[0]
    if snapshot_manifest.http is None:
        raise WebtrisSceneError(
            "ACCEPTED_SNAPSHOT_MISMATCH",
            "the accepted WebTRIS site has no bounded HTTP metadata",
        )
    parser_payload = decode_webtris_http_payload(
        payload,
        content_encoding=snapshot_manifest.http.response_content_encoding,
    )
    content_encoding = snapshot_manifest.http.response_content_encoding
    reference = WebtrisMemberRef(
        snapshot_id=acquisition.snapshot_id,
        member_path=member.relative_path,
        member_sha256=member.sha256,
        content_encoding="gzip" if content_encoding == "gzip" else "identity",
        parser_payload_sha256=(sha256_hex(parser_payload) if content_encoding == "gzip" else None),
        member_role="site",
        page_number=1,
        synthetic=acquisition.synthetic,
    )
    try:
        report = parse_webtris_site((reference, parser_payload))
    except WebtrisAdapterError as exc:
        raise WebtrisSceneError(
            "PARSER_REPLAY_FAILED",
            "the accepted WebTRIS site no longer passes the admitted parser contract",
        ) from exc
    if (
        report.fingerprint() != acquisition.parser_report_fingerprint
        or report.counts.rows_seen != acquisition.rows_seen
        or report.counts.records_accepted != acquisition.records_accepted
        or report.counts.intervals_missing != acquisition.intervals_missing
        or report.status is not acquisition.parser_status
    ):
        raise WebtrisSceneError(
            "PARSER_REPORT_MISMATCH",
            "the accepted WebTRIS site does not reproduce the acquisition parser report",
        )
    if report.status is ManchesterValidationState.REJECTED:
        raise WebtrisSceneError(
            "PARSER_REPLAY_REJECTED",
            "a rejected WebTRIS parser report cannot reach the map",
        )
    return report
