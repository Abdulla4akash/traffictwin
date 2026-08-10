"""Integration tests for accrual monitor — end-to-end plan → report."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

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
    StudyQuestion,
)
from traffictwin.preregistration.service import attach_evidence, freeze_plan
from traffictwin.study_accrual.service import build_accrual_report

FIXED = datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC)
ATTACH = datetime(2026, 1, 11, 10, 0, 0, tzinfo=UTC)


def _frozen_plan() -> StudyPlan:
    base = StudyPlan(
        plan_id="accrual-integration-001",
        study_question=StudyQuestion(
            text="Integration test: does variation change completion under predeclared replication?",  # noqa: E501
            hypothesis="Variation improves.",
        ),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key="task.completion.rate",
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary completion rate for integration.",
            )
        ],
        estimand=EstimandDefinition(
            estimand_id="est-001",
            description="Mean difference for integration with sufficient length.",
            population="common seeds",
            effect_measure="mean_diff",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1, 2],
        planned_arms=["baseline", "variation"],
        cohort_rules=[
            CohortRule(rule_id="cohort-001", description="Include valid tasks for integration.")
        ],
        exclusion_rules=[
            ExclusionRule(
                rule_id="exclude-001", description="Exclude invalid data for integration."
            )
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="Integration stopping rule with sufficient length.",
            max_replicates=4,
            interim_looks=2,
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            interpretation="Integration interpretation with sufficient length.",
            comparison="two_sided",
        ),
        limitations="Integration limitations with sufficient length for validation.",
        planned_run_cells=[],
    )
    return freeze_plan(base, clock=lambda: FIXED)


def _att(cell_id: str, is_admitted: bool = True) -> EvidenceAttachment:
    return EvidenceAttachment(
        artifact_fingerprint=hashlib.sha256(f"fp-{cell_id}".encode()).hexdigest(),
        cell_id=cell_id,
        artifact_type="metric_collection",
        observed_metric_key="task.completion.rate",
        observed_metric_version=METRIC_VERSION,
        observed_unit="ratio",
        is_admitted=is_admitted,
        admission_label=ArtifactAdmission.ADMITTED if is_admitted else ArtifactAdmission.UNADMITTED,
        attached_at=ATTACH,
    )


def test_integration_freeze_attach_monitor_reconciles() -> None:
    plan = _frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_att(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH)
    report = build_accrual_report(attached)
    s = report.snapshot
    # Reconciliation as per service
    total_expected_states = (
        s.planned_missing_count
        + s.attached_unadmitted_count
        + s.attached_admitted_count
        + s.complete_count
        + s.incompatible_count
        + s.rejected_count
        + s.withdrawn_count
    )
    assert total_expected_states == s.expected_count
    assert s.attached_count == s.expected_count - s.planned_missing_count
    assert s.remaining_count == s.expected_count - s.complete_count
    # No extra
    assert s.extra_count == 0
    assert report.fingerprint is not None
    assert len(report.fingerprint) == 64


def test_integration_partial_accrual_with_blockers() -> None:
    plan = _frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    # Only attach half, with one unadmitted
    half = cells[:2]
    atts = [_att(half[0].cell_id, is_admitted=True), _att(half[1].cell_id, is_admitted=False)]
    attached = plan.model_copy(
        update={
            "evidence_attachments": sorted(atts, key=lambda a: a.cell_id),
            "status": attached_status(plan),
            "evidence_attached_at": ATTACH,
            "fingerprint": plan.fingerprint,
        }
    )
    report = build_accrual_report(attached)
    assert report.snapshot.planned_missing_count > 0
    assert report.snapshot.attached_unadmitted_count == 1
    assert report.blockers  # Should have blockers due to incomplete accrual


def attached_status(plan: StudyPlan):  # type: ignore[no-untyped-def]  # noqa: ANN201
    from traffictwin.preregistration.models import StudyPlanStatus

    return StudyPlanStatus.EVIDENCE_ATTACHED


def test_integration_with_generic_review_and_power_fingerprint() -> None:
    plan = _frozen_plan()
    # Add power plan fingerprint
    plan_with_power = plan.model_copy(
        update={"power_plan_fingerprint": hashlib.sha256(b"power").hexdigest()}
    )
    cells = sorted(plan_with_power.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_att(c.cell_id) for c in cells]
    attached = attach_evidence(plan_with_power, atts, clock=lambda: ATTACH)
    generic = {"rejected_cells": [cells[0].cell_id], "interim_looks_used": 2}
    report = build_accrual_report(attached, generic_review_payload=generic)
    assert report.power_plan_fingerprint == plan_with_power.power_plan_fingerprint
    assert report.snapshot.power_plan_fingerprint == plan_with_power.power_plan_fingerprint
    assert report.snapshot.rejected_count == 1


def test_integration_csv_export_contains_all_cells() -> None:
    from traffictwin.study_accrual.exports import export_cells_csv

    plan = _frozen_plan()
    cells = sorted(plan.planned_run_cells, key=lambda c: c.cell_id)
    atts = [_att(c.cell_id) for c in cells]
    attached = attach_evidence(plan, atts, clock=lambda: ATTACH)
    report = build_accrual_report(attached)
    csv_text = export_cells_csv(report)
    lines = csv_text.strip().split("\n")
    # header + one row per cell
    assert len(lines) == 1 + len(report.cells)
    assert lines[0].startswith("cell_id")
