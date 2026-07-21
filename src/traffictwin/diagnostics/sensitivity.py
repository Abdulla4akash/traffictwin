"""Verified single-boundary nearest-flip analysis for deterministic rules."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import JsonScalar, JsonValue
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import Finding, RuleResult, RuleStatus

SUPPORTED_NEAREST_FLIP_RULE_IDS = ("R5", "R7", "R8")
CORE_RULE_IDS = tuple(f"R{index}" for index in range(9))


class NearestFlipStatus(StrEnum):
    """Availability state for one nearest-flip analysis."""

    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"


class NearestFlipReason(StrEnum):
    """Stable reason code explaining the analysis state."""

    AVAILABLE = "AVAILABLE"
    UNSUPPORTED_RULE = "UNSUPPORTED_RULE"
    RULE_DISABLED = "RULE_DISABLED"
    SOURCE_RULE_NOT_NOT_TRIGGERED = "SOURCE_RULE_NOT_NOT_TRIGGERED"
    DISCRETE_CONSTRAINT_UNMET = "DISCRETE_CONSTRAINT_UNMET"
    OBSERVED_BOUNDARY_INVALID = "OBSERVED_BOUNDARY_INVALID"
    CANDIDATE_DID_NOT_TRIGGER = "CANDIDATE_DID_NOT_TRIGGER"


class NearestFlipConstraint(BaseModel):
    """One discrete admission constraint that the analysis never changes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_path: str
    constraint_kind: Literal["discrete_support"] = "discrete_support"
    observed_value: int | None
    required_minimum: int
    unit: Literal["count"] = "count"
    satisfied: bool
    mutable_by_analysis: Literal[False] = False
    detail: str


class NearestFlipCandidate(BaseModel):
    """One equal-minimum verified configuration candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_path: str
    current_value: float
    flip_value: float
    absolute_delta: float = Field(ge=0.0, allow_inf_nan=False)
    direction: Literal["decrease"] = "decrease"
    unit: str
    source_operator: Literal["greater_than_or_equal"] = "greater_than_or_equal"
    inclusive_boundary: Literal[True] = True
    verified_status: Literal[RuleStatus.TRIGGERED] = RuleStatus.TRIGGERED
    candidate_rule_config: dict[str, JsonValue]


class NearestFlipAnalysis(BaseModel):
    """Typed deterministic DIA-05 sensitivity artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["DIA-05"] = "DIA-05"
    analysis_version: Literal["1.0"] = "1.0"
    analysis_id: str
    status: NearestFlipStatus
    reason_code: NearestFlipReason
    reason: str
    rule_id: str
    rule_version: str | None
    ruleset_version: str
    source_status: RuleStatus | None
    candidate_status: RuleStatus | None
    source_rule_config: dict[str, JsonValue]
    candidates: list[NearestFlipCandidate] = Field(default_factory=list)
    tie_count: int = Field(default=0, ge=0)
    constraints: list[NearestFlipConstraint] = Field(default_factory=list)
    evidence_keys: list[str] = Field(default_factory=list)
    evidence_pack_id: str
    evidence_pack_fingerprint: str
    source_bundle_fingerprint: str | None
    current_result_fingerprint: str | None
    candidate_result_fingerprint: str | None
    synthetic: bool
    analysed_at: datetime
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_candidates(self) -> NearestFlipAnalysis:
        """Keep availability and tie fields internally consistent."""

        if self.tie_count != len(self.candidates):
            raise ValueError("tie_count must equal the number of returned candidates")
        if self.status is NearestFlipStatus.AVAILABLE and not self.candidates:
            raise ValueError("available nearest-flip analysis requires a verified candidate")
        if self.status is not NearestFlipStatus.AVAILABLE and self.candidates:
            raise ValueError("non-available nearest-flip analysis cannot contain candidates")
        return self

    def canonical_json(self) -> str:
        """Return deterministic JSON with only the analysis timestamp normalised."""

        data = self.model_dump(mode="json")
        data["analysed_at"] = "<normalised>"
        return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        """Return the deterministic artifact fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        """Return formatted JSON without non-standard numeric values."""

        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


class NearestFlipContract(BaseModel):
    """Machine-readable public boundary for DIA-05."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["DIA-05"] = "DIA-05"
    analysis_version: Literal["1.0"] = "1.0"
    evidence_boundary: Literal["EvidencePack"] = "EvidencePack"
    source_status_required: Literal["not_triggered"] = "not_triggered"
    candidate_verification: Literal["ordinary_rule_engine_re_evaluation"] = (
        "ordinary_rule_engine_re_evaluation"
    )
    configuration_distance: Literal["absolute_one_axis_delta_in_parameter_unit"] = (
        "absolute_one_axis_delta_in_parameter_unit"
    )
    supported_threshold_parameters: dict[str, str]
    unsupported_rule_ids: list[str]
    discrete_constraint_policy: Literal["report_but_never_change"] = "report_but_never_change"
    tie_policy: Literal["retain_all_equal_minimum_verified_candidates"] = (
        "retain_all_equal_minimum_verified_candidates"
    )
    persistence_policy: Literal["analysis_does_not_persist_configuration"] = (
        "analysis_does_not_persist_configuration"
    )
    limitations: list[str]


def nearest_flip_contract() -> NearestFlipContract:
    """Return the static versioned DIA-05 contract."""

    return NearestFlipContract(
        supported_threshold_parameters={
            "R5": "r5.maximum_absolute_gap",
            "R7": "r7.minimum_outcome_gap",
            "R8": "r8.minimum_energy_per_completed_task_j",
        },
        unsupported_rule_ids=["R0", "R1", "R2", "R3", "R4", "R6", "declarative"],
        limitations=_limitations(),
    )


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def analyse_nearest_flip(
    evidence_pack: EvidencePack,
    rule_id: str,
    rule_config: RuleSetConfig | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> NearestFlipAnalysis:
    """Return the exact verified one-axis flip for an eligible R5, R7, or R8 result."""

    config = rule_config or RuleSetConfig()
    selected = rule_id.strip().upper()
    analysed_at = clock()
    source_section = _source_section(config, selected)
    analysis_id = _analysis_id(
        evidence_pack,
        selected,
        source_section,
        config.ruleset_version,
    )
    common = _common_fields(evidence_pack, config, selected, analysed_at, analysis_id)

    if selected not in SUPPORTED_NEAREST_FLIP_RULE_IDS:
        return NearestFlipAnalysis(
            **common,
            status=NearestFlipStatus.UNSUPPORTED,
            reason_code=NearestFlipReason.UNSUPPORTED_RULE,
            reason=(
                "DIA-05 v1.0 supports only the single-boundary R5, R7, and R8 families; "
                "this rule remains unchanged and was not evaluated for a flip."
            ),
            rule_version=None,
            source_status=None,
            candidate_status=None,
            source_rule_config=source_section,
            current_result_fingerprint=None,
            candidate_result_fingerprint=None,
        )

    section = getattr(config, selected.lower())
    if not section.enabled:
        return NearestFlipAnalysis(
            **common,
            status=NearestFlipStatus.NOT_APPLICABLE,
            reason_code=NearestFlipReason.RULE_DISABLED,
            reason="The selected rule is disabled in the supplied configuration.",
            rule_version="1.0",
            source_status=None,
            candidate_status=None,
            source_rule_config=source_section,
            current_result_fingerprint=None,
            candidate_result_fingerprint=None,
        )

    source_result = _evaluate_selected(evidence_pack, config, selected, analysed_at)
    source_fingerprint = _rule_result_fingerprint(source_result)
    if source_result.status is not RuleStatus.NOT_TRIGGERED:
        return NearestFlipAnalysis(
            **common,
            status=NearestFlipStatus.NOT_APPLICABLE,
            reason_code=NearestFlipReason.SOURCE_RULE_NOT_NOT_TRIGGERED,
            reason=(
                "Nearest flip requires a current not_triggered result; observed "
                f"{source_result.status.value}."
            ),
            rule_version=source_result.rule_version,
            source_status=source_result.status,
            candidate_status=None,
            source_rule_config=source_section,
            evidence_keys=source_result.evidence_keys,
            current_result_fingerprint=source_fingerprint,
            candidate_result_fingerprint=None,
        )

    boundary = _boundary_from_result(selected, source_result, config)
    constraints = _constraints_from_result(selected, source_result, config)
    if boundary is None:
        return NearestFlipAnalysis(
            **common,
            status=NearestFlipStatus.NOT_APPLICABLE,
            reason_code=NearestFlipReason.OBSERVED_BOUNDARY_INVALID,
            reason="The admitted rule result did not expose a finite supported boundary value.",
            rule_version=source_result.rule_version,
            source_status=source_result.status,
            candidate_status=None,
            source_rule_config=source_section,
            constraints=constraints,
            evidence_keys=source_result.evidence_keys,
            current_result_fingerprint=source_fingerprint,
            candidate_result_fingerprint=None,
        )

    if not constraints or any(not item.satisfied for item in constraints):
        return NearestFlipAnalysis(
            **common,
            status=NearestFlipStatus.NOT_APPLICABLE,
            reason_code=NearestFlipReason.DISCRETE_CONSTRAINT_UNMET,
            reason=(
                "A discrete evidence-support constraint is unmet; nearest-flip analysis never "
                "lowers sample, pair, or group-support requirements."
            ),
            rule_version=source_result.rule_version,
            source_status=source_result.status,
            candidate_status=None,
            source_rule_config=source_section,
            constraints=constraints,
            evidence_keys=source_result.evidence_keys,
            current_result_fingerprint=source_fingerprint,
            candidate_result_fingerprint=None,
        )

    parameter_path, field_name, current_value, observed_value, unit = boundary
    if observed_value > current_value:
        return NearestFlipAnalysis(
            **common,
            status=NearestFlipStatus.NOT_APPLICABLE,
            reason_code=NearestFlipReason.OBSERVED_BOUNDARY_INVALID,
            reason="The observed value is not below the current inclusive threshold.",
            rule_version=source_result.rule_version,
            source_status=source_result.status,
            candidate_status=None,
            source_rule_config=source_section,
            constraints=constraints,
            evidence_keys=source_result.evidence_keys,
            current_result_fingerprint=source_fingerprint,
            candidate_result_fingerprint=None,
        )

    candidate_config = _candidate_config(config, selected, field_name, observed_value)
    candidate_result = _evaluate_selected(
        evidence_pack,
        candidate_config,
        selected,
        analysed_at,
    )
    candidate_fingerprint = _rule_result_fingerprint(candidate_result)
    if candidate_result.status is not RuleStatus.TRIGGERED:
        return NearestFlipAnalysis(
            **common,
            status=NearestFlipStatus.NOT_APPLICABLE,
            reason_code=NearestFlipReason.CANDIDATE_DID_NOT_TRIGGER,
            reason=(
                "The ordinary rule engine did not verify the exact boundary candidate as triggered."
            ),
            rule_version=source_result.rule_version,
            source_status=source_result.status,
            candidate_status=candidate_result.status,
            source_rule_config=source_section,
            constraints=constraints,
            evidence_keys=source_result.evidence_keys,
            current_result_fingerprint=source_fingerprint,
            candidate_result_fingerprint=candidate_fingerprint,
        )

    candidate_section = getattr(candidate_config, selected.lower()).model_dump(mode="json")
    candidate = NearestFlipCandidate(
        parameter_path=parameter_path,
        current_value=current_value,
        flip_value=observed_value,
        absolute_delta=abs(current_value - observed_value),
        unit=unit,
        candidate_rule_config=candidate_section,
    )
    return NearestFlipAnalysis(
        **common,
        status=NearestFlipStatus.AVAILABLE,
        reason_code=NearestFlipReason.AVAILABLE,
        reason=("The ordinary rule engine verified the exact inclusive single-boundary candidate."),
        rule_version=source_result.rule_version,
        source_status=source_result.status,
        candidate_status=candidate_result.status,
        source_rule_config=source_section,
        candidates=[candidate],
        tie_count=1,
        constraints=constraints,
        evidence_keys=source_result.evidence_keys,
        current_result_fingerprint=source_fingerprint,
        candidate_result_fingerprint=candidate_fingerprint,
    )


def _common_fields(
    evidence_pack: EvidencePack,
    config: RuleSetConfig,
    rule_id: str,
    analysed_at: datetime,
    analysis_id: str,
) -> dict[str, JsonValue]:
    return {
        "analysis_id": analysis_id,
        "rule_id": rule_id,
        "ruleset_version": config.ruleset_version,
        "evidence_pack_id": evidence_pack.pack_id,
        "evidence_pack_fingerprint": evidence_pack.fingerprint(),
        "source_bundle_fingerprint": evidence_pack.source_bundle_fingerprint,
        "synthetic": evidence_pack.synthetic,
        "analysed_at": analysed_at,
        "provenance": {
            "source_evidence_fingerprint": evidence_pack.fingerprint(),
            "source_bundle_fingerprint": evidence_pack.source_bundle_fingerprint,
            "metric_version": evidence_pack.metric_collection.metric_version,
        },
        "limitations": _limitations(),
    }


def _source_section(config: RuleSetConfig, rule_id: str) -> dict[str, JsonValue]:
    if rule_id not in CORE_RULE_IDS:
        return {}
    return cast(dict[str, JsonValue], getattr(config, rule_id.lower()).model_dump(mode="json"))


def _analysis_id(
    evidence_pack: EvidencePack,
    rule_id: str,
    source_section: dict[str, JsonValue],
    ruleset_version: str,
) -> str:
    basis = json.dumps(
        {
            "analysis_version": "1.0",
            "evidence_pack_fingerprint": evidence_pack.fingerprint(),
            "rule_id": rule_id,
            "ruleset_version": ruleset_version,
            "source_rule_config": source_section,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"nearest-flip-{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:12]}"


def _evaluate_selected(
    evidence_pack: EvidencePack,
    config: RuleSetConfig,
    rule_id: str,
    evaluated_at: datetime,
) -> RuleResult:
    isolated = _isolated_config(config, rule_id)
    report = evaluate_rules(evidence_pack, isolated, clock=lambda: evaluated_at)
    if len(report.results) != 1 or report.results[0].rule_id != rule_id:
        raise RuntimeError(f"isolated nearest-flip evaluation failed for {rule_id}")
    return report.results[0]


def _isolated_config(config: RuleSetConfig, rule_id: str) -> RuleSetConfig:
    payload = config.model_dump(mode="json")
    for candidate in CORE_RULE_IDS:
        payload[candidate.lower()]["enabled"] = candidate == rule_id
    return RuleSetConfig.model_validate(payload)


def _candidate_config(
    config: RuleSetConfig,
    rule_id: str,
    field_name: str,
    value: float,
) -> RuleSetConfig:
    payload = config.model_dump(mode="json")
    payload[rule_id.lower()][field_name] = value
    return RuleSetConfig.model_validate(payload)


def _boundary_from_result(
    rule_id: str,
    result: RuleResult,
    config: RuleSetConfig,
) -> tuple[str, str, float, float, str] | None:
    if rule_id == "R5":
        observed = _finding_number(result, "R5-F2", "maximum_absolute_gap")
        current = config.r5.maximum_absolute_gap
        return _boundary(
            "r5.maximum_absolute_gap", "maximum_absolute_gap", current, observed, "ratio"
        )
    if rule_id == "R7":
        observed = _finding_number(result, None, "observed_value")
        current = config.r7.minimum_outcome_gap
        return _boundary(
            "r7.minimum_outcome_gap", "minimum_outcome_gap", current, observed, "ratio"
        )
    observed = _finding_number(result, "R8-F1", "energy_per_completed_task_j")
    current = config.r8.minimum_energy_per_completed_task_j
    return _boundary(
        "r8.minimum_energy_per_completed_task_j",
        "minimum_energy_per_completed_task_j",
        current,
        observed,
        "J/task",
    )


def _boundary(
    parameter_path: str,
    field_name: str,
    current: float,
    observed: float | None,
    unit: str,
) -> tuple[str, str, float, float, str] | None:
    if observed is None or observed < 0 or not math.isfinite(current):
        return None
    return parameter_path, field_name, float(current), observed, unit


def _constraints_from_result(
    rule_id: str,
    result: RuleResult,
    config: RuleSetConfig,
) -> list[NearestFlipConstraint]:
    if rule_id == "R5":
        observed = _finding_whole_number(result, "R5-F1", "pair_count")
        return [
            _constraint(
                "r5.minimum_pair_count",
                observed,
                config.r5.minimum_pair_count,
                "explicit training-validation pairs",
            )
        ]
    if rule_id == "R7":
        observed_groups = _finding_whole_number(result, None, "group_count")
        observed_support = _finding_whole_number(
            result,
            None,
            "minimum_group_support_observed",
        )
        return [
            _constraint(
                "r7.minimum_group_count",
                observed_groups,
                2,
                "exact admitted operational groups",
            ),
            _constraint(
                "r7.minimum_group_support",
                observed_support,
                config.r7.minimum_group_support,
                "minimum observations in every admitted group",
            ),
        ]
    observed = _finding_whole_number(result, "R8-F2", "completed_task_count")
    return [
        _constraint(
            "r8.minimum_completed_tasks",
            observed,
            config.r8.minimum_completed_tasks,
            "completed tasks in the exact energy population",
        )
    ]


def _constraint(
    parameter_path: str,
    observed: int | None,
    required: int,
    subject: str,
) -> NearestFlipConstraint:
    satisfied = observed is not None and observed >= required
    return NearestFlipConstraint(
        parameter_path=parameter_path,
        observed_value=observed,
        required_minimum=required,
        satisfied=satisfied,
        detail=f"{subject}: observed {observed}, required at least {required}",
    )


def _finding_number(
    result: RuleResult,
    finding_id: str | None,
    key: str,
) -> float | None:
    finding = _finding(result, finding_id)
    if finding is None:
        return None
    value = finding.observed_values.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _finding_whole_number(
    result: RuleResult,
    finding_id: str | None,
    key: str,
) -> int | None:
    number = _finding_number(result, finding_id, key)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def _finding(result: RuleResult, finding_id: str | None) -> Finding | None:
    if finding_id is None:
        return result.findings[0] if result.findings else None
    return next((item for item in result.findings if item.finding_id == finding_id), None)


def _rule_result_fingerprint(result: RuleResult) -> str:
    payload = result.model_dump(mode="json")
    payload["evaluated_at"] = "<normalised>"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _limitations() -> list[str]:
    return [
        "A nearest flip is a mathematical sensitivity boundary, not a recommended threshold.",
        "v1.0 changes one continuous severity threshold and never lowers discrete evidence "
        "support.",
        "The analysis does not persist, export as a default, or mutate the supplied configuration.",
        "R5, R7, and R8 defaults remain provisional and require predeclared external calibration.",
        "The result does not establish statistical significance, causality, optimisation, or "
        "external validity.",
    ]
