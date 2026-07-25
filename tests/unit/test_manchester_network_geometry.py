"""Evidence for reading real directed edge geometry from a baseline network.

Fixtures are small synthetic networks so the suite runs offline; the values they
encode were measured on the accepted 1.25 GB Greater Manchester build.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.network_geometry import (
    MAX_LINE_BYTES,
    EdgeGeometrySummary,
    NetworkGeometryError,
    RealNetworkEdge,
    geometry_fingerprint,
    read_junction_coordinates,
    read_network_location,
    stream_raw_edges,
    summarise_edge_geometry,
    to_real_network_edge,
)

#: The accepted network's own projection, copied verbatim from its <location>.
PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
NET_OFFSET = "-517074.60,-5908760.37"


def _network(body: str, *, location: str | None = None) -> str:
    head = (
        location
        if location is not None
        else (
            f'  <location netOffset="{NET_OFFSET}" convBoundary="0.00,0.00,1000.00,1000.00" '
            f'origBoundary="-2.30,53.40,-2.20,53.50" projParameter="{PROJ}"/>'
        )
    )
    return f"<?xml version='1.0'?>\n<net>\n{head}\n{body}\n</net>\n"


def _write(tmp_path: Path, body: str, *, location: str | None = None) -> Path:
    target = tmp_path / "test.net.xml"
    target.write_text(_network(body, location=location), encoding="utf-8")
    return target


JUNCTIONS = (
    '  <junction id="J1" type="priority" x="31667.45" y="16671.27" incLanes="" intLanes=""/>\n'
    '  <junction id="J2" type="priority" x="31754.33" y="16753.35" incLanes="" intLanes=""/>'
)


class TestInternalEdgesAreExcluded:
    """1,301,793 of the network's 2,106,404 edges are junction-internal
    connectors. An observation can never legitimately be attributed to one."""

    def test_a_colon_prefixed_edge_is_excluded(self, tmp_path: Path) -> None:
        body = (
            f"{JUNCTIONS}\n"
            '  <edge id=":J1_0" function="internal">\n'
            '    <lane id=":J1_0_0" index="0" speed="10" length="5" shape="0,0 1,1"/>\n'
            "  </edge>\n"
            '  <edge id="E1" from="J1" to="J2" type="highway.primary" '
            'shape="31667.45,16671.27 31754.33,16753.35">\n'
            "  </edge>"
        )
        edges = list(stream_raw_edges(_write(tmp_path, body)))
        assert [edge[0] for edge in edges] == ["E1"]

    def test_a_function_internal_edge_is_excluded(self, tmp_path: Path) -> None:
        body = (
            f"{JUNCTIONS}\n"
            '  <edge id="NotColon" function="internal" from="J1" to="J2" '
            'shape="31667.45,16671.27 31754.33,16753.35">\n  </edge>'
        )
        assert list(stream_raw_edges(_write(tmp_path, body))) == []

    def test_internal_edges_are_counted_not_silently_dropped(self, tmp_path: Path) -> None:
        body = (
            f"{JUNCTIONS}\n"
            '  <edge id=":J1_0" function="internal">\n  </edge>\n'
            '  <edge id="E1" from="J1" to="J2" type="highway.primary" '
            'shape="31667.45,16671.27 31754.33,16753.35">\n  </edge>'
        )
        summary = summarise_edge_geometry(_write(tmp_path, body))
        assert summary.total_edge_elements == 2
        assert summary.internal_edges_excluded == 1
        assert summary.real_edges == 1


class TestGeometryProvenanceIsRecorded:
    """36% of real edges carry no shape. A straight line between two junctions
    is not the true road shape, and distance-based matching is sensitive to the
    difference, so the two sources are never conflated."""

    def test_an_explicit_shape_is_labelled_as_true_road_shape(self, tmp_path: Path) -> None:
        body = (
            f"{JUNCTIONS}\n"
            '  <edge id="E1" from="J1" to="J2" type="highway.primary" '
            'shape="31667.45,16671.27 31700.00,16700.00 31754.33,16753.35">\n  </edge>'
        )
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        assert edge.geometry_source == "explicit_edge_shape"
        assert edge.geometry_is_true_road_shape is True
        assert len(edge.shape) == 3

    def test_a_shapeless_edge_falls_back_to_its_junctions(self, tmp_path: Path) -> None:
        body = f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="J2" type="highway.primary">\n  </edge>'
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        assert edge.geometry_source == "junction_endpoints"
        assert edge.geometry_is_true_road_shape is False
        assert len(edge.shape) == 2

    def test_a_shapeless_edge_with_unknown_junctions_is_unresolvable(self, tmp_path: Path) -> None:
        body = (
            f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="MISSING" '
            'type="highway.primary">\n  </edge>'
        )
        summary = summarise_edge_geometry(_write(tmp_path, body))
        assert summary.real_edges == 1
        assert summary.edges_unresolvable == 1

    def test_a_forged_fidelity_claim_is_refused(self, tmp_path: Path) -> None:
        body = f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="J2" type="highway.primary">\n  </edge>'
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        payload: dict[str, Any] = json.loads(edge.canonical_json())
        payload["geometry_is_true_road_shape"] = True
        with pytest.raises(ValidationError, match="follow from the recorded geometry source"):
            RealNetworkEdge.model_validate_json(json.dumps(payload))

    def test_junction_derived_geometry_cannot_claim_extra_points(self, tmp_path: Path) -> None:
        body = (
            f"{JUNCTIONS}\n"
            '  <edge id="E1" from="J1" to="J2" type="highway.primary" '
            'shape="31667.45,16671.27 31700.00,16700.00 31754.33,16753.35">\n  </edge>'
        )
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        payload: dict[str, Any] = json.loads(edge.canonical_json())
        payload["geometry_source"] = "junction_endpoints"
        payload["geometry_is_true_road_shape"] = False
        with pytest.raises(ValidationError, match="exactly two endpoints"):
            RealNetworkEdge.model_validate_json(json.dumps(payload))


class TestRealGeometryIsNotSyntheticGeometry:
    def test_a_real_edge_is_fixed_non_synthetic(self, tmp_path: Path) -> None:
        body = f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="J2" type="highway.primary">\n  </edge>'
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        assert edge.synthetic is False
        assert edge.reviewed_for_matching is False
        assert edge.matched_to_observation is False

    def test_reading_geometry_never_claims_a_match(self, tmp_path: Path) -> None:
        body = f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="J2" type="highway.primary">\n  </edge>'
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        payload: dict[str, Any] = json.loads(edge.canonical_json())
        payload["matched_to_observation"] = True
        with pytest.raises(ValidationError):
            RealNetworkEdge.model_validate_json(json.dumps(payload))


class TestRoadFeaturesAreReadNotJudged:
    def test_the_road_type_is_recorded_verbatim(self, tmp_path: Path) -> None:
        body = (
            f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="J2" type="highway.secondary">\n  </edge>'
        )
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        assert edge.road_type == "highway.secondary"

    def test_the_signed_road_number_is_read_from_its_param_child(self, tmp_path: Path) -> None:
        body = (
            f"{JUNCTIONS}\n"
            '  <edge id="E1" from="J1" to="J2" type="highway.secondary">\n'
            '    <lane id="E1_0" index="0" speed="13.41" length="21.27" shape="0,0 1,1"/>\n'
            '    <param key="ref" value="B5461"/>\n'
            "  </edge>"
        )
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        assert edge.road_ref == "B5461"

    def test_an_edge_without_a_ref_reports_none_rather_than_guessing(self, tmp_path: Path) -> None:
        body = (
            f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="J2" type="highway.residential">\n  </edge>'
        )
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        assert edge.road_ref is None

    def test_no_road_class_is_filtered_out(self, tmp_path: Path) -> None:
        # Which classes may carry a motor-traffic count is a scientific decision
        # (open question 6). The reader stays complete and neutral.
        body = f"{JUNCTIONS}\n" + "\n".join(
            f'  <edge id="E{index}" from="J1" to="J2" type="{road}">\n  </edge>'
            for index, road in enumerate(
                ("highway.footway", "highway.cycleway", "highway.motorway", "highway.service")
            )
        )
        observed = {edge[3] for edge in stream_raw_edges(_write(tmp_path, body))}
        assert observed == {
            "highway.footway",
            "highway.cycleway",
            "highway.motorway",
            "highway.service",
        }


class TestProjectionComesFromTheNetwork:
    def test_the_location_is_read_from_the_network(self, tmp_path: Path) -> None:
        body = f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="J2">\n  </edge>'
        location = read_network_location(_write(tmp_path, body))
        assert location.proj_parameter == PROJ
        assert location.net_offset == NET_OFFSET

    def test_a_network_without_a_location_is_refused(self, tmp_path: Path) -> None:
        target = tmp_path / "n.net.xml"
        target.write_text("<?xml version='1.0'?>\n<net>\n</net>\n", encoding="utf-8")
        with pytest.raises(NetworkGeometryError, match="NETWORK_LOCATION_UNREADABLE"):
            read_network_location(target)

    def test_an_incomplete_location_is_refused(self, tmp_path: Path) -> None:
        location = '  <location netOffset="0,0" projParameter="+proj=utm +zone=30"/>'
        path = _write(tmp_path, JUNCTIONS, location=location)
        with pytest.raises(NetworkGeometryError, match="NETWORK_LOCATION_INCOMPLETE"):
            read_network_location(path)

    def test_an_unreadable_offset_is_refused(self, tmp_path: Path) -> None:
        location = (
            '  <location netOffset="not-a-pair" convBoundary="0,0,1,1" '
            f'origBoundary="0,0,1,1" projParameter="{PROJ}"/>'
        )
        path = _write(tmp_path, JUNCTIONS, location=location)
        with pytest.raises(NetworkGeometryError, match="NETWORK_OFFSET_UNREADABLE"):
            list(stream_raw_edges(path))

    def test_an_uninterpretable_projection_is_refused(self, tmp_path: Path) -> None:
        location = (
            '  <location netOffset="0,0" convBoundary="0,0,1,1" '
            'origBoundary="0,0,1,1" projParameter="not a projection"/>'
        )
        path = _write(tmp_path, JUNCTIONS, location=location)
        with pytest.raises(NetworkGeometryError, match="NETWORK_PROJECTION_UNSUPPORTED"):
            list(stream_raw_edges(path))

    def test_the_offset_is_removed_rather_than_added(self, tmp_path: Path) -> None:
        # netconvert writes network = utm + netOffset, so the offset is removed
        # before projecting back. The wrong sign puts the network thousands of
        # kilometres away, which is silent rather than loud.
        body = (
            f"{JUNCTIONS}\n"
            '  <edge id="E1" from="J1" to="J2" type="highway.primary" '
            'shape="31667.45,16671.27 31754.33,16753.35">\n  </edge>'
        )
        edge = to_real_network_edge(next(iter(stream_raw_edges(_write(tmp_path, body)))))
        first = edge.shape[0]
        assert -2.4 < float(first.longitude) < -2.0, "should land in Greater Manchester"
        assert 53.3 < float(first.latitude) < 53.7


class TestBoundedReading:
    def test_junctions_are_collected(self, tmp_path: Path) -> None:
        junctions = read_junction_coordinates(_write(tmp_path, JUNCTIONS))
        assert set(junctions) == {b"J1", b"J2"}
        assert junctions[b"J1"] == (31667.45, 16671.27)

    def test_an_implausibly_long_line_is_refused(self, tmp_path: Path) -> None:
        target = tmp_path / "long.net.xml"
        target.write_text("<net>\n" + "x" * (MAX_LINE_BYTES + 10) + "\n</net>\n", encoding="utf-8")
        with pytest.raises(NetworkGeometryError, match="NETWORK_LINE_UNBOUNDED"):
            read_junction_coordinates(target)

    def test_a_shape_beyond_the_bound_is_not_admitted(self, tmp_path: Path) -> None:
        huge = " ".join(f"{31667 + index}.0,{16671 + index}.0" for index in range(600))
        body = f'{JUNCTIONS}\n  <edge id="E1" from="J1" to="J2" shape="{huge}">\n  </edge>'
        assert list(stream_raw_edges(_write(tmp_path, body))) == []


class TestSummaryArithmetic:
    def test_counts_must_reconcile(self) -> None:
        with pytest.raises(ValidationError, match="account for every edge element"):
            EdgeGeometrySummary(
                total_edge_elements=10,
                internal_edges_excluded=2,
                real_edges=3,
                edges_with_explicit_shape=3,
                edges_from_junction_endpoints=0,
                edges_unresolvable=0,
                shape_points_total=6,
                max_shape_points=2,
                junctions_available=4,
            )

    def test_every_real_edge_must_be_accounted_for(self) -> None:
        with pytest.raises(ValidationError, match="resolved, derived, or counted unresolvable"):
            EdgeGeometrySummary(
                total_edge_elements=5,
                internal_edges_excluded=2,
                real_edges=3,
                edges_with_explicit_shape=1,
                edges_from_junction_endpoints=0,
                edges_unresolvable=0,
                shape_points_total=2,
                max_shape_points=2,
                junctions_available=4,
            )

    def test_the_fidelity_share_is_derived_not_stored(self, tmp_path: Path) -> None:
        body = (
            f"{JUNCTIONS}\n"
            '  <edge id="E1" from="J1" to="J2" shape="31667.45,16671.27 31754.33,16753.35">\n'
            "  </edge>\n"
            '  <edge id="E2" from="J1" to="J2">\n  </edge>'
        )
        summary = summarise_edge_geometry(_write(tmp_path, body))
        assert summary.edges_with_explicit_shape == 1
        assert summary.edges_from_junction_endpoints == 1
        assert summary.true_shape_fraction == pytest.approx(0.5)
        assert summary.fidelity_reported_separately is True


class TestGeometryBinding:
    def test_a_reading_is_bound_to_its_network_identity(self, tmp_path: Path) -> None:
        summary = summarise_edge_geometry(_write(tmp_path, JUNCTIONS))
        first = geometry_fingerprint(summary, "a" * 64)
        second = geometry_fingerprint(summary, "b" * 64)
        assert first != second, "the same counts from a different network must not collide"
        assert len(first) == 64
