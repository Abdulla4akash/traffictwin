"""Acceptance-record tests for real VEC-04 matched joins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from traffictwin.integration.vec_task_join import vec_task_join_contract

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reference/generated/vec_task_join_verification.json"
CONTRACT = ROOT / "docs/reference/generated/vec_task_join_contract.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_generated_contract_matches_library() -> None:
    assert _read(CONTRACT) == vec_task_join_contract().model_dump(mode="json")


def test_real_matched_runs_reconcile_and_report_no_target() -> None:
    report = _read(REPORT)
    assert report["status"] == "accepted"
    assert report["matched_run_count"] == 6
    assert report["scenario_count"] == 3
    assert report["total_tasks"] == 46_861_416
    assert report["total_no_eligible_target_tasks"] == 1_907
    assert all(item["status"] == "accepted" for item in report["reports"])
    assert report["external_source_unchanged"] is True


def test_record_is_permission_safe_and_preserves_limitations() -> None:
    text = REPORT.read_text(encoding="utf-8")
    assert "sumo_vehicle_id" not in text
    assert "/Users/" not in text
    assert "akash" not in text.lower()
    assert "actions do not confirm transfer" in text
