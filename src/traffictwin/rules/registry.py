"""Diagnostic rule registry."""

from __future__ import annotations

from traffictwin.rules.base import DiagnosticRule
from traffictwin.rules.r0_insufficient_evidence import R0InsufficientEvidenceRule
from traffictwin.rules.r1_under_offloading import R1UnderOffloadingRule
from traffictwin.rules.r2_infrastructure_bottleneck import R2InfrastructureBottleneckRule
from traffictwin.rules.r3_scenario_triviality import R3ScenarioTrivialityRule
from traffictwin.rules.r4_load_imbalance import R4LoadImbalanceRule
from traffictwin.rules.r5_validation_drift import R5ValidationDriftRule
from traffictwin.rules.r6_temporal_degradation import R6TemporalDegradationRule
from traffictwin.rules.r7_fairness import R7FairnessRule
from traffictwin.rules.r8_energy_anomaly import R8EnergyAnomalyRule


def default_rule_registry() -> dict[str, DiagnosticRule]:
    """Return enabled rule implementations in stable order."""

    rules: list[DiagnosticRule] = [
        R0InsufficientEvidenceRule(),
        R1UnderOffloadingRule(),
        R2InfrastructureBottleneckRule(),
        R3ScenarioTrivialityRule(),
        R4LoadImbalanceRule(),
        R5ValidationDriftRule(),
        R6TemporalDegradationRule(),
        R7FairnessRule(),
        R8EnergyAnomalyRule(),
    ]
    registry = {rule.rule_id: rule for rule in rules}
    if len(registry) != len(rules):
        msg = "duplicate diagnostic rule identifier"
        raise ValueError(msg)
    return {rule_id: registry[rule_id] for rule_id in sorted(registry)}


def enabled_rules(rule_ids: list[str]) -> list[DiagnosticRule]:
    """Return enabled rules in stable order."""

    registry = default_rule_registry()
    return [registry[rule_id] for rule_id in sorted(rule_ids) if rule_id in registry]
