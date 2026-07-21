from __future__ import annotations

from dataclasses import replace
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
    load_tos_rsu_series_for_ui,
    tos_readiness_for_ui,
    tos_results_for_ui,
    tos_supervisor_pack_for_ui,
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
    rsu_series = load_tos_rsu_series_for_ui(package, "baseline_uk2030_wd_am_fs0")

    assert not isinstance(analysis, ServiceError)
    assert not isinstance(comparison, ServiceError)
    assert not isinstance(frame, ServiceError)
    assert not isinstance(rsu_series, ServiceError)
    by_key = {item.metric_key: item for item in comparison.comparable_metrics}
    assert by_key["tos.task.deadline_success.rate"].absolute_delta == pytest.approx(0.03)
    assert analysis.diagnostic_report.insufficient_rule_ids == [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
        "R7",
        "R8",
    ]
    assert frame.rsus[0].semantics_status == "confirmed_from_vec_env_source"
    assert rsu_series[0].concurrency_pressure_fraction == pytest.approx(0.2)
    assert view.source_contract.execution.direct_launch.value == "false"


def test_streamlit_tos_page_renders_without_package() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("TOS Data Import").run(timeout=10)

    assert not app.exception


def test_tos_result_campaigns_are_scoped_to_selected_fleet(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    view = inspect_tos_for_ui(package)
    assert not isinstance(view, ServiceError)
    small_only = view.evaluation_runs[0].model_copy(
        update={"campaign": "small_only", "eval_fleet": "small"}
    )
    mixed_view = replace(view, evaluation_runs=[*view.evaluation_runs, small_only])

    result = tos_results_for_ui(mixed_view, evaluation_fleet="uk2030")

    assert not isinstance(result, ServiceError)
    assert "small_only" not in result.campaigns


def test_tos_ui_exposes_readiness_and_private_supervisor_archive(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    view = inspect_tos_for_ui(package)
    assert not isinstance(view, ServiceError)

    readiness = tos_readiness_for_ui(view)
    archive = tos_supervisor_pack_for_ui(view, variation_campaign="capscalar_mappo")

    assert not isinstance(readiness, ServiceError)
    assert readiness.capabilities["direct_launch"].value == "blocked"
    assert isinstance(archive, bytes)
    assert archive.startswith(b"PK")


def test_streamlit_tos_page_inspects_source_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = write_tos_package(tmp_path / "tos")
    monkeypatch.setenv("TRAFFICTWIN_TOS_DATA_PATH", str(package))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("TOS Data Import").run(timeout=10)
    app.button[0].click().run(timeout=15)

    assert not app.exception
    assert any("Semantics evidence commit" in item.value for item in app.caption)
    assert any(item.label == "Load RSU Pressure History" for item in app.button)
