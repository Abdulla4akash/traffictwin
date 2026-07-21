from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import diagnostic_report_for_case

EXPECTED = Path("tests/golden/expected/cross_rule_reasoning_mixed.json")


def test_mixed_fault_cross_rule_relationship_matches_golden() -> None:
    diagnostic = diagnostic_report_for_case("mixed_fault")
    report = diagnostic.cross_rule_analysis
    assert report is not None

    projection = {
        "schema_version": report.schema_version,
        "policy_version": report.policy_version,
        "status": report.status.value,
        "counts_by_type": report.counts_by_type,
        "retained_rule_ids": report.retained_rule_ids,
        "suppressed_rule_ids": report.suppressed_rule_ids,
        "unclassified_triggered_rule_ids": report.unclassified_triggered_rule_ids,
        "relationships": [
            {
                "policy_id": relationship.policy_id,
                "relation_type": relationship.relation_type.value,
                "source_rule_id": relationship.source_rule_id,
                "target_rule_id": relationship.target_rule_id,
                "source_status": relationship.source_status.value,
                "target_status": relationship.target_status.value,
                "overlap_basis": relationship.overlap_basis.value,
                "shared_evidence_keys": relationship.shared_evidence_keys,
                "source_precedence": relationship.source_precedence,
                "target_precedence": relationship.target_precedence,
                "symmetric": relationship.symmetric,
                "presentation_effect": relationship.presentation_effect,
            }
            for relationship in report.relationships
        ],
    }
    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))
