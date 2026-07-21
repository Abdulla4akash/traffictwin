"""Deterministic DIA-06 threshold-sensitivity sweeps over EvidencePack rules."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.diagnostics.sensitivity import NearestFlipAnalysis, analyse_nearest_flip
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import JsonScalar, JsonValue
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import RuleResult, RuleStatus

SUPPORTED_SWEEP_RULE_IDS = ("R5", "R7", "R8")
CORE_RULE_IDS = tuple(f"R{index}" for index in range(9))
GRID_PRECISION_DECIMAL_PLACES = 12


class ThresholdSweepStatus(StrEnum):
    """Availability state for one threshold sweep."""

    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"


class ThresholdSweepReason(StrEnum):
    """Stable reason explaining the sweep state."""

    AVAILABLE = "AVAILABLE"
    UNSUPPORTED_RULE = "UNSUPPORTED_RULE"
    RULE_DISABLED = "RULE_DISABLED"


class ThresholdSweepRequest(BaseModel):
    """Bounded deterministic request for one inclusive linear grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    rule_id: str = Field(min_length=1)
    minimum_threshold: float = Field(ge=0.0, allow_inf_nan=False)
    maximum_threshold: float = Field(gt=0.0, allow_inf_nan=False)
    point_count: int = Field(default=11, ge=2, le=101)

    @model_validator(mode="after")
    def validate_bounds(self) -> ThresholdSweepRequest:
        """Require a non-empty increasing threshold interval."""

        if self.maximum_threshold <= self.minimum_threshold:
            raise ValueError("maximum_threshold must be greater than minimum_threshold")
        return self


class ThresholdSweepPoint(BaseModel):
    """One retained ordinary rule-engine result on the declared grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: int = Field(ge=0)
    threshold: float = Field(ge=0.0, allow_inf_nan=False)
    status: RuleStatus
    triggered: bool
    is_source_threshold: bool
    rule_config: dict[str, JsonValue]
    result_fingerprint: str
    evidence_keys: list[str] = Field(default_factory=list)
    finding_count: int = Field(ge=0)
    missing_evidence_count: int = Field(ge=0)


class ThresholdFlipBoundary(BaseModel):
    """One sampled interval whose adjacent points change trigger membership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lower_ordinal: int = Field(ge=0)
    upper_ordinal: int = Field(ge=1)
    lower_threshold: float = Field(ge=0.0, allow_inf_nan=False)
    upper_threshold: float = Field(gt=0.0, allow_inf_nan=False)
    lower_status: RuleStatus
    upper_status: RuleStatus
    transition: Literal["triggered_to_not_triggered", "not_triggered_to_triggered"]
    interpretation: Literal["sampled_interval_not_exact_boundary"] = (
        "sampled_interval_not_exact_boundary"
    )


class TriggerStabilitySummary(BaseModel):
    """Deterministic status and trigger-membership summary for the complete grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluated_point_count: int = Field(ge=1)
    triggered_point_count: int = Field(ge=0)
    triggered_fraction: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    status_counts: dict[str, int]
    status_transition_count: int = Field(ge=0)
    trigger_transition_count: int = Field(ge=0)
    all_statuses_identical: bool
    triggered_membership_monotonic_prefix: bool
    status_sequence_fingerprint: str

    @model_validator(mode="after")
    def validate_counts(self) -> TriggerStabilitySummary:
        """Keep all summary counts internally consistent."""

        if sum(self.status_counts.values()) != self.evaluated_point_count:
            raise ValueError("status_counts must cover every evaluated point")
        if self.triggered_point_count > self.evaluated_point_count:
            raise ValueError("triggered_point_count cannot exceed evaluated_point_count")
        return self


class ThresholdSensitivityReport(BaseModel):
    """Typed deterministic DIA-06 report over one complete threshold grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["DIA-06"] = "DIA-06"
    analysis_version: Literal["1.0"] = "1.0"
    analysis_id: str
    status: ThresholdSweepStatus
    reason_code: ThresholdSweepReason
    reason: str
    request: ThresholdSweepRequest
    rule_id: str
    rule_version: str | None
    ruleset_version: str
    parameter_path: str | None
    threshold_unit: str | None
    inclusive_boundary: bool
    provisional_default: bool
    source_threshold: float | None
    source_status: RuleStatus | None
    source_rule_config: dict[str, JsonValue]
    fixed_rule_config: dict[str, JsonValue]
    source_result_fingerprint: str | None
    requested_point_count: int = Field(ge=2)
    evaluated_point_count: int = Field(ge=0)
    source_threshold_injected: bool
    points: list[ThresholdSweepPoint] = Field(default_factory=list)
    stability: TriggerStabilitySummary | None
    flip_boundaries: list[ThresholdFlipBoundary] = Field(default_factory=list)
    nearest_flip: NearestFlipAnalysis | None
    nearest_flip_fingerprint: str | None
    evidence_pack_id: str
    evidence_pack_fingerprint: str
    source_bundle_fingerprint: str | None
    synthetic: bool
    analysed_at: datetime
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_report(self) -> ThresholdSensitivityReport:
        """Keep availability, point, and nested-artifact fields consistent."""

        if self.evaluated_point_count != len(self.points):
            raise ValueError("evaluated_point_count must equal the number of retained points")
        if self.status is ThresholdSweepStatus.AVAILABLE:
            if not self.points or self.stability is None:
                raise ValueError("available threshold sweep requires points and stability")
        elif self.points or self.stability is not None or self.flip_boundaries:
            raise ValueError("non-available threshold sweep cannot contain evaluated grid output")
        if (self.nearest_flip is None) != (self.nearest_flip_fingerprint is None):
            raise ValueError("nearest flip and its fingerprint must be present together")
        return self

    def canonical_json(self) -> str:
        """Return deterministic JSON with generated analysis timestamps normalised."""

        data = self.model_dump(mode="json")
        data["analysed_at"] = "<normalised>"
        nearest = data.get("nearest_flip")
        if isinstance(nearest, dict):
            nearest["analysed_at"] = "<normalised>"
        return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        """Return the deterministic report fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        """Return readable strict JSON."""

        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


class ThresholdSensitivityContract(BaseModel):
    """Machine-readable DIA-06 service and persistence boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["DIA-06"] = "DIA-06"
    analysis_version: Literal["1.0"] = "1.0"
    evidence_boundary: Literal["EvidencePack"] = "EvidencePack"
    supported_threshold_parameters: dict[str, str]
    unsupported_rule_ids: list[str]
    grid_method: Literal["inclusive_linear_v1"] = "inclusive_linear_v1"
    grid_precision_decimal_places: Literal[12] = 12
    minimum_point_count: Literal[2] = 2
    maximum_point_count: Literal[101] = 101
    source_threshold_policy: Literal["insert_when_inside_declared_range"] = (
        "insert_when_inside_declared_range"
    )
    point_evaluation: Literal["ordinary_rule_engine_same_evidence_and_timestamp"] = (
        "ordinary_rule_engine_same_evidence_and_timestamp"
    )
    result_retention: Literal["retain_every_evaluated_status"] = "retain_every_evaluated_status"
    flip_boundary_semantics: Literal["adjacent_sampled_trigger_membership_interval"] = (
        "adjacent_sampled_trigger_membership_interval"
    )
    exact_boundary_source: Literal["DIA-05_when_admissible"] = "DIA-05_when_admissible"
    persistence_policy: Literal["session_only_until_explicit_complete_config_export_import"] = (
        "session_only_until_explicit_complete_config_export_import"
    )
    limitations: list[str]


class ThresholdSweepAxis(BaseModel):
    """One public selected-rule threshold-axis contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_path: str
    field_name: str
    unit: str
    maximum_allowed: float | None = None


SWEEP_AXES: dict[str, ThresholdSweepAxis] = {
    "R5": ThresholdSweepAxis(
        parameter_path="r5.maximum_absolute_gap",
        field_name="maximum_absolute_gap",
        unit="ratio",
    ),
    "R7": ThresholdSweepAxis(
        parameter_path="r7.minimum_outcome_gap",
        field_name="minimum_outcome_gap",
        unit="ratio",
        maximum_allowed=1.0,
    ),
    "R8": ThresholdSweepAxis(
        parameter_path="r8.minimum_energy_per_completed_task_j",
        field_name="minimum_energy_per_completed_task_j",
        unit="J/task",
    ),
}


def threshold_sensitivity_contract() -> ThresholdSensitivityContract:
    """Return the static versioned DIA-06 contract."""

    return ThresholdSensitivityContract(
        supported_threshold_parameters={
            rule_id: axis.parameter_path for rule_id, axis in SWEEP_AXES.items()
        },
        unsupported_rule_ids=["R0", "R1", "R2", "R3", "R4", "R6", "declarative"],
        limitations=_limitations(),
    )


def threshold_sweep_axis(rule_id: str) -> ThresholdSweepAxis:
    """Return the immutable public axis contract for one supported rule."""

    selected = rule_id.strip().upper()
    axis = SWEEP_AXES.get(selected)
    if axis is None:
        raise ValueError(f"threshold sweep is unsupported for {selected or rule_id!r}")
    return axis


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def evaluate_threshold_sweep(
    evidence_pack: EvidencePack,
    request: ThresholdSweepRequest,
    rule_config: RuleSetConfig | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> ThresholdSensitivityReport:
    """Evaluate and retain the full requested threshold grid through the ordinary rule engine."""

    config = rule_config or RuleSetConfig()
    selected = request.rule_id.strip().upper()
    analysed_at = clock()
    source_section = _source_section(config, selected)
    common = _common_fields(
        evidence_pack,
        request,
        config,
        selected,
        source_section,
        analysed_at,
    )
    axis = SWEEP_AXES.get(selected)
    if axis is None:
        return ThresholdSensitivityReport(
            **common,
            status=ThresholdSweepStatus.UNSUPPORTED,
            reason_code=ThresholdSweepReason.UNSUPPORTED_RULE,
            reason=(
                "DIA-06 v1.0 supports only the contracted R5, R7, and R8 single-boundary "
                "thresholds; no grid was evaluated."
            ),
            rule_version=None,
            parameter_path=None,
            threshold_unit=None,
            source_threshold=None,
            source_status=None,
            fixed_rule_config={},
            source_result_fingerprint=None,
            evaluated_point_count=0,
            source_threshold_injected=False,
            stability=None,
            nearest_flip=None,
            nearest_flip_fingerprint=None,
        )

    _validate_rule_bounds(request, selected, axis)
    section = getattr(config, selected.lower())
    source_threshold = float(getattr(section, axis.field_name))
    fixed_config = source_section.copy()
    fixed_config.pop(axis.field_name, None)
    if not section.enabled:
        return ThresholdSensitivityReport(
            **common,
            status=ThresholdSweepStatus.NOT_APPLICABLE,
            reason_code=ThresholdSweepReason.RULE_DISABLED,
            reason="The selected rule is disabled in the supplied complete configuration.",
            rule_version="1.0",
            parameter_path=axis.parameter_path,
            threshold_unit=axis.unit,
            source_threshold=source_threshold,
            source_status=None,
            fixed_rule_config=fixed_config,
            source_result_fingerprint=None,
            evaluated_point_count=0,
            source_threshold_injected=False,
            stability=None,
            nearest_flip=None,
            nearest_flip_fingerprint=None,
        )

    thresholds, injected = _threshold_grid(request, source_threshold)
    source_result = _evaluate_selected(evidence_pack, config, selected, analysed_at)
    points: list[ThresholdSweepPoint] = []
    for ordinal, threshold in enumerate(thresholds):
        point_config = config_with_threshold(config, selected, threshold)
        result = _evaluate_selected(evidence_pack, point_config, selected, analysed_at)
        points.append(
            ThresholdSweepPoint(
                ordinal=ordinal,
                threshold=threshold,
                status=result.status,
                triggered=result.status is RuleStatus.TRIGGERED,
                is_source_threshold=threshold == source_threshold,
                rule_config=cast(
                    dict[str, JsonValue],
                    getattr(point_config, selected.lower()).model_dump(mode="json"),
                ),
                result_fingerprint=_rule_result_fingerprint(result),
                evidence_keys=result.evidence_keys,
                finding_count=len(result.findings),
                missing_evidence_count=len(result.missing_evidence),
            )
        )
    stability = _stability(points)
    boundaries = _flip_boundaries(points)
    nearest = analyse_nearest_flip(
        evidence_pack,
        selected,
        config,
        clock=lambda: analysed_at,
    )
    return ThresholdSensitivityReport(
        **common,
        status=ThresholdSweepStatus.AVAILABLE,
        reason_code=ThresholdSweepReason.AVAILABLE,
        reason="Every declared threshold point was evaluated by the ordinary rule engine.",
        rule_version=source_result.rule_version,
        parameter_path=axis.parameter_path,
        threshold_unit=axis.unit,
        source_threshold=source_threshold,
        source_status=source_result.status,
        fixed_rule_config=fixed_config,
        source_result_fingerprint=_rule_result_fingerprint(source_result),
        evaluated_point_count=len(points),
        source_threshold_injected=injected,
        points=points,
        stability=stability,
        flip_boundaries=boundaries,
        nearest_flip=nearest,
        nearest_flip_fingerprint=nearest.fingerprint(),
    )


def config_with_threshold(
    config: RuleSetConfig,
    rule_id: str,
    threshold: float,
) -> RuleSetConfig:
    """Return a validated complete config with one supported threshold changed in memory."""

    selected = rule_id.strip().upper()
    axis = SWEEP_AXES.get(selected)
    if axis is None:
        raise ValueError(f"threshold sweep is unsupported for {selected or rule_id!r}")
    if isinstance(threshold, bool) or not math.isfinite(threshold) or threshold < 0:
        raise ValueError("threshold must be finite and non-negative")
    if axis.maximum_allowed is not None and threshold > axis.maximum_allowed:
        raise ValueError(f"{selected} threshold must be <= {axis.maximum_allowed}")
    payload = config.model_dump(mode="json")
    payload[selected.lower()][axis.field_name] = threshold
    return RuleSetConfig.model_validate(payload)


def config_for_evaluated_point(
    report: ThresholdSensitivityReport,
    source_config: RuleSetConfig,
    threshold: float,
) -> RuleSetConfig:
    """Return a complete config only for an exact point retained by this report."""

    if report.status is not ThresholdSweepStatus.AVAILABLE:
        raise ValueError("configuration export requires an available threshold sweep")
    source_section = _source_section(source_config, report.rule_id)
    if source_config.ruleset_version != report.ruleset_version:
        raise ValueError("source config ruleset version does not match the sweep report")
    if source_section != report.source_rule_config:
        raise ValueError("source config does not match the sweep report")
    if not any(point.threshold == threshold for point in report.points):
        raise ValueError("threshold was not evaluated in this sweep")
    return config_with_threshold(source_config, report.rule_id, threshold)


def _validate_rule_bounds(
    request: ThresholdSweepRequest,
    rule_id: str,
    axis: ThresholdSweepAxis,
) -> None:
    if axis.maximum_allowed is not None and request.maximum_threshold > axis.maximum_allowed:
        raise ValueError(f"{rule_id} maximum_threshold must be <= {axis.maximum_allowed}")


def _threshold_grid(
    request: ThresholdSweepRequest,
    source_threshold: float,
) -> tuple[list[float], bool]:
    span = request.maximum_threshold - request.minimum_threshold
    denominator = request.point_count - 1
    thresholds = [
        round(
            request.minimum_threshold + span * ordinal / denominator,
            GRID_PRECISION_DECIMAL_PLACES,
        )
        for ordinal in range(request.point_count)
    ]
    thresholds[0] = request.minimum_threshold
    thresholds[-1] = request.maximum_threshold
    injected = False
    if (
        request.minimum_threshold <= source_threshold <= request.maximum_threshold
        and source_threshold not in thresholds
    ):
        thresholds.append(source_threshold)
        injected = True
    return sorted(set(thresholds)), injected


def _stability(points: list[ThresholdSweepPoint]) -> TriggerStabilitySummary:
    statuses = [point.status.value for point in points]
    triggered = [point.triggered for point in points]
    status_counts = dict(sorted(Counter(statuses).items()))
    status_transitions = sum(
        left.status is not right.status for left, right in zip(points, points[1:], strict=False)
    )
    trigger_transitions = sum(
        left.triggered != right.triggered for left, right in zip(points, points[1:], strict=False)
    )
    seen_not_triggered = False
    monotonic_prefix = True
    for membership in triggered:
        if not membership:
            seen_not_triggered = True
        elif seen_not_triggered:
            monotonic_prefix = False
            break
    sequence = json.dumps(statuses, separators=(",", ":"), allow_nan=False)
    triggered_count = sum(triggered)
    return TriggerStabilitySummary(
        evaluated_point_count=len(points),
        triggered_point_count=triggered_count,
        triggered_fraction=triggered_count / len(points),
        status_counts=status_counts,
        status_transition_count=status_transitions,
        trigger_transition_count=trigger_transitions,
        all_statuses_identical=len(status_counts) == 1,
        triggered_membership_monotonic_prefix=monotonic_prefix,
        status_sequence_fingerprint=hashlib.sha256(sequence.encode("utf-8")).hexdigest(),
    )


def _flip_boundaries(points: list[ThresholdSweepPoint]) -> list[ThresholdFlipBoundary]:
    boundaries: list[ThresholdFlipBoundary] = []
    for lower, upper in zip(points, points[1:], strict=False):
        if lower.triggered == upper.triggered:
            continue
        transition: Literal["triggered_to_not_triggered", "not_triggered_to_triggered"] = (
            "triggered_to_not_triggered" if lower.triggered else "not_triggered_to_triggered"
        )
        boundaries.append(
            ThresholdFlipBoundary(
                lower_ordinal=lower.ordinal,
                upper_ordinal=upper.ordinal,
                lower_threshold=lower.threshold,
                upper_threshold=upper.threshold,
                lower_status=lower.status,
                upper_status=upper.status,
                transition=transition,
            )
        )
    return boundaries


def _common_fields(
    evidence_pack: EvidencePack,
    request: ThresholdSweepRequest,
    config: RuleSetConfig,
    rule_id: str,
    source_section: dict[str, JsonValue],
    analysed_at: datetime,
) -> dict[str, JsonValue]:
    evidence_fingerprint = evidence_pack.fingerprint()
    normalised_request = request.model_copy(update={"rule_id": rule_id})
    analysis_basis = json.dumps(
        {
            "analysis_version": "1.0",
            "evidence_pack_fingerprint": evidence_fingerprint,
            "request": normalised_request.model_dump(mode="json"),
            "selected_rule_id": rule_id,
            "ruleset_version": config.ruleset_version,
            "source_rule_config": source_section,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    analysis_id = (
        f"threshold-sweep-{hashlib.sha256(analysis_basis.encode('utf-8')).hexdigest()[:12]}"
    )
    return {
        "analysis_id": analysis_id,
        "request": normalised_request,
        "rule_id": rule_id,
        "ruleset_version": config.ruleset_version,
        "inclusive_boundary": True,
        "provisional_default": True,
        "source_rule_config": source_section,
        "requested_point_count": request.point_count,
        "evidence_pack_id": evidence_pack.pack_id,
        "evidence_pack_fingerprint": evidence_fingerprint,
        "source_bundle_fingerprint": evidence_pack.source_bundle_fingerprint,
        "synthetic": evidence_pack.synthetic,
        "analysed_at": analysed_at,
        "provenance": {
            "source_evidence_fingerprint": evidence_fingerprint,
            "source_bundle_fingerprint": evidence_pack.source_bundle_fingerprint,
            "metric_version": evidence_pack.metric_collection.metric_version,
            "grid_method": "inclusive_linear_v1",
            "grid_precision_decimal_places": GRID_PRECISION_DECIMAL_PLACES,
        },
        "limitations": _limitations(),
    }


def _source_section(config: RuleSetConfig, rule_id: str) -> dict[str, JsonValue]:
    if rule_id not in CORE_RULE_IDS:
        return {}
    return cast(dict[str, JsonValue], getattr(config, rule_id.lower()).model_dump(mode="json"))


def _evaluate_selected(
    evidence_pack: EvidencePack,
    config: RuleSetConfig,
    rule_id: str,
    evaluated_at: datetime,
) -> RuleResult:
    payload = config.model_dump(mode="json")
    for candidate in CORE_RULE_IDS:
        payload[candidate.lower()]["enabled"] = candidate == rule_id
    isolated = RuleSetConfig.model_validate(payload)
    report = evaluate_rules(evidence_pack, isolated, clock=lambda: evaluated_at)
    if len(report.results) != 1 or report.results[0].rule_id != rule_id:
        raise RuntimeError(f"isolated threshold-sweep evaluation failed for {rule_id}")
    return report.results[0]


def _rule_result_fingerprint(result: RuleResult) -> str:
    payload = result.model_dump(mode="json")
    payload["evaluated_at"] = "<normalised>"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _limitations() -> list[str]:
    return [
        "Threshold sweeps are descriptive sensitivity, not threshold calibration or a "
        "recommendation.",
        "v1.0 sweeps only one contracted continuous severity boundary for R5, R7, or R8.",
        "Discrete evidence-support and selected-dimension settings remain fixed at every point.",
        "A sampled transition interval is not an exact boundary; DIA-05 supplies exact "
        "verification when admissible.",
        "The service does not persist configuration, establish significance, optimise outcomes, "
        "prove causality, or validate provisional defaults externally.",
    ]
