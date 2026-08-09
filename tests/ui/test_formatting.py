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


def test_format_scalar_unified_contract() -> None:
    """Single authoritative scalar formatter must handle all consequence types."""

    from traffictwin.ui.formatting import format_scalar

    # None
    assert format_scalar(None) == "Unavailable"
    # bool before int
    assert format_scalar(True) == "True"
    assert format_scalar(False) == "False"
    # int
    assert format_scalar(42) == "42"
    assert format_scalar(-7) == "-7"
    # finite float lossless
    assert format_scalar(2024123.0) == "2024123.0"
    assert float(format_scalar(2024123.0)) == 2024123.0
    assert format_scalar(0.25) == "0.25"
    assert format_scalar(0.123456789012345) == "0.123456789012345"
    assert float(format_scalar(0.123456789012345)) == 0.123456789012345
    # NaN / Inf
    assert format_scalar(float("nan")) == "NaN"
    assert format_scalar(float("inf")) == "Infinity"
    assert format_scalar(float("-inf")) == "-Infinity"
    # other
    assert format_scalar("hello") == "hello"
