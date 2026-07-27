"""Privacy and cadence tests for session-scoped bus identity (decision F0)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from traffictwin.integration.manchester.bods_session_identity import (
    BodsSessionIdentityError,
    extract_session_observations,
    extract_session_observations_from_member,
    measure_session_cadence,
    measurement_to_json,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "manchester" / "bods" / "siri-vm-synthetic.xml"
SALT = b"unit-test-session-salt-32-bytes!"


def _member(*, recorded_shift_s: int = 0, lon_shift: str = "0.0000") -> bytes:
    """Return the synthetic SIRI member, optionally advanced in time and space."""

    text = FIXTURE.read_text(encoding="utf-8")
    if recorded_shift_s:
        for base in (datetime(2026, 7, 22, 12, 0, 0), datetime(2026, 7, 22, 11, 59, 50)):
            shifted = (base + timedelta(seconds=recorded_shift_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
            original = base.strftime("%Y-%m-%dT%H:%M:%SZ")
            text = text.replace(
                f"<RecordedAtTime>{original}</RecordedAtTime>",
                f"<RecordedAtTime>{shifted}</RecordedAtTime>",
            )
    if lon_shift != "0.0000":
        text = text.replace(
            "<Longitude>-2.2400</Longitude>", f"<Longitude>-2.{lon_shift}</Longitude>"
        )
    return text.encode("utf-8")


def test_same_vehicle_links_across_snapshots_and_raw_refs_never_leak() -> None:
    first = extract_session_observations_from_member(
        _member(), snapshot_id="snap-a", session_salt=SALT
    )
    second = extract_session_observations_from_member(
        _member(recorded_shift_s=60, lon_shift="2380"),
        snapshot_id="snap-b",
        session_salt=SALT,
    )

    assert first.activities_seen == 2
    assert first.observations_extracted == 2
    tokens_first = {obs.session_token for obs in first.observations}
    tokens_second = {obs.session_token for obs in second.observations}
    assert tokens_first == tokens_second, "the same vehicles must link within one session"

    for result in (first, second):
        rendered = result.canonical_json()
        assert "synthetic-vehicle-alpha" not in rendered
        assert "synthetic-vehicle-beta" not in rendered
    assert all(obs.raw_reference_available is False for obs in first.observations)


def test_a_different_session_salt_breaks_linkage_by_construction() -> None:
    one = extract_session_observations_from_member(
        _member(), snapshot_id="snap-a", session_salt=SALT
    )
    other = extract_session_observations_from_member(
        _member(), snapshot_id="snap-a", session_salt=secrets.token_bytes(32)
    )
    assert {o.session_token for o in one.observations}.isdisjoint(
        {o.session_token for o in other.observations}
    )


def test_short_salt_and_non_xml_members_refuse() -> None:
    with pytest.raises(BodsSessionIdentityError, match="SALT_TOO_SHORT"):
        extract_session_observations_from_member(
            _member(), snapshot_id="snap-a", session_salt=b"short"
        )
    with pytest.raises(BodsSessionIdentityError, match="MEMBER_NOT_XML"):
        extract_session_observations_from_member(
            b"not xml at all", snapshot_id="snap-a", session_salt=SALT
        )


def test_malformed_activities_are_counted_not_invented() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    mutilated = text.replace("<VehicleRef>synthetic-vehicle-alpha</VehicleRef>", "", 1).encode(
        "utf-8"
    )
    result = extract_session_observations_from_member(
        mutilated, snapshot_id="snap-a", session_salt=SALT
    )
    assert result.activities_seen == 2
    assert result.observations_extracted == 1
    assert result.malformed_skipped == 1


def test_cadence_measurement_is_aggregate_only_and_arithmetically_sound() -> None:
    results = [
        extract_session_observations_from_member(
            _member(), snapshot_id="snap-a", session_salt=SALT
        ),
        extract_session_observations_from_member(
            _member(recorded_shift_s=60, lon_shift="2380"),
            snapshot_id="snap-b",
            session_salt=SALT,
        ),
        extract_session_observations_from_member(
            _member(recorded_shift_s=120, lon_shift="2360"),
            snapshot_id="snap-c",
            session_salt=SALT,
        ),
    ]

    measurement = measure_session_cadence(results)

    assert measurement.snapshot_count == 3
    assert measurement.vehicles_seen_total == 2
    assert measurement.vehicles_linked_across_snapshots == 2
    assert measurement.observation_count == 6
    assert measurement.update_delta_seconds_median == 60.0
    assert measurement.update_delta_seconds_max == 60.0
    assert measurement.displacement_m_max is not None
    assert 100.0 < measurement.displacement_m_max < 300.0
    assert measurement.implied_speed_mps_max is not None
    assert measurement.implied_speed_mps_max < 5.0
    rendered = measurement_to_json(measurement)
    assert "synthetic-vehicle" not in rendered
    assert "session_token" not in rendered, "tokens must not appear in published aggregates"
    assert measurement.salt_persisted is False
    assert measurement.cross_session_linkable is False


def test_cadence_refuses_single_snapshot_and_duplicates() -> None:
    result = extract_session_observations_from_member(
        _member(), snapshot_id="snap-a", session_salt=SALT
    )
    with pytest.raises(BodsSessionIdentityError, match="SESSION_TOO_SHORT"):
        measure_session_cadence([result])
    with pytest.raises(BodsSessionIdentityError, match="DUPLICATE_SNAPSHOT"):
        measure_session_cadence([result, result])


def test_workspace_extraction_refuses_an_unverifiable_quarantine(tmp_path: Path) -> None:
    fake = tmp_path / "quarantine" / "bods_siri_vm-fake"
    fake.mkdir(parents=True)
    (fake / "member.xml").write_bytes(_member())
    with pytest.raises(Exception, match=r"(?i)snapshot_invalid|quarantine|receipt|manifest"):
        extract_session_observations(tmp_path, "bods_siri_vm-fake", session_salt=SALT)


def test_gzip_wire_members_decompress_after_hash_verification() -> None:
    import gzip

    compressed = gzip.compress(_member(), mtime=0)
    result = extract_session_observations_from_member(
        compressed, snapshot_id="snap-gz", session_salt=SALT
    )
    assert result.activities_seen == 2
    assert result.observations_extracted == 2


def test_progression_aggregates_by_hour_and_stays_bus_only() -> None:
    from traffictwin.integration.manchester.bods_session_identity import (
        measure_session_progression,
    )

    results = [
        extract_session_observations_from_member(
            _member(), snapshot_id="snap-a", session_salt=SALT
        ),
        extract_session_observations_from_member(
            _member(recorded_shift_s=60, lon_shift="2380"),
            snapshot_id="snap-b",
            session_salt=SALT,
        ),
    ]

    progression = measure_session_progression(results)

    assert progression.hour_utc == (12,) or progression.hour_utc == (11, 12)
    assert sum(progression.segment_count_by_hour) == 2
    # One vehicle moves and one dwells; a zero-speed segment is honest dwell,
    # not an error, so only the moving vehicle's bucket must be positive.
    assert any(speed > 0 for speed in progression.speed_mps_median_by_hour)
    assert progression.bus_progression_only is True
    assert progression.road_traffic_speed_available is False
    assert progression.dft_comparison_performed is False
    rendered = progression.canonical_json()
    assert "synthetic-vehicle" not in rendered
    assert "session_token" not in rendered


def test_progression_refuses_a_motionless_session() -> None:
    from traffictwin.integration.manchester.bods_session_identity import (
        measure_session_progression,
    )

    results = [
        extract_session_observations_from_member(
            _member(), snapshot_id="snap-a", session_salt=SALT
        ),
        extract_session_observations_from_member(
            _member(), snapshot_id="snap-b", session_salt=SALT
        ),
    ]
    with pytest.raises(BodsSessionIdentityError, match="NO_PROGRESSION"):
        measure_session_progression(results)
