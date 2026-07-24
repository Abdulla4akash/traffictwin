"""Identifier-only Bee Network classification over accepted BODS observations.

The policy in this module is activated by one accepted private BODS snapshot
whose aggregate ``OperatorRef`` inventory verified five Gate-A candidate NOCs.
It never uses display names or geography as a membership predicate.  The sixth
candidate remains pending because it was not observed in the verification
snapshot, and every non-match remains explicitly accounted for.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, model_validator

from traffictwin.integration.manchester.bods import (
    BodsParseReport,
    FreshnessState,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel

BEE_NETWORK_SCOPE_SCHEMA_VERSION = "1.0"
BEE_NETWORK_SCOPE_METHOD_VERSION = "bee-network-operator-scope-1.0"
BEE_NETWORK_SCOPE_CAPABILITY_ID = "MAN-05"
BEE_NETWORK_POLICY_VERSION = "bee-network-operator-allowlist-v1-20260723"

_VERIFICATION_COMPLETED_AT_UTC = datetime(
    2026,
    7,
    23,
    22,
    39,
    8,
    884920,
    tzinfo=UTC,
)
_VERIFIED_OPERATOR_COUNTS = (
    ("BNDB", 92),
    ("BNFM", 32),
    ("BNGN", 340),
    ("BNML", 422),
    ("BNSM", 483),
)
_PENDING_OPERATOR_REFS = ("BNVB",)

BeeNetworkMembership = Literal[
    "bee_network_franchised",
    "non_franchised_or_unknown",
]


class BeeNetworkScopeError(RuntimeError):
    """Typed refusal for incompatible membership evidence."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BeeNetworkOperatorEvidence(ManchesterSnapshotModel):
    """One live-feed-verified operator reference and its aggregate count."""

    operator_ref: str = Field(pattern=r"^[A-Z0-9]{2,12}$")
    records_observed: int = Field(gt=0)


class BeeNetworkScopePolicy(ManchesterSnapshotModel):
    """Frozen local-only membership policy backed by aggregate live evidence."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["bee-network-operator-scope-1.0"] = "bee-network-operator-scope-1.0"
    policy_version: Literal["bee-network-operator-allowlist-v1-20260723"] = (
        "bee-network-operator-allowlist-v1-20260723"
    )
    identifier_field: Literal["OperatorRef"] = "OperatorRef"
    verification_snapshot_id: Literal["bods_siri_vm-20260723T223908Z-33e07061a500"] = (
        "bods_siri_vm-20260723T223908Z-33e07061a500"
    )
    verification_raw_fingerprint: Literal[
        "33e07061a500f19c1be5d1cd24f9094b12f0734b6b8edf74f0650c5a2cfed4f7"
    ] = "33e07061a500f19c1be5d1cd24f9094b12f0734b6b8edf74f0650c5a2cfed4f7"
    verification_parser_report_fingerprint: Literal[
        "9111421dec9e0c05662abf142d3ae0862a059e005387b30b1cc2973ff225f25c"
    ] = "9111421dec9e0c05662abf142d3ae0862a059e005387b30b1cc2973ff225f25c"
    verification_completed_at_utc: datetime = _VERIFICATION_COMPLETED_AT_UTC
    evidence_records_seen: Literal[1565] = 1565
    verified_operator_evidence: tuple[BeeNetworkOperatorEvidence, ...]
    pending_operator_refs: tuple[str, ...] = _PENDING_OPERATOR_REFS
    identifier_match_only: Literal[True] = True
    display_name_matching_allowed: Literal[False] = False
    geography_matching_allowed: Literal[False] = False
    reference_licence_status: Literal["unconfirmed_ga_bee_4"] = "unconfirmed_ga_bee_4"
    local_lookup_only: Literal[True] = True
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_policy(self) -> BeeNetworkScopePolicy:
        observed = tuple(
            (item.operator_ref, item.records_observed) for item in self.verified_operator_evidence
        )
        if observed != _VERIFIED_OPERATOR_COUNTS:
            raise ValueError("verified operator evidence must match the accepted aggregate probe")
        if self.pending_operator_refs != _PENDING_OPERATOR_REFS:
            raise ValueError("unobserved candidate operator references must remain pending")
        if self.verification_completed_at_utc != _VERIFICATION_COMPLETED_AT_UTC:
            raise ValueError("verification time must match the accepted BODS snapshot")
        if sum(count for _operator, count in observed) > self.evidence_records_seen:
            raise ValueError("verified operator counts cannot exceed the source denominator")
        return self

    @property
    def verified_operator_refs(self) -> tuple[str, ...]:
        return tuple(item.operator_ref for item in self.verified_operator_evidence)


class BeeNetworkVehicleClassification(ManchesterSnapshotModel):
    """One privacy-safe accepted BODS record classified by exact identifier."""

    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str
    vehicle_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    operator_ref: str = Field(min_length=1, max_length=100)
    line_ref: str = Field(min_length=1, max_length=200)
    freshness_state: FreshnessState
    membership: BeeNetworkMembership
    policy_version: Literal["bee-network-operator-allowlist-v1-20260723"] = (
        "bee-network-operator-allowlist-v1-20260723"
    )
    identifier_match_only: Literal[True] = True
    public_export_available: Literal[False] = False


class BeeNetworkMembershipCounts(ManchesterSnapshotModel):
    """Complete parser-to-membership reconciliation for one BODS report."""

    activities_seen: int = Field(ge=0)
    records_classified: int = Field(ge=0)
    bee_network_franchised: int = Field(ge=0)
    non_franchised_or_unknown: int = Field(ge=0)
    out_of_scope: int = Field(ge=0)
    missing_identifier: int = Field(ge=0)
    ambiguous_identifier: int = Field(ge=0)
    malformed_activity: int = Field(ge=0)
    duplicate_collapsed: int = Field(ge=0)
    conflicting_duplicates: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> BeeNetworkMembershipCounts:
        if self.records_classified != (
            self.bee_network_franchised + self.non_franchised_or_unknown
        ):
            raise ValueError("membership outcomes must partition classified records")
        if self.missing_identifier or self.ambiguous_identifier:
            raise ValueError("the strict BODS parser admits exactly one non-empty OperatorRef")
        if self.activities_seen != (
            self.records_classified
            + self.out_of_scope
            + self.malformed_activity
            + self.duplicate_collapsed
            + self.conflicting_duplicates
        ):
            raise ValueError("membership counts must reconcile every source activity")
        return self


class BeeNetworkMembershipReport(ManchesterSnapshotModel):
    """Deterministic membership projection over one accepted BODS parse report."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["bee-network-operator-scope-1.0"] = "bee-network-operator-scope-1.0"
    source_snapshot_id: str
    source_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy: BeeNetworkScopePolicy
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    counts: BeeNetworkMembershipCounts
    classifications: tuple[BeeNetworkVehicleClassification, ...]
    synthetic: bool
    bee_network_membership_available: Literal[True] = True
    candidate_operator_still_pending: Literal[True] = True
    display_name_matching_used: Literal[False] = False
    geography_matching_used: Literal[False] = False
    raw_vehicle_identifiers_in_output: Literal[False] = False
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> BeeNetworkMembershipReport:
        if self.policy_fingerprint != self.policy.fingerprint():
            raise ValueError("policy fingerprint must bind the embedded policy")
        if self.counts.records_classified != len(self.classifications):
            raise ValueError("classified record count must match the classifications")
        fingerprints = tuple(item.source_record_fingerprint for item in self.classifications)
        if fingerprints != tuple(sorted(fingerprints)) or len(set(fingerprints)) != len(
            fingerprints
        ):
            raise ValueError("classifications must have unique sorted source fingerprints")
        verified = set(self.policy.verified_operator_refs)
        for item in self.classifications:
            if item.source_snapshot_id != self.source_snapshot_id:
                raise ValueError("every classification must bind the source snapshot")
            expected: BeeNetworkMembership = (
                "bee_network_franchised"
                if item.operator_ref in verified
                else "non_franchised_or_unknown"
            )
            if item.membership != expected:
                raise ValueError("membership must be derived only from exact OperatorRef")
        observed_matched = sum(
            item.membership == "bee_network_franchised" for item in self.classifications
        )
        if observed_matched != self.counts.bee_network_franchised:
            raise ValueError("matched classification count must reconcile")
        return self


def bee_network_scope_policy_v1() -> BeeNetworkScopePolicy:
    """Return the immutable first live-feed-verified operator policy."""

    return BeeNetworkScopePolicy(
        verified_operator_evidence=tuple(
            BeeNetworkOperatorEvidence(operator_ref=operator_ref, records_observed=count)
            for operator_ref, count in _VERIFIED_OPERATOR_COUNTS
        )
    )


def classify_bee_network_membership(
    source_report: BodsParseReport,
    policy: BeeNetworkScopePolicy | None = None,
) -> BeeNetworkMembershipReport:
    """Classify every parser-admitted position using exact ``OperatorRef`` only."""

    selected_policy = bee_network_scope_policy_v1() if policy is None else policy
    verified = set(selected_policy.verified_operator_refs)
    classifications = tuple(
        sorted(
            (
                BeeNetworkVehicleClassification(
                    source_record_fingerprint=record.fingerprint(),
                    source_snapshot_id=source_report.source.snapshot_id,
                    vehicle_token=record.vehicle_token,
                    operator_ref=record.operator_ref,
                    line_ref=record.line_ref,
                    freshness_state=record.freshness_state,
                    membership=(
                        "bee_network_franchised"
                        if record.operator_ref in verified
                        else "non_franchised_or_unknown"
                    ),
                )
                for record in source_report.records
            ),
            key=lambda item: item.source_record_fingerprint,
        )
    )
    matched = sum(item.membership == "bee_network_franchised" for item in classifications)
    counts = BeeNetworkMembershipCounts(
        activities_seen=source_report.counts.activities_seen,
        records_classified=len(classifications),
        bee_network_franchised=matched,
        non_franchised_or_unknown=len(classifications) - matched,
        out_of_scope=source_report.counts.outside_bounds,
        missing_identifier=0,
        ambiguous_identifier=0,
        malformed_activity=source_report.counts.malformed,
        duplicate_collapsed=source_report.counts.duplicate_collapsed,
        conflicting_duplicates=source_report.counts.conflicting_duplicates,
    )
    return BeeNetworkMembershipReport(
        source_snapshot_id=source_report.source.snapshot_id,
        source_report_fingerprint=source_report.fingerprint(),
        policy=selected_policy,
        policy_fingerprint=selected_policy.fingerprint(),
        counts=counts,
        classifications=classifications,
        synthetic=source_report.source.synthetic,
    )


def verify_bee_network_membership_report(
    report: BeeNetworkMembershipReport,
    source_report: BodsParseReport,
) -> None:
    """Re-derive a persisted membership report against its exact source report."""

    if (
        report.source_snapshot_id != source_report.source.snapshot_id
        or report.source_report_fingerprint != source_report.fingerprint()
        or report.synthetic != source_report.source.synthetic
    ):
        raise BeeNetworkScopeError(
            "SOURCE_REPORT_MISMATCH",
            "membership evidence does not bind the supplied BODS report",
        )
    expected = classify_bee_network_membership(source_report, report.policy)
    if expected != report:
        raise BeeNetworkScopeError(
            "MEMBERSHIP_REPORT_MISMATCH",
            "membership evidence does not reproduce from the source report and policy",
        )
