"""AppTest coverage for the additive Campaigns page.

Every receipt is written into ``tmp_path`` and named explicitly. No test points
the page at a real campaign directory, and the page has no way to find one on
its own.
"""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from traffictwin.integration.vec_campaign.models import (
    VecCampaignApproval,
    VecCampaignCell,
    VecCampaignCellState,
    VecCampaignPhase,
    VecCampaignReceipt,
    VecCampaignStatus,
)
from traffictwin.ui.state import default_session_state, load_ui_config

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
    phase: VecCampaignPhase = VecCampaignPhase.PILOT,
    held_out: bool = False,
    status: VecCampaignStatus = VecCampaignStatus.COMPLETED,
) -> VecCampaignReceipt:
    cells = [
        _cell("cap-2.5", 40, VecCampaignCellState.ADMITTED),
        _cell("cap-1.0", 40, VecCampaignCellState.ADMITTED),
    ]
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
        cells=cells,
        planned_cell_count=len(cells),
        admitted_cell_count=len(cells),
        reused_cell_count=0,
        failed_cell_count=0,
        skipped_cell_count=0,
        total_output_bytes=4096,
        total_elapsed_seconds=123.0,
        started_at_utc="2026-07-27T09:05:00+00:00",
        finished_at_utc="2026-07-27T09:15:00+00:00",
        limitations=["Synthetic receipt fixture."],
    )


def _write(tmp_path: Path, receipt: VecCampaignReceipt | None = None) -> Path:
    path = tmp_path / "campaign_receipt.json"
    path.write_text((receipt or _receipt()).model_dump_json(), encoding="utf-8")
    return path


def _app(monkeypatch: MonkeyPatch, workspace: Path) -> Any:  # noqa: ANN401 - AppTest loads dynamically
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/campaigns.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def test_the_page_shows_nothing_until_a_receipt_is_named(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)

    assert not app.exception
    assert any(title.value == "Campaigns" for title in app.title)
    assert app.text_input[0].value == ""
    info_values = " ".join(str(info.value) for info in app.info)
    assert "never searches" in info_values
    # Nothing is loaded, so no table exists to imply a campaign was found.
    assert not app.dataframe


def test_the_page_states_it_is_not_live_and_reads_receipts_only(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)

    captions = " ".join(str(caption.value) for caption in app.caption)
    assert "does not poll, refresh, or report whether anything is running now" in captions
    assert "No registry is opened here" in captions
    assert "no scientific result is computed or shown" in captions


def test_a_named_receipt_renders_identity_approval_cells_and_usage(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    receipt_path = _write(tmp_path)
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    app.text_input[0].set_value(str(receipt_path)).run(timeout=20)

    assert not app.exception
    subheaders = [str(header.value) for header in app.subheader]
    assert "Design identity" in subheaders
    assert "Approval provenance" in subheaders
    assert "Declared cells" in subheaders
    assert "Budget usage" in subheaders
    # Identity, per-arm, approval, cells, and the advanced per-cell detail table.
    assert len(app.dataframe) == 5
    rendered = " ".join(str(frame.value) for frame in app.dataframe)
    assert "vec-synthetic-campaign" in rendered


def test_held_out_authorisation_is_shown_verbatim(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    receipt_path = _write(tmp_path, _receipt(phase=VecCampaignPhase.HELD_OUT, held_out=True))
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    app.text_input[0].set_value(str(receipt_path)).run(timeout=20)

    assert not app.exception
    rendered = " ".join(str(frame.value) for frame in app.dataframe)
    assert "held_out" in rendered
    markdown = " ".join(str(item.value) for item in app.markdown)
    assert "HELD-OUT AUTHORISED" in markdown


def test_the_budget_usage_metrics_state_that_ceilings_are_absent(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    receipt_path = _write(tmp_path)
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    app.text_input[0].set_value(str(receipt_path)).run(timeout=20)

    assert not app.exception
    labels = [str(metric.label) for metric in app.metric]
    assert "Declared cells" in labels
    assert "Output bytes" in labels
    captions = " ".join(str(caption.value) for caption in app.caption)
    assert "the receipt does not embed" in captions


def test_a_missing_receipt_is_an_honest_state_with_no_table(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    app.text_input[0].set_value(str(tmp_path / "absent.json")).run(timeout=20)

    assert not app.exception
    info_values = " ".join(str(info.value) for info in app.info)
    assert "No file exists" in info_values
    assert not app.dataframe


def test_a_directory_path_is_refused_rather_than_scanned(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    app.text_input[0].set_value(str(tmp_path)).run(timeout=20)

    assert not app.exception
    info_values = " ".join(str(info.value) for info in app.info)
    assert "does not list or scan directories" in info_values
    assert not app.dataframe


def test_a_mismatched_artifact_names_what_it_actually_is(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    other = tmp_path / "campaign_analysis.json"
    other.write_text('{"method_version": "vec-campaign-analysis-1.0"}', encoding="utf-8")
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    app.text_input[0].set_value(str(other)).run(timeout=20)

    assert not app.exception
    info_values = " ".join(str(info.value) for info in app.info)
    assert "vec-campaign-analysis-1.0" in info_values
    assert not app.dataframe


def test_the_page_never_implies_a_campaign_is_running(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    receipt_path = _write(tmp_path)
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    app.text_input[0].set_value(str(receipt_path)).run(timeout=20)

    assert not app.exception
    fragments = [
        *(str(title.value) for title in app.title),
        *(str(caption.value) for caption in app.caption),
        *(str(header.value) for header in app.subheader),
        *(str(item.value) for item in app.markdown),
    ]
    # Every place the page mentions liveness or running state must be denying
    # it. A bare mention would be exactly the implication to avoid.
    suspicious = [
        fragment
        for fragment in fragments
        if any(word in fragment.lower() for word in ("live", "running", "monitor", "in progress"))
    ]
    assert suspicious, "the page should address liveness explicitly rather than stay silent"
    for fragment in suspicious:
        lowered = fragment.lower()
        assert "never" in lowered or "not " in lowered, fragment
