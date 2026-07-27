"""Generate the dissertation's results tables through the accepted REP-01 exporter.

Two tables the write-up quotes and must never retype by hand, published from one
completed `campaign_analysis.json`:

* **Per-arm descriptives** — every arm's primary and secondary metric summaries
  (mean, minimum, maximum, and the per-seed values behind them), with each row
  labelled primary or secondary by which list of the analysis it came from.
* **Predeclared comparisons** — each variation-versus-baseline STA-01 evaluation:
  the mean paired difference, the bootstrap interval, and the randomisation
  p-value, beside the admitted pair count and the estimate's own interpretation.

**Every number is copied, never computed.** This script derives no metric, no
difference, no interval, and no p-value. It reads what
:class:`~traffictwin.integration.vec_campaign.analysis.VecCampaignAnalysis`
already recorded and hands it to
:func:`traffictwin.reporting.latex.write_projection_exports`, which does all the
rendering. Values are written at full round-trip precision so nothing is lost or
silently rounded on the way into the dissertation.

**Labels are read from the artifacts, never inferred.** The exploratory/
confirmatory status and the research status come from the analysis payload's own
type-level fields. The seed cohort comes from the sibling `campaign_receipt.json`
when one is present, and is reported as undeclared when it is not. Note what this
means and does not mean: the accepted analysis module fixes `confirmatory` to
`False` for *any* campaign it analyses, so a held-out cohort is reported as a
held-out cohort and the statistical status still reads exploratory. Running a
reserved seed cohort does not by itself make a result confirmatory — signing the
confirmatory protocol does, and that is a person's decision recorded elsewhere.

**The input path is a required argument with no default.** The script never
searches for a campaign directory, so it cannot wander into one that is
executing, and it writes only under the output directory it is given.

Deterministic by construction: no timestamps and no environment paths reach any
output, so regeneration on unchanged input rewrites identical bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from traffictwin.integration.vec_campaign.analysis import (
    VecArmDescriptives,
    VecCampaignAnalysis,
)
from traffictwin.reporting.latex import (
    MAX_CELL_CHARACTERS,
    MAX_FIGURE_ENTRIES,
    ResearchExportKind,
    ResearchExportProjection,
    ResearchExportReceipt,
    ResearchFigureEntry,
    write_projection_exports,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "dissertation_appendices" / "tables"

MAX_ANALYSIS_BYTES = 64 * 1024 * 1024
CAMPAIGN_RECEIPT_NAME = "campaign_receipt.json"

_UNSAFE_STEM = re.compile(r"[^a-z0-9]+")

STANDING_TABLE_NOTES = (
    "Every value is copied verbatim from the named campaign analysis payload. This "
    "generator computes no metric, difference, interval, or p-value of its own, and "
    "the rendering is done entirely by the accepted REP-01 exporter.",
    "Interval and randomisation outputs are STA-01 diagnostics reported as the "
    "analysis recorded them. They are not accepted thresholds, and non-significance "
    "is not evidence of equivalence.",
    "The comparisons share one baseline arm without multiplicity correction. The "
    "predeclaration reserves any corrected claim for the separately signed "
    "confirmatory protocol.",
    "Deadline success is never physical completion, and reconstructed evaluator "
    "behaviour is never an observed journey.",
    "Consuming a reserved seed cohort does not make a result confirmatory. The "
    "accepted analysis module fixes its confirmatory field to false for every "
    "campaign it analyses; promotion is a signed decision recorded elsewhere.",
)


class ResultsTableError(RuntimeError):
    """Raised when a required input is missing, unreadable, or unusable."""


def format_exact(value: float | int | None) -> str:
    """Render one recorded number at full round-trip precision.

    The dissertation quotes these cells, so nothing is rounded on the way in.
    ``repr`` of a float is the shortest string that reads back as the same
    double, which is exactly the "verbatim" the results tables need.
    """

    if value is None:
        return "unavailable"
    if isinstance(value, int):
        return str(value)
    return repr(value)


def _fit(text: str, warnings: list[str], subject: str) -> str:
    """Fit one string to the accepted renderer's bound, recording any truncation.

    The exporter refuses an over-long cell, caption, or source id outright. A
    long experiment identifier must not turn into a crash, and it must not
    silently lose characters either, so an over-long value is truncated *and*
    the truncation is carried into the projection's own warnings.
    """

    if len(text) <= MAX_CELL_CHARACTERS:
        return text
    warnings.append(
        f"{subject} was truncated to the exporter's {MAX_CELL_CHARACTERS}-character "
        "bound; the complete value is in the source analysis payload and the "
        "provenance note"
    )
    return text[: MAX_CELL_CHARACTERS - 1] + "…"


def _seed_values_cell(row: VecArmDescriptives, warnings: list[str]) -> str:
    ordered = sorted(row.seed_values.items(), key=lambda item: (len(item[0]), item[0]))
    rendered = "; ".join(f"{seed}={format_exact(value)}" for seed, value in ordered)
    return _fit(rendered, warnings, f"per-seed values for {row.arm_label}/{row.metric_key}")


def read_analysis(path: str | Path) -> VecCampaignAnalysis:
    """Read and validate one completed campaign analysis payload."""

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ResultsTableError(f"analysis payload is missing or unsafe: {source}")
    size = source.stat().st_size
    if size > MAX_ANALYSIS_BYTES:
        raise ResultsTableError(f"analysis payload is implausibly large ({size} bytes): {source}")
    try:
        return VecCampaignAnalysis.model_validate_json(source.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ResultsTableError(
            f"analysis payload is not a valid campaign analysis: {exc}"
        ) from exc


def read_seed_cohort(analysis_path: str | Path) -> str:
    """Return the declared seed cohort from the sibling campaign receipt.

    Reported as ``undeclared`` when no receipt sits beside the analysis, rather
    than guessed from the experiment identifier.
    """

    receipt = Path(analysis_path).parent / CAMPAIGN_RECEIPT_NAME
    if receipt.is_symlink() or not receipt.is_file():
        return "undeclared"
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "undeclared"
    phase = payload.get("phase")
    return phase if isinstance(phase, str) and phase else "undeclared"


def _status_label(analysis: VecCampaignAnalysis, cohort: str) -> str:
    """Compose the compact status line both renderers can carry.

    Deliberately short: the caption and source id are bounded at
    ``MAX_CELL_CHARACTERS``, and the full status is recorded in the provenance
    note beside the tables.
    """

    stance = "confirmatory" if analysis.confirmatory else "exploratory"
    return f"{stance}; {analysis.research_status}; cohort {cohort}"


def build_descriptives_projection(
    analysis: VecCampaignAnalysis, cohort: str
) -> ResearchExportProjection:
    """Project every arm's primary and secondary descriptives without recalculation."""

    warnings: list[str] = []
    rows: list[list[str]] = []
    for role, entries in (
        ("primary", analysis.primary_descriptives),
        ("secondary", analysis.secondary_descriptives),
    ):
        for entry in sorted(entries, key=lambda item: (item.metric_key, item.arm_label)):
            rows.append(
                [
                    entry.arm_label,
                    entry.metric_key,
                    role,
                    str(len(entry.seed_values)),
                    format_exact(entry.mean),
                    format_exact(entry.minimum),
                    format_exact(entry.maximum),
                    _seed_values_cell(entry, warnings),
                ]
            )
    label = _status_label(analysis, cohort)
    return ResearchExportProjection(
        kind=ResearchExportKind.METRICS,
        source_id=_fit(f"{analysis.experiment_id}; {label}", warnings, "source id"),
        title="Per-arm descriptive results",
        caption=_fit(
            f"Per-arm descriptives, {analysis.experiment_id}; baseline "
            f"{analysis.baseline_label}; {label}.",
            warnings,
            "descriptives caption",
        ),
        columns=[
            "Arm",
            "Metric",
            "Role",
            "Seeds",
            "Mean",
            "Minimum",
            "Maximum",
            "Per-seed values",
        ],
        rows=rows,
        figure_entries=[],
        synthetic=False,
        warnings=warnings[:20],
    )


def build_comparisons_projection(
    analysis: VecCampaignAnalysis, cohort: str
) -> ResearchExportProjection:
    """Project the predeclared comparisons exactly as the analysis recorded them."""

    rows: list[list[str]] = []
    figure_entries: list[ResearchFigureEntry] = []
    for comparison in sorted(analysis.comparisons, key=lambda item: item.variation_label):
        study = comparison.study
        interval = study.bootstrap_interval
        bounds = (
            "unavailable"
            if comparison.bootstrap_lower is None or comparison.bootstrap_upper is None
            else (
                f"[{format_exact(comparison.bootstrap_lower)}, "
                f"{format_exact(comparison.bootstrap_upper)}] "
                f"@ {format_exact(interval.confidence_level)}"
            )
        )
        rows.append(
            [
                f"{comparison.variation_label} vs {analysis.baseline_label}",
                comparison.study_status,
                str(comparison.admitted_pair_count),
                format_exact(comparison.mean_paired_difference),
                bounds,
                format_exact(comparison.randomisation_p_value),
                study.estimate.interpretation or "unavailable",
                study.metric_unit or "unavailable",
            ]
        )
        room_left = len(figure_entries) < MAX_FIGURE_ENTRIES
        if comparison.mean_paired_difference is not None and room_left:
            figure_entries.append(
                ResearchFigureEntry(
                    label=f"{comparison.variation_label} vs {analysis.baseline_label}",
                    numeric_value=comparison.mean_paired_difference,
                )
            )
    warnings: list[str] = []
    label = _status_label(analysis, cohort)
    return ResearchExportProjection(
        kind=ResearchExportKind.STATISTICAL_STUDY,
        source_id=_fit(f"{analysis.experiment_id}; {label}", warnings, "source id"),
        title="Predeclared paired comparisons",
        caption=_fit(
            f"Paired comparisons on {analysis.primary_metric_key}; variation minus "
            f"baseline {analysis.baseline_label}; {label}.",
            warnings,
            "comparisons caption",
        ),
        columns=[
            "Comparison",
            "Study status",
            "Admitted pairs",
            "Mean paired difference",
            "Bootstrap interval",
            "Randomisation p",
            "Interpretation",
            "Unit",
        ],
        rows=rows,
        figure_entries=figure_entries,
        synthetic=False,
        warnings=warnings[:20],
    )


def output_stem(analysis: VecCampaignAnalysis) -> str:
    """Return the deterministic file stem for one analysis, from its experiment id."""

    stem = _UNSAFE_STEM.sub("_", analysis.experiment_id.lower()).strip("_")
    if not stem:
        raise ResultsTableError(
            f"experiment id {analysis.experiment_id!r} yields no safe output stem"
        )
    return stem


def render_provenance(
    analysis: VecCampaignAnalysis,
    cohort: str,
    analysis_path: Path,
    analysis_sha256: str,
    published: list[tuple[str, ResearchExportReceipt]],
) -> str:
    """Render the deterministic provenance note that ships beside the tables."""

    lines = [
        f"# Results tables provenance — {analysis.experiment_id}",
        "",
        "Generated by `scripts/generate_results_tables.py` through the accepted REP-01",
        "exporter (`src/traffictwin/reporting/latex.py`). Every value is copied from the",
        "source payload below; this generator computes nothing.",
        "",
        "## Source",
        "",
        f"- Analysis payload: `{analysis_path.as_posix()}`",
        f"- Analysis SHA-256: `{analysis_sha256}`",
        f"- Experiment id: {analysis.experiment_id}",
        f"- Design fingerprint: `{analysis.design_fingerprint}`",
        f"- Campaign status: {analysis.campaign_status}",
        f"- Analysis method version: {analysis.method_version}",
        f"- Admitted metric collections: {analysis.admitted_collection_count}",
        f"- Baseline arm: {analysis.baseline_label}",
        f"- Primary endpoint: {analysis.primary_metric_key}",
        "",
        "## Declared status",
        "",
        f"- Seed cohort (from the sibling campaign receipt): {cohort}",
        f"- Statistical stance (from the analysis payload): "
        f"{'confirmatory' if analysis.confirmatory else 'exploratory'}",
        f"- Research status (from the analysis payload): {analysis.research_status}",
        f"- Significance claimed: {str(analysis.significance_claimed).lower()}",
        "",
        "## Published files",
        "",
        "| File | Format | SHA-256 | Bytes | Projection fingerprint |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, receipt in published:
        for item in receipt.files:
            lines.append(
                f"| `{item.name}` | {item.format} | `{item.checksum_sha256}` "
                f"| {item.size_bytes} | `{receipt.projection_fingerprint[:12]}` |"
            )
        del name
    lines.extend(["", "## How to read these tables", ""])
    lines.extend(f"- {note}" for note in STANDING_TABLE_NOTES)
    lines.extend(
        [
            "",
            "The descriptives table ships without a figure on purpose. Its rows mix units —",
            "a success ratio beside a latency in milliseconds — and the accepted exporter",
            "draws numeric entries on one shared linear scale, so a combined figure would",
            "misrepresent them. The per-metric figures published under",
            "`docs/dissertation_appendices/figures/` are the accepted rendering of those",
            "series. The comparisons table does carry a figure: every paired difference it",
            "plots is in the primary endpoint's single unit.",
            "",
            "The limitations the analysis payload itself records:",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in analysis.limitations)
    lines.append("")
    return "\n".join(lines)


def generate(
    analysis_path: str | Path,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Generate both tables and their provenance note; return the written paths."""

    source = Path(analysis_path)
    analysis = read_analysis(source)
    cohort = read_seed_cohort(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    stem = output_stem(analysis)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    descriptives = target / f"{stem}_arm_descriptives.tex"
    comparisons = target / f"{stem}_predeclared_comparisons.tex"
    comparisons_figure = target / f"{stem}_predeclared_comparisons.svg"
    provenance = target / f"{stem}_provenance.md"

    published = [
        (
            "descriptives",
            write_projection_exports(
                build_descriptives_projection(analysis, cohort),
                descriptives,
                overwrite=overwrite,
            ),
        ),
        (
            "comparisons",
            write_projection_exports(
                build_comparisons_projection(analysis, cohort),
                comparisons,
                figure_path=comparisons_figure,
                overwrite=overwrite,
            ),
        ),
    ]
    if provenance.exists() and not overwrite:
        raise ResultsTableError(f"refusing to overwrite {provenance} without --overwrite")
    provenance.write_text(
        render_provenance(analysis, cohort, source, digest, published), encoding="utf-8"
    )
    return [descriptives, comparisons, comparisons_figure, provenance]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_results_tables",
        description="Generate the dissertation results tables from one campaign analysis payload.",
    )
    parser.add_argument(
        "analysis",
        type=Path,
        help="path to a completed campaign_analysis.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="directory the tables and provenance note are written to",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="allow existing generated files to be replaced",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Generate the results tables and return a process exit code."""

    args = _build_parser().parse_args(argv)
    try:
        written = generate(args.analysis, args.output_dir, overwrite=args.overwrite)
    except (ResultsTableError, OSError, ValueError) as exc:
        print(f"results tables were not generated: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
