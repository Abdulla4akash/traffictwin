"""Unit coverage for the confirmatory-mode campaign report renderer.

Every design, receipt, and analysis here is built in memory. Nothing reads a
registry, opens a campaign directory, imports the campaign service, or touches
the live campaign's data.

The fleet seeds used below are deliberately ordinary integers. The reserved
confirmatory cohort belongs to the campaign the owner authorised, and no test
needs to name it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collections,
)
from traffictwin.experiments import evaluate_paired_statistical_study
from traffictwin.integration.vec_campaign.analysis import VecCampaignAnalysis
from traffictwin.integration.vec_campaign.confirmatory_report import (
    ConfirmatoryReportError,
    render_confirmatory_report,
)
from traffictwin.integration.vec_campaign.models import (
    VecCampaignApproval,
    VecCampaignArm,
    VecCampaignBudget,
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignDesign,
    VecCampaignPhase,
    VecCampaignReceipt,
    VecCampaignStatus,
)
from traffictwin.integration.vec_fresh_admission.models import VecPairingSeedSource
from traffictwin.integration.vec_runner.models import VecFleet

DIGEST = "b" * 64
OTHER_DIGEST = "c" * 64
CELL_FINGERPRINT = "d" * 64
BASELINE_ARM = "cap-2.5"
VARIATION_ARM = "cap-0.75"
PRIMARY_METRIC = "tos.task.deadline_success.rate"
COHORT_SEEDS = [90, 91, 92]


def _approval(
    *, digest: str = DIGEST, held_out: bool = True, approved_by: str = "A. Owner"
) -> VecCampaignApproval:
    return VecCampaignApproval(
        predeclaration_path="docs/evaluation/synthetic_confirmatory_protocol.md",
        predeclaration_sha256=digest,
        approved_by=approved_by,
        approved_role="repository owner",
        approved_at_utc="2026-07-27T18:00:00+00:00",
        held_out_authorised=held_out,
    )


def _design(
    *,
    phase: VecCampaignPhase = VecCampaignPhase.HELD_OUT,
    approval: VecCampaignApproval | None = None,
    variation_arms: list[VecCampaignArm] | None = None,
    primary_metric_key: str = PRIMARY_METRIC,
) -> VecCampaignDesign:
    return VecCampaignDesign(
        experiment_id="vec-capacity-confirmatory",
        research_question=(
            "Does the predeclared reduced per-vehicle RSU task capacity move the primary "
            "endpoint on the reserved cohort?"
        ),
        run_id_prefix="capconf",
        phase=phase,
        approval=approval if approval is not None else _approval(),
        trace_file="traces/trace_inc_fullrsu.npz",
        trace_sha256="e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
        actor_id="ukfleettrain_mappo_model_c_17",
        fleet=VecFleet.UK_2030,
        evaluator_seed=0,
        max_steps=3600,
        timeout_seconds=7200,
        baseline_arm=VecCampaignArm(label=BASELINE_ARM, rsu_capacity_per_vehicle=2.5),
        variation_arms=(
            variation_arms
            if variation_arms is not None
            else [VecCampaignArm(label=VARIATION_ARM, rsu_capacity_per_vehicle=0.75)]
        ),
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        fleet_seeds=list(COHORT_SEEDS),
        primary_metric_key=primary_metric_key,
        budget=VecCampaignBudget(max_cells=12, max_total_output_bytes=1_000_000_000),
    )


def _cell(arm_label: str, seed: int, state: VecCampaignCellState) -> VecCampaignCell:
    admitted = state in {VecCampaignCellState.ADMITTED, VecCampaignCellState.REUSED}
    return VecCampaignCell(
        arm_label=arm_label,
        fleet_seed=seed,
        run_id=f"capconf-{arm_label}-fs{seed}",
        request_fingerprint=CELL_FINGERPRINT,
        state=state,
        output_directory_name=f"capconf-{arm_label}-fs{seed}",
        elapsed_seconds=120.0,
        output_bytes=4096,
        receipt_fingerprint=CELL_FINGERPRINT if admitted else None,
        registry_run_id=f"capconf-{arm_label}-fs{seed}" if admitted else None,
        admission_stable_fingerprint=CELL_FINGERPRINT if admitted else None,
        detail="synthetic cell",
    )


def _receipt(
    design: VecCampaignDesign,
    *,
    status: VecCampaignStatus = VecCampaignStatus.COMPLETED,
    verified: bool = True,
    approval: VecCampaignApproval | None = None,
    cell_states: list[VecCampaignCellState] | None = None,
    design_fingerprint: str | None = None,
    experiment_id: str | None = None,
) -> VecCampaignReceipt:
    arms = [arm.label for arm in design.arms()]
    planned = [(arm, seed) for arm in arms for seed in design.fleet_seeds]
    states = cell_states or [VecCampaignCellState.ADMITTED] * len(planned)
    cells = [_cell(arm, seed, state) for (arm, seed), state in zip(planned, states, strict=True)]
    admitted = sum(1 for cell in cells if cell.state is VecCampaignCellState.ADMITTED)
    reused = sum(1 for cell in cells if cell.state is VecCampaignCellState.REUSED)
    failed = sum(
        1
        for cell in cells
        if cell.state
        in {VecCampaignCellState.EXECUTION_FAILED, VecCampaignCellState.ADMISSION_REFUSED}
    )
    skipped = sum(
        1
        for cell in cells
        if cell.state in {VecCampaignCellState.SKIPPED_BUDGET, VecCampaignCellState.SKIPPED_HALTED}
    )
    return VecCampaignReceipt(
        status=status,
        design_fingerprint=design_fingerprint or design.fingerprint(),
        experiment_id=experiment_id or design.experiment_id,
        phase=design.phase,
        approval=approval if approval is not None else design.approval,
        predeclaration_verified_unchanged=verified,
        experiment_registered=True,
        cells=cells,
        planned_cell_count=len(cells),
        admitted_cell_count=admitted,
        reused_cell_count=reused,
        failed_cell_count=failed,
        skipped_cell_count=skipped,
        total_output_bytes=4096 * len(cells),
        total_elapsed_seconds=120.0 * len(cells),
        started_at_utc="2026-07-27T18:05:00+00:00",
        finished_at_utc="2026-07-27T20:05:00+00:00",
        limitations=["Synthetic campaign fixture."],
    )


def _study() -> dict[str, Any]:
    """Build a real STA-01 artifact so the fixture cannot drift from the tool."""

    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0, 3.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    payload: dict[str, Any] = json.loads(study.model_dump_json())
    return payload


def _descriptive(arm: str, metric: str, seed_values: dict[str, float]) -> dict[str, Any]:
    values = list(seed_values.values())
    return {
        "arm_label": arm,
        "metric_key": metric,
        "seed_values": seed_values,
        "mean": sum(values) / len(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def _analysis(
    design: VecCampaignDesign,
    *,
    mean_paired_difference: float | None = -0.0312,
    bootstrap_lower: float | None = -0.0450,
    bootstrap_upper: float | None = -0.0180,
    randomisation_p_value: float | None = 0.0625,
    study_status: str = "available",
    campaign_status: str = "completed",
    **overrides: object,
) -> VecCampaignAnalysis:
    payload: dict[str, Any] = {
        "experiment_id": design.experiment_id,
        "design_fingerprint": design.fingerprint(),
        "campaign_status": campaign_status,
        "primary_metric_key": design.primary_metric_key,
        "baseline_label": design.baseline_arm.label,
        "admitted_collection_count": 6,
        "comparisons": [
            {
                "variation_label": design.variation_arms[0].label,
                "study_status": study_status,
                "admitted_pair_count": 3,
                "mean_paired_difference": mean_paired_difference,
                "bootstrap_lower": bootstrap_lower,
                "bootstrap_upper": bootstrap_upper,
                "randomisation_p_value": randomisation_p_value,
                "study": _study(),
            }
        ],
        "primary_descriptives": [
            _descriptive(BASELINE_ARM, PRIMARY_METRIC, {"90": 0.790, "91": 0.791, "92": 0.792}),
            _descriptive(VARIATION_ARM, PRIMARY_METRIC, {"90": 0.759, "91": 0.760, "92": 0.761}),
        ],
        "secondary_descriptives": [
            _descriptive(
                BASELINE_ARM, "task.latency.mean_ms", {"90": 9000.0, "91": 6000.0, "92": 13000.0}
            ),
            _descriptive(
                VARIATION_ARM, "task.latency.mean_ms", {"90": 14000.0, "91": 9000.0, "92": 20000.0}
            ),
        ],
        "generated_at_utc": "2026-07-27T20:10:00+00:00",
        "limitations": ["Exploratory harness limitation carried forward."],
    }
    payload.update(overrides)
    return VecCampaignAnalysis.model_validate(payload)


def _render(
    *,
    design: VecCampaignDesign | None = None,
    receipt: VecCampaignReceipt | None = None,
    analysis: VecCampaignAnalysis | None = None,
    predeclaration_sha256: str = DIGEST,
) -> str:
    resolved_design = design if design is not None else _design()
    return render_confirmatory_report(
        resolved_design,
        receipt if receipt is not None else _receipt(resolved_design),
        analysis if analysis is not None else _analysis(resolved_design),
        predeclaration_sha256=predeclaration_sha256,
    )


def _headings(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("#")]


def test_the_report_cites_the_signed_predeclaration_and_the_design_fingerprint() -> None:
    design = _design()
    markdown = _render(design=design)

    assert "docs/evaluation/synthetic_confirmatory_protocol.md" in markdown
    assert DIGEST in markdown
    assert design.fingerprint() in markdown
    assert "Held-out cohort authorised: True" in markdown
    assert "Verified unchanged at execution: True" in markdown


def test_exactly_one_contrast_is_presented_as_the_confirmatory_result() -> None:
    markdown = _render()

    assert "## The confirmatory result" in markdown
    assert f"`{VARIATION_ARM}` against baseline arm `{BASELINE_ARM}`" in markdown
    assert "| Estimate (variation − baseline) | -0.031200 |" in markdown
    assert "| Bootstrap interval | [-0.045000, -0.018000] |" in markdown
    assert "| Randomisation p-value | 0.0625 |" in markdown
    assert "| Effect direction | variation below baseline |" in markdown


def test_every_other_number_is_labelled_descriptive_context() -> None:
    markdown = _render()

    assert "## Descriptive context (not the confirmatory result)" in markdown
    assert "descriptive, never promoted" in markdown
    # The secondary latency values live only under the descriptive heading.
    descriptive_start = markdown.index("## Descriptive context")
    execution_start = markdown.index("## Campaign execution evidence")
    assert "task.latency.mean_ms" in markdown[descriptive_start:execution_start]
    assert "task.latency.mean_ms" not in markdown[:descriptive_start]


def test_a_null_result_renders_with_identical_sections_and_prominence() -> None:
    """The publishable-null commitment only means something if the layout is the same."""

    design = _design()
    signal = _render(design=design, analysis=_analysis(design))
    null = _render(
        design=design,
        analysis=_analysis(
            design,
            mean_paired_difference=0.0,
            bootstrap_lower=-0.0121,
            bootstrap_upper=0.0119,
            randomisation_p_value=1.0,
        ),
    )

    assert _headings(null) == _headings(signal)
    assert null.index("## The confirmatory result") == signal.index("## The confirmatory result")
    assert "| Effect direction | no difference in the estimate |" in null
    assert "| Estimate (variation − baseline) | 0.000000 |" in null


def test_a_reversed_result_renders_with_identical_sections_and_prominence() -> None:
    design = _design()
    signal = _render(design=design, analysis=_analysis(design))
    reversed_result = _render(
        design=design,
        analysis=_analysis(
            design,
            mean_paired_difference=0.0412,
            bootstrap_lower=0.0210,
            bootstrap_upper=0.0620,
            randomisation_p_value=0.0625,
        ),
    )

    assert _headings(reversed_result) == _headings(signal)
    assert "| Effect direction | variation above baseline |" in reversed_result


def test_an_unevaluable_study_renders_rather_than_disappearing() -> None:
    design = _design()
    markdown = _render(
        design=design,
        analysis=_analysis(
            design,
            study_status="insufficient",
            mean_paired_difference=None,
            bootstrap_lower=None,
            bootstrap_upper=None,
            randomisation_p_value=None,
        ),
    )

    assert _headings(markdown) == _headings(_render(design=design))
    assert "| STA-01 study status | `insufficient` |" in markdown
    assert "| Estimate (variation − baseline) | unavailable |" in markdown
    assert "| Effect direction | unavailable — the study did not produce an estimate |" in markdown


def test_the_ceiling_is_owner_approved_candidate_and_approval_is_never_claimed() -> None:
    markdown = _render()

    assert "`owner_approved_candidate`" in markdown
    assert "not supervisor approval" in markdown
    assert (
        "It does not claim supervisor approval, ethics approval, or scientific validation."
        in markdown
    )
    for forbidden in ("scientifically_validated", "ground truth", "supervisor-approved"):
        assert forbidden not in markdown


def test_no_significance_language_beyond_sta01_outputs() -> None:
    markdown = _render()
    lowered = markdown.lower()

    assert "statistically significant" not in lowered
    assert "proves" not in lowered
    assert "confirms that" not in lowered
    # The word appears only where the report refuses to make the claim.
    for line in markdown.splitlines():
        if "significant" in line.lower():
            assert "does not declare" in line.lower()


def test_a_pilot_phase_design_is_refused() -> None:
    design = _design(phase=VecCampaignPhase.PILOT, approval=_approval(held_out=False))

    with pytest.raises(ConfirmatoryReportError, match="NOT_HELD_OUT_PHASE"):
        _render(design=design, receipt=_receipt(design), analysis=_analysis(design))


def test_a_mismatched_predeclaration_digest_is_refused() -> None:
    with pytest.raises(ConfirmatoryReportError, match="PREDECLARATION_DIGEST_MISMATCH"):
        _render(predeclaration_sha256=OTHER_DIGEST)


def test_a_malformed_predeclaration_digest_is_refused() -> None:
    with pytest.raises(ConfirmatoryReportError, match="PREDECLARATION_DIGEST_MALFORMED"):
        _render(predeclaration_sha256="not-a-digest")


def test_a_receipt_for_another_design_is_refused() -> None:
    design = _design()
    receipt = _receipt(design, design_fingerprint="e" * 64)

    with pytest.raises(ConfirmatoryReportError, match="RECEIPT_DESIGN_MISMATCH"):
        _render(design=design, receipt=receipt)


def test_a_receipt_recording_a_different_approval_is_refused() -> None:
    design = _design()
    receipt = _receipt(design, approval=_approval(approved_by="Someone Else"))

    with pytest.raises(ConfirmatoryReportError, match="RECEIPT_APPROVAL_MISMATCH"):
        _render(design=design, receipt=receipt)


def test_an_unverified_predeclaration_is_refused() -> None:
    design = _design()

    with pytest.raises(ConfirmatoryReportError, match="PREDECLARATION_NOT_VERIFIED"):
        _render(design=design, receipt=_receipt(design, verified=False))


def test_an_incomplete_campaign_is_refused() -> None:
    design = _design()
    states = [VecCampaignCellState.ADMITTED] * 5 + [VecCampaignCellState.SKIPPED_HALTED]
    receipt = _receipt(design, status=VecCampaignStatus.HALTED_ON_BUDGET, cell_states=states)

    with pytest.raises(ConfirmatoryReportError, match="CAMPAIGN_NOT_COMPLETED"):
        _render(
            design=design,
            receipt=receipt,
            analysis=_analysis(design, campaign_status="halted_on_budget"),
        )


def test_skipped_cells_are_refused_even_when_the_status_reads_completed() -> None:
    """A completed status with a skipped cell is still an incomplete declared matrix."""

    design = _design()
    states = [VecCampaignCellState.ADMITTED] * 5 + [VecCampaignCellState.SKIPPED_BUDGET]
    receipt = _receipt(design, cell_states=states)

    with pytest.raises(ConfirmatoryReportError, match="CAMPAIGN_HAS_SKIPPED_CELLS"):
        _render(design=design, receipt=receipt)


def test_an_analysis_bound_to_another_design_is_refused() -> None:
    design = _design()
    analysis = _analysis(design, design_fingerprint="f" * 64)

    with pytest.raises(ConfirmatoryReportError, match="ANALYSIS_DESIGN_MISMATCH"):
        _render(design=design, analysis=analysis)


def test_an_analysis_from_a_different_campaign_run_is_refused() -> None:
    design = _design()

    with pytest.raises(ConfirmatoryReportError, match="ANALYSIS_RECEIPT_MISMATCH"):
        _render(design=design, analysis=_analysis(design, campaign_status="halted_on_failure"))


def test_an_analysis_of_a_different_primary_endpoint_is_refused() -> None:
    design = _design()
    analysis = _analysis(design, primary_metric_key="task.latency.mean_ms")

    with pytest.raises(ConfirmatoryReportError, match="PRIMARY_METRIC_MISMATCH"):
        _render(design=design, analysis=analysis)


def test_a_multi_arm_design_is_refused_rather_than_having_one_arm_chosen() -> None:
    design = _design(
        variation_arms=[
            VecCampaignArm(label=VARIATION_ARM, rsu_capacity_per_vehicle=0.75),
            VecCampaignArm(label="cap-1.0", rsu_capacity_per_vehicle=1.0),
        ]
    )

    with pytest.raises(ConfirmatoryReportError, match="NOT_A_SINGLE_CONTRAST"):
        _render(design=design, receipt=_receipt(design), analysis=_analysis(design))


def test_an_analysis_comparing_a_different_arm_is_refused() -> None:
    design = _design()
    analysis = _analysis(design)
    payload = analysis.model_dump(mode="json")
    payload["comparisons"][0]["variation_label"] = "cap-1.0"

    with pytest.raises(ConfirmatoryReportError, match="CONTRAST_ARM_MISMATCH"):
        _render(design=design, analysis=VecCampaignAnalysis.model_validate(payload))


def test_the_report_states_why_an_exploratory_typed_analysis_can_be_confirmatory() -> None:
    markdown = _render()

    assert "`confirmatory: false`" in markdown
    assert "running the harness is not what makes" in markdown


def test_rendering_is_deterministic() -> None:
    design = _design()
    receipt = _receipt(design)
    analysis = _analysis(design)

    first = render_confirmatory_report(design, receipt, analysis, predeclaration_sha256=DIGEST)
    second = render_confirmatory_report(design, receipt, analysis, predeclaration_sha256=DIGEST)
    assert first == second
