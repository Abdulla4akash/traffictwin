"""Standalone synthetic scenario presets."""

from __future__ import annotations

from traffictwin.domain.enums import TaskClass
from traffictwin.synthetic.config import (
    IncidentSpec,
    SyntheticPolicyProfile,
    SyntheticScenarioConfig,
)


def list_preset_names() -> list[str]:
    """Return supported standalone preset names."""

    return [
        "baseline",
        "stressed_demand",
        "under_offloading",
        "infrastructure_bottleneck",
        "mixed_fault",
        "partial_evidence",
        "trivial_multi_algorithm",
    ]


def preset_config(
    name: str,
    *,
    random_seed: int = 7,
    policy: SyntheticPolicyProfile | None = None,
) -> SyntheticScenarioConfig:
    """Return a documented deterministic preset configuration."""

    if name == "baseline":
        return SyntheticScenarioConfig(
            scenario_id="baseline",
            name="Standalone baseline",
            description="Moderate synthetic demand with usable infrastructure capacity.",
            random_seed=random_seed,
            task_arrival_rate=0.11,
            congestion_multiplier=1.0,
            policy_behavior=policy or SyntheticPolicyProfile.BALANCED,
        )
    if name == "stressed_demand":
        return SyntheticScenarioConfig(
            scenario_id="stressed_demand",
            name="Standalone stressed demand",
            description="Higher synthetic demand with reduced capacity and longer trips.",
            baseline_seed_id="seed-baseline",
            random_seed=random_seed,
            task_arrival_rate=0.18,
            congestion_multiplier=1.65,
            rsu_capacity=22.0,
            policy_behavior=policy or SyntheticPolicyProfile.BALANCED,
            synthetic_faults=["higher_demand", "reduced_rsu_capacity", "longer_trips"],
            incident_schedule=[
                IncidentSpec(
                    timestamp_s=120.0,
                    incident_type="synthetic_congestion_pulse",
                    location="synthetic-corridor-a",
                    severity="moderate",
                )
            ],
        )
    if name == "under_offloading":
        return SyntheticScenarioConfig(
            scenario_id="under_offloading",
            name="Standalone under-offloading candidate",
            description="T1-heavy low-tier workload with low offload use and spare RSU capacity.",
            baseline_seed_id="seed-baseline",
            random_seed=random_seed,
            vehicle_tier_mix={"low": 0.7, "medium": 0.2, "high": 0.1},
            task_arrival_rate=0.14,
            task_class_mix={TaskClass.T1: 0.6, TaskClass.T2: 0.25, TaskClass.T3: 0.15},
            congestion_multiplier=1.05,
            policy_behavior=policy or SyntheticPolicyProfile.LOW_OFFLOAD,
            synthetic_faults=["weak_vehicle_t1_concentration", "spare_rsu_capacity"],
        )
    if name == "infrastructure_bottleneck":
        return SyntheticScenarioConfig(
            scenario_id="infrastructure_bottleneck",
            name="Standalone infrastructure-bottleneck candidate",
            description="Sustained high synthetic RSU utilisation and queue pressure.",
            baseline_seed_id="seed-baseline",
            random_seed=random_seed,
            task_arrival_rate=0.17,
            congestion_multiplier=1.55,
            rsu_capacity=18.0,
            policy_behavior=policy or SyntheticPolicyProfile.SELECTIVE,
            synthetic_faults=["sustained_rsu_overload", "reduced_rsu_capacity", "longer_trips"],
        )
    if name == "mixed_fault":
        return SyntheticScenarioConfig(
            scenario_id="mixed_fault",
            name="Standalone mixed candidate",
            description="Low offload use with one saturated synthetic RSU and one spare RSU.",
            baseline_seed_id="seed-baseline",
            random_seed=random_seed,
            vehicle_tier_mix={"low": 0.65, "medium": 0.25, "high": 0.10},
            task_arrival_rate=0.16,
            task_class_mix={TaskClass.T1: 0.55, TaskClass.T2: 0.30, TaskClass.T3: 0.15},
            congestion_multiplier=1.3,
            policy_behavior=policy or SyntheticPolicyProfile.LOW_OFFLOAD,
            synthetic_faults=[
                "weak_vehicle_t1_concentration",
                "sustained_rsu_overload",
                "localised_saturation",
                "longer_trips",
            ],
        )
    if name == "partial_evidence":
        return SyntheticScenarioConfig(
            scenario_id="partial_evidence",
            name="Standalone partial-evidence bundle",
            description="Tasks-only synthetic bundle to exercise evidence limitations.",
            baseline_seed_id="seed-baseline",
            random_seed=random_seed,
            task_arrival_rate=0.10,
            congestion_multiplier=1.0,
            policy_behavior=policy or SyntheticPolicyProfile.LOW_OFFLOAD,
            include_infrastructure=False,
            include_vehicles=False,
            include_traffic=False,
            include_trips=False,
            include_incidents=False,
            synthetic_faults=["incomplete_evidence"],
        )
    if name == "trivial_multi_algorithm":
        return SyntheticScenarioConfig(
            scenario_id="trivial_multi_algorithm",
            name="Standalone trivial low-pressure scenario",
            description="Low-pressure synthetic scenario for R3-compatible multi-policy evidence.",
            random_seed=random_seed,
            task_arrival_rate=0.06,
            congestion_multiplier=0.85,
            rsu_capacity=50.0,
            policy_behavior=policy or SyntheticPolicyProfile.BALANCED,
            synthetic_faults=["low_pressure"],
        )
    msg = f"unknown synthetic preset: {name}"
    raise ValueError(msg)


def default_workspace_configs() -> list[SyntheticScenarioConfig]:
    """Return standalone demo configs for single-run scenarios."""

    return [
        preset_config("baseline"),
        preset_config("stressed_demand"),
        preset_config("under_offloading"),
        preset_config("infrastructure_bottleneck"),
        preset_config("mixed_fault"),
        preset_config("partial_evidence"),
    ]
