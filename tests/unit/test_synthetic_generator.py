from __future__ import annotations

from pathlib import Path

from tests.helpers import fixed_clock
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.rules.engine import evaluate_rules
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.generator import generate_run_data, serialisable_rows
from traffictwin.synthetic.scenarios import preset_config


def test_synthetic_generation_is_deterministic() -> None:
    config = preset_config("baseline", random_seed=11)

    first = serialisable_rows(generate_run_data(config).rows)
    second = serialisable_rows(generate_run_data(config).rows)

    assert first == second


def test_different_synthetic_seeds_change_records() -> None:
    first = serialisable_rows(generate_run_data(preset_config("baseline", random_seed=1)).rows)
    second = serialisable_rows(generate_run_data(preset_config("baseline", random_seed=2)).rows)

    assert first != second


def test_generated_bundle_passes_existing_validator(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")

    result = validate_bundle(bundle)

    assert result.report.may_import
    assert result.manifest is not None
    assert result.manifest.environment.name == "synthetic"
    assert result.canonical.record_counts()["tasks"] > 0


def test_standalone_diagnostic_scenarios_trigger_expected_rules(tmp_path: Path) -> None:
    expectations = {
        "baseline": [],
        "under_offloading": ["R1"],
        "infrastructure_bottleneck": ["R2"],
    }
    for name, expected in expectations.items():
        bundle = write_synthetic_bundle(preset_config(name), tmp_path / name)
        result = validate_bundle(bundle)
        metrics = compute_metrics_for_bundle(result, clock=fixed_clock)

        pack = build_evidence_pack(result, metrics, clock=fixed_clock)
        report = evaluate_rules(pack, clock=fixed_clock)
        assert report.triggered_rule_ids == expected


def test_partial_evidence_is_accepted_with_limitations(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("partial_evidence"), tmp_path / "partial")

    result = validate_bundle(bundle)

    assert result.report.may_import
    assert "infrastructure" in result.report.unavailable_evidence_categories
    assert "trips" in result.report.unavailable_evidence_categories
