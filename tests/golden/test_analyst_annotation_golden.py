from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.annotations import (
    AnalystAnnotationRequest,
    AnalystArtifactReference,
    AnalystDecisionLabel,
)
from traffictwin.storage.registry import Registry

EXPECTED = Path("tests/golden/expected/analyst_annotation_history.json")


def test_append_only_annotation_history_matches_golden(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    target = AnalystArtifactReference(
        kind="research_report",
        artifact_id="report-run-run-baseline-001",
    )
    registry.append_analyst_annotation(
        AnalystAnnotationRequest(
            target=target,
            author_label="Analyst A",
            note="Synthetic fixture accepted for software demonstration only.",
            decision_label=AnalystDecisionLabel.ACCEPTED,
        ),
        clock=lambda: datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
    )
    registry.append_analyst_annotation(
        AnalystAnnotationRequest(
            target=target,
            author_label="Analyst B",
            note="Follow up with external evidence before making effectiveness claims.",
            decision_label=AnalystDecisionLabel.FOLLOW_UP,
        ),
        clock=lambda: datetime(2026, 7, 21, 10, 5, tzinfo=UTC),
    )
    actual = registry.list_analyst_annotations(target=target, limit=100).model_dump(mode="json")

    assert actual == json.loads(EXPECTED.read_text(encoding="utf-8"))
