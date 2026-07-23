"""Offline tests for receipt-free accepted WebTRIS discovery and replay."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_webtris_acquisition import (
    REPORT_DATE,
    SITE_ID,
    SITE_NAME,
    acquire,
    default_responses,
    full_day_rows,
    make_request,
    paged,
)
from traffictwin.integration.manchester.webtris import (
    WebtrisDailyParseReport,
    WebtrisSiteParseReport,
)
from traffictwin.integration.manchester.webtris_acquisition import (
    WebtrisAcceptedSnapshotCatalogue,
    WebtrisAcquisitionError,
    catalogue_accepted_webtris_snapshots,
    open_accepted_webtris_snapshot,
)
from traffictwin.release.compatibility import initialise_v07_workspace


def _workspace(tmp_path: Path) -> Path:
    return initialise_v07_workspace(tmp_path / "workspace-v0.7").path


def test_empty_and_three_product_catalogues_are_bounded_and_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    empty = catalogue_accepted_webtris_snapshots(workspace)
    assert empty.snapshots == ()
    assert empty.counts.total == 0

    acquired = {
        product: acquire(workspace, make_request(product))
        for product in ("site", "daily_report", "daily_quality")
    }

    def refuse_socket(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("accepted WebTRIS catalogue must not use the network")

    monkeypatch.setattr(socket, "socket", refuse_socket)
    catalogue = catalogue_accepted_webtris_snapshots(workspace)

    assert tuple(item.product for item in catalogue.snapshots) == (
        "daily_quality",
        "daily_report",
        "site",
    )
    assert catalogue.counts.site == 1
    assert catalogue.counts.daily_report == 1
    assert catalogue.counts.daily_quality == 1
    assert catalogue.counts.parser_reproduced == 2
    assert catalogue.counts.parser_scope_unavailable == 1
    assert catalogue.counts.total == 3

    opened_daily = open_accepted_webtris_snapshot(workspace, acquired["daily_report"].snapshot_id)
    assert isinstance(opened_daily.report, WebtrisDailyParseReport)
    assert opened_daily.summary.site_id == SITE_ID
    assert opened_daily.summary.site_name == SITE_NAME
    assert opened_daily.summary.report_date == REPORT_DATE
    assert opened_daily.summary.page_size == 96
    assert opened_daily.summary.parser_report_fingerprint == opened_daily.report.fingerprint()

    opened_site = open_accepted_webtris_snapshot(workspace, acquired["site"].snapshot_id)
    assert isinstance(opened_site.report, WebtrisSiteParseReport)
    assert opened_site.summary.site_name == "Synthetic MIDAS site fixture"

    opened_quality = open_accepted_webtris_snapshot(
        workspace, acquired["daily_quality"].snapshot_id
    )
    assert opened_quality.report is None
    assert opened_quality.summary.site_name is None
    assert opened_quality.summary.site_name_basis == "not_present_in_product"
    assert opened_quality.summary.parser_replay_state == "scope_unavailable"
    assert opened_quality.summary.parser_report_fingerprint is None


def test_catalogue_refuses_unsafe_ids_symlinks_and_fixed_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import traffictwin.integration.manchester.webtris_acquisition as module

    workspace = _workspace(tmp_path)
    result = acquire(workspace, make_request("site"))

    with pytest.raises(WebtrisAcquisitionError) as unsafe:
        open_accepted_webtris_snapshot(workspace, "../accepted/escape")
    assert unsafe.value.code == "SNAPSHOT_ID_INVALID"

    unrelated = workspace / "accepted" / "dft_raw_counts-20260723T120000Z-abcdef012345"
    unrelated.mkdir()
    assert catalogue_accepted_webtris_snapshots(workspace).counts.total == 1

    monkeypatch.setattr(module, "WEBTRIS_ACCEPTED_CATALOGUE_MAX_SNAPSHOTS", 0)
    with pytest.raises(WebtrisAcquisitionError) as limited:
        catalogue_accepted_webtris_snapshots(workspace)
    assert limited.value.code == "ACCEPTED_CATALOGUE_LIMIT"

    monkeypatch.setattr(module, "WEBTRIS_ACCEPTED_CATALOGUE_MAX_SNAPSHOTS", 512)
    target = tmp_path / "outside"
    target.mkdir()
    unsafe_link = workspace / "accepted" / "webtris_site-20260723T120000Z-abcdef012345"
    unsafe_link.symlink_to(target, target_is_directory=True)
    with pytest.raises(WebtrisAcquisitionError) as symlinked:
        catalogue_accepted_webtris_snapshots(workspace)
    assert symlinked.value.code == "ACCEPTED_SNAPSHOT_INVALID"
    assert symlinked.value.accepted_snapshot_id == unsafe_link.name
    assert result.snapshot_id != unsafe_link.name


def test_catalogue_models_reconcile_product_and_replay_counts(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    acquire(workspace, make_request("daily_report"))
    catalogue = catalogue_accepted_webtris_snapshots(workspace)
    payload = catalogue.model_dump(mode="python")
    payload["counts"]["daily_report"] = 0

    with pytest.raises(ValidationError, match="product totals|catalogue counts"):
        WebtrisAcceptedSnapshotCatalogue.model_validate(payload)


def test_catalogue_refuses_tampered_accepted_bytes(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    result = acquire(workspace, make_request("daily_report"))
    target = workspace / "accepted" / result.snapshot_id / "raw" / "pages" / "page-0001.json"
    payload = target.read_bytes()
    changed = payload.replace(b'"Total Volume": "1"', b'"Total Volume": "2"', 1)
    assert changed != payload and len(changed) == len(payload)
    target.chmod(0o600)
    target.write_bytes(changed)

    with pytest.raises(WebtrisAcquisitionError) as tampered:
        open_accepted_webtris_snapshot(workspace, result.snapshot_id)
    assert tampered.value.code == "ACCEPTED_SNAPSHOT_INVALID"
    assert tampered.value.accepted_snapshot_id == result.snapshot_id


def test_catalogue_requires_an_isolated_v07_workspace(tmp_path: Path) -> None:
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()

    with pytest.raises(WebtrisAcquisitionError) as invalid:
        catalogue_accepted_webtris_snapshots(ordinary)
    assert invalid.value.code == "WORKSPACE_INVALID"


def test_multi_page_warning_accepted_report_reproduces_exact_findings(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    responses = default_responses()
    responses["daily"] = paged(full_day_rows(missing_intervals={7}), 48)
    result = acquire(
        workspace,
        make_request(
            "daily_report",
            page_size=48,
            admitted_warning_codes=("MISSING_INTERVAL_MEASUREMENTS",),
        ),
        responses,
    )

    opened = open_accepted_webtris_snapshot(workspace, result.snapshot_id)

    assert isinstance(opened.report, WebtrisDailyParseReport)
    assert opened.summary.pages == 2
    assert opened.summary.page_size == 48
    assert opened.summary.intervals_missing == 1
    assert opened.summary.stored_validation_state.value == "accepted_with_warnings"
    assert opened.summary.parser_report_fingerprint == result.parser_report_fingerprint
