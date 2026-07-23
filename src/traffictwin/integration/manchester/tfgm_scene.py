"""Accepted TfGM signal snapshot to private latest-available map scene.

This is a local, explicit orchestration boundary. It re-verifies an admitted
MAN-04 acquisition, re-reads and re-parses its accepted ZIP, applies MAN-07
spatial admission, builds one MAN-08 static-reference layer, and optionally
publishes a latest-available scene. It performs no acquisition or network I/O
and cannot represent signal phase, timing, queues, counts, incidents, or live
state.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from traffictwin.integration.manchester.archive import ManchesterArchiveError, read_bounded_zip
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
    ManchesterValidationState,
    sha256_hex,
)
from traffictwin.integration.manchester.scene_publication import (
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
    tfgm_signal_spatial_evidence,
)
from traffictwin.integration.manchester.tfgm_acquisition import (
    TFGM_ARCHIVE_POLICY,
    TFGM_CSV_ARCHIVE_MEMBER,
    TFGM_LICENCE_ID,
    TFGM_OGL_ARCHIVE_MEMBER,
    TFGM_ZIP_MEMBER_PATH,
    TfgmAcquisitionResult,
)
from traffictwin.integration.manchester.tfgm_signals import (
    TFGM_SIGNALS_ATTRIBUTION,
    TfgmSignalAdapterError,
    TfgmSignalMemberRef,
    TfgmSignalParseReport,
    parse_tfgm_signal_csv,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

TFGM_SCENE_SCHEMA_VERSION = "1.0"
TFGM_SCENE_METHOD_VERSION = "manchester-tfgm-scene-1.0"
TFGM_SCENE_LAYER_ID = "tfgm-signal-locations"


class TfgmSceneError(RuntimeError):
    """Display-safe refusal from the accepted-snapshot-to-scene bridge."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TfgmSignalLayerSummary(ManchesterSnapshotModel):
    """Small reconciled summary of one accepted TfGM layer build."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-04"] = "MAN-04"
    map_capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-tfgm-scene-1.0"] = "manchester-tfgm-scene-1.0"
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
    publication_class: Literal["private"] = "private"
    evidence_kind: Literal["static_traffic_signal_reference"] = "static_traffic_signal_reference"
    live_state_available: Literal[False] = False
    phase_available: Literal[False] = False
    timing_available: Literal[False] = False
    traffic_count_available: Literal[False] = False
    public_export_available: Literal[False] = False
    synthetic: bool

    @model_validator(mode="after")
    def validate_summary(self) -> TfgmSignalLayerSummary:
        if self.records_accepted != self.spatial_admitted + self.spatial_excluded:
            raise ValueError("spatial counts must reconcile every accepted signal record")
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
            raise ValueError("layer status must reconcile spatial admission")
        return self


@dataclass(frozen=True, slots=True)
class TfgmSignalLayerBuild:
    """In-memory verified evidence retained for lead review and composition."""

    summary: TfgmSignalLayerSummary
    acquisition: TfgmAcquisitionResult
    parser_report: TfgmSignalParseReport
    spatial_report: SpatialAdmissionReport
    layer_request: MapLayerRequest


@dataclass(frozen=True, slots=True)
class TfgmLatestScenePublication:
    """The verified source bridge plus its atomic MAN-08 publication receipt."""

    layer: TfgmSignalLayerBuild
    publication: ManchesterScenePublicationReceipt


def build_tfgm_signal_layer(
    workspace_root: str | Path,
    acquisition: TfgmAcquisitionResult,
    *,
    evaluated_at_utc: datetime,
) -> TfgmSignalLayerBuild:
    """Re-verify accepted bytes and build one private static signal layer request."""

    workspace = _validated_v07_workspace(workspace_root)
    admitted = _validated_acquisition(acquisition)
    report = _read_and_parse_accepted(workspace, admitted)
    spatial = evaluate_spatial_batch(
        tuple(tfgm_signal_spatial_evidence(record) for record in report.records)
    )
    freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="tfgm_signals",
            evidence_validation=report.status,
            snapshot_available=True,
            use_mode="historical",
            evaluated_at_utc=evaluated_at_utc,
            synthetic=admitted.synthetic,
        )
    )
    layer_request = MapLayerRequest(
        layer_id=TFGM_SCENE_LAYER_ID,
        title="TfGM traffic-signal locations",
        mode="latest_available",
        source="tfgm_signals",
        snapshot_id=admitted.snapshot_id,
        snapshot_fingerprint=admitted.fingerprint(),
        spatial_report=spatial,
        freshness=freshness,
        publication_class=ManchesterPublicationClass.PRIVATE,
        licence_id=TFGM_LICENCE_ID,
        licence_uri=OGL_V3_URI,
        attribution_lines=(TFGM_SIGNALS_ATTRIBUTION,),
        synthetic=admitted.synthetic,
    )
    layer = build_map_layer(layer_request)
    summary = TfgmSignalLayerSummary(
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
        synthetic=admitted.synthetic,
    )
    return TfgmSignalLayerBuild(
        summary=summary,
        acquisition=admitted,
        parser_report=report,
        spatial_report=spatial,
        layer_request=layer_request,
    )


def publish_tfgm_latest_scene(
    workspace_root: str | Path,
    acquisition: TfgmAcquisitionResult,
    *,
    evaluated_at_utc: datetime,
    additional_layer_requests: Sequence[MapLayerRequest] = (),
) -> TfgmLatestScenePublication:
    """Explicitly publish a latest scene containing TfGM and optional separate layers."""

    layer = build_tfgm_signal_layer(
        workspace_root,
        acquisition,
        evaluated_at_utc=evaluated_at_utc,
    )
    requests = tuple(
        sorted((*additional_layer_requests, layer.layer_request), key=lambda item: item.layer_id)
    )
    publication = publish_historical_scene(
        workspace_root,
        ManchesterScenePublicationRequest(
            mode="latest_available",
            layer_requests=requests,
        ),
    )
    return TfgmLatestScenePublication(layer=layer, publication=publication)


def _validated_v07_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise TfgmSceneError(
            "WORKSPACE_INVALID",
            "configure a valid isolated v0.7 workspace before building a TfGM layer",
        ) from exc
    return workspace.resolve(strict=True)


def _validated_acquisition(acquisition: TfgmAcquisitionResult) -> TfgmAcquisitionResult:
    try:
        return TfgmAcquisitionResult.model_validate_json(acquisition.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise TfgmSceneError(
            "ACQUISITION_INVALID",
            "the supplied TfGM acquisition receipt failed internal validation",
        ) from exc


def _read_and_parse_accepted(
    workspace: Path,
    acquisition: TfgmAcquisitionResult,
) -> TfgmSignalParseReport:
    accepted = workspace / ACCEPTED_DIRECTORY_NAME / acquisition.snapshot_id
    try:
        snapshot_receipt = verify_manchester_snapshot(accepted)
        zip_payload = read_manchester_member(accepted, TFGM_ZIP_MEMBER_PATH)
    except ManchesterSnapshotError as exc:
        raise TfgmSceneError(
            "ACCEPTED_SNAPSHOT_INVALID",
            "the accepted TfGM snapshot could not be re-verified",
        ) from exc
    if snapshot_receipt != acquisition.snapshot_receipt:
        raise TfgmSceneError(
            "ACCEPTED_SNAPSHOT_MISMATCH",
            "the accepted snapshot receipt does not match the acquisition receipt",
        )
    if sha256_hex(zip_payload) != acquisition.zip_sha256:
        raise TfgmSceneError(
            "ACCEPTED_SNAPSHOT_MISMATCH",
            "the accepted ZIP does not match the acquisition receipt",
        )
    try:
        contents = read_bounded_zip(
            zip_payload,
            policy=TFGM_ARCHIVE_POLICY,
            selected_members=(TFGM_CSV_ARCHIVE_MEMBER, TFGM_OGL_ARCHIVE_MEMBER),
        )
    except ManchesterArchiveError as exc:
        raise TfgmSceneError(
            "ACCEPTED_ARCHIVE_INVALID",
            "the accepted TfGM ZIP failed bounded archive validation",
        ) from exc
    if contents.members != acquisition.zip_members:
        raise TfgmSceneError(
            "ACCEPTED_ARCHIVE_MISMATCH",
            "the accepted ZIP inventory does not match the acquisition receipt",
        )
    csv_payload = contents.selected[TFGM_CSV_ARCHIVE_MEMBER]
    attribution_payload = contents.selected[TFGM_OGL_ARCHIVE_MEMBER]
    if (
        sha256_hex(csv_payload) != acquisition.csv_member.sha256
        or len(csv_payload) != acquisition.csv_member.byte_size
        or sha256_hex(attribution_payload) != acquisition.attribution_member.sha256
        or len(attribution_payload) != acquisition.attribution_member.byte_size
    ):
        raise TfgmSceneError(
            "ACCEPTED_ARCHIVE_MISMATCH",
            "selected TfGM members do not match the acquisition receipt",
        )
    evidence_class: Literal["full_official_csv", "redistributable_derived_sample"] = (
        "redistributable_derived_sample" if acquisition.synthetic else "full_official_csv"
    )
    reference = TfgmSignalMemberRef(
        snapshot_id=acquisition.snapshot_id,
        member_path=TFGM_CSV_ARCHIVE_MEMBER,
        member_sha256=acquisition.csv_sha256,
        evidence_class=evidence_class,
        synthetic=acquisition.synthetic,
    )
    try:
        report = parse_tfgm_signal_csv((reference, csv_payload))
    except TfgmSignalAdapterError as exc:
        raise TfgmSceneError(
            "PARSER_REPLAY_FAILED",
            "the accepted TfGM CSV no longer passes the admitted parser contract",
        ) from exc
    if (
        report.fingerprint() != acquisition.parser_report_fingerprint
        or report.counts.rows_seen != acquisition.rows_seen
        or report.counts.records_accepted != acquisition.records_accepted
        or report.counts.rows_malformed != acquisition.rows_malformed
        or report.status is not acquisition.parser_status
        or tuple(sorted({finding.code for finding in report.findings}))
        != acquisition.parser_warning_codes
    ):
        raise TfgmSceneError(
            "PARSER_REPORT_MISMATCH",
            "the accepted TfGM CSV does not reproduce the acquisition parser report",
        )
    if report.status is ManchesterValidationState.REJECTED:
        raise TfgmSceneError(
            "PARSER_REPORT_REJECTED",
            "rejected TfGM evidence cannot become a map layer",
        )
    return report
