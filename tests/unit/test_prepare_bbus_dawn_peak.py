from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
from scripts.prepare_bbus_dawn_peak import (
    PROTOCOL_PATH,
    PROTOCOL_SHA256,
    SESSIONS,
    BBusPreparationError,
    RouteRequest,
    _assert_private_output,
    _lane_allows_bus,
    _new_private_output,
    _placement_preflight,
    _write_route_requests,
    bus_eligible_edge_ids,
)

from traffictwin.integration.manchester.bus_trace_campaign import ProjectedCandidate


def _candidate(edge_id: str) -> ProjectedCandidate:
    return ProjectedCandidate(
        edge_id=edge_id,
        edge_ordinal=0,
        geometry_source="explicit_edge_shape",
        snapped_x_m=0.0,
        snapped_y_m=0.0,
        distance_m=0.0,
        along_edge_m=0.0,
    )


def test_protocol_binding_and_exact_session_roles_are_frozen() -> None:
    assert hashlib.sha256(Path(PROTOCOL_PATH).read_bytes()).hexdigest() == PROTOCOL_SHA256
    assert tuple(spec.label for spec in SESSIONS) == ("dawn-20260728", "peak-20260728")
    assert all(spec.expected_snapshot_count == 52 for spec in SESSIONS)
    assert SESSIONS[0].end < SESSIONS[1].start


@pytest.mark.parametrize(
    ("allow", "disallow", "expected"),
    [
        ("bus taxi", None, True),
        ("passenger taxi", None, False),
        (None, "pedestrian bicycle", True),
        (None, "bus coach", False),
        (None, None, True),
        ("bus", "taxi", False),
    ],
)
def test_bus_lane_permission_is_explicit(
    allow: str | None, disallow: str | None, expected: bool
) -> None:
    assert _lane_allows_bus(allow, disallow) is expected


def test_bus_eligible_edge_reader_excludes_internal_and_non_bus_lanes(tmp_path: Path) -> None:
    network = tmp_path / "network.net.xml"
    network.write_text(
        """<net>
    <edge id="road-bus" from="a" to="b">
        <lane id="road-bus_0" allow="bus taxi"/>
    </edge>
    <edge id="road-car" from="b" to="c">
        <lane id="road-car_0" allow="passenger"/>
    </edge>
    <edge id=":internal" function="internal">
        <lane id=":internal_0" allow="bus"/>
    </edge>
</net>
""",
        encoding="utf-8",
    )

    assert bus_eligible_edge_ids(network) == frozenset({"road-bus"})


def test_route_request_xml_never_contains_the_session_token(tmp_path: Path) -> None:
    path = tmp_path / "requests.xml"
    request = RouteRequest(
        route_id="segment-0000000",
        vehicle_key="private-session-token",
        segment_index=0,
        start=_candidate("edge-a"),
        end=_candidate("edge-b"),
    )

    _write_route_requests(path, (request,))
    text = path.read_text(encoding="utf-8")

    assert "private-session-token" not in text
    assert 'id="segment-0000000"' in text
    assert 'from="edge-a"' in text
    assert 'to="edge-b"' in text


def test_output_is_new_only_and_confined_to_named_data_child(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    output = _new_private_output(tmp_path, Path("data/bbus-private"))
    assert output == (tmp_path / "data" / "bbus-private").resolve()

    with pytest.raises(BBusPreparationError, match="never overwritten"):
        _new_private_output(tmp_path, Path("data/bbus-private"))
    with pytest.raises(BBusPreparationError, match="named child"):
        _new_private_output(tmp_path, Path("outside"))


def test_placement_preflight_refuses_cell_overflow_without_generating_sites() -> None:
    count = 2_001
    pos_x = np.arange(count, dtype=np.float32)[None, :] * np.float32(50.0)
    pos_y = np.zeros((1, count), dtype=np.float32)
    mask = np.ones((1, count), dtype=bool)

    result = _placement_preflight(pos_x, pos_y, mask)

    assert result["status"] == "refused"
    assert result["refusal_code"] == "OCCUPIED_PLACEMENT_CELLS_EXCEEDED"
    assert result["placement_executed"] is False
    assert result["rsu_positions_generated"] is False


def test_private_text_scan_refuses_a_raw_identity_marker(tmp_path: Path) -> None:
    safe = tmp_path / "safe.json"
    safe.write_text('{"derived": true, "session_salt_persisted": false}\n', encoding="utf-8")
    _assert_private_output(safe)

    unsafe = tmp_path / "unsafe.json"
    unsafe.write_text('{"VehicleRef": "raw"}\n', encoding="utf-8")
    with pytest.raises(BBusPreparationError, match="forbidden raw-identity"):
        _assert_private_output(unsafe)
