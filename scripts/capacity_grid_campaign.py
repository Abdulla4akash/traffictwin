#!/usr/bin/env python3
"""Launch, resume, or analyse the exploratory three-trace capacity grid (A1).

Two pilot-mirroring campaigns — one per admitted non-incident trace — bound to the
committed grid predeclaration's SHA-256. Exploratory only: fresh seeds {50, 51, 52},
held_out_authorised is False, and the analysis harness's non-confirmatory status is
type-level. The inc leg of the grid is the completed pilot and is never re-run.

Usage:
    uv run python scripts/capacity_grid_campaign.py {we,ev} {fingerprint,launch,analyze}
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
REGISTRY_PATH = ".demo/registry-capacity-grid.sqlite"

TRACES = {
    "we": {
        "experiment_id": "vec-capacity-grid-we",
        "run_id_prefix": "gridwe",
        "trace_file": "traces/trace_we_fullrsu.npz",
        "trace_sha256": "a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be",
        "max_steps": 32_400,
        "output_root": "data/vec-fresh/capacity-grid-we",
        "question": (
            "Does the capacity-invariance and latency-collapse pattern measured on the "
            "incident trace replicate on the zero-event weekend trace?"
        ),
    },
    "ev": {
        "experiment_id": "vec-capacity-grid-ev",
        "run_id_prefix": "gridev",
        "trace_file": "traces/trace_ev_fullrsu.npz",
        "trace_sha256": "70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208",
        "max_steps": 23_400,
        "output_root": "data/vec-fresh/capacity-grid-ev",
        "question": (
            "Does the capacity-invariance and latency-collapse pattern measured on the "
            "incident trace replicate on the event-night trace?"
        ),
    },
    "ev-baseline": {
        "experiment_id": "vec-baseline-invariance-ev",
        "run_id_prefix": "b0ev",
        "trace_file": "traces/trace_ev_fullrsu.npz",
        "trace_sha256": "70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208",
        "max_steps": 23_400,
        "output_root": "data/vec-fresh/baseline-invariance-ev",
        "actor_id": "baseline_model_c_17",
        "predeclaration_path": (
            "docs/evaluation/baseline_invariance_prediction_predeclaration.md"
        ),
        "predeclaration_sha256": (
            "fe3db75311d3f7c89d3492fd4cf283fd36fcaad8919e51cd62bcf8673978c030"
        ),
        "question": (
            "Is the baseline actor exactly as capacity-invariant as the ukfleettrain "
            "actor on the event-night trace, as the observability-gap mechanism "
            "predicts?"
        ),
    },
}


def grid_design(trace_key: str) -> VecCampaignDesign:
    """Return the exact delegated grid design for one trace; edits need re-approval."""

    spec = TRACES[trace_key]
    return VecCampaignDesign(
        experiment_id=spec["experiment_id"],
        research_question=spec["question"],
        run_id_prefix=spec["run_id_prefix"],
        phase=VecCampaignPhase.PILOT,
        approval=VecCampaignApproval(
            predeclaration_path=spec.get(
                "predeclaration_path", "docs/evaluation/capacity_grid_predeclaration.md"
            ),
            predeclaration_sha256=spec.get(
                "predeclaration_sha256",
                "93384588f9f1158b94e708138e3f0000da9b3be8ca109334bc38d27aec3561e1",
            ),
            approved_by=(
                "Abdulla (repository owner; delegation relayed in session, 27-28 July "
                "2026: 'take reasonable choices and keep working' / 'I want to do some "
                "experimenting now'; not an owner-typed signature)"
            ),
            approved_role="repository owner",
            approved_at_utc="2026-07-28T00:45:00+00:00",
            held_out_authorised=False,
        ),
        trace_file=spec["trace_file"],
        trace_sha256=spec["trace_sha256"],
        actor_id=spec.get("actor_id", "ukfleettrain_mappo_model_c_17"),
        fleet=VecFleet.UK_2030,
        evaluator_seed=0,
        max_steps=spec["max_steps"],
        timeout_seconds=7_200,
        baseline_arm=VecCampaignArm(label="cap-2.5", rsu_capacity_per_vehicle=2.5),
        variation_arms=[
            VecCampaignArm(label="cap-1.5", rsu_capacity_per_vehicle=1.5),
            VecCampaignArm(label="cap-1.0", rsu_capacity_per_vehicle=1.0),
            VecCampaignArm(label="cap-0.75", rsu_capacity_per_vehicle=0.75),
        ],
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        fleet_seeds=[50, 51, 52],
        primary_metric_key="tos.task.deadline_success.rate",
        budget=VecCampaignBudget(
            max_cells=12,
            max_total_output_bytes=3_000_000_000,
            halt_on_failure=True,
        ),
    )


def _launch(trace_key: str) -> int:
    spec = TRACES[trace_key]
    receipt = execute_campaign(
        grid_design(trace_key),
        input_root=INPUT_ROOT,
        vec_repo=VEC_REPO,
        tos_data_repo=TOS_DATA_REPO,
        output_root=spec["output_root"],
        registry_path=REGISTRY_PATH,
        predeclaration_root=".",
    )
    print("status              :", receipt.status.value)
    print("admitted            :", receipt.admitted_cell_count)
    print("reused              :", receipt.reused_cell_count)
    print("failed              :", receipt.failed_cell_count)
    print("total elapsed (s)   :", round(receipt.total_elapsed_seconds, 1))
    for cell in receipt.cells:
        print(
            f"  {cell.output_directory_name:>16} {cell.state.value:>18} "
            f"{(cell.elapsed_seconds or 0.0):9.1f}s  {cell.detail[:60]}"
        )
    Path(spec["output_root"], "campaign_receipt.json").write_text(
        receipt.model_dump_json(indent=2), encoding="utf-8"
    )
    return 0 if receipt.status.value == "completed" else 1


def _analyze(trace_key: str) -> int:
    spec = TRACES[trace_key]
    receipt_file = Path(spec["output_root"], "campaign_receipt.json")
    if not receipt_file.is_file():
        print(f"no campaign receipt at {receipt_file}; run launch first", file=sys.stderr)
        return 1
    receipt = VecCampaignReceipt.model_validate_json(receipt_file.read_text(encoding="utf-8"))
    analysis = analyze_campaign(grid_design(trace_key), receipt, REGISTRY_PATH)
    Path(spec["output_root"], "campaign_analysis.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8"
    )
    report = render_campaign_analysis_markdown(analysis)
    appendices = ["\n---\n\n# Appendix: full STA-01 study reports (exploratory)\n"]
    for row in analysis.comparisons:
        appendices.append(f"\n## {row.variation_label} versus {analysis.baseline_label}\n")
        appendices.append(statistical_study_to_markdown(row.study))
    report = report + "\n".join(appendices)
    Path(spec["output_root"], "campaign_analysis.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", choices=sorted(TRACES))
    parser.add_argument("command", choices=["fingerprint", "launch", "analyze"])
    args = parser.parse_args()
    if args.command == "fingerprint":
        print(grid_design(args.trace).fingerprint())
        return 0
    if args.command == "launch":
        return _launch(args.trace)
    return _analyze(args.trace)


if __name__ == "__main__":
    raise SystemExit(main())
