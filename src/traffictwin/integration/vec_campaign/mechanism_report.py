"""Mechanism-evidence report over one completed campaign analysis.

The explainability exhibit that sits beside the exploratory analysis: where
:func:`traffictwin.integration.vec_campaign.analysis.render_campaign_analysis_markdown`
reports *what* each arm did, this renders the per-seed evidence for *how* the
arms differ — the full seed × arm matrix, an invariance check that shows which
metrics the control never moved, and a range-comparison table for the metrics it
did move.

Everything is a re-presentation of values the analysis already recorded. This
module computes no metric, reads no registry, launches nothing, and imports no
campaign service — its only inputs are a parsed analysis model or the plain dict
of one. Its status is fixed in the type: ``descriptive_non_causal`` and
``exploratory`` are ``True``; ``confirmatory``, ``significance_claimed``, and
``causal_claim`` are ``False``.

Two distinctions the report keeps separate, because collapsing them is the easy
misreading:

* **Arm-level range overlap** compares each arm's across-seed minimum and
  maximum. Overlapping ranges are common when seeds differ a lot.
* **Per-seed ordering consistency** asks whether every individual seed ranks the
  two arms the same way. Ranges can overlap while every seed still agrees.

A mechanism claim needs the second; only reporting the first would understate
the evidence, and only reporting the second would overstate it.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field

from traffictwin.integration.vec_campaign.analysis import (
    VecArmDescriptives,
    VecCampaignAnalysis,
)
from traffictwin.integration.vec_campaign.models import VecCampaignModel

VEC_MECHANISM_REPORT_METHOD_VERSION: Literal["vec-campaign-mechanism-report-1.0"] = (
    "vec-campaign-mechanism-report-1.0"
)

STANDING_MECHANISM_LIMITATIONS = (
    "Descriptive, non-causal, exploratory re-presentation of values the campaign "
    "analysis already recorded; it establishes no mechanism, only the evidence a "
    "person reads a mechanism from.",
    "Invariance is measured as exact equality of the recorded values across arms "
    "within a seed. It shows the control did not move the metric in this grid; it "
    "does not prove the metric cannot move.",
    "Range overlap and per-seed ordering are distinct: overlapping across-seed "
    "ranges do not contradict a consistent per-seed ordering, and neither is a "
    "significance statement.",
    "Owner-approved-candidate status throughout — not supervisor approval, not "
    "validated, not causal, not generalisable beyond the studied grid.",
)


class MechanismReportError(ValueError):
    """Raised when an analysis payload cannot be re-presented as mechanism evidence."""


class MechanismSeedRow(VecCampaignModel):
    """One metric's values for one seed, across every arm that recorded it."""

    metric_key: str
    seed_id: str
    arm_values: dict[str, float]
    arms_missing_this_seed: list[str] = Field(default_factory=list)


class MechanismInvariance(VecCampaignModel):
    """Whether one metric moved across arms within one seed."""

    metric_key: str
    seed_id: str
    compared_arm_count: int = Field(ge=0)
    distinct_value_count: int = Field(ge=0)
    values_exactly_equal_across_arms: bool
    spread: float = Field(ge=0)


class MechanismMetricInvariance(VecCampaignModel):
    """Whether one metric was invariant to the control in every seed."""

    metric_key: str
    seed_count: int = Field(ge=0)
    invariant_seed_count: int = Field(ge=0)
    invariant_in_every_seed: bool
    per_seed: list[MechanismInvariance]


class MechanismRangeComparison(VecCampaignModel):
    """How one metric's two adjacent arms compare, by range and by seed."""

    metric_key: str
    lower_arm_label: str
    upper_arm_label: str
    lower_minimum: float
    lower_maximum: float
    upper_minimum: float
    upper_maximum: float
    ranges_overlap: bool
    range_gap: float | None = None
    paired_seed_count: int = Field(ge=0)
    per_seed_ordering_consistent: bool
    seeds_where_upper_exceeds_lower: int = Field(ge=0)


class CampaignMechanismReport(VecCampaignModel):
    """The complete mechanism-evidence exhibit for one completed campaign."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["vec-campaign-mechanism-report-1.0"] = (
        VEC_MECHANISM_REPORT_METHOD_VERSION
    )
    experiment_id: str
    design_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    campaign_status: str
    primary_metric_key: str
    baseline_label: str
    arm_labels: list[str]
    seed_ids: list[str]

    primary_rows: list[MechanismSeedRow]
    secondary_rows: list[MechanismSeedRow]
    invariance: list[MechanismMetricInvariance]
    range_comparisons: list[MechanismRangeComparison]
    limitations: list[str] = Field(min_length=1, max_length=16)

    # Status is fixed in the type; no caller can widen it.
    descriptive_non_causal: Literal[True] = True
    exploratory: Literal[True] = True
    confirmatory: Literal[False] = False
    significance_claimed: Literal[False] = False
    causal_claim: Literal[False] = False
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"


def build_mechanism_report(
    analysis: VecCampaignAnalysis | dict[str, Any],
) -> CampaignMechanismReport:
    """Re-present one completed campaign analysis as mechanism evidence.

    ``analysis`` may be the parsed model or the plain dict loaded from a
    committed ``campaign_analysis.json``. A dict is validated through JSON mode
    exactly as it was persisted, so the strict nested models cannot be handed a
    shape they would refuse.
    """

    parsed = _as_analysis(analysis)
    arm_labels = _arm_labels(parsed)
    seed_ids = _seed_ids(parsed)
    primary_rows = _seed_rows(parsed.primary_descriptives, arm_labels)
    secondary_rows = _seed_rows(parsed.secondary_descriptives, arm_labels)
    return CampaignMechanismReport(
        experiment_id=parsed.experiment_id,
        design_fingerprint=parsed.design_fingerprint,
        campaign_status=parsed.campaign_status,
        primary_metric_key=parsed.primary_metric_key,
        baseline_label=parsed.baseline_label,
        arm_labels=arm_labels,
        seed_ids=seed_ids,
        primary_rows=primary_rows,
        secondary_rows=secondary_rows,
        invariance=_invariance([*primary_rows, *secondary_rows]),
        range_comparisons=_range_comparisons(parsed, arm_labels),
        limitations=list(STANDING_MECHANISM_LIMITATIONS),
    )


def _as_analysis(analysis: VecCampaignAnalysis | dict[str, Any]) -> VecCampaignAnalysis:
    if isinstance(analysis, VecCampaignAnalysis):
        return analysis
    try:
        return VecCampaignAnalysis.model_validate_json(json.dumps(analysis))
    except (TypeError, ValueError) as exc:
        raise MechanismReportError(f"the payload is not a valid campaign analysis: {exc}") from exc


def _arm_labels(analysis: VecCampaignAnalysis) -> list[str]:
    """Return arm labels in the analysis's own declared order."""

    labels: list[str] = []
    for row in [*analysis.primary_descriptives, *analysis.secondary_descriptives]:
        if row.arm_label not in labels:
            labels.append(row.arm_label)
    return labels


def _seed_ids(analysis: VecCampaignAnalysis) -> list[str]:
    seeds = {
        seed
        for row in [*analysis.primary_descriptives, *analysis.secondary_descriptives]
        for seed in row.seed_values
    }
    return _sorted_seeds(seeds)


def _sorted_seeds(seeds: set[str]) -> list[str]:
    # Numeric seed labels sort numerically so seed 10 follows seed 9, not seed 1.
    if all(seed.lstrip("-").isdigit() for seed in seeds):
        return sorted(seeds, key=int)
    return sorted(seeds)


def _seed_rows(rows: list[VecArmDescriptives], arm_labels: list[str]) -> list[MechanismSeedRow]:
    by_metric: dict[str, dict[str, dict[str, float]]] = {}
    for row in rows:
        metric = by_metric.setdefault(row.metric_key, {})
        for seed, value in row.seed_values.items():
            metric.setdefault(seed, {})[row.arm_label] = value
    seed_rows: list[MechanismSeedRow] = []
    for metric_key in by_metric:
        for seed in _sorted_seeds(set(by_metric[metric_key])):
            arm_values = by_metric[metric_key][seed]
            seed_rows.append(
                MechanismSeedRow(
                    metric_key=metric_key,
                    seed_id=seed,
                    arm_values=dict(sorted(arm_values.items())),
                    arms_missing_this_seed=[
                        label for label in arm_labels if label not in arm_values
                    ],
                )
            )
    return seed_rows


def _invariance(rows: list[MechanismSeedRow]) -> list[MechanismMetricInvariance]:
    by_metric: dict[str, list[MechanismSeedRow]] = {}
    for row in rows:
        by_metric.setdefault(row.metric_key, []).append(row)
    checks: list[MechanismMetricInvariance] = []
    for metric_key, metric_rows in by_metric.items():
        per_seed = []
        for row in metric_rows:
            values = list(row.arm_values.values())
            distinct = {_exact_key(value) for value in values}
            per_seed.append(
                MechanismInvariance(
                    metric_key=metric_key,
                    seed_id=row.seed_id,
                    compared_arm_count=len(values),
                    distinct_value_count=len(distinct),
                    # One arm is not evidence of invariance across arms.
                    values_exactly_equal_across_arms=len(values) > 1 and len(distinct) == 1,
                    spread=max(values) - min(values) if values else 0.0,
                )
            )
        invariant = [item for item in per_seed if item.values_exactly_equal_across_arms]
        checks.append(
            MechanismMetricInvariance(
                metric_key=metric_key,
                seed_count=len(per_seed),
                invariant_seed_count=len(invariant),
                invariant_in_every_seed=bool(per_seed) and len(invariant) == len(per_seed),
                per_seed=per_seed,
            )
        )
    return checks


def _exact_key(value: float) -> str:
    """Return a key that distinguishes values the recorded bytes distinguish."""

    return repr(float(value))


def _range_comparisons(
    analysis: VecCampaignAnalysis, arm_labels: list[str]
) -> list[MechanismRangeComparison]:
    by_metric: dict[str, dict[str, VecArmDescriptives]] = {}
    for row in [*analysis.primary_descriptives, *analysis.secondary_descriptives]:
        by_metric.setdefault(row.metric_key, {})[row.arm_label] = row
    comparisons: list[MechanismRangeComparison] = []
    for metric_key, arms in by_metric.items():
        ordered = [label for label in arm_labels if label in arms]
        for lower_label, upper_label in zip(ordered, ordered[1:], strict=False):
            comparisons.append(_compare(metric_key, arms[lower_label], arms[upper_label]))
    return comparisons


def _compare(
    metric_key: str,
    lower: VecArmDescriptives,
    upper: VecArmDescriptives,
) -> MechanismRangeComparison:
    overlap = not (lower.maximum < upper.minimum or upper.maximum < lower.minimum)
    gap = (
        None
        if overlap
        else (
            upper.minimum - lower.maximum
            if upper.minimum > lower.maximum
            else lower.minimum - upper.maximum
        )
    )
    shared = sorted(set(lower.seed_values) & set(upper.seed_values))
    exceeds = sum(1 for seed in shared if upper.seed_values[seed] > lower.seed_values[seed])
    return MechanismRangeComparison(
        metric_key=metric_key,
        lower_arm_label=lower.arm_label,
        upper_arm_label=upper.arm_label,
        lower_minimum=lower.minimum,
        lower_maximum=lower.maximum,
        upper_minimum=upper.minimum,
        upper_maximum=upper.maximum,
        ranges_overlap=overlap,
        range_gap=gap,
        paired_seed_count=len(shared),
        # Consistent means every shared seed ranks the pair the same way.
        per_seed_ordering_consistent=bool(shared) and exceeds in {0, len(shared)},
        seeds_where_upper_exceeds_lower=exceeds,
    )


def render_mechanism_report_markdown(report: CampaignMechanismReport) -> str:
    """Render the deterministic mechanism-evidence markdown."""

    lines = [
        f"# Mechanism evidence — `{report.experiment_id}`",
        "",
        "**Status: descriptive, non-causal, exploratory owner-approved-candidate "
        "evidence.** This report re-presents values the campaign analysis already "
        "recorded. It makes no confirmatory claim, no significance claim, and no "
        "causal claim.",
        "",
        f"- Method: `{report.method_version}` (schema {report.schema_version})",
        f"- Design fingerprint: `{report.design_fingerprint}`",
        f"- Campaign status: `{report.campaign_status}`",
        f"- Primary endpoint: `{report.primary_metric_key}` "
        f"(baseline arm `{report.baseline_label}`)",
        f"- Arms: {', '.join(f'`{label}`' for label in report.arm_labels)}",
        f"- Seeds: {', '.join(report.seed_ids)}",
        "",
        "## Per-seed values, primary endpoint",
        "",
        *_seed_table(report.primary_rows, report.arm_labels),
    ]
    if report.secondary_rows:
        lines += [
            "",
            "## Per-seed values, secondary metrics (never promoted)",
            "",
            *_seed_table(report.secondary_rows, report.arm_labels),
        ]
    lines += ["", "## Invariance to the control", "", *_invariance_section(report)]
    lines += ["", "## Adjacent-arm range comparison", "", *_range_section(report)]
    lines += ["", "## Limitations", ""]
    lines += [f"- {item}" for item in report.limitations]
    lines.append("")
    return "\n".join(lines)


def _seed_table(rows: list[MechanismSeedRow], arm_labels: list[str]) -> list[str]:
    if not rows:
        return ["No per-seed values are recorded."]
    header = "| Metric | Seed | " + " | ".join(f"`{label}`" for label in arm_labels) + " |"
    divider = "|---|---:|" + "---:|" * len(arm_labels)
    lines = [header, divider]
    for row in rows:
        cells = [
            f"{row.arm_values[label]:.6f}" if label in row.arm_values else "unavailable"
            for label in arm_labels
        ]
        lines.append(f"| `{row.metric_key}` | {row.seed_id} | " + " | ".join(cells) + " |")
    return lines


def _invariance_section(report: CampaignMechanismReport) -> list[str]:
    if not report.invariance:
        return ["No metric had values to compare across arms."]
    lines = [
        "A metric is invariant in a seed when every arm recorded exactly the same "
        "value — the control moved the arms, and the metric did not follow.",
        "",
        "| Metric | Seeds | Invariant seeds | Invariant in every seed | Max spread |",
        "|---|---:|---:|:---:|---:|",
    ]
    for check in report.invariance:
        spread = max((item.spread for item in check.per_seed), default=0.0)
        mark = "**yes**" if check.invariant_in_every_seed else "no"
        lines.append(
            f"| `{check.metric_key}` | {check.seed_count} | {check.invariant_seed_count} "
            f"| {mark} | {spread:.6f} |"
        )
    invariant = [check.metric_key for check in report.invariance if check.invariant_in_every_seed]
    if invariant:
        lines += [
            "",
            "Bit-identical across every arm within every seed: "
            + ", ".join(f"`{key}`" for key in invariant)
            + ". In this grid the control did not move these metrics at all.",
        ]
    return lines


def _range_section(report: CampaignMechanismReport) -> list[str]:
    if not report.range_comparisons:
        return ["No adjacent arm pair had values to compare."]
    lines = [
        "Range overlap compares each arm's across-seed minimum and maximum. "
        "Per-seed ordering asks whether every shared seed ranks the pair the same "
        "way. The two answer different questions and can differ.",
        "",
        "| Metric | Lower arm | Upper arm | Lower range | Upper range | Ranges overlap "
        "| Pairs | Ordering consistent |",
        "|---|---|---|---|---|:---:|---:|:---:|",
    ]
    for row in report.range_comparisons:
        lines.append(
            f"| `{row.metric_key}` | `{row.lower_arm_label}` | `{row.upper_arm_label}` "
            f"| [{row.lower_minimum:.6f}, {row.lower_maximum:.6f}] "
            f"| [{row.upper_minimum:.6f}, {row.upper_maximum:.6f}] "
            f"| {'yes' if row.ranges_overlap else 'no'} | {row.paired_seed_count} "
            f"| {'yes' if row.per_seed_ordering_consistent else 'no'} |"
        )
    return lines
