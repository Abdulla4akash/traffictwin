"""Versioned task-energy evidence contract."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

TASK_ENERGY_CONTRACT_VERSION: Literal["1.0"] = "1.0"


class TaskEnergyContract(BaseModel):
    """Exact semantics required before canonical task-energy metrics are admissible."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = TASK_ENERGY_CONTRACT_VERSION
    quantity: Literal["per_task_total_energy"] = "per_task_total_energy"
    canonical_energy_unit: Literal["J"] = "J"
    observation_level: Literal["one_value_per_task_record"] = "one_value_per_task_record"
    per_task_eligibility: Literal["finite_non_negative_energy"] = "finite_non_negative_energy"
    per_completed_eligibility: Literal["completed_and_finite_non_negative_energy"] = (
        "completed_and_finite_non_negative_energy"
    )
    energy_delay_eligibility: Literal["completed_with_finite_non_negative_energy_and_latency"] = (
        "completed_with_finite_non_negative_energy_and_latency"
    )
    canonical_delay_unit: Literal["ms"] = "ms"

    def fingerprint(self) -> str:
        """Return a source-independent semantic-contract fingerprint."""

        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


DEFAULT_TASK_ENERGY_CONTRACT = TaskEnergyContract()
