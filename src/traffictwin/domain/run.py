"""Run domain model."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from traffictwin.domain.enums import ExecutionMode, RunStatus, ValidationStatus
from traffictwin.domain.experiment import utc_now
from traffictwin.domain.scenario import StrictModel, _validate_identifier


class Run(StrictModel):
    """Metadata for one exported, imported, or executed run."""

    schema_version: str = "1.0"
    run_id: str
    experiment_id: str | None = None
    seed_id: str
    algorithm: str = Field(min_length=1)
    checkpoint: str | None = None
    random_seed: int = Field(ge=0)
    environment_version: str | None = None
    environment_commit: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    execution_mode: ExecutionMode = ExecutionMode.EXPORT_ONLY
    status: RunStatus = RunStatus.REGISTERED
    source_bundle: str | None = None
    validation_status: ValidationStatus = ValidationStatus.NOT_VALIDATED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("run_id", "experiment_id", "seed_id")
    @classmethod
    def validate_identifiers(cls, value: str | None, info: object) -> str | None:
        field_name = getattr(info, "field_name", "identifier")
        return _validate_identifier(value, field_name)

    @model_validator(mode="after")
    def validate_time_order(self) -> Run:
        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at < self.started_at
        ):
            raise ValueError("ended_at must not be before started_at")
        return self
