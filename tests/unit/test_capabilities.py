from __future__ import annotations

import pytest

from traffictwin.config.capabilities import (
    RANDY_ENVIRONMENT_CAPABILITIES,
    CapabilitySet,
    CapabilitySupport,
    default_export_import_manifest,
)


def test_capability_coerces_true_false_unknown() -> None:
    capabilities = CapabilitySet(
        direct_launch=True,
        asynchronous_launch=False,
        task_arrival_multiplier="unknown",
    )

    assert capabilities.direct_launch is CapabilitySupport.TRUE
    assert capabilities.asynchronous_launch is CapabilitySupport.FALSE
    assert capabilities.task_arrival_multiplier is CapabilitySupport.UNKNOWN


def test_invalid_capability_value_rejected() -> None:
    with pytest.raises(ValueError, match="capability must be true, false, or unknown"):
        CapabilitySet(direct_launch="maybe")


def test_default_manifest_is_export_import_only() -> None:
    manifest = default_export_import_manifest()

    assert manifest.adapter == "generic_csv"
    assert manifest.supports.seed_export is CapabilitySupport.TRUE
    assert manifest.supports.run_bundle_import is CapabilitySupport.TRUE
    assert manifest.supports.direct_launch is CapabilitySupport.FALSE
    assert manifest.supports.asynchronous_launch is CapabilitySupport.FALSE


def test_no_unsupported_randy_capability_defaults_to_true() -> None:
    manifest = default_export_import_manifest()

    for field_name in RANDY_ENVIRONMENT_CAPABILITIES:
        assert getattr(manifest.supports, field_name) is not CapabilitySupport.TRUE


def test_manifest_plain_dict_uses_bools_and_unknown() -> None:
    supports = default_export_import_manifest().supports.as_manifest_dict()

    assert supports["seed_export"] is True
    assert supports["direct_launch"] is False
    assert supports["rsu_capacity"] == "unknown"
