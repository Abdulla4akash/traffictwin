from __future__ import annotations

from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.rules.engine import evaluate_rules
from traffictwin.synthetic.experiments import (
    build_r3_evidence_pack_from_bundles,
    generate_trivial_multi_algorithm_experiment,
)


def test_trivial_multi_algorithm_experiment_triggers_r3(tmp_path: Path) -> None:
    bundles = generate_trivial_multi_algorithm_experiment(tmp_path / "trivial")

    pack = build_r3_evidence_pack_from_bundles(bundles, clock=fixed_clock)
    report = evaluate_rules(pack, clock=fixed_clock)

    assert len(bundles) == 9
    assert "R3" in report.triggered_rule_ids
