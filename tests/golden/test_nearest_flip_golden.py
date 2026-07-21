from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.diagnostics.sensitivity import analyse_nearest_flip, nearest_flip_contract
from traffictwin.domain.energy import DEFAULT_TASK_ENERGY_CONTRACT
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection, MetricStatus, MetricValue

EXPECTED = Path("tests/golden/expected/nearest_flip_r8.json")


def _metric(key: str, value: float, unit: str, metadata: dict[str, object]) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=unit,
        scope="run",
        implementation_version="test",
        run_id="run-nearest-golden",
        experiment_id="exp-nearest-golden",
        seed_id="seed-nearest-golden",
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
        pack_id="pack-nearest-golden",
        generated_at=fixed_clock(),
        synthetic=True,
        run_context={"run_id": "run-nearest-golden"},
        source_bundle_fingerprint="source-nearest-golden",
        validation_summary={"may_import": True, "counts_by_severity": {}},
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.AVAILABLE,
            vehicles=EvidenceStatus.UNAVAILABLE,
            infrastructure=EvidenceStatus.UNAVAILABLE,
            diagnosis=EvidenceStatus.AVAILABLE,
        ),
        metric_engine_config=MetricEngineConfig(),
        metric_collection=MetricCollection(
            run_id="run-nearest-golden",
            metric_version="test",
            results=[energy, completed],
            unavailable_count=0,
            partial_count=0,
            generated_at=fixed_clock(),
        ),
    )


def test_nearest_flip_contract_and_r8_result_match_golden() -> None:
    pack = _pack()
    analysis = analyse_nearest_flip(pack, "R8", clock=fixed_clock)
    actual = {
        "contract": nearest_flip_contract().model_dump(mode="json"),
        "analysis": analysis.model_dump(mode="json"),
        "analysis_fingerprint": analysis.fingerprint(),
    }

    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

    assert actual == expected
