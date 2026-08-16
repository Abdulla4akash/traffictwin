"""The recommendation LLM boundary: bounded input, guarded output, typed refusals."""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping

import pytest

from traffictwin.analyst.prose import ANALYST_DEEPSEEK_API_URL, AnalystProseError
from traffictwin.analyst.recommendation_prose import (
    RecommendationProse,
    RecommendationProseRequest,
    build_recommendation_prose_request,
    render_recommendation_prose,
)

_FIXTURE_KEY = "fixture" + "-recommendation-key"


def _request(**overrides: object) -> RecommendationProseRequest:
    values: dict[str, object] = {
        "category": "INVESTIGATE_RSU_LOAD_MANAGEMENT",
        "headline": "Investigate RSU load management",
        "rationale": (
            "The current evidence supports investigating infrastructure-side "
            "RSU load management before attributing the result to the "
            "learned offloading policy."
        ),
        "analyst_signal": "INFRASTRUCTURE_SIDE_SIGNAL",
        "confidence": "moderate",
        "evidence_standing": "SYNTHETIC",
        "supported_facts": (
            "R4-F1: The Jain capacity-normalised index is 0.71 against the "
            "configured maximum. [evidence: infra.load_balance."
            "jain_capacity_normalised]",
        ),
        "not_established": (
            "The evidence does not establish that infrastructure is the causal mechanism.",
        ),
        "missing_evidence": ("R5: this check could not evaluate on the selected evidence.",),
        "limitations": ("All selected evidence is synthetic.",),
        "alternative_category": None,
        "alternative_reason": None,
        "source_actions": (
            "R4: inspect placement and routing distribution — uneven load "
            "with headroom (conditional; prerequisite: same seed)",
        ),
        "packet_fingerprint": "b" * 64,
        "provenance_refs": ("analyst_packet:0123456789abcdef",),
    }
    values.update(overrides)
    return RecommendationProseRequest.model_validate(values)


def _content(
    explanation: str,
    why_not: str | None = None,
    next_explanation: str = (
        "A safe next investigation would inspect placement and routing "
        "distribution under the stated prerequisite."
    ),
) -> str:
    return json.dumps(
        {
            "recommendation_explanation": explanation,
            "why_not_alternative": why_not,
            "next_investigation_explanation": next_explanation,
        }
    )


_GOOD = (
    "TrafficTwin recommends investigating RSU load management: the Jain "
    "capacity-normalised index of 0.71 indicates uneven distribution while "
    "headroom remains. The evidence is synthetic and descriptive only, and "
    "the model-side check could not evaluate."
)


def _response(content: str, *, finish_reason: str = "stop") -> bytes:
    return json.dumps(
        {
            "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 80},
        }
    ).encode("utf-8")


class _Transport:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.calls: list[tuple[str, dict[str, str], bytes, float]] = []

    def __call__(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
        self.calls.append((url, dict(headers), body, timeout))
        return self.raw


class TestProviderBoundary:
    def test_without_a_key_nothing_is_sent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        transport = _Transport(_response(_content(_GOOD)))
        with pytest.raises(AnalystProseError) as excinfo:
            render_recommendation_prose(_request(), transport=transport)
        assert excinfo.value.code == "LLM_NOT_CONFIGURED"
        assert transport.calls == []

    def test_the_key_travels_in_the_header_never_the_body(self) -> None:
        transport = _Transport(_response(_content(_GOOD)))
        prose = render_recommendation_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert isinstance(prose, RecommendationProse)
        url, headers, body, _ = transport.calls[0]
        assert url == ANALYST_DEEPSEEK_API_URL
        assert headers["Authorization"] == f"Bearer {_FIXTURE_KEY}"
        assert _FIXTURE_KEY.encode() not in body
        payload = json.loads(body)
        user_content = json.loads(payload["messages"][1]["content"])
        assert user_content["category"] == "INVESTIGATE_RSU_LOAD_MANAGEMENT"

    def test_the_request_builder_accepts_no_user_text(self) -> None:
        parameters = inspect.signature(build_recommendation_prose_request).parameters
        assert list(parameters) == ["packet"], (
            "user free text must have no path into the provider request"
        )

    def test_private_content_is_refused_before_transport(self) -> None:
        transport = _Transport(_response(_content(_GOOD)))
        request = _request(supported_facts=("R4-F1: bundle at /Users/private/ws",))
        with pytest.raises(AnalystProseError) as excinfo:
            render_recommendation_prose(request, api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "PRIVATE_CONTENT_REFUSED"
        assert transport.calls == []

    def test_a_timeout_is_a_typed_refusal(self) -> None:
        def transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
            raise AnalystProseError("LLM_TIMEOUT", "DeepSeek could not be reached")

        with pytest.raises(AnalystProseError) as excinfo:
            render_recommendation_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "LLM_TIMEOUT"

    @pytest.mark.parametrize(
        "raw",
        [
            b"not json",
            _response("not json content"),
            _response(json.dumps({"recommendation_explanation": "x"})),
            _response(
                json.dumps(
                    {
                        "recommendation_explanation": "x",
                        "why_not_alternative": None,
                        "next_investigation_explanation": "y",
                        "extra_field": 1,
                    }
                )
            ),
            _response(_content("")),
        ],
    )
    def test_malformed_responses_are_typed_refusals(self, raw: bytes) -> None:
        with pytest.raises(AnalystProseError) as excinfo:
            render_recommendation_prose(_request(), api_key=_FIXTURE_KEY, transport=_Transport(raw))
        assert excinfo.value.code == "LLM_MALFORMED_RESPONSE"


class TestOutputGuards:
    def _refused(self, explanation: str, **request_overrides: object) -> str:
        transport = _Transport(_response(_content(explanation)))
        with pytest.raises(AnalystProseError) as excinfo:
            render_recommendation_prose(
                _request(**request_overrides), api_key=_FIXTURE_KEY, transport=transport
            )
        return excinfo.value.code

    def test_an_invented_number_is_refused(self) -> None:
        assert (
            self._refused("Rebalancing should recover 15 percent of deadline misses.")
            == "LLM_NUMBER_INVENTED"
        )

    def test_a_causal_claim_is_refused(self) -> None:
        assert (
            self._refused("This proves the imbalance caused the failures.")
            == "LLM_UNSUPPORTED_CLAIM"
        )

    def test_a_retraining_command_is_refused(self) -> None:
        assert (
            self._refused("The offloading policy should be retrained before anything else.")
            == "LLM_UNSUPPORTED_RETRAINING"
        )

    def test_an_expansion_command_is_refused(self) -> None:
        assert (
            self._refused("The operator should increase capacity at the busiest units.")
            == "LLM_UNSUPPORTED_EXPANSION"
        )

    def test_confidence_promotion_is_refused(self) -> None:
        assert (
            self._refused("TrafficTwin holds high confidence in this direction.")
            == "LLM_CONFIDENCE_PROMOTED"
        )

    def test_standing_promotion_is_refused(self) -> None:
        assert (
            self._refused("This admitted research shows uneven load distribution.")
            == "LLM_STANDING_PROMOTED"
        )

    def test_an_execution_claim_is_refused(self) -> None:
        assert (
            self._refused("The controlled what-if has been run and confirms the signal.")
            == "LLM_UNSUPPORTED_EXECUTION_CLAIM"
        )

    def test_a_mutated_recommendation_is_refused(self) -> None:
        assert (
            self._refused(
                "Instead, investigate the learned offloading policy or its training conditions."
            )
            == "LLM_RECOMMENDATION_MUTATED"
        )

    def test_naming_the_declared_alternative_is_allowed(self) -> None:
        transport = _Transport(
            _response(
                _content(
                    _GOOD,
                    why_not=(
                        "Investigate infrastructure capacity constraints under "
                        "a controlled variation remains a supported alternative "
                        "track, per the packet."
                    ),
                )
            )
        )
        prose = render_recommendation_prose(
            _request(
                alternative_category="INVESTIGATE_INFRASTRUCTURE_CAPACITY",
                alternative_reason="R2 also triggered.",
            ),
            api_key=_FIXTURE_KEY,
            transport=transport,
        )
        assert prose.why_not_alternative is not None

    def test_prose_output_carries_no_decision_fields(self) -> None:
        fields = set(RecommendationProse.model_fields)
        for forbidden in ("category", "confidence", "signal", "standing", "recommendation"):
            assert forbidden not in fields
        prose = render_recommendation_prose(
            _request(),
            api_key=_FIXTURE_KEY,
            transport=_Transport(_response(_content(_GOOD))),
        )
        assert prose.llm_output is True
        assert prose.evidence is False
        assert prose.approval is False
        assert prose.execution is False
        assert len(prose.input_digest) == 64
        assert len(prose.response_digest) == 64
