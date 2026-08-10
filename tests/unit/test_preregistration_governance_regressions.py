"""Governance regression tests covering all blocker fixes (1-9)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from traffictwin.metrics.catalogue import METRIC_VERSION
from traffictwin.preregistration.models import (
    AnalysisMethod,
    ArtifactAdmission,
    CohortRule,
    DecisionGateStatus,
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
)

FIXED = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 1, 16, 12, 0, 0, tzinfo=UTC)


def _base_plan(**overrides) -> StudyPlan:
    base = StudyPlan(
        plan_id="gov-001",
        study_question=StudyQuestion(text="Governance regression: does variation change outcome under replication?", hypothesis="Variation improves."),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key="task.completion.rate",
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary completion rate.",
            )
        ],
        estimand=EstimandDefinition(estimand_id="est-001", description="Mean difference over common seeds with sufficient length.", population="common seeds", effect_measure="mean_diff"),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1, 2, 3],
        planned_arms=["baseline", "variation"],
        seeds=["seed-baseline", "seed-variation"],
        policies=["policy-a"],
        metrics=["task.completion.rate"],
        cohort_rules=[CohortRule(rule_id="cohort-001", description="Include all valid tasks for governance.")],
        exclusion_rules=[ExclusionRule(rule_id="exclude-001", description="Exclude invalid tasks for governance.")],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(description="Fixed sample with no interim looks; observe all replicates for governance.", max_replicates=3),
        decision_rule=DecisionRule(rule_type="two_sided_test", alpha=0.05, interpretation="Reject if p <0.05; non-significance not equivalence for governance.", comparison="two_sided"),
        limitations="Governance limitations with sufficient length for testing.",
        planned_run_cells=[],
    )
    if overrides:
        return base.model_copy(update=overrides)
    return base


def _frozen_plan(**overrides) -> StudyPlan:
    return freeze_plan(_base_plan(**overrides), clock=lambda: FIXED)


def _all_attachments(plan: StudyPlan, admitted: bool, label: ArtifactAdmission) -> list[EvidenceAttachment]:
    return [
        EvidenceAttachment(
            artifact_fingerprint=hashlib.sha256(c.cell_id.encode()).hexdigest(),
            cell_id=c.cell_id,
            observed_metric_key="task.completion.rate",
            observed_metric_version=METRIC_VERSION,
            observed_unit="ratio",
            is_admitted=admitted,
            admission_label=label,
        )
        for c in plan.planned_run_cells
    ]


# ---------------------------------------------------------------------------
# Blocker 1: READY must never promote unadmitted
# ---------------------------------------------------------------------------


def test_blocker1_synthetic_all_unadmitted_not_ready() -> None:
    plan = _frozen_plan(evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE)
    atts = _all_attachments(plan, admitted=False, label=ArtifactAdmission.UNADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status != DecisionGateStatus.READY
    assert attached.gate_report.is_ready is False
    assert "not explicitly admitted" in " ".join(attached.gate_report.reasons).lower() or attached.gate_report.incompatible_cells


def test_blocker1_imported_all_unadmitted_not_ready() -> None:
    plan = _frozen_plan(evidence_mode=EvidenceMode.IMPORTED_EVIDENCE)
    atts = _all_attachments(plan, admitted=False, label=ArtifactAdmission.UNADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status != DecisionGateStatus.READY


def test_blocker1_historical_all_unadmitted_not_ready() -> None:
    plan = _frozen_plan(evidence_mode=EvidenceMode.HISTORICAL_OBSERVATION)
    atts = _all_attachments(plan, admitted=False, label=ArtifactAdmission.UNADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status != DecisionGateStatus.READY


def test_blocker1_admitted_research_label_admitted_but_not_admitted_flag() -> None:
    plan = _frozen_plan(evidence_mode=EvidenceMode.ADMITTED_RESEARCH)
    # Label says ADMITTED but flag is False -> must not be READY
    atts = _all_attachments(plan, admitted=False, label=ArtifactAdmission.ADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status != DecisionGateStatus.READY


def test_blocker1_synthetic_label_but_flag_false() -> None:
    plan = _frozen_plan(evidence_mode=EvidenceMode.ADMITTED_RESEARCH)
    atts = _all_attachments(plan, admitted=False, label=ArtifactAdmission.SYNTHETIC)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status != DecisionGateStatus.READY
    # also test imported label
    atts2 = _all_attachments(plan, admitted=False, label=ArtifactAdmission.IMPORTED)
    attached2 = attach_evidence(plan, atts2, clock=lambda: LATER)
    assert attached2.gate_report.status != DecisionGateStatus.READY


def test_blocker1_all_admitted_compatible_ready() -> None:
    plan = _frozen_plan(evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE)
    atts = _all_attachments(plan, admitted=True, label=ArtifactAdmission.ADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status == DecisionGateStatus.READY
    assert attached.gate_report.is_ready is True
    assert "compatible admitted evidence" in " ".join(attached.gate_report.reasons).lower()


def test_blocker1_ready_reason_truthful() -> None:
    plan = _frozen_plan()
    atts = _all_attachments(plan, admitted=True, label=ArtifactAdmission.ADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status == DecisionGateStatus.READY
    assert "admitted" in " ".join(attached.gate_report.reasons).lower()
    # Unadmitted must not have admitted wording
    unad = _all_attachments(plan, admitted=False, label=ArtifactAdmission.UNADMITTED)
    attached2 = attach_evidence(plan, unad, clock=lambda: LATER)
    if attached2.gate_report.status == DecisionGateStatus.READY:
        pytest.fail("unadmitted must not be READY")
    assert "compatible admitted evidence" not in " ".join(attached2.gate_report.reasons).lower()


# ---------------------------------------------------------------------------
# Blocker 2: Post-evidence taint monotonic
# ---------------------------------------------------------------------------


def test_blocker2_pre_evidence_amendment() -> None:
    parent = _frozen_plan()
    child = create_amendment(parent, changes={"limitations": "Pre-evidence child limitations with sufficient length for governance."}, amendment_reason="Pre-evidence amendment reason sufficient for governance.")
    assert child.revision_history[-1].amendment_label.value == "pre_evidence"
    assert child.revision_history[-1].is_post_evidence is False


def test_blocker2_post_evidence_child() -> None:
    parent = _frozen_plan()
    atts = _all_attachments(parent, admitted=True, label=ArtifactAdmission.ADMITTED)
    with_ev = attach_evidence(parent, atts[:1], clock=lambda: LATER)
    child = create_amendment(with_ev, changes={"limitations": "Post child limitations with sufficient length for governance."}, amendment_reason="Post-evidence amendment reason sufficient for governance.")
    assert child.revision_history[-1].amendment_label.value == "post_evidence"
    assert child.revision_history[-1].is_post_evidence is True


def test_blocker2_grandchild_retains_post() -> None:
    parent = _frozen_plan()
    atts = _all_attachments(parent, admitted=True, label=ArtifactAdmission.ADMITTED)
    with_ev = attach_evidence(parent, atts[:1], clock=lambda: LATER)
    child = create_amendment(with_ev, changes={"limitations": "Child limitations with sufficient length for governance check."}, amendment_reason="Child post-evidence reason sufficient for governance.")
    # child is DRAFT, freeze it then amend again
    child_frozen = freeze_plan(child, clock=lambda: LATER)
    # attach evidence to child_frozen to ensure lineage has evidence (but child already has lineage)
    grandchild = create_amendment(child_frozen, changes={"limitations": "Grandchild limitations with sufficient length for governance check."}, amendment_reason="Grandchild post-evidence reason sufficient for governance.")
    assert grandchild.revision_history[-1].amendment_label.value == "post_evidence"
    assert grandchild.revision_history[-1].is_post_evidence is True
    # also check that child_frozen's lineage still post
    assert has_evidence_in_lineage_wrapped(grandchild) is True


def has_evidence_in_lineage_wrapped(plan: StudyPlan) -> bool:
    from traffictwin.preregistration.models import has_evidence_in_lineage

    return has_evidence_in_lineage(plan)


def test_blocker2_three_generations() -> None:
    parent = _frozen_plan()
    with_ev = attach_evidence(parent, _all_attachments(parent, True, ArtifactAdmission.ADMITTED)[:1], clock=lambda: LATER)
    c1 = create_amendment(with_ev, changes={"limitations": "Gen1 limitations with sufficient length for governance."}, amendment_reason="Gen1 post-evidence reason sufficient for governance.")
    c1f = freeze_plan(c1, clock=lambda: LATER)
    c2 = create_amendment(c1f, changes={"limitations": "Gen2 limitations with sufficient length for governance."}, amendment_reason="Gen2 post-evidence reason sufficient for governance.")
    assert c2.revision_history[-1].is_post_evidence is True
    c2f = freeze_plan(c2, clock=lambda: LATER)
    c3 = create_amendment(c2f, changes={"limitations": "Gen3 limitations with sufficient length for governance."}, amendment_reason="Gen3 post-evidence reason sufficient for governance.")
    assert c3.revision_history[-1].amendment_label.value == "post_evidence"


def test_blocker2_pre_chain_stays_pre() -> None:
    parent = _frozen_plan()
    c1 = create_amendment(parent, changes={"limitations": "C1 pre limitations with sufficient length for governance."}, amendment_reason="C1 pre reason sufficient for governance.")
    c1f = freeze_plan(c1, clock=lambda: LATER)
    c2 = create_amendment(c1f, changes={"limitations": "C2 pre limitations with sufficient length for governance."}, amendment_reason="C2 pre reason sufficient for governance.")
    assert c2.revision_history[-1].amendment_label.value == "pre_evidence"
    # ensure no evidence in lineage
    assert has_evidence_in_lineage_wrapped(c2) is False


def test_blocker2_export_import_retains_post() -> None:
    parent = _frozen_plan()
    with_ev = attach_evidence(parent, _all_attachments(parent, True, ArtifactAdmission.ADMITTED)[:1], clock=lambda: LATER)
    child = create_amendment(with_ev, changes={"limitations": "Export child limitations with sufficient length for governance."}, amendment_reason="Export child post reason sufficient for governance.")
    exported = export_plan_json(child)
    imported = import_plan_json(exported)
    # Imported child should still have post-evidence lineage
    assert has_evidence_in_lineage_wrapped(imported) is True
    # Next amendment from imported should still be post
    imported_frozen = freeze_plan(imported, clock=lambda: LATER)
    grand = create_amendment(imported_frozen, changes={"limitations": "Grand export limitations with sufficient length."}, amendment_reason="Grand export post reason sufficient for governance.")
    assert grand.revision_history[-1].is_post_evidence is True


# ---------------------------------------------------------------------------
# Blocker 3: Freeze must never silently rewrite matrix
# ---------------------------------------------------------------------------


def test_blocker3_no_cells_derives() -> None:
    plan = _base_plan()
    # No authored cells, should derive
    frozen = freeze_plan(plan, clock=lambda: FIXED)
    assert len(frozen.planned_run_cells) == len(plan.planned_arms) * (len(plan.seeds) if plan.seeds else 1) * (len(plan.policies) if plan.policies else 1) * len(plan.replication_ids) * len(plan.primary_outcomes)


def test_blocker3_exact_but_reordered_succeeds() -> None:
    plan = _base_plan()
    built = build_run_matrix(plan)
    # Shuffle order
    import random

    shuffled = built.copy()
    random.Random(0).shuffle(shuffled)
    plan_with_shuffled = plan.model_copy(update={"planned_run_cells": shuffled})
    frozen = freeze_plan(plan_with_shuffled, clock=lambda: FIXED)
    # Should succeed because set matches; order is non-semantic
    assert len(frozen.planned_run_cells) == len(built)


def test_blocker3_missing_cell_raises() -> None:
    plan = _base_plan()
    built = build_run_matrix(plan)
    missing_one = built[:-1]
    bad = plan.model_copy(update={"planned_run_cells": missing_one})
    with pytest.raises(ValueError, match="does not match deterministic matrix"):
        freeze_plan(bad, clock=lambda: FIXED)


def test_blocker3_extra_cell_raises() -> None:
    plan = _base_plan()
    built = build_run_matrix(plan)
    extra = built + [
        EvidenceAttachment.model_fields  # dummy to get extra cell: create extra PlannedRunCell
    ]  # type: ignore
    # Actually create extra cell with same structure but different replication
    from traffictwin.preregistration.models import PlannedRunCell

    extra_cell = PlannedRunCell(cell_id="cell-9999", arm_id="baseline", seed_id="seed-baseline", policy_label="policy-a", replication_id=999, metric_key="task.completion.rate", metric_version=METRIC_VERSION)
    bad = plan.model_copy(update={"planned_run_cells": built + [extra_cell]})
    with pytest.raises(ValueError, match="does not match deterministic matrix"):
        freeze_plan(bad, clock=lambda: FIXED)


def test_blocker3_wrong_arm_raises() -> None:
    plan = _base_plan()
    built = build_run_matrix(plan)
    # Change arm of first cell
    wrong = built[0].model_copy(update={"arm_id": "wrong-arm"})
    bad_cells = [wrong] + built[1:]
    bad = plan.model_copy(update={"planned_run_cells": bad_cells})
    with pytest.raises(ValueError, match="does not match deterministic matrix|ambiguous arm"):
        freeze_plan(bad, clock=lambda: FIXED)


def test_blocker3_wrong_replication_raises() -> None:
    plan = _base_plan()
    built = build_run_matrix(plan)
    wrong = built[0].model_copy(update={"replication_id": 9999})
    bad = plan.model_copy(update={"planned_run_cells": [wrong] + built[1:]})
    with pytest.raises(ValueError):
        freeze_plan(bad, clock=lambda: FIXED)


def test_blocker3_wrong_metric_version_raises() -> None:
    plan = _base_plan()
    built = build_run_matrix(plan)
    wrong = built[0].model_copy(update={"metric_version": "9.9"})
    bad = plan.model_copy(update={"planned_run_cells": [wrong] + built[1:]})
    with pytest.raises(ValueError):
        freeze_plan(bad, clock=lambda: FIXED)


def test_blocker3_five_vs_six_raises() -> None:
    # Force a plan where built is 6 but provided 5
    plan = _base_plan(replication_ids=[1, 2, 3], planned_arms=["baseline", "variation"], seeds=["seed-baseline"], policies=["policy-a"])
    built = build_run_matrix(plan)
    assert len(built) == 6
    bad = plan.model_copy(update={"planned_run_cells": built[:5]})
    with pytest.raises(ValueError):
        freeze_plan(bad, clock=lambda: FIXED)


# ---------------------------------------------------------------------------
# Blocker 4: Frozen fingerprint preservation
# ---------------------------------------------------------------------------


def test_blocker4_fingerprint_unchanged_after_attach() -> None:
    plan = _frozen_plan()
    before = plan.fingerprint
    assert before is not None
    atts = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.fingerprint == before
    assert attached.evidence_state_fingerprint is not None
    assert attached.evidence_state_fingerprint != before


def test_blocker4_amended_child_anchor() -> None:
    parent = _frozen_plan()
    child = create_amendment(parent, changes={"limitations": "Child limitations with sufficient length for anchor test."}, amendment_reason="Child amendment reason sufficient for anchor test.")
    child_frozen = freeze_plan(child, clock=lambda: FIXED)
    before_child_fp = child_frozen.fingerprint
    before_parent_fp = child_frozen.parent_fingerprint
    atts = _all_attachments(child_frozen, True, ArtifactAdmission.ADMITTED)
    attached_child = attach_evidence(child_frozen, atts, clock=lambda: LATER)
    assert attached_child.fingerprint == before_child_fp
    assert attached_child.parent_fingerprint == before_parent_fp
    assert attached_child.evidence_state_fingerprint is not None


def test_blocker4_attachment_change_does_not_alter_frozen() -> None:
    plan = _frozen_plan()
    before = plan.fingerprint
    atts1 = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    atts2 = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    # Mutate one fingerprint to be different evidence state
    atts2[0] = atts2[0].model_copy(update={"artifact_fingerprint": "b" * 64})
    attached1 = attach_evidence(plan, atts1, clock=lambda: LATER)
    attached2 = attach_evidence(plan, atts2, clock=lambda: LATER)
    assert attached1.fingerprint == before
    assert attached2.fingerprint == before
    assert attached1.evidence_state_fingerprint != attached2.evidence_state_fingerprint


def test_blocker4_export_import_preserves_frozen() -> None:
    plan = _frozen_plan()
    orig_fp = plan.fingerprint
    atts = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    exported = export_plan_json(attached)
    imported = import_plan_json(exported)
    assert imported.fingerprint == orig_fp
    assert imported.parent_fingerprint == plan.parent_fingerprint
    # Evidence state also preserved via import
    assert imported.evidence_state_fingerprint == attached.evidence_state_fingerprint


# ---------------------------------------------------------------------------
# Blocker 5: Unit compatibility
# ---------------------------------------------------------------------------


def test_blocker5_exact_unit_compatible() -> None:
    plan = _frozen_plan()
    atts = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    # All have correct unit ratio, should be ready
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status == DecisionGateStatus.READY


def test_blocker5_wrong_unit_blocks() -> None:
    plan = _frozen_plan()
    atts = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    # Change one to wrong unit
    bad = atts[0].model_copy(update={"observed_unit": "ms"})
    atts2 = [bad] + atts[1:]
    attached = attach_evidence(plan, atts2, clock=lambda: LATER)
    assert attached.gate_report.status == DecisionGateStatus.BLOCKED
    assert atts[0].cell_id in attached.gate_report.incompatible_cells
    assert "unit mismatch" in attached.gate_report.incompatibility_reasons[atts[0].cell_id].lower()


def test_blocker5_wrong_unit_with_correct_version_still_blocked() -> None:
    plan = _frozen_plan()
    atts = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    bad = atts[0].model_copy(update={"observed_unit": "count", "observed_metric_version": METRIC_VERSION})
    attached = attach_evidence(plan, [bad] + atts[1:], clock=lambda: LATER)
    assert attached.gate_report.status == DecisionGateStatus.BLOCKED


# ---------------------------------------------------------------------------
# Blocker 6: Incompatibility reasons reach report
# ---------------------------------------------------------------------------


def test_blocker6_version_mismatch_reason() -> None:
    plan = _frozen_plan()
    atts = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    bad = atts[0].model_copy(update={"observed_metric_version": "9.9"})
    attached = attach_evidence(plan, [bad] + atts[1:], clock=lambda: LATER)
    assert attached.gate_report.incompatible_cells
    reason = attached.gate_report.incompatibility_reasons[bad.cell_id]
    assert "metric_version mismatch" in reason.lower()
    # Also check attachment itself has reason
    assert attached.evidence_attachments[0].incompatibility_reason is not None


def test_blocker6_admission_failure_reason() -> None:
    plan = _frozen_plan()
    atts = _all_attachments(plan, False, ArtifactAdmission.UNADMITTED)
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    # All should be incompatible due to admission
    assert attached.gate_report.incompatible_cells
    for cid in attached.gate_report.incompatible_cells:
        assert "not explicitly admitted" in attached.gate_report.incompatibility_reasons[cid].lower()


# ---------------------------------------------------------------------------
# Blocker 7: Duplicate attachment cell IDs
# ---------------------------------------------------------------------------


def test_blocker7_duplicate_rejected() -> None:
    plan = _frozen_plan()
    atts = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    # Duplicate first cell
    dup = atts[0]
    atts_dup = [dup, dup] + atts[1:]
    with pytest.raises(ValueError, match="duplicate attachment cell_ids"):
        attach_evidence(plan, atts_dup, clock=lambda: LATER)


def test_blocker7_unadmitted_then_admitted_same_cell_rejected() -> None:
    plan = _frozen_plan()
    base = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    # Create two attachments for same cell, one unadmitted, one admitted
    cell = base[0].cell_id
    a1 = EvidenceAttachment(artifact_fingerprint="a" * 64, cell_id=cell, observed_metric_key="task.completion.rate", observed_metric_version=METRIC_VERSION, observed_unit="ratio", is_admitted=False, admission_label=ArtifactAdmission.UNADMITTED)
    a2 = EvidenceAttachment(artifact_fingerprint="b" * 64, cell_id=cell, observed_metric_key="task.completion.rate", observed_metric_version=METRIC_VERSION, observed_unit="ratio", is_admitted=True, admission_label=ArtifactAdmission.ADMITTED)
    with pytest.raises(ValueError, match="duplicate"):
        attach_evidence(plan, [a1, a2] + base[1:], clock=lambda: LATER)


def test_blocker7_distinct_cells_ok() -> None:
    plan = _frozen_plan()
    atts = _all_attachments(plan, True, ArtifactAdmission.ADMITTED)
    # Distinct cells should not raise
    attached = attach_evidence(plan, atts, clock=lambda: LATER)
    assert attached.gate_report.status == DecisionGateStatus.READY


# ---------------------------------------------------------------------------
# Blocker 8: Seed/policy matrix semantics
# ---------------------------------------------------------------------------


def test_blocker8_seeds_all_represented() -> None:
    plan = _base_plan(seeds=["a", "b", "c"], policies=["p1"], planned_arms=["baseline", "variation"])
    matrix = build_run_matrix(plan)
    # 2 arms *3 seeds *1 pol *3 reps *1 primary =18
    assert len(matrix) == 2 * 3 * 1 * 3 * 1
    seed_ids = {c.seed_id for c in matrix}
    assert seed_ids == {"a", "b", "c"}


def test_blocker8_policies_both_represented() -> None:
    plan = _base_plan(seeds=["a"], policies=["p1", "p2"], planned_arms=["baseline", "variation"])
    matrix = build_run_matrix(plan)
    assert len(matrix) == 2 * 1 * 2 * 3 * 1
    pols = {c.policy_label for c in matrix}
    assert pols == {"p1", "p2"}


def test_blocker8_permuting_input_same_canonical_matrix() -> None:
    plan1 = _base_plan(seeds=["a", "b", "c"], policies=["p1", "p2"])
    plan2 = _base_plan(seeds=["c", "a", "b"], policies=["p2", "p1"])
    m1 = {(c.arm_id, c.seed_id, c.policy_label, c.replication_id, c.metric_key) for c in build_run_matrix(plan1)}
    m2 = {(c.arm_id, c.seed_id, c.policy_label, c.replication_id, c.metric_key) for c in build_run_matrix(plan2)}
    assert m1 == m2


def test_blocker8_changing_seed_changes_fingerprint() -> None:
    plan1 = _base_plan(seeds=["a", "b"])
    plan2 = _base_plan(seeds=["a", "c"])
    f1 = freeze_plan(plan1, clock=lambda: FIXED).fingerprint
    f2 = freeze_plan(plan2, clock=lambda: FIXED).fingerprint
    assert f1 != f2


def test_blocker8_matrix_size_calculation() -> None:
    plan = _base_plan(seeds=["a", "b"], policies=["p1", "p2"], replication_ids=[1, 2], planned_arms=["baseline", "variation"], primary_outcomes=[
        OutcomeDefinition(outcome_id="p1", metric_key="task.completion.rate", metric_version=METRIC_VERSION, unit="ratio", denominator="generated_tasks", description="Primary 1 for size calc."),
        OutcomeDefinition(outcome_id="p2", metric_key="task.latency.mean_ms", metric_version=METRIC_VERSION, unit="ms", denominator="observed_tasks", description="Primary 2 for size calc."),
    ])
    # 2*2*2*2*2=32
    assert len(build_run_matrix(plan)) == 32


# ---------------------------------------------------------------------------
# Blocker 9: Bounded range expansion
# ---------------------------------------------------------------------------


def test_blocker9_huge_range_rejected_before_materialisation() -> None:
    plan = _base_plan(replication_ids=[], replication_generation_rule="0..40000000")
    # Should fail via cardinality check, not OOM
    with pytest.raises(ValueError, match="exceeds limit"):
        build_run_matrix(plan)
    with pytest.raises(ValueError, match="not freezable|exceeds limit"):
        freeze_plan(plan, clock=lambda: FIXED)


def test_blocker9_range_cardinality_with_seeds_policies() -> None:
    # arms 2 * seeds 2 * policies 2 * reps 100 * prim 1 =800, under limit 10k should pass
    plan_ok = _base_plan(seeds=["a", "b"], policies=["p1", "p2"], replication_generation_rule="range:100", replication_ids=[], planned_arms=["baseline", "variation"])
    assert len(build_run_matrix(plan_ok)) == 800
    # Now huge: 2*2*2*2000*1=16000 >10000 should fail
    plan_huge = _base_plan(seeds=["a", "b"], policies=["p1", "p2"], replication_generation_rule="range:2000", replication_ids=[], planned_arms=["baseline", "variation"])
    with pytest.raises(ValueError, match="exceeds limit"):
        build_run_matrix(plan_huge)


# ---------------------------------------------------------------------------
# Blocker 11: DecisionGateReport invariants
# ---------------------------------------------------------------------------


def test_blocker11_ready_requires_flags() -> None:
    from traffictwin.preregistration.models import DecisionGateReport, DecisionGateStatus

    with pytest.raises(ValueError):
        DecisionGateReport(status=DecisionGateStatus.READY, is_ready=False, is_blocked=False, is_unavailable=False)
    with pytest.raises(ValueError):
        DecisionGateReport(status=DecisionGateStatus.READY, is_ready=True, is_blocked=True, is_unavailable=False)
    with pytest.raises(ValueError):
        DecisionGateReport(status=DecisionGateStatus.BLOCKED, is_ready=True, is_blocked=True, is_unavailable=False)
    with pytest.raises(ValueError):
        DecisionGateReport(status=DecisionGateStatus.UNAVAILABLE, is_ready=True, is_blocked=False, is_unavailable=True)
    # Valid
    ok = DecisionGateReport(status=DecisionGateStatus.READY, is_ready=True, is_blocked=False, is_unavailable=False)
    assert ok.status == DecisionGateStatus.READY
    ok2 = DecisionGateReport(status=DecisionGateStatus.BLOCKED, is_ready=False, is_blocked=True, is_unavailable=False)
    assert ok2.is_blocked is True
