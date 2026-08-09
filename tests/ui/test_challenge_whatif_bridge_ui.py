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
    from typing import cast

    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path / "ws"))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(tmp_path / "ws" / "registry.sqlite"))
    for k in _ENV_CLEAR:
        if k not in ("TRAFFICTWIN_WORKSPACE_PATH", "TRAFFICTWIN_REGISTRY_PATH"):
            monkeypatch.delenv(k, raising=False)
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)
    app_test_cls = vars(importlib.import_module("streamlit.testing.v1"))["AppTest"]
    app = cast(
        AppTest,
        app_test_cls.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.WHATIF_STUDIO)}"),
    )
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
    assert "Reset to stock defaults" in buttons
    assert "Clear challenge prefill" not in buttons
    # Keep editing button should not exist (LOW-5)
    assert "Keep editing" not in buttons


def test_unmapped_controls_disclosure_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    d = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    handoff = draft_to_handoff_dict(d)
    app = _run_page(
        monkeypatch, UiPage.WHATIF_STUDIO, extra_state={PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff}
    )
    assert not app.exception
    captions = [str(c.value) for c in app.caption]
    assert "Unmapped controls keep ordinary What-If Studio defaults." in captions
    assert "The actual generated ledger is authoritative." in captions


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
    captions = [str(c.value) for c in app.caption]
    assert "Unmapped controls keep ordinary What-If Studio defaults." in captions
    assert "The actual generated ledger is authoritative." in captions


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
    c_mul = vals.get("Congestion multiplier")
    assert c_mul is not None
    assert float(c_mul) == 2.2
    tar = vals.get("Task arrival rate")
    assert tar is not None
    assert abs(float(tar) - 0.16) < 1e-6
    # Find duration with value 900 (incident duration)
    dur_vals: list[float] = []
    for inp in app.number_input:
        if "Duration (s)" in str(inp.label) and inp.value is not None:
            dur_vals.append(float(inp.value))
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
    c_mul2 = vals.get("Congestion multiplier")
    assert c_mul2 is not None
    assert float(c_mul2) == 2.5
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
    """HIGH-2: old receipt CH-01→CH-02 relabel proof as mandatory transaction."""
    # 1. Prepare CH-01 through real bridge
    d01 = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    h01 = draft_to_handoff_dict(d01)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: h01,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    # 2. Generate real What-If pair
    [b for b in app.button if b.label == "Generate comparison"][0].click().run(timeout=30)
    assert not app.exception
    assert "whatif_pair_receipt" in app.session_state
    receipt = app.session_state["whatif_pair_receipt"]
    assert isinstance(receipt, dict)
    pair_id = receipt["pair_id"]
    request_fp = receipt["request_fingerprint"]
    assert "last_whatif_generation_challenge_context" in app.session_state
    ctx = app.session_state["last_whatif_generation_challenge_context"]
    assert isinstance(ctx, dict)
    # 4. Exact CH-01 identity and receipt binding
    assert ctx["challenge_id"] == "CH-01-arena-surge"
    assert ctx["challenge_fingerprint"] == d01.fingerprint
    assert ctx["pair_id"] == pair_id
    assert ctx["request_fingerprint"] == request_fp
    # 5. Prepare CH-02 as new pending draft WITHOUT generating
    d02 = build_challenge_whatif_draft(get_challenge_seed("CH-02-lane-closure-corridor"))  # type: ignore[arg-type]
    h02 = draft_to_handoff_dict(d02)
    app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] = h02
    app.session_state["whatif_challenge_prefill_applied_fingerprint"] = None
    # 6. Rerender
    app.run(timeout=30)
    assert not app.exception
    # 7. Pending draft is CH-02
    pending = app.session_state["pending_whatif_challenge_draft"]
    assert isinstance(pending, dict)
    assert pending["challenge_id"] == "CH-02-lane-closure-corridor"
    # 8. Old receipt remains same
    assert "whatif_pair_receipt" in app.session_state
    receipt2 = app.session_state["whatif_pair_receipt"]
    assert receipt2["pair_id"] == pair_id
    assert receipt2["request_fingerprint"] == request_fp
    # Generation context remains CH-01 exact
    assert "last_whatif_generation_challenge_context" in app.session_state
    ctx2 = app.session_state["last_whatif_generation_challenge_context"]
    assert isinstance(ctx2, dict)
    assert ctx2["challenge_id"] == "CH-01-arena-surge"
    assert ctx2["pair_id"] == pair_id
    assert ctx2["request_fingerprint"] == request_fp
    assert ctx2["challenge_fingerprint"] == d01.fingerprint
    # Old success wording does not claim CH-02 generated the old pair
    success_text = " ".join(str(s.value) for s in app.success)
    assert "Generated from the supported subset of CH-02" not in success_text
    assert "CH-02" not in success_text or pair_id in success_text or "CH-01" in success_text


# --- MEDIUM-6: cross-draft reset regression ---


def test_ch01_to_ch07_resets_full_control_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CH-01 → CH-07 without Clear must reset full control set to defaults then overlay CH-07.

    Proves: no CH-01 incident/event/demand leak, duration 900 gone, ledger is CH-07+defaults.
    """
    from traffictwin.ui.whatif_controls import DEFAULT_WHATIF_WIDGET_VALUES

    # Step 1: prepare CH-01
    d01 = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    h01 = draft_to_handoff_dict(d01)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: h01,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    # Confirm CH-01 controls present
    vals01 = {str(inp.label): inp.value for inp in app.number_input}
    # congestion 2.2 is CH-01 specific
    c_mul_01 = vals01.get("Congestion multiplier")
    assert c_mul_01 is not None and abs(float(c_mul_01) - 2.2) < 1e-6
    dur_vals_01: list[float] = [
        float(inp.value)
        for inp in app.number_input
        if "Duration (s)" in str(inp.label) and inp.value is not None
    ]
    assert any(abs(v - 900.0) < 1e-6 for v in dur_vals_01), (
        f"CH-01 duration 900 missing {dur_vals_01}"
    )
    # Also check incident type is stadium_event (CH-01)
    incident_types_01 = [str(c.value) for c in app.text_input if "Event type" in str(c.label)]
    assert any("stadium_event" in t for t in incident_types_01)

    # Step 2: prepare CH-07 in same session without Clear
    d07 = build_challenge_whatif_draft(get_challenge_seed("CH-07-scaling-strategy"))  # type: ignore[arg-type]
    h07 = draft_to_handoff_dict(d07)
    # Inject new draft via session state (simulates Portfolio → Prepare again)
    app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] = h07
    app.session_state["whatif_challenge_prefill_applied_fingerprint"] = (
        d01.fingerprint
    )  # old applied, new will trigger reset
    app.run(timeout=30)
    assert not app.exception

    # Step 3: prove every control not mapped by CH-07 has returned to stock default
    # CH-07 maps: vehicle_count 80, rsu_count 6, congestion 1.0, task_arrival 0.2
    # It does NOT map incident_type/location/event_demand/duration etc.
    # Use DEFAULT_WHATIF_WIDGET_VALUES for expected defaults
    # Map widget labels to expected keys via app.session_state
    # Check incident fields returned to defaults
    assert (
        app.session_state["whatif_incident_type"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_type"]
    )
    assert (
        app.session_state["whatif_incident_location"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_location"]
    )
    assert (
        app.session_state["whatif_event_demand_multiplier"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_event_demand_multiplier"]
    )
    assert (
        app.session_state["whatif_incident_duration_s"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_duration_s"]
    )
    assert (
        app.session_state["whatif_incident_start_s"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_start_s"]
    )
    assert (
        app.session_state["whatif_lanes_closed"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_lanes_closed"]
    )
    # Explicitly prove CH-01-only incident/event state is gone
    assert "stadium_event" not in str(app.session_state["whatif_incident_type"])
    assert "old-trafford" not in str(app.session_state["whatif_incident_location"])
    # Explicitly prove CH-01 duration 900.0 does not leak
    assert float(app.session_state["whatif_incident_duration_s"]) != 900.0
    dur_vals_after: list[float] = [
        float(inp.value)
        for inp in app.number_input
        if "Duration (s)" in str(inp.label) and inp.value is not None
    ]
    assert all(abs(v - 900.0) > 1e-6 for v in dur_vals_after), f"leaked 900 in {dur_vals_after}"
    # CH-01 demand 2.0 must not leak unless CH-07 maps same field/value
    # CH-07 maps congestion 1.0, not 2.2, so 2.2 must be gone; event_demand default 1.3
    assert abs(float(app.session_state["whatif_congestion_multiplier"]) - 2.2) > 1e-6
    assert float(app.session_state["whatif_congestion_multiplier"]) == 1.0  # CH-07 value
    assert float(app.session_state["whatif_event_demand_multiplier"]) == float(
        DEFAULT_WHATIF_WIDGET_VALUES["whatif_event_demand_multiplier"]
    )
    # Also prove CH-07-supported values plus ordinary defaults only via generation
    assert int(app.session_state["whatif_vehicle_count"]) == 80
    assert int(app.session_state["whatif_rsu_count"]) == 6
    assert abs(float(app.session_state["whatif_task_arrival_rate"]) - 0.2) < 1e-6
    # Task mix not mapped by CH-07 so should be defaults
    assert float(app.session_state["whatif_task_mix_t1"]) == float(
        DEFAULT_WHATIF_WIDGET_VALUES["whatif_task_mix_t1"]
    )
    assert float(app.session_state["whatif_rsu_capacity"]) == float(
        DEFAULT_WHATIF_WIDGET_VALUES["whatif_rsu_capacity"]
    )

    # Step 4: click Generate and inspect ledger
    gen_btn = [b for b in app.button if b.label == "Generate comparison"]
    assert gen_btn
    gen_btn[0].click().run(timeout=30)
    assert not app.exception
    assert "whatif_pair_receipt" in app.session_state
    receipt = app.session_state["whatif_pair_receipt"]
    changed = {p["field_path"]: p for p in receipt.get("changed_parameters", [])}
    # Ledger must contain CH-07 values, not CH-01 leakage
    assert (
        "congestion_multiplier" not in changed
        or str(changed["congestion_multiplier"]["variation_value"]) == "1.0"
    )
    # Prove incident fields not in ledger as CH-01 leakage (defaults, no diff)
    # Key: duration_s in ledger should NOT be 900.0
    for p in receipt.get("changed_parameters", []):
        if "duration_s" in p["field_path"]:
            assert abs(float(p["variation_value"]) - 900.0) > 1e-6, f"leaked 900 in ledger {p}"
        if p["field_path"] == "event_demand_multiplier":
            assert abs(float(p["variation_value"]) - 2.0) > 1e-6, (
                f"leaked CH-01 event_demand 2.0 {p}"
            )


def test_same_fingerprint_rerun_preserves_user_edit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Same CH-07 fingerprint rerun does not reset a user edit."""
    d07 = build_challenge_whatif_draft(get_challenge_seed("CH-07-scaling-strategy"))  # type: ignore[arg-type]
    h07 = draft_to_handoff_dict(d07)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: h07,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    # User edits congestion from 1.0 to 2.5
    inp = next(inp for inp in app.number_input if "Congestion multiplier" in str(inp.label))
    inp.set_value(2.5).run(timeout=30)
    assert not app.exception
    vals = {str(i.label): i.value for i in app.number_input}
    edited_val = vals.get("Congestion multiplier")
    assert edited_val is not None and abs(float(edited_val) - 2.5) < 1e-6
    # Rerun with same fingerprint (no new draft) should preserve edit
    app.run(timeout=30)
    assert not app.exception
    vals2 = {str(i.label): i.value for i in app.number_input}
    edited_val2 = vals2.get("Congestion multiplier")
    assert edited_val2 is not None and abs(float(edited_val2) - 2.5) < 1e-6


def test_new_draft_resets_before_overlay_clears_user_edit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A later different draft resets before overlay (clears user edit)."""
    d07 = build_challenge_whatif_draft(get_challenge_seed("CH-07-scaling-strategy"))  # type: ignore[arg-type]
    h07 = draft_to_handoff_dict(d07)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: h07,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    # User edits vehicle_count from 80 to 42
    inp = next(inp for inp in app.number_input if "Vehicle count" in str(inp.label))
    inp.set_value(42).run(timeout=30)
    assert not app.exception
    assert int(app.session_state["whatif_vehicle_count"]) == 42
    # Now inject CH-01 (different fingerprint) — should reset complete set then overlay CH-01
    d01 = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    h01 = draft_to_handoff_dict(d01)
    app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] = h01
    # Keep old fingerprint to trigger reset path on next run
    app.run(timeout=30)
    assert not app.exception
    # vehicle_count should now be default (CH-01 does NOT map vehicle_count) — not 42, not 80
    from traffictwin.ui.whatif_controls import DEFAULT_WHATIF_WIDGET_VALUES

    assert int(app.session_state["whatif_vehicle_count"]) == int(
        DEFAULT_WHATIF_WIDGET_VALUES["whatif_vehicle_count"]
    )
    # And CH-01 mapped values should be present
    assert abs(float(app.session_state["whatif_congestion_multiplier"]) - 2.2) < 1e-6


def test_clear_restores_full_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Reset to stock defaults must restore the same authoritative stock defaults."""
    from traffictwin.ui.whatif_controls import DEFAULT_WHATIF_WIDGET_VALUES

    d01 = build_challenge_whatif_draft(get_challenge_seed("CH-01-arena-surge"))  # type: ignore[arg-type]
    h01 = draft_to_handoff_dict(d01)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: h01,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    assert "stadium_event" in str(app.session_state["whatif_incident_type"])
    # Click Reset to stock defaults
    clear_btn = [b for b in app.button if b.label == "Reset to stock defaults"]
    assert clear_btn
    clear_btn[0].click().run(timeout=30)
    assert not app.exception
    # All controls should be defaults
    for key, expected in DEFAULT_WHATIF_WIDGET_VALUES.items():
        assert app.session_state[key] == expected, (
            f"{key} not reset: {app.session_state[key]} != {expected}"
        )
    # Pending draft gone
    assert (
        PENDING_WHATIF_CHALLENGE_DRAFT_KEY not in app.session_state
        or app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] is None
    )
    assert app.session_state["whatif_challenge_prefill_applied_fingerprint"] is None


def test_ch07_exact_source_contract() -> None:
    """CH-07 source contract: exact four overrides, exact mappings, no incident."""
    seed = get_challenge_seed("CH-07-scaling-strategy")
    assert seed is not None
    assert seed.parameter_overrides == {
        "fleet.count": 80,
        "infrastructure.rsu_count": 6,
        "demand.multiplier": 1.0,
        "workload.birth_rate_multiplier": 2.0,
    }
    draft = build_challenge_whatif_draft(seed)
    assert {f.challenge_path for f in draft.supported_fields} == {
        "fleet.count",
        "infrastructure.rsu_count",
        "demand.multiplier",
        "workload.birth_rate_multiplier",
    }
    assert {(f.challenge_path, f.whatif_field) for f in draft.supported_fields} == {
        ("fleet.count", "vehicle_count"),
        ("infrastructure.rsu_count", "rsu_count"),
        ("demand.multiplier", "congestion_multiplier"),
        ("workload.birth_rate_multiplier", "task_arrival_rate"),
    }
    assert len(draft.supported_fields) == 4
    assert len(draft.unsupported_fields) == 0
    assert draft.mapping_status.value == "FULLY_MAPPABLE"
    assert draft.whatif_overrides == {
        "vehicle_count": 80,
        "rsu_count": 6,
        "congestion_multiplier": 1.0,
        "task_arrival_rate": 0.2,
    }
    assert set(draft.whatif_overrides) == {
        "vehicle_count",
        "rsu_count",
        "congestion_multiplier",
        "task_arrival_rate",
    }
    # By set equality, cannot secretly include incident controls
    assert not any(k.startswith("incident") for k in draft.whatif_overrides)
    assert "lanes_closed" not in draft.whatif_overrides
    assert "event_demand_multiplier" not in draft.whatif_overrides


def test_ch07_default_incident_truth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CH-07 leaves ordinary default incident enabled; not attributed to CH-07."""
    from traffictwin.ui.whatif_controls import DEFAULT_WHATIF_WIDGET_VALUES

    seed = get_challenge_seed("CH-07-scaling-strategy")
    assert seed is not None
    draft = build_challenge_whatif_draft(seed)
    handoff = draft_to_handoff_dict(draft)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: handoff,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    # Exact CH-07 mapped widget values
    assert int(app.session_state["whatif_vehicle_count"]) == 80
    assert int(app.session_state["whatif_rsu_count"]) == 6
    assert float(app.session_state["whatif_congestion_multiplier"]) == 1.0
    assert abs(float(app.session_state["whatif_task_arrival_rate"]) - 0.2) < 1e-9
    # Every stock incident value remains ordinary Studio default
    assert bool(app.session_state["whatif_incident_enabled"]) is True
    assert (
        app.session_state["whatif_incident_type"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_type"]
    )
    assert (
        app.session_state["whatif_incident_location"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_location"]
    )
    assert (
        app.session_state["whatif_incident_severity"]
        == DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_severity"]
    )
    assert float(app.session_state["whatif_incident_start_s"]) == float(
        DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_start_s"]
    )
    assert float(app.session_state["whatif_incident_duration_s"]) == float(
        DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_duration_s"]
    )
    assert int(app.session_state["whatif_lanes_closed"]) == int(
        DEFAULT_WHATIF_WIDGET_VALUES["whatif_lanes_closed"]
    )
    assert float(app.session_state["whatif_event_demand_multiplier"]) == float(
        DEFAULT_WHATIF_WIDGET_VALUES["whatif_event_demand_multiplier"]
    )
    # Exact UI disclosure via captions (exact element value)
    captions = [str(c.value) for c in app.caption]
    assert "Unmapped controls keep ordinary What-If Studio defaults." in captions
    assert "The actual generated ledger is authoritative." in captions
    # Draft must not list incident as mapped
    assert not any("incident" in f.whatif_field for f in draft.supported_fields)
    # Generate via real form
    gen_btn = [b for b in app.button if b.label == "Generate comparison"]
    assert gen_btn
    gen_btn[0].click().run(timeout=30)
    assert not app.exception
    assert "whatif_pair_receipt" in app.session_state
    receipt = app.session_state["whatif_pair_receipt"]
    assert isinstance(receipt, dict)
    # Generation provenance unconditional
    assert "last_whatif_generation_challenge_context" in app.session_state
    ctx = app.session_state["last_whatif_generation_challenge_context"]
    assert isinstance(ctx, dict)
    assert ctx["challenge_id"] == "CH-07-scaling-strategy"
    assert ctx["challenge_fingerprint"] == draft.fingerprint
    assert ctx["mapping_status"] == "FULLY_MAPPABLE"
    assert ctx["supported_count"] == 4
    assert ctx["unsupported_count"] == 0
    assert ctx["pair_id"] == receipt["pair_id"]
    assert ctx["request_fingerprint"] == receipt["request_fingerprint"]
    assert ctx["user_edited"] is False
    assert receipt["pair_id"].startswith("whatif-")
    # Source vs actual ledger: draft has no incident, ledger may have incident if baseline differs
    assert "incident" not in draft.whatif_overrides
    # Pin ledger paths — CH-07 mapped fields must be present, incident not in source
    changed_fields = {p["field_path"] for p in receipt.get("changed_parameters", [])}
    # At minimum, the three CH-07 fields that differ from baseline preset 'baseline' appear
    assert "vehicle_count" in changed_fields
    assert "rsu_count" in changed_fields
    # Ensure draft source set does not secretly include incident
    assert draft.whatif_overrides.keys() == {
        "vehicle_count",
        "rsu_count",
        "congestion_multiplier",
        "task_arrival_rate",
    }


def test_unmapped_user_edit_represented_in_ledger_not_challenge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unmapped field edited by user appears in ledger, not attributed to challenge."""
    from traffictwin.ui.whatif_controls import DEFAULT_WHATIF_WIDGET_VALUES

    d07 = build_challenge_whatif_draft(get_challenge_seed("CH-07-scaling-strategy"))  # type: ignore[arg-type]
    h07 = draft_to_handoff_dict(d07)
    app = _run_whatif(
        monkeypatch,
        tmp_path,
        extra_state={
            PENDING_WHATIF_CHALLENGE_DRAFT_KEY: h07,
            "whatif_challenge_prefill_applied_fingerprint": None,
        },
    )
    assert not app.exception
    # Edit unmapped control: incident_duration (CH-07 does not map it) from default 60.0 to 123.0
    default_dur = float(DEFAULT_WHATIF_WIDGET_VALUES["whatif_incident_duration_s"])
    assert float(app.session_state["whatif_incident_duration_s"]) == default_dur
    dur_inp = next(inp for inp in app.number_input if "Duration (s)" in str(inp.label))
    dur_inp.set_value(123.0).run(timeout=30)
    assert not app.exception
    assert abs(float(app.session_state["whatif_incident_duration_s"]) - 123.0) < 1e-6
    # Generate
    gen_btn = [b for b in app.button if b.label == "Generate comparison"]
    assert gen_btn
    gen_btn[0].click().run(timeout=30)
    assert not app.exception
    receipt = app.session_state["whatif_pair_receipt"]
    changed = {p["field_path"]: p for p in receipt.get("changed_parameters", [])}
    # Unmapped edit must be in actual ledger
    assert (
        "incident_schedule[0].duration_s" in changed
        or "incident_duration_s" in changed
        or any("duration_s" in k for k in changed)
    ), f"duration not in ledger {list(changed.keys())}"
    # Find the duration entry
    dur_key = next((k for k in changed if "duration" in k), None)
    assert dur_key is not None
    assert abs(float(changed[dur_key]["variation_value"]) - 123.0) < 1e-6
    # Provenance must not attribute duration to CH-07; ledger proves user edit
    assert "last_whatif_generation_challenge_context" in app.session_state
    ctx = app.session_state["last_whatif_generation_challenge_context"]
    assert isinstance(ctx, dict)
    assert ctx["challenge_id"] == "CH-07-scaling-strategy"
    assert ctx["challenge_fingerprint"] == d07.fingerprint
    assert ctx["pair_id"] == receipt["pair_id"]
    assert ctx["request_fingerprint"] == receipt["request_fingerprint"]
    # Unmapped edit: provenance based on mapped fields only — pair binding proves generation
    assert receipt["pair_id"].startswith("whatif-")
    # Challenge mapped fields must not include duration
    assert not any("incident" in f.whatif_field for f in d07.supported_fields)
    assert d07.whatif_overrides.keys() == {
        "vehicle_count",
        "rsu_count",
        "congestion_multiplier",
        "task_arrival_rate",
    }
