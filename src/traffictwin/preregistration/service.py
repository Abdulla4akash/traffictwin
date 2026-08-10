"""Deterministic service for preregistration governance workflow."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import yaml

from traffictwin.metrics.catalogue import METRIC_VERSION
from traffictwin.preregistration.models import (
    AmendmentLabel,
    AnalysisMethod,
    DecisionGateReport,
    DecisionGateStatus,
    EvidenceAttachment,
    EvidenceMode,
    MultiplicityPolicy,
    PlannedRunCell,
    StudyPlan,
    StudyPlanRevision,
    StudyPlanStatus,
    field_level_diff,
    has_evidence_in_lineage,
    is_explicitly_admitted,
)

MAX_CELLS = 10000


def utc_now() -> datetime:
    return datetime.now(UTC)


def validate_study_plan(plan: StudyPlan) -> list[str]:
    """Return deterministic list of validation findings. Empty means freezable."""
    findings: list[str] = []

    if not plan.study_question.text.strip() or len(plan.study_question.text.strip()) < 12:
        findings.append("study_question.text must contain at least 12 characters")

    if not plan.primary_outcomes:
        findings.append("missing primary outcome: at least one primary outcome is required")
    else:
        for outcome in plan.primary_outcomes:
            if not outcome.metric_key.strip():
                findings.append(f"primary outcome {outcome.outcome_id!r} missing metric_key")
            if not outcome.metric_version.strip():
                findings.append(f"primary outcome {outcome.outcome_id!r} missing metric_version")
            if not outcome.unit.strip():
                findings.append(f"primary outcome {outcome.outcome_id!r} missing unit")
            if outcome.denominator is None or not outcome.denominator.strip():
                findings.append(f"primary outcome {outcome.outcome_id!r} missing denominator")
            if outcome.metric_version != METRIC_VERSION:
                findings.append(
                    f"primary outcome {outcome.outcome_id!r} has inconsistent metric_version {outcome.metric_version!r} expected {METRIC_VERSION!r}"  # noqa: E501
                )
        primary_ids = [o.outcome_id for o in plan.primary_outcomes]
        if len(set(primary_ids)) != len(primary_ids):
            findings.append("duplicate primary outcome_id")
        versions = {o.metric_version for o in plan.primary_outcomes}
        if len(versions) > 1:
            findings.append(f"inconsistent metric versions across primary outcomes: {sorted(versions)}")  # noqa: E501
        secondary_versions = {o.metric_version for o in plan.secondary_outcomes}
        if secondary_versions and secondary_versions != versions:
            findings.append(
                f"secondary outcomes use different metric_version from primary: {sorted(secondary_versions)} vs {sorted(versions)}"  # noqa: E501
            )

    if not plan.replication_ids and not plan.replication_generation_rule:
        findings.append("empty replication set: replication_ids or replication_generation_rule is required")  # noqa: E501
    if plan.replication_ids:
        if len(plan.replication_ids) == 0:
            findings.append("replication_ids must not be empty")
        if len(set(plan.replication_ids)) != len(plan.replication_ids):
            findings.append("duplicate replication_ids")

    if not plan.planned_arms:
        findings.append("planned arms must contain at least one arm")
    else:
        if len(set(plan.planned_arms)) != len(plan.planned_arms):
            findings.append("duplicate arm identities")
        for arm in plan.planned_arms:
            if not arm.strip():
                findings.append("arm identities must not be blank")
            if arm.strip() != arm:
                findings.append(f"arm {arm!r} has surrounding whitespace")

    if not plan.cohort_rules:
        findings.append("inclusion rules must contain at least one cohort rule")
    if not plan.exclusion_rules:
        findings.append("exclusion rules must contain at least one exclusion rule")

    method = plan.analysis_method
    rule = plan.decision_rule
    alpha_required_methods = {
        AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        AnalysisMethod.PAIRED_BOOTSTRAP,
        AnalysisMethod.SIGN_FLIP,
        AnalysisMethod.TOST_EQUIVALENCE,
        AnalysisMethod.REGRESSION,
        AnalysisMethod.MIXED_EFFECTS,
    }
    if method in alpha_required_methods:
        if rule.alpha is None and rule.threshold is None:
            findings.append(f"decision rule must provide alpha or threshold for analysis_method {method.value!r}")  # noqa: E501
        if method == AnalysisMethod.TOST_EQUIVALENCE:
            if rule.threshold is None:
                findings.append("TOST equivalence requires a threshold (equivalence margin)")
            if rule.alpha is None:
                findings.append("TOST equivalence requires alpha")
            if rule.comparison != "equivalence":
                findings.append("TOST equivalence decision_rule must use comparison='equivalence'")
        if method != AnalysisMethod.TOST_EQUIVALENCE and rule.comparison == "equivalence":
            findings.append(f"analysis_method {method.value!r} is incompatible with equivalence comparison")  # noqa: E501

    if len(plan.primary_outcomes) > 1:  # noqa: SIM102
        if plan.multiplicity_policy in (MultiplicityPolicy.NONE_SINGLE_TEST, MultiplicityPolicy.NOT_APPLICABLE):  # noqa: E501
            findings.append("multiplicity policy required when multiple primary outcomes exist")

    if not plan.stopping_rule.description.strip() or len(plan.stopping_rule.description.strip()) < 12:  # noqa: E501
        findings.append("stopping_rule.description must contain at least 12 characters")

    if not plan.decision_rule.interpretation.strip() or len(plan.decision_rule.interpretation.strip()) < 12:  # noqa: E501
        findings.append("decision_rule.interpretation must contain at least 12 characters")

    if not plan.limitations.strip() or len(plan.limitations.strip()) < 12:
        findings.append("limitations must contain at least 12 characters")

    if plan.planned_run_cells:
        cell_ids = [c.cell_id for c in plan.planned_run_cells]
        if len(set(cell_ids)) != len(cell_ids):
            findings.append("duplicate run cells: cell_id duplicates")
        composites = [(c.arm_id, c.seed_id, c.policy_label, c.replication_id, c.metric_key, c.metric_version, c.replication_unit.value) for c in plan.planned_run_cells]  # noqa: E501
        if len(set(composites)) != len(composites):
            findings.append("duplicate run cells: arm/seed/policy/replication/metric duplicates")
        for cell in plan.planned_run_cells:
            if cell.arm_id not in plan.planned_arms:
                findings.append(f"run cell {cell.cell_id!r} has ambiguous arm {cell.arm_id!r} not in planned_arms")  # noqa: E501
        primary_keys = {o.metric_key for o in plan.primary_outcomes}
        cell_keys = {c.metric_key for c in plan.planned_run_cells}
        for pk in primary_keys:
            if pk not in cell_keys:
                findings.append(f"missing primary outcome metric {pk!r} in run cells")
        primary_versions = {o.metric_version for o in plan.primary_outcomes}
        for cell in plan.planned_run_cells:
            if cell.metric_version not in primary_versions:
                findings.append(
                    f"run cell {cell.cell_id!r} has inconsistent metric_version {cell.metric_version!r} not in primary outcomes {sorted(primary_versions)}"  # noqa: E501
                )
        allowed_keys = {o.metric_key for o in plan.primary_outcomes} | {o.metric_key for o in plan.secondary_outcomes}  # noqa: E501
        for cell in plan.planned_run_cells:
            if cell.metric_key not in allowed_keys:
                findings.append(f"run cell {cell.cell_id!r} has undeclared post-hoc metric {cell.metric_key!r}")  # noqa: E501
        if len(plan.planned_run_cells) > MAX_CELLS:
            findings.append(f"run matrix exceeds limit {MAX_CELLS}")
    else:
        if plan.planned_arms and (plan.replication_ids or plan.replication_generation_rule):
            pass
        else:
            findings.append("planned_run_cells is empty and cannot be derived from arms/replication")  # noqa: E501

    if plan.evidence_mode == EvidenceMode.UNAVAILABLE:
        findings.append("evidence_mode must not be unavailable for a freezable plan")

    return sorted(set(findings))


def is_freezable(plan: StudyPlan) -> bool:
    return len(validate_study_plan(plan)) == 0


def _parse_replication_count(plan: StudyPlan) -> int:
    """Return count of replication IDs without materialising full list, bounded."""
    if plan.replication_ids:
        return len(plan.replication_ids)
    rule = (plan.replication_generation_rule or "").strip()
    if not rule:
        return 0
    if rule.startswith("range:"):
        try:
            n = int(rule.split(":", 1)[1].strip())
            return n if n >= 0 else 0
        except Exception:
            return 0
    if ".." in rule:
        try:
            parts = rule.split("..")
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            if end < start:
                return 0
            return end - start + 1
        except Exception:
            return 0
    if "," in rule:
        try:
            return len({x.strip() for x in rule.split(",") if x.strip()})
        except Exception:
            return 0
    try:
        int(rule)
        return 1
    except Exception:
        return 0


def _materialize_replication_ids(plan: StudyPlan) -> list[int]:
    replication_ids = plan.replication_ids
    if replication_ids:
        return sorted(replication_ids)
    rule = (plan.replication_generation_rule or "").strip()
    if not rule:
        return []
    if rule.startswith("range:"):
        n = int(rule.split(":", 1)[1].strip())
        if n < 1:
            raise ValueError("range must be >=1")
        return list(range(n))
    if ".." in rule:
        parts = rule.split("..")
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        if end < start:
            raise ValueError("invalid range")
        return list(range(start, end + 1))
    if "," in rule:
        return sorted({int(x.strip()) for x in rule.split(",") if x.strip()})
    return [int(rule)]


def build_run_matrix(plan: StudyPlan) -> list[PlannedRunCell]:
    """Build deterministic run-cell matrix from declared plan. Raises ValueError on invalid."""
    if not plan.primary_outcomes:
        raise ValueError("missing primary outcome")
    if not plan.planned_arms:
        raise ValueError("planned_arms must contain at least one arm")
    if not plan.replication_ids and not plan.replication_generation_rule:
        raise ValueError("empty replication set")

    # Bounded cardinality check before materialisation
    repl_count = _parse_replication_count(plan)
    if repl_count == 0:
        raise ValueError("empty replication set after generation rule")
    # Determine seeds/policies dimensions: if empty, treat as 1 (metadata-only)
    seeds_dim = plan.seeds if plan.seeds else [None]  # type: ignore
    policies_dim = plan.policies if plan.policies else [None]  # type: ignore
    # But spec says every selector must affect matrix; if seeds/policies empty, 1 is correct.  # noqa: E501
    # If non-empty, each must be represented.
    arms = plan.planned_arms
    primaries = plan.primary_outcomes
    projected = len(arms) * len(seeds_dim) * len(policies_dim) * repl_count * len(primaries)
    if projected > MAX_CELLS:
        raise ValueError(f"run matrix exceeds limit {MAX_CELLS}: projected {projected}")

    replication_ids = _materialize_replication_ids(plan)
    if not replication_ids:
        raise ValueError("empty replication set after generation rule")

    sorted_arms = sorted(arms)
    sorted_seeds = sorted(seeds_dim) if seeds_dim[0] is not None else [None]
    sorted_policies = sorted(policies_dim) if policies_dim[0] is not None else [None]
    sorted_replications = sorted(replication_ids)
    sorted_primaries = sorted(primaries, key=lambda o: o.outcome_id)

    cells: list[PlannedRunCell] = []
    seq = 1
    seen = set()
    for arm in sorted_arms:
        for seed_val in sorted_seeds:
            for pol_val in sorted_policies:
                for rep in sorted_replications:
                    for outcome in sorted_primaries:
                        # Canonical seed/policy mapping: if dim 1 (None), use arm fallback for cell fields to keep legacy compat,  # noqa: E501
                        # but still ensure matrix size reflects dimensions. For determinism, use seed/pol when present.  # noqa: E501
                        seed_id = seed_val if seed_val is not None else (plan.seeds[0] if plan.seeds else None)  # noqa: E501
                        # If seeds_dim has multiple, seed_id is current val; else fallback.  # noqa: E501
                        if seeds_dim[0] is not None:
                            seed_id = seed_val
                        policy_label = pol_val if pol_val is not None else (plan.policies[0] if plan.policies else arm)  # noqa: E501
                        if policies_dim[0] is not None:
                            policy_label = pol_val  # type: ignore
                        cell_id = f"cell-{seq:04d}"
                        composite = (arm, seed_id, policy_label, rep, outcome.metric_key, outcome.metric_version, plan.replication_unit.value)  # noqa: E501
                        if composite in seen:
                            raise ValueError(f"duplicate run cells: {composite}")
                        seen.add(composite)
                        cells.append(
                            PlannedRunCell(
                                cell_id=cell_id,
                                arm_id=arm,
                                seed_id=seed_id,
                                policy_label=policy_label,  # type: ignore
                                replication_id=rep,
                                metric_key=outcome.metric_key,
                                metric_version=outcome.metric_version,
                                replication_unit=plan.replication_unit,
                            )
                        )
                        seq += 1
                        if len(cells) > MAX_CELLS:
                            raise ValueError(f"run matrix exceeds limit {MAX_CELLS}")
    return cells


def _canonical_cell_key(cell: PlannedRunCell) -> tuple:
    return (cell.arm_id, cell.seed_id, cell.policy_label, cell.replication_id, cell.metric_key, cell.metric_version, cell.replication_unit.value)  # noqa: E501


def fingerprint_plan(plan: StudyPlan) -> str:
    """Return deterministic fingerprint for a plan, excluding wall-clock fields."""
    return plan.compute_fingerprint()


def freeze_plan(plan: StudyPlan, *, clock: Callable[[], datetime] | None = None) -> StudyPlan:
    """Validate and freeze a draft plan into an immutable version. Raises ValueError if not freezable."""  # noqa: E501
    if plan.status != StudyPlanStatus.DRAFT:
        raise ValueError(f"only DRAFT plans can be frozen; current status is {plan.status.value!r}")
    findings = validate_study_plan(plan)
    if findings:
        raise ValueError(f"plan is not freezable: {'; '.join(findings)}")
    try:
        built_cells = build_run_matrix(plan)
    except ValueError as exc:
        raise ValueError(f"run matrix invalid: {exc}") from exc

    if not plan.planned_run_cells:
        cells = built_cells
    else:
        # Strict: authored matrix must exactly match deterministic derived matrix
        built_set = {_canonical_cell_key(c) for c in built_cells}
        provided_set = {_canonical_cell_key(c) for c in plan.planned_run_cells}
        # Also check cell_id uniqueness already validated, but comparison is on scientific contents  # noqa: E501
        if built_set != provided_set:
            # Provide detailed diagnostic without silently repairing
            missing = built_set - provided_set
            extra = provided_set - built_set
            details = []
            if missing:
                details.append(f"missing expected cells: {sorted(missing)[:3]}")
            if extra:
                details.append(f"extra authored cells: {sorted(extra)[:3]}")
            if len(built_set) != len(provided_set):
                details.append(f"count mismatch built={len(built_set)} provided={len(provided_set)}")  # noqa: E501
            raise ValueError(
                f"authored planned_run_cells does not match deterministic matrix; {'; '.join(details)}"  # noqa: E501
            )
        # Order is non-semantic, canonicalise to sorted built order for determinism but preserve identity  # noqa: E501
        # Keep provided cells sorted deterministically for fingerprint stability
        cells = sorted(plan.planned_run_cells, key=_canonical_cell_key)

    now = clock() if clock is not None else utc_now()
    frozen = plan.model_copy(
        update={
            "status": StudyPlanStatus.FROZEN,
            "frozen_at": now,
            "planned_run_cells": cells,
        }
    )
    fp = frozen.compute_fingerprint()
    frozen = frozen.model_copy(update={"fingerprint": fp})
    return frozen


def create_amendment(
    parent: StudyPlan,
    *,
    changes: dict[str, Any],
    amendment_reason: str,
    clock: Callable[[], datetime] | None = None,
    evidence_attached_at: datetime | None = None,
) -> StudyPlan:
    """Create a new version as child of a frozen plan. Preserves parent fingerprint bytes immutably."""  # noqa: E501
    if parent.status not in (StudyPlanStatus.FROZEN, StudyPlanStatus.EVIDENCE_ATTACHED, StudyPlanStatus.DECIDED, StudyPlanStatus.CLOSED):  # noqa: E501
        raise ValueError(f"only frozen or later plans can be amended; parent status is {parent.status.value!r}")  # noqa: E501
    if not amendment_reason.strip() or len(amendment_reason.strip()) < 12:
        raise ValueError("amendment_reason must contain at least 12 characters")
    if parent.fingerprint is None:
        raise ValueError("parent plan must have a fingerprint; freeze it first")
    parent_fp = parent.fingerprint
    parent_version = parent.version

    # Monotonic taint derived from lineage
    is_post = has_evidence_in_lineage(parent)
    # Also consider explicit evidence_attached_at passed in
    if evidence_attached_at is not None:
        is_post = True
    label = AmendmentLabel.POST_EVIDENCE if is_post else AmendmentLabel.PRE_EVIDENCE

    now = clock() if clock is not None else utc_now()
    parent_payload = parent.model_dump(mode="json", by_alias=True)
    new_payload = dict(parent_payload)
    for key, value in changes.items():
        if key in ("plan_id", "fingerprint", "frozen_at", "created_at", "evidence_attached_at", "parent_fingerprint", "revision_history", "evidence_state_fingerprint"):  # noqa: E501
            raise ValueError(f"field {key!r} cannot be changed via amendment")
        new_payload[key] = value

    new_version = parent_version + 1
    new_payload["version"] = new_version
    new_payload["status"] = StudyPlanStatus.DRAFT.value
    new_payload["parent_fingerprint"] = parent_fp
    new_payload["parent_version"] = parent_version
    new_payload["frozen_at"] = None
    new_payload["fingerprint"] = None
    new_payload["evidence_state_fingerprint"] = None
    new_payload["evidence_attachments"] = []
    new_payload["gate_report"] = None
    new_payload["evidence_attached_at"] = None

    new_payload["created_at"] = now.isoformat()

    parent_history = list(parent.revision_history)
    old_canonical = parent.canonical_payload()
    tmp_new = StudyPlan.model_validate(new_payload)
    new_canonical = tmp_new.canonical_payload()
    diff = field_level_diff(old_canonical, new_canonical)

    revision = StudyPlanRevision(
        version=new_version,
        parent_fingerprint=parent_fp,
        parent_version=parent_version,
        amendment_reason=amendment_reason.strip(),
        diff=diff,
        created_at=now,
        is_post_evidence=is_post,
        amendment_label=label,
    )
    new_history = parent_history + [revision]
    new_payload["revision_history"] = [r.model_dump(mode="json") for r in new_history]

    new_plan = StudyPlan.model_validate(new_payload)
    return new_plan


def attach_evidence(
    plan: StudyPlan,
    attachments: list[EvidenceAttachment],
    *,
    clock: Callable[[], datetime] | None = None,
) -> StudyPlan:
    """Attach imported evidence by fingerprint to a frozen plan. Returns new plan with EVIDENCE_ATTACHED status."""  # noqa: E501
    if plan.status not in (StudyPlanStatus.FROZEN, StudyPlanStatus.EVIDENCE_ATTACHED):
        raise ValueError(f"evidence can only be attached to FROZEN or EVIDENCE_ATTACHED plans; current {plan.status.value!r}")  # noqa: E501
    if plan.fingerprint is None:
        raise ValueError("plan must have a fingerprint before attaching evidence")
    if not attachments:
        raise ValueError("at least one attachment is required")

    # Detect duplicate attachment cell IDs before dict collapse
    seen = set()
    duplicates = []
    for att in attachments:
        if att.cell_id in seen:
            duplicates.append(att.cell_id)
        seen.add(att.cell_id)
    if duplicates:
        raise ValueError(f"duplicate attachment cell_ids: {sorted(set(duplicates))}")

    now = clock() if clock is not None else utc_now()

    normalized: list[EvidenceAttachment] = []
    for att in attachments:
        if att.attached_at is None:
            att = att.model_copy(update={"attached_at": now})
        normalized.append(att)

    # Preserve frozen fingerprint immutably; compute separate evidence-state fingerprint
    frozen_fp = plan.fingerprint
    # Build updated copy with attachments and status, but keep frozen fingerprint
    updated = plan.model_copy(
        update={
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attachments": sorted(normalized, key=lambda a: a.cell_id),
            "evidence_attached_at": now,
        }
    )
    # Gate evaluation will also compute incompatibility reasons and set them on copies
    gate, enriched_attachments = evaluate_gate_with_reasons(updated, sorted(normalized, key=lambda a: a.cell_id))  # noqa: E501
    # Enrich attachments with incompatibility reasons
    updated = updated.model_copy(update={"evidence_attachments": enriched_attachments, "gate_report": gate})  # noqa: E501
    # Keep frozen fingerprint immutable
    updated = updated.model_copy(update={"fingerprint": frozen_fp})
    # Compute separate evidence-state fingerprint
    evidence_fp = updated.compute_evidence_state_fingerprint()
    updated = updated.model_copy(update={"evidence_state_fingerprint": evidence_fp})

    return updated


def evaluate_gate_with_reasons(
    plan: StudyPlan, attachments: list[EvidenceAttachment] | None = None
) -> tuple[DecisionGateReport, list[EvidenceAttachment]]:
    """Evaluate gate and return enriched attachments with incompatibility_reason."""
    if attachments is None:
        attachments = plan.evidence_attachments

    expected_cell_ids = {c.cell_id for c in plan.planned_run_cells}
    if not expected_cell_ids:
        report = DecisionGateReport(
            status=DecisionGateStatus.UNAVAILABLE,
            reasons=["no planned run cells defined"],
            is_unavailable=True,
            is_ready=False,
            is_blocked=False,
        )
        return report, attachments

    if not plan.primary_outcomes:
        report = DecisionGateReport(
            status=DecisionGateStatus.UNAVAILABLE,
            reasons=["primary outcome missing: gate cannot be ready"],
            is_unavailable=True,
            is_ready=False,
            is_blocked=False,
        )
        return report, attachments

    if not attachments:
        report = DecisionGateReport(
            status=DecisionGateStatus.UNAVAILABLE,
            reasons=["required evidence missing: no attachments"],
            missing_cells=sorted(expected_cell_ids),
            is_unavailable=True,
            is_ready=False,
            is_blocked=False,
        )
        return report, attachments

    # Check duplicate already handled upstream, but also guard here
    seen = set()
    dup = []
    for a in attachments:
        if a.cell_id in seen:
            dup.append(a.cell_id)
        seen.add(a.cell_id)
    if dup:
        report = DecisionGateReport(
            status=DecisionGateStatus.BLOCKED,
            reasons=[f"duplicate attachment cell_ids: {sorted(set(dup))}"],
            is_blocked=True,
            is_ready=False,
            is_unavailable=False,
        )
        return report, attachments

    observed_by_cell: dict[str, EvidenceAttachment] = {a.cell_id: a for a in attachments}
    missing = sorted(expected_cell_ids - set(observed_by_cell.keys()))
    extra = sorted(set(observed_by_cell.keys()) - expected_cell_ids)

    # Build expected maps
    expected_versions = {c.cell_id: c.metric_version for c in plan.planned_run_cells}
    # Unit per metric_key from primary outcomes
    unit_by_metric = {o.metric_key: o.unit for o in plan.primary_outcomes}
    # Also map cell_id to expected unit via metric_key
    expected_units = {}
    for c in plan.planned_run_cells:
        expected_units[c.cell_id] = unit_by_metric.get(c.metric_key)

    incompatible: list[str] = []
    incompat_reasons: dict[str, str] = {}
    enriched: dict[str, EvidenceAttachment] = {}

    primary_keys = {o.metric_key for o in plan.primary_outcomes}

    for cell_id, att in observed_by_cell.items():
        reason_parts = []
        is_incompat = False
        # Initialize enriched copy
        enriched_att = att

        if cell_id in expected_versions:
            exp_ver = expected_versions[cell_id]
            if att.observed_metric_version != exp_ver:
                is_incompat = True
                reason_parts.append(f"metric_version mismatch: expected {exp_ver!r} observed {att.observed_metric_version!r}")  # noqa: E501
            # Unit compatibility
            exp_unit = expected_units.get(cell_id)
            if exp_unit is None:
                is_incompat = True
                reason_parts.append(f"missing expected unit for {cell_id!r}")
            elif att.observed_unit != exp_unit:
                is_incompat = True
                reason_parts.append(f"unit mismatch: expected {exp_unit!r} observed {att.observed_unit!r}")  # noqa: E501
            # Admission check: authoritative is is_admitted
            if not is_explicitly_admitted(att):
                is_incompat = True
                reason_parts.append(f"not explicitly admitted: is_admitted={att.is_admitted!r} label={att.admission_label.value!r}")  # noqa: E501
        else:
            # extra cell will be handled separately, but also mark incompat
            pass

        # Also if observed metric_key not in primary, treat as incompat? Extra already, but keep
        if att.observed_metric_key not in primary_keys and cell_id in expected_cell_ids:  # noqa: SIM102
            # Primary metric mismatch
            if att.observed_metric_key != next((c.metric_key for c in plan.planned_run_cells if c.cell_id == cell_id), None):  # noqa: E501
                is_incompat = True
                reason_parts.append(f"metric_key mismatch for {cell_id!r}")

        if is_incompat:
            incompatible.append(cell_id)
            reason = "; ".join(reason_parts) if reason_parts else "incompatible"
            incompat_reasons[cell_id] = reason
            enriched_att = att.model_copy(update={"incompatibility_reason": reason})
        else:
            # Clear incompatibility if previously set but now compatible
            if att.incompatibility_reason is not None:
                enriched_att = att.model_copy(update={"incompatibility_reason": None})

        enriched[cell_id] = enriched_att

    # Handle extra cells as incompatible as well
    for cell_id in extra:
        # Extra cells are incompatible by definition
        if cell_id not in incompatible:
            incompatible.append(cell_id)
            incompat_reasons[cell_id] = "extra cell not in planned matrix"

    enriched_list = [enriched[cid] for cid in sorted(enriched.keys())]
    # Preserve original order sorted by cell_id for determinism

    reasons: list[str] = []
    if missing:
        reasons.append(f"missing cells: {', '.join(missing)}")
    if extra:
        reasons.append(f"extra cells: {', '.join(extra)}")
    if incompatible:
        # Include incompatibility reasons in report
        for cid in sorted(incompatible):
            if cid in incompat_reasons:
                reasons.append(f"incompatible {cid}: {incompat_reasons[cid]}")
            else:
                reasons.append(f"incompatible cells: {', '.join(sorted(incompatible))}")
                break

    if missing:
        report = DecisionGateReport(
            status=DecisionGateStatus.UNAVAILABLE,
            reasons=reasons or ["missing required evidence"],
            missing_cells=missing,
            extra_cells=extra,
            incompatible_cells=sorted(set(incompatible)),
            incompatibility_reasons=incompat_reasons,
            is_unavailable=True,
            is_ready=False,
            is_blocked=False,
        )
        return report, enriched_list
    if incompatible or extra:
        report = DecisionGateReport(
            status=DecisionGateStatus.BLOCKED,
            reasons=reasons or ["incompatible or extra evidence blocks gate"],
            missing_cells=missing,
            extra_cells=extra,
            incompatible_cells=sorted(set(incompatible)),
            incompatibility_reasons=incompat_reasons,
            is_blocked=True,
            is_ready=False,
            is_unavailable=False,
        )
        return report, enriched_list

    # Ready only if all expected cells present, compatible, and explicitly admitted
    # Already ensured no missing/incompatible/extra, but double-check admission
    # (incompatible already includes admission failures)
    report = DecisionGateReport(
        status=DecisionGateStatus.READY,
        reasons=["all planned cells have compatible admitted evidence"],
        missing_cells=[],
        extra_cells=[],
        incompatible_cells=[],
        incompatibility_reasons={},
        is_ready=True,
        is_blocked=False,
        is_unavailable=False,
    )
    return report, enriched_list


def evaluate_gate(plan: StudyPlan, attachments: list[EvidenceAttachment] | None = None) -> DecisionGateReport:  # noqa: E501
    """Evaluate whether decision gate can be evaluated."""
    report, _ = evaluate_gate_with_reasons(plan, attachments)
    return report


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

def export_plan_json(plan: StudyPlan) -> str:
    """Return deterministic JSON export."""
    data = plan.model_dump(mode="json", by_alias=True)
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)


def export_plan_yaml(plan: StudyPlan) -> str:
    """Return deterministic YAML export."""
    data = plan.model_dump(mode="json", by_alias=True)
    return yaml.safe_dump(data, sort_keys=True, allow_unicode=False)


def export_plan_csv(cells: list[PlannedRunCell]) -> str:
    """Return CSV for run matrix."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["cell_id", "arm_id", "seed_id", "policy_label", "replication_id", "metric_key", "metric_version", "replication_unit"],  # noqa: E501
    )
    writer.writeheader()
    for cell in sorted(cells, key=lambda c: c.cell_id):
        writer.writerow(
            {
                "cell_id": cell.cell_id,
                "arm_id": cell.arm_id,
                "seed_id": cell.seed_id or "",
                "policy_label": cell.policy_label,
                "replication_id": cell.replication_id,
                "metric_key": cell.metric_key,
                "metric_version": cell.metric_version,
                "replication_unit": cell.replication_unit.value,
            }
        )
    return output.getvalue()


def import_plan_json(payload: str) -> StudyPlan:
    """Import and validate a plan from JSON. Fail closed on malformed."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    try:
        plan = StudyPlan.model_validate(data)
    except Exception as exc:
        raise ValueError(f"invalid StudyPlan: {exc}") from exc
    return plan


def import_plan_yaml(payload: str) -> StudyPlan:
    """Import and validate a plan from YAML. Fail closed."""
    try:
        data = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("YAML must contain a mapping")
    try:
        plan = StudyPlan.model_validate(data)
    except Exception as exc:
        raise ValueError(f"invalid StudyPlan: {exc}") from exc
    return plan


def verify_plan(plan: StudyPlan) -> tuple[bool, str]:
    """Verify fingerprint matches canonical payload. Returns (ok, fingerprint)."""
    if plan.fingerprint is None:
        return False, plan.compute_fingerprint()
    computed = plan.compute_fingerprint()
    return computed == plan.fingerprint, computed


def planned_vs_observed_matrix(plan: StudyPlan) -> dict[str, Any]:
    """Return planned-versus-observed coverage matrix."""
    expected = {c.cell_id: c for c in plan.planned_run_cells}
    observed = {a.cell_id: a for a in plan.evidence_attachments}
    rows: list[dict[str, Any]] = []
    for cell_id in sorted(expected.keys()):
        exp = expected[cell_id]
        att = observed.get(cell_id)
        if att is None:
            rows.append(
                {
                    "cell_id": cell_id,
                    "arm_id": exp.arm_id,
                    "replication_id": exp.replication_id,
                    "expected_metric": exp.metric_key,
                    "expected_version": exp.metric_version,
                    "expected_unit": next((o.unit for o in plan.primary_outcomes if o.metric_key == exp.metric_key), None),  # noqa: E501
                    "observed": False,
                    "observed_version": None,
                    "observed_unit": None,
                    "is_admitted": None,
                    "status": "missing",
                    "incompatibility_reason": None,
                }
            )
        else:
            is_compat = att.observed_metric_version == exp.metric_version and att.observed_unit == next(  # noqa: E501
                (o.unit for o in plan.primary_outcomes if o.metric_key == exp.metric_key), None
            ) and is_explicitly_admitted(att)
            rows.append(
                {
                    "cell_id": cell_id,
                    "arm_id": exp.arm_id,
                    "replication_id": exp.replication_id,
                    "expected_metric": exp.metric_key,
                    "expected_version": exp.metric_version,
                    "expected_unit": next((o.unit for o in plan.primary_outcomes if o.metric_key == exp.metric_key), None),  # noqa: E501
                    "observed": True,
                    "observed_version": att.observed_metric_version,
                    "observed_unit": att.observed_unit,
                    "is_admitted": att.is_admitted,
                    "status": "present" if is_compat else "incompatible",
                    "incompatibility_reason": att.incompatibility_reason,
                }
            )
    for cell_id in sorted(set(observed.keys()) - set(expected.keys())):
        att = observed[cell_id]
        rows.append(
            {
                "cell_id": cell_id,
                "arm_id": None,
                "replication_id": None,
                "expected_metric": None,
                "expected_version": None,
                "expected_unit": None,
                "observed": True,
                "observed_version": att.observed_metric_version,
                "observed_unit": att.observed_unit,
                "is_admitted": att.is_admitted,
                "status": "extra",
                "incompatibility_reason": att.incompatibility_reason or "extra cell not in planned matrix",  # noqa: E501
            }
        )
    return {"rows": rows, "expected_count": len(expected), "observed_count": len(observed)}
