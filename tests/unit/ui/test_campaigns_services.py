"""Unit coverage for the read-only campaign receipt loader.

Every receipt here is written into ``tmp_path``. Nothing reads a real campaign
directory, opens a registry, or names the reserved confirmatory seed cohort.
"""

from __future__ import annotations

import json
from pathlib import Path

from traffictwin.integration.vec_campaign.models import (
    VecCampaignApproval,
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignPhase,
    VecCampaignReceipt,
    VecCampaignStatus,
)
from traffictwin.ui.campaigns_services import (
    MAX_RECEIPT_BYTES,
    CampaignReceiptView,
    CampaignsError,
    approval_rows,
    arm_summaries,
    budget_usage,
    cell_rows,
    declared_seeds,
    identity_rows,
    load_campaign_receipt,
    phase_badges,
)

FINGERPRINT = "a" * 64
DIGEST = "b" * 64


def _cell(arm: str, seed: int, state: VecCampaignCellState) -> VecCampaignCell:
    admitted = state in {VecCampaignCellState.ADMITTED, VecCampaignCellState.REUSED}
    return VecCampaignCell(
        arm_label=arm,
        fleet_seed=seed,
        run_id=f"synth-{arm}-fs{seed}",
        request_fingerprint=FINGERPRINT,
        state=state,
        output_directory_name=f"synth-{arm}-fs{seed}",
        elapsed_seconds=61.5,
        output_bytes=2048,
        receipt_fingerprint=FINGERPRINT if admitted else None,
        registry_run_id=f"synth-{arm}-fs{seed}" if admitted else None,
        admission_stable_fingerprint=FINGERPRINT if admitted else None,
        detail=f"synthetic {state.value} cell",
    )


def _receipt(
    *,
    status: VecCampaignStatus = VecCampaignStatus.COMPLETED,
    phase: VecCampaignPhase = VecCampaignPhase.PILOT,
    held_out: bool = False,
    cells: list[VecCampaignCell] | None = None,
    findings: list[str] | None = None,
) -> VecCampaignReceipt:
    recorded = cells or [
        _cell("cap-2.5", 40, VecCampaignCellState.ADMITTED),
        _cell("cap-2.5", 41, VecCampaignCellState.ADMITTED),
        _cell("cap-1.0", 40, VecCampaignCellState.REUSED),
        _cell("cap-1.0", 41, VecCampaignCellState.ADMITTED),
    ]
    states = [cell.state for cell in recorded]
    return VecCampaignReceipt(
        status=status,
        design_fingerprint=FINGERPRINT,
        experiment_id="vec-synthetic-campaign",
        phase=phase,
        approval=VecCampaignApproval(
            predeclaration_path="docs/evaluation/synthetic_predeclaration.md",
            predeclaration_sha256=DIGEST,
            approved_by="A. Owner",
            approved_role="repository owner",
            approved_at_utc="2026-07-27T09:00:00+00:00",
            held_out_authorised=held_out,
        ),
        predeclaration_verified_unchanged=True,
        experiment_registered=True,
        cells=recorded,
        planned_cell_count=len(recorded),
        admitted_cell_count=states.count(VecCampaignCellState.ADMITTED),
        reused_cell_count=states.count(VecCampaignCellState.REUSED),
        failed_cell_count=sum(
            1
            for state in states
            if state
            in {VecCampaignCellState.EXECUTION_FAILED, VecCampaignCellState.ADMISSION_REFUSED}
        ),
        skipped_cell_count=sum(
            1
            for state in states
            if state in {VecCampaignCellState.SKIPPED_BUDGET, VecCampaignCellState.SKIPPED_HALTED}
        ),
        total_output_bytes=2048 * len(recorded),
        total_elapsed_seconds=61.5 * len(recorded),
        started_at_utc="2026-07-27T09:05:00+00:00",
        finished_at_utc="2026-07-27T09:15:00+00:00",
        findings=findings or [],
        limitations=["Synthetic receipt fixture."],
    )


def _write(tmp_path: Path, receipt: VecCampaignReceipt | None = None) -> Path:
    path = tmp_path / "campaign_receipt.json"
    path.write_text((receipt or _receipt()).model_dump_json(), encoding="utf-8")
    return path


def _load(tmp_path: Path, **kwargs: object) -> CampaignReceiptView:
    loaded = load_campaign_receipt(str(_write(tmp_path, **kwargs)))  # type: ignore[arg-type]
    assert isinstance(loaded, CampaignReceiptView)
    return loaded


def test_no_path_returns_the_nothing_supplied_state_and_never_picks_a_file() -> None:
    for supplied in (None, "", "   "):
        loaded = load_campaign_receipt(supplied)
        assert isinstance(loaded, CampaignsError)
        assert "never searches" in loaded.message


def test_a_directory_is_refused_rather_than_scanned(tmp_path: Path) -> None:
    loaded = load_campaign_receipt(str(tmp_path))

    assert isinstance(loaded, CampaignsError)
    assert "does not list or scan directories" in loaded.message


def test_a_missing_file_is_an_honest_error(tmp_path: Path) -> None:
    loaded = load_campaign_receipt(str(tmp_path / "absent.json"))

    assert isinstance(loaded, CampaignsError)
    assert "No file exists" in loaded.message


def test_a_non_json_file_is_refused_with_its_reason(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("this is not json", encoding="utf-8")

    loaded = load_campaign_receipt(str(path))

    assert isinstance(loaded, CampaignsError)
    assert "not valid JSON" in loaded.message


def test_another_campaign_artifact_is_named_rather_than_dumped(tmp_path: Path) -> None:
    """A campaign directory holds several JSON files; say which one this is."""

    path = tmp_path / "campaign_analysis.json"
    path.write_text(
        json.dumps({"method_version": "vec-campaign-analysis-1.0", "experiment_id": "x"}),
        encoding="utf-8",
    )

    loaded = load_campaign_receipt(str(path))

    assert isinstance(loaded, CampaignsError)
    assert "vec-campaign-analysis-1.0" in loaded.message
    assert "not a campaign receipt" in loaded.message


def test_a_json_object_without_a_method_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "mystery.json"
    path.write_text(json.dumps({"experiment_id": "x"}), encoding="utf-8")

    loaded = load_campaign_receipt(str(path))

    assert isinstance(loaded, CampaignsError)
    assert "declares no method version" in loaded.message


def test_a_json_array_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    loaded = load_campaign_receipt(str(path))

    assert isinstance(loaded, CampaignsError)
    assert "JSON object" in loaded.message


def test_a_receipt_shaped_file_that_does_not_validate_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "broken_receipt.json"
    payload = json.loads(_receipt().model_dump_json())
    payload["planned_cell_count"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_campaign_receipt(str(path))

    assert isinstance(loaded, CampaignsError)
    assert "not a valid campaign receipt" in loaded.message
    assert loaded.detail


def test_an_oversized_file_is_refused_without_being_parsed(tmp_path: Path) -> None:
    path = tmp_path / "huge.json"
    path.write_text("x" * (MAX_RECEIPT_BYTES + 1), encoding="utf-8")

    loaded = load_campaign_receipt(str(path))

    assert isinstance(loaded, CampaignsError)
    assert "larger than a campaign receipt can be" in loaded.message


def test_a_valid_receipt_loads_with_the_path_it_came_from(tmp_path: Path) -> None:
    view = _load(tmp_path)

    assert view.source_path.name == "campaign_receipt.json"
    assert view.receipt.experiment_id == "vec-synthetic-campaign"


def test_identity_rows_carry_the_recorded_fingerprints_and_phase(tmp_path: Path) -> None:
    rows = {row.label: row.value for row in identity_rows(_load(tmp_path).receipt)}

    assert rows["Experiment id"] == "vec-synthetic-campaign"
    assert rows["Phase"] == "pilot"
    assert rows["Campaign status"] == "completed"
    assert rows["Design fingerprint"] == FINGERPRINT
    assert rows["Method version"] == "vec-bounded-campaign-1.0"


def test_approval_rows_show_held_out_authorisation_verbatim(tmp_path: Path) -> None:
    rows = {row.label: row.value for row in approval_rows(_load(tmp_path).receipt)}

    assert rows["Held-out cohort authorised"] == "False"
    assert rows["Predeclaration SHA-256"] == DIGEST
    assert rows["Approved by"] == "A. Owner"
    assert rows["Predeclaration verified unchanged at execution"] == "True"


def test_held_out_authorisation_is_badged_in_both_directions(tmp_path: Path) -> None:
    pilot = phase_badges(_load(tmp_path).receipt)
    held_out = phase_badges(
        _load(tmp_path, receipt=_receipt(phase=VecCampaignPhase.HELD_OUT, held_out=True)).receipt
    )

    assert "HELD-OUT NOT AUTHORISED" in pilot
    assert "PHASE: PILOT" in pilot
    assert "HELD-OUT AUTHORISED" in held_out
    assert "PHASE: HELD_OUT" in held_out
    # No badge ever suggests a campaign is running.
    for badges in (pilot, held_out):
        assert not any("LIVE" in badge or "RUNNING" in badge for badge in badges)


def test_cell_rows_preserve_the_recorded_order_and_states(tmp_path: Path) -> None:
    rows = cell_rows(_load(tmp_path).receipt)

    assert [row.arm_label for row in rows] == ["cap-2.5", "cap-2.5", "cap-1.0", "cap-1.0"]
    assert [row.state for row in rows] == ["admitted", "admitted", "reused", "admitted"]
    assert rows[0].elapsed_seconds == 61.5
    assert rows[0].output_bytes == 2048


def test_arm_summaries_count_every_state_group(tmp_path: Path) -> None:
    cells = [
        _cell("cap-2.5", 40, VecCampaignCellState.ADMITTED),
        _cell("cap-2.5", 41, VecCampaignCellState.EXECUTION_FAILED),
        _cell("cap-1.0", 40, VecCampaignCellState.SKIPPED_HALTED),
    ]
    view = _load(
        tmp_path,
        receipt=_receipt(status=VecCampaignStatus.HALTED_ON_FAILURE, cells=cells),
    )

    summaries = {summary.arm_label: summary for summary in arm_summaries(view.receipt)}
    assert summaries["cap-2.5"].admitted == 1
    assert summaries["cap-2.5"].failed == 1
    assert summaries["cap-1.0"].skipped == 1
    assert [summary.arm_label for summary in arm_summaries(view.receipt)] == [
        "cap-2.5",
        "cap-1.0",
    ]


def test_declared_seeds_are_read_back_from_the_cells(tmp_path: Path) -> None:
    assert declared_seeds(_load(tmp_path).receipt) == [40, 41]


def test_budget_usage_reports_consumption_and_says_the_ceilings_are_absent(
    tmp_path: Path,
) -> None:
    usage = budget_usage(_load(tmp_path).receipt)

    assert usage.planned_cell_count == 4
    assert usage.recorded_cell_count == 4
    assert usage.admitted_cell_count == 3
    assert usage.reused_cell_count == 1
    assert usage.total_output_bytes == 8192
    assert usage.declared_ceilings_available is False
    assert "does not embed" in usage.ceilings_unavailable_reason


def test_a_halted_receipt_reads_as_halted_not_as_running(tmp_path: Path) -> None:
    view = _load(tmp_path, receipt=_receipt(status=VecCampaignStatus.HALTED_ON_BUDGET))

    rows = {row.label: row.value for row in identity_rows(view.receipt)}
    assert rows["Campaign status"] == "halted_on_budget"
    assert "STATUS: HALTED_ON_BUDGET" in phase_badges(view.receipt)


def test_no_scientific_number_is_surfaced_by_any_row(tmp_path: Path) -> None:
    """Receipts only: states, times, and byte counts — never a metric value."""

    view = _load(tmp_path)
    surfaced = " ".join(
        [
            *(f"{row.label} {row.value}" for row in identity_rows(view.receipt)),
            *(f"{row.label} {row.value}" for row in approval_rows(view.receipt)),
            *(f"{row.arm_label} {row.state} {row.detail}" for row in cell_rows(view.receipt)),
        ]
    )
    for scientific in ("deadline_success", "latency", "offload", "p_value", "bootstrap"):
        assert scientific not in surfaced
