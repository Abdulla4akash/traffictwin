"""Focused unit tests for Study Accrual Monitor service."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from traffictwin.metrics.catalogue import METRIC_VERSION
from traffictwin.preregistration.models import (
    AnalysisMethod,
    ArtifactAdmission,
    CohortRule,
    DecisionRule,
    EstimandDefinition,
    EvidenceAttachment,
    EvidenceMode,
    ExclusionRule,
    MissingnessPolicy,
    MultiplicityPolicy,
    OutcomeDefinition,
    ReplicationUnit,
    StoppingRule,
    StudyPlan,
    StudyPlanStatus,
    StudyQuestion,
)
from traffictwin.preregistration.service import attach_evidence, create_amendment, freeze_plan
from traffictwin.study_accrual.exports import (
    export_cells_csv,
    export_deviations_csv,
    export_report_json,
    export_report_json_canonical,
)
from traffictwin.study_accrual.models import AccrualCellStatus, AccrualDeviationCode
from traffictwin.study_accrual.service import build_accrual_report

FIXED = datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC)
ATTACH_TIME = datetime(2026, 1, 11, 10, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 12, 10, 0, 0, tzinfo=UTC)


def _base_frozen_plan(**overrides: object) -> StudyPlan:  # noqa: ANN003
    base = StudyPlan(
        plan_id="accrual-unit-001",
        study_question=StudyQuestion(
            text="Does variation change completion rate under predeclared replication?",
            hypothesis="Variation improves completion rate.",
        ),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key="task.completion.rate",
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary completion rate in ratio unit.",
            )
        ],
        estimand=EstimandDefinition(
            estimand_id="est-001",
            description="Mean difference over common seeds.",
            population="common seeds",
            effect_measure="mean_diff",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1, 2],
        planned_arms=["baseline", "variation"],
        cohort_rules=[
            CohortRule(rule_id="cohort-001", description="Include all valid generated tasks.")
        ],
        exclusion_rules=[
            ExclusionRule(rule_id="exclude-001", description="Exclude invalid source data.")
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="Fixed sample with limited interim looks for testing.",
            max_replicates=4,
            interim_looks=1,
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            interpretation="Reject if p < 0.05; non-significance not equivalence.",
            comparison="two_sided",
        ),
        limitations="Synthetic demo limitations with sufficient length for validation.",
        planned_run_cells=[],
    )
    if overrides:
        # Merge via model_copy after base freeze? Handle pre-freeze overrides only
        base = base.model_copy(update=overrides)
    frozen = freeze_plan(base, clock=lambda: FIXED)
    return frozen


def _admitted_attachment(
    cell_id: str,
    metric_version: str = METRIC_VERSION,
    unit: str = "ratio",
    is_admitted: bool = True,
) -> EvidenceAttachment:
    return EvidenceAttachment(
        artifact_fingerprint=hashlib.sha256(f"fp-{cell_id}".encode()).hexdigest(),
        cell_id=cell_id,
        artifact_type="metric_collection",
        observed_metric_key="task.completion.rate",
        observed_metric_version=metric_version,
        observed_unit=unit,
        is_admitted=is_admitted,
        admission_label=ArtifactAdmission.ADMITTED if is_admitted else ArtifactAdmission.UNADMITTED,
        attached_at=ATTACH_TIME,
    )


# ---------------------------------------------------------------------------
# Complete clean accrual
# ---------------------------------------------------------------------------


def test_complete_clean_accrual() -> None:
    plan = _base_frozen_plan()
    atts = [_admitted_attachment(c.cell_id) for c in plan.planned_run_cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached)
    s = report.snapshot
    assert s.expected_count == len(plan.planned_run_cells)
    assert s.attached_count == s.expected_count
    assert s.admitted_count == s.expected_count
    assert s.complete_count == s.expected_count
    assert s.remaining_count == 0
    assert s.extra_count == 0
    assert s.incompatible_count == 0
    assert s.rejected_count == 0
    assert s.planned_missing_count == 0
    assert not report.is_unavailable
    assert not report.blockers or all("overrun" not in b.lower() for b in report.blockers)
    # Every cell is complete
    for cell in report.cells:
        if cell.cell_id in {c.cell_id for c in plan.planned_run_cells}:
            assert cell.status == AccrualCellStatus.COMPLETE
            assert cell.compatibility == "compatible"
            assert "admitted" in cell.admission_state


# ---------------------------------------------------------------------------
# Missing cells
# ---------------------------------------------------------------------------


def test_missing_cells() -> None:
    plan = _base_frozen_plan()
    # Attach only half
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    half = cells[: len(cells) // 2]
    atts = [_admitted_attachment(c.cell_id) for c in half]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME) if atts else plan
    # If we attached half, report should show missing
    report = build_accrual_report(attached if atts else plan)
    s = report.snapshot
    assert s.expected_count == len(cells)
    assert s.attached_count == len(half)
    assert s.planned_missing_count == len(cells) - len(half)
    assert s.remaining_count == s.expected_count - s.complete_count
    assert any(d.code == AccrualDeviationCode.MISSING_CELL for d in report.deviations)


def test_missing_cells_no_double_counting() -> None:
    plan = _base_frozen_plan()
    # No attachments at all
    report = build_accrual_report(plan)
    s = report.snapshot
    # Reconciliation: expected == planned_missing when none attached
    assert s.planned_missing_count == s.expected_count
    assert s.attached_count == 0
    assert s.admitted_count == 0
    assert (
        s.expected_count
        == s.planned_missing_count
        + s.complete_count
        + s.attached_unadmitted_count
        + s.attached_admitted_count
        + s.incompatible_count
        + s.rejected_count
        + s.withdrawn_count
    )


# ---------------------------------------------------------------------------
# Unadmitted attachment
# ---------------------------------------------------------------------------


def test_unadmitted_attachment_not_counted_as_admitted() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    # One admitted, one unadmitted
    atts = []
    for idx, c in enumerate(cells):
        if idx == 0:
            atts.append(_admitted_attachment(c.cell_id, is_admitted=True))
        elif idx == 1:
            atts.append(_admitted_attachment(c.cell_id, is_admitted=False))
        else:
            atts.append(_admitted_attachment(c.cell_id, is_admitted=True))
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached)
    s = report.snapshot
    # Admitted should be expected -1 (one unadmitted not counted)
    assert s.admitted_count == s.expected_count - 1
    # Check specific cell status
    status_by_id = {c.cell_id: c.status for c in report.cells}
    assert status_by_id[cells[1].cell_id] == AccrualCellStatus.ATTACHED_UNADMITTED
    assert status_by_id[cells[0].cell_id] == AccrualCellStatus.COMPLETE
    # Ensure unadmitted not counted as complete
    assert s.complete_count == s.expected_count - 1
    # Ensure admitted ≠ attached (attached includes unadmitted)
    assert s.attached_count == s.expected_count
    assert s.admitted_count < s.attached_count


def test_mutation_target_unadmitted_vs_admitted() -> None:
    """Regression for mutation: counting unadmitted as admitted must be detected."""
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [
        _admitted_attachment(cells[0].cell_id, is_admitted=True),
        _admitted_attachment(cells[1].cell_id, is_admitted=False),
    ]
    # Need to handle duplication? Use only 2 cells for brevity; but plan has 4 cells (2 arms *2 reps)  # noqa: E501
    # So include remaining cells as admitted to avoid missing confusion
    for c in cells[2:]:
        atts.append(_admitted_attachment(c.cell_id, is_admitted=True))
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached)
    # This test will fail if mutation counts unadmitted as admitted
    assert report.snapshot.admitted_count == len(cells) - 1
    assert report.snapshot.complete_count == len(cells) - 1
    # Check gate inconsistency: if mutation incorrectly inflates admitted, remaining would be 0 but unadmitted still blocks  # noqa: E501
    assert any(c.status == AccrualCellStatus.ATTACHED_UNADMITTED for c in report.cells)


# ---------------------------------------------------------------------------
# Rejected / withdrawn
# ---------------------------------------------------------------------------


def test_rejected_evidence() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    # Mark first cell as rejected via explicit set
    report = build_accrual_report(attached, rejected_cell_ids={cells[0].cell_id})
    s = report.snapshot
    assert s.rejected_count == 1
    assert s.admitted_count == s.expected_count - 1
    assert any(d.code == AccrualDeviationCode.REJECTED_EVIDENCE for d in report.deviations)
    status_by_id = {c.cell_id: c.status for c in report.cells}
    assert status_by_id[cells[0].cell_id] == AccrualCellStatus.REJECTED


def test_withdrawn_evidence() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached, withdrawn_cell_ids={cells[1].cell_id})
    s = report.snapshot
    assert s.withdrawn_count == 1
    assert any(d.code == AccrualDeviationCode.WITHDRAWN_EVIDENCE for d in report.deviations)
    status_by_id = {c.cell_id: c.status for c in report.cells}
    assert status_by_id[cells[1].cell_id] == AccrualCellStatus.WITHDRAWN


def test_rejected_via_generic_payload() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    generic = {"rejected_cells": [cells[0].cell_id], "withdrawn_cells": [cells[1].cell_id]}
    report = build_accrual_report(attached, generic_review_payload=generic)
    assert report.snapshot.rejected_count == 1
    assert report.snapshot.withdrawn_count == 1


# ---------------------------------------------------------------------------
# Extra cells
# ---------------------------------------------------------------------------


def test_extra_cells() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    # Add an extra cell not in planned matrix
    extra_att = EvidenceAttachment(
        artifact_fingerprint=hashlib.sha256(b"extra").hexdigest(),
        cell_id="cell-9999",
        artifact_type="metric_collection",
        observed_metric_key="task.completion.rate",
        observed_metric_version=METRIC_VERSION,
        observed_unit="ratio",
        is_admitted=True,
        admission_label=ArtifactAdmission.ADMITTED,
        attached_at=ATTACH_TIME,
    )
    atts.append(extra_att)
    attached = plan.model_copy(
        update={
            "evidence_attachments": sorted(atts, key=lambda a: a.cell_id),
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": plan.fingerprint,
        }
    )
    # Bypass attach_evidence duplicate check for extra — directly set attachments
    # But we need to ensure gate not required; build report should handle extra
    report = build_accrual_report(attached)
    assert report.snapshot.extra_count == 1
    assert any(d.code == AccrualDeviationCode.EXTRA_CELL for d in report.deviations)
    # Extra cell status
    extra_entry = next(c for c in report.cells if c.cell_id == "cell-9999")
    assert extra_entry.status == AccrualCellStatus.EXTRA


# ---------------------------------------------------------------------------
# Post-evidence amendment
# ---------------------------------------------------------------------------


def test_post_evidence_amendment_detected() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    # Create amendment after evidence
    amended = create_amendment(
        attached,
        changes={
            "limitations": "Amended limitations after evidence with sufficient length for governance."  # noqa: E501
        },
        amendment_reason="Clarify limitations after seeing early accrual pattern with sufficient length.",  # noqa: E501
        clock=lambda: LATER,
    )
    # Amended plan is DRAFT, not frozen - but we check report handles post_evidence flag
    # For monitoring, we should evaluate the frozen evidence-attached plan's history? Actually attached has no amendment history yet  # noqa: E501
    # Create a new frozen plan from amended? Simpler: test report on amended (draft) is unavailable but shows post_evidence count  # noqa: E501
    # Instead, we test report on attached which has evidence, then check that creating amendment marks post_evidence  # noqa: E501
    # Now build report on a plan that has post_evidence revision in history: we can manually construct  # noqa: E501
    # Use create_amendment then freeze again? For accrual, post_evidence is detected via revision_history is_post_evidence  # noqa: E501
    # So we will test amendment detection via a plan that was amended after evidence then re-frozen with evidence re-attached?  # noqa: E501
    # Simpler: directly construct a plan with revision_history containing post_evidence
    # Let's test that attached plan's revision doesn't yet contain post; but after amendment, new draft does  # noqa: E501
    report_draft = build_accrual_report(amended)
    assert report_draft.snapshot.post_evidence_amendment_count == 1
    assert (
        any(d.code == AccrualDeviationCode.POST_EVIDENCE_AMENDMENT for d in report_draft.deviations)
        is False
    )  # draft unavailable, no deviations
    # Now freeze the amended plan and re-attach evidence to see post_evidence deviation in ready report  # noqa: E501
    refrozen = freeze_plan(amended, clock=lambda: LATER)
    # Re-attach same evidence (need to re-attach because amendment clears evidence)
    atts2 = [_admitted_attachment(c.cell_id) for c in refrozen.planned_run_cells]
    reattached = attach_evidence(refrozen, atts2, clock=lambda: LATER)
    report2 = build_accrual_report(reattached)
    # reattached's history contains the post_evidence revision from parent
    assert report2.snapshot.post_evidence_amendment_count == 1
    assert any(d.code == AccrualDeviationCode.POST_EVIDENCE_AMENDMENT for d in report2.deviations)


# ---------------------------------------------------------------------------
# Count reconciliation
# ---------------------------------------------------------------------------


def test_count_reconciliation_invariants() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    # Mixed scenario: 1 missing, 1 unadmitted, 1 incompatible (version), 1 complete
    # But plan has 4 cells; we need to handle 4.
    # Create: cell0 missing, cell1 unadmitted, cell2 incompatible, cell3 complete
    atts = [
        # cell0 missing -> no att
        _admitted_attachment(cells[1].cell_id, is_admitted=False),
        _admitted_attachment(cells[2].cell_id, metric_version="9.9"),
        _admitted_attachment(cells[3].cell_id, is_admitted=True),
    ]
    # Need to attach with missing cell0: we must not include it
    # Use direct model_copy to bypass attach_evidence validation which would require missing handling via gate?  # noqa: E501
    attached_plan = plan.model_copy(
        update={
            "evidence_attachments": sorted(atts, key=lambda a: a.cell_id),
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": plan.fingerprint,
        }
    )
    report = build_accrual_report(attached_plan)
    s = report.snapshot
    # Reconciliation checks from service (should not raise)
    expected_sum = (
        s.planned_missing_count
        + s.attached_unadmitted_count
        + s.attached_admitted_count
        + s.complete_count
        + s.incompatible_count
        + s.rejected_count
        + s.withdrawn_count
    )
    assert expected_sum == s.expected_count
    assert s.attached_count == s.expected_count - s.planned_missing_count
    assert s.remaining_count == s.expected_count - s.complete_count
    # No double-counting: sum of mutually exclusive states == expected
    assert s.expected_count == len(cells)
    assert s.planned_missing_count == 1
    assert s.attached_unadmitted_count == 1
    assert s.incompatible_count == 1
    assert s.complete_count == 1


def test_no_double_counting_across_states() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached, rejected_cell_ids={cells[0].cell_id})
    # Check each expected cell appears exactly once in report.cells filtered to expected ids
    expected_ids = {c.cell_id for c in cells}
    reported_expected = [c for c in report.cells if c.cell_id in expected_ids]
    assert len(reported_expected) == len(expected_ids)
    # Ensure no cell has two statuses
    cell_ids = [c.cell_id for c in reported_expected]
    assert len(cell_ids) == len(set(cell_ids))


# ---------------------------------------------------------------------------
# Stopping progress
# ---------------------------------------------------------------------------


def test_stopping_progress_on_track_and_overrun() -> None:
    plan = _base_frozen_plan()
    # On track: attached == expected (4), max_replicates 4 => no overrun
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached)
    sp = report.stopping_progress
    assert sp.expected_count == len(cells)
    assert sp.attached_count == len(cells)
    assert sp.is_overrun is False
    assert sp.status == "on_track"

    # Overrun: add extra cell and set max_replicates small to trigger overrun
    extra = EvidenceAttachment(
        artifact_fingerprint=hashlib.sha256(b"extra2").hexdigest(),
        cell_id="cell-9999",
        artifact_type="metric_collection",
        observed_metric_key="task.completion.rate",
        observed_metric_version=METRIC_VERSION,
        observed_unit="ratio",
        is_admitted=True,
        admission_label=ArtifactAdmission.ADMITTED,
        attached_at=ATTACH_TIME,
    )
    atts_plus = atts + [extra]
    attached_plus = plan.model_copy(  # noqa: F841
        update={
            "evidence_attachments": sorted(atts_plus, key=lambda a: a.cell_id),
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": plan.fingerprint,
        }
    )
    # Use a plan with max_replicates=2 to force overrun when attached 4+extra
    small_plan = _base_frozen_plan(
        stopping_rule=StoppingRule(
            description="Small max replicates for overrun test.",
            max_replicates=2,
            interim_looks=1,
        )
    )
    # Need to rebuild attachments for small_plan's cells (same count 4)
    small_cells = sorted(small_plan.planned_run_cells, key=lambda c: c.cell_id)
    small_atts = [_admitted_attachment(c.cell_id) for c in small_cells] + [extra]
    small_attached = small_plan.model_copy(
        update={
            "evidence_attachments": sorted(small_atts, key=lambda a: a.cell_id),
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": small_plan.fingerprint,
        }
    )
    report_over = build_accrual_report(small_attached)
    assert report_over.stopping_progress.is_overrun is True
    assert any(d.code == AccrualDeviationCode.STOPPING_RULE_OVERRUN for d in report_over.deviations)


def test_unplanned_interim_look() -> None:
    plan = _base_frozen_plan()  # interim_looks=1
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    # Use 5 looks when allowed 1
    report = build_accrual_report(attached, interim_looks_used=5)
    assert any(d.code == AccrualDeviationCode.UNPLANNED_INTERIM_LOOK for d in report.deviations)
    assert report.stopping_progress.interim_looks_used == 5
    assert report.stopping_progress.interim_looks_allowed == 1


# ---------------------------------------------------------------------------
# Metric / unit mismatch
# ---------------------------------------------------------------------------


def test_metric_contract_mismatch() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = []
    for c in cells:
        if c.cell_id == cells[0].cell_id:
            atts.append(_admitted_attachment(c.cell_id, metric_version="9.9"))
        else:
            atts.append(_admitted_attachment(c.cell_id))
    attached = plan.model_copy(
        update={
            "evidence_attachments": sorted(atts, key=lambda a: a.cell_id),
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": plan.fingerprint,
        }
    )
    report = build_accrual_report(attached)
    assert report.snapshot.incompatible_count == 1
    assert any(d.code == AccrualDeviationCode.METRIC_CONTRACT_MISMATCH for d in report.deviations)
    assert any(
        c.status == AccrualCellStatus.INCOMPATIBLE
        for c in report.cells
        if c.cell_id == cells[0].cell_id
    )


def test_unit_mismatch() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = []
    for c in cells:
        if c.cell_id == cells[0].cell_id:
            atts.append(_admitted_attachment(c.cell_id, unit="seconds"))
        else:
            atts.append(_admitted_attachment(c.cell_id))
    attached = plan.model_copy(
        update={
            "evidence_attachments": sorted(atts, key=lambda a: a.cell_id),
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": plan.fingerprint,
        }
    )
    report = build_accrual_report(attached)
    assert report.snapshot.incompatible_count == 1
    assert any(d.code == AccrualDeviationCode.UNIT_MISMATCH for d in report.deviations)


def test_duplicate_attachment() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    dup_id = cells[0].cell_id
    att1 = _admitted_attachment(dup_id)
    att2 = EvidenceAttachment(
        artifact_fingerprint=hashlib.sha256(b"dup2").hexdigest(),
        cell_id=dup_id,
        artifact_type="metric_collection",
        observed_metric_key="task.completion.rate",
        observed_metric_version=METRIC_VERSION,
        observed_unit="ratio",
        is_admitted=True,
        admission_label=ArtifactAdmission.ADMITTED,
        attached_at=LATER,
    )
    other_atts = [_admitted_attachment(c.cell_id) for c in cells[1:]]
    all_atts = [att1, att2] + other_atts
    # Directly set without attach_evidence validation (which would reject duplicate)
    attached = plan.model_copy(
        update={
            "evidence_attachments": sorted(
                all_atts,
                key=lambda a: (a.cell_id, a.attached_at.isoformat() if a.attached_at else ""),
            ),
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": plan.fingerprint,
        }
    )
    report = build_accrual_report(attached)
    assert any(d.code == AccrualDeviationCode.DUPLICATE_ATTACHMENT for d in report.deviations)


# ---------------------------------------------------------------------------
# Fingerprint order independence
# ---------------------------------------------------------------------------


def test_order_independent_fingerprint() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    # Create attachments in reverse order
    atts_forward = [_admitted_attachment(c.cell_id) for c in cells]
    atts_reverse = list(reversed(atts_forward))
    attached_forward = attach_evidence(plan, atts_forward, clock=lambda: ATTACH_TIME)
    attached_reverse = plan.model_copy(  # noqa: F841
        update={
            "evidence_attachments": sorted(
                atts_reverse, key=lambda a: a.cell_id
            ),  # sorted inside service anyway but test order
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": plan.fingerprint,
        }
    )
    # Build reports with different input order but same content; fingerprints must match
    # To ensure order independence, we shuffle attachments before service (service sorts)
    import random

    random.seed(0)
    shuffled = atts_forward.copy()
    random.shuffle(shuffled)
    attached_shuffled = plan.model_copy(
        update={
            "evidence_attachments": shuffled,
            "status": StudyPlanStatus.EVIDENCE_ATTACHED,
            "evidence_attached_at": ATTACH_TIME,
            "fingerprint": plan.fingerprint,
        }
    )
    report1 = build_accrual_report(attached_forward)
    report2 = build_accrual_report(attached_shuffled)
    assert report1.fingerprint == report2.fingerprint
    assert report1.compute_fingerprint() == report2.compute_fingerprint()
    # Also test canonical JSON identical regardless of input order
    assert export_report_json_canonical(report1) == export_report_json_canonical(report2)


def test_fingerprint_stable_excludes_wall_clock() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached)
    fp1 = report.compute_fingerprint()
    # Recompute after touching non-semantic field? Fingerprint should be stable
    report2 = build_accrual_report(attached)
    assert report2.compute_fingerprint() == fp1


# ---------------------------------------------------------------------------
# Unavailable states
# ---------------------------------------------------------------------------


def test_unavailable_when_draft() -> None:
    # Create a draft plan (not frozen)
    plan = StudyPlan(
        plan_id="draft-001",
        study_question=StudyQuestion(
            text="Draft question with sufficient length for testing unavailable.",
            hypothesis="Hypothesis",
        ),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key="task.completion.rate",
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary for draft test.",
            )
        ],
        estimand=EstimandDefinition(
            estimand_id="est-001",
            description="Mean difference for draft test with sufficient length.",
            population="common seeds",
            effect_measure="mean_diff",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1],
        planned_arms=["baseline"],
        cohort_rules=[
            CohortRule(rule_id="cohort-001", description="Include valid tasks for draft.")
        ],
        exclusion_rules=[
            ExclusionRule(rule_id="exclude-001", description="Exclude invalid tasks for draft.")
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="Draft stopping rule with sufficient length.", max_replicates=1
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            interpretation="Draft interpretation with sufficient length.",
            comparison="two_sided",
        ),
        limitations="Draft limitations with sufficient length for validation.",
        planned_run_cells=[],
    )
    # plan.status is DRAFT by default
    report = build_accrual_report(plan)
    assert report.is_unavailable is True
    assert report.snapshot.plan_status == "DRAFT"
    assert any(w.code == "PLAN_NOT_FROZEN" for w in report.warnings)


def test_unavailable_when_no_planned_cells() -> None:
    # Freeze a plan with empty matrix? But freeze requires matrix; we can construct a frozen plan with empty cells manually  # noqa: E501
    plan = _base_frozen_plan()
    empty_plan = plan.model_copy(update={"planned_run_cells": [], "fingerprint": plan.fingerprint})
    report = build_accrual_report(empty_plan)
    assert report.is_unavailable is True
    assert any(w.code == "NO_PLANNED_CELLS" for w in report.warnings)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def test_exports_deterministic() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached)
    j1 = export_report_json(report)
    j2 = export_report_json(report)
    assert j1 == j2
    csv1 = export_cells_csv(report)
    csv2 = export_cells_csv(report)
    assert csv1 == csv2
    assert "cell_id" in csv1
    assert "status" in csv1
    dev_csv = export_deviations_csv(report)
    assert "code" in dev_csv


# ---------------------------------------------------------------------------
# Bounded inputs & fail-closed
# ---------------------------------------------------------------------------


def test_bounded_interim_looks_rejected() -> None:
    plan = _base_frozen_plan()
    with pytest.raises(ValueError, match="bounded"):
        build_accrual_report(plan, interim_looks_used=101)


def test_negative_interim_looks_rejected() -> None:
    plan = _base_frozen_plan()
    with pytest.raises(ValueError):
        build_accrual_report(plan, interim_looks_used=-1)


# ---------------------------------------------------------------------------
# No path contamination in fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_no_path_contamination() -> None:
    plan = _base_frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_admitted_attachment(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH_TIME)
    report = build_accrual_report(attached)
    payload = report.canonical_payload()
    # Ensure no local path like /tmp or /Users appears in canonical payload
    payload_str = str(payload)
    assert "/tmp" not in payload_str  # noqa: S108
    assert "/Users" not in payload_str
