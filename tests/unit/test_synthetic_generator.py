from __future__ import annotations

from pathlib import Path

from tests.helpers import fixed_clock
from traffictwin.domain.energy import DEFAULT_TASK_ENERGY_CONTRACT
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.rules.engine import evaluate_rules
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import IncidentSpec
from traffictwin.synthetic.generator import generate_run_data, serialisable_rows
from traffictwin.synthetic.scenarios import incident_variant_config, preset_config


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
    assert result.manifest.energy_contract == DEFAULT_TASK_ENERGY_CONTRACT
    assert result.canonical.record_counts()["tasks"] > 0


def test_standalone_diagnostic_scenarios_trigger_expected_rules(tmp_path: Path) -> None:
    expectations = {
        "baseline": [],
        "under_offloading": ["R1", "R7"],
        "infrastructure_bottleneck": ["R2", "R7", "R8"],
        "mixed_fault": ["R1", "R2", "R4", "R7"],
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


def test_s5_and_s6_presets_preserve_synthetic_event_context(tmp_path: Path) -> None:
    expectations = {
        "s5_stadium_event_siting": ("S5", "synthetic_stadium_egress", None),
        "s6_road_clearing_corridor": ("S6", "synthetic_road_clearing", 2),
    }
    for name, (preset_id, event_type, lanes_closed) in expectations.items():
        config = preset_config(name)
        bundle = write_synthetic_bundle(config, tmp_path / name)
        result = validate_bundle(bundle)

        assert result.report.may_import
        assert result.seed is not None
        assert result.seed.preset_id == preset_id
        assert result.seed.traffic.event_type == event_type
        assert result.seed.traffic.lanes_closed == lanes_closed
        assert len(result.canonical.incidents) == 1
        assert "Synthetic" in result.seed.description


def test_authored_incident_fields_round_trip_and_seed_a_variant(tmp_path: Path) -> None:
    config = preset_config("baseline").model_copy(
        update={
            "scenario_id": "authored-event",
            "incident_schedule": [
                IncidentSpec(
                    timestamp_s=45.0,
                    incident_type="synthetic_collision",
                    location="corridor-a",
                    severity="high",
                    duration_s=180.0,
                    lanes_closed=2,
                    demand_multiplier=1.75,
                    vehicles_involved=["vehicle-001", "vehicle-002"],
                )
            ],
        }
    )
    validation = validate_bundle(write_synthetic_bundle(config, tmp_path / "authored-event"))

    assert validation.report.may_import
    incident = validation.canonical.incidents[0]
    assert incident.duration_s == 180.0
    assert incident.lanes_closed == 2
    assert incident.demand_multiplier == 1.75
    assert incident.vehicles_involved == ["vehicle-001", "vehicle-002"]
    assert validation.seed is not None
    assert validation.seed.traffic.event_demand_multiplier == 1.75
    assert validation.seed.traffic.vehicles_involved == ["vehicle-001", "vehicle-002"]

    variant = incident_variant_config(config)
    assert variant.baseline_seed_id == "seed-authored-event"
    assert variant.incident_schedule == config.incident_schedule
    assert "incident_seeded_variant" in variant.synthetic_faults
