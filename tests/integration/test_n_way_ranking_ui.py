from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from tests.statistical_helpers import study_collection

from traffictwin.domain.experiment import Experiment
from traffictwin.experiments.n_way_ranking import NWayRankingStatus, NWayRankingStudy
from traffictwin.metrics.results import MetricCollection
from traffictwin.storage.registry import Registry


def _collection(algorithm: str, random_seed: int, value: float) -> MetricCollection:
    collection = study_collection(
        "baseline",
        random_seed,
        value,
        run_id=f"run-{algorithm}-{random_seed}",
        experiment_id="exp-nway",
        algorithm=algorithm,
    )
    return collection.model_copy(
        update={
            "results": [
                metric.model_copy(update={"seed_id": "seed-family"})
                for metric in collection.results
            ]
        }
    )


def test_streamlit_statistical_page_runs_n_way_registered_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.sqlite"
    registry = Registry(registry_path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-nway",
            research_question="N-way Streamlit plan",
            baseline_seed_id="seed-family",
            algorithms=["policy-a", "policy-b", "policy-c"],
            common_random_seed_set=[1, 2, 3],
            planned_replicates=3,
        )
    )
    for seed in (1, 2, 3):
        for algorithm, value in {
            "policy-a": 0.9,
            "policy-b": 0.7,
            "policy-c": 0.5,
        }.items():
            collection = _collection(algorithm, seed, value)
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
        "N-way policy ranking (STA-02)"
    ).run(timeout=10)
    next(button for button in app.button if button.label == "Evaluate N-way ranking").click().run(
        timeout=10
    )

    result = app.session_state["n_way_ranking_study"]
    assert not app.exception
    assert isinstance(result, NWayRankingStudy)
    assert result.status is NWayRankingStatus.AVAILABLE
    assert any(
        heading.value == "N-Way Policy Ranking And Common-Seed Audit" for heading in app.subheader
    )
    assert {button.label for button in app.download_button} >= {
        "Download NWayRankingStudy JSON",
        "Download N-Way Markdown",
        "Download N-Way Audit CSV",
    }
