"""R7 operational outcome-disparity rule compiled from the closed YAML grammar."""

from __future__ import annotations

from datetime import datetime
from textwrap import dedent

from traffictwin.domain.fairness import DEFAULT_OPERATIONAL_FAIRNESS_POLICY
from traffictwin.domain.spatial import DEFAULT_TASK_RSU_TARGET_CONTRACT
from traffictwin.evidence.pack import EvidencePack
from traffictwin.rules.base import DiagnosticRule
from traffictwin.rules.config import R7Config, RuleSetConfig
from traffictwin.rules.declarative import (
    DeclarativeDiagnosticRule,
    DeclarativeRuleDefinition,
    NumericPredicateDefinition,
    parse_declarative_rule_yaml,
)
from traffictwin.rules.models import RuleResult

VEHICLE_TIER_DIMENSION = "vehicle_tier_completion"
TARGET_RSU_DIMENSION = "target_rsu_completion"


class R7FairnessRule(DiagnosticRule):
    """Evaluate one explicitly selected operational disparity dimension."""

    rule_id = "R7"
    rule_version = "1.0"
    title = "Operational outcome-disparity candidate"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Compile the selected built-in definition and evaluate it over EvidencePack."""

        definition = r7_rule_definition(config.r7)
        result = DeclarativeDiagnosticRule(definition).evaluate_definition(
            evidence_pack,
            evaluated_at,
        )
        return result.model_copy(
            update={
                "metadata": {
                    **result.metadata,
                    "r7_dimension": config.r7.dimension,
                    "r7_minimum_outcome_gap": config.r7.minimum_outcome_gap,
                    "r7_minimum_group_support": config.r7.minimum_group_support,
                }
            },
            deep=True,
        )


def r7_rule_definition(config: R7Config | None = None) -> DeclarativeRuleDefinition:
    """Return the fingerprinted built-in R7 definition for one explicit dimension."""

    resolved = config or R7Config()
    template = (
        _vehicle_tier_yaml() if resolved.dimension == VEHICLE_TIER_DIMENSION else _target_rsu_yaml()
    )
    definition = parse_declarative_rule_yaml(template, allow_reserved_core_id=True)
    predicate = definition.predicates[0]
    if not isinstance(predicate, NumericPredicateDefinition):  # pragma: no cover - static guard
        raise TypeError("built-in R7 definition must contain one numeric predicate")
    configured_predicate = predicate.model_copy(
        update={
            "threshold": resolved.minimum_outcome_gap,
            "minimum_group_support": resolved.minimum_group_support,
        }
    )
    return definition.model_copy(update={"predicates": [configured_predicate]})


def _vehicle_tier_yaml() -> str:
    policy_fingerprint = DEFAULT_OPERATIONAL_FAIRNESS_POLICY.fingerprint()
    return dedent(
        f"""
        schema_version: "1.0"
        grammar_version: "1.0"
        rule_id: R7
        rule_version: "1.0"
        title: Operational outcome-disparity candidate
        purpose: Detect supported completion-rate disparity across stable operational vehicle tiers.
        condition: all
        predicates:
          - kind: numeric_threshold
            predicate_id: R7_TIER_GAP
            metric_key: fairness.vehicle_tier.completion_rate.max_gap
            reducer: scalar
            operator: gte
            threshold: 0.20
            expected_unit: ratio
            required_metadata:
              - key: fairness_policy_version
                expected: "1.0"
              - key: fairness_policy_fingerprint
                expected: "{policy_fingerprint}"
              - key: group_dimension
                expected: vehicle_tier
              - key: coverage_fraction
                expected: 1.0
              - key: attribute_interpretation
                expected: operational_groups_only_not_protected_attributes
            minimum_group_count: 2
            group_count_metadata_key: group_count
            minimum_group_support: 2
            group_support_metadata_key: group_support_counts
            statement: >-
              The admitted vehicle-tier completion-rate gap is compared with the configured
              operational-disparity threshold.
        triggered_hypothesis: >-
          Supported completion outcomes differ across the selected operational vehicle-tier
          groups.
        alternative_explanations:
          - different task mixes or arrival conditions across operational tiers
          - finite synthetic or imported sample variation
          - policy behavior interacting with supplied resource tiers
          - uniformly poor or good completion can coexist with the reported disparity
        recommendations:
          - action: compare group outcomes across matched common-seed repetitions
            rationale: replication can test whether the operational disparity is stable
            expected_direction: group gaps and their variability become measurable
            prerequisite: compatible fairness policy, group coverage, and matched run provenance
            verification_step: >-
              recompute the same group metrics and R7 under the predeclared threshold
        limitations:
          - >-
            Vehicle tier is an operational resource category, not a protected or demographic
            attribute.
          - >-
            The threshold is a provisional synthetic-development value, not an external fairness
            standard.
          - >-
            R7 does not prove discrimination, causality, statistical significance, or acceptable
            overall performance.
        """
    ).strip()


def _target_rsu_yaml() -> str:
    contract_fingerprint = DEFAULT_TASK_RSU_TARGET_CONTRACT.fingerprint()
    return dedent(
        f"""
        schema_version: "1.0"
        grammar_version: "1.0"
        rule_id: R7
        rule_version: "1.0"
        title: Operational outcome-disparity candidate
        purpose: Detect supported completion-rate disparity across exact execution-target RSUs.
        condition: all
        predicates:
          - kind: numeric_threshold
            predicate_id: R7_TARGET_RSU_GAP
            metric_key: spatial.rsu.task.completion_rate_by_target
            reducer: mapping_max_gap
            operator: gte
            threshold: 0.20
            expected_unit: ratio
            required_metadata:
              - key: task_rsu_target_contract_version
                expected: "1.0"
              - key: task_rsu_target_contract_fingerprint
                expected: "{contract_fingerprint}"
              - key: target_semantics
                expected: executing_rsu_id
              - key: target_join_method
                expected: exact_task_target_id_to_infrastructure_rsu_id
              - key: coverage_fraction
                expected: 1.0
              - key: attribution_interpretation
                expected: observed_execution_target_not_causal_assignment
            minimum_group_count: 2
            group_count_metadata_key: group_count
            minimum_group_support: 2
            group_support_metadata_key: group_support_counts
            statement: >-
              The admitted exact-target RSU completion-rate range is compared with the configured
              operational-disparity threshold.
        triggered_hypothesis: >-
          Supported completion outcomes differ across the selected exact execution-target RSU
          groups.
        alternative_explanations:
          - different task mixes or arrival conditions at observed targets
          - different target capacities, workload, or routing constraints
          - finite synthetic or imported sample variation
          - target grouping records lineage and does not identify an RSU as the cause
        recommendations:
          - action: compare exact-target group outcomes across matched common-seed repetitions
            rationale: replication can test whether the operational target disparity is stable
            expected_direction: group gaps and their variability become measurable
            prerequisite: >-
              compatible exact-target contract, complete joins, and matched run provenance
            verification_step: >-
              recompute the same target metrics and R7 under the predeclared threshold
        limitations:
          - >-
            Target RSU is an operational execution group, not a protected attribute or geographic
            causal assignment.
          - >-
            The threshold is a provisional synthetic-development value, not an external fairness
            standard.
          - >-
            R7 does not prove siting or routing cause, statistical significance, or acceptable
            overall performance.
        """
    ).strip()
