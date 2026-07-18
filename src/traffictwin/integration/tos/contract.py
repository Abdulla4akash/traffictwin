"""Versioned source contract derived from the inspected vec_env repository."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.config.capabilities import CapabilitySupport
from traffictwin.integration.tos.models import (
    TOS_ADAPTER_VERSION,
    TOS_SUMO_VERSION,
    TOS_VEC_ENV_EVIDENCE_COMMIT,
)


class TosContractStatus(StrEnum):
    """Evidence status for a source-contract statement."""

    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class TosFieldContract(BaseModel):
    """Meaning and unit of one field evidenced in source code or artifacts."""

    model_config = ConfigDict(extra="forbid")

    field: str
    artifact: str
    meaning: str
    unit: str | None
    status: TosContractStatus
    evidence: list[str]
    limitations: list[str] = Field(default_factory=list)


class TosControlContract(BaseModel):
    """Source-environment and TrafficTwin support for one scenario control."""

    model_config = ConfigDict(extra="forbid")

    control: str
    source_support: CapabilitySupport
    adapter_support: CapabilitySupport
    mechanism: str | None = None
    status: TosContractStatus
    limitations: list[str] = Field(default_factory=list)


class TosExecutionContract(BaseModel):
    """Observed evaluator interface and blockers to a TrafficTwin launcher."""

    model_config = ConfigDict(extra="forbid")

    status: TosContractStatus
    interface: str
    command_template: list[str]
    output_contract: str
    direct_launch: CapabilitySupport
    asynchronous_launch: CapabilitySupport
    blockers: list[str]


class TosSourceContract(BaseModel):
    """Machine-readable contract for the inspected TOS/vec_env artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    adapter_version: str = TOS_ADAPTER_VERSION
    evidence_repository: str = "vec_env"
    evidence_commit: str = TOS_VEC_ENV_EVIDENCE_COMMIT
    source_versions: dict[str, str]
    fields: list[TosFieldContract]
    controls: list[TosControlContract]
    execution: TosExecutionContract
    unavailable_outputs: list[str]
    interpretation_limits: list[str]

    def to_json(self) -> str:
        """Return a stable, formatted JSON representation."""

        return self.model_dump_json(indent=2)


def tos_source_contract() -> TosSourceContract:
    """Return the source contract established by the read-only code audit."""

    source = "jaxmarl/env/vec_jax.py"
    evaluator = "eval/eval_sumo_stage1_mc.py"
    trace_builder = "eval/build_trace.py"
    fields = [
        TosFieldContract(
            field="task_type",
            artifact="instrumented/pertask/*_pertask.npz",
            meaning="Task class code: 0=T1, 1=T2, 2=T3.",
            unit="code",
            status=TosContractStatus.CONFIRMED,
            evidence=[source],
        ),
        TosFieldContract(
            field="task_met",
            artifact="instrumented/pertask/*_pertask.npz",
            meaning="Whether modelled end-to-end latency was within the class deadline.",
            unit="boolean",
            status=TosContractStatus.CONFIRMED,
            evidence=[source],
            limitations=["This does not establish eventual physical task completion."],
        ),
        TosFieldContract(
            field="task_lat_ms",
            artifact="instrumented/pertask/*_pertask.npz",
            meaning="Modelled end-to-end task latency including compute backlog delay.",
            unit="ms",
            status=TosContractStatus.CONFIRMED,
            evidence=[source],
            limitations=[
                "Unavailable offload paths can receive the environment's capped failure latency."
            ],
        ),
        TosFieldContract(
            field="times",
            artifact="traces/*.npz and instrumented/perstep/*_perstep.npz",
            meaning="SUMO simulation timestamp.",
            unit="s",
            status=TosContractStatus.CONFIRMED,
            evidence=[trace_builder],
        ),
        TosFieldContract(
            field="pos_x, pos_y, rsu_xy",
            artifact="traces/*.npz",
            meaning="SUMO network coordinates.",
            unit="m",
            status=TosContractStatus.CONFIRMED,
            evidence=[trace_builder, "SUMO FCD output contract"],
        ),
        TosFieldContract(
            field="speed",
            artifact="traces/*.npz",
            meaning="Vehicle speed copied from SUMO FCD output.",
            unit="m/s",
            status=TosContractStatus.CONFIRMED,
            evidence=[trace_builder, "SUMO FCD output contract"],
        ),
        TosFieldContract(
            field="veh_action",
            artifact="instrumented/perstep/*_perstep.npz",
            meaning="Decision code at a time-local vehicle slot: 0=local, 1=V2I, 2=V2V.",
            unit="code",
            status=TosContractStatus.CONFIRMED,
            evidence=[source],
            limitations=["The chosen RSU or peer target is not exported."],
        ),
        TosFieldContract(
            field="rsu_load",
            artifact="instrumented/perstep/*_perstep.npz",
            meaning="Number of in-flight tasks assigned to an RSU.",
            unit="tasks",
            status=TosContractStatus.CONFIRMED,
            evidence=[source],
            limitations=["This is not queue length and not CPU utilisation."],
        ),
        TosFieldContract(
            field="rsu_busy_ms",
            artifact="instrumented/perstep/*_perstep.npz",
            meaning="Total remaining RSU compute backlog across in-flight tasks.",
            unit="ms",
            status=TosContractStatus.CONFIRMED,
            evidence=[source],
            limitations=["It has no validated utilisation denominator."],
        ),
        TosFieldContract(
            field="rsu_max_concurrent",
            artifact="instrumented/json/*.json",
            meaning="Maximum concurrent in-flight task count for each RSU.",
            unit="tasks",
            status=TosContractStatus.CONFIRMED,
            evidence=[source, evaluator],
            limitations=[
                "The evaluator default is round(2.5 * maxN), but the recorded summary value is "
                "authoritative for an imported run."
            ],
        ),
        TosFieldContract(
            field="vehicle array index",
            artifact="traces/*.npz",
            meaning="Padded, time-local slot allocated by the FCD trace builder.",
            unit=None,
            status=TosContractStatus.CONFIRMED,
            evidence=[trace_builder],
            limitations=[
                "Slots are reused and cannot be treated as persistent physical vehicle IDs."
            ],
        ),
        TosFieldContract(
            field="fleet_tier_hist",
            artifact="instrumented/json/*.json",
            meaning="Aggregate count of sampled compute tiers in the padded fleet.",
            unit="vehicles",
            status=TosContractStatus.CONFIRMED,
            evidence=[evaluator],
            limitations=["Per-slot vehicle tier is not exported."],
        ),
    ]
    unknown = CapabilitySupport.UNKNOWN
    disabled = CapabilitySupport.FALSE
    controls = [
        TosControlContract(
            control="task_arrival_rate",
            source_support=CapabilitySupport.TRUE,
            adapter_support=disabled,
            mechanism="Training stress configuration/environment variables.",
            status=TosContractStatus.CONFIRMED,
            limitations=["The current SUMO evaluator does not expose this as a CLI argument."],
        ),
        TosControlContract(
            control="task_class_mix",
            source_support=CapabilitySupport.TRUE,
            adapter_support=disabled,
            mechanism="VEC_JAX_TASK_DIST preset.",
            status=TosContractStatus.CONFIRMED,
        ),
        TosControlContract(
            control="task_ordering",
            source_support=CapabilitySupport.TRUE,
            adapter_support=disabled,
            mechanism="Training stress configuration/environment variables.",
            status=TosContractStatus.CONFIRMED,
        ),
        TosControlContract(
            control="vehicle_count",
            source_support=CapabilitySupport.TRUE,
            adapter_support=disabled,
            mechanism="Environment configuration or trace maxN during evaluation.",
            status=TosContractStatus.CONFIRMED,
        ),
        TosControlContract(
            control="vehicle_tier_mix",
            source_support=CapabilitySupport.TRUE,
            adapter_support=disabled,
            mechanism="Evaluator --fleet preset and --fleet-seed.",
            status=TosContractStatus.CONFIRMED,
        ),
        TosControlContract(
            control="rsu_count_and_placement",
            source_support=CapabilitySupport.TRUE,
            adapter_support=disabled,
            mechanism="RSU placement preprocessing encoded into the trace NPZ.",
            status=TosContractStatus.CONFIRMED,
            limitations=["Not exposed as a direct evaluator override."],
        ),
        TosControlContract(
            control="rsu_capacity",
            source_support=CapabilitySupport.TRUE,
            adapter_support=disabled,
            mechanism="Evaluator --rsu-cap-per-veh argument.",
            status=TosContractStatus.CONFIRMED,
        ),
        TosControlContract(
            control="action_toggles",
            source_support=unknown,
            adapter_support=disabled,
            status=TosContractStatus.UNKNOWN,
            limitations=["Action masks exist internally, but no scenario-level toggle is exposed."],
        ),
        TosControlContract(
            control="signal_timing",
            source_support=unknown,
            adapter_support=disabled,
            status=TosContractStatus.UNKNOWN,
        ),
        TosControlContract(
            control="lane_closure",
            source_support=unknown,
            adapter_support=disabled,
            status=TosContractStatus.UNKNOWN,
        ),
    ]
    return TosSourceContract(
        source_versions={
            "python": "3.11",
            "jax": "0.4.30",
            "jaxlib": "0.4.30",
            "sumo": TOS_SUMO_VERSION,
        },
        fields=fields,
        controls=controls,
        execution=TosExecutionContract(
            status=TosContractStatus.INFERRED,
            interface="Python CLI evaluator",
            command_template=[
                "python",
                "eval/eval_sumo_stage1_mc.py",
                "--trace",
                "TRACE.npz",
                "--actor",
                "ACTOR_PARAMS.npz",
                "--seed",
                "0",
                "--fleet",
                "uk2030",
                "--fleet-seed",
                "0",
                "--out-json",
                "OUT.json",
            ],
            output_contract="Current evaluator writes one aggregate summary JSON.",
            direct_launch=disabled,
            asynchronous_launch=disabled,
            blockers=[
                "Actor/checkpoint files referenced by the results package are unavailable.",
                "The evaluator contains a source-author-specific hard-coded repository path.",
                "The writer for supplied per-step and per-task arrays is not present.",
                "The evaluator has not been runtime-tested in the TrafficTwin environment.",
            ],
        ),
        unavailable_outputs=[
            "persistent vehicle identifiers",
            "per-vehicle compute tier",
            "V2I RSU target",
            "V2V peer target",
            "decision-time action availability",
            "decision-time link quality",
            "trip or journey-time records",
            "raw SUMO FCD/XML/network/route files",
        ],
        interpretation_limits=[
            "The evidence commit documents semantics; it is not asserted as the producer commit "
            "for every data-package row.",
            "Concurrency pressure rsu_load/rsu_max_concurrent is an inspection signal, not a "
            "TrafficTwin infrastructure utilisation metric.",
            "No source field is promoted to canonical data when its semantics do not match the "
            "existing canonical contract.",
        ],
    )
