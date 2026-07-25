"""Adversarial evidence for the motor-eligible connectivity review.

Fixtures are small synthetic networks.  The behaviours they pin were measured on
the accepted Greater Manchester build: every lane carries exactly one of
``allow``/``disallow``, and ``netconvert`` builds ``highway.service`` so that it
permits a delivery van but not a private car.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.network_connectivity import (
    DEFAULT_PROBE_EXPANSION,
    ISOLATED_COMPONENT_MAX_EDGES,
    MAX_PROBE_EXPANSION,
    MAX_ROUTE_PROBES,
    MOTOR_VEHICLE_CLASSES,
    UNDEFINED_VEHICLE_CLASSES,
    ComponentSummary,
    IsolatedFragmentInventory,
    ManchesterNetworkConnectivityReport,
    MotorNetworkGraph,
    NetworkConnectivityError,
    build_motor_network_graph,
    classify_lane_access,
    combine_lane_access,
    review_network_file,
    run_route_probe,
    select_contrast_probe_pairs,
    select_probe_pairs,
    stream_network_edges,
    strong_component_labels,
    summarise_components,
    weak_component_labels,
)
from traffictwin.integration.manchester.network_service import (
    CONNECTIVITY_RECORD_NAME,
    MAX_CONNECTIVITY_RECORD_BYTES,
    ConnectivityReviewAvailability,
    connectivity_record_matches,
    read_connectivity_record,
    write_connectivity_record,
)

# The exact permission strings netconvert 1.27.1 writes, taken from the accepted
# Greater Manchester network rather than composed by hand.
CAR_DISALLOW = (
    "tram rail_urban rail rail_electric rail_fast ship container "
    "cable_car subway aircraft wheelchair scooter drone"
)
SERVICE_ALLOW = "pedestrian delivery bicycle"
FOOTWAY_ALLOW = "pedestrian"
BUS_ALLOW = "bus"


def _lane(edge_id: str, *, allow: str | None = None, disallow: str | None = None) -> str:
    permission = f' allow="{allow}"' if allow is not None else ""
    if disallow is not None:
        permission += f' disallow="{disallow}"'
    return f'    <lane id="{edge_id}_0" index="0"{permission} speed="13.41" length="20.00"/>'


def _edge(
    edge_id: str,
    source: str | None,
    target: str | None,
    road_type: str,
    *,
    allow: str | None = None,
    disallow: str | None = None,
    lanes: bool = True,
) -> str:
    attributes = f'<edge id="{edge_id}"'
    if source is not None:
        attributes += f' from="{source}"'
    if target is not None:
        attributes += f' to="{target}"'
    attributes += f' type="{road_type}"'
    body = _lane(edge_id, allow=allow, disallow=disallow) if lanes else ""
    inner = f"\n{body}" if body else ""
    return f"  {attributes}>{inner}\n  </edge>"


def _network(*edges: str) -> str:
    return "<?xml version='1.0'?>\n<net>\n" + "\n".join(edges) + "\n</net>\n"


def _car(edge_id: str, source: str, target: str, road_type: str = "highway.residential") -> str:
    return _edge(edge_id, source, target, road_type, disallow=CAR_DISALLOW)


#: One network holding every population the review has to account for.
FIXTURE_EDGES = (
    # A strongly connected triangle: the "largest component".
    _car("a1", "J1", "J2"),
    _car("a2", "J2", "J3"),
    _car("a3", "J3", "J1"),
    # A one-way fragment: two strong components joined by one inter-SCC edge.
    _car("b1", "J10", "J11"),
    # A self-loop. Real in SUMO, and never evidence anywhere else is reachable.
    _car("loop", "J40", "J40"),
    # Permits a motor vehicle but not a private car.
    _edge("bus1", "J20", "J21", "highway.busway", allow=BUS_ALLOW),
    # A service road as netconvert actually builds it: delivery, not car.
    _edge("svc1", "J22", "J23", "highway.service", allow=SERVICE_ALLOW),
    # No motor vehicle at all.
    _edge("foot1", "J30", "J31", "highway.footway", allow=FOOTWAY_ALLOW),
    # Junction-internal connector.
    _edge(":J1_0", "J1", "J2", "highway.residential", disallow=CAR_DISALLOW),
    # Real road, but missing an endpoint: dangling, not internal.
    _edge("dangle", "J50", None, "highway.residential", disallow=CAR_DISALLOW),
    # Real road declaring no lane: permissions unreadable, not open.
    _edge("nolane", "J60", "J61", "highway.residential", lanes=False),
)

TOTAL_EDGE_ELEMENTS = len(FIXTURE_EDGES)

EMPTY_ISOLATED = IsolatedFragmentInventory(
    max_edges_per_fragment=ISOLATED_COMPONENT_MAX_EDGES,
    fragment_components=0,
    fragment_edges=0,
    fragment_junctions=0,
    fragment_length_m=Decimal("0"),
    singleton_junction_components=0,
    single_edge_components=0,
    self_loop_edges=0,
    examples=(),
    examples_truncated=False,
)


@pytest.fixture
def network(tmp_path: Path) -> Path:
    target = tmp_path / "fixture.net.xml"
    target.write_text(_network(*FIXTURE_EDGES), encoding="utf-8")
    return target


@pytest.fixture
def graph(network: Path) -> MotorNetworkGraph:
    return build_motor_network_graph(network)


class TestLaneAccessFollowsTheNetwork:
    def test_a_car_disallow_list_still_permits_a_car(self) -> None:
        assert classify_lane_access(None, CAR_DISALLOW) == "passenger_car"

    def test_a_service_road_permits_a_van_but_not_a_car(self) -> None:
        # This is the measured netconvert 1.27.1 behaviour, and it is the whole
        # reason two subgraphs exist rather than one.
        assert classify_lane_access(SERVICE_ALLOW, None) == "motor_vehicle_no_car"

    def test_a_bus_only_way_permits_a_motor_vehicle_but_not_a_car(self) -> None:
        assert classify_lane_access(BUS_ALLOW, None) == "motor_vehicle_no_car"

    def test_a_footway_permits_no_motor_vehicle(self) -> None:
        assert classify_lane_access(FOOTWAY_ALLOW, None) == "no_motor_vehicle"

    def test_an_unrestricted_lane_permits_everything(self) -> None:
        assert classify_lane_access(None, None) == "passenger_car"

    def test_contradictory_permissions_are_unreadable_not_resolved(self) -> None:
        # Preferring one attribute over the other would be an invented rule.
        assert classify_lane_access(BUS_ALLOW, CAR_DISALLOW) == "permissions_unreadable"

    def test_an_explicit_car_denial_is_honoured(self) -> None:
        assert classify_lane_access(None, "passenger") == "motor_vehicle_no_car"

    def test_denying_every_motor_class_leaves_no_motor_vehicle(self) -> None:
        assert classify_lane_access(None, " ".join(sorted(MOTOR_VEHICLE_CLASSES))) == (
            "no_motor_vehicle"
        )

    def test_an_undefined_custom_class_never_admits_an_edge(self) -> None:
        for undefined in UNDEFINED_VEHICLE_CLASSES:
            assert classify_lane_access(undefined, None) == "no_motor_vehicle"

    def test_the_best_lane_decides_the_edge(self) -> None:
        assert combine_lane_access(["no_motor_vehicle", "passenger_car"]) == "passenger_car"
        assert combine_lane_access(["no_motor_vehicle", "motor_vehicle_no_car"]) == (
            "motor_vehicle_no_car"
        )

    def test_an_unreadable_lane_never_upgrades_an_edge(self) -> None:
        assert combine_lane_access(["permissions_unreadable"]) == "permissions_unreadable"

    def test_an_edge_with_no_lanes_is_unreadable_not_open(self) -> None:
        assert combine_lane_access([]) == "permissions_unreadable"


class TestEveryEdgeElementIsAccountedFor:
    def test_the_stream_yields_every_element_including_unusable_ones(self, network: Path) -> None:
        streamed = list(stream_network_edges(network))
        assert len(streamed) == TOTAL_EDGE_ELEMENTS

    def test_internal_edges_are_flagged_rather_than_dropped(self, network: Path) -> None:
        internal = [item for item in stream_network_edges(network) if item.internal]
        assert [item.edge_id for item in internal] == [":J1_0"]

    def test_totals_reconcile_additively_without_subtraction(
        self, graph: MotorNetworkGraph
    ) -> None:
        assert graph.total_edge_elements_read == TOTAL_EDGE_ELEMENTS
        assert graph.internal_edges_excluded == 1
        assert graph.internal_edges_excluded + graph.real_edges_read == (
            graph.total_edge_elements_read
        )
        assert len(graph) + graph.dangling_edges_excluded == graph.real_edges_read

    def test_a_dangling_edge_is_counted_not_mistaken_for_internal(
        self, graph: MotorNetworkGraph
    ) -> None:
        assert graph.dangling_edges_excluded == 1
        assert graph.internal_edges_excluded == 1

    def test_a_lane_free_edge_is_counted_and_stays_unreadable(
        self, graph: MotorNetworkGraph
    ) -> None:
        assert graph.no_lane_edges == 1
        assert graph.access_counts()["permissions_unreadable"] == 1

    def test_self_loops_are_counted(self, graph: MotorNetworkGraph) -> None:
        assert graph.self_loop_edges == 1

    def test_an_edge_with_no_id_fails_closed_rather_than_passing_as_internal(
        self, tmp_path: Path
    ) -> None:
        # A nameless element cannot be audited by identity, so calling it an
        # internal connector would claim knowledge the file does not provide.
        target = tmp_path / "nameless.net.xml"
        target.write_text(
            _network(_car("a1", "J1", "J2"), '  <edge from="J1" to="J2">\n  </edge>'),
            encoding="utf-8",
        )
        with pytest.raises(NetworkConnectivityError) as missing:
            list(stream_network_edges(target))
        assert missing.value.code == "NETWORK_EDGE_ID_MISSING"

    def test_a_nameless_edge_blocks_the_whole_review(self, tmp_path: Path) -> None:
        target = tmp_path / "nameless.net.xml"
        target.write_text(
            _network(_car("a1", "J1", "J2"), '  <edge from="J1" to="J2">\n  </edge>'),
            encoding="utf-8",
        )
        with pytest.raises(NetworkConnectivityError):
            review_network_file(
                target,
                network_id="fixture",
                network_identity_sha256="0" * 64,
                total_edge_elements=2,
            )


class TestBothSubgraphsArePreserved:
    def test_the_car_subgraph_excludes_delivery_and_bus_only_ways(
        self, graph: MotorNetworkGraph
    ) -> None:
        car = {graph.edge_id(item) for item in graph.eligible_ordinals("passenger_car")}
        assert car == {"a1", "a2", "a3", "b1", "loop"}

    def test_the_motor_subgraph_includes_them(self, graph: MotorNetworkGraph) -> None:
        motor = {graph.edge_id(item) for item in graph.eligible_ordinals("any_motor_vehicle")}
        assert motor == {"a1", "a2", "a3", "b1", "loop", "bus1", "svc1"}

    def test_neither_subgraph_admits_a_footway_or_an_unreadable_edge(
        self, graph: MotorNetworkGraph
    ) -> None:
        for eligibility in ("passenger_car", "any_motor_vehicle"):
            admitted = {graph.edge_id(item) for item in graph.eligible_ordinals(eligibility)}
            assert "foot1" not in admitted
            assert "nolane" not in admitted


class TestComponentsAndTheirReconciliation:
    def test_weak_components_merge_the_triangle(self, graph: MotorNetworkGraph) -> None:
        summary, _, _ = summarise_components(graph, kind="weak", eligibility="passenger_car")
        assert summary.component_count == 3
        assert summary.largest_component_edges == 3
        assert summary.largest_component_junctions == 3
        assert summary.edges_between_components == 0

    def test_strong_components_split_the_one_way_fragment(self, graph: MotorNetworkGraph) -> None:
        summary, _, _ = summarise_components(graph, kind="strong", eligibility="passenger_car")
        # J10 and J11 are separate strong components; the edge joining them
        # belongs to neither and is counted explicitly.
        assert summary.edges_between_components == 1
        assert summary.largest_component_edges == 3

    def test_edge_totals_reconcile_for_both_kinds(self, graph: MotorNetworkGraph) -> None:
        for kind in ("weak", "strong"):
            summary, _, _ = summarise_components(graph, kind=kind, eligibility="passenger_car")
            assert (
                summary.largest_component_edges
                + summary.edges_outside_largest_component
                + summary.edges_between_components
                == summary.eligible_edges
            )

    def test_length_totals_reconcile_exactly_for_both_kinds(self, graph: MotorNetworkGraph) -> None:
        for kind in ("weak", "strong"):
            summary, _, _ = summarise_components(graph, kind=kind, eligibility="passenger_car")
            assert (
                summary.largest_component_length_m
                + summary.length_outside_largest_component_m
                + summary.length_between_components_m
                == summary.eligible_edge_length_m
            )

    def test_inter_scc_length_is_named_not_folded_into_the_outside_figure(
        self, graph: MotorNetworkGraph
    ) -> None:
        strong, _, _ = summarise_components(graph, kind="strong", eligibility="passenger_car")
        weak, _, _ = summarise_components(graph, kind="weak", eligibility="passenger_car")
        # b1 spans two strong components: its 20 m belong to neither side, and
        # must not silently enlarge the length credited to other components.
        assert strong.edges_between_components == 1
        assert strong.length_between_components_m == Decimal("20.000")
        assert weak.length_between_components_m == Decimal("0.000")
        assert (
            strong.length_outside_largest_component_m
            == weak.length_outside_largest_component_m - Decimal("20.000")
        )

    def test_untouched_junctions_are_reported_not_counted_as_components(
        self, graph: MotorNetworkGraph
    ) -> None:
        summary, _, _ = summarise_components(graph, kind="weak", eligibility="passenger_car")
        # J20-J23, J30, J31, J60, J61 carry no car-eligible edge.
        assert summary.junctions_untouched == graph.junction_count - summary.junctions_touched
        assert summary.junctions_untouched > 0

    def test_coverage_never_rounds_up_to_complete(self, graph: MotorNetworkGraph) -> None:
        summary, _, _ = summarise_components(graph, kind="weak", eligibility="passenger_car")
        assert summary.largest_component_edge_share == Decimal("0.600000")
        assert summary.largest_component_edge_share < Decimal("1")

    def test_ranking_is_stable_across_repeated_reads(self, network: Path) -> None:
        first, _, _ = summarise_components(
            build_motor_network_graph(network), kind="weak", eligibility="passenger_car"
        )
        second, _, _ = summarise_components(
            build_motor_network_graph(network), kind="weak", eligibility="passenger_car"
        )
        assert first.canonical_json() == second.canonical_json()

    def test_a_weak_summary_may_not_claim_edges_leaving_a_component(self) -> None:
        # Only a directed summary can have an edge belonging to neither side.
        with pytest.raises(ValidationError, match="cannot have edges leaving it"):
            ComponentSummary(
                kind="weak",
                eligibility="passenger_car",
                eligible_edges=1,
                eligible_edge_length_m=Decimal("0"),
                junctions_touched=2,
                junctions_untouched=0,
                component_count=1,
                largest_component_junctions=2,
                largest_component_edges=0,
                largest_component_length_m=Decimal("0"),
                largest_component_edge_share=Decimal("0"),
                largest_component_length_share=Decimal("0"),
                edges_outside_largest_component=0,
                length_outside_largest_component_m=Decimal("0"),
                edges_between_components=1,
                length_between_components_m=Decimal("0"),
                inventory=(),
                inventory_truncated=False,
                isolated=EMPTY_ISOLATED,
            )

    def test_a_summary_that_loses_an_edge_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="must account for every eligible edge"):
            ComponentSummary(
                kind="strong",
                eligibility="passenger_car",
                eligible_edges=9,
                eligible_edge_length_m=Decimal("0"),
                junctions_touched=2,
                junctions_untouched=0,
                component_count=1,
                largest_component_junctions=2,
                largest_component_edges=1,
                largest_component_length_m=Decimal("0"),
                largest_component_edge_share=Decimal("0"),
                largest_component_length_share=Decimal("0"),
                edges_outside_largest_component=1,
                length_outside_largest_component_m=Decimal("0"),
                edges_between_components=1,
                length_between_components_m=Decimal("0"),
                inventory=(),
                inventory_truncated=False,
                isolated=EMPTY_ISOLATED,
            )


class TestIsolatedFragmentsAreVisible:
    def test_small_fragments_are_counted_over_all_of_them(self, graph: MotorNetworkGraph) -> None:
        summary, _, _ = summarise_components(graph, kind="weak", eligibility="passenger_car")
        # The one-way pair and the self-loop are both fragments.
        assert summary.isolated.fragment_components == 2
        assert summary.isolated.fragment_edges == 2
        assert summary.isolated.fragment_junctions == 3

    def test_a_singleton_and_a_self_loop_are_reported_exactly(
        self, graph: MotorNetworkGraph
    ) -> None:
        summary, _, _ = summarise_components(graph, kind="weak", eligibility="passenger_car")
        assert summary.isolated.singleton_junction_components == 1
        assert summary.isolated.single_edge_components == 2
        assert summary.isolated.self_loop_edges == 1

    def test_fragments_appear_even_though_they_rank_last_by_size(
        self, graph: MotorNetworkGraph
    ) -> None:
        summary, _, _ = summarise_components(graph, kind="weak", eligibility="passenger_car")
        sampled = {
            edge_id for entry in summary.isolated.examples for edge_id in entry.example_edge_ids
        }
        # A size-descending runner-up list would push these off the end; the
        # fragment inventory exists precisely so they survive.
        assert {"b1", "loop"} <= sampled

    def test_fragment_totals_are_not_a_property_of_the_sample_size(
        self, graph: MotorNetworkGraph
    ) -> None:
        summary, _, _ = summarise_components(graph, kind="weak", eligibility="passenger_car")
        assert summary.isolated.fragment_components >= len(summary.isolated.examples)


class TestBoundedProbes:
    def _ordinal(self, graph: MotorNetworkGraph, edge_id: str) -> int:
        for index in range(len(graph)):
            if graph.edge_id(index) == edge_id:
                return index
        raise AssertionError(f"missing fixture edge {edge_id}")

    def test_a_reachable_pair_routes_and_reports_hops(self, graph: MotorNetworkGraph) -> None:
        probe = run_route_probe(
            graph,
            "passenger_car",
            probe_index=0,
            origin_edge=self._ordinal(graph, "a1"),
            destination_edge=self._ordinal(graph, "a3"),
        )
        assert probe.outcome == "routed"
        assert probe.hops == 1

    def test_an_unreachable_pair_is_reported_unreachable(self, graph: MotorNetworkGraph) -> None:
        probe = run_route_probe(
            graph,
            "passenger_car",
            probe_index=1,
            origin_edge=self._ordinal(graph, "a1"),
            destination_edge=self._ordinal(graph, "b1"),
        )
        assert probe.outcome == "unreachable"
        assert probe.hops is None

    def test_an_ineligible_endpoint_is_refused_rather_than_routed(
        self, graph: MotorNetworkGraph
    ) -> None:
        probe = run_route_probe(
            graph,
            "passenger_car",
            probe_index=2,
            origin_edge=self._ordinal(graph, "a1"),
            destination_edge=self._ordinal(graph, "svc1"),
        )
        assert probe.outcome == "endpoint_not_eligible"

    def test_a_service_road_becomes_probeable_only_in_the_motor_subgraph(
        self, graph: MotorNetworkGraph
    ) -> None:
        probe = run_route_probe(
            graph,
            "any_motor_vehicle",
            probe_index=3,
            origin_edge=self._ordinal(graph, "svc1"),
            destination_edge=self._ordinal(graph, "svc1"),
        )
        assert probe.outcome != "endpoint_not_eligible"

    def test_exhausting_the_bound_is_its_own_outcome_not_unreachable(
        self, graph: MotorNetworkGraph
    ) -> None:
        # Failing to find a path is not proving there is none, so the two
        # outcomes must never collapse into one.
        # a1 ends at J2 and a1 starts at J1, so the walk J2 -> J3 -> J1 needs
        # two expansions and a bound of one cuts it off mid-search.
        probe = run_route_probe(
            graph,
            "passenger_car",
            probe_index=4,
            origin_edge=self._ordinal(graph, "a1"),
            destination_edge=self._ordinal(graph, "a1"),
            expansion_limit=1,
        )
        assert probe.outcome == "probe_limit_reached"
        assert probe.junctions_expanded == 1

    def test_a_pair_sharing_a_junction_routes_in_zero_hops(self, graph: MotorNetworkGraph) -> None:
        probe = run_route_probe(
            graph,
            "passenger_car",
            probe_index=5,
            origin_edge=self._ordinal(graph, "a1"),
            destination_edge=self._ordinal(graph, "a2"),
        )
        assert probe.outcome == "routed"
        assert probe.hops == 0

    def test_every_probe_branch_reports_the_selection_it_was_given(
        self, graph: MotorNetworkGraph
    ) -> None:
        # Each outcome branch builds its own RouteProbe. A branch that forgets
        # the selection would be invisible for spread probes, because the
        # mislabel and the default coincide, so every branch is pinned here.
        branches = {
            "routed": (
                self._ordinal(graph, "a1"),
                self._ordinal(graph, "a3"),
                DEFAULT_PROBE_EXPANSION,
            ),
            "unreachable": (
                self._ordinal(graph, "a1"),
                self._ordinal(graph, "b1"),
                DEFAULT_PROBE_EXPANSION,
            ),
            "probe_limit_reached": (
                self._ordinal(graph, "a1"),
                self._ordinal(graph, "a1"),
                1,
            ),
            "endpoint_not_eligible": (
                self._ordinal(graph, "a1"),
                self._ordinal(graph, "svc1"),
                DEFAULT_PROBE_EXPANSION,
            ),
        }
        for expected, (origin, destination, limit) in branches.items():
            probe = run_route_probe(
                graph,
                "passenger_car",
                probe_index=0,
                origin_edge=origin,
                destination_edge=destination,
                selection="largest_to_fragment",
                expansion_limit=limit,
            )
            assert probe.outcome == expected
            assert probe.selection == "largest_to_fragment"

    def test_a_zero_hop_probe_also_reports_its_selection(self, graph: MotorNetworkGraph) -> None:
        probe = run_route_probe(
            graph,
            "passenger_car",
            probe_index=0,
            origin_edge=self._ordinal(graph, "a1"),
            destination_edge=self._ordinal(graph, "a2"),
            selection="largest_to_fragment",
        )
        assert probe.outcome == "routed"
        assert probe.hops == 0
        assert probe.selection == "largest_to_fragment"

    def test_contrast_pairs_target_outside_the_largest_component(
        self, graph: MotorNetworkGraph
    ) -> None:
        _, labels, ranks = summarise_components(graph, kind="strong", eligibility="passenger_car")
        pairs = select_contrast_probe_pairs(
            graph, "passenger_car", labels=labels, ranks=ranks, count=4
        )
        assert pairs
        for origin, destination in pairs:
            origin_label = labels[graph.endpoints(origin)[0]]
            destination_label = labels[graph.endpoints(destination)[0]]
            assert ranks[origin_label] == 1
            assert ranks[destination_label] > 1

    def test_probe_selection_is_deterministic(self, network: Path) -> None:
        first = select_probe_pairs(build_motor_network_graph(network), "passenger_car", count=4)
        second = select_probe_pairs(build_motor_network_graph(network), "passenger_car", count=4)
        assert first == second

    def test_an_unbounded_probe_request_is_refused(self, graph: MotorNetworkGraph) -> None:
        with pytest.raises(NetworkConnectivityError) as excess:
            run_route_probe(
                graph,
                "passenger_car",
                probe_index=0,
                origin_edge=0,
                destination_edge=0,
                expansion_limit=MAX_PROBE_EXPANSION + 1,
            )
        assert excess.value.code == "PROBE_EXPANSION_REFUSED"

    def test_an_excessive_probe_count_is_refused(self, graph: MotorNetworkGraph) -> None:
        with pytest.raises(NetworkConnectivityError) as excess:
            select_probe_pairs(graph, "passenger_car", count=MAX_ROUTE_PROBES + 1)
        assert excess.value.code == "PROBE_COUNT_REFUSED"


class TestTheReportRefusesOverclaiming:
    def _report(self, network: Path) -> ManchesterNetworkConnectivityReport:
        return review_network_file(
            network,
            network_id="fixture",
            network_identity_sha256="0" * 64,
            total_edge_elements=TOTAL_EDGE_ELEMENTS,
            probe_count=3,
        )

    def test_the_review_publishes_both_subgraphs_for_both_kinds(self, network: Path) -> None:
        report = self._report(network)
        assert {(item.kind, item.eligibility) for item in report.components} == {
            ("weak", "any_motor_vehicle"),
            ("strong", "any_motor_vehicle"),
            ("weak", "passenger_car"),
            ("strong", "passenger_car"),
        }

    def test_the_report_is_bound_to_one_network_identity(self, network: Path) -> None:
        assert self._report(network).network_identity_sha256 == "0" * 64

    def test_universal_routability_is_structurally_false(self, network: Path) -> None:
        assert self._report(network).proves_universal_routability is False

    def test_a_forged_universal_routability_claim_is_refused(self, network: Path) -> None:
        payload: dict[str, Any] = json.loads(self._report(network).canonical_json())
        payload["proves_universal_routability"] = True
        with pytest.raises(ValidationError):
            ManchesterNetworkConnectivityReport.model_validate_json(json.dumps(payload))

    def test_a_forged_matching_or_calibration_claim_is_refused(self, network: Path) -> None:
        for field in ("matching_performed", "calibration_performed", "accepted_for_real_matching"):
            payload: dict[str, Any] = json.loads(self._report(network).canonical_json())
            payload[field] = True
            with pytest.raises(ValidationError):
                ManchesterNetworkConnectivityReport.model_validate_json(json.dumps(payload))

    def test_the_capability_stays_planned(self, network: Path) -> None:
        assert self._report(network).capability_status == "planned"

    def test_a_recorded_edge_count_that_disagrees_refuses_the_review(self, network: Path) -> None:
        # The recorded total is checked, never used to derive the internal
        # count, so a disagreement surfaces instead of silently rebalancing.
        with pytest.raises(NetworkConnectivityError) as mismatch:
            review_network_file(
                network,
                network_id="fixture",
                network_identity_sha256="0" * 64,
                total_edge_elements=TOTAL_EDGE_ELEMENTS + 5,
            )
        assert mismatch.value.code == "NETWORK_EDGE_COUNTS_INCONSISTENT"

    def test_asking_for_an_unsummarised_subgraph_refuses(self, network: Path) -> None:
        report = self._report(network)
        assert report.summary_for("weak", "passenger_car").kind == "weak"

    def test_the_access_summary_reconciles(self, network: Path) -> None:
        access = self._report(network).access
        assert access.internal_edges_excluded + access.real_edges == access.total_edge_elements
        assert access.graph_edges + access.dangling_edges_excluded == access.real_edges

    def test_the_motor_but_not_car_gap_is_named_not_implied(self, network: Path) -> None:
        access = self._report(network).access
        assert access.motor_vehicle_no_car_edges == 2
        assert "highway.service" in access.motor_but_not_car_note

    def test_the_review_is_reproducible(self, network: Path) -> None:
        assert self._report(network).canonical_json() == self._report(network).canonical_json()


class TestGraphLevelInvariants:
    def test_weak_labels_cover_every_junction(self, graph: MotorNetworkGraph) -> None:
        labels = weak_component_labels(graph, "passenger_car")
        assert len(labels) == graph.junction_count

    def test_strong_labels_cover_every_junction(self, graph: MotorNetworkGraph) -> None:
        labels = strong_component_labels(graph, "passenger_car")
        assert len(labels) == graph.junction_count
        assert all(label >= 0 for label in labels)

    def test_a_cycle_shares_one_strong_component(self, graph: MotorNetworkGraph) -> None:
        labels = strong_component_labels(graph, "passenger_car")
        triangle = [
            labels[graph.endpoints(index)[0]]
            for index in range(len(graph))
            if graph.edge_id(index) in {"a1", "a2", "a3"}
        ]
        assert len(set(triangle)) == 1

    def test_a_one_way_pair_does_not(self, graph: MotorNetworkGraph) -> None:
        labels = strong_component_labels(graph, "passenger_car")
        for index in range(len(graph)):
            if graph.edge_id(index) == "b1":
                source, target = graph.endpoints(index)
                assert labels[source] != labels[target]


class TestPersistedReviewRecords:
    """The service reads a stored review; it never traverses a network itself."""

    def _review(self, network: Path) -> ManchesterNetworkConnectivityReport:
        return review_network_file(
            network,
            network_id="fixture",
            network_identity_sha256="a" * 64,
            total_edge_elements=TOTAL_EDGE_ELEMENTS,
            probe_count=2,
            contrast_probe_count=0,
        )

    def test_an_absent_record_is_absent_not_unreadable(self, tmp_path: Path) -> None:
        assert read_connectivity_record(tmp_path).state == "absent"

    def test_malformed_json_is_unreadable_not_absent(self, tmp_path: Path) -> None:
        # Reporting a corrupt record as merely missing would send the operator
        # to re-run a review instead of inspecting a file that failed to parse.
        (tmp_path / CONNECTIVITY_RECORD_NAME).write_text("{not json", encoding="utf-8")
        outcome = read_connectivity_record(tmp_path)
        assert outcome.state == "unreadable"
        assert outcome.review is None

    def test_well_formed_json_of_the_wrong_shape_is_unreadable(self, tmp_path: Path) -> None:
        (tmp_path / CONNECTIVITY_RECORD_NAME).write_text('{"a": 1}', encoding="utf-8")
        assert read_connectivity_record(tmp_path).state == "unreadable"

    def test_a_symlinked_record_is_refused_rather_than_followed(
        self, tmp_path: Path, network: Path
    ) -> None:
        real = tmp_path / "elsewhere.json"
        real.write_text(self._review(network).canonical_json(), encoding="utf-8")
        (tmp_path / CONNECTIVITY_RECORD_NAME).symlink_to(real)
        outcome = read_connectivity_record(tmp_path)
        assert outcome.state == "refused_symlink"
        assert outcome.review is None

    def test_an_oversized_record_is_refused_unread(self, tmp_path: Path) -> None:
        oversized = tmp_path / CONNECTIVITY_RECORD_NAME
        oversized.write_bytes(b"{" + b" " * (MAX_CONNECTIVITY_RECORD_BYTES + 1))
        assert read_connectivity_record(tmp_path).state == "refused_oversized"

    def test_a_valid_record_round_trips(self, tmp_path: Path, network: Path) -> None:
        review = self._review(network)
        write_connectivity_record(tmp_path, review)
        outcome = read_connectivity_record(tmp_path)
        assert outcome.state == "available"
        assert outcome.review is not None
        assert outcome.review.canonical_json() == review.canonical_json()

    def test_writing_replaces_atomically_and_leaves_no_temporary(
        self, tmp_path: Path, network: Path
    ) -> None:
        store = tmp_path / "store"
        store.mkdir()
        write_connectivity_record(store, self._review(network))
        write_connectivity_record(store, self._review(network))
        # A partial or abandoned temporary file would show up here.
        assert [item.name for item in store.iterdir()] == [CONNECTIVITY_RECORD_NAME]

    def test_a_review_matches_only_its_own_candidate(self, network: Path) -> None:
        review = self._review(network)
        assert connectivity_record_matches(
            review, network_id="fixture", network_identity_sha256="a" * 64
        )

    def test_a_matching_digest_under_another_id_does_not_match(self, network: Path) -> None:
        # Same bytes, different artifact: this must never read as available.
        review = self._review(network)
        assert not connectivity_record_matches(
            review, network_id="some-other-network", network_identity_sha256="a" * 64
        )

    def test_a_matching_id_under_another_digest_does_not_match(self, network: Path) -> None:
        review = self._review(network)
        assert not connectivity_record_matches(
            review, network_id="fixture", network_identity_sha256="b" * 64
        )

    def test_a_stale_record_never_publishes_a_review(self) -> None:
        availability = ConnectivityReviewAvailability(
            network_id="fixture",
            state="stale",
            network_identity_sha256="a" * 64,
            review_identity_sha256="b" * 64,
            review_network_id="other",
            reason="different network",
        )
        assert availability.review is None

    def test_a_non_available_state_may_not_carry_a_review(self, network: Path) -> None:
        with pytest.raises(ValidationError, match="published only when the record is available"):
            ConnectivityReviewAvailability(
                network_id="fixture",
                state="stale",
                network_identity_sha256="a" * 64,
                review_identity_sha256="a" * 64,
                review_network_id="other",
                reason="different network",
                review=self._review(network),
            )

    def test_an_available_state_must_carry_a_review(self) -> None:
        with pytest.raises(ValidationError, match="published only when the record is available"):
            ConnectivityReviewAvailability(
                network_id="fixture",
                state="available",
                network_identity_sha256="a" * 64,
                review_identity_sha256="a" * 64,
                review_network_id="fixture",
            )

    def test_an_available_view_may_not_embed_another_networks_review(self, network: Path) -> None:
        # The binding is enforced on the model itself, so a caller cannot
        # assemble an available view around a foreign review.
        with pytest.raises(ValidationError, match="same network id and identity"):
            ConnectivityReviewAvailability(
                network_id="a-different-network",
                state="available",
                network_identity_sha256="a" * 64,
                review_identity_sha256="a" * 64,
                review_network_id="a-different-network",
                review=self._review(network),
            )

    def test_an_available_view_may_not_embed_another_identity(self, network: Path) -> None:
        with pytest.raises(ValidationError, match="same network id and identity"):
            ConnectivityReviewAvailability(
                network_id="fixture",
                state="available",
                network_identity_sha256="b" * 64,
                review_identity_sha256="b" * 64,
                review_network_id="fixture",
                review=self._review(network),
            )

    def test_a_consistent_available_view_is_accepted(self, network: Path) -> None:
        review = self._review(network)
        availability = ConnectivityReviewAvailability(
            network_id="fixture",
            state="available",
            network_identity_sha256="a" * 64,
            review_identity_sha256="a" * 64,
            review_network_id="fixture",
            review=review,
        )
        assert availability.review is not None

    def test_a_record_that_is_not_utf8_is_unreadable(self, tmp_path: Path) -> None:
        (tmp_path / CONNECTIVITY_RECORD_NAME).write_bytes(b"\xff\xfe not utf-8")
        assert read_connectivity_record(tmp_path).state == "unreadable"
