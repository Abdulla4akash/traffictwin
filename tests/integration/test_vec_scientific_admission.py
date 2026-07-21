"""Acceptance-record tests for VEC-09 scientific admission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from traffictwin.integration.vec_science import (
    VecScientificAdmissionReport,
    vec_scientific_admission_contract,
)

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reference/generated/vec_scientific_admission_report.json"
CONTRACT = ROOT / "docs/reference/generated/vec_scientific_admission_contract.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_generated_contract_matches_library() -> None:
    assert _read(CONTRACT) == vec_scientific_admission_contract().model_dump(mode="json")


def test_real_admission_keeps_metric_and_rule_boundaries() -> None:
    record = _read(REPORT)
    report = VecScientificAdmissionReport.model_validate(record["admission"])
    metrics = report.evidence_pack.metric_collection.by_key()
    rules = {item.rule_id: item for item in report.rule_readiness}

    assert record["status"] == "accepted"
    assert record["selected_run_label"] == "fcd_s102_uk2030_we_fs0"
    assert sum(item.status.value == "available" for item in metrics.values()) == 18
    assert sum(item.status.value == "unavailable" for item in metrics.values()) == 8
    assert metrics["tos.task.deadline_success.rate"].status.value == "available"
    assert metrics["task.completion.rate"].status.value == "unavailable"
    assert metrics["task.energy.per_completed_j"].status.value == "unavailable"
    assert rules["R6"].status.value == "conditional"
    assert {rules[key].status.value for key in ("R1", "R2", "R7")} == {"blocked"}
    assert all(item.threshold_evaluated is False for item in rules.values())
    assert all(item.finding_emitted is False for item in rules.values())
    assert record["external_source_unchanged"] is True


def test_admission_record_is_permission_safe_and_preserves_selection_label() -> None:
    raw = REPORT.read_text(encoding="utf-8")

    assert "sumo_vehicle_id" not in raw
    assert "/Users/" not in raw
    assert "/private/" not in raw
    assert "akash" not in raw.lower()
    assert '"selection_label_preserved": "_s102_best_of_seeds"' in raw
