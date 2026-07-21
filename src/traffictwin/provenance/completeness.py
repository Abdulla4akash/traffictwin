"""Deterministic report-claim provenance completeness scoring."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from io import StringIO

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.metrics.results import MetricStatus
from traffictwin.provenance.contributions import MetricContributionReport
from traffictwin.provenance.differences import (
    DifferenceContributionReport,
    DifferenceContributionStatus,
)
from traffictwin.provenance.models import (
    ProvenanceNodeType,
    ProvenanceStatus,
    ProvenanceTrace,
)
from traffictwin.reporting.claims import REPORT_CLAIM_DENOMINATOR
from traffictwin.reporting.models import (
    ReportClaimExclusion,
    ReportClaimKind,
    ReportClaimReference,
    ResearchReportType,
)
from traffictwin.rules.models import RuleStatus

PROVENANCE_COMPLETENESS_SCHEMA_VERSION = "1.0"
PROVENANCE_COMPLETENESS_CAPABILITY_ID = "PRO-03"
SCORE_NUMERATOR_DEFINITION = (
    "Claims classified source_row_complete under the complete accepted-canonical-row rules. "
    "Aggregate-only and unavailable claims contribute zero; no weighting or partial credit is used."
)


class ClaimCompletenessClassification(StrEnum):
    """Mutually exclusive PRO-03 claim classifications."""

    SOURCE_ROW_COMPLETE = "source_row_complete"
    AGGREGATE_ONLY = "aggregate_only"
    UNAVAILABLE = "unavailable"


class ClaimTraceDepth(StrEnum):
    """Deepest evidenced node type reachable from a claim trace root."""

    SOURCE_ROW = "source_row"
    SOURCE_FILE = "source_file"
    CANONICAL_RECORD = "canonical_record"
    CANONICAL_TABLE = "canonical_table"
    AGGREGATE = "aggregate"
    UNAVAILABLE = "unavailable"


class CompletenessReportStatus(StrEnum):
    """Overall inventory state without collapsing the class counts."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    NO_CLAIMS = "no_claims"


class ClaimCompletenessAssessment(BaseModel):
    """One denominator claim and its deterministic provenance classification."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    claim_kind: ReportClaimKind
    artifact_key: str = Field(min_length=1)
    section: str = Field(min_length=1)
    label: str = Field(min_length=1)
    artifact_status: str = Field(min_length=1)
    classification: ClaimCompletenessClassification
    trace_depth: ClaimTraceDepth
    trace_root_node_id: str | None = None
    trace_fingerprint: str | None = None
    candidate_source_row_count: int = Field(default=0, ge=0)
    included_source_row_count: int = Field(default=0, ge=0)
    required_evidence: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ProvenanceCompletenessReport(BaseModel):
    """Complete claim inventory and unweighted source-row completeness score."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = PROVENANCE_COMPLETENESS_SCHEMA_VERSION
    capability_id: str = PROVENANCE_COMPLETENESS_CAPABILITY_ID
    report_id: str = Field(min_length=1)
    report_type: ResearchReportType
    generated_at: datetime
    denominator_definition: str = REPORT_CLAIM_DENOMINATOR
    score_numerator_definition: str = SCORE_NUMERATOR_DEFINITION
    denominator_count: int = Field(ge=0)
    source_row_complete_count: int = Field(ge=0)
    aggregate_only_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    score: float | None = Field(default=None, ge=0, le=1)
    aggregate_or_better_fraction: float | None = Field(default=None, ge=0, le=1)
    overall_status: CompletenessReportStatus
    trace_depth_rules: list[str]
    claims: list[ClaimCompletenessAssessment]
    exclusions: list[ReportClaimExclusion]
    unavailable_is_not_zero: bool = True
    limitations: list[str]

    @model_validator(mode="after")
    def validate_inventory(self) -> ProvenanceCompletenessReport:
        """Require unique claims and exact denominator/count reconciliation."""

        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("provenance completeness claim IDs must be unique")
        if self.denominator_count != len(self.claims):
            raise ValueError("provenance completeness denominator does not match claim inventory")
        actual_counts = {
            classification: sum(claim.classification is classification for claim in self.claims)
            for classification in ClaimCompletenessClassification
        }
        if (
            self.source_row_complete_count
            != actual_counts[ClaimCompletenessClassification.SOURCE_ROW_COMPLETE]
            or self.aggregate_only_count
            != actual_counts[ClaimCompletenessClassification.AGGREGATE_ONLY]
            or self.unavailable_count != actual_counts[ClaimCompletenessClassification.UNAVAILABLE]
        ):
            raise ValueError("provenance completeness class counts do not match claim inventory")
        if self.denominator_count != (
            self.source_row_complete_count + self.aggregate_only_count + self.unavailable_count
        ):
            raise ValueError("provenance completeness classifications do not reconcile")
        if self.denominator_count == 0:
            if self.score is not None or self.aggregate_or_better_fraction is not None:
                raise ValueError("a zero-claim report must not publish a numeric score")
            if self.overall_status is not CompletenessReportStatus.NO_CLAIMS:
                raise ValueError("a zero-claim report must have no_claims status")
        else:
            expected_score = self.source_row_complete_count / self.denominator_count
            expected_aggregate = (
                self.source_row_complete_count + self.aggregate_only_count
            ) / self.denominator_count
            if self.score != expected_score:
                raise ValueError("provenance completeness score does not reconcile")
            if self.aggregate_or_better_fraction != expected_aggregate:
                raise ValueError("provenance completeness aggregate fraction does not reconcile")
            if self.source_row_complete_count == self.denominator_count:
                expected_status = CompletenessReportStatus.COMPLETE
            elif self.unavailable_count == self.denominator_count:
                expected_status = CompletenessReportStatus.UNAVAILABLE
            else:
                expected_status = CompletenessReportStatus.PARTIAL
            if self.overall_status is not expected_status:
                raise ValueError("provenance completeness overall status does not reconcile")
        return self

    def canonical_json(self) -> str:
        """Return deterministic JSON with the volatile generation time normalised."""

        payload = self.model_dump(mode="json")
        payload["generated_at"] = "<normalised>"
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        """Fingerprint the exact denominator, classifications, score, and exclusions."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        """Return readable deterministic JSON."""

        return self.model_dump_json(indent=2)


class ProvenanceCompletenessContract(BaseModel):
    """Published PRO-03 v1.0 denominator and classification contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = PROVENANCE_COMPLETENESS_SCHEMA_VERSION
    capability_id: str = PROVENANCE_COMPLETENESS_CAPABILITY_ID
    supported_report_types: list[ResearchReportType]
    denominator_definition: str = REPORT_CLAIM_DENOMINATOR
    score_numerator_definition: str = SCORE_NUMERATOR_DEFINITION
    classification_rules: dict[str, str]
    trace_depth_rules: list[str]
    exclusion_policy: list[str]
    zero_denominator_policy: str
    unavailable_is_not_zero: bool = True
    limitations: list[str]


@dataclass(frozen=True)
class ClaimEvidence:
    """Internal typed inputs used to assess one explicit report claim."""

    reference: ReportClaimReference
    artifact_status: str
    trace: ProvenanceTrace | None = None
    contribution_report: MetricContributionReport | None = None
    difference_report: DifferenceContributionReport | None = None
    required_evidence: tuple[str, ...] = ()
    dependency_assessments: tuple[ClaimCompletenessAssessment, ...] = ()
    reason_codes: tuple[str, ...] = ()


def provenance_completeness_contract() -> ProvenanceCompletenessContract:
    """Return the immutable PRO-03 v1.0 method contract."""

    return ProvenanceCompletenessContract(
        supported_report_types=[
            ResearchReportType.RUN,
            ResearchReportType.DIAGNOSTICS,
            ResearchReportType.COMPARISON,
            ResearchReportType.FULL,
        ],
        classification_rules={
            ClaimCompletenessClassification.SOURCE_ROW_COMPLETE.value: (
                "The result is available, its complete accepted-canonical-row ledger reconciles, "
                "at least one candidate source row exists, and every row has a bundle-relative "
                "source file and positive source-row reference. Rule claims additionally require "
                "all cited metric dependencies at this class and no missing evidence."
            ),
            ClaimCompletenessClassification.AGGREGATE_ONLY.value: (
                "A typed result exists but complete source-row admission is not established, for "
                "example because the result is partial, the source is aggregate, the population "
                "is empty, or a rule retains missing evidence."
            ),
            ClaimCompletenessClassification.UNAVAILABLE.value: (
                "The typed result is unavailable/invalid, a rule reports insufficient evidence, "
                "or an ordinary metric comparison is unavailable."
            ),
        },
        trace_depth_rules=_trace_depth_rules(),
        exclusion_policy=[
            "Only explicit ReportClaimReference entries enter the denominator.",
            "Headings, narrative, limitations, warnings, identity metadata, validation summaries, "
            "and reproduction commands remain visible as named exclusion categories.",
            "An unavailable referenced claim stays in the denominator and contributes zero.",
        ],
        zero_denominator_policy=(
            "Publish score=null and overall_status=no_claims; never treat an empty denominator as "
            "complete."
        ),
        limitations=[
            "Source-row complete means complete for accepted canonical candidates; raw rows "
            "rejected before canonicalisation remain validation evidence outside this denominator.",
            "The score measures traceability depth, not truth, causal validity, model quality, or "
            "scientific importance.",
            "All denominator claims have equal weight; report authors cannot raise the score by "
            "assigning weights.",
            "External report types without typed ReportClaimReference inventories are unsupported.",
        ],
    )


def build_provenance_completeness_report(
    *,
    report_id: str,
    report_type: ResearchReportType,
    claim_evidence: list[ClaimEvidence],
    exclusions: list[ReportClaimExclusion],
    clock: Callable[[], datetime] | None = None,
) -> ProvenanceCompletenessReport:
    """Classify every explicit denominator claim and calculate the unweighted score."""

    assessments = [_assess_claim(evidence) for evidence in claim_evidence]
    source_count = sum(
        assessment.classification is ClaimCompletenessClassification.SOURCE_ROW_COMPLETE
        for assessment in assessments
    )
    aggregate_count = sum(
        assessment.classification is ClaimCompletenessClassification.AGGREGATE_ONLY
        for assessment in assessments
    )
    unavailable_count = sum(
        assessment.classification is ClaimCompletenessClassification.UNAVAILABLE
        for assessment in assessments
    )
    denominator = len(assessments)
    score = source_count / denominator if denominator else None
    aggregate_or_better = (source_count + aggregate_count) / denominator if denominator else None
    if denominator == 0:
        overall = CompletenessReportStatus.NO_CLAIMS
    elif source_count == denominator:
        overall = CompletenessReportStatus.COMPLETE
    elif unavailable_count == denominator:
        overall = CompletenessReportStatus.UNAVAILABLE
    else:
        overall = CompletenessReportStatus.PARTIAL
    return ProvenanceCompletenessReport(
        report_id=report_id,
        report_type=report_type,
        generated_at=clock() if clock is not None else datetime.now(UTC),
        denominator_count=denominator,
        source_row_complete_count=source_count,
        aggregate_only_count=aggregate_count,
        unavailable_count=unavailable_count,
        score=score,
        aggregate_or_better_fraction=aggregate_or_better,
        overall_status=overall,
        trace_depth_rules=_trace_depth_rules(),
        claims=assessments,
        exclusions=exclusions,
        limitations=provenance_completeness_contract().limitations,
    )


def assess_claim_evidence(evidence: ClaimEvidence) -> ClaimCompletenessAssessment:
    """Classify one explicit claim for composition into a report inventory."""

    return _assess_claim(evidence)


def provenance_completeness_report_to_csv(report: ProvenanceCompletenessReport) -> str:
    """Render the complete denominator inventory as deterministic CSV."""

    output = StringIO(newline="")
    fieldnames = [
        "schema_version",
        "capability_id",
        "report_id",
        "report_type",
        "denominator_count",
        "source_row_complete_count",
        "aggregate_only_count",
        "unavailable_count",
        "score",
        "claim_id",
        "claim_kind",
        "artifact_key",
        "section",
        "artifact_status",
        "classification",
        "trace_depth",
        "candidate_source_row_count",
        "included_source_row_count",
        "required_evidence_json",
        "reason_codes_json",
        "score_numerator_definition",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    claims: list[ClaimCompletenessAssessment | None] = list(report.claims) or [None]
    for claim in claims:
        writer.writerow(
            {
                "schema_version": report.schema_version,
                "capability_id": report.capability_id,
                "report_id": report.report_id,
                "report_type": report.report_type.value,
                "denominator_count": report.denominator_count,
                "source_row_complete_count": report.source_row_complete_count,
                "aggregate_only_count": report.aggregate_only_count,
                "unavailable_count": report.unavailable_count,
                "score": report.score if report.score is not None else "",
                "claim_id": claim.claim_id if claim is not None else "",
                "claim_kind": claim.claim_kind.value if claim is not None else "",
                "artifact_key": claim.artifact_key if claim is not None else "",
                "section": claim.section if claim is not None else "",
                "artifact_status": claim.artifact_status if claim is not None else "",
                "classification": claim.classification.value if claim is not None else "",
                "trace_depth": claim.trace_depth.value if claim is not None else "",
                "candidate_source_row_count": (
                    claim.candidate_source_row_count if claim is not None else ""
                ),
                "included_source_row_count": (
                    claim.included_source_row_count if claim is not None else ""
                ),
                "required_evidence_json": (
                    json.dumps(claim.required_evidence, separators=(",", ":"))
                    if claim is not None
                    else "[]"
                ),
                "reason_codes_json": (
                    json.dumps(claim.reason_codes, separators=(",", ":"))
                    if claim is not None
                    else "[]"
                ),
                "score_numerator_definition": report.score_numerator_definition,
            }
        )
    return output.getvalue()


def _assess_claim(evidence: ClaimEvidence) -> ClaimCompletenessAssessment:
    if evidence.reference.claim_kind is ReportClaimKind.METRIC_RESULT:
        return _assess_metric_claim(evidence)
    if evidence.reference.claim_kind is ReportClaimKind.RULE_RESULT:
        return _assess_rule_claim(evidence)
    if evidence.reference.claim_kind is ReportClaimKind.METRIC_COMPARISON:
        return _assess_comparison_claim(evidence)
    raise ValueError(f"unsupported report claim kind: {evidence.reference.claim_kind}")


def _assess_metric_claim(evidence: ClaimEvidence) -> ClaimCompletenessAssessment:
    depth = _trace_depth(evidence.trace)
    reasons = list(evidence.reason_codes)
    status = MetricStatus(evidence.artifact_status)
    ledger = evidence.contribution_report
    candidate_count = ledger.candidate_row_count if ledger is not None else 0
    included_count = ledger.included_row_count if ledger is not None else 0
    if status in {MetricStatus.UNAVAILABLE, MetricStatus.INVALID}:
        classification = ClaimCompletenessClassification.UNAVAILABLE
        reasons.append(f"metric_status:{status.value}")
    elif status is MetricStatus.PARTIAL:
        classification = ClaimCompletenessClassification.AGGREGATE_ONLY
        reasons.append("partial_metric_is_not_source_row_complete")
    elif _complete_metric_ledger(ledger) and depth is ClaimTraceDepth.SOURCE_ROW:
        classification = ClaimCompletenessClassification.SOURCE_ROW_COMPLETE
    else:
        classification = ClaimCompletenessClassification.AGGREGATE_ONLY
        if ledger is None:
            reasons.append("complete_accepted_row_ledger_unavailable")
        elif ledger.candidate_row_count == 0:
            reasons.append("no_candidate_source_rows")
        elif depth is not ClaimTraceDepth.SOURCE_ROW:
            reasons.append(f"deepest_trace_node:{depth.value}")
        else:
            reasons.append("accepted_row_ledger_did_not_reconcile")
    return _assessment(
        evidence,
        classification=classification,
        depth=depth,
        candidate_count=candidate_count,
        included_count=included_count,
        reasons=reasons,
    )


def _assess_rule_claim(evidence: ClaimEvidence) -> ClaimCompletenessAssessment:
    depth = _trace_depth(evidence.trace)
    reasons = list(evidence.reason_codes)
    status = RuleStatus(evidence.artifact_status)
    dependencies = evidence.dependency_assessments
    if status in {RuleStatus.INSUFFICIENT_EVIDENCE, RuleStatus.INVALID}:
        classification = ClaimCompletenessClassification.UNAVAILABLE
        reasons.append(f"rule_status:{status.value}")
    elif (
        dependencies
        and all(
            dependency.classification is ClaimCompletenessClassification.SOURCE_ROW_COMPLETE
            for dependency in dependencies
        )
        and not reasons
        and depth is ClaimTraceDepth.SOURCE_ROW
    ):
        classification = ClaimCompletenessClassification.SOURCE_ROW_COMPLETE
    else:
        classification = ClaimCompletenessClassification.AGGREGATE_ONLY
        if not dependencies:
            reasons.append("no_source_row_complete_metric_dependency_inventory")
        elif any(
            dependency.classification is ClaimCompletenessClassification.UNAVAILABLE
            for dependency in dependencies
        ):
            reasons.append("one_or_more_metric_dependencies_unavailable")
        elif any(
            dependency.classification is ClaimCompletenessClassification.AGGREGATE_ONLY
            for dependency in dependencies
        ):
            reasons.append("one_or_more_metric_dependencies_aggregate_only")
        if depth is not ClaimTraceDepth.SOURCE_ROW:
            reasons.append(f"deepest_trace_node:{depth.value}")
    return _assessment(
        evidence,
        classification=classification,
        depth=depth,
        candidate_count=sum(item.candidate_source_row_count for item in dependencies),
        included_count=sum(item.included_source_row_count for item in dependencies),
        reasons=reasons,
    )


def _assess_comparison_claim(evidence: ClaimEvidence) -> ClaimCompletenessAssessment:
    report = evidence.difference_report
    reasons = list(evidence.reason_codes)
    if report is None:
        return _assessment(
            evidence,
            classification=ClaimCompletenessClassification.UNAVAILABLE,
            depth=ClaimTraceDepth.UNAVAILABLE,
            candidate_count=0,
            included_count=0,
            reasons=[*reasons, "difference_provenance_report_unavailable"],
        )
    candidate_count = report.baseline.candidate_row_count + report.variation.candidate_row_count
    included_count = report.baseline.included_row_count + report.variation.included_row_count
    if report.status is DifferenceContributionStatus.UNAVAILABLE:
        classification = ClaimCompletenessClassification.UNAVAILABLE
        depth = ClaimTraceDepth.UNAVAILABLE
        reasons.append("difference_status:unavailable")
    elif _complete_difference_rows(report):
        classification = ClaimCompletenessClassification.SOURCE_ROW_COMPLETE
        depth = ClaimTraceDepth.SOURCE_ROW
    else:
        classification = ClaimCompletenessClassification.AGGREGATE_ONLY
        depth = ClaimTraceDepth.AGGREGATE
        reasons.append("comparison_has_no_nonempty_complete_two_side_row_ledger")
    return _assessment(
        evidence,
        classification=classification,
        depth=depth,
        candidate_count=candidate_count,
        included_count=included_count,
        reasons=reasons,
        fingerprint=report.fingerprint(),
    )


def _assessment(
    evidence: ClaimEvidence,
    *,
    classification: ClaimCompletenessClassification,
    depth: ClaimTraceDepth,
    candidate_count: int,
    included_count: int,
    reasons: list[str],
    fingerprint: str | None = None,
) -> ClaimCompletenessAssessment:
    trace = evidence.trace
    return ClaimCompletenessAssessment(
        **evidence.reference.model_dump(mode="python"),
        artifact_status=evidence.artifact_status,
        classification=classification,
        trace_depth=depth,
        trace_root_node_id=trace.root_node_id if trace is not None else None,
        trace_fingerprint=fingerprint
        or _claim_evidence_fingerprint(evidence, classification, depth),
        candidate_source_row_count=candidate_count,
        included_source_row_count=included_count,
        required_evidence=sorted(set(evidence.required_evidence)),
        reason_codes=sorted(set(reasons)),
        limitations=[
            "Classification records deterministic lineage depth, not causal attribution or truth."
        ],
    )


def _complete_metric_ledger(report: MetricContributionReport | None) -> bool:
    if report is None or not report.complete_row_ledger or report.candidate_row_count == 0:
        return False
    if report.candidate_row_count != len(report.rows):
        return False
    if report.candidate_row_count != report.included_row_count + report.excluded_row_count:
        return False
    return all(bool(row.source_file) and row.source_row >= 1 for row in report.rows)


def _claim_evidence_fingerprint(
    evidence: ClaimEvidence,
    classification: ClaimCompletenessClassification,
    depth: ClaimTraceDepth,
) -> str:
    trace = evidence.trace
    payload = {
        "claim_kind": evidence.reference.claim_kind.value,
        "artifact_key": evidence.reference.artifact_key,
        "artifact_status": evidence.artifact_status,
        "classification": classification.value,
        "trace_depth": depth.value,
        "trace_root_node_id": trace.root_node_id if trace is not None else None,
        "source_fingerprint": trace.source_fingerprint if trace is not None else None,
        "trace_completeness": (
            trace.completeness.model_dump(mode="json") if trace is not None else None
        ),
        "contribution_report": (
            evidence.contribution_report.model_dump(mode="json")
            if evidence.contribution_report is not None
            else None
        ),
        "dependency_fingerprints": [
            item.trace_fingerprint for item in evidence.dependency_assessments
        ],
        "required_evidence": sorted(set(evidence.required_evidence)),
        "reason_codes": sorted(set(evidence.reason_codes)),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _complete_difference_rows(report: DifferenceContributionReport) -> bool:
    candidate_count = report.baseline.candidate_row_count + report.variation.candidate_row_count
    if report.baseline.candidate_row_count == 0 or report.variation.candidate_row_count == 0:
        return False
    if candidate_count != len(report.rows):
        return False
    for summary in (report.baseline, report.variation):
        if summary.candidate_row_count != (summary.included_row_count + summary.excluded_row_count):
            return False
        if sum(row.side is summary.side for row in report.rows) != summary.candidate_row_count:
            return False
    return all(bool(row.source_file) and row.source_row >= 1 for row in report.rows)


def _trace_depth(trace: ProvenanceTrace | None) -> ClaimTraceDepth:
    if trace is None:
        return ClaimTraceDepth.UNAVAILABLE
    by_id = trace.by_id()
    root = by_id.get(trace.root_node_id)
    if root is None or root.status in {ProvenanceStatus.UNAVAILABLE, ProvenanceStatus.INVALID}:
        return ClaimTraceDepth.UNAVAILABLE
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for edge in trace.edges:
        adjacency[edge.source_node_id].append(edge.target_node_id)
    reachable: set[str] = set()
    queue: deque[str] = deque([trace.root_node_id])
    while queue:
        node_id = queue.popleft()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        queue.extend(sorted(adjacency[node_id]))
    available_types = {
        by_id[node_id].node_type
        for node_id in reachable
        if by_id[node_id].status not in {ProvenanceStatus.UNAVAILABLE, ProvenanceStatus.INVALID}
    }
    for node_type, depth in (
        (ProvenanceNodeType.SOURCE_ROW, ClaimTraceDepth.SOURCE_ROW),
        (ProvenanceNodeType.SOURCE_FILE, ClaimTraceDepth.SOURCE_FILE),
        (ProvenanceNodeType.CANONICAL_RECORD, ClaimTraceDepth.CANONICAL_RECORD),
        (ProvenanceNodeType.CANONICAL_TABLE, ClaimTraceDepth.CANONICAL_TABLE),
    ):
        if node_type in available_types:
            return depth
    return ClaimTraceDepth.AGGREGATE


def _trace_depth_rules() -> list[str]:
    return [
        "Follow only existing directed provenance edges outward from the claim root.",
        "Ignore unavailable or invalid nodes when selecting the deepest evidenced type.",
        "Depth order is source_row, source_file, canonical_record, canonical_table, aggregate, "
        "then unavailable.",
        "Reaching one sampled source row establishes depth only; source_row_complete additionally "
        "requires the separate complete accepted-row ledger to reconcile.",
    ]
