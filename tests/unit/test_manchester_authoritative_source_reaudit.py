"""Integrity checks for the Phase-185 official-source contract re-audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RECORD = (
    ROOT
    / "docs"
    / "integration"
    / "evidence"
    / "manchester_authoritative_source_reaudit_20260802.json"
)
ALLOWED_HOSTS = {
    "www.gov.uk",
    "roadtraffic.dft.gov.uk",
    "storage.googleapis.com",
    "webtris.nationalhighways.co.uk",
}
PROVIDER_DRAFTS = ROOT / "docs" / "integration" / "provider_enquiry_drafts.md"
RETENTION_DESIGN = ROOT / "docs" / "integration" / "manchester_bods_retention.md"


def _record() -> dict[str, Any]:
    payload: object = json.loads(RECORD.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_every_source_is_official_https() -> None:
    sources = _record()["official_sources"]
    assert len(sources) == 7
    for source in sources:
        parsed = urlparse(source["url"])
        assert parsed.scheme == "https"
        assert parsed.hostname in ALLOWED_HOSTS
        assert source["finding"]


def test_dft_and_webtris_timezones_remain_fail_closed() -> None:
    record = _record()
    for key in ("dft_raw_count_hour", "webtris_report_time"):
        source = record[key]
        assert source["status"] == "open_official_sources_silent"
        assert source["timezone_documented"] is False
        assert source["utc_projection_permitted"] is False
    assert record["webtris_report_time"]["near_live_permitted"] is False


def test_bods_general_reuse_and_registration_are_documented() -> None:
    contract = _record()["bods_consumer_contract"]
    reuse = contract["general_reuse_and_publication"]
    registration = contract["api_registration"]
    assert reuse["status"] == "documented"
    for right in ("copy", "adapt", "publish", "distribute", "transmit"):
        assert reuse[right] is True
    assert registration["account_required_for_api"] is True
    assert registration["email_required"] is True
    assert registration["ga_bods_6_closed"] is True


def test_bods_retention_and_identifier_residuals_are_not_invented() -> None:
    retention = _record()["bods_consumer_contract"]["source_specific_retention"]
    assert retention["retention_duration_documented"] is False
    assert retention["consumer_retention_cap_found"] is False
    assert retention["vehicleref_same_day_consistency_documented"] is True
    assert retention["vehicleref_multi_day_persistence_documented"] is False


def test_phase_created_no_external_or_release_authority() -> None:
    disposition = _record()["traffictwin_disposition"]
    assert disposition["generic_bods_source_reuse_blocker_closed"] is True
    assert disposition["generic_bods_api_registration_fact_closed"] is True
    assert disposition["precautionary_private_retention_remains"] is True
    assert disposition["identifier_redaction_remains"] is True
    for field in (
        "longitudinal_trace_privacy_approved",
        "public_row_level_positions_approved",
        "public_identifier_export_approved",
        "complete_bee_membership_accepted",
        "provider_contacted",
        "operational_data_fetched",
        "capability_accepted",
    ):
        assert disposition[field] is False


def test_provider_and_retention_docs_preserve_the_narrowed_residual() -> None:
    drafts = PROVIDER_DRAFTS.read_text(encoding="utf-8")
    retention = RETENTION_DESIGN.read_text(encoding="utf-8")
    assert "closes the generic BODS reuse/publication and API-registration facts" in drafts
    assert "Multi-day `VehicleRef` persistence" in drafts
    assert "not presented as a BODS licence ban or an official 24-hour rule" in retention
    assert "project privacy/data-management approval" in retention
