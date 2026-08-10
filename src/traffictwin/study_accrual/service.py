"""Deterministic accrual monitoring — never mutates the plan."""

from __future__ import annotations

from collections import Counter
from typing import Any

from traffictwin.preregistration.models import (
    EvidenceAttachment,
    PlannedRunCell,
    StudyPlan,
    StudyPlanStatus,
    is_explicitly_admitted,
)
from traffictwin.study_accrual.models import (
    AccrualCellEntry,
    AccrualCellStatus,
    AccrualDeviation,
    AccrualDeviationCode,
    AccrualReport,
    AccrualSnapshot,
    AccrualTimelineEntry,
    AccrualWarning,
    StoppingProgress,
    _normalise_timestamp,
)

MAX_CELLS = 10000


def _expected_unit_map(plan: StudyPlan) -> dict[str, str]:
    return {o.metric_key: o.unit for o in plan.primary_outcomes}


def _expected_version_map(plan: StudyPlan) -> dict[str, str]:
    return {c.cell_id: c.metric_version for c in plan.planned_run_cells}


def _expected_cell_map(plan: StudyPlan) -> dict[str, PlannedRunCell]:
    return {c.cell_id: c for c in plan.planned_run_cells}


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


def _latest_decision(attachment: EvidenceAttachment | None) -> str | None:
    if attachment is None:
        return None
    if attachment.incompatibility_reason is not None:
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
    # Direct metric/unit mismatch check; admission failure is not incompatibility
    if attachment.observed_metric_version != exp_ver:
        return f"incompatible: metric_version mismatch expected {exp_ver!r} observed {attachment.observed_metric_version!r}"  # noqa: E501
    if exp_unit is not None and attachment.observed_unit != exp_unit:
        return f"incompatible: unit mismatch expected {exp_unit!r} observed {attachment.observed_unit!r}"  # noqa: E501
    if attachment.observed_metric_key != cell.metric_key:
        return f"incompatible: metric_key mismatch expected {cell.metric_key!r} observed {attachment.observed_metric_key!r}"  # noqa: E501
    # If stored incompatibility_reason is about admission, treat as compatible for compatibility label  # noqa: E501
    # but admission state will show unadmitted
    if (
        attachment.incompatibility_reason is not None
        and "not explicitly admitted" not in attachment.incompatibility_reason.lower()
    ):
        return f"incompatible: {attachment.incompatibility_reason}"
    return "compatible"


def _is_incompatible(
    plan: StudyPlan,
    cell: PlannedRunCell | None,
    attachment: EvidenceAttachment | None,
) -> tuple[bool, str | None]:
    if attachment is None or cell is None:
        return False, None
    # Only version/unit/key mismatches are incompatibilities; admission failure is separate state
    exp_ver = cell.metric_version
    if attachment.observed_metric_version != exp_ver:
        return (
            True,
            f"metric_version mismatch expected {exp_ver!r} observed {attachment.observed_metric_version!r}",  # noqa: E501
        )
    exp_unit = _expected_unit_map(plan).get(cell.metric_key)
    if exp_unit is not None and attachment.observed_unit != exp_unit:
        return True, f"unit mismatch expected {exp_unit!r} observed {attachment.observed_unit!r}"
    if attachment.observed_metric_key != cell.metric_key:
        return (
            True,
            f"metric_key mismatch expected {cell.metric_key!r} observed {attachment.observed_metric_key!r}",  # noqa: E501
        )
    # Check stored incompatibility_reason only if it indicates metric/unit mismatch, not pure admission  # noqa: E501
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


def build_accrual_report(
    plan: StudyPlan,
    *,
    rejected_cell_ids: set[str] | None = None,
    withdrawn_cell_ids: set[str] | None = None,
    interim_looks_used: int | None = None,
    generic_review_payload: dict[str, Any] | None = None,
) -> AccrualReport:
    """Build deterministic accrual report without mutating the plan.

    - Does not admit evidence automatically.
    - Does not change plan status.
    - Fail-closed: validates bounded inputs.
    - Order-independent fingerprint via sorted cells/deviations.
    """
    # Bounded inputs guard
    if len(plan.planned_run_cells) > MAX_CELLS:
        raise ValueError(f"planned_run_cells exceeds limit {MAX_CELLS}")
    if len(plan.evidence_attachments) > MAX_CELLS:
        raise ValueError(f"evidence_attachments exceeds limit {MAX_CELLS}")

    rejected_cell_ids = set(rejected_cell_ids or set())
    withdrawn_cell_ids = set(withdrawn_cell_ids or set())

    # Parse generic review payload if provided (optional handoff contract)
    if generic_review_payload is not None:
        # Generic JSON may contain rejected/withdrawn lists without breaking identity
        for key in ("rejected_cells", "rejected_cell_ids", "rejected"):
            if key in generic_review_payload:
                val = generic_review_payload[key]
                if isinstance(val, list):
                    rejected_cell_ids.update(str(x).strip() for x in val if str(x).strip())
        for key in ("withdrawn_cells", "withdrawn_cell_ids", "withdrawn"):
            if key in generic_review_payload:
                val = generic_review_payload[key]
                if isinstance(val, list):
                    withdrawn_cell_ids.update(str(x).strip() for x in val if str(x).strip())
        # interim looks may be in payload
        for key in ("interim_looks", "interim_looks_used", "looks"):
            if key in generic_review_payload and interim_looks_used is None:
                try:  # noqa: SIM105
                    interim_looks_used = int(generic_review_payload[key])
                except Exception:  # noqa: S110
                    pass

    if interim_looks_used is None:
        interim_looks_used = 0
    if interim_looks_used < 0:
        raise ValueError("interim_looks_used must be non-negative")
    if interim_looks_used > 100:
        raise ValueError("interim_looks_used bounded to <=100")

    # Unavailable states — explicit, never silently computed
    if plan.status == StudyPlanStatus.DRAFT:
        # Draft has no frozen identity; monitor is unavailable
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
            attached_admitted_count=0,
            planned_missing_count=len(plan.planned_run_cells),
            withdrawn_count=0,
            post_evidence_amendment_count=sum(
                1 for r in plan.revision_history if r.is_post_evidence
            ),
            power_plan_fingerprint=plan.power_plan_fingerprint,
        )
        stopping = StoppingProgress(
            max_replicates=plan.stopping_rule.max_replicates,
            interim_looks_allowed=plan.stopping_rule.interim_looks,
            interim_looks_used=interim_looks_used,
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
            attached_admitted_count=0,
            planned_missing_count=0,
            withdrawn_count=0,
            post_evidence_amendment_count=sum(
                1 for r in plan.revision_history if r.is_post_evidence
            ),
            power_plan_fingerprint=plan.power_plan_fingerprint,
        )
        stopping = StoppingProgress(
            max_replicates=plan.stopping_rule.max_replicates,
            interim_looks_allowed=plan.stopping_rule.interim_looks,
            interim_looks_used=interim_looks_used,
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
    # Detect duplicates before deduping
    duplicate_ids = _detect_duplicate_attachments(plan.evidence_attachments)
    # Build attachment map deduped (last wins) but record duplicate deviations
    attachment_by_cell: dict[str, EvidenceAttachment] = {}
    for att in sorted(plan.evidence_attachments, key=lambda a: a.cell_id):
        # For dedup, keep first encountered sorted order; duplicates already flagged
        if att.cell_id not in attachment_by_cell:
            attachment_by_cell[att.cell_id] = att
        else:
            # Keep earliest for determinism; duplicate already flagged
            pass

    # Also count extra not in expected
    extra_cell_ids = sorted(set(attachment_by_cell.keys()) - expected_ids)

    # Post-evidence amendment count
    post_evidence_count = sum(1 for r in plan.revision_history if r.is_post_evidence)

    cells: list[AccrualCellEntry] = []
    deviations: list[AccrualDeviation] = []
    warnings: list[AccrualWarning] = []
    timeline: list[AccrualTimelineEntry] = []
    blockers: list[str] = []

    # Counters for mutually exclusive final states
    status_counter: Counter[AccrualCellStatus] = Counter()

    # Stopping progress counters (to be computed after loop)
    admitted_for_progress = 0

    # For each expected cell, determine single final status
    for cell_id in sorted(expected_ids):
        cell = expected_map[cell_id]
        attachment = attachment_by_cell.get(cell_id)
        is_dup = cell_id in duplicate_ids

        # Determine withdrawn/rejected before other checks — explicit unavailable states
        is_withdrawn = cell_id in withdrawn_cell_ids
        is_rejected = cell_id in rejected_cell_ids

        # Determine incompatibility (metric/unit) — typed, not inferred beyond explicit records
        incompat_flag, incompat_reason = _is_incompatible(plan, cell, attachment)

        # Determine deviation reason for this cell (for display)
        deviation_reason: str | None = None

        # Status assignment — mutually exclusive, priority order ensures no double-count
        status: AccrualCellStatus
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
            # Determine which mismatch code
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
                # Covers metric_key mismatch or generic incompatibility_reason
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
            deviation_reason = None  # Not a deviation, just pending admission
            # No deviation code for simply unadmitted; monitoring shows pending
        else:
            # is_admitted True and compatible
            # Distinguish complete vs attached_admitted based on post_evidence amendment
            # If any post-evidence amendment exists, admitted evidence collected before amendment is not clean  # noqa: E501
            # We treat all admitted cells as attached_admitted when post_evidence_count>0, else complete  # noqa: E501
            # This keeps both statuses exercised and respects monitoring boundary (no plan change)
            if post_evidence_count > 0:
                status = AccrualCellStatus.ATTACHED_ADMITTED
                # No per-cell deviation for amendment; plan-level deviation added later
            else:
                status = AccrualCellStatus.COMPLETE
            admitted_for_progress += 1
            # deviation_reason stays None for clean complete

        # Duplicate is a separate deviation but does not change mutually exclusive status
        # (already counted once). Add duplicate deviation if applicable.
        if is_dup:
            # Add duplicate deviation (plan-level but per-cell)
            # Avoid double-adding if already present for this cell
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.DUPLICATE_ATTACHMENT,
                    cell_id=cell_id,
                    message=f"Duplicate attachment for cell {cell_id}",
                    details={"duplicate": True},
                )
            )
            # If status was already determined, keep it; duplicate is additional evidence but status remains  # noqa: E501

        status_counter[status] += 1

        # Build timeline entries for this cell if attachment exists
        if attachment is not None and attachment.attached_at is not None:
            timeline.append(
                AccrualTimelineEntry(
                    timestamp=_normalise_timestamp(attachment.attached_at),
                    event_type="evidence_attached",
                    cell_id=cell_id,
                    message=f"Evidence attached for cell {cell_id}",
                    details={
                        "admission_state": _admission_state_label(attachment),
                        "status": status.value,
                    },
                )
            )
            # If gate report exists, add decision timeline? Use plan gate for each cell?
            # Not per-cell, but overall gate will be added later.

        # Expected identity dict for display
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
            attachment_state=_attachment_state_label(attachment, is_dup),
            admission_state=_admission_state_label(attachment),
            compatibility=_compatibility_label(plan, cell, attachment),
            first_observed_time=_first_observed_time(attachment),
            latest_decision=_latest_decision(attachment),
            deviation_reason=deviation_reason,
            status=status,
        )
        cells.append(cell_entry)

    # Handle extra cells (observed but not expected)
    for cell_id in extra_cell_ids:
        attachment = attachment_by_cell[cell_id]
        is_dup = cell_id in duplicate_ids
        status_counter[AccrualCellStatus.EXTRA] += 1
        deviations.append(
            AccrualDeviation(
                code=AccrualDeviationCode.EXTRA_CELL,
                cell_id=cell_id,
                message=f"Extra evidence cell {cell_id} not in planned matrix",
                details={"observed_metric": attachment.observed_metric_key},
            )
        )
        if is_dup:
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.DUPLICATE_ATTACHMENT,
                    cell_id=cell_id,
                    message=f"Duplicate attachment for extra cell {cell_id}",
                    details={"duplicate": True, "extra": True},
                )
            )
        timeline.append(
            AccrualTimelineEntry(
                timestamp=_normalise_timestamp(attachment.attached_at),
                event_type="extra_evidence_observed",
                cell_id=cell_id,
                message=f"Extra evidence observed for cell {cell_id}",
                details={"extra": True},
            )
        )
        # Extra cells have no expected identity
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
            attachment_state=_attachment_state_label(attachment, is_dup),
            admission_state=_admission_state_label(attachment),
            compatibility="extra",
            first_observed_time=_first_observed_time(attachment),
            latest_decision=_latest_decision(attachment),
            deviation_reason="extra_cell: observed evidence not in planned matrix",
            status=AccrualCellStatus.EXTRA,
        )
        cells.append(cell_entry)

    # Sort cells deterministically for stable fingerprint and display
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
                timeline.append(
                    AccrualTimelineEntry(
                        timestamp=_normalise_timestamp(rev.created_at),
                        event_type="post_evidence_amendment",
                        cell_id=None,
                        message=f"Amendment v{rev.version} after evidence: {rev.amendment_reason[:60]}",  # noqa: E501
                        details={"version": rev.version},
                    )
                )

    # Stopping rule progress
    max_replicates = plan.stopping_rule.max_replicates
    interim_allowed = plan.stopping_rule.interim_looks
    expected_count = len(expected_ids)
    attached_count = sum(
        status_counter[s]
        for s in (
            AccrualCellStatus.ATTACHED_UNADMITTED,
            AccrualCellStatus.ATTACHED_ADMITTED,
            AccrualCellStatus.COMPLETE,
            AccrualCellStatus.INCOMPATIBLE,
            AccrualCellStatus.REJECTED,
            AccrualCellStatus.WITHDRAWN,
        )
        if s in status_counter
    )
    # admitted_count defined as explicitly admitted and not withdrawn/rejected/incompatible? Use counter logic  # noqa: E501
    admitted_count = (
        status_counter[AccrualCellStatus.COMPLETE]
        + status_counter[AccrualCellStatus.ATTACHED_ADMITTED]
    )
    incompatible_count = status_counter[AccrualCellStatus.INCOMPATIBLE]
    rejected_count = status_counter[AccrualCellStatus.REJECTED]
    withdrawn_count = status_counter[AccrualCellStatus.WITHDRAWN]
    extra_count = status_counter[AccrualCellStatus.EXTRA]
    planned_missing_count = status_counter[AccrualCellStatus.PLANNED_MISSING]
    attached_unadmitted_count = status_counter[AccrualCellStatus.ATTACHED_UNADMITTED]
    attached_admitted_count = status_counter[AccrualCellStatus.ATTACHED_ADMITTED]
    complete_count = status_counter[AccrualCellStatus.COMPLETE]

    remaining_count = expected_count - complete_count
    if remaining_count < 0:
        remaining_count = 0

    # Stopping overrun detection — explicit, not inferred without record
    is_overrun = False
    overrun_by = 0
    status_str = "on_track"
    if max_replicates is not None:
        # Overrun if attached exceeds expected or max_replicates * something
        # Fail-closed: we compare attached_count vs expected_count and vs max_replicates
        # If max_replicates is smaller than expected (unlikely), use max
        effective_max = max_replicates
        # If stopping rule describes max_replicates as total draws, overrun when attached > max
        if attached_count > effective_max:
            is_overrun = True
            overrun_by = attached_count - effective_max
            status_str = "overrun"
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.STOPPING_RULE_OVERRUN,
                    cell_id=None,
                    message=f"Stopping rule overrun: attached {attached_count} exceeds max_replicates {effective_max} by {overrun_by}",  # noqa: E501
                    details={
                        "max_replicates": effective_max,
                        "attached_count": attached_count,
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
                    details={"max_replicates": effective_max, "attached": attached_count},
                )
            )
        elif attached_count > expected_count:
            # This would also be extra cells, but extra already counted; overrun relative to expected  # noqa: E501
            is_overrun = True
            overrun_by = attached_count - expected_count
            status_str = "overrun"
            deviations.append(
                AccrualDeviation(
                    code=AccrualDeviationCode.STOPPING_RULE_OVERRUN,
                    cell_id=None,
                    message=f"Stopping rule overrun: attached {attached_count} exceeds expected {expected_count} by {overrun_by}",  # noqa: E501
                    details={"expected_count": expected_count, "attached_count": attached_count},
                )
            )

    if interim_looks_used > interim_allowed:
        # Unplanned interim look — only if explicit count exceeds allowed
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

    # Gate blockers: reflect current gate status if not READY
    if plan.gate_report is not None:
        if plan.gate_report.status.value != "ready":
            blockers.append(
                f"Gate status: {plan.gate_report.status.value} — {'; '.join(plan.gate_report.reasons[:2])}"  # noqa: E501
            )
            # Also add timeline entry for gate decision
            timeline.append(
                AccrualTimelineEntry(
                    timestamp=None,
                    event_type="gate_decision",
                    cell_id=None,
                    message=f"Gate {plan.gate_report.status.value}: {'; '.join(plan.gate_report.reasons[:1])}",  # noqa: E501
                    details={
                        "status": plan.gate_report.status.value,
                        "missing_cells": plan.gate_report.missing_cells[:3],
                        "extra_cells": plan.gate_report.extra_cells[:3],
                    },
                )
            )
        # Add incompatibility blockers
        if plan.gate_report.incompatible_cells:
            blockers.append(
                f"Incompatible cells block gate: {', '.join(plan.gate_report.incompatible_cells[:3])}"  # noqa: E501
            )
    else:
        # No gate report yet — blocker if not enough evidence
        if attached_count < expected_count:
            blockers.append(
                f"Accrual incomplete: {attached_count}/{expected_count} cells attached; gate unavailable."  # noqa: E501
            )
        if admitted_count < expected_count:
            blockers.append(
                f"Admission incomplete: {admitted_count}/{expected_count} admitted; gate not ready."
            )

    # Warnings for deviations that block
    if incompatible_count > 0:
        warnings.append(
            AccrualWarning(
                code="INCOMPATIBLE_EVIDENCE",
                message=f"{incompatible_count} cells have contract incompatibilities and are not admitted.",  # noqa: E501
                severity="blocked",
            )
        )
        if not blockers:
            blockers.append(f"{incompatible_count} incompatible cells block decision.")
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
    if post_evidence_count > 0:
        warnings.append(
            AccrualWarning(
                code="POST_EVIDENCE_AMENDMENT",
                message=f"{post_evidence_count} post-evidence amendments require review before decision.",  # noqa: E501
                severity="warning",
            )
        )
        blockers.append(
            f"{post_evidence_count} post-evidence amendments; plan was amended after evidence collection."  # noqa: E501
        )

    # Ensure blockers are deterministic sorted
    blockers = sorted(set(blockers))

    # Sort deviations deterministically (already partly) for fingerprint stability
    deviations = sorted(deviations, key=lambda d: (d.code.value, d.cell_id or ""))

    # Sort timeline deterministically
    timeline = sorted(timeline, key=lambda t: (t.timestamp or "", t.event_type, t.cell_id or ""))

    # Build snapshot — must reconcile counts, no double-counting
    # Reconciliation invariant: expected_count == sum of expected-cell statuses
    expected_status_sum = (
        planned_missing_count
        + attached_unadmitted_count
        + attached_admitted_count
        + complete_count
        + incompatible_count
        + rejected_count
        + withdrawn_count
    )
    # Fail-closed: if invariant broken, raise rather than silently misrepresent
    if expected_status_sum != expected_count:
        raise ValueError(
            f"count reconciliation failed: expected_status_sum {expected_status_sum} != expected_count {expected_count}"  # noqa: E501
        )
    # attached_count already computed as sum of statuses with attachment
    # Verify attached reconciliation
    recomputed_attached = (
        attached_unadmitted_count
        + attached_admitted_count
        + complete_count
        + incompatible_count
        + rejected_count
        + withdrawn_count
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
        attached_admitted_count=attached_admitted_count,
        planned_missing_count=planned_missing_count,
        withdrawn_count=withdrawn_count,
        post_evidence_amendment_count=post_evidence_count,
        power_plan_fingerprint=plan.power_plan_fingerprint,
    )

    stopping = StoppingProgress(
        max_replicates=max_replicates,
        interim_looks_allowed=interim_allowed,
        interim_looks_used=interim_looks_used,
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
    # Compute deterministic fingerprint
    report = report.model_copy(update={"fingerprint": report.compute_fingerprint()})
    return report
