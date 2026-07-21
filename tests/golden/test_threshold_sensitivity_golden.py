from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.diagnostics.threshold_sweep import (
    ThresholdSweepRequest,
    evaluate_threshold_sweep,
    threshold_sensitivity_contract,
)
from traffictwin.domain.energy import DEFAULT_TASK_ENERGY_CONTRACT
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection, MetricStatus, MetricValue

EXPECTED = Path("tests/golden/expected/threshold_sensitivity_r8.json")


def _metric(key: str, value: float, unit: str, metadata: dict[str, object]) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=unit,
        scope="run",
        implementation_version="test",
        run_id="run-threshold-golden",
        experiment_id="exp-threshold-golden",
        seed_id="seed-threshold-golden",
        algorithm="test",
        random_seed=7,
        synthetic=True,
        computed_at=fixed_clock(),
        metadata=metadata,
    )


def _pack() -> EvidencePack:
    contract = DEFAULT_TASK_ENERGY_CONTRACT
    energy = _metric(
        "task.energy.per_completed_j",
        1.0,
        "J/task",
        {
            "energy_family_version": "1.0",
            "energy_contract_fingerprint": contract.fingerprint(),
            "energy_contract_version": "1.0",
            "energy_quantity": "per_task_total_energy",
            "energy_unit": "J",
            "eligibility_policy": "completed_and_finite_non_negative_energy",
            "coverage_fraction": 1.0,
            "eligible_count": 20,
            "population_count": 20,
        },
    )
    completed = _metric("task.completed.count", 20, "count", {})
    return EvidencePack(
        pack_id="pack-threshold-golden",
        generated_at=fixed_clock(),
        synthetic=True,
        run_context={"run_id": "run-threshold-golden"},
        source_bundle_fingerprint="source-threshold-golden",
        validation_summary={"may_import": True, "counts_by_severity": {}},
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.AVAILABLE,
            vehicles=EvidenceStatus.UNAVAILABLE,
            infrastructure=EvidenceStatus.UNAVAILABLE,
            diagnosis=EvidenceStatus.AVAILABLE,
        ),
        metric_engine_config=MetricEngineConfig(),
        metric_collection=MetricCollection(
            run_id="run-threshold-golden",
            metric_version="test",
            results=[energy, completed],
            unavailable_count=0,
            partial_count=0,
            generated_at=fixed_clock(),
        ),
    )


def _projection() -> dict[str, object]:
    report = evaluate_threshold_sweep(
        _pack(),
        ThresholdSweepRequest(
            rule_id="R8",
            minimum_threshold=0.0,
            maximum_threshold=2.0,
            point_count=4,
        ),
        clock=fixed_clock,
    )
    nearest = report.nearest_flip
    return {
        "contract": threshold_sensitivity_contract().model_dump(mode="json"),
        "report": {
            "schema_version": report.schema_version,
            "capability": report.capability,
            "analysis_version": report.analysis_version,
            "analysis_id": report.analysis_id,
            "status": report.status.value,
            "reason_code": report.reason_code.value,
            "request": report.request.model_dump(mode="json"),
            "rule_id": report.rule_id,
            "rule_version": report.rule_version,
            "ruleset_version": report.ruleset_version,
            "parameter_path": report.parameter_path,
            "threshold_unit": report.threshold_unit,
            "source_threshold": report.source_threshold,
            "source_status": report.source_status.value if report.source_status else None,
            "source_rule_config": report.source_rule_config,
            "fixed_rule_config": report.fixed_rule_config,
            "requested_point_count": report.requested_point_count,
            "evaluated_point_count": report.evaluated_point_count,
            "source_threshold_injected": report.source_threshold_injected,
            "points": [point.model_dump(mode="json") for point in report.points],
            "stability": (
                report.stability.model_dump(mode="json") if report.stability is not None else None
            ),
            "flip_boundaries": [
                boundary.model_dump(mode="json") for boundary in report.flip_boundaries
            ],
            "nearest_flip": (
                {
                    "status": nearest.status.value,
                    "reason_code": nearest.reason_code.value,
                    "candidates": [
                        candidate.model_dump(mode="json") for candidate in nearest.candidates
                    ],
                    "constraints": [
                        constraint.model_dump(mode="json") for constraint in nearest.constraints
                    ],
                    "fingerprint": nearest.fingerprint(),
                }
                if nearest is not None
                else None
            ),
            "evidence_pack_fingerprint": report.evidence_pack_fingerprint,
            "source_result_fingerprint": report.source_result_fingerprint,
            "report_fingerprint": report.fingerprint(),
        },
    }


def test_threshold_sensitivity_contract_and_r8_grid_match_golden() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert _projection() == expected
