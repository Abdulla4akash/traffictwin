"""Explicit real-source refresh workflows for the Manchester operations UI.

These workflows are deliberately operator-triggered.  They compose the existing
bounded acquisition, immutable snapshot, parser, spatial, and scene-publication
boundaries without adding background polling or changing source semantics:

* WebTRIS is one selected strategic-road site/day (latest-available or historical).
* TfGM is a static traffic-signal location reference, never live signal state.
* DfT is selected historical survey/reference evidence, never live road traffic.

Every published map keeps already-admitted, source-separated layers unless the
same source layer is being replaced.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from traffictwin.integration.manchester.dft import MAX_MEMBER_JSON_BYTES
from traffictwin.integration.manchester.dft_acquisition import (
    DftAcquisitionRequest,
    DftAcquisitionResult,
    DftDataset,
    acquire_dft_snapshot,
)
from traffictwin.integration.manchester.dft_scene import (
    DFT_COUNT_POINT_LAYER_ID,
    publish_dft_count_point_scene,
)
from traffictwin.integration.manchester.map_layers import (
    ManchesterMapScene,
    MapLayerRequest,
    MapMode,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterSnapshotModel,
    ManchesterSnapshotPolicy,
)
from traffictwin.integration.manchester.scene_publication import MANCHESTER_SCENE_MAX_BYTES
from traffictwin.integration.manchester.tfgm_acquisition import (
    TFGM_ARCHIVE_POLICY,
    TfgmAcquisitionRequest,
    acquire_tfgm_signals_snapshot,
)
from traffictwin.integration.manchester.tfgm_scene import (
    TFGM_SCENE_LAYER_ID,
    publish_tfgm_latest_scene,
)
from traffictwin.integration.manchester.webtris import (
    MAX_MEMBER_BYTES,
    WebtrisDailyParseReport,
    WebtrisSiteParseReport,
)
from traffictwin.integration.manchester.webtris_acquisition import (
    WebtrisAcquisitionRequest,
    acquire_webtris_snapshot,
    open_accepted_webtris_snapshot,
)
from traffictwin.integration.manchester.webtris_scene import publish_webtris_site_scene
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

MANCHESTER_SOURCE_REFRESH_SCHEMA_VERSION = "1.0"
MANCHESTER_SOURCE_REFRESH_METHOD_VERSION = "manchester-source-refresh-1.0"

_WEBTRIS_POLICY = ManchesterSnapshotPolicy(
    max_member_count=4,
    max_member_bytes=MAX_MEMBER_BYTES,
    max_total_bytes=4 * MAX_MEMBER_BYTES,
)
_DFT_POLICY = ManchesterSnapshotPolicy(
    max_member_count=2,
    max_member_bytes=MAX_MEMBER_JSON_BYTES,
    max_total_bytes=2 * MAX_MEMBER_JSON_BYTES,
)
_TFGM_POLICY = ManchesterSnapshotPolicy(
    max_member_count=1,
    max_member_bytes=TFGM_ARCHIVE_POLICY.max_compressed_bytes,
    max_total_bytes=TFGM_ARCHIVE_POLICY.max_compressed_bytes,
)


class ManchesterSourceRefreshError(RuntimeError):
    """Display-safe orchestration refusal for an explicit source refresh."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class WebtrisSourceRefreshSummary(ManchesterSnapshotModel):
    """Small receipt for one explicit three-product WebTRIS site/day refresh."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-03"] = "MAN-03"
    method_version: Literal["manchester-source-refresh-1.0"] = "manchester-source-refresh-1.0"
    site_id: str = Field(pattern=r"^[1-9][0-9]{0,9}$")
    site_name: str
    report_date: date
    site_snapshot_id: str
    daily_snapshot_id: str
    quality_snapshot_id: str
    intervals_accepted: int = Field(ge=0)
    intervals_missing: int = Field(ge=0)
    daily_parser_status: Literal["accepted", "accepted_with_warnings"]
    daily_warning_codes: tuple[str, ...]
    quality_rows_accepted: int = Field(ge=0)
    scene_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    road_domain: Literal["national_highways_strategic_road"] = "national_highways_strategic_road"
    live_road_traffic_available: Literal[False] = False
    source_time_promoted_to_utc: Literal[False] = False


class TfgmSourceRefreshSummary(ManchesterSnapshotModel):
    """Small receipt for one static TfGM signal-location refresh."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-04"] = "MAN-04"
    method_version: Literal["manchester-source-refresh-1.0"] = "manchester-source-refresh-1.0"
    snapshot_id: str
    records_accepted: int = Field(ge=0)
    spatial_admitted: int = Field(ge=0)
    spatial_excluded: int = Field(ge=0)
    scene_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_kind: Literal["static_traffic_signal_reference"] = "static_traffic_signal_reference"
    live_state_available: Literal[False] = False


class DftSourceRefreshSummary(ManchesterSnapshotModel):
    """Small receipt for selected historical DfT rows and their map reference."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-02"] = "MAN-02"
    method_version: Literal["manchester-source-refresh-1.0"] = "manchester-source-refresh-1.0"
    raw_count_snapshot_id: str
    count_point_snapshot_id: str
    aadf_snapshot_id: str
    raw_count_records: int = Field(ge=0)
    count_point_records: int = Field(ge=0)
    aadf_records: int = Field(ge=0)
    scene_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_kind: Literal["historical_survey_and_reference"] = "historical_survey_and_reference"
    live_road_traffic_available: Literal[False] = False


def refresh_webtris_site_day(
    workspace_root: str | Path,
    *,
    site_id: str,
    report_date: date,
) -> WebtrisSourceRefreshSummary:
    """Fetch one WebTRIS site, daily report, and quality response, then update the map."""

    workspace = _validated_workspace(workspace_root)
    site = acquire_webtris_snapshot(
        workspace,
        WebtrisAcquisitionRequest(
            product="site",
            site_id=site_id,
            max_pages=1,
            policy=_WEBTRIS_POLICY,
            publication_class=ManchesterPublicationClass.PRIVATE,
            synthetic=False,
        ),
    )
    opened = open_accepted_webtris_snapshot(workspace, site.snapshot_id)
    report = opened.report
    if not isinstance(report, WebtrisSiteParseReport) or len(report.records) != 1:
        raise ManchesterSourceRefreshError(
            "WEBTRIS_SITE_REPLAY_FAILED",
            "the accepted site response did not reproduce exactly one selected site",
        )
    site_name = report.records[0].description
    daily = acquire_webtris_snapshot(
        workspace,
        WebtrisAcquisitionRequest(
            product="daily_report",
            site_id=site_id,
            site_name=site_name,
            report_date=report_date,
            page_size=96,
            max_pages=4,
            policy=_WEBTRIS_POLICY,
            publication_class=ManchesterPublicationClass.PRIVATE,
            admitted_warning_codes=(
                "LENGTH_TOTAL_MISMATCH",
                "MISSING_INTERVAL_MEASUREMENTS",
            ),
            synthetic=False,
        ),
    )
    opened_daily = open_accepted_webtris_snapshot(workspace, daily.snapshot_id)
    daily_report = opened_daily.report
    if not isinstance(daily_report, WebtrisDailyParseReport):
        raise ManchesterSourceRefreshError(
            "WEBTRIS_DAILY_REPLAY_FAILED",
            "the accepted daily response did not reproduce its parser report",
        )
    quality = acquire_webtris_snapshot(
        workspace,
        WebtrisAcquisitionRequest(
            product="daily_quality",
            site_id=site_id,
            site_name=site_name,
            report_date=report_date,
            max_pages=1,
            policy=_WEBTRIS_POLICY,
            publication_class=ManchesterPublicationClass.PRIVATE,
            synthetic=False,
        ),
    )
    existing = _existing_layer_requests(
        workspace,
        "latest_available",
        replaced_layer_ids={f"webtris-site-{site_id}"},
        replaced_layer_prefixes=("webtris-site-",),
    )
    published = publish_webtris_site_scene(
        workspace,
        (site,),
        mode="latest_available",
        evaluated_at_utc=datetime.now(UTC),
        additional_layer_requests=existing,
    )
    daily_parser_status: Literal["accepted", "accepted_with_warnings"] = (
        "accepted" if daily.parser_status.value == "accepted" else "accepted_with_warnings"
    )
    return WebtrisSourceRefreshSummary(
        site_id=site_id,
        site_name=site_name,
        report_date=report_date,
        site_snapshot_id=site.snapshot_id,
        daily_snapshot_id=daily.snapshot_id,
        quality_snapshot_id=quality.snapshot_id,
        intervals_accepted=daily.records_accepted,
        intervals_missing=daily.intervals_missing,
        daily_parser_status=daily_parser_status,
        daily_warning_codes=tuple(
            sorted(
                finding.code
                for finding in daily_report.findings
                if finding.severity.value == "warning"
            )
        ),
        quality_rows_accepted=quality.records_accepted,
        scene_fingerprint=published.publication.scene_fingerprint,
    )


def refresh_tfgm_signal_locations(
    workspace_root: str | Path,
) -> TfgmSourceRefreshSummary:
    """Fetch the audited TfGM static archive and update its latest-available layer."""

    workspace = _validated_workspace(workspace_root)
    acquisition = acquire_tfgm_signals_snapshot(
        workspace,
        TfgmAcquisitionRequest(
            policy=_TFGM_POLICY,
            admitted_warning_codes=("KRN_MISSING",),
            synthetic=False,
        ),
    )
    existing = _existing_layer_requests(
        workspace,
        "latest_available",
        replaced_layer_ids={TFGM_SCENE_LAYER_ID},
    )
    published = publish_tfgm_latest_scene(
        workspace,
        acquisition,
        evaluated_at_utc=datetime.now(UTC),
        additional_layer_requests=existing,
    )
    summary = published.layer.summary
    return TfgmSourceRefreshSummary(
        snapshot_id=acquisition.snapshot_id,
        records_accepted=summary.records_accepted,
        spatial_admitted=summary.spatial_admitted,
        spatial_excluded=summary.spatial_excluded,
        scene_fingerprint=published.publication.scene_fingerprint,
    )


def refresh_dft_historical_rows(
    workspace_root: str | Path,
    *,
    raw_count_row_id: int,
    count_point_row_id: int,
    aadf_row_id: int,
) -> DftSourceRefreshSummary:
    """Fetch three selected Manchester DfT row identities and publish the reference point."""

    workspace = _validated_workspace(workspace_root)
    requested_rows: tuple[tuple[DftDataset, int], ...] = (
        ("raw_counts", raw_count_row_id),
        ("count_points", count_point_row_id),
        ("aadf", aadf_row_id),
    )
    results: dict[DftDataset, DftAcquisitionResult] = {
        dataset: acquire_dft_snapshot(
            workspace,
            DftAcquisitionRequest(
                dataset=dataset,
                filter_id=filter_id,
                page_size=1,
                max_pages=2,
                max_rows=2,
                policy=_DFT_POLICY,
                publication_class=ManchesterPublicationClass.PRIVATE,
                accept_with_warnings=False,
                synthetic=False,
            ),
        )
        for dataset, filter_id in requested_rows
    }
    existing = _existing_layer_requests(
        workspace,
        "historical_replay",
        replaced_layer_ids={DFT_COUNT_POINT_LAYER_ID},
    )
    count_point = results["count_points"]
    published = publish_dft_count_point_scene(
        workspace,
        count_point,
        mode="historical_replay",
        evaluated_at_utc=datetime.now(UTC),
        additional_layer_requests=existing,
    )
    return DftSourceRefreshSummary(
        raw_count_snapshot_id=results["raw_counts"].snapshot_id,
        count_point_snapshot_id=count_point.snapshot_id,
        aadf_snapshot_id=results["aadf"].snapshot_id,
        raw_count_records=results["raw_counts"].records_accepted,
        count_point_records=count_point.records_accepted,
        aadf_records=results["aadf"].records_accepted,
        scene_fingerprint=published.publication.scene_fingerprint,
    )


def _existing_layer_requests(
    workspace: Path,
    mode: MapMode,
    *,
    replaced_layer_ids: set[str],
    replaced_layer_prefixes: tuple[str, ...] = (),
) -> tuple[MapLayerRequest, ...]:
    """Re-open an existing bounded scene and retain unrelated source requests."""

    target = workspace / "manchester" / "scenes" / f"{mode}.json"
    if target.is_symlink():
        raise ManchesterSourceRefreshError(
            "SCENE_PATH_REFUSED", "the existing scene is not a safe regular file"
        )
    if not target.exists():
        return ()
    if not target.is_file():
        raise ManchesterSourceRefreshError(
            "SCENE_PATH_REFUSED", "the existing scene is not a safe regular file"
        )
    payload = target.read_bytes()
    if not payload or len(payload) > MANCHESTER_SCENE_MAX_BYTES:
        raise ManchesterSourceRefreshError(
            "SCENE_SIZE_REFUSED", "the existing scene exceeds the bounded display size"
        )
    try:
        scene = ManchesterMapScene.model_validate_json(payload)
    except ValueError as exc:
        raise ManchesterSourceRefreshError(
            "SCENE_REPLAY_FAILED", "the existing scene failed exact local validation"
        ) from exc
    if scene.mode != mode:
        raise ManchesterSourceRefreshError(
            "SCENE_MODE_MISMATCH", "the existing scene mode does not match its fixed path"
        )
    return tuple(
        layer.request
        for layer in scene.layers
        if layer.request.layer_id not in replaced_layer_ids
        and not any(layer.request.layer_id.startswith(prefix) for prefix in replaced_layer_prefixes)
    )


def _validated_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise ManchesterSourceRefreshError(
            "WORKSPACE_INVALID",
            "configure a valid isolated v0.7 workspace before refreshing source evidence",
        ) from exc
    return workspace.resolve(strict=True)
