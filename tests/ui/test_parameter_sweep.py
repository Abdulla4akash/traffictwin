from __future__ import annotations

from importlib import import_module
from pathlib import Path

from pytest import MonkeyPatch

from traffictwin.experiments.parameter_sweep import (
    ParameterSweepMode,
    ParameterSweepRequest,
)
from traffictwin.ui.services import (
    ServiceError,
    execute_parameter_sweep_for_ui,
    parameter_sweep_catalog_for_ui,
    prepare_parameter_sweep_for_ui,
)


def test_parameter_sweep_ui_service_validates_and_executes(tmp_path: Path) -> None:
    catalog = parameter_sweep_catalog_for_ui()
    assert catalog.max_axes == 4
    assert catalog.max_points == 256
    assert "synthetic.task_arrival_rate" in [item.value for item in catalog.parameter_paths]

    request = prepare_parameter_sweep_for_ui(
        sweep_id="sweep-ui-service",
        title="UI service sweep",
        description="A bounded test",
        mode=ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES.value,
        preset_name="baseline",
        axes=[("synthetic.task_arrival_rate", "0.08, 0.12")],
        metric_keys=["task.completion.rate"],
    )
    assert isinstance(request, ParameterSweepRequest)

    result = execute_parameter_sweep_for_ui(request, tmp_path / "sweep")
    assert not isinstance(result, ServiceError)
    assert result.point_count == 2
    assert result.response_row_count == 2


def test_parameter_sweep_ui_service_rejects_invalid_scalar_values() -> None:
    result = prepare_parameter_sweep_for_ui(
        sweep_id="sweep-ui-invalid",
        title="Invalid",
        description="",
        mode=ParameterSweepMode.SEED_SNAPSHOTS.value,
        preset_name="baseline",
        axes=[("synthetic.rsu_count", "[1, 2]")],
        metric_keys=[],
    )

    assert isinstance(result, ServiceError)
    assert "scalar" in (result.detail or "")


def test_streamlit_parameter_sweep_builds_local_response_surface(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "exports").mkdir(parents=True)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Parameter Sweep").run(timeout=10)

    assert not app.exception
    assert any(title.value == "Parameter Sweep" for title in app.title)
    next(button for button in app.button if button.label == "Build Parameter Sweep").click().run(
        timeout=20
    )

    assert not app.exception
    assert any(heading.value == "Sweep Result" for heading in app.subheader)
    assert any(heading.value == "Response Surface" for heading in app.subheader)
    result_path = workspace / "exports" / "parameter-sweeps" / "sweep-ui" / "sweep_result.json"
    assert result_path.is_file()
