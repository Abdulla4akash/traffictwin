"""Synthetic admission, refusal, and STA-01 chain tests for fresh-run admission."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from tests.tos_v2_helpers import (
    V2_SCENARIO,
    build_v2_occupancy_rows,
    build_v2_perstep,
    build_v2_pertask,
    build_v2_trace,
)
from traffictwin.domain.experiment import Experiment
from traffictwin.experiments import (
    ObjectiveDirection,
    PairedStudyConfig,
    evaluate_paired_statistical_study,
)
from traffictwin.experiments.statistical_study import StatisticalStudyStatus
from traffictwin.integration.vec_fresh_admission import (
    VEC_FRESH_ADMISSION_METHOD_VERSION,
    VecFreshAdmissionError,
    VecFreshRunStudyContext,
    VecPairingSeedSource,
    admit_vec_fresh_run,
    build_fresh_run_admission,
    register_fresh_run_admission,
)
from traffictwin.integration.vec_fresh_admission.service import REVIEWED_TRACE_SCENARIOS
from traffictwin.integration.vec_identity import (
    VecIdentitySnapshot,
    build_vehicle_identity_snapshot,
)
from traffictwin.integration.vec_runner.models import (
    PINNED_ACTORS,
    PINNED_REVIEWED_TRACES,
    PINNED_VEC_ENV_COMMIT,
    VecExecutionReceipt,
    VecRunnerFileEvidence,
    VecRunRequest,
    VecRuntimeEvidence,
    output_fingerprint,
)
from traffictwin.integration.vec_science import build_vec_scientific_admission
from traffictwin.integration.vec_task_join import VecTaskJoinError, build_task_join_report
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.storage.registry import Registry

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
SYNTHETIC_TRACE_SHA = "b" * 64
V2_T = 6


def _arrays(
    *, met_drop_seed: int | None = None
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], VecIdentitySnapshot]:
    trace = build_v2_trace()
    perstep = build_v2_perstep()
    pertask = build_v2_pertask()
    if met_drop_seed is not None:
        met = np.asarray(pertask["task_met"]).copy()
        active = np.asarray(pertask["task_active"], dtype=bool)
        flat_indices = np.flatnonzero(active & met)
        drop_count = (met_drop_seed % (flat_indices.size - 1)) + 1
        assert 0 < drop_count < flat_indices.size
        met.flat[flat_indices[:drop_count]] = False
        pertask["task_met"] = met
        successes = met & active
        perstep["veh_done"] = successes.sum(axis=1).astype(perstep["veh_done"].dtype)
        perstep["done"] = successes.sum(axis=(1, 2)).astype(perstep["done"].dtype)
    header, rows = build_v2_occupancy_rows()
    identity = build_vehicle_identity_snapshot(trace, header, rows, scenario=V2_SCENARIO)
    return trace, perstep, pertask, identity


def _receipt(
    *,
    run_id: str = "fresh_unit",
    fleet_seed: int = 0,
    evaluator_seed: int = 0,
    max_steps: int = V2_T,
    rsu_capacity: float = 2.5,
) -> VecExecutionReceipt:
    request = VecRunRequest(
        run_id=run_id,
        trace_file="traces/synthetic.npz",
        trace_sha256=SYNTHETIC_TRACE_SHA,
        actor_id="baseline_model_c_17",
        evaluator_seed=evaluator_seed,
        fleet_seed=fleet_seed,
        rsu_capacity_per_vehicle=rsu_capacity,
        max_steps=max_steps,
        timeout_seconds=600,
    )
    outputs = [
        VecRunnerFileEvidence(
            path=name,
            sha256=char * 64,
            size_bytes=1,
            media_type="application/octet-stream",
            read_only=True,
        )
        for name, char in (("per-step.npz", "1"), ("per-task.npz", "2"), ("run.json", "3"))
    ]
    return VecExecutionReceipt(
        status="completed",
        request=request,
        request_fingerprint=request.fingerprint(),
        preflight_fingerprint="c" * 64,
        argv=[],
        started_at_utc="2026-07-26T00:00:00+00:00",
        finished_at_utc="2026-07-26T00:00:01+00:00",
        elapsed_seconds=1.0,
        exit_code=0,
        timed_out=False,
        cancellation_requested=False,
        runtime=VecRuntimeEvidence(
            python="3.12.4",
            numpy="1.26.4",
            jax="0.4.30",
            jaxlib="0.4.30",
            jax_backend="cpu",
            jax_device_count=1,
            platform="test",
            machine="test",
            processor="test",
            environment_sha256="d" * 64,
        ),
        repositories=[],
        inputs_before=[],
        inputs_after=[],
        logs=[],
        stdout_excerpt="",
        stderr_excerpt="",
        outputs=outputs,
        findings=[],
        output_fingerprint=output_fingerprint(outputs),
        external_repositories_modified=False,
        raw_inputs_modified=False,
        published=True,
    )


def _study(
    *,
    seed_id: str = "cap-2.5",
    source: VecPairingSeedSource = VecPairingSeedSource.FLEET_SEED,
) -> VecFreshRunStudyContext:
    return VecFreshRunStudyContext(
        experiment_id="vec-fresh-unit",
        seed_id=seed_id,
        pairing_seed_source=source,
        synthetic_fixture=True,
    )


def test_admitted_values_match_vec_science_definitions() -> None:
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt()
    record, collection = build_fresh_run_admission(
        trace, perstep, pertask, identity, receipt, _study(), computed_at=NOW
    )
    task_report = build_task_join_report(
        trace, perstep, pertask, identity, run_label="science_parity"
    )
    science = build_vec_scientific_admission(
        trace,
        perstep,
        pertask,
        identity,
        task_report,
        reproduction_report_fingerprint="a" * 64,
        reproduction_grade="numerically_equivalent",
        computed_at=NOW,
        trip_report=None,
    )
    fresh = collection.by_key()
    accepted = science.evidence_pack.metric_collection.by_key()
    assert set(fresh) == set(accepted)
    for key, metric in fresh.items():
        assert metric.status is accepted[key].status, key
        if metric.status is MetricStatus.AVAILABLE:
            assert metric.value == pytest.approx(accepted[key].value), key
    assert record.available_metric_count == 12
    assert record.unavailable_metric_count == 8
    assert record.research_status == "owner_approved_candidate"
    assert record.reproduction_graded is False


def test_metrics_carry_declared_study_context_and_receipt_binding() -> None:
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt(fleet_seed=5)
    record, collection = build_fresh_run_admission(
        trace, perstep, pertask, identity, receipt, _study(), computed_at=NOW
    )
    expected_run_id = f"vec:fresh:{receipt.fingerprint()[:16]}"
    assert record.registry_run_id == expected_run_id
    assert record.registry_bundle_id == f"vec-fresh:{receipt.fingerprint()}"
    assert collection.run_id == expected_run_id
    assert collection.metric_version == VEC_FRESH_ADMISSION_METHOD_VERSION
    for metric in collection.results:
        assert metric.experiment_id == "vec-fresh-unit"
        assert metric.seed_id == "cap-2.5"
        assert metric.random_seed == 5
        assert metric.algorithm == "baseline_model_c_17"
        assert metric.checkpoint == PINNED_ACTORS["baseline_model_c_17"][0]
        assert metric.environment_commit == PINNED_VEC_ENV_COMMIT
        assert metric.synthetic is True
    available = collection.by_key()["tos.task.deadline_success.rate"]
    assert available.metadata["rsu_capacity_per_vehicle"] == 2.5
    assert available.metadata["pairing_seed_source"] == "fleet_seed"


def test_evaluator_seed_pairing_source_is_recorded() -> None:
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt(evaluator_seed=7, fleet_seed=3)
    record, collection = build_fresh_run_admission(
        trace,
        perstep,
        pertask,
        identity,
        receipt,
        _study(source=VecPairingSeedSource.EVALUATOR_SEED),
        computed_at=NOW,
    )
    assert record.pairing_random_seed == 7
    assert all(metric.random_seed == 7 for metric in collection.results)


def test_truncated_execution_is_refused() -> None:
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt(max_steps=2)
    with pytest.raises(VecFreshAdmissionError, match="TRUNCATED_EXECUTION_REFUSED"):
        build_fresh_run_admission(
            trace, perstep, pertask, identity, receipt, _study(), computed_at=NOW
        )


def test_unreviewed_trace_requires_synthetic_label() -> None:
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt()
    study = VecFreshRunStudyContext(
        experiment_id="vec-fresh-unit",
        seed_id="cap-2.5",
        pairing_seed_source=VecPairingSeedSource.FLEET_SEED,
        synthetic_fixture=False,
    )
    with pytest.raises(VecFreshAdmissionError, match="UNREVIEWED_TRACE_REFUSED"):
        build_fresh_run_admission(
            trace, perstep, pertask, identity, receipt, study, computed_at=NOW
        )


def test_operational_path_refuses_synthetic_fixture_context(tmp_path: Path) -> None:
    with pytest.raises(VecFreshAdmissionError, match="synthetic fixture"):
        admit_vec_fresh_run(
            tmp_path,
            tmp_path / "registry.sqlite",
            _study(),
            tos_data_repo=tmp_path,
        )


def test_unreconciled_arrays_fail_closed() -> None:
    trace, perstep, pertask, identity = _arrays()
    met = np.asarray(pertask["task_met"]).copy()
    active = np.asarray(pertask["task_active"], dtype=bool)
    met.flat[np.flatnonzero(active & met)[0]] = False
    pertask["task_met"] = met
    receipt = _receipt()
    with pytest.raises(VecTaskJoinError):
        build_fresh_run_admission(
            trace, perstep, pertask, identity, receipt, _study(), computed_at=NOW
        )


def test_registry_roundtrip_reaches_sta01_paired_study(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    registry = Registry(registry_path)
    registry.add_experiment(
        Experiment(
            experiment_id="vec-fresh-unit",
            research_question=(
                "Does reduced RSU capacity change deadline success on the fixture trace?"
            ),
            baseline_seed_id="cap-2.5",
            variation_seed_ids=["cap-1.0"],
            algorithms=["baseline_model_c_17"],
            common_random_seed_set=[0, 1, 2],
            planned_replicates=3,
        )
    )
    for fleet_seed in (0, 1, 2):
        for seed_id, capacity, met_drop in (
            ("cap-2.5", 2.5, None),
            ("cap-1.0", 1.0, fleet_seed),
        ):
            trace, perstep, pertask, identity = _arrays(met_drop_seed=met_drop)
            receipt = _receipt(
                run_id=f"fresh_{seed_id.replace('.', '_').replace('-', '_')}_{fleet_seed}",
                fleet_seed=fleet_seed,
                rsu_capacity=capacity,
            )
            record, collection = build_fresh_run_admission(
                trace,
                perstep,
                pertask,
                identity,
                receipt,
                _study(seed_id=seed_id),
                computed_at=NOW,
            )
            outcome = register_fresh_run_admission(record, collection, registry_path)
            assert outcome.run_created is True
            assert outcome.metrics_created is True

    payloads = Registry(registry_path).list_metric_collection_json()
    collections = [MetricCollection.model_validate_json(payload) for payload in payloads]
    study_inputs = [
        collection
        for collection in collections
        if collection.results and collection.results[0].experiment_id == "vec-fresh-unit"
    ]
    assert len(study_inputs) == 6
    config = PairedStudyConfig(
        experiment_id="vec-fresh-unit",
        baseline_seed_id="cap-2.5",
        variation_seed_id="cap-1.0",
        algorithm="baseline_model_c_17",
        checkpoint=PINNED_ACTORS["baseline_model_c_17"][0],
        metric_key="tos.task.deadline_success.rate",
        objective=ObjectiveDirection.MAXIMISE,
        bootstrap_repetitions=1_000,
        randomisation_repetitions=1_000,
        expected_random_seeds=[0, 1, 2],
    )
    study = evaluate_paired_statistical_study(study_inputs, config)
    assert study.status is StatisticalStudyStatus.AVAILABLE
    assert study.pairing_audit.eligible_pair_count == 3
    assert study.estimate.mean_paired_difference is not None
    assert study.estimate.mean_paired_difference < 0


def test_repeat_admission_of_same_receipt_confirms_idempotently(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt()
    first, first_collection = build_fresh_run_admission(
        trace, perstep, pertask, identity, receipt, _study(), computed_at=NOW
    )
    created = register_fresh_run_admission(first, first_collection, registry_path)
    assert created.run_created is True

    later = NOW + timedelta(minutes=7)
    second, second_collection = build_fresh_run_admission(
        trace, perstep, pertask, identity, receipt, _study(), computed_at=later
    )
    # The resume defect's trigger: the admission clock leaks into the metric
    # collection, so the stable fingerprints of two admissions of the SAME
    # receipt differ — confirmation must not depend on them matching.
    assert second.stable_fingerprint() != first.stable_fingerprint()
    outcome = register_fresh_run_admission(second, second_collection, registry_path)
    assert outcome.run_created is False
    assert outcome.run_idempotent is True
    assert outcome.metrics_created is False
    assert outcome.registry_run_id == created.registry_run_id


def test_repeat_admission_under_different_study_context_refuses(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt()
    record, collection = build_fresh_run_admission(
        trace, perstep, pertask, identity, receipt, _study(), computed_at=NOW
    )
    register_fresh_run_admission(record, collection, registry_path)
    other, other_collection = build_fresh_run_admission(
        trace, perstep, pertask, identity, receipt, _study(seed_id="cap-1.0"), computed_at=NOW
    )
    with pytest.raises(VecFreshAdmissionError, match="declared study context"):
        register_fresh_run_admission(other, other_collection, registry_path)


def test_inc_and_ev_are_reviewed_and_weekday_traces_stay_refused() -> None:
    inc_sha = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
    ev_sha = "70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208"
    assert REVIEWED_TRACE_SCENARIOS[inc_sha] == "inc"
    assert PINNED_REVIEWED_TRACES[inc_sha] == "traces/trace_inc_fullrsu.npz"
    assert REVIEWED_TRACE_SCENARIOS[ev_sha] == "ev"
    assert PINNED_REVIEWED_TRACES[ev_sha] == "traces/trace_ev_fullrsu.npz"
    refused = (
        "5e36a7cb8b49afa9929574c9627216b7479a28ee0cbd83cc81ff852e647fd7ee",
        "848ba3cf278515f6a628bfb575892373454fae60ea6edf717da3b7683051ba9f",
    )
    for audited_but_unreviewed in refused:
        assert audited_but_unreviewed not in PINNED_REVIEWED_TRACES
        assert audited_but_unreviewed not in REVIEWED_TRACE_SCENARIOS


def test_register_is_idempotent(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt()
    record, collection = build_fresh_run_admission(
        trace, perstep, pertask, identity, receipt, _study(), computed_at=NOW
    )
    first = register_fresh_run_admission(record, collection, registry_path)
    second = register_fresh_run_admission(record, collection, registry_path)
    assert first.run_created is True
    assert second.run_created is False
    assert second.run_idempotent is True
    assert second.metrics_created is False


def test_record_rejects_mislabelled_registry_identity() -> None:
    trace, perstep, pertask, identity = _arrays()
    receipt = _receipt()
    record, _ = build_fresh_run_admission(
        trace, perstep, pertask, identity, receipt, _study(), computed_at=NOW
    )
    payload = record.model_dump(mode="json")
    payload["registry_run_id"] = "vec:fresh:0000000000000000"
    with pytest.raises(ValueError, match="derive from the receipt fingerprint"):
        type(record).model_validate(payload)
    payload = record.model_dump(mode="json")
    payload["limitations"] = ["shortened"]
    with pytest.raises(ValueError, match="standing fresh-admission statements"):
        type(record).model_validate(payload)
