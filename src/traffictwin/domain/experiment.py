"""Experiment domain model."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, field_validator

from traffictwin.domain.enums import ExperimentStatus
from traffictwin.domain.scenario import StrictModel, _validate_identifier


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


class Experiment(StrictModel):
    """A planned or executed research comparison across one baseline and variations."""

    schema_version: str = "1.0"
    experiment_id: str
    research_question: str = Field(min_length=1)
    hypothesis: str | None = None
    baseline_seed_id: str
    variation_seed_ids: list[str] = Field(default_factory=list)
    algorithms: list[str] = Field(default_factory=list)
    common_random_seed_set: list[int] = Field(default_factory=list)
    planned_replicates: int = Field(default=1, ge=1)
    status: ExperimentStatus = ExperimentStatus.PLANNED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("experiment_id", "baseline_seed_id")
    @classmethod
    def validate_identifiers(cls, value: str) -> str:
        return _validate_identifier(value, "experiment identifier") or value

    @field_validator("variation_seed_ids")
    @classmethod
    def validate_variations(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("variation_seed_ids must not contain duplicates")
        for seed_id in value:
            _validate_identifier(seed_id, "variation_seed_ids item")
        return value

    @field_validator("algorithms")
    @classmethod
    def validate_algorithms(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("algorithms must not contain duplicates")
        return value

    @field_validator("common_random_seed_set")
    @classmethod
    def validate_random_seed_set(cls, value: list[int]) -> list[int]:
        if any(seed < 0 for seed in value):
            raise ValueError("common_random_seed_set values must be non-negative")
        if len(set(value)) != len(value):
            raise ValueError("common_random_seed_set must not contain duplicates")
        return value
