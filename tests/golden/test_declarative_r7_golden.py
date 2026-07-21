from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.unit.test_r7_fairness import _evaluate, _pack, _tier_metric

from traffictwin.rules.config import R7Config
from traffictwin.rules.declarative import declarative_rule_contract
from traffictwin.rules.r7_fairness import r7_rule_definition

EXPECTED = Path("tests/golden/expected/declarative_r7_contract.json")


def test_declarative_contract_definitions_and_r7_result_match_golden() -> None:
    tier = r7_rule_definition(R7Config(dimension="vehicle_tier_completion"))
    target = r7_rule_definition(R7Config(dimension="target_rsu_completion"))
    result = _evaluate(_pack(_tier_metric(gap=0.5)))
    projection: dict[str, Any] = {
        "contract": declarative_rule_contract().model_dump(mode="json"),
        "definitions": [
            {
                "dimension": "vehicle_tier_completion",
                "fingerprint": tier.fingerprint(),
                "definition": tier.model_dump(mode="json"),
            },
            {
                "dimension": "target_rsu_completion",
                "fingerprint": target.fingerprint(),
                "definition": target.model_dump(mode="json"),
            },
        ],
        "r7": {
            "status": result.status.value,
            "confidence": result.confidence.value,
            "hypothesis": result.hypothesis,
            "evidence_keys": result.evidence_keys,
            "finding_support": {
                finding.finding_id: finding.support.value for finding in result.findings
            },
            "missing_evidence": result.missing_evidence,
            "alternative_explanations": result.alternative_explanations,
            "limitations": result.limitations,
            "metadata": result.metadata,
        },
    }

    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))
