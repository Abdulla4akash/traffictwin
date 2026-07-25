from __future__ import annotations

import csv
import io
from copy import deepcopy
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import yaml
from pytest import MonkeyPatch
from tests.unit.test_registry import make_seed

from traffictwin.storage.registry import Registry
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.services import (
    ServiceError,
    build_experiment_protocol_for_ui,
    experiment_plan_yaml_for_ui,
    experiment_protocol_csv_for_ui,
    experiment_protocol_yaml_for_ui,
    load_experiment_planner_catalog,
    load_registered_experiment_protocol_for_ui,
    prepare_experiment_plan_for_ui,
    register_experiment_plan_for_ui,
)
from traffictwin.ui.state import default_session_state, load_ui_config


def _planner_registry(path: Path) -> Registry:
    registry = Registry(path)
    baseline = make_seed()
    variation = baseline.model_copy(
        update={
            "seed_id": "s1-gridlock-stressed",
            "name": "Stressed gridlock",
            "demand": baseline.demand.model_copy(update={"multiplier": 3.0}),
        }
    )
    registry.add_seed(baseline)
    registry.add_seed(variation)
    return registry


def test_planner_service_previews_exports_and_registers_without_runs(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    registry = _planner_registry(registry_path)
    catalog = load_experiment_planner_catalog(registry_path)

    assert not isinstance(catalog, ServiceError)
    assert [seed.seed_id for seed in catalog.seeds] == [
        "s1-gridlock-stressed",
        "s1-gridlock-x2",
    ]
    assert catalog.algorithms == ["MAPPO"]

    fixed = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    summary = prepare_experiment_plan_for_ui(
        experiment_id="exp-ui-plan",
        research_question="Does demand change outcomes?",
        hypothesis="The stressed seed may reduce completion.",
        baseline_seed_id="s1-gridlock-x2",
        variation_seed_ids=["s1-gridlock-stressed"],
        algorithms=["MAPPO"],
        additional_algorithm_labels="synthetic-reference",
        common_random_seeds="7, 8",
        registered_seeds=catalog.seeds,
        clock=lambda: fixed,
    )

    assert not isinstance(summary, ServiceError)
    assert summary.planned_run_count == 8
    document = yaml.safe_load(experiment_plan_yaml_for_ui(summary))
    assert document["experiment_id"] == "exp-ui-plan"
    assert document["status"] == "planned"
    assert document["created_at"] == "2026-07-18T12:00:00Z"
    protocol = build_experiment_protocol_for_ui(summary.experiment, catalog.seeds)
    assert not isinstance(protocol, ServiceError)
    assert len(protocol.slots) == 8
    assert len(list(csv.DictReader(io.StringIO(experiment_protocol_csv_for_ui(protocol))))) == 8
    protocol_document = yaml.safe_load(experiment_protocol_yaml_for_ui(protocol))
    assert protocol_document["direct_launch_supported"] is False

    registered = register_experiment_plan_for_ui(summary, registry_path)
    assert not isinstance(registered, ServiceError)
    assert registry.get_experiment("exp-ui-plan") == registered
    assert registry.inspect().run_count == 0

    duplicate = register_experiment_plan_for_ui(summary, registry_path)
    assert isinstance(duplicate, ServiceError)
    assert "already exists" in (duplicate.detail or "")
    restored = load_registered_experiment_protocol_for_ui("exp-ui-plan", registry_path)
    assert not isinstance(restored, ServiceError)
    assert restored == protocol


def test_planner_service_rejects_invalid_random_seed_input(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    _planner_registry(registry_path)
    catalog = load_experiment_planner_catalog(registry_path)
    assert not isinstance(catalog, ServiceError)

    result = prepare_experiment_plan_for_ui(
        experiment_id="exp-invalid",
        research_question="Is this plan valid?",
        hypothesis="",
        baseline_seed_id="s1-gridlock-x2",
        variation_seed_ids=[],
        algorithms=["MAPPO"],
        additional_algorithm_labels="",
        common_random_seeds="7, seven",
        registered_seeds=catalog.seeds,
    )

    assert isinstance(result, ServiceError)
    assert "comma-separated integers" in (result.detail or "")


def test_streamlit_experiment_planner_validates_and_registers(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.sqlite"
    registry = _planner_registry(registry_path)
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(registry_path))

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.EXPERIMENT_PLANNER)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=10)

    assert not app.exception
    assert any(title.value == "Experiment Planner" for title in app.title)
    next(field for field in app.text_input if field.label == "Experiment ID").set_value(
        "exp-apptest-plan"
    )
    next(button for button in app.button if button.label == "Validate Plan").click().run(timeout=10)

    assert not app.exception
    assert any(heading.value == "Validated Plan Preview" for heading in app.subheader)
    assert any(heading.value == "Execution Protocol" for heading in app.subheader)
    next(
        button for button in app.button if button.label == "Register Planned Experiment"
    ).click().run(timeout=10)

    assert not app.exception
    assert registry.get_experiment("exp-apptest-plan").status.value == "planned"
    assert registry.inspect().run_count == 0
    app.run(timeout=10)
    assert any(heading.value == "Registered Protocol Export" for heading in app.subheader)


def test_streamlit_home_renders_workspace_planner_actions(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "reports").mkdir(parents=True)
    (workspace / "exports").mkdir()
    registry_path = workspace / "registry.sqlite"
    _planner_registry(registry_path)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(registry_path))
    # The planner quick actions belong to the complete v0.6 home, which stays
    # reachable through the explicit legacy compatibility route.
    monkeypatch.setenv("TRAFFICTWIN_V07_NAVIGATION", "legacy")

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)

    assert not app.exception
    # The contract this pins is reachability: the legacy v0.6 home offers the
    # planner from both its workflow row and its quick actions. It previously
    # asserted two buttons carrying the *same* label, which is what made them
    # indistinguishable to keyboard and screen-reader users. The labels now
    # differ; both routes still exist.
    planner_labels = [
        button.label for button in app.button if "Plan an Experiment" in (button.label or "")
    ]
    assert len(planner_labels) == 2, planner_labels
    assert len(set(planner_labels)) == 2, (
        f"both planner routes must be distinguishable: {planner_labels}"
    )
