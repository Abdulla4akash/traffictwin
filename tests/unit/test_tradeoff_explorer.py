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
        _spec(
            "metric.throughput",
            TradeoffDirection.MAXIMIZE,
            unit="ratio",
            denom=TradeoffDenominator.REPLICATION,
            constraint=constraint_on_first,
        ),
        _spec(
            "metric.latency",
            TradeoffDirection.MINIMIZE,
            unit="ms",
            denom=TradeoffDenominator.COMPLETED_TASKS,
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
            observations=[_obs("a", "metric.throughput", 0.8), _obs("a", "metric.latency", 100.0)],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[_obs("b", "metric.throughput", 0.7), _obs("b", "metric.latency", 120.0)],
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
                        _obs("a", "metric.throughput", 0.8),
                        _obs("a", "metric.latency", 100.0),
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
                _obs("arm_a", "metric.throughput", 0.95, unit="ratio"),
                _obs(
                    "arm_a",
                    "metric.latency",
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
                _obs("arm_b", "metric.throughput", 0.80, unit="ratio"),
                _obs(
                    "arm_b",
                    "metric.latency",
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
                _obs("arm_a", "metric.throughput", 0.95, unit="ratio"),
                _obs(
                    "arm_a",
                    "metric.latency",
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
                _obs("arm_b", "metric.throughput", 0.80, unit="ratio"),
                _obs(
                    "arm_b",
                    "metric.latency",
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
            "metric.latency",
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
                    "metric.latency",
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
                    "metric.latency",
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
                _obs("arm_a", "metric.throughput", 0.90),
                _obs(
                    "arm_a",
                    "metric.latency",
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
                _obs("arm_b", "metric.throughput", 0.80),
                _obs(
                    "arm_b",
                    "metric.latency",
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
    assert "metric.latency" in feas_a.unavailable_metrics
    assert any(
        f.code == "MISSING_METRIC_UNAVAILABLE" and f.arm_id == "arm_a" for f in report.findings
    )
    # Only feasible arm is B, so frontier is B
    assert report.frontier.frontier_arm_ids == ["arm_b"]


# ---------------------------------------------------------------------------
# Metric direction correctness
# ---------------------------------------------------------------------------


def test_metric_direction_correctness() -> None:
    # Same values but test that direction matters
    specs_max = [
        _spec("m1", TradeoffDirection.MAXIMIZE),
        _spec(
            "m2", TradeoffDirection.MINIMIZE, unit="ms", denom=TradeoffDenominator.COMPLETED_TASKS
        ),
    ]
    # Arm A: higher m1 (better for maximize), higher m2 (worse for minimize)
    # Arm B: lower m1 (worse), lower m2 (better) => trade-off, both frontier
    arms_tradeoff = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "m1", 10.0),
                _obs("a", "m2", 100.0, unit="ms", denom=TradeoffDenominator.COMPLETED_TASKS),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "m1", 8.0),
                _obs("b", "m2", 80.0, unit="ms", denom=TradeoffDenominator.COMPLETED_TASKS),
            ],
        ),
    ]
    study_tradeoff = _study(specs_max, arms_tradeoff)
    report_tradeoff = build_tradeoff_report(study_tradeoff)
    assert sorted(report_tradeoff.frontier.frontier_arm_ids) == ["a", "b"]

    # Now test dominance when both metrics favor A
    specs_min_both = [
        _spec("m1", TradeoffDirection.MAXIMIZE),
        _spec(
            "m2", TradeoffDirection.MINIMIZE, unit="ms", denom=TradeoffDenominator.COMPLETED_TASKS
        ),
    ]
    arms_dominance = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                _obs("a", "m1", 10.0),
                _obs("a", "m2", 80.0, unit="ms", denom=TradeoffDenominator.COMPLETED_TASKS),
            ],
        ),
        TradeoffArm(
            arm_id="b",
            label="B",
            description="d",
            observations=[
                _obs("b", "m1", 8.0),
                _obs("b", "m2", 100.0, unit="ms", denom=TradeoffDenominator.COMPLETED_TASKS),
            ],
        ),
    ]
    study_dom = _study(specs_min_both, arms_dominance)
    report_dom = build_tradeoff_report(study_dom)
    # A dominates B because higher m1 and lower m2
    assert report_dom.frontier.frontier_arm_ids == ["a"]
    dom_a_b = next(
        d for d in report_dom.dominance if d.dominator_arm_id == "a" and d.dominated_arm_id == "b"
    )
    assert dom_a_b.dominates is True

    # If we reverse direction of m2 to MAXIMIZE, then A no longer dominates B (now A has lower m2 but maximize wants higher, so B better on m2)  # noqa: E501
    # Then they would trade off.
    specs_reversed = [
        _spec("m1", TradeoffDirection.MAXIMIZE),
        _spec(
            "m2", TradeoffDirection.MAXIMIZE, unit="ms", denom=TradeoffDenominator.COMPLETED_TASKS
        ),
    ]
    study_rev = _study(specs_reversed, arms_dominance)
    report_rev = build_tradeoff_report(study_rev)
    # Now A better on m1, B better on m2 => both frontier, no dominance
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
                _obs("arm_a", "metric.throughput", 0.9),
                _obs(
                    "arm_a",
                    "metric.latency",
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
                _obs("arm_b", "metric.throughput", 0.85),
                _obs(
                    "arm_b",
                    "metric.latency",
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
                _obs("arm_c", "metric.throughput", 0.80),
                _obs(
                    "arm_c",
                    "metric.latency",
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
                _obs("arm_a", "metric.throughput", 0.9),
                _obs(
                    "arm_a",
                    "metric.latency",
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
                _obs("arm_b", "metric.throughput", 0.85),
                _obs(
                    "arm_b",
                    "metric.latency",
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
                _obs("a", "metric.throughput", 0.9),
                _obs(
                    "a",
                    "metric.latency",
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
                _obs("b", "metric.throughput", 0.8),
                _obs(
                    "b",
                    "metric.latency",
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
    _js = report.to_json()  # noqa: F841
    # Allowed phrase is "no winner, best, or optimal claim" — disallowed is claiming best/optimal/winner/recommended positively  # noqa: E501
    # Check that report does not claim optimal/best in a positive sense beyond the disclaimer
    # We allow the disclaimer that contains "no winner" etc.
    # So verify that specific positive claims are absent
    assert "recommended policy" not in md.lower()
    # The dominance wording must be correct
    for dom in report.dominance:
        assert "dominates under declared metrics" in dom.reason or "does not dominate" in dom.reason
        assert "best" not in dom.reason.lower()
        assert "optimal" not in dom.reason.lower()
        assert "winner" not in dom.reason.lower()
    # Frontier description must use allowed language
    assert (
        "non-dominated" in report.frontier.description.lower()
        or "descriptive frontier" in report.frontier.description.lower()
    )
    assert "best" not in report.frontier.description.lower()
    assert "optimal" not in report.frontier.description.lower()
    assert "winner" not in report.frontier.description.lower()
    # Overall report findings must not contain winner language except where disclaimer
    # Count occurrences of disallowed words outside disclaimer context
    lower_md = md.lower()
    # Remove the disclaimer sentence before checking
    disclaimer_removed = lower_md.replace(
        "descriptive differences only; no winner, best, or optimal claim is made unless", ""
    )
    disclaimer_removed = disclaimer_removed.replace("no best, optimal, winner", "")
    # After removal, those words should not appear as standalone claims
    # We check that md does not contain " best " or " optimal " in a positive claim (heuristic)
    assert " best policy" not in lower_md
    assert " optimal policy" not in lower_md
    assert " winner" not in disclaimer_removed or "no winner" in disclaimer_removed


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
                _obs("a", "metric.throughput", 0.90, per_rep={"rep_001": 0.91, "rep_002": 0.89}),
                _obs(
                    "a",
                    "metric.latency",
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
                _obs("b", "metric.throughput", 0.85, per_rep={"rep_001": 0.86, "rep_002": 0.84}),
                _obs(
                    "b",
                    "metric.latency",
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
                _obs("a", "metric.throughput", 0.9),
                _obs(
                    "a",
                    "metric.latency",
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
                _obs("b", "metric.throughput", 0.85),
                _obs(
                    "b",
                    "metric.latency",
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
                _obs("a", "metric.throughput", 0.9),
                _obs(
                    "a",
                    "metric.latency",
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
                _obs("b", "metric.throughput", 0.85),
                _obs(
                    "b",
                    "metric.latency",
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
                _obs("a", "metric.throughput", 0.9),
                _obs(
                    "a",
                    "metric.latency",
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
                _obs("b", "metric.throughput", 0.85),
                _obs(
                    "b",
                    "metric.latency",
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
            "metric.latency",
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
                    "metric.latency",
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
                    "metric.latency",
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
                _obs("a", "metric.throughput", 0.9),
                _obs(
                    "a",
                    "metric.latency",
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
                _obs("b", "metric.throughput", 0.85),
                _obs(
                    "b",
                    "metric.latency",
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
