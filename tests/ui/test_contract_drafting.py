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
    # Exactly one H1, non-empty
    titles = [str(t.value) for t in app.title]
    assert len(titles) == 1, f"expected exactly one H1, got {titles}"
    assert titles[0].strip() != "", "H1 must be non-empty"
    assert "Contract Drafting Assistant" in titles[0]
    # Authority/evidence boundary visible before results
    warnings = [str(w.value) for w in app.warning]
    assert any("does not freeze" in w.lower() for w in warnings), (
        f"boundary not visible: {warnings}"
    )
    assert any("evidence and authority boundary" in w.lower() for w in warnings)
    # Useful empty state when no report
    infos = [str(i.value) for i in app.info]
    captions = [str(c.value) for c in app.caption]
    assert any("No samples profiled" in s for s in infos) or any(
        "Bounded inspection" in s for s in captions
    )


def test_contract_drafting_shows_sensitive_name_with_review_signal() -> None:
    """Positive UI: api_key row shows privacy_review=True and PRIVACY_REVIEW_REQUIRED."""
    from traffictwin.contract_drafting.service import build_draft_report

    tmp = Path(tempfile.mkdtemp())
    p1 = tmp / "sens1.csv"
    p2 = tmp / "sens2.csv"
    with p1.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["api_key", "ok"])
        w.writerow(["k1", "1"])
    with p2.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["api_key", "ok"])
        w.writerow(["k2", "2"])
    report = build_draft_report([p1, p2])

    app = _run_app("src/traffictwin/ui/app_pages/contract_drafting.py")
    app.session_state["cda_report"] = report.model_dump(mode="json")
    from traffictwin.contract_drafting.service import prepare_handoff

    handoff = prepare_handoff(report, source_id="test_src")
    app.session_state["cda_handoff"] = handoff.model_dump(mode="json")
    app.run(timeout=20)
    assert not app.exception
    # Exactly one H1 and boundary still visible
    assert len([str(t.value) for t in app.title]) == 1
    # Field name must be exact and not redacted
    draft_df_text = ""
    for df in app.dataframe:
        try:
            draft_df_text += str(df.value)
        except Exception:
            draft_df_text += ""
    assert "api_key" in draft_df_text, f"api_key not in draft dataframe: {draft_df_text[:500]}"
    assert "[REDACTED" not in draft_df_text
    # Must show privacy_review = True for api_key row (actual column value) — draft table
    found_api_key_true = False
    found_ok_false = False
    for df in app.dataframe:
        val = df.value
        records = []
        if hasattr(val, "to_dict"):
            try:
                records = val.to_dict(orient="records")
            except Exception:
                records = []
        elif isinstance(val, list):
            records = val
        if not records or not any("privacy_review" in r for r in records if isinstance(r, dict)):
            continue
        for row in records:
            if isinstance(row, dict) and row.get("field") == "api_key":
                assert row.get("privacy_review") == "True", (
                    f"api_key privacy_review should be True: {row}"
                )
                found_api_key_true = True
            if isinstance(row, dict) and row.get("field") == "ok":
                assert row.get("privacy_review") == "False", f"ok should be False: {row}"
                found_ok_false = True
    assert found_api_key_true, "api_key row not found in draft dataframe"
    assert found_ok_false, "ok row not found in draft dataframe"
    # Findings must contain exact PRIVACY_REVIEW_REQUIRED for api_key
    combined = " ".join(
        str(x.value)
        for x in list(app.info)
        + list(app.warning)
        + list(app.markdown)
        + list(app.caption)
        + list(app.error)
    )
    assert "PRIVACY_REVIEW_REQUIRED" in combined, (
        f"missing PRIVACY_REVIEW_REQUIRED: {combined[:500]}"
    )
    assert "api_key" in combined


def test_contract_drafting_benign_fields_show_no_privacy_review() -> None:
    """Negative UI: benign fields show privacy_review=False and no finding."""
    from traffictwin.contract_drafting.service import build_draft_report

    tmp = Path(tempfile.mkdtemp())
    p1 = tmp / "ben1.csv"
    p2 = tmp / "ben2.csv"
    headers = ["road_name", "access_token_count", "secretariat_office"]
    with p1.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerow(["High Road", "1", "office1"])
    with p2.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerow(["Main St", "2", "office2"])
    report = build_draft_report([p1, p2])

    app = _run_app("src/traffictwin/ui/app_pages/contract_drafting.py")
    app.session_state["cda_report"] = report.model_dump(mode="json")
    from traffictwin.contract_drafting.service import prepare_handoff

    handoff = prepare_handoff(report, source_id="test_src")
    app.session_state["cda_handoff"] = handoff.model_dump(mode="json")
    app.run(timeout=20)
    assert not app.exception
    # Draft table must contain benign rows with privacy_review False
    found_benign = dict.fromkeys(headers, False)
    for df in app.dataframe:
        val = df.value
        records = []
        if hasattr(val, "to_dict"):
            try:
                records = val.to_dict(orient="records")
            except Exception:
                records = []
        elif isinstance(val, list):
            records = val
        if not records or not any("privacy_review" in r for r in records if isinstance(r, dict)):
            continue
        for row in records:
            if isinstance(row, dict) and row.get("field") in headers:
                assert row.get("privacy_review") == "False", (
                    f"{row.get('field')} should be False: {row}"
                )
                key = row.get("field")
                if isinstance(key, str):
                    found_benign[key] = True
    for h, found in found_benign.items():
        assert found, f"benign field {h} not found in draft dataframe"
    # No PRIVACY_REVIEW_REQUIRED for benign fields
    combined = " ".join(
        str(x.value)
        for x in list(app.info) + list(app.warning) + list(app.markdown) + list(app.caption)
    )
    for name in headers:
        assert name in str([df.value for df in app.dataframe])
        assert not any(
            "PRIVACY_REVIEW_REQUIRED" in str(x.value) and name in str(x.value)
            for x in list(app.info) + list(app.warning) + list(app.markdown)
        ), f"unexpected PRIVACY finding for {name}"
    assert "[REDACTED" not in combined


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
