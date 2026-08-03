"""Strict pre-adapter contract intake for provider-restricted measured traffic feeds.

No source field, endpoint, unit, quota, timezone or right is assumed here.  The
module records reviewed facts from a private provider response and reduces them
to a safe readiness state.  Even an accepted contract stops before a probe or
adapter: transport freezing, minimum-volume access and source-specific parsing
are later, separately authorised stages.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

RESTRICTED_FEED_CONTRACT_SCHEMA_VERSION: Literal["1.0"] = "1.0"
RESTRICTED_FEED_CONTRACT_METHOD_VERSION: Literal["restricted-traffic-feed-access-contract-1.0"] = (
    "restricted-traffic-feed-access-contract-1.0"
)
RESTRICTED_FEED_CONTRACT_MAX_BYTES = 2 * 1024 * 1024

RestrictedFeedProduct: TypeAlias = Literal[
    "tfgm_scoot",
    "tfgm_utc",
    "tfgm_utmc",
    "tfgm_automatic_counter",
    "ntis_measured_traffic",
]
ProviderFamily: TypeAlias = Literal["TfGM", "National Highways NTIS"]
KnownRequirement: TypeAlias = Literal["unknown", "not_required", "required"]
PermissionState: TypeAlias = Literal[
    "unknown", "permitted", "prohibited", "aggregate_only", "agreement_specific"
]
ContractReadiness: TypeAlias = Literal[
    "unavailable_awaiting_provider_contract",
    "provider_response_under_review",
    "provider_contract_refused",
    "contract_accepted_adapter_not_implemented",
]
ContractNextStage: TypeAlias = Literal[
    "wait_for_provider_response",
    "review_provider_response",
    "resolve_contract_blockers",
    "freeze_transport_then_authorize_minimum_probe",
    "none",
]

_PRODUCT_PROVIDER: dict[RestrictedFeedProduct, ProviderFamily] = {
    "tfgm_scoot": "TfGM",
    "tfgm_utc": "TfGM",
    "tfgm_utmc": "TfGM",
    "tfgm_automatic_counter": "TfGM",
    "ntis_measured_traffic": "National Highways NTIS",
}
RESTRICTED_FEED_PRODUCTS: tuple[RestrictedFeedProduct, ...] = tuple(_PRODUCT_PROVIDER)
_PLACEHOLDER_IDENTITIES = frozenset(
    {"tbd", "todo", "unknown", "agent", "anonymous", "none", "n/a", "na", "-", "_"}
)


class RestrictedTrafficFeedContractError(RuntimeError):
    """Display-safe contract intake failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class RestrictedFeedContractModel(ManchesterSnapshotModel):
    """Strict, frozen contract base."""


class SafeReference(RestrictedFeedContractModel):
    """Safe local citation handle; never provider prose, a URL, email or private path."""

    reference_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")


class ProviderResponseEvidence(RestrictedFeedContractModel):
    """Digest and date only; the private response/agreement stays outside the record."""

    provider_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_response_received_at_utc: datetime
    provider_response_reference: SafeReference
    agreement_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    agreement_reference: SafeReference | None = None
    provider_prose_present: Literal[False] = False
    credential_present: Literal[False] = False
    private_path_present: Literal[False] = False

    @model_validator(mode="after")
    def validate_evidence(self) -> ProviderResponseEvidence:
        _require_utc(self.provider_response_received_at_utc, "provider response time")
        if (self.agreement_sha256 is None) != (self.agreement_reference is None):
            raise ValueError("agreement digest and safe reference must be supplied together")
        return self


class ContractReviewer(RestrictedFeedContractModel):
    reviewer_name: str = Field(min_length=1, max_length=200)
    reviewer_role: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_reviewer(self) -> ContractReviewer:
        for value in (self.reviewer_name, self.reviewer_role):
            if not value.strip() or value.strip().casefold() in _PLACEHOLDER_IDENTITIES:
                raise ValueError("contract review requires a real named person and role")
        return self


class AcademicAccessTerms(RestrictedFeedContractModel):
    availability: Literal["unknown", "available", "unavailable"] = "unknown"
    academic_eligibility: Literal["unknown", "eligible", "ineligible", "conditional"] = "unknown"
    data_owner_contact: SafeReference | None = None
    eligibility_conditions: SafeReference | None = None
    correct_contact_confirmed: Literal["unknown", "yes", "redirect_required"] = "unknown"

    @model_validator(mode="after")
    def validate_access(self) -> AcademicAccessTerms:
        if self.academic_eligibility == "conditional" and self.eligibility_conditions is None:
            raise ValueError("conditional academic eligibility needs a safe conditions reference")
        return self


class DeliveryTerms(RestrictedFeedContractModel):
    modes: tuple[Literal["unknown", "live", "delayed", "historical", "periodic_export"], ...] = (
        "unknown",
    )
    delivery_schedule_reference: SafeReference | None = None

    @model_validator(mode="after")
    def validate_modes(self) -> DeliveryTerms:
        if not self.modes or len(set(self.modes)) != len(self.modes):
            raise ValueError("delivery modes must be non-empty and unique")
        if "unknown" in self.modes and self.modes != ("unknown",):
            raise ValueError("unknown delivery mode cannot accompany a known mode")
        return self


class CommercialTerms(RestrictedFeedContractModel):
    pricing: Literal["unknown", "free", "paid", "bespoke_commercial"] = "unknown"
    quotation_required: Literal["unknown", "yes", "no"] = "unknown"
    quotation_reference: SafeReference | None = None
    budget_authority: Literal["unknown", "not_required", "required_unapproved", "approved"] = (
        "unknown"
    )
    spending_authority_created_by_contract: Literal[False] = False

    @model_validator(mode="after")
    def validate_commercial(self) -> CommercialTerms:
        if self.pricing in {"paid", "bespoke_commercial"} and self.quotation_required != "yes":
            raise ValueError("paid or bespoke access requires a quotation decision")
        if self.pricing == "free" and self.quotation_required != "no":
            raise ValueError("free access must record that no quotation is required")
        if (self.quotation_required == "yes") != (self.quotation_reference is not None):
            raise ValueError("a required quotation needs exactly one safe quotation reference")
        return self


class OnboardingTerms(RestrictedFeedContractModel):
    application: KnownRequirement = "unknown"
    account: KnownRequirement = "unknown"
    credential: KnownRequirement = "unknown"
    ip_allowlist: KnownRequirement = "unknown"
    data_sharing_agreement: KnownRequirement = "unknown"
    process_reference: SafeReference | None = None


class ProviderLimit(RestrictedFeedContractModel):
    status: Literal["unknown", "limited", "unlimited", "not_applicable"] = "unknown"
    value: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_limit(self) -> ProviderLimit:
        if (self.status == "limited") != (self.value is not None):
            raise ValueError("exactly a limited provider bound carries an integer value")
        return self


class RequestLimitTerms(RestrictedFeedContractModel):
    requests_per_minute: ProviderLimit = ProviderLimit()
    concurrent_requests: ProviderLimit = ProviderLimit()
    requests_per_day: ProviderLimit = ProviderLimit()
    requests_per_month: ProviderLimit = ProviderLimit()
    page_size_rows: ProviderLimit = ProviderLimit()
    export_volume_rows: ProviderLimit = ProviderLimit()
    backoff_rules: Literal["unknown", "documented", "not_applicable"] = "unknown"
    limit_reference: SafeReference | None = None


class RetentionTerms(RestrictedFeedContractModel):
    status: Literal["unknown", "fixed_days", "unlimited", "not_permitted"] = "unknown"
    maximum_days: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_retention(self) -> RetentionTerms:
        if (self.status == "fixed_days") != (self.maximum_days is not None):
            raise ValueError("exactly fixed-day retention carries a maximum day count")
        return self


class RightsTerms(RestrictedFeedContractModel):
    licence: Literal["unknown", "permitted", "restricted", "denied"] = "unknown"
    licence_reference: SafeReference | None = None
    attribution: KnownRequirement = "unknown"
    attribution_reference: SafeReference | None = None
    retention: RetentionTerms = RetentionTerms()
    backup: PermissionState = "unknown"
    deletion: Literal["unknown", "required", "not_required", "provider_managed"] = "unknown"
    derived_academic_results: PermissionState = "unknown"
    aggregate_publication: PermissionState = "unknown"
    row_level_publication: PermissionState = "unknown"

    @model_validator(mode="after")
    def validate_rights(self) -> RightsTerms:
        if self.attribution == "required" and self.attribution_reference is None:
            raise ValueError("required attribution needs a safe rule reference")
        return self


class DetectorTerms(RestrictedFeedContractModel):
    retain_detector_identifiers: PermissionState = "unknown"
    retain_detector_locations: PermissionState = "unknown"
    reference_identifiers_in_research: PermissionState = "unknown"
    reference_locations_in_research: PermissionState = "unknown"


class TimeTerms(RestrictedFeedContractModel):
    timestamp_field_reference: SafeReference | None = None
    timezone: Literal["unknown", "UTC", "Europe/London", "fixed_offset", "other"] = "unknown"
    timezone_reference: SafeReference | None = None
    daylight_saving: Literal[
        "unknown",
        "not_applicable",
        "offset_in_timestamp",
        "fold_flag",
        "provider_revision",
        "documented_local_clock",
    ] = "unknown"
    interval_boundary: Literal[
        "unknown", "instant", "start_inclusive", "end_inclusive", "cumulative"
    ] = "unknown"
    revision_semantics: Literal[
        "unknown", "immutable", "latest_replaces", "versioned", "provider_defined"
    ] = "unknown"


class SensitiveFieldTerms(RestrictedFeedContractModel):
    handling: Literal["unknown", "none_required", "exclusions_required"] = "unknown"
    excluded_field_references: tuple[SafeReference, ...] = ()
    public_output_treatment: Literal[
        "unknown", "unchanged_permitted", "aggregate", "anonymise", "publication_prohibited"
    ] = "unknown"
    security_reference: SafeReference | None = None

    @model_validator(mode="after")
    def validate_sensitive(self) -> SensitiveFieldTerms:
        if (self.handling == "exclusions_required") != bool(self.excluded_field_references):
            raise ValueError("required exclusions must list safe field references")
        return self


class TechnicalTerms(RestrictedFeedContractModel):
    transport: Literal[
        "unknown", "https_json", "https_xml", "sftp_export", "portal_export", "other"
    ] = "unknown"
    endpoint_reference: SafeReference | None = None
    schema_status: Literal["unknown", "exact_schema_received", "schema_unavailable"] = "unknown"
    schema_reference: SafeReference | None = None
    schema_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    sample_status: Literal["unknown", "received", "unavailable"] = "unknown"
    sample_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    coverage: Literal["unknown", "documented", "not_applicable"] = "unknown"
    coverage_reference: SafeReference | None = None
    units: Literal["unknown", "documented", "not_applicable"] = "unknown"
    units_reference: SafeReference | None = None
    quality_flags: Literal["unknown", "documented", "not_provided"] = "unknown"
    quality_reference: SafeReference | None = None
    outage_behavior: Literal["unknown", "documented", "not_applicable"] = "unknown"
    support_route: Literal["unknown", "documented", "not_available"] = "unknown"
    change_notifications: Literal["unknown", "documented", "not_available"] = "unknown"

    @model_validator(mode="after")
    def validate_technical(self) -> TechnicalTerms:
        exact = self.schema_status == "exact_schema_received"
        if exact != (self.schema_reference is not None and self.schema_sha256 is not None):
            raise ValueError("an exact schema needs a safe reference and digest")
        if (self.sample_status == "received") != (self.sample_sha256 is not None):
            raise ValueError("a received sample needs its private-byte digest")
        return self


class RestrictedTrafficFeedAccessContract(RestrictedFeedContractModel):
    """One independently reviewed product contract; it never enables a sibling product."""

    schema_version: Literal["1.0"] = RESTRICTED_FEED_CONTRACT_SCHEMA_VERSION
    method_version: Literal["restricted-traffic-feed-access-contract-1.0"] = (
        RESTRICTED_FEED_CONTRACT_METHOD_VERSION
    )
    capability_ids: tuple[Literal["MAN-01", "MAN-07", "MAN-09", "MAN-10"], ...] = (
        "MAN-01",
        "MAN-07",
        "MAN-09",
        "MAN-10",
    )
    capability_status: Literal["planned"] = "planned"
    product: RestrictedFeedProduct
    provider: ProviderFamily
    contract_status: Literal[
        "draft_unknown", "provider_response_recorded", "reviewed_accepted", "reviewed_refused"
    ] = "draft_unknown"
    access: AcademicAccessTerms = AcademicAccessTerms()
    delivery: DeliveryTerms = DeliveryTerms()
    commercial: CommercialTerms = CommercialTerms()
    onboarding: OnboardingTerms = OnboardingTerms()
    request_limits: RequestLimitTerms = RequestLimitTerms()
    rights: RightsTerms = RightsTerms()
    detectors: DetectorTerms = DetectorTerms()
    time: TimeTerms = TimeTerms()
    sensitive_fields: SensitiveFieldTerms = SensitiveFieldTerms()
    technical: TechnicalTerms = TechnicalTerms()
    evidence: ProviderResponseEvidence | None = None
    reviewer: ContractReviewer | None = None
    reviewed_at_utc: datetime | None = None
    owner_decision_id: str | None = Field(
        default=None, pattern=r"^decision-[A-Za-z0-9][A-Za-z0-9_.:-]{7,95}$"
    )
    source_adapter_available: Literal[False] = False
    credentialed_probe_authorized: Literal[False] = False
    provider_request_performed: Literal[False] = False
    source_fields_assumed: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract(self) -> RestrictedTrafficFeedAccessContract:
        if self.provider != _PRODUCT_PROVIDER[self.product]:
            raise ValueError("product and provider family do not match")
        reviewed = self.contract_status in {"reviewed_accepted", "reviewed_refused"}
        if reviewed != all(
            value is not None
            for value in (
                self.evidence,
                self.reviewer,
                self.reviewed_at_utc,
                self.owner_decision_id,
            )
        ):
            raise ValueError(
                "a reviewed contract requires evidence, reviewer, UTC time and decision"
            )
        if self.contract_status == "provider_response_recorded" and self.evidence is None:
            raise ValueError("a recorded provider response requires its private-evidence digest")
        if self.reviewed_at_utc is not None:
            _require_utc(self.reviewed_at_utc, "contract review time")
        blockers = _fact_blockers(self)
        if self.contract_status == "reviewed_accepted" and blockers:
            raise ValueError("an accepted provider contract cannot retain unknown or blocked facts")
        return self


class ProviderContractAssessment(RestrictedFeedContractModel):
    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["restricted-traffic-feed-access-contract-1.0"] = (
        RESTRICTED_FEED_CONTRACT_METHOD_VERSION
    )
    product: RestrictedFeedProduct
    provider: ProviderFamily
    contract_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    readiness: ContractReadiness
    blockers: tuple[str, ...]
    next_stage: ContractNextStage
    quotation_decision_required: bool
    spending_authority_created: Literal[False] = False
    credentialed_probe_authorized: Literal[False] = False
    source_adapter_available: Literal[False] = False
    measured_traffic_available: Literal[False] = False
    sibling_products_enabled: Literal[False] = False
    provider_request_performed: Literal[False] = False
    source_fields_assumed: Literal[False] = False

    @model_validator(mode="after")
    def validate_assessment(self) -> ProviderContractAssessment:
        if self.readiness == "contract_accepted_adapter_not_implemented":
            if self.blockers or self.next_stage != "freeze_transport_then_authorize_minimum_probe":
                raise ValueError("accepted contract assessment has the wrong next stage")
        elif self.readiness == "provider_contract_refused":
            if self.next_stage != "none":
                raise ValueError("a refused contract has no adapter stage")
        elif not self.blockers:
            raise ValueError("an unresolved contract assessment must expose blockers")
        return self


def restricted_feed_contract_template(
    product: RestrictedFeedProduct,
) -> RestrictedTrafficFeedAccessContract:
    """Return a fully unknown, non-enabling template for one exact product."""

    return RestrictedTrafficFeedAccessContract(product=product, provider=_PRODUCT_PROVIDER[product])


def assess_restricted_feed_contract(
    contract: RestrictedTrafficFeedAccessContract,
) -> ProviderContractAssessment:
    """Reduce reviewed facts to a safe stage without ever authorising access or an adapter."""

    fact_blockers = _fact_blockers(contract)
    quotation = contract.commercial.pricing in {"paid", "bespoke_commercial"}
    readiness: ContractReadiness
    next_stage: ContractNextStage
    if contract.contract_status == "reviewed_refused":
        readiness = "provider_contract_refused"
        blockers: tuple[str, ...] = ("PROVIDER_CONTRACT_REFUSED",)
        next_stage = "none"
    elif contract.contract_status == "reviewed_accepted":
        readiness = "contract_accepted_adapter_not_implemented"
        blockers = ()
        next_stage = "freeze_transport_then_authorize_minimum_probe"
    elif contract.contract_status == "provider_response_recorded":
        readiness = "provider_response_under_review"
        blockers = tuple(sorted({"CONTRACT_REVIEW_REQUIRED", *fact_blockers}))
        next_stage = "resolve_contract_blockers" if fact_blockers else "review_provider_response"
    else:
        readiness = "unavailable_awaiting_provider_contract"
        blockers = tuple(sorted({"PROVIDER_RESPONSE_REQUIRED", *fact_blockers}))
        next_stage = "wait_for_provider_response"
    return ProviderContractAssessment(
        product=contract.product,
        provider=contract.provider,
        contract_fingerprint=contract.fingerprint(),
        readiness=readiness,
        blockers=blockers,
        next_stage=next_stage,
        quotation_decision_required=quotation,
    )


def load_restricted_feed_contract(path: str | Path) -> RestrictedTrafficFeedAccessContract:
    """Read one bounded private contract without network access, mutation or path disclosure."""

    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise RestrictedTrafficFeedContractError(
            "PROVIDER_CONTRACT_MISSING", "a safe provider contract file is required"
        )
    try:
        size = target.stat().st_size
        if size <= 0 or size > RESTRICTED_FEED_CONTRACT_MAX_BYTES:
            raise ValueError("contract size invalid")
        payload = target.read_bytes()
        if len(payload) != size:
            raise ValueError("contract changed during read")
        return RestrictedTrafficFeedAccessContract.model_validate_json(payload)
    except (OSError, ValueError) as exc:
        raise RestrictedTrafficFeedContractError(
            "PROVIDER_CONTRACT_INVALID", "the provider contract failed its strict schema"
        ) from exc


def _fact_blockers(contract: RestrictedTrafficFeedAccessContract) -> tuple[str, ...]:
    blockers: set[str] = set()
    if contract.access.availability != "available":
        blockers.add("ACADEMIC_AVAILABILITY_REQUIRED")
    if contract.access.academic_eligibility not in {"eligible", "conditional"}:
        blockers.add("ACADEMIC_ELIGIBILITY_REQUIRED")
    if (
        contract.access.data_owner_contact is None
        or contract.access.correct_contact_confirmed != "yes"
    ):
        blockers.add("DATA_OWNER_CONTACT_REQUIRED")
    if (
        contract.delivery.modes == ("unknown",)
        or contract.delivery.delivery_schedule_reference is None
    ):
        blockers.add("DELIVERY_MODE_REQUIRED")
    if (
        contract.commercial.pricing == "unknown"
        or contract.commercial.quotation_required == "unknown"
    ):
        blockers.add("COST_TERMS_REQUIRED")
    if contract.commercial.pricing in {"paid", "bespoke_commercial"} and (
        contract.commercial.budget_authority != "approved"
    ):
        blockers.add("BUDGET_AUTHORITY_REQUIRED")
    if (
        contract.commercial.pricing == "free"
        and contract.commercial.budget_authority != "not_required"
    ):
        blockers.add("BUDGET_AUTHORITY_REQUIRED")
    if (
        "unknown"
        in {
            contract.onboarding.application,
            contract.onboarding.account,
            contract.onboarding.credential,
            contract.onboarding.ip_allowlist,
            contract.onboarding.data_sharing_agreement,
        }
        or contract.onboarding.process_reference is None
    ):
        blockers.add("ONBOARDING_PROCESS_REQUIRED")
    limits = (
        contract.request_limits.requests_per_minute,
        contract.request_limits.concurrent_requests,
        contract.request_limits.requests_per_day,
        contract.request_limits.requests_per_month,
        contract.request_limits.page_size_rows,
        contract.request_limits.export_volume_rows,
    )
    if any(item.status == "unknown" for item in limits) or (
        contract.request_limits.backoff_rules == "unknown"
        or contract.request_limits.limit_reference is None
    ):
        blockers.add("REQUEST_LIMITS_REQUIRED")
    if (
        contract.rights.licence in {"unknown", "denied"}
        or contract.rights.licence_reference is None
        or contract.rights.attribution == "unknown"
        or (
            contract.rights.attribution == "required"
            and contract.rights.attribution_reference is None
        )
        or contract.rights.retention.status in {"unknown", "not_permitted"}
        or contract.rights.backup == "unknown"
        or contract.rights.deletion == "unknown"
        or contract.rights.derived_academic_results == "unknown"
        or contract.rights.aggregate_publication == "unknown"
        or contract.rights.row_level_publication == "unknown"
    ):
        blockers.add("RIGHTS_RETENTION_PUBLICATION_REQUIRED")
    if "unknown" in {
        contract.detectors.retain_detector_identifiers,
        contract.detectors.retain_detector_locations,
        contract.detectors.reference_identifiers_in_research,
        contract.detectors.reference_locations_in_research,
    }:
        blockers.add("DETECTOR_TREATMENT_REQUIRED")
    if (
        contract.time.timestamp_field_reference is None
        or contract.time.timezone == "unknown"
        or contract.time.timezone_reference is None
        or contract.time.daylight_saving == "unknown"
        or contract.time.interval_boundary == "unknown"
        or contract.time.revision_semantics == "unknown"
    ):
        blockers.add("TIME_DST_INTERVAL_REVISION_REQUIRED")
    if (
        contract.sensitive_fields.handling == "unknown"
        or contract.sensitive_fields.public_output_treatment == "unknown"
        or contract.sensitive_fields.security_reference is None
    ):
        blockers.add("SENSITIVE_FIELD_TREATMENT_REQUIRED")
    technical = contract.technical
    if (
        technical.transport == "unknown"
        or technical.endpoint_reference is None
        or technical.schema_status != "exact_schema_received"
        or technical.sample_status == "unknown"
        or technical.coverage == "unknown"
        or technical.coverage_reference is None
        or technical.units == "unknown"
        or technical.units_reference is None
        or technical.quality_flags == "unknown"
        or technical.quality_reference is None
        or technical.outage_behavior == "unknown"
        or technical.support_route == "unknown"
        or technical.change_notifications == "unknown"
    ):
        blockers.add("TECHNICAL_SCHEMA_COVERAGE_UNITS_REQUIRED")
    if contract.evidence is None:
        blockers.add("PROVIDER_RESPONSE_EVIDENCE_REQUIRED")
    return tuple(sorted(blockers))


def _require_utc(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be an aware UTC timestamp")
