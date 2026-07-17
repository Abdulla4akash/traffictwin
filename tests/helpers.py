from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.ingestion.bundle import BundleValidationResult, validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricCollection

FIXED_TIME = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
FIXTURES = Path("tests/fixtures/bundles")


def fixed_clock() -> datetime:
    return FIXED_TIME


def bundle_result(name: str) -> BundleValidationResult:
    return validate_bundle(FIXTURES / name)


def metric_collection(name: str) -> MetricCollection:
    return compute_metrics_for_bundle(bundle_result(name), clock=fixed_clock)


def metric_projection(collection: MetricCollection, keys: list[str]) -> dict[str, object]:
    by_key = collection.by_key()
    return {
        "run_id": collection.run_id,
        "metric_version": collection.metric_version,
        "metrics": {
            key: {
                "status": by_key[key].status.value,
                "value": by_key[key].value,
                "unit": by_key[key].unit,
                "reason_codes": [reason.value for reason in by_key[key].reason_codes],
            }
            for key in keys
        },
    }


def assert_json_has_no_nan(value: object) -> None:
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        for item in value.values():
            assert_json_has_no_nan(item)
    elif isinstance(value, list):
        for item in value:
            assert_json_has_no_nan(item)
