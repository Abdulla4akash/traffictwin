"""Acceptance-record tests for the real read-only VEC-03 verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT
from traffictwin.integration.vec_identity import vec_identity_contract

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reference/generated/vec_identity_verification.json"
CONTRACT = ROOT / "docs/reference/generated/vec_identity_contract.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_generated_contract_matches_library() -> None:
    assert _read(CONTRACT) == vec_identity_contract().model_dump(mode="json")


def test_real_acceptance_record_has_complete_identity_coverage() -> None:
    report = _read(REPORT)

    assert report["status"] == "accepted"
    assert report["source_commit"] == TOS_DATA_AUDITED_COMMIT
    assert report["scenario_count"] == 5
    assert report["total_spans"] == 45_299
    assert report["total_active_trace_cells"] == 17_210_508
    assert report["total_identity_cells"] == 17_210_508
    assert {item["scenario"] for item in report["reports"]} == {
        "ev",
        "inc",
        "wd_am",
        "wd_pm",
        "we",
    }
    assert all(item["status"] == "accepted" for item in report["reports"])
    assert all(item["missing_identity_cells"] == 0 for item in report["reports"])
    assert all(item["inactive_identity_cells"] == 0 for item in report["reports"])
    assert report["external_source_unchanged"] is True


def test_acceptance_record_is_permission_safe() -> None:
    text = REPORT.read_text(encoding="utf-8")

    assert "sumo_vehicle_id" not in text
    assert "/Users/" not in text
    assert "/private/" not in text
    assert "akash" not in text.lower()
