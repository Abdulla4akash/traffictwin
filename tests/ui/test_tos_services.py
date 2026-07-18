from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from tests.tos_helpers import write_tos_package

from traffictwin.ui.services import (
    ServiceError,
    analyse_tos_run_for_ui,
    compare_tos_runs_for_ui,
    inspect_tos_for_ui,
    load_tos_replay_for_ui,
)


def test_tos_ui_services_use_integration_pipeline(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    view = inspect_tos_for_ui(package, deep=True)
    assert not isinstance(view, ServiceError)

    baseline = "tos:baseline:wd_am:uk2030:fs0"
    variation = "tos:capscalar_mappo:wd_am:uk2030:fs0"
    analysis = analyse_tos_run_for_ui(view, baseline)
    comparison = compare_tos_runs_for_ui(view, baseline, variation)
    frame = load_tos_replay_for_ui(package, "baseline_uk2030_wd_am_fs0", 0)

    assert not isinstance(analysis, ServiceError)
    assert not isinstance(comparison, ServiceError)
    assert not isinstance(frame, ServiceError)
    by_key = {item.metric_key: item for item in comparison.comparable_metrics}
    assert by_key["tos.task.deadline_success.rate"].absolute_delta == pytest.approx(0.03)
    assert analysis.diagnostic_report.insufficient_rule_ids == ["R1", "R2", "R3"]
    assert frame.rsus[0].semantics_status == "unresolved"


def test_streamlit_tos_page_renders_without_package() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("TOS Data Import").run(timeout=10)

    assert not app.exception
