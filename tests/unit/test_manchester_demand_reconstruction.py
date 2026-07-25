"""Evidence for count-constrained candidate demand input.

Direction application is the subject: the approved policy applies a raw count's
direction to the underlying directed edges *after* an undirected road group is
identified, and the three outcomes must never merge.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.demand_reconstruction import (
    ACCEPTANCE_BASIS,
    DEMAND_LABEL,
    EXCLUDED_PANDEMIC_YEARS,
    CountConstrainedDemandInput,
    DemandInputLedger,
    DemandReconstructionError,
    DirectionResolution,
    EdgeHourCount,
    demand_input_fingerprint,
    ordinals_by_edge_id,
    resolve_direction,
    site_is_in_survey_window,
    write_edgedata_counts,
)
from traffictwin.integration.manchester.network_geometry import (
    EdgeSpatialIndex,
    build_edge_index,
)

PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
NET_OFFSET = "-517074.60,-5908760.37"
TOLERANCE = Decimal("45")


def _index(tmp_path: Path, edges: str, junctions: str) -> EdgeSpatialIndex:
    head = (
        f'  <location netOffset="{NET_OFFSET}" convBoundary="0.00,0.00,5000.00,5000.00" '
        f'origBoundary="-2.40,53.30,-2.10,53.60" projParameter="{PROJ}"/>'
    )
    target = tmp_path / "n.net.xml"
    target.write_text(
        f"<?xml version='1.0'?>\n<net>\n{head}\n{junctions}\n{edges}\n</net>\n", encoding="utf-8"
    )
    return build_edge_index(target)


def _straight_network(tmp_path: Path) -> EdgeSpatialIndex:
    """One northbound and one southbound edge on the same alignment."""

    junctions = (
        '  <junction id="A" type="priority" x="31000.00" y="16000.00" incLanes="" intLanes=""/>\n'
        '  <junction id="B" type="priority" x="31000.00" y="16400.00" incLanes="" intLanes=""/>'
    )
    edges = (
        '  <edge id="NB" from="A" to="B" type="highway.primary" '
        'shape="31000.00,16000.00 31000.00,16400.00">\n  </edge>\n'
        '  <edge id="SB" from="B" to="A" type="highway.primary" '
        'shape="31000.00,16400.00 31000.00,16000.00">\n  </edge>'
    )
    return _index(tmp_path, edges, junctions)


def _collinear_fragments(tmp_path: Path) -> EdgeSpatialIndex:
    """Two northbound fragments of one carriageway, split at a junction."""

    junctions = (
        '  <junction id="A" type="priority" x="31000.00" y="16000.00" incLanes="" intLanes=""/>\n'
        '  <junction id="B" type="priority" x="31000.00" y="16400.00" incLanes="" intLanes=""/>'
    )
    edges = (
        '  <edge id="N1" from="A" to="B" type="highway.primary" '
        'shape="31000.00,16000.00 31000.00,16200.00">\n  </edge>\n'
        '  <edge id="N2" from="A" to="B" type="highway.primary" '
        'shape="31000.00,16200.00 31000.00,16400.00">\n  </edge>'
    )
    return _index(tmp_path, edges, junctions)


class TestDirectionApplication:
    def test_a_single_compatible_edge_binds(self, tmp_path: Path) -> None:
        index = _straight_network(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["NB", "SB"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="N",
            member_edge_ids=["NB"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
        )
        assert result.binding == "bound_to_single_edge"
        assert result.edge_id == "NB"

    def test_opposing_edges_are_kept_not_chosen_between(self, tmp_path: Path) -> None:
        # Both carriageways offered but only the northbound one is within 45 deg
        # of north, so this must bind rather than defer.
        index = _straight_network(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["NB", "SB"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="N",
            member_edge_ids=["NB", "SB"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
        )
        assert result.binding == "bound_to_single_edge"
        assert result.edge_id == "NB"

    def test_collinear_fragments_count_as_one_binding_target(self, tmp_path: Path) -> None:
        # Owner ruling, 25 July 2026. SUMO splits one carriageway at every
        # junction, so several fragments run within a couple of degrees of each
        # other and all satisfy the 45 deg tolerance. They are one road, not
        # opposing directions.
        index = _collinear_fragments(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["N1", "N2"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="N",
            member_edge_ids=["N1", "N2"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
            distance_by_edge={"N1": Decimal("3.0"), "N2": Decimal("80.0")},
        )
        assert result.binding == "bound_to_collinear_fragment_group"
        assert result.edge_id == "N1", "a point count binds to the fragment it sits on"
        assert result.collinear_group == ("N1", "N2")
        assert result.collinear_spread_degrees is not None

    def test_the_collapsed_fragment_set_is_kept(self, tmp_path: Path) -> None:
        index = _collinear_fragments(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["N1", "N2"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="N",
            member_edge_ids=["N1", "N2"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
            distance_by_edge={"N1": Decimal("3.0"), "N2": Decimal("80.0")},
        )
        # Collapsing is a review convenience; edge-level lineage must survive it.
        assert set(result.collinear_group) == {"N1", "N2"}
        assert {edge_id for edge_id, _ in result.considered} == {"N1", "N2"}

    def test_collinear_fragments_without_distances_still_defer(self, tmp_path: Path) -> None:
        # Without a distance the fragment carrying the count cannot be
        # identified, so the count is not bound to an arbitrary one.
        index = _collinear_fragments(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["N1", "N2"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="N",
            member_edge_ids=["N1", "N2"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
        )
        assert result.binding == "several_compatible_edges_require_confirmation"
        assert result.edge_id is None

    def test_genuinely_divergent_bearings_still_require_confirmation(self, tmp_path: Path) -> None:
        # Two compatible edges 60 deg apart are not one carriageway, so the
        # ruling does not reach them and the approved policy still defers.
        junctions = (
            '  <junction id="A" type="priority" x="31000.00" y="16000.00" '
            'incLanes="" intLanes=""/>\n'
            '  <junction id="B" type="priority" x="31400.00" y="16400.00" '
            'incLanes="" intLanes=""/>'
        )
        edges = (
            '  <edge id="NNW" from="A" to="B" type="highway.primary" '
            'shape="31000.00,16000.00 30800.00,16346.41">\n  </edge>\n'
            '  <edge id="NNE" from="A" to="B" type="highway.primary" '
            'shape="31000.00,16000.00 31200.00,16346.41">\n  </edge>'
        )
        index = _index(tmp_path, edges, junctions)
        ordinals = ordinals_by_edge_id(index, ["NNW", "NNE"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="N",
            member_edge_ids=["NNW", "NNE"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
            distance_by_edge={"NNW": Decimal("3.0"), "NNE": Decimal("4.0")},
        )
        assert result.binding == "several_compatible_edges_require_confirmation"
        assert result.edge_id is None
        assert result.collinear_spread_degrees is not None
        assert result.collinear_spread_degrees > TOLERANCE

    def test_no_compatible_edge_is_unresolved_not_reversed(self, tmp_path: Path) -> None:
        index = _straight_network(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["NB"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="E",
            member_edge_ids=["NB"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
        )
        assert result.binding == "direction_unresolved"
        assert result.edge_id is None
        assert "not reversed or invented" in result.reason

    def test_a_combined_direction_is_never_forced(self, tmp_path: Path) -> None:
        index = _straight_network(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["NB", "SB"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="C",
            member_edge_ids=["NB", "SB"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
        )
        assert result.binding == "combined_direction_not_forced"
        assert result.edge_id is None

    def test_an_unknown_direction_code_is_reported(self, tmp_path: Path) -> None:
        index = _straight_network(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["NB"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="NE",
            member_edge_ids=["NB"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
        )
        assert result.binding == "direction_absent"

    def test_every_considered_edge_is_recorded(self, tmp_path: Path) -> None:
        index = _straight_network(tmp_path)
        ordinals = ordinals_by_edge_id(index, ["NB", "SB"])
        result = resolve_direction(
            count_point_id=1,
            direction_of_travel="N",
            member_edge_ids=["NB", "SB"],
            index=index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=TOLERANCE,
        )
        assert {edge_id for edge_id, _ in result.considered} == {"NB", "SB"}

    def test_a_resolution_claiming_an_edge_without_binding_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exactly when the direction bound"):
            DirectionResolution(
                count_point_id=1,
                direction_of_travel="N",
                binding="direction_unresolved",
                edge_id="NB",
                tolerance_degrees=TOLERANCE,
                reason="x",
            )


class TestMeasuredZeroStaysDistinct:
    def test_a_measured_zero_must_carry_a_zero_count(self) -> None:
        with pytest.raises(ValidationError, match="measured-zero cell must carry a zero"):
            EdgeHourCount(
                edge_id="NB",
                count_point_id=1,
                direction_of_travel="N",
                hour=7,
                interval_start_s=0,
                interval_end_s=3600,
                all_motor_vehicles=5,
                measured_zero=True,
            )

    def test_a_measured_zero_is_admitted(self) -> None:
        cell = EdgeHourCount(
            edge_id="NB",
            count_point_id=1,
            direction_of_travel="N",
            hour=7,
            interval_start_s=0,
            interval_end_s=3600,
            all_motor_vehicles=0,
            measured_zero=True,
        )
        assert cell.all_motor_vehicles == 0
        assert cell.measured_zero is True


class TestLedgerAccountsForEverything:
    def test_every_site_is_admitted_or_rejected(self) -> None:
        with pytest.raises(ValidationError, match="admitted or rejected, never dropped"):
            DemandInputLedger(
                sites_offered=10,
                sites_admissible=5,
                sites_rejected_wrong_disposition=2,
                directions_offered=0,
                directions_bound=0,
                directions_requiring_confirmation=0,
                directions_unresolved=0,
                directions_combined_not_forced=0,
                cells_bound=0,
                measured_zero_cells_bound=0,
            )

    def test_every_direction_reaches_exactly_one_outcome(self) -> None:
        with pytest.raises(ValidationError, match="exactly one outcome"):
            DemandInputLedger(
                sites_offered=1,
                sites_admissible=1,
                sites_rejected_wrong_disposition=0,
                directions_offered=10,
                directions_bound=3,
                directions_requiring_confirmation=2,
                directions_unresolved=1,
                directions_combined_not_forced=0,
                cells_bound=0,
                measured_zero_cells_bound=0,
            )


class TestTheAcceptanceLimitationPropagates:
    def _input(self) -> CountConstrainedDemandInput:
        resolution = DirectionResolution(
            count_point_id=1,
            direction_of_travel="N",
            binding="bound_to_single_edge",
            edge_id="NB",
            tolerance_degrees=TOLERANCE,
            reason="bound",
        )
        return CountConstrainedDemandInput(
            match_policy_id="manchester-dft-map-match-owner-policy-1.1",
            match_policy_fingerprint="a" * 64,
            direction_tolerance_degrees=TOLERANCE,
            counts=(
                EdgeHourCount(
                    edge_id="NB",
                    count_point_id=1,
                    direction_of_travel="N",
                    hour=7,
                    interval_start_s=0,
                    interval_end_s=3600,
                    all_motor_vehicles=120,
                    measured_zero=False,
                ),
            ),
            resolutions=(resolution,),
            ledger=DemandInputLedger(
                sites_offered=1,
                sites_admissible=1,
                sites_rejected_wrong_disposition=0,
                directions_offered=1,
                directions_bound=1,
                directions_requiring_confirmation=0,
                directions_unresolved=0,
                directions_combined_not_forced=0,
                cells_bound=1,
                measured_zero_cells_bound=0,
            ),
        )

    def test_the_acceptance_basis_is_owner_policy_not_analyst(self) -> None:
        demand = self._input()
        assert demand.acceptance_basis == ACCEPTANCE_BASIS == "owner_policy_accepted_candidate"
        assert demand.analyst_accepted is False
        assert demand.human_accepted is False
        assert demand.supervisor_approved is False

    def test_the_product_is_labelled_a_candidate_not_observed_travel(self) -> None:
        demand = self._input()
        assert demand.demand_label == DEMAND_LABEL == "count_constrained_candidate_demand"
        assert demand.observed_origin_destination_travel is False

    def test_a_forged_analyst_acceptance_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(self._input().canonical_json())
        payload["analyst_accepted"] = True
        with pytest.raises(ValidationError):
            CountConstrainedDemandInput.model_validate_json(json.dumps(payload))

    def test_a_forged_observed_travel_claim_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(self._input().canonical_json())
        payload["observed_origin_destination_travel"] = True
        with pytest.raises(ValidationError):
            CountConstrainedDemandInput.model_validate_json(json.dumps(payload))

    def test_a_count_cannot_bind_to_an_unresolved_edge(self) -> None:
        payload: dict[str, Any] = json.loads(self._input().canonical_json())
        payload["counts"][0]["edge_id"] = "GHOST"
        with pytest.raises(ValidationError, match="the direction step resolved"):
            CountConstrainedDemandInput.model_validate_json(json.dumps(payload))

    def test_edge_totals_aggregate_only_bound_counts(self) -> None:
        assert self._input().edge_totals() == {"NB": 120}


class TestLineageBinding:
    def test_the_fingerprint_binds_every_upstream_artifact(self) -> None:
        base = demand_input_fingerprint(
            match_policy_fingerprint="a" * 64,
            profile_lineage_fingerprint="b" * 64,
            network_identity_sha256="c" * 64,
        )
        changed_network = demand_input_fingerprint(
            match_policy_fingerprint="a" * 64,
            profile_lineage_fingerprint="b" * 64,
            network_identity_sha256="d" * 64,
        )
        changed_profile = demand_input_fingerprint(
            match_policy_fingerprint="a" * 64,
            profile_lineage_fingerprint="e" * 64,
            network_identity_sha256="c" * 64,
        )
        assert len({base, changed_network, changed_profile}) == 3


class TestTheOwnersSurveyWindow:
    """Option A, selected 25 July 2026 and recorded in commit 13ae063: each site
    is represented by its latest survey, admitted only if that survey falls in
    2019 or in 2022 and later."""

    def test_the_pandemic_years_are_excluded(self) -> None:
        assert frozenset({"2020", "2021"}) == EXCLUDED_PANDEMIC_YEARS
        assert site_is_in_survey_window("2020-06-15") is False
        assert site_is_in_survey_window("2021-11-02") is False

    def test_two_thousand_nineteen_is_admitted(self) -> None:
        assert site_is_in_survey_window("2019-03-15") is True

    def test_two_thousand_twenty_two_onward_is_admitted(self) -> None:
        for date in ("2022-03-30", "2023-01-01", "2024-04-16", "2025-10-14"):
            assert site_is_in_survey_window(date) is True

    def test_everything_before_two_thousand_nineteen_is_excluded(self) -> None:
        for date in ("2018-04-17", "2015-07-08", "2009-05-01", "2000-04-04"):
            assert site_is_in_survey_window(date) is False

    def test_the_window_gap_is_deliberate_not_a_range(self) -> None:
        # 2019 in, 2020 and 2021 out, 2022 in. A plain ">= 2019" rule would
        # silently readmit pandemic-restricted traffic.
        admitted = [
            y for y in ("2019", "2020", "2021", "2022") if site_is_in_survey_window(f"{y}-06-01")
        ]
        assert admitted == ["2019", "2022"]


class TestEdgeDataWriting:
    def _count(self, edge_id: str, hour: int, vehicles: int) -> EdgeHourCount:
        return EdgeHourCount(
            edge_id=edge_id,
            count_point_id=1,
            direction_of_travel="N",
            hour=hour,
            interval_start_s=(hour - 7) * 3600,
            interval_end_s=(hour - 7) * 3600 + 3600,
            all_motor_vehicles=vehicles,
            measured_zero=vehicles == 0,
        )

    def test_counts_are_written_in_the_attribute_routesampler_reads(self, tmp_path: Path) -> None:
        target = tmp_path / "counts.edgedata.xml"
        write_edgedata_counts(target, [self._count("E1", 7, 120)])
        body = target.read_text(encoding="utf-8")
        assert 'entered="120"' in body, "routeSampler reads the entered attribute by default"
        assert '<edge id="E1"' in body

    def test_one_interval_per_hour_with_exact_half_open_windows(self, tmp_path: Path) -> None:
        target = tmp_path / "counts.edgedata.xml"
        written = write_edgedata_counts(
            target, [self._count("E1", 7, 10), self._count("E1", 8, 20)]
        )
        body = target.read_text(encoding="utf-8")
        assert '<interval id="h00" begin="0" end="3600">' in body
        assert '<interval id="h01" begin="3600" end="7200">' in body
        assert written == {"h00": 1, "h01": 1}

    def test_a_measured_zero_is_written_as_zero(self, tmp_path: Path) -> None:
        target = tmp_path / "counts.edgedata.xml"
        write_edgedata_counts(target, [self._count("E1", 7, 0)])
        assert 'entered="0"' in target.read_text(encoding="utf-8")

    def test_an_empty_count_set_is_refused(self, tmp_path: Path) -> None:
        # An edgeData file with no observations would assert an unconstrained
        # network rather than a measured one.
        with pytest.raises(DemandReconstructionError, match="NO_BOUND_COUNTS"):
            write_edgedata_counts(tmp_path / "counts.edgedata.xml", [])

    def test_edges_are_written_in_a_stable_order(self, tmp_path: Path) -> None:
        target = tmp_path / "counts.edgedata.xml"
        write_edgedata_counts(target, [self._count("E2", 7, 5), self._count("E1", 7, 5)])
        body = target.read_text(encoding="utf-8")
        assert body.index('id="E1"') < body.index('id="E2"')
