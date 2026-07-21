from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from tests.helpers import fixed_clock, metric_collection
from traffictwin.domain.energy import DEFAULT_TASK_ENERGY_CONTRACT, TaskEnergyContract
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.ingestion.hashes import sha256_file
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.metrics.comparison import (
    ComparisonRequest,
    ComparisonStatus,
    compare_metric_collections,
)
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricStatus, UnavailableReason
from traffictwin.metrics.windowed import WindowedMetricConfig, compute_windowed_metrics_for_bundle
from traffictwin.provenance.query import build_provenance_context, get_metric_contributions
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config
from traffictwin.validation.codes import ValidationCode

ENERGY_KEYS = (
    "task.energy.mean_per_observed_task_j",
    "task.energy.per_completed_j",
    "task.energy_delay_product.mean_j_ms",
)
CONTRACT_FINGERPRINT = "d71e4d10bb37aded7a6c8cdfc5b9cde4c59ef41b88c51facb54930ae9664ebaa"


def test_energy_contract_is_strict_versioned_and_requires_joules() -> None:
    assert DEFAULT_TASK_ENERGY_CONTRACT.fingerprint() == CONTRACT_FINGERPRINT
    with pytest.raises(ValueError):
        TaskEnergyContract(quantity="instantaneous_power")

    manifest = BundleManifest.model_validate(
        {
            "schema_version": "1.0",
            "bundle": {
                "bundle_id": "energy-contract",
                "created_at": "2026-07-20T00:00:00Z",
                "source": "synthetic_fixture",
            },
            "run": {
                "run_id": "energy-contract-run",
                "experiment_id": "energy-contract-experiment",
                "seed_id": "energy-contract-seed",
                "algorithm": "synthetic",
                "random_seed": 1,
            },
            "environment": {"name": "synthetic"},
            "files": {"tasks": {"path": "tasks.csv", "units": {"energy_j": "J"}}},
            "provenance": {"producer": "test"},
            "energy_contract": {},
        }
    )
    incompatible = manifest.model_dump(mode="json")
    incompatible["files"]["tasks"]["units"]["energy_j"] = "kWh"
    with pytest.raises(ValueError, match="requires tasks.units.energy_j to be J"):
        BundleManifest.model_validate(incompatible)


def test_synthetic_energy_family_has_exact_values_coverage_and_provenance(
    tmp_path: Path,
) -> None:
    bundle_path = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    bundle = validate_bundle(bundle_path)
    metrics = compute_metrics_for_bundle(bundle, clock=fixed_clock).by_key()

    assert bundle.manifest is not None
    assert bundle.manifest.energy_contract == DEFAULT_TASK_ENERGY_CONTRACT
    assert metrics["task.energy.mean_per_observed_task_j"].value == 0.9941935483870968
    assert metrics["task.energy.per_completed_j"].value == 0.9941935483870968
    assert metrics["task.energy_delay_product.mean_j_ms"].value == 215.2725101612903
    assert all(metrics[key].status is MetricStatus.AVAILABLE for key in ENERGY_KEYS)
    assert metrics["task.energy.mean_per_observed_task_j"].metadata["eligible_count"] == 31
    assert metrics["task.energy.mean_per_observed_task_j"].metadata["population_count"] == 33
    assert metrics["task.energy.per_completed_j"].metadata["coverage_fraction"] == 1.0
    assert (
        metrics["task.energy_delay_product.mean_j_ms"].metadata["energy_contract_fingerprint"]
        == CONTRACT_FINGERPRINT
    )

    context = build_provenance_context(bundle_path, clock=fixed_clock)
    ledger = get_metric_contributions(context, "task.energy_delay_product.mean_j_ms")
    assert ledger.complete_row_ledger
    assert ledger.candidate_row_count == 33
    assert ledger.included_row_count == 31


def test_energy_family_is_unavailable_without_explicit_contract() -> None:
    metrics = metric_collection("baseline_valid").by_key()

    for key in ENERGY_KEYS:
        assert metrics[key].status is MetricStatus.UNAVAILABLE
        assert metrics[key].reason_codes == [UnavailableReason.ENERGY_CONTRACT_UNAVAILABLE]
        assert metrics[key].missing_evidence == ["manifest.energy_contract"]


def test_windowed_energy_reuses_whole_run_contract_and_exact_calculator(tmp_path: Path) -> None:
    bundle = validate_bundle(
        write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    )
    whole_run = compute_metrics_for_bundle(bundle, clock=fixed_clock).by_key()
    series = compute_windowed_metrics_for_bundle(
        bundle,
        WindowedMetricConfig(width_s=600, analysis_start_s=0, analysis_end_s=600),
        clock=fixed_clock,
    )
    window_metrics = series.slices[0].metrics

    assert window_metrics is not None
    by_key = window_metrics.by_key()
    for key in ENERGY_KEYS:
        assert by_key[key].value == whole_run[key].value
        assert (
            by_key[key].metadata["energy_contract_fingerprint"]
            == whole_run[key].metadata["energy_contract_fingerprint"]
        )


def test_energy_comparison_requires_matching_contract_fingerprints(tmp_path: Path) -> None:
    baseline_bundle = validate_bundle(
        write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    )
    variation_bundle = validate_bundle(
        write_synthetic_bundle(preset_config("stressed_demand"), tmp_path / "variation")
    )
    baseline = compute_metrics_for_bundle(baseline_bundle, clock=fixed_clock)
    variation = compute_metrics_for_bundle(variation_bundle, clock=fixed_clock)
    request = ComparisonRequest(
        baseline_run_id=baseline.run_id,
        variation_run_id=variation.run_id,
        requested_metric_keys=["task.energy.per_completed_j"],
    )

    compatible = compare_metric_collections(baseline, variation, request, clock=fixed_clock)
    assert compatible.comparable_metrics[0].status is ComparisonStatus.AVAILABLE
    assert (
        compatible.comparable_metrics[0].provenance["energy_contract_fingerprint"]
        == CONTRACT_FINGERPRINT
    )

    changed_results = []
    for metric in variation.results:
        if metric.metric_key == "task.energy.per_completed_j":
            metadata = dict(metric.metadata)
            metadata["energy_contract_fingerprint"] = "incompatible"
            metric = metric.model_copy(update={"metadata": metadata})
        changed_results.append(metric)
    incompatible_variation = variation.model_copy(update={"results": changed_results})
    incompatible = compare_metric_collections(
        baseline,
        incompatible_variation,
        request,
        clock=fixed_clock,
    )

    result = incompatible.unavailable_comparisons[0]
    assert result.status is ComparisonStatus.UNAVAILABLE
    assert UnavailableReason.COMPARISON_PAIR_INCOMPATIBLE in result.reason_codes


def test_negative_energy_rejects_bundle_before_metrics(tmp_path: Path) -> None:
    bundle_path = write_synthetic_bundle(preset_config("baseline"), tmp_path / "negative")
    tasks_path = bundle_path / "tasks.csv"
    with tasks_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0])
    rows[0]["energy_j"] = "-1"
    with tasks_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    manifest_path = bundle_path / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["tasks"]["checksum_sha256"] = sha256_file(tasks_path)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    result = validate_bundle(bundle_path)

    assert not result.report.may_import
    assert ValidationCode.TASK_ENERGY_NEGATIVE in {
        finding.code for finding in result.report.findings
    }
