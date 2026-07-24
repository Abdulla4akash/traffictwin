"""Deterministic tests for identifier-only Bee Network classification."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_bods import parse
from traffictwin.integration.manchester.bee_network import (
    BEE_NETWORK_POLICY_VERSION,
    BeeNetworkCandidateReview,
    BeeNetworkMembershipReport,
    BeeNetworkScopeError,
    bee_network_scope_policy_v1,
    classify_bee_network_membership,
    review_pending_bee_network_operators,
    verify_bee_network_candidate_review,
    verify_bee_network_membership_report,
)


def test_policy_contains_only_live_verified_operator_refs() -> None:
    policy = bee_network_scope_policy_v1()

    assert policy.policy_version == BEE_NETWORK_POLICY_VERSION
    assert policy.verified_operator_refs == ("BNDB", "BNFM", "BNGN", "BNML", "BNSM")
    assert policy.pending_operator_refs == ("BNVB",)
    assert sum(item.records_observed for item in policy.verified_operator_evidence) == 1369
    assert policy.evidence_records_seen == 1565
    assert policy.display_name_matching_allowed is False
    assert policy.geography_matching_allowed is False
    assert policy.local_lookup_only is True
    assert policy.public_export_available is False


def test_exact_operator_ref_classifies_every_admitted_record() -> None:
    source = parse()

    report = classify_bee_network_membership(source)

    assert report.counts.activities_seen == 2
    assert report.counts.records_classified == 2
    assert report.counts.bee_network_franchised == 1
    assert report.counts.non_franchised_or_unknown == 1
    assert report.counts.out_of_scope == 0
    assert report.counts.missing_identifier == 0
    assert report.counts.ambiguous_identifier == 0
    assert report.raw_vehicle_identifiers_in_output is False
    assert report.public_export_available is False
    by_operator = {item.operator_ref: item for item in report.classifications}
    assert by_operator["BNSM"].membership == "bee_network_franchised"
    assert by_operator["SYN1"].membership == "non_franchised_or_unknown"
    assert all(item.policy_version == BEE_NETWORK_POLICY_VERSION for item in report.classifications)

    # Classification is additive: the original parser record remains explicitly unverified.
    assert all(record.bee_network_membership == "unverified" for record in source.records)
    assert all(record.bee_network_membership_available is False for record in source.records)


def test_display_name_and_pending_candidate_do_not_activate_membership() -> None:
    source = parse()
    original = source.records[0]
    pending = original.model_copy(
        update={
            "operator_ref": "BNVB",
            "published_line_name": "Bee Network",
        }
    )
    unknown_with_branding = source.records[1].model_copy(
        update={
            "operator_ref": "OTHER",
            "published_line_name": "Bee Network branded text",
        }
    )
    modified = source.model_copy(update={"records": (pending, unknown_with_branding)})

    report = classify_bee_network_membership(modified)

    assert {item.membership for item in report.classifications} == {"non_franchised_or_unknown"}
    assert report.counts.bee_network_franchised == 0
    assert report.display_name_matching_used is False
    assert report.geography_matching_used is False


def test_membership_output_is_input_order_invariant_and_reproducible() -> None:
    source = parse()
    first = classify_bee_network_membership(source)
    repeated = classify_bee_network_membership(source)
    reordered = source.model_copy(update={"records": tuple(reversed(source.records))})
    reordered_result = classify_bee_network_membership(reordered)

    assert first == repeated
    assert first.classifications == reordered_result.classifications
    verify_bee_network_membership_report(first, source)


def test_report_reload_rejects_membership_and_policy_mutations() -> None:
    source = parse()
    report = classify_bee_network_membership(source)
    payload = report.model_dump(mode="json")

    membership_mutation = deepcopy(payload)
    current = membership_mutation["classifications"][0]["membership"]
    membership_mutation["classifications"][0]["membership"] = (
        "non_franchised_or_unknown"
        if current == "bee_network_franchised"
        else "bee_network_franchised"
    )
    with pytest.raises(ValidationError):
        BeeNetworkMembershipReport.model_validate(membership_mutation)

    policy_mutation = deepcopy(payload)
    policy_mutation["policy"]["pending_operator_refs"] = []
    with pytest.raises(ValidationError):
        BeeNetworkMembershipReport.model_validate(policy_mutation)

    fingerprint_mutation = deepcopy(payload)
    fingerprint_mutation["policy_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        BeeNetworkMembershipReport.model_validate(fingerprint_mutation)


def test_external_verifier_refuses_a_different_source_report() -> None:
    source = parse()
    report = classify_bee_network_membership(source)
    drifted = source.model_copy(
        update={"source": source.source.model_copy(update={"synthetic": False})}
    )

    with pytest.raises(BeeNetworkScopeError, match="SOURCE_REPORT_MISMATCH"):
        verify_bee_network_membership_report(report, drifted)


def test_pending_candidate_review_is_aggregate_only_and_does_not_activate_policy() -> None:
    source = parse()
    review = review_pending_bee_network_operators(source)

    assert review.candidate_evidence[0].operator_ref == "BNVB"
    assert review.candidate_evidence[0].records_observed == 0
    assert review.pending_candidates_observed == ()
    assert review.pending_candidates_unobserved == ("BNVB",)
    assert review.policy_update_required is False
    assert review.policy_activation_performed is False
    assert review.automatic_policy_activation_available is False
    assert review.complete_fleet_coverage_available is False
    assert review.complete_service_coverage_available is False
    assert review.raw_vehicle_identifiers_in_output is False
    assert review.public_export_available is False
    verify_bee_network_candidate_review(review, source)


def test_observed_pending_candidate_requests_review_but_remains_unclassified() -> None:
    source = parse()
    candidate = source.records[0].model_copy(update={"operator_ref": "BNVB"})
    modified = source.model_copy(update={"records": (candidate, *source.records[1:])})

    review = review_pending_bee_network_operators(modified)
    classification = classify_bee_network_membership(modified)

    assert review.pending_candidates_observed == ("BNVB",)
    assert review.pending_candidates_unobserved == ()
    assert review.candidate_evidence[0].records_observed == 1
    assert review.policy_update_required is True
    assert review.policy_activation_performed is False
    assert (
        next(
            item for item in classification.classifications if item.operator_ref == "BNVB"
        ).membership
        == "non_franchised_or_unknown"
    )


def test_candidate_review_reload_and_source_binding_fail_closed() -> None:
    source = parse()
    review = review_pending_bee_network_operators(source)
    payload = review.model_dump(mode="json")
    payload["complete_fleet_coverage_available"] = True
    with pytest.raises(ValidationError):
        BeeNetworkCandidateReview.model_validate(payload)

    drifted = source.model_copy(
        update={"source": source.source.model_copy(update={"synthetic": False})}
    )
    with pytest.raises(BeeNetworkScopeError, match="SOURCE_REPORT_MISMATCH"):
        verify_bee_network_candidate_review(review, drifted)
