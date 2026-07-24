"""Presentation tests for the redesigned Run Overview page."""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.pages.run_overview import ENERGY_KPI_KEYS, KPI_KEYS, PRIMARY_KPI_TITLES
from traffictwin.ui.state import default_session_state


def _app() -> AppTest:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/run_overview.py")
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def test_kpi_keys_remain_stable_for_consumers() -> None:
    assert set(PRIMARY_KPI_TITLES).issubset(KPI_KEYS)
    assert KPI_KEYS["Latency P99"] == "task.latency.p99_ms"
    assert len(ENERGY_KPI_KEYS) == 3


def test_primary_row_shows_four_kpis_with_units() -> None:
    app = _app().run(timeout=25)

    assert not app.exception
    labels = {item.label for item in app.metric}
    assert "Latency P50 (ms)" in labels
    assert "Completion rate" in labels
    assert "Observed-task energy (J)" in labels
    assert "Energy-delay product (J·ms)" in labels
    # Every metric is present: 4 primary + 5 secondary + 3 energy.
    assert len(app.metric) == len(KPI_KEYS) + len(ENERGY_KPI_KEYS)


def test_metric_values_stay_numeric_or_visibly_unavailable() -> None:
    app = _app().run(timeout=25)

    assert not app.exception
    for item in app.metric:
        value = str(item.value)
        numeric = value.replace(".", "", 1).replace("%", "", 1).isdigit()
        assert numeric or value == "Unavailable"
