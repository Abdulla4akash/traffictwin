"""Render one campaign's mechanism-evidence exhibit from its analysis JSON.

The command line over
:mod:`traffictwin.integration.vec_campaign.mechanism_report`. Given a completed
`campaign_analysis.json` it writes a markdown exhibit: a provenance header naming
exactly which payload produced it, a note on how to read the adjacent-arm range
comparison, and then the accepted renderer's output **verbatim**.

**It changes nothing about the mechanism report.** The body is whatever
:func:`render_mechanism_report_markdown` produced, byte for byte. This script
adds a header around it and computes no metric, no comparison, and no summary of
its own.

**Both paths are required and neither has a default.** The script never searches
for a campaign directory and never picks an output location, so it cannot wander
into a campaign that is executing. An existing output file is kept unless
``--overwrite`` is passed.

**On the range comparison.** Pooled per-arm ranges and per-seed ordering answer
different questions, and a report that collapses them misleads in one direction
or the other. Ranges pooled across seeds can overlap whenever between-seed
variation exceeds adjacent-arm separation, while every individual seed still
ranks the two arms the same way — the paired within-seed contrast is what the
statistical machinery actually uses. The header says this in general terms; it is
never restated as the superseded claim that adjacent-arm ranges do not overlap.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from traffictwin.integration.vec_campaign.analysis import VecCampaignAnalysis
from traffictwin.integration.vec_campaign.mechanism_report import (
    MechanismReportError,
    build_mechanism_report,
    render_mechanism_report_markdown,
)

MAX_ANALYSIS_BYTES = 64 * 1024 * 1024

RESEARCH_LABELS = "exploratory, owner_approved_candidate, descriptive non-causal"

RANGE_READING_NOTE = (
    "**Reading the adjacent-arm range comparison.** Pooled per-arm ranges and per-seed "
    "ordering answer different questions. Ranges pooled across seeds can overlap whenever "
    "between-seed variation exceeds adjacent-arm separation, while every individual seed "
    "still ranks the two arms the same way. The paired within-seed contrast is what the "
    "statistical machinery uses. Citing only the pooled ranges understates the evidence; "
    "citing only the ordering overstates it. The table below reports both, separately, and "
    "neither is a claim about cause."
)


class MechanismRenderError(RuntimeError):
    """Raised when an analysis payload cannot be rendered as a mechanism exhibit."""


def main(argv: list[str] | None = None) -> int:
    """Render one exhibit and report where it landed."""

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "analysis_json",
        type=Path,
        help="Path to a completed campaign_analysis.json. Required; there is no default.",
    )
    parser.add_argument(
        "output_markdown",
        type=Path,
        help="Path the exhibit is written to. Required; there is no default.",
    )
    parser.add_argument(
        "--related-record",
        action="append",
        default=None,
        metavar="TEXT",
        help="Repeatable. A record to cite in the header, e.g. the corrected results record.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file instead of refusing.",
    )
    arguments = parser.parse_args(argv)
    try:
        written = render_exhibit(
            arguments.analysis_json,
            arguments.output_markdown,
            related_records=arguments.related_record,
            overwrite=arguments.overwrite,
        )
    except MechanismRenderError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"written: {written}")
    return 0


def render_exhibit(
    analysis_path: Path,
    output_path: Path,
    *,
    related_records: list[str] | None = None,
    overwrite: bool = False,
) -> Path:
    """Write the mechanism exhibit for one completed analysis."""

    output = Path(output_path)
    if output.exists() and not overwrite:
        raise MechanismRenderError(
            f"{output} already exists; pass --overwrite to replace it",
        )
    analysis, digest = _load_analysis(Path(analysis_path))
    try:
        report = build_mechanism_report(analysis)
    except MechanismReportError as error:
        raise MechanismRenderError(str(error)) from error
    document = _header(
        analysis,
        source_name=Path(analysis_path).name,
        source_digest=digest,
        related_records=related_records or [],
    )
    # The accepted renderer's output is emitted verbatim; nothing edits it.
    document += render_mechanism_report_markdown(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return output


def _load_analysis(path: Path) -> tuple[VecCampaignAnalysis, str]:
    """Read and validate one completed analysis, returning it with its byte identity."""

    if not path.is_file():
        raise MechanismRenderError(f"analysis JSON not found: {path}")
    payload = path.read_bytes()
    if len(payload) > MAX_ANALYSIS_BYTES:
        raise MechanismRenderError(f"analysis JSON exceeds {MAX_ANALYSIS_BYTES} bytes: {path}")
    digest = hashlib.sha256(payload).hexdigest()
    try:
        analysis = VecCampaignAnalysis.model_validate_json(payload)
    except ValueError as error:
        raise MechanismRenderError(f"not a valid campaign analysis: {error}") from error
    return analysis, digest


def _header(
    analysis: VecCampaignAnalysis,
    *,
    source_name: str,
    source_digest: str,
    related_records: list[str],
) -> str:
    lines = [
        f"# Campaign mechanism exhibit — `{analysis.experiment_id}`",
        "",
        f"Status: **{RESEARCH_LABELS}.** Owner-approved-candidate is not supervisor approval,",
        "not ethics approval, not validation, and not a causal claim. Every value in this",
        "exhibit was recorded by the campaign analysis and is re-presented here, not",
        "recomputed.",
        "",
        "## Source identity",
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
        f"| Primary endpoint | `{analysis.primary_metric_key}` |",
        f"| Baseline arm | `{analysis.baseline_label}` |",
        f"| Admitted collections | {analysis.admitted_collection_count} |",
        f"| Confirmatory | `{analysis.confirmatory}` |",
        f"| Significance claimed | `{analysis.significance_claimed}` |",
        "",
        RANGE_READING_NOTE,
        "",
    ]
    if related_records:
        lines += ["## Related records", ""]
        lines += [f"- {record}" for record in related_records]
        lines.append("")
    lines += [
        "## Limitations, copied from the analysis",
        "",
        *[f"- {limitation}" for limitation in analysis.limitations],
        "",
        "---",
        "",
        "Everything below is the accepted mechanism renderer's output, verbatim.",
        "",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
