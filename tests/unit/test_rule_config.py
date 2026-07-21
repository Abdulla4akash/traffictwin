from __future__ import annotations

import pytest
from pydantic import ValidationError

from traffictwin.rules.config import RuleSetConfig


def test_default_rule_config_is_versioned_and_enabled() -> None:
    config = RuleSetConfig()

    assert config.schema_version == "1.0"
    assert config.ruleset_version == "1.3"
    assert config.enabled_rule_ids() == [
        "R0",
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
        "R7",
        "R8",
    ]


def test_threshold_validation_rejects_invalid_ratios() -> None:
    with pytest.raises(ValidationError):
        RuleSetConfig.model_validate({"r1": {"offload_rate_max": 1.5}})


def test_disabled_rule_is_removed_from_enabled_list() -> None:
    config = RuleSetConfig.model_validate({"r2": {"enabled": False}})

    assert config.enabled_rule_ids() == ["R0", "R1", "R3", "R4", "R5", "R6", "R7", "R8"]
