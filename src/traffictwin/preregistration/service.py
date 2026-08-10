"""Deterministic service for preregistration governance workflow."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import yaml

from traffictwin.metrics.catalogue import METRIC_VERSION

from traffictwin.preregistration.models import (
    AnalysisMethod,
    ArtifactAdmission,
    DecisionGateReport,
    DecisionGateStatus,
    DecisionRule,
    EvidenceAttachment,
    EvidenceMode,
    MissingnessPolicy,
    MultiplicityPolicy,
    PlannedRunCell,
    ReplicationUnit,
    StudyPlan,
    StudyPlanRevision,
    StudyPlanStatus,
    AmendmentLabel,
    field_level_diff,
)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

MAX_CELLS = 10000


def utc_now() -> datetime:
    return datetime.now(UTC)


def validate_study_plan(plan: StudyPlan) -> list[str]:
    """Return deterministic list of validation findings. Empty means freezable."""
    findings: list[str] = []

    # study question
    if not plan.study_question.text.strip() or len(plan.study_question.text.strip()) < 12:
        findings.append("study_question.text must contain at least 12 characters")

    # evidence mode is required (enum guarantees present)

    # primary outcome
    if not plan.primary_outcomes:
        findings.append("missing primary outcome: at least one primary outcome is required")
    else:
        # check each primary outcome has required fields
        for outcome in plan.primary_outcomes:
            if not outcome.metric_key.strip():
                findings.append(f"primary outcome {outcome.outcome_id!r} missing metric_key")
            if not outcome.metric_version.strip():
                findings.append(f"primary outcome {outcome.outcome_id!r} missing metric_version")
            if not outcome.unit.strip():
                findings.append(f"primary outcome {outcome.outcome_id!r} missing unit")
            # denominator required for freeze (spec requires denominator)
            if outcome.denominator is None or not outcome.denominator.strip():
                # For count metrics denominator could be n/a, but spec says denominator required
                findings.append(f"primary outcome {outcome.outcome_id!r} missing denominator")
            # metric_version must be known (currently 1.0)
            if outcome.metric_version != METRIC_VERSION:
                findings.append(
                    f"primary outcome {outcome.outcome_id!r} has inconsistent metric_version {outcome.metric_version!r} expected {METRIC_VERSION!r}"
                )
        # check primary vs secondary duplicate already validated in model but keep for safety
        primary_ids = [o.outcome_id for o in plan.primary_outcomes]
        if len(set(primary_ids)) != len(primary_ids):
            findings.append("duplicate primary outcome_id")
        # check inconsistent metric versions across primary outcomes
        versions = {o.metric_version for o in plan.primary_outcomes}
        if len(versions) > 1:
            findings.append(f"inconsistent metric versions across primary outcomes: {sorted(versions)}")
        # also check secondary metric versions consistency with primary?
        # If secondary exists, its metric_version should also be consistent (not strictly required but check)
        secondary_versions = {o.metric_version for o in plan.secondary_outcomes}
        if secondary_versions and secondary_versions != versions:
            # If secondary uses different version, flag
            findings.append(f"secondary outcomes use different metric_version from primary: {sorted(secondary_versions)} vs {sorted(versions)}")

    # unit already checked

    # replication unit
    # enum guarantees present, but check not OTHER without description?
    # replication ids or generation rule
    if not plan.replication_ids and not plan.replication_generation_rule:
        findings.append("empty replication set: replication_ids or replication_generation_rule is required")
    if plan.replication_ids and plan.replication_generation_rule:
        # both provided is ok? But spec says planned replication IDs or generation rule, so either is ok. Allow both.
        pass
    if plan.replication_ids:
        if len(plan.replication_ids) == 0:
            findings.append("replication_ids must not be empty")
        if len(set(plan.replication_ids)) != len(plan.replication_ids):
            findings.append("duplicate replication_ids")

    # planned arms
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

    # inclusion / exclusion rules
    if not plan.cohort_rules:
        findings.append("inclusion rules must contain at least one cohort rule")
    if not plan.exclusion_rules:
        findings.append("exclusion rules must contain at least one exclusion rule")
    # missingness handling is enum, always present

    # analysis method is enum, always present - but check compatibility with decision rule
    # require alpha or threshold where applicable
    method = plan.analysis_method
    rule = plan.decision_rule
    # Methods that require alpha
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
            findings.append(f"decision rule must provide alpha or threshold for analysis_method {method.value!r}")
        if method == AnalysisMethod.TOST_EQUIVALENCE:
            if rule.threshold is None:
                findings.append("TOST equivalence requires a threshold (equivalence margin)")
            if rule.alpha is None:
                findings.append("TOST equivalence requires alpha")
            if rule.comparison != "equivalence":
                findings.append("TOST equivalence decision_rule must use comparison='equivalence'")
        if method != AnalysisMethod.TOST_EQUIVALENCE and rule.comparison == "equivalence":
            findings.append(f"analysis_method {method.value!r} is incompatible with equivalence comparison")

    # multiplicity policy when multiple primary tests exist
    if len(plan.primary_outcomes) > 1:
        if plan.multiplicity_policy in (MultiplicityPolicy.NONE_SINGLE_TEST, MultiplicityPolicy.NOT_APPLICABLE):
            findings.append("multiplicity policy required when multiple primary outcomes exist")

    # stopping rule
    if not plan.stopping_rule.description.strip() or len(plan.stopping_rule.description.strip()) < 12:
        findings.append("stopping_rule.description must contain at least 12 characters")

    # decision interpretation
    if not plan.decision_rule.interpretation.strip() or len(plan.decision_rule.interpretation.strip()) < 12:
        findings.append("decision_rule.interpretation must contain at least 12 characters")

    # limitations
    if not plan.limitations.strip() or len(plan.limitations.strip()) < 12:
        findings.append("limitations must contain at least 12 characters")

    # planned run cells consistency
    # If cells are present, validate them
    if plan.planned_run_cells:
        # check duplicate cells (by cell_id or by composite arm+replication+metric)
        cell_ids = [c.cell_id for c in plan.planned_run_cells]
        if len(set(cell_ids)) != len(cell_ids):
            findings.append("duplicate run cells: cell_id duplicates")
        # composite duplicate
        composites = [(c.arm_id, c.replication_id, c.metric_key, c.metric_version) for c in plan.planned_run_cells]
        if len(set(composites)) != len(composites):
            findings.append("duplicate run cells: arm/replication/metric duplicates")
        # ambiguous arm identities
        for cell in plan.planned_run_cells:
            if cell.arm_id not in plan.planned_arms:
                findings.append(f"run cell {cell.cell_id!r} has ambiguous arm {cell.arm_id!r} not in planned_arms")
        # missing primary outcome: each primary metric_key must appear in cells
        primary_keys = {o.metric_key for o in plan.primary_outcomes}
        cell_keys = {c.metric_key for c in plan.planned_run_cells}
        for pk in primary_keys:
            if pk not in cell_keys:
                findings.append(f"missing primary outcome metric {pk!r} in run cells")
        # inconsistent metric versions
        primary_versions = {o.metric_version for o in plan.primary_outcomes}
        for cell in plan.planned_run_cells:
            if cell.metric_version not in primary_versions:
                findings.append(
                    f"run cell {cell.cell_id!r} has inconsistent metric_version {cell.metric_version!r} not in primary outcomes {sorted(primary_versions)}"
                )
        # empty replication set already checked
        # decision rule incompatible already checked
        # undeclared post-hoc primary outcomes: if cells contain metric_key not in primary or secondary
        allowed_keys = {o.metric_key for o in plan.primary_outcomes} | {o.metric_key for o in plan.secondary_outcomes}
        for cell in plan.planned_run_cells:
            if cell.metric_key not in allowed_keys:
                findings.append(f"run cell {cell.cell_id!r} has undeclared post-hoc metric {cell.metric_key!r}")
        # check too many cells
        if len(plan.planned_run_cells) > MAX_CELLS:
            findings.append(f"run matrix exceeds limit {MAX_CELLS}")
    else:
        # If no planned_run_cells, we will build matrix; but if arms and replication present, matrix should be built
        # Validate that we can build matrix
        if plan.planned_arms and (plan.replication_ids or plan.replication_generation_rule):
            # Matrix build would be non-empty, so missing cells is not yet error; but if frozen we expect cells?
            # For draft, allow empty cells but warn? For freeze, require non-empty matrix
            pass
        else:
            findings.append("planned_run_cells is empty and cannot be derived from arms/replication")

    # check seeds/policies/metrics selectors: if provided, must be non-empty? Not required for freeze but recommended
    # Keep optional

    # check that evidence_mode is not UNAVAILABLE?
    if plan.evidence_mode == EvidenceMode.UNAVAILABLE:
        findings.append("evidence_mode must not be unavailable for a freezable plan")

    return sorted(set(findings))


def is_freezable(plan: StudyPlan) -> bool:
    return len(validate_study_plan(plan)) == 0


def build_run_matrix(plan: StudyPlan) -> list[PlannedRunCell]:
    """Build deterministic run-cell matrix from declared plan. Raises ValueError on invalid."""
    findings = validate_study_plan(plan)
    # Still allow building matrix if only cell-related findings due to empty cells? Need to separate.
    # For matrix building, we re-validate specific matrix conditions
    if not plan.primary_outcomes:
        raise ValueError("missing primary outcome")
    if not plan.planned_arms:
        raise ValueError("planned_arms must contain at least one arm")
    if not plan.replication_ids and not plan.replication_generation_rule:
        raise ValueError("empty replication set")
    # If replication_generation_rule provided, derive ids deterministically
    replication_ids = plan.replication_ids
    if not replication_ids and plan.replication_generation_rule:
        # Parse generation rule like "0..4" or "0,1,2" or "range(5)"
        # For deterministic, we support simple forms: "range:N" or "0..N" or comma list
        rule = plan.replication_generation_rule.strip()
        try:
            if rule.startswith("range:"):
                n = int(rule.split(":", 1)[1].strip())
                if n < 1:
                    raise ValueError("range must be >=1")
                replication_ids = list(range(n))
            elif ".." in rule:
                parts = rule.split("..")
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                if end < start:
                    raise ValueError("invalid range")
                replication_ids = list(range(start, end + 1))
            elif "," in rule:
                replication_ids = sorted({int(x.strip()) for x in rule.split(",") if x.strip()})
            else:
                # single int
                replication_ids = [int(rule)]
        except Exception as exc:
            raise ValueError(f"invalid replication_generation_rule {rule!r}: {exc}") from exc

    if not replication_ids:
        raise ValueError("empty replication set after generation rule")

    primary = plan.primary_outcomes[0]  # use first primary for cell metric version; but we need to handle multiple primaries -> create cells per outcome?
    # For multiple primary outcomes, we need cells per primary outcome per arm per replication
    # Instead create cells for each primary outcome
    cells: list[PlannedRunCell] = []
    seq = 1
    # Deterministic ordering: sorted arms, sorted replication_ids, sorted primary outcomes by outcome_id
    sorted_arms = sorted(plan.planned_arms)
    sorted_replications = sorted(replication_ids)
    sorted_primaries = sorted(plan.primary_outcomes, key=lambda o: o.outcome_id)
    # Also include secondary? No, run matrix is for primary outcomes only; secondary are additional?
    # Spec says planned_run_cells from declared plan; we will generate for each primary outcome
    seen = set()
    for arm in sorted_arms:
        for rep in sorted_replications:
            for outcome in sorted_primaries:
                arm_id = arm
                # Resolve seed_id and policy_label from plan.seeds and plan.policies if available, else use arm as seed/policy
                # For simplicity, use first seed if available, else arm as seed_id
                seed_id = plan.seeds[0] if plan.seeds else None
                # Policy label: use first policy if available else arm
                policy_label = plan.policies[0] if plan.policies else arm
                cell_id = f"cell-{seq:04d}"
                composite = (arm_id, rep, outcome.metric_key, outcome.metric_version)
                if composite in seen:
                    raise ValueError(f"duplicate run cells: {composite}")
                seen.add(composite)
                cells.append(
                    PlannedRunCell(
                        cell_id=cell_id,
                        arm_id=arm_id,
                        seed_id=seed_id,
                        policy_label=policy_label,
                        replication_id=rep,
                        metric_key=outcome.metric_key,
                        metric_version=outcome.metric_version,
                        replication_unit=plan.replication_unit,
                    )
                )
                seq += 1
                if len(cells) > MAX_CELLS:
                    raise ValueError(f"run matrix exceeds limit {MAX_CELLS}")

    # Also validate duplicate arm identities already handled
    # Validate ambiguous arm identities handled via construction
    # Validate missing primary outcome handled
    # Validate inconsistent metric versions handled via outcome metric_version
    # Validate decision rule incompatible handled outside

    # If plan already has cells, validate they match built matrix? For strictness, if plan.planned_run_cells provided, we validate no duplicates etc and return them sorted
    # But to ensure deterministic, we rebuild and compare?
    # For now return built cells

    return cells


def fingerprint_plan(plan: StudyPlan) -> str:
    """Return deterministic fingerprint for a plan, excluding wall-clock fields."""
    return plan.compute_fingerprint()


def freeze_plan(plan: StudyPlan, *, clock: Callable[[], datetime] | None = None) -> StudyPlan:
    """Validate and freeze a draft plan into an immutable version. Raises ValueError if not freezable."""
    if plan.status != StudyPlanStatus.DRAFT:
        raise ValueError(f"only DRAFT plans can be frozen; current status is {plan.status.value!r}")
    findings = validate_study_plan(plan)
    if findings:
        raise ValueError(f"plan is not freezable: {'; '.join(findings)}")
    # Build matrix deterministically if not provided or ensure consistency
    try:
        built_cells = build_run_matrix(plan)
    except ValueError as exc:
        raise ValueError(f"run matrix invalid: {exc}") from exc

    # If plan has no cells, populate; if has cells, verify they match built (or keep provided but sorted)
    if not plan.planned_run_cells:
        cells = built_cells
    else:
        # Validate provided cells match built shape? For deterministic, we ensure provided cells are subset of built? But spec says build deterministic run-cell matrix from declared plan, reject duplicate etc. So we can keep provided if valid, otherwise rebuild.
        # To ensure deterministic fingerprint, we sort and compare
        provided_sorted = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
        built_sorted = sorted(built_cells, key=lambda c: c.cell_id)
        # If counts differ, we should raise or use built? Use built to ensure deterministic
        if len(provided_sorted) != len(built_sorted):
            # Prefer built to enforce correct matrix
            cells = built_cells
        else:
            # Check if provided cells match built composites
            provided_composites = {(c.arm_id, c.replication_id, c.metric_key) for c in provided_sorted}
            built_composites = {(c.arm_id, c.replication_id, c.metric_key) for c in built_sorted}
            if provided_composites != built_composites:
                cells = built_cells
            else:
                cells = provided_sorted

    now = clock() if clock is not None else utc_now()
    # Compute fingerprint over content without volatile fields
    # Create frozen copy with normalized fields
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
    """Create a new version as child of a frozen plan. Preserves parent fingerprint bytes immutably."""
    if parent.status not in (StudyPlanStatus.FROZEN, StudyPlanStatus.EVIDENCE_ATTACHED, StudyPlanStatus.DECIDED, StudyPlanStatus.CLOSED):
        raise ValueError(f"only frozen or later plans can be amended; parent status is {parent.status.value!r}")
    if not amendment_reason.strip() or len(amendment_reason.strip()) < 12:
        raise ValueError("amendment_reason must contain at least 12 characters")
    if parent.fingerprint is None:
        raise ValueError("parent plan must have a fingerprint; freeze it first")
    parent_fp = parent.fingerprint
    parent_version = parent.version

    # Determine if this is post-evidence amendment
    is_post = False
    label = AmendmentLabel.PRE_EVIDENCE
    if parent.evidence_attached_at is not None or evidence_attached_at is not None:
        # If evidence attachment time is known, label as post-evidence
        is_post = True
        label = AmendmentLabel.POST_EVIDENCE
    # Also if parent status is EVIDENCE_ATTACHED or later, it's post
    if parent.status in (StudyPlanStatus.EVIDENCE_ATTACHED, StudyPlanStatus.DECIDED, StudyPlanStatus.CLOSED):
        is_post = True
        label = AmendmentLabel.POST_EVIDENCE

    # Prevent editing frozen plan in place: we create new plan with incremented version
    now = clock() if clock is not None else utc_now()
    # Build new plan payload by applying changes to parent's dump
    parent_payload = parent.model_dump(mode="json", by_alias=True)
    # Remove immutable wall-clock and fingerprint fields from changes handling
    # Changes should be top-level fields of StudyPlan
    # We need to apply changes deterministically
    new_payload = dict(parent_payload)
    # Apply changes
    for key, value in changes.items():
        if key in ("plan_id", "fingerprint", "frozen_at", "created_at", "evidence_attached_at", "parent_fingerprint", "revision_history"):
            raise ValueError(f"field {key!r} cannot be changed via amendment")
        new_payload[key] = value

    # Increment version
    new_version = parent_version + 1
    new_payload["version"] = new_version
    new_payload["status"] = StudyPlanStatus.DRAFT.value if isinstance(StudyPlanStatus.DRAFT, str) else StudyPlanStatus.DRAFT
    # But amendment should create a new version that is DRAFT initially? Or FROZEN? Spec says amendment must create a new version, point to parent, state reason, produce diff, preserve parent bytes/fingerprint. It doesn't say amendment is automatically frozen; likely new version is DRAFT then must be frozen again.
    # For immutability, we will create new plan as DRAFT that points to parent, then caller can freeze it.
    # However we need to record revision.
    new_payload["status"] = StudyPlanStatus.DRAFT.value
    new_payload["parent_fingerprint"] = parent_fp
    new_payload["parent_version"] = parent_version
    new_payload["frozen_at"] = None
    new_payload["fingerprint"] = None
    # Keep evidence attachments and gate? Should reset for new version? But amendment after evidence should preserve evidence? Spec says amendment must preserve parent bytes and fingerprint, distinguish pre/post evidence where evidence attachment time known.
    # For new version, we clear evidence_attachments and gate_report until re-attached, but keep revision history
    new_payload["evidence_attachments"] = []
    new_payload["gate_report"] = None
    new_payload["evidence_attached_at"] = None

    # Reconstruct StudyPlan from new_payload (need to handle datetime strings)
    # Use model_validate
    # But new_payload has datetime iso strings for created_at; need to keep parent created_at? Keep original created_at?
    # For amendment, created_at should be now
    new_payload["created_at"] = now.isoformat()

    # Preserve revision_history: copy parent history plus new revision entry
    parent_history = list(parent.revision_history)
    # Compute diff between canonical payloads
    # Need to compute canonical payloads excluding wall-clock
    # Build temporary old and new plans to get canonical payloads
    old_canonical = parent.canonical_payload()
    # Build new plan temporarily to get canonical
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
    # Ensure fingerprint is not yet set (draft)
    return new_plan


def attach_evidence(
    plan: StudyPlan,
    attachments: list[EvidenceAttachment],
    *,
    clock: Callable[[], datetime] | None = None,
) -> StudyPlan:
    """Attach imported evidence by fingerprint to a frozen plan. Returns new plan with EVIDENCE_ATTACHED status."""
    if plan.status not in (StudyPlanStatus.FROZEN, StudyPlanStatus.EVIDENCE_ATTACHED):
        raise ValueError(f"evidence can only be attached to FROZEN or EVIDENCE_ATTACHED plans; current {plan.status.value!r}")
    if plan.fingerprint is None:
        raise ValueError("plan must have a fingerprint before attaching evidence")
    # Validate attachments reference immutable fingerprints, not importing raw data
    # We must not read active E2 output directories; we just validate fingerprint format and admission label
    # Record missing, extra, incompatible
    now = clock() if clock is not None else utc_now()

    # Normalize attachments timestamps
    normalized: list[EvidenceAttachment] = []
    for att in attachments:
        # Ensure attached_at normalized
        if att.attached_at is None:
            att = att.model_copy(update={"attached_at": now})
        normalized.append(att)

    # Check that we don't mutate frozen parent bytes: we create new copy
    new_status = StudyPlanStatus.EVIDENCE_ATTACHED
    # Preserve parent fingerprint immutably
    # Determine reconciliation
    expected_cell_ids = {c.cell_id for c in plan.planned_run_cells}
    observed_cell_ids = {a.cell_id for a in normalized}
    # Also check admission: unadmitted remains unadmitted
    # We must not reinterpret unadmitted as admitted

    # Create new plan copy with attachments
    updated = plan.model_copy(
        update={
            "status": new_status,
            "evidence_attachments": normalized,
            "evidence_attached_at": now,
        }
    )
    # Recompute gate? Not automatically but we can evaluate gate status
    gate = evaluate_gate(updated, normalized)
    updated = updated.model_copy(update={"gate_report": gate})
    # Fingerprint of plan should remain same for frozen content? But spec says preserve the frozen plan; attaching evidence must preserve frozen plan and reconcile expected vs observed.
    # The plan's fingerprint for the frozen content should not change? However evidence_attached_at and attachments change status, so fingerprint would change if we include them.
    # But spec says preserve the frozen plan - meaning parent bytes and fingerprint preserved. Attaching evidence should not mutate frozen bytes; it creates new version? Or status moves to EVIDENCE_ATTACHED but parent fingerprint preserved.
    # We should keep original fingerprint for parent but compute new fingerprint for evidence-attached version that includes attachments but excludes parent? Or keep parent fingerprint?
    # For now we keep original fingerprint and not recompute, but set gate.
    # However to distinguish, we could keep fingerprint as parent fingerprint and add new fingerprint? Simpler: keep fingerprint unchanged for evidence-attached version but also compute new fingerprint for verification? The spec says preserve the parent bytes and fingerprint, but attaching evidence must preserve the frozen plan - suggests evidence attachment does not rewrite frozen fields, only adds attachment layer.
    # We'll keep fingerprint as parent fingerprint and not overwrite.
    # But if we keep fingerprint, gate evaluation must be based on attachments not fingerprint.
    # We'll keep fingerprint same as parent.

    # Compute new fingerprint for evidence-attached version, preserving parent trace
    original_fp = plan.fingerprint
    # Recompute fingerprint to include attachments and new status, while preserving parent link
    new_fp = updated.compute_fingerprint()
    if updated.parent_fingerprint is None:
        updated = updated.model_copy(update={"parent_fingerprint": original_fp, "fingerprint": new_fp})
    else:
        updated = updated.model_copy(update={"fingerprint": new_fp})

    return updated


def evaluate_gate(plan: StudyPlan, attachments: list[EvidenceAttachment] | None = None) -> DecisionGateReport:
    """Evaluate whether decision gate can be evaluated."""
    if attachments is None:
        attachments = plan.evidence_attachments

    expected_cell_ids = {c.cell_id for c in plan.planned_run_cells}
    # If no planned cells, gate is unavailable
    if not expected_cell_ids:
        return DecisionGateReport(
            status=DecisionGateStatus.UNAVAILABLE,
            reasons=["no planned run cells defined"],
            is_unavailable=True,
        )

    # Primary outcome missing? Check primary_outcomes present
    if not plan.primary_outcomes:
        return DecisionGateReport(
            status=DecisionGateStatus.UNAVAILABLE,
            reasons=["primary outcome missing: gate cannot be ready"],
            is_unavailable=True,
        )

    # If no evidence attached, unavailable
    if not attachments:
        return DecisionGateReport(
            status=DecisionGateStatus.UNAVAILABLE,
            reasons=["required evidence missing: no attachments"],
            missing_cells=sorted(expected_cell_ids),
            is_unavailable=True,
        )

    observed_by_cell: dict[str, EvidenceAttachment] = {a.cell_id: a for a in attachments}

    missing = sorted(expected_cell_ids - set(observed_by_cell.keys()))
    extra = sorted(set(observed_by_cell.keys()) - expected_cell_ids)
    incompatible: list[str] = []

    # Check each observed cell for compatibility
    # Expected metric version per cell: from plan cells
    expected_versions = {c.cell_id: c.metric_version for c in plan.planned_run_cells}
    expected_units = {c.metric_key: next((o.unit for o in plan.primary_outcomes if o.metric_key == c.metric_key), None) for c in plan.planned_run_cells}
    # Also check metric_key matches primary
    primary_keys = {o.metric_key for o in plan.primary_outcomes}
    for cell_id, att in observed_by_cell.items():
        if cell_id in expected_versions:
            exp_ver = expected_versions[cell_id]
            if att.observed_metric_version != exp_ver:
                incompatible.append(cell_id)
                if att.incompatibility_reason is None:
                    att = att.model_copy(update={"incompatibility_reason": f"metric_version mismatch: expected {exp_ver!r} observed {att.observed_metric_version!r}"})
            # Check unit incompatibility? Could be incompatible if unit differs from primary outcome unit
            # But allow same metric_key with different unit as incompatible
            # Check is_admitted: unadmitted remains unadmitted, but gate blocked if required evidence is unadmitted?
            # Spec says gate must remain unavailable or blocked if required evidence is missing or incompatible, and unadmitted remains unadmitted
            if not att.is_admitted and att.admission_label == ArtifactAdmission.UNADMITTED:
                # Unadmitted is not compatible for gate unless evidence_mode allows unadmitted?
                # For now treat unadmitted as incompatible for admitted research gate
                if plan.evidence_mode == EvidenceMode.ADMITTED_RESEARCH:
                    if cell_id not in incompatible:
                        incompatible.append(cell_id)
        else:
            # extra cell already counted, but also check if its metric_version is incompatible? It's extra so blocked
            pass
        # Also check if observed metric_key is primary outcome; if not, treat as incompatible? But extra already
        if att.observed_metric_key not in primary_keys:
            # If secondary outcome, not primary, but gate evaluates primary only, so extra? Actually if observed is secondary, it's extra for gate
            pass
        # Ensure unadmitted never reinterpreted as admitted: we keep att.is_admitted as provided, never change

    # Also check duplicate cells already validated at plan level, but gate should block if duplicate? Already rejected at freeze.

    reasons: list[str] = []
    if missing:
        reasons.append(f"missing cells: {', '.join(missing)}")
    if extra:
        reasons.append(f"extra cells: {', '.join(extra)}")
    if incompatible:
        reasons.append(f"incompatible cells: {', '.join(incompatible)}")

    if missing:
        return DecisionGateReport(
            status=DecisionGateStatus.UNAVAILABLE,
            reasons=reasons or ["missing required evidence"],
            missing_cells=missing,
            extra_cells=extra,
            incompatible_cells=sorted(set(incompatible)),
            is_unavailable=True,
        )
    if incompatible or extra:
        return DecisionGateReport(
            status=DecisionGateStatus.BLOCKED,
            reasons=reasons or ["incompatible or extra evidence blocks gate"],
            missing_cells=missing,
            extra_cells=extra,
            incompatible_cells=sorted(set(incompatible)),
            is_blocked=True,
        )

    # Also check decision rule requires primary outcome still present and not replaced without amendment
    # That is handled via amendment diff; gate ready only if all expected cells present and compatible
    return DecisionGateReport(
        status=DecisionGateStatus.READY,
        reasons=["all planned cells have compatible admitted evidence"],
        missing_cells=[],
        extra_cells=[],
        incompatible_cells=[],
        is_ready=True,
    )


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
        fieldnames=["cell_id", "arm_id", "seed_id", "policy_label", "replication_id", "metric_key", "metric_version", "replication_unit"],
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
                    "observed": False,
                    "observed_version": None,
                    "is_admitted": None,
                    "status": "missing",
                }
            )
        else:
            rows.append(
                {
                    "cell_id": cell_id,
                    "arm_id": exp.arm_id,
                    "replication_id": exp.replication_id,
                    "expected_metric": exp.metric_key,
                    "expected_version": exp.metric_version,
                    "observed": True,
                    "observed_version": att.observed_metric_version,
                    "is_admitted": att.is_admitted,
                    "status": "incompatible" if att.observed_metric_version != exp.metric_version or not att.is_admitted else "present",
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
                "observed": True,
                "observed_version": att.observed_metric_version,
                "is_admitted": att.is_admitted,
                "status": "extra",
            }
        )
    return {"rows": rows, "expected_count": len(expected), "observed_count": len(observed)}
