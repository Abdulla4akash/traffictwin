"""Deterministic challenge-candidate design and external-proposal guards."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from traffictwin.analyst.challenge_candidates import (
    HARDER_STEP_FRACTION,
    MAX_CANDIDATES,
    SUPPORTED_CANDIDATE_FIELDS,
    CandidateGenerationMode,
    CandidateValidationStatus,
    ChallengeFamily,
    ChallengeHypothesis,
    build_candidate_proposal_request,
    candidate_to_whatif_draft,
    default_candidate_baseline,
    design_candidates,
    match_hypothesis,
    propose_candidates_with_llm,
    validate_external_proposal,
)
from traffictwin.analyst.models import AnalystRefusalError
from traffictwin.analyst.prose import AnalystProseError
from traffictwin.ui.challenge_whatif_bridge import ChallengeWhatIfMappingStatus
from traffictwin.ui.whatif_controls import WHATIF_CONTROL_SPEC, is_value_representable


def _valid_external_payload() -> dict[str, object]:
    return {
        "title": "Bounded capacity squeeze",
        "family": "INFRASTRUCTURE_CAPACITY_PRESSURE",
        "intended_mechanism": "service capacity scarcity with headroom",
        "rationale": "pressure exactly one resource while the rest stays fixed",
        "changed_parameters": {"rsu_capacity": 12.0},
    }


# ---------------------------------------------------------------------------
# deterministic modes
# ---------------------------------------------------------------------------


def test_make_harder_prepares_bounded_single_mechanism_candidates() -> None:
    result = design_candidates(CandidateGenerationMode.MAKE_HARDER)
    assert result.outcome == "CANDIDATES_PREPARED"
    assert 1 <= len(result.candidates) <= MAX_CANDIDATES
    baseline = default_candidate_baseline()
    for candidate in result.candidates:
        assert candidate.validation_status is CandidateValidationStatus.VALID_CHALLENGE
        # single mechanism: one or two fields, never a broad sweep
        assert 1 <= len(candidate.changed_parameters) <= 2
        for change in candidate.changed_parameters:
            assert change.whatif_field in SUPPORTED_CANDIDATE_FIELDS
            assert change.baseline_value == baseline[change.whatif_field]


def test_make_harder_never_maximises_or_touches_bounds() -> None:
    result = design_candidates(CandidateGenerationMode.MAKE_HARDER)
    changed_fields: set[str] = set()
    for candidate in result.candidates:
        for change in candidate.changed_parameters:
            changed_fields.add(change.whatif_field)
            spec = WHATIF_CONTROL_SPEC.get(change.whatif_field)
            if spec is None or not isinstance(change.proposed_value, (int, float)):
                continue
            value = float(change.proposed_value)
            if "min" in spec:
                assert value > float(spec["min"]) + 1e-9
            if "max" in spec:
                assert value < float(spec["max"]) - 1e-9
    # "harder" pressures a few distinct mechanisms, not every control at once
    assert len(changed_fields) < len(SUPPORTED_CANDIDATE_FIELDS) / 2


def test_identical_inputs_produce_identical_candidate_sets() -> None:
    first = design_candidates(CandidateGenerationMode.SURPRISE_ME)
    second = design_candidates(CandidateGenerationMode.SURPRISE_ME)
    assert first.fingerprint() == second.fingerprint()
    assert [c.fingerprint() for c in first.candidates] == [
        c.fingerprint() for c in second.candidates
    ]


def test_candidates_are_meaningfully_distinct_mechanisms() -> None:
    for mode in (CandidateGenerationMode.MAKE_HARDER, CandidateGenerationMode.SURPRISE_ME):
        result = design_candidates(mode)
        families = [c.family for c in result.candidates]
        assert len(set(families)) == len(families)
        fingerprints = [c.mechanism_fingerprint() for c in result.candidates]
        assert len(set(fingerprints)) == len(fingerprints)


def test_changed_ledger_is_exact_and_held_constant_preserved() -> None:
    baseline = default_candidate_baseline()
    result = design_candidates(CandidateGenerationMode.MAKE_HARDER)
    candidate = next(c for c in result.candidates if c.family is ChallengeFamily.TASK_PRESSURE)
    (change,) = candidate.changed_parameters
    expected = round(float(baseline["task_arrival_rate"]) * (1 + HARDER_STEP_FRACTION), 6)
    assert change.proposed_value == expected
    held = {control.dimension for control in candidate.held_constant}
    assert "task_arrival_rate" not in held
    for field in SUPPORTED_CANDIDATE_FIELDS:
        if field != "task_arrival_rate":
            assert field in held
    assert any("metric contract" in dimension for dimension in held)


def test_task_mix_shift_keeps_shares_summing_to_one() -> None:
    result = design_candidates(CandidateGenerationMode.SURPRISE_ME)
    candidate = next(c for c in result.candidates if c.family is ChallengeFamily.TASK_MIX_SHIFT)
    proposed = {c.whatif_field: float(c.proposed_value) for c in candidate.changed_parameters}
    assert abs(sum(proposed.values()) - 1.0) < 1e-6
    for value in proposed.values():
        assert 0.0 < value < 1.0


def test_every_candidate_reports_prediction_unavailable() -> None:
    for mode in (CandidateGenerationMode.MAKE_HARDER, CandidateGenerationMode.SURPRISE_ME):
        for candidate in design_candidates(mode).candidates:
            assert candidate.prediction_status == "PREDICTION_UNAVAILABLE"
            assert "OUTSIDE_SUPPORTED_ENVELOPE" in candidate.prediction_reason


def test_every_candidate_carries_derived_synthetic_standing_and_no_authority() -> None:
    for candidate in design_candidates(CandidateGenerationMode.SURPRISE_ME).candidates:
        assert "not an observation" in candidate.evidence_standing
        assert candidate.execution_authority is False
        assert candidate.approval is False
        assert candidate.llm_evidence is False
        assert candidate.creates_new_evidence is False


# ---------------------------------------------------------------------------
# hypothesis mode
# ---------------------------------------------------------------------------


def test_placement_hypothesis_is_refused_not_approximated() -> None:
    result = design_candidates(
        CandidateGenerationMode.TEST_HYPOTHESIS,
        free_text="Create a scenario where infrastructure placement matters.",
    )
    assert result.outcome == "HYPOTHESIS_NOT_REPRESENTABLE"
    assert result.candidates == ()
    (reason,) = result.unrepresentable_reasons
    assert reason.idea == ChallengeHypothesis.INFRASTRUCTURE_PLACEMENT.value
    assert "placement" in reason.reason.lower()
    assert any("substitut" in note for note in result.designer_notes)


@pytest.mark.parametrize(
    ("text", "hypothesis"),
    [
        ("stress admission rejection", ChallengeHypothesis.ADMISSION_POLICY),
        ("queue pressure in the waiting room", ChallengeHypothesis.QUEUE_CAPACITY),
        ("weak onboard capability", ChallengeHypothesis.LOCAL_COMPUTE_CAPABILITY),
        ("task ordering stress", ChallengeHypothesis.TASK_ORDERING),
    ],
)
def test_other_unrepresentable_hypotheses_are_refused_by_name(
    text: str, hypothesis: ChallengeHypothesis
) -> None:
    result = design_candidates(CandidateGenerationMode.TEST_HYPOTHESIS, free_text=text)
    assert result.outcome == "HYPOTHESIS_NOT_REPRESENTABLE"
    assert result.unrepresentable_reasons[0].idea == hypothesis.value


def test_supported_hypotheses_yield_matching_families() -> None:
    result = design_candidates(
        CandidateGenerationMode.TEST_HYPOTHESIS,
        hypothesis=ChallengeHypothesis.TASK_PRIORITY_PRESSURE,
    )
    assert result.outcome == "CANDIDATES_PREPARED"
    assert result.candidates[0].family is ChallengeFamily.TASK_MIX_SHIFT
    interaction = design_candidates(
        CandidateGenerationMode.TEST_HYPOTHESIS,
        free_text="test the model and infrastructure interaction",
    )
    assert interaction.candidates[0].family is ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION


def test_unmatched_free_text_returns_insufficient_context_with_vocabulary() -> None:
    assert match_hypothesis("make it interesting somehow") is None
    result = design_candidates(
        CandidateGenerationMode.TEST_HYPOTHESIS, free_text="make it interesting somehow"
    )
    assert result.outcome == "INSUFFICIENT_CONTEXT"
    assert result.candidates == ()
    assert any(
        ChallengeHypothesis.INFRASTRUCTURE_CAPACITY.value in note for note in result.designer_notes
    )


def test_recommendation_context_only_reorders_families() -> None:
    unbiased = design_candidates(CandidateGenerationMode.MAKE_HARDER)
    biased = design_candidates(
        CandidateGenerationMode.MAKE_HARDER,
        recommendation_category="INVESTIGATE_INFRASTRUCTURE_CAPACITY",
    )
    assert biased.candidates[0].family is ChallengeFamily.INFRASTRUCTURE_CAPACITY_PRESSURE
    assert {c.family for c in biased.candidates} == {c.family for c in unbiased.candidates}
    with pytest.raises(AnalystRefusalError):
        design_candidates(
            CandidateGenerationMode.MAKE_HARDER,
            recommendation_category="RETRAIN_EVERYTHING",
        )


def test_insufficient_evidence_recommendation_adds_distinguishing_note() -> None:
    result = design_candidates(
        CandidateGenerationMode.SURPRISE_ME,
        recommendation_category="INSUFFICIENT_EVIDENCE",
    )
    assert any("distinguish competing explanations" in note for note in result.designer_notes)
    assert not any("prove" in c.why_informative.lower() for c in result.candidates)


# ---------------------------------------------------------------------------
# external (LLM) proposal validation
# ---------------------------------------------------------------------------


def test_valid_external_proposal_is_validated_and_labelled() -> None:
    candidate = validate_external_proposal(_valid_external_payload())
    assert candidate.generated_by == "llm_proposal_validated"
    assert candidate.llm_used is True
    assert candidate.llm_evidence is False
    # same family + field as a deterministic template → flagged redundant
    assert candidate.validation_status is CandidateValidationStatus.VALID_BUT_REDUNDANT


def test_external_proposal_cannot_invent_parameters() -> None:
    payload = _valid_external_payload()
    payload["changed_parameters"] = {"placement_mode": "least-busy"}
    with pytest.raises(AnalystProseError) as excinfo:
        validate_external_proposal(payload)
    assert excinfo.value.code == "LLM_UNKNOWN_PARAMETER"


def test_external_proposal_cannot_bypass_bounds() -> None:
    payload = _valid_external_payload()
    payload["family"] = "TRAFFIC_DEMAND_PRESSURE"
    payload["changed_parameters"] = {"congestion_multiplier": 9.0}
    with pytest.raises(AnalystProseError) as excinfo:
        validate_external_proposal(payload)
    assert excinfo.value.code == "LLM_BOUNDS_VIOLATION"
    payload["changed_parameters"] = {"policy_profile": "invented-profile"}
    with pytest.raises(AnalystProseError) as excinfo:
        validate_external_proposal(payload)
    assert excinfo.value.code == "LLM_BOUNDS_VIOLATION"


def test_external_proposal_cannot_claim_a_winner() -> None:
    payload = _valid_external_payload()
    payload["rationale"] = "the least-busy strategy will win under this pressure"
    with pytest.raises(AnalystProseError) as excinfo:
        validate_external_proposal(payload)
    assert excinfo.value.code == "LLM_WINNER_CLAIM_REFUSED"


def test_external_proposal_cannot_fabricate_evidence_or_numbers() -> None:
    payload = _valid_external_payload()
    payload["rationale"] = "evidence shows this separates the strategies"
    with pytest.raises(AnalystProseError) as excinfo:
        validate_external_proposal(payload)
    assert excinfo.value.code == "LLM_EVIDENCE_FABRICATED"
    payload = _valid_external_payload()
    payload["rationale"] = "expect a 37.5 point improvement"
    with pytest.raises(AnalystProseError) as excinfo:
        validate_external_proposal(payload)
    assert excinfo.value.code == "LLM_EVIDENCE_FABRICATED"


def test_external_proposal_schema_is_closed() -> None:
    payload = _valid_external_payload()
    payload["execute_now"] = True
    with pytest.raises(AnalystProseError) as excinfo:
        validate_external_proposal(payload)
    assert excinfo.value.code == "LLM_MALFORMED_RESPONSE"


def test_bound_saturated_external_proposal_is_flagged_trivial() -> None:
    payload = _valid_external_payload()
    payload["family"] = "TRAFFIC_DEMAND_PRESSURE"
    payload["changed_parameters"] = {"congestion_multiplier": 3.0}
    candidate = validate_external_proposal(payload)
    assert candidate.validation_status is CandidateValidationStatus.VALID_BUT_TRIVIAL
    assert any("maximal stress" in reason for reason in candidate.validation_reasons)


def test_unsupported_ideas_stay_visible_and_partial() -> None:
    payload = _valid_external_payload()
    payload["unsupported_ideas"] = ["tighten the admission policy"]
    candidate = validate_external_proposal(payload)
    assert candidate.validation_status is CandidateValidationStatus.PARTIALLY_REPRESENTABLE
    assert candidate.unsupported_ideas[0].idea == "tighten the admission policy"
    assert "never" in candidate.unsupported_ideas[0].reason


def test_cross_field_inconsistency_is_refused() -> None:
    payload = _valid_external_payload()
    payload["family"] = "TASK_MIX_SHIFT"
    payload["changed_parameters"] = {"task_mix_t1": 0.9}
    with pytest.raises(AnalystRefusalError) as excinfo:
        validate_external_proposal(payload)
    assert "sum to 1.0" in str(excinfo.value)


# ---------------------------------------------------------------------------
# LLM proposer transport boundary
# ---------------------------------------------------------------------------


def test_llm_proposer_requires_a_key_and_deterministic_modes_do_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    request = build_candidate_proposal_request(CandidateGenerationMode.SURPRISE_ME)
    with pytest.raises(AnalystProseError) as excinfo:
        propose_candidates_with_llm(request, api_key=None, transport=_forbidden_transport)
    assert excinfo.value.code == "LLM_NOT_CONFIGURED"
    # the deterministic product remains complete without any key
    assert design_candidates(CandidateGenerationMode.SURPRISE_ME).candidates


def _forbidden_transport(
    url: str, headers: object, body: bytes, timeout: float
) -> bytes:  # pragma: no cover - must never be called
    raise AssertionError("no provider request may occur without a key")


def test_llm_proposer_payload_contains_no_credentials_or_paths() -> None:
    request = build_candidate_proposal_request(CandidateGenerationMode.MAKE_HARDER)
    serialised = request.canonical_json()
    assert "DEEPSEEK" not in serialised
    assert "Authorization" not in serialised
    assert "Bearer" not in serialised
    assert "/Users/" not in serialised
    assert re.search(r"\bsk-[A-Za-z0-9]{16,}", serialised) is None
    payload = json.loads(serialised)
    assert set(payload["baseline"]) == set(SUPPORTED_CANDIDATE_FIELDS)


def test_llm_proposals_pass_through_deterministic_validation() -> None:
    request = build_candidate_proposal_request(CandidateGenerationMode.SURPRISE_ME)
    proposals_json = json.dumps(
        {
            "proposals": [
                {
                    "title": "Task mix stress",
                    "family": "TASK_MIX_SHIFT",
                    "intended_mechanism": "demanding task composition",
                    "rationale": "give the offloading decision a real role",
                    "changed_parameters": {
                        "task_mix_t1": 0.5,
                        "task_mix_t2": 0.3,
                        "task_mix_t3": 0.2,
                    },
                }
            ]
        }
    )
    raw = json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": proposals_json},
                }
            ]
        }
    ).encode("utf-8")

    def transport(url: str, headers: object, body: bytes, timeout: float) -> bytes:
        return raw

    (candidate,) = propose_candidates_with_llm(request, api_key="test-key", transport=transport)
    assert candidate.family is ChallengeFamily.TASK_MIX_SHIFT
    assert candidate.generated_by == "llm_proposal_validated"


def test_llm_winner_claim_inside_transport_response_is_refused() -> None:
    request = build_candidate_proposal_request(CandidateGenerationMode.SURPRISE_ME)
    proposals_json = json.dumps(
        {
            "proposals": [
                {
                    "title": "Rigged scenario",
                    "family": "TASK_PRESSURE",
                    "intended_mechanism": "task pressure",
                    "rationale": "the simpler policy is guaranteed to look better",
                    "changed_parameters": {"task_arrival_rate": 0.2},
                }
            ]
        }
    )
    raw = json.dumps(
        {"choices": [{"finish_reason": "stop", "message": {"content": proposals_json}}]}
    ).encode("utf-8")
    with pytest.raises(AnalystProseError) as excinfo:
        propose_candidates_with_llm(request, api_key="test-key", transport=lambda *args: raw)
    assert excinfo.value.code == "LLM_WINNER_CLAIM_REFUSED"


# ---------------------------------------------------------------------------
# What-If Studio handoff
# ---------------------------------------------------------------------------


def test_handoff_draft_carries_exact_overrides_and_no_execution() -> None:
    result = design_candidates(CandidateGenerationMode.MAKE_HARDER)
    candidate = result.candidates[0]
    draft = candidate_to_whatif_draft(candidate)
    assert draft.mapping_status is ChallengeWhatIfMappingStatus.FULLY_MAPPABLE
    expected = {c.whatif_field: c.proposed_value for c in candidate.changed_parameters}
    assert draft.whatif_overrides == expected
    for field, value in draft.whatif_overrides.items():
        if field != "policy_profile":
            assert is_value_representable(field, value)[0]
    assert any("Nothing has been executed" in warning for warning in draft.warnings)
    assert draft.evidence_standing == candidate.evidence_standing


def test_handoff_enables_incident_when_incident_fields_change() -> None:
    result = design_candidates(CandidateGenerationMode.SURPRISE_ME)
    candidate = next(c for c in result.candidates if c.family is ChallengeFamily.INCIDENT_PRESSURE)
    draft = candidate_to_whatif_draft(candidate)
    assert draft.whatif_overrides["incident_enabled"] is True


def test_partial_candidate_hands_off_supported_subset_only() -> None:
    payload = _valid_external_payload()
    payload["unsupported_ideas"] = ["tighten the admission policy"]
    candidate = validate_external_proposal(payload)
    draft = candidate_to_whatif_draft(candidate)
    assert draft.mapping_status is ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE
    assert draft.unsupported_fields[0].challenge_value == "tighten the admission policy"
    assert "admission" not in json.dumps(draft.whatif_overrides)


def test_handoff_is_pure_and_writes_nothing(tmp_path: Path) -> None:
    result = design_candidates(CandidateGenerationMode.MAKE_HARDER)
    before = sorted(tmp_path.rglob("*"))
    candidate_to_whatif_draft(result.candidates[0])
    assert sorted(tmp_path.rglob("*")) == before


# ---------------------------------------------------------------------------
# module-level boundaries
# ---------------------------------------------------------------------------


def test_no_execution_retraining_or_research_path_exists() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "src/traffictwin/analyst/challenge_candidates.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "subprocess",
        "execute_campaign",
        "vec_fresh",
        "run_vec_evaluator",
        "generate_run_data",
        "retrain",
        "training_run",
        "kubernetes",
    ):
        assert forbidden not in source, forbidden
