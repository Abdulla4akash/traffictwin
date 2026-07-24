from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from tests.statistical_helpers import study_collections

from traffictwin.domain.experiment import Experiment
from traffictwin.experiments.statistical_study import StatisticalStudy, StatisticalStudyStatus
from traffictwin.storage.registry import Registry


def test_streamlit_statistical_study_page_runs_registered_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.sqlite"
    registry = Registry(registry_path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-paired",
            research_question="Common-seed comparison",
            baseline_seed_id="seed-baseline",
            variation_seed_ids=["seed-variation"],
            algorithms=["policy-a"],
            common_random_seed_set=[1, 2, 3],
            planned_replicates=3,
        )
    )
    for collection in study_collections([1.0, 2.0, 3.0]):
        registry.store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(registry_path))
    # This test navigates via the complete v0.6 radio router, which is the explicit
    # legacy compatibility route now that grouped st.navigation is the normal default.
    monkeypatch.setenv("TRAFFICTWIN_V07_NAVIGATION", "legacy")

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Statistical Study").run(timeout=10)
    next(button for button in app.button if button.label == "Evaluate paired study").click().run(
        timeout=10
    )

    result = app.session_state["statistical_study"]
    assert not app.exception
    assert isinstance(result, StatisticalStudy)
    assert result.status is StatisticalStudyStatus.AVAILABLE
    assert any(metric.label == "Eligible pairs" and metric.value == "3" for metric in app.metric)
    assert any(
        heading.value == "Pairing Audit And Statistical Results" for heading in app.subheader
    )
    assert {button.label for button in app.download_button} >= {
        "Download StatisticalStudy JSON",
        "Download Study Markdown",
        "Download Pair Audit CSV",
    }
    # Presentation (Tier 2): the study status is a categorical badge, not a numeric metric,
    # and the results are organised into tabs rather than a flat raw dump.
    assert not any(metric.label == "Study status" for metric in app.metric)
    markdown_text = "\n".join(str(block.value) for block in app.markdown)
    assert "Study status:" in markdown_text
    tab_labels = {str(tab.label) for tab in app.tabs}
    assert {"Results", "Paired observations", "Pairing audit", "Exports & evidence"} <= tab_labels
    # The raw plan/provenance JSON lives only under the Advanced/Evidence expander.
    assert len(app.json) == 1
