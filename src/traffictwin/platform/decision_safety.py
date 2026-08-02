"""Decision-Safety Ruleset v2: broad, bounded decision support.

The layer permits useful decisions when a digest-bound study policy says the
inputs are compatible: metric-specific rankings, tied winners, evidence-backed
advice, an owner-preselected default and reviewable instruction drafts.  It
does not execute those drafts or create evidence.  Comparisons outside the
measured envelope, incompatible contracts/standings, hidden deviations and
missing support or uncertainty still fail closed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

METHOD_VERSION: Literal["decision-safety-2.0"] = "decision-safety-2.0"
DESIGN_REFERENCE: Literal["docs/platform/decision_safety_layer_design.md"] = (
    "docs/platform/decision_safety_layer_design.md"
)
CITATION_REFERENCE: Literal["docs/producer_citation_requirements.md"] = (
    "docs/producer_citation_requirements.md"
)

CONFIRMATORY_RECORD_PATH = "docs/evaluation/capacity_confirmatory_results_20260728.md"
CONFIRMATORY_RECORD_SHA256 = "5659be5530dc0dce97123206e35359c6a1d7bf84e95a7ebaee54a4a69600ed76"

OptionKind = Literal["prediction", "forecast", "proposed", "admitted_analysis", "non_admitted"]
IntervalStatus = Literal["available", "zero_width", "unavailable"]
MetricDirection = Literal["higher_is_better", "lower_is_better"]
CauseScope = Literal["none", "simulation_internal", "real_world"]

DISPLAY_ORDER = (
    "standing_scope_deviation",
    "eligibility",
    "metric_specific_result",
    "uncertainty_and_support",
    "companion_metrics",
    "ranking_advice_default_and_drafts",
    "citations",
)

_PRIVATE_MARKERS = ("/Users/", "/home/", "\\Users\\")
_CAUSAL_MARKERS = (
    "causes",
    "caused by",
    "because of",
    "individual vehicle improvement",
    "experienced by a vehicle",
)
_UNSUPPORTED_SUPERLATIVES = ("globally optimal", "universally best", "proven safest")
_CAUSE_ORDER: dict[CauseScope, int] = {"none": 0, "simulation_internal": 1, "real_world": 2}


class DecisionSafetyError(RuntimeError):
    """Typed refusal; the layer fails closed rather than broadening a claim."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class SafetyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class CauseDesignAuthority(SafetyModel):
    design_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    maximum_scope: CauseScope


class DecisionSafetyPolicy(SafetyModel):
    """One owner-selected, study-specific and digest-bound decision policy."""

    policy_id: str
    policy_version: str
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    comparison_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    minimum_support_count: int = Field(ge=1)
    required_overall_service_companions: tuple[str, ...] = Field(min_length=1)
    ranking_allowed: bool
    advisory_recommendation_allowed: bool
    execution_instruction_drafts_allowed: bool
    owner_preselected_default_option_id: str | None = None
    maximum_cause_scope: CauseScope
    cause_design_authorities: tuple[CauseDesignAuthority, ...] = ()
    fixed_display_order: tuple[str, ...] = DISPLAY_ORDER
    thresholds_predeclared: Literal[True] = True
    owner_approved: Literal[True] = True

    @model_validator(mode="after")
    def validate_policy(self) -> DecisionSafetyPolicy:
        if len(set(self.required_overall_service_companions)) != len(
            self.required_overall_service_companions
        ):
            raise ValueError("required companion metrics must be unique")
        if self.fixed_display_order != DISPLAY_ORDER:
            raise ValueError("fixed display order must match Decision-Safety Ruleset v2")
        digests = [authority.design_digest for authority in self.cause_design_authorities]
        if len(set(digests)) != len(digests):
            raise ValueError("cause design authority digests must be unique")
        return self


class DecisionOption(SafetyModel):
    """One typed option from a predictor, registry or admitted analysis."""

    option_id: str
    kind: OptionKind
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    comparison_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    compatibility_group: str
    trace: str
    actor: str
    capacity: float
    inside_measured_envelope: bool
    actor_capacity_measured: bool
    matched_budget: bool
    comparison_predeclared: bool
    support_count: int = Field(ge=0)
    interval_status: IntervalStatus
    primary_metric_name: str
    primary_metric_value: float
    metric_direction: MetricDirection
    headline_improvement_claimed: bool
    overall_service_claimed: bool = False
    service_endpoint_present: bool = False
    companions_present: tuple[str, ...]
    execution_deviations: tuple[str, ...] = ()
    deviations_disclosed: bool = True
    cause_scope: CauseScope = "none"
    cause_design_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    execution_instruction_draft: str | None = None
    wording: str = ""
    citation_reference: str = CITATION_REFERENCE

    @model_validator(mode="after")
    def validate_cause_binding(self) -> DecisionOption:
        if self.cause_scope == "none" and self.cause_design_digest is not None:
            raise ValueError("cause_design_digest requires a non-none cause scope")
        if self.cause_scope != "none" and self.cause_design_digest is None:
            raise ValueError("a scoped cause statement requires a design digest")
        return self


class ExecutionInstructionDraft(SafetyModel):
    option_id: str
    text: str
    review_required: Literal[True] = True
    executable: Literal[False] = False
    execution_authority: Literal[False] = False
    creates_new_evidence: Literal[False] = False


class SafetyNotice(SafetyModel):
    code: str
    text: str
    recommendation: bool = False
    evidence_backed: bool = False
    creates_new_evidence: Literal[False] = False
    causal_scope: CauseScope = "none"
    execution_authority: Literal[False] = False


class DecisionSupportAssessment(SafetyModel):
    """A bounded decision aid with no execution or approval authority."""

    schema_version: Literal["2.0"] = "2.0"
    method_version: Literal["decision-safety-2.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/decision_safety_layer_design.md"] = DESIGN_REFERENCE
    status: Literal["presentable_with_cautions", "refused"]
    ruleset_digest: str
    policy_id: str
    policy_source_digest: str
    display_order: tuple[str, ...]
    input_digests: tuple[str, ...]
    compatible_option_ids: tuple[str, ...]
    exclusions: dict[str, str]
    notices: tuple[SafetyNotice, ...]
    ranked_option_ids: tuple[str, ...] = ()
    metric_winner_option_ids: tuple[str, ...] = ()
    advisory_recommendation: str | None = None
    owner_preselected_default_option_id: str | None = None
    execution_instruction_drafts: tuple[ExecutionInstructionDraft, ...] = ()
    recommendation: bool = False
    evidence_backed: bool = False
    creates_new_evidence: Literal[False] = False
    causal_scope: CauseScope = "none"
    execution_authority: Literal[False] = False
    policy_ceiling: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    citation_reference: Literal["docs/producer_citation_requirements.md"] = CITATION_REFERENCE


def ruleset_digest(policy: DecisionSafetyPolicy) -> str:
    material = {
        "method_version": METHOD_VERSION,
        "policy": policy.model_dump(mode="json"),
        "rules": (
            "measured_envelope",
            "compatibility_and_standing",
            "matched_predeclared_ranking",
            "metric_vs_overall_service",
            "study_specific_support_and_uncertainty",
            "execution_deviation",
            "scoped_cause",
            "bounded_actionability",
        ),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()


def _screen_private(option: DecisionOption) -> None:
    material = "\n".join(
        text for text in (option.wording, option.execution_instruction_draft or "") if text
    )
    for marker in _PRIVATE_MARKERS:
        if marker in material:
            raise DecisionSafetyError(
                "PRIVATE_CONTENT_DETECTED",
                f"option '{option.option_id}' carries a private path",
            )


def _validate_cause(option: DecisionOption, policy: DecisionSafetyPolicy) -> None:
    lowered = option.wording.lower()
    has_cause_wording = any(marker in lowered for marker in _CAUSAL_MARKERS)
    if option.cause_scope == "none":
        if has_cause_wording:
            raise DecisionSafetyError(
                "CAUSAL_SCOPE_UNSUPPORTED",
                f"option '{option.option_id}' uses cause wording without a bound design scope",
            )
        return
    authority = next(
        (
            item
            for item in policy.cause_design_authorities
            if item.design_digest == option.cause_design_digest
        ),
        None,
    )
    if (
        option.kind != "admitted_analysis"
        or authority is None
        or (
            _CAUSE_ORDER[option.cause_scope]
            > min(
                _CAUSE_ORDER[policy.maximum_cause_scope],
                _CAUSE_ORDER[authority.maximum_scope],
            )
        )
    ):
        raise DecisionSafetyError(
            "CAUSAL_SCOPE_UNSUPPORTED",
            f"option '{option.option_id}' requests cause scope '{option.cause_scope}' "
            "without compatible admitted design support",
        )


def _validate_comparison_contract(
    options: tuple[DecisionOption, ...], policy: DecisionSafetyPolicy
) -> None:
    if any(
        option.comparison_contract_digest != policy.comparison_contract_digest for option in options
    ):
        raise DecisionSafetyError(
            "INCOMPATIBLE_COMPARISON_CONTRACT",
            "every option must bind the policy's exact comparison contract digest",
        )
    groups = {option.compatibility_group for option in options}
    if len(groups) != 1:
        raise DecisionSafetyError(
            "INCOMPATIBLE_COMPARISON_CONTRACT",
            "options from different compatibility groups cannot share an assessment",
        )
    kinds = {option.kind for option in options}
    if "non_admitted" in kinds:
        raise DecisionSafetyError(
            "NON_ADMITTED_INPUT",
            "non-admitted work remains descriptive context, not a decision input",
        )
    if len(kinds) != 1:
        raise DecisionSafetyError(
            "INCOMPATIBLE_EVIDENCE",
            "different evidence standings require separately labelled assessments",
        )


def _rank(
    options: tuple[DecisionOption, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    metric_names = {option.primary_metric_name for option in options}
    directions = {option.metric_direction for option in options}
    if len(metric_names) != 1 or len(directions) != 1:
        raise DecisionSafetyError(
            "INCOMPATIBLE_COMPARISON_CONTRACT",
            "a ranking requires one endpoint definition and direction",
        )
    if any(not option.matched_budget or not option.comparison_predeclared for option in options):
        raise DecisionSafetyError(
            "RANKING_NOT_PREDECLARED_OR_MATCHED",
            "ranking requires a predeclared comparison with matched budgets in every cell",
        )
    reverse = options[0].metric_direction == "higher_is_better"
    ranked = tuple(
        option.option_id
        for option in sorted(
            options,
            key=lambda item: (
                -item.primary_metric_value if reverse else item.primary_metric_value,
                item.option_id,
            ),
        )
    )
    winning_value = (
        max(option.primary_metric_value for option in options)
        if reverse
        else min(option.primary_metric_value for option in options)
    )
    values = {option.option_id: option.primary_metric_value for option in options}
    winners = tuple(option_id for option_id in ranked if values[option_id] == winning_value)
    return ranked, winners


def assess(
    options: tuple[DecisionOption, ...],
    *,
    policy: DecisionSafetyPolicy,
    request_ranking: bool = False,
    request_advisory_recommendation: bool = False,
) -> DecisionSupportAssessment:
    """Apply v2 rules deterministically; useful outputs remain non-executable."""

    if not options:
        raise DecisionSafetyError("SUPPORT_INSUFFICIENT", "an assessment needs a typed option")
    _validate_comparison_contract(options, policy)
    for option in options:
        _screen_private(option)
        _validate_cause(option, policy)
        lowered = option.wording.lower()
        if any(marker in lowered for marker in _UNSUPPORTED_SUPERLATIVES):
            raise DecisionSafetyError(
                "UNSUPPORTED_GENERALISATION",
                f"option '{option.option_id}' claims reach beyond a metric-specific comparison",
            )

    notices: list[SafetyNotice] = []
    exclusions: dict[str, str] = {}
    compatible: list[DecisionOption] = []
    for option in options:
        if not option.inside_measured_envelope:
            exclusions[option.option_id] = "OUTSIDE_MEASURED_ENVELOPE"
            continue
        if not option.actor_capacity_measured:
            exclusions[option.option_id] = "ACTOR_CAPACITY_NOT_MEASURED"
            continue
        if option.execution_deviations and not option.deviations_disclosed:
            raise DecisionSafetyError(
                "EXECUTION_DEVIATION_UNACKNOWLEDGED",
                f"option '{option.option_id}' has an undisclosed execution deviation",
            )
        if option.support_count < policy.minimum_support_count:
            exclusions[option.option_id] = (
                f"SUPPORT_INSUFFICIENT: {option.support_count} < "
                f"study policy {policy.minimum_support_count}"
            )
            continue
        if option.interval_status == "unavailable":
            exclusions[option.option_id] = "UNCERTAINTY_UNAVAILABLE"
            continue
        if option.overall_service_claimed:
            missing = [
                name
                for name in policy.required_overall_service_companions
                if name not in option.companions_present
            ]
            if not option.service_endpoint_present or missing:
                raise DecisionSafetyError(
                    "OVERALL_SERVICE_SUPPORT_MISSING",
                    f"option '{option.option_id}' needs a service endpoint "
                    f"and companions {missing}",
                )
        elif option.headline_improvement_claimed:
            notices.append(
                SafetyNotice(
                    code="METRIC_SPECIFIC_ONLY",
                    text=(
                        f"option '{option.option_id}' may be described as better only on "
                        f"'{option.primary_metric_name}', not as better overall service"
                    ),
                    evidence_backed=option.kind == "admitted_analysis",
                    causal_scope=option.cause_scope,
                )
            )
        for deviation in option.execution_deviations:
            notices.append(
                SafetyNotice(
                    code="EXECUTION_DEVIATION",
                    text=f"option '{option.option_id}': {deviation}",
                    evidence_backed=option.kind == "admitted_analysis",
                )
            )
        compatible.append(option)

    digest = ruleset_digest(policy)
    input_digests = tuple(option.source_digest for option in options)
    if not compatible:
        return DecisionSupportAssessment(
            status="refused",
            ruleset_digest=digest,
            policy_id=policy.policy_id,
            policy_source_digest=policy.source_digest,
            display_order=policy.fixed_display_order,
            input_digests=input_digests,
            compatible_option_ids=(),
            exclusions=exclusions,
            notices=tuple(notices),
        )

    compatible_tuple = tuple(compatible)
    ranked: tuple[str, ...] = ()
    winners: tuple[str, ...] = ()
    if request_ranking or request_advisory_recommendation:
        if not policy.ranking_allowed:
            raise DecisionSafetyError(
                "RANKING_NOT_ALLOWED", "the bound study policy forbids ranking"
            )
        ranked, winners = _rank(compatible_tuple)
        notices.append(
            SafetyNotice(
                code="METRIC_SPECIFIC_RANKING",
                text=(
                    f"ranking is confined to '{compatible_tuple[0].primary_metric_name}' "
                    "inside the compatible predeclared matched-budget comparison"
                ),
                evidence_backed=all(item.kind == "admitted_analysis" for item in compatible_tuple),
                causal_scope=max(
                    (item.cause_scope for item in compatible_tuple),
                    key=lambda scope: _CAUSE_ORDER[scope],
                ),
            )
        )

    advisory: str | None = None
    recommendation = False
    evidence_backed = all(item.kind == "admitted_analysis" for item in compatible_tuple)
    if request_advisory_recommendation:
        if not policy.advisory_recommendation_allowed or not evidence_backed:
            raise DecisionSafetyError(
                "ADVISORY_RECOMMENDATION_UNSUPPORTED",
                "advice requires policy permission and admitted compatible evidence",
            )
        advisory = (
            f"Advisory: prefer {', '.join(winners)} for the predeclared metric "
            f"'{compatible_tuple[0].primary_metric_name}' within this measured comparison only."
        )
        recommendation = True

    default_id = policy.owner_preselected_default_option_id
    if default_id is not None and default_id not in {item.option_id for item in compatible_tuple}:
        raise DecisionSafetyError(
            "OWNER_DEFAULT_UNAVAILABLE",
            "the owner-preselected default is absent or excluded from this assessment",
        )

    drafts: list[ExecutionInstructionDraft] = []
    for option in compatible_tuple:
        if option.execution_instruction_draft is None:
            continue
        if not policy.execution_instruction_drafts_allowed:
            raise DecisionSafetyError(
                "EXECUTION_DRAFT_NOT_ALLOWED",
                "the bound policy does not allow reviewable instruction drafts",
            )
        drafts.append(
            ExecutionInstructionDraft(
                option_id=option.option_id,
                text=option.execution_instruction_draft,
            )
        )

    notices.append(
        SafetyNotice(
            code="SUPPORT_AND_UNCERTAINTY_RETAINED",
            text=(
                f"every included option meets study-specific support >= "
                f"{policy.minimum_support_count} and carries an available interval status"
            ),
            evidence_backed=evidence_backed,
        )
    )
    maximum_cause = max(
        (item.cause_scope for item in compatible_tuple),
        key=lambda scope: _CAUSE_ORDER[scope],
    )
    return DecisionSupportAssessment(
        status="presentable_with_cautions",
        ruleset_digest=digest,
        policy_id=policy.policy_id,
        policy_source_digest=policy.source_digest,
        display_order=policy.fixed_display_order,
        input_digests=input_digests,
        compatible_option_ids=tuple(item.option_id for item in compatible_tuple),
        exclusions=exclusions,
        notices=tuple(notices),
        ranked_option_ids=ranked,
        metric_winner_option_ids=winners,
        advisory_recommendation=advisory,
        owner_preselected_default_option_id=default_id,
        execution_instruction_drafts=tuple(drafts),
        recommendation=recommendation,
        evidence_backed=evidence_backed,
        causal_scope=maximum_cause,
    )


def confirmed_capacity_notice(repo_root: Path) -> SafetyNotice:
    """Emit the exact capacity notice only while the reviewed source digest matches."""

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
            "the confirmatory record changed; refusing stale headline numbers",
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
            "This metric-specific result is not an overall-service ranking."
        ),
        evidence_backed=True,
    )


def assessment_to_json(assessment: DecisionSupportAssessment) -> str:
    return json.dumps(assessment.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)
