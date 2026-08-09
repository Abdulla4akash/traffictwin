"""UI tests for Manchester Evidence Hub."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
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
    tmp_path: Path,
    page: UiPage = UiPage.MANCHESTER_EVIDENCE_HUB,
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


def test_manchester_hub_has_exactly_one_title(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert len(app.title) == 1
    assert app.title[0].value == "Manchester Evidence Hub"


def test_page_renders_with_no_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert app.title[0].value == "Manchester Evidence Hub"


def test_page_renders_with_no_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in ["BODS_API_KEY", "NATIONAL_HIGHWAYS_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception


def test_source_roles_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    subheaders = "\n".join(str(s.value) for s in app.subheader)
    captions = "\n".join(str(c.value) for c in app.caption)
    combined = markdowns + subheaders + captions
    assert "Historical traffic count" in combined or "DfT" in combined
    assert "WebTRIS" in combined
    assert "BODS" in combined


def test_bods_bus_only_warning_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    warnings = "\n".join(str(w.value) for w in app.warning)
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    combined = warnings + markdowns
    assert "bus-only" in combined.lower() or "bus only" in combined.lower()


def test_national_highways_coverage_limitation_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(str(x.value) for x in app.warning) + "\n".join(str(x.value) for x in app.caption)
    assert "Strategic" in all_text or "strategic" in all_text.lower()
    assert "NOT general" in all_text or "not general" in all_text.lower()


def test_dft_historical_state_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(str(x.value) for x in app.warning)
    assert "historical" in all_text.lower()
    assert "DfT" in all_text


def test_manual_incident_authored_input_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    warnings = "\n".join(str(w.value) for w in app.warning)
    captions = "\n".join(str(c.value) for c in app.caption)
    combined = markdowns + warnings + captions
    assert "AUTHORED" in combined or "authored" in combined.lower()


def test_provider_unavailable_states_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.warning) + "\n".join(str(x.value) for x in app.markdown)
    assert "Not configured" in all_text or "unavailable" in all_text.lower()


def test_scientific_gate_blocker_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(str(x.value) for x in app.warning) + "\n".join(str(x.value) for x in app.info)
    assert "BLOCKED" in all_text or "OWNER" in all_text


def test_no_secret_values_rendered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BODS_API_KEY", "super-secret-bods-123")
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "super-secret-nh-456")
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(str(x.value) for x in app.warning) + "\n".join(str(x.value) for x in app.caption) + "\n".join(str(x.value) for x in app.info)
    assert "super-secret-bods-123" not in all_text
    assert "super-secret-nh-456" not in all_text
    # Should show Configured, not secret
    assert "Configured" in all_text or "Not configured" in all_text


def test_no_live_manchester_aggregate_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(str(x.value) for x in app.warning)
    lowered = all_text.lower()
    # Must not claim live Manchester aggregate; disclaimer allowed
    if "live manchester" in lowered:
        assert "no live manchester" in lowered or "not live" in lowered


def test_open_manchester_operations_action_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    buttons = [b.label for b in app.button]
    assert "Open Manchester Operations" in buttons


def test_open_scenario_builder_action_works(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    buttons = [b.label for b in app.button]
    assert "Open Scenario Builder" in buttons


def test_no_network_during_ordinary_render(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Patch socket to ensure no network call
    import socket

    orig = socket.socket

    def fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Network call not allowed during page render")

    monkeypatch.setattr(socket, "socket", fail)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception


def test_evidence_state_not_inferred_from_absent_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Page should show explicit unavailable states, not fake inferred available
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(str(x.value) for x in app.caption)
    assert "Unavailable" in all_text or "unavailable" in all_text.lower() or "No accepted" in all_text


def test_accessibility_heading_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert len(app.subheader) >= 3


def test_hermetic_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in _ENV_CLEAR:
        monkeypatch.setenv(key, "injected")
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert app.title[0].value == "Manchester Evidence Hub"
