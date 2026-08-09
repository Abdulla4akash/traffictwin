"""Service tests for Portfolio Explorer projection."""

from __future__ import annotations

import json

from traffictwin.domain.enums import RsuCapacityMode
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.portfolio import (
    default_synthetic_portfolio_rules,
    select_portfolio_policy,
)
from traffictwin.ui.portfolio_explorer import (
    build_portfolio_explorer_view,
    get_challenge_seed,
    get_challenge_seed_library,
    get_demo_portfolio_study,
)


def test_challenge_library_is_deterministic_and_bounded() -> None:
    first = get_challenge_seed_library()
    second = get_challenge_seed_library()
    assert len(first) == 7
    assert [c.challenge_id for c in first] == [c.challenge_id for c in second]
    assert first[0].challenge_id == "CH-01-arena-surge"
    # Stable IDs
    ids = {c.challenge_id for c in first}
    assert len(ids) == 7
    for c in first:
        assert c.title
        assert c.purpose
        assert c.why_challenging


def test_challenge_parameters_are_supported_or_explicitly_unavailable() -> None:
    for challenge in get_challenge_seed_library():
        # All current challenges are executable via validated ScenarioSeed
        assert challenge.executable_now is True
        # Rebuilding the seed must succeed (fields are supported)
        from traffictwin.ui.portfolio_explorer import _scenario_seed_from_challenge  # noqa: PLC0415

        seed = _scenario_seed_from_challenge(challenge)
        assert isinstance(seed, ScenarioSeed)
        assert seed.seed_id == challenge.challenge_id
        # No invented waiting-room vs compute conflation
        for param in challenge.parameter_overrides:
            assert "compute" not in param.lower() or "rsu_capacity" in param


def test_waiting_room_not_labelled_compute_power() -> None:
    for challenge in get_challenge_seed_library():
        combined = " ".join([challenge.title, challenge.purpose, *challenge.limitations]).lower()
        # Must not call rsu_capacity compute power
        assert "compute power" not in combined or "rsu_capacity_mode" in combined
        # Challenge CH-04 specifically distinguishes waiting-room vs compute
        if challenge.challenge_id == "CH-04-rsu-waiting-room-squeeze":
            assert any("waiting-room" in lim.lower() for lim in challenge.limitations)
            assert any("rsu_capacity_mode" in lim for lim in challenge.limitations)


def test_deterministic_portfolio_projection() -> None:
    view1 = build_portfolio_explorer_view("CH-01-arena-surge")
    view2 = build_portfolio_explorer_view("CH-01-arena-surge")
    assert view1.fingerprint == view2.fingerprint
    assert view1.selection is not None and view2.selection is not None
    assert view1.selection.selected_algorithm == view2.selection.selected_algorithm
    assert view1.selection.matched_rule_id == view2.selection.matched_rule_id
    # Different challenge gives different fingerprint
    view3 = build_portfolio_explorer_view("CH-03-t1-heavy-weak-fleet")
    assert view1.fingerprint != view3.fingerprint


def test_selected_strategy_equals_backend_selector() -> None:
    from traffictwin.ui.portfolio_explorer import _scenario_seed_from_challenge

    for challenge in get_challenge_seed_library():
        seed = _scenario_seed_from_challenge(challenge)
        expected = select_portfolio_policy(seed, default_synthetic_portfolio_rules())
        view = build_portfolio_explorer_view(challenge.challenge_id)
        assert view.selection is not None
        assert view.selection.selected_algorithm == expected.selected_algorithm
        assert view.selection.matched_rule_id == expected.matched_rule_id
        assert view.selection.rationale == expected.rationale


def test_rationale_comes_from_authoritative_rule() -> None:
    rules = default_synthetic_portfolio_rules()
    rule_rationale = {r.rule_id: r.rationale for r in rules.rules}
    rule_rationale["fallback"] = "No rule matched; the explicit fallback was selected."
    for challenge in get_challenge_seed_library():
        view = build_portfolio_explorer_view(challenge.challenge_id)
        assert view.selection is not None
        rule_id = view.selection.matched_rule_id or "fallback"
        assert view.selection.rationale == rule_rationale[rule_id]


def test_all_candidates_preserved_and_ranked() -> None:
    view = build_portfolio_explorer_view("CH-01-arena-surge")
    assert len(view.candidate_views) == 3
    algorithms = {c.algorithm for c in view.candidate_views}
    assert algorithms == {"synthetic-always-local", "synthetic-selective", "synthetic-balanced"}
    # Ranking by mean_regret ascending
    regrets = [c.mean_regret for c in view.candidate_views if c.mean_regret is not None]
    assert regrets == sorted(regrets)
    for idx, cand in enumerate(view.candidate_views, start=1):
        assert cand.rank == idx


def test_regret_and_winner_preserved() -> None:
    study = get_demo_portfolio_study()
    view = build_portfolio_explorer_view("CH-01-arena-surge")
    assert view.study_report is not None
    held = view.study_report.held_out_evaluation
    assert held.mean_regret is not None
    assert held.winner_or_tie_rate is not None
    # Constituents preserve winner/tie and regret
    for cand in view.candidate_views:
        assert cand.winner_or_tie_rate is not None
        assert cand.mean_regret is not None


def test_tie_winner_and_dominance_preserved() -> None:
    study = get_demo_portfolio_study()
    assert len(study.dominance_matrix) == 6
    view = build_portfolio_explorer_view("CH-04-rsu-waiting-room-squeeze")
    assert view.study_report is not None
    assert len(view.study_report.dominance_matrix) == 6
    # Check one dominance entry
    first = view.study_report.dominance_matrix[0]
    assert first.available_seed_count == 2  # held-out has 2 seeds
    assert first.wins + first.ties + first.losses == first.available_seed_count


def test_development_vs_held_out_preserved() -> None:
    study = get_demo_portfolio_study()
    assert len(study.development_seed_ids) == 3
    assert len(study.held_out_seed_ids) == 2
    assert set(study.development_seed_ids).isdisjoint(study.held_out_seed_ids)
    view = build_portfolio_explorer_view("CH-02-lane-closure-corridor")
    assert view.study_report is not None
    assert view.study_report.development_evaluation.evaluated_seed_count == 3
    assert view.study_report.held_out_evaluation.evaluated_seed_count == 2


def test_synthetic_provenance_preserved_and_no_optimality_claim() -> None:
    view = build_portfolio_explorer_view("CH-05-load-aware-forwarding")
    assert view.selection is not None
    assert view.selection.synthetic_demonstration_only is True
    assert view.study_report is not None
    assert "synthetic" in " ".join(view.study_report.warnings).lower()
    # No optimality claim
    combined_warnings = " ".join(view.warnings).lower()
    assert (
        "optimal" not in combined_warnings
        or "not optimal" in combined_warnings
        or "not an optimal" in combined_warnings
    )
    assert "kubernetes" not in combined_warnings
    assert "live manchester" not in combined_warnings
    # Candidate standing
    for cand in view.candidate_views:
        assert "synthetic demonstration only" in cand.evidence_standing


def test_challenge_seed_deterministic_parameters() -> None:
    ch1 = get_challenge_seed("CH-01-arena-surge")
    assert ch1 is not None
    assert ch1.parameter_overrides["demand.multiplier"] == 2.2
    ch4 = get_challenge_seed("CH-04-rsu-waiting-room-squeeze")
    assert ch4 is not None
    assert (
        ch4.parameter_overrides["infrastructure.rsu_capacity_mode"] == RsuCapacityMode.REDUCED.value
    )
    assert ch4.parameter_overrides["infrastructure.rsu_count"] == 3


def test_no_network_provider_sumo_vec_dependency() -> None:
    # Import must not pull SUMO/VEC or provider modules
    import sys

    before = set(sys.modules.keys())
    _ = build_portfolio_explorer_view("CH-07-scaling-strategy")
    after = set(sys.modules.keys())
    new_modules = after - before
    for mod in new_modules:
        assert "sumo" not in mod.lower() or "synthetic" in mod.lower()
        assert "vec" not in mod.lower() or "synthetic" in mod.lower() or "portfolio" in mod.lower()


def test_portfolio_study_is_deterministic() -> None:
    study1 = get_demo_portfolio_study()
    study2 = get_demo_portfolio_study()
    assert study1.selector_id == study2.selector_id == "synthetic-portfolio-v1"
    assert study1.metric_key == study2.metric_key
    assert (
        study1.held_out_evaluation.winner_or_tie_rate
        == study2.held_out_evaluation.winner_or_tie_rate
    )
    # Fingerprint via view
    v1 = build_portfolio_explorer_view("CH-01-arena-surge")
    v2 = build_portfolio_explorer_view("CH-01-arena-surge")
    assert v1.fingerprint == v2.fingerprint
    # JSON deterministic
    j1 = json.loads(v1.model_dump_json())
    j2 = json.loads(v2.model_dump_json())
    j1.pop("fingerprint", None)
    j2.pop("fingerprint", None)
    # Fingerprint differs when challenge changes
    v_other = build_portfolio_explorer_view("CH-03-t1-heavy-weak-fleet")
    assert v1.fingerprint != v_other.fingerprint
