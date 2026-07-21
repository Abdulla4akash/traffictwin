from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import pytest

from tests.helpers import fixed_clock
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricStatus
from traffictwin.rules.config import R8Config, RuleSetConfig
from traffictwin.rules.models import RuleResult, RuleStatus
from traffictwin.rules.r8_energy_anomaly import (
    COMPLETED_COUNT_KEY,
    ENERGY_PER_COMPLETED_KEY,
    R8EnergyAnomalyRule,
    r8_energy_diagnosis_contract,
)
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


class MetricChange(TypedDict, total=False):
    status: MetricStatus
    unit: str
    value: object
    metadata_update: dict[str, object]


R8_ADMISSION_MUTATIONS: list[tuple[str, MetricChange, str]] = [
    (
        ENERGY_PER_COMPLETED_KEY,
        {"status": MetricStatus.PARTIAL},
        "metric status is partial",
    ),
    (ENERGY_PER_COMPLETED_KEY, {"unit": "kWh/task"}, "unit 'kWh/task' is not 'J/task'"),
    (
        ENERGY_PER_COMPLETED_KEY,
        {"metadata_update": {"energy_contract_fingerprint": "incompatible"}},
        "metadata 'energy_contract_fingerprint' is absent or incompatible",
    ),
    (
        ENERGY_PER_COMPLETED_KEY,
        {"metadata_update": {"coverage_fraction": 0.5}},
        "completed-task energy coverage is not complete",
    ),
    (
        ENERGY_PER_COMPLETED_KEY,
        {"metadata_update": {"eligible_count": 30}},
        "eligible and population counts differ",
    ),
    (
        COMPLETED_COUNT_KEY,
        {"value": 30},
        "completed-task denominator conflicts",
    ),
]


def _pack(tmp_path: Path, preset: str) -> EvidencePack:
    bundle = validate_bundle(write_synthetic_bundle(preset_config(preset), tmp_path / preset))
    metrics = compute_metrics_for_bundle(bundle, clock=fixed_clock)
    return build_evidence_pack(bundle, metrics, clock=fixed_clock)


def _evaluate(pack: EvidencePack, r8: R8Config | None = None) -> RuleResult:
    config = RuleSetConfig(r8=r8 or R8Config())
    return R8EnergyAnomalyRule().evaluate(pack, config, fixed_clock())


def _replace_metric(
    pack: EvidencePack,
    metric_key: str,
    *,
    status: MetricStatus | None = None,
    unit: str | None = None,
    value: object | None = None,
    metadata_update: dict[str, object] | None = None,
) -> EvidencePack:
    changed = []
    for metric in pack.metric_collection.results:
        if metric.metric_key != metric_key:
            changed.append(metric)
            continue
        update: dict[str, object] = {}
        if status is not None:
            update["status"] = status
        if unit is not None:
            update["unit"] = unit
        if value is not None:
            update["value"] = value
        if metadata_update is not None:
            update["metadata"] = {**metric.metadata, **metadata_update}
        changed.append(metric.model_copy(update=update, deep=True))
    collection = pack.metric_collection.model_copy(update={"results": changed}, deep=True)
    return pack.model_copy(update={"metric_collection": collection}, deep=True)


def test_r8_contract_pins_exact_boundary_and_provisional_defaults() -> None:
    contract = r8_energy_diagnosis_contract()

    assert contract.capability == "DIA-03"
    assert contract.rule_id == "R8"
    assert contract.ruleset_version == "1.3"
    assert contract.metric_key == ENERGY_PER_COMPLETED_KEY
    assert contract.denominator_metric_key == COMPLETED_COUNT_KEY
    assert contract.default_r8_config.minimum_energy_per_completed_task_j == 1.5
    assert contract.default_r8_config.minimum_completed_tasks == 10
    assert len(contract.required_energy_contract_fingerprint) == 64


def test_r8_triggers_for_supported_synthetic_energy_candidate(tmp_path: Path) -> None:
    result = _evaluate(_pack(tmp_path, "infrastructure_bottleneck"))

    assert result.status is RuleStatus.TRIGGERED
    assert result.confidence.value == "moderate"
    assert result.evidence_keys == [COMPLETED_COUNT_KEY, ENERGY_PER_COMPLETED_KEY]
    assert result.metadata["r8_observed_energy_per_completed_task_j"] == pytest.approx(1.62)
    assert result.metadata["r8_completed_task_count"] == 10
    assert "high mean energy cost" in (result.hypothesis or "")


def test_r8_boundary_is_inclusive_and_lower_energy_does_not_trigger(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "baseline")
    observed = pack.metric_collection.by_key()[ENERGY_PER_COMPLETED_KEY].value
    assert isinstance(observed, float)

    boundary = _evaluate(
        pack,
        R8Config(
            minimum_energy_per_completed_task_j=observed,
            minimum_completed_tasks=31,
        ),
    )
    below = _evaluate(pack)

    assert boundary.status is RuleStatus.TRIGGERED
    assert below.status is RuleStatus.NOT_TRIGGERED
    assert below.hypothesis is None


def test_r8_high_energy_with_thin_completed_support_is_conflicting(tmp_path: Path) -> None:
    result = _evaluate(_pack(tmp_path, "s5_stadium_event_siting"))

    assert result.status is RuleStatus.CONFLICTING_EVIDENCE
    assert result.confidence.value == "low"
    assert result.metadata["r8_completed_task_count"] == 1
    assert "too few completed tasks" in (result.hypothesis or "")


def test_r8_is_insufficient_without_explicit_energy_contract() -> None:
    validation = validate_bundle(Path("tests/fixtures/bundles/baseline_valid"))
    metrics = compute_metrics_for_bundle(validation, clock=fixed_clock)
    pack = build_evidence_pack(validation, metrics, clock=fixed_clock)

    result = _evaluate(pack)

    assert result.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert any("metric status is unavailable" in item for item in result.missing_evidence)
    failure_count = result.metadata["r8_admission_failure_count"]
    assert isinstance(failure_count, int)
    assert failure_count >= 1


@pytest.mark.parametrize(
    ("metric_key", "change", "expected"),
    R8_ADMISSION_MUTATIONS,
)
def test_r8_rejects_partial_mixed_or_inconsistent_evidence(
    tmp_path: Path,
    metric_key: str,
    change: MetricChange,
    expected: str,
) -> None:
    pack = _replace_metric(_pack(tmp_path, "baseline"), metric_key, **change)

    result = _evaluate(pack)

    assert result.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert any(expected in item for item in result.missing_evidence)
    assert result.confidence.value == "unavailable"


def test_r8_configuration_rejects_non_finite_or_invalid_support() -> None:
    with pytest.raises(ValueError):
        R8Config(minimum_energy_per_completed_task_j=float("nan"))
    with pytest.raises(ValueError):
        R8Config(minimum_completed_tasks=0)
