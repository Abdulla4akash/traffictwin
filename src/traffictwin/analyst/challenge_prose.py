"""Bounded LLM explanation of an already-planned What-If challenge.

The challenge is planned deterministically before this module runs and
cannot be changed here: the prose model has no category, parameter, mode,
fingerprint, readiness, or standing field, and deterministic guards
refuse prose that invents a number, names an unregistered profile or an
unrequested What-If field, promotes readiness, claims proof, causality,
execution, or evidence, or reuses any of the bounded-investigation
violations. The LLM receives only the validated challenge projection;
user free text has no path into the request. On any refusal the
deterministic challenge description stands alone.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from hashlib import sha256
from typing import Literal

from traffictwin.analyst.challenge import (
    REGISTERED_POLICY_PROFILES,
    WhatIfChallengeSpec,
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
from traffictwin.analyst.recommendation_prose import (
    guard_bounded_investigation_output,
)
from traffictwin.ui.whatif_controls import WHATIF_WIDGET_KEYS

CHALLENGE_PROSE_MAX_INPUT_CHARACTERS = 12_000
CHALLENGE_PROSE_MAX_FIELD_CHARACTERS = 1_200

_CHALLENGE_SYSTEM_PROMPT = (
    "Rewrite one TrafficTwin deterministic What-If challenge specification "
    "as concise plain language. Return JSON only with exactly these keys: "
    "challenge_explanation (string), control_explanation (string), "
    "interpretation_boundary (string). Explain why this challenge follows "
    "from the recommendation, what is varied, what is held fixed and why, "
    "what user input is still required, and what the comparison cannot "
    "establish. Use only the facts, numbers, dimensions and limitations "
    "present in the packet. Do not add numbers, parameters, modes, "
    "certainty, causes or commands. Do not change or dispute the "
    "challenge, its readiness, or its controls. Never say anything has "
    "run or will prove something. Keep each field under 110 words."
)
CHALLENGE_PROMPT_TEMPLATE_DIGEST = sha256(_CHALLENGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest()

_PROOF_CLAIM_MARKERS = (
    "will prove",
    "would prove",
    "proves",
    "will confirm",
    "confirms the mechanism",
    "will demonstrate conclusively",
)
_READINESS_PROMOTION_MARKERS = (
    "ready to run",
    "prefill is ready",
    "challenge is ready",
    "can be executed now",
    "no further input is needed",
    "already prepared in what-if studio",
)
_RESULT_CLAIM_MARKERS = (
    "the result shows",
    "the results show",
    "the outcome shows",
    "the comparison showed",
    "this is evidence that",
)


class ChallengeProseRequest(AnalystModel):
    """The only content that ever reaches the LLM."""

    schema_version: Literal["challenge-prose-request-1.0"] = "challenge-prose-request-1.0"
    challenge_category: str
    headline: str
    statement: str
    readiness: str
    analyst_signal: str
    recommendation_category: str
    confidence: str
    evidence_standing: str
    track_titles: tuple[str, ...] = ()
    variables_under_investigation: tuple[str, ...] = ()
    held_fixed_dimensions: tuple[str, ...] = ()
    required_user_inputs: tuple[str, ...] = ()
    unsupported_dimensions: tuple[str, ...] = ()
    expected_observables: tuple[str, ...] = ()
    could_support: tuple[str, ...] = ()
    cannot_establish: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    challenge_fingerprint: str
    provenance_refs: tuple[str, ...] = ()

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


class ChallengeProse(AnalystModel):
    """LLM prose with digests only; no authority-bearing fields exist."""

    provider: Literal["deepseek"] = "deepseek"
    model: Literal["deepseek-v4-flash"] = ANALYST_DEEPSEEK_MODEL
    prompt_template_digest: str
    input_digest: str
    response_digest: str
    challenge_explanation: str
    control_explanation: str
    interpretation_boundary: str
    llm_output: Literal[True] = True
    evidence: Literal[False] = False
    approval: Literal[False] = False
    execution: Literal[False] = False


def build_challenge_prose_request(spec: WhatIfChallengeSpec) -> ChallengeProseRequest:
    """Project the challenge into the bounded structure the LLM may see.

    This is the only constructor the page uses; it accepts no user text.
    """

    return ChallengeProseRequest(
        challenge_category=spec.category.value,
        headline=spec.headline,
        statement=spec.statement,
        readiness=spec.readiness.value,
        analyst_signal=spec.analyst_signal,
        recommendation_category=spec.recommendation_category,
        confidence=spec.confidence,
        evidence_standing=spec.evidence_standing,
        track_titles=tuple(track.title for track in spec.tracks),
        variables_under_investigation=tuple(
            track.variable_under_investigation
            for track in spec.tracks
            if track.variable_under_investigation is not None
        ),
        held_fixed_dimensions=tuple(
            dict.fromkeys(
                control.dimension for track in spec.tracks for control in track.held_fixed
            )
        ),
        required_user_inputs=tuple(
            user_input.prompt for track in spec.tracks for user_input in track.required_user_inputs
        ),
        unsupported_dimensions=tuple(
            dict.fromkeys(
                dimension for track in spec.tracks for dimension in track.unsupported_dimensions
            )
        ),
        expected_observables=tuple(
            dict.fromkeys(
                observable for track in spec.tracks for observable in track.expected_observables
            )
        ),
        could_support=tuple(track.could_support for track in spec.tracks),
        cannot_establish=tuple(track.cannot_establish for track in spec.tracks),
        missing_evidence=spec.missing_evidence,
        limitations=spec.limitations,
        challenge_fingerprint=spec.fingerprint(),
        provenance_refs=spec.provenance_refs,
    )


def challenge_prose_status(
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


def _guard_challenge_output(text: str, request_json: str) -> None:
    guard_bounded_investigation_output(text, request_json)
    lowered = text.lower()
    request_lowered = request_json.lower()
    for markers, code, reason in (
        (_PROOF_CLAIM_MARKERS, "LLM_UNSUPPORTED_CLAIM", "the prose claimed proof"),
        (
            _READINESS_PROMOTION_MARKERS,
            "LLM_READINESS_PROMOTED",
            "the prose promoted the challenge readiness",
        ),
        (
            _RESULT_CLAIM_MARKERS,
            "LLM_UNSUPPORTED_EXECUTION_CLAIM",
            "the prose claimed a result that does not exist",
        ),
    ):
        for marker in markers:
            if marker in lowered and marker not in request_lowered:
                raise AnalystProseError(code, f"{reason} ({marker!r})")
    for profile in REGISTERED_POLICY_PROFILES:
        if profile in lowered and profile not in request_lowered:
            raise AnalystProseError(
                "LLM_CHALLENGE_MUTATED",
                f"the prose introduced a profile the challenge did not select ({profile})",
            )
    for field in WHATIF_WIDGET_KEYS:
        if field in lowered and field not in request_lowered:
            raise AnalystProseError(
                "LLM_CHALLENGE_MUTATED",
                f"the prose introduced a What-If dimension the challenge did not request ({field})",
            )


def render_challenge_prose(
    request: ChallengeProseRequest,
    *,
    api_key: str | None = None,
    transport: AnalystTransport = default_deepseek_transport,
) -> ChallengeProse:
    """Render prose, or raise a typed :class:`AnalystProseError`.

    The challenge is not an output of this function: the caller keeps the
    deterministic specification regardless of what the prose says.
    """

    serialised = request.canonical_json()
    screen_prose_payload(serialised, max_characters=CHALLENGE_PROSE_MAX_INPUT_CHARACTERS)
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise AnalystProseError(
            "LLM_NOT_CONFIGURED", "DEEPSEEK_API_KEY is unavailable in this process"
        )
    body = json.dumps(
        {
            "model": ANALYST_DEEPSEEK_MODEL,
            "messages": (
                {"role": "system", "content": _CHALLENGE_SYSTEM_PROMPT},
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
        "challenge_explanation",
        "control_explanation",
        "interpretation_boundary",
    }
    if not isinstance(parsed, dict) or set(parsed) != expected_keys:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            "DeepSeek content must contain exactly the three prose fields",
        )
    fields: dict[str, str] = {}
    for key_name in sorted(expected_keys):
        value = parsed.get(key_name)
        if not isinstance(value, str) or not value.strip():
            raise AnalystProseError(
                "LLM_MALFORMED_RESPONSE", f"{key_name} must be a non-empty string"
            )
        if len(value) > CHALLENGE_PROSE_MAX_FIELD_CHARACTERS:
            raise AnalystProseError(
                "LLM_MALFORMED_RESPONSE",
                f"{key_name} exceeds {CHALLENGE_PROSE_MAX_FIELD_CHARACTERS} characters",
            )
        _guard_challenge_output(value, serialised)
        fields[key_name] = value.strip()
    return ChallengeProse(
        prompt_template_digest=CHALLENGE_PROMPT_TEMPLATE_DIGEST,
        input_digest=sha256(serialised.encode("utf-8")).hexdigest(),
        response_digest=sha256(raw).hexdigest(),
        challenge_explanation=fields["challenge_explanation"],
        control_explanation=fields["control_explanation"],
        interpretation_boundary=fields["interpretation_boundary"],
    )
