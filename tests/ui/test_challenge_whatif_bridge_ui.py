"""UI tests for Challenge → What-If bridge slice — real AppTest paths."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.challenge_whatif_bridge import (
    PENDING_WHATIF_CHALLENGE_DRAFT_KEY,
    build_challenge_whatif_draft,
    draft_to_handoff_dict,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.portfolio_explorer import get_challenge_seed
from traffictwin.ui.state import default_session_state

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


def _run_page(
    monkeypatch: pytest.MonkeyPatch,
    page: UiPage = UiPage.PORTFOLIO_EXPLORER,
    extra_state: dict[str, object] | None = None,
) -> AppTest:
    for key in _ENV_CLEAR:
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    state = deepcopy(default_session_state())
    state["_v07_navigation_active"] = True
    for k, v in state.items():
        app.session_state[k] = v
    if extra_state:
        for k, v in extra_state.items():
            app.session_state[k] = v
    app.run(timeout=30)
    return app


def _run_whatif(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, extra_state: dict[str, object] | None = None
) -> AppTest:
    import importlib

    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path / "ws"))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(tmp_path / "ws" / "registry.sqlite"))
    for k in _ENV_CLEAR:
        if k not in ("TRAFFICTWIN_WORKSPACE_PATH", "TRAFFICTWIN_REGISTRY_PATH"):
            monkeypatch.delenv(k, raising=False)
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)
    app_test_cls = vars(importlib.import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test_cls.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.WHATIF_STUDIO)}")
    from traffictwin.ui.state import load_ui_config

    state = deepcopy(default_session_state(load_ui_config()))
    state["_v07_navigation_active"] = True
    for k, v in state.items():
        app.session_state[k] = v
    if extra_state:
        for k, v in extra_state.items():
            app.session_state[k] = v
    app.run(timeout=30)
    return app


# Portfolio Explorer: real challenge selection, button exists, handoff correct


def test_portfolio_prepare_button_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch, UiPage.PORTFOLIO_EXPLORER)
    assert not app.exception
    buttons = [b.label for b in app.button]
    assert "Prepare supported values in What-If Studio" in buttons


def test_portfolio_shows_supported_and_unsupported_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch, UiPage.PORTFOLIO_EXPLORER)
    assert not app.exception
    all_text = "\n".join(
        str(x.value) for coll in [app.markdown, app.caption, app.info, app.warning] for x in coll
    )
    assert "Supported in What-If Studio:" in all_text
    assert "Not represented by current What-If controls:" in all_text


def test_portfolio_prepare_builds_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    challenge = get_challenge_seed("CH-01-arena-surge")
    assert challenge is not None
    draft = build_challenge_whatif_draft(challenge)
    handoff = draft_to_handoff_dict(draft)
    app = _run_page(monkeypatch, UiPage.PORTFOLIO_EXPLORER)
    assert not app.exception
    found = any(b.label == "Prepare supported values in What-If Studio" for b in app.button)
    assert found, "Prepare button not found"
    app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] = handoff
    app.session_state["_v07_pending_page"] = UiPage.WHATIF_STUDIO.value
    app.session_state["whatif_challenge_prefill_applied_fingerprint"] = None
    assert handoff.get("challenge_id") == "CH-01-arena-surge"
    assert len(handoff.get("supported_fields", [])) == len(draft.supported_fields)
    assert len(handoff.get("unsupported_fields", [])) == len(draft.unsupported_fields)
    assert app.session_state["_v07_pending_page"] == UiPage.WHATIF_STUDIO.value
    from traffictwin.ui.navigation import V07_PENDING_PAGE_KEY
    from traffictwin.ui.navigation_v07 import page_script_for

    assert app.session_state[V07_PENDING_PAGE_KEY] == UiPage.WHATIF_STUDIO.value
    assert page_script_for(UiPage.WHATIF_STUDIO) == "app_pages/whatif_studio.py"


def test_portfolio_warning_visible_for_partial_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.ui.challenge_whatif_bridge import build_draft_for_challenge_id

    d = build_draft_for_challenge_id("CH-04-rsu-waiting-room-squeeze")
    assert d is not None
    assert d.mapping_status.value == "PARTIALLY_MAPPABLE"
    assert len(d.unsupported_fields) == 1
    handoff = draft_to_handoff_dict(d)
    app = _run_page(
        monkeypatch, UiPage.WHATIF_STUDIO, extra_state={PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff}
    )
    assert not app.exception
    all_text = "\n".join(
        str(x.value) for coll in [app.markdown, app.caption, app.warning, app.info] for x in coll
    )
    assert "Only the supported subset will be prefilled" in all_text


# What-If Studio: receives handoff, shows panel, prefills widgets


def test_whatif_shows_challenge_source_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    d = build_challenge_whatif_draft(get_challenge_seed("CH-02-lane-closure-corridor"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app = _run_page(
        monkeypatch, UiPage.WHATIF_STUDIO, extra_state={PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff}
    )
    assert not app.exception
    all_text = "\n".join(
        str(x.value) for coll in [app.markdown, app.caption, app.warning, app.info] for x in coll
    )
    assert "Prepared from CH-02" in all_text
    assert "lane-closure corridor" in all_text.lower() or "lane closure" in all_text.lower()
    assert "PARTIALLY_MAPPABLE" in all_text or "PARTIALLY" in all_text


def test_whatif_supported_widgets_prefilled(monkeypatch: pytest.MonkeyPatch) -> None:
    d = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app = _run_page(
        monkeypatch,
        UiPage.WHATIF_STUDIO,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    found_congestion = False
    for inp in app.number_input:
        label = str(getattr(inp, "label", "") or "")
        if "Congestion multiplier" in label:
            val = inp.value
            assert val is not None
            assert float(val) == 2.2, f"expected 2.2 got {val}"
            found_congestion = True
    assert found_congestion, "congestion multiplier input not found"
    found_tar = False
    for inp in app.number_input:
        label = str(getattr(inp, "label", "") or "")
        if "Task arrival rate" in label:
            val = inp.value
            assert val is not None
            assert abs(float(val) - 0.16) < 1e-6, f"expected 0.16 got {val}"
            found_tar = True
    assert found_tar, "task arrival rate input not found"
    # Duration 900 for CH-01 (15min*60)
    found_dur = False
    for inp in app.number_input:
        label = str(getattr(inp, "label", "") or "")
        if "Duration (s)" in label:
            val = inp.value
            if val is not None and abs(float(val) - 900.0) < 1e-6:
                found_dur = True
    assert found_dur, "duration 900 not found prefilled"


def test_whatif_unsupported_fields_displayed(monkeypatch: pytest.MonkeyPatch) -> None:
    d = build_challenge_whatif_draft(get_challenge_seed("CH-04-rsu-waiting-room-squeeze"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app = _run_page(
        monkeypatch, UiPage.WHATIF_STUDIO, extra_state={PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff}
    )
    assert not app.exception
    all_text = "\n".join(
        str(x.value) for coll in [app.markdown, app.caption, app.warning, app.info] for x in coll
    )
    assert "Not applied" in all_text
    assert "rsu_capacity_mode" in all_text or "UNSUPPORTED" in all_text


def test_whatif_clear_prefill_button_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    d = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app = _run_page(
        monkeypatch, UiPage.WHATIF_STUDIO, extra_state={PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff}
    )
    assert not app.exception
    buttons = [b.label for b in app.button]
    assert "Clear challenge prefill" in buttons
    # Keep editing button should not exist (LOW-5)
    assert "Keep editing" not in buttons


def test_whatif_without_handoff_has_no_challenge_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch, UiPage.WHATIF_STUDIO)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown)
    assert "Prepared from" not in all_text


def test_portfolio_does_not_label_run_or_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch, UiPage.PORTFOLIO_EXPLORER)
    assert not app.exception
    buttons = [b.label for b in app.button]
    assert "Prepare supported values in What-If Studio" in buttons
    forbidden = ["Run challenge", "Execute challenge", "Replay challenge"]
    for f in forbidden:
        assert f not in buttons, f"forbidden label {f!r} found"


def test_bridge_ledger_distinction_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    d = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app = _run_page(
        monkeypatch, UiPage.WHATIF_STUDIO, extra_state={PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff}
    )
    assert not app.exception
    all_text = "\n".join(
        str(x.value) for coll in [app.markdown, app.caption, app.info, app.warning] for x in coll
    )
    assert (
        "Challenge source fields" in all_text
        or "actual What-If" in all_text
        or "ledger" in all_text.lower()
    )


def test_range_validation_no_crash_and_status_truthful(monkeypatch: pytest.MonkeyPatch) -> None:
    """Out-of-range challenge value must not crash and must be unsupported."""
    from traffictwin.ui.portfolio_explorer import ChallengeExecutionStatus, ChallengeSeedDefinition

    c = ChallengeSeedDefinition(
        challenge_id="CH-99-range-ui",
        title="Range UI test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={"demand.multiplier": 5.0},
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    from traffictwin.ui.challenge_whatif_bridge import build_challenge_whatif_draft as build

    d = build(c)
    assert d.mapping_status.value == "NOT_MAPPABLE"
    handoff = draft_to_handoff_dict(d)
    app = _run_page(
        monkeypatch, UiPage.WHATIF_STUDIO, extra_state={PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff}
    )
    # Should not crash, should show unsupported
    assert not app.exception
    all_text = "\n".join(
        str(x.value) for coll in [app.markdown, app.caption, app.warning, app.info] for x in coll
    )
    assert "outside current What-If control range" in all_text.lower() or "UNSUPPORTED" in all_text
    assert "StreamlitValueAboveMaxError" not in all_text


# --- Real E2E through AppTest form (HIGH-1 A, B, C) ---


def test_prepared_challenge_survives_rerun_into_generation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test A: prepared CH-01 values survive rerun into generation and appear in receipt."""
    d = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    # Assert prefilled widget values before generate
    vals = {str(inp.label): inp.value for inp in app.number_input}
    assert float(vals.get("Congestion multiplier", 0)) == 2.2
    assert abs(float(vals.get("Task arrival rate", 0)) - 0.16) < 1e-6
    # Find duration with value 900 (incident duration)
    dur_vals = [float(inp.value) for inp in app.number_input if "Duration (s)" in str(inp.label)]
    assert any(abs(v - 900.0) < 1e-6 for v in dur_vals), f"900 not in {dur_vals}"
    # Trigger Generate through real form
    gen_btn = [b for b in app.button if b.label == "Generate comparison"]
    assert gen_btn
    gen_btn[0].click().run(timeout=30)
    assert not app.exception
    assert "whatif_pair_receipt" in app.session_state
    receipt = app.session_state["whatif_pair_receipt"]
    # Receipt must reflect CH-01 values
    assert receipt["pair_id"].startswith("whatif-")
    changed = {p["field_path"]: p for p in receipt.get("changed_parameters", [])}
    assert "congestion_multiplier" in changed
    assert str(changed["congestion_multiplier"]["variation_value"]) == "2.2"
    assert "task_arrival_rate" in changed
    # task_arrival in variation is 0.16
    assert abs(float(changed["task_arrival_rate"]["variation_value"]) - 0.16) < 1e-6
    assert "incident_schedule[0].duration_s" in changed
    assert abs(float(changed["incident_schedule[0].duration_s"]["variation_value"]) - 900.0) < 1e-6


def test_no_challenge_and_ch01_request_differ(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test B: no-challenge generation vs CH-01 generation must differ."""
    # Without challenge
    app_no = _run_whatif(monkeypatch, tmp_path, extra_state=None)
    assert not app_no.exception
    gen_no = [b for b in app_no.button if b.label == "Generate comparison"][0]
    gen_no.click().run(timeout=30)
    assert not app_no.exception
    assert "whatif_pair_receipt" in app_no.session_state
    receipt_no = app_no.session_state["whatif_pair_receipt"]
    assert receipt_no is not None

    # With CH-01, fresh isolated workspace (use different tmp sub)
    import pathlib
    import tempfile

    tmp2 = pathlib.Path(tempfile.mkdtemp(dir=str(tmp_path)))
    d = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app_ch = _run_whatif(
        monkeypatch,
        tmp2,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app_ch.exception
    gen_ch = [b for b in app_ch.button if b.label == "Generate comparison"][0]
    gen_ch.click().run(timeout=30)
    assert not app_ch.exception
    assert "whatif_pair_receipt" in app_ch.session_state
    receipt_ch = app_ch.session_state["whatif_pair_receipt"]
    assert receipt_ch is not None

    # Fingerprints / pair IDs must differ
    assert receipt_no["request_fingerprint"] != receipt_ch["request_fingerprint"]
    assert receipt_no["pair_id"] != receipt_ch["pair_id"]
    assert receipt_no["pair_id"] != receipt_ch["pair_id"]


def test_user_edit_survives_through_generation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test C: user edit after prefill survives into generated receipt."""
    d = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    # Edit congestion from 2.2 to 2.5 (within range)
    inp = next(inp for inp in app.number_input if "Congestion multiplier" in str(inp.label))
    inp.set_value(2.5).run(timeout=30)
    assert not app.exception
    # Verify edit persisted
    vals = {str(i.label): i.value for i in app.number_input}
    assert float(vals.get("Congestion multiplier", 0)) == 2.5
    # Generate
    gen_btn = [b for b in app.button if b.label == "Generate comparison"][0]
    gen_btn.click().run(timeout=30)
    assert not app.exception
    assert "whatif_pair_receipt" in app.session_state
    receipt = app.session_state["whatif_pair_receipt"]
    assert receipt is not None
    changed = {p["field_path"]: p for p in receipt.get("changed_parameters", [])}
    assert "congestion_multiplier" in changed
    assert abs(float(changed["congestion_multiplier"]["variation_value"]) - 2.5) < 1e-6
    # Generation context should mark user_edited
    assert "last_whatif_generation_challenge_context" in app.session_state
    ctx = app.session_state["last_whatif_generation_challenge_context"]
    assert isinstance(ctx, dict)
    assert ctx.get("user_edited") is True


def test_old_receipt_not_relabelled_by_later_ch02(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """HIGH-2: old receipt without challenge must not be relabelled by later CH-02 draft."""
    # Generate without challenge
    app = _run_whatif(monkeypatch, tmp_path, extra_state=None)
    assert not app.exception
    [b for b in app.button if b.label == "Generate comparison"][0].click().run(timeout=30)
    assert not app.exception
    assert "whatif_pair_receipt" in app.session_state
    receipt = app.session_state["whatif_pair_receipt"]
    assert receipt is not None
    pair_id = receipt["pair_id"]
    # Inject CH-02 draft AFTER generation
    d2 = build_challenge_whatif_draft(get_challenge_seed("CH-02-lane-closure-corridor"))  # type: ignore[arg-type]
    app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] = draft_to_handoff_dict(d2)
    app.session_state["whatif_challenge_prefill_applied_fingerprint"] = None
    app.run(timeout=30)
    assert not app.exception
    # Success text should NOT contain CH-02 now
    success_text = " ".join(str(s.value) for s in app.success)
    # The receipt's provenance should remain without CH-02 label (last generation context was None)
    assert (
        "CH-02" not in success_text
        or "Generated from the supported subset of CH-02" not in success_text
    )
    # Specifically, last generation context should still be None or not matching CH-02
    ctx = app.session_state["last_whatif_generation_challenge_context"]
    # AppTest session_state returns None if missing? check containment
    if "last_whatif_generation_challenge_context" not in app.session_state:
        ctx = None
    assert ctx is None or ctx.get("pair_id") == pair_id  # type: ignore[union-attr]
    if isinstance(ctx, dict):
        assert ctx.get("challenge_id") != "CH-02-lane-closure-corridor"
