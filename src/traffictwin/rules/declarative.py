"""Closed trusted-local YAML grammar for deterministic EvidencePack rules."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, TypeAlias

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, Node

from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import JsonScalar, MetricStatus, MetricValue
from traffictwin.rules.base import DiagnosticRule
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.models import (
    ConfidenceCategory,
    Finding,
    FindingSupport,
    Recommendation,
    RuleResult,
    RuleStatus,
    result_from_findings,
)

DECLARATIVE_RULE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
DECLARATIVE_GRAMMAR_VERSION: Literal["1.0"] = "1.0"
MAX_RULE_YAML_BYTES = 65_536
MAX_RULE_PREDICATES = 16
MAX_METADATA_REQUIREMENTS = 8
RESERVED_CORE_RULE_IDS = frozenset(f"R{index}" for index in range(9))

_RULE_ID_PATTERN = r"^[A-Z][A-Z0-9_]{1,31}$"
_LOCAL_RULE_ID_PATTERN = r"^LOCAL_[A-Z0-9_]{1,25}$"
_SAFE_KEY_PATTERN = r"^[A-Za-z0-9_.:-]{1,160}$"
_VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$"


class DeclarativeRuleError(ValueError):
    """Raised when a declarative rule cannot be safely admitted or evaluated."""


class RuleConditionMode(StrEnum):
    """Supported flat boolean combination modes."""

    ALL = "all"
    ANY = "any"


class NumericOperator(StrEnum):
    """Supported finite numeric comparison operators."""

    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"


class NumericReducer(StrEnum):
    """Supported ways to obtain one numeric value from a metric."""

    SCALAR = "scalar"
    MAPPING_MAX_GAP = "mapping_max_gap"


class PredicateTruth(StrEnum):
    """Three-valued result of one admitted predicate."""

    TRUE = "true"
    FALSE = "false"
    UNAVAILABLE = "unavailable"


class DeclarativeModel(BaseModel):
    """Strict immutable base for declarative-rule artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class MetadataRequirement(DeclarativeModel):
    """One exact scalar metric-metadata requirement."""

    key: str = Field(pattern=_SAFE_KEY_PATTERN)
    expected: JsonScalar

    @field_validator("expected")
    @classmethod
    def validate_finite_expected(cls, value: JsonScalar) -> JsonScalar:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("metadata expectations must be finite")
        return value


class NumericPredicateDefinition(DeclarativeModel):
    """Finite numeric threshold predicate over a scalar or grouped metric."""

    kind: Literal["numeric_threshold"] = "numeric_threshold"
    predicate_id: str = Field(pattern=_SAFE_KEY_PATTERN)
    metric_key: str = Field(pattern=_SAFE_KEY_PATTERN)
    reducer: NumericReducer = NumericReducer.SCALAR
    operator: NumericOperator
    threshold: float = Field(strict=True, allow_inf_nan=False)
    expected_unit: str = Field(min_length=1, max_length=64)
    required_metadata: list[MetadataRequirement] = Field(
        default_factory=list,
        max_length=MAX_METADATA_REQUIREMENTS,
    )
    minimum_group_count: int | None = Field(default=None, strict=True, ge=2, le=1_000)
    group_count_metadata_key: str | None = Field(default=None, pattern=_SAFE_KEY_PATTERN)
    minimum_group_support: int | None = Field(
        default=None,
        strict=True,
        ge=1,
        le=1_000_000,
    )
    group_support_metadata_key: str | None = Field(default=None, pattern=_SAFE_KEY_PATTERN)
    statement: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_group_requirements(self) -> NumericPredicateDefinition:
        if (self.minimum_group_count is None) != (self.group_count_metadata_key is None):
            raise ValueError(
                "minimum_group_count and group_count_metadata_key must be supplied together"
            )
        if (self.minimum_group_support is None) != (self.group_support_metadata_key is None):
            raise ValueError(
                "minimum_group_support and group_support_metadata_key must be supplied together"
            )
        if self.reducer is NumericReducer.MAPPING_MAX_GAP and self.minimum_group_count is None:
            raise ValueError("mapping_max_gap requires an explicit minimum_group_count")
        return self


class BooleanPredicateDefinition(DeclarativeModel):
    """Exact boolean predicate over an already-computed scalar metric."""

    kind: Literal["boolean_equals"] = "boolean_equals"
    predicate_id: str = Field(pattern=_SAFE_KEY_PATTERN)
    metric_key: str = Field(pattern=_SAFE_KEY_PATTERN)
    expected: bool = Field(strict=True)
    expected_unit: str = Field(min_length=1, max_length=64)
    required_metadata: list[MetadataRequirement] = Field(
        default_factory=list,
        max_length=MAX_METADATA_REQUIREMENTS,
    )
    statement: str = Field(min_length=1, max_length=300)


DeclarativePredicate: TypeAlias = Annotated[
    NumericPredicateDefinition | BooleanPredicateDefinition,
    Field(discriminator="kind"),
]


class DeclarativeRecommendation(DeclarativeModel):
    """Bounded non-executable follow-up text for a declarative result."""

    action: str = Field(min_length=1, max_length=240)
    rationale: str = Field(min_length=1, max_length=360)
    expected_direction: str = Field(min_length=1, max_length=240)
    prerequisite: str = Field(min_length=1, max_length=240)
    verification_step: str = Field(min_length=1, max_length=300)
    conditional: Literal[True] = True


class DeclarativeRuleDefinition(DeclarativeModel):
    """Versioned closed definition compiled into one ordinary diagnostic rule."""

    schema_version: Literal["1.0"] = DECLARATIVE_RULE_SCHEMA_VERSION
    grammar_version: Literal["1.0"] = DECLARATIVE_GRAMMAR_VERSION
    rule_id: str = Field(pattern=_RULE_ID_PATTERN)
    rule_version: str = Field(pattern=_VERSION_PATTERN)
    title: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1, max_length=400)
    condition: RuleConditionMode
    predicates: list[DeclarativePredicate] = Field(
        min_length=1,
        max_length=MAX_RULE_PREDICATES,
    )
    triggered_hypothesis: str = Field(min_length=1, max_length=600)
    alternative_explanations: list[str] = Field(default_factory=list, max_length=8)
    recommendations: list[DeclarativeRecommendation] = Field(default_factory=list, max_length=4)
    limitations: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_unique_predicates(self) -> DeclarativeRuleDefinition:
        predicate_ids = [item.predicate_id for item in self.predicates]
        if len(predicate_ids) != len(set(predicate_ids)):
            raise ValueError("declarative predicate identifiers must be unique")
        for values, label, maximum in (
            (self.alternative_explanations, "alternative explanation", 360),
            (self.limitations, "limitation", 360),
        ):
            if any(not value or len(value) > maximum for value in values):
                raise ValueError(f"each declarative {label} must contain 1-{maximum} characters")
        return self

    def canonical_json(self) -> str:
        """Return stable canonical JSON for this complete definition."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Return the stable identity of the complete rule definition."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class PredicateEvaluation(DeclarativeModel):
    """Typed evaluation of one predicate without hidden coercion."""

    predicate_id: str
    metric_key: str
    truth: PredicateTruth
    observed_value: JsonScalar = None
    expected_condition: str
    reason: str | None = None
    group_count: int | None = None
    minimum_group_support_observed: int | None = None


class DeclarativeRuleRegistryReport(DeclarativeModel):
    """Stable inventory of explicitly registered local rule definitions."""

    schema_version: Literal["1.0"] = "1.0"
    definitions: list[DeclarativeRuleDefinition]
    registry_fingerprint: str


class DeclarativeRuleContract(DeclarativeModel):
    """Machine-readable public boundary of the DIA-04 grammar."""

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["DIA-04"] = "DIA-04"
    grammar_version: Literal["1.0"] = DECLARATIVE_GRAMMAR_VERSION
    trust_boundary: Literal["trusted_local_static_yaml_not_a_sandbox"] = (
        "trusted_local_static_yaml_not_a_sandbox"
    )
    evidence_boundary: Literal["EvidencePack.metric_collection"] = "EvidencePack.metric_collection"
    maximum_yaml_bytes: int = MAX_RULE_YAML_BYTES
    maximum_predicates: int = MAX_RULE_PREDICATES
    condition_modes: list[str]
    numeric_operators: list[str]
    numeric_reducers: list[str]
    boolean_operators: list[str]
    custom_rule_id_pattern: str = _LOCAL_RULE_ID_PATTERN
    rejected_yaml_features: list[str]
    excluded_language_features: list[str]
    reference_rule_id: Literal["R7"] = "R7"


class _ClosedRuleLoader(yaml.SafeLoader):
    """SafeLoader that rejects anchors, aliases, and duplicate mapping keys."""

    def compose_node(self, parent: Node | None, index: int) -> Node:
        event = self.peek_event()  # type: ignore[no-untyped-call]
        tag = getattr(event, "tag", None)
        if tag is not None and not str(tag).startswith("tag:yaml.org,2002:"):
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "YAML custom tags are not supported by the declarative rule grammar",
                event.start_mark,
            )
        if isinstance(event, AliasEvent) or getattr(event, "anchor", None) is not None:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "YAML anchors and aliases are not supported by the declarative rule grammar",
                event.start_mark,
            )
        node = super().compose_node(parent, index)
        if node is None:  # pragma: no cover - guarded by PyYAML's composer
            raise DeclarativeRuleError("YAML composer returned no node")
        return node

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[object, object]:
        keys: list[object] = []
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if any(key == existing for existing in keys):
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"duplicate key {key!r} is not supported",
                    key_node.start_mark,
                )
            keys.append(key)
        return super().construct_mapping(node, deep=deep)


def declarative_rule_contract() -> DeclarativeRuleContract:
    """Return the static versioned DIA-04 grammar contract."""

    return DeclarativeRuleContract(
        condition_modes=[item.value for item in RuleConditionMode],
        numeric_operators=[item.value for item in NumericOperator],
        numeric_reducers=[item.value for item in NumericReducer],
        boolean_operators=["equals"],
        rejected_yaml_features=[
            "custom tags",
            "anchors and aliases",
            "duplicate keys",
            "multiple documents",
            "documents larger than the published byte bound",
        ],
        excluded_language_features=[
            "imports",
            "function calls",
            "eval or exec",
            "templates",
            "nested rule references",
            "arbitrary expressions or reducers",
            "dynamic metric-key construction",
        ],
    )


def parse_declarative_rule_yaml(
    text: str,
    *,
    allow_reserved_core_id: bool = False,
) -> DeclarativeRuleDefinition:
    """Parse one bounded safe YAML document into a strict rule definition."""

    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise DeclarativeRuleError("declarative rule YAML must be valid UTF-8") from exc
    if len(encoded) > MAX_RULE_YAML_BYTES:
        raise DeclarativeRuleError(f"declarative rule YAML exceeds {MAX_RULE_YAML_BYTES} bytes")
    try:
        payload = yaml.load(text, Loader=_ClosedRuleLoader)  # noqa: S506 - closed SafeLoader.
    except yaml.YAMLError as exc:
        raise DeclarativeRuleError(f"invalid declarative rule YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise DeclarativeRuleError("declarative rule YAML must contain one mapping document")
    try:
        definition = DeclarativeRuleDefinition.model_validate(payload)
    except ValueError as exc:
        raise DeclarativeRuleError(f"invalid declarative rule definition: {exc}") from exc
    _validate_rule_identifier(definition.rule_id, allow_reserved_core_id)
    return definition


def load_declarative_rule(
    path: str | Path,
    *,
    allow_reserved_core_id: bool = False,
) -> DeclarativeRuleDefinition:
    """Read and parse one trusted local rule file under the same byte bound."""

    source = Path(path)
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise DeclarativeRuleError(f"could not read declarative rule: {exc}") from exc
    if len(payload) > MAX_RULE_YAML_BYTES:
        raise DeclarativeRuleError(f"declarative rule YAML exceeds {MAX_RULE_YAML_BYTES} bytes")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DeclarativeRuleError("declarative rule YAML must be UTF-8") from exc
    return parse_declarative_rule_yaml(
        text,
        allow_reserved_core_id=allow_reserved_core_id,
    )


def compile_declarative_rule(
    definition: DeclarativeRuleDefinition,
    *,
    allow_reserved_core_id: bool = False,
) -> DeclarativeDiagnosticRule:
    """Compile one validated definition into an ordinary deterministic rule."""

    _validate_rule_identifier(definition.rule_id, allow_reserved_core_id)
    return DeclarativeDiagnosticRule(definition)


def evaluate_declarative_rule(
    definition: DeclarativeRuleDefinition,
    evidence_pack: EvidencePack,
    *,
    evaluated_at: datetime | None = None,
    allow_reserved_core_id: bool = False,
) -> RuleResult:
    """Evaluate one validated definition against the EvidencePack boundary."""

    rule = compile_declarative_rule(
        definition,
        allow_reserved_core_id=allow_reserved_core_id,
    )
    return rule.evaluate_definition(evidence_pack, evaluated_at or datetime.now(UTC))


class DeclarativeDiagnosticRule(DiagnosticRule):
    """Compiled rule implementation over a closed declarative definition."""

    def __init__(self, definition: DeclarativeRuleDefinition) -> None:
        self.definition = definition
        self.rule_id = definition.rule_id
        self.rule_version = definition.rule_version
        self.title = definition.title

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate through the ordinary DiagnosticRule interface."""

        del config
        return self.evaluate_definition(evidence_pack, evaluated_at)

    def evaluate_definition(
        self,
        evidence_pack: EvidencePack,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate all predicates and produce an ordinary RuleResult."""

        metrics = evidence_pack.metric_collection.by_key()
        evaluations = [
            _evaluate_predicate(item, metrics.get(item.metric_key))
            for item in self.definition.predicates
        ]
        status = _combined_status(self.definition.condition, evaluations)
        findings = [
            _finding(index, predicate, evaluation, metrics)
            for index, (predicate, evaluation) in enumerate(
                zip(self.definition.predicates, evaluations, strict=True),
                start=1,
            )
        ]
        missing = sorted(
            {
                f"{evaluation.metric_key}: {evaluation.reason}"
                for evaluation in evaluations
                if evaluation.truth is PredicateTruth.UNAVAILABLE and evaluation.reason is not None
            }
        )
        unavailable_count = sum(item.truth is PredicateTruth.UNAVAILABLE for item in evaluations)
        true_count = sum(item.truth is PredicateTruth.TRUE for item in evaluations)
        false_count = sum(item.truth is PredicateTruth.FALSE for item in evaluations)
        confidence = (
            ConfidenceCategory.LOW
            if status is RuleStatus.TRIGGERED and unavailable_count
            else (
                ConfidenceCategory.MODERATE
                if status is RuleStatus.TRIGGERED
                else ConfidenceCategory.UNAVAILABLE
            )
        )
        return result_from_findings(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            title=self.title,
            status=status,
            synthetic=evidence_pack.synthetic,
            evaluated_at=evaluated_at,
            hypothesis=(
                self.definition.triggered_hypothesis if status is RuleStatus.TRIGGERED else None
            ),
            findings=findings,
            missing_evidence=missing,
            alternative_explanations=(
                self.definition.alternative_explanations if status is RuleStatus.TRIGGERED else []
            ),
            recommendations=[
                Recommendation(**item.model_dump()) for item in self.definition.recommendations
            ],
            confidence=confidence,
            confidence_basis=[
                "categorical confidence reflects predicate completeness under the closed "
                "declarative grammar; it is not a probability"
            ],
            limitations=[
                *self.definition.limitations,
                "Declarative thresholds are deterministic configuration, not statistical or "
                "causal proof.",
            ],
            metadata={
                "declarative_definition_fingerprint": self.definition.fingerprint(),
                "declarative_schema_version": self.definition.schema_version,
                "declarative_grammar_version": self.definition.grammar_version,
                "declarative_condition": self.definition.condition.value,
                "declarative_trust_boundary": "trusted_local_static_yaml_not_a_sandbox",
                "predicate_count": len(evaluations),
                "true_predicate_count": true_count,
                "false_predicate_count": false_count,
                "unavailable_predicate_count": unavailable_count,
            },
        )


class DeclarativeRuleRegistry:
    """Explicit in-process registry for trusted local declarative definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, DeclarativeRuleDefinition] = {}

    def register(self, definition: DeclarativeRuleDefinition) -> None:
        """Register one non-core definition, rejecting duplicate identifiers."""

        _validate_rule_identifier(definition.rule_id, allow_reserved_core_id=False)
        if definition.rule_id in self._definitions:
            raise DeclarativeRuleError(
                f"duplicate declarative rule identifier: {definition.rule_id}"
            )
        self._definitions[definition.rule_id] = definition

    def definitions(self) -> list[DeclarativeRuleDefinition]:
        """Return definitions ordered by stable identifier."""

        return [self._definitions[key] for key in sorted(self._definitions)]

    def report(self) -> DeclarativeRuleRegistryReport:
        """Return a fingerprinted registry inventory."""

        definitions = self.definitions()
        canonical = json.dumps(
            [item.model_dump(mode="json") for item in definitions],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return DeclarativeRuleRegistryReport(
            definitions=definitions,
            registry_fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def evaluate_all(
        self,
        evidence_pack: EvidencePack,
        *,
        evaluated_at: datetime | None = None,
    ) -> list[RuleResult]:
        """Evaluate every registered definition in stable order."""

        timestamp = evaluated_at or datetime.now(UTC)
        return [
            DeclarativeDiagnosticRule(item).evaluate_definition(evidence_pack, timestamp)
            for item in self.definitions()
        ]


def _validate_rule_identifier(rule_id: str, allow_reserved_core_id: bool) -> None:
    if rule_id in RESERVED_CORE_RULE_IDS:
        if allow_reserved_core_id:
            return
        raise DeclarativeRuleError(f"reserved core rule identifier is not available: {rule_id}")
    if not rule_id.startswith("LOCAL_"):
        raise DeclarativeRuleError("trusted local declarative rule IDs must start with LOCAL_")


def _evaluate_predicate(
    predicate: DeclarativePredicate,
    metric: MetricValue | None,
) -> PredicateEvaluation:
    expected = _expected_condition(predicate)
    if metric is None:
        return _unavailable(predicate, expected, "metric is absent from the EvidencePack")
    if metric.status is not MetricStatus.AVAILABLE:
        return _unavailable(
            predicate,
            expected,
            f"metric status is {metric.status.value}, not available",
        )
    if metric.unit != predicate.expected_unit:
        return _unavailable(
            predicate,
            expected,
            f"metric unit {metric.unit!r} does not match {predicate.expected_unit!r}",
        )
    metadata_reason = _metadata_reason(predicate.required_metadata, metric)
    if metadata_reason is not None:
        return _unavailable(predicate, expected, metadata_reason)
    if isinstance(predicate, BooleanPredicateDefinition):
        if not isinstance(metric.value, bool):
            return _unavailable(predicate, expected, "metric value is not boolean")
        truth = PredicateTruth.TRUE if metric.value is predicate.expected else PredicateTruth.FALSE
        return PredicateEvaluation(
            predicate_id=predicate.predicate_id,
            metric_key=predicate.metric_key,
            truth=truth,
            observed_value=metric.value,
            expected_condition=expected,
        )

    observed, group_count, group_keys, reason = _numeric_observation(predicate, metric)
    if reason is not None or observed is None:
        return _unavailable(predicate, expected, reason or "numeric observation is unavailable")
    support_minimum, support_reason = _group_support(
        predicate,
        metric,
        group_count,
        group_keys,
    )
    if support_reason is not None:
        return _unavailable(predicate, expected, support_reason)
    comparison = _NUMERIC_OPERATORS[predicate.operator](observed, predicate.threshold)
    return PredicateEvaluation(
        predicate_id=predicate.predicate_id,
        metric_key=predicate.metric_key,
        truth=PredicateTruth.TRUE if comparison else PredicateTruth.FALSE,
        observed_value=observed,
        expected_condition=expected,
        group_count=group_count,
        minimum_group_support_observed=support_minimum,
    )


def _numeric_observation(
    predicate: NumericPredicateDefinition,
    metric: MetricValue,
) -> tuple[float | None, int | None, tuple[str, ...] | None, str | None]:
    if predicate.reducer is NumericReducer.SCALAR:
        number = _finite_number(metric.value)
        if number is None:
            return None, None, None, "metric value is not a finite numeric scalar"
        return number, _metadata_group_count(predicate, metric), None, None
    if not isinstance(metric.value, dict):
        return None, None, None, "mapping_max_gap requires a mapping metric"
    values: list[float] = []
    group_keys: list[str] = []
    for key, raw in sorted(metric.value.items()):
        if not isinstance(key, str):
            return None, None, None, "mapping metric contains a non-string group key"
        number = _finite_number(raw)
        if number is None:
            return None, None, None, f"mapping group {key!r} is null or non-numeric"
        group_keys.append(key)
        values.append(number)
    group_count = len(values)
    if predicate.minimum_group_count is not None and group_count < predicate.minimum_group_count:
        return (
            None,
            group_count,
            tuple(group_keys),
            f"mapping has {group_count} groups; requires {predicate.minimum_group_count}",
        )
    if not values:
        return None, group_count, tuple(group_keys), "mapping contains no groups"
    metadata_count = _metadata_group_count(predicate, metric)
    if metadata_count is not None and metadata_count != group_count:
        return (
            None,
            group_count,
            tuple(group_keys),
            "mapping group count conflicts with metric metadata",
        )
    return round(max(values) - min(values), 12), group_count, tuple(group_keys), None


def _metadata_group_count(
    predicate: NumericPredicateDefinition,
    metric: MetricValue,
) -> int | None:
    if predicate.group_count_metadata_key is None:
        return None
    value = metric.metadata.get(predicate.group_count_metadata_key)
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value


def _group_support(
    predicate: NumericPredicateDefinition,
    metric: MetricValue,
    observed_group_count: int | None,
    observed_group_keys: tuple[str, ...] | None,
) -> tuple[int | None, str | None]:
    if predicate.minimum_group_count is not None:
        group_count = _metadata_group_count(predicate, metric)
        if group_count is None:
            return None, "required group-count metadata is absent or invalid"
        if group_count < predicate.minimum_group_count:
            return (
                None,
                f"group count {group_count} is below {predicate.minimum_group_count}",
            )
        if observed_group_count is not None and group_count != observed_group_count:
            return None, "group-count metadata does not match observed mapping groups"
    if predicate.minimum_group_support is None:
        return None, None
    assert predicate.group_support_metadata_key is not None
    support = metric.metadata.get(predicate.group_support_metadata_key)
    if not isinstance(support, dict) or not support:
        return None, "required group-support metadata is absent or invalid"
    counts: list[int] = []
    for key, value in sorted(support.items()):
        if not isinstance(key, str) or not isinstance(value, int) or isinstance(value, bool):
            return None, "group-support metadata contains an invalid entry"
        counts.append(value)
    if observed_group_count is not None and len(counts) != observed_group_count:
        return None, "group-support metadata does not match observed mapping groups"
    if observed_group_keys is not None and tuple(sorted(support)) != observed_group_keys:
        return None, "group-support metadata keys do not match observed mapping groups"
    minimum = min(counts)
    if minimum < predicate.minimum_group_support:
        return (
            minimum,
            f"minimum group support {minimum} is below {predicate.minimum_group_support}",
        )
    return minimum, None


def _metadata_reason(
    requirements: list[MetadataRequirement],
    metric: MetricValue,
) -> str | None:
    for requirement in requirements:
        if requirement.key not in metric.metadata:
            return f"required metadata {requirement.key!r} is absent"
        observed = metric.metadata[requirement.key]
        if not _same_scalar(observed, requirement.expected):
            return f"required metadata {requirement.key!r} is incompatible"
    return None


def _same_scalar(observed: object, expected: JsonScalar) -> bool:
    if isinstance(observed, bool) or isinstance(expected, bool):
        return isinstance(observed, bool) and isinstance(expected, bool) and observed is expected
    if isinstance(observed, int | float) and isinstance(expected, int | float):
        return math.isfinite(float(observed)) and float(observed) == float(expected)
    return type(observed) is type(expected) and observed == expected


def _finite_number(value: object) -> float | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


_NUMERIC_OPERATORS: dict[NumericOperator, Callable[[float, float], bool]] = {
    NumericOperator.LT: lambda observed, threshold: observed < threshold,
    NumericOperator.LTE: lambda observed, threshold: observed <= threshold,
    NumericOperator.GT: lambda observed, threshold: observed > threshold,
    NumericOperator.GTE: lambda observed, threshold: observed >= threshold,
}


def _unavailable(
    predicate: DeclarativePredicate,
    expected: str,
    reason: str,
) -> PredicateEvaluation:
    return PredicateEvaluation(
        predicate_id=predicate.predicate_id,
        metric_key=predicate.metric_key,
        truth=PredicateTruth.UNAVAILABLE,
        expected_condition=expected,
        reason=reason,
    )


def _expected_condition(predicate: DeclarativePredicate) -> str:
    if isinstance(predicate, BooleanPredicateDefinition):
        return f"{predicate.metric_key} equals {str(predicate.expected).lower()}"
    reducer = (
        "value"
        if predicate.reducer is NumericReducer.SCALAR
        else "maximum group value minus minimum group value"
    )
    symbol = {
        NumericOperator.LT: "<",
        NumericOperator.LTE: "<=",
        NumericOperator.GT: ">",
        NumericOperator.GTE: ">=",
    }[predicate.operator]
    return (
        f"{predicate.metric_key} {reducer} {symbol} {predicate.threshold} {predicate.expected_unit}"
    )


def _combined_status(
    mode: RuleConditionMode,
    evaluations: list[PredicateEvaluation],
) -> RuleStatus:
    truths = [item.truth for item in evaluations]
    if mode is RuleConditionMode.ALL:
        if PredicateTruth.FALSE in truths:
            return RuleStatus.NOT_TRIGGERED
        if all(item is PredicateTruth.TRUE for item in truths):
            return RuleStatus.TRIGGERED
        return RuleStatus.INSUFFICIENT_EVIDENCE
    if PredicateTruth.TRUE in truths:
        return RuleStatus.TRIGGERED
    if all(item is PredicateTruth.FALSE for item in truths):
        return RuleStatus.NOT_TRIGGERED
    return RuleStatus.INSUFFICIENT_EVIDENCE


def _finding(
    index: int,
    predicate: DeclarativePredicate,
    evaluation: PredicateEvaluation,
    metrics: dict[str, MetricValue],
) -> Finding:
    support = {
        PredicateTruth.TRUE: FindingSupport.SUPPORTS,
        PredicateTruth.FALSE: FindingSupport.CONTRADICTS,
        PredicateTruth.UNAVAILABLE: FindingSupport.NEUTRAL,
    }[evaluation.truth]
    observed_values: dict[str, JsonScalar] = {
        "predicate_truth": evaluation.truth.value,
        "observed_value": evaluation.observed_value,
        "reason": evaluation.reason,
        "group_count": evaluation.group_count,
        "minimum_group_support_observed": evaluation.minimum_group_support_observed,
    }
    return Finding(
        finding_id=f"{predicate.predicate_id}-F{index}",
        statement=predicate.statement,
        evidence_keys=[predicate.metric_key] if predicate.metric_key in metrics else [],
        observed_values=observed_values,
        expected_condition=evaluation.expected_condition,
        support=support,
    )
