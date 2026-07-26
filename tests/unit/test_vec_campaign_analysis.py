"""Exploratory-analysis tests over a synthetic admitted campaign."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from tests.tos_v2_helpers import (
    V2_SCENARIO,
    build_v2_occupancy_rows,
    build_v2_perstep,
    build_v2_pertask,
    build_v2_trace,
)
from traffictwin.integration.vec_campaign import (
    VecCampaignApproval,
    VecCampaignArm,
    VecCampaignBudget,
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignDesign,
    VecCampaignError,
    VecCampaignPhase,
    VecCampaignReceipt,
    VecCampaignStatus,
    analyze_campaign,
    register_campaign_experiment,
    render_campaign_analysis_markdown,
)
from traffictwin.integration.vec_fresh_admission import (
    VecFreshRunStudyContext,
    VecPairingSeedSource,
    build_fresh_run_admission,
    register_fresh_run_admission,
)
from traffictwin.integration.vec_identity import build_vehicle_identity_snapshot
from traffictwin.integration.vec_runner.models import (
    VecExecutionReceipt,
    VecRunnerFileEvidence,
    VecRunRequest,
    VecRuntimeEvidence,
    output_fingerprint,
)

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
SYNTHETIC_TRACE_SHA = "b" * 64
INC_TRACE_SHA = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
V2_T = 6
ARMS = (("cap-2.5", 2.5), ("cap-1.5", 1.5), ("cap-1.0", 1.0), ("cap-0.75", 0.75))


def _design(digest: str) -> VecCampaignDesign:
    return VecCampaignDesign(
        experiment_id="vec-analysis-unit",
        research_question="Does capacity reduction degrade deadline success?",
        run_id_prefix="anapilot",
        phase=VecCampaignPhase.PILOT,
        approval=VecCampaignApproval(
            predeclaration_path="predeclaration.md",
            predeclaration_sha256=digest,
            approved_by="A. Owner",
            approved_role="repository owner",
            approved_at_utc="2026-07-26T12:00:00+00:00",
        ),
        trace_file="traces/trace_inc_fullrsu.npz",
        trace_sha256=INC_TRACE_SHA,
        actor_id="baseline_model_c_17",
        fleet="uk2030",
        evaluator_seed=0,
        max_steps=V2_T,
        timeout_seconds=600,
        baseline_arm=VecCampaignArm(label=ARMS[0][0], rsu_capacity_per_vehicle=ARMS[0][1]),
        variation_arms=[
            VecCampaignArm(label=label, rsu_capacity_per_vehicle=capacity)
            for label, capacity in ARMS[1:]
        ],
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        fleet_seeds=[0, 1, 2],
        primary_metric_key="tos.task.deadline_success.rate",
        budget=VecCampaignBudget(max_cells=12, max_total_output_bytes=10_000_000),
    )


def _runner_receipt(run_id: str, fleet_seed: int, capacity: float) -> VecExecutionReceipt:
    request = VecRunRequest(
        run_id=run_id,
        trace_file="traces/synthetic.npz",
        trace_sha256=SYNTHETIC_TRACE_SHA,
        actor_id="baseline_model_c_17",
        fleet_seed=fleet_seed,
        rsu_capacity_per_vehicle=capacity,
        max_steps=V2_T,
        timeout_seconds=600,
    )
    outputs = [
        VecRunnerFileEvidence(
            path="per-step.npz",
            sha256="1" * 64,
            size_bytes=1,
            media_type="application/octet-stream",
            read_only=True,
        )
    ]
    return VecExecutionReceipt(
        status="completed",
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint="c" * 64,
        argv=[],
        started_at_utc="2026-07-26T00:00:00+00:00",
        finished_at_utc="2026-07-26T00:00:01+00:00",
        elapsed_seconds=1.0,
        exit_code=0,
        timed_out=False,
        cancellation_requested=False,
        runtime=VecRuntimeEvidence(
            python="3.12.4",
            numpy="1.26.4",
            jax="0.4.30",
            jaxlib="0.4.30",
            jax_backend="cpu",
            jax_device_count=1,
            platform="test",
            machine="test",
            processor="test",
            environment_sha256="d" * 64,
        ),
        repositories=[],
        inputs_before=[],
        inputs_after=[],
        logs=[],
        stdout_excerpt="",
        stderr_excerpt="",
        outputs=outputs,
        findings=[],
        output_fingerprint=output_fingerprint(outputs),
        external_repositories_modified=False,
        raw_inputs_modified=False,
        published=True,
    )


def _populated_registry(tmp_path: Path, design: VecCampaignDesign) -> list[VecCampaignCell]:
    """Admit 12 synthetic cells whose deadline rate degrades with capacity."""

    registry_path = tmp_path / "registry.sqlite"
    register_campaign_experiment(design, registry_path)
    header, rows = build_v2_occupancy_rows()
    cells: list[VecCampaignCell] = []
    drop_by_arm = {"cap-2.5": None, "cap-1.5": 0, "cap-1.0": 1, "cap-0.75": 2}
    for fleet_seed in design.fleet_seeds:
        for arm in design.arms():
            trace = build_v2_trace()
            perstep = build_v2_perstep()
            pertask = build_v2_pertask()
            drop = drop_by_arm[arm.label]
            if drop is not None:
                met = np.asarray(pertask["task_met"]).copy()
                active = np.asarray(pertask["task_active"], dtype=bool)
                flat = np.flatnonzero(active & met)
                count = min(drop + fleet_seed % 2 + 1, flat.size - 1)
                met.flat[flat[:count]] = False
                pertask["task_met"] = met
                successes = met & active
                perstep["veh_done"] = successes.sum(axis=1).astype(perstep["veh_done"].dtype)
                perstep["done"] = successes.sum(axis=(1, 2)).astype(perstep["done"].dtype)
            identity = build_vehicle_identity_snapshot(trace, header, rows, scenario=V2_SCENARIO)
            runner_receipt = _runner_receipt(
                design.cell_run_id(arm.label, fleet_seed),
                fleet_seed,
                arm.rsu_capacity_per_vehicle,
            )
            record, collection = build_fresh_run_admission(
                trace,
                perstep,
                pertask,
                identity,
                runner_receipt,
                VecFreshRunStudyContext(
                    experiment_id=design.experiment_id,
                    seed_id=arm.label,
                    pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
                    synthetic_fixture=True,
                ),
                computed_at=NOW,
            )
            register_fresh_run_admission(record, collection, registry_path)
            cells.append(
                VecCampaignCell(
                    arm_label=arm.label,
                    fleet_seed=fleet_seed,
                    run_id=runner_receipt.request.run_id,
                    request_fingerprint=runner_receipt.request_fingerprint,
                    state=VecCampaignCellState.ADMITTED,
                    output_directory_name=f"{arm.label}-fs{fleet_seed}",
                    elapsed_seconds=1.0,
                    output_bytes=1,
                    receipt_fingerprint=runner_receipt.fingerprint(),
                    registry_run_id=record.registry_run_id,
                    admission_stable_fingerprint=record.stable_fingerprint(),
                    detail="admitted",
                )
            )
    return cells


def _receipt(design: VecCampaignDesign, cells: list[VecCampaignCell]) -> VecCampaignReceipt:
    return VecCampaignReceipt(
        status=VecCampaignStatus.COMPLETED,
        design_fingerprint=design.fingerprint(),
        experiment_id=design.experiment_id,
        phase=design.phase,
        approval=design.approval,
        predeclaration_verified_unchanged=True,
        experiment_registered=True,
        cells=cells,
        planned_cell_count=len(cells),
        admitted_cell_count=len(cells),
        reused_cell_count=0,
        failed_cell_count=0,
        skipped_cell_count=0,
        total_output_bytes=len(cells),
        total_elapsed_seconds=float(len(cells)),
        started_at_utc=NOW.isoformat(),
        finished_at_utc=NOW.isoformat(),
        limitations=["exploratory synthetic campaign"],
    )


def test_analysis_runs_all_predeclared_comparisons(tmp_path: Path) -> None:
    digest = hashlib.sha256(b"design").hexdigest()
    design = _design(digest)
    cells = _populated_registry(tmp_path, design)
    receipt = _receipt(design, cells)

    analysis = analyze_campaign(design, receipt, tmp_path / "registry.sqlite", generated_at=NOW)

    assert analysis.admitted_collection_count == 12
    assert [row.variation_label for row in analysis.comparisons] == [
        "cap-1.5",
        "cap-1.0",
        "cap-0.75",
    ]
    for row in analysis.comparisons:
        assert row.study_status == "available"
        assert row.admitted_pair_count == 3
        assert row.mean_paired_difference is not None
        assert row.mean_paired_difference < 0
    ordered = {row.arm_label: row.mean for row in analysis.primary_descriptives}
    assert ordered["cap-2.5"] > ordered["cap-1.5"] > ordered["cap-1.0"] > ordered["cap-0.75"]
    assert analysis.confirmatory is False
    assert analysis.significance_claimed is False
    assert analysis.research_status == "owner_approved_candidate"


def test_analysis_report_renders_exploratory_language(tmp_path: Path) -> None:
    digest = hashlib.sha256(b"design").hexdigest()
    design = _design(digest)
    cells = _populated_registry(tmp_path, design)
    analysis = analyze_campaign(
        design, _receipt(design, cells), tmp_path / "registry.sqlite", generated_at=NOW
    )

    report = render_campaign_analysis_markdown(analysis)

    assert "No confirmatory or significance claim" in report
    assert "cap-0.75" in report
    assert "secondary metrics, never promoted" in report
    assert "multiplicity correction" in report
    assert render_campaign_analysis_markdown(analysis) == report


def test_analysis_refuses_wrong_receipt_and_empty_registry(tmp_path: Path) -> None:
    digest = hashlib.sha256(b"design").hexdigest()
    design = _design(digest)
    cells = _populated_registry(tmp_path, design)
    receipt = _receipt(design, cells)

    other = _design(hashlib.sha256(b"other-design").hexdigest())
    with pytest.raises(VecCampaignError, match="ANALYSIS_DESIGN_MISMATCH"):
        analyze_campaign(other, receipt, tmp_path / "registry.sqlite")

    empty = tmp_path / "empty"
    empty.mkdir()
    register_campaign_experiment(design, empty / "registry.sqlite")
    with pytest.raises(VecCampaignError, match="ANALYSIS_NO_ADMITTED_COLLECTIONS"):
        analyze_campaign(design, receipt, empty / "registry.sqlite")


def test_analysis_passes_through_insufficient_status(tmp_path: Path) -> None:
    digest = hashlib.sha256(b"design").hexdigest()
    design = _design(digest)
    cells = _populated_registry(tmp_path, design)
    kept = [cell for cell in cells if not (cell.arm_label == "cap-1.0" and cell.fleet_seed > 0)]
    dropped = [cell for cell in cells if cell not in kept]
    truncated = kept + [
        VecCampaignCell(
            arm_label=cell.arm_label,
            fleet_seed=cell.fleet_seed,
            run_id=cell.run_id,
            request_fingerprint=cell.request_fingerprint,
            state=VecCampaignCellState.EXECUTION_FAILED,
            output_directory_name=cell.output_directory_name,
            detail="synthetic failure for insufficiency test",
        )
        for cell in dropped
    ]
    receipt = VecCampaignReceipt(
        status=VecCampaignStatus.HALTED_ON_FAILURE,
        design_fingerprint=design.fingerprint(),
        experiment_id=design.experiment_id,
        phase=design.phase,
        approval=design.approval,
        predeclaration_verified_unchanged=True,
        experiment_registered=True,
        cells=truncated,
        planned_cell_count=len(truncated),
        admitted_cell_count=len(kept),
        reused_cell_count=0,
        failed_cell_count=len(dropped),
        skipped_cell_count=0,
        total_output_bytes=len(kept),
        total_elapsed_seconds=float(len(kept)),
        started_at_utc=NOW.isoformat(),
        finished_at_utc=NOW.isoformat(),
        limitations=["exploratory synthetic campaign"],
    )

    analysis = analyze_campaign(design, receipt, tmp_path / "registry.sqlite", generated_at=NOW)

    by_label = {row.variation_label: row for row in analysis.comparisons}
    assert by_label["cap-1.5"].study_status == "available"
    assert by_label["cap-1.0"].study_status == "insufficient"
    assert by_label["cap-0.75"].study_status == "available"
