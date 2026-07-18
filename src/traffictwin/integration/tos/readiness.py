"""Machine-readable readiness gates for deeper TOS integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.integration.tos.audit import audit_tos_package

Clock = Callable[[], datetime]


class ReadinessStatus(StrEnum):
    """State of one evidence or permission gate."""

    READY = "ready"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class IntegrationGate(BaseModel):
    """One explicit gate between read-only analysis and deeper integration."""

    model_config = ConfigDict(extra="forbid")

    gate_id: str
    title: str
    status: ReadinessStatus
    evidence: list[str] = Field(default_factory=list)
    required_for: list[str] = Field(default_factory=list)
    next_action: str


class TosIntegrationReadinessReport(BaseModel):
    """Current evidence-backed capability decision for the supplied TOS package."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    report_id: str
    generated_at: datetime
    package_fingerprint: str
    package_commit: str | None
    semantics_source_commit: str
    overall_status: ReadinessStatus
    gates: list[IntegrationGate]
    capabilities: dict[str, ReadinessStatus]
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return finite, deterministic JSON."""

        return self.model_dump_json(indent=2)


def build_tos_integration_readiness(
    root: str | Path,
    *,
    fixture_permission: bool | None = None,
    publication_permission: bool | None = None,
    clock: Clock | None = None,
) -> TosIntegrationReadinessReport:
    """Build readiness from inspected artifacts and explicit permission attestations."""

    now = (clock or _utc_now)()
    audit = audit_tos_package(root, clock=lambda: now)
    gates = [
        IntegrationGate(
            gate_id="G01_SOURCE_SUMMARY_CONTRACT",
            title="Source summary contract",
            status=ReadinessStatus.READY,
            evidence=["evals/eval_results_master.csv", audit.semantics_source_commit],
            required_for=["summary_import", "paired_comparison", "results_workbench"],
            next_action="Keep the source-specific deadline-success semantics distinct.",
        ),
        IntegrationGate(
            gate_id="G02_EXACT_PRODUCER_PROVENANCE",
            title="Exact producer commit and command",
            status=ReadinessStatus.UNKNOWN,
            evidence=[f"package commit: {audit.package_commit or 'unavailable'}"],
            required_for=["canonical_conversion", "reproducible_rerun", "direct_launch"],
            next_action="Obtain the exact commit and invocation that produced the supplied arrays.",
        ),
        IntegrationGate(
            gate_id="G03_CHECKPOINT_PAYLOAD",
            title="Approved actor checkpoint",
            status=(
                ReadinessStatus.READY
                if audit.actor_checkpoint_file_count > 0
                else ReadinessStatus.BLOCKED
            ),
            evidence=[f"checkpoint files present: {audit.actor_checkpoint_file_count}"],
            required_for=["evaluator_smoke", "direct_launch"],
            next_action="Obtain one approved checkpoint matched to its producing commit.",
        ),
        IntegrationGate(
            gate_id="G04_INSTRUMENTED_WRITER",
            title="Instrumented output writer",
            status=ReadinessStatus.BLOCKED,
            evidence=["instrumented writer is absent from the inspected vec_env source"],
            required_for=["instrumented_rerun", "canonical_conversion", "direct_launch"],
            next_action="Obtain the writer or an approved output contract from Randy.",
        ),
        IntegrationGate(
            gate_id="G05_CANONICAL_OUTCOME_IDENTITY",
            title="Physical completion and persistent identity",
            status=ReadinessStatus.BLOCKED,
            evidence=[
                "task_met records deadline success rather than eventual completion",
                "processed FCD vehicle slots are time-local and recycled",
            ],
            required_for=["canonical_task_records", "canonical_vehicle_records"],
            next_action=(
                "Obtain eventual completion and stable vehicle identity, or keep these canonical "
                "tables unavailable."
            ),
        ),
        IntegrationGate(
            gate_id="G06_DECISION_CONTEXT",
            title="Vehicle tier, target, action availability, and link context",
            status=ReadinessStatus.BLOCKED,
            evidence=["the supplied outputs do not expose the required decision-time context"],
            required_for=["real_r1_evaluation", "target_provenance"],
            next_action="Request the missing decision-time fields without inferring them.",
        ),
        IntegrationGate(
            gate_id="G07_TEMPORAL_FAILURE_ALIGNMENT",
            title="Task-failure and infrastructure temporal alignment",
            status=ReadinessStatus.BLOCKED,
            evidence=[
                "RSU source state is available for showcase runs",
                "physical task completion windows are unavailable",
            ],
            required_for=["real_r2_evaluation"],
            next_action="Obtain event-level completion evidence aligned to RSU state.",
        ),
        IntegrationGate(
            gate_id="G08_RAW_TRIP_OUTPUT",
            title="Raw SUMO trip output",
            status=ReadinessStatus.BLOCKED,
            evidence=["processed FCD traces are present; tripinfo or equivalent is absent"],
            required_for=["journey_time_integration", "raw_sumo_reproduction"],
            next_action="Obtain tripinfo or another explicitly documented trip-duration output.",
        ),
        _permission_gate(
            "G09_FIXTURE_PERMISSION",
            "Sanitised fixture permission",
            fixture_permission,
            ["committed_real_schema_fixture", "public_ci_adapter_test"],
            "Obtain written permission for one small matched sanitised fixture.",
        ),
        _permission_gate(
            "G10_PUBLICATION_PERMISSION",
            "Aggregate-results publication permission",
            publication_permission,
            ["public_tos_atlas", "public_tos_results"],
            "Obtain written permission before publishing Randy-derived aggregate outputs.",
        ),
        IntegrationGate(
            gate_id="G11_LOCAL_EVALUATOR_SMOKE",
            title="Path-independent evaluator smoke run",
            status=ReadinessStatus.BLOCKED,
            evidence=["the evaluator contract is documented but has not run locally"],
            required_for=["direct_launch"],
            next_action="Run one bounded evaluator case after G02-G04 are satisfied.",
        ),
    ]
    capabilities = {
        "summary_import": ReadinessStatus.READY,
        "results_workbench": ReadinessStatus.READY,
        "historical_replay": ReadinessStatus.READY,
        "private_supervisor_pack": ReadinessStatus.READY,
        "canonical_conversion": _all_ready(gates, "canonical_conversion"),
        "real_r1_evaluation": _all_ready(gates, "real_r1_evaluation"),
        "real_r2_evaluation": _all_ready(gates, "real_r2_evaluation"),
        "journey_time_integration": _all_ready(gates, "journey_time_integration"),
        "direct_launch": _all_ready(gates, "direct_launch"),
        "public_tos_atlas": _all_ready(gates, "public_tos_atlas"),
    }
    return TosIntegrationReadinessReport(
        report_id=f"tos-readiness-{audit.package_fingerprint[:12]}",
        generated_at=now,
        package_fingerprint=audit.package_fingerprint,
        package_commit=audit.package_commit,
        semantics_source_commit=audit.semantics_source_commit,
        overall_status=(
            ReadinessStatus.READY
            if all(status is ReadinessStatus.READY for status in capabilities.values())
            else ReadinessStatus.BLOCKED
        ),
        gates=gates,
        capabilities=capabilities,
        warnings=[
            "Ready applies only to explicitly named capabilities.",
            "Unknown permissions must not be treated as granted.",
            "This report does not establish scientific or external validity.",
        ],
    )


def _permission_gate(
    gate_id: str,
    title: str,
    permission: bool | None,
    required_for: list[str],
    next_action: str,
) -> IntegrationGate:
    status = (
        ReadinessStatus.UNKNOWN
        if permission is None
        else ReadinessStatus.READY
        if permission
        else ReadinessStatus.BLOCKED
    )
    evidence = [
        "permission not yet recorded"
        if permission is None
        else "permission explicitly confirmed"
        if permission
        else "permission explicitly denied"
    ]
    return IntegrationGate(
        gate_id=gate_id,
        title=title,
        status=status,
        evidence=evidence,
        required_for=required_for,
        next_action=next_action,
    )


def _all_ready(gates: list[IntegrationGate], capability: str) -> ReadinessStatus:
    relevant = [gate.status for gate in gates if capability in gate.required_for]
    if any(status is ReadinessStatus.BLOCKED for status in relevant):
        return ReadinessStatus.BLOCKED
    if any(status is ReadinessStatus.UNKNOWN for status in relevant):
        return ReadinessStatus.UNKNOWN
    return ReadinessStatus.READY


def _utc_now() -> datetime:
    return datetime.now(UTC)
