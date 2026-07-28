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
    "wd-am": {
        "experiment_id": "vec-capacity-grid-wd-am",
        "run_id_prefix": "gridam",
        "trace_file": "traces/trace_wd_am_fullrsu.npz",
        "trace_sha256": "5e36a7cb8b49afa9929574c9627216b7479a28ee0cbd83cc81ff852e647fd7ee",
        "max_steps": 10_800,
        "output_root": "data/vec-fresh/capacity-grid-wd-am",
        "predeclaration_path": ("docs/evaluation/capacity_sweep_completion_predeclaration.md"),
        "predeclaration_sha256": (
            "a2cb0e3d1dbfd01dbf8629842f79977435eb00087fb68e412dc08361652305ed"
        ),
        "question": (
            "Does capacity inertness replicate on the morning-peak trace, completing "
            "the five-regime sweep?"
        ),
    },
    "wd-pm": {
        "experiment_id": "vec-capacity-grid-wd-pm",
        "run_id_prefix": "gridpm",
        "trace_file": "traces/trace_wd_pm_fullrsu.npz",
        "trace_sha256": "848ba3cf278515f6a628bfb575892373454fae60ea6edf717da3b7683051ba9f",
        "max_steps": 25_200,
        "output_root": "data/vec-fresh/capacity-grid-wd-pm",
        "predeclaration_path": ("docs/evaluation/capacity_sweep_completion_predeclaration.md"),
        "predeclaration_sha256": (
            "a2cb0e3d1dbfd01dbf8629842f79977435eb00087fb68e412dc08361652305ed"
        ),
        "question": (
            "Does capacity inertness replicate on the evening-peak trace, completing "
            "the five-regime sweep?"
        ),
    },
    "ev-deep": {
        "experiment_id": "vec-capacity-deep-ev",
        "run_id_prefix": "deepev",
        "trace_file": "traces/trace_ev_fullrsu.npz",
        "trace_sha256": "70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208",
        "max_steps": 23_400,
        "output_root": "data/vec-fresh/capacity-deep-ev",
        "variation_arms": [("cap-0.5", 0.5), ("cap-0.25", 0.25), ("cap-0.1", 0.1)],
        "predeclaration_path": ("docs/evaluation/capacity_sweep_completion_predeclaration.md"),
        "predeclaration_sha256": (
            "a2cb0e3d1dbfd01dbf8629842f79977435eb00087fb68e412dc08361652305ed"
        ),
        "question": (
            "At what deep-squeeze level, if any above cap-0.1, does the event-night "
            "regime's outcome sensitivity switch on?"
        ),
    },
    "inc-deep": {
        "experiment_id": "vec-capacity-deep-inc",
        "run_id_prefix": "deepinc",
        "trace_file": "traces/trace_inc_fullrsu.npz",
        "trace_sha256": "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
        "max_steps": 3_600,
        "output_root": "data/vec-fresh/capacity-deep-inc",
        "variation_arms": [("cap-0.5", 0.5), ("cap-0.25", 0.25), ("cap-0.1", 0.1)],
        "fleet_seeds": [60, 61, 62],
        "predeclaration_path": ("docs/evaluation/ceiling_law_prediction_predeclaration.md"),
        "predeclaration_sha256": (
            "78dcd3ce3004d31edae87e8534a0a6e2dfb945e601649d7ac6cc26e3ffca7d4b"
        ),
        "question": (
            "Does the tail-latency ceiling law L(c) = 39,959 ms x c, fitted across the "
            "pilot's 3.3x range, predict the ceiling 7.5x below that range's floor?"
        ),
    },
    "inc-baseline": {
        "experiment_id": "vec-crossover-inc-baseline",
        "run_id_prefix": "xoverinc",
        "trace_file": "traces/trace_inc_fullrsu.npz",
        "trace_sha256": "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
        "max_steps": 3_600,
        "output_root": "data/vec-fresh/crossover-inc-baseline",
        "actor_id": "baseline_model_c_17",
        "fleet_seeds": [0, 1, 2],
        "predeclaration_path": ("docs/evaluation/actor_crossover_candidate_inc_20260728.md"),
        "predeclaration_sha256": (
            "b8f0efa29f4c41210b44447595a53b2975e47af913f3057c1ac1e1540c885492"
        ),
        "question": (
            "Does the actor that wins at comfortable capacity lose under squeeze on the "
            "one trace where capacity moves outcomes at all?"
        ),
    },
    "we-deep": {
        "experiment_id": "vec-capacity-deep-we",
        "run_id_prefix": "deepwe",
        "trace_file": "traces/trace_we_fullrsu.npz",
        "trace_sha256": "a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be",
        "max_steps": 32_400,
        "output_root": "data/vec-fresh/capacity-deep-we",
        "variation_arms": [("cap-0.5", 0.5), ("cap-0.25", 0.25), ("cap-0.1", 0.1)],
        "fleet_seeds": [60, 61, 62],
        "predeclaration_path": ("docs/evaluation/density_gap_options_20260728.md"),
        "predeclaration_sha256": (
            "00681a14efb5b7134fb81abae0f365c27148972723d6ae3140deecfd2254ef3a"
        ),
        "question": (
            "Where does binding onset sit on this density, and does onset capacity scale "
            "with concurrent density as the low-end hypothesis predicts?"
        ),
    },
    "wd-am-deep": {
        "experiment_id": "vec-capacity-deep-wd-am",
        "run_id_prefix": "deepam",
        "trace_file": "traces/trace_wd_am_fullrsu.npz",
        "trace_sha256": "5e36a7cb8b49afa9929574c9627216b7479a28ee0cbd83cc81ff852e647fd7ee",
        "max_steps": 10_800,
        "output_root": "data/vec-fresh/capacity-deep-wd-am",
        "variation_arms": [("cap-0.5", 0.5), ("cap-0.25", 0.25), ("cap-0.1", 0.1)],
        "fleet_seeds": [60, 61, 62],
        "predeclaration_path": ("docs/evaluation/density_gap_options_20260728.md"),
        "predeclaration_sha256": (
            "00681a14efb5b7134fb81abae0f365c27148972723d6ae3140deecfd2254ef3a"
        ),
        "question": (
            "Where does binding onset sit on this density, and does onset capacity scale "
            "with concurrent density as the low-end hypothesis predicts?"
        ),
    },
    "wd-pm-deep": {
        "experiment_id": "vec-capacity-deep-wd-pm",
        "run_id_prefix": "deeppm",
        "trace_file": "traces/trace_wd_pm_fullrsu.npz",
        "trace_sha256": "848ba3cf278515f6a628bfb575892373454fae60ea6edf717da3b7683051ba9f",
        "max_steps": 25_200,
        "output_root": "data/vec-fresh/capacity-deep-wd-pm",
        "variation_arms": [("cap-0.5", 0.5), ("cap-0.25", 0.25), ("cap-0.1", 0.1)],
        "fleet_seeds": [60, 61, 62],
        "predeclaration_path": ("docs/evaluation/density_gap_options_20260728.md"),
        "predeclaration_sha256": (
            "00681a14efb5b7134fb81abae0f365c27148972723d6ae3140deecfd2254ef3a"
        ),
        "question": (
            "Where does binding onset sit on this density, and does onset capacity scale "
            "with concurrent density as the low-end hypothesis predicts?"
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
        "predeclaration_path": ("docs/evaluation/baseline_invariance_prediction_predeclaration.md"),
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
            VecCampaignArm(label=label, rsu_capacity_per_vehicle=cap)
            for label, cap in spec.get(
                "variation_arms",
                [("cap-1.5", 1.5), ("cap-1.0", 1.0), ("cap-0.75", 0.75)],
            )
        ],
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        fleet_seeds=spec.get("fleet_seeds", [50, 51, 52]),
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
