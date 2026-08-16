"""The Analyst LLM boundary: bounded input, guarded output, typed refusals."""

from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from traffictwin.analyst.prose import (
    ANALYST_DEEPSEEK_API_URL,
    AnalystProse,
    AnalystProseError,
    AnalystProseRequest,
    render_analyst_prose,
)

_FIXTURE_KEY = "fixture" + "-deepseek-key"


def _request(**overrides: object) -> AnalystProseRequest:
    values: dict[str, object] = {
        "signal": "INFRASTRUCTURE_SIDE_SIGNAL",
        "statement": (
            "Within the selected evidence, the strongest supported signal is infrastructure-side."
        ),
        "confidence": "moderate",
        "supported_facts": (
            "R2-F1: P95 utilisation is compared with the configured "
            "saturation threshold. [evidence: infra.utilisation.p95] "
            "observed 0.95",
        ),
        "not_supported": ("R5: this check could not evaluate on the selected evidence.",),
        "limitations": ("All selected evidence is synthetic.",),
        "unavailable_metric_keys": ("task.offload.rate",),
        "evidence_standing": "SYNTHETIC",
        "next_investigation": "test increased RSU capacity in a controlled variation",
        "packet_fingerprint": "a" * 64,
        "evidence_refs": ("diagnostics:0123456789abcdef",),
    }
    values.update(overrides)
    return AnalystProseRequest.model_validate(values)


def _response(
    explanation: str = (
        "The strongest supported signal is infrastructure-side: P95 "
        "utilisation reached 0.95 against the configured threshold, while "
        "the model-side checks could not evaluate. The evidence is "
        "synthetic and descriptive only."
    ),
    next_investigation: str | None = "test increased RSU capacity in a controlled variation",
    *,
    content: str | None = None,
    finish_reason: str = "stop",
) -> bytes:
    if content is None:
        content = json.dumps({"explanation": explanation, "next_investigation": next_investigation})
    return json.dumps(
        {
            "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 60},
        }
    ).encode("utf-8")


class _Transport:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.calls: list[tuple[str, dict[str, str], bytes, float]] = []

    def __call__(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
        self.calls.append((url, dict(headers), body, timeout))
        return self.raw


class TestConfigurationGate:
    def test_without_a_key_nothing_is_sent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        transport = _Transport(_response())
        with pytest.raises(AnalystProseError) as excinfo:
            render_analyst_prose(_request(), transport=transport)
        assert excinfo.value.code == "LLM_NOT_CONFIGURED"
        assert transport.calls == []

    def test_the_key_travels_in_the_header_never_the_body(self) -> None:
        transport = _Transport(_response())
        prose = render_analyst_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert isinstance(prose, AnalystProse)
        url, headers, body, timeout = transport.calls[0]
        assert url == ANALYST_DEEPSEEK_API_URL
        assert headers["Authorization"] == f"Bearer {_FIXTURE_KEY}"
        assert _FIXTURE_KEY.encode() not in body
        payload = json.loads(body)
        assert payload["temperature"] == 0
        assert payload["response_format"] == {"type": "json_object"}
        user_content = payload["messages"][1]["content"]
        assert json.loads(user_content)["signal"] == "INFRASTRUCTURE_SIDE_SIGNAL"

    def test_private_content_is_refused_before_transport(self) -> None:
        transport = _Transport(_response())
        request = _request(supported_facts=("R2-F1: artifact at /Users/someone/private/bundle",))
        with pytest.raises(AnalystProseError) as excinfo:
            render_analyst_prose(request, api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "PRIVATE_CONTENT_REFUSED"
        assert transport.calls == []


class TestTypedTransportFailures:
    def test_a_timeout_is_a_typed_refusal(self) -> None:
        def transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
            raise AnalystProseError(
                "LLM_TIMEOUT", "DeepSeek could not be reached within the timeout"
            )

        with pytest.raises(AnalystProseError) as excinfo:
            render_analyst_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "LLM_TIMEOUT"

    @pytest.mark.parametrize(
        ("raw", "code"),
        [
            (b"not json", "LLM_MALFORMED_RESPONSE"),
            (b'{"choices": []}', "LLM_MALFORMED_RESPONSE"),
            (_response(finish_reason="length"), "LLM_MALFORMED_RESPONSE"),
            (_response(content="not json content"), "LLM_MALFORMED_RESPONSE"),
            (_response(content='{"explanation": "x", "extra": 1}'), "LLM_MALFORMED_RESPONSE"),
            (
                _response(content='{"explanation": "", "next_investigation": null}'),
                "LLM_MALFORMED_RESPONSE",
            ),
        ],
    )
    def test_malformed_responses_are_typed_refusals(self, raw: bytes, code: str) -> None:
        with pytest.raises(AnalystProseError) as excinfo:
            render_analyst_prose(_request(), api_key=_FIXTURE_KEY, transport=_Transport(raw))
        assert excinfo.value.code == code


class TestOutputGuards:
    def test_an_invented_number_is_refused(self) -> None:
        transport = _Transport(
            _response(explanation="Adding 3 RSUs will improve performance by 17 percent.")
        )
        with pytest.raises(AnalystProseError) as excinfo:
            render_analyst_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "LLM_NUMBER_INVENTED"

    def test_unsupported_claim_language_is_refused(self) -> None:
        transport = _Transport(
            _response(explanation="This proves that the infrastructure caused the failure.")
        )
        with pytest.raises(AnalystProseError) as excinfo:
            render_analyst_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "LLM_UNSUPPORTED_CLAIM"

    def test_evidence_standing_promotion_is_refused(self) -> None:
        transport = _Transport(
            _response(
                explanation=(
                    "The evidence stands as admitted research supporting the "
                    "infrastructure interpretation."
                )
            )
        )
        with pytest.raises(AnalystProseError) as excinfo:
            render_analyst_prose(_request(), api_key=_FIXTURE_KEY, transport=transport)
        assert excinfo.value.code == "LLM_STANDING_PROMOTED"

    def test_prose_output_carries_no_classification_field(self) -> None:
        prose = render_analyst_prose(
            _request(), api_key=_FIXTURE_KEY, transport=_Transport(_response())
        )
        assert "signal" not in AnalystProse.model_fields
        assert "classification" not in AnalystProse.model_fields
        assert prose.llm_output is True
        assert prose.evidence is False
        assert prose.approval is False
        assert prose.execution is False
        assert len(prose.input_digest) == 64
        assert len(prose.response_digest) == 64
