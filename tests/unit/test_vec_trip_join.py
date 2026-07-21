"""Synthetic golden and refusal tests for VEC-05."""

from __future__ import annotations

import gzip

import numpy as np
import pytest

from tests.tos_v2_helpers import (
    V2_SCENARIO,
    build_v2_occupancy_rows,
    build_v2_trace,
    build_v2_tripinfo_records,
)
from traffictwin.integration.vec_identity import (
    VecIdentitySnapshot,
    build_vehicle_identity_snapshot,
)
from traffictwin.integration.vec_trip_join import (
    VecTripExclusionKind,
    VecTripJoinError,
    build_trip_join_dataset,
    vec_trip_join_contract,
)


def _identity() -> VecIdentitySnapshot:
    header, rows = build_v2_occupancy_rows()
    return build_vehicle_identity_snapshot(build_v2_trace(), header, rows, scenario=V2_SCENARIO)


def _tripinfo() -> bytes:
    rows = "".join(
        (
            f'<tripinfo id="{item["id"]}" depart="{item["depart"]}" '
            f'arrival="{item["arrival"]}" duration="{item["duration"]}" '
            f'routeLength="{item["routeLength"]}"/>'
        )
        for item in build_v2_tripinfo_records()
    )
    return gzip.compress(f"<tripinfos>{rows}</tripinfos>".encode(), mtime=0)


def test_exact_id_join_preserves_clock_exclusions_and_cohort() -> None:
    payload = _tripinfo()
    dataset = build_trip_join_dataset(
        build_v2_trace(),
        _identity(),
        payload,
        source_path="tripinfo/synthetic.xml.gz",
    )

    assert dataset.report.matched_vehicle_count == 2
    assert dataset.report.occupancy_vehicle_count == 3
    assert dataset.report.right_censored_count == 1
    assert dataset.report.missing_before_boundary_count == 0
    assert dataset.matched[0].depart_s == 100.0
    assert dataset.matched[0].time_semantics == "full_day_sumo_clock"
    assert dataset.exclusions[0].depart_s is None
    assert dataset.exclusions[0].kind is VecTripExclusionKind.RIGHT_CENSORED_AT_TRACE_BOUNDARY
    assert dataset.report.compressed_size_bytes == len(payload)
    assert dataset.report.full_day_clock_preserved is True


def test_duration_summary_reuses_only_compatible_metric_definitions() -> None:
    dataset = build_trip_join_dataset(
        build_v2_trace(),
        _identity(),
        _tripinfo(),
        source_path="tripinfo/synthetic.xml.gz",
    )
    summary = dataset.report.duration_summary

    assert summary.eligible_count == 2
    assert summary.mean_s == pytest.approx(2.7)
    assert "trip.duration.p95_s" in summary.compatible_existing_metric_ids
    assert "trip.completion.rate" in summary.incompatible_existing_metric_ids
    assert vec_trip_join_contract().fingerprint() == vec_trip_join_contract().fingerprint()


@pytest.mark.parametrize(
    "xml, message",
    [
        (
            b'<tripinfos><tripinfo id="a" depart="1" arrival="3" '
            b'duration="1" routeLength="4"/></tripinfos>',
            "invalid required values",
        ),
        (
            b'<tripinfos><tripinfo id="a" depart="1" arrival="3" '
            b'duration="2" routeLength="4"/><tripinfo id="a" depart="1" '
            b'arrival="3" duration="2" routeLength="4"/></tripinfos>',
            "unique",
        ),
        (b"<!DOCTYPE tripinfos><tripinfos/>", "DTD"),
    ],
)
def test_invalid_tripinfo_is_refused(xml: bytes, message: str) -> None:
    with pytest.raises(VecTripJoinError, match=message):
        build_trip_join_dataset(
            build_v2_trace(),
            _identity(),
            gzip.compress(xml, mtime=0),
            source_path="tripinfo/bad.xml.gz",
        )


def test_changed_trace_and_unsafe_path_are_refused() -> None:
    changed = build_v2_trace()
    changed["speed"] = np.asarray(changed["speed"]).copy()
    changed["speed"][0, 0] += np.float32(1.0)
    with pytest.raises(VecTripJoinError, match="trace does not match"):
        build_trip_join_dataset(
            changed, _identity(), _tripinfo(), source_path="tripinfo/synthetic.xml.gz"
        )
    with pytest.raises(VecTripJoinError, match="safe relative"):
        build_trip_join_dataset(
            build_v2_trace(), _identity(), _tripinfo(), source_path="../raw.xml.gz"
        )


def test_missing_before_boundary_keeps_every_trip_value_unavailable() -> None:
    header, rows = build_v2_occupancy_rows()
    rows.append(["veh_missing_early", "2", "0", "0"])
    trace = build_v2_trace()
    trace["mask"] = np.asarray(trace["mask"]).copy()
    trace["mask"][0, 2] = True
    identity = build_vehicle_identity_snapshot(trace, header, rows, scenario=V2_SCENARIO)
    dataset = build_trip_join_dataset(
        trace, identity, _tripinfo(), source_path="tripinfo/synthetic.xml.gz"
    )
    excluded = next(
        item for item in dataset.exclusions if item.sumo_vehicle_id == "veh_missing_early"
    )
    assert excluded.kind is VecTripExclusionKind.MISSING_BEFORE_TRACE_BOUNDARY
    assert excluded.arrival_s is None
    assert excluded.cause == "unavailable"
