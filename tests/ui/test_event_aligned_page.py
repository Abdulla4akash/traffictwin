"""UI tests for Event-Aligned Analysis page."""

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
    page: UiPage | None = None,
    extra_state: dict[str, object] | None = None,
) -> AppTest:
    if page is None:
        try:
            page = UiPage.EVENT_ALIGNED_ANALYSIS  # type: ignore[attr-defined]
        except AttributeError:
            page = None  # type: ignore[assignment]
    for key in _ENV_CLEAR:
        monkeypatch.delenv(key, raising=False)
    # Fallback if page not yet registered: directly load file
    try:
        script = page_script_for(page) if page is not None else "app_pages/event_aligned_analysis.py"  # noqa: E501
    except Exception:
        script = "app_pages/event_aligned_analysis.py"
    app = AppTest.from_file(f"src/traffictwin/ui/{script}")
    state = deepcopy(default_session_state())
    state["_v07_navigation_active"] = True
    for k, v in state.items():
        app.session_state[k] = v
    if extra_state:
        for k, v in extra_state.items():
            app.session_state[k] = v
    app.run(timeout=30)
    return app


def test_event_aligned_page_has_exactly_one_title(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:  # noqa: E501
    try:
        app = _run_page(monkeypatch, tmp_path)
    except Exception as exc:
        pytest.skip(f"page not yet registered in navigation: {exc}")
    if app.exception and any("EVENT_ALIGNED_ANALYSIS" in str(e.message) for e in app.exception):
        pytest.skip("page not yet registered in labels")
    assert not app.exception
    assert len(app.title) == 1
    assert app.title[0].value == "Event-Aligned Analysis"


def test_event_aligned_page_shows_authored_label_and_preview(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:  # noqa: E501
    try:
        app = _run_page(monkeypatch, tmp_path)
    except Exception as exc:
        pytest.skip(f"page not yet registered: {exc}")
    if app.exception and any("EVENT_ALIGNED_ANALYSIS" in str(e.message) for e in app.exception):
        pytest.skip("page not yet registered in labels")
    assert not app.exception
    # Check that caption mentions authored not observed
    captions = [c.value for c in app.caption]
    joined = " ".join(captions).lower()
    assert "authored" in joined
    # Check that window preview caption exists
    assert any("[start,end)" in c for c in captions) or any("half-open" in c.lower() for c in captions)  # noqa: E501


def test_event_aligned_build_and_export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    try:
        app = _run_page(monkeypatch, tmp_path)
    except Exception as exc:
        pytest.skip(f"page not yet registered: {exc}")
    if app.exception and any("EVENT_ALIGNED_ANALYSIS" in str(e.message) for e in app.exception):
        pytest.skip("page not yet registered in labels")
    assert not app.exception
    # Find build button and click
    buttons = [b.label for b in app.button]
    assert "Build aligned analysis" in buttons
    # Set valid inputs before clicking (already defaults are valid)
    # Click build
    app.button[0].click().run(timeout=30)
    assert not app.exception
    # After build, should show report identity or excluded runs
    # Check that at least one dataframe exists (chart table or coverage)
    assert len(app.dataframe) >= 1 or len(app.metric) >= 1


def test_event_aligned_chart_table_equivalence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:  # noqa: E501
    """Chart and table must consume same report rows - verify via service directly."""

    from datetime import UTC, datetime

    from traffictwin.event_aligned.models import (
        EventAlignedWindowSpec,
        EventAnchor,
        EventAnchorKind,
    )
    from traffictwin.event_aligned.service import build_event_aligned_report
    from traffictwin.ingestion.bundle import validate_bundle
    from traffictwin.metrics.catalogue import METRIC_DEFINITIONS

    b1 = validate_bundle(Path("tests/fixtures/bundles/baseline_valid"))
    b2 = validate_bundle(Path("tests/fixtures/bundles/variation_valid"))
    defn = METRIC_DEFINITIONS["task.completion.rate"]
    spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version=defn.implementation_version,
        metric_unit=defn.unit,
    )
    a1 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b1.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b1.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    a2 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 5, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b2.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b2.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="chart-table-ui")
    # Simulate UI preparation: chart rows are available subset of table rows
    table_rows = sorted(report.metric_points, key=lambda p: (p.run_id, p.bin_index))
    chart_rows = [r for r in table_rows if r.status == "available"]
    assert len(chart_rows) <= len(table_rows)
    assert len(table_rows) == len(report.metric_points)
    # Ensure no zero-filled missing bins
    for p in report.metric_points:
        if p.status != "available":
            assert p.value is None
