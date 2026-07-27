"""Render the capacity study's dissertation figures through the accepted REP-01 machinery.

Four table/figure pairs, each published as a LaTeX fragment and a self-contained
SVG by :mod:`traffictwin.reporting.latex`:

* **Mean task latency** for every fleet seed at every capacity arm — the metric
  the control actually moved.
* **Deadline-success rate** on the same seed x arm structure, rendered on the
  accepted zero-anchored scale so the flat ~0.79 band is shown at true size
  rather than magnified into an apparent effect.
* **Paired deadline-success differences**, copied verbatim from the STA-01
  studies the analysis already recorded, as the companion that resolves the band
  the zero-anchored chart deliberately leaves small.
* **Invariance across arms**, from the accepted mechanism report's own exact
  equality check, showing which metrics the capacity control never moved.

**Nothing here computes science.** Every rendered value is read from a completed
`campaign_analysis.json` or from
:func:`traffictwin.integration.vec_campaign.mechanism_report.build_mechanism_report`,
and the drawing is done entirely by the accepted exporter. This script chooses
which recorded values to project and where to write them; it derives no metric,
no difference, and no summary of its own.

**The input path is a required argument with no default.** The script never
searches for a campaign directory, so it cannot wander into one that is
executing.

**Two properties of the accepted renderer, recorded rather than worked around.**
Its numeric figures are horizontal bar series on a shared signed linear scale,
not polylines, so a per-seed "curve" is rendered as an ordered contiguous run of
bars — one run per seed, four capacity points each — and the exact values live
in the companion table. Its scale is zero-anchored by construction, so there is
no zoom to state: the zero-anchored chart is what the machinery produces, and
the recorded paired differences are published beside it as the readable
companion.

Deterministic by construction: no timestamps and no environment paths reach any
output, so regeneration on unchanged input rewrites identical bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from traffictwin.integration.vec_campaign.analysis import VecCampaignAnalysis
from traffictwin.integration.vec_campaign.mechanism_report import (
    CampaignMechanismReport,
    MechanismSeedRow,
    build_mechanism_report,
)
from traffictwin.reporting.latex import (
    MAX_CELL_CHARACTERS,
    MAX_TABLE_COLUMNS,
    ResearchExportKind,
    ResearchExportProjection,
    ResearchExportReceipt,
    ResearchFigureEntry,
    write_projection_exports,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "dissertation_appendices" / "figures"
PROVENANCE_NAME = "provenance.md"

#: The two renderers draw different fields — the SVG draws the title and the
#: source line, the LaTeX fragment draws the caption — so the status labels are
#: carried in the source id *and* the caption to reach both. They are measured
#: onto the source line rather than the title because the title is set at 24px
#: against a 1000px canvas, where this string alone would overflow and clip.
RESEARCH_LABELS = "exploratory, owner_approved_candidate, descriptive non-causal"

#: The accepted SVG canvas, less the 40px left inset and a matching right margin.
FIGURE_TEXT_BUDGET_PX = 920

DEFAULT_LATENCY_METRIC = "task.latency.mean_ms"
MAX_ANALYSIS_BYTES = 64 * 1024 * 1024

LATENCY_SLUG = "capacity_latency_by_seed"
DEADLINE_SLUG = "capacity_deadline_success_by_seed"
DIFFERENCES_SLUG = "capacity_deadline_success_paired_differences"
INVARIANCE_SLUG = "capacity_offload_invariance"

IDENTICAL = "identical_across_arms"
VARIES = "varies_across_arms"

UNAVAILABLE = "unavailable"


class CapacityFigureError(RuntimeError):
    """Raised when an analysis payload cannot be rendered as capacity figures."""


@dataclass(frozen=True)
class GeneratedFigure:
    """One published table/figure pair and the projection identity behind it."""

    slug: str
    projection: ResearchExportProjection
    receipt: ResearchExportReceipt


def main(argv: list[str] | None = None) -> int:
    """Render every capacity figure and report where the files landed."""

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "analysis_json",
        type=Path,
        help="Path to a completed campaign_analysis.json. Required; there is no default.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory the .tex/.svg pairs and the provenance note are written to.",
    )
    parser.add_argument(
        "--latency-metric",
        default=DEFAULT_LATENCY_METRIC,
        help="Secondary metric key rendered as the latency-versus-capacity figure.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing outputs; required when regenerating committed figures.",
    )
    arguments = parser.parse_args(argv)
    try:
        figures = generate_capacity_figures(
            arguments.analysis_json,
            arguments.output_dir,
            latency_metric=arguments.latency_metric,
            overwrite=arguments.overwrite,
        )
    except CapacityFigureError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except FileExistsError as error:
        print(
            f"error: {Path(str(error)).name} already exists; pass --overwrite to replace it",
            file=sys.stderr,
        )
        return 1
    for figure in figures:
        names = ", ".join(item.name for item in figure.receipt.files)
        print(f"{figure.slug}: {names}")
    print(f"{PROVENANCE_NAME}: written")
    return 0


def generate_capacity_figures(
    analysis_path: Path,
    output_dir: Path,
    *,
    latency_metric: str = DEFAULT_LATENCY_METRIC,
    overwrite: bool = False,
) -> list[GeneratedFigure]:
    """Publish every capacity figure and its provenance note into ``output_dir``."""

    analysis, source_digest = _load_analysis(analysis_path)
    report = build_mechanism_report(analysis)
    source_id = _source_id(analysis)
    synthetic = _synthetic_mode(analysis)

    projections = [
        (
            LATENCY_SLUG,
            _latency_projection(analysis, report, latency_metric, source_id, synthetic),
        ),
        (
            DEADLINE_SLUG,
            _deadline_projection(analysis, report, source_id, synthetic),
        ),
        (
            DIFFERENCES_SLUG,
            _differences_projection(analysis, source_id, synthetic),
        ),
        (
            INVARIANCE_SLUG,
            _invariance_projection(analysis, report, source_id, synthetic),
        ),
    ]
    figures: list[GeneratedFigure] = []
    for slug, projection in projections:
        receipt = write_projection_exports(
            projection,
            output_dir / f"{slug}.tex",
            figure_path=output_dir / f"{slug}.svg",
            overwrite=overwrite,
        )
        figures.append(GeneratedFigure(slug=slug, projection=projection, receipt=receipt))
    _write_provenance(
        output_dir / PROVENANCE_NAME,
        analysis=analysis,
        report=report,
        source_name=analysis_path.name,
        source_digest=source_digest,
        figures=figures,
        latency_metric=latency_metric,
        overwrite=overwrite,
    )
    return figures


def _load_analysis(path: Path) -> tuple[VecCampaignAnalysis, str]:
    """Read and validate one completed analysis, returning it with its byte identity."""

    if not path.is_file():
        raise CapacityFigureError(f"analysis JSON not found: {path}")
    payload = path.read_bytes()
    if len(payload) > MAX_ANALYSIS_BYTES:
        raise CapacityFigureError(f"analysis JSON exceeds {MAX_ANALYSIS_BYTES} bytes: {path}")
    digest = hashlib.sha256(payload).hexdigest()
    try:
        analysis = VecCampaignAnalysis.model_validate_json(payload)
    except ValueError as error:
        raise CapacityFigureError(f"not a valid campaign analysis: {error}") from error
    return analysis, digest


def _source_id(analysis: VecCampaignAnalysis) -> str:
    """Return the SVG's source line: design identity plus the status labels.

    Fixed width by construction — a 16-character fingerprint prefix and a
    constant label string — so the rendered line cannot grow past the canvas for
    some other analysis with a longer experiment id. The experiment id itself
    rides in the caption and the provenance note.
    """

    return f"{analysis.design_fingerprint[:16]} ({RESEARCH_LABELS})"


def _caption(description: str, analysis: VecCampaignAnalysis) -> str:
    """Return the LaTeX caption: status labels, the description, and the source study.

    The experiment-id clause is appended only when the whole caption stays inside
    the accepted 160-character bound, so a long experiment id degrades to a
    shorter caption rather than a validation failure. Identity survives either
    way: the fragment always carries its projection fingerprint, and the
    provenance note maps that fingerprint back to the source file.
    """

    stem = f"{RESEARCH_LABELS.capitalize()}. {description}"
    attributed = f"{stem}, {analysis.experiment_id}."
    return attributed if len(attributed) <= MAX_CELL_CHARACTERS else f"{stem}."


def _synthetic_mode(analysis: VecCampaignAnalysis) -> bool | None:
    """Return the recorded source mode, or ``None`` when the studies disagree."""

    modes = {comparison.study.synthetic for comparison in analysis.comparisons}
    return next(iter(modes)) if len(modes) == 1 else None


def _latency_projection(
    analysis: VecCampaignAnalysis,
    report: CampaignMechanismReport,
    latency_metric: str,
    source_id: str,
    synthetic: bool | None,
) -> ResearchExportProjection:
    rows = _metric_rows(report.secondary_rows, latency_metric, report.seed_ids)
    if not rows:
        raise CapacityFigureError(
            f"the analysis records no secondary metric {latency_metric!r}; "
            "pass --latency-metric with a key the analysis actually carries"
        )
    columns, table_rows = _seed_matrix(rows, report.arm_labels)
    return ResearchExportProjection(
        kind=ResearchExportKind.METRICS,
        source_id=source_id,
        title="Capacity pilot mean task latency by fleet seed and capacity arm",
        caption=_caption("Mean task latency per seed at each capacity arm", analysis),
        columns=columns,
        rows=table_rows,
        figure_entries=_numeric_entries(rows, report.arm_labels),
        synthetic=synthetic,
        warnings=[],
    )


def _deadline_projection(
    analysis: VecCampaignAnalysis,
    report: CampaignMechanismReport,
    source_id: str,
    synthetic: bool | None,
) -> ResearchExportProjection:
    rows = _metric_rows(report.primary_rows, report.primary_metric_key, report.seed_ids)
    if not rows:
        raise CapacityFigureError(
            f"the analysis records no primary metric {report.primary_metric_key!r}"
        )
    columns, table_rows = _seed_matrix(rows, report.arm_labels)
    return ResearchExportProjection(
        kind=ResearchExportKind.METRICS,
        source_id=source_id,
        title="Capacity pilot deadline-success rate by fleet seed and capacity arm",
        caption=_caption(
            "Deadline-success rate per seed at each capacity arm, zero-anchored",
            analysis,
        ),
        columns=columns,
        rows=table_rows,
        figure_entries=_numeric_entries(rows, report.arm_labels),
        synthetic=synthetic,
        warnings=[
            "Zero-anchored scale; the band is narrow at true size, see the "
            "paired-differences companion",
        ],
    )


def _differences_projection(
    analysis: VecCampaignAnalysis,
    source_id: str,
    synthetic: bool | None,
) -> ResearchExportProjection:
    """Project the paired differences the analysis already recorded, unchanged."""

    table_rows = [
        [
            _text(f"{comparison.variation_label} vs {analysis.baseline_label}"),
            _text(comparison.study_status),
            str(comparison.admitted_pair_count),
            _number(comparison.mean_paired_difference),
            _interval(comparison.bootstrap_lower, comparison.bootstrap_upper),
            _number(comparison.randomisation_p_value),
        ]
        for comparison in analysis.comparisons
    ]
    entries = [
        ResearchFigureEntry(
            label=_text(f"{comparison.variation_label} vs {analysis.baseline_label}"),
            numeric_value=comparison.mean_paired_difference,
        )
        for comparison in analysis.comparisons
        if comparison.mean_paired_difference is not None
    ]
    warnings = []
    if len(entries) != len(analysis.comparisons):
        warnings.append("Comparisons without a recorded paired difference are omitted")
    return ResearchExportProjection(
        kind=ResearchExportKind.STATISTICAL_STUDY,
        source_id=source_id,
        title="Capacity pilot recorded paired deadline-success differences",
        caption=_caption(
            f"Paired {analysis.primary_metric_key} differences recorded by the analysis",
            analysis,
        ),
        columns=[
            "Contrast",
            "Study status",
            "Pairs",
            "Mean paired difference",
            "Bootstrap interval",
            "Randomisation p",
        ],
        rows=table_rows,
        figure_entries=entries,
        synthetic=synthetic,
        warnings=warnings,
    )


def _invariance_projection(
    analysis: VecCampaignAnalysis,
    report: CampaignMechanismReport,
    source_id: str,
    synthetic: bool | None,
) -> ResearchExportProjection:
    """Project the accepted mechanism report's own exact-equality check."""

    wide = 2 + len(report.arm_labels) + 1 <= MAX_TABLE_COLUMNS
    value_lookup = {
        (row.metric_key, row.seed_id): row.arm_values
        for row in [*report.primary_rows, *report.secondary_rows]
    }
    if wide:
        columns = ["Metric", "Seed", *report.arm_labels, "Identical across arms"]
    else:
        columns = ["Metric", "Seed", "Distinct values", "Spread", "Identical across arms"]
    table_rows: list[list[str]] = []
    entries: list[ResearchFigureEntry] = []
    for metric in report.invariance:
        for seed in metric.per_seed:
            identical = seed.values_exactly_equal_across_arms
            if wide:
                arm_values = value_lookup.get((metric.metric_key, seed.seed_id), {})
                cells = [_number(arm_values.get(arm)) for arm in report.arm_labels]
            else:
                cells = [str(seed.distinct_value_count), _number(seed.spread)]
            table_rows.append(
                [
                    _text(metric.metric_key),
                    _text(seed.seed_id),
                    *cells,
                    "yes" if identical else "no",
                ]
            )
            entries.append(
                ResearchFigureEntry(
                    label=_text(f"{metric.metric_key} seed {seed.seed_id}"),
                    category=IDENTICAL if identical else VARIES,
                )
            )
    return ResearchExportProjection(
        kind=ResearchExportKind.METRICS,
        source_id=source_id,
        title="Capacity pilot metric invariance across capacity arms",
        caption=_caption(
            "Exact equality of each metric's values across arms, within each seed",
            analysis,
        ),
        columns=columns,
        rows=table_rows,
        figure_entries=entries,
        synthetic=synthetic,
        warnings=[
            "Equality is exact on the recorded values, never a rounded display",
        ],
    )


def _metric_rows(
    rows: list[MechanismSeedRow],
    metric_key: str,
    seed_ids: list[str],
) -> list[MechanismSeedRow]:
    """Return one metric's seed rows in the report's own seed order."""

    selected = {row.seed_id: row for row in rows if row.metric_key == metric_key}
    return [selected[seed] for seed in seed_ids if seed in selected]


def _seed_matrix(
    rows: list[MechanismSeedRow],
    arm_labels: list[str],
) -> tuple[list[str], list[list[str]]]:
    """Render seed x arm values wide when the column budget allows, long otherwise."""

    if len(arm_labels) + 1 <= MAX_TABLE_COLUMNS:
        columns = ["Fleet seed", *arm_labels]
        table = [
            [_text(row.seed_id), *[_number(row.arm_values.get(arm)) for arm in arm_labels]]
            for row in rows
        ]
        return columns, table
    columns = ["Fleet seed", "Capacity arm", "Value"]
    table = [
        [_text(row.seed_id), _text(arm), _number(row.arm_values.get(arm))]
        for row in rows
        for arm in arm_labels
    ]
    return columns, table


def _numeric_entries(
    rows: list[MechanismSeedRow],
    arm_labels: list[str],
) -> list[ResearchFigureEntry]:
    """One bar per seed x arm, seed-major so each seed's arms read as one run."""

    return [
        ResearchFigureEntry(
            label=_text(f"seed {row.seed_id} at {arm}"),
            numeric_value=row.arm_values[arm],
        )
        for row in rows
        for arm in arm_labels
        if arm in row.arm_values
    ]


def _number(value: float | None) -> str:
    """Render a recorded value at full round-trip precision, never rounded to look equal."""

    return UNAVAILABLE if value is None else repr(float(value))


def _interval(lower: float | None, upper: float | None) -> str:
    if lower is None or upper is None:
        return UNAVAILABLE
    return f"[{repr(float(lower))}, {repr(float(upper))}]"


def _text(value: str) -> str:
    return " ".join(str(value).split())


def _write_provenance(
    path: Path,
    *,
    analysis: VecCampaignAnalysis,
    report: CampaignMechanismReport,
    source_name: str,
    source_digest: str,
    figures: list[GeneratedFigure],
    latency_metric: str,
    overwrite: bool,
) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    lines = [
        "# Capacity-study figure provenance",
        "",
        f"Status: **{RESEARCH_LABELS}**. Owner-approved-candidate is not supervisor",
        "approval, not validation, and not a causal claim.",
        "",
        "## Source",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Source analysis file | `{source_name}` |",
        f"| Source SHA-256 | `{source_digest}` |",
        f"| Experiment | `{analysis.experiment_id}` |",
        f"| Design fingerprint | `{analysis.design_fingerprint}` |",
        f"| Campaign status | `{analysis.campaign_status}` |",
        f"| Analysis method version | `{analysis.method_version}` |",
        f"| Analysis generated at | `{analysis.generated_at_utc}` |",
        f"| Primary metric | `{analysis.primary_metric_key}` |",
        f"| Baseline arm | `{analysis.baseline_label}` |",
        f"| Latency metric rendered | `{latency_metric}` |",
        f"| Capacity arms | {', '.join(f'`{arm}`' for arm in report.arm_labels)} |",
        f"| Fleet seeds | {', '.join(f'`{seed}`' for seed in report.seed_ids)} |",
        f"| Admitted collections | {analysis.admitted_collection_count} |",
        "",
        "The analysis file was read and never written. No registry, campaign service, or",
        "live campaign directory is opened by the generator.",
        "",
        "## Published figures",
        "",
        "Each row is one projection rendered twice from the same fingerprinted payload, so",
        "the table and the figure cannot disagree.",
        "",
        "| Figure | Projection fingerprint | File | SHA-256 | Bytes |",
        "|---|---|---|---|---|",
    ]
    for figure in figures:
        fingerprint = figure.projection.fingerprint()
        for item in figure.receipt.files:
            lines.append(
                f"| `{figure.slug}` | `{fingerprint}` | `{item.name}` | "
                f"`{item.checksum_sha256}` | {item.size_bytes} |"
            )
    lines += [
        "",
        "## How to read these figures",
        "",
        "- **Every number is a recorded value.** The generator selects and lays out values",
        "  the completed analysis and the accepted mechanism report already computed. It",
        "  derives no metric, no difference, and no summary of its own.",
        "- **Table cells carry full round-trip precision** rather than a rounded display, so",
        "  the invariance column can be checked against the digits beside it. Two values that",
        "  print identically in the table are identical in the recorded bytes.",
        "- **The bars are a bar series, not a polyline.** The accepted renderer draws",
        "  horizontal bars on a shared signed linear scale, so a per-seed latency curve",
        "  appears as one contiguous run of bars per seed, in capacity order. The companion",
        "  table holds the exact values the curve is drawn from.",
        "- **The deadline-success chart is zero-anchored** because the accepted scale always",
        "  is. That is deliberate: at true size the band is visibly flat, which is the",
        f"  finding. `{DIFFERENCES_SLUG}` publishes the paired differences the analysis",
        "  recorded, which is where the within-band structure can be read without magnifying",
        "  a difference into an apparent effect.",
        "- **Invariance categories render in the renderer's neutral colour.** Its categorical",
        "  palette is keyed to diagnostic-rule statuses, which these are not, so the",
        "  categories are distinguished by their text rather than by a borrowed colour.",
        "",
        "## Limitations, copied from the analysis",
        "",
    ]
    lines += [f"- {limitation}" for limitation in analysis.limitations]
    lines += [
        "",
        "## Regenerating",
        "",
        "```bash",
        "uv run python scripts/generate_capacity_figures.py \\",
        "  <path-to-campaign_analysis.json> --overwrite",
        "```",
        "",
        "The input path has no default. Regeneration on unchanged input rewrites identical",
        "bytes, so a regenerated figure never appears as commit churn.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
