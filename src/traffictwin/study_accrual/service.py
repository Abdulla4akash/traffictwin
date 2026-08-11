"""Deterministic accrual monitoring — never mutates the plan."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from traffictwin.preregistration.models import (
    EvidenceAttachment,
    PlannedRunCell,
    StudyPlan,
    StudyPlanStatus,
    is_explicitly_admitted,
)
from traffictwin.preregistration.service import evaluate_gate_with_reasons
from traffictwin.study_accrual.models import (
    AccrualCellEntry,
    AccrualCellStatus,
    AccrualDeviation,
    AccrualDeviationCode,
    AccrualReport,
    AccrualReviewHandoff,
    AccrualReviewState,
    AccrualSnapshot,
    AccrualTimelineEntry,
    AccrualWarning,
    StoppingProgress,
    _normalise_timestamp,
)

MAX_CELLS = 10000


def _expected_cell_map(plan: StudyPlan) -> dict[str, PlannedRunCell]:
    return {c.cell_id: c for c in plan.planned_run_cells}


def _expected_unit_map(plan: StudyPlan) -> dict[str, str]:
    return {o.metric_key: o.unit for o in plan.primary_outcomes}


def _detect_duplicate_attachments(
    attachments: list[EvidenceAttachment],
) -> set[str]:
    seen: set[str] = set()
    dups: set[str] = set()
    for att in attachments:
        if att.cell_id in seen:
            dups.add(att.cell_id)
        seen.add(att.cell_id)
    return dups


def _first_observed_time(
    attachment: EvidenceAttachment | None,
) -> str | None:
    if attachment is None or attachment.attached_at is None:
        return None
    return _normalise_timestamp(attachment.attached_at)


def _latest_decision(
    attachment: EvidenceAttachment | None,
    review_state: AccrualReviewState | None,
) -> str | None:
    if attachment is None:
        return None
    if review_state == AccrualReviewState.REJECTED:
        return "rejected"
    if review_state == AccrualReviewState.WITHDRAWN:
        return "withdrawn"
    if (
        attachment.incompatibility_reason is not None
        and "not explicitly admitted" not in attachment.incompatibility_reason.lower()
    ):
        return f"incompatible: {attachment.incompatibility_reason}"
    if is_explicitly_admitted(attachment):
        return "admitted"
    return "unadmitted"


def _compatibility_label(
    plan: StudyPlan,
    cell: PlannedRunCell | None,
    attachment: EvidenceAttachment | None,
) -> str:
    if attachment is None:
        return "missing"
    if cell is None:
        return "extra"
    exp_ver = cell.metric_version
    exp_unit = _expected_unit_map(plan).get(cell.metric_key)
    if attachment.observed_metric_version != exp_ver:
        return f"incompatible: metric_version mismatch expected {exp_ver!r} observed {attachment.observed_metric_version!r}"  # noqa: E501
    if exp_unit is not None and attachment.observed_unit != exp_unit:
        return f"incompatible: unit mismatch expected {exp_unit!r} observed {attachment.observed_unit!r}"  # noqa: E501
    if attachment.observed_metric_key != cell.metric_key:
        return f"incompatible: metric_key mismatch expected {cell.metric_key!r} observed {attachment.observed_metric_key!r}"  # noqa: E501
    if (
        attachment.incompatibility_reason is not None
        and "not explicitly admitted" not in attachment.incompatibility_reason.lower()
    ):
        return f"incompatible: {attachment.incompatibility_reason}"  # noqa: E501
    return "compatible"


def _is_incompatible(
    plan: StudyPlan,
    cell: PlannedRunCell | None,
    attachment: EvidenceAttachment | None,
) -> tuple[bool, str | None]:
    if attachment is None or cell is None:
        return False, None
    exp_ver = cell.metric_version
    if attachment.observed_metric_version != exp_ver:
        return (
            True,
            f"metric_version mismatch expected {exp_ver!r} observed {attachment.observed_metric_version!r}",  # noqa: E501
        )  # noqa: E501
    exp_unit = _expected_unit_map(plan).get(cell.metric_key)
    if exp_unit is not None and attachment.observed_unit != exp_unit:
        return True, f"unit mismatch expected {exp_unit!r} observed {attachment.observed_unit!r}"  # noqa: E501
    if attachment.observed_metric_key != cell.metric_key:
        return (
            True,
            f"metric_key mismatch expected {cell.metric_key!r} observed {attachment.observed_metric_key!r}",  # noqa: E501
        )  # noqa: E501
    if (
        attachment.incompatibility_reason is not None
        and "not explicitly admitted" not in attachment.incompatibility_reason.lower()
    ):
        return True, attachment.incompatibility_reason
    return False, None


def _admission_state_label(attachment: EvidenceAttachment | None) -> str:
    if attachment is None:
        return "none"
    if is_explicitly_admitted(attachment):
        return f"admitted ({attachment.admission_label.value})"
    return f"unadmitted ({attachment.admission_label.value})"


def _attachment_state_label(attachment: EvidenceAttachment | None, is_duplicate: bool) -> str:
    if attachment is None:
        return "missing"
    if is_duplicate:
        return "duplicate_attached"
    return "attached"


def _verify_plan_fingerprint(plan: StudyPlan) -> str | None:
    """Return error message if fingerprint invalid, else None."""
    if plan.status == StudyPlanStatus.DRAFT:
        return None
    if plan.fingerprint is None:
        return "frozen StudyPlan fingerprint is missing"
    computed = plan.compute_fingerprint()
    if plan.fingerprint != computed:
        return "frozen StudyPlan fingerprint does not match current semantic payload"
    return None


def _verify_evidence_state_fingerprint(plan: StudyPlan) -> str | None:
    if not plan.evidence_attachments:
        return None
    if plan.evidence_state_fingerprint is None:
        return "evidence_state_fingerprint is missing for plan with attachments"
    computed = plan.compute_evidence_state_fingerprint()
    if plan.evidence_state_fingerprint != computed:
        return "evidence_state_fingerprint does not match current evidence attachments"
    return None


def _derive_replicate_counts(
    plan: StudyPlan, attachment_by_cell: dict[str, EvidenceAttachment], duplicate_ids: set[str]
) -> tuple[int, int]:
    planned_ids = {c.replication_id for c in plan.planned_run_cells}
    planned_count = len(planned_ids)
    # Observed: distinct replication_id where at least one expected cell for that replicate has an attachment  # noqa: E501
    # and that attachment is not duplicate-blocked? For duplicate, still consider observed but blocked.  # noqa: E501
    # Use expected cell map to find replication_id for each cell_id
    cell_map = _expected_cell_map(plan)
    observed_ids: set[int] = set()
    for cell_id, att in attachment_by_cell.items():  # noqa: B007
        if cell_id in duplicate_ids:
            # Duplicate still counts as observed for replicate, but does not prove non-duplicate completion  # noqa: E501
            # We count it but it will be blocked separately
            if cell_id in cell_map:
                observed_ids.add(cell_map[cell_id].replication_id)
            continue
        if cell_id in cell_map:
            observed_ids.add(cell_map[cell_id].replication_id)
        # Extra cells do not contribute (no planned replication_id)
    observed_count = len(observed_ids)
    return planned_count, observed_count


def build_accrual_report(
    plan: StudyPlan,
    *,
    review_handoff: AccrualReviewHandoff | None = None,
) -> AccrualReport:
    """Build deterministic accrual report without mutating the plan.

    - Verifies frozen plan and evidence-state fingerprints (fail-closed).
    - Does not admit evidence automatically.
    - Does not change plan status.
    - Fail-closed bounded inputs.
    - Order-independent fingerprint.
    """
    if len(plan.planned_run_cells) > MAX_CELLS:
        raise ValueError(f"planned_run_cells exceeds limit {MAX_CELLS}")
    if len(plan.evidence_attachments) > MAX_CELLS:
        raise ValueError(f"evidence_attachments exceeds limit {MAX_CELLS}")

    # B1 verification
    fp_error = _verify_plan_fingerprint(plan)
    if fp_error is not None:
        snapshot = AccrualSnapshot(
            plan_id=plan.plan_id,
            plan_fingerprint=plan.fingerprint,
            plan_version=plan.version,
            plan_status=plan.status.value,
            expected_count=len(plan.planned_run_cells),
            attached_count=0,
            admitted_count=0,
            rejected_count=0,
            incompatible_count=0,
            extra_count=0,
            remaining_count=len(plan.planned_run_cells),
            complete_count=0,
            attached_unadmitted_count=0,
            planned_missing_count=len(plan.planned_run_cells),
            withdrawn_count=0,
            duplicate_count=0,
            post_evidence_amendment_count=sum(
                1 for r in plan.revision_history if r.is_post_evidence
            ),
            power_plan_fingerprint=plan.power_plan_fingerprint,
            planned_replicate_count=0,
            observed_replicate_count=0,
        )
        stopping = StoppingProgress(
            max_replicates=plan.stopping_rule.max_replicates,
            interim_looks_allowed=plan.stopping_rule.interim_looks,
            interim_looks_used=review_handoff.interim_looks_used
            if review_handoff and review_handoff.interim_looks_used is not None
            else 0,
            planned_replicate_count=0,
            observed_replicate_count=0,
            expected_count=len(plan.planned_run_cells),
            attached_count=0,
            admitted_count=0,
            remaining=len(plan.planned_run_cells),
            is_overrun=False,
            overrun_by=0,
            status="unavailable: plan fingerprint mismatch",
        )
        report = AccrualReport(
            snapshot=snapshot,
            cells=[],
            deviations=[],
            warnings=[
                AccrualWarning(
                    code="FINGERPRINT_MISMATCH",
                    message=fp_error,
                    severity="blocked",
                )
            ],
            stopping_progress=stopping,
            timeline=[],
            amendment_history=[
                r.model_dump(mode="json")
                for r in sorted(plan.revision_history, key=lambda x: x.version)
            ],
            blockers=[fp_error],
            power_plan_fingerprint=plan.power_plan_fingerprint,
            is_unavailable=True,
            unavailable_reason=fp_error,
        )
        report = report.model_copy(update={"fingerprint": report.compute_fingerprint()})
        return report

    # B2 evidence-state verification (only if attachments present)
    ev_error = _verify_evidence_state_fingerprint(plan)
    if ev_error is not None:
        snapshot = AccrualSnapshot(
            plan_id=plan.plan_id,
            plan_fingerprint=plan.fingerprint,
            plan_version=plan.version,
            plan_status=plan.status.value,
            expected_count=len(plan.planned_run_cells),
            attached_count=0,
            admitted_count=0,
            rejected_count=0,
            incompatible_count=0,
            extra_count=0,
            remaining_count=len(plan.planned_run_cells),
            complete_count=0,
            attached_unadmitted_count=0,
            planned_missing_count=len(plan.planned_run_cells),
            withdrawn_count=0,
            duplicate_count=0,
            post_evidence_amendment_count=sum(
                1 for r in plan.revision_history if r.is_post_evidence
            ),
            power_plan_fingerprint=plan.power_plan_fingerprint,
            planned_replicate_count=0,
            observed_replicate_count=0,
        )
        stopping = StoppingProgress(
            max_replicates=plan.stopping_rule.max_replicates,
            interim_looks_allowed=plan.stopping_rule.interim_looks,
            interim_looks_used=review_handoff.interim_looks_used
            if review_handoff and review_handoff.interim_looks_used is not None
            else 0,
            planned_replicate_count=0,
            observed_replicate_count=0,
            expected_count=len(plan.planned_run_cells),
            attached_count=0,
            admitted_count=0,
            remaining=len(plan.planned_run_cells),
            is_overrun=False,
            overrun_by=0,
            status="unavailable: evidence-state fingerprint mismatch",
        )
        report = AccrualReport(
            snapshot=snapshot,
            cells=[],
            deviations=[],
            warnings=[
                AccrualWarning(
                    code="EVIDENCE_STATE_MISMATCH",
                    message=ev_error,
                    severity="blocked",
                )
            ],
            stopping_progress=stopping,
            timeline=[],
            amendment_history=[
                r.model_dump(mode="json")
                for r in sorted(plan.revision_history, key=lambda x: x.version)
            ],
            blockers=[ev_error],
            power_plan_fingerprint=plan.power_plan_fingerprint,
            is_unavailable=True,
            unavailable_reason=ev_error,
        )
        report = report.model_copy(update={"fingerprint": report.compute_fingerprint()})
        return report

    # Unavailable draft/no cells
    if plan.status == StudyPlanStatus.DRAFT:
        snapshot = AccrualSnapshot(
            plan_id=plan.plan_id,
            plan_fingerprint=None,
            plan_version=plan.version,
            plan_status=plan.status.value,
            expected_count=len(plan.planned_run_cells),
            attached_count=0,
            admitted_count=0,
            rejected_count=0,
            incompatible_count=0,
            extra_count=0,
            remaining_count=len(plan.planned_run_cells),
            complete_count=0,
            attached_unadmitted_count=0,
            planned_missing_count=len(plan.planned_run_cells),
            withdrawn_count=0,
            duplicate_count=0,
            post_evidence_amendment_count=sum(
                1 for r in plan.revision_history if r.is_post_evidence
            ),
            power_plan_fingerprint=plan.power_plan_fingerprint,
            planned_replicate_count=0,
            observed_replicate_count=0,
        )
        stopping = StoppingProgress(
            max_replicates=plan.stopping_rule.max_replicates,
            interim_looks_allowed=plan.stopping_rule.interim_looks,
            interim_looks_used=review_handoff.interim_looks_used
            if review_handoff and review_handoff.interim_looks_used is not None
            else 0,
            planned_replicate_count=0,
            observed_replicate_count=0,
            expected_count=len(plan.planned_run_cells),
            attached_count=0,
            admitted_count=0,
            remaining=len(plan.planned_run_cells),
            is_overrun=False,
            overrun_by=0,
            status="unavailable: plan not frozen",
        )
        report = AccrualReport(
            snapshot=snapshot,
            cells=[],
            deviations=[],
            warnings=[
                AccrualWarning(
                    code="PLAN_NOT_FROZEN",
                    message="StudyPlan is not frozen; accrual is unavailable before freeze.",
                    severity="blocked",
                )
            ],
            stopping_progress=stopping,
            timeline=[],
            amendment_history=[
                r.model_dump(mode="json")
                for r in sorted(plan.revision_history, key=lambda x: x.version)
            ],
            blockers=["Plan must be frozen before accrual can be monitored."],
            power_plan_fingerprint=plan.power_plan_fingerprint,
            is_unavailable=True,
            unavailable_reason="Plan status is DRAFT; frozen identity required.",
        )
        report = report.model_copy(update={"fingerprint": report.compute_fingerprint()})
        return report

    if not plan.planned_run_cells:
        snapshot = AccrualSnapshot(
            plan_id=plan.plan_id,
            plan_fingerprint=plan.fingerprint,
            plan_version=plan.version,
            plan_status=plan.status.value,
            expected_count=0,
            attached_count=0,
            admitted_count=0,
            rejected_count=0,
            incompatible_count=0,
            extra_count=len(plan.evidence_attachments),
            remaining_count=0,
            complete_count=0,
            attached_unadmitted_count=0,
            planned_missing_count=0,
            withdrawn_count=0,
            duplicate_count=0,
            post_evidence_amendment_count=sum(
                1 for r in plan.revision_history if r.is_post_evidence
            ),
            power_plan_fingerprint=plan.power_plan_fingerprint,
            planned_replicate_count=0,
            observed_replicate_count=0,
        )
        stopping = StoppingProgress(
            max_replicates=plan.stopping_rule.max_replicates,
            interim_looks_allowed=plan.stopping_rule.interim_looks,
            interim_looks_used=review_handoff.interim_looks_used
            if review_handoff and review_handoff.interim_looks_used is not None
            else 0,
            planned_replicate_count=0,
            observed_replicate_count=0,
            expected_count=0,
            attached_count=0,
            admitted_count=0,
            remaining=0,
            is_overrun=False,
            overrun_by=0,
            status="unavailable: no planned run cells",
        )
        report = AccrualReport(
            snapshot=snapshot,
            cells=[],
            deviations=[],
            warnings=[
                AccrualWarning(
                    code="NO_PLANNED_CELLS",
                    message="StudyPlan has no planned run cells; accrual cannot be evaluated.",
                    severity="blocked",
                )
            ],
            stopping_progress=stopping,
            timeline=[],
            amendment_history=[
                r.model_dump(mode="json")
                for r in sorted(plan.revision_history, key=lambda x: x.version)
            ],
            blockers=["No planned run cells defined."],
            power_plan_fingerprint=plan.power_plan_fingerprint,
            is_unavailable=True,
            unavailable_reason="Planned run matrix is empty.",
        )
        report = report.model_copy(update={"fingerprint": report.compute_fingerprint()})
        return report

    expected_map = _expected_cell_map(plan)
    expected_ids = set(expected_map.keys())
    duplicate_ids = _detect_duplicate_attachments(plan.evidence_attachments)

    # Build raw attachment list grouped by cell_id for duplicate handling
    # For non-duplicate, keep single; for duplicate, keep list but do not select one as authoritative  # noqa: E501
    attachment_groups: dict[str, list[EvidenceAttachment]] = defaultdict(list)
    for att in plan.evidence_attachments:
        attachment_groups[att.cell_id].append(att)

    # For service internal, create a dict for non-duplicate singletons (used for replicate counts etc)  # noqa: E501
    # But we will not select one for duplicate cells; we mark duplicate and do not use its content
    single_attachment_by_cell: dict[str, EvidenceAttachment] = {}
    for cell_id, group in attachment_groups.items():
        if len(group) == 1 and cell_id not in duplicate_ids:
            single_attachment_by_cell[cell_id] = group[0]
        # For duplicate_ids, we don't populate single map; they remain blocked

    # Extra cells: those not in expected, regardless of duplicate
    extra_cell_ids = sorted(set(attachment_groups.keys()) - expected_ids)

    # Review handoff validation
    review_by_cell: dict[str, AccrualReviewState] = {}
    interim_looks_used = 0
    if review_handoff is not None:
        # Pydantic already validated schema, duplicates, blank, bounds
        interim_looks_used = review_handoff.interim_looks_used or 0
        for dec in review_handoff.decisions:
            # For this V1, keep review decisions scoped to expected planned cells only
            if dec.cell_id not in expected_ids:
                # Refuse: review decision for extra or non-planned cell
                snapshot = AccrualSnapshot(
                    plan_id=plan.plan_id,
                    plan_fingerprint=plan.fingerprint,
                    plan_version=plan.version,
                    plan_status=plan.status.value,
                    expected_count=len(expected_ids),
                    attached_count=0,
                    admitted_count=0,
                    rejected_count=0,
                    incompatible_count=0,
                    extra_count=len(extra_cell_ids),
                    remaining_count=len(expected_ids),
                    complete_count=0,
                    attached_unadmitted_count=0,
                    planned_missing_count=len(expected_ids),
                    withdrawn_count=0,
                    duplicate_count=len(duplicate_ids),
                    post_evidence_amendment_count=sum(
                        1 for r in plan.revision_history if r.is_post_evidence
                    ),
                    power_plan_fingerprint=plan.power_plan_fingerprint,
                    planned_replicate_count=0,
                    observed_replicate_count=0,
                )
                stopping = StoppingProgress(
                    max_replicates=plan.stopping_rule.max_replicates,
                    interim_looks_allowed=plan.stopping_rule.interim_looks,
                    interim_looks_used=interim_looks_used,
                    planned_replicate_count=0,
                    observed_replicate_count=0,
                    expected_count=len(expected_ids),
                    attached_count=0,
                    admitted_count=0,
                    remaining=len(expected_ids),
                    is_overrun=False,
                    overrun_by=0,
                    status="unavailable: review decision for non-expected cell",
                )
                report = AccrualReport(
                    snapshot=snapshot,
                    cells=[],
                    deviations=[],
                    warnings=[
                        AccrualWarning(
                            code="REVIEW_SCOPE_MISMATCH",
                            message=f"Review decision for cell {dec.cell_id!r} not in planned matrix; extra review not supported in V1.",  # noqa: E501
                            severity="blocked",
                        )
                    ],
                    stopping_progress=stopping,
                    timeline=[],
                    amendment_history=[
                        r.model_dump(mode="json")
                        for r in sorted(plan.revision_history, key=lambda x: x.version)
                    ],
                    blockers=[
                        f"Review handoff contains cell {dec.cell_id!r} outside planned matrix."
                    ],
                    power_plan_fingerprint=plan.power_plan_fingerprint,
                    is_unavailable=True,
                    unavailable_reason="Review decision references non-planned cell.",
                )
                report = report.model_copy(update={"fingerprint": report.compute_fingerprint()})
                return report
            if dec.cell_id not in attachment_groups:
                snapshot = AccrualSnapshot(
                    plan_id=plan.plan_id,
                    plan_fingerprint=plan.fingerprint,
                    plan_version=plan.version,
                    plan_status=plan.status.value,
                    expected_count=len(expected_ids),
                    attached_count=0,
                    admitted_count=0,
                    rejected_count=0,
                    incompatible_count=0,
                    extra_count=len(extra_cell_ids),
                    remaining_count=len(expected_ids),
                    complete_count=0,
                    attached_unadmitted_count=0,
                    planned_missing_count=len(expected_ids),
                    withdrawn_count=0,
                    duplicate_count=len(duplicate_ids),
                    post_evidence_amendment_count=sum(
                        1 for r in plan.revision_history if r.is_post_evidence
                    ),
                    power_plan_fingerprint=plan.power_plan_fingerprint,
                    planned_replicate_count=0,
                    observed_replicate_count=0,
                )
                stopping = StoppingProgress(
                    max_replicates=plan.stopping_rule.max_replicates,
                    interim_looks_allowed=plan.stopping_rule.interim_looks,
                    interim_looks_used=interim_looks_used,
                    planned_replicate_count=0,
                    observed_replicate_count=0,
                    expected_count=len(expected_ids),
                    attached_count=0,
                    admitted_count=0,
                    remaining=len(expected_ids),
                    is_overrun=False,
                    overrun_by=0,
                    status="unavailable: review decision for missing evidence",
                )
                report = AccrualReport(
                    snapshot=snapshot,
                    cells=[],
                    deviations=[],
                    warnings=[
                        AccrualWarning(
                            code="REVIEW_MISSING_EVIDENCE",
                            message=f"Review decision for cell {dec.cell_id!r} has no attached evidence; cannot reject/withdraw missing evidence.",  # noqa: E501
                            severity="blocked",
                        )
                    ],
                    stopping_progress=stopping,
                    timeline=[],
                    amendment_history=[
                        r.model_dump(mode="json")
                        for r in sorted(plan.revision_history, key=lambda x: x.version)
                    ],
                    blockers=[f"Review decision for {dec.cell_id!r} has no evidence attached."],
                    power_plan_fingerprint=plan.power_plan_fingerprint,
                    is_unavailable=True,
                    unavailable_reason="Review decision requires attached evidence.",
                )
                report = report.model_copy(update={"fingerprint": report.compute_fingerprint()})
                return report
            review_by_cell[dec.cell_id] = dec.state
    else:
        interim_looks_used = 0

    post_evidence_count = sum(1 for r in plan.revision_history if r.is_post_evidence)

    cells: list[AccrualCellEntry] = []
    deviations: list[AccrualDeviation] = []
    warnings: list[AccrualWarning] = []
    timeline: list[AccrualTimelineEntry] = []
    blockers: list[str] = []

    status_counter: Counter[AccrualCellStatus] = Counter()

    # For each expected cell, determine single final status — mutually exclusive
    for cell_id in sorted(expected_ids):
        cell = expected_map[cell_id]
        is_dup = cell_id in duplicate_ids
        review_state = review_by_cell.get(cell_id)
        status: AccrualCellStatus | None = None
        deviation_reason: str | None = None

        # Duplicate takes precedence: fail-closed, no authoritative selection
        if is_dup:
            status = AccrualCellStatus.DUPLICATE
            deviation_reason = "duplicate_attachment: multiple evidence records for same cell"
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.DUPLICATE_ATTACHMENT,
                    cell_id=cell_id,
                    message=f"Duplicate attachment for cell {cell_id}",
                    details={"duplicate": True},
                )
            )
            # Timeline for duplicate
            for att in attachment_groups[cell_id]:
                try:
                    ts = _normalise_timestamp(att.attached_at) if att.attached_at else None
                except ValueError:
                    ts = None
                timeline.append(
                    AccrualTimelineEntry(
                        timestamp=ts,
                        event_type="duplicate_evidence_observed",
                        cell_id=cell_id,
                        message=f"Duplicate evidence observed for cell {cell_id}",
                        details={"duplicate": True, "admission_state": _admission_state_label(att)},
                    )
                )
            # For duplicate, we do not evaluate attachment content; we create a cell entry with no attachment-derived fields  # noqa: E501
            # Use first group's first attachment for display but mark as duplicate (no authoritative)  # noqa: E501
            # Choose earliest attached_at for first_observed deterministically (sorted)
            first_att = sorted(
                attachment_groups[cell_id],
                key=lambda a: a.attached_at.isoformat() if a.attached_at else "",
            )[0]
            cell_entry = AccrualCellEntry(
                cell_id=cell_id,
                arm_id=cell.arm_id,
                seed_id=cell.seed_id,
                policy_label=cell.policy_label,
                replication_id=cell.replication_id,
                metric_key=cell.metric_key,
                metric_version=cell.metric_version,
                replication_unit=cell.replication_unit.value,
                expected_identity={
                    "cell_id": cell.cell_id,
                    "arm_id": cell.arm_id,
                    "seed_id": cell.seed_id,
                    "policy_label": cell.policy_label,
                    "replication_id": cell.replication_id,
                    "metric_key": cell.metric_key,
                    "metric_version": cell.metric_version,
                    "replication_unit": cell.replication_unit.value,
                },
                attachment_state="duplicate_attached",
                admission_state="conflicting",
                compatibility="conflicting",
                first_observed_time=_first_observed_time(first_att),
                latest_decision=review_state.value.lower() if review_state else "duplicate",
                deviation_reason=deviation_reason,
                status=status,
            )
            cells.append(cell_entry)
            status_counter[status] += 1
            continue

        # Non-duplicate: get single attachment if exists
        attachment = single_attachment_by_cell.get(cell_id)
        is_withdrawn = review_state == AccrualReviewState.WITHDRAWN
        is_rejected = review_state == AccrualReviewState.REJECTED

        incompat_flag, incompat_reason = _is_incompatible(plan, cell, attachment)

        if attachment is None:
            status = AccrualCellStatus.PLANNED_MISSING
            deviation_reason = "missing_cell: no evidence attached for expected cell"
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.MISSING_CELL,
                    cell_id=cell_id,
                    message=f"Missing evidence for expected cell {cell_id}",
                    details={
                        "expected_metric": cell.metric_key,
                        "expected_version": cell.metric_version,
                    },
                )
            )
        elif is_withdrawn:
            status = AccrualCellStatus.WITHDRAWN
            deviation_reason = "withdrawn_evidence: evidence withdrawn after attachment"
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.WITHDRAWN_EVIDENCE,
                    cell_id=cell_id,
                    message=f"Evidence for cell {cell_id} was withdrawn",
                    details={"observed_metric": attachment.observed_metric_key},
                )
            )
        elif is_rejected:
            status = AccrualCellStatus.REJECTED
            deviation_reason = "rejected_evidence: review rejected the attached evidence"
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.REJECTED_EVIDENCE,
                    cell_id=cell_id,
                    message=f"Evidence for cell {cell_id} was rejected",
                    details={"admission_label": attachment.admission_label.value},
                )
            )
        elif incompat_flag:
            status = AccrualCellStatus.INCOMPATIBLE
            if attachment is not None and attachment.observed_metric_version != cell.metric_version:
                code = AccrualDeviationCode.METRIC_CONTRACT_MISMATCH
                deviation_reason = f"metric_contract_mismatch: {incompat_reason}"
            elif (
                attachment is not None
                and _expected_unit_map(plan).get(cell.metric_key) is not None
                and attachment.observed_unit != _expected_unit_map(plan).get(cell.metric_key)
            ):
                code = AccrualDeviationCode.UNIT_MISMATCH
                deviation_reason = f"unit_mismatch: {incompat_reason}"
            else:
                if incompat_reason and "unit" in incompat_reason.lower():
                    code = AccrualDeviationCode.UNIT_MISMATCH
                else:
                    code = AccrualDeviationCode.METRIC_CONTRACT_MISMATCH
                deviation_reason = f"incompatible: {incompat_reason}"
            deviations.append(
                AccrualDeviation(
                    code=code,
                    cell_id=cell_id,
                    message=deviation_reason or f"Incompatible evidence for cell {cell_id}",
                    details={"reason": incompat_reason},
                )
            )
        elif not is_explicitly_admitted(attachment):
            status = AccrualCellStatus.ATTACHED_UNADMITTED
            deviation_reason = None
        else:
            # Compatible admitted and not rejected/withdrawn → COMPLETE (even if post-evidence amendment exists)  # noqa: E501
            status = AccrualCellStatus.COMPLETE
            deviation_reason = None

        # Timeline for non-duplicate attachment
        if attachment is not None and attachment.attached_at is not None:
            try:
                ts_norm = _normalise_timestamp(attachment.attached_at)
            except ValueError:
                ts_norm = None
            timeline.append(
                AccrualTimelineEntry(
                    timestamp=ts_norm,
                    event_type="evidence_attached",
                    cell_id=cell_id,
                    message=f"Evidence attached for cell {cell_id}",
                    details={
                        "admission_state": _admission_state_label(attachment),
                        "status": status.value,
                    },
                )
            )
            if review_state is not None:
                timeline.append(
                    AccrualTimelineEntry(
                        timestamp=None,
                        event_type="review_decision",
                        cell_id=cell_id,
                        message=f"Review {review_state.value} for cell {cell_id}",
                        details={"review_state": review_state.value},
                    )
                )

        expected_identity = {
            "cell_id": cell.cell_id,
            "arm_id": cell.arm_id,
            "seed_id": cell.seed_id,
            "policy_label": cell.policy_label,
            "replication_id": cell.replication_id,
            "metric_key": cell.metric_key,
            "metric_version": cell.metric_version,
            "replication_unit": cell.replication_unit.value,
        }

        latest_decision_val = _latest_decision(attachment, review_state)
        cell_entry = AccrualCellEntry(
            cell_id=cell_id,
            arm_id=cell.arm_id,
            seed_id=cell.seed_id,
            policy_label=cell.policy_label,
            replication_id=cell.replication_id,
            metric_key=cell.metric_key,
            metric_version=cell.metric_version,
            replication_unit=cell.replication_unit.value,
            expected_identity=expected_identity,
            attachment_state=_attachment_state_label(attachment, False),
            admission_state=_admission_state_label(attachment),
            compatibility=_compatibility_label(plan, cell, attachment),
            first_observed_time=_first_observed_time(attachment),
            latest_decision=latest_decision_val,
            deviation_reason=deviation_reason,
            status=status,
        )
        cells.append(cell_entry)
        status_counter[status] += 1

    # Handle extra cells (observed but not expected) — never increase replicate count
    for cell_id in extra_cell_ids:
        group = attachment_groups[cell_id]
        # For extra, also consider duplicate? Extra with duplicate is still extra + duplicate
        is_dup_extra = len(group) > 1
        # Pick first for display but mark appropriately
        attachment = sorted(
            group, key=lambda a: a.attached_at.isoformat() if a.attached_at else ""
        )[0]
        status_counter[AccrualCellStatus.EXTRA] += 1
        deviations.append(
            AccrualDeviation(
                code=AccrualDeviationCode.EXTRA_CELL,
                cell_id=cell_id,
                message=f"Extra evidence cell {cell_id} not in planned matrix",
                details={"observed_metric": attachment.observed_metric_key},
            )
        )
        if is_dup_extra:
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.DUPLICATE_ATTACHMENT,
                    cell_id=cell_id,
                    message=f"Duplicate attachment for extra cell {cell_id}",
                    details={"duplicate": True, "extra": True},
                )
            )
        try:
            ts_norm = (
                _normalise_timestamp(attachment.attached_at) if attachment.attached_at else None
            )
        except ValueError:
            ts_norm = None
        timeline.append(
            AccrualTimelineEntry(
                timestamp=ts_norm,
                event_type="extra_evidence_observed",
                cell_id=cell_id,
                message=f"Extra evidence observed for cell {cell_id}",
                details={"extra": True},
            )
        )
        cell_entry = AccrualCellEntry(
            cell_id=cell_id,
            arm_id=None,
            seed_id=None,
            policy_label=None,
            replication_id=None,
            metric_key=attachment.observed_metric_key,
            metric_version=attachment.observed_metric_version,
            replication_unit=None,
            expected_identity=None,
            attachment_state=_attachment_state_label(attachment, is_dup_extra),
            admission_state=_admission_state_label(attachment),
            compatibility="extra",
            first_observed_time=_first_observed_time(attachment),
            latest_decision=_latest_decision(attachment, None),
            deviation_reason="extra_cell: observed evidence not in planned matrix",
            status=AccrualCellStatus.EXTRA,
        )
        cells.append(cell_entry)

    cells = sorted(cells, key=lambda c: c.cell_id)

    # Plan-level deviations: post_evidence_amendment
    if post_evidence_count > 0:
        for rev in sorted(plan.revision_history, key=lambda r: r.version):
            if rev.is_post_evidence:
                deviations.append(
                    AccrualDeviation(
                        code=AccrualDeviationCode.POST_EVIDENCE_AMENDMENT,
                        cell_id=None,
                        message=f"Post-evidence amendment v{rev.version}: {rev.amendment_reason[:80]}",  # noqa: E501
                        details={
                            "version": rev.version,
                            "parent_fingerprint": rev.parent_fingerprint,
                            "is_post_evidence": True,
                        },
                    )
                )
                try:
                    ts_norm = _normalise_timestamp(rev.created_at)
                except ValueError:
                    ts_norm = None
                timeline.append(
                    AccrualTimelineEntry(
                        timestamp=ts_norm,
                        event_type="post_evidence_amendment",
                        cell_id=None,
                        message=f"Amendment v{rev.version} after evidence: {rev.amendment_reason[:60]}",  # noqa: E501
                        details={"version": rev.version},
                    )
                )

    # Stopping progress via distinct replication IDs
    max_replicates = plan.stopping_rule.max_replicates
    interim_allowed = plan.stopping_rule.interim_looks
    expected_count = len(expected_ids)
    # Use helper to compute replicate counts
    planned_replicate_count, observed_replicate_count = _derive_replicate_counts(
        plan, single_attachment_by_cell, duplicate_ids
    )
    # For observed count, include duplicate-blocked replicates as observed but still blocked (they are attached)  # noqa: E501
    # Already counted via single map? For duplicate we used duplicate_ids to still count via single map missing, so we need to patch:  # noqa: E501
    # For duplicate cells, they are not in single map, so they would be missed. So we need to recompute observed including duplicates  # noqa: E501
    # Do explicit: collect distinct replication_id where any expected cell for that replicate has an attachment group (any)  # noqa: E501
    all_observed_reps: set[int] = set()
    for cell_id in attachment_groups:
        if cell_id in expected_map:
            # Only expected cells contribute to replicate count, extra does not
            all_observed_reps.add(expected_map[cell_id].replication_id)
    planned_replicate_count = len({c.replication_id for c in plan.planned_run_cells})
    observed_replicate_count = len(all_observed_reps)

    # Now compute attached/admitted counts for snapshot
    attached_count = sum(
        status_counter[s]
        for s in (
            AccrualCellStatus.ATTACHED_UNADMITTED,
            AccrualCellStatus.COMPLETE,
            AccrualCellStatus.INCOMPATIBLE,
            AccrualCellStatus.REJECTED,
            AccrualCellStatus.WITHDRAWN,
            AccrualCellStatus.DUPLICATE,
        )
        if s in status_counter
    )
    admitted_count = status_counter[AccrualCellStatus.COMPLETE]
    incompatible_count = status_counter[AccrualCellStatus.INCOMPATIBLE]
    rejected_count = status_counter[AccrualCellStatus.REJECTED]
    withdrawn_count = status_counter[AccrualCellStatus.WITHDRAWN]
    extra_count = status_counter[AccrualCellStatus.EXTRA]
    planned_missing_count = status_counter[AccrualCellStatus.PLANNED_MISSING]
    attached_unadmitted_count = status_counter[AccrualCellStatus.ATTACHED_UNADMITTED]
    duplicate_count = status_counter[AccrualCellStatus.DUPLICATE]
    complete_count = status_counter[AccrualCellStatus.COMPLETE]

    remaining_count = expected_count - complete_count
    if remaining_count < 0:
        remaining_count = 0

    is_overrun = False
    overrun_by = 0
    status_str = "on_track"
    if max_replicates is not None and observed_replicate_count > max_replicates:
        is_overrun = True
        overrun_by = observed_replicate_count - max_replicates
        status_str = "overrun"
        deviations.append(
            AccrualDeviation(
                code=AccrualDeviationCode.STOPPING_RULE_OVERRUN,
                cell_id=None,
                message=f"Stopping rule overrun: observed replicates {observed_replicate_count} exceeds max_replicates {max_replicates} by {overrun_by}",  # noqa: E501
                details={
                    "max_replicates": max_replicates,
                    "observed_replicate_count": observed_replicate_count,
                    "overrun_by": overrun_by,
                },
            )
        )
        timeline.append(
            AccrualTimelineEntry(
                timestamp=None,
                event_type="stopping_rule_overrun",
                cell_id=None,
                message=f"Stopping rule overrun by {overrun_by}",
                details={"max_replicates": max_replicates, "observed": observed_replicate_count},
            )
        )

    if interim_looks_used > interim_allowed:
        deviations.append(
            AccrualDeviation(
                code=AccrualDeviationCode.UNPLANNED_INTERIM_LOOK,
                cell_id=None,
                message=f"Unplanned interim look: used {interim_looks_used} exceeds allowed {interim_allowed}",  # noqa: E501
                details={"allowed": interim_allowed, "used": interim_looks_used},
            )
        )
        timeline.append(
            AccrualTimelineEntry(
                timestamp=None,
                event_type="unplanned_interim_look",
                cell_id=None,
                message=f"Unplanned interim look {interim_looks_used} > {interim_allowed}",
                details={"allowed": interim_allowed, "used": interim_looks_used},
            )
        )
        status_str = "overrun" if status_str == "overrun" else "unplanned_look"
        warnings.append(
            AccrualWarning(
                code="UNPLANNED_INTERIM_LOOK",
                message=f"Interim looks used ({interim_looks_used}) exceed planned ({interim_allowed}); not an interim decision.",  # noqa: E501
                severity="warning",
            )
        )

    # Recompute gate using authoritative implementation for comparison
    # Use raw attachments that are singletons? For duplicate case, pass all attachments to see duplicate blocker  # noqa: E501
    # Build list for gate: use the non-duplicate singles plus one per duplicate group? But duplicate detection should be triggered via passing all groups flattened  # noqa: E501
    gate_attachments: list[EvidenceAttachment] = []
    for cell_id, group in attachment_groups.items():
        if cell_id in expected_ids:
            # For expected, gate should see all attachments (including duplicates) to detect duplicates  # noqa: E501
            gate_attachments.extend(group)
        else:
            # Extra cells: each extra attachment
            gate_attachments.extend(group)
    # Also include missing? No.

    try:
        recomputed_gate, _ = evaluate_gate_with_reasons(plan, gate_attachments)
    except Exception:
        recomputed_gate = None

    # Compare stored gate if exists
    if plan.gate_report is not None and recomputed_gate is not None:
        # Material inconsistency check: status differs or missing/extra/incompatible lists differ
        stored = plan.gate_report
        # Consider mismatch if status differs or counts differ
        if (
            stored.status != recomputed_gate.status
            or set(stored.missing_cells) != set(recomputed_gate.missing_cells)
            or set(stored.extra_cells) != set(recomputed_gate.extra_cells)
            or set(stored.incompatible_cells) != set(recomputed_gate.incompatible_cells)
        ):
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.GATE_REPORT_MISMATCH,
                    cell_id=None,
                    message="Stored preregistration gate report mismatches recomputed gate context",
                    details={
                        "stored_status": stored.status.value,
                        "recomputed_status": recomputed_gate.status.value,
                        "stored_missing": sorted(stored.missing_cells)[:3],
                        "recomputed_missing": sorted(recomputed_gate.missing_cells)[:3],
                    },
                )
            )
            warnings.append(
                AccrualWarning(
                    code="GATE_REPORT_MISMATCH",
                    message="Stored preregistration gate report is stale vs current evidence; recomputed gate context is shown.",  # noqa: E501
                    severity="warning",
                )
            )
            timeline.append(
                AccrualTimelineEntry(
                    timestamp=None,
                    event_type="gate_report_mismatch",
                    cell_id=None,
                    message=f"Gate mismatch stored {stored.status.value} vs recomputed {recomputed_gate.status.value}",  # noqa: E501
                    details={
                        "stored": stored.status.value,
                        "recomputed": recomputed_gate.status.value,
                    },
                )
            )
            blockers.append(
                "Stored preregistration gate report mismatches current recomputed gate context."
            )

    # Derive blockers from current accrual state first — authoritative
    # Current expected cells in these states block clean accrual
    blocking_states = {
        AccrualCellStatus.PLANNED_MISSING,
        AccrualCellStatus.ATTACHED_UNADMITTED,
        AccrualCellStatus.INCOMPATIBLE,
        AccrualCellStatus.REJECTED,
        AccrualCellStatus.WITHDRAWN,
        AccrualCellStatus.DUPLICATE,
    }
    current_blocking_count = sum(status_counter[s] for s in blocking_states if s in status_counter)
    if current_blocking_count > 0:
        # Add blocker for each category present
        for state in sorted(blocking_states, key=lambda s: s.value):
            cnt = status_counter.get(state, 0)
            if cnt > 0:
                blockers.append(
                    f"Accrual blocker: {cnt} cells in {state.value} require resolution."
                )
    # Post-evidence amendment blocker
    if post_evidence_count > 0:
        warnings.append(
            AccrualWarning(
                code="POST_EVIDENCE_AMENDMENT",
                message=f"{post_evidence_count} post-evidence amendments require review before decision.",  # noqa: E501
                severity="warning",
            )
        )
        blockers.append(
            f"{post_evidence_count} post-evidence amendments; plan was amended after evidence collection; study governance blocked."  # noqa: E501
        )

    # Warnings for deviations that block (but blockers already added above)
    if incompatible_count > 0:
        warnings.append(
            AccrualWarning(
                code="INCOMPATIBLE_EVIDENCE",
                message=f"{incompatible_count} cells have contract incompatibilities and are not admitted.",  # noqa: E501
                severity="blocked",
            )
        )
    if extra_count > 0:
        warnings.append(
            AccrualWarning(
                code="EXTRA_CELLS",
                message=f"{extra_count} extra cells outside the planned matrix were observed.",
                severity="warning",
            )
        )
    if rejected_count > 0:
        warnings.append(
            AccrualWarning(
                code="REJECTED_EVIDENCE",
                message=f"{rejected_count} cells have rejected evidence.",
                severity="blocked",
            )
        )
    if withdrawn_count > 0:
        warnings.append(
            AccrualWarning(
                code="WITHDRAWN_EVIDENCE",
                message=f"{withdrawn_count} cells have withdrawn evidence.",
                severity="warning",
            )
        )
    if duplicate_count > 0:
        warnings.append(
            AccrualWarning(
                code="DUPLICATE_ATTACHMENT",
                message=f"{duplicate_count} cells have duplicate evidence records; no authoritative attachment selected.",  # noqa: E501
                severity="blocked",
            )
        )

    # Gate context adds information but does not remove current blockers
    if recomputed_gate is not None:
        if recomputed_gate.status.value != "ready":
            # Add recomputed gate context as blocker if not already blocked
            if recomputed_gate.missing_cells:
                blockers.append(
                    f"Recomputed preregistration gate: {recomputed_gate.status.value} — missing {', '.join(recomputed_gate.missing_cells[:3])}"  # noqa: E501
                )
            elif recomputed_gate.incompatible_cells:
                blockers.append(
                    f"Recomputed preregistration gate: {recomputed_gate.status.value} — incompatible {', '.join(recomputed_gate.incompatible_cells[:3])}"  # noqa: E501
                )
            else:
                blockers.append(
                    f"Recomputed preregistration gate: {recomputed_gate.status.value} — {'; '.join(recomputed_gate.reasons[:1])}"  # noqa: E501
                )
        else:
            # Even if gate ready, if we have current blockers, we keep them — stored READY does not suppress  # noqa: E501
            if (
                current_blocking_count == 0
                and post_evidence_count == 0
                and not is_overrun
                and interim_looks_used <= interim_allowed
            ):
                # No blockers, gate ready context is positive but not a blocker
                pass
            else:
                # Gate ready but we still have blockers, keep blockers
                pass
        # Always add timeline for gate
        timeline.append(
            AccrualTimelineEntry(
                timestamp=None,
                event_type="recomputed_gate",
                cell_id=None,
                message=f"Recomputed gate {recomputed_gate.status.value}: {'; '.join(recomputed_gate.reasons[:1])}",  # noqa: E501
                details={"status": recomputed_gate.status.value},
            )
        )

    # Ensure blockers invariant: if any warning blocked then blockers non-empty
    has_blocked_warning = any(w.severity == "blocked" for w in warnings)
    if has_blocked_warning and not blockers:
        blockers.append("Accrual blocked: see warnings with blocked severity.")

    blockers = sorted(set(blockers))
    deviations = sorted(deviations, key=lambda d: (d.code.value, d.cell_id or ""))

    def _canonical_details_svc(details: Any) -> str:  # noqa: ANN401
        import json

        if details is None:
            return ""
        return json.dumps(
            details, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )

    timeline = sorted(
        timeline,
        key=lambda t: (
            t.timestamp or "",
            t.event_type,
            t.cell_id or "",
            _canonical_details_svc(t.details),
            t.message,
        ),
    )

    # Reconciliation
    expected_status_sum = (
        planned_missing_count
        + attached_unadmitted_count
        + complete_count
        + incompatible_count
        + rejected_count
        + withdrawn_count
        + duplicate_count
    )
    if expected_status_sum != expected_count:
        raise ValueError(
            f"count reconciliation failed: expected_status_sum {expected_status_sum} != expected_count {expected_count}"  # noqa: E501
        )
    recomputed_attached = (
        attached_unadmitted_count
        + complete_count
        + incompatible_count
        + rejected_count
        + withdrawn_count
        + duplicate_count
    )
    if recomputed_attached != attached_count:
        raise ValueError(
            f"attached reconciliation failed: {recomputed_attached} != {attached_count}"
        )

    snapshot = AccrualSnapshot(
        plan_id=plan.plan_id,
        plan_fingerprint=plan.fingerprint,
        plan_version=plan.version,
        plan_status=plan.status.value,
        expected_count=expected_count,
        attached_count=attached_count,
        admitted_count=admitted_count,
        rejected_count=rejected_count,
        incompatible_count=incompatible_count,
        extra_count=extra_count,
        remaining_count=remaining_count,
        complete_count=complete_count,
        attached_unadmitted_count=attached_unadmitted_count,
        planned_missing_count=planned_missing_count,
        withdrawn_count=withdrawn_count,
        duplicate_count=duplicate_count,
        post_evidence_amendment_count=post_evidence_count,
        power_plan_fingerprint=plan.power_plan_fingerprint,
        planned_replicate_count=planned_replicate_count,
        observed_replicate_count=observed_replicate_count,
    )

    stopping = StoppingProgress(
        max_replicates=max_replicates,
        interim_looks_allowed=interim_allowed,
        interim_looks_used=interim_looks_used,
        planned_replicate_count=planned_replicate_count,
        observed_replicate_count=observed_replicate_count,
        expected_count=expected_count,
        attached_count=attached_count,
        admitted_count=admitted_count,
        remaining=remaining_count,
        is_overrun=is_overrun,
        overrun_by=overrun_by,
        status=status_str,
    )

    report = AccrualReport(
        schema_version="1.0",
        snapshot=snapshot,
        cells=cells,
        deviations=deviations,
        warnings=warnings,
        stopping_progress=stopping,
        timeline=timeline,
        amendment_history=[
            r.model_dump(mode="json")
            for r in sorted(plan.revision_history, key=lambda x: x.version)
        ],
        blockers=blockers,
        power_plan_fingerprint=plan.power_plan_fingerprint,
        is_unavailable=False,
        unavailable_reason=None,
    )
    report = report.model_copy(update={"fingerprint": report.compute_fingerprint()})
    return report
