from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from tests.statistical_helpers import study_collections

from traffictwin.domain.experiment import Experiment
from traffictwin.experiments.equivalence_testing import (
    EquivalenceConclusion,
    EquivalenceStudy,
)
from traffictwin.storage.registry import Registry


def test_streamlit_statistical_page_runs_registered_equivalence_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.sqlite"
    registry = Registry(registry_path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-paired",
            research_question="Equivalence Streamlit plan",
            baseline_seed_id="seed-baseline",
            variation_seed_ids=["seed-variation"],
            algorithms=["policy-a"],
            common_random_seed_set=[1, 2, 3, 4, 5],
            planned_replicates=5,
        )
    )
    for collection in study_collections([-0.01, 0.0, 0.01, 0.005, -0.005]):
        registry.store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(registry_path))

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Statistical Study").run(timeout=10)
    next(radio for radio in app.radio if radio.label == "Study type").set_value(
        "Paired equivalence TOST (STA-03)"
    ).run(timeout=10)
    next(
        button for button in app.button if button.label == "Evaluate equivalence study"
    ).click().run(timeout=10)

    result = app.session_state["equivalence_study"]
    assert not app.exception
    assert isinstance(result, EquivalenceStudy)
    assert result.tost.conclusion is EquivalenceConclusion.DEMONSTRATED
    assert any(
        heading.value == "Paired TOST Equivalence Result And Common-Seed Audit"
        for heading in app.subheader
    )
    assert {button.label for button in app.download_button} >= {
        "Download EquivalenceStudy JSON",
        "Download Equivalence Markdown",
        "Download Equivalence Audit CSV",
    }
