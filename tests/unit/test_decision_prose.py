"""The LLM can only explain the decision; every escape hatch is guarded."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from traffictwin.analyst import (
    RecommendationDecision,
    build_analyst_packet,
    build_decision_prose_request,
    classify_packet,
    decide_recommendation,
    decision_prose_status,
    render_decision_prose,
    select_recommendation,
)
from traffictwin.analyst.prose import AnalystProseError
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.services.bundles import validate_bundle_for_ui

FIXTURE_KEY = "fixture" + "-decision-key"


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("decision-prose") / "demo"
    initialise_workspace(workspace)
    return workspace


@pytest.fixture(scope="module")
def model_decision(demo_workspace: Path) -> RecommendationDecision:
    baseline = validate_bundle_for_ui(demo_workspace / "bundles" / "baseline")
    variation = validate_bundle_for_ui(demo_workspace / "bundles" / "under_offloading")
    packet = build_analyst_packet(baseline, variation)
    classification = classify_packet(packet)
    recommendation = select_recommendation(packet, classification)
    return decide_recommendation(packet, classification, recommendation)


def _transport_returning(fields: dict[str, object]) -> object:
    def transport(url: str, headers: object, body: bytes, timeout: float) -> bytes:
        del url, headers, body, timeout
        return json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(fields)},
                    }
                ]
            }
        ).encode("utf-8")

    return transport


_VALID_FIELDS = {
    "decision_explanation": (
        "TrafficTwin recommends inspecting the policy's offloading decision "
        "distribution first, because the model-side check triggered while "
        "the infrastructure checks did not."
    ),
    "why_not_explanation": (
        "Retraining stays unavailable because the comparison does not isolate the policy identity."
    ),
    "evidence_gap_explanation": (
        "Training-to-validation evidence is unavailable on synthetic "
        "bundles, so that check could not evaluate."
    ),
}


class TestHappyPath:
    def test_valid_prose_renders_with_digests_only(
        self, model_decision: RecommendationDecision
    ) -> None:
        request = build_decision_prose_request(model_decision)
        prose = render_decision_prose(
            request,
            model_decision,
            api_key=FIXTURE_KEY,
            transport=_transport_returning(_VALID_FIELDS),  # type: ignore[arg-type]
        )
        assert prose.llm_output is True
        assert prose.evidence is False
        assert prose.approval is False
        assert prose.execution is False
        assert prose.input_digest
        assert prose.response_digest

    def test_the_request_contains_no_user_text_parameter(
        self, model_decision: RecommendationDecision
    ) -> None:
        request = build_decision_prose_request(model_decision)
        assert request.decision_fingerprint == model_decision.fingerprint()
        assert request.ranked_candidates
        assert request.excluded_candidates
        assert request.retraining_gate_lines


class TestGuards:
    def test_prose_cannot_switch_the_direction(
        self, model_decision: RecommendationDecision
    ) -> None:
        fields = dict(_VALID_FIELDS)
        fields["decision_explanation"] = (
            "Actually an Infrastructure/resource-side investigation is the "
            "better recommendation here."
        )
        with pytest.raises(AnalystProseError) as error:
            render_decision_prose(
                build_decision_prose_request(model_decision),
                model_decision,
                api_key=FIXTURE_KEY,
                transport=_transport_returning(fields),  # type: ignore[arg-type]
            )
        assert error.value.code == "LLM_DECISION_MUTATED"

    def test_prose_cannot_promote_an_excluded_candidate(
        self, model_decision: RecommendationDecision
    ) -> None:
        fields = dict(_VALID_FIELDS)
        fields["decision_explanation"] = (
            "The best next step is to investigate infrastructure-side RSU load management."
        )
        with pytest.raises(AnalystProseError) as error:
            render_decision_prose(
                build_decision_prose_request(model_decision),
                model_decision,
                api_key=FIXTURE_KEY,
                transport=_transport_returning(fields),  # type: ignore[arg-type]
            )
        assert error.value.code == "LLM_CANDIDATE_PROMOTED"

    def test_excluded_candidates_stay_discussable_in_the_why_not_field(
        self, model_decision: RecommendationDecision
    ) -> None:
        fields = dict(_VALID_FIELDS)
        fields["why_not_explanation"] = (
            "Investigate infrastructure-side RSU load management was "
            "excluded because its check did not trigger."
        )
        prose = render_decision_prose(
            build_decision_prose_request(model_decision),
            model_decision,
            api_key=FIXTURE_KEY,
            transport=_transport_returning(fields),  # type: ignore[arg-type]
        )
        assert prose.why_not_explanation is not None

    def test_prose_cannot_invent_numbers(self, model_decision: RecommendationDecision) -> None:
        fields = dict(_VALID_FIELDS)
        fields["decision_explanation"] = "Deadline attainment fell by 37.5 points."
        with pytest.raises(AnalystProseError) as error:
            render_decision_prose(
                build_decision_prose_request(model_decision),
                model_decision,
                api_key=FIXTURE_KEY,
                transport=_transport_returning(fields),  # type: ignore[arg-type]
            )
        assert error.value.code == "LLM_NUMBER_INVENTED"

    def test_prose_cannot_command_retraining(self, model_decision: RecommendationDecision) -> None:
        fields = dict(_VALID_FIELDS)
        fields["decision_explanation"] = "The policy should be retrained immediately."
        with pytest.raises(AnalystProseError) as error:
            render_decision_prose(
                build_decision_prose_request(model_decision),
                model_decision,
                api_key=FIXTURE_KEY,
                transport=_transport_returning(fields),  # type: ignore[arg-type]
            )
        assert error.value.code == "LLM_UNSUPPORTED_RETRAINING"

    def test_a_mismatched_request_is_refused_before_any_transport(
        self, model_decision: RecommendationDecision, demo_workspace: Path
    ) -> None:
        baseline = validate_bundle_for_ui(demo_workspace / "bundles" / "baseline")
        packet = build_analyst_packet(baseline)
        classification = classify_packet(packet)
        recommendation = select_recommendation(packet, classification)
        other = decide_recommendation(packet, classification, recommendation)

        def exploding_transport(*args: object) -> bytes:
            raise AssertionError("transport must not be reached")

        with pytest.raises(AnalystProseError) as error:
            render_decision_prose(
                build_decision_prose_request(other),
                model_decision,
                api_key=FIXTURE_KEY,
                transport=exploding_transport,
            )
        assert error.value.code == "LLM_INPUT_MISMATCH"


class TestFailureModes:
    def test_no_key_is_a_typed_refusal_and_status_reports_it(
        self, model_decision: RecommendationDecision, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        status = decision_prose_status()
        assert status["configured"] is False
        assert status["mode"] == "deterministic_only"
        with pytest.raises(AnalystProseError) as error:
            render_decision_prose(
                build_decision_prose_request(model_decision),
                model_decision,
                transport=_transport_returning(_VALID_FIELDS),  # type: ignore[arg-type]
            )
        assert error.value.code == "LLM_NOT_CONFIGURED"

    def test_transport_failure_stays_typed(self, model_decision: RecommendationDecision) -> None:
        def failing_transport(*args: object) -> bytes:
            raise AnalystProseError("LLM_TIMEOUT", "DeepSeek could not be reached")

        with pytest.raises(AnalystProseError) as error:
            render_decision_prose(
                build_decision_prose_request(model_decision),
                model_decision,
                api_key=FIXTURE_KEY,
                transport=failing_transport,
            )
        assert error.value.code == "LLM_TIMEOUT"

    def test_wrong_fields_are_malformed(self, model_decision: RecommendationDecision) -> None:
        with pytest.raises(AnalystProseError) as error:
            render_decision_prose(
                build_decision_prose_request(model_decision),
                model_decision,
                api_key=FIXTURE_KEY,
                transport=_transport_returning({"verdict": "retrain"}),  # type: ignore[arg-type]
            )
        assert error.value.code == "LLM_MALFORMED_RESPONSE"

    def test_the_decision_is_never_an_output_of_prose(
        self, model_decision: RecommendationDecision
    ) -> None:
        before = model_decision.canonical_json()
        render_decision_prose(
            build_decision_prose_request(model_decision),
            model_decision,
            api_key=FIXTURE_KEY,
            transport=_transport_returning(_VALID_FIELDS),  # type: ignore[arg-type]
        )
        assert model_decision.canonical_json() == before
