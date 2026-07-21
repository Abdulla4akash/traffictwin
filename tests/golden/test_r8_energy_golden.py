from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.r8_energy_anomaly import r8_energy_diagnosis_contract
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

EXPECTED = Path("tests/golden/expected/r8_energy_diagnosis.json")


def test_r8_contract_and_triggered_projection_match_golden(tmp_path: Path) -> None:
    bundle = validate_bundle(
        write_synthetic_bundle(
            preset_config("infrastructure_bottleneck"),
            tmp_path / "energy-candidate",
        )
    )
    metrics = compute_metrics_for_bundle(bundle, clock=fixed_clock)
    pack = build_evidence_pack(bundle, metrics, clock=fixed_clock)
    report = evaluate_rules(pack, clock=fixed_clock)
    result = next(item for item in report.results if item.rule_id == "R8")
    projection = {
        "contract": r8_energy_diagnosis_contract().model_dump(mode="json"),
        "result": {
            "rule_id": result.rule_id,
            "rule_version": result.rule_version,
            "title": result.title,
            "status": result.status.value,
            "hypothesis": result.hypothesis,
            "evidence_keys": result.evidence_keys,
            "confidence": result.confidence.value,
            "findings": [
                {
                    "finding_id": finding.finding_id,
                    "support": finding.support.value,
                    "observed_values": finding.observed_values,
                    "expected_condition": finding.expected_condition,
                }
                for finding in result.findings
            ],
            "metadata": result.metadata,
            "limitations": result.limitations,
        },
    }

    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))
