"""Corridor network-build contract (platform slice 6, design §5 fixtures).

Offline only: no network, no osmium, no netconvert run. The properties
asserted are the reviewed design's provenance story — Manchester-literal
rejection, dated-extract pinning, checksum/licence drift, workspace
containment, bounded argv, measured extent/role classification, landmark
reconciliation, observation-empty labels, and deterministic receipts free of
private paths.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.integration.corridor_network import (
    EXCLUDED_CLAIMS,
    CorridorBuildReceipt,
    CorridorLandmark,
    CorridorNetworkError,
    CorridorScope,
    ExtractPin,
    NetworkStructure,
    assess_feasibility,
    canonical_network_identity,
    classify_extent,
    contained_destination,
    haversine_m,
    load_corridor_scope,
    netconvert_arguments,
    osmium_clip_arguments,
    receipt_to_json,
    verify_extract,
)

#: Mohakhali → Hazrat Shahjalal International Airport corridor fixture values.
_LANDMARKS = (
    CorridorLandmark(name="Mohakhali interchange", longitude=90.4009, latitude=23.7778),
    CorridorLandmark(name="Banani overpass", longitude=90.4010, latitude=23.7940),
    CorridorLandmark(name="Kurmitola area", longitude=90.4030, latitude=23.8220),
    CorridorLandmark(name="Airport terminal approach", longitude=90.4066, latitude=23.8430),
)


def _scope(**overrides: object) -> CorridorScope:
    payload: dict[str, object] = {
        "region": "Dhaka, Bangladesh",
        "corridor_name": "Dhaka-Airport road (Mohakhali to Hazrat Shahjalal International)",
        "min_longitude": 90.37,
        "min_latitude": 23.76,
        "max_longitude": 90.44,
        "max_latitude": 23.86,
        "landmarks": _LANDMARKS,
        "decided_by": "owner (decision worksheet pending)",
        "decision_provenance": "fixture scope for offline tests",
    }
    payload.update(overrides)
    return CorridorScope.model_validate(payload)


def _pin(**overrides: object) -> ExtractPin:
    payload: dict[str, object] = {
        "url": "https://download.geofabrik.de/asia/bangladesh-260801.osm.pbf",
        "reference_date": "2026-08-01",
        "byte_size": 5,
        "sha256": hashlib.sha256(b"bytes").hexdigest(),
        "provider_checksum": None,
        "retrieved_at_utc": "2026-08-01T21:00:00+00:00",
    }
    payload.update(overrides)
    return ExtractPin.model_validate(payload)


# --- scope schema and the false-provenance guard -----------------------------


def test_manchester_literals_are_refused_by_name() -> None:
    for poisoned in (
        {"region": "Greater-Manchester"},
        {"corridor_name": "gm-baseline corridor"},
        {"decision_provenance": "reuse local authority E08000003"},
        {"decided_by": "the Manchester binding"},
    ):
        with pytest.raises(ValidationError, match="false provenance"):
            _scope(**poisoned)


def test_scope_geometry_and_landmarks_are_validated() -> None:
    with pytest.raises(ValidationError, match="min_longitude < max_longitude"):
        _scope(min_longitude=91.0)
    with pytest.raises(ValidationError, match="outside the frozen corridor bbox"):
        _scope(max_latitude=23.80)
    with pytest.raises(ValidationError):
        _scope(landmarks=_LANDMARKS[:3])
    duplicated = (*_LANDMARKS[:3], _LANDMARKS[0])
    with pytest.raises(ValidationError, match="unique"):
        _scope(landmarks=duplicated)


def test_scope_loads_from_json_with_typed_refusals(tmp_path: Path) -> None:
    path = tmp_path / "scope.json"
    path.write_text(_scope().model_dump_json(), encoding="utf-8")
    loaded = load_corridor_scope(path)
    assert loaded.corridor_name.startswith("Dhaka-Airport road")
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"region": "Dhaka"}), encoding="utf-8")
    with pytest.raises(CorridorNetworkError) as excinfo:
        load_corridor_scope(broken)
    assert excinfo.value.code == "SCOPE_INVALID"


# --- the dated extract pin ---------------------------------------------------


def test_latest_redirects_and_licence_drift_are_refused() -> None:
    with pytest.raises(ValidationError, match="dated provider artifact"):
        _pin(url="https://download.geofabrik.de/asia/bangladesh-latest.osm.pbf")
    with pytest.raises(ValidationError):
        _pin(licence="CC-BY-4.0")
    with pytest.raises(ValidationError):
        _pin(attribution="data by someone")


def test_checksum_drift_refuses_on_size_and_digest(tmp_path: Path) -> None:
    extract = tmp_path / "bangladesh-260801.osm.pbf"
    extract.write_bytes(b"bytes")
    verify_extract(extract, _pin())
    with pytest.raises(CorridorNetworkError) as size_drift:
        verify_extract(extract, _pin(byte_size=99))
    assert size_drift.value.code == "EXTRACT_CHECKSUM_DRIFT"
    with pytest.raises(CorridorNetworkError) as digest_drift:
        verify_extract(extract, _pin(sha256="0" * 64))
    assert digest_drift.value.code == "EXTRACT_CHECKSUM_DRIFT"


# --- containment and bounded tools ------------------------------------------


def test_destinations_stay_inside_the_workspace(tmp_path: Path) -> None:
    destination = contained_destination(tmp_path, "staging/corridor.osm.pbf")
    assert destination.is_relative_to(tmp_path)
    for escape in ("../outside.pbf", "/etc/passwd", "a/../../outside"):
        with pytest.raises(CorridorNetworkError) as excinfo:
            contained_destination(tmp_path, escape)
        assert excinfo.value.code == "WORKSPACE_ESCAPE_REFUSED"


def test_tool_argv_is_bounded_and_shell_free(tmp_path: Path) -> None:
    scope = _scope()
    clip = osmium_clip_arguments(scope, tmp_path / "in.pbf", tmp_path / "out.pbf")
    assert clip[0] == "osmium"
    assert "--bbox" in clip
    assert "90.37,23.76,90.44,23.86" in clip
    build = netconvert_arguments(tmp_path / "in.osm", tmp_path / "net.xml")
    assert build[0] == "netconvert"
    assert all(isinstance(argument, str) for argument in clip + build)
    assert not any(";" in argument or "|" in argument for argument in clip + build)


# --- measured extent, landmarks, feasibility ---------------------------------


def _junction_grid() -> list[tuple[float, float]]:
    # A grid covering the whole corridor bbox, plus a junction ~50 m from each
    # landmark (a real corridor network has junctions at its landmarks).
    grid = [
        (90.36 + 0.01 * column, 23.75 + 0.01 * row) for column in range(10) for row in range(13)
    ]
    grid.extend((landmark.longitude + 0.0004, landmark.latitude) for landmark in _LANDMARKS)
    return grid


def test_extent_containment_and_landmarks_are_measured() -> None:
    extent = classify_extent(
        _scope(),
        proj_parameter="+proj=utm +zone=46 +ellps=WGS84 +datum=WGS84 +units=m +no_defs",
        net_offset="-500000.0,-2600000.0",
        conv_boundary="0.00,0.00,7000.00,11000.00",
        junctions_lonlat=_junction_grid(),
    )
    assert extent.requested_corridor_contained
    assert len(extent.landmark_reconciliation) == 4
    for row in extent.landmark_reconciliation:
        assert row.nearest_junction_distance_m < 1_500.0
    assert not assess_feasibility(
        NetworkStructure(
            edge_count_total=100,
            edge_count_internal=40,
            edge_count_real=60,
            junction_count=50,
            no_shape_edge_share=0.36,
        ),
        extent,
    )


def test_feasibility_gaps_are_typed_not_repaired() -> None:
    clipped = classify_extent(
        _scope(),
        proj_parameter="+proj=utm +zone=46",
        net_offset="0,0",
        conv_boundary="0,0,1,1",
        junctions_lonlat=[(90.40, 23.77), (90.401, 23.771)],
        landmark_tolerance_m=150.0,
    )
    assert not clipped.requested_corridor_contained
    gaps = assess_feasibility(
        NetworkStructure(
            edge_count_total=2,
            edge_count_internal=2,
            edge_count_real=0,
            junction_count=2,
            no_shape_edge_share=1.0,
        ),
        clipped,
    )
    assert any(gap.startswith("NETWORK_EMPTY") for gap in gaps)
    assert any(gap.startswith("CORRIDOR_NOT_CONTAINED") for gap in gaps)
    assert any(gap.startswith("LANDMARK_UNRECONCILED") for gap in gaps)
    with pytest.raises(CorridorNetworkError) as excinfo:
        classify_extent(
            _scope(),
            proj_parameter="+proj=utm +zone=46",
            net_offset="0,0",
            conv_boundary="0,0,1,1",
            junctions_lonlat=[],
        )
    assert excinfo.value.code == "NETWORK_EMPTY"


def test_haversine_is_sane_at_dhaka_latitudes() -> None:
    assert haversine_m(90.40, 23.78, 90.40, 23.78) == 0.0
    one_degree_north = haversine_m(90.40, 23.78, 90.40, 24.78)
    assert 110_000 < one_degree_north < 112_000


# --- the receipt -------------------------------------------------------------


def _receipt(**overrides: object) -> CorridorBuildReceipt:
    extent = classify_extent(
        _scope(),
        proj_parameter="+proj=utm +zone=46",
        net_offset="-500000.0,-2600000.0",
        conv_boundary="0,0,7000,11000",
        junctions_lonlat=_junction_grid(),
    )
    payload: dict[str, object] = {
        "scope": _scope(),
        "extract_pin": _pin(),
        "extract_verified": True,
        "source_sha256": "a" * 64,
        "derived_network_sha256": "b" * 64,
        "derived_canonical_identity": "c" * 64,
        "tool_versions": {"osmium": "1.16.0", "netconvert": "1.27.1"},
        "stage_durations_seconds": {"clip": 4.0, "decode": 2.0, "build": 30.0},
        "structure": NetworkStructure(
            edge_count_total=100,
            edge_count_internal=40,
            edge_count_real=60,
            junction_count=50,
            no_shape_edge_share=0.36,
        ),
        "extent": extent,
        "network_artifact_name": "dhaka-airport-corridor.net.xml",
        "feasibility_gaps": (),
        "accepted": True,
        "generated_at_utc": "2026-08-01T21:30:00+00:00",
    }
    payload.update(overrides)
    return CorridorBuildReceipt.model_validate(payload)


def test_receipt_is_observation_empty_and_claim_capped_by_type() -> None:
    receipt = _receipt()
    assert receipt.role == "corridor_network_candidate"
    assert receipt.observation_status == "unavailable"
    assert receipt.excluded_claims == EXCLUDED_CLAIMS
    assert receipt.attribution == "© OpenStreetMap contributors, ODbL 1.0"
    with pytest.raises(ValidationError):
        CorridorBuildReceipt.model_validate({**_receipt().model_dump(), "observation_status": "0"})
    with pytest.raises(ValidationError):
        CorridorBuildReceipt.model_validate({**_receipt().model_dump(), "role": "city_baseline"})


def test_receipt_refuses_identity_collisions_and_private_paths() -> None:
    with pytest.raises(ValidationError, match="identities must differ"):
        _receipt(derived_network_sha256="a" * 64)
    with pytest.raises(ValidationError, match="private absolute path"):
        _receipt(tool_versions={"osmium": "/Users/someone/bin/osmium 1.16"})
    with pytest.raises(ValidationError, match="never its absolute path"):
        _receipt(network_artifact_name="/absolute/net.xml")
    with pytest.raises(ValidationError, match="cannot carry feasibility gaps"):
        _receipt(feasibility_gaps=("NETWORK_EMPTY: fixture",), accepted=True)


def test_receipts_are_deterministic() -> None:
    assert receipt_to_json(_receipt()) == receipt_to_json(_receipt())


def test_canonical_identity_strips_comment_banners(tmp_path: Path) -> None:
    first = tmp_path / "first.net.xml"
    second = tmp_path / "second.net.xml"
    body = b'<net>\n<edge id="1"/>\n</net>\n'
    first.write_bytes(b"<!-- generated 2026-08-01 by /private/tool -->\n" + body)
    second.write_bytes(b"<!-- generated 2026-08-02 elsewhere -->\n" + body)
    assert canonical_network_identity(first) == canonical_network_identity(second)
    third = tmp_path / "third.net.xml"
    third.write_bytes(b'<!-- banner -->\n<net>\n<edge id="2"/>\n</net>\n')
    assert canonical_network_identity(first) != canonical_network_identity(third)


def test_the_module_is_disjoint_from_manchester_bindings() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "traffictwin"
        / "integration"
        / "corridor_network.py"
    ).read_text(encoding="utf-8")
    assert "from traffictwin.integration.manchester" not in source
    assert "import traffictwin.integration.manchester" not in source
