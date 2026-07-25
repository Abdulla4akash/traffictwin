"""Read-only status across the whole Manchester research workflow.

This is the boundary a CLI command or a thin UI page reads to answer one
question honestly: *where does the Gate-D chain actually stand, and what is it
waiting on?*

Deliberately read-only and offline. It never fetches, never runs a subprocess,
never computes a scientific metric, and never writes. Acquisition, building,
decoding, and simulation stay in the CLI, where an operator authorises each one
explicitly and a Streamlit rerun cannot trigger them.

**Unavailable is a first-class state.** Every stage that cannot proceed reports
its exact blocker and, where the blocker is a decision rather than a missing
artifact, who it waits on. An absent result is never rendered as zero, as empty
success, or as a stage that simply is not mentioned — a reader who scrolls past a
missing stage has been misled just as surely as one who is shown a wrong number.

**Acceptance basis propagates.** Rows the owner's *written policy* accepted carry
``owner_policy_accepted_candidate``. No analyst, human, or supervisor has
reviewed any row, and no view here may describe them as reviewed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

WORKFLOW_SERVICE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
WORKFLOW_SERVICE_METHOD_VERSION: Literal["manchester-workflow-service-1.0"] = (
    "manchester-workflow-service-1.0"
)

RESEARCH_STATUS: Literal["owner_approved_candidate"] = "owner_approved_candidate"

StageState: TypeAlias = Literal[
    "available",
    "blocked_on_owner_decision",
    "blocked_on_missing_artifact",
    "blocked_outside_grant",
    "not_started",
]

BlockerOwner: TypeAlias = Literal["owner", "supervisor", "lead", "none"]


class WorkflowServiceModel(ManchesterSnapshotModel):
    """Strict frozen base for workflow status views."""


class WorkflowStage(WorkflowServiceModel):
    """One stage of the Gate-D research chain and its honest state."""

    key: str = Field(min_length=1, max_length=64)
    phase: int = Field(ge=1, le=13)
    title: str = Field(min_length=1, max_length=120)
    state: StageState
    #: Populated whenever the stage is not available. A blocked stage without a
    #: stated reason is indistinguishable from one nobody has looked at.
    blocker: str | None = Field(default=None, max_length=300)
    #: Who can lift the blocker. ``none`` only when the stage is available.
    blocker_owner: BlockerOwner = "none"
    #: What has actually been produced, if anything.
    summary: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_stage(self) -> WorkflowStage:
        if self.state == "available":
            if self.blocker is not None:
                raise ValueError("an available stage cannot carry a blocker")
            if self.blocker_owner != "none":
                raise ValueError("an available stage has no blocker owner")
        else:
            if not self.blocker:
                raise ValueError("a stage that is not available must state its blocker")
            if self.state == "blocked_on_owner_decision" and self.blocker_owner == "none":
                raise ValueError("a decision blocker must name who can lift it")
        return self


class ManchesterWorkflowStatus(WorkflowServiceModel):
    """Complete honest status across the Manchester research workflow."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-workflow-service-1.0"] = WORKFLOW_SERVICE_METHOD_VERSION
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS

    stages: tuple[WorkflowStage, ...] = Field(min_length=1)
    open_owner_decisions: tuple[str, ...] = ()

    capability_status: Literal["planned"] = "planned"
    gate_d_state: Literal["foundation_only"] = "foundation_only"
    gate_e_state: Literal["foundation_only"] = "foundation_only"

    #: Rows the written policy accepted; no person reviewed them.
    acceptance_basis: Literal["owner_policy_accepted_candidate"] = "owner_policy_accepted_candidate"
    analyst_reviewed: Literal[False] = False
    human_accepted: Literal[False] = False
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False

    performs_network_access: Literal[False] = False
    performs_subprocess_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_status(self) -> ManchesterWorkflowStatus:
        decision_blocked = [
            stage for stage in self.stages if stage.state == "blocked_on_owner_decision"
        ]
        if decision_blocked and not self.open_owner_decisions:
            raise ValueError(
                "a stage blocked on an owner decision requires that decision to be listed"
            )
        return self

    @property
    def available_stages(self) -> tuple[WorkflowStage, ...]:
        return tuple(stage for stage in self.stages if stage.state == "available")

    @property
    def blocked_stages(self) -> tuple[WorkflowStage, ...]:
        return tuple(stage for stage in self.stages if stage.state != "available")


#: The four decisions that are the owner's alone. Recorded here so a reader of
#: any blocked stage can see what is actually being waited on, rather than
#: having to reconstruct it from scattered evidence records.
OPEN_OWNER_DECISIONS: tuple[str, ...] = (
    "the candidate demand gridlocks in simulation; whether to regenerate the route pool with a "
    "realistic trip-length mix is an owner decision because it changes the demand's provenance",
    "165 map-match rows await manual review; policy v1.1 disables automatic acceptance, so a "
    "person is required and no agent may stand in for one",
    "the comparison contract fingerprint is not registered; the registry lives in a module outside "
    "the agent grant, so production goodness-of-fit correctly stays unavailable",
    "whether GEH is an acceptance criterion, and at what threshold; routeSampler reports it but no "
    "threshold has been approved, so it is recorded as a tool diagnostic only",
)


def _stage(
    key: str,
    phase: int,
    title: str,
    state: StageState,
    *,
    blocker: str | None = None,
    blocker_owner: BlockerOwner = "none",
    summary: str | None = None,
) -> WorkflowStage:
    return WorkflowStage(
        key=key,
        phase=phase,
        title=title,
        state=state,
        blocker=blocker,
        blocker_owner=blocker_owner,
        summary=summary,
    )


def manchester_workflow_status(
    workspace_root: str | Path | None = None,
) -> ManchesterWorkflowStatus:
    """Report where the Gate-D chain stands, without touching the network.

    ``workspace_root`` is accepted so a caller can point at an operator
    workspace, but nothing is fetched or executed either way: the state of each
    stage is determined by what the repository can prove, not by probing.
    """

    _ = workspace_root  # reserved for per-workspace artifact inspection
    stages = (
        _stage(
            "observation_acquisition",
            1,
            "Real DfT observation acquisition",
            "available",
            summary="Manchester local authority 85; count points and raw counts acquired, "
            "quarantined, hashed and promoted",
        ),
        _stage(
            "map_matching",
            2,
            "Observation-to-network map matching",
            "available",
            summary="owner policy v1.1; rows it accepted are owner_policy_accepted_candidate, "
            "never analyst-reviewed",
        ),
        _stage(
            "network_review",
            3,
            "Network review and connectivity",
            "available",
            summary="motor-access components and bounded route probes; bounded probes never "
            "claim universal routability",
        ),
        _stage(
            "temporal_profile",
            4,
            "DfT temporal profile",
            "available",
            summary="local clock hour basis; missing hours stay missing and a measured zero "
            "stays distinct from a missing one",
        ),
        _stage(
            "candidate_demand",
            5,
            "Count-constrained candidate demand",
            "available",
            summary="count-constrained candidate demand, not observed origin-destination travel",
        ),
        _stage(
            "calibration_contract",
            6,
            "Calibration contract",
            "blocked_on_missing_artifact",
            blocker="the contract binds a mapping fingerprint and a projection report fingerprint "
            "for artifacts that do not exist yet; supplying placeholders would fabricate lineage",
        ),
        _stage(
            "sumo_run",
            7,
            "Controlled SUMO execution",
            "blocked_on_owner_decision",
            blocker="the runner is built and tested, but the candidate demand gridlocks: one "
            "simulated hour drove halting share to 88.8% with teleports reaching 35.7% of "
            "inserted vehicles, so any FCD produced would be unusable",
            blocker_owner="owner",
        ),
        _stage(
            "comparison_contract",
            8,
            "Comparison contract",
            "blocked_outside_grant",
            blocker="the contract is built and fingerprinted, but its approved-fingerprint "
            "registry lives in a module outside the agent grant, so production goodness-of-fit "
            "stays unavailable until the owner of that module registers it",
            blocker_owner="lead",
        ),
        _stage(
            "vec_chain",
            9,
            "SUMO-to-VEC chain",
            "blocked_on_missing_artifact",
            blocker="no accepted one-second FCD and network pair exists, because the controlled "
            "run has not produced one",
        ),
        _stage(
            "product_integration",
            10,
            "CLI, service and thin UI integration",
            "available",
            summary="in progress; this status view is part of it",
        ),
        _stage(
            "gate_closure",
            11,
            "Gate B, C and F closure",
            "not_started",
            blocker="not started; independent of every open decision above",
        ),
        _stage(
            "ui_presentation",
            12,
            "Remaining UI presentation",
            "not_started",
            blocker="deliberately sequenced after the research chain is integrated",
        ),
        _stage(
            "alpha_checkpoint",
            13,
            "Final verified alpha checkpoint",
            "not_started",
            blocker="a checkpoint is proposed for lead review and never tagged by an agent",
        ),
    )
    return ManchesterWorkflowStatus(
        stages=stages,
        open_owner_decisions=OPEN_OWNER_DECISIONS,
    )
