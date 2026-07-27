#!/usr/bin/env python3
"""Launch, resume, or analyse the approved capacity-squeeze pilot campaign.

The design below is the single canonical construction of the approved pilot:
its fingerprint (which covers the approval block byte-for-byte) must match the
campaign receipt, so this file — not any session scratchpad — is the durable
source for resuming an interrupted campaign or analysing a completed one.

Usage:
    uv run python scripts/capacity_pilot_campaign.py fingerprint
    uv run python scripts/capacity_pilot_campaign.py launch
    uv run python scripts/capacity_pilot_campaign.py analyze

``launch`` is safely re-runnable: cells whose output directories already hold
an intact completed receipt for the same request fingerprint are reused, so a
resume costs only the unfinished cells. ``analyze`` writes the exploratory
report and refuses if the stored receipt does not belong to this design.
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
OUTPUT_ROOT = "data/vec-fresh/capacity-pilot"
REGISTRY_PATH = ".demo/registry-capacity-pilot.sqlite"
RECEIPT_PATH = f"{OUTPUT_ROOT}/campaign_receipt.json"
ANALYSIS_JSON_PATH = f"{OUTPUT_ROOT}/campaign_analysis.json"
ANALYSIS_REPORT_PATH = f"{OUTPUT_ROOT}/campaign_analysis.md"


def pilot_design() -> VecCampaignDesign:
    """Return the exact approved pilot design; do not edit without re-approval."""

    return VecCampaignDesign(
        experiment_id="vec-capacity-squeeze-pilot",
        research_question=(
            "Does reducing per-vehicle RSU task capacity degrade deadline success on the "
            "Manchester incident trace, and is the degradation graceful or a cliff?"
        ),
        run_id_prefix="cappilot",
        phase=VecCampaignPhase.PILOT,
        approval=VecCampaignApproval(
            predeclaration_path="docs/evaluation/capacity_squeeze_pilot_predeclaration.md",
            predeclaration_sha256=(
                "7509c7c1fdc50862d72d60b95d637de5477a3a33d4ceb555f207efc53fa539b6"
            ),
            approved_by=(
                "Abdulla (repository owner; delegation relayed in session, 26 July 2026: "
                "'take reasonable decisions in each of them')"
            ),
            approved_role="repository owner",
            approved_at_utc="2026-07-26T22:30:00+00:00",
            held_out_authorised=False,
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
            VecCampaignArm(label="cap-1.5", rsu_capacity_per_vehicle=1.5),
            VecCampaignArm(label="cap-1.0", rsu_capacity_per_vehicle=1.0),
            VecCampaignArm(label="cap-0.75", rsu_capacity_per_vehicle=0.75),
        ],
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        fleet_seeds=[0, 1, 2],
        primary_metric_key="tos.task.deadline_success.rate",
        budget=VecCampaignBudget(
            max_cells=12,
            max_total_output_bytes=3_000_000_000,
            halt_on_failure=True,
        ),
    )


def _launch() -> int:
    receipt = execute_campaign(
        pilot_design(),
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
    analysis = analyze_campaign(pilot_design(), receipt, REGISTRY_PATH)
    Path(ANALYSIS_JSON_PATH).write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    report = render_campaign_analysis_markdown(analysis)
    appendices = [
        "\n---\n\n# Appendix: full STA-01 study reports (exploratory)\n",
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
        print(pilot_design().fingerprint())
        return 0
    if args.command == "launch":
        return _launch()
    return _analyze()


if __name__ == "__main__":
    raise SystemExit(main())
