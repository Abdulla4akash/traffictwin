"""Acceptance-record tests for all real VEC-05 trip joins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from traffictwin.integration.vec_trip_join import vec_trip_join_contract

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reference/generated/vec_trip_join_verification.json"
CONTRACT = ROOT / "docs/reference/generated/vec_trip_join_contract.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_generated_contract_matches_library() -> None:
    assert _read(CONTRACT) == vec_trip_join_contract().model_dump(mode="json")


def test_real_scenarios_reconcile_exact_cohorts_and_exclusions() -> None:
    report = _read(REPORT)
    assert report["status"] == "accepted"
    assert report["tripinfo_file_count"] == 4
    assert report["scenario_join_count"] == 5
    assert report["total_occupancy_vehicles"] == 43_767
    assert report["total_matched_vehicles"] == 42_881
    assert report["total_right_censored"] == 872
    assert report["total_missing_before_boundary"] == 14
    assert all(item["full_day_clock_preserved"] for item in report["reports"])
    assert report["external_source_unchanged"] is True


def test_acceptance_record_is_permission_safe() -> None:
    text = REPORT.read_text(encoding="utf-8")
    assert "sumo_vehicle_id" not in text
    assert "/Users/" not in text
    assert "/private/" not in text
    assert "akash" not in text.lower()
