"""Bounded, resumable, sequential execution of one predeclared VEC campaign.

The service composes accepted services in one order and adds nothing
scientific of its own: verify the approved predeclaration is unchanged,
register the declared experiment plan, then for each declared cell run the
VEC-07 evaluator in the foreground and admit its published result through the
ADR-061 fresh-run policy. It computes no metric, chooses no threshold, and
writes no conclusion.

Execution is deliberately serial and in-process. There is no background job,
detached process, persistent queue, scheduler, or concurrency here — those
remain prohibited by the accepted VEC-10 boundary, and a long campaign is
therefore a long foreground operation that can be interrupted and resumed
rather than a service that outlives its caller.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.domain.enums import ExperimentStatus
from traffictwin.domain.experiment import Experiment
from traffictwin.integration.vec_campaign.models import (
    VecCampaignArm,
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignDesign,
    VecCampaignReceipt,
    VecCampaignStatus,
)
from traffictwin.integration.vec_fresh_admission import (
    VecFreshAdmissionError,
    VecFreshRunStudyContext,
    admit_vec_fresh_run,
)
from traffictwin.integration.vec_runner import (
    VecExecutionReceipt,
    VecRunnerError,
    VecTerminalStatus,
    run_vec_evaluator,
)
from traffictwin.storage.registry import DuplicateIdentifierError, Registry, RegistryError

_RECEIPT_FILE = "execution_receipt.json"
_HASH_CHUNK_BYTES = 1024 * 1024

STANDING_CAMPAIGN_LIMITATIONS = (
    "A campaign executes a predeclared design; completing it is not a scientific "
    "finding, an accepted threshold, or supervisor approval.",
    "Execution is sequential and foreground only; no background queue, detached "
    "process, scheduler, or concurrency is introduced.",
    "Every admitted cell remains an owner-approved candidate fresh-run admission "
    "with reproduction explicitly ungraded.",
    "A failed cell is recorded and never retried with altered controls; missing "
    "cells stay missing rather than being imputed.",
)


class VecCampaignError(RuntimeError):
    """Raised when a campaign cannot be started safely."""


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def verify_predeclaration(design: VecCampaignDesign, predeclaration_root: Path) -> None:
    """Refuse unless the approved predeclaration file is present and unchanged.

    The digest recorded at approval time is compared against the file on disk,
    so a design that was edited after it was approved cannot execute under the
    old approval.
    """

    approval = design.approval
    candidate = Path(approval.predeclaration_path)
    path = candidate if candidate.is_absolute() else predeclaration_root / candidate
    if path.is_symlink() or not path.is_file():
        raise VecCampaignError(
            f"approved predeclaration is missing or unsafe: {approval.predeclaration_path}"
        )
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    if digest.hexdigest() != approval.predeclaration_sha256:
        raise VecCampaignError(
            "PREDECLARATION_CHANGED_AFTER_APPROVAL: the approved document digest does "
            "not match the file on disk; re-approve the current design before running"
        )


def register_campaign_experiment(design: VecCampaignDesign, registry_path: str | Path) -> bool:
    """Register the declared experiment plan idempotently.

    Returns True when the plan was newly registered. An existing plan under the
    same identifier is accepted only when its arms and common seed set match the
    design exactly, so a campaign cannot quietly attach to a different plan.
    """

    registry = Registry(Path(registry_path))
    now = _utc_now()
    experiment = Experiment(
        experiment_id=design.experiment_id,
        research_question=design.research_question,
        baseline_seed_id=design.baseline_arm.label,
        variation_seed_ids=[arm.label for arm in design.variation_arms],
        algorithms=[design.actor_id],
        common_random_seed_set=list(design.fleet_seeds),
        planned_replicates=len(design.fleet_seeds),
        status=ExperimentStatus.PLANNED,
        created_at=now,
        updated_at=now,
    )
    try:
        registry.add_experiment(experiment)
    except DuplicateIdentifierError as duplicate:
        try:
            existing = registry.get_experiment(design.experiment_id)
        except RegistryError as exc:
            raise VecCampaignError(
                f"experiment {design.experiment_id} exists but could not be read"
            ) from exc
        mismatches = []
        if existing.baseline_seed_id != experiment.baseline_seed_id:
            mismatches.append("baseline arm")
        if sorted(existing.variation_seed_ids) != sorted(experiment.variation_seed_ids):
            mismatches.append("variation arms")
        if sorted(existing.common_random_seed_set) != sorted(experiment.common_random_seed_set):
            mismatches.append("common seed set")
        if sorted(existing.algorithms) != sorted(experiment.algorithms):
            mismatches.append("algorithms")
        if mismatches:
            raise VecCampaignError(
                "EXPERIMENT_PLAN_CONFLICT: the registered plan differs from this design "
                f"({', '.join(mismatches)}); use a new experiment_id"
            ) from duplicate
        return False
    return True


def execute_campaign(
    design: VecCampaignDesign,
    *,
    input_root: str | Path,
    vec_repo: str | Path,
    tos_data_repo: str | Path,
    output_root: str | Path,
    registry_path: str | Path,
    predeclaration_root: str | Path = Path(),
    clock: Callable[[], datetime] = _utc_now,
) -> VecCampaignReceipt:
    """Execute one approved campaign sequentially and return its receipt.

    Cells are ordered seed-major so that an interrupted campaign still holds
    complete arm coverage for the seeds it finished, which is what the paired
    study needs; an arm-major order would leave every seed half-populated.
    """

    started = clock()
    findings: list[str] = []
    try:
        verify_predeclaration(design, Path(predeclaration_root))
        experiment_registered = register_campaign_experiment(design, registry_path)
    except VecCampaignError as exc:
        refused_cells = [
            _skipped_cell(design, arm, seed, VecCampaignCellState.SKIPPED_HALTED, str(exc))
            for seed in design.fleet_seeds
            for arm in design.arms()
        ]
        return _receipt(
            design,
            VecCampaignStatus.REFUSED,
            refused_cells,
            predeclaration_verified_unchanged=False,
            experiment_registered=False,
            started=started,
            finished=clock(),
            findings=[str(exc)],
        )

    output_base = Path(output_root)
    output_base.mkdir(parents=True, exist_ok=True)
    cells: list[VecCampaignCell] = []
    total_bytes = 0
    halted = False
    budget_exhausted = False

    for fleet_seed in design.fleet_seeds:
        for arm in design.arms():
            if halted or budget_exhausted:
                state = (
                    VecCampaignCellState.SKIPPED_BUDGET
                    if budget_exhausted
                    else VecCampaignCellState.SKIPPED_HALTED
                )
                reason = (
                    "output budget exhausted before this cell"
                    if budget_exhausted
                    else "a prior cell failed and halt_on_failure is set"
                )
                cells.append(_skipped_cell(design, arm, fleet_seed, state, reason))
                continue

            request = design.cell_request(arm, fleet_seed)
            directory_name = f"{arm.label}-fs{fleet_seed}"
            cell_dir = output_base / directory_name
            reused = _completed_receipt(cell_dir, request.fingerprint())
            receipt: VecExecutionReceipt | None = reused

            if receipt is None:
                try:
                    receipt = run_vec_evaluator(
                        input_root, vec_repo, tos_data_repo, cell_dir, request
                    )
                except (VecRunnerError, OSError) as exc:
                    detail = f"execution did not complete: {exc}"
                    findings.append(f"{directory_name}: {detail}")
                    cells.append(
                        VecCampaignCell(
                            arm_label=arm.label,
                            fleet_seed=fleet_seed,
                            run_id=request.run_id,
                            request_fingerprint=request.fingerprint(),
                            state=VecCampaignCellState.EXECUTION_FAILED,
                            output_directory_name=directory_name,
                            detail=detail[:2_000],
                        )
                    )
                    halted = design.budget.halt_on_failure
                    continue

            cell_bytes = sum(item.size_bytes for item in receipt.outputs)
            if total_bytes + cell_bytes > design.budget.max_total_output_bytes:
                detail = (
                    f"cell output of {cell_bytes} bytes would exceed the declared "
                    f"{design.budget.max_total_output_bytes}-byte campaign budget"
                )
                findings.append(f"{directory_name}: {detail}")
                cells.append(
                    _skipped_cell(
                        design,
                        arm,
                        fleet_seed,
                        VecCampaignCellState.SKIPPED_BUDGET,
                        detail,
                    )
                )
                budget_exhausted = True
                continue

            try:
                record, outcome = admit_vec_fresh_run(
                    cell_dir,
                    registry_path,
                    VecFreshRunStudyContext(
                        experiment_id=design.experiment_id,
                        seed_id=arm.label,
                        pairing_seed_source=design.pairing_seed_source,
                    ),
                    tos_data_repo=tos_data_repo,
                    clock=clock,
                )
            except (VecFreshAdmissionError, RegistryError, OSError) as exc:
                detail = f"admission refused: {exc}"
                findings.append(f"{directory_name}: {detail}")
                cells.append(
                    VecCampaignCell(
                        arm_label=arm.label,
                        fleet_seed=fleet_seed,
                        run_id=request.run_id,
                        request_fingerprint=request.fingerprint(),
                        state=VecCampaignCellState.ADMISSION_REFUSED,
                        output_directory_name=directory_name,
                        elapsed_seconds=receipt.elapsed_seconds,
                        output_bytes=cell_bytes,
                        receipt_fingerprint=receipt.fingerprint(),
                        detail=detail[:2_000],
                    )
                )
                halted = design.budget.halt_on_failure
                continue

            total_bytes += cell_bytes
            cells.append(
                VecCampaignCell(
                    arm_label=arm.label,
                    fleet_seed=fleet_seed,
                    run_id=request.run_id,
                    request_fingerprint=request.fingerprint(),
                    state=(
                        VecCampaignCellState.REUSED
                        if reused is not None
                        else VecCampaignCellState.ADMITTED
                    ),
                    output_directory_name=directory_name,
                    elapsed_seconds=receipt.elapsed_seconds,
                    output_bytes=cell_bytes,
                    receipt_fingerprint=receipt.fingerprint(),
                    registry_run_id=outcome.registry_run_id,
                    admission_stable_fingerprint=record.stable_fingerprint(),
                    detail=(
                        "reused an intact published result and confirmed its admission"
                        if reused is not None
                        else f"executed in {receipt.elapsed_seconds:.3f}s and admitted"
                    ),
                )
            )

    any_failure = any(
        cell.state
        in {VecCampaignCellState.EXECUTION_FAILED, VecCampaignCellState.ADMISSION_REFUSED}
        for cell in cells
    )
    if budget_exhausted:
        status = VecCampaignStatus.HALTED_ON_BUDGET
    elif halted or any_failure:
        status = VecCampaignStatus.HALTED_ON_FAILURE
    else:
        status = VecCampaignStatus.COMPLETED

    return _receipt(
        design,
        status,
        cells,
        predeclaration_verified_unchanged=True,
        experiment_registered=experiment_registered,
        started=started,
        finished=clock(),
        findings=findings,
    )


def _completed_receipt(cell_dir: Path, request_fingerprint: str) -> VecExecutionReceipt | None:
    """Return an intact completed receipt for this exact request, if present."""

    path = cell_dir / _RECEIPT_FILE
    if path.is_symlink() or not path.is_file():
        return None
    try:
        receipt = VecExecutionReceipt.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if receipt.status is not VecTerminalStatus.COMPLETED:
        return None
    if receipt.request_fingerprint != request_fingerprint:
        return None
    return receipt


def _skipped_cell(
    design: VecCampaignDesign,
    arm: VecCampaignArm,
    fleet_seed: int,
    state: VecCampaignCellState,
    detail: str,
) -> VecCampaignCell:
    request = design.cell_request(arm, fleet_seed)
    return VecCampaignCell(
        arm_label=arm.label,
        fleet_seed=fleet_seed,
        run_id=request.run_id,
        request_fingerprint=request.fingerprint(),
        state=state,
        output_directory_name=f"{arm.label}-fs{fleet_seed}",
        detail=detail[:2_000] or "skipped",
    )


def _receipt(
    design: VecCampaignDesign,
    status: VecCampaignStatus,
    cells: list[VecCampaignCell],
    *,
    predeclaration_verified_unchanged: bool,
    experiment_registered: bool,
    started: datetime,
    finished: datetime,
    findings: list[str],
) -> VecCampaignReceipt:
    states = [cell.state for cell in cells]
    return VecCampaignReceipt(
        status=status,
        design_fingerprint=design.fingerprint(),
        experiment_id=design.experiment_id,
        phase=design.phase,
        approval=design.approval,
        predeclaration_verified_unchanged=predeclaration_verified_unchanged,
        experiment_registered=experiment_registered,
        cells=cells,
        planned_cell_count=len(cells),
        admitted_cell_count=states.count(VecCampaignCellState.ADMITTED),
        reused_cell_count=states.count(VecCampaignCellState.REUSED),
        failed_cell_count=(
            states.count(VecCampaignCellState.EXECUTION_FAILED)
            + states.count(VecCampaignCellState.ADMISSION_REFUSED)
        ),
        skipped_cell_count=(
            states.count(VecCampaignCellState.SKIPPED_BUDGET)
            + states.count(VecCampaignCellState.SKIPPED_HALTED)
        ),
        total_output_bytes=sum(cell.output_bytes or 0 for cell in cells),
        total_elapsed_seconds=sum(cell.elapsed_seconds or 0.0 for cell in cells),
        started_at_utc=started.isoformat(),
        finished_at_utc=finished.isoformat(),
        findings=findings[:64],
        limitations=list(STANDING_CAMPAIGN_LIMITATIONS),
    )
