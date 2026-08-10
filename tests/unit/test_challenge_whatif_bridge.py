"""Unit tests for the Challenge → What-If bridge (V2 challenge-bridge slice).

Required contract:

1. deterministic mapping
2. unknown field remains unsupported
3. abstract capacity mode never becomes numeric capacity
4. unsupported ordering not silently lost
5. unsupported fleet-tier semantics not silently converted
6. mapping fingerprint changes when mapped content changes
7. fingerprint changes when unsupported content changes
8. no path/secret leakage
9. all seven challenge IDs handled
10. original challenge object is not mutated
"""

from __future__ import annotations

import copy
import json

from traffictwin.domain.enums import FleetTierMix, RsuCapacityMode, WorkloadOrdering
from traffictwin.synthetic.whatif_pair import WhatIfVariationOverrides
from traffictwin.ui.challenge_whatif_bridge import (
    ChallengeWhatIfMappingStatus,
    build_challenge_whatif_draft,
    build_draft_for_challenge_id,
    draft_from_handoff_dict,
    draft_to_handoff_dict,
    is_valid_handoff_dict,
)
from traffictwin.ui.portfolio_explorer import (
    ChallengeExecutionStatus,
    ChallengeSeedDefinition,
    get_challenge_seed,
    get_challenge_seed_library,
)


def test_deterministic_mapping() -> None:
    c = get_challenge_seed("CH-01-arena-surge")
    assert c is not None
    d1 = build_challenge_whatif_draft(c)
    d2 = build_challenge_whatif_draft(c)
    assert d1.fingerprint == d2.fingerprint
    assert d1.model_dump(mode="json") == d2.model_dump(mode="json")
    # Also deterministic via ID helper
    d3 = build_draft_for_challenge_id("CH-01-arena-surge")
    assert d3 is not None
    assert d3.fingerprint == d1.fingerprint


def test_unknown_field_remains_unsupported() -> None:
    c = ChallengeSeedDefinition(
        challenge_id="CH-99-unknown",
        title="Unknown field test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={"unknown.field": 123, "another.weird": "x"},
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    d = build_challenge_whatif_draft(c)
    assert len(d.unsupported_fields) == 2
    paths = {f.challenge_path for f in d.unsupported_fields}
    assert "unknown.field" in paths
    assert "another.weird" in paths
    assert len(d.supported_fields) == 0
    assert d.mapping_status == ChallengeWhatIfMappingStatus.NOT_MAPPABLE


def test_abstract_capacity_mode_never_becomes_numeric_capacity() -> None:
    c = ChallengeSeedDefinition(
        challenge_id="CH-99-capacity",
        title="Capacity mode test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={
            "infrastructure.rsu_capacity_mode": RsuCapacityMode.REDUCED.value,
        },
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    d = build_challenge_whatif_draft(c)
    assert len(d.unsupported_fields) == 1
    assert d.unsupported_fields[0].challenge_path == "infrastructure.rsu_capacity_mode"
    assert "UNSUPPORTED BY CURRENT WHAT-IF CONTROLS" in d.unsupported_fields[0].reason
    # Must NOT produce numeric rsu_capacity
    assert "rsu_capacity" not in d.whatif_overrides
    assert len(d.supported_fields) == 0
    # Also test that even if we had a REDUCED mode alongside a valid field,
    # the valid field maps but capacity mode stays unsupported
    c2 = ChallengeSeedDefinition(
        challenge_id="CH-99-capacity2",
        title="Capacity mode mixed",
        purpose="test",
        why_challenging="test",
        parameter_overrides={
            "infrastructure.rsu_capacity_mode": RsuCapacityMode.REDUCED.value,
            "demand.multiplier": 1.5,
        },
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    d2 = build_challenge_whatif_draft(c2)
    assert any(f.challenge_path == "demand.multiplier" for f in d2.supported_fields)
    assert any(
        f.challenge_path == "infrastructure.rsu_capacity_mode" for f in d2.unsupported_fields
    )
    assert "rsu_capacity" not in d2.whatif_overrides
    assert d2.whatif_overrides.get("congestion_multiplier") == 1.5


def test_unsupported_ordering_not_silently_lost() -> None:
    c = ChallengeSeedDefinition(
        challenge_id="CH-99-ordering",
        title="Ordering test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={
            "workload.ordering": WorkloadOrdering.EASY_FIRST.value,
        },
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    d = build_challenge_whatif_draft(c)
    assert len(d.unsupported_fields) == 1
    assert d.unsupported_fields[0].challenge_path == "workload.ordering"
    assert "UNSUPPORTED BY CURRENT WHAT-IF CONTROLS" in d.unsupported_fields[0].reason
    assert len(d.supported_fields) == 0


def test_unsupported_fleet_tier_not_silently_converted() -> None:
    c = ChallengeSeedDefinition(
        challenge_id="CH-99-fleet",
        title="Fleet tier test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={
            "fleet.tier_mix": FleetTierMix.WEAK.value,
        },
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    d = build_challenge_whatif_draft(c)
    assert len(d.unsupported_fields) == 1
    assert d.unsupported_fields[0].challenge_path == "fleet.tier_mix"
    assert "UNSUPPORTED BY CURRENT WHAT-IF CONTROLS" in d.unsupported_fields[0].reason
    assert len(d.supported_fields) == 0


def test_fingerprint_changes_when_mapped_content_changes() -> None:
    c = get_challenge_seed("CH-01-arena-surge")
    assert c is not None
    d1 = build_challenge_whatif_draft(c)
    c2 = copy.deepcopy(c)
    # Supported field is demand.multiplier — change within representable range
    c2.parameter_overrides["demand.multiplier"] = 1.8
    d2 = build_challenge_whatif_draft(c2)
    assert d1.fingerprint != d2.fingerprint


def test_fingerprint_changes_when_unsupported_content_changes() -> None:
    c = get_challenge_seed("CH-05-load-aware-forwarding")
    assert c is not None
    d1 = build_challenge_whatif_draft(c)
    # CH-05 has unsupported fleet.tier_mix — changing it should affect fingerprint
    c2 = copy.deepcopy(c)
    # Change unsupported fleet tier value
    original_val = c2.parameter_overrides["fleet.tier_mix"]
    new_val = (
        FleetTierMix.HIGH_COMPUTE.value
        if original_val != FleetTierMix.HIGH_COMPUTE.value
        else FleetTierMix.WEAK.value
    )
    c2.parameter_overrides["fleet.tier_mix"] = new_val
    d2 = build_challenge_whatif_draft(c2)
    assert d1.fingerprint != d2.fingerprint
    # Adding a new unsupported field should also change fingerprint
    c3 = copy.deepcopy(c)
    c3.parameter_overrides["infrastructure.rsu_capacity_mode"] = RsuCapacityMode.REDUCED.value
    d3 = build_challenge_whatif_draft(c3)
    assert d1.fingerprint != d3.fingerprint


def test_no_path_secret_leakage() -> None:
    for c in get_challenge_seed_library():
        d = build_challenge_whatif_draft(c)
        handoff = draft_to_handoff_dict(d)
        payload = json.dumps(handoff, sort_keys=True, default=str)
        assert "/Users/" not in payload
        assert "/tmp/" not in payload  # noqa: S108 - asserting no tmp path leakage is intentional
        assert "/home/" not in payload
        assert "secret" not in payload.lower()
        # Rehydration preserves fingerprint
        restored = draft_from_handoff_dict(handoff)
        assert restored.fingerprint == d.fingerprint
        assert is_valid_handoff_dict(handoff) is True
    # Invalid handoff dicts
    assert is_valid_handoff_dict({}) is False
    assert is_valid_handoff_dict(None) is False  # noqa: S101 - testing None  # type: ignore[arg-type]
    assert is_valid_handoff_dict({"challenge_id": "x"}) is False


def test_all_seven_challenge_ids_handled() -> None:
    library = get_challenge_seed_library()
    assert len(library) == 7
    ids = [c.challenge_id for c in library]
    assert ids == [
        "CH-01-arena-surge",
        "CH-02-lane-closure-corridor",
        "CH-03-t1-heavy-weak-fleet",
        "CH-04-rsu-waiting-room-squeeze",
        "CH-05-load-aware-forwarding",
        "CH-06-stale-state-scheduling",
        "CH-07-scaling-strategy",
    ]
    for cid in ids:
        d = build_draft_for_challenge_id(cid)
        assert d is not None
        assert d.challenge_id == cid
        # Must have at least status classification
        assert d.mapping_status in (
            ChallengeWhatIfMappingStatus.FULLY_MAPPABLE,
            ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE,
            ChallengeWhatIfMappingStatus.NOT_MAPPABLE,
        )
        # Check overrides validate against WhatIf schema if non-empty
        if d.whatif_overrides:
            WhatIfVariationOverrides.model_validate(d.whatif_overrides)


def test_original_challenge_not_mutated() -> None:
    c = get_challenge_seed("CH-03-t1-heavy-weak-fleet")
    assert c is not None
    original_overrides = copy.deepcopy(c.parameter_overrides)
    original_status = c.status
    _ = build_challenge_whatif_draft(c)
    assert c.parameter_overrides == original_overrides
    assert c.status == original_status
    # Also test with a fresh object
    c2 = ChallengeSeedDefinition(
        challenge_id="CH-99-mutate",
        title="Mutate test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={"demand.multiplier": 2.0, "fleet.tier_mix": "weak"},
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    orig2 = copy.deepcopy(c2.parameter_overrides)
    _ = build_challenge_whatif_draft(c2)
    assert c2.parameter_overrides == orig2


def test_challenge_by_challenge_audit() -> None:
    """Audit all seven challenges with expected mapping details."""

    expectations: dict[str, dict[str, object]] = {
        "CH-01-arena-surge": {
            "status": ChallengeWhatIfMappingStatus.FULLY_MAPPABLE,
            "supported_count": 6,
            "unsupported_count": 0,
            "has_supported": True,
        },
        "CH-02-lane-closure-corridor": {
            "status": ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE,
            "supported_count": 6,
            "unsupported_count": 1,
            "has_supported": True,
        },
        "CH-03-t1-heavy-weak-fleet": {
            "status": ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE,
            "supported_count": 3,
            "unsupported_count": 1,
            "has_supported": True,
        },
        "CH-04-rsu-waiting-room-squeeze": {
            "status": ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE,
            "supported_count": 3,
            "unsupported_count": 1,
            "has_supported": True,
        },
        "CH-05-load-aware-forwarding": {
            "status": ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE,
            "supported_count": 2,
            "unsupported_count": 2,
            "has_supported": True,
        },
        "CH-06-stale-state-scheduling": {
            "status": ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE,
            "supported_count": 3,
            "unsupported_count": 1,
            "has_supported": True,
        },
        "CH-07-scaling-strategy": {
            "status": ChallengeWhatIfMappingStatus.FULLY_MAPPABLE,
            "supported_count": 4,
            "unsupported_count": 0,
            "has_supported": True,
        },
    }
    for cid, exp in expectations.items():
        d = build_draft_for_challenge_id(cid)
        assert d is not None, f"missing draft for {cid}"
        assert d.mapping_status == exp["status"], (
            f"{cid}: expected {exp['status']}, got {d.mapping_status}"
        )
        assert len(d.supported_fields) == exp["supported_count"], f"{cid}: supported count"
        assert len(d.unsupported_fields) == exp["unsupported_count"], f"{cid}: unsupported count"
        if exp["has_supported"]:
            assert len(d.supported_fields) >= 1, f"{cid}: should have at least one supported field"


def test_traffic_incident_fields_mapped_correctly() -> None:
    """Traffic incident fields map to IncidentSpec with correct conversions."""
    c = get_challenge_seed("CH-01-arena-surge")
    assert c is not None
    d = build_challenge_whatif_draft(c)
    ov = d.whatif_overrides
    # duration_min 15.0 -> 900.0 s
    assert ov["incident_duration_s"] == 900.0
    assert ov["incident_type"] == "stadium_event"
    assert ov["incident_location"] == "old-trafford-corridor"
    assert ov["event_demand_multiplier"] == 2.0
    assert "incident_enabled" in ov
    assert ov["incident_enabled"] is True


def test_demand_birth_rate_mapping() -> None:
    c = get_challenge_seed("CH-07-scaling-strategy")
    assert c is not None
    d = build_challenge_whatif_draft(c)
    ov = d.whatif_overrides
    # demand 1.0 -> congestion 1.0, birth_rate 2.0 -> 0.2
    assert ov["congestion_multiplier"] == 1.0
    assert ov["task_arrival_rate"] == 0.2
    assert ov["vehicle_count"] == 80
    assert ov["rsu_count"] == 6


def test_workload_class_mix_mapping() -> None:
    c = get_challenge_seed("CH-03-t1-heavy-weak-fleet")
    assert c is not None
    d = build_challenge_whatif_draft(c)
    ov = d.whatif_overrides
    assert ov["task_mix_t1"] == 0.6
    assert ov["task_mix_t2"] == 0.2
    assert ov["task_mix_t3"] == 0.2


def test_range_validation_fails_closed_congestion_above_max() -> None:
    """Out-of-range mapped value must be unsupported, not crash, not FULLY_MAPPABLE."""
    c = ChallengeSeedDefinition(
        challenge_id="CH-99-range-high",
        title="Range high test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={"demand.multiplier": 5.0},
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    d = build_challenge_whatif_draft(c)
    # 5.0 > max 3.0 for congestion_multiplier, so should be unsupported
    assert len(d.supported_fields) == 0
    assert len(d.unsupported_fields) == 1
    assert d.mapping_status == ChallengeWhatIfMappingStatus.NOT_MAPPABLE
    assert "outside current What-If control range" in d.unsupported_fields[0].reason
    assert "above maximum" in d.unsupported_fields[0].reason.lower()
    assert "rsu_capacity" not in d.whatif_overrides
    assert "congestion_multiplier" not in d.whatif_overrides


def test_range_validation_valid_remains_mapped() -> None:
    """Current valid challenge values must remain mapped after range validation."""
    c = get_challenge_seed("CH-01-arena-surge")
    assert c is not None
    d = build_challenge_whatif_draft(c)
    # CH-01 has congestion 2.2 which is within 0.25-3.0
    assert d.mapping_status == ChallengeWhatIfMappingStatus.FULLY_MAPPABLE
    assert any(f.challenge_path == "demand.multiplier" for f in d.supported_fields)


def test_range_validation_partial_with_mixed_validity() -> None:
    """When one field is out-of-range, others still map and status is PARTIAL."""
    c = ChallengeSeedDefinition(
        challenge_id="CH-99-range-mixed",
        title="Range mixed test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={
            "demand.multiplier": 5.0,  # out of range
            "workload.birth_rate_multiplier": 1.5,  # valid -> 0.15
            "infrastructure.rsu_count": 3,  # valid
        },
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    d = build_challenge_whatif_draft(c)
    assert len(d.supported_fields) == 2
    assert len(d.unsupported_fields) == 1
    assert d.mapping_status == ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE
    assert any(f.challenge_path == "demand.multiplier" for f in d.unsupported_fields)
    assert d.whatif_overrides.get("task_arrival_rate") == 0.15
    assert d.whatif_overrides.get("rsu_count") == 3
    assert "congestion_multiplier" not in d.whatif_overrides


def test_range_validation_low_bound() -> None:
    """Below-minimum value should also fail closed."""
    c = ChallengeSeedDefinition(
        challenge_id="CH-99-range-low",
        title="Range low test",
        purpose="test",
        why_challenging="test",
        parameter_overrides={"demand.multiplier": 0.1},  # below min 0.25
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
    )
    d = build_challenge_whatif_draft(c)
    assert len(d.unsupported_fields) == 1
    assert "outside current What-If control range" in d.unsupported_fields[0].reason
