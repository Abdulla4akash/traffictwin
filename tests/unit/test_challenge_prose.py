"""The challenge LLM boundary: bounded input, guarded output, typed refusals."""

from __future__ import annotations

import inspect
import json
from collections.abc import Mapping

import pytest

from traffictwin.analyst.challenge_prose import (
    ChallengeProse,
    ChallengeProseRequest,
    build_challenge_prose_request,
    render_challenge_prose,
)
from traffictwin.analyst.prose import ANALYST_DEEPSEEK_API_URL, AnalystProseError

_FIXTURE_KEY = "fixture" + "-challenge-key"


def _request(**overrides: object) -> ChallengeProseRequest:
    values: dict[str, object] = {
        "challenge_category": "INFRASTRUCTURE_CAPACITY_CHALLENGE",
        "headline": "Vary service capacity under a fixed model and scenario",
        "statement": (
            "Prepare a controlled comparison in which the service/compute "
            "capacity level changes while the model profile, scenario, seed "
            "and metric definitions remain fixed."
        ),
        "readiness": "NEEDS_USER_INPUT",
        "analyst_signal": "INFRASTRUCTURE_SIDE_SIGNAL",
        "recommendation_category": "INVESTIGATE_INFRASTRUCTURE_CAPACITY",
        "confidence": "moderate",
        "evidence_standing": "SYNTHETIC",
        "track_titles": ("Vary service/compute capacity (rsu_capacity)",),
        "variables_under_investigation": (
            "RSU service/compute concurrency capacity (rsu_capacity)",
        ),
        "held_fixed_dimensions": ("policy_profile", "congestion_multiplier", "random_seed"),
        "required_user_inputs": (
            "Select the comparison service-capacity level for the variation arm.",
        ),
        "unsupported_dimensions": ("waiting-room/queue capacity (not separately exposed)",),
        "expected_observables": ("task.completion.rate", "infra.utilisation.p95"),
        "could_support": ("Whether outcomes change under a capacity variation.",),
        "cannot_establish": ("It does not establish a causal mechanism.",),
        "missing_evidence": ("R5: this check could not evaluate on the selected evidence.",),
        "limitations": ("All selected evidence is synthetic.",),
        "challenge_fingerprint": "c" * 64,
        "provenance_refs": ("analyst_packet:0123456789abcdef",),
    }
    values.update(overrides)
    return ChallengeProseRequest.model_validate(values)


_GOOD = (
    "This challenge varies the service capacity dimension while the policy "
    "profile, scenario and seed stay fixed, so any change in the observed "
    "task outcomes can be attributed to the controlled variation rather "
    "than a mixture of mechanisms. One capacity level still needs your "
    "selection. The evidence is synthetic and descriptive only."
)


def _content(
    explanation: str = _GOOD,
    control: str = (
        "The policy profile and scenario dimensions are held fixed so the "
        "comparison isolates the capacity dimension."
    ),
    boundary: str = (
        "The comparison cannot establish a causal mechanism and does not "
        "rank configurations as generally better."
    ),
) -> str:
    return json.dumps(
        {
            "challenge_explanation": explanation,
            "control_explanation": control,
            "interpretation_boundary": boundary,
        }
    )


def _response(content: str, *, finish_reason: str = "stop") -> bytes:
    return json.dumps(
        {
            "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 90},
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
        transport = _Transport(_response(_content()))
        with pytest.raises(AnalystProseError) as excinfo:
            render_challenge_prose(_request(), transport=transport)
        assert excinfo.value.code == "LLM_NOT_CONFIGURED"
        assert transport.calls == []

    def test_the_key_travels_in_the_header_never_the_body(self) -> None:
        transport = _Transport(_response(_content()))
        prose = render_challenge_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert isinstance(prose, ChallengeProse)
        url, headers, body, _ = transport.calls[0]
        assert url == ANALYST_DEEPSEEK_API_URL
        assert headers["Authorization"] == f"Bearer {_FIXTURE_KEY}"
        assert _FIXTURE_KEY.encode() not in body
        user_content = json.loads(json.loads(body)["messages"][1]["content"])
        assert user_content["challenge_category"] == "INFRASTRUCTURE_CAPACITY_CHALLENGE"

    def test_the_request_builder_accepts_no_user_text(self) -> None:
        parameters = inspect.signature(build_challenge_prose_request).parameters
        assert list(parameters) == ["spec"], (
            "user free text must have no path into the provider request"
        )

    def test_private_content_is_refused_before_transport(self) -> None:
        transport = _Transport(_response(_content()))
        request = _request(limitations=("bundle at /Users/private/ws",))
        with pytest.raises(AnalystProseError) as excinfo:
            render_challenge_prose(request, api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "PRIVATE_CONTENT_REFUSED"
        assert transport.calls == []

    def test_a_timeout_is_a_typed_refusal(self) -> None:
        def transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
            raise AnalystProseError("LLM_TIMEOUT", "DeepSeek could not be reached")

        with pytest.raises(AnalystProseError) as excinfo:
            render_challenge_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "LLM_TIMEOUT"

    @pytest.mark.parametrize(
        "raw",
        [
            b"not json",
            _response("not json content"),
            _response(json.dumps({"challenge_explanation": "x"})),
            _response(
                json.dumps(
                    {
                        "challenge_explanation": "x",
                        "control_explanation": "y",
                        "interpretation_boundary": "z",
                        "extra": 1,
                    }
                )
            ),
            _response(_content(explanation="")),
        ],
    )
    def test_malformed_responses_are_typed_refusals(self, raw: bytes) -> None:
        with pytest.raises(AnalystProseError) as excinfo:
            render_challenge_prose(_request(), api_key=_FIXTURE_KEY, transport=_Transport(raw))
        assert excinfo.value.code == "LLM_MALFORMED_RESPONSE"


class TestOutputGuards:
    def _refused(self, explanation: str, **request_overrides: object) -> str:
        transport = _Transport(_response(_content(explanation=explanation)))
        with pytest.raises(AnalystProseError) as excinfo:
            render_challenge_prose(
                _request(**request_overrides), api_key=_FIXTURE_KEY, transport=transport
            )
        return excinfo.value.code

    def test_an_invented_number_is_refused(self) -> None:
        assert (
            self._refused("Compare capacity 22 against capacity 44 for best effect.")
            == "LLM_NUMBER_INVENTED"
        )

    def test_a_proof_claim_is_refused(self) -> None:
        assert (
            self._refused("This comparison will prove the capacity mechanism.")
            == "LLM_UNSUPPORTED_CLAIM"
        )

    def test_a_causal_claim_is_refused(self) -> None:
        assert (
            self._refused("The failures were caused by the capacity limit.")
            == "LLM_UNSUPPORTED_CLAIM"
        )

    def test_an_unrequested_dimension_is_refused(self) -> None:
        assert (
            self._refused("Also consider varying vehicle_count alongside capacity.")
            == "LLM_CHALLENGE_MUTATED"
        )

    def test_an_unselected_profile_is_refused(self) -> None:
        assert (
            self._refused("Try the synthetic-always-local profile instead.")
            == "LLM_CHALLENGE_MUTATED"
        )

    def test_readiness_promotion_is_refused(self) -> None:
        assert (
            self._refused("The challenge is ready to run without further input.")
            == "LLM_READINESS_PROMOTED"
        )

    def test_an_execution_claim_is_refused(self) -> None:
        assert (
            self._refused("The controlled comparison was executed and behaved as expected.")
            == "LLM_UNSUPPORTED_EXECUTION_CLAIM"
        )

    def test_a_result_claim_is_refused(self) -> None:
        assert (
            self._refused("The results show that capacity dominates the outcome.")
            == "LLM_UNSUPPORTED_EXECUTION_CLAIM"
        )

    def test_standing_promotion_is_refused(self) -> None:
        assert (
            self._refused("This admitted research design isolates capacity.")
            == "LLM_STANDING_PROMOTED"
        )

    def test_prose_output_carries_no_authority_fields(self) -> None:
        fields = set(ChallengeProse.model_fields)
        for forbidden in (
            "category",
            "readiness",
            "confidence",
            "standing",
            "parameters",
            "overrides",
            "fingerprint",
        ):
            assert forbidden not in fields
        prose = render_challenge_prose(
            _request(), api_key=_FIXTURE_KEY, transport=_Transport(_response(_content()))
        )
        assert prose.llm_output is True
        assert prose.evidence is False
        assert prose.approval is False
        assert prose.execution is False
        assert len(prose.input_digest) == 64
        assert len(prose.response_digest) == 64
