"""Deterministic DIA-07 relationships over retained diagnostic rule results."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.metrics.results import JsonScalar
from traffictwin.rules.models import RuleResult, RuleStatus

POLICY_VERSION = "1.0"


class CrossRuleRelationType(StrEnum):
    """Closed relationship types admitted by the DIA-07 v1 policy."""

    CONFLICT = "conflict"
    CORROBORATION = "corroboration"
    SUPPRESSION = "suppression"


class CrossRuleOverlapBasis(StrEnum):
    """How a relationship establishes its evidence connection."""

    EXACT_SHARED_EVIDENCE = "exact_shared_evidence"
    EXPLICIT_BLOCKED_RULE = "explicit_blocked_rule"


class CrossRuleTargetSelector(StrEnum):
    """Closed mechanism used to select the target rule."""

    FIXED_RULE_ID = "fixed_rule_id"
    SOURCE_METADATA_BLOCKED_RULES = "source_metadata_blocked_rules"


class CrossRuleReasoningStatus(StrEnum):
    """Whether the complete policy pass emitted any relationships."""

    RELATIONSHIPS_RECORDED = "relationships_recorded"
    NO_RELATIONSHIPS = "no_relationships"


class CrossRulePolicy(BaseModel):
    """One static, versioned relationship activation policy."""

    model_config = ConfigDict(extra="forbid")

    policy_id: str
    policy_version: str = POLICY_VERSION
    relation_type: CrossRuleRelationType
    source_rule_id: str
    target_rule_id: str | None
    target_selector: CrossRuleTargetSelector
    source_statuses: list[RuleStatus]
    target_statuses: list[RuleStatus]
    overlap_basis: CrossRuleOverlapBasis
    required_shared_evidence_keys: list[str] = Field(default_factory=list)
    source_precedence: int = Field(ge=0)
    target_precedence: int = Field(ge=0)
    symmetric: bool
    statement: str
    presentation_effect: str
    limitations: list[str] = Field(default_factory=list)


class CrossRuleRelationship(BaseModel):
    """One activated policy relationship without rewriting either input result."""

    model_config = ConfigDict(extra="forbid")

    relationship_id: str
    policy_id: str
    policy_version: str
    relation_type: CrossRuleRelationType
    source_rule_id: str
    target_rule_id: str
    source_status: RuleStatus
    target_status: RuleStatus
    overlap_basis: CrossRuleOverlapBasis
    shared_evidence_keys: list[str] = Field(default_factory=list)
    source_only_evidence_keys: list[str] = Field(default_factory=list)
    target_only_evidence_keys: list[str] = Field(default_factory=list)
    source_precedence: int = Field(ge=0)
    target_precedence: int = Field(ge=0)
    symmetric: bool
    statement: str
    activation_reason: str
    presentation_effect: str
    original_result_fingerprints: dict[str, str]
    synthetic: bool
    limitations: list[str] = Field(default_factory=list)


class CrossRuleReasoningReport(BaseModel):
    """Complete additive DIA-07 relationship record for one DiagnosticReport."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    analysis_id: str
    generated_at: datetime
    source_diagnostic_report_id: str
    evidence_pack_id: str
    ruleset_version: str
    policy_version: str = POLICY_VERSION
    status: CrossRuleReasoningStatus
    relationships: list[CrossRuleRelationship] = Field(default_factory=list)
    counts_by_type: dict[str, int]
    retained_rule_ids: list[str]
    original_result_fingerprints: dict[str, str]
    suppressed_rule_ids: list[str] = Field(default_factory=list)
    unclassified_triggered_rule_ids: list[str] = Field(default_factory=list)
    unresolved_blocked_rule_ids: list[str] = Field(default_factory=list)
    synthetic: bool
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return formatted JSON without non-standard numeric values."""

        return json.dumps(
            self.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )

    def canonical_json(self) -> str:
        """Return canonical JSON with the generated timestamp normalised."""

        data = self.model_dump(mode="json")
        data["generated_at"] = "<normalised>"
        return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        """Return a deterministic analysis fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class CrossRuleReasoningContract(BaseModel):
    """Published boundary and policies for DIA-07 v1."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    policy_version: str = POLICY_VERSION
    evidence_boundary: str
    policies: list[CrossRulePolicy]
    precedence_tiers: dict[str, int]
    retention_guarantee: str
    confidence_semantics: str
    undeclared_pair_semantics: str
    supported_rule_ids: list[str]
    limitations: list[str]

    def fingerprint(self) -> str:
        """Return a deterministic policy-contract fingerprint."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cross_rule_reasoning_contract() -> CrossRuleReasoningContract:
    """Return the complete static DIA-07 v1 policy contract."""

    return CrossRuleReasoningContract(
        evidence_boundary=(
            "The service consumes completed RuleResult objects only. It does not read raw files, "
            "recompute metrics, or change rule statuses."
        ),
        policies=_policies(),
        precedence_tiers={"data_readiness": 100, "ordinary_diagnostic": 50},
        retention_guarantee=(
            "Every input RuleResult remains in DiagnosticReport.results. Suppression changes only "
            "presentation/actionability metadata and never deletes, rewrites, or changes a status."
        ),
        confidence_semantics=(
            "Relationships do not calculate probability, strength, rank, or confidence and do not "
            "change a RuleResult confidence category."
        ),
        undeclared_pair_semantics=(
            "No relationship is inferred for an undeclared pair, including R3 and R5-R8 or "
            "arbitrary declarative rules."
        ),
        supported_rule_ids=["R0", "R1", "R2", "R4"],
        limitations=[
            "R1/R2 conflict records competing candidate interpretations and does not select one.",
            "R1/R4 corroboration records compatible context only and does not increase confidence.",
            "R0 suppression is activated only by its explicit blocked_rules metadata.",
            "Exact evidence-key overlap is shared lineage context, not statistical independence "
            "or causality.",
            "The v1 policy is intentionally incomplete rather than inferring uncalibrated "
            "relationships.",
        ],
    )


def evaluate_cross_rule_reasoning(
    results: list[RuleResult],
    *,
    diagnostic_report_id: str,
    evidence_pack_id: str,
    ruleset_version: str,
    source_evidence_fingerprint: str,
    synthetic: bool,
    generated_at: datetime,
) -> CrossRuleReasoningReport:
    """Evaluate the closed v1 policy over retained ordinary rule results."""

    ordered = sorted(results, key=lambda item: item.rule_id)
    by_id = {result.rule_id: result for result in ordered}
    if len(by_id) != len(ordered):
        raise ValueError("cross-rule reasoning requires unique RuleResult.rule_id values")
    if any(result.synthetic is not synthetic for result in ordered):
        raise ValueError("cross-rule reasoning requires one consistent synthetic source label")

    fingerprints = {result.rule_id: rule_result_fingerprint(result) for result in ordered}
    relationships: list[CrossRuleRelationship] = []
    policies = _policies()
    for policy in policies:
        if policy.target_selector is not CrossRuleTargetSelector.FIXED_RULE_ID:
            continue
        assert policy.target_rule_id is not None
        source = by_id.get(policy.source_rule_id)
        target = by_id.get(policy.target_rule_id)
        if source is None or target is None:
            continue
        if (
            source.status not in policy.source_statuses
            or target.status not in policy.target_statuses
        ):
            continue
        shared = sorted(set(source.evidence_keys) & set(target.evidence_keys))
        if not set(policy.required_shared_evidence_keys).issubset(shared):
            continue
        relationships.append(
            _relationship(
                policy,
                source,
                target,
                fingerprints,
                synthetic,
                shared,
                activation_reason=(
                    f"{source.rule_id} and {target.rule_id} are both triggered and share every "
                    "required exact evidence key: "
                    f"{', '.join(policy.required_shared_evidence_keys)}."
                ),
            )
        )

    unresolved: list[str] = []
    suppression = next(
        policy
        for policy in policies
        if policy.target_selector is CrossRuleTargetSelector.SOURCE_METADATA_BLOCKED_RULES
    )
    readiness = by_id.get(suppression.source_rule_id)
    if readiness is not None and readiness.status in suppression.source_statuses:
        for target_rule_id in _blocked_rule_ids(readiness):
            target = by_id.get(target_rule_id)
            if target is None or target_rule_id == readiness.rule_id:
                unresolved.append(target_rule_id)
                continue
            shared = sorted(set(readiness.evidence_keys) & set(target.evidence_keys))
            relationships.append(
                _relationship(
                    suppression,
                    readiness,
                    target,
                    fingerprints,
                    synthetic,
                    shared,
                    activation_reason=(
                        f"{readiness.rule_id} explicitly lists {target.rule_id} in blocked_rules; "
                        "the target result remains retained but is not actionable until the "
                        "readiness blocker is resolved."
                    ),
                )
            )

    relationships.sort(
        key=lambda item: (item.relation_type.value, item.source_rule_id, item.target_rule_id)
    )
    participating = {
        rule_id
        for relationship in relationships
        for rule_id in (relationship.source_rule_id, relationship.target_rule_id)
    }
    triggered = {result.rule_id for result in ordered if result.status is RuleStatus.TRIGGERED}
    suppressed = sorted(
        {
            relationship.target_rule_id
            for relationship in relationships
            if relationship.relation_type is CrossRuleRelationType.SUPPRESSION
        }
    )
    contract = cross_rule_reasoning_contract()
    sequence_fingerprint = _fingerprint_payload(fingerprints)
    analysis_id = (
        "cross-rule-"
        + _fingerprint_payload(
            {
                "evidence_pack_id": evidence_pack_id,
                "ruleset_version": ruleset_version,
                "policy_version": POLICY_VERSION,
                "result_sequence_fingerprint": sequence_fingerprint,
            }
        )[:16]
    )
    warnings = (
        [
            "R0 named blocked rule IDs that were not present in the evaluated result set: "
            + ", ".join(sorted(set(unresolved)))
        ]
        if unresolved
        else []
    )
    return CrossRuleReasoningReport(
        analysis_id=analysis_id,
        generated_at=generated_at,
        source_diagnostic_report_id=diagnostic_report_id,
        evidence_pack_id=evidence_pack_id,
        ruleset_version=ruleset_version,
        status=(
            CrossRuleReasoningStatus.RELATIONSHIPS_RECORDED
            if relationships
            else CrossRuleReasoningStatus.NO_RELATIONSHIPS
        ),
        relationships=relationships,
        counts_by_type={
            relation_type.value: sum(
                relationship.relation_type is relation_type for relationship in relationships
            )
            for relation_type in CrossRuleRelationType
        },
        retained_rule_ids=[result.rule_id for result in ordered],
        original_result_fingerprints=fingerprints,
        suppressed_rule_ids=suppressed,
        unclassified_triggered_rule_ids=sorted(triggered - participating),
        unresolved_blocked_rule_ids=sorted(set(unresolved)),
        synthetic=synthetic,
        provenance={
            "source_evidence_fingerprint": source_evidence_fingerprint,
            "input_rule_result_count": len(ordered),
            "policy_contract_fingerprint": contract.fingerprint(),
            "result_sequence_fingerprint": sequence_fingerprint,
        },
        warnings=warnings,
        limitations=[
            contract.retention_guarantee,
            contract.confidence_semantics,
            contract.undeclared_pair_semantics,
            "Relationship records describe deterministic rule-result context, not proven causes.",
        ],
    )


def rule_result_fingerprint(result: RuleResult) -> str:
    """Fingerprint one result while normalising only its evaluation timestamp."""

    payload = result.model_dump(mode="json")
    payload["evaluated_at"] = "<normalised>"
    return _fingerprint_payload(payload)


def _policies() -> list[CrossRulePolicy]:
    triggered = [RuleStatus.TRIGGERED]
    all_statuses = list(RuleStatus)
    return [
        CrossRulePolicy(
            policy_id="XR1_R1_R2_COMPETING_CANDIDATES",
            relation_type=CrossRuleRelationType.CONFLICT,
            source_rule_id="R1",
            target_rule_id="R2",
            target_selector=CrossRuleTargetSelector.FIXED_RULE_ID,
            source_statuses=triggered,
            target_statuses=triggered,
            overlap_basis=CrossRuleOverlapBasis.EXACT_SHARED_EVIDENCE,
            required_shared_evidence_keys=["task.generated.count"],
            source_precedence=50,
            target_precedence=50,
            symmetric=True,
            statement=(
                "Evidence supports both policy under-use and infrastructure saturation candidates; "
                "the current report does not choose between them."
            ),
            presentation_effect="retain both candidates with no winner",
            limitations=[
                "Shared task-count lineage does not establish which candidate explains an outcome."
            ],
        ),
        CrossRulePolicy(
            policy_id="XR2_R1_R4_SHARED_CAPACITY_CONTEXT",
            relation_type=CrossRuleRelationType.CORROBORATION,
            source_rule_id="R1",
            target_rule_id="R4",
            target_selector=CrossRuleTargetSelector.FIXED_RULE_ID,
            source_statuses=triggered,
            target_statuses=triggered,
            overlap_basis=CrossRuleOverlapBasis.EXACT_SHARED_EVIDENCE,
            required_shared_evidence_keys=["infra.utilisation.mean"],
            source_precedence=50,
            target_precedence=50,
            symmetric=True,
            statement=(
                "R1 and R4 provide compatible candidate context around remaining aggregate "
                "capacity and uneven work distribution."
            ),
            presentation_effect="retain both candidates as contextual corroboration",
            limitations=[
                "Corroboration does not increase confidence or prove policy, routing, or "
                "placement cause."
            ],
        ),
        CrossRulePolicy(
            policy_id="XR3_R0_EXPLICIT_READINESS_BLOCKER",
            relation_type=CrossRuleRelationType.SUPPRESSION,
            source_rule_id="R0",
            target_rule_id=None,
            target_selector=CrossRuleTargetSelector.SOURCE_METADATA_BLOCKED_RULES,
            source_statuses=triggered,
            target_statuses=all_statuses,
            overlap_basis=CrossRuleOverlapBasis.EXPLICIT_BLOCKED_RULE,
            required_shared_evidence_keys=[],
            source_precedence=100,
            target_precedence=50,
            symmetric=False,
            statement=(
                "R0 explicitly blocks interpretation of this ordinary rule until its evidence "
                "readiness requirement is repaired."
            ),
            presentation_effect="retain target and mark it non-actionable while blocked",
            limitations=[
                "Suppression is a presentation/actionability state and never changes the target "
                "status."
            ],
        ),
    ]


def _relationship(
    policy: CrossRulePolicy,
    source: RuleResult,
    target: RuleResult,
    fingerprints: dict[str, str],
    synthetic: bool,
    shared: list[str],
    *,
    activation_reason: str,
) -> CrossRuleRelationship:
    identity = _fingerprint_payload(
        {
            "policy_id": policy.policy_id,
            "source": fingerprints[source.rule_id],
            "target": fingerprints[target.rule_id],
        }
    )[:16]
    return CrossRuleRelationship(
        relationship_id=f"relationship-{identity}",
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        relation_type=policy.relation_type,
        source_rule_id=source.rule_id,
        target_rule_id=target.rule_id,
        source_status=source.status,
        target_status=target.status,
        overlap_basis=policy.overlap_basis,
        shared_evidence_keys=shared,
        source_only_evidence_keys=sorted(set(source.evidence_keys) - set(shared)),
        target_only_evidence_keys=sorted(set(target.evidence_keys) - set(shared)),
        source_precedence=policy.source_precedence,
        target_precedence=policy.target_precedence,
        symmetric=policy.symmetric,
        statement=policy.statement,
        activation_reason=activation_reason,
        presentation_effect=policy.presentation_effect,
        original_result_fingerprints={
            source.rule_id: fingerprints[source.rule_id],
            target.rule_id: fingerprints[target.rule_id],
        },
        synthetic=synthetic,
        limitations=policy.limitations,
    )


def _blocked_rule_ids(result: RuleResult) -> list[str]:
    value = result.metadata.get("blocked_rules")
    if not isinstance(value, str) or not value:
        return []
    return sorted({item.strip() for item in value.split(",") if item.strip()})


def _fingerprint_payload(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
