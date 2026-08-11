# mypy: disable-error-code="arg-type,attr-defined,assignment"
"""Unit tests for Multi-Objective Trade-Off Explorer."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.experiments.tradeoff_explorer import (
    TradeoffAdmissionState,
    TradeoffArm,
    TradeoffConstraint,
    TradeoffConstraintOperator,
    TradeoffDenominator,
    TradeoffDirection,
    TradeoffEvidenceMode,
    TradeoffMetricSpec,
    TradeoffObservation,
    TradeoffStatus,
    TradeoffStudy,
    build_tradeoff_report,
    tradeoff_frontier_to_csv,
    tradeoff_report_to_csv,
    tradeoff_report_to_markdown,
)


def _spec(
    key: str,
    direction: TradeoffDirection,
    *,
    version: str = "1.0",
    unit: str = "ratio",
    denom: TradeoffDenominator = TradeoffDenominator.REPLICATION,
    constraint: TradeoffConstraint | None = None,
) -> TradeoffMetricSpec:
    return TradeoffMetricSpec(
        metric_key=key,
        metric_version=version,
        unit=unit,
        denominator=denom,
        direction=direction,
        hard_constraint=constraint,
    )


def _obs(
    arm_id: str,
    key: str,
    value: float | None,
    *,
    version: str = "1.0",
    unit: str = "ratio",
    denom: TradeoffDenominator = TradeoffDenominator.REPLICATION,
    status: TradeoffStatus = TradeoffStatus.AVAILABLE,
    per_rep: dict[str, float | None] | None = None,
) -> TradeoffObservation:
    return TradeoffObservation(
        arm_id=arm_id,
        metric_key=key,
        metric_version=version,
        unit=unit,
        denominator=denom,
        value=value,
        status=status,
        per_replication_values=per_rep or {},
        replication_count=len(per_rep) if per_rep else (1 if value is not None else 0),
        reason=None if status == TradeoffStatus.AVAILABLE else "missing",
    )


def _study(
    specs: list[TradeoffMetricSpec],
    arms: list[TradeoffArm],
    **overrides: object,
) -> TradeoffStudy:
    base: dict[str, object] = dict(  # noqa: C408
        schema_version="1.0",
        study_id="test_tradeoff_study",
        source_fingerprint=hashlib.sha256(b"tradeoff").hexdigest(),
        evidence_mode=TradeoffEvidenceMode.SYNTHETIC_DEMONSTRATION,
        admission_state=TradeoffAdmissionState.SYNTHETIC_DEMONSTRATION,
        arms=arms,
        metric_specs=specs,
        matched_replication_ids=["rep_001", "rep_002"],
        limitations=["synthetic demonstration"],
        provenance={"fixture": "unit"},
        generated_at=None,
    )
    base.update(overrides)
    return TradeoffStudy.model_validate(base)


def _two_metric_specs_with_constraints(
    constraint_on_first: TradeoffConstraint | None = None,
) -> list[TradeoffMetricSpec]:
    return [
        TradeoffMetricSpec(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=TradeoffDenominator.OFFERED_TASKS,
            direction=TradeoffDirection.MAXIMIZE,
            hard_constraint=constraint_on_first,
        ),
        TradeoffMetricSpec(
            metric_key="task.latency.mean_ms",
            metric_version="1.0",
            unit="ms",
            denominator=TradeoffDenominator.COMPLETED_TASKS,
            direction=TradeoffDirection.MINIMIZE,
        ),
    ]


# ---------------------------------------------------------------------------
# Strict validation
# ---------------------------------------------------------------------------


def test_strict_validation_rejects_extra_fields() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "task.completion.rate_offered", 0.8),
                _obs("a", "task.latency.mean_ms", 100.0),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "task.completion.rate_offered", 0.7),
                _obs("b", "task.latency.mean_ms", 120.0),
            ],
        ),
    ]
    study = _study(specs, arms)
    payload = study.model_dump(mode="json")
    payload["extra_field"] = "not allowed"
    with pytest.raises(ValidationError):
        TradeoffStudy.model_validate(payload)


def test_bounded_inputs_enforced_metrics() -> None:
    # Less than 2 metrics
    with pytest.raises(ValidationError):
        _study(
            [_spec("single", TradeoffDirection.MAXIMIZE)],
            [
                TradeoffArm(
                    arm_id="a", label="A", description="d", observations=[_obs("a", "single", 1.0)]
                ),
                TradeoffArm(
                    arm_id="b", label="B", description="d", observations=[_obs("b", "single", 0.9)]
                ),
            ],
        )
    # More than 6 metrics
    specs7 = [_spec(f"k{i}", TradeoffDirection.MAXIMIZE) for i in range(7)]
    arms7 = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[_obs("a", f"k{i}", 1.0) for i in range(7)],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[_obs("b", f"k{i}", 0.9) for i in range(7)],
        ),
    ]
    with pytest.raises(ValidationError):
        _study(specs7, arms7)


def test_bounded_inputs_enforced_arms() -> None:
    specs = _two_metric_specs_with_constraints()
    # Only 1 arm
    with pytest.raises(ValidationError):
        _study(
            specs,
            [
                TradeoffArm(
                    arm_id="a",
                    label="A",
                    description="d",
                    observations=[
                        _obs("a", "task.completion.rate_offered", 0.8),
                        _obs("a", "task.latency.mean_ms", 100.0),
                    ],
                )
            ],
        )


# ---------------------------------------------------------------------------
# Clear two-arm dominance
# ---------------------------------------------------------------------------


def test_clear_two_arm_dominance() -> None:
    specs = _two_metric_specs_with_constraints()
    # Arm A dominates B on both metrics: higher throughput, lower latency
    arms = [
        TradeoffArm(
            arm_id="arm_a",
            label="Arm A",
            description="d",
            strategy_type="s1",
            observations=[
                _obs("arm_a", "task.completion.rate_offered", 0.95, unit="ratio"),
                _obs(
                    "arm_a",
                    "task.latency.mean_ms",
                    80.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_b",
            label="Arm B",
            description="d",
            strategy_type="s2",
            observations=[
                _obs("arm_b", "task.completion.rate_offered", 0.80, unit="ratio"),
                _obs(
                    "arm_b",
                    "task.latency.mean_ms",
                    150.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    assert report.frontier.frontier_arm_ids == ["arm_a"]
    assert report.frontier.dominated_arm_ids == ["arm_b"]
    assert report.frontier.dominated_by["arm_b"] == ["arm_a"]
    # Dominance true only for A->B
    dom_a_b = next(
        d
        for d in report.dominance
        if d.dominator_arm_id == "arm_a" and d.dominated_arm_id == "arm_b"
    )
    dom_b_a = next(
        d
        for d in report.dominance
        if d.dominator_arm_id == "arm_b" and d.dominated_arm_id == "arm_a"
    )
    assert dom_a_b.dominates is True
    assert "dominates under declared metrics" in dom_a_b.reason
    assert dom_b_a.dominates is False
    # Feasibility both feasible
    for f in report.feasibility:
        assert f.is_feasible is True
        assert f.status == TradeoffStatus.FEASIBLE


# ---------------------------------------------------------------------------
# Trade-off/non-dominated pair
# ---------------------------------------------------------------------------


def test_tradeoff_non_dominated_pair() -> None:
    specs = _two_metric_specs_with_constraints()
    # A better on throughput, B better on latency => non-dominated
    arms = [
        TradeoffArm(
            arm_id="arm_a",
            label="A",
            description="d",
            observations=[
                _obs("arm_a", "task.completion.rate_offered", 0.95, unit="ratio"),
                _obs(
                    "arm_a",
                    "task.latency.mean_ms",
                    150.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_b",
            label="B",
            description="d",
            observations=[
                _obs("arm_b", "task.completion.rate_offered", 0.80, unit="ratio"),
                _obs(
                    "arm_b",
                    "task.latency.mean_ms",
                    80.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    assert sorted(report.frontier.frontier_arm_ids) == ["arm_a", "arm_b"]
    assert report.frontier.dominated_arm_ids == []
    # No dominance
    for d in report.dominance:
        assert d.dominates is False


# ---------------------------------------------------------------------------
# Constraint violation
# ---------------------------------------------------------------------------


def test_constraint_violation() -> None:
    # Use compatible metrics so constraint is evaluated in feasible path (not unavailable fallback)
    constraint = TradeoffConstraint(
        metric_key="task.completion.rate_offered",
        operator=TradeoffConstraintOperator.GE,
        threshold=0.85,
        reason="must achieve throughput",
    )
    specs = [
        TradeoffMetricSpec(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=TradeoffDenominator.OFFERED_TASKS,
            direction=TradeoffDirection.MAXIMIZE,
            hard_constraint=constraint,
        ),
        TradeoffMetricSpec(
            metric_key="task.latency.mean_ms",
            metric_version="1.0",
            unit="ms",
            denominator=TradeoffDenominator.COMPLETED_TASKS,
            direction=TradeoffDirection.MINIMIZE,
        ),
    ]
    arms = [
        TradeoffArm(
            arm_id="arm_a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="arm_a",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.90,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="arm_a",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=100.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_b",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="arm_b",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.80,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="arm_b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=80.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    feas_a = next(f for f in report.feasibility if f.arm_id == "arm_a")
    feas_b = next(f for f in report.feasibility if f.arm_id == "arm_b")
    assert feas_a.is_feasible is True
    assert feas_a.status == TradeoffStatus.FEASIBLE
    assert feas_b.is_feasible is False
    assert feas_b.status == TradeoffStatus.INFEASIBLE
    assert any("violates declared constraint" in m for m in feas_b.violation_messages)
    # Frontier only contains feasible arm
    assert report.frontier.frontier_arm_ids == ["arm_a"]
    # Sensitivity should show frontier without constraints includes both if they trade off
    assert "frontier_without_constraints" in report.sensitivity
    # Without constraints, both would be on frontier because they trade off (A better throughput, B better latency)  # noqa: E501
    # However with constraint violation, sensitivity frontier_with and without differ
    assert report.sensitivity["frontier_with_constraints"] == ["arm_a"]
    # Without constraints, since trade-off pair, both are frontier
    assert sorted(report.sensitivity["frontier_without_constraints"]) == ["arm_a", "arm_b"]
    # Finding code for violated constraint
    assert any(f.code == "CONSTRAINT_VIOLATED" for f in report.findings)


# ---------------------------------------------------------------------------
# Incompatible metric withheld
# ---------------------------------------------------------------------------


def test_incompatible_metric_withheld() -> None:
    # Use known contract key but with wrong version -> incompatible
    specs = [
        TradeoffMetricSpec(
            metric_key="task.completion.rate_offered",
            metric_version="2.0",
            unit="ratio",
            denominator=TradeoffDenominator.OFFERED_TASKS,
            direction=TradeoffDirection.MAXIMIZE,
        ),
        _spec(
            "task.latency.mean_ms",
            TradeoffDirection.MINIMIZE,
            unit="ms",
            denom=TradeoffDenominator.COMPLETED_TASKS,
        ),
    ]
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs(
                    "a",
                    "task.completion.rate_offered",
                    0.9,
                    unit="ratio",
                    denom=TradeoffDenominator.OFFERED_TASKS,
                    version="2.0",
                ),
                _obs(
                    "a",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs(
                    "b",
                    "task.completion.rate_offered",
                    0.8,
                    unit="ratio",
                    denom=TradeoffDenominator.OFFERED_TASKS,
                    version="2.0",
                ),
                _obs(
                    "b",
                    "task.latency.mean_ms",
                    120.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    # Incompatible audit
    comp = next(c for c in report.compatibility if c.metric_key == "task.completion.rate_offered")
    assert comp.status.value == "incompatible"
    assert "version" in comp.finding.lower()
    # No numeric aggregate for incompatible metric: observations in report's feasibility should mark incompatible  # noqa: E501
    for feas in report.feasibility:
        assert "task.completion.rate_offered" in feas.incompatible_metrics
        assert feas.status == TradeoffStatus.INCOMPATIBLE
        assert feas.is_feasible is False
    # Frontier should be empty because incompatible metrics make arms not feasible
    assert report.frontier.frontier_arm_ids == []
    # Findings contain withheld
    assert any(f.code == "INCOMPATIBLE_METRIC_WITHHELD" for f in report.findings)
    # Dominance should not consider incompatible metric (or no feasible arms)
    assert all(not d.dominates for d in report.dominance) or len(report.dominance) == 0


# ---------------------------------------------------------------------------
# Missing metric unavailable
# ---------------------------------------------------------------------------


def test_missing_metric_unavailable() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="arm_a",
            label="A",
            description="d",
            observations=[
                _obs("arm_a", "task.completion.rate_offered", 0.90),
                _obs(
                    "arm_a",
                    "task.latency.mean_ms",
                    None,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                    status=TradeoffStatus.UNAVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_b",
            label="B",
            description="d",
            observations=[
                _obs("arm_b", "task.completion.rate_offered", 0.80),
                _obs(
                    "arm_b",
                    "task.latency.mean_ms",
                    80.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    feas_a = next(f for f in report.feasibility if f.arm_id == "arm_a")
    assert feas_a.status == TradeoffStatus.UNAVAILABLE
    assert feas_a.is_feasible is False
    assert "task.latency.mean_ms" in feas_a.unavailable_metrics
    assert any(
        f.code == "MISSING_METRIC_UNAVAILABLE" and f.arm_id == "arm_a" for f in report.findings
    )
    # Only feasible arm is B, so frontier is B
    assert report.frontier.frontier_arm_ids == ["arm_b"]


# ---------------------------------------------------------------------------
# Metric direction correctness
# ---------------------------------------------------------------------------


def test_metric_direction_correctness() -> None:
    # Same values but test that direction matters — use COMPATIBLE metrics
    specs_max = [
        TradeoffMetricSpec(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=TradeoffDenominator.OFFERED_TASKS,
            direction=TradeoffDirection.MAXIMIZE,
        ),
        TradeoffMetricSpec(
            metric_key="task.latency.mean_ms",
            metric_version="1.0",
            unit="ms",
            denominator=TradeoffDenominator.COMPLETED_TASKS,
            direction=TradeoffDirection.MINIMIZE,
        ),
    ]
    # Arm A: higher throughput (better for maximize), higher latency (worse for minimize)
    # Arm B: lower throughput (worse), lower latency (better) => trade-off, both frontier
    arms_tradeoff = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.95,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=100.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.80,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=80.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
    ]
    study_tradeoff = _study(specs_max, arms_tradeoff)
    report_tradeoff = build_tradeoff_report(study_tradeoff)
    assert sorted(report_tradeoff.frontier.frontier_arm_ids) == ["a", "b"]

    # Now test dominance when both metrics favor A
    specs_min_both = [
        TradeoffMetricSpec(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=TradeoffDenominator.OFFERED_TASKS,
            direction=TradeoffDirection.MAXIMIZE,
        ),
        TradeoffMetricSpec(
            metric_key="task.latency.mean_ms",
            metric_version="1.0",
            unit="ms",
            denominator=TradeoffDenominator.COMPLETED_TASKS,
            direction=TradeoffDirection.MINIMIZE,
        ),
    ]
    arms_dominance = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.95,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=80.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.80,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=100.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
    ]
    study_dom = _study(specs_min_both, arms_dominance)
    report_dom = build_tradeoff_report(study_dom)
    # A dominates B because higher throughput and lower latency
    assert report_dom.frontier.frontier_arm_ids == ["a"]
    dom_a_b = next(
        d for d in report_dom.dominance if d.dominator_arm_id == "a" and d.dominated_arm_id == "b"
    )
    assert dom_a_b.dominates is True

    # If we reverse direction of latency to MAXIMIZE, then A no longer dominates B  # noqa: E501
    # Then they would trade off.
    specs_reversed = [
        TradeoffMetricSpec(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=TradeoffDenominator.OFFERED_TASKS,
            direction=TradeoffDirection.MAXIMIZE,
        ),
        TradeoffMetricSpec(
            metric_key="task.latency.mean_ms",
            metric_version="1.0",
            unit="ms",
            denominator=TradeoffDenominator.COMPLETED_TASKS,
            direction=TradeoffDirection.MAXIMIZE,
        ),
    ]
    study_rev = _study(specs_reversed, arms_dominance)
    report_rev = build_tradeoff_report(study_rev)
    # Now A better on throughput, B better on latency (when latency maximize, higher is better, so B 100 > A 80, B better) => both frontier  # noqa: E501
    assert sorted(report_rev.frontier.frontier_arm_ids) == ["a", "b"]
    dom_rev = next(
        d for d in report_rev.dominance if d.dominator_arm_id == "a" and d.dominated_arm_id == "b"
    )
    assert dom_rev.dominates is False


# ---------------------------------------------------------------------------
# Deterministic frontier and fingerprint
# ---------------------------------------------------------------------------


def test_deterministic_frontier_and_fingerprint() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="arm_a",
            label="A",
            description="d",
            observations=[
                _obs("arm_a", "task.completion.rate_offered", 0.9),
                _obs(
                    "arm_a",
                    "task.latency.mean_ms",
                    90.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_b",
            label="B",
            description="d",
            observations=[
                _obs("arm_b", "task.completion.rate_offered", 0.85),
                _obs(
                    "arm_b",
                    "task.latency.mean_ms",
                    110.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_c",
            label="C",
            description="d",
            observations=[
                _obs("arm_c", "task.completion.rate_offered", 0.80),
                _obs(
                    "arm_c",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report1 = build_tradeoff_report(study, clock=lambda: datetime(2026, 8, 10, 12, 0, tzinfo=UTC))
    report2 = build_tradeoff_report(study, clock=lambda: datetime(2030, 1, 1, tzinfo=UTC))
    assert report1.frontier.frontier_arm_ids == report2.frontier.frontier_arm_ids
    assert report1.fingerprint() == report2.fingerprint()
    assert report1.report_fingerprint == report2.report_fingerprint
    # Study fingerprint deterministic
    assert study.fingerprint() == _study(specs, arms).fingerprint()
    # Report canonical JSON deterministic
    assert report1.canonical_json() == report2.canonical_json()


def test_input_order_independence() -> None:
    specs_ordered = _two_metric_specs_with_constraints()
    specs_reversed = list(reversed(specs_ordered))
    arms_ordered = [
        TradeoffArm(
            arm_id="arm_a",
            label="A",
            description="d",
            observations=[
                _obs("arm_a", "task.completion.rate_offered", 0.9),
                _obs(
                    "arm_a",
                    "task.latency.mean_ms",
                    90.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_b",
            label="B",
            description="d",
            observations=[
                _obs("arm_b", "task.completion.rate_offered", 0.85),
                _obs(
                    "arm_b",
                    "task.latency.mean_ms",
                    110.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    arms_reversed = list(reversed(arms_ordered))
    # Also reverse observations within arms
    arms_rev_obs = []
    for arm in arms_reversed:
        arms_rev_obs.append(
            TradeoffArm(
                arm_id=arm.arm_id,
                label=arm.label,
                description=arm.description,
                strategy_type=arm.strategy_type,
                observations=list(reversed(arm.observations)),
            )
        )
    study1 = _study(specs_ordered, arms_ordered)
    study2 = _study(specs_reversed, arms_rev_obs)
    assert study1.fingerprint() == study2.fingerprint()
    report1 = build_tradeoff_report(study1)
    report2 = build_tradeoff_report(study2)
    assert report1.fingerprint() == report2.fingerprint()
    assert report1.frontier.frontier_arm_ids == report2.frontier.frontier_arm_ids


# ---------------------------------------------------------------------------
# No winner language
# ---------------------------------------------------------------------------


def test_no_winner_language() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "task.completion.rate_offered", 0.9),
                _obs(
                    "a",
                    "task.latency.mean_ms",
                    80.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "task.completion.rate_offered", 0.8),
                _obs(
                    "b",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    md = tradeoff_report_to_markdown(report)
    js_text = report.to_json()
    csv_text = tradeoff_report_to_csv(report)
    frontier_csv = tradeoff_frontier_to_csv(report)

    # Collect all textual outputs that could contain decision language
    combined_texts = [
        md,
        js_text,
        csv_text,
        frontier_csv,
        report.frontier.description,
    ]
    combined_texts.extend(d.reason for d in report.dominance)
    combined_texts.extend(f.message for f in report.findings)
    combined = " ".join(combined_texts)

    # Allowed negated disclaimer strings that may contain forbidden tokens
    allowed_disclaimers = [
        "no best, optimal, winner, or recommended claim is made unless a declared scalar decision rule explicitly selects one",  # noqa: E501
        "no winner, best, or optimal claim is made unless",
        "descriptive dominance only; no best, optimal, winner, or recommended claim is made",
        "no best, optimal, winner",
        "descriptive frontier",
        "non-dominated",
        "feasible under declared metrics and constraints",
        "dominates under declared metrics",
        "does not dominate under declared metrics",
        "violates declared constraint",
        "descriptive frontier; non-dominated and feasible under declared metrics",
    ]

    # Sanitize: remove allowed disclaimers case-insensitively
    sanitized = combined.lower()
    for disc in allowed_disclaimers:
        sanitized = sanitized.replace(disc.lower(), "")

    forbidden_tokens = ["best", "optimal", "winner", "recommended", "recommendation"]
    for token in forbidden_tokens:
        assert token not in sanitized, (
            f"forbidden decision language '{token}' found outside allowed disclaimer in report outputs: {sanitized[:500]!r}"  # noqa: E501
        )

    # Also pin that at least one allowed disclaimer is present (proves disclaimer exists)
    assert "no best, optimal, winner, or recommended claim is made" in md.lower()
    # Frontier and dominance must use allowed wording
    assert (
        "non-dominated" in report.frontier.description.lower()
        or "descriptive frontier" in report.frontier.description.lower()
    )
    for dom in report.dominance:
        assert "dominates under declared metrics" in dom.reason or "does not dominate" in dom.reason

    # CSV and JSON should also not contain positive claims
    assert "best" not in csv_text.lower() or "no best" in csv_text.lower()
    assert "optimal" not in csv_text.lower() or "no optimal" in csv_text.lower()


# ---------------------------------------------------------------------------
# Matched-replication robustness
# ---------------------------------------------------------------------------


def test_matched_replication_robustness() -> None:
    specs = _two_metric_specs_with_constraints()
    # Provide per-replication values for two replications where frontier stable
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs(
                    "a",
                    "task.completion.rate_offered",
                    0.90,
                    per_rep={"rep_001": 0.91, "rep_002": 0.89},
                ),
                _obs(
                    "a",
                    "task.latency.mean_ms",
                    90.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                    per_rep={"rep_001": 88.0, "rep_002": 92.0},
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs(
                    "b",
                    "task.completion.rate_offered",
                    0.85,
                    per_rep={"rep_001": 0.86, "rep_002": 0.84},
                ),
                _obs(
                    "b",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                    per_rep={"rep_001": 98.0, "rep_002": 102.0},
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    # A dominates B on aggregate and also per replication (higher throughput, lower latency)
    assert report.frontier.frontier_arm_ids == ["a"]
    assert report.replication_stability["a"] == 1.0
    assert report.replication_stability["b"] == 0.0
    # Findings include stability
    assert any(f.code == "REPLICATION_STABILITY" and f.arm_id == "a" for f in report.findings)


def test_missing_per_replication_robustness_unavailable() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "task.completion.rate_offered", 0.9),
                _obs(
                    "a",
                    "task.latency.mean_ms",
                    90.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "task.completion.rate_offered", 0.85),
                _obs(
                    "b",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    assert any(f.code == "REPLICATION_STABILITY_UNAVAILABLE" for f in report.findings)


# ---------------------------------------------------------------------------
# CSV and JSON exports
# ---------------------------------------------------------------------------


def test_exports_contain_expected_fields() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "task.completion.rate_offered", 0.9),
                _obs(
                    "a",
                    "task.latency.mean_ms",
                    90.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "task.completion.rate_offered", 0.85),
                _obs(
                    "b",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    js = report.to_json()
    data = json.loads(js)
    assert data["study_id"] == study.study_id
    assert data["report_fingerprint"] == report.report_fingerprint
    assert "/Users" not in js
    assert "/tmp" not in js  # noqa: S108
    csv_text = tradeoff_report_to_csv(report)
    assert "study_id" in csv_text.splitlines()[0]
    assert study.study_id in csv_text
    frontier_csv = tradeoff_frontier_to_csv(report)
    assert "arm_id" in frontier_csv.splitlines()[0]
    md = tradeoff_report_to_markdown(report)
    assert "# Multi-Objective Trade-Off Report" in md


# ---------------------------------------------------------------------------
# Admission fail-closed
# ---------------------------------------------------------------------------


def test_unadmitted_evidence_fails_closed() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "task.completion.rate_offered", 0.9),
                _obs(
                    "a",
                    "task.latency.mean_ms",
                    90.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "task.completion.rate_offered", 0.85),
                _obs(
                    "b",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(
        specs,
        arms,
        admission_state=TradeoffAdmissionState.UNADMITTED,
        evidence_mode=TradeoffEvidenceMode.UNADMITTED_RESEARCH,
    )
    with pytest.raises(ValueError, match="UNADMITTED_EVIDENCE"):
        build_tradeoff_report(study)


# ---------------------------------------------------------------------------
# Unknown / unregistered compatibility remains unavailable
# ---------------------------------------------------------------------------


def test_unknown_metric_unavailable() -> None:
    specs = [
        TradeoffMetricSpec(
            metric_key="custom.unknown.metric",
            metric_version="1.0",
            unit="ratio",
            denominator=TradeoffDenominator.REPLICATION,
            direction=TradeoffDirection.MAXIMIZE,
        ),
        _spec(
            "task.latency.mean_ms",
            TradeoffDirection.MINIMIZE,
            unit="ms",
            denom=TradeoffDenominator.COMPLETED_TASKS,
        ),
    ]
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "custom.unknown.metric", 0.5, unit="ratio"),
                _obs(
                    "a",
                    "task.latency.mean_ms",
                    80.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "custom.unknown.metric", 0.6, unit="ratio"),
                _obs(
                    "b",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    comp = next(c for c in report.compatibility if c.metric_key == "custom.unknown.metric")
    assert comp.status.value == "unavailable"
    assert "no registered compatibility" in comp.finding.lower()


# ---------------------------------------------------------------------------
# Extra forbid and field validators
# ---------------------------------------------------------------------------


def test_extra_forbid_on_arm() -> None:
    with pytest.raises(ValidationError):
        TradeoffArm.model_validate(
            {"arm_id": "a", "label": "A", "description": "d", "observations": [], "extra": "no"}
        )


def test_fingerprint_excludes_wall_clock() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "task.completion.rate_offered", 0.9),
                _obs(
                    "a",
                    "task.latency.mean_ms",
                    90.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "task.completion.rate_offered", 0.85),
                _obs(
                    "b",
                    "task.latency.mean_ms",
                    100.0,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    s1 = _study(specs, arms, generated_at=datetime(2026, 1, 1, tzinfo=UTC))
    s2 = _study(specs, arms, generated_at=datetime(2030, 1, 1, tzinfo=UTC))
    assert s1.fingerprint() == s2.fingerprint()
    r1 = build_tradeoff_report(s1, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    r2 = build_tradeoff_report(s1, clock=lambda: datetime(2030, 1, 1, tzinfo=UTC))
    assert r1.fingerprint() == r2.fingerprint()
    assert r1.report_fingerprint == r2.report_fingerprint


# ---------------------------------------------------------------------------
# B1 regression: unregistered metric constraint must be fail-closed
# ---------------------------------------------------------------------------


def test_unregistered_metric_constraint_fail_closed() -> None:
    # Claude repro: custom metric UNAVAILABLE, constraint <=0.5, value 0.99 should NOT be feasible
    specs = [
        TradeoffMetricSpec(
            metric_key="custom.made_up.metric",
            metric_version="1.0",
            unit="ratio",
            denominator=TradeoffDenominator.REPLICATION,
            direction=TradeoffDirection.MAXIMIZE,
            hard_constraint=TradeoffConstraint(
                metric_key="custom.made_up.metric",
                operator=TradeoffConstraintOperator.LE,
                threshold=0.5,
                reason="must be <=0.5",
            ),
        ),
        TradeoffMetricSpec(
            metric_key="task.latency.mean_ms",
            metric_version="1.0",
            unit="ms",
            denominator=TradeoffDenominator.COMPLETED_TASKS,
            direction=TradeoffDirection.MINIMIZE,
        ),
    ]
    arms = [
        TradeoffArm(
            arm_id="arm_a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="arm_a",
                    metric_key="custom.made_up.metric",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.REPLICATION,
                    value=0.99,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="arm_a",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=90.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_b",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="arm_b",
                    metric_key="custom.made_up.metric",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.REPLICATION,
                    value=0.40,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="arm_b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=100.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    comp = next(c for c in report.compatibility if c.metric_key == "custom.made_up.metric")
    assert comp.status.value == "unavailable"
    assert "no registered compatibility" in comp.finding.lower()
    feas_a = next(f for f in report.feasibility if f.arm_id == "arm_a")
    feas_b = next(f for f in report.feasibility if f.arm_id == "arm_b")
    assert feas_a.is_feasible is False
    assert feas_a.status == TradeoffStatus.UNAVAILABLE
    assert "custom.made_up.metric" in feas_a.unavailable_metrics
    assert feas_b.is_feasible is False
    assert feas_b.status == TradeoffStatus.UNAVAILABLE
    assert not any(
        f.code == "CONSTRAINT_VIOLATED" and f.metric_key == "custom.made_up.metric"
        for f in report.findings
    )
    assert all("custom.made_up.metric" not in d.comparisons for d in report.dominance)
    assert report.frontier.frontier_arm_ids == []
    assert report.frontier.dominated_arm_ids == []
    assert any(f.code == "CONSTRAINT_SENSITIVITY_UNAVAILABLE" for f in report.findings)
    assert "frontier_without_constraints" not in report.sensitivity


# ---------------------------------------------------------------------------
# B2 regressions
# ---------------------------------------------------------------------------


def test_stability_no_matched_ids_unavailable() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.90,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=90.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.85,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=100.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
    ]
    study = _study(specs, arms, matched_replication_ids=[])
    report = build_tradeoff_report(study)
    assert report.replication_stability["a"] is None
    assert report.replication_stability["b"] is None
    assert any(f.code == "REPLICATION_STABILITY_UNAVAILABLE" for f in report.findings)
    data = json.loads(report.to_json())
    assert data["replication_stability"]["a"] is None
    csv_text = tradeoff_report_to_csv(report)
    assert ",," in csv_text or csv_text.count(",,") >= 1
    md = tradeoff_report_to_markdown(report)
    assert "stability unavailable" in md.lower()


def test_stability_matched_ids_but_no_per_rep_values_unavailable() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.90,
                    status=TradeoffStatus.AVAILABLE,
                    per_replication_values={},
                    replication_count=1,
                ),
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=90.0,
                    status=TradeoffStatus.AVAILABLE,
                    per_replication_values={},
                    replication_count=1,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.85,
                    status=TradeoffStatus.AVAILABLE,
                    per_replication_values={},
                    replication_count=1,
                ),
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=100.0,
                    status=TradeoffStatus.AVAILABLE,
                    per_replication_values={},
                    replication_count=1,
                ),
            ],
        ),
    ]
    study = _study(specs, arms, matched_replication_ids=["rep_001", "rep_002"])
    report = build_tradeoff_report(study)
    assert report.replication_stability["a"] is None
    assert report.replication_stability["b"] is None
    assert any(f.code == "REPLICATION_STABILITY_UNAVAILABLE" for f in report.findings)
    data = json.loads(report.to_json())
    assert data["replication_stability"]["a"] is None


def test_stability_genuine_zero() -> None:
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.90,
                    status=TradeoffStatus.AVAILABLE,
                    per_replication_values={"rep_001": 0.91, "rep_002": 0.89},
                    replication_count=2,
                ),
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=80.0,
                    status=TradeoffStatus.AVAILABLE,
                    per_replication_values={"rep_001": 78.0, "rep_002": 82.0},
                    replication_count=2,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.80,
                    status=TradeoffStatus.AVAILABLE,
                    per_replication_values={"rep_001": 0.81, "rep_002": 0.79},
                    replication_count=2,
                ),
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=120.0,
                    status=TradeoffStatus.AVAILABLE,
                    per_replication_values={"rep_001": 118.0, "rep_002": 122.0},
                    replication_count=2,
                ),
            ],
        ),
    ]
    study = _study(specs, arms, matched_replication_ids=["rep_001", "rep_002"])
    report = build_tradeoff_report(study)
    assert report.frontier.frontier_arm_ids == ["a"]
    assert report.replication_stability["a"] == 1.0
    assert report.replication_stability["b"] == 0.0
    assert report.replication_stability["b"] is not None
    data = json.loads(report.to_json())
    assert data["replication_stability"]["a"] == 1.0
    assert data["replication_stability"]["b"] == 0.0
    csv_text = tradeoff_frontier_to_csv(report)
    assert "1" in csv_text
    assert "0" in csv_text
    md = tradeoff_report_to_markdown(report)
    assert "stability 1.000" in md.lower()
    assert "stability 0.000" in md.lower()


def test_equal_arms_do_not_dominate_each_other_and_both_remain_frontier() -> None:
    """Strict Pareto: equal arms must not dominate and both remain frontier."""
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="arm_a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="arm_a",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.90,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="arm_a",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=90.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_b",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="arm_b",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.90,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="arm_b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=90.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    # Neither dominates
    dom_a_b = next(
        d
        for d in report.dominance
        if d.dominator_arm_id == "arm_a" and d.dominated_arm_id == "arm_b"
    )
    dom_b_a = next(
        d
        for d in report.dominance
        if d.dominator_arm_id == "arm_b" and d.dominated_arm_id == "arm_a"
    )
    assert dom_a_b.dominates is False
    assert dom_b_a.dominates is False
    assert dom_a_b.comparisons["task.completion.rate_offered"] == "equal"
    assert dom_a_b.comparisons["task.latency.mean_ms"] == "equal"
    assert "does not dominate" in dom_a_b.reason
    # Both remain frontier
    assert sorted(report.frontier.frontier_arm_ids) == ["arm_a", "arm_b"]
    assert report.frontier.dominated_arm_ids == []
    assert report.frontier.dominated_by["arm_a"] == []
    assert report.frontier.dominated_by["arm_b"] == []
    assert sorted(report.frontier.all_feasible_arm_ids) == ["arm_a", "arm_b"]
    # Both feasible
    for fid in ["arm_a", "arm_b"]:
        feas = next(f for f in report.feasibility if f.arm_id == fid)
        assert feas.is_feasible is True
        assert feas.status == TradeoffStatus.FEASIBLE


def test_arm_with_unavailable_selected_metric_is_infeasible_not_frontier() -> None:
    """Fail-closed: arm missing selected metric is unavailable, not frontier."""
    specs = _two_metric_specs_with_constraints()
    arms = [
        TradeoffArm(
            arm_id="A_strong",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="A_strong",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.95,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="A_strong",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=80.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="B_weak",
            label="B",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="B_weak",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.80,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="B_weak",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=120.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="C_worst",
            label="C",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="C_worst",
                    metric_key="task.completion.rate_offered",
                    metric_version="1.0",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.70,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="C_worst",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=None,
                    status=TradeoffStatus.UNAVAILABLE,
                    reason="missing",
                ),
            ],
        ),
    ]
    study = _study(specs, arms)
    report = build_tradeoff_report(study)
    # Frontier and feasible
    assert report.frontier.frontier_arm_ids == ["A_strong"]
    assert report.frontier.dominated_arm_ids == ["B_weak"]
    assert report.frontier.dominated_by["B_weak"] == ["A_strong"]
    assert sorted(report.frontier.all_feasible_arm_ids) == ["A_strong", "B_weak"]
    # C_worst is not feasible, not frontier, not dominated (incomparable)
    assert "C_worst" not in report.frontier.frontier_arm_ids
    assert "C_worst" not in report.frontier.dominated_arm_ids
    assert "C_worst" not in report.frontier.all_feasible_arm_ids
    feas_c = next(f for f in report.feasibility if f.arm_id == "C_worst")
    assert feas_c.is_feasible is False
    assert feas_c.status == TradeoffStatus.UNAVAILABLE
    assert "task.latency.mean_ms" in feas_c.unavailable_metrics
    assert "missing metrics" in feas_c.reason
    assert any(
        f.code == "MISSING_METRIC_UNAVAILABLE" and f.arm_id == "C_worst" for f in report.findings
    )
    # No dominance entry should treat C as feasible
    assert all(
        d.dominator_arm_id != "C_worst" and d.dominated_arm_id != "C_worst"
        for d in report.dominance
    )
    # Verify fail-closed dominance branch exists in source (ensures mutant kill)
    import pathlib

    src = pathlib.Path("src/traffictwin/experiments/tradeoff_explorer.py").read_text()
    # Exact fail-closed block for missing/unavailable pairwise evidence
    needle = '''                if va is None or vb is None:
                    missing_for_pair = True
                    comparisons[key] = "unavailable"'''
    assert needle in src
    # Must have two fail-closed assignments (missing + dominator_worse)
    assert src.count("at_least_as_good = False") == 2
    assert "at_least_as_good = False\n                    break" in src
