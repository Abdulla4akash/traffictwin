"""Deterministic source-policy evidence for the MAN-07 freshness service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.bods import bods_freshness_state
from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    FreshnessSource,
    SourceFreshnessEvaluation,
    evaluate_source_freshness,
    source_freshness_policy,
)
from traffictwin.integration.manchester.models import ManchesterValidationState

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def request(
    source: str,
    **changes: object,
) -> FreshnessEvaluationRequest:
    payload: dict[str, object] = {
        "source": source,
        "evidence_validation": ManchesterValidationState.ACCEPTED,
        "snapshot_available": True,
        "use_mode": "historical",
        "evaluated_at_utc": NOW,
        "synthetic": False,
    }
    payload.update(changes)
    return FreshnessEvaluationRequest.model_validate(payload)


def bods_request(**changes: object) -> FreshnessEvaluationRequest:
    payload: dict[str, object] = {
        "use_mode": "live",
        "observed_at_utc": NOW,
        "valid_until_utc": NOW + timedelta(seconds=90),
    }
    payload.update(changes)
    return request("bods_siri_vm", **payload)


def test_policy_matrix_refuses_retrieval_time_and_near_live_claims() -> None:
    sources: tuple[FreshnessSource, ...] = (
        "bods_siri_vm",
        "dft_raw_counts",
        "dft_count_points",
        "dft_aadf",
        "webtris_daily",
        "tfgm_signals",
        "randy_tos",
        "synthetic",
    )
    policies = [source_freshness_policy(source) for source in sources]

    assert all(policy.retrieval_time_can_upgrade_state is False for policy in policies)
    assert all("near_live" not in policy.eligible_truth_states for policy in policies)
    assert source_freshness_policy("bods_siri_vm").accepted_live_age_seconds == 60
    assert source_freshness_policy("dft_raw_counts").blockers == ("GA-DFT-1",)
    assert source_freshness_policy("webtris_daily").blockers == ("GA-WT-1",)


@pytest.mark.parametrize("age_seconds", [Decimal("0"), Decimal("60")])
def test_bods_live_window_is_inclusive(age_seconds: Decimal) -> None:
    evaluated = NOW + timedelta(seconds=float(age_seconds))
    result = evaluate_source_freshness(bods_request(evaluated_at_utc=evaluated))

    assert result.truth_state == "live_vehicle"
    assert result.reason == "bods_within_live_window"
    assert result.observation_age_seconds == age_seconds
    assert result.transit_live_available is True
    assert result.road_traffic_live_available is False
    assert result.retrieval_time_used is False


def test_bods_fraction_beyond_ceiling_is_stale_without_rounding() -> None:
    result = evaluate_source_freshness(
        bods_request(evaluated_at_utc=NOW + timedelta(seconds=60, microseconds=1))
    )

    assert result.truth_state == "stale"
    assert result.reason == "bods_observation_too_old"
    assert result.observation_age_seconds == Decimal("60.000001")


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"evaluated_at_utc": NOW - timedelta(microseconds=1)}, "bods_future_dated"),
        (
            {
                "valid_until_utc": NOW + timedelta(seconds=10),
                "evaluated_at_utc": NOW + timedelta(seconds=10, microseconds=1),
            },
            "bods_validity_expired",
        ),
    ],
)
def test_bods_future_and_expired_evidence_are_stale(
    changes: dict[str, object], reason: str
) -> None:
    result = evaluate_source_freshness(bods_request(**changes))

    assert result.truth_state == "stale"
    assert result.reason == reason
    assert result.transit_live_available is False


def test_offline_bods_replay_is_historical_even_when_recent() -> None:
    result = evaluate_source_freshness(bods_request(use_mode="offline_replay"))

    assert result.truth_state == "historical"
    assert result.reason == "offline_replay_is_historical"
    assert result.observation_age_seconds == Decimal("0")


def test_unified_bods_result_matches_existing_adapter_policy() -> None:
    recorded = NOW
    valid_until = NOW + timedelta(seconds=90)
    for mode in ("live", "offline_replay"):
        for offset in (-1, 0, 60, 61, 91):
            evaluated = NOW + timedelta(seconds=offset)
            expected = bods_freshness_state(
                recorded_at_utc=recorded,
                valid_until_utc=valid_until,
                evaluated_at_utc=evaluated,
                mode=mode,
                synthetic=False,
            )
            actual = evaluate_source_freshness(
                bods_request(use_mode=mode, evaluated_at_utc=evaluated)
            )
            assert actual.truth_state == expected


@pytest.mark.parametrize("source", ["dft_raw_counts", "dft_count_points", "dft_aadf"])
def test_dft_is_historical_and_cannot_be_promoted_by_live_mode(source: str) -> None:
    result = evaluate_source_freshness(request(source, use_mode="live"))

    assert result.truth_state == "historical"
    assert result.reason == "source_policy_is_historical"
    assert result.road_traffic_live_available is False


def test_webtris_is_historical_but_cached_outage_evidence_is_stale() -> None:
    normal = evaluate_source_freshness(request("webtris_daily", use_mode="live"))
    outage = evaluate_source_freshness(
        request(
            "webtris_daily",
            use_mode="live",
            service_state="forced_unavailable",
            service_notice_id="WEBTRIS-2026-OUTAGE",
            using_cached_snapshot=True,
        )
    )

    assert normal.truth_state == "historical"
    assert outage.truth_state == "stale"
    assert outage.reason == "cached_snapshot_during_service_outage"
    assert outage.service_override_applied is True


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("tfgm_signals", "static_reference_has_no_traffic_freshness"),
        ("randy_tos", "simulation_clock_has_no_wall_freshness"),
    ],
)
def test_reference_and_simulation_sources_are_not_wall_clock_freshness(
    source: str, reason: str
) -> None:
    result = evaluate_source_freshness(request(source))

    assert result.evaluation_status == "not_applicable"
    assert result.truth_state is None
    assert result.reason == reason


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"snapshot_available": False}, "accepted_snapshot_unavailable"),
        (
            {"evidence_validation": ManchesterValidationState.REJECTED},
            "evidence_validation_rejected",
        ),
    ],
)
def test_missing_or_rejected_evidence_is_unavailable(
    changes: dict[str, object], reason: str
) -> None:
    result = evaluate_source_freshness(request("dft_raw_counts", **changes))

    assert result.evaluation_status == "unavailable"
    assert result.truth_state == "unavailable"
    assert result.reason == reason


def test_forced_service_outage_without_cache_is_explicitly_unavailable() -> None:
    result = evaluate_source_freshness(
        request(
            "webtris_daily",
            service_state="forced_unavailable",
            service_notice_id="WEBTRIS-2026-OUTAGE",
        )
    )

    assert result.truth_state == "unavailable"
    assert result.reason == "service_notice_forced_unavailable"
    assert result.service_override_applied is True


def test_synthetic_input_stays_synthetic() -> None:
    result = evaluate_source_freshness(request("synthetic", synthetic=True, use_mode="live"))

    assert result.truth_state == "synthetic"
    assert result.reason == "synthetic_evidence"
    assert result.road_traffic_live_available is False


def test_missing_and_invalid_bods_source_times_fail_closed() -> None:
    missing = evaluate_source_freshness(request("bods_siri_vm", use_mode="live"))
    invalid = evaluate_source_freshness(bods_request(valid_until_utc=NOW - timedelta(seconds=1)))

    assert missing.truth_state == "unavailable"
    assert missing.reason == "source_timestamp_missing"
    assert invalid.truth_state == "unavailable"
    assert invalid.reason == "invalid_validity_window"


@pytest.mark.parametrize(
    "payload",
    [
        {"evaluated_at_utc": datetime(2026, 7, 22, 12, 0)},
        {"evaluated_at_utc": datetime(2026, 7, 22, 13, 0, tzinfo=timezone(timedelta(hours=1)))},
        {"observed_at_utc": NOW, "valid_until_utc": None},
    ],
)
def test_requests_refuse_ambiguous_or_incomplete_bods_times(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        request("bods_siri_vm", **payload)


def test_historical_sources_refuse_invented_utc_validity_fields() -> None:
    with pytest.raises(ValidationError, match="cannot receive fabricated"):
        request(
            "webtris_daily",
            observed_at_utc=NOW,
            valid_until_utc=NOW + timedelta(minutes=1),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"service_state": "forced_unavailable"},
        {"service_notice_id": "notice-without-override"},
        {
            "snapshot_available": False,
            "using_cached_snapshot": True,
        },
    ],
)
def test_service_override_metadata_must_be_internally_consistent(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        request("webtris_daily", **changes)


def test_output_schema_cannot_be_strengthened_into_road_live_evidence() -> None:
    live = evaluate_source_freshness(bods_request())
    payload = live.model_dump(mode="python")
    payload["road_traffic_live_available"] = True

    with pytest.raises(ValidationError):
        SourceFreshnessEvaluation.model_validate(payload)

    payload = live.model_dump(mode="python")
    payload["truth_state"] = "historical"
    payload["transit_live_available"] = False
    with pytest.raises(ValidationError, match="truth state must match"):
        SourceFreshnessEvaluation.model_validate(payload)

    payload = live.model_dump(mode="python")
    payload["policy_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError, match="policy fingerprint"):
        SourceFreshnessEvaluation.model_validate(payload)


def test_fingerprints_are_stable_and_sensitive_to_evaluation_instant() -> None:
    first = evaluate_source_freshness(bods_request())
    repeated = evaluate_source_freshness(bods_request())
    later = evaluate_source_freshness(bods_request(evaluated_at_utc=NOW + timedelta(seconds=1)))

    assert first.fingerprint() == repeated.fingerprint()
    assert first.request_fingerprint == repeated.request_fingerprint
    assert first.request_fingerprint != later.request_fingerprint
