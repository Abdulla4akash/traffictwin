"""Checked-in real-evidence acceptance checks for VEC-11."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, cast

from traffictwin.integration.vec_publication import (
    vec_dissertation_pack_contract,
    verify_vec_dissertation_pack,
)
from traffictwin.integration.vec_science import VecScientificAdmissionReport
from traffictwin.integration.vec_task_join import VecTaskJoinReport
from traffictwin.integration.vec_trip_join import VecTripJoinReport

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "docs/reference/generated"
PACK = GENERATED / "vec_dissertation_pack"
RUN_LABEL = "fcd_s102_uk2030_we_fs0"


def _read(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_checked_in_pack_is_exactly_verifiable_and_contract_matches_code() -> None:
    manifest = verify_vec_dissertation_pack(PACK)
    contract = _read(GENERATED / "vec_dissertation_pack_contract.json")

    assert contract == vec_dissertation_pack_contract().model_dump(mode="json")
    assert manifest.status == "accepted"
    assert manifest.sample_count == 3
    assert manifest.aggregate_metric_count == 26
    assert manifest.available_metric_count == 18
    assert manifest.unavailable_metric_count == 8
    assert manifest.selection_label == "_s102_best_of_seeds"
    assert manifest.public_hosting_authorized is False


def test_manifest_fingerprints_bind_the_accepted_vec_04_vec_05_and_vec_09_reports() -> None:
    manifest = verify_vec_dissertation_pack(PACK)
    science_record = _read(GENERATED / "vec_scientific_admission_report.json")
    science = VecScientificAdmissionReport.model_validate(science_record["admission"])
    task_record = _read(GENERATED / "vec_task_join_verification.json")
    task = next(
        VecTaskJoinReport.model_validate(item)
        for item in task_record["reports"]
        if item["run_label"] == RUN_LABEL
    )
    trip_record = _read(GENERATED / "vec_trip_join_verification.json")
    trip = next(
        VecTripJoinReport.model_validate(item)
        for item in trip_record["reports"]
        if item["scenario"] == "we"
    )

    assert manifest.scientific_admission_fingerprint == science.fingerprint()
    assert manifest.task_join_report_fingerprint == task.fingerprint()
    assert manifest.trip_join_report_fingerprint == trip.fingerprint()
    assert science.task_join_report_fingerprint == task.fingerprint()
    assert science.trip_join_report_fingerprint == trip.fingerprint()


def test_pack_contains_no_raw_identity_clock_target_or_private_path_columns() -> None:
    sample = PACK / "sanitised_matched_sample_s102.csv"
    with sample.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    forbidden_columns = {
        "sumo_vehicle_id",
        "slot",
        "task_index",
        "time_index",
        "trace_time_s",
        "depart_s",
        "arrival_s",
        "selected_target_index",
        "eligible_best_rsu",
        "eligible_best_v2v",
    }
    assert rows
    assert forbidden_columns.isdisjoint(rows[0])
    combined = b"\n".join(path.read_bytes() for path in sorted(PACK.iterdir()))
    assert b"/Users/" not in combined
    assert b"file://" not in combined
    assert b"checkpoint" in combined  # visible only in the mandatory excluded inventory


def test_publication_policy_reference_now_points_to_the_accepted_pack() -> None:
    policy = _read(GENERATED / "tos_publication_policy.json")

    assert policy["status"] == "accepted"
    assert policy["capability_implemented"] is True
    assert policy["blocker"] is None
    assert policy["accepted_pack"] == "vec_dissertation_pack/manifest.json"
