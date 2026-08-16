"""Bounded LLM explanation of an already-decided Recommendation Agent result.

The decision is derived deterministically before this module runs and is
structurally out of the LLM's reach: the prose model carries no
direction, ranking, status, or numeric field, and deterministic guards
refuse prose that invents a number, uses causal or certainty language,
promotes standing or confidence, commands retraining or infrastructure
expansion, claims an execution happened, names a direction the engine
did not choose, or presents an excluded candidate as the
recommendation. On any refusal the deterministic presentation stands
alone; with no API key configured the feature is complete without this
module.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from hashlib import sha256
from typing import Literal

from traffictwin.analyst.decision import (
    DIRECTION_DISPLAY_NAMES,
    CandidateStatus,
    RecommendationDecision,
)
from traffictwin.analyst.models import AnalystModel
from traffictwin.analyst.prose import (
    ANALYST_DEEPSEEK_API_URL,
    ANALYST_DEEPSEEK_MODEL,
    ANALYST_TIMEOUT_SECONDS,
    AnalystProseError,
    AnalystTransport,
    default_deepseek_transport,
    parse_deepseek_response_content,
    screen_prose_payload,
)
from traffictwin.analyst.recommendation_prose import guard_bounded_investigation_output

DECISION_MAX_INPUT_CHARACTERS = 14_000
DECISION_MAX_FIELD_CHARACTERS = 1_200

_DECISION_SYSTEM_PROMPT = (
    "Rewrite one TrafficTwin deterministic recommendation decision as "
    "concise plain language. Return JSON only with exactly these keys: "
    "decision_explanation (string), why_not_explanation (string or null), "
    "evidence_gap_explanation (string). Explain what TrafficTwin "
    "recommends investigating first and why that follows from the packet, "
    "then why the excluded candidates were not recommended, then what "
    "evidence is missing. Use only the facts, candidates, ranks, reasons "
    "and limitations present in the packet. Do not add numbers, causes, "
    "certainty, commands or approvals. Do not change, reorder or dispute "
    "the ranking, and do not introduce any investigation the packet does "
    "not name. Never state that retraining or infrastructure expansion is "
    "required. Keep each field under 110 words."
)
DECISION_PROMPT_TEMPLATE_DIGEST = sha256(_DECISION_SYSTEM_PROMPT.encode("utf-8")).hexdigest()


class DecisionProseRequest(AnalystModel):
    """The only content that ever reaches the LLM."""

    schema_version: Literal["decision-prose-request-1.0"] = "decision-prose-request-1.0"
    direction: str
    direction_display: str
    headline: str
    statement: str
    analyst_signal: str
    confidence: str
    evidence_standing: str
    ranked_candidates: tuple[str, ...] = ()
    excluded_candidates: tuple[str, ...] = ()
    retraining_gate_lines: tuple[str, ...] = ()
    supported_facts: tuple[str, ...] = ()
    not_established: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    decision_fingerprint: str
    provenance_refs: tuple[str, ...] = ()

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class DecisionProse(AnalystModel):
    """LLM prose with digests only; structurally unable to decide anything."""

    provider: Literal["deepseek"] = "deepseek"
    model: Literal["deepseek-v4-flash"] = ANALYST_DEEPSEEK_MODEL
    prompt_template_digest: str
    input_digest: str
    response_digest: str
    decision_explanation: str
    why_not_explanation: str | None = None
    evidence_gap_explanation: str
    llm_output: Literal[True] = True
    evidence: Literal[False] = False
    approval: Literal[False] = False
    execution: Literal[False] = False


def build_decision_prose_request(decision: RecommendationDecision) -> DecisionProseRequest:
    """Project the decision into the bounded structure the LLM may see.

    This is the only constructor the page uses; it accepts no user text.
    """

    ranked = tuple(
        f"{item.rank}. {item.title} ({item.status.value})"
        for item in sorted(
            (item for item in decision.candidates if item.rank is not None),
            key=lambda item: item.rank or 0,
        )
    )
    excluded = tuple(
        f"{item.title} ({item.status.value}): " + " ".join(item.exclusion_reasons)
        for item in decision.candidates
        if item.rank is None
    )
    gate_lines = tuple(
        f"{item.requirement_id} — "
        + ("satisfied" if item.satisfied else "NOT satisfied")
        + f": {item.evidence}"
        for item in decision.retraining_gate.requirements
    )
    return DecisionProseRequest(
        direction=decision.direction.value,
        direction_display=decision.direction_display,
        headline=decision.headline,
        statement=decision.statement,
        analyst_signal=decision.analyst_signal,
        confidence=decision.confidence,
        evidence_standing=decision.evidence_standing,
        ranked_candidates=ranked,
        excluded_candidates=excluded,
        retraining_gate_lines=gate_lines,
        supported_facts=decision.supported_facts,
        not_established=decision.not_established,
        missing_evidence=decision.missing_evidence,
        limitations=decision.limitations,
        decision_fingerprint=decision.fingerprint(),
        provenance_refs=decision.provenance_refs,
    )


def decision_prose_status(environment: Mapping[str, str] | None = None) -> dict[str, object]:
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


def _guard_decision_output(
    text: str,
    request_json: str,
    decision: RecommendationDecision,
    *,
    field: str,
) -> None:
    guard_bounded_investigation_output(text, request_json)
    lowered = text.lower()
    allowed_direction = decision.direction_display.lower()
    for direction, display in DIRECTION_DISPLAY_NAMES.items():
        if direction is decision.direction:
            continue
        if display.lower() in lowered and display.lower() != allowed_direction:
            raise AnalystProseError(
                "LLM_DECISION_MUTATED",
                f"the prose introduced a direction the engine did not choose ({direction.value})",
            )
    if field != "why_not_explanation":
        for item in decision.candidates:
            if item.rank is not None:
                continue
            if item.status is CandidateStatus.NOT_EVALUABLE and field == (
                "evidence_gap_explanation"
            ):
                continue
            if item.title.lower() in lowered:
                raise AnalystProseError(
                    "LLM_CANDIDATE_PROMOTED",
                    "the prose presented an excluded candidate inside the "
                    f"decision explanation ({item.candidate_id.value})",
                )


def render_decision_prose(
    request: DecisionProseRequest,
    decision: RecommendationDecision,
    *,
    api_key: str | None = None,
    transport: AnalystTransport = default_deepseek_transport,
) -> DecisionProse:
    """Render prose, or raise a typed :class:`AnalystProseError`.

    The decision is not an output of this function: the caller keeps the
    deterministic decision regardless of what the prose says, and the
    request must belong to the supplied decision.
    """

    if request.decision_fingerprint != decision.fingerprint():
        raise AnalystProseError(
            "LLM_INPUT_MISMATCH",
            "the prose request does not belong to the supplied decision",
        )
    serialised = request.canonical_json()
    screen_prose_payload(serialised, max_characters=DECISION_MAX_INPUT_CHARACTERS)
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise AnalystProseError(
            "LLM_NOT_CONFIGURED", "DEEPSEEK_API_KEY is unavailable in this process"
        )
    body = json.dumps(
        {
            "model": ANALYST_DEEPSEEK_MODEL,
            "messages": (
                {"role": "system", "content": _DECISION_SYSTEM_PROMPT},
                {"role": "user", "content": serialised},
            ),
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "max_tokens": 600,
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
        "decision_explanation",
        "why_not_explanation",
        "evidence_gap_explanation",
    }
    if not isinstance(parsed, dict) or set(parsed) != expected_keys:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            "DeepSeek content must contain exactly the three prose fields",
        )
    explanation = parsed.get("decision_explanation")
    why_not = parsed.get("why_not_explanation")
    gap = parsed.get("evidence_gap_explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "decision_explanation must be a non-empty string"
        )
    if why_not is not None and not isinstance(why_not, str):
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "why_not_explanation must be a string or null"
        )
    if not isinstance(gap, str) or not gap.strip():
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            "evidence_gap_explanation must be a non-empty string",
        )
    for field, field_text in (
        ("decision_explanation", explanation),
        ("why_not_explanation", why_not or ""),
        ("evidence_gap_explanation", gap),
    ):
        if len(field_text) > DECISION_MAX_FIELD_CHARACTERS:
            raise AnalystProseError(
                "LLM_MALFORMED_RESPONSE",
                f"a prose field exceeds {DECISION_MAX_FIELD_CHARACTERS} characters",
            )
        if field_text:
            _guard_decision_output(field_text, serialised, decision, field=field)
    return DecisionProse(
        prompt_template_digest=DECISION_PROMPT_TEMPLATE_DIGEST,
        input_digest=sha256(serialised.encode("utf-8")).hexdigest(),
        response_digest=sha256(raw).hexdigest(),
        decision_explanation=explanation.strip(),
        why_not_explanation=why_not.strip() if isinstance(why_not, str) else None,
        evidence_gap_explanation=gap.strip(),
    )
