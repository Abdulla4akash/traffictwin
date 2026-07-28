"""Design, approval, budget, resumability, and refusal tests for VEC campaigns."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.domain.experiment import Experiment
from traffictwin.integration.vec_campaign import (
    VecCampaignApproval,
    VecCampaignArm,
    VecCampaignBudget,
    VecCampaignDesign,
    VecCampaignError,
    VecCampaignPhase,
    VecCampaignStatus,
    execute_campaign,
    register_campaign_experiment,
    verify_predeclaration,
)
from traffictwin.integration.vec_fresh_admission import VecPairingSeedSource
from traffictwin.integration.vec_runner.models import VecFleet
from traffictwin.storage.registry import Registry

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
INC_TRACE_SHA = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
INC_TRACE_FILE = "traces/trace_inc_fullrsu.npz"
PREDECLARATION_TEXT = "# Capacity-Squeeze Pilot — Predeclaration\n\nfixed design\n"


def _predeclaration(tmp_path: Path, text: str = PREDECLARATION_TEXT) -> tuple[Path, str]:
    path = tmp_path / "predeclaration.md"
    path.write_text(text, encoding="utf-8")
    return path, hashlib.sha256(text.encode()).hexdigest()


def _approval(digest: str, *, held_out: bool = False) -> VecCampaignApproval:
    return VecCampaignApproval(
        predeclaration_path="predeclaration.md",
        predeclaration_sha256=digest,
        approved_by="A. Owner",
        approved_role="repository owner",
        approved_at_utc="2026-07-26T12:00:00+00:00",
        held_out_authorised=held_out,
    )


def _design(
    digest: str,
    *,
    phase: VecCampaignPhase = VecCampaignPhase.PILOT,
    seeds: list[int] | None = None,
    held_out: bool = False,
    max_cells: int = 12,
    max_bytes: int = 1_000_000_000,
    halt_on_failure: bool = True,
    experiment_id: str = "vec-capacity-pilot",
) -> VecCampaignDesign:
    return VecCampaignDesign(
        experiment_id=experiment_id,
        research_question="Does reduced per-vehicle RSU task capacity degrade deadline success?",
        run_id_prefix="cappilot",
        phase=phase,
        approval=_approval(digest, held_out=held_out),
        trace_file=INC_TRACE_FILE,
        trace_sha256=INC_TRACE_SHA,
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
        fleet_seeds=seeds if seeds is not None else [0, 1, 2],
        primary_metric_key="tos.task.deadline_success.rate",
        budget=VecCampaignBudget(
            max_cells=max_cells,
            max_total_output_bytes=max_bytes,
            halt_on_failure=halt_on_failure,
        ),
    )


def test_design_plans_deterministic_seed_major_cells(tmp_path: Path) -> None:
    _, digest = _predeclaration(tmp_path)
    design = _design(digest)
    arms = design.arms()

    assert [arm.label for arm in arms] == ["cap-2.5", "cap-1.5", "cap-1.0", "cap-0.75"]
    assert design.cell_run_id("cap-1.0", 2) == "cappilot-cap-1.0-fs2"
    request = design.cell_request(arms[2], 2)
    assert request.rsu_capacity_per_vehicle == 1.0
    assert request.fleet_seed == 2
    assert request.max_steps == 3600
    assert design.fingerprint() == _design(digest).fingerprint()


def test_approval_cannot_be_defaulted_or_a_placeholder(tmp_path: Path) -> None:
    _, digest = _predeclaration(tmp_path)
    with pytest.raises(ValidationError):
        VecCampaignApproval(  # type: ignore[call-arg]
            predeclaration_path="predeclaration.md",
            predeclaration_sha256=digest,
        )
    for placeholder in ("TBD", "n/a", "agent", "   "):
        with pytest.raises(ValidationError):
            VecCampaignApproval(
                predeclaration_path="predeclaration.md",
                predeclaration_sha256=digest,
                approved_by=placeholder,
                approved_role="repository owner",
                approved_at_utc="2026-07-26T12:00:00+00:00",
            )


def test_held_out_phase_requires_explicit_authorisation(tmp_path: Path) -> None:
    _, digest = _predeclaration(tmp_path)
    with pytest.raises(ValidationError, match="held_out_authorised"):
        _design(digest, phase=VecCampaignPhase.HELD_OUT, seeds=[10, 11, 12], held_out=False)

    design = _design(digest, phase=VecCampaignPhase.HELD_OUT, seeds=[10, 11, 12], held_out=True)
    assert design.phase is VecCampaignPhase.HELD_OUT


def test_unreviewed_trace_and_duplicate_arms_are_refused(tmp_path: Path) -> None:
    _, digest = _predeclaration(tmp_path)
    with pytest.raises(ValidationError, match="reviewed traces"):
        VecCampaignDesign(
            experiment_id="vec-bad-trace",
            research_question="q",
            run_id_prefix="bad",
            phase=VecCampaignPhase.PILOT,
            approval=_approval(digest),
            trace_file="traces/trace_ev_fullrsu.npz",
            trace_sha256="0" * 63 + "1",
            actor_id="baseline_model_c_17",
            fleet=VecFleet.UK_2030,
            evaluator_seed=0,
            max_steps=3600,
            timeout_seconds=600,
            baseline_arm=VecCampaignArm(label="a", rsu_capacity_per_vehicle=2.5),
            variation_arms=[VecCampaignArm(label="b", rsu_capacity_per_vehicle=1.0)],
            pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
            fleet_seeds=[0, 1, 2],
            primary_metric_key="tos.task.deadline_success.rate",
            budget=VecCampaignBudget(max_cells=6, max_total_output_bytes=1_000),
        )

    with pytest.raises(ValidationError, match="capacities must be distinct"):
        VecCampaignDesign(
            experiment_id="vec-dup-arms",
            research_question="q",
            run_id_prefix="dup",
            phase=VecCampaignPhase.PILOT,
            approval=_approval(digest),
            trace_file=INC_TRACE_FILE,
            trace_sha256=INC_TRACE_SHA,
            actor_id="baseline_model_c_17",
            fleet=VecFleet.UK_2030,
            evaluator_seed=0,
            max_steps=3600,
            timeout_seconds=600,
            baseline_arm=VecCampaignArm(label="a", rsu_capacity_per_vehicle=2.5),
            variation_arms=[VecCampaignArm(label="b", rsu_capacity_per_vehicle=2.5)],
            pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
            fleet_seeds=[0, 1, 2],
            primary_metric_key="tos.task.deadline_success.rate",
            budget=VecCampaignBudget(max_cells=6, max_total_output_bytes=1_000),
        )


def test_design_refuses_to_exceed_its_own_cell_budget(tmp_path: Path) -> None:
    _, digest = _predeclaration(tmp_path)
    with pytest.raises(ValidationError, match="needs 12 cells"):
        _design(digest, max_cells=6)


def test_predeclaration_digest_mismatch_refuses(tmp_path: Path) -> None:
    path, digest = _predeclaration(tmp_path)
    design = _design(digest)
    verify_predeclaration(design, tmp_path)

    path.write_text(PREDECLARATION_TEXT + "edited after approval\n", encoding="utf-8")
    with pytest.raises(VecCampaignError, match="PREDECLARATION_CHANGED_AFTER_APPROVAL"):
        verify_predeclaration(design, tmp_path)

    path.unlink()
    with pytest.raises(VecCampaignError, match="missing or unsafe"):
        verify_predeclaration(design, tmp_path)


def test_experiment_registration_is_idempotent_and_conflict_aware(tmp_path: Path) -> None:
    _, digest = _predeclaration(tmp_path)
    registry_path = tmp_path / "registry.sqlite"
    design = _design(digest)

    assert register_campaign_experiment(design, registry_path) is True
    assert register_campaign_experiment(design, registry_path) is False

    registered = Registry(registry_path).get_experiment("vec-capacity-pilot")
    assert registered.baseline_seed_id == "cap-2.5"
    assert registered.common_random_seed_set == [0, 1, 2]
    assert registered.algorithms == ["ukfleettrain_mappo_model_c_17"]

    conflicting = _design(digest, seeds=[7, 8, 9])
    with pytest.raises(VecCampaignError, match="EXPERIMENT_PLAN_CONFLICT"):
        register_campaign_experiment(conflicting, registry_path)


def test_registered_plan_supplies_sta01_pairing_inputs(tmp_path: Path) -> None:
    _, digest = _predeclaration(tmp_path)
    registry_path = tmp_path / "registry.sqlite"
    design = _design(digest)
    register_campaign_experiment(design, registry_path)

    plan: Experiment = Registry(registry_path).get_experiment(design.experiment_id)
    assert plan.baseline_seed_id in {arm.label for arm in design.arms()}
    for variation in plan.variation_seed_ids:
        assert variation != plan.baseline_seed_id
    assert len(plan.common_random_seed_set) >= 3


def test_refused_campaign_admits_nothing_and_records_every_cell(tmp_path: Path) -> None:
    path, digest = _predeclaration(tmp_path)
    design = _design(digest)
    path.write_text("tampered\n", encoding="utf-8")

    receipt = execute_campaign(
        design,
        input_root=tmp_path,
        vec_repo=tmp_path,
        tos_data_repo=tmp_path,
        output_root=tmp_path / "out",
        registry_path=tmp_path / "registry.sqlite",
        predeclaration_root=tmp_path,
        clock=lambda: NOW,
    )

    assert receipt.status is VecCampaignStatus.REFUSED
    assert receipt.admitted_cell_count == 0
    assert receipt.reused_cell_count == 0
    assert receipt.planned_cell_count == 12
    assert len(receipt.cells) == 12
    assert receipt.predeclaration_verified_unchanged is False
    assert receipt.experiment_registered is False
    assert receipt.background_execution is False
    assert receipt.concurrent_execution is False
    assert receipt.scientific_conclusion_recorded is False
    assert any("PREDECLARATION_CHANGED_AFTER_APPROVAL" in item for item in receipt.findings)
    assert not (tmp_path / "registry.sqlite").exists()


def test_execution_failure_halts_and_marks_remaining_cells(tmp_path: Path) -> None:
    _, digest = _predeclaration(tmp_path)
    design = _design(digest)

    receipt = execute_campaign(
        design,
        input_root=tmp_path / "missing-input-root",
        vec_repo=tmp_path / "missing-vec-repo",
        tos_data_repo=tmp_path / "missing-tos-data",
        output_root=tmp_path / "out",
        registry_path=tmp_path / "registry.sqlite",
        predeclaration_root=tmp_path,
        clock=lambda: NOW,
    )

    assert receipt.status is VecCampaignStatus.HALTED_ON_FAILURE
    assert receipt.admitted_cell_count == 0
    assert receipt.failed_cell_count == 1
    assert receipt.skipped_cell_count == 11
    assert receipt.cells[0].state.value == "execution_failed"
    assert all(cell.registry_run_id is None for cell in receipt.cells)
    assert receipt.experiment_registered is True
