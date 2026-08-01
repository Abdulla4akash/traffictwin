"""VEC outcome predictor (platform slice 2, design §7 test list).

Tested against the COMMITTED fit artifact only — no test reads ``data/``.
The properties asserted are the design's honesty story: the self-test gate
(a tampered artifact refuses to load), predictions pinned to measured values
at measured points, one typed refusal per taxonomy row, the fit boundary
refusing non-admitted sources by name, and the property that no input can
emerge unlabelled — prediction xor refusal, always.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from traffictwin.platform.outcome_predictor import (
    BASELINE_ACTOR,
    METRIC_CEILING,
    METRIC_DEADLINE,
    METRIC_LATENCY_MEAN,
    METRIC_OFFLOAD,
    METRIC_P50,
    TRAINED_ACTOR,
    LoadedFit,
    OutcomePredictorError,
    PredictionRecord,
    PredictionRefusal,
    VecScenario,
    fit_outcome_predictor,
    load_outcome_predictor_fit,
    predict,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIT_ARTIFACT = REPO_ROOT / "docs" / "platform" / "outcome_predictor_fit.json"


@pytest.fixture(scope="module")
def loaded() -> LoadedFit:
    return load_outcome_predictor_fit(FIT_ARTIFACT)


def _scenario(
    trace: str,
    capacity: float,
    actor: str = TRAINED_ACTOR,
    *,
    fleet_preset: str = "uk2030",
    fleet_size: int | None = None,
) -> VecScenario:
    return VecScenario(
        trace=trace,
        capacity=capacity,
        actor=actor,
        fleet_preset=fleet_preset,
        fleet_size=fleet_size,
    )


def _metric(record: PredictionRecord, name: str) -> float:
    for metric in record.metrics:
        if metric.metric == name:
            return metric.point
    raise AssertionError(f"metric {name} absent from record")


# --- the self-test gate ------------------------------------------------------


def test_committed_artifact_loads_and_carries_its_own_digest(loaded: LoadedFit) -> None:
    assert loaded.digest == hashlib.sha256(FIT_ARTIFACT.read_bytes()).hexdigest()
    assert loaded.fit.self_test.passed
    assert len(loaded.fit.sources) == 16
    assert {source.kind for source in loaded.fit.sources} == {
        "campaign_analysis",
        "pilot_dynamics",
        "ceiling_law_verdict",
        "latency_tail_record",
    }


def test_tampered_ceiling_constant_refuses_to_load(tmp_path: Path) -> None:
    payload = json.loads(FIT_ARTIFACT.read_text(encoding="utf-8"))
    payload["ceiling"]["k_ms_per_unit_capacity"] = 41_000.0
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(OutcomePredictorError) as excinfo:
        load_outcome_predictor_fit(path)
    assert excinfo.value.code == "FIT_SELF_TEST_FAILED"


def test_tampered_seed_value_breaks_the_margin_and_refuses(tmp_path: Path) -> None:
    payload = json.loads(FIT_ARTIFACT.read_text(encoding="utf-8"))
    arms = payload["saturated"][TRAINED_ACTOR]["arms"]
    for arm in arms:
        deadline = arm["metrics"].get(METRIC_DEADLINE)
        if deadline is not None and "0" in deadline["seed_values"]:
            deadline["seed_values"]["0"] = deadline["seed_values"]["0"] * 1.1
    path = tmp_path / "tampered-margin.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(OutcomePredictorError) as excinfo:
        load_outcome_predictor_fit(path)
    assert excinfo.value.code == "FIT_SELF_TEST_FAILED"


def test_the_stored_self_test_flag_alone_cannot_authorise(tmp_path: Path) -> None:
    # Flipping the stored pass flag while the constants are broken must not
    # load: the gate recomputes, it does not trust the artifact's own claim.
    payload = json.loads(FIT_ARTIFACT.read_text(encoding="utf-8"))
    payload["p50"]["pinned_ms"] = 47.0
    path = tmp_path / "tampered-p50.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(OutcomePredictorError) as excinfo:
        load_outcome_predictor_fit(path)
    assert excinfo.value.code == "FIT_SELF_TEST_FAILED"


# --- regression pins at measured points --------------------------------------


def test_inc_trained_at_measured_arm_returns_the_measured_values(loaded: LoadedFit) -> None:
    record = predict(_scenario("inc", 2.5), loaded)
    assert isinstance(record, PredictionRecord)
    assert record.regime == "saturated"
    arms = {arm.capacity: arm for arm in loaded.fit.saturated[TRAINED_ACTOR].arms}
    deadline_stat = arms[2.5].metrics[METRIC_DEADLINE]
    assert _metric(record, METRIC_DEADLINE) == deadline_stat.mean
    # The pilot's published seed-0 value is inside the stored pooled table.
    assert deadline_stat.seed_values["0"] == pytest.approx(0.7924845945705774)
    assert _metric(record, METRIC_LATENCY_MEAN) == arms[2.5].metrics[METRIC_LATENCY_MEAN].mean


def test_ceiling_predictions_reproduce_the_law_at_the_deep_arms(loaded: LoadedFit) -> None:
    k = loaded.fit.ceiling.k_ms_per_unit_capacity
    for capacity, published in ((0.5, 19_980.0), (0.25, 9_990.0), (0.1, 3_996.0)):
        record = predict(_scenario("inc", capacity), loaded)
        assert isinstance(record, PredictionRecord)
        point = _metric(record, METRIC_CEILING)
        assert point == pytest.approx(k * capacity)
        # The predeclared verdict values used the rounded published K.
        assert point == pytest.approx(published, rel=1e-4)


def test_p50_is_pinned_and_offload_constants_match_the_records(loaded: LoadedFit) -> None:
    record = predict(_scenario("inc", 1.0), loaded)
    assert isinstance(record, PredictionRecord)
    assert _metric(record, METRIC_P50) == pytest.approx(44.3, abs=0.05)
    assert _metric(record, METRIC_OFFLOAD) == pytest.approx(0.408, abs=0.005)
    baseline = predict(_scenario("inc", 1.0, BASELINE_ACTOR), loaded)
    assert isinstance(baseline, PredictionRecord)
    assert _metric(baseline, METRIC_OFFLOAD) == pytest.approx(0.470, abs=0.005)


def test_off_saturation_prediction_is_the_measured_lookup(loaded: LoadedFit) -> None:
    lookup = next(
        entry for entry in loaded.fit.inert if entry.trace == "we" and entry.actor == TRAINED_ACTOR
    )
    record = predict(_scenario("we", 1.0), loaded)
    assert isinstance(record, PredictionRecord)
    assert record.regime == "measured_inert"
    assert _metric(record, METRIC_DEADLINE) == lookup.metrics[METRIC_DEADLINE].mean
    assert record.sources == (lookup.experiment_id,)
    assert METRIC_P50 in record.metrics_unavailable
    assert METRIC_CEILING in record.metrics_unavailable


def test_baseline_on_inc_never_claims_the_unmeasured_metrics(loaded: LoadedFit) -> None:
    record = predict(_scenario("inc", 1.0, BASELINE_ACTOR), loaded)
    assert isinstance(record, PredictionRecord)
    present = {metric.metric for metric in record.metrics}
    assert METRIC_CEILING not in present
    assert METRIC_P50 not in present
    assert METRIC_CEILING in record.metrics_unavailable
    assert METRIC_P50 in record.metrics_unavailable


# --- regimes -----------------------------------------------------------------


def test_regime_boundaries_follow_the_measured_onsets(loaded: LoadedFit) -> None:
    for trace, onset in (("we", 0.25), ("wd_pm", 0.25), ("ev", 0.1), ("wd_am", 0.1)):
        above = predict(_scenario(trace, onset + 0.01), loaded)
        at = predict(_scenario(trace, onset), loaded)
        assert isinstance(above, PredictionRecord)
        assert isinstance(at, PredictionRecord)
        assert above.regime == "measured_inert"
        assert at.regime == "near_onset"


def test_near_onset_correction_is_faint_and_cites_its_arm(loaded: LoadedFit) -> None:
    inert = predict(_scenario("we", 1.0), loaded)
    near = predict(_scenario("we", 0.25), loaded)
    assert isinstance(inert, PredictionRecord)
    assert isinstance(near, PredictionRecord)
    # At we's onset the exact identity broke in LATENCY (sub-microsecond),
    # not in deadline rate — the correction must mirror that measurement.
    assert _metric(near, METRIC_DEADLINE) == _metric(inert, METRIC_DEADLINE)
    latency_delta = _metric(near, METRIC_LATENCY_MEAN) - _metric(inert, METRIC_LATENCY_MEAN)
    assert latency_delta != 0.0
    assert abs(latency_delta) < 0.001
    assert "vec-capacity-deep-we" in near.sources
    deeper = predict(_scenario("we", 0.1), loaded)
    assert isinstance(deeper, PredictionRecord)
    assert _metric(deeper, METRIC_DEADLINE) != _metric(inert, METRIC_DEADLINE)


# --- the refusal taxonomy ----------------------------------------------------


def test_every_refusal_row_fires_with_its_code(loaded: LoadedFit) -> None:
    cases: list[tuple[VecScenario, str]] = [
        (_scenario("berlin", 1.0), "TRACE_NOT_MEASURED"),
        (_scenario("we", 3.0), "CAPACITY_OUT_OF_ENVELOPE"),
        (_scenario("we", 0.05), "CAPACITY_OUT_OF_ENVELOPE"),
        (_scenario("we", 1.0, fleet_preset="synthetic"), "FLEET_PRESET_NOT_MEASURED"),
        (_scenario("inc", 1.0, fleet_size=1216), "DENSITY_GAP"),
        (_scenario("we", 1.0, fleet_size=2488), "TRACE_NOT_MEASURED"),
        (_scenario("we", 1.0, "some_other_checkpoint"), "ACTOR_NOT_MEASURED"),
        (_scenario("we", 1.0, BASELINE_ACTOR), "ACTOR_NOT_MEASURED"),
    ]
    for scenario, expected in cases:
        outcome = predict(scenario, loaded)
        assert isinstance(outcome, PredictionRefusal), scenario
        assert outcome.code == expected
        assert outcome.closing_campaign
        assert outcome.fit_digest == loaded.digest


def test_matching_fleet_size_is_not_a_gap(loaded: LoadedFit) -> None:
    outcome = predict(_scenario("we", 1.0, fleet_size=139), loaded)
    assert isinstance(outcome, PredictionRecord)
    inc = predict(_scenario("inc", 1.0, fleet_size=2488), loaded)
    assert isinstance(inc, PredictionRecord)


# --- the labelling property --------------------------------------------------


def test_no_input_emerges_unlabelled(loaded: LoadedFit) -> None:
    traces = ["we", "ev", "wd_am", "wd_pm", "inc", "berlin"]
    capacities = [0.05, 0.1, 0.25, 0.5, 0.75, 1.3, 2.5, 3.0]
    actors = [TRAINED_ACTOR, BASELINE_ACTOR, "unknown_actor"]
    presets = ["uk2030", "synthetic"]
    fleet_sizes: list[int | None] = [None, 1216]
    for trace in traces:
        for capacity in capacities:
            for actor in actors:
                for preset in presets:
                    for fleet_size in fleet_sizes:
                        outcome = predict(
                            _scenario(
                                trace,
                                capacity,
                                actor,
                                fleet_preset=preset,
                                fleet_size=fleet_size,
                            ),
                            loaded,
                        )
                        assert isinstance(outcome, PredictionRecord | PredictionRefusal)
                        if isinstance(outcome, PredictionRecord):
                            assert outcome.prediction is True
                            assert outcome.evidence is False
                            assert outcome.confirmatory is False
                            assert outcome.fit_digest == loaded.digest
                            assert outcome.metrics, "a prediction must carry metrics"
                            for metric in outcome.metrics:
                                assert (
                                    metric.interval_low <= metric.point <= metric.interval_high
                                ), (outcome.scenario, metric.metric)
                        else:
                            assert outcome.refusal is True
                            assert outcome.evidence is False
                            assert outcome.code in {
                                "TRACE_NOT_MEASURED",
                                "CAPACITY_OUT_OF_ENVELOPE",
                                "FLEET_PRESET_NOT_MEASURED",
                                "DENSITY_GAP",
                                "ACTOR_NOT_MEASURED",
                            }


# --- the fit boundary refuses by name ----------------------------------------


def _fit_from(tmp_path: Path, paths: list[Path]) -> None:
    fit_outcome_predictor(paths, repo_root=tmp_path, generated_at_utc="2026-08-01T00:00:00+00:00")


def test_gpu_track_sources_are_refused_by_name(tmp_path: Path) -> None:
    refused_dir = tmp_path / "data" / "gpu-track"
    refused_dir.mkdir(parents=True)
    path = refused_dir / "campaign_analysis.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(OutcomePredictorError) as excinfo:
        _fit_from(tmp_path, [path])
    assert excinfo.value.code == "NON_ADMITTED_SOURCE_REFUSED"


def test_non_admitted_content_is_refused_by_name(tmp_path: Path) -> None:
    path = tmp_path / "sparse_return.json"
    path.write_text(
        json.dumps({"record_type": "diagnostic", "status": "NON_ADMITTED"}),
        encoding="utf-8",
    )
    with pytest.raises(OutcomePredictorError) as excinfo:
        _fit_from(tmp_path, [path])
    assert excinfo.value.code == "NON_ADMITTED_SOURCE_REFUSED"


def test_incomplete_campaigns_never_enter_the_fit(tmp_path: Path) -> None:
    path = tmp_path / "running.json"
    path.write_text(
        json.dumps(
            {
                "experiment_id": "vec-capacity-squeeze-pilot",
                "campaign_status": "running",
                "primary_descriptives": [],
                "design_fingerprint": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OutcomePredictorError) as excinfo:
        _fit_from(tmp_path, [path])
    assert excinfo.value.code == "CAMPAIGN_NOT_COMPLETED"


def test_unregistered_experiments_never_enter_the_fit(tmp_path: Path) -> None:
    path = tmp_path / "unknown.json"
    path.write_text(
        json.dumps(
            {
                "experiment_id": "vec-sparse64-homecoming",
                "campaign_status": "completed",
                "primary_descriptives": [],
                "design_fingerprint": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OutcomePredictorError) as excinfo:
        _fit_from(tmp_path, [path])
    assert excinfo.value.code == "SOURCE_NOT_REGISTERED"


def test_design_fingerprint_mismatch_refuses(tmp_path: Path) -> None:
    path = tmp_path / "drifted.json"
    path.write_text(
        json.dumps(
            {
                "experiment_id": "vec-capacity-squeeze-pilot",
                "campaign_status": "completed",
                "primary_descriptives": [],
                "design_fingerprint": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OutcomePredictorError) as excinfo:
        _fit_from(tmp_path, [path])
    assert excinfo.value.code == "DESIGN_FINGERPRINT_MISMATCH"
