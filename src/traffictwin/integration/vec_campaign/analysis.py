"""Deterministic exploratory analysis over one completed VEC campaign.

The harness evaluates exactly the comparisons the campaign's design
predeclared — each variation arm against the single baseline arm on the single
primary endpoint — using the accepted STA-01 evaluator with its tool defaults,
and renders one deterministic report.

What it refuses to be: a conclusion generator. The output's exploratory status
is carried as type-level literals (``confirmatory: False``,
``significance_claimed: False``); STA-01's own insufficient/incompatible
statuses pass through untouched; secondary metrics are reported descriptively
per arm and are never promoted; and the three comparisons share one baseline
with no multiplicity correction, which the report states rather than hides.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from traffictwin.experiments import (
    ObjectiveDirection,
    PairedStudyConfig,
    evaluate_paired_statistical_study,
)
from traffictwin.experiments.statistical_study import StatisticalStudy
from traffictwin.integration.vec_campaign.models import (
    VecCampaignCellState,
    VecCampaignDesign,
    VecCampaignModel,
    VecCampaignReceipt,
)
from traffictwin.integration.vec_campaign.service import VecCampaignError
from traffictwin.integration.vec_runner.models import PINNED_ACTORS
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.storage.registry import Registry, RegistryError

VEC_CAMPAIGN_ANALYSIS_METHOD_VERSION: Literal["vec-campaign-analysis-1.0"] = (
    "vec-campaign-analysis-1.0"
)

STANDING_ANALYSIS_LIMITATIONS = (
    "Exploratory owner-approved-candidate evidence only; no confirmatory claim, "
    "no significance claim, and no scientific acceptance is made by this analysis.",
    "The comparisons share one baseline without multiplicity correction; the "
    "predeclaration reserves any corrected claim for the separately signed "
    "confirmatory protocol on the held-out seeds.",
    "Deadline success is never physical completion; reconstructed evaluator "
    "behaviour is never an observed journey; results describe one audited policy "
    "on one reviewed trace with one fleet preset.",
    "Interval and randomisation outputs are reported verbatim as STA-01 "
    "diagnostics of the exploratory pilot, not as accepted thresholds.",
)


class VecArmDescriptives(VecCampaignModel):
    """Per-arm descriptive values for one metric, listed per seed."""

    arm_label: str
    metric_key: str
    seed_values: dict[str, float]
    mean: float
    minimum: float
    maximum: float


class VecCampaignComparison(VecCampaignModel):
    """One predeclared variation-versus-baseline STA-01 evaluation."""

    variation_label: str
    study_status: str
    admitted_pair_count: int = Field(ge=0)
    mean_paired_difference: float | None = None
    bootstrap_lower: float | None = None
    bootstrap_upper: float | None = None
    randomisation_p_value: float | None = None
    study: StatisticalStudy


class VecCampaignAnalysis(VecCampaignModel):
    """Deterministic exploratory analysis artifact for one campaign."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["vec-campaign-analysis-1.0"] = VEC_CAMPAIGN_ANALYSIS_METHOD_VERSION
    experiment_id: str
    design_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    campaign_status: str
    primary_metric_key: str
    baseline_label: str
    admitted_collection_count: int = Field(ge=0)
    comparisons: list[VecCampaignComparison] = Field(min_length=1)
    primary_descriptives: list[VecArmDescriptives] = Field(min_length=1)
    secondary_descriptives: list[VecArmDescriptives] = Field(default_factory=list)
    generated_at_utc: str
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    confirmatory: Literal[False] = False
    significance_claimed: Literal[False] = False
    limitations: list[str] = Field(min_length=1, max_length=16)


SECONDARY_METRIC_KEYS = (
    "task.latency.mean_ms",
    "task.offload.rate",
    "tos.task.no_eligible_target.rate_among_offload",
)


def analyze_campaign(
    design: VecCampaignDesign,
    receipt: VecCampaignReceipt,
    registry_path: str | Path,
    *,
    objective: ObjectiveDirection = ObjectiveDirection.MAXIMISE,
    generated_at: datetime | None = None,
) -> VecCampaignAnalysis:
    """Evaluate the predeclared comparisons over a campaign's admitted evidence."""

    if receipt.design_fingerprint != design.fingerprint():
        raise VecCampaignError(
            "ANALYSIS_DESIGN_MISMATCH: the receipt does not belong to this design"
        )
    admitted_states = {VecCampaignCellState.ADMITTED, VecCampaignCellState.REUSED}
    admitted_run_ids = {
        cell.registry_run_id
        for cell in receipt.cells
        if cell.state in admitted_states and cell.registry_run_id is not None
    }
    if not admitted_run_ids:
        raise VecCampaignError("ANALYSIS_NO_ADMITTED_CELLS: nothing to analyse")

    registry = Registry(Path(registry_path))
    try:
        experiment = registry.get_experiment(design.experiment_id)
        payloads = registry.list_metric_collection_json()
    except RegistryError as exc:
        raise VecCampaignError(f"registry evidence could not be read: {exc}") from exc
    collections = [
        collection
        for collection in (MetricCollection.model_validate_json(item) for item in payloads)
        if collection.run_id in admitted_run_ids
        and collection.results
        and collection.results[0].experiment_id == design.experiment_id
    ]
    if not collections:
        raise VecCampaignError(
            "ANALYSIS_NO_ADMITTED_COLLECTIONS: admitted cells have no registry metrics"
        )

    comparisons = []
    for arm in design.variation_arms:
        config = PairedStudyConfig(
            experiment_id=design.experiment_id,
            baseline_seed_id=design.baseline_arm.label,
            variation_seed_id=arm.label,
            algorithm=design.actor_id,
            checkpoint=PINNED_ACTORS[design.actor_id][0],
            metric_key=design.primary_metric_key,
            objective=objective,
            expected_random_seeds=list(experiment.common_random_seed_set),
        )
        study = evaluate_paired_statistical_study(collections, config)
        comparisons.append(
            VecCampaignComparison(
                variation_label=arm.label,
                study_status=study.status.value,
                admitted_pair_count=study.pairing_audit.eligible_pair_count,
                mean_paired_difference=study.estimate.mean_paired_difference,
                bootstrap_lower=study.bootstrap_interval.lower,
                bootstrap_upper=study.bootstrap_interval.upper,
                randomisation_p_value=study.randomisation_test.p_value,
                study=study,
            )
        )

    primary = _descriptives(collections, design, design.primary_metric_key)
    secondaries = [
        row for key in SECONDARY_METRIC_KEYS for row in _descriptives(collections, design, key)
    ]
    return VecCampaignAnalysis(
        experiment_id=design.experiment_id,
        design_fingerprint=design.fingerprint(),
        campaign_status=receipt.status.value,
        primary_metric_key=design.primary_metric_key,
        baseline_label=design.baseline_arm.label,
        admitted_collection_count=len(collections),
        comparisons=comparisons,
        primary_descriptives=primary,
        secondary_descriptives=secondaries,
        generated_at_utc=(generated_at or datetime.now(tz=UTC)).isoformat(),
        limitations=list(STANDING_ANALYSIS_LIMITATIONS),
    )


def render_campaign_analysis_markdown(analysis: VecCampaignAnalysis) -> str:
    """Render one deterministic exploratory report."""

    lines = [
        f"# Exploratory campaign analysis — `{analysis.experiment_id}`",
        "",
        "**Status: exploratory owner-approved-candidate evidence. No confirmatory or "
        "significance claim is made by this report.**",
        "",
        f"- Method: `{analysis.method_version}`",
        f"- Design fingerprint: `{analysis.design_fingerprint}`",
        f"- Campaign status: `{analysis.campaign_status}`",
        f"- Admitted metric collections: {analysis.admitted_collection_count}",
        f"- Primary endpoint: `{analysis.primary_metric_key}` "
        f"(baseline arm `{analysis.baseline_label}`)",
        f"- Generated at: {analysis.generated_at_utc}",
        "",
        "## Predeclared comparisons (variation − baseline)",
        "",
        "| Variation | Study status | Pairs | Mean paired difference | "
        "Bootstrap interval | Randomisation p (diagnostic) |",
        "|---|---|---:|---:|---|---:|",
    ]
    for row in analysis.comparisons:
        interval = (
            f"[{row.bootstrap_lower:.6f}, {row.bootstrap_upper:.6f}]"
            if row.bootstrap_lower is not None and row.bootstrap_upper is not None
            else "unavailable"
        )
        difference = (
            f"{row.mean_paired_difference:.6f}"
            if row.mean_paired_difference is not None
            else "unavailable"
        )
        p_value = (
            f"{row.randomisation_p_value:.4f}"
            if row.randomisation_p_value is not None
            else "unavailable"
        )
        lines.append(
            f"| `{row.variation_label}` | {row.study_status} | {row.admitted_pair_count} "
            f"| {difference} | {interval} | {p_value} |"
        )
    lines += ["", "## Per-arm descriptives (primary endpoint)", ""]
    lines += _descriptive_table(analysis.primary_descriptives)
    if analysis.secondary_descriptives:
        lines += ["", "## Per-arm descriptives (secondary metrics, never promoted)", ""]
        lines += _descriptive_table(analysis.secondary_descriptives)
    lines += ["", "## Limitations", ""]
    lines += [f"- {item}" for item in analysis.limitations]
    lines.append("")
    return "\n".join(lines)


def _descriptives(
    collections: list[MetricCollection],
    design: VecCampaignDesign,
    metric_key: str,
) -> list[VecArmDescriptives]:
    rows = []
    for arm in design.arms():
        seed_values: dict[str, float] = {}
        for collection in collections:
            context = collection.results[0]
            if context.seed_id != arm.label:
                continue
            metric = collection.by_key().get(metric_key)
            if (
                metric is not None
                and metric.status is MetricStatus.AVAILABLE
                and isinstance(metric.value, int | float)
            ):
                seed_values[str(context.random_seed)] = float(metric.value)
        if seed_values:
            values = list(seed_values.values())
            rows.append(
                VecArmDescriptives(
                    arm_label=arm.label,
                    metric_key=metric_key,
                    seed_values=dict(sorted(seed_values.items())),
                    mean=sum(values) / len(values),
                    minimum=min(values),
                    maximum=max(values),
                )
            )
    return rows


def _descriptive_table(rows: list[VecArmDescriptives]) -> list[str]:
    lines = [
        "| Arm | Metric | Seeds | Mean | Min | Max |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row.arm_label}` | `{row.metric_key}` | {len(row.seed_values)} "
            f"| {row.mean:.6f} | {row.minimum:.6f} | {row.maximum:.6f} |"
        )
    return lines
