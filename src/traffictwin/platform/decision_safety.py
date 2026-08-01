"""Decision-safety layer (post-v1 D-1): guardrails and refusals, not choices.

Implements ``docs/platform/decision_safety_layer_design.md``: the layer that
answers exactly one question — is there enough compatible, correctly scoped
information to present an option set as a bounded decision-support
comparison, and which cautions must accompany it? It never answers what an
operator should deploy. TrafficTwin's own central finding is the reason: a
familiar QoS metric improved while deadline attainment stayed flat, actions
were invariant, and the change lived inside already-failed tasks — a naive
"minimise latency" layer would have recommended degrading the system.

Structure, not politeness:

- every assessment is ``recommendation: false`` / ``evidence: false`` /
  ``causal: false`` and preserves the INPUT order — there is no ranking,
  winner, default, or deployment signal anywhere;
- the eight deterministic rules are code-versioned; changing one changes the
  ruleset digest;
- the required confirmed-capacity notice is emitted only while the pinned
  confirmatory record digest matches — stale bytes refuse rather than
  reproduce headline numbers;
- non-admitted inputs refuse outright; predictions and admitted evidence
  never merge into one comparison; causal or recommendation wording refuses
  by name; and an LLM cannot originate facts or resolve a refusal.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

METHOD_VERSION: Literal["decision-safety-1.0"] = "decision-safety-1.0"
DESIGN_REFERENCE: Literal["docs/platform/decision_safety_layer_design.md"] = (
    "docs/platform/decision_safety_layer_design.md"
)
CITATION_REFERENCE: Literal["docs/producer_citation_requirements.md"] = (
    "docs/producer_citation_requirements.md"
)

#: The confirmatory results record this layer's required notice is pinned to.
CONFIRMATORY_RECORD_PATH = "docs/evaluation/capacity_confirmatory_results_20260728.md"
CONFIRMATORY_RECORD_SHA256 = "5659be5530dc0dce97123206e35359c6a1d7bf84e95a7ebaee54a4a69600ed76"

OptionKind = Literal["prediction", "forecast", "proposed", "admitted_analysis", "non_admitted"]
IntervalStatus = Literal["available", "zero_width", "unavailable"]

#: Wording that triggers the causality rule — no current input supports it.
_CAUSAL_MARKERS = (
    "causes",
    "caused by",
    "because of",
    "individual vehicle improvement",
    "experienced by a vehicle",
)
#: Wording that triggers the actionability rule.
_RECOMMENDATION_MARKERS = (
    "recommend",
    "deploy",
    "should degrade",
    "best option",
    "winning option",
    "optimal",
)
_PRIVATE_MARKERS = ("/Users/", "/home/", "\\Users\\")

#: The versioned ruleset. Changing ANY value changes the ruleset digest and
#: needs owner review (design §4).
MINIMUM_SUPPORT = 3
REQUIRED_COMPANIONS: tuple[str, ...] = (
    "deadline_attainment",
    "action_change",
    "failure_locus",
)
RULESET: dict[str, object] = {
    "version": "1.0",
    "minimum_support": MINIMUM_SUPPORT,
    "required_companions_on_headline_improvement": list(REQUIRED_COMPANIONS),
    "rules": [
        "envelope",
        "standing",
        "proxy_inversion",
        "support",
        "uncertainty",
        "deviation",
        "causality",
        "actionability",
    ],
}


def ruleset_digest() -> str:
    return hashlib.sha256(json.dumps(RULESET, sort_keys=True).encode("utf-8")).hexdigest()


class DecisionSafetyError(RuntimeError):
    """Typed refusal; the layer fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class SafetyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class DecisionOption(SafetyModel):
    """One typed input option from the predictor, matrix, registry or an
    admitted analysis — never free text, a URL, or a raw payload."""

    option_id: str
    kind: OptionKind
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    trace: str
    actor: str
    capacity: float
    inside_measured_envelope: bool
    actor_capacity_measured: bool
    support_count: int = Field(ge=0)
    interval_status: IntervalStatus
    headline_improvement_claimed: bool
    companions_present: tuple[str, ...]
    execution_deviations: tuple[str, ...] = ()
    deviations_disclosed: bool = True
    wording: str = ""
    citation_reference: str = CITATION_REFERENCE


class SafetyNotice(SafetyModel):
    code: str
    text: str
    recommendation: Literal[False] = False
    evidence: Literal[False] = False
    causal: Literal[False] = False


class DecisionSupportAssessment(SafetyModel):
    """The output contract: cautions and exclusions, never a choice."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["decision-safety-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/decision_safety_layer_design.md"] = DESIGN_REFERENCE
    status: Literal["presentable_with_cautions", "refused"]
    ruleset_digest: str
    input_digests: tuple[str, ...]
    compatible_option_ids: tuple[str, ...]
    exclusions: dict[str, str]
    notices: tuple[SafetyNotice, ...]
    recommendation: Literal[False] = False
    evidence: Literal[False] = False
    causal: Literal[False] = False
    policy_ceiling: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    citation_reference: Literal["docs/producer_citation_requirements.md"] = CITATION_REFERENCE


def _screen_wording(option: DecisionOption) -> None:
    lowered = option.wording.lower()
    for marker in _PRIVATE_MARKERS:
        if marker in option.wording:
            raise DecisionSafetyError(
                "PRIVATE_CONTENT_DETECTED",
                f"option '{option.option_id}' carries a private path in its wording",
            )
    for marker in _CAUSAL_MARKERS:
        if marker in lowered:
            raise DecisionSafetyError(
                "CAUSAL_WORDING_FORBIDDEN",
                f"option '{option.option_id}' uses causal or individual-experience "
                f"wording ('{marker}'); no separately authorised design supports it",
            )
    for marker in _RECOMMENDATION_MARKERS:
        if marker in lowered:
            raise DecisionSafetyError(
                "RECOMMENDATION_REQUEST_FORBIDDEN",
                f"option '{option.option_id}' asks for a recommendation ('{marker}'); "
                "this layer never translates a model output into an instruction",
            )


def assess(
    options: tuple[DecisionOption, ...],
    *,
    request_ranking: bool = False,
) -> DecisionSupportAssessment:
    """Apply the eight rules in order; refuse categorically, exclude locally.

    Output order is the input order — the layer never sorts by any value.
    """

    if request_ranking:
        raise DecisionSafetyError(
            "RECOMMENDATION_REQUEST_FORBIDDEN",
            "ranking, winners, defaults and deployment signals do not exist in this "
            "layer; comparisons render in neutral input order only",
        )
    if not options:
        raise DecisionSafetyError(
            "SUPPORT_INSUFFICIENT", "an assessment needs at least one typed option"
        )
    kinds = {option.kind for option in options}
    if "non_admitted" in kinds:
        raise DecisionSafetyError(
            "NON_ADMITTED_INPUT",
            "non-admitted results are not decision inputs in any combination; they "
            "may be inventoried elsewhere, never compared here",
        )
    if "admitted_analysis" in kinds and kinds & {"prediction", "forecast", "proposed"}:
        raise DecisionSafetyError(
            "INCOMPATIBLE_EVIDENCE",
            "predictions, forecasts and proposals never merge with admitted evidence "
            "into one comparison; present them as separately labelled views",
        )
    for option in options:
        _screen_wording(option)

    minimum_support = MINIMUM_SUPPORT
    required_companions = REQUIRED_COMPANIONS
    notices: list[SafetyNotice] = []
    exclusions: dict[str, str] = {}
    compatible: list[str] = []
    for option in options:
        if not option.inside_measured_envelope:
            exclusions[option.option_id] = (
                "OUTSIDE_MEASURED_ENVELOPE: the option extrapolates beyond the tested envelope"
            )
            continue
        if not option.actor_capacity_measured:
            exclusions[option.option_id] = (
                "ACTOR_CAPACITY_NOT_MEASURED: inside the global envelope but outside "
                "this actor/trace pair's admitted cells"
            )
            continue
        if option.execution_deviations and not option.deviations_disclosed:
            raise DecisionSafetyError(
                "EXECUTION_DEVIATION_UNACKNOWLEDGED",
                f"option '{option.option_id}' carries execution deviations it does "
                "not disclose; deviations are never optional notes",
            )
        if option.support_count < minimum_support:
            exclusions[option.option_id] = (
                f"SUPPORT_INSUFFICIENT: {option.support_count} < required {minimum_support}"
            )
            continue
        if option.headline_improvement_claimed:
            missing = [
                companion
                for companion in required_companions
                if companion not in option.companions_present
            ]
            if missing:
                raise DecisionSafetyError(
                    "COMPANION_METRIC_MISSING",
                    f"option '{option.option_id}' claims a headline improvement "
                    f"without its companions {missing}; the proxy-inversion rule "
                    "requires deadline, action-change and failure-locus context",
                )
        if option.interval_status == "unavailable":
            notices.append(
                SafetyNotice(
                    code="UNCERTAINTY_UNAVAILABLE",
                    text=(
                        f"option '{option.option_id}' has no uncertainty interval; "
                        "unavailable is not zero-width"
                    ),
                )
            )
        for deviation in option.execution_deviations:
            notices.append(
                SafetyNotice(
                    code="EXECUTION_DEVIATION",
                    text=f"option '{option.option_id}': {deviation}",
                )
            )
        compatible.append(option.option_id)

    if not compatible:
        return DecisionSupportAssessment(
            status="refused",
            ruleset_digest=ruleset_digest(),
            input_digests=tuple(option.source_digest for option in options),
            compatible_option_ids=(),
            exclusions=exclusions,
            notices=tuple(notices),
        )
    notices.append(
        SafetyNotice(
            code="SMALL_SAMPLE_LIMIT",
            text=(
                "small-sample limits are retained exactly: five paired seeds carry an "
                "exact two-sided sign-test floor of p=0.0625 and are never presented "
                "as conventionally significant"
            ),
        )
    )
    return DecisionSupportAssessment(
        status="presentable_with_cautions",
        ruleset_digest=ruleset_digest(),
        input_digests=tuple(option.source_digest for option in options),
        compatible_option_ids=tuple(compatible),
        exclusions=exclusions,
        notices=tuple(notices),
    )


def confirmed_capacity_notice(repo_root: Path) -> SafetyNotice:
    """The required §6 notice, emitted only while its pinned digest matches."""

    record = repo_root / CONFIRMATORY_RECORD_PATH
    if not record.is_file():
        raise DecisionSafetyError(
            "INPUT_DIGEST_MISMATCH",
            f"the pinned confirmatory record '{CONFIRMATORY_RECORD_PATH}' is missing",
        )
    digest = hashlib.sha256(record.read_bytes()).hexdigest()
    if digest != CONFIRMATORY_RECORD_SHA256:
        raise DecisionSafetyError(
            "INPUT_DIGEST_MISMATCH",
            "the confirmatory record's bytes changed; refusing to reproduce stale "
            "headline numbers — re-pin after review",
        )
    return SafetyNotice(
        code="CONFIRMED_CAPACITY_CONTEXT",
        text=(
            "Lowering RSU capacity from 2.5 to 0.75 reduced mean latency by 8,310.9 ms. "
            "Bootstrap interval: [−9,097.5, −7,524.3] ms. All five held-out seeds moved "
            "in the same direction. The exact two-sided sign-test floor is p=0.0625. "
            "Do not claim conventional statistical significance. Deadline attainment "
            "remained effectively flat. Actions/offloading decisions were invariant "
            "across capacity arms. The latency change occurred within already-failed "
            "tasks and was not an improvement experienced by an individual vehicle. "
            "This is not a reason to degrade capacity."
        ),
    )


def assessment_to_json(assessment: DecisionSupportAssessment) -> str:
    return json.dumps(assessment.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)
