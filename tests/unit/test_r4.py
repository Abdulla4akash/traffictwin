from __future__ import annotations

from pathlib import Path

from tests.helpers import fixed_clock
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import RuleResult, RuleStatus
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def _r4_result(tmp_path: Path, preset: str) -> RuleResult:
    bundle = write_synthetic_bundle(preset_config(preset), tmp_path / preset)
    validation = validate_bundle(bundle)
    metrics = compute_metrics_for_bundle(validation, clock=fixed_clock)
    evidence = build_evidence_pack(validation, metrics, clock=fixed_clock)
    report = evaluate_rules(evidence, clock=fixed_clock)
    return next(result for result in report.results if result.rule_id == "R4")


def test_r4_triggers_for_deterministic_localised_synthetic_imbalance(tmp_path: Path) -> None:
    result = _r4_result(tmp_path, "mixed_fault")

    assert result.status is RuleStatus.TRIGGERED
    assert "routing" in (result.hypothesis or "")
    assert "task-to-RSU routing and location context" in result.missing_evidence


def test_r4_does_not_trigger_for_balanced_baseline(tmp_path: Path) -> None:
    result = _r4_result(tmp_path, "baseline")

    assert result.status is RuleStatus.NOT_TRIGGERED
