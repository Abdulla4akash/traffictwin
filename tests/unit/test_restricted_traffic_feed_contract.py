from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.integration.manchester.restricted_traffic_feed_contract import (
    ProviderContractAssessment,
    RestrictedFeedProduct,
    RestrictedTrafficFeedAccessContract,
    RestrictedTrafficFeedContractError,
    assess_restricted_feed_contract,
    load_restricted_feed_contract,
    restricted_feed_contract_template,
)

PRODUCTS: tuple[RestrictedFeedProduct, ...] = (
    "tfgm_scoot",
    "tfgm_utc",
    "tfgm_utmc",
    "tfgm_automatic_counter",
    "ntis_measured_traffic",
)
RUNNER = CliRunner()


def _ref(label: str) -> dict[str, str]:
    return {"reference_id": label}


def _accepted_payload(
    product: RestrictedFeedProduct = "tfgm_scoot",
    *,
    pricing: str = "free",
    budget: str = "not_required",
) -> dict[str, object]:
    template = restricted_feed_contract_template(product).model_dump(mode="json")
    template.update(
        {
            "contract_status": "reviewed_accepted",
            "access": {
                "availability": "available",
                "academic_eligibility": "eligible",
                "data_owner_contact": _ref("provider-data-owner-role"),
                "eligibility_conditions": None,
                "correct_contact_confirmed": "yes",
            },
            "delivery": {
                "modes": ["historical", "periodic_export"],
                "delivery_schedule_reference": _ref("delivery-schedule-v1"),
            },
            "commercial": {
                "pricing": pricing,
                "quotation_required": (
                    "yes" if pricing in {"paid", "bespoke_commercial"} else "no"
                ),
                "quotation_reference": (
                    _ref("academic-dataset-quotation-v1")
                    if pricing in {"paid", "bespoke_commercial"}
                    else None
                ),
                "budget_authority": budget,
                "spending_authority_created_by_contract": False,
            },
            "onboarding": {
                "application": "required",
                "account": "required",
                "credential": "required",
                "ip_allowlist": "not_required",
                "data_sharing_agreement": "required",
                "process_reference": _ref("academic-onboarding-v1"),
            },
            "request_limits": {
                "requests_per_minute": {"status": "limited", "value": 2},
                "concurrent_requests": {"status": "limited", "value": 1},
                "requests_per_day": {"status": "limited", "value": 100},
                "requests_per_month": {"status": "limited", "value": 1000},
                "page_size_rows": {"status": "limited", "value": 500},
                "export_volume_rows": {"status": "limited", "value": 10000},
                "backoff_rules": "documented",
                "limit_reference": _ref("provider-rate-card-v1"),
            },
            "rights": {
                "licence": "restricted",
                "licence_reference": _ref("academic-licence-v1"),
                "attribution": "required",
                "attribution_reference": _ref("attribution-rule-v1"),
                "retention": {"status": "fixed_days", "maximum_days": 365},
                "backup": "agreement_specific",
                "deletion": "required",
                "derived_academic_results": "permitted",
                "aggregate_publication": "permitted",
                "row_level_publication": "prohibited",
            },
            "detectors": {
                "retain_detector_identifiers": "agreement_specific",
                "retain_detector_locations": "agreement_specific",
                "reference_identifiers_in_research": "aggregate_only",
                "reference_locations_in_research": "aggregate_only",
            },
            "time": {
                "timestamp_field_reference": _ref("schema.timestamp-field"),
                "timezone": "UTC",
                "timezone_reference": _ref("schema.timestamp-utc"),
                "daylight_saving": "not_applicable",
                "interval_boundary": "start_inclusive",
                "revision_semantics": "versioned",
            },
            "sensitive_fields": {
                "handling": "exclusions_required",
                "excluded_field_references": [_ref("schema.security-field")],
                "public_output_treatment": "aggregate",
                "security_reference": _ref("public-output-security-v1"),
            },
            "technical": {
                "transport": "sftp_export",
                "endpoint_reference": _ref("provider-endpoint-role"),
                "schema_status": "exact_schema_received",
                "schema_reference": _ref("schema-v1"),
                "schema_sha256": "1" * 64,
                "sample_status": "received",
                "sample_sha256": "2" * 64,
                "coverage": "documented",
                "coverage_reference": _ref("network-coverage-v1"),
                "units": "documented",
                "units_reference": _ref("schema-units-v1"),
                "quality_flags": "documented",
                "quality_reference": _ref("schema-quality-v1"),
                "outage_behavior": "documented",
                "support_route": "documented",
                "change_notifications": "documented",
            },
            "evidence": {
                "provider_response_sha256": "3" * 64,
                "provider_response_received_at_utc": "2026-08-04T09:00:00Z",
                "provider_response_reference": _ref("provider-response-20260804"),
                "agreement_sha256": "4" * 64,
                "agreement_reference": _ref("agreement-v1"),
                "provider_prose_present": False,
                "credential_present": False,
                "private_path_present": False,
            },
            "reviewer": {
                "reviewer_name": "A. Researcher",
                "reviewer_role": "academic data-contract reviewer",
            },
            "reviewed_at_utc": "2026-08-04T10:00:00Z",
            "owner_decision_id": "decision-provider-20260804",
        }
    )
    return template


def _contract(payload: dict[str, object]) -> RestrictedTrafficFeedAccessContract:
    return RestrictedTrafficFeedAccessContract.model_validate_json(json.dumps(payload))


def test_every_product_template_is_independently_unknown_and_fail_closed() -> None:
    assessments = []
    for product in PRODUCTS:
        contract = restricted_feed_contract_template(product)
        assessment = assess_restricted_feed_contract(contract)
        assessments.append(assessment)
        assert contract.product == product
        assert assessment.readiness == "unavailable_awaiting_provider_contract"
        assert assessment.next_stage == "wait_for_provider_response"
        assert "PROVIDER_RESPONSE_REQUIRED" in assessment.blockers
        assert "TIME_DST_INTERVAL_REVISION_REQUIRED" in assessment.blockers
        assert assessment.source_adapter_available is False
        assert assessment.credentialed_probe_authorized is False
        assert assessment.source_fields_assumed is False
    assert [item.provider for item in assessments[:4]] == ["TfGM"] * 4
    assert assessments[4].provider == "National Highways NTIS"


def test_reviewed_complete_contract_still_stops_before_probe_or_adapter() -> None:
    contract = _contract(_accepted_payload())

    assessment = assess_restricted_feed_contract(contract)

    assert assessment.readiness == "contract_accepted_adapter_not_implemented"
    assert assessment.blockers == ()
    assert assessment.next_stage == "freeze_transport_then_authorize_minimum_probe"
    assert assessment.credentialed_probe_authorized is False
    assert assessment.source_adapter_available is False
    assert assessment.measured_traffic_available is False
    assert assessment.sibling_products_enabled is False
    assert assessment.provider_request_performed is False


def test_paid_or_bespoke_terms_create_quote_blocker_not_spending_authority() -> None:
    payload = _accepted_payload(pricing="paid", budget="required_unapproved")
    payload["contract_status"] = "provider_response_recorded"
    payload["reviewer"] = None
    payload["reviewed_at_utc"] = None
    payload["owner_decision_id"] = None
    commercial = dict(cast(dict[str, object], payload["commercial"]))
    commercial.update(
        {
            "quotation_required": "yes",
            "quotation_reference": _ref("quotation-v1"),
        }
    )
    payload["commercial"] = commercial
    contract = _contract(payload)

    assessment = assess_restricted_feed_contract(contract)

    assert assessment.readiness == "provider_response_under_review"
    assert assessment.quotation_decision_required is True
    assert "BUDGET_AUTHORITY_REQUIRED" in assessment.blockers
    assert assessment.spending_authority_created is False
    payload["contract_status"] = "reviewed_accepted"
    payload["reviewer"] = {
        "reviewer_name": "A. Researcher",
        "reviewer_role": "academic data-contract reviewer",
    }
    payload["reviewed_at_utc"] = "2026-08-04T10:00:00Z"
    payload["owner_decision_id"] = "decision-provider-20260804"
    with pytest.raises(ValidationError, match="unknown or blocked facts"):
        _contract(payload)


def test_paid_contract_cannot_bypass_quotation_decision() -> None:
    payload = _accepted_payload(pricing="paid", budget="approved")
    commercial = cast(dict[str, object], payload["commercial"])
    commercial["quotation_required"] = "no"
    commercial["quotation_reference"] = None

    with pytest.raises(ValidationError, match="requires a quotation decision"):
        RestrictedTrafficFeedAccessContract.model_validate(payload)


def test_unknown_time_detector_security_or_schema_cannot_be_accepted() -> None:
    for section in ("time", "detectors", "sensitive_fields", "technical"):
        payload = _accepted_payload()
        payload[section] = restricted_feed_contract_template("tfgm_scoot").model_dump(mode="json")[
            section
        ]
        with pytest.raises(ValidationError, match="unknown or blocked facts"):
            _contract(payload)


def test_ineligible_or_incomplete_known_terms_cannot_be_accepted() -> None:
    mutations: tuple[tuple[str, str, object], ...] = (
        ("access", "academic_eligibility", "ineligible"),
        ("access", "correct_contact_confirmed", "redirect_required"),
        ("delivery", "delivery_schedule_reference", None),
        ("commercial", "budget_authority", "unknown"),
        ("rights", "licence", "denied"),
        ("rights", "retention", {"status": "not_permitted", "maximum_days": None}),
        ("rights", "attribution_reference", None),
    )
    for section, field, value in mutations:
        payload = _accepted_payload()
        terms = cast(dict[str, object], payload[section])
        terms[field] = value
        with pytest.raises(ValidationError):
            _contract(payload)

    payload = _accepted_payload()
    access = cast(dict[str, object], payload["access"])
    access["academic_eligibility"] = "conditional"
    access["eligibility_conditions"] = None
    with pytest.raises(ValidationError, match="conditions reference"):
        _contract(payload)


def test_contract_refusal_never_enables_an_adapter() -> None:
    payload = restricted_feed_contract_template("ntis_measured_traffic").model_dump(mode="json")
    payload.update(
        {
            "contract_status": "reviewed_refused",
            "evidence": {
                "provider_response_sha256": "5" * 64,
                "provider_response_received_at_utc": "2026-08-04T09:00:00Z",
                "provider_response_reference": _ref("provider-response-refused"),
            },
            "reviewer": {
                "reviewer_name": "A. Researcher",
                "reviewer_role": "academic data-contract reviewer",
            },
            "reviewed_at_utc": "2026-08-04T10:00:00Z",
            "owner_decision_id": "decision-provider-refused",
        }
    )
    assessment = assess_restricted_feed_contract(_contract(payload))
    assert assessment.readiness == "provider_contract_refused"
    assert assessment.next_stage == "none"
    assert assessment.source_adapter_available is False


def test_one_product_contract_cannot_enable_a_sibling_product() -> None:
    scoot = assess_restricted_feed_contract(_contract(_accepted_payload("tfgm_scoot")))
    utc = assess_restricted_feed_contract(restricted_feed_contract_template("tfgm_utc"))

    assert scoot.product == "tfgm_scoot"
    assert scoot.readiness == "contract_accepted_adapter_not_implemented"
    assert utc.product == "tfgm_utc"
    assert utc.readiness == "unavailable_awaiting_provider_contract"
    assert scoot.sibling_products_enabled is False


def test_private_contract_loader_is_read_only_and_errors_are_path_safe(tmp_path: Path) -> None:
    target = tmp_path / "private-provider-contract.json"
    target.write_text(json.dumps(_accepted_payload()), encoding="utf-8")
    before = target.read_bytes()

    loaded = load_restricted_feed_contract(target)

    assert loaded.product == "tfgm_scoot"
    assert target.read_bytes() == before
    unsafe = tmp_path / "contract-link.json"
    unsafe.symlink_to(target)
    with pytest.raises(RestrictedTrafficFeedContractError) as raised:
        load_restricted_feed_contract(unsafe)
    assert raised.value.code == "PROVIDER_CONTRACT_MISSING"
    assert str(target) not in str(raised.value)
    assert str(unsafe) not in str(raised.value)


def test_extra_endpoint_credentials_or_provider_prose_fields_are_refused() -> None:
    payload = _accepted_payload()
    payload["api_key"] = "secret"
    with pytest.raises(ValidationError):
        _contract(payload)
    payload = _accepted_payload()
    evidence = dict(cast(dict[str, object], payload["evidence"]))
    evidence["provider_prose"] = "private email body"
    payload["evidence"] = evidence
    with pytest.raises(ValidationError):
        _contract(payload)


def test_assessment_json_is_safe_and_contains_no_private_response_material() -> None:
    contract = _contract(_accepted_payload())
    assessment: ProviderContractAssessment = assess_restricted_feed_contract(contract)
    rendered = assessment.model_dump_json()
    for forbidden in (
        "provider-response-20260804",
        "agreement-v1",
        "provider-endpoint-role",
        "schema.timestamp-field",
        "academic-licence-v1",
        "security-field",
    ):
        assert forbidden not in rendered


def test_cli_template_and_status_are_safe_read_only_surfaces(tmp_path: Path) -> None:
    template_result = RUNNER.invoke(
        app,
        [
            "integration",
            "manchester",
            "provider",
            "template",
            "tfgm_automatic_counter",
            "--format",
            "json",
        ],
    )
    assert template_result.exit_code == 0
    template = RestrictedTrafficFeedAccessContract.model_validate_json(template_result.stdout)
    assert template.product == "tfgm_automatic_counter"
    assert template.contract_status == "draft_unknown"

    target = tmp_path / "contract.json"
    target.write_text(json.dumps(_accepted_payload()), encoding="utf-8")
    before = target.read_bytes()
    status_result = RUNNER.invoke(
        app,
        [
            "integration",
            "manchester",
            "provider",
            "status",
            str(target),
            "--format",
            "json",
        ],
    )
    assert status_result.exit_code == 0
    status = ProviderContractAssessment.model_validate_json(status_result.stdout)
    assert status.readiness == "contract_accepted_adapter_not_implemented"
    assert status.source_adapter_available is False
    assert target.read_bytes() == before
    assert str(target) not in status_result.stdout
    assert "provider-response-20260804" not in status_result.stdout


def test_cli_rejects_unknown_product_without_creating_a_template() -> None:
    result = RUNNER.invoke(
        app,
        ["integration", "manchester", "provider", "template", "tfgm_everything"],
    )
    assert result.exit_code == 1
    assert "unsupported product" in result.stderr
