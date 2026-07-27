"""Unit coverage for the predeclared §2 route-pool diagnosis measurements.

Every pool here is tiny and synthetic. Nothing in this module touches a real
route pool, the alpha.7 candidate demand, or any simulation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.integration.manchester.demand_diagnosis import (
    DemandDiagnosisError,
    EdgeAttributes,
    PoolRoute,
    RoutePoolDiagnosis,
    diagnose_route_pool,
    iter_route_pool,
    render_diagnosis_markdown,
    summarise,
)


def _edges() -> dict[str, EdgeAttributes]:
    """Four edges of 1 km each; ``e1`` is the only boundary entry."""

    return {
        "e1": EdgeAttributes(length_m=1000.0, free_flow_speed_mps=10.0, is_boundary=True),
        "e2": EdgeAttributes(length_m=1000.0, free_flow_speed_mps=20.0),
        "e3": EdgeAttributes(length_m=1000.0, free_flow_speed_mps=25.0),
        "e4": EdgeAttributes(length_m=2000.0, free_flow_speed_mps=10.0),
    }


def _pool() -> list[PoolRoute]:
    return [
        PoolRoute(route_id="r0", edge_ids=("e1", "e2", "e3")),
        PoolRoute(route_id="r1", edge_ids=("e2", "e3")),
        PoolRoute(route_id="r2", edge_ids=("e1", "e4")),
    ]


def _diagnose(**overrides: object) -> RoutePoolDiagnosis:
    arguments: dict[str, object] = {
        "routes": _pool(),
        "edges": _edges(),
        "counted_edge_ids": ["e2", "e4"],
        "pool_label": "synthetic-pool",
    }
    arguments.update(overrides)
    return diagnose_route_pool(
        arguments["routes"],  # type: ignore[arg-type]
        arguments["edges"],  # type: ignore[arg-type]
        arguments["counted_edge_ids"],  # type: ignore[arg-type]
        pool_label=str(arguments["pool_label"]),
    )


def test_edge_attributes_refuse_undefined_residence_time() -> None:
    with pytest.raises(DemandDiagnosisError, match="free-flow speed must be positive"):
        EdgeAttributes(length_m=100.0, free_flow_speed_mps=0.0)
    with pytest.raises(DemandDiagnosisError, match="length must be positive"):
        EdgeAttributes(length_m=0.0, free_flow_speed_mps=10.0)


def test_route_length_distribution_is_measured_in_km() -> None:
    diagnosis = _diagnose()

    # r0 = 3 km, r1 = 2 km, r2 = 1 + 2 = 3 km.
    assert diagnosis.route_length_km.n == 3
    assert diagnosis.route_length_km.minimum == pytest.approx(2.0)
    assert diagnosis.route_length_km.maximum == pytest.approx(3.0)
    assert diagnosis.route_length_km.mean == pytest.approx(8.0 / 3)
    assert diagnosis.route_length_km.p50 == pytest.approx(3.0)


def test_route_edge_count_distribution_needs_no_edge_mapping() -> None:
    diagnosis = _diagnose()

    assert diagnosis.route_edge_count.n == 3
    assert diagnosis.route_edge_count.minimum == pytest.approx(2.0)
    assert diagnosis.route_edge_count.maximum == pytest.approx(3.0)


def test_free_flow_residence_time_sums_per_edge_traversal() -> None:
    diagnosis = _diagnose()

    # r0 = 1000/10 + 1000/20 + 1000/25 = 100 + 50 + 40 = 190 s
    # r1 = 50 + 40 = 90 s ; r2 = 100 + 2000/10 = 300 s
    assert diagnosis.free_flow_residence_time_s.minimum == pytest.approx(90.0)
    assert diagnosis.free_flow_residence_time_s.maximum == pytest.approx(300.0)
    assert diagnosis.free_flow_residence_time_s.mean == pytest.approx((190 + 90 + 300) / 3)


def test_counted_edge_multiplicity_counts_routes_not_traversals() -> None:
    pool = [
        # A route that doubles back over e2 must still count once.
        PoolRoute(route_id="r0", edge_ids=("e2", "e3", "e2")),
        PoolRoute(route_id="r1", edge_ids=("e2", "e4")),
    ]

    diagnosis = _diagnose(routes=pool)

    assert diagnosis.counted_edge_count == 2
    # e2 is on both routes, e4 on one.
    assert diagnosis.counted_edge_multiplicity.n == 2
    assert diagnosis.counted_edge_multiplicity.maximum == pytest.approx(2.0)
    assert diagnosis.counted_edge_multiplicity.minimum == pytest.approx(1.0)
    assert diagnosis.counted_edges_with_zero_coverage == 0


def test_counted_edges_no_route_touches_are_reported() -> None:
    diagnosis = _diagnose(counted_edge_ids=["e2", "e4", "e9"])

    assert diagnosis.counted_edge_count == 3
    assert diagnosis.counted_edges_with_zero_coverage == 1


def test_fringe_share_counts_routes_entering_from_a_boundary_edge() -> None:
    diagnosis = _diagnose()

    # r0 and r2 both start on the boundary edge e1; r1 starts on e2.
    assert diagnosis.fringe_denominator == 3
    assert diagnosis.fringe_entry_route_count == 2
    assert diagnosis.fringe_share == pytest.approx(2 / 3)


def test_fringe_share_is_unavailable_rather_than_zero_without_a_denominator() -> None:
    diagnosis = _diagnose(
        routes=[PoolRoute(route_id="r0", edge_ids=("unmapped",))],
        edges={},
    )

    assert diagnosis.fringe_denominator == 0
    assert diagnosis.fringe_share is None


def test_routes_with_unknown_edges_are_recorded_not_silently_measured() -> None:
    pool = [*_pool(), PoolRoute(route_id="r3", edge_ids=("e1", "ghost", "other"))]

    diagnosis = _diagnose(routes=pool)

    assert diagnosis.route_count == 4
    assert diagnosis.measured_route_count == 3
    assert diagnosis.routes_with_unknown_edges == 1
    assert diagnosis.unknown_edge_reference_count == 2
    # The unmeasurable route still contributes its edge count and its fringe entry.
    assert diagnosis.route_edge_count.n == 4
    assert diagnosis.fringe_denominator == 4
    assert diagnosis.route_length_km.n == 3


def test_an_empty_pool_summarises_to_explicit_unavailable_values() -> None:
    diagnosis = _diagnose(routes=[])

    assert diagnosis.route_count == 0
    assert diagnosis.route_length_km.n == 0
    assert diagnosis.route_length_km.mean is None
    assert diagnosis.route_length_km.p50 is None
    assert diagnosis.fringe_share is None


def test_a_route_without_edges_is_refused() -> None:
    with pytest.raises(DemandDiagnosisError, match="declares no edges"):
        _diagnose(routes=[PoolRoute(route_id="r0", edge_ids=())])


def test_summarise_is_deterministic_and_order_independent() -> None:
    ascending = summarise([1.0, 2.0, 3.0, 4.0])
    descending = summarise([4.0, 3.0, 2.0, 1.0])

    assert ascending.model_dump() == descending.model_dump()
    assert ascending.p50 == pytest.approx(2.5)


def test_the_artifact_cannot_carry_a_verdict_or_a_threshold() -> None:
    diagnosis = _diagnose()

    assert diagnosis.purpose == "measurements_only"
    assert diagnosis.viability_verdict_included is False
    assert diagnosis.threshold_applied is False
    assert diagnosis.variant_selected is False
    assert diagnosis.research_status == "owner_approved_candidate"


def test_the_artifact_round_trips_through_canonical_json() -> None:
    diagnosis = _diagnose()

    restored = RoutePoolDiagnosis.model_validate_json(diagnosis.model_dump_json())

    assert restored == diagnosis
    assert restored.fingerprint() == diagnosis.fingerprint()


def test_markdown_publishes_the_measurements_and_refuses_a_verdict() -> None:
    rendered = render_diagnosis_markdown(_diagnose())

    assert "# Route-pool diagnosis — synthetic-pool" in rendered
    assert "`measurements_only`" in rendered
    assert "| Route length (km) | 3 |" in rendered
    assert "| Free-flow residence time (s) | 3 |" in rendered
    assert "| Counted-edge multiplicity | 2 |" in rendered
    assert "states no viability verdict" in rendered
    assert "selects no variant" in rendered
    # Deterministic: the same diagnosis always renders the same bytes.
    assert rendered == render_diagnosis_markdown(_diagnose())


def test_markdown_shows_unavailable_rather_than_a_placeholder_number() -> None:
    rendered = render_diagnosis_markdown(_diagnose(routes=[]))

    assert "| Route length (km) | 0 | unavailable |" in rendered
    assert "Fringe share: unavailable" in rendered


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_streaming_parser_reads_standalone_and_embedded_routes(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "pool.rou.xml",
        "<routes>\n"
        '  <route id="r0" edges="e1 e2"/>\n'
        '  <vehicle id="v1" depart="0.00">\n'
        '    <route edges="e2 e3"/>\n'
        "  </vehicle>\n"
        "</routes>\n",
    )

    routes = list(iter_route_pool(source))

    assert [route.route_id for route in routes] == ["r0", "v1"]
    assert routes[0].edge_ids == ("e1", "e2")
    assert routes[1].edge_ids == ("e2", "e3")


def test_streaming_parser_handles_an_attribute_split_across_lines(tmp_path: Path) -> None:
    # A line-by-line regex would drop this route entirely; the diagnosis would
    # then under-count without saying so, which is the failure this guards.
    source = _write(
        tmp_path / "pool.rou.xml",
        '<routes>\n  <route id="r0"\n         edges="e1 e2\n                e3"/>\n</routes>\n',
    )

    routes = list(iter_route_pool(source))

    assert len(routes) == 1
    assert routes[0].edge_ids == ("e1", "e2", "e3")


def test_streaming_parser_is_lazy_and_does_not_read_ahead(tmp_path: Path) -> None:
    # The second route is malformed. A parser that read the whole file up front
    # would raise before yielding anything; a streaming one yields the first
    # route first. This is what keeps a 1.28 GB pool affordable.
    source = _write(
        tmp_path / "pool.rou.xml",
        '<routes>\n  <route id="r0" edges="e1 e2"/>\n  <route id="r1" edges=""/>\n</routes>\n',
    )

    stream = iter_route_pool(source)
    first = next(stream)

    assert first.route_id == "r0"
    with pytest.raises(DemandDiagnosisError, match="declares no edges"):
        next(stream)


def test_streaming_parser_refuses_a_route_declaring_no_edges(tmp_path: Path) -> None:
    source = _write(tmp_path / "pool.rou.xml", '<routes>\n  <route id="r0" edges=""/>\n</routes>\n')

    with pytest.raises(DemandDiagnosisError, match="declares no edges"):
        list(iter_route_pool(source))


def test_streaming_parser_refuses_unparseable_xml(tmp_path: Path) -> None:
    source = _write(tmp_path / "pool.rou.xml", "<routes><route edges='e1'>\n")

    with pytest.raises(DemandDiagnosisError, match="not parseable XML"):
        list(iter_route_pool(source))


def test_streaming_parser_refuses_an_entity_expansion_attack(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "pool.rou.xml",
        '<?xml version="1.0"?>\n'
        "<!DOCTYPE routes [\n"
        '  <!ENTITY boom "e1 e1 e1 e1 e1 e1 e1 e1 e1 e1">\n'
        "]>\n"
        '<routes>\n  <route id="r0" edges="&boom;"/>\n</routes>\n',
    )

    with pytest.raises(DemandDiagnosisError, match="refused XML feature"):
        list(iter_route_pool(source))


def test_streaming_parser_refuses_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DemandDiagnosisError, match="no route file exists"):
        list(iter_route_pool(tmp_path / "absent.rou.xml"))


def test_parser_output_feeds_the_diagnosis_directly(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "pool.rou.xml",
        '<routes>\n  <route id="r0" edges="e1 e2 e3"/>\n  <route id="r1" edges="e2 e3"/>\n'
        '  <route id="r2" edges="e1 e4"/>\n</routes>\n',
    )

    streamed = diagnose_route_pool(
        iter_route_pool(source), _edges(), ["e2", "e4"], pool_label="synthetic-pool"
    )

    assert streamed == _diagnose()
