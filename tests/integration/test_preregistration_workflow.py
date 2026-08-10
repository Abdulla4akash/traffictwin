"""Integration coverage for preregistration workflow."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from traffictwin.metrics.catalogue import METRIC_VERSION
from traffictwin.preregistration.models import (
    AnalysisMethod,
    ArtifactAdmission,
    CohortRule,
    DecisionRule,
    EvidenceAttachment,
    EvidenceMode,
    EstimandDefinition,
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
from traffictwin.preregistration.service import (
    attach_evidence,
    build_run_matrix,
    create_amendment,
    evaluate_gate,
    export_plan_json,
    freeze_plan,
    import_plan_json,
    planned_vs_observed_matrix,
    validate_study_plan,
)

FIXED = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 16, 12, 0, 0, tzinfo=UTC)


def _plan() -> StudyPlan:
    return StudyPlan(
        plan_id="integration-001",
        study_question=StudyQuestion(
            text="Integration test: does variation change outcome over replicates?",
            hypothesis="Variation improves.",
        ),
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key="task.completion.rate",
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary completion rate integration test.",
            )
        ],
        secondary_outcomes=[
            OutcomeDefinition(
                outcome_id="secondary-001",
                metric_key="task.latency.mean_ms",
                metric_version=METRIC_VERSION,
                unit="ms",
                denominator="observed_tasks",
                description="Secondary latency mean.",
            )
        ],
        estimand=EstimandDefinition(
            estimand_id="est-001",
            description="Mean difference for integration testing with sufficient length.",
            population="common seeds",
            effect_measure="mean_diff",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[10, 20],
        planned_arms=["baseline", "variation"],
        seeds=["seed-a", "seed-b"],
        policies=["policy-x"],
        metrics=["task.completion.rate"],
        cohort_rules=[
            CohortRule(rule_id="cohort-001", description="Include valid tasks integration.")
        ],
        exclusion_rules=[
            ExclusionRule(rule_id="exclude-001", description="Exclude invalid tasks integration.")
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_BOOTSTRAP,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="Integration stopping rule with sufficient length for validation.",
            max_replicates=2,
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            interpretation="Integration decision interpretation text sufficient length.",
            comparison="two_sided",
        ),
        limitations="Integration limitations with sufficient characters for freeze.",
    )


def test_integration_build_and_freeze_and_attach() -> None:
    plan = _plan()
    assert validate_study_plan(plan) == []
    matrix = build_run_matrix(plan)
    # 2 arms *2 seeds *1 policy *2 reps *1 primary =8
    assert len(matrix) == 8
    frozen = freeze_plan(plan, clock=lambda: FIXED)
    assert frozen.status == StudyPlanStatus.FROZEN
    assert len(frozen.planned_run_cells) == 8
    # Export / import round-trip
    exported = export_plan_json(frozen)
    imported = import_plan_json(exported)
    assert imported.fingerprint == frozen.fingerprint

    # Verify matrix preserved
    assert len(imported.planned_run_cells) == 8

    # Attach evidence for all cells
    atts = [
        EvidenceAttachment(
            artifact_fingerprint=hashlib.sha256(c.cell_id.encode()).hexdigest(),
            cell_id=c.cell_id,
            observed_metric_key="task.completion.rate",
            observed_metric_version=METRIC_VERSION,
            observed_unit="ratio",
            is_admitted=True,
            admission_label=ArtifactAdmission.ADMITTED,
        )
        for c in frozen.planned_run_cells
    ]
    attached = attach_evidence(frozen, atts, clock=lambda: LATER)
    assert attached.status == StudyPlanStatus.EVIDENCE_ATTACHED
    cov = planned_vs_observed_matrix(attached)
    assert cov["expected_count"] == 8
    assert cov["observed_count"] == 8
    assert all(r["status"] == "present" for r in cov["rows"] if r["arm_id"] is not None)
    gate = attached.gate_report
    assert gate is not None
    assert gate.status.value == "ready"


def test_integration_amendment_chain() -> None:
    plan = _plan()
    frozen = freeze_plan(plan, clock=lambda: FIXED)
    # First amendment
    amended = create_amendment(
        frozen,
        changes={"limitations": "First amendment limitations with enough length for governance."},
        amendment_reason="First amendment reason sufficient for governance tracking.",
    )
    assert amended.version == 2
    assert amended.parent_fingerprint == frozen.fingerprint
    frozen2 = freeze_plan(amended, clock=lambda: LATER)
    assert frozen2.status == StudyPlanStatus.FROZEN
    # Second amendment post-evidence
    att = EvidenceAttachment(
        artifact_fingerprint="a" * 64,
        cell_id=frozen2.planned_run_cells[0].cell_id,
        observed_metric_key="task.completion.rate",
        observed_metric_version=METRIC_VERSION,
        observed_unit="ratio",
        is_admitted=True,
        admission_label=ArtifactAdmission.ADMITTED,
    )
    with_ev = attach_evidence(frozen2, [att], clock=lambda: LATER)
    amended2 = create_amendment(
        with_ev,
        changes={"limitations": "Second amendment post evidence with sufficient length."},
        amendment_reason="Second amendment post evidence reason sufficient length.",
    )
    assert amended2.revision_history[-1].is_post_evidence is True
    assert amended2.revision_history[-1].amendment_label.value == "post_evidence"


def test_integration_gate_blocked_on_incompatible() -> None:
    plan = _plan()
    frozen = freeze_plan(plan, clock=lambda: FIXED)
    bad_atts = [
        EvidenceAttachment(
            artifact_fingerprint=hashlib.sha256(c.cell_id.encode()).hexdigest(),
            cell_id=c.cell_id,
            observed_metric_key="task.completion.rate",
            observed_metric_version="9.9",  # incompatible
            observed_unit="ratio",
            is_admitted=True,
            admission_label=ArtifactAdmission.ADMITTED,
        )
        for c in frozen.planned_run_cells
    ]
    attached = attach_evidence(frozen, bad_atts, clock=lambda: LATER)
    assert attached.gate_report.status.value == "blocked"
    assert len(attached.gate_report.incompatible_cells) == len(frozen.planned_run_cells)
