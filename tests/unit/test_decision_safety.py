"""Decision-Safety Ruleset v2 decision-table and adversarial tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.platform.decision_safety import (
    CONFIRMATORY_RECORD_PATH,
    DISPLAY_ORDER,
    CauseDesignAuthority,
    DecisionOption,
    DecisionSafetyError,
    DecisionSafetyPolicy,
    assess,
    assessment_to_json,
    confirmed_capacity_notice,
    ruleset_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIGEST = "c" * 64


def _policy(**overrides: object) -> DecisionSafetyPolicy:
    payload: dict[str, object] = {
        "policy_id": "capacity-study-decision-policy",
        "policy_version": "2.0",
        "source_digest": "b" * 64,
        "comparison_contract_digest": CONTRACT_DIGEST,
        "minimum_support_count": 5,
        "required_overall_service_companions": (
            "deadline_attainment",
            "action_change",
            "failure_locus",
        ),
        "ranking_allowed": True,
        "advisory_recommendation_allowed": True,
        "execution_instruction_drafts_allowed": True,
        "owner_preselected_default_option_id": None,
        "maximum_cause_scope": "simulation_internal",
    }
    payload.update(overrides)
    return DecisionSafetyPolicy.model_validate(payload)


def _option(option_id: str = "opt-a", **overrides: object) -> DecisionOption:
    payload: dict[str, object] = {
        "option_id": option_id,
        "kind": "admitted_analysis",
        "source_digest": "a" * 64,
        "comparison_contract_digest": CONTRACT_DIGEST,
        "compatibility_group": "capacity-confirmatory-inc",
        "trace": "inc",
        "actor": "ukfleettrain_mappo_model_c_17",
        "capacity": 0.75,
        "inside_measured_envelope": True,
        "actor_capacity_measured": True,
        "matched_budget": True,
        "comparison_predeclared": True,
        "support_count": 5,
        "interval_status": "available",
        "primary_metric_name": "deadline_completion",
        "primary_metric_value": 0.77,
        "metric_direction": "higher_is_better",
        "headline_improvement_claimed": False,
        "companions_present": (),
    }
    payload.update(overrides)
    return DecisionOption.model_validate(payload)


def test_presentable_assessment_is_evidence_backed_but_creates_nothing() -> None:
    policy = _policy()
    assessment = assess((_option(),), policy=policy)
    assert assessment.status == "presentable_with_cautions"
    assert assessment.recommendation is False
    assert assessment.evidence_backed is True
    assert assessment.creates_new_evidence is False
    assert assessment.execution_authority is False
    assert assessment.causal_scope == "none"
    assert assessment.display_order == DISPLAY_ORDER
    assert assessment.ruleset_digest == ruleset_digest(policy)
    assert "creates_new_evidence" in assessment_to_json(assessment)


def test_compatible_predeclared_ranking_advice_default_and_draft_are_allowed() -> None:
    policy = _policy(owner_preselected_default_option_id="cap-2.5")
    assessment = assess(
        (
            _option(
                "cap-0.75",
                capacity=0.75,
                primary_metric_value=0.78,
                execution_instruction_draft="Set the simulation capacity arm to 0.75.",
            ),
            _option("cap-2.5", capacity=2.5, primary_metric_value=0.77),
        ),
        policy=policy,
        request_ranking=True,
        request_advisory_recommendation=True,
    )
    assert assessment.ranked_option_ids == ("cap-0.75", "cap-2.5")
    assert assessment.metric_winner_option_ids == ("cap-0.75",)
    assert assessment.recommendation is True
    assert assessment.evidence_backed is True
    assert "within this measured comparison only" in str(assessment.advisory_recommendation)
    assert assessment.owner_preselected_default_option_id == "cap-2.5"
    assert len(assessment.execution_instruction_drafts) == 1
    draft = assessment.execution_instruction_drafts[0]
    assert draft.review_required is True
    assert draft.executable is False
    assert draft.execution_authority is False


def test_metric_ranking_preserves_ties_and_refuses_unmatched_or_unapproved_work() -> None:
    tied = assess(
        (_option("b", primary_metric_value=1.0), _option("a", primary_metric_value=1.0)),
        policy=_policy(),
        request_ranking=True,
    )
    assert tied.ranked_option_ids == ("a", "b")
    assert tied.metric_winner_option_ids == ("a", "b")

    with pytest.raises(DecisionSafetyError) as unmatched:
        assess(
            (_option(), _option("unmatched", matched_budget=False)),
            policy=_policy(),
            request_ranking=True,
        )
    assert unmatched.value.code == "RANKING_NOT_PREDECLARED_OR_MATCHED"
    with pytest.raises(DecisionSafetyError) as forbidden:
        assess((_option(),), policy=_policy(ranking_allowed=False), request_ranking=True)
    assert forbidden.value.code == "RANKING_NOT_ALLOWED"


def test_metric_specific_win_is_not_silently_promoted_to_overall_service() -> None:
    metric_only = assess(
        (
            _option(
                primary_metric_name="latency_ms",
                primary_metric_value=895.561,
                metric_direction="lower_is_better",
                headline_improvement_claimed=True,
            ),
        ),
        policy=_policy(),
    )
    assert any(notice.code == "METRIC_SPECIFIC_ONLY" for notice in metric_only.notices)

    with pytest.raises(DecisionSafetyError) as unsupported:
        assess(
            (
                _option(
                    overall_service_claimed=True,
                    service_endpoint_present=False,
                    companions_present=("deadline_attainment",),
                ),
            ),
            policy=_policy(),
        )
    assert unsupported.value.code == "OVERALL_SERVICE_SUPPORT_MISSING"

    supported = assess(
        (
            _option(
                overall_service_claimed=True,
                service_endpoint_present=True,
                companions_present=(
                    "deadline_attainment",
                    "action_change",
                    "failure_locus",
                ),
            ),
        ),
        policy=_policy(),
    )
    assert supported.status == "presentable_with_cautions"


def test_incompatible_standings_groups_and_contracts_refuse() -> None:
    with pytest.raises(DecisionSafetyError) as non_admitted:
        assess((_option(kind="non_admitted"),), policy=_policy())
    assert non_admitted.value.code == "NON_ADMITTED_INPUT"
    with pytest.raises(DecisionSafetyError) as standing:
        assess((_option(), _option("pred", kind="prediction")), policy=_policy())
    assert standing.value.code == "INCOMPATIBLE_EVIDENCE"
    with pytest.raises(DecisionSafetyError) as group:
        assess(
            (_option(), _option("other", compatibility_group="other-study")),
            policy=_policy(),
        )
    assert group.value.code == "INCOMPATIBLE_COMPARISON_CONTRACT"
    with pytest.raises(DecisionSafetyError) as contract:
        assess(
            (_option(comparison_contract_digest="d" * 64),),
            policy=_policy(),
        )
    assert contract.value.code == "INCOMPATIBLE_COMPARISON_CONTRACT"


def test_envelope_support_and_uncertainty_are_mandatory() -> None:
    assessment = assess(
        (
            _option("inside"),
            _option("outside", inside_measured_envelope=False),
            _option("actor-out", actor_capacity_measured=False),
            _option("thin", support_count=4),
            _option("uncertain", interval_status="unavailable"),
        ),
        policy=_policy(),
    )
    assert assessment.compatible_option_ids == ("inside",)
    assert assessment.exclusions == {
        "outside": "OUTSIDE_MEASURED_ENVELOPE",
        "actor-out": "ACTOR_CAPACITY_NOT_MEASURED",
        "thin": "SUPPORT_INSUFFICIENT: 4 < study policy 5",
        "uncertain": "UNCERTAINTY_UNAVAILABLE",
    }
    refused = assess((_option(interval_status="unavailable"),), policy=_policy())
    assert refused.status == "refused"


def test_deviations_propagate_and_hidden_deviations_refuse() -> None:
    assessment = assess(
        (_option(execution_deviations=("one fixed evaluation repeated",)),),
        policy=_policy(),
    )
    assert any(notice.code == "EXECUTION_DEVIATION" for notice in assessment.notices)
    with pytest.raises(DecisionSafetyError) as hidden:
        assess(
            (
                _option(
                    execution_deviations=("one fixed evaluation repeated",),
                    deviations_disclosed=False,
                ),
            ),
            policy=_policy(),
        )
    assert hidden.value.code == "EXECUTION_DEVIATION_UNACKNOWLEDGED"


def test_cause_wording_requires_digest_bound_scope_and_policy_support() -> None:
    with pytest.raises(DecisionSafetyError) as unbound:
        assess((_option(wording="the intervention causes the result"),), policy=_policy())
    assert unbound.value.code == "CAUSAL_SCOPE_UNSUPPORTED"

    scoped = assess(
        (
            _option(
                wording="inside the simulator, the intervention causes this transition",
                cause_scope="simulation_internal",
                cause_design_digest="e" * 64,
            ),
        ),
        policy=_policy(
            cause_design_authorities=(
                CauseDesignAuthority(design_digest="e" * 64, maximum_scope="simulation_internal"),
            )
        ),
    )
    assert scoped.causal_scope == "simulation_internal"
    with pytest.raises(DecisionSafetyError) as too_broad:
        assess(
            (
                _option(
                    cause_scope="real_world",
                    cause_design_digest="e" * 64,
                ),
            ),
            policy=_policy(
                maximum_cause_scope="simulation_internal",
                cause_design_authorities=(
                    CauseDesignAuthority(design_digest="e" * 64, maximum_scope="real_world"),
                ),
            ),
        )
    assert too_broad.value.code == "CAUSAL_SCOPE_UNSUPPORTED"

    real_world = assess(
        (
            _option(
                wording="the admitted field design causes this scoped real-world outcome",
                cause_scope="real_world",
                cause_design_digest="f" * 64,
            ),
        ),
        policy=_policy(
            maximum_cause_scope="real_world",
            cause_design_authorities=(
                CauseDesignAuthority(design_digest="f" * 64, maximum_scope="real_world"),
            ),
        ),
    )
    assert real_world.causal_scope == "real_world"


def test_private_content_global_superlatives_and_missing_owner_default_refuse() -> None:
    with pytest.raises(DecisionSafetyError) as private:
        assess((_option(wording="see /Users/someone/secret"),), policy=_policy())
    assert private.value.code == "PRIVATE_CONTENT_DETECTED"
    with pytest.raises(DecisionSafetyError) as global_claim:
        assess((_option(wording="this is universally best"),), policy=_policy())
    assert global_claim.value.code == "UNSUPPORTED_GENERALISATION"
    with pytest.raises(DecisionSafetyError) as default:
        assess((_option(),), policy=_policy(owner_preselected_default_option_id="missing"))
    assert default.value.code == "OWNER_DEFAULT_UNAVAILABLE"


def test_ruleset_digest_changes_with_study_specific_thresholds() -> None:
    five = _policy(minimum_support_count=5)
    twenty = _policy(minimum_support_count=20)
    assert ruleset_digest(five) != ruleset_digest(twenty)
    assert five.fixed_display_order == DISPLAY_ORDER


def test_confirmed_notice_is_digest_pinned_and_uses_v2_semantics() -> None:
    notice = confirmed_capacity_notice(REPO_ROOT)
    assert "8,310.9" in notice.text
    assert "[−9,097.5, −7,524.3]" in notice.text
    assert "p=0.0625" in notice.text
    assert "effectively flat" in notice.text
    assert "already-failed tasks" in notice.text
    assert "not an overall-service ranking" in notice.text
    assert notice.recommendation is False
    assert notice.evidence_backed is True
    assert notice.creates_new_evidence is False
    assert notice.causal_scope == "none"
    assert notice.execution_authority is False
    assert (REPO_ROOT / CONFIRMATORY_RECORD_PATH).is_file()


def test_stale_or_missing_records_refuse(tmp_path: Path) -> None:
    with pytest.raises(DecisionSafetyError) as missing:
        confirmed_capacity_notice(tmp_path)
    assert missing.value.code == "INPUT_DIGEST_MISMATCH"
    record = tmp_path / "stale" / CONFIRMATORY_RECORD_PATH
    record.parent.mkdir(parents=True)
    record.write_text("tampered", encoding="utf-8")
    with pytest.raises(DecisionSafetyError) as stale:
        confirmed_capacity_notice(tmp_path / "stale")
    assert stale.value.code == "INPUT_DIGEST_MISMATCH"


def test_no_execution_surface_exists() -> None:
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "decision_safety.py").read_text(
        encoding="utf-8"
    )
    assert "subprocess" not in source
    assert "execute_campaign" not in source
    assert "execution_authority: Literal[False]" in source
