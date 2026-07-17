from __future__ import annotations

from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.definitions import MetricDomain


def test_metric_catalogue_has_unique_stable_keys() -> None:
    catalogue = metric_catalogue()

    assert list(catalogue) == sorted(catalogue)
    assert len(catalogue) == len(set(catalogue))
    assert "task.completion.rate" in catalogue
    assert "comparison.absolute_delta" in catalogue
    assert catalogue["comparison.relative_delta"].domain is MetricDomain.COMPARISON


def test_metric_definitions_include_version_and_required_evidence() -> None:
    catalogue = metric_catalogue()

    for key, definition in catalogue.items():
        assert definition.key == key
        assert definition.implementation_version == "1.0"
        if not key.startswith("comparison."):
            assert definition.required_tables
