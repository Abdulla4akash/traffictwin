from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.domain.enums import Decision
from traffictwin.domain.scenario import ScenarioSeed, SeedDocument


def valid_seed_payload() -> dict[str, Any]:
    return {
        "id": "s1-gridlock-x2",
        "name": "Arena egress gridlock at double demand",
        "base": "S1-arena-egress-gridlock",
        "demand": {"multiplier": 2.0},
        "workload": {
            "birth_rate_multiplier": 2.0,
            "class_mix": {"T1": 0.3, "T2": 0.3, "T3": 0.4},
            "ordering": "mixed",
        },
        "fleet": {"count": None, "tier_mix": "mixed"},
        "infrastructure": {
            "rsu_count": 2,
            "rsu_capacity_mode": "standard",
            "failed_rsus": [],
        },
        "allowed_decisions": ["local", "v2i", "v2v"],
        "policy": {"algorithm": "MAPPO", "checkpoint": None},
        "evaluation": {"random_seed": 7},
        "compare_against": None,
        "provenance": {
            "created_by": "Abdulla Al Mamun Akash",
            "source": "TrafficTwin tests",
        },
    }


def test_valid_scenario_seed_model() -> None:
    seed = ScenarioSeed.model_validate(valid_seed_payload())

    assert seed.seed_id == "s1-gridlock-x2"
    assert seed.schema_version == "1.0"
    assert seed.allowed_decisions == [Decision.LOCAL, Decision.V2I, Decision.V2V]
    assert seed.workload.class_mix


def test_invalid_class_mix_rejected() -> None:
    payload = valid_seed_payload()
    workload = dict(payload["workload"])
    workload["class_mix"] = {"T1": 0.5, "T2": 0.3, "T3": 0.3}
    payload["workload"] = workload

    with pytest.raises(ValidationError, match="class_mix shares must sum to 1.0"):
        ScenarioSeed.model_validate(payload)


def test_duplicate_decisions_rejected() -> None:
    payload = valid_seed_payload()
    payload["allowed_decisions"] = ["local", "local"]

    with pytest.raises(ValidationError, match="allowed_decisions must not contain duplicates"):
        ScenarioSeed.model_validate(payload)


def test_unknown_fields_rejected() -> None:
    payload = valid_seed_payload()
    payload["undocumented_randy_field"] = "must not pass"

    with pytest.raises(ValidationError):
        ScenarioSeed.model_validate(payload)


def test_unsupported_seed_schema_version_rejected() -> None:
    payload = valid_seed_payload()
    payload["schema_version"] = "1.0"

    with pytest.raises(ValidationError, match="Input should be '1.0'"):
        SeedDocument.model_validate(
            {"schema_version": "1.0", "seed": {**payload, "schema_version": "2.0"}}
        )
