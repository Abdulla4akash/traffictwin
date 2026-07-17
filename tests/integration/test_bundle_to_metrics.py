from __future__ import annotations

import zipfile
from pathlib import Path

from tests.helpers import FIXTURES, fixed_clock

from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import import_bundle, validate_bundle
from traffictwin.metrics.aggregation import aggregate_experiment
from traffictwin.metrics.comparison import compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricCollection
from traffictwin.storage.registry import Registry


def test_directory_bundle_to_metrics_and_evidence_pack() -> None:
    result = validate_bundle(FIXTURES / "baseline_valid")
    collection = compute_metrics_for_bundle(result, clock=fixed_clock)
    pack = build_evidence_pack(result, collection, clock=fixed_clock)

    assert collection.by_key()["task.completion.rate"].value == 1.0
    assert pack.metric_collection.run_id == "run-baseline-001"
    assert pack.evidence_availability.tasks.value == "available"


def test_zip_bundle_produces_equivalent_metric_values(tmp_path: Path) -> None:
    source = FIXTURES / "baseline_valid"
    archive = tmp_path / "baseline_valid.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                zip_file.write(path, path.relative_to(source).as_posix())

    directory_metrics = compute_metrics_for_bundle(validate_bundle(source), clock=fixed_clock)
    zip_metrics = compute_metrics_for_bundle(validate_bundle(archive), clock=fixed_clock)

    assert directory_metrics.model_dump(
        mode="json", exclude={"generated_at"}
    ) == zip_metrics.model_dump(
        mode="json",
        exclude={"generated_at"},
    )


def test_two_bundles_compare_end_to_end() -> None:
    baseline = validate_bundle(FIXTURES / "baseline_valid")
    variation = validate_bundle(FIXTURES / "variation_valid")
    report = compare_metric_collections(
        compute_metrics_for_bundle(baseline, clock=fixed_clock),
        compute_metrics_for_bundle(variation, clock=fixed_clock),
        baseline_seed=baseline.seed,
        variation_seed=variation.seed,
        clock=fixed_clock,
    )

    by_key = {metric.metric_key: metric for metric in report.comparable_metrics}
    assert by_key["task.completion.rate"].absolute_delta == -0.25
    assert by_key["trip.duration.mean_s"].absolute_delta == 330.0


def test_registry_metric_storage_and_experiment_summary(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    baseline = validate_bundle(FIXTURES / "baseline_valid")
    variation = validate_bundle(FIXTURES / "variation_valid")
    import_bundle(FIXTURES / "baseline_valid", registry_path)
    import_bundle(FIXTURES / "variation_valid", registry_path)
    registry = Registry(registry_path)

    for result in (baseline, variation):
        collection = compute_metrics_for_bundle(result, clock=fixed_clock)
        pack = build_evidence_pack(result, collection, clock=fixed_clock)
        registry.store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
        registry.store_evidence_pack(
            pack_id=pack.pack_id,
            run_id=collection.run_id,
            source_fingerprint=collection.input_fingerprint,
            payload_json=pack.to_json(),
        )

    payloads = registry.list_metric_collection_json()
    collections = [MetricCollection.model_validate_json(payload) for payload in payloads]
    report = aggregate_experiment(collections, clock=fixed_clock)

    assert registry.inspect().metric_collection_count == 2
    assert registry.inspect().evidence_pack_count == 2
    assert report.experiment_id == "exp-gridlock-001"
    assert report.condition_count == 2
