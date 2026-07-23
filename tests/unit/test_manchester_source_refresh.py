"""Tests for explicit source-refresh orchestration and scene preservation."""

from __future__ import annotations

import gzip
import json
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_map_layers import request as layer_request
from traffictwin.integration.manchester.scene_publication import (
    ManchesterScenePublicationRequest,
    publish_historical_scene,
)
from traffictwin.integration.manchester.source_refresh import (
    DftSourceRefreshSummary,
    ManchesterSourceRefreshError,
    TfgmSourceRefreshSummary,
    WebtrisSourceRefreshSummary,
    _existing_layer_requests,
)
from traffictwin.integration.manchester.webtris import WebtrisMemberRef, parse_webtris_site
from traffictwin.integration.manchester.webtris_acquisition import (
    WebtrisAcquisitionError,
    decode_webtris_http_payload,
)
from traffictwin.release.compatibility import initialise_v07_workspace


def _workspace(tmp_path: Path) -> Path:
    return initialise_v07_workspace(tmp_path / "workspace-v0.7").path


def test_existing_scene_preserves_only_unrelated_source_layers(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    requests = tuple(
        sorted(
            (
                layer_request(layer_id="tfgm-signal-locations", title="TfGM"),
                layer_request(layer_id="webtris-site-34", title="WebTRIS 34"),
                layer_request(layer_id="webtris-site-100", title="WebTRIS 100"),
            ),
            key=lambda item: item.layer_id,
        )
    )
    publish_historical_scene(
        workspace,
        ManchesterScenePublicationRequest(
            mode="latest_available",
            layer_requests=requests,
        ),
    )

    preserved = _existing_layer_requests(
        workspace,
        "latest_available",
        replaced_layer_ids={"webtris-site-34"},
        replaced_layer_prefixes=("webtris-site-",),
    )

    assert tuple(item.layer_id for item in preserved) == ("tfgm-signal-locations",)


def test_missing_scene_is_an_empty_composition(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    assert (
        _existing_layer_requests(
            workspace,
            "historical_replay",
            replaced_layer_ids={"dft-count-points"},
        )
        == ()
    )


def test_unsafe_existing_scene_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    scene_dir = workspace / "manchester/scenes"
    scene_dir.mkdir(parents=True)
    target = scene_dir / "latest_available.json"
    target.symlink_to(workspace / "workspace-manifest.json")

    with pytest.raises(ManchesterSourceRefreshError) as excinfo:
        _existing_layer_requests(
            workspace,
            "latest_available",
            replaced_layer_ids=set(),
        )

    assert excinfo.value.code == "SCENE_PATH_REFUSED"


def test_refresh_summaries_make_unsupported_live_claims_unrepresentable() -> None:
    webtris = WebtrisSourceRefreshSummary(
        site_id="34",
        site_name="M56/8150A",
        report_date=date(2026, 3, 1),
        site_snapshot_id="site-snapshot",
        daily_snapshot_id="daily-snapshot",
        quality_snapshot_id="quality-snapshot",
        intervals_accepted=96,
        intervals_missing=0,
        daily_parser_status="accepted",
        daily_warning_codes=(),
        quality_rows_accepted=1,
        scene_fingerprint="a" * 64,
    )
    tfgm = TfgmSourceRefreshSummary(
        snapshot_id="signals-snapshot",
        records_accepted=2_529,
        spatial_admitted=2_529,
        spatial_excluded=0,
        scene_fingerprint="b" * 64,
    )
    dft = DftSourceRefreshSummary(
        raw_count_snapshot_id="raw-snapshot",
        count_point_snapshot_id="point-snapshot",
        aadf_snapshot_id="aadf-snapshot",
        raw_count_records=1,
        count_point_records=1,
        aadf_records=1,
        scene_fingerprint="c" * 64,
    )

    assert webtris.live_road_traffic_available is False
    assert webtris.source_time_promoted_to_utc is False
    assert tfgm.live_state_available is False
    assert dft.live_road_traffic_available is False
    with pytest.raises(ValidationError):
        WebtrisSourceRefreshSummary.model_validate(
            {**webtris.model_dump(mode="json"), "live_road_traffic_available": True}
        )
    with pytest.raises(ValidationError):
        TfgmSourceRefreshSummary.model_validate(
            {**tfgm.model_dump(mode="json"), "live_state_available": True}
        )
    with pytest.raises(ValidationError):
        DftSourceRefreshSummary.model_validate(
            {**dft.model_dump(mode="json"), "live_road_traffic_available": True}
        )


def test_webtris_gzip_keeps_wire_hash_and_binds_decoded_parser_bytes() -> None:
    parser_payload = json.dumps(
        {
            "row_count": 1,
            "sites": [
                {
                    "Id": "34",
                    "Name": "M56 northbound",
                    "Description": "M56/8150A",
                    "Longitude": "-2.3075",
                    "Latitude": "53.3578",
                    "Status": "Active",
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    wire_payload = gzip.compress(parser_payload, mtime=0)

    decoded = decode_webtris_http_payload(wire_payload, content_encoding="gzip")
    reference = WebtrisMemberRef(
        snapshot_id="webtris_site-20260723T120000Z-" + "a" * 12,
        member_path="site/site.json",
        member_sha256=sha256(wire_payload).hexdigest(),
        content_encoding="gzip",
        parser_payload_sha256=sha256(decoded).hexdigest(),
        member_role="site",
        synthetic=False,
    )
    report = parse_webtris_site((reference, decoded))

    assert report.counts.records_accepted == 1
    assert report.records[0].site_id == "34"
    with pytest.raises(WebtrisAcquisitionError) as excinfo:
        decode_webtris_http_payload(wire_payload, content_encoding="deflate")
    assert excinfo.value.code == "CONTENT_ENCODING_REJECTED"
