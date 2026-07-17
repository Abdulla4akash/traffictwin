from __future__ import annotations

from tests.helpers import metric_collection

from traffictwin.config.capabilities import CapabilitySupport
from traffictwin.ui.formatting import capability_label, format_metric_value, format_ratio


def test_capability_labels_preserve_unknown() -> None:
    assert capability_label(CapabilitySupport.TRUE) == "Supported"
    assert capability_label(CapabilitySupport.FALSE) == "Unsupported"
    assert capability_label(CapabilitySupport.UNKNOWN) == "Unknown"


def test_metric_formatting_distinguishes_unavailable_from_zero() -> None:
    metrics = metric_collection("partial_valid").by_key()

    assert format_metric_value(metrics["infra.queue_length.mean"]) == "Unavailable"
    assert format_ratio(0.0) == "0.0%"
