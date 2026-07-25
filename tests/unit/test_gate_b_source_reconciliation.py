"""Gate-B reconciliation across the non-DfT Manchester sources.

Gate B asks for the eligible TfGM, WebTRIS, BODS and National Highways evidence
to be reconciled. Three blockers behind it are **external and unresolved**, and
the recorded source-documentation probe established that none of the official
pages answers them:

* `GA-DFT-1` — the DfT raw-count hour carries no stated timezone;
* `GA-WT-1` — WebTRIS clock semantics are unstated, and the feed runs a month in
  arrears, so near-live admission is rejected;
* BODS retention and republication terms are unstated.

None of those can be closed here. Closing one needs a provider reply, and an
invented reply would be worse than an open blocker. What these checks do instead
is pin the invariants each unresolved blocker implies, because those are exactly
what could regress silently: a source quietly promoted to near-live, a credential
quietly persisted, a retention default quietly appearing.

Automated candidate evidence only. It accepts no gate and closes no blocker.
"""

from __future__ import annotations

import typing

import pytest

from traffictwin.integration.manchester.freshness import (
    FreshnessSource,
    source_freshness_policy,
)

_ALL_SOURCES: tuple[FreshnessSource, ...] = typing.get_args(FreshnessSource)

#: Only the audited National Highways feeds may ever be near-live. Every other
#: source promoted into that state would be asserting a currency it cannot show.
_NEAR_LIVE_ELIGIBLE = frozenset(
    {
        "national_highways_closures",
        "national_highways_speed_limits",
        "national_highways_vms",
    }
)


class TestNearLiveStaysReservedToAuditedSources:
    @pytest.mark.parametrize("source", _ALL_SOURCES)
    def test_only_audited_national_highways_feeds_may_be_near_live(
        self, source: FreshnessSource
    ) -> None:
        states = source_freshness_policy(source).eligible_truth_states
        if source in _NEAR_LIVE_ELIGIBLE:
            assert "near_live" in states
        else:
            assert "near_live" not in states, f"{source} must not be eligible for near_live"

    def test_webtris_is_not_near_live_eligible(self) -> None:
        # GA-WT-1 is open and the feed runs a month in arrears, so the recorded
        # probe rejected near-live admission. That rejection lives here too.
        assert "near_live" not in source_freshness_policy("webtris_daily").eligible_truth_states

    def test_dft_is_historical_only_and_never_live(self) -> None:
        # DfT is an archive. A live state would misrepresent a survey from 2019
        # as current traffic.
        for source in ("dft_raw_counts", "dft_count_points", "dft_aadf"):
            states = source_freshness_policy(source).eligible_truth_states
            assert "near_live" not in states
            assert "live_vehicle" not in states
            assert "historical" in states


class TestSourcesWithoutAcceptedTermsStayUnavailable:
    def test_tfgm_signals_offer_no_real_state(self) -> None:
        # TfGM signal data has no accepted terms, so the only honest states are
        # unavailable and synthetic.
        states = source_freshness_policy("tfgm_signals").eligible_truth_states
        assert set(states) == {"unavailable", "synthetic"}

    def test_randy_tos_offers_no_real_state(self) -> None:
        states = source_freshness_policy("randy_tos").eligible_truth_states
        assert set(states) == {"unavailable", "synthetic"}

    @pytest.mark.parametrize("source", _ALL_SOURCES)
    def test_every_source_can_be_unavailable(self, source: FreshnessSource) -> None:
        # A source with no way to express unavailability would have to invent a
        # state when its evidence is missing.
        assert "unavailable" in source_freshness_policy(source).eligible_truth_states


class TestBodsLiveIsBoundedNotOpenEnded:
    def test_only_bods_may_claim_a_live_vehicle(self) -> None:
        for source in _ALL_SOURCES:
            states = source_freshness_policy(source).eligible_truth_states
            if source != "bods_siri_vm":
                assert "live_vehicle" not in states, (
                    f"{source} must not claim a live vehicle observation"
                )

    def test_bods_can_still_degrade_to_stale_and_unavailable(self) -> None:
        # A live source that cannot express staleness would present an old
        # position as current.
        states = source_freshness_policy("bods_siri_vm").eligible_truth_states
        assert {"stale", "unavailable"} <= set(states)


class TestTheUnresolvedBlockersAreRecordedNotClosed:
    """These blockers need a provider reply. Inventing one would be worse than
    leaving them open, so the checks assert only that they remain visible."""

    def test_the_source_documentation_probe_records_that_none_resolved(self) -> None:
        import json
        from pathlib import Path

        record = json.loads(
            Path("docs/integration/evidence/manchester_source_docs_probe_20260724.json").read_text(
                encoding="utf-8"
            )
        )
        assert record["capability_change"] == "none"
        conclusion = record["conclusion"].lower()
        assert "timezone" in conclusion
        assert "retention" in conclusion or "republication" in conclusion

    def test_the_webtris_probe_records_a_rejected_near_live_admission(self) -> None:
        import json
        from pathlib import Path

        record = json.loads(
            Path(
                "docs/integration/evidence/manchester_webtris_recency_probe_20260724.json"
            ).read_text(encoding="utf-8")
        )
        conclusion = record["conclusion"]
        assert conclusion["near_live_admission"] == "rejected"
        assert conclusion["capability_status_changed"] is False
        assert "GA-WT-1" in conclusion["near_live_reason_codes"]

    def test_the_national_highways_record_persists_no_credential(self) -> None:
        import json
        from pathlib import Path

        record = json.loads(
            Path(
                "docs/integration/evidence/national_highways_operational_acceptance_20260724.json"
            ).read_text(encoding="utf-8")
        )
        assert record["credential_persisted"] is False
        assert record["automatic_polling_performed"] is False
        assert record["accepted_private_raw_bytes_committed"] is False
