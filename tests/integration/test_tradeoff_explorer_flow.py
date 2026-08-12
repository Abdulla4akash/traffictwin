"""Integration test for tradeoff explorer flow."""

from __future__ import annotations

import json
from pathlib import Path

from traffictwin.experiments.resource_strategy import load_resource_strategy_study_file
from traffictwin.experiments.tradeoff_explorer import (
    TradeoffConstraint,
    TradeoffConstraintOperator,
    TradeoffDirection,
    build_tradeoff_report,
    tradeoff_report_to_markdown,
    tradeoff_study_from_resource_strategy_study,
)


def test_end_to_end_resource_strategy_to_tradeoff() -> None:
    rs_study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    assert rs_study.study_id

    # Select 2 metrics for tradeoff
    t_study = tradeoff_study_from_resource_strategy_study(
        rs_study, metric_keys=["task.completion.rate_offered", "task.latency.mean_ms"]
    )
    assert len(t_study.metric_specs) == 2
    # Check directions inferred correctly
    dir_map = {s.metric_key: s.direction for s in t_study.metric_specs}
    assert dir_map["task.completion.rate_offered"] == TradeoffDirection.MAXIMIZE
    assert dir_map["task.latency.mean_ms"] == TradeoffDirection.MINIMIZE

    report = build_tradeoff_report(t_study)
    assert report.study_id == rs_study.study_id
    assert len(report.feasibility) == len(rs_study.arms)
    assert len(report.frontier.frontier_arm_ids) >= 1
    # All feasibility and frontier are descriptive
    assert "descriptive" in report.frontier.description.lower()
    md = tradeoff_report_to_markdown(report)
    assert "# Multi-Objective Trade-Off Report" in md
    # JSON roundtrip
    j = report.to_json()
    data = json.loads(j)
    assert data["study_id"] == rs_study.study_id
    assert data["report_fingerprint"] == report.report_fingerprint
    # No winner language positively claimed
    assert "recommended policy" not in md.lower()


def test_integration_constraint_sensitivity() -> None:
    rs_study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    constraint = TradeoffConstraint(
        metric_key="task.completion.rate_offered",
        operator=TradeoffConstraintOperator.GE,
        threshold=0.95,
    )
    t_study = tradeoff_study_from_resource_strategy_study(
        rs_study,
        metric_keys=["task.completion.rate_offered", "task.latency.mean_ms"],
        constraints={"task.completion.rate_offered": constraint},
    )
    report = build_tradeoff_report(t_study)
    # At least one arm may violate if threshold high
    _infeas = [f for f in report.feasibility if not f.is_feasible]  # noqa: F841  # noqa: F841
    # frontier without constraints should differ maybe
    assert "frontier_with_constraints" in report.sensitivity
    assert "frontier_without_constraints" in report.sensitivity


def test_integration_incompatible_handling() -> None:
    _rs_study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    assert _rs_study is not None
    # Create a spec with incompatible version by manually building TradeoffStudy with wrong version
    import hashlib

    from traffictwin.experiments.tradeoff_explorer import (
        TradeoffArm,
        TradeoffDenominator,
        TradeoffDirection,
        TradeoffMetricSpec,
        TradeoffObservation,
        TradeoffStatus,
        TradeoffStudy,
    )

    specs = [
        TradeoffMetricSpec(
            metric_key="task.completion.rate_offered",
            metric_version="9.9",
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
    arms = [
        TradeoffArm(
            arm_id="a",
            label="A",
            description="d",
            observations=[
                TradeoffObservation(
                    arm_id="a",
                    metric_key="task.completion.rate_offered",
                    metric_version="9.9",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.9,
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
                    metric_version="9.9",
                    unit="ratio",
                    denominator=TradeoffDenominator.OFFERED_TASKS,
                    value=0.8,
                    status=TradeoffStatus.AVAILABLE,
                ),
                TradeoffObservation(
                    arm_id="b",
                    metric_key="task.latency.mean_ms",
                    metric_version="1.0",
                    unit="ms",
                    denominator=TradeoffDenominator.COMPLETED_TASKS,
                    value=120.0,
                    status=TradeoffStatus.AVAILABLE,
                ),
            ],
        ),
    ]
    study = TradeoffStudy(
        study_id="compat_test",
        source_fingerprint=hashlib.sha256(b"compat").hexdigest(),
        arms=arms,
        metric_specs=specs,
        matched_replication_ids=["rep_001"],
    )
    report = build_tradeoff_report(study)
    assert any(c.status.value == "incompatible" for c in report.compatibility)
    assert all(f.status.value == "incompatible" for f in report.feasibility)
