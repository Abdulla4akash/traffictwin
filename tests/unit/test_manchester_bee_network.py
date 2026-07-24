"""Deterministic tests for identifier-only Bee Network classification."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_bods import parse
from traffictwin.integration.manchester.bee_network import (
    BEE_NETWORK_POLICY_VERSION,
    BeeNetworkMembershipReport,
    BeeNetworkScopeError,
    bee_network_scope_policy_v1,
    classify_bee_network_membership,
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
