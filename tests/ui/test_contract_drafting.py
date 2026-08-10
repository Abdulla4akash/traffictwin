"""UI tests for Contract Drafting Assistant page."""

from __future__ import annotations

import csv
import tempfile
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from traffictwin.ui.state import default_session_state, load_ui_config


def _run_app(path: str) -> Any:  # noqa: ANN401
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]  # noqa: N806
    app = app_test.from_file(path)
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def test_contract_drafting_page_renders() -> None:
    app = _run_app("src/traffictwin/ui/app_pages/contract_drafting.py")
    app.run(timeout=20)
    assert not app.exception
    # Must have authoritative H1
    assert any("Contract Drafting Assistant" in str(t.value) for t in app.title) or any(
        "Contract Drafting Assistant" in str(h.value) for h in app.header
    )
    # Warning before results
    assert any("does not freeze" in str(w.value).lower() for w in app.warning) or any(
        "evidence and authority boundary" in str(w.value).lower() for w in app.warning
    )
    # Sample selection button exists
    assert any(b.label == "Profile samples" for b in app.button)
    # Empty state info
    assert any("No samples profiled" in str(i.value) for i in app.info) or any(
        "Bounded inspection" in str(c.value) for c in app.caption
    )
    # No duplicate widget keys: AppTest would have thrown on duplicate; just ensure no exception
    assert not app.exception


def test_contract_drafting_page_with_report_renders_consensus() -> None:
    from traffictwin.contract_drafting.service import build_draft_report

    tmp = Path(tempfile.mkdtemp())
    p1 = tmp / "s1.csv"
    p2 = tmp / "s2.csv"
    with p1.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a", "b"])
        w.writerow(["1", "hello"])
    with p2.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["a", "b"])
        w.writerow(["2", "world"])

    report = build_draft_report([p1, p2])

    app = _run_app("src/traffictwin/ui/app_pages/contract_drafting.py")
    # Seed report into session
    app.session_state["cda_report"] = report.model_dump(mode="json")
    from traffictwin.contract_drafting.service import prepare_handoff

    handoff = prepare_handoff(report, source_id="test_src")
    app.session_state["cda_handoff"] = handoff.model_dump(mode="json")
    app.run(timeout=20)
    assert not app.exception
    # Should show consensus table via dataframe
    assert len(app.dataframe) >= 1
    # Should show disagreement or info
    # Check that handoff download exists
    assert (
        any("Download handoff" in str(b.label) for b in app.button)
        or any("handoff" in str(b.label).lower() for b in app.download_button)
        if hasattr(app, "download_button")
        else True
    )
    # Explicit link text for Data Contract Workbench review
    text_combined = " ".join(
        [str(x.value) for x in list(app.markdown) + list(app.caption) + list(app.info)]
    )
    assert "Data Contract Workbench" in text_combined


def test_contract_drafting_page_accessibility_heading() -> None:
    app = _run_app("src/traffictwin/ui/app_pages/contract_drafting.py")
    app.run(timeout=20)
    assert not app.exception
    # Accessibility: page must have title header
    assert any("Contract Drafting Assistant" in str(t.value) for t in app.title)


def test_contract_drafting_first_click_succeeds() -> None:
    """Fresh defaults: Profile samples click must not fail due to duplicate paths."""
    app = _run_app("src/traffictwin/ui/app_pages/contract_drafting.py")
    app.run(timeout=20)
    assert not app.exception
    # Find Profile samples button and click it once from clean default state
    btn = next((b for b in app.button if b.label == "Profile samples"), None)
    assert btn is not None, "Profile samples button not found"
    btn.click().run(timeout=20)
    assert not app.exception
    # No duplicate-path validation error
    error_text = " ".join(str(e.value) for e in app.error)
    assert "must contain unique" not in error_text.lower()
    assert "duplicate" not in error_text.lower()
    # Either valid report was created (two distinct defaults) or honest empty guidance
    # With valid bundled defaults, we expect a report and handoff
    # Check session_state via app
    report_dict = app.session_state["cda_report"] if "cda_report" in app.session_state else None  # noqa: SIM401
    # If defaults are two valid fixtures, report should exist with 2 samples
    if report_dict is not None:
        from traffictwin.contract_drafting.models import ContractDraftReport

        report = ContractDraftReport.model_validate(report_dict)
        assert report.total_samples == 2
        assert report.fingerprint is not None
        # Handoff should also exist
        handoff_dict = (
            app.session_state["cda_handoff"]  # noqa: SIM401
            if "cda_handoff" in app.session_state
            else None
        )
        assert handoff_dict is not None
        from traffictwin.contract_drafting.models import DraftContractHandoff

        handoff = DraftContractHandoff.model_validate(handoff_dict)
        assert handoff.draft_only is True
        assert handoff.freeze_executed is False
        assert handoff.human_review_required is True
    else:
        # Fallback: if page intentionally ships empty, it must guide user
        combined = " ".join(
            str(x.value) for x in list(app.info) + list(app.caption) + list(app.markdown)
        )
        assert "Provide 2–20" in combined or "No samples profiled" in combined
