"""Tests for the synthetic MAN-09 map-match review UI service."""

from __future__ import annotations

import pytest

from traffictwin.integration.manchester.map_matching import ManchesterMapMatchingError
from traffictwin.ui.map_match_review import (
    REJECT_ALL_SENTINEL,
    candidate_display_rows,
    eligible_candidates_by_point,
    map_match_preflight_for_ui,
    review_from_selections,
    synthetic_map_match_demo_report,
)


def test_demo_report_is_deterministic_and_clearly_synthetic() -> None:
    report = synthetic_map_match_demo_report()

    assert report.fingerprint() == synthetic_map_match_demo_report().fingerprint()
    assert report.request.synthetic is True
    assert report.request.network.reviewed_manchester_network is False
    assert report.manual_review_required is True
    assert report.automatic_selection_performed is False
    assert report.real_manchester_matching_available is False
    assert report.sumo_baseline_available is False
    assert report.counts.candidate_pairs_evaluated == 9


def test_demo_covers_clear_ambiguous_and_no_candidate_situations() -> None:
    eligible = eligible_candidates_by_point(synthetic_map_match_demo_report())

    assert len(eligible["synthetic:obs-clear"]) == 1
    assert len(eligible["synthetic:obs-ambiguous"]) == 2
    assert eligible["synthetic:obs-distant"] == []


def test_review_derives_rejection_reasons_from_the_report() -> None:
    report = synthetic_map_match_demo_report()
    eligible = eligible_candidates_by_point(report)
    review = review_from_selections(
        report,
        {
            "synthetic:obs-clear": eligible["synthetic:obs-clear"][0].fingerprint(),
            "synthetic:obs-ambiguous": REJECT_ALL_SENTINEL,
            "synthetic:obs-distant": REJECT_ALL_SENTINEL,
        },
    )

    assert review.candidates_selected == 1
    assert review.observations_rejected == 2
    reasons = {decision.point_id: decision.reason for decision in review.decisions}
    assert reasons["synthetic:obs-clear"] == "SYNTHETIC_FIXTURE_SELECTION"
    assert reasons["synthetic:obs-ambiguous"] == "AMBIGUOUS_CANDIDATES"
    assert reasons["synthetic:obs-distant"] == "NO_SUITABLE_CANDIDATE"
    assert review.accepted_real_map_match is False
    assert review.sumo_baseline_available is False
    assert review.calibration_available is False


def test_review_refuses_a_candidate_from_another_observation() -> None:
    report = synthetic_map_match_demo_report()
    eligible = eligible_candidates_by_point(report)
    wrong = eligible["synthetic:obs-ambiguous"][0].fingerprint()

    with pytest.raises(ManchesterMapMatchingError, match="UNKNOWN_CANDIDATE"):
        review_from_selections(
            report,
            {
                "synthetic:obs-clear": wrong,
                "synthetic:obs-ambiguous": REJECT_ALL_SENTINEL,
                "synthetic:obs-distant": REJECT_ALL_SENTINEL,
            },
        )


def test_display_rows_keep_complete_reconciliation_visible() -> None:
    report = synthetic_map_match_demo_report()
    rows = candidate_display_rows(report)

    assert len(rows) == 9
    assert {row["observation"] for row in rows} == {
        "synthetic:obs-clear",
        "synthetic:obs-ambiguous",
        "synthetic:obs-distant",
    }
    assert any(row["eligible"] is False for row in rows)


def test_preflight_keeps_every_real_blocker() -> None:
    preflight = map_match_preflight_for_ui()

    assert preflight.status == "unavailable"
    assert preflight.synthetic_harness_available is True
    assert preflight.real_candidate_generation_available is False
    assert "MANCHESTER_NETWORK_LICENCE_UNAPPROVED" in preflight.blockers
