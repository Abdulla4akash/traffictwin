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
        "R4": RuleDefinition(
            rule_id="R4",
            title=registry["R4"].title,
            rule_version=registry["R4"].rule_version,
            purpose="Identify uneven capacity-normalised RSU load at moderate total utilisation.",
            required_evidence=[
                "infra.load_balance.jain_capacity_normalised",
                "infra.utilisation.mean",
                "infra.observed_rsu.count",
            ],
            limitations=[
                "Routing and location context are required before interpreting the candidate cause."
            ],
        ),
        "R5": RuleDefinition(
            rule_id="R5",
            title=registry["R5"].title,
            rule_version=registry["R5"].rule_version,
            purpose=(
                "Identify descriptive gaps between explicitly paired training and validation "
                "metrics."
            ),
            required_evidence=[
                "experiment.training_validation.pair_count",
                "experiment.training_validation.max_absolute_gap",
            ],
            limitations=[
                "R5 does not infer pairings, overfitting, or causal mechanisms from labels."
            ],
        ),
        "R6": RuleDefinition(
            rule_id="R6",
            title=registry["R6"].title,
            rule_version=registry["R6"].rule_version,
            purpose=(
                "Identify sustained adverse within-run metric movement and classify declared-event "
                "recovery without treating gaps as values."
            ),
            required_evidence=[
                "temporal_evidence",
                "windowed_metric_series",
                "window-applicable scalar metric with objective direction",
            ],
            limitations=[
                "R6 thresholds are provisional and results are descriptive candidates, not causal "
                "incident or drift proof."
            ],
        ),
        "R7": RuleDefinition(
            rule_id="R7",
            title=registry["R7"].title,
            rule_version=registry["R7"].rule_version,
            purpose=(
                "Identify supported operational completion-outcome disparity across one "
                "explicitly selected vehicle-tier or exact target-RSU dimension."
            ),
            required_evidence=[
                "fairness.vehicle_tier.completion_rate.max_gap or "
                "spatial.rsu.task.completion_rate_by_target",
                "complete compatible operational group contract",
                "at least two groups with declared minimum support",
            ],
            limitations=[
                "R7 is compiled through the closed declarative grammar and does not establish "
                "protected-attribute fairness, geography, significance, or causality."
            ],
        ),
        "R8": RuleDefinition(
            rule_id="R8",
            title=registry["R8"].title,
            rule_version=registry["R8"].rule_version,
            purpose=(
                "Identify high mean energy cost per completed task under one exact canonical "
                "energy contract and a minimum completed-task support requirement."
            ),
            required_evidence=[
                "task.energy.per_completed_j",
                "task.completed.count",
                "exact canonical v1.0 task-energy contract and complete completed-task coverage",
            ],
            limitations=[
                "R8 uses a provisional synthetic-development threshold and is not a statistical "
                "anomaly test, hardware benchmark, causal diagnosis, or external standard."
            ],
        ),
    }
    return {rule_id: definitions[rule_id] for rule_id in sorted(definitions)}
