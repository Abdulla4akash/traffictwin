"""Cross-lane composition smokes for the V4 twelve-lane integration.

Each lane's own suite proves its feature in isolation; these checks prove the
claims that only exist once the lanes share one interpreter and one registry:
imports compose without cycles, registration covers every lane, and the
boundary guarantees (draft-only, unexecuted, fail-closed, no automatic
promotion) hold in the combined tree.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.event_scenario_bridge.models import (
    DeclaredEventReference,
    EventImpactEnvelope,
    EventScenarioBridgeRequest,
    MutationKind,
    ScenarioMutationProposal,
)
from traffictwin.event_scenario_bridge.service import build_event_scenario_bridge_manifest
from traffictwin.experiments.tradeoff_explorer import (
    TradeoffArm,
    TradeoffConstraint,
    TradeoffConstraintOperator,
    TradeoffDenominator,
    TradeoffDirection,
    TradeoffMetricSpec,
    TradeoffObservation,
    TradeoffStatus,
    TradeoffStudy,
    build_tradeoff_report,
)


def test_all_twelve_lane_modules_import_together_without_cycles() -> None:
    """One interpreter, every V4 feature plus the shared runtime and CLI."""

    import traffictwin.baseline_registry
    import traffictwin.calibration
    import traffictwin.cli
    import traffictwin.contract_drafting
    import traffictwin.event_scenario_bridge
    import traffictwin.evidence_admission
    import traffictwin.metric_contract_registry
    import traffictwin.reproducibility_replay
    import traffictwin.study_accrual
    import traffictwin.study_workspace
    import traffictwin.ui.page_runtime
    import traffictwin.workspace_activation

    assert traffictwin.cli.app.registered_groups, "CLI groups must be registered"
    group_names = {group.name for group in traffictwin.cli.app.registered_groups}
    assert {
        "baseline",
        "evidence-admission",
        "metric-contract",
        "replay",
        "workspace",
    }.issubset(group_names)


def test_study_workspace_coexists_with_every_registered_v4_page() -> None:
    from traffictwin.ui.labels import UiPage
    from traffictwin.ui.navigation_v07 import validate_v07_page_specs
    from traffictwin.ui.page_runtime import PAGE_RENDERERS

    validate_v07_page_specs()
    assert set(PAGE_RENDERERS) == set(UiPage)
    v4_pages = {
        UiPage.STUDY_WORKSPACE,
        UiPage.EVIDENCE_ADMISSION_INBOX,
        UiPage.METRIC_CONTRACT_REGISTRY,
        UiPage.CALIBRATION_WORKBENCH,
        UiPage.BASELINE_REGISTRY,
        UiPage.STUDY_ACCRUAL_MONITOR,
        UiPage.REPRODUCIBILITY_REPLAY,
        UiPage.CONTRACT_DRAFTING_ASSISTANT,
        UiPage.EVENT_SCENARIO_BRIDGE,
        UiPage.MULTIOBJECTIVE_TRADEOFF,
        UiPage.WORKSPACE_ACTIVATION,
    }
    assert v4_pages.issubset(set(UiPage))


def test_legacy_resource_strategy_unchanged_without_metric_declarations() -> None:
    """Lane 3's optional per-arm declarations must not burden legacy studies."""

    from traffictwin.experiments.resource_strategy import (
        ResourceStrategyArm,
        ResourceStrategyLifecycle,
        ResourceStrategyReplication,
    )

    arm = ResourceStrategyArm(
        arm_id="arm_legacy",
        label="Legacy arm",
        description="A pre-V4 arm with no metric declarations",
        strategy_type="baseline",
        replications=[
            ResourceStrategyReplication(
                replication_id="rep_001",
                lifecycle=ResourceStrategyLifecycle(
                    offered=1000,
                    admitted=800,
                    rejected=200,
                    forwarded=400,
                    started=760,
                    compute_completed=720,
                    returned=700,
                    dropped=80,
                    deadline_success=680,
                ),
            )
        ],
    )
    assert arm.metric_declarations == [], "declarations must default to absent"


def test_tradeoff_explorer_fails_closed_when_metric_unavailable() -> None:
    def _obs(
        arm_id: str,
        key: str,
        value: float | None,
        *,
        status: TradeoffStatus,
        unit: str,
        denom: TradeoffDenominator,
    ) -> TradeoffObservation:
        return TradeoffObservation(
            arm_id=arm_id,
            metric_key=key,
            metric_version="1.0",
            unit=unit,
            denominator=denom,
            value=value,
            status=status,
            per_replication_values={},
            replication_count=1 if value is not None else 0,
            reason=None if status == TradeoffStatus.AVAILABLE else "missing",
        )

    specs = [
        TradeoffMetricSpec(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=TradeoffDenominator.OFFERED_TASKS,
            direction=TradeoffDirection.MAXIMIZE,
            hard_constraint=TradeoffConstraint(
                metric_key="task.completion.rate_offered",
                operator=TradeoffConstraintOperator.GE,
                threshold=0.5,
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
            arm_id="arm_gap",
            label="Gap",
            description="one metric unavailable",
            observations=[
                _obs(
                    "arm_gap",
                    "task.completion.rate_offered",
                    0.9,
                    status=TradeoffStatus.AVAILABLE,
                    unit="ratio",
                    denom=TradeoffDenominator.OFFERED_TASKS,
                ),
                _obs(
                    "arm_gap",
                    "task.latency.mean_ms",
                    None,
                    status=TradeoffStatus.UNAVAILABLE,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
        TradeoffArm(
            arm_id="arm_full",
            label="Full",
            description="all metrics available",
            observations=[
                _obs(
                    "arm_full",
                    "task.completion.rate_offered",
                    0.8,
                    status=TradeoffStatus.AVAILABLE,
                    unit="ratio",
                    denom=TradeoffDenominator.OFFERED_TASKS,
                ),
                _obs(
                    "arm_full",
                    "task.latency.mean_ms",
                    75.0,
                    status=TradeoffStatus.AVAILABLE,
                    unit="ms",
                    denom=TradeoffDenominator.COMPLETED_TASKS,
                ),
            ],
        ),
    ]
    study = TradeoffStudy.model_validate(
        {
            "schema_version": "1.0",
            "study_id": "v4_cross_lane_smoke",
            "source_fingerprint": hashlib.sha256(b"v4").hexdigest(),
            "evidence_mode": "synthetic_demonstration",
            "admission_state": "synthetic_demonstration",
            "arms": arms,
            "metric_specs": specs,
            "matched_replication_ids": ["rep_001"],
            "limitations": ["synthetic demonstration"],
            "provenance": {"fixture": "v4-cross-lane"},
            "generated_at": None,
        }
    )
    report = build_tradeoff_report(study)
    gap = next(f for f in report.feasibility if f.arm_id == "arm_gap")
    assert gap.status == TradeoffStatus.UNAVAILABLE
    assert gap.is_feasible is False, "an arm with an unavailable metric must fail closed"
    assert report.frontier.frontier_arm_ids == ["arm_full"]


def test_contract_drafting_handoff_stays_draft_only(tmp_path: Path) -> None:
    import csv as _csv

    from traffictwin.contract_drafting.service import build_draft_report, prepare_handoff

    for index, name in enumerate(("s1.csv", "s2.csv")):
        path = tmp_path / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = _csv.writer(handle)
            writer.writerow(["speed_kmh", "vehicle_count"])
            writer.writerow([str(30.0 + index), str(10 + index)])
    report = build_draft_report([tmp_path / "s1.csv", tmp_path / "s2.csv"])
    handoff = prepare_handoff(report, source_id="src1", contract_version="1.0.0")
    assert handoff.draft_only is True
    assert handoff.freeze_executed is False
    assert handoff.human_review_required is True


def test_event_bridge_handoffs_remain_unexecuted() -> None:
    request = EventScenarioBridgeRequest.model_validate(
        {
            "bridge_id": "bridge-v4-smoke",
            "title": "Cross-lane smoke bridge",
            "description": "Unexecuted design linking event to scenario",
            "event_reference": DeclaredEventReference(
                event_id="event-smoke-001",
                event_kind="Authored road closure",
                anchor_time_utc=datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC),
                source_label="Authored — Manual timestamp",
                provenance_detail="Declared for what-if planning",
            ),
            "baseline_seed_fingerprint": "a" * 64,
            "baseline_seed_id": "seed-baseline",
            "impact_envelope": EventImpactEnvelope(
                affected_links=["link-a"],
                affected_area_label="Central corridor",
                pre_duration_s=600,
                event_duration_s=600,
                post_duration_s=600,
                bin_width_s=60,
            ),
            "mutation_proposals": [
                ScenarioMutationProposal(
                    mutation_kind=MutationKind.LANE_CLOSURE,
                    target_description="Close 1 lane on link-a",
                    lanes_closed=1,
                )
            ],
            "intended_metrics": ["task.completion.rate"],
            "intended_windows": ["pre", "event", "post"],
        }
    )
    manifest = build_event_scenario_bridge_manifest(request)
    assert manifest.verify_fingerprint()
    assert any(finding.finding_id == "bridge-unexecuted" for finding in manifest.findings), (
        "the bridge must declare itself unexecuted"
    )
    assert any("no simulation or vec was launched" in lim.lower() for lim in manifest.limitations)


def test_replay_contract_is_closed_allowlist_and_imports_integrated_tree() -> None:
    from traffictwin.reproducibility_replay.service import replay_contract

    contract = replay_contract()
    assert contract.allowlisted_kinds, "allowlist must be non-empty"
    assert len(contract.allowlisted_kinds) == len(set(contract.allowlisted_kinds))
    assert contract.allowlist_fingerprint


def test_baseline_registry_registration_never_promotes() -> None:
    from traffictwin.baseline_registry import (
        BaselineArtifactType,
        BaselineEvidenceStanding,
        BaselineScope,
        BaselineSourceStanding,
        build_candidate,
        create_empty_registry,
        register_candidate,
    )

    clock = lambda: datetime(2026, 8, 1, tzinfo=UTC)  # noqa: E731
    registry = create_empty_registry(clock=clock)
    candidate = build_candidate(
        candidate_id="cand-001",
        scope=BaselineScope(
            scope_id="scope-default",
            purpose="Reference baseline for cross-lane smoke purposes",
            cohort_definition="Synthetic smoke cohort",
        ),
        artifact_fingerprint=hashlib.sha256(b"artifact").hexdigest(),
        artifact_type=BaselineArtifactType.STUDY_CAPSULE
        if hasattr(BaselineArtifactType, "STUDY_CAPSULE")
        else next(iter(BaselineArtifactType)),
        schema_version="1.0",
        metric_contracts=["task.completion.rate@1.0"],
        cohort_definition="Synthetic smoke cohort",
        evidence_standing=BaselineEvidenceStanding.ADMITTED_RESEARCH,
        source_standing=next(iter(BaselineSourceStanding)),
        regression_gate_policy="none declared for smoke",
        limitations="cross-lane smoke only",
        clock=clock,
    )
    registry = register_candidate(registry, candidate, clock=clock)
    assert not registry.active_baselines, "registering a candidate must not promote it"


def test_study_accrual_report_is_deterministic_with_admission_style_review() -> None:
    """Accrual must be pure over its inputs — no cached-state shortcut."""

    from tests.integration.test_study_accrual_integration import _frozen_plan

    from traffictwin.study_accrual.service import build_accrual_report

    plan = _frozen_plan()
    first = build_accrual_report(plan)
    second = build_accrual_report(plan)
    assert first.compute_fingerprint() == second.compute_fingerprint()
