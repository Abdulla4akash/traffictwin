"""Service tests for Portfolio Explorer projection."""

from __future__ import annotations

import json

import pytest

from traffictwin.domain.enums import RsuCapacityMode
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.portfolio import (
    default_synthetic_portfolio_rules,
    select_portfolio_policy,
)
from traffictwin.ui.portfolio_explorer import (
    ChallengeExecutionStatus,
    build_portfolio_explorer_view,
    get_challenge_seed,
    get_challenge_seed_library,
    get_demo_portfolio_study,
    is_selector_input,
)


def test_challenge_library_is_deterministic_and_bounded() -> None:
    first = get_challenge_seed_library()
    second = get_challenge_seed_library()
    assert len(first) == 7
    assert [c.challenge_id for c in first] == [c.challenge_id for c in second]
    assert first[0].challenge_id == "CH-01-arena-surge"
    ids = {c.challenge_id for c in first}
    assert len(ids) == 7
    for c in first:
        assert c.title
        assert c.purpose
        assert c.why_challenging


def test_challenge_titles_and_status_are_truthful() -> None:
    library = {c.challenge_id: c for c in get_challenge_seed_library()}
    assert library["CH-04-rsu-waiting-room-squeeze"].title == "Reduced-capacity stress"
    assert library["CH-05-load-aware-forwarding"].title == "High-load forwarding context"
    assert library["CH-06-stale-state-scheduling"].title == "Ordered-arrival fallback case"
    assert library["CH-07-scaling-strategy"].title == "Scaling stress"
    for c in library.values():
        assert c.status == ChallengeExecutionStatus.REPRESENTABLE_ONLY
        assert c.evidence_standing == "synthetic demonstration only"
        # REPRESENTABLE_ONLY challenges must state no generic execution path
        assert "Representable as a validated ScenarioSeed" in " ".join(c.limitations)
        assert "does not currently provide a generic ScenarioSeed-to-run" in " ".join(c.limitations)


def test_challenge_parameters_are_representable_not_executable() -> None:
    for challenge in get_challenge_seed_library():
        # All seven are REPRESENTABLE_ONLY via current tri-state
        assert challenge.status == ChallengeExecutionStatus.REPRESENTABLE_ONLY
        assert challenge.status != ChallengeExecutionStatus.EXECUTABLE  # type: ignore[comparison-overlap]
        # Yet the ScenarioSeed itself validates (schema-valid != executable)
        from traffictwin.ui.portfolio_explorer import _scenario_seed_from_challenge  # noqa: PLC0415

        seed = _scenario_seed_from_challenge(challenge)
        assert isinstance(seed, ScenarioSeed)
        assert seed.seed_id == challenge.challenge_id
        # Protect selector-input vs recorded distinction via authoritative contract
        from traffictwin.ui.portfolio_explorer import (  # noqa: PLC0415
            SELECTOR_CONSUMED_FIELDS,
            is_selector_input,
        )

        for param in challenge.parameter_overrides:
            expected_is_input = param in SELECTOR_CONSUMED_FIELDS or param.startswith(
                "workload.class_mix"
            )
            assert is_selector_input(param) == expected_is_input, param


def test_target_evidence_surfaces_truthful() -> None:
    for challenge in get_challenge_seed_library():
        # New truthful name must be present; old alias still works via property
        assert isinstance(challenge.target_evidence_surfaces, list)
        assert len(challenge.target_evidence_surfaces) >= 1
        assert challenge.expected_evidence_surfaces == challenge.target_evidence_surfaces


def test_waiting_room_not_labelled_compute_power() -> None:
    for challenge in get_challenge_seed_library():
        combined = " ".join([challenge.title, challenge.purpose, *challenge.limitations]).lower()
        assert "compute power" not in combined or "rsu_capacity_mode" in combined
        if challenge.challenge_id == "CH-04-rsu-waiting-room-squeeze":
            assert any("waiting-room" in lim.lower() for lim in challenge.limitations)
            assert any("rsu_capacity_mode" in lim for lim in challenge.limitations)


def test_inert_overrides_are_marked() -> None:
    # Known inert fields must be classified as NOT selector input
    for inert in [
        "traffic.event_type",
        "traffic.location",
        "infrastructure.rsu_count",
        "fleet.count",
        "evaluation.random_seed",
        "traffic.lanes_closed",
    ]:
        assert is_selector_input(inert) is False, inert
    # Known selector inputs must be marked
    for active in [
        "demand.multiplier",
        "workload.birth_rate_multiplier",
        "workload.class_mix",
        "fleet.tier_mix",
        "infrastructure.rsu_capacity_mode",
        "workload.ordering",
    ]:
        assert is_selector_input(active) is True, active
    # Challenge library must visibly contain inert examples
    library = {c.challenge_id: c for c in get_challenge_seed_library()}
    assert "traffic.event_type" in library["CH-01-arena-surge"].parameter_overrides
    assert is_selector_input("traffic.event_type") is False
    assert (
        "infrastructure.rsu_count" in library["CH-04-rsu-waiting-room-squeeze"].parameter_overrides
    )
    assert is_selector_input("infrastructure.rsu_count") is False


def test_ch03_matched_rule_is_p1_not_p2() -> None:
    view = build_portfolio_explorer_view("CH-03-t1-heavy-weak-fleet")
    assert view.selection is not None
    assert view.selection.matched_rule_id == "P1-weak-fleet"
    # Description must acknowledge shadowing
    ch = get_challenge_seed("CH-03-t1-heavy-weak-fleet")
    assert ch is not None
    assert "P1" in ch.why_challenging and "P1" in " ".join(ch.limitations)


def test_deterministic_portfolio_projection() -> None:
    view1 = build_portfolio_explorer_view("CH-01-arena-surge")
    view2 = build_portfolio_explorer_view("CH-01-arena-surge")
    assert view1.fingerprint == view2.fingerprint
    assert view1.selection is not None and view2.selection is not None
    assert view1.selection.selected_algorithm == view2.selection.selected_algorithm
    assert view1.selection.matched_rule_id == view2.selection.matched_rule_id
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


def test_matched_rule_claim_agrees_with_display() -> None:
    for challenge in get_challenge_seed_library():
        view = build_portfolio_explorer_view(challenge.challenge_id)
        assert view.selection is not None
        # Displayed matched_rule_id must equal authoritative selector
        from traffictwin.ui.portfolio_explorer import _scenario_seed_from_challenge

        seed = _scenario_seed_from_challenge(challenge)
        expected = select_portfolio_policy(seed, default_synthetic_portfolio_rules())
        assert view.selection.matched_rule_id == expected.matched_rule_id


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
    regrets = [c.mean_regret for c in view.candidate_views if c.mean_regret is not None]
    assert regrets == sorted(regrets)
    for idx, cand in enumerate(view.candidate_views, start=1):
        assert cand.rank == idx


def test_seeds_not_won_semantics() -> None:
    view = build_portfolio_explorer_view("CH-01-arena-surge")
    assert view.study_report is not None
    # Backend failure_seed_ids means not winner/tie, not crash — UI must expose as seeds_not_won
    for cand in view.candidate_views:
        assert isinstance(cand.seeds_not_won, list)
        # Alias still works but primary is seeds_not_won
        assert cand.failure_seed_ids == cand.seeds_not_won
        # At least one constituent should have some not-won seeds on held-out n=2
        # (synthetic-selective wins both, others not)
    # Check held-out constituents directly
    study = view.study_report
    for ce in study.held_out_constituents:
        # failure_seed_ids are seeds where constituent was not winner
        assert all(sid in study.held_out_seed_ids for sid in ce.failure_seed_ids)


def test_regret_and_winner_preserved() -> None:
    view = build_portfolio_explorer_view("CH-01-arena-surge")
    assert view.study_report is not None
    held = view.study_report.held_out_evaluation
    assert held.mean_regret is not None
    assert held.winner_or_tie_rate is not None
    for cand in view.candidate_views:
        assert cand.winner_or_tie_rate is not None
        assert cand.mean_regret is not None


def test_tie_winner_and_dominance_preserved() -> None:
    study = get_demo_portfolio_study()
    assert len(study.dominance_matrix) == 6
    view = build_portfolio_explorer_view("CH-04-rsu-waiting-room-squeeze")
    assert view.study_report is not None
    assert len(view.study_report.dominance_matrix) == 6
    first = view.study_report.dominance_matrix[0]
    assert first.available_seed_count == 2
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
    combined_warnings = " ".join(view.warnings).lower()
    assert (
        "optimal" not in combined_warnings
        or "not optimal" in combined_warnings
        or "not an optimal" in combined_warnings
    )
    if "kubernetes" in combined_warnings:
        assert "no " in combined_warnings and "kubernetes" in combined_warnings
    if "live manchester" in combined_warnings:
        assert "no live manchester" in combined_warnings
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
    import sys

    before = set(sys.modules.keys())
    _ = build_portfolio_explorer_view("CH-07-scaling-strategy")
    after = set(sys.modules.keys())
    new_modules = after - before
    for mod in new_modules:
        assert "sumo" not in mod.lower() or "synthetic" in mod.lower()
        assert "vec" not in mod.lower() or "synthetic" in mod.lower() or "portfolio" in mod.lower()


def test_portfolio_study_is_deterministic_independent() -> None:
    from traffictwin.ui.portfolio_explorer import _cached_demo_portfolio_study

    _cached_demo_portfolio_study.cache_clear()
    study1 = get_demo_portfolio_study()
    _cached_demo_portfolio_study.cache_clear()
    study2 = get_demo_portfolio_study()
    assert study1.selector_id == study2.selector_id == "synthetic-portfolio-v1"
    assert study1.metric_key == study2.metric_key
    assert (
        study1.held_out_evaluation.winner_or_tie_rate
        == study2.held_out_evaluation.winner_or_tie_rate
    )
    # Must be independent objects, not same cached instance
    assert study1 is not study2
    # JSON equality after removing fingerprint-like fields
    j1 = json.loads(study1.model_dump_json())
    j2 = json.loads(study2.model_dump_json())
    # generated_at will differ due to clock? Both use _fixed_clock, so equal, but we pop to be safe
    j1.pop("generated_at", None)
    j2.pop("generated_at", None)
    assert j1 == j2

    # View determinism also independent
    _cached_demo_portfolio_study.cache_clear()
    v1 = build_portfolio_explorer_view("CH-01-arena-surge")
    _cached_demo_portfolio_study.cache_clear()
    v2 = build_portfolio_explorer_view("CH-01-arena-surge")
    assert v1.fingerprint == v2.fingerprint
    j1 = json.loads(v1.model_dump_json())
    j2 = json.loads(v2.model_dump_json())
    j1.pop("fingerprint", None)
    j2.pop("fingerprint", None)
    assert j1 == j2
    v_other = build_portfolio_explorer_view("CH-03-t1-heavy-weak-fleet")
    assert v1.fingerprint != v_other.fingerprint


def test_fingerprint_binds_dominance_via_production_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dominance mutation via real builder must change production fingerprint."""
    baseline = build_portfolio_explorer_view("CH-01-arena-surge")
    baseline_fp = baseline.fingerprint
    assert len(baseline_fp) == 64
    # identical evidence -> same fingerprint via production path
    again = build_portfolio_explorer_view("CH-01-arena-surge")
    assert again.fingerprint == baseline_fp

    from traffictwin.ui import portfolio_explorer as pe  # noqa: PLC0415

    orig_study = pe._cached_demo_portfolio_study()
    mutated = orig_study.model_copy(deep=True)
    # Mutate dominance evidence: first pairwise win count
    mutated.dominance_matrix[0] = mutated.dominance_matrix[0].model_copy(
        update={"wins": mutated.dominance_matrix[0].wins + 1}
    )
    monkeypatch.setattr(pe, "_cached_demo_portfolio_study", lambda: mutated)
    mutated_view = pe.build_portfolio_explorer_view("CH-01-arena-surge")
    assert mutated_view.fingerprint != baseline_fp

    # Restore and prove deterministic return
    monkeypatch.setattr(pe, "_cached_demo_portfolio_study", lambda: orig_study)
    restored = pe.build_portfolio_explorer_view("CH-01-arena-surge")
    assert restored.fingerprint == baseline_fp


def test_fingerprint_binds_held_out_evidence_via_production_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Held-out mean regret, winner rate and candidate scores must be fingerprint-bound."""
    baseline = build_portfolio_explorer_view("CH-01-arena-surge")
    baseline_fp = baseline.fingerprint
    assert baseline.study_report is not None
    assert len(baseline.candidate_views) == 3

    from traffictwin.ui import portfolio_explorer as pe  # noqa: PLC0415

    orig_study = pe._cached_demo_portfolio_study()

    # Mutate held-out winner/tie rate
    mutated = orig_study.model_copy(deep=True)
    orig_rate = mutated.held_out_evaluation.winner_or_tie_rate
    assert orig_rate is not None
    mutated.held_out_evaluation = mutated.held_out_evaluation.model_copy(
        update={
            "winner_or_tie_rate": orig_rate + 0.1 if orig_rate + 0.1 <= 1.0 else orig_rate - 0.1
        }
    )
    monkeypatch.setattr(pe, "_cached_demo_portfolio_study", lambda: mutated)
    mutated_view = pe.build_portfolio_explorer_view("CH-01-arena-surge")
    assert mutated_view.fingerprint != baseline_fp

    # Mutate held-out mean regret
    mutated2 = orig_study.model_copy(deep=True)
    orig_regret = mutated2.held_out_evaluation.mean_regret
    assert orig_regret is not None
    mutated2.held_out_evaluation = mutated2.held_out_evaluation.model_copy(
        update={"mean_regret": orig_regret + 1.0}
    )
    monkeypatch.setattr(pe, "_cached_demo_portfolio_study", lambda: mutated2)
    mutated_view2 = pe.build_portfolio_explorer_view("CH-01-arena-surge")
    assert mutated_view2.fingerprint != baseline_fp
    assert mutated_view2.fingerprint != mutated_view.fingerprint

    # Mutate candidate mean regret via constituent evaluation
    mutated3 = orig_study.model_copy(deep=True)
    mutated3.held_out_constituents[0] = mutated3.held_out_constituents[0].model_copy(
        update={"mean_regret": (mutated3.held_out_constituents[0].mean_regret or 0) + 5.0}
    )
    monkeypatch.setattr(pe, "_cached_demo_portfolio_study", lambda: mutated3)
    mutated_view3 = pe.build_portfolio_explorer_view("CH-01-arena-surge")
    assert mutated_view3.fingerprint != baseline_fp

    # Mutate challenge parameter override also via production path (different challenge)
    other = pe.build_portfolio_explorer_view("CH-02-lane-closure-corridor")
    assert other.fingerprint != baseline_fp

    # Restore original study and prove fingerprint returns deterministically
    monkeypatch.setattr(pe, "_cached_demo_portfolio_study", lambda: orig_study)
    restored = pe.build_portfolio_explorer_view("CH-01-arena-surge")
    assert restored.fingerprint == baseline_fp


def test_cache_mutation_isolation() -> None:
    from traffictwin.ui.portfolio_explorer import _cached_demo_portfolio_study

    _cached_demo_portfolio_study.cache_clear()
    view1 = build_portfolio_explorer_view("CH-01-arena-surge")
    assert view1.study_report is not None
    original_rate = view1.study_report.held_out_evaluation.winner_or_tie_rate
    # Mutate nested study data in view1
    view1.study_report.held_out_evaluation.winner_or_tie_rate = 0.99
    view1.candidate_views[0].mean_regret = 999.0
    # Next build must remain canonical
    view2 = build_portfolio_explorer_view("CH-01-arena-surge")
    assert view2.study_report is not None
    assert view2.study_report.held_out_evaluation.winner_or_tie_rate == original_rate
    assert view2.candidate_views[0].mean_regret != 999.0
    # Also direct study cache isolation
    _cached_demo_portfolio_study.cache_clear()
    s1 = get_demo_portfolio_study()
    s1.warnings.append("injected")
    s2 = get_demo_portfolio_study()
    assert "injected" not in s2.warnings
    assert s1 is not s2


def test_n2_held_out_limitation_is_surfaced() -> None:
    view = build_portfolio_explorer_view("CH-01-arena-surge")
    assert view.study_report is not None
    assert len(view.study_report.held_out_seed_ids) == 2
    assert view.study_report.development_evaluation.evaluated_seed_count == 3
    # Selector does not outperform best constituent on n=2
    held_rate = view.study_report.held_out_evaluation.winner_or_tie_rate
    best_rate = max(
        c.winner_or_tie_rate
        for c in view.study_report.held_out_constituents
        if c.winner_or_tie_rate is not None
    )
    assert held_rate is not None and best_rate is not None
    # On these two seeds, synthetic-selective is best
    best_algo = max(
        view.study_report.held_out_constituents,
        key=lambda c: c.winner_or_tie_rate if c.winner_or_tie_rate is not None else -1,
    ).algorithm
    assert best_algo == "synthetic-selective"
    assert held_rate <= best_rate
