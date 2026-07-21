"""Typed contracts for import-only Eclipse SUMO result packages."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.scenario import _validate_identifier
from traffictwin.evidence.availability import EvidenceAvailability
from traffictwin.metrics.results import MetricCollection
from traffictwin.validation.report import ValidationReport

SUMO_ADAPTER_VERSION = "1.0"
SUMO_RESULT_MANIFEST_VERSION = "1.0"
SUMO_VALIDATOR_VERSION = "sumo-results-1.0"
SUPPORTED_SUMO_VERSION_PREFIXES = ("1.27.",)


class SumoModel(BaseModel):
    """Strict base model for SUMO adapter artifacts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SumoBundleInfo(SumoModel):
    """Identity of one immutable SUMO result package."""

    bundle_id: str
    created_at: datetime

    @field_validator("bundle_id")
    @classmethod
    def validate_bundle_id(cls, value: str) -> str:
        return _validate_identifier(value, "bundle_id") or value


class SumoSourceInfo(SumoModel):
    """Declared scenario, software, permission, and retrieval provenance."""

    scenario_id: str = Field(min_length=1)
    scenario_url: str = Field(min_length=1)
    sumo_version: str = Field(min_length=1)
    source_commit: str | None = None
    licence_spdx: str = Field(min_length=1)
    retrieval_date: date
    redistribution_allowed: bool
    restrictions: list[str] = Field(default_factory=list)
    synthetic: bool = True


class SumoRunInfo(SumoModel):
    """Run metadata explicitly declared by the result producer or curator."""

    run_id: str
    experiment_id: str | None = None
    seed_id: str
    algorithm: str = Field(min_length=1)
    random_seed: int = Field(ge=0)

    @field_validator("run_id", "experiment_id", "seed_id")
    @classmethod
    def validate_identifiers(cls, value: str | None, info: object) -> str | None:
        return _validate_identifier(value, getattr(info, "field_name", "identifier"))


class SumoFileDeclaration(SumoModel):
    """One immutable XML result file declared by the package."""

    path: str = Field(min_length=1)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_safe_relative_path(self) -> SumoFileDeclaration:
        if self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("SUMO result file path must be a safe relative path")
        return self


class SumoFiles(SumoModel):
    """The v1 adapter's supported XML outputs."""

    tripinfo: SumoFileDeclaration
    summary: SumoFileDeclaration


class SumoResultManifest(SumoModel):
    """Top-level ``sumo-source.yaml`` contract."""

    schema_version: str
    adapter: str
    bundle: SumoBundleInfo
    source: SumoSourceInfo
    run: SumoRunInfo
    files: SumoFiles

    @model_validator(mode="after")
    def validate_version_and_adapter(self) -> SumoResultManifest:
        if self.schema_version != SUMO_RESULT_MANIFEST_VERSION:
            raise ValueError(
                f"only SUMO result manifest {SUMO_RESULT_MANIFEST_VERSION} is supported"
            )
        if self.adapter != "sumo_results":
            raise ValueError("adapter must be sumo_results")
        return self


class SumoTripStatus(StrEnum):
    """Observed state of one SUMO tripinfo element."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    UNDEPARTED = "undeparted"


class SumoTripObservation(SumoModel):
    """Source-specific tripinfo values retained without canonical relabelling."""

    source_file: str
    source_record: int = Field(ge=1)
    vehicle_id: str = Field(min_length=1)
    departure_time_s: float | None = None
    reported_arrival_time_s: float | None = None
    reported_duration_s: float = Field(ge=0)
    vaporized_reason: str | None = None
    status: SumoTripStatus


class SumoSummaryStep(SumoModel):
    """One documented simulation-wide SUMO summary step."""

    source_file: str
    source_record: int = Field(ge=1)
    time_s: float = Field(ge=0)
    loaded: int | None = Field(default=None, ge=0)
    inserted: int | None = Field(default=None, ge=0)
    running: int = Field(ge=0)
    waiting: int | None = Field(default=None, ge=0)
    ended: int | None = Field(default=None, ge=0)
    arrived: int | None = Field(default=None, ge=0)
    collisions: int | None = Field(default=None, ge=0)
    teleports: int | None = Field(default=None, ge=0)
    halting: int | None = Field(default=None, ge=0)
    stopped: int | None = Field(default=None, ge=0)
    discarded: int | None = Field(default=None, ge=0)
    mean_waiting_time_s: float | None = Field(default=None, ge=0)
    mean_travel_time_s: float | None = Field(default=None, ge=0)
    mean_speed_mps: float | None = Field(default=None, ge=0)
    mean_speed_relative: float | None = Field(default=None, ge=0)
    step_duration_ms: float | None = Field(default=None, ge=0)


class SumoRawFileEvidence(SumoModel):
    """Fingerprint and size of one preserved raw source file."""

    path: str
    sha256: str
    size_bytes: int = Field(ge=0)


class SumoValidationResult(SumoModel):
    """Complete read-only validation and canonicalisation result."""

    source: str
    fingerprint: str | None = None
    manifest: SumoResultManifest | None = None
    raw_files: list[SumoRawFileEvidence] = Field(default_factory=list)
    canonical: CanonicalTables = Field(default_factory=CanonicalTables)
    trip_observations: list[SumoTripObservation] = Field(default_factory=list)
    summary_steps: list[SumoSummaryStep] = Field(default_factory=list)
    evidence: EvidenceAvailability = Field(default_factory=EvidenceAvailability)
    report: ValidationReport = Field(default_factory=ValidationReport)

    def to_json(self) -> str:
        """Return a formatted machine-readable result."""

        return self.model_dump_json(indent=2)


class SumoImportResult(SumoModel):
    """Registry outcome for one validated SUMO result package."""

    bundle_id: str | None = None
    run_id: str | None = None
    created: bool = False
    idempotent: bool = False
    status: str
    metrics_stored: bool = False
    message: str


class SumoAnalysis(SumoModel):
    """Validated result plus deterministic canonical metrics."""

    validation: SumoValidationResult
    metrics: MetricCollection | None = None
