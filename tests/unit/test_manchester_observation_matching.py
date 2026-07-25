"""Adversarial evidence for real observation-to-network map matching.

The policy under test is the owner-approved candidate policy
``manchester-dft-map-match-owner-candidate-1.0``. Fixtures are small synthetic
networks; the values they encode were measured on the accepted Greater
Manchester network and the 305 real Manchester count points.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.network_geometry import (
    EdgeSpatialIndex,
    build_edge_index,
)
from traffictwin.integration.manchester.observation_matching import (
    DFT_UNNUMBERED_ROAD_PLACEHOLDERS,
    HARD_EXCLUDED_CLASSES,
    MAJOR_ROAD_CLASSES,
    MINOR_ROAD_CLASSES,
    ManchesterMapMatchPolicy,
    ObservationMatch,
    ObservationMatchingError,
    angular_difference,
    bare_road_class,
    classify_edge_class,
    dft_road_reference,
    edge_bearing_degrees,
    is_signed_reference,
    match_observation,
    normalise_road_reference,
    policy_summary_fingerprint,
)

PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
NET_OFFSET = "-517074.60,-5908760.37"


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


POLICY = ManchesterMapMatchPolicy()


class TestPolicyIsTheApprovedOne:
    def test_the_approved_values_are_recorded_exactly(self) -> None:
        assert POLICY.outer_search_radius_m == Decimal("50")
        assert POLICY.native_eligibility_m == Decimal("30")
        assert POLICY.fallback_eligibility_m == Decimal("50")
        assert POLICY.clear_native_m == Decimal("10")
        assert POLICY.clear_fallback_m == Decimal("20")
        assert POLICY.direction_tolerance_degrees == Decimal("45")
        assert POLICY.sensitivity_radii_m == (
            Decimal("10"),
            Decimal("20"),
            Decimal("30"),
            Decimal("50"),
            Decimal("100"),
        )

    def test_automatic_acceptance_is_disabled_in_version_one(self) -> None:
        assert POLICY.automatic_acceptance_enabled is False
        assert POLICY.service_requires_manual_confirmation is True
        assert POLICY.fuzzy_text_matching_accepts is False

    def test_the_policy_never_claims_supervisor_approval(self) -> None:
        assert POLICY.research_status == "owner_approved_candidate"
        assert POLICY.supervisor_approved is False
        assert POLICY.scientifically_validated is False

    def test_a_forged_supervisor_claim_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(POLICY.canonical_json())
        payload["supervisor_approved"] = True
        with pytest.raises(ValidationError):
            ManchesterMapMatchPolicy.model_validate_json(json.dumps(payload))

    def test_a_forged_automatic_acceptance_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(POLICY.canonical_json())
        payload["automatic_acceptance_enabled"] = True
        with pytest.raises(ValidationError):
            ManchesterMapMatchPolicy.model_validate_json(json.dumps(payload))

    def test_incoherent_distances_are_refused(self) -> None:
        with pytest.raises(ValidationError, match="cannot exceed the retrieval radius"):
            ManchesterMapMatchPolicy(native_eligibility_m=Decimal("80"))
        with pytest.raises(ValidationError, match="cannot exceed native eligibility"):
            ManchesterMapMatchPolicy(clear_native_m=Decimal("40"))

    def test_the_fingerprint_covers_the_class_lists(self) -> None:
        # The class lists live in module constants, so the plain policy digest
        # would not change if one were edited.
        first = policy_summary_fingerprint(POLICY)
        assert len(first) == 64
        assert first != POLICY.fingerprint()


class TestRoadClassRule:
    def test_pedestrian_only_classes_are_hard_excluded(self) -> None:
        for road_class in ("footway", "path", "cycleway", "steps", "bridleway"):
            assert classify_edge_class(f"highway.{road_class}", "Major") == "hard_excluded"
            assert classify_edge_class(f"highway.{road_class}", "Minor") == "hard_excluded"

    def test_major_admits_only_major_classes(self) -> None:
        assert classify_edge_class("highway.trunk", "Major") == "admissible"
        assert classify_edge_class("highway.primary", "Major") == "admissible"
        assert classify_edge_class("highway.residential", "Major") == "wrong_road_type_family"

    def test_minor_admits_only_minor_classes(self) -> None:
        assert classify_edge_class("highway.residential", "Minor") == "admissible"
        assert classify_edge_class("highway.service", "Minor") == "admissible"
        assert classify_edge_class("highway.motorway", "Minor") == "wrong_road_type_family"

    def test_a_class_outside_the_approved_policy_is_reported_distinctly(self) -> None:
        # Seven classes present in the real network are in neither list. Folding
        # them into hard_excluded would report the policy as more complete than
        # it is, so they fail closed under their own reason.
        for road_class in ("pedestrian", "track", "busway", "bus_guideway", "raceway"):
            assert classify_edge_class(f"highway.{road_class}", "Major") == "not_in_approved_policy"

    def test_a_railway_is_not_a_road_class(self) -> None:
        assert classify_edge_class("railway.rail", "Major") == "not_a_road_class"
        assert classify_edge_class("railway.tram", "Minor") == "not_a_road_class"

    def test_a_missing_class_is_reported_not_guessed(self) -> None:
        assert classify_edge_class(None, "Major") == "class_missing"

    def test_the_three_class_sets_do_not_overlap(self) -> None:
        assert not (MAJOR_ROAD_CLASSES & MINOR_ROAD_CLASSES)
        assert not (HARD_EXCLUDED_CLASSES & MAJOR_ROAD_CLASSES)
        assert not (HARD_EXCLUDED_CLASSES & MINOR_ROAD_CLASSES)

    def test_bare_class_strips_only_the_network_prefix(self) -> None:
        assert bare_road_class("highway.primary") == "primary"
        assert bare_road_class("railway.rail") is None
        assert bare_road_class(None) is None


class TestRoadIdentity:
    def test_normalisation_is_conservative(self) -> None:
        assert normalise_road_reference(" a56 ") == "A56"
        assert normalise_road_reference("A 56") == "A56"
        assert normalise_road_reference(None) is None

    def test_normalisation_never_merges_different_roads(self) -> None:
        assert normalise_road_reference("A56") != normalise_road_reference("A566")

    def test_a_motorway_standard_a_road_is_a_signed_reference(self) -> None:
        # A57(M) appears in the real Manchester data.
        assert is_signed_reference(normalise_road_reference("A57(M)")) is True

    def test_dft_category_placeholders_are_not_references(self) -> None:
        # 125 of 305 real sites carry "U" and 19 carry "C". Comparing those as
        # road numbers would make every site disagree with every edge.
        assert frozenset({"U", "C"}) == DFT_UNNUMBERED_ROAD_PLACEHOLDERS
        assert dft_road_reference("U") is None
        assert dft_road_reference("C") is None
        assert dft_road_reference("A56") == "A56"
        assert dft_road_reference("B5093") == "B5093"


class TestDirectionGeometry:
    def test_a_bearing_is_measured_clockwise_from_north(self) -> None:
        assert edge_bearing_degrees((0.0, 0.0, 0.0, 10.0)) == Decimal("0.000")
        assert edge_bearing_degrees((0.0, 0.0, 10.0, 0.0)) == Decimal("90.000")
        assert edge_bearing_degrees((0.0, 0.0, 0.0, -10.0)) == Decimal("180.000")
        assert edge_bearing_degrees((0.0, 0.0, -10.0, 0.0)) == Decimal("270.000")

    def test_a_degenerate_edge_has_no_bearing(self) -> None:
        assert edge_bearing_degrees((0.0, 0.0, 0.0, 0.0)) is None
        assert edge_bearing_degrees((0.0, 0.0)) is None

    def test_angular_difference_wraps_the_short_way(self) -> None:
        assert angular_difference(Decimal("350"), Decimal("10")) == Decimal("20")
        assert angular_difference(Decimal("10"), Decimal("350")) == Decimal("20")
        assert angular_difference(Decimal("0"), Decimal("180")) == Decimal("180")


class TestCandidateGeneration:
    def test_a_clean_single_road_is_triaged_clear(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("E1", "highway.primary", ref="A56"))
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=POLICY,
        )
        assert match.confidence == "clear_candidate"
        assert len(match.groups) == 1
        assert match.groups[0].exact_reference_match is True

    def test_even_a_clear_candidate_awaits_the_analyst(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("E1", "highway.primary", ref="A56"))
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=POLICY,
        )
        assert match.disposition == "awaiting_analyst_review"
        assert match.automatically_accepted is False
        assert match.analyst_reviewed is False

    def test_a_footway_beside_the_point_is_rejected_with_its_reason(self, tmp_path: Path) -> None:
        body = f"{_edge('E1', 'highway.primary', ref='A56')}\n{_edge('E2', 'highway.footway')}"
        index = _index(tmp_path, body)
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=POLICY,
        )
        assert {rejection.reason for rejection in match.rejections} == {"hard_excluded"}
        assert all(group.road_class_family != "footway" for group in match.groups)

    def test_a_site_with_only_excluded_neighbours_terminates_explicitly(
        self, tmp_path: Path
    ) -> None:
        index = _index(tmp_path, _edge("E1", "highway.footway"))
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=POLICY,
        )
        assert match.confidence == "no_suitable_candidate"
        assert match.disposition == "no_suitable_candidate"
        assert match.rejections, "the rejected edge must stay in the ledger"

    def test_a_service_candidate_always_needs_confirmation(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("E1", "highway.service"))
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Minor",
            dft_road_name="U",
            dft_road_ref=None,
            index=index,
            policy=POLICY,
        )
        assert match.confidence == "review_required"
        assert match.groups[0].contains_service_member is True
        assert match.groups[0].members[0].requires_manual_confirmation is True

    def test_competing_groups_force_review(self, tmp_path: Path) -> None:
        body = (
            f"{_edge('E1', 'highway.primary', ref='A56')}\n"
            f"{_edge('E2', 'highway.trunk', ref='A57')}"
        )
        index = _index(tmp_path, body)
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=POLICY,
        )
        assert match.confidence == "review_required"
        assert len(match.groups) > 1

    def test_an_unsupported_road_type_is_refused(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("E1", "highway.primary"))
        easting, northing = _site(index)
        with pytest.raises(ObservationMatchingError, match="UNSUPPORTED_ROAD_TYPE"):
            match_observation(
                count_point_id=1,
                easting=easting,
                northing=northing,
                dft_road_type="Motorway",
                dft_road_name=None,
                dft_road_ref=None,
                index=index,
                policy=POLICY,
            )


class TestNothingDisappears:
    def test_a_result_always_has_exactly_one_terminal_disposition(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("E1", "highway.primary", ref="A56"))
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=POLICY,
        )
        assert match.disposition in {
            "accepted_by_analyst",
            "rejected_by_analyst",
            "no_suitable_candidate",
            "unavailable_missing_evidence",
            "awaiting_analyst_review",
        }

    def test_a_no_candidate_result_cannot_carry_groups(self) -> None:
        payload: dict[str, Any] = {
            "policy_fingerprint": "a" * 64,
            "count_point_id": 1,
            "dft_road_type": "Major",
            "confidence": "no_suitable_candidate",
            "disposition": "awaiting_analyst_review",
        }
        with pytest.raises(ValidationError, match="must terminate as no_suitable_candidate"):
            ObservationMatch.model_validate_json(json.dumps(payload))

    def test_a_candidate_result_cannot_self_accept(self, tmp_path: Path) -> None:
        index = _index(tmp_path, _edge("E1", "highway.primary", ref="A56"))
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=POLICY,
        )
        payload: dict[str, Any] = json.loads(match.canonical_json())
        payload["disposition"] = "accepted_by_analyst"
        with pytest.raises(ValidationError, match="must await analyst review"):
            ObservationMatch.model_validate_json(json.dumps(payload))

    def test_edge_level_lineage_survives_grouping(self, tmp_path: Path) -> None:
        body = (
            f"{_edge('E1', 'highway.primary', ref='A56')}\n"
            f"{_edge('E2', 'highway.primary', ref='A56')}"
        )
        index = _index(tmp_path, body)
        easting, northing = _site(index)
        match = match_observation(
            count_point_id=1,
            easting=easting,
            northing=northing,
            dft_road_type="Major",
            dft_road_name="A56",
            dft_road_ref="A56",
            index=index,
            policy=POLICY,
        )
        assert len(match.groups) == 1, "same reference and family should group"
        assert {member.edge_id for member in match.groups[0].members} == {"E1", "E2"}
