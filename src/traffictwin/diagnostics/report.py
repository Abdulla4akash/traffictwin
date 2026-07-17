"""Diagnostic report models."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.metrics.results import JsonScalar, JsonValue
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.models import RuleResult, RuleStatus


class OverallReadiness(StrEnum):
    """Overall diagnostic readiness for a report."""

    READY = "ready"
    PARTIALLY_READY = "partially_ready"
    INSUFFICIENT = "insufficient"
    INVALID = "invalid"


class DiagnosticReport(BaseModel):
    """Versioned deterministic diagnostic report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    report_id: str
    evidence_pack_id: str
    run_context: dict[str, JsonScalar]
    generated_at: datetime
    ruleset_version: str
    rule_config: RuleSetConfig
    results: list[RuleResult]
    triggered_rule_ids: list[str]
    insufficient_rule_ids: list[str]
    conflicting_rule_ids: list[str]
    blocked_rules: list[str]
    evidence_summary: dict[str, JsonValue]
    overall_readiness: OverallReadiness
    synthetic: bool
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    conflict_observations: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return JSON output."""

        return self.model_dump_json(indent=2)

    def canonical_json(self) -> str:
        """Return canonical JSON excluding volatile generated/evaluated timestamps."""

        data = self.model_dump(mode="json")
        data["generated_at"] = "<normalised>"
        for result in data["results"]:
            result["evaluated_at"] = "<normalised>"
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        """Return a stable report fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def diagnostic_report_id(
    *,
    evidence_pack_id: str,
    ruleset_version: str,
    generated_at: datetime,
) -> str:
    """Build a deterministic report id for fixed evidence/config/clock inputs."""

    basis = f"{evidence_pack_id}|{ruleset_version}|{generated_at.isoformat()}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
    return f"diagnostic-{digest}"


def readiness_from_results(results: list[RuleResult]) -> OverallReadiness:
    """Derive an overall readiness label without choosing one global cause."""

    if any(result.status is RuleStatus.INVALID for result in results):
        return OverallReadiness.INVALID
    if not results:
        return OverallReadiness.INSUFFICIENT
    if all(result.status is RuleStatus.INSUFFICIENT_EVIDENCE for result in results):
        return OverallReadiness.INSUFFICIENT
    if any(result.status is RuleStatus.INSUFFICIENT_EVIDENCE for result in results):
        return OverallReadiness.PARTIALLY_READY
    return OverallReadiness.READY
