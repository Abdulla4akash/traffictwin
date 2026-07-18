"""Deterministic analysis over the documented TOS evaluation master."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.integration.tos.analysis_models import (
    TosAggregateCell,
    TosAnalysisMeasureDefinition,
    TosCampaignComparisonReport,
    TosDescriptiveStatistics,
    TosEvaluationDomain,
    TosEvaluationMatrix,
    TosGeneralisationEntry,
    TosGeneralisationMatrix,
    TosPairedMeasureComparison,
    TosPairedObservation,
)
from traffictwin.integration.tos.models import TosEvaluationRun
from traffictwin.integration.tos.readers import package_fingerprint, safe_package_path
from traffictwin.metrics.statistics import (
    arithmetic_mean,
    percentile_linear,
    sample_standard_deviation,
)

Clock = Callable[[], datetime]

CELL_ORDER = ("wd_am", "wd_pm", "we", "ev", "inc")

_MEASURES = (
    TosAnalysisMeasureDefinition(
        key="tos.task.deadline_success.rate",
        human_name="Deadline success rate",
        description="Share of source-modelled task arrivals whose latency met the class deadline.",
        unit="fraction",
        source_fields=["completion"],
        higher_is_better=True,
        limitations=[
            "This is deadline success, not evidence that a late task eventually completed.",
        ],
    ),
    TosAnalysisMeasureDefinition(
        key="tos.task.deadline_success.t1_rate",
        human_name="T1 deadline success rate",
        description="Deadline-success share for source task type T1.",
        unit="fraction",
        source_fields=["t1_completion"],
        higher_is_better=True,
    ),
    TosAnalysisMeasureDefinition(
        key="tos.task.deadline_success.t2_rate",
        human_name="T2 deadline success rate",
        description="Deadline-success share for source task type T2.",
        unit="fraction",
        source_fields=["t2_completion"],
        higher_is_better=True,
    ),
    TosAnalysisMeasureDefinition(
        key="tos.task.deadline_success.t3_rate",
        human_name="T3 deadline success rate",
        description="Deadline-success share for source task type T3.",
        unit="fraction",
        source_fields=["t3_completion"],
        higher_is_better=True,
    ),
    TosAnalysisMeasureDefinition(
        key="tos.task.latency.mean_all_arrivals_ms",
        human_name="Mean modelled latency",
        description="Source mean latency over all arrivals, including deadline-missing backlog.",
        unit="ms",
        source_fields=["avg_latency_ms_per_task"],
        higher_is_better=False,
        limitations=[
            "Incident-cell values can be dominated by modelled backlog carried by misses.",
        ],
    ),
    TosAnalysisMeasureDefinition(
        key="tos.task.energy.mean_per_arrival_j",
        human_name="Mean modelled energy per arrival",
        description="Source mean energy value per task arrival.",
        unit="J/task",
        source_fields=["avg_energy_j_per_task"],
        higher_is_better=False,
        limitations=["This is a source-model output, not a physical power measurement."],
    ),
    TosAnalysisMeasureDefinition(
        key="tos.decision.share.local",
        human_name="Local decision share",
        description="Share of task decisions assigned to local execution.",
        unit="fraction",
        source_fields=["p_local"],
    ),
    TosAnalysisMeasureDefinition(
        key="tos.decision.share.v2i",
        human_name="V2I decision share",
        description="Share of task decisions assigned to vehicle-to-infrastructure offloading.",
        unit="fraction",
        source_fields=["p_v2i"],
    ),
    TosAnalysisMeasureDefinition(
        key="tos.decision.share.v2v",
        human_name="V2V decision share",
        description="Share of task decisions assigned to vehicle-to-vehicle offloading.",
        unit="fraction",
        source_fields=["p_v2v"],
    ),
    TosAnalysisMeasureDefinition(
        key="tos.decision.offload_share",
        human_name="Offload decision share",
        description="V2I plus V2V decision share from the evaluation summary.",
        unit="fraction",
        source_fields=["p_v2i", "p_v2v"],
    ),
)


def tos_analysis_catalogue() -> tuple[TosAnalysisMeasureDefinition, ...]:
    """Return the stable source-analysis measure catalogue."""

    return _MEASURES


def measure_definition(key: str) -> TosAnalysisMeasureDefinition:
    """Resolve one source-analysis measure."""

    for definition in _MEASURES:
        if definition.key == key:
            return definition
    raise ValueError(f"unknown TOS analysis measure: {key}")


def evaluation_value(run: TosEvaluationRun, measure_key: str) -> float:
    """Return one source value without reinterpreting the source formula."""

    values = {
        "tos.task.deadline_success.rate": run.completion,
        "tos.task.deadline_success.t1_rate": run.t1_completion,
        "tos.task.deadline_success.t2_rate": run.t2_completion,
        "tos.task.deadline_success.t3_rate": run.t3_completion,
        "tos.task.latency.mean_all_arrivals_ms": run.avg_latency_ms_per_task,
        "tos.task.energy.mean_per_arrival_j": run.avg_energy_j_per_task,
        "tos.decision.share.local": run.p_local,
        "tos.decision.share.v2i": run.p_v2i,
        "tos.decision.share.v2v": run.p_v2v,
        "tos.decision.offload_share": run.p_v2i + run.p_v2v,
    }
    try:
        return values[measure_key]
    except KeyError as exc:
        raise ValueError(f"unknown TOS analysis measure: {measure_key}") from exc


def descriptive_statistics(values: Sequence[float]) -> TosDescriptiveStatistics:
    """Build deterministic descriptive statistics with explicit small-n behavior."""

    return TosDescriptiveStatistics(
        n=len(values),
        mean=arithmetic_mean(values),
        sample_sd=sample_standard_deviation(values),
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        p50=percentile_linear(values, 0.5),
    )


def build_evaluation_matrix(
    rows: Sequence[TosEvaluationRun],
    root: str | Path,
    *,
    measure_key: str = "tos.task.deadline_success.rate",
    evaluation_fleet: str = "uk2030",
    clock: Clock | None = None,
) -> TosEvaluationMatrix:
    """Aggregate source rows by campaign, scenario cell, and fleet seed."""

    definition = measure_definition(measure_key)
    selected = [run for run in rows if run.eval_fleet == evaluation_fleet]
    grouped: dict[tuple[str, str], list[TosEvaluationRun]] = defaultdict(list)
    for run in selected:
        grouped[(run.campaign, run.cell)].append(run)
    entries: list[TosAggregateCell] = []
    for (campaign, cell), group in sorted(
        grouped.items(),
        key=lambda item: (_campaign_sort_key(item[0][0]), _cell_sort_key(item[0][1])),
    ):
        ordered = sorted(group, key=lambda run: run.fleet_seed)
        by_seed = {run.fleet_seed: evaluation_value(run, measure_key) for run in ordered}
        entries.append(
            TosAggregateCell(
                campaign=campaign,
                cell=cell,
                evaluation_fleet=evaluation_fleet,
                measure_key=measure_key,
                values_by_fleet_seed=by_seed,
                statistics=descriptive_statistics(list(by_seed.values())),
                source_rows=[run.source_row for run in ordered],
                engine_versions=sorted({run.engine_version for run in ordered}),
            )
        )
    campaigns = sorted({run.campaign for run in selected}, key=_campaign_sort_key)
    cells = sorted({run.cell for run in selected}, key=_cell_sort_key)
    return TosEvaluationMatrix(
        measure=definition,
        evaluation_fleet=evaluation_fleet,
        campaigns=campaigns,
        cells=cells,
        entries=entries,
        package_fingerprint=package_fingerprint(root),
        generated_at=(clock or _utc_now)(),
        warnings=[
            "Values are imported simulation results and are not real-world validation.",
            "Statistics describe fleet-seed replicates; they are not confidence intervals.",
        ],
    )


def compare_campaigns(
    rows: Sequence[TosEvaluationRun],
    root: str | Path,
    baseline_campaign: str,
    variation_campaign: str,
    *,
    evaluation_fleet: str = "uk2030",
    measure_keys: Iterable[str] | None = None,
    clock: Clock | None = None,
) -> TosCampaignComparisonReport:
    """Compare campaigns by common source cell and fleet seed."""

    keys = list(measure_keys or ("tos.task.deadline_success.rate",))
    for key in keys:
        measure_definition(key)
    baseline_rows = [
        run
        for run in rows
        if run.campaign == baseline_campaign and run.eval_fleet == evaluation_fleet
    ]
    variation_rows = [
        run
        for run in rows
        if run.campaign == variation_campaign and run.eval_fleet == evaluation_fleet
    ]
    if not baseline_rows:
        raise ValueError(f"no rows for baseline campaign {baseline_campaign!r}")
    if not variation_rows:
        raise ValueError(f"no rows for variation campaign {variation_campaign!r}")
    comparisons: list[TosPairedMeasureComparison] = []
    shared_cells = sorted(
        {run.cell for run in baseline_rows} & {run.cell for run in variation_rows},
        key=_cell_sort_key,
    )
    for key in keys:
        definition = measure_definition(key)
        for cell in shared_cells:
            baseline = {run.fleet_seed: run for run in baseline_rows if run.cell == cell}
            variation = {run.fleet_seed: run for run in variation_rows if run.cell == cell}
            common = sorted(set(baseline) & set(variation))
            observations: list[TosPairedObservation] = []
            compatibility: set[str] = set()
            for seed in common:
                base_run = baseline[seed]
                varied_run = variation[seed]
                compatibility.update(_compatibility_findings(base_run, varied_run))
                base_value = evaluation_value(base_run, key)
                varied_value = evaluation_value(varied_run, key)
                delta = varied_value - base_value
                relative: float | None
                reason: str | None = None
                if base_value == 0:
                    relative = 0.0 if varied_value == 0 else None
                    reason = None if varied_value == 0 else "BASELINE_ZERO"
                else:
                    relative = delta / abs(base_value)
                observations.append(
                    TosPairedObservation(
                        fleet_seed=seed,
                        baseline=base_value,
                        variation=varied_value,
                        absolute_delta=delta,
                        relative_delta=relative,
                        relative_delta_reason=reason,
                        baseline_source_row=base_run.source_row,
                        variation_source_row=varied_run.source_row,
                    )
                )
            comparisons.append(
                TosPairedMeasureComparison(
                    measure=definition,
                    cell=cell,
                    evaluation_fleet=evaluation_fleet,
                    baseline_campaign=baseline_campaign,
                    variation_campaign=variation_campaign,
                    baseline_statistics=descriptive_statistics(
                        [observation.baseline for observation in observations]
                    ),
                    variation_statistics=descriptive_statistics(
                        [observation.variation for observation in observations]
                    ),
                    paired_difference_statistics=descriptive_statistics(
                        [observation.absolute_delta for observation in observations]
                    ),
                    observations=observations,
                    unmatched_baseline_fleet_seeds=sorted(set(baseline) - set(variation)),
                    unmatched_variation_fleet_seeds=sorted(set(variation) - set(baseline)),
                    compatibility_findings=sorted(compatibility),
                )
            )
    return TosCampaignComparisonReport(
        baseline_campaign=baseline_campaign,
        variation_campaign=variation_campaign,
        evaluation_fleet=evaluation_fleet,
        comparisons=comparisons,
        package_fingerprint=package_fingerprint(root),
        generated_at=(clock or _utc_now)(),
        warnings=[
            "Deltas are variation minus baseline and do not establish causal effects.",
            "One campaign comparison is not a definitive algorithm conclusion.",
        ],
    )


def build_generalisation_matrix(
    rows: Sequence[TosEvaluationRun], root: str | Path
) -> TosGeneralisationMatrix:
    """Classify source cells only where package documents the training relationship."""

    dictionary = safe_package_path(root, "DATA_DICTIONARY.md")
    entries: list[TosGeneralisationEntry] = []
    campaigns = sorted({run.campaign for run in rows}, key=_campaign_sort_key)
    cells = sorted({run.cell for run in rows}, key=_cell_sort_key)
    for campaign in campaigns:
        for cell in cells:
            domain, evidence, source, limitations = _domain_classification(campaign, cell)
            entries.append(
                TosGeneralisationEntry(
                    campaign=campaign,
                    cell=cell,
                    evaluation_domain=domain,
                    evidence_file=source if safe_package_path(root, source).exists() else None,
                    evidence_statement=evidence,
                    limitations=limitations,
                )
            )
    return TosGeneralisationMatrix(
        entries=entries,
        warnings=[
            "Unknown means the inspected package does not establish the relationship.",
            "Domain labels describe data provenance, not performance quality.",
            f"Primary package evidence: {dictionary.relative_to(Path(root).resolve()).as_posix()}",
        ],
    )


def _domain_classification(
    campaign: str, cell: str
) -> tuple[TosEvaluationDomain, str, str, list[str]]:
    if campaign.startswith("fcdtrain_manwe"):
        if cell == "we":
            return (
                TosEvaluationDomain.IN_DOMAIN,
                "The package dictionary identifies the weekend cell as the FCD-training trace.",
                "DATA_DICTIONARY.md",
                ["The label does not imply external validation."],
            )
        return (
            TosEvaluationDomain.HELD_OUT,
            "The package dictionary labels non-weekend cells as held out for fcdtrain.",
            "DATA_DICTIONARY.md",
            ["The incident cell is also described as a held-out regime."],
        )
    record_prefixes = {
        "ukfleettrain_ippo": "records/TRAINING_ukfleettrain_ippo.md",
        "ukfleettrain_mappo": "records/TRAINING_ukfleettrain_mappo.md",
        "capscalar_ippo": "records/TRAINING_capscalar_ippo.md",
        "capscalar_mappo": "records/TRAINING_capscalar_mappo.md",
    }
    if campaign in record_prefixes:
        return (
            TosEvaluationDomain.HELD_OUT,
            (
                "The training record states that Manchester evaluation mobility is held out "
                "by construction."
            ),
            record_prefixes[campaign],
            ["Held-out mobility does not by itself establish broader generalisation."],
        )
    if campaign.startswith("gridlocktrain") and cell == "inc":
        suffix = "ippo" if campaign.endswith("ippo") else "mappo"
        prefix = "gridlocktrain_ft" if "_ft_" in campaign else "gridlocktrain"
        return (
            TosEvaluationDomain.HELD_OUT,
            "The training record explicitly states that the incident evaluation was held out.",
            f"records/TRAINING_{prefix}_{suffix}.md",
            ["Other evaluation-cell relationships are left unknown."],
        )
    return (
        TosEvaluationDomain.UNKNOWN,
        "The inspected package does not explicitly classify this campaign/cell relationship.",
        "DATA_DICTIONARY.md",
        ["No in-domain or held-out label is inferred from the campaign name alone."],
    )


def _compatibility_findings(baseline: TosEvaluationRun, variation: TosEvaluationRun) -> list[str]:
    findings: list[str] = []
    checks = (
        ("engine_version", baseline.engine_version, variation.engine_version),
        ("obs_variant", baseline.obs_variant, variation.obs_variant),
        ("trace", baseline.trace, variation.trace),
        ("duration_s", baseline.duration_s, variation.duration_s),
        ("max_vehicle_slots", baseline.max_vehicle_slots, variation.max_vehicle_slots),
    )
    for name, base_value, varied_value in checks:
        if base_value != varied_value:
            findings.append(f"{name} differs: {base_value!s} vs {varied_value!s}")
    return findings


def _cell_sort_key(cell: str) -> tuple[int, str]:
    try:
        return CELL_ORDER.index(cell), cell
    except ValueError:
        return len(CELL_ORDER), cell


def _campaign_sort_key(campaign: str) -> tuple[int, str]:
    return (0 if campaign == "baseline" else 1, campaign)


def _utc_now() -> datetime:
    return datetime.now(UTC)
