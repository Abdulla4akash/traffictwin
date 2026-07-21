"""Versioned run-bundle manifest model."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.domain.energy import TaskEnergyContract
from traffictwin.domain.enums import ExecutionMode
from traffictwin.domain.measurement import SyntheticMeasurementImpairmentAudit
from traffictwin.domain.scenario import _validate_identifier
from traffictwin.domain.spatial import TaskRsuTargetContract, VehicleSpatialGridContract

SUPPORTED_MANIFEST_SCHEMA_VERSION: Literal["1.0"] = "1.0"
SUPPORTED_FILE_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class SourceFileFormat(StrEnum):
    """Physical tabular encoding declared for one source file."""

    CSV = "csv"
    PARQUET = "parquet"


class SourceCompression(StrEnum):
    """Supported outer compression for a declared source file."""

    GZIP = "gzip"


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
    format: SourceFileFormat = SourceFileFormat.CSV
    compression: SourceCompression | None = None
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
        if self.format is SourceFileFormat.PARQUET and self.compression is not None:
            raise ValueError("outer compression is supported only for CSV files")
        return self

    def source_column_for(self, canonical_field: str) -> str:
        """Return the source column for a canonical field."""

        return self.column_map.get(canonical_field, canonical_field)


class ProvenanceInfo(ManifestModel):
    """Producer provenance."""

    producer: str = Field(min_length=1)
    notes: str | None = None


class CanonicalisationEvidence(ManifestModel):
    """Recorded user confirmation for mappings proposed by the inference wizard."""

    schema_version: Literal["1.0"] = "1.0"
    inference_version: str = Field(min_length=1)
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_state: Literal["accepted_suggestions", "edited"]
    confirmed_by: str = Field(min_length=1)
    excluded_files: list[str] = Field(default_factory=list)


class BundleManifest(ManifestModel):
    """Top-level run-bundle manifest."""

    schema_version: Literal["1.0"]
    bundle: BundleInfo
    run: RunInfo
    environment: EnvironmentInfo
    files: dict[str, FileDeclaration] = Field(default_factory=dict)
    provenance: ProvenanceInfo
    energy_contract: TaskEnergyContract | None = None
    task_rsu_target_contract: TaskRsuTargetContract | None = None
    vehicle_spatial_grid_contract: VehicleSpatialGridContract | None = None
    synthetic_measurement_impairment: SyntheticMeasurementImpairmentAudit | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    canonicalisation: CanonicalisationEvidence | None = None

    @field_validator("files")
    @classmethod
    def validate_file_kinds(cls, value: dict[str, FileDeclaration]) -> dict[str, FileDeclaration]:
        supported = {"tasks", "infra_state", "vehicle_state", "traffic_obs", "trips", "incidents"}
        unsupported = sorted(set(value) - supported)
        if unsupported:
            raise ValueError(f"unsupported file declarations: {', '.join(unsupported)}")
        return value

    @model_validator(mode="after")
    def validate_canonicalisation_fingerprint(self) -> BundleManifest:
        if self.canonicalisation is None:
            return self
        if any(
            declaration.format is not SourceFileFormat.CSV or declaration.compression is not None
            for declaration in self.files.values()
        ):
            raise ValueError(
                "manifest-inference confirmation applies only to uncompressed CSV declarations"
            )
        evidence = self.canonicalisation
        mappings = [
            {
                "path": declaration.path,
                "kind": kind,
                "checksum_sha256": declaration.checksum_sha256,
                "required_columns": declaration.required_columns,
                "column_map": declaration.column_map,
                "units": declaration.units,
            }
            for kind, declaration in self.files.items()
        ]
        expected = canonicalisation_confirmation_fingerprint(
            inference_version=evidence.inference_version,
            source_fingerprint=evidence.source_fingerprint,
            draft_fingerprint=evidence.draft_fingerprint,
            confirmation_state=evidence.confirmation_state,
            confirmed_by=evidence.confirmed_by,
            mappings=mappings,
            excluded_files=evidence.excluded_files,
        )
        if evidence.confirmation_fingerprint != expected:
            raise ValueError("canonicalisation confirmation fingerprint does not match mappings")
        return self

    @model_validator(mode="after")
    def validate_energy_contract(self) -> BundleManifest:
        if self.energy_contract is None:
            return self
        tasks = self.files.get("tasks")
        if tasks is None:
            raise ValueError("energy_contract requires a tasks file declaration")
        if tasks.units.get("energy_j") != self.energy_contract.canonical_energy_unit:
            raise ValueError("energy_contract requires tasks.units.energy_j to be J")
        return self

    @model_validator(mode="after")
    def validate_task_rsu_target_contract(self) -> BundleManifest:
        if self.task_rsu_target_contract is None:
            return self
        tasks = self.files.get("tasks")
        infrastructure = self.files.get("infra_state")
        if tasks is None or infrastructure is None:
            raise ValueError(
                "task_rsu_target_contract requires tasks and infra_state file declarations"
            )
        target_column = tasks.source_column_for("target_id")
        if target_column not in tasks.required_columns:
            raise ValueError(
                "task_rsu_target_contract requires the mapped tasks target_id column to be required"
            )
        rsu_column = infrastructure.source_column_for("rsu_id")
        if rsu_column not in infrastructure.required_columns:
            raise ValueError(
                "task_rsu_target_contract requires the mapped infra_state rsu_id column to be "
                "required"
            )
        return self

    @model_validator(mode="after")
    def validate_vehicle_spatial_grid_contract(self) -> BundleManifest:
        contract = self.vehicle_spatial_grid_contract
        if contract is None:
            return self
        vehicles = self.files.get("vehicle_state")
        if vehicles is None:
            raise ValueError("vehicle_spatial_grid_contract requires a vehicle_state declaration")
        for field in ("x", "y"):
            source_column = vehicles.source_column_for(field)
            if source_column not in vehicles.required_columns:
                raise ValueError(
                    "vehicle_spatial_grid_contract requires mapped vehicle_state x and y columns "
                    "to be required"
                )
            if vehicles.units.get(field) != contract.canonical_coordinate_unit:
                raise ValueError(
                    "vehicle_spatial_grid_contract requires vehicle_state x and y units to be m"
                )
        return self

    @model_validator(mode="after")
    def validate_synthetic_measurement_impairment(self) -> BundleManifest:
        audit = self.synthetic_measurement_impairment
        if audit is None:
            return self
        if self.run.execution_mode is not ExecutionMode.SYNTHETIC:
            raise ValueError("synthetic_measurement_impairment requires synthetic execution mode")
        if not self.bundle.source.startswith("synthetic"):
            raise ValueError("synthetic_measurement_impairment requires a synthetic bundle label")
        required_tables = {item.table_kind.value for item in audit.field_audits} | {
            item.table_kind.value for item in audit.dropout_audits
        }
        missing = sorted(required_tables - set(self.files))
        if missing:
            raise ValueError(
                "synthetic_measurement_impairment references undeclared tables: "
                + ", ".join(missing)
            )
        return self


def canonicalisation_confirmation_fingerprint(
    *,
    inference_version: str,
    source_fingerprint: str,
    draft_fingerprint: str,
    confirmation_state: str,
    confirmed_by: str,
    mappings: list[dict[str, Any]],
    excluded_files: list[str],
) -> str:
    """Fingerprint confirmed mappings in both standalone and embedded forms."""

    payload = {
        "schema_version": "1.0",
        "inference_version": inference_version,
        "source_fingerprint": source_fingerprint,
        "draft_fingerprint": draft_fingerprint,
        "confirmation_state": confirmation_state,
        "confirmed_by": confirmed_by,
        "mappings": sorted(mappings, key=lambda item: (str(item["path"]), str(item["kind"]))),
        "excluded_files": sorted(excluded_files),
        "analysis_ready": True,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
