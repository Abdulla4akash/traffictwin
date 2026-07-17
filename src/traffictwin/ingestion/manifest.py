"""Versioned run-bundle manifest model."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.domain.enums import ExecutionMode
from traffictwin.domain.scenario import _validate_identifier

SUPPORTED_MANIFEST_SCHEMA_VERSION: Literal["1.0"] = "1.0"
SUPPORTED_FILE_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class ManifestModel(BaseModel):
    """Base manifest model."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class BundleInfo(ManifestModel):
    """Bundle-level metadata."""

    bundle_id: str
    created_at: datetime
    source: str = Field(min_length=1)

    @field_validator("bundle_id")
    @classmethod
    def validate_bundle_id(cls, value: str) -> str:
        return _validate_identifier(value, "bundle_id") or value


class RunInfo(ManifestModel):
    """Run-level metadata from the manifest."""

    run_id: str
    experiment_id: str
    seed_id: str
    algorithm: str = Field(min_length=1)
    checkpoint: str | None = None
    random_seed: int = Field(ge=0)
    execution_mode: ExecutionMode = ExecutionMode.IMPORTED
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("run_id", "experiment_id", "seed_id")
    @classmethod
    def validate_identifiers(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "identifier")
        return _validate_identifier(value, field_name) or value

    @model_validator(mode="after")
    def validate_time_order(self) -> RunInfo:
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not be before started_at")
        return self


class EnvironmentInfo(ManifestModel):
    """Environment metadata."""

    name: str = Field(min_length=1)
    version: str | None = None
    commit: str | None = None


class FileDeclaration(ManifestModel):
    """Declared source file and mapping information."""

    path: str = Field(min_length=1)
    schema_version: Literal["1.0"] = SUPPORTED_FILE_SCHEMA_VERSION
    required_columns: list[str] = Field(default_factory=list)
    column_map: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    checksum_sha256: str | None = None
    required: bool = False

    @field_validator("required_columns")
    @classmethod
    def validate_required_columns(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("required_columns must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_safe_relative_path(self) -> FileDeclaration:
        if self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("file declaration path must be a safe relative path")
        return self

    def source_column_for(self, canonical_field: str) -> str:
        """Return the source column for a canonical field."""

        return self.column_map.get(canonical_field, canonical_field)


class ProvenanceInfo(ManifestModel):
    """Producer provenance."""

    producer: str = Field(min_length=1)
    notes: str | None = None


class BundleManifest(ManifestModel):
    """Top-level run-bundle manifest."""

    schema_version: Literal["1.0"]
    bundle: BundleInfo
    run: RunInfo
    environment: EnvironmentInfo
    files: dict[str, FileDeclaration] = Field(default_factory=dict)
    provenance: ProvenanceInfo

    @field_validator("files")
    @classmethod
    def validate_file_kinds(cls, value: dict[str, FileDeclaration]) -> dict[str, FileDeclaration]:
        supported = {"tasks", "infra_state", "vehicle_state", "traffic_obs", "trips", "incidents"}
        unsupported = sorted(set(value) - supported)
        if unsupported:
            raise ValueError(f"unsupported file declarations: {', '.join(unsupported)}")
        return value
