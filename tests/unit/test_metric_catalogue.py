from __future__ import annotations

from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.definitions import MetricDomain


def test_metric_catalogue_has_unique_stable_keys() -> None:
    catalogue = metric_catalogue()

    assert list(catalogue) == sorted(catalogue)
    assert len(catalogue) == len(set(catalogue))
    assert "task.completion.rate" in catalogue
    assert "task.latency.p99_ms" in catalogue
    assert "comparison.absolute_delta" in catalogue
    assert catalogue["comparison.relative_delta"].domain is MetricDomain.COMPARISON


def test_metric_definitions_include_version_and_required_evidence() -> None:
    catalogue = metric_catalogue()

    for key, definition in catalogue.items():
        assert definition.key == key
        assert definition.implementation_version == "1.0"
        if not key.startswith("comparison."):
            assert definition.required_tables


def test_metric_definitions_declare_window_applicability_and_anchor() -> None:
    catalogue = metric_catalogue()

    for key, definition in catalogue.items():
        if key.startswith("comparison."):
            assert not definition.time_window_applicable
            assert definition.time_anchor is None
        else:
            assert definition.time_window_applicable
            assert definition.time_anchor is not None

    p99 = catalogue["task.latency.p99_ms"]
    assert p99.time_anchor == "tasks.arrival_time_s"
    assert p99.limitations
