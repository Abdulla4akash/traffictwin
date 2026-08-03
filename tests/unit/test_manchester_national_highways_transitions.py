from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from traffictwin.integration.manchester.national_highways import (
    NationalHighwaysEnvelope,
    NationalHighwaysParseCounts,
    NationalHighwaysParseReport,
    NationalHighwaysRecord,
)
from traffictwin.integration.manchester.national_highways_transitions import (
    NationalHighwaysAcceptedTransitionSnapshot,
    NationalHighwaysTransitionError,
    NationalHighwaysTransitionHistory,
    advance_transition_history,
    compare_national_highways_snapshots,
    public_transition_aggregate,
)

T0 = datetime(2026, 8, 3, 8, tzinfo=UTC)
T1 = T0 + timedelta(minutes=5)
ENVELOPE = NationalHighwaysEnvelope(
    min_longitude=Decimal("-2.6"),
    min_latitude=Decimal("53.3"),
    max_longitude=Decimal("-1.9"),
    max_latitude=Decimal("53.7"),
)


def _token(seed: str) -> str:
    return seed * 24


def _record(
    seed: str,
    *,
    fingerprint_seed: str | None = None,
    valid_until: datetime | None = None,
    road_name: str = "M60",
) -> NationalHighwaysRecord:
    return NationalHighwaysRecord(
        product="closures",
        source_id="national_highways_closures",
        record_token=_token(seed),
        source_record_fingerprint=(fingerprint_seed or seed) * 64,
        publication_time_utc=T0,
        valid_from_utc=T0 - timedelta(hours=1),
        valid_until_utc=valid_until,
        latitude=Decimal("53.5"),
        longitude=Decimal("-2.2"),
        source_geometry_point_count=1,
        source_geometry_sha256=seed * 64,
        location_description="Synthetic test location",
        road_name=road_name,
        direction="clockwise",
        operational_type="roadClosed",
        synthetic=True,
    )


def _report(
    records: tuple[NationalHighwaysRecord, ...],
    *,
    publication: datetime,
    envelope: NationalHighwaysEnvelope = ENVELOPE,
) -> NationalHighwaysParseReport:
    ordered = tuple(sorted(records, key=lambda item: item.record_token))
    return NationalHighwaysParseReport(
        product="closures",
        source_id="national_highways_closures",
        raw_sha256=("a" if publication == T0 else "b") * 64,
        publication_time_utc=publication,
        feed_type="SituationPublication",
        model_base_version="3",
        envelope=envelope,
        envelope_fingerprint=envelope.fingerprint(),
        records=ordered,
        counts=NationalHighwaysParseCounts(
            source_items_seen=len(ordered),
            records_accepted=len(ordered),
            outside_envelope=0,
            coordinates_missing=0,
            exact_duplicates_collapsed=0,
        ),
        synthetic=True,
    )


def _snapshot(
    snapshot_id: str, report: NationalHighwaysParseReport
) -> NationalHighwaysAcceptedTransitionSnapshot:
    return NationalHighwaysAcceptedTransitionSnapshot(
        snapshot_id=snapshot_id,
        snapshot_receipt_fingerprint=("c" if report.publication_time_utc == T0 else "d") * 64,
        parser_report_fingerprint=report.fingerprint(),
        report=report,
    )


def test_all_six_states_reconcile_with_safe_wording_and_allowlisted_changes() -> None:
    unchanged = _record("1")
    changed_before = _record("2", fingerprint_seed="2", road_name="M60")
    changed_after = _record("2", fingerprint_seed="3", road_name="M62").model_copy(
        update={"publication_time_utc": T1}
    )
    no_longer = _record("4", valid_until=T1 + timedelta(hours=1))
    expired = _record("5", valid_until=T1)
    first_seen = _record("6").model_copy(update={"publication_time_utc": T1})
    reappeared = _record("7").model_copy(update={"publication_time_utc": T1})
    previous = _snapshot(
        "nh-prior",
        _report((unchanged, changed_before, no_longer, expired), publication=T0),
    )
    current = _snapshot(
        "nh-current",
        _report((unchanged, changed_after, first_seen, reappeared), publication=T1),
    )
    history = NationalHighwaysTransitionHistory(
        product="closures",
        seen_record_tokens=(_token("7"),),
        through_snapshot_id="nh-before-prior",
        through_publication_time_utc=T0 - timedelta(minutes=5),
    )

    report = compare_national_highways_snapshots(previous, current, history=history)

    assert report.counts.model_dump() == {
        "first_seen": 1,
        "content_changed": 1,
        "unchanged": 1,
        "no_longer_listed": 1,
        "validity_expired": 1,
        "reappeared": 1,
        "total": 6,
    }
    by_state = {item.state: item for item in report.transitions}
    assert by_state["content_changed"].changed_fields == ("road_name",)
    assert by_state["no_longer_listed"].wording == ("No longer listed in the latest accepted feed")
    assert "cleared" not in report.canonical_json().lower()
    assert report.measured_speed_available is False
    assert report.literal_display_text_present is False


def test_order_independence_and_opaque_history_advance() -> None:
    first = _record("1")
    second = _record("2")
    previous = _snapshot("nh-prior", _report((second, first), publication=T0))
    current = _snapshot("nh-current", _report((first, second), publication=T1))

    report = compare_national_highways_snapshots(previous, current)
    history = advance_transition_history(current)

    assert report.counts.unchanged == 2
    assert history.seen_record_tokens == (_token("1"), _token("2"))
    assert report.transitions == tuple(
        sorted(report.transitions, key=lambda item: item.record_token)
    )


def test_scope_time_product_and_history_mismatches_fail_closed() -> None:
    record = _record("1")
    previous = _snapshot("nh-prior", _report((record,), publication=T0))
    same_time = _snapshot("nh-current", _report((record,), publication=T0))
    other_envelope = NationalHighwaysEnvelope(
        min_longitude=Decimal("-2.5"),
        min_latitude=Decimal("53.3"),
        max_longitude=Decimal("-1.9"),
        max_latitude=Decimal("53.7"),
    )
    changed_scope = _snapshot(
        "nh-current",
        _report((record,), publication=T1, envelope=other_envelope),
    )

    with pytest.raises(NationalHighwaysTransitionError, match="TIME_NOT_INCREASING"):
        compare_national_highways_snapshots(previous, same_time)
    with pytest.raises(NationalHighwaysTransitionError, match="SCOPE_CONTRACT_MISMATCH"):
        compare_national_highways_snapshots(previous, changed_scope)
    wrong_history = NationalHighwaysTransitionHistory(product="vms", seen_record_tokens=())
    valid_current = _snapshot("nh-current", _report((record,), publication=T1))
    with pytest.raises(NationalHighwaysTransitionError, match="HISTORY_PRODUCT_MISMATCH"):
        compare_national_highways_snapshots(previous, valid_current, history=wrong_history)


def test_changed_source_fingerprint_without_projected_change_is_explicit() -> None:
    before = _record("1", fingerprint_seed="1")
    after = before.model_copy(
        update={"source_record_fingerprint": "2" * 64, "publication_time_utc": T1}
    )
    report = compare_national_highways_snapshots(
        _snapshot("nh-prior", _report((before,), publication=T0)),
        _snapshot("nh-current", _report((after,), publication=T1)),
    )
    assert report.transitions[0].changed_fields == ("unprojected_source_content",)


def test_public_projection_removes_tokens_locations_and_row_level_claims() -> None:
    before = _record("1")
    report = compare_national_highways_snapshots(
        _snapshot("nh-prior", _report((before,), publication=T0)),
        _snapshot("nh-current", _report((), publication=T1)),
    )

    public = public_transition_aggregate(report)

    assert public.counts.no_longer_listed == 1
    assert public.opaque_tokens_present is False
    assert public.locations_present is False
    assert public.public_release_approved is False
    assert _token("1") not in public.canonical_json()
