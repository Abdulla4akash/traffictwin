"""Re-verify one executed VEC campaign offline and report what disagrees.

The command line over :mod:`traffictwin.integration.vec_campaign.verify`. Given
the design constructor that produced a campaign, the campaign's output directory,
and optionally the registry it admitted into, it re-derives every fingerprint,
re-reads every cell receipt, re-hashes every published output, looks up every
admitted cell's registry identity, and re-hashes the approved predeclaration.

**Nothing is repaired and nothing is written.** There is no `--fix`, no
`--reconcile`, and no output-file default: an exhibit is written only where
``--markdown-out`` explicitly names a path, and an existing file there is kept
unless ``--overwrite`` is passed. The campaign directory, the registry rows, and
the predeclaration are read and never modified.

**Every path is required and none is guessed.** The script never searches for a
campaign directory, so it cannot wander into one that is currently executing.

**Exit codes.** ``0`` verification ran and every check passed; ``1`` verification
ran and at least one check failed; ``2`` verification could not be performed at
all (a missing campaign receipt, a design module that will not import). The
middle case is the informative one: exit ``1`` means the artifacts contradict
each other, not that the tool broke.

Usage::

    uv run python scripts/verify_campaign.py \\
        --design-module scripts/some_campaign.py \\
        --design-attr some_design \\
        --campaign-dir data/vec-fresh/some-campaign \\
        --registry .demo/registry-some.sqlite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from traffictwin.integration.vec_campaign.verify import (
    CampaignVerificationError,
    CampaignVerificationReport,
    VerificationSeverity,
    load_design_from_module,
    render_verification_markdown,
    verify_campaign,
)

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNVERIFIABLE = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_campaign",
        description="Offline consistency verification of one executed VEC campaign.",
    )
    parser.add_argument(
        "--design-module",
        required=True,
        type=Path,
        help="path to the trusted repository script exposing the campaign design constructor",
    )
    parser.add_argument(
        "--design-attr",
        required=True,
        help="name of the design constructor in that module (for example: pilot_design)",
    )
    parser.add_argument(
        "--campaign-dir",
        required=True,
        type=Path,
        help="the campaign output directory holding campaign_receipt.json and the cell directories",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help=(
            "optional registry database to check admitted cells against; when omitted the "
            "registry checks are reported as not run rather than as passed"
        ),
    )
    parser.add_argument(
        "--predeclaration-root",
        type=Path,
        default=Path(),
        help="root that relative predeclaration paths resolve against (default: current directory)",
    )
    parser.add_argument(
        "--skip-output-hashes",
        action="store_true",
        help=(
            "skip re-hashing published output payloads; recorded as a check not run, "
            "useful when the payloads are large and only receipt structure is in question"
        ),
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=None,
        help="optional path to write the verification exhibit to",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="optional path to write the typed verification report to",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="allow an existing output file to be replaced",
    )
    return parser


def _summarise(report: CampaignVerificationReport) -> str:
    verdict = "PASS" if report.passed else "FAIL"
    failures = len(report.failures())
    warnings = len(report.warnings())
    lines = [
        f"{verdict}  {report.experiment_id}  ({report.campaign_directory})",
        (
            f"  cells matched {report.cells_examined}/{report.planned_cell_count}, "
            f"executed re-read {report.executed_cells_examined}, "
            f"admitted checked {report.admitted_cells_examined}, "
            f"outputs re-hashed {report.output_files_hashed}"
        ),
        f"  findings: {failures} failure(s), {warnings} warning(s)",
    ]
    if report.checks_not_run:
        lines.append(f"  checks NOT run: {', '.join(str(c) for c in report.checks_not_run)}")
    for finding in report.findings:
        marker = "FAIL" if finding.severity is VerificationSeverity.FAILURE else "WARN"
        lines.append(f"  [{marker}] {finding.code} {finding.subject}: {finding.detail}")
    return "\n".join(lines)


def _write(path: Path, text: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise CampaignVerificationError(f"refusing to overwrite {path} without --overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run one verification pass and return its exit code."""

    args = _build_parser().parse_args(argv)
    try:
        design = load_design_from_module(args.design_module, args.design_attr)
        report = verify_campaign(
            design,
            args.campaign_dir,
            registry_path=args.registry,
            predeclaration_root=args.predeclaration_root,
            hash_outputs=not args.skip_output_hashes,
        )
        if args.markdown_out is not None:
            _write(
                args.markdown_out, render_verification_markdown(report), overwrite=args.overwrite
            )
        if args.json_out is not None:
            _write(args.json_out, report.canonical_json() + "\n", overwrite=args.overwrite)
    except (CampaignVerificationError, OSError, ValueError) as exc:
        print(f"verification could not be performed: {exc}", file=sys.stderr)
        return EXIT_UNVERIFIABLE

    print(_summarise(report))
    return EXIT_PASS if report.passed else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
