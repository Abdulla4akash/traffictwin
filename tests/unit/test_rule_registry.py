from __future__ import annotations

from traffictwin.rules.catalogue import rule_catalogue
from traffictwin.rules.registry import default_rule_registry, enabled_rules


def test_rule_registry_has_unique_ordered_ids() -> None:
    registry = default_rule_registry()

    assert list(registry) == ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]
    assert len(registry) == len(set(registry))


def test_enabled_rules_preserve_deterministic_order() -> None:
    rules = enabled_rules(["R3", "R1"])

    assert [rule.rule_id for rule in rules] == ["R1", "R3"]


def test_rule_catalogue_documents_required_evidence() -> None:
    catalogue = rule_catalogue()

    assert catalogue["R1"].required_evidence
    assert "experiment.cross_algorithm_dispersion" in catalogue["R3"].required_evidence
    assert "temporal_evidence" in catalogue["R6"].required_evidence
    assert "fairness.vehicle_tier.completion_rate.max_gap" in (catalogue["R7"].required_evidence[0])
    assert "task.energy.per_completed_j" in catalogue["R8"].required_evidence
