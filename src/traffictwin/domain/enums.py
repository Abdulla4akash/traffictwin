"""Shared domain enumerations for TrafficTwin."""

from enum import StrEnum


class TaskClass(StrEnum):
    """Supported task classes in the Phase 1 seed schema."""

    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class Decision(StrEnum):
    """Supported offloading decision labels in TrafficTwin's internal contract."""

    LOCAL = "local"
    V2I = "v2i"
    V2V = "v2v"


class WorkloadOrdering(StrEnum):
    """Supported workload ordering settings."""

    EASY_FIRST = "easy_first"
    MIXED = "mixed"
    HARD_FIRST = "hard_first"


class FleetTierMix(StrEnum):
    """Coarse fleet capability mix categories for scenario seeds."""

    WEAK = "weak"
    MIXED = "mixed"
    HIGH_COMPUTE = "high_compute"


class RsuCapacityMode(StrEnum):
    """Coarse RSU capacity settings for scenario seeds."""

    REDUCED = "reduced"
    STANDARD = "standard"
    EXPANDED = "expanded"


class ExperimentStatus(StrEnum):
    """Lifecycle states for an experiment record."""

    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class RunStatus(StrEnum):
    """Lifecycle states for a run record."""

    REGISTERED = "registered"
    EXPORTED = "exported"
    IMPORTED = "imported"
    VALIDATING = "validating"
    VALIDATED = "validated"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionMode(StrEnum):
    """Known execution modes for run metadata."""

    EXPORT_ONLY = "export_only"
    IMPORTED = "imported"
    DIRECT_LAUNCH = "direct_launch"
    SYNTHETIC = "synthetic"


class ValidationStatus(StrEnum):
    """Validation state for an imported or registered run."""

    NOT_VALIDATED = "not_validated"
    VALID = "valid"
    INVALID = "invalid"
