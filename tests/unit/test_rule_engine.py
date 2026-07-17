from __future__ import annotations

from copy import deepcopy

from tests.helpers import diagnostic_case, fixed_clock
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.evaluation import evidence_pack_from_case


def test_rule_engine_is_deterministic_for_fixed_clock() -> None:
    pack = evidence_pack_from_case(diagnostic_case("mixed_fault"), clock=fixed_clock)

    first = evaluate_rules(pack, clock=fixed_clock)
    second = evaluate_rules(pack, clock=fixed_clock)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_rule_engine_does_not_mutate_evidence_pack() -> None:
    pack = evidence_pack_from_case(diagnostic_case("under_offloading"), clock=fixed_clock)
    before = deepcopy(pack.model_dump(mode="json"))

    evaluate_rules(pack, clock=fixed_clock)

    assert pack.model_dump(mode="json") == before


def test_disabled_rules_do_not_execute() -> None:
    pack = evidence_pack_from_case(diagnostic_case("mixed_fault"), clock=fixed_clock)
    config = RuleSetConfig.model_validate({"r1": {"enabled": False}})

    report = evaluate_rules(pack, config, clock=fixed_clock)

    assert "R1" not in [result.rule_id for result in report.results]
    assert report.triggered_rule_ids == ["R2"]


def test_every_cited_evidence_key_exists() -> None:
    pack = evidence_pack_from_case(diagnostic_case("mixed_fault"), clock=fixed_clock)
    report = evaluate_rules(pack, clock=fixed_clock)
    metric_keys = set(pack.metric_collection.by_key())

    for result in report.results:
        for key in result.evidence_keys:
            assert key in metric_keys
