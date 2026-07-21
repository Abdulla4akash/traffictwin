"""Domain models for TrafficTwin."""

from traffictwin.domain.energy import DEFAULT_TASK_ENERGY_CONTRACT, TaskEnergyContract
from traffictwin.domain.enums import (
    Decision,
    ExecutionMode,
    ExperimentStatus,
    FleetTierMix,
    RsuCapacityMode,
    RunStatus,
    TaskClass,
    ValidationStatus,
    WorkloadOrdering,
)
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.fairness import (
    DEFAULT_OPERATIONAL_FAIRNESS_POLICY,
    OperationalFairnessPolicy,
)
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed, SeedDocument
from traffictwin.domain.spatial import (
    DEFAULT_SYNTHETIC_SPATIAL_GRID_CONTRACT,
    DEFAULT_TASK_RSU_TARGET_CONTRACT,
    TaskRsuTargetContract,
    VehicleSpatialGridContract,
)

__all__ = [
    "Decision",
    "DEFAULT_SYNTHETIC_SPATIAL_GRID_CONTRACT",
    "DEFAULT_TASK_ENERGY_CONTRACT",
    "DEFAULT_TASK_RSU_TARGET_CONTRACT",
    "DEFAULT_OPERATIONAL_FAIRNESS_POLICY",
    "ExecutionMode",
    "Experiment",
    "ExperimentStatus",
    "FleetTierMix",
    "RsuCapacityMode",
    "Run",
    "RunStatus",
    "ScenarioSeed",
    "SeedDocument",
    "TaskClass",
    "TaskEnergyContract",
    "TaskRsuTargetContract",
    "OperationalFairnessPolicy",
    "ValidationStatus",
    "VehicleSpatialGridContract",
    "WorkloadOrdering",
]
