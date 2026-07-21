from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.unit.test_r6_temporal_degradation import (
    MISS_KEY,
    _deadline_tables,
    _evaluate,
)

from traffictwin.evidence.temporal import TemporalEvidenceConfig

EXPECTED = Path("tests/golden/expected/r6_temporal_recovery.json")


def test_r6_temporal_recovery_matches_golden_projection() -> None:
    pack, result = _evaluate(
        _deadline_tables([0.1, 0.1, 0.3, 0.4, 0.1, 0.1]),
        TemporalEvidenceConfig(
            metric_key=MISS_KEY,
            event_time_s=20,
            event_label="incident",
        ),
    )
    temporal = pack.temporal_evidence
    assert temporal is not None
    projection: dict[str, Any] = {
        "temporal": {
            "status": temporal.status.value,
            "metric_key": temporal.metric_key,
            "unit": temporal.unit,
            "higher_is_better": temporal.higher_is_better,
            "eligible_window_count": temporal.eligible_window_count,
            "event_window_ordinal": (
                temporal.event.event_window_ordinal if temporal.event is not None else None
            ),
            "point_values": [point.value for point in temporal.points],
            "point_eligibility": [point.eligibility.value for point in temporal.points],
            "series_fingerprint": temporal.series_fingerprint,
            "evidence_fingerprint": temporal.fingerprint(),
        },
        "r6": {
            "status": result.status.value,
            "confidence": result.confidence.value,
            "evidence_keys": result.evidence_keys,
            "finding_support": {
                finding.finding_id: finding.support.value for finding in result.findings
            },
            "metadata": result.metadata,
        },
    }

    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))
