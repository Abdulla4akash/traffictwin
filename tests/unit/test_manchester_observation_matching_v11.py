"""Adversarial evidence for exploratory owner-policy v1.1.

The override under test relaxes the DfT/OSM road-class family split when an
exact normalised signed reference matches. Every guard is attacked here: wrong
references, duplicate reference groups, non-motor edges, excessive distance, and
the acceptance vocabulary that must never claim a person reviewed anything.

Fixtures are small synthetic networks; the situation they reproduce is real —
21 of the 305 Manchester count points terminated with no suitable candidate
under v1.0, several on the A56 and A6042 with a rejected edge under a metre away.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.network_connectivity import MotorAccess
from traffictwin.integration.manchester.network_geometry import (
    EdgeSpatialIndex,
    build_edge_index,
)
from traffictwin.integration.manchester.observation_matching import (
    ManchesterMapMatchPolicy,
    match_observation,
)
from traffictwin.integration.manchester.observation_matching_v11 import (
    MOTOR_PERMITTING_ACCESS,
    ManchesterMapMatchPolicyV11,
    ManualReviewEntry,
    ManualReviewQueue,
    ObservationMatchV11,
    PolicyReconciliation,
    build_manual_review_queue,
    match_observation_v11,
    permits_motor_vehicles,
    policy_v11_summary_fingerprint,
    reconcile_policies,
)

PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
NET_OFFSET = "-517074.60,-5908760.37"

POLICY = ManchesterMapMatchPolicyV11()


def _network(body: str) -> str:
    head = (
        f'  <location netOffset="{NET_OFFSET}" convBoundary="0.00,0.00,5000.00,5000.00" '
        f'origBoundary="-2.40,53.30,-2.10,53.60" projParameter="{PROJ}"/>'
    )
    return f"<?xml version='1.0'?>\n<net>\n{head}\n{body}\n</net>\n"


def _junctions(*names: str) -> str:
    return "\n".join(
        f'  <junction id="{name}" type="priority" x="{31000 + index * 60}.00" '
        f'y="{16000 + index * 60}.00" incLanes="" intLanes=""/>'
        for index, name in enumerate(names)
    )


def _edge(edge_id: str, road_type: str, *, ref: str | None = None, shape: str | None = None) -> str:
    geometry = f' shape="{shape}"' if shape else ""
    body = f'    <param key="ref" value="{ref}"/>\n' if ref else ""
    return (
        f'  <edge id="{edge_id}" from="J0" to="J1" type="{road_type}"{geometry}>\n{body}  </edge>'
    )


def _index(tmp_path: Path, body: str) -> EdgeSpatialIndex:
    target = tmp_path / "n.net.xml"
    target.write_text(_network(f"{_junctions('J0', 'J1')}\n{body}"), encoding="utf-8")
    return build_edge_index(target)


def _site(index: EdgeSpatialIndex, ordinal: int = 0) -> tuple[float, float]:
    geometry = index.geometry(ordinal)
    return geometry[0], geometry[1]


def _access(*edge_ids: str, level: MotorAccess = "passenger_car") -> dict[str, MotorAccess]:
    return dict.fromkeys(edge_ids, level)


def _match(
    index: EdgeSpatialIndex,
    *,
    easting: float,
    northing: float,
    road_type: str = "Major",
    road_name: str | None = "A56",
    road_ref: str | None = "A56",
    access: dict[str, MotorAccess] | None = None,
    policy: ManchesterMapMatchPolicyV11 = POLICY,
) -> ObservationMatchV11:
    return match_observation_v11(
        count_point_id=1,
        easting=easting,
        northing=northing,
        dft_road_type=road_type,
        dft_road_name=road_name,
        dft_road_ref=road_ref,
        index=index,
        policy=policy,
        motor_access=access,
    )


class TestThePolicyDeclaresWhatItIs:
    def test_it_is_exploratory_candidate_software_evidence(self) -> None:
        assert POLICY.exploratory_candidate_software_evidence is True
        assert POLICY.scientifically_validated is False
        assert POLICY.supervisor_approved is False

    def test_owner_policy_acceptance_is_never_human_or_analyst_acceptance(self) -> None:
        assert POLICY.owner_policy_acceptance_enabled is True
        assert POLICY.analyst_accepted is False
        assert POLICY.human_accepted is False

    def test_the_override_is_declared_narrow(self) -> None:
        assert POLICY.override_relaxes_only == "wrong_road_type_family"
        assert POLICY.override_max_distance_m == Decimal("5")
        assert POLICY.override_requires_motor_vehicle_access is True
        assert POLICY.override_requires_unique_reference_group is True
        assert POLICY.override_uses_fuzzy_names is False

    def test_v1_1_inherits_every_v1_0_search_value_unchanged(self) -> None:
        # A difference between the two runs can then only come from the override.
        assert POLICY.base == ManchesterMapMatchPolicy()

    def test_a_forged_supervisor_or_analyst_claim_is_refused(self) -> None:
        for field in ("supervisor_approved", "analyst_accepted", "human_accepted"):
            payload: dict[str, Any] = json.loads(POLICY.canonical_json())
            payload[field] = True
            with pytest.raises(ValidationError):
                ManchesterMapMatchPolicyV11.model_validate_json(json.dumps(payload))

    def test_a_forged_fuzzy_name_override_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(POLICY.canonical_json())
        payload["override_uses_fuzzy_names"] = True
        with pytest.raises(ValidationError):
            ManchesterMapMatchPolicyV11.model_validate_json(json.dumps(payload))

    def test_an_override_looser_than_a_clear_match_is_refused(self) -> None:
        # An override is a tighter claim than a strict clear match, never looser.
        with pytest.raises(ValidationError, match="must not exceed the strict clear distance"):
            ManchesterMapMatchPolicyV11(override_max_distance_m=Decimal("25"))

    def test_the_fingerprint_covers_the_inherited_class_lists(self) -> None:
        assert policy_v11_summary_fingerprint(POLICY) != POLICY.fingerprint()

    def test_motor_permission_never_assumes_an_unknown(self) -> None:
        assert permits_motor_vehicles(None) is False
        assert permits_motor_vehicles("no_motor_vehicle") is False
        for level in MOTOR_PERMITTING_ACCESS:
            assert permits_motor_vehicles(level) is True  # type: ignore[arg-type]


class TestTheOverrideRescuesTheRealCase:
    """A Major count point on an A road that OSM tags as a minor class."""

    def test_v1_0_finds_nothing_for_this_site(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=ManchesterMapMatchPolicy(),
        )
        assert result.confidence == "no_suitable_candidate"
        assert result.rejections[0].reason == "wrong_road_type_family"

    def test_v1_1_accepts_it_under_the_override(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert result.disposition == "owner_policy_accepted_candidate"
        assert result.acceptance_path == "exact_reference_family_override"
        assert result.overrides_applied[0].reason == "exact_reference_family_override"

    def test_the_accepted_row_carries_an_audit_flag(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        assert _match(index, easting=easting, northing=northing, access=_access("e1")).audit_flag

    def test_the_family_mismatch_is_preserved_and_displayed(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert result.family_mismatch is not None
        assert "Major" in result.family_mismatch
        assert "highway.unclassified" in result.family_mismatch
        assert "preserved, not repaired" in result.family_mismatch

    def test_the_original_rejection_is_still_in_the_ledger(self, tmp_path: Path) -> None:
        # An override readmits a candidate; it does not erase the record that
        # the candidate was rejected first.
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert [item.reason for item in result.rejections] == ["wrong_road_type_family"]

    def test_the_row_never_claims_a_person_reviewed_it(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert result.analyst_accepted is False
        assert result.human_accepted is False
        assert result.supervisor_approved is False
        assert result.exploratory_candidate_software_evidence is True


class TestWrongReferencesNeverOverride:
    def test_a_different_road_number_does_not_override(self, tmp_path: Path) -> None:
        # A56 and A566 are different roads and no normalisation may blur that.
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A566"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert result.disposition != "owner_policy_accepted_candidate"
        assert [item.refusal for item in result.overrides_refused] == ["reference_not_exact"]

    def test_an_edge_with_no_reference_does_not_override(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert [item.refusal for item in result.overrides_refused] == ["reference_not_exact"]

    def test_an_observation_with_no_reference_does_not_override(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(
            index,
            easting=easting,
            northing=northing,
            road_name=None,
            road_ref=None,
            access=_access("e1"),
        )
        assert [item.refusal for item in result.overrides_refused] == ["reference_absent"]
        assert result.disposition != "owner_policy_accepted_candidate"

    def test_a_matching_road_name_alone_never_overrides(self, tmp_path: Path) -> None:
        # Fuzzy or name-based identity is never an override basis.
        index = _index(tmp_path, _edge("e1", "highway.unclassified"))
        easting, northing = _site(index)
        result = _match(
            index,
            easting=easting,
            northing=northing,
            road_name="CHESTER ROAD",
            road_ref=None,
            access=_access("e1"),
        )
        assert not result.overrides_applied
        assert result.disposition != "owner_policy_accepted_candidate"


class TestDuplicateReferenceGroupsNeverOverride:
    def test_two_competing_exact_reference_groups_refuse_the_override(self, tmp_path: Path) -> None:
        # Competing identities are ambiguity, not a tie to break.
        index = _index(
            tmp_path,
            "\n".join(
                (
                    _edge("e1", "highway.unclassified", ref="A56"),
                    _edge("e2", "highway.residential", ref="A56"),
                )
            ),
        )
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1", "e2"))
        assert result.disposition == "awaiting_manual_review"
        assert result.acceptance_path is None
        assert result.override_acceptance_refused == "several_exact_reference_groups"

    def test_ambiguous_candidates_stay_visible_rather_than_disappearing(
        self, tmp_path: Path
    ) -> None:
        # Discarding the readmitted candidates would report an ambiguous site as
        # having no suitable candidate at all, which loses the very evidence an
        # analyst needs to resolve it.
        index = _index(
            tmp_path,
            "\n".join(
                (
                    _edge("e1", "highway.unclassified", ref="A56"),
                    _edge("e2", "highway.residential", ref="A56"),
                )
            ),
        )
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1", "e2"))
        assert result.confidence == "review_required"
        assert {item.edge_id for item in result.overrides_applied} == {"e1", "e2"}
        assert len([group for group in result.groups if group.exact_reference_match]) == 2
        assert any("same exact signed reference" in reason for reason in result.review_reasons)

    def test_an_admissible_exact_match_beside_a_family_mismatch_refuses_the_override(
        self, tmp_path: Path
    ) -> None:
        # The strict path already has a candidate, so no override is needed and
        # none is applied.
        index = _index(
            tmp_path,
            "\n".join(
                (
                    _edge("e1", "highway.primary", ref="A56"),
                    _edge("e2", "highway.unclassified", ref="A56"),
                )
            ),
        )
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1", "e2"))
        assert result.acceptance_path == "strict_v1_0_clear"
        assert result.override_acceptance_refused == "strict_path_already_accepted"
        assert result.audit_flag is False

    def test_a_readmitted_candidate_never_demotes_a_strict_acceptance(self, tmp_path: Path) -> None:
        # v1.1 must never accept less than v1.0 did.
        index = _index(
            tmp_path,
            "\n".join(
                (
                    _edge("e1", "highway.primary", ref="A56"),
                    _edge("e2", "highway.unclassified", ref="A56"),
                )
            ),
        )
        easting, northing = _site(index)
        older = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=ManchesterMapMatchPolicy(),
        )
        newer = _match(index, easting=easting, northing=northing, access=_access("e1", "e2"))
        assert older.confidence == "clear_candidate"
        assert newer.disposition == "owner_policy_accepted_candidate"


class TestNonMotorEdgesNeverOverride:
    def test_an_edge_that_permits_no_motor_vehicle_is_refused(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(
            index,
            easting=easting,
            northing=northing,
            access=_access("e1", level="no_motor_vehicle"),
        )
        assert [item.refusal for item in result.overrides_refused] == [
            "does_not_permit_motor_vehicles"
        ]
        assert result.disposition != "owner_policy_accepted_candidate"

    def test_unknown_motor_access_fails_closed(self, tmp_path: Path) -> None:
        # "We could not tell" is never "it permits traffic".
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access={})
        assert [item.refusal for item in result.overrides_refused] == ["motor_access_unknown"]

    def test_an_absent_access_lookup_fails_closed(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=None)
        assert result.disposition != "owner_policy_accepted_candidate"

    def test_a_hard_excluded_class_is_never_reachable_by_the_override(self, tmp_path: Path) -> None:
        # The override relaxes the family split only; a footway stays rejected.
        index = _index(tmp_path, _edge("e1", "highway.footway", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert not result.overrides_applied
        assert not result.overrides_refused
        assert [item.reason for item in result.rejections] == ["hard_excluded"]

    def test_a_class_outside_the_approved_lists_is_never_overridden(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.busway", ref="A56"))
        easting, northing = _site(index)
        result = _match(
            index,
            easting=easting,
            northing=northing,
            access=_access("e1", level="motor_vehicle_no_car"),
        )
        assert not result.overrides_applied
        assert [item.reason for item in result.rejections] == ["not_in_approved_policy"]

    def test_a_service_edge_still_requires_manual_confirmation(self, tmp_path: Path) -> None:
        # v1.0's standing service rule survives v1.1 unchanged.
        index = _index(tmp_path, _edge("e1", "highway.service", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert [item.refusal for item in result.overrides_refused] == [
            "service_class_requires_manual_confirmation"
        ]
        assert result.disposition != "owner_policy_accepted_candidate"


class TestExcessiveDistanceNeverOverrides:
    def test_a_candidate_beyond_the_override_distance_is_refused(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        # 12 m away: inside v1.0 eligibility, well outside the 5 m override.
        result = _match(index, easting=easting + 12.0, northing=northing, access=_access("e1"))
        assert [item.refusal for item in result.overrides_refused] == ["beyond_override_distance"]
        assert result.disposition != "owner_policy_accepted_candidate"

    def test_a_candidate_just_inside_the_override_distance_is_accepted(
        self, tmp_path: Path
    ) -> None:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting + 4.0, northing=northing, access=_access("e1"))
        assert result.acceptance_path == "exact_reference_family_override"


class TestTheStrictPathIsUnchanged:
    def test_a_v1_0_clear_candidate_becomes_owner_policy_accepted(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.primary", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert result.acceptance_path == "strict_v1_0_clear"
        assert result.audit_flag is False
        assert result.family_mismatch is None

    def test_a_strict_acceptance_is_still_not_analyst_acceptance(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.primary", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert result.analyst_accepted is False
        assert "No analyst, human, or supervisor has reviewed it" in " ".join(result.reasons)

    def test_a_site_with_no_candidate_at_all_stays_unavailable(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.footway", ref="A56"))
        easting, northing = _site(index)
        result = _match(index, easting=easting, northing=northing, access=_access("e1"))
        assert result.disposition == "no_suitable_candidate"
        assert not result.groups


class TestTheArtifactRefusesToLie:
    def _accepted(self, tmp_path: Path) -> ObservationMatchV11:
        index = _index(tmp_path, _edge("e1", "highway.unclassified", ref="A56"))
        easting, northing = _site(index)
        return _match(index, easting=easting, northing=northing, access=_access("e1"))

    def test_a_forged_analyst_acceptance_is_refused(self, tmp_path: Path) -> None:
        for field in ("analyst_accepted", "human_accepted", "supervisor_approved"):
            payload: dict[str, Any] = json.loads(self._accepted(tmp_path).canonical_json())
            payload[field] = True
            with pytest.raises(ValidationError):
                ObservationMatchV11.model_validate_json(json.dumps(payload))

    def test_an_override_acceptance_may_not_drop_the_family_mismatch(self, tmp_path: Path) -> None:
        payload: dict[str, Any] = json.loads(self._accepted(tmp_path).canonical_json())
        payload["family_mismatch"] = None
        with pytest.raises(ValidationError, match="must display the family mismatch"):
            ObservationMatchV11.model_validate_json(json.dumps(payload))

    def test_an_override_acceptance_may_not_drop_its_audit_flag(self, tmp_path: Path) -> None:
        payload: dict[str, Any] = json.loads(self._accepted(tmp_path).canonical_json())
        payload["audit_flag"] = False
        with pytest.raises(ValidationError, match="audit flag marks exactly the override"):
            ObservationMatchV11.model_validate_json(json.dumps(payload))

    def test_a_strict_acceptance_may_not_claim_an_audit_flag(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("e1", "highway.primary", ref="A56"))
        easting, northing = _site(index)
        payload: dict[str, Any] = json.loads(
            _match(index, easting=easting, northing=northing, access=_access("e1")).canonical_json()
        )
        payload["audit_flag"] = True
        with pytest.raises(ValidationError, match="audit flag marks exactly the override"):
            ObservationMatchV11.model_validate_json(json.dumps(payload))

    def test_an_acceptance_without_a_path_is_refused(self, tmp_path: Path) -> None:
        payload: dict[str, Any] = json.loads(self._accepted(tmp_path).canonical_json())
        payload["acceptance_path"] = None
        with pytest.raises(ValidationError):
            ObservationMatchV11.model_validate_json(json.dumps(payload))

    def test_a_review_row_must_say_why(self, tmp_path: Path) -> None:
        index = _index(
            tmp_path,
            "\n".join(
                (
                    _edge("e1", "highway.unclassified", ref="A56"),
                    _edge("e2", "highway.residential", ref="A56"),
                )
            ),
        )
        easting, northing = _site(index)
        payload: dict[str, Any] = json.loads(
            _match(
                index, easting=easting, northing=northing, access=_access("e1", "e2")
            ).canonical_json()
        )
        payload["review_reasons"] = []
        with pytest.raises(ValidationError, match="must say why"):
            ObservationMatchV11.model_validate_json(json.dumps(payload))


class TestTheManualReviewQueueIsPreserved:
    def _results(self, tmp_path: Path) -> list[ObservationMatchV11]:
        accepted_index = _index(tmp_path / "a", _edge("e1", "highway.primary", ref="A56"))
        (tmp_path / "a").mkdir(exist_ok=True)
        review_index = _index(tmp_path / "b", _edge("e1", "highway.unclassified", ref="A566"))
        results = []
        for index in (accepted_index, review_index):
            easting, northing = _site(index)
            results.append(_match(index, easting=easting, northing=northing, access=_access("e1")))
        return results

    def test_unaccepted_rows_are_queued_with_denominators(self, tmp_path: Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        queue = build_manual_review_queue(self._results(tmp_path))
        assert queue.observations_total == 2
        assert queue.accepted_total == 1
        assert queue.queued_total == 1
        assert queue.queue_preserved is True

    def test_an_accepted_row_may_not_enter_the_queue(self) -> None:
        with pytest.raises(ValidationError, match="does not belong in the manual review queue"):
            ManualReviewEntry(
                count_point_id=1,
                dft_road_type="Major",
                confidence="clear_candidate",
                disposition="owner_policy_accepted_candidate",
                eligible_group_count=1,
                review_reasons=("nothing",),
            )

    def test_a_queue_that_loses_a_row_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="must account for every observation"):
            ManualReviewQueue(observations_total=5, accepted_total=1, queued_total=1, entries=())

    def test_a_queue_that_undercounts_its_entries_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="must list every row it counts"):
            ManualReviewQueue(observations_total=2, accepted_total=1, queued_total=1, entries=())


class TestTheReconciliationIsExact:
    def _pair(self, tmp_path: Path, road_type: str, ref: str) -> tuple[Any, ObservationMatchV11]:
        index = _index(tmp_path, _edge("e1", road_type, ref=ref))
        easting, northing = _site(index)
        older = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=ManchesterMapMatchPolicy(),
        )
        newer = _match(index, easting=easting, northing=northing, access=_access("e1"))
        return older, newer

    def test_every_observation_is_accounted_for(self, tmp_path: Path) -> None:
        older, newer = self._pair(tmp_path, "highway.unclassified", "A56")
        report = reconcile_policies([older], [newer])
        assert report.observations_total == 1
        assert sum(item.observations for item in report.transitions) == 1

    def test_the_rescued_transition_is_published_exactly(self, tmp_path: Path) -> None:
        older, newer = self._pair(tmp_path, "highway.unclassified", "A56")
        report = reconcile_policies([older], [newer])
        assert report.v1_0_no_suitable_candidate == 1
        assert report.v1_1_owner_policy_accepted == 1
        assert report.accepted_by_override_path == 1
        assert report.accepted_by_strict_path == 0

    def test_a_changed_observation_records_the_override_edges(self, tmp_path: Path) -> None:
        older, newer = self._pair(tmp_path, "highway.unclassified", "A56")
        report = reconcile_policies([older], [newer])
        assert report.changed_observations[0].override_edge_ids == ("e1",)
        assert report.changed_observations[0].family_mismatch is not None

    def test_the_strict_path_is_counted_separately(self, tmp_path: Path) -> None:
        older, newer = self._pair(tmp_path, "highway.primary", "A56")
        report = reconcile_policies([older], [newer])
        assert report.accepted_by_strict_path == 1
        assert report.accepted_by_override_path == 0

    def test_mismatched_populations_are_refused(self, tmp_path: Path) -> None:
        older, newer = self._pair(tmp_path, "highway.unclassified", "A56")
        with pytest.raises(Exception, match="RECONCILIATION_POPULATION_MISMATCH"):
            reconcile_policies([older, older], [newer])

    def test_the_reconciliation_never_claims_validation(self, tmp_path: Path) -> None:
        older, newer = self._pair(tmp_path, "highway.unclassified", "A56")
        report = reconcile_policies([older], [newer])
        assert report.scientifically_validated is False
        assert report.supervisor_approved is False
        assert report.exploratory_candidate_software_evidence is True

    def test_a_forged_reconciliation_total_is_refused(self, tmp_path: Path) -> None:
        older, newer = self._pair(tmp_path, "highway.unclassified", "A56")
        payload: dict[str, Any] = json.loads(reconcile_policies([older], [newer]).canonical_json())
        payload["v1_1_owner_policy_accepted"] = 5
        with pytest.raises(ValidationError):
            PolicyReconciliation.model_validate_json(json.dumps(payload))


class TestTheOverrideDoesNotSettleABroaderAmbiguity:
    """The conservative default, and the recorded choice that relaxes it."""

    def _competing(self, tmp_path: Path) -> EdgeSpatialIndex:
        # For a Major site: one exact-reference edge in the *minor* family
        # (which v1.0 rejects on the family split), plus an unreferenced
        # Major-family edge that v1.0 already admitted as a competing group.
        return _index(
            tmp_path,
            "\n".join(
                (
                    _edge("e1", "highway.unclassified", ref="A56"),
                    _edge("e2", "highway.secondary"),
                )
            ),
        )

    def test_by_default_a_competing_group_blocks_the_override(self, tmp_path: Path) -> None:
        index = self._competing(tmp_path)
        easting, northing = _site(index)
        result = _match(
            index,
            easting=easting,
            northing=northing,
            access=_access("e1", "e2"),
        )
        assert result.disposition == "awaiting_manual_review"
        assert result.override_acceptance_refused == "other_eligible_groups_remain"
        assert any("broader ambiguity" in reason for reason in result.review_reasons)

    def test_the_relaxed_reading_is_an_explicit_recorded_choice(self, tmp_path: Path) -> None:
        relaxed = ManchesterMapMatchPolicyV11(override_requires_sole_eligible_group=False)
        index = self._competing(tmp_path)
        easting, northing = _site(index)
        result = _match(
            index,
            easting=easting,
            northing=northing,
            access=_access("e1", "e2"),
            policy=relaxed,
        )
        assert result.acceptance_path == "exact_reference_family_override"

    def test_relaxing_the_guard_changes_the_policy_fingerprint(self) -> None:
        # A different rule must never produce results that look identical.
        relaxed = ManchesterMapMatchPolicyV11(override_requires_sole_eligible_group=False)
        assert relaxed.fingerprint() != POLICY.fingerprint()

    def test_the_conservative_default_is_the_one_that_ships(self) -> None:
        assert POLICY.override_requires_sole_eligible_group is True
