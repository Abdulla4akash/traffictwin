from __future__ import annotations

from tests.helpers import FIXED_TIME, metric_collection
from traffictwin.canonical.records import InfrastructureRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.engine import compute_metrics
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricStatus, RunMetricContext


def test_infrastructure_metrics_from_variation_fixture() -> None:
    metrics = metric_collection("variation_valid").by_key()

    assert metrics["infra.observed_rsu.count"].value == 2
    assert metrics["infra.queue_length.mean"].value == 4.75
    assert metrics["infra.queue_length.max"].value == 8
    assert metrics["infra.utilisation.mean"].value == 0.8125
    assert metrics["infra.utilisation.p95"].value == 0.9394999999999999
    assert metrics["infra.saturation.episode_count"].value == 1
    assert metrics["infra.saturation.duration_s"].value == 0.0


def test_saturation_duration_uses_known_timestamp_gaps() -> None:
    context = RunMetricContext(
        run_id="run",
        experiment_id="exp",
        seed_id="seed",
        algorithm="algo",
        random_seed=1,
        synthetic=True,
    )
    tables = CanonicalTables(
        infrastructure=[
            InfrastructureRecord(
                timestamp_s=0,
                rsu_id="rsu-1",
                utilisation_fraction=0.91,
                source_file="infra.csv",
                source_row=1,
            ),
            InfrastructureRecord(
                timestamp_s=10,
                rsu_id="rsu-1",
                utilisation_fraction=0.92,
                source_file="infra.csv",
                source_row=2,
            ),
            InfrastructureRecord(
                timestamp_s=40,
                rsu_id="rsu-1",
                utilisation_fraction=0.93,
                source_file="infra.csv",
                source_row=3,
            ),
        ]
    )

    metrics = compute_metrics(
        tables,
        context,
        EvidenceAvailability(infrastructure=EvidenceStatus.AVAILABLE),
        MetricEngineConfig(saturation_threshold=0.90, saturation_max_gap_s=15),
        clock=lambda: FIXED_TIME,
    ).by_key()

    assert metrics["infra.saturation.episode_count"].value == 2
    assert metrics["infra.saturation.duration_s"].value == 10.0


def test_capacity_normalised_load_balance_unavailable_without_capacity() -> None:
    metric = metric_collection("baseline_valid").by_key()[
        "infra.load_balance.jain_capacity_normalised"
    ]

    assert metric.status is MetricStatus.UNAVAILABLE
    assert "CAPACITY_UNAVAILABLE" in [reason.value for reason in metric.reason_codes]
