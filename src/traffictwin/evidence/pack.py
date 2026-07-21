"""Versioned evidence pack for future deterministic rules."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.evidence.availability import EvidenceAvailability
from traffictwin.evidence.temporal import TemporalEvidence
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import JsonScalar, MetricCollection


class EvidencePack(BaseModel):
    """Structured evidence object consumed by future diagnostic rules."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    pack_id: str
    generated_at: datetime
    synthetic: bool
    run_context: dict[str, JsonScalar]
    source_bundle_fingerprint: str | None
    validation_summary: dict[str, JsonScalar | dict[str, JsonScalar]]
    evidence_availability: EvidenceAvailability
    metric_engine_config: MetricEngineConfig
    metric_collection: MetricCollection
    temporal_evidence: TemporalEvidence | None = None
    excluded_record_counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)

    def to_json(self) -> str:
        """Return JSON output."""

        return self.model_dump_json(indent=2)

    def canonical_json(self) -> str:
        """Return canonical JSON excluding volatile generated timestamps."""

        data = self.model_dump(mode="json")
        data["generated_at"] = "<normalised>"
        data["metric_collection"]["generated_at"] = "<normalised>"
        for result in data["metric_collection"]["results"]:
            result["computed_at"] = "<normalised>"
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        """Return a deterministic fingerprint for this evidence pack."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
