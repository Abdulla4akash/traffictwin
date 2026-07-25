from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path

from pytest import MonkeyPatch

from traffictwin.experiments.scenario_mutation import (
    MutationOperator,
    ScenarioMutationRequest,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.services import (
    ServiceError,
    execute_scenario_mutation_for_ui,
    prepare_scenario_mutation_for_ui,
    scenario_mutation_catalog_for_ui,
)
from traffictwin.ui.state import default_session_state, load_ui_config

FIXTURE = Path("tests/fixtures/bundles/baseline_valid")


def test_scenario_mutation_ui_service_plans_and_executes(tmp_path: Path) -> None:
    catalog = scenario_mutation_catalog_for_ui()
    assert catalog.max_changed_rows == 20_000
    assert MutationOperator.RSU_REMOVAL in catalog.operators

    request = prepare_scenario_mutation_for_ui(
        parent_bundle=FIXTURE,
        mutation_id="mutation-ui-service",
        title="UI dropout",
        description="Bounded test",
        operator=MutationOperator.ROW_DROPOUT.value,
        table_kind="tasks",
        drop_fraction=0.25,
        max_absolute_jitter_s=1.0,
        rsu_id="rsu-2",
        random_seed=17,
    )
    assert isinstance(request, ScenarioMutationRequest)

    result = execute_scenario_mutation_for_ui(FIXTURE, request, tmp_path / "mutation")
    assert not isinstance(result, ServiceError)
    assert result.changed_row_count == 1
    assert result.validation_may_import


def test_scenario_mutation_ui_service_rejects_missing_rsu() -> None:
    result = prepare_scenario_mutation_for_ui(
        parent_bundle=FIXTURE,
        mutation_id="mutation-ui-invalid",
        title="Invalid",
        description="",
        operator=MutationOperator.RSU_REMOVAL.value,
        table_kind="tasks",
        drop_fraction=0.25,
        max_absolute_jitter_s=1.0,
        rsu_id="rsu-99",
        random_seed=17,
    )

    assert isinstance(result, ServiceError)
    assert "absent" in (result.detail or "")


def test_streamlit_scenario_mutation_builds_validated_copy(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "exports").mkdir(parents=True)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.SCENARIO_MUTATION)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=10)

    assert not app.exception
    assert any(title.value == "Scenario Mutations" for title in app.title)
    next(button for button in app.button if button.label == "Build Mutated Copy").click().run(
        timeout=20
    )

    assert not app.exception
    assert any(heading.value == "Mutation result" for heading in app.subheader)
    output = workspace / "exports" / "scenario-mutations" / "mutation-ui"
    assert (output / "mutation_manifest.json").is_file()
    assert (output / "bundle" / "manifest.yaml").is_file()
