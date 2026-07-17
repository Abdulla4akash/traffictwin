"""Diagnostic rule catalogue."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.rules.registry import default_rule_registry


class RuleDefinition(BaseModel):
    """Public metadata for one diagnostic rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    title: str
    rule_version: str
    purpose: str
    required_evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def rule_catalogue() -> dict[str, RuleDefinition]:
    """Return rule definitions ordered by stable rule id."""

    registry = default_rule_registry()
    definitions = {
        "R0": RuleDefinition(
            rule_id="R0",
            title=registry["R0"].title,
            rule_version=registry["R0"].rule_version,
            purpose="Identify validation and evidence gaps that block or qualify diagnosis.",
            required_evidence=["validation_summary", "evidence_availability", "metric_collection"],
            limitations=["R0 emits data-readiness guidance, not causal hypotheses."],
        ),
        "R1": RuleDefinition(
            rule_id="R1",
            title=registry["R1"].title,
            rule_version=registry["R1"].rule_version,
            purpose="Identify candidate under-use of external compute capacity.",
            required_evidence=[
                "task.generated.count",
                "task.completion.rate_by_class",
                "task.offload.rate",
                "infra.utilisation.mean",
            ],
            limitations=[
                "Direct T1-by-low-tier evidence is not available in Phase 3 metric packs."
            ],
        ),
        "R2": RuleDefinition(
            rule_id="R2",
            title=registry["R2"].title,
            rule_version=registry["R2"].rule_version,
            purpose="Identify infrastructure pressure that may constrain task completion.",
            required_evidence=[
                "task.generated.count",
                "task.incomplete.rate",
                "infra.utilisation.p95",
                "infra.queue_length.max",
                "infra.saturation.duration_s",
                "infra.saturation.episode_count",
            ],
            limitations=["Temporal overlap is not directly available in Phase 3 metric packs."],
        ),
        "R3": RuleDefinition(
            rule_id="R3",
            title=registry["R3"].title,
            rule_version=registry["R3"].rule_version,
            purpose="Identify scenarios that may not distinguish policies.",
            required_evidence=[
                "experiment.algorithm.count",
                "experiment.cross_algorithm_dispersion",
            ],
            limitations=["Ordinary single-run EvidencePacks are insufficient for R3."],
        ),
    }
    return {rule_id: definitions[rule_id] for rule_id in sorted(definitions)}
