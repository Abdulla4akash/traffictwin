"""Bounded LLM explanation of an already-decided recommendation.

The recommendation is selected deterministically before this module runs
and cannot be changed here: the prose model has no category, confidence,
standing, or numeric field, and deterministic guards refuse prose that
invents a number, uses causal or certainty language, promotes standing or
confidence, commands retraining or infrastructure expansion, claims an
execution happened, or names a recommendation the selector did not
choose. The LLM receives only the validated packet projection; user free
text has no path into the request. On any refusal the deterministic
presentation stands alone.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from hashlib import sha256
from typing import Literal

from traffictwin.analyst.models import AnalystModel
from traffictwin.analyst.prose import (
    ANALYST_DEEPSEEK_API_URL,
    ANALYST_DEEPSEEK_MODEL,
    ANALYST_TIMEOUT_SECONDS,
    AnalystProseError,
    AnalystTransport,
    default_deepseek_transport,
    guard_prose_output,
    parse_deepseek_response_content,
    screen_prose_payload,
)
from traffictwin.analyst.recommendation import (
    CATEGORY_DISPLAY_NAMES,
    RecommendationEvidencePacket,
)

RECOMMENDATION_MAX_INPUT_CHARACTERS = 10_000
RECOMMENDATION_MAX_FIELD_CHARACTERS = 1_200

_RECOMMENDATION_SYSTEM_PROMPT = (
    "Rewrite one TrafficTwin deterministic recommendation packet as concise "
    "plain language. Return JSON only with exactly these keys: "
    "recommendation_explanation (string), why_not_alternative (string or "
    "null), next_investigation_explanation (string). Explain what "
    "TrafficTwin recommends investigating, why that follows from the "
    "evidence in the packet, what evidence is missing, and what a safe "
    "next investigation would examine. Use only the facts, numbers, "
    "limitations and category present in the packet. Do not add numbers, "
    "causes, certainty, commands or approvals. Do not change or dispute "
    "the recommendation. Never state that retraining or infrastructure "
    "expansion is required. Keep each field under 110 words."
)
RECOMMENDATION_PROMPT_TEMPLATE_DIGEST = sha256(
    _RECOMMENDATION_SYSTEM_PROMPT.encode("utf-8")
).hexdigest()

_RETRAINING_COMMAND_MARKERS = (
    "must retrain",
    "retrain the model",
    "needs retraining",
    "should be retrained",
    "retraining is required",
    "retraining is necessary",
)
_EXPANSION_COMMAND_MARKERS = (
    "add more rsus",
    "add more infrastructure",
    "increase capacity",
    "expand the infrastructure",
    "expand infrastructure",
    "must scale",
    "scale up",
)
_CONFIDENCE_PROMOTION_MARKERS = (
    "high confidence",
    "certainly",
    "definitely",
    "undoubtedly",
    "confident that",
    "conclusive",
)
_CAUSAL_CLAIM_MARKERS = (
    "root cause",
    "caused the",
    "caused by",
    "is the cause",
    "was the cause",
    "definitively caused",
)
_EXECUTION_CLAIM_MARKERS = (
    "has been executed",
    "was executed",
    "has been run",
    "experiment has run",
    "experiment was launched",
    "simulation was launched",
    "what-if has run",
    "already ran",
)


class RecommendationProseRequest(AnalystModel):
    """The only content that ever reaches the LLM."""

    schema_version: Literal["recommendation-prose-request-1.0"] = "recommendation-prose-request-1.0"
    category: str
    headline: str
    rationale: str
    analyst_signal: str
    confidence: str
    evidence_standing: str
    supported_facts: tuple[str, ...] = ()
    not_established: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    alternative_category: str | None = None
    alternative_reason: str | None = None
    source_actions: tuple[str, ...] = ()
    packet_fingerprint: str
    provenance_refs: tuple[str, ...] = ()

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class RecommendationProse(AnalystModel):
    """LLM prose with digests only; structurally unable to decide anything."""

    provider: Literal["deepseek"] = "deepseek"
    model: Literal["deepseek-v4-flash"] = ANALYST_DEEPSEEK_MODEL
    prompt_template_digest: str
    input_digest: str
    response_digest: str
    recommendation_explanation: str
    why_not_alternative: str | None = None
    next_investigation_explanation: str
    llm_output: Literal[True] = True
    evidence: Literal[False] = False
    approval: Literal[False] = False
    execution: Literal[False] = False


def build_recommendation_prose_request(
    packet: RecommendationEvidencePacket,
) -> RecommendationProseRequest:
    """Project the packet into the bounded structure the LLM may see.

    This is the only constructor the page uses; it accepts no user text.
    """

    return RecommendationProseRequest(
        category=packet.category.value,
        headline=packet.headline,
        rationale=packet.rationale,
        analyst_signal=packet.analyst_signal,
        confidence=packet.confidence,
        evidence_standing=packet.evidence_standing,
        supported_facts=packet.supported_facts,
        not_established=packet.not_established,
        missing_evidence=packet.missing_evidence,
        limitations=packet.limitations,
        alternative_category=(
            packet.alternative_category.value if packet.alternative_category else None
        ),
        alternative_reason=packet.alternative_reason,
        source_actions=tuple(
            f"{source.rule_id}: {source.action} — {source.rationale} "
            f"(conditional; prerequisite: {source.prerequisite})"
            for source in packet.source_recommendations
        ),
        packet_fingerprint=packet.fingerprint(),
        provenance_refs=packet.provenance_refs,
    )


def recommendation_prose_status(
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
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


def _guard_marked_phrases(
    text: str,
    request_json: str,
    markers: tuple[str, ...],
    code: str,
    reason: str,
) -> None:
    lowered = text.lower()
    request_lowered = request_json.lower()
    for marker in markers:
        if marker in lowered and marker not in request_lowered:
            raise AnalystProseError(code, f"{reason} ({marker!r})")


def _guard_recommendation_output(
    text: str, request_json: str, request: RecommendationProseRequest
) -> None:
    guard_prose_output(text, request_json)
    _guard_marked_phrases(
        text,
        request_json,
        _CAUSAL_CLAIM_MARKERS,
        "LLM_UNSUPPORTED_CLAIM",
        "the prose claimed causality beyond the packet",
    )
    _guard_marked_phrases(
        text,
        request_json,
        _RETRAINING_COMMAND_MARKERS,
        "LLM_UNSUPPORTED_RETRAINING",
        "the prose commanded retraining beyond the packet",
    )
    _guard_marked_phrases(
        text,
        request_json,
        _EXPANSION_COMMAND_MARKERS,
        "LLM_UNSUPPORTED_EXPANSION",
        "the prose commanded infrastructure expansion beyond the packet",
    )
    _guard_marked_phrases(
        text,
        request_json,
        _CONFIDENCE_PROMOTION_MARKERS,
        "LLM_CONFIDENCE_PROMOTED",
        "the prose promoted the categorical confidence",
    )
    _guard_marked_phrases(
        text,
        request_json,
        _EXECUTION_CLAIM_MARKERS,
        "LLM_UNSUPPORTED_EXECUTION_CLAIM",
        "the prose claimed an execution that did not happen",
    )
    allowed = {request.category, request.alternative_category or ""}
    lowered = text.lower()
    for category, display in CATEGORY_DISPLAY_NAMES.items():
        if category.value in allowed:
            continue
        if display.lower() in lowered:
            raise AnalystProseError(
                "LLM_RECOMMENDATION_MUTATED",
                "the prose introduced a recommendation the selector did not "
                f"choose ({category.value})",
            )


def render_recommendation_prose(
    request: RecommendationProseRequest,
    *,
    api_key: str | None = None,
    transport: AnalystTransport = default_deepseek_transport,
) -> RecommendationProse:
    """Render prose, or raise a typed :class:`AnalystProseError`.

    The recommendation is not an output of this function: the caller keeps
    the deterministic packet regardless of what the prose says.
    """

    serialised = request.canonical_json()
    screen_prose_payload(serialised, max_characters=RECOMMENDATION_MAX_INPUT_CHARACTERS)
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise AnalystProseError(
            "LLM_NOT_CONFIGURED", "DEEPSEEK_API_KEY is unavailable in this process"
        )
    body = json.dumps(
        {
            "model": ANALYST_DEEPSEEK_MODEL,
            "messages": (
                {"role": "system", "content": _RECOMMENDATION_SYSTEM_PROMPT},
                {"role": "user", "content": serialised},
            ),
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "max_tokens": 500,
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
    content = parse_deepseek_response_content(raw)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "DeepSeek content is not valid JSON"
        ) from error
    expected_keys = {
        "recommendation_explanation",
        "why_not_alternative",
        "next_investigation_explanation",
    }
    if not isinstance(parsed, dict) or set(parsed) != expected_keys:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            "DeepSeek content must contain exactly the three prose fields",
        )
    explanation = parsed.get("recommendation_explanation")
    why_not = parsed.get("why_not_alternative")
    next_explanation = parsed.get("next_investigation_explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            "recommendation_explanation must be a non-empty string",
        )
    if why_not is not None and not isinstance(why_not, str):
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "why_not_alternative must be a string or null"
        )
    if not isinstance(next_explanation, str) or not next_explanation.strip():
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            "next_investigation_explanation must be a non-empty string",
        )
    for field_text in (explanation, why_not or "", next_explanation):
        if len(field_text) > RECOMMENDATION_MAX_FIELD_CHARACTERS:
            raise AnalystProseError(
                "LLM_MALFORMED_RESPONSE",
                f"a prose field exceeds {RECOMMENDATION_MAX_FIELD_CHARACTERS} characters",
            )
        if field_text:
            _guard_recommendation_output(field_text, serialised, request)
    return RecommendationProse(
        prompt_template_digest=RECOMMENDATION_PROMPT_TEMPLATE_DIGEST,
        input_digest=sha256(serialised.encode("utf-8")).hexdigest(),
        response_digest=sha256(raw).hexdigest(),
        recommendation_explanation=explanation.strip(),
        why_not_alternative=why_not.strip() if isinstance(why_not, str) else None,
        next_investigation_explanation=next_explanation.strip(),
    )
