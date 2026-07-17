from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import diagnostic_projection

EXPECTED = Path("tests/golden/expected")
CASES = {
    "baseline_no_strong_hypothesis": "diagnosis_baseline.json",
    "under_offloading": "diagnosis_under_offloading.json",
    "infrastructure_bottleneck": "diagnosis_infrastructure_bottleneck.json",
    "trivial_scenario": "diagnosis_trivial_scenario.json",
    "mixed_fault": "diagnosis_mixed_fault.json",
    "insufficient_evidence": "diagnosis_insufficient_evidence.json",
    "contradictory_evidence": "diagnosis_contradictory_evidence.json",
}


def test_diagnostic_golden_projections() -> None:
    for case_id, filename in CASES.items():
        expected = json.loads((EXPECTED / filename).read_text(encoding="utf-8"))

        assert diagnostic_projection(case_id) == expected
