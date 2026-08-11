"""UI tests for Event-to-Scenario Bridge page."""

from __future__ import annotations

from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

_ENV_CLEAR = [
    "TRAFFICTWIN_WORKSPACE_PATH",
    "TRAFFICTWIN_REGISTRY_PATH",
    "TRAFFICTWIN_TOS_DATA_PATH",
    "TRAFFICTWIN_FIXTURE_PATH",
    "TRAFFICTWIN_RANDY_PACK_PATH",
    "TRAFFICTWIN_BODS_BOUNDING_BOX",
    "BODS_API_KEY",
    "NATIONAL_HIGHWAYS_API_KEY",
]


def _run_page(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    for key in _ENV_CLEAR:
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("src/traffictwin/ui/app_pages/event_scenario_bridge.py")
    from traffictwin.ui.state import default_session_state

    state = deepcopy(default_session_state())
    state["_v07_navigation_active"] = True
    for k, v in state.items():
        app.session_state[k] = v
    app.run(timeout=30)
    return app


def test_event_scenario_bridge_page_has_exactly_one_title(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    assert len(app.title) == 1
    assert app.title[0].value == "Event-to-Scenario Bridge"


def test_event_scenario_bridge_page_shows_evidence_boundary_before_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Evidence boundary must appear before any results: warning or caption with unexecuted
    all_text = " ".join(
        [c.value for c in app.caption]
        + [w.value for w in app.warning]
        + [i.value for i in app.info]
    ).lower()
    assert "unexecuted" in all_text
    assert (
        "does not run sumo" in all_text
        or "does not represent" in all_text
        or "not represent" in all_text
    )


def test_event_scenario_bridge_page_preview_and_export(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Click Preview bridge handoffs
    preview_btn = next(b for b in app.button if b.label == "Preview bridge handoffs")
    preview_btn.click().run(timeout=30)
    assert not app.exception
    # After preview, should have handoff preview subheader and download buttons
    subheaders = [s.value for s in app.subheader]
    assert any("Bridge handoff preview" in s for s in subheaders)
    # Download buttons
    labels = [b.label for b in app.download_button]
    assert any("Download bridge JSON" in lbl for lbl in labels)
    assert any("Download handoff summary CSV" in lbl for lbl in labels)


def test_event_scenario_bridge_page_no_run_button(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    labels = [b.label for b in app.button]
    for lbl in labels:
        assert "run" not in lbl.lower() or "preview" in lbl.lower(), f"Unexpected Run button: {lbl}"


def test_event_scenario_bridge_page_has_useful_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Before preview, should not have handoff preview; empty state is the boundary text
    subheaders_before = [s.value for s in app.subheader]
    assert not any("Bridge handoff preview" in s for s in subheaders_before)
    # But should have the form headers
    assert any("Declare event" in s for s in subheaders_before)


def test_event_scenario_bridge_page_widget_keys_unique(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Collect widget keys from session stateKeys — run twice to ensure no duplicate key error
    app.run(timeout=30)
    assert not app.exception


def test_event_scenario_bridge_page_mutation_labels_unique_for_three_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Set mutation_count to 3
    # Find selectbox for mutation count
    mut_count_box = next(b for b in app.selectbox if b.label == "How many ordered mutations?")
    mut_count_box.select("3").run(timeout=30)
    assert not app.exception
    # Collect all rendered control labels across selectbox, text_input, number_input, multiselect
    labels = []
    for sb in app.selectbox:
        labels.append(sb.label.strip().lower())
    for ti in app.text_input:
        labels.append(ti.label.strip().lower())
    for ni in app.number_input:
        labels.append(ni.label.strip().lower())
    for ms in app.multiselect:
        labels.append(ms.label.strip().lower())
    # Normalize whitespace
    import re

    normalized = [re.sub(r"\s+", " ", lbl) for lbl in labels if lbl]
    # Check no duplicates
    seen = set()
    duplicates = set()
    for lbl in normalized:
        if lbl in seen:
            duplicates.add(lbl)
        seen.add(lbl)
    assert not duplicates, f"Duplicate control labels found: {duplicates} among {normalized}"


def test_event_scenario_bridge_page_stale_preview_withheld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Preview valid request
    preview_btn = next(b for b in app.button if b.label == "Preview bridge handoffs")
    preview_btn.click().run(timeout=30)
    assert not app.exception
    # Capture old fingerprint
    # Find caption with Bridge fingerprint
    captions = [c.value for c in app.caption]
    old_fp = None
    for cap in captions:
        if "Bridge fingerprint:" in cap:
            # Extract fingerprint summary (first 16 chars before …)
            import re

            m = re.search(r"Bridge fingerprint: `([^`]+)`", cap)
            if m:
                old_fp = m.group(1)
                break
    assert old_fp is not None, "old fingerprint not found"
    # Also ensure handoff preview and downloads visible
    assert any("Bridge handoff preview" in s.value for s in app.subheader)
    assert any("Download bridge JSON" in b.label for b in app.download_button)

    # Edit Study title without clicking Preview
    title_input = next(t for t in app.text_input if t.label == "Study title")
    title_input.set_value("What-if study for stale check — updated title").run(timeout=30)
    assert not app.exception
    # After edit, old preview should be withheld, stale warning visible
    warnings = [w.value for w in app.warning]
    assert any("Inputs changed since the last preview" in w for w in warnings), (
        f"stale warning not found, warnings: {warnings}"
    )  # noqa: E501
    # Old fingerprint/handoff preview no longer presented as current
    # The old fingerprint should not be shown as current (handoff preview subheader should be gone)
    assert not any("Bridge handoff preview" in s.value for s in app.subheader), (
        "stale handoff preview should be withheld"
    )  # noqa: E501
    # Downloads unavailable/withheld
    assert len(app.download_button) == 0 or not any(
        "Download bridge JSON" in b.label for b in app.download_button
    ), "downloads should be withheld when stale"

    # Click Preview again
    preview_btn2 = next(b for b in app.button if b.label == "Preview bridge handoffs")
    preview_btn2.click().run(timeout=30)
    assert not app.exception
    # New title represented
    # Check new fingerprint differs
    captions_new = [c.value for c in app.caption]
    new_fp = None
    for cap in captions_new:
        if "Bridge fingerprint:" in cap:
            import re

            m = re.search(r"Bridge fingerprint: `([^`]+)`", cap)
            if m:
                new_fp = m.group(1)
                break
    assert new_fp is not None
    assert new_fp != old_fp, f"new fingerprint {new_fp} should differ from old {old_fp}"
    # Stale warning gone
    warnings_new = [w.value for w in app.warning]
    # The stale warning should be gone, but boundary warning remains; check that our specific stale text gone  # noqa: E501
    assert not any("Inputs changed since the last preview" in w for w in warnings_new)
    # New handoffs rendered
    assert any("Bridge handoff preview" in s.value for s in app.subheader)
    assert any("Download bridge JSON" in b.label for b in app.download_button)


def test_event_scenario_bridge_page_causal_title_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Set Study title to causal wording
    title_input = next(t for t in app.text_input if t.label == "Study title")
    title_input.set_value("Causal analysis of authored closure event").run(timeout=30)
    assert not app.exception
    # Click Preview
    preview_btn = next(b for b in app.button if b.label == "Preview bridge handoffs")
    preview_btn.click().run(timeout=30)
    # Should show error about title causality, not raw traceback
    # Check for error or warning containing our message
    # The page should have shown Study title is invalid with causality message
    # We can check that the manifest was not created (no handoff preview)
    assert not any("Bridge handoff preview" in s.value for s in app.subheader)
    # The error should be readable, not a multi-line Pydantic traceback
    # Check that the error message contains our validation text
    # Since AppTest may store error in app.error, let's look at app.error specifically
    if hasattr(app, "error") and app.error:
        err_text = " ".join(e.value for e in app.error).lower()
        assert "must not claim causality" in err_text or "study title is invalid" in err_text
    else:
        # Fallback: check that preview did not succeed and no fingerprint shown
        assert not any("Bridge fingerprint" in c.value for c in app.caption)
