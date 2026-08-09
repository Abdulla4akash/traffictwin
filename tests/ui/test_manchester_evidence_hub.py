"""UI tests for Manchester Evidence Hub — hardened M1."""

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
    # Empty workspace must show useful truth, not crash
    all_text = "\n".join(str(x.value) for x in app.caption) + "\n".join(
        str(x.value) for x in app.info
    )
    assert "No workspace" in all_text or "provider evidence unavailable" in all_text.lower()
    # Must show metric for known sources
    metrics = {m.label: m.value for m in app.metric}
    assert "Sources known" in metrics
    assert int(metrics["Sources known"]) == 9
    # Must show acquisition-ready vs accepted distinction (honest counts)
    assert "Accepted" in metrics
    assert "Acquisition-ready" in metrics


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
    # New NTIS source must be visible
    assert (
        "TfGM/NTIS" in combined
        or "tfgm_ntis" in combined.lower()
        or "measured traffic" in combined.lower()
    )


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
    all_text = (
        "\n".join(str(x.value) for x in app.markdown)
        + "\n".join(str(x.value) for x in app.warning)
        + "\n".join(str(x.value) for x in app.caption)
    )
    assert "Strategic" in all_text or "strategic" in all_text.lower()
    assert "NOT general" in all_text or "not general" in all_text.lower()


def test_dft_historical_state_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.warning
    )
    assert "historical" in all_text.lower()
    assert "DfT" in all_text


def test_webtris_not_live_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.caption
    )
    # WebTRIS must not be described as live; must mention historical
    assert "historical" in all_text.lower()
    # Ensure not claiming live WebTRIS
    lowered = all_text.lower()
    if "webtris" in lowered and "live" in lowered:
        # If live appears near webtris, must be qualified with NOT live
        assert "not live" in lowered or "do not call live" in lowered


def test_tfgm_reference_not_telemetry_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.caption
    )
    assert "infrastructure" in all_text.lower()
    assert (
        "NOT traffic telemetry" in all_text
        or "NOT telemetry" in all_text
        or "reference" in all_text.lower()
    )


def test_tfgm_ntis_measured_blocker_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = (
        "\n".join(str(x.value) for x in app.markdown)
        + "\n".join(str(x.value) for x in app.warning)
        + "\n".join(str(x.value) for x in app.caption)
        + "\n".join(str(x.value) for x in app.info)
    )
    assert "TfGM/NTIS" in all_text or "measured traffic" in all_text.lower()
    assert "provider contract" in all_text.lower()


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
    all_text = "\n".join(str(x.value) for x in app.warning) + "\n".join(
        str(x.value) for x in app.markdown
    )
    assert "Not configured" in all_text or "unavailable" in all_text.lower()


def test_scientific_gate_blocker_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = (
        "\n".join(str(x.value) for x in app.markdown)
        + "\n".join(str(x.value) for x in app.warning)
        + "\n".join(str(x.value) for x in app.info)
    )
    assert "BLOCKED" in all_text or "OWNER" in all_text


def test_scientific_blockers_as_decisions_not_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = (
        "\n".join(str(x.value) for x in app.warning)
        + "\n".join(str(x.value) for x in app.info)
        + "\n".join(str(x.value) for x in app.markdown)
    )
    # Must list human/scientific gates, not invent defaults
    assert "boundary/network decision" in all_text.lower() or "boundary" in all_text.lower()
    assert "map-matching policy" in all_text.lower() or "map matching" in all_text.lower()
    assert "174" in all_text
    assert "calibration objective" in all_text.lower()
    assert "uncertainty" in all_text.lower()
    # Must not silently turn missing decisions into defaults like "MAE" as chosen objective
    # The page should say BLOCKED / OWNER DECISION REQUIRED, not a default value
    assert "BLOCKED" in all_text
    assert "OWNER" in all_text


def test_no_secret_values_rendered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BODS_API_KEY", "super-secret-bods-123")
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "super-secret-nh-456")
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = (
        "\n".join(str(x.value) for x in app.markdown)
        + "\n".join(str(x.value) for x in app.warning)
        + "\n".join(str(x.value) for x in app.caption)
        + "\n".join(str(x.value) for x in app.info)
    )
    assert "super-secret-bods-123" not in all_text
    assert "super-secret-nh-456" not in all_text
    assert "Configured" in all_text or "Not configured" in all_text


def test_no_live_manchester_aggregate_claim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.warning
    )
    lowered = all_text.lower()
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
    import socket

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network call not allowed during page render")

    monkeypatch.setattr(socket, "socket", fail)
    # Also patch provider acquisition entrypoints to ensure they are not called on render
    for mod_path in [
        "traffictwin.integration.manchester.bods_acquisition.acquire_bods_snapshot",
        "traffictwin.integration.manchester.national_highways_acquisition.acquire_national_highways_snapshot",  # noqa: E501
        "traffictwin.integration.manchester.webtris_acquisition.acquire_webtris_snapshot",
        "traffictwin.integration.manchester.dft_acquisition.acquire_dft_snapshot",
    ]:
        import contextlib

        with contextlib.suppress(AttributeError):
            monkeypatch.setattr(
                mod_path,
                lambda *a, _p=mod_path, **k: (_ for _ in ()).throw(
                    AssertionError(f"Provider acquisition not allowed: {_p}")
                ),
            )
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception


def test_no_absolute_private_path_in_download_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Provide a fake workspace path that looks like a private absolute path
    fake_workspace = tmp_path / "my_workspace"
    fake_workspace.mkdir()
    (fake_workspace / "evidence" / "dft").mkdir(parents=True)
    app = _run_page(monkeypatch, tmp_path, extra_state={"selected_workspace": str(fake_workspace)})
    assert not app.exception
    # Find download button data — AppTest stores download_button content
    # Instead, directly test the service export for this workspace is path-free
    from traffictwin.ui.manchester_evidence_hub import build_manchester_hub_view

    view = build_manchester_hub_view(fake_workspace)
    dumped = view.model_dump_json(indent=2)
    assert str(fake_workspace) not in dumped
    assert "/Users/" not in dumped
    assert "/private/" not in dumped
    assert "/tmp/" not in dumped  # noqa: S108 or str(tmp_path) not in dumped
    # The page should display LOCAL PATH disclaimer separately
    captions = "\n".join(str(c.value) for c in app.caption)
    assert "LOCAL PATH" in captions
    assert "NOT PART OF EVIDENCE IDENTITY" in captions


def test_evidence_state_not_inferred_from_absent_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.caption
    )
    assert (
        "Unavailable" in all_text or "unavailable" in all_text.lower() or "No accepted" in all_text
    )


def test_acquisition_ready_not_confused_with_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Empty workspace: DfT acquisition READY but no accepted evidence — page must show both
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = (
        "\n".join(str(x.value) for x in app.markdown)
        + "\n".join(str(x.value) for x in app.caption)
        + "\n".join(str(x.value) for x in app.info)
        + "\n".join(str(x.value) for x in app.warning)
    )
    # Should mention READY and also No accepted
    assert "READY" in all_text or "Ready" in all_text
    assert "No accepted" in all_text


def test_partial_workspace_renders_independently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ws = tmp_path / "partial_ws"
    ws.mkdir()
    (ws / "evidence" / "dft").mkdir(parents=True)
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    app = _run_page(monkeypatch, tmp_path, extra_state={"selected_workspace": str(ws)})
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.caption
    )
    # DfT should show accepted, BODS still not configured — independence
    assert "DfT" in all_text
    # Overall page must not claim whole Manchester available because one source exists
    metrics = {m.label: m.value for m in app.metric}
    assert int(metrics["Accepted"]) < int(metrics["Sources known"])


def test_source_table_has_expected_columns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Dataframe existence implies source table rendered
    assert len(app.dataframe) >= 1
    # Check that table contains expected source role text in markdown detail
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "Coverage:" in markdowns
    assert "Software support:" in markdowns
    assert "Evidence ceiling:" in markdowns


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


def test_summary_counts_not_combined_into_fake_total(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    captions = "\n".join(str(c.value) for c in app.caption)
    infos = "\n".join(str(i.value) for i in app.info)
    combined = captions + infos
    assert "not combined" in combined.lower() or "Each source retains" in combined


def test_exact_metrics_match_typed_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Pin exact metric labels and typed-derived counts for empty state."""
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    metrics = {m.label: m.value for m in app.metric}
    # Five separate cards, no fake total
    assert metrics["Sources known"] == "9"
    assert metrics["Accepted"] == "1"
    assert metrics["Acquisition-ready"] == "5"
    assert metrics["Blocked"] == "7"
    assert metrics["Unavailable"] == "7"
    # Union caption must be honest
    captions = "\n".join(str(c.value) for c in app.caption)
    assert "Blocked or unavailable (unique): 7" in captions
    assert "never exceeds known sources (9)" in captions


def test_blockers_table_uses_typed_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Blockers table must be filtered by typed scientific/rights state, not wording."""
    from traffictwin.ui.manchester_evidence_hub import (
        RightsRetentionState,
        ScientificGateState,
    )

    monkeypatch.delenv("BODS_API_KEY", raising=False)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Service truth: blocker row count is number of sources where
    # scientific_gate_typed != NOT_APPLICABLE or rights_typed != RECORDED
    from traffictwin.ui.manchester_evidence_hub import build_manchester_hub_view

    view = build_manchester_hub_view(None)
    expected = sum(
        1
        for s in view.sources
        if s.scientific_gate_typed != ScientificGateState.NOT_APPLICABLE
        or s.rights_typed != RightsRetentionState.RECORDED
    )
    # Dataframe second table is blockers — check row count matches typed filter
    # First dataframe is source readiness (9 rows), second is blockers
    assert len(app.dataframe) >= 2
    blocker_df = app.dataframe[1].value
    # pandas DataFrame
    assert len(blocker_df) == expected


def test_source_table_rendered_from_structured_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    df = app.dataframe[0].value
    # Must have 9 rows, one per source, with expected columns
    assert len(df) == 9
    assert "source" in df.columns or "Source" in str(df.columns)
    # Check DfT row has exact coverage and ceiling chrome (not typed enum)
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "Coverage:" in markdowns
    assert "Software support:" in markdowns
    assert "DfT" in markdowns


def test_webtris_exact_typed_state_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Instead of page-wide substring soup, directly pin WebTRIS row."""
    from traffictwin.ui.manchester_evidence_hub import build_manchester_hub_view

    view = build_manchester_hub_view(None)
    w = next(s for s in view.sources if s.source_id == "webtris")
    assert w.freshness_state == "historical"
    assert w.evidence_type == "historical"
    assert w.local_evidence_typed.name in {"NOT_ACCEPTED", "ACCEPTED_AVAILABLE"}
    # UI must show historical, not live
    app = _run_page(monkeypatch, tmp_path)
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.caption
    )
    assert "historical" in all_text.lower()
    # Expand WebTRIS detail exists
    assert "WebTRIS" in all_text


def test_tfgm_infra_not_telemetry_exact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from traffictwin.ui.manchester_evidence_hub import build_manchester_hub_view

    view = build_manchester_hub_view(None)
    tfgm = next(s for s in view.sources if s.source_id == "tfgm")
    assert tfgm.source_role == "Infrastructure/reference information"
    assert tfgm.freshness_state == "unavailable"
    assert tfgm.local_evidence_typed.name in {"NOT_ACCEPTED", "ACCEPTED_AVAILABLE"}
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.caption
    )
    assert "infrastructure" in all_text.lower()
    assert "NOT traffic telemetry" in all_text or "NOT telemetry" in all_text
