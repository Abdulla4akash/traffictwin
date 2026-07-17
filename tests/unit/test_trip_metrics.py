from __future__ import annotations

from tests.helpers import FIXED_TIME, metric_collection
from traffictwin.canonical.records import TripRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.engine import compute_metrics
from traffictwin.metrics.results import RunMetricContext


def test_trip_metrics_from_variation_fixture() -> None:
    metrics = metric_collection("variation_valid").by_key()

    assert metrics["trip.records.count"].value == 2
    assert metrics["trip.completed.count"].value == 2
    assert metrics["trip.incomplete.count"].value == 0
    assert metrics["trip.completion.rate"].value == 1.0
    assert metrics["trip.duration.mean_s"].value == 960.0
    assert metrics["trip.duration.p50_s"].value == 960.0
    assert metrics["trip.duration.p95_s"].value == 1014.0
    assert metrics["trip.duration.min_s"].value == 900.0
    assert metrics["trip.duration.max_s"].value == 1020.0


def test_trip_duration_can_be_derived_when_explicit_duration_is_absent() -> None:
    context = RunMetricContext(
        run_id="run",
        experiment_id="exp",
        seed_id="seed",
        algorithm="algo",
        random_seed=1,
        synthetic=True,
    )
    tables = CanonicalTables(
        trips=[
            TripRecord(
                trip_id="trip-1",
                departure_time_s=10,
                arrival_time_s=70,
                source_file="trips.csv",
                source_row=1,
            )
        ]
    )

    metrics = compute_metrics(
        tables,
        context,
        EvidenceAvailability(trips=EvidenceStatus.AVAILABLE),
        clock=lambda: FIXED_TIME,
    ).by_key()

    assert metrics["trip.completed.count"].value == 1
    assert metrics["trip.duration.mean_s"].value == 60.0
