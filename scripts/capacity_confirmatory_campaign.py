#!/usr/bin/env python3
"""Launch, resume, or analyse the capacity confirmatory campaign (candidate (b)).

The design below is the single canonical construction of the chosen confirmatory
protocol — candidate (b), latency primary, ``cap-0.75`` — whose approval binds the
final SHA-256 of the chosen candidate file with ``held_out_authorised`` set. The
approval provenance is an in-session owner delegation recorded verbatim in that
file's decision record; it is not an owner-typed signature, and editing the
candidate file invalidates the digest and refuses execution.

Usage:
    uv run python scripts/capacity_confirmatory_campaign.py fingerprint
    uv run python scripts/capacity_confirmatory_campaign.py launch
    uv run python scripts/capacity_confirmatory_campaign.py analyze

``launch`` is safely re-runnable: cells whose output directories already hold an
intact completed receipt for the same request fingerprint are reused, so a resume
costs only the unfinished cells. ``analyze`` writes the report and refuses if the
stored receipt does not belong to this design. The held-out seeds {10-14} are
consumed only here; pilot seeds are never pooled in.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from traffictwin.experiments.statistical_study import statistical_study_to_markdown
from traffictwin.integration.vec_campaign import (
    VecCampaignApproval,
    VecCampaignArm,
    VecCampaignBudget,
    VecCampaignDesign,
    VecCampaignPhase,
    VecCampaignReceipt,
    analyze_campaign,
    execute_campaign,
    render_campaign_analysis_markdown,
)
from traffictwin.integration.vec_fresh_admission import VecPairingSeedSource
from traffictwin.integration.vec_runner.models import VecFleet

INPUT_ROOT = "../external/tos-data"
VEC_REPO = "../external/vec_env"
TOS_DATA_REPO = "../external/tos-data"
OUTPUT_ROOT = "data/vec-fresh/capacity-confirmatory"
REGISTRY_PATH = ".demo/registry-capacity-confirmatory.sqlite"
RECEIPT_PATH = f"{OUTPUT_ROOT}/campaign_receipt.json"
ANALYSIS_JSON_PATH = f"{OUTPUT_ROOT}/campaign_analysis.json"
ANALYSIS_REPORT_PATH = f"{OUTPUT_ROOT}/campaign_analysis.md"


def confirmatory_design() -> VecCampaignDesign:
    """Return the exact chosen confirmatory design; do not edit without re-approval."""

    return VecCampaignDesign(
        experiment_id="vec-capacity-confirmatory",
        research_question=(
            "Does tightening per-vehicle RSU task capacity from 2.5 to 0.75 reduce mean "
            "task latency on the Manchester incident trace, confirmed on held-out seeds "
            "with the latency primary declared before any held-out data existed?"
        ),
        run_id_prefix="capconf",
        phase=VecCampaignPhase.HELD_OUT,
        approval=VecCampaignApproval(
            predeclaration_path=(
                "docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md"
            ),
            predeclaration_sha256=(
                "ac9d6cb7cd24f19ba683352cd3d12d91cbd610343ac392028feb53797bbae2a8"
            ),
            approved_by=(
                "Abdulla (repository owner; delegation relayed in session, 27 July 2026: "
                "'take reasonable choices and keep working' — see the candidate file's "
                "decision record; not an owner-typed signature)"
            ),
            approved_role="repository owner",
            approved_at_utc="2026-07-27T13:30:00+00:00",
            held_out_authorised=True,
        ),
        trace_file="traces/trace_inc_fullrsu.npz",
        trace_sha256="e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
        actor_id="ukfleettrain_mappo_model_c_17",
        fleet=VecFleet.UK_2030,
        evaluator_seed=0,
        max_steps=3600,
        timeout_seconds=7200,
        baseline_arm=VecCampaignArm(label="cap-2.5", rsu_capacity_per_vehicle=2.5),
        variation_arms=[
            VecCampaignArm(label="cap-0.75", rsu_capacity_per_vehicle=0.75),
        ],
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        fleet_seeds=[10, 11, 12, 13, 14],
        primary_metric_key="task.latency.mean_ms",
        budget=VecCampaignBudget(
            max_cells=10,
            max_total_output_bytes=3_000_000_000,
            halt_on_failure=True,
        ),
    )


def _launch() -> int:
    receipt = execute_campaign(
        confirmatory_design(),
        input_root=INPUT_ROOT,
        vec_repo=VEC_REPO,
        tos_data_repo=TOS_DATA_REPO,
        output_root=OUTPUT_ROOT,
        registry_path=REGISTRY_PATH,
        predeclaration_root=".",
    )
    print("status              :", receipt.status.value)
    print("admitted            :", receipt.admitted_cell_count)
    print("reused              :", receipt.reused_cell_count)
    print("failed              :", receipt.failed_cell_count)
    print("skipped             :", receipt.skipped_cell_count)
    print("total elapsed (s)   :", round(receipt.total_elapsed_seconds, 1))
    for cell in receipt.cells:
        print(
            f"  {cell.output_directory_name:>16} {cell.state.value:>18} "
            f"{(cell.elapsed_seconds or 0.0):9.1f}s  {cell.detail[:60]}"
        )
    Path(RECEIPT_PATH).write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    print("receipt written to", RECEIPT_PATH)
    return 0 if receipt.status.value == "completed" else 1


def _analyze() -> int:
    receipt_file = Path(RECEIPT_PATH)
    if not receipt_file.is_file():
        print(f"no campaign receipt at {RECEIPT_PATH}; run launch first", file=sys.stderr)
        return 1
    receipt = VecCampaignReceipt.model_validate_json(receipt_file.read_text(encoding="utf-8"))
    analysis = analyze_campaign(confirmatory_design(), receipt, REGISTRY_PATH)
    Path(ANALYSIS_JSON_PATH).write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    report = render_campaign_analysis_markdown(analysis)
    appendices = [
        "\n---\n\n# Appendix: full STA-01 study reports\n",
    ]
    for row in analysis.comparisons:
        appendices.append(f"\n## {row.variation_label} versus {analysis.baseline_label}\n")
        appendices.append(statistical_study_to_markdown(row.study))
    report = report + "\n".join(appendices)
    Path(ANALYSIS_REPORT_PATH).write_text(report, encoding="utf-8")
    print(report)
    print("analysis written to", ANALYSIS_JSON_PATH, "and", ANALYSIS_REPORT_PATH)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fingerprint", "launch", "analyze"])
    args = parser.parse_args()
    if args.command == "fingerprint":
        print(confirmatory_design().fingerprint())
        return 0
    if args.command == "launch":
        return _launch()
    return _analyze()


if __name__ == "__main__":
    raise SystemExit(main())
