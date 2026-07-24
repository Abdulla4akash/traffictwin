"""Tests for the metadata-only Manchester live-status export."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal, cast

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.bods_live import BodsLiveRefreshSummary
from traffictwin.integration.manchester.bods_live_control import (
    BodsLiveControlState,
    initial_bods_live_control_state,
)
from traffictwin.integration.manchester.live_status_export import (
    ManchesterLiveStatusExport,
    build_live_status_export,
)
from traffictwin.integration.manchester.national_highways_live import (
    NationalHighwaysControlState,
    NationalHighwaysProductSummary,
    NationalHighwaysRefreshSummary,
    initial_national_highways_control_state,
)

_NOW = datetime(2026, 7, 24, 10, tzinfo=UTC)


def _bods_summary() -> BodsLiveRefreshSummary:
    return BodsLiveRefreshSummary(
        snapshot_id="bods-private-snapshot",
        evaluated_at_utc=_NOW,
        acquisition_receipt_fingerprint="a" * 64,
        parser_report_fingerprint="b" * 64,
        scene_fingerprint="c" * 64,
        scene_file_sha256="d" * 64,
        records_accepted=7,
        live_vehicle=4,
        stale=2,
        synthetic_records=1,
        bee_network_franchised=3,
        non_franchised_or_unknown=4,
        membership_out_of_scope=0,
        membership_missing_identifier=0,
        membership_ambiguous_identifier=0,
        bee_network_policy_fingerprint="e" * 64,
        bee_network_membership_report_fingerprint="f" * 64,
        layer_count=2,
        transit_live_available=True,
    )


def _bods_state(
    *, status: Literal["succeeded", "in_progress"] = "succeeded"
) -> BodsLiveControlState:
    summary = _bods_summary()
    return BodsLiveControlState(
        attempts_total=1,
        successes_total=1 if status == "succeeded" else 0,
        failures_total=0,
        last_attempt_at_utc=_NOW,
        last_attempt_status=status,
        last_request_scope_fingerprint="1" * 64,
        latest_success=summary if status == "succeeded" else None,
        history=(summary,) if status == "succeeded" else (),
        history_entry_count=1 if status == "succeeded" else 0,
    )


def _nh_summary() -> NationalHighwaysRefreshSummary:
    products = tuple(
        NationalHighwaysProductSummary(
            product=cast(Literal["closures", "speed_limits", "vms"], product),
            snapshot_id=f"private-{product}",
            publication_time_utc=_NOW,
            source_items_seen=count,
            records_accepted=count,
            outside_envelope=0,
            coordinates_missing=0,
            exact_duplicates_collapsed=0,
            raw_sha256=character * 64,
            report_fingerprint=character * 64,
        )
        for product, count, character in (
            ("closures", 2, "a"),
            ("speed_limits", 3, "b"),
            ("vms", 4, "c"),
        )
    )
    return NationalHighwaysRefreshSummary(
        evaluated_at_utc=_NOW,
        products=products,
        total_records_accepted=9,
        latest_scene_sha256="d" * 64,
        live_overlay_sha256="e" * 64,
    )


def _nh_state() -> NationalHighwaysControlState:
    summary = _nh_summary()
    return NationalHighwaysControlState(
        attempts_total=1,
        successes_total=1,
        failures_total=0,
        last_attempt_at_utc=_NOW,
        last_attempt_status="succeeded",
        history=(summary,),
        history_entry_count=1,
    )


def test_initial_states_export_only_unavailable_source_metadata() -> None:
    result = build_live_status_export(
        generated_at_utc=_NOW,
        bods=initial_bods_live_control_state(),
        national_highways=initial_national_highways_control_state(),
    )

    assert tuple(source.status for source in result.sources) == (
        "never_attempted",
        "never_attempted",
    )
    assert all(not source.metrics for source in result.sources)
    assert result.local_metadata_download_available is True
    assert result.public_metadata_hosting_accepted is False
    assert result.public_raw_snapshot_available is False
    assert result.public_live_scene_hosting_accepted is False


def test_successful_states_export_only_fixed_aggregate_metrics() -> None:
    result = build_live_status_export(
        generated_at_utc=_NOW,
        bods=_bods_state(),
        national_highways=_nh_state(),
    )
    payload = result.canonical_json()
    loaded = ManchesterLiveStatusExport.model_validate_json(payload)

    assert loaded == result
    assert [metric.value for metric in result.sources[0].metrics] == [7, 4, 2, 1]
    assert [metric.value for metric in result.sources[1].metrics] == [2, 3, 4]
    for forbidden in (
        "bods-private-snapshot",
        "private-closures",
        "private-speed_limits",
        "private-vms",
        "VehicleRef",
        "BNDB",
        "api_key",
        "subscription_key",
        "longitude",
        "latitude",
    ):
        assert forbidden not in payload


def test_in_progress_bods_state_is_not_mislabeled_as_failure() -> None:
    result = build_live_status_export(
        generated_at_utc=_NOW,
        bods=_bods_state(status="in_progress"),
        national_highways=initial_national_highways_control_state(),
    )

    assert result.sources[0].status == "in_progress_without_success"
    assert not result.sources[0].metrics


def test_literal_publication_refusals_cannot_be_enabled() -> None:
    result = build_live_status_export(
        generated_at_utc=_NOW,
        bods=_bods_state(),
        national_highways=_nh_state(),
    )
    document = json.loads(result.canonical_json())
    document["public_position_export_available"] = True
    with pytest.raises(ValidationError):
        ManchesterLiveStatusExport.model_validate(document)

    document = json.loads(result.canonical_json())
    document["complete_manchester_coverage_available"] = True
    with pytest.raises(ValidationError):
        ManchesterLiveStatusExport.model_validate(document)

    document = json.loads(result.canonical_json())
    document["public_metadata_hosting_accepted"] = True
    with pytest.raises(ValidationError):
        ManchesterLiveStatusExport.model_validate(document)


def test_aggregate_mutation_and_non_utc_time_are_rejected() -> None:
    result = build_live_status_export(
        generated_at_utc=_NOW,
        bods=_bods_state(),
        national_highways=_nh_state(),
    )
    document = json.loads(result.canonical_json())
    document["sources"][0]["metrics"][0]["value"] = 99
    with pytest.raises(ValidationError):
        ManchesterLiveStatusExport.model_validate(document)

    with pytest.raises(ValidationError):
        build_live_status_export(
            generated_at_utc=datetime(2026, 7, 24, 10),
            bods=initial_bods_live_control_state(),
            national_highways=initial_national_highways_control_state(),
        )

    document = json.loads(result.canonical_json())
    document["generated_at_utc"] = "2026-07-23T10:00:00Z"
    with pytest.raises(ValidationError):
        ManchesterLiveStatusExport.model_validate(document)
