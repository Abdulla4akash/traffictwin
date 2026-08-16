"""Bounded LLM prose rendering for the Analyst.

The LLM receives only the validated prose request derived from the
Analyst Evidence Packet — never raw CSV, never a repository file, never
the user's free text. It returns prose only. Deterministic guards refuse
any response that introduces a number absent from the request, uses
unsupported causal/proof/optimality language (via the existing XAI
language gate), or promotes evidence standing. On any refusal the
deterministic presentation stands alone; the LLM is an optional
enhancement, exactly as ADR-005 allows.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from hashlib import sha256
from typing import Literal, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from traffictwin.analyst.models import (
    AnalystClassification,
    AnalystEvidencePacket,
    AnalystModel,
)
from traffictwin.platform.xai_instrumentation import (
    XaiInstrumentationError,
    validate_explanation_language,
)

ANALYST_DEEPSEEK_API_URL: Literal["https://api.deepseek.com/chat/completions"] = (
    "https://api.deepseek.com/chat/completions"
)
ANALYST_DEEPSEEK_MODEL: Literal["deepseek-v4-flash"] = "deepseek-v4-flash"
ANALYST_MAX_INPUT_CHARACTERS = 8_000
ANALYST_MAX_RESPONSE_BYTES = 16_384
ANALYST_MAX_EXPLANATION_CHARACTERS = 1_200
ANALYST_TIMEOUT_SECONDS = 20.0

AnalystTransport = Callable[[str, Mapping[str, str], bytes, float], bytes]

_ANALYST_SYSTEM_PROMPT = (
    "Rewrite one TrafficTwin deterministic analysis packet as concise plain "
    "language. Return JSON only with exactly these keys: explanation "
    "(string), next_investigation (string or null). Use only the facts, "
    "numbers, limitations and classification present in the packet. Do not "
    "add numbers, evidence, causes, probabilities, approvals or certainty. "
    "Do not change or dispute the classification. Do not present synthetic "
    "evidence as real observation. Keep the explanation under 120 words."
)
ANALYST_PROMPT_TEMPLATE_DIGEST = sha256(_ANALYST_SYSTEM_PROMPT.encode("utf-8")).hexdigest()

_PRIVATE_PATTERNS = (
    re.compile(r"/Users/|/home/", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
    re.compile(r"api[ _-]?key|password|credential|bearer|private key", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"raw BODS", re.IGNORECASE),
    re.compile(r"participant(_id|_code|_response|_data)?", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
)

_STANDING_PROMOTION_MARKERS = (
    "admitted research",
    "manchester observation",
    "real-world measurement",
    "ground truth",
    "scientifically validated",
)

_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


class AnalystProseError(RuntimeError):
    """Typed prose refusal; the deterministic presentation stands alone."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class AnalystProseRequest(AnalystModel):
    """The only content that ever reaches the LLM."""

    schema_version: Literal["analyst-prose-request-1.0"] = "analyst-prose-request-1.0"
    signal: str
    statement: str
    confidence: str
    supported_facts: tuple[str, ...] = ()
    not_supported: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    unavailable_metric_keys: tuple[str, ...] = ()
    evidence_standing: str
    next_investigation: str | None = None
    packet_fingerprint: str
    evidence_refs: tuple[str, ...] = ()

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class AnalystProse(AnalystModel):
    """LLM prose with digests only; never evidence, never authority."""

    provider: Literal["deepseek"] = "deepseek"
    model: Literal["deepseek-v4-flash"] = ANALYST_DEEPSEEK_MODEL
    prompt_template_digest: str
    input_digest: str
    response_digest: str
    explanation: str
    next_investigation: str | None = None
    llm_output: Literal[True] = True
    evidence: Literal[False] = False
    approval: Literal[False] = False
    execution: Literal[False] = False


def build_prose_request(
    packet: AnalystEvidencePacket, classification: AnalystClassification
) -> AnalystProseRequest:
    """Project the packet into the bounded structure the LLM may see."""

    standing: str = packet.identity.baseline_standing
    if packet.identity.variation_standing not in (None, standing):
        standing = "MIXED"
    refs = tuple(
        f"{name}:{value[:16]}"
        for name, value in (
            ("baseline_bundle", packet.provenance.baseline_bundle_fingerprint),
            ("variation_bundle", packet.provenance.variation_bundle_fingerprint),
            ("diagnostics", packet.provenance.subject_diagnostic_fingerprint),
            ("consequence_lens", packet.provenance.consequence_lens_fingerprint),
        )
        if value is not None
    )
    return AnalystProseRequest(
        signal=classification.signal.value,
        statement=classification.statement,
        confidence=classification.confidence,
        supported_facts=classification.supported_facts,
        not_supported=classification.not_supported,
        limitations=packet.limitations,
        unavailable_metric_keys=packet.unavailable_metric_keys,
        evidence_standing=standing,
        next_investigation=classification.next_investigation,
        packet_fingerprint=classification.packet_fingerprint,
        evidence_refs=refs,
    )


def analyst_prose_status(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    """Report configuration without probing, displaying or hashing the key."""

    source = os.environ if environment is None else environment
    configured = bool(source.get("DEEPSEEK_API_KEY"))
    return {
        "configured": configured,
        "provider": "deepseek",
        "model": ANALYST_DEEPSEEK_MODEL,
        "mode": "deepseek_prose" if configured else "deterministic_only",
        "reason": None if configured else "DEEPSEEK_API_KEY is not set in this process",
    }


def _default_transport(
    url: str, headers: Mapping[str, str], body: bytes, timeout_seconds: float
) -> bytes:
    request = Request(url, data=body, headers=dict(headers), method="POST")  # noqa: S310
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            raw = cast(bytes, response.read(ANALYST_MAX_RESPONSE_BYTES + 1))
    except HTTPError as error:
        if error.code in {401, 403}:
            code = "LLM_AUTH_FAILED"
        elif error.code == 402:
            code = "LLM_BILLING_UNAVAILABLE"
        elif error.code == 429:
            code = "LLM_RATE_LIMITED"
        else:
            code = "LLM_PROVIDER_UNAVAILABLE"
        raise AnalystProseError(code, f"DeepSeek returned HTTP {error.code}") from error
    except (TimeoutError, URLError) as error:
        raise AnalystProseError(
            "LLM_TIMEOUT", "DeepSeek could not be reached within the timeout"
        ) from error
    if len(raw) > ANALYST_MAX_RESPONSE_BYTES:
        raise AnalystProseError("LLM_RESPONSE_TOO_LARGE", "DeepSeek response exceeded the limit")
    return raw


def _screen_request(serialised: str) -> None:
    if any(pattern.search(serialised) for pattern in _PRIVATE_PATTERNS):
        raise AnalystProseError(
            "PRIVATE_CONTENT_REFUSED",
            "the prose request contains private, credential, participant or "
            "raw-data material; nothing was sent",
        )
    if len(serialised) > ANALYST_MAX_INPUT_CHARACTERS:
        raise AnalystProseError(
            "LLM_INPUT_TOO_LARGE",
            f"the prose request exceeds {ANALYST_MAX_INPUT_CHARACTERS} characters",
        )


def _response_content(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "DeepSeek returned invalid JSON"
        ) from error
    if not isinstance(payload, dict):
        raise AnalystProseError("LLM_MALFORMED_RESPONSE", "DeepSeek response is not an object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "DeepSeek response must contain exactly one choice"
        )
    choice = choices[0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "DeepSeek response did not finish cleanly"
        )
    message = choice.get("message")
    if not isinstance(message, dict):
        raise AnalystProseError("LLM_MALFORMED_RESPONSE", "DeepSeek response has no message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AnalystProseError("LLM_MALFORMED_RESPONSE", "DeepSeek returned empty content")
    return content


def _guard_output(text: str, request_json: str) -> None:
    """Refuse prose that invents numbers, claims, or standing."""

    allowed_numbers = set(_NUMBER_PATTERN.findall(request_json))
    invented = [token for token in _NUMBER_PATTERN.findall(text) if token not in allowed_numbers]
    if invented:
        raise AnalystProseError(
            "LLM_NUMBER_INVENTED",
            "the prose introduced numbers absent from the validated packet: "
            + ", ".join(sorted(set(invented))[:5]),
        )
    try:
        validate_explanation_language(text)
    except XaiInstrumentationError as error:
        raise AnalystProseError(
            "LLM_UNSUPPORTED_CLAIM",
            f"the prose used unsupported claim language ({error.code})",
        ) from error
    lowered = text.lower()
    request_lowered = request_json.lower()
    for marker in _STANDING_PROMOTION_MARKERS:
        if marker in lowered and marker not in request_lowered:
            raise AnalystProseError(
                "LLM_STANDING_PROMOTED",
                f"the prose promoted evidence standing ({marker!r})",
            )


def render_analyst_prose(
    request: AnalystProseRequest,
    *,
    api_key: str | None = None,
    transport: AnalystTransport = _default_transport,
) -> AnalystProse:
    """Render prose, or raise a typed :class:`AnalystProseError`.

    The classification is not an output of this function: the caller keeps
    the deterministic classification regardless of what the prose says.
    """

    serialised = request.canonical_json()
    _screen_request(serialised)
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise AnalystProseError(
            "LLM_NOT_CONFIGURED", "DEEPSEEK_API_KEY is unavailable in this process"
        )
    body = json.dumps(
        {
            "model": ANALYST_DEEPSEEK_MODEL,
            "messages": (
                {"role": "system", "content": _ANALYST_SYSTEM_PROMPT},
                {"role": "user", "content": serialised},
            ),
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "max_tokens": 400,
            "stream": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    raw = transport(ANALYST_DEEPSEEK_API_URL, headers, body, ANALYST_TIMEOUT_SECONDS)
    content = _response_content(raw)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "DeepSeek content is not valid JSON"
        ) from error
    if not isinstance(parsed, dict) or set(parsed) != {"explanation", "next_investigation"}:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            "DeepSeek content must contain exactly explanation and next_investigation",
        )
    explanation = parsed.get("explanation")
    next_investigation = parsed.get("next_investigation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise AnalystProseError("LLM_MALFORMED_RESPONSE", "explanation must be a non-empty string")
    if next_investigation is not None and not isinstance(next_investigation, str):
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "next_investigation must be a string or null"
        )
    if len(explanation) > ANALYST_MAX_EXPLANATION_CHARACTERS:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            f"explanation exceeds {ANALYST_MAX_EXPLANATION_CHARACTERS} characters",
        )
    _guard_output(explanation, serialised)
    if next_investigation is not None:
        _guard_output(next_investigation, serialised)
    return AnalystProse(
        prompt_template_digest=ANALYST_PROMPT_TEMPLATE_DIGEST,
        input_digest=sha256(serialised.encode("utf-8")).hexdigest(),
        response_digest=sha256(raw).hexdigest(),
        explanation=explanation.strip(),
        next_investigation=(
            next_investigation.strip() if isinstance(next_investigation, str) else None
        ),
    )
