from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.services import (
    ServiceError,
    build_synthetic_config_from_form,
    generate_synthetic_bundle_for_ui,
    measurement_impairment_contract_for_ui,
    preview_synthetic_scenario,
)
from traffictwin.ui.state import default_session_state, load_ui_config


def _measurement_form() -> dict[str, object]:
    return {
        "scenario_id": "ui-measurement-demo",
        "name": "UI measurement demo",
        "description": "Synthetic bounded measurement robustness input.",
        "experiment_id": "exp-ui-measurement",
        "baseline_seed_id": "",
        "random_seed": 11,
        "duration_s": 120.0,
        "sampling_interval_s": 30.0,
        "vehicle_count": 6,
        "vehicle_low_share": 0.4,
        "vehicle_medium_share": 0.4,
        "vehicle_high_share": 0.2,
        "task_arrival_rate": 0.08,
        "task_mix_t1": 0.3,
        "task_mix_t2": 0.4,
        "task_mix_t3": 0.3,
        "rsu_count": 2,
        "rsu_capacity": 20.0,
        "baseline_network_delay_ms": 45.0,
        "congestion_multiplier": 1.0,
        "policy_behavior": "synthetic-balanced",
        "trip_count": 3,
        "synthetic_faults": "",
        "include_infrastructure": True,
        "include_vehicles": True,
        "include_traffic": True,
        "include_trips": True,
        "include_incidents": True,
        "measurement_imperfections_enabled": True,
        "measurement_random_seed": 31,
        "vehicle_position_max_error_m": 3.0,
        "vehicle_speed_max_error_mps": 1.5,
        "traffic_speed_max_error_mps": 2.0,
        "traffic_count_max_error": 4,
        "infrastructure_utilisation_max_error": 0.1,
        "infrastructure_queue_max_error": 3,
        "infrastructure_dropout_fraction": 0.2,
        "vehicle_dropout_fraction": 0.1,
        "traffic_dropout_fraction": 0.2,
    }


def test_measurement_ui_service_previews_and_generates_audited_bundle(tmp_path: Path) -> None:
    config = build_synthetic_config_from_form(_measurement_form())

    assert not isinstance(config, ServiceError)
    assert config.measurement_imperfections is not None
    preview = preview_synthetic_scenario(config)
    assert "-imp-" in preview.expected_bundle_id
    assert "-imp-" in preview.expected_run_id
    assert preview.summary_rows[-1]["value"] == config.measurement_imperfections.fingerprint()

    generated = generate_synthetic_bundle_for_ui(config, tmp_path / "impaired")
    assert not isinstance(generated, ServiceError)
    manifest = generated.analysis.validation.manifest
    assert manifest is not None
    assert manifest.synthetic_measurement_impairment is not None
    assert generated.analysis.validation.report.may_import

    contract = measurement_impairment_contract_for_ui()
    assert contract.synthetic_only is True
    assert contract.calibrated_sensor_model is False


def test_streamlit_scenario_builder_exposes_working_measurement_controls() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.SCENARIO)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=10)

    assert not app.exception
    assert any(title.value == "Scenario Builder" for title in app.title)
    enabled = next(
        item for item in app.checkbox if item.label == "Enable synthetic measurement imperfections"
    )
    position = next(
        item for item in app.number_input if item.label == "Vehicle position max error (m)"
    )
    enabled.set_value(True)
    position.set_value(2.5)
    next(button for button in app.button if button.label == "Validate Preview").click().run(
        timeout=10
    )

    assert not app.exception
    bundle_id = next(item for item in app.metric if item.label == "Bundle ID")
    assert "-imp-" in bundle_id.value
