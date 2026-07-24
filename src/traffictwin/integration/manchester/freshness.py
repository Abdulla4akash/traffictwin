"""MAN-07 candidate: deterministic source-specific freshness and truth labels.

Evaluation uses caller-supplied UTC source/evaluation instants and frozen Gate-A
policy. It never reads the wall clock or retrieval time, and it cannot promote
undocumented DfT/WebTRIS timestamps into live evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    ManchesterValidationState,
)

MANCHESTER_FRESHNESS_SCHEMA_VERSION = "1.0"
MANCHESTER_FRESHNESS_METHOD_VERSION = "manchester-freshness-v1"
MANCHESTER_FRESHNESS_CAPABILITY_ID = "MAN-07"
BODS_LIVE_AGE_SECONDS: Literal[60] = 60
NATIONAL_HIGHWAYS_NEAR_LIVE_AGE_SECONDS: Literal[600] = 600

FreshnessSource: TypeAlias = Literal[
    "bods_siri_vm",
    "dft_raw_counts",
    "dft_count_points",
    "dft_aadf",
    "webtris_daily",
    "tfgm_signals",
    "randy_tos",
    "national_highways_closures",
    "national_highways_speed_limits",
    "national_highways_vms",
    "synthetic",
]
FreshnessTruthState: TypeAlias = Literal[
    "historical",
    "near_live",
    "live_vehicle",
    "stale",
    "unavailable",
    "synthetic",
]
FreshnessReason: TypeAlias = Literal[
    "bods_within_live_window",
    "bods_observation_too_old",
    "bods_validity_expired",
    "bods_future_dated",
    "national_highways_within_near_live_window",
    "national_highways_publication_too_old",
    "national_highways_publication_future_dated",
    "offline_replay_is_historical",
    "source_policy_is_historical",
    "synthetic_evidence",
    "static_reference_has_no_traffic_freshness",
    "simulation_clock_has_no_wall_freshness",
    "evidence_validation_rejected",
    "accepted_snapshot_unavailable",
    "service_notice_forced_unavailable",
    "cached_snapshot_during_service_outage",
    "source_timestamp_missing",
    "invalid_validity_window",
]


class ManchesterFreshnessModel(ManchesterSnapshotModel):
    """Strict frozen base for MAN-07 freshness artifacts."""


class SourceFreshnessPolicy(ManchesterFreshnessModel):
    """Frozen source-specific classification and display contract."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    policy_version: Literal["manchester-freshness-v1"] = "manchester-freshness-v1"
    source: FreshnessSource
    source_time_basis: Literal[
        "utc_instant",
        "local_clock_hour",
        "source_string_undeclared",
        "date_only",
        "simulation_clock",
        "synthetic_clock",
    ]
    expected_observation_field: str | None = Field(default=None, max_length=100)
    expected_valid_until_field: str | None = Field(default=None, max_length=100)
    accepted_live_age_seconds: Literal[60, 600] | None = None
    eligible_truth_states: tuple[FreshnessTruthState, ...]
    traffic_freshness_applicable: bool
    retrieval_time_can_upgrade_state: Literal[False] = False
    missing_timestamp_behaviour: Literal["unavailable", "not_applicable"]
    display_wording: str = Field(min_length=1, max_length=300)
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_policy(self) -> SourceFreshnessPolicy:
        if len(set(self.eligible_truth_states)) != len(self.eligible_truth_states):
            raise ValueError("eligible truth states must be unique")
        is_bods = self.source == "bods_siri_vm"
        bods_shape = (
            self.expected_observation_field == "RecordedAtTime"
            and self.expected_valid_until_field == "ValidUntilTime"
            and self.accepted_live_age_seconds == BODS_LIVE_AGE_SECONDS
        )
        is_national_highways = self.source.startswith("national_highways_")
        national_highways_shape = (
            self.expected_observation_field == "publicationTime"
            and self.expected_valid_until_field is None
            and self.accepted_live_age_seconds == NATIONAL_HIGHWAYS_NEAR_LIVE_AGE_SECONDS
        )
        if is_bods != bods_shape:
            raise ValueError("only BODS may define the v1 live-vehicle UTC window")
        if is_national_highways != national_highways_shape:
            raise ValueError("only National Highways may define the v1 near-live UTC window")
        if ("near_live" in self.eligible_truth_states) != is_national_highways:
            raise ValueError("near_live is reserved for the audited National Highways sources")
        return self


class FreshnessEvaluationRequest(ManchesterFreshnessModel):
    """All evidence used to classify one accepted local snapshot."""

    source: FreshnessSource
    evidence_validation: ManchesterValidationState
    snapshot_available: bool
    use_mode: Literal["live", "offline_replay", "historical"]
    evaluated_at_utc: datetime
    observed_at_utc: datetime | None = None
    valid_until_utc: datetime | None = None
    synthetic: bool
    service_state: Literal["normal", "forced_unavailable"] = "normal"
    service_notice_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$",
    )
    using_cached_snapshot: bool = False

    @model_validator(mode="after")
    def validate_request(self) -> FreshnessEvaluationRequest:
        _require_utc(self.evaluated_at_utc, "evaluated_at_utc")
        for label, value in (
            ("observed_at_utc", self.observed_at_utc),
            ("valid_until_utc", self.valid_until_utc),
        ):
            if value is not None:
                _require_utc(value, label)
        if (self.service_state == "forced_unavailable") != (self.service_notice_id is not None):
            raise ValueError("service override and notice ID must be supplied together")
        if self.using_cached_snapshot and not self.snapshot_available:
            raise ValueError("a cached fallback requires an accepted local snapshot")
        if self.source == "synthetic" and not self.synthetic:
            raise ValueError("the synthetic source must remain labelled synthetic")
        national_highways = self.source.startswith("national_highways_")
        if (
            self.source not in {"bods_siri_vm", "synthetic"}
            and not national_highways
            and (self.observed_at_utc is not None or self.valid_until_utc is not None)
        ):
            raise ValueError(
                "non-BODS audited sources cannot receive fabricated UTC validity fields"
            )
        if self.source == "bods_siri_vm" and (
            (self.observed_at_utc is None) != (self.valid_until_utc is None)
        ):
            raise ValueError("BODS observation and validity timestamps must be supplied together")
        if national_highways and self.valid_until_utc is not None:
            raise ValueError("National Highways snapshot freshness uses publicationTime only")
        return self


class SourceFreshnessEvaluation(ManchesterFreshnessModel):
    """One deterministic source truth-state decision with a stable reason."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    method_version: Literal["manchester-freshness-v1"] = "manchester-freshness-v1"
    source: FreshnessSource
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_status: Literal["classified", "unavailable", "not_applicable"]
    truth_state: FreshnessTruthState | None
    reason: FreshnessReason
    evaluated_at_utc: datetime
    observed_at_utc: datetime | None = None
    valid_until_utc: datetime | None = None
    observation_age_seconds: Decimal | None = None
    service_override_applied: bool
    retrieval_time_used: Literal[False] = False
    source_value_preserved: Literal[True] = True
    transit_live_available: bool
    road_traffic_live_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_evaluation(self) -> SourceFreshnessEvaluation:
        _require_utc(self.evaluated_at_utc, "evaluated_at_utc")
        if self.observed_at_utc is not None:
            _require_utc(self.observed_at_utc, "observed_at_utc")
        if self.valid_until_utc is not None:
            _require_utc(self.valid_until_utc, "valid_until_utc")
        if (self.evaluation_status == "not_applicable") != (self.truth_state is None):
            raise ValueError("only not-applicable sources may omit a truth state")
        if (self.evaluation_status == "unavailable") != (self.truth_state == "unavailable"):
            raise ValueError("unavailable evaluation must use the unavailable truth state")
        expected_transit_live = self.truth_state == "live_vehicle"
        if self.transit_live_available != expected_transit_live:
            raise ValueError("transit-live capability must match the truth state")
        if expected_transit_live and self.source != "bods_siri_vm":
            raise ValueError("only BODS may emit live_vehicle")
        if self.policy_fingerprint != source_freshness_policy(self.source).fingerprint():
            raise ValueError("policy fingerprint must match the frozen source policy")
        expected_states: dict[FreshnessReason, FreshnessTruthState | None] = {
            "bods_within_live_window": "live_vehicle",
            "bods_observation_too_old": "stale",
            "bods_validity_expired": "stale",
            "bods_future_dated": "stale",
            "national_highways_within_near_live_window": "near_live",
            "national_highways_publication_too_old": "stale",
            "national_highways_publication_future_dated": "stale",
            "offline_replay_is_historical": "historical",
            "source_policy_is_historical": "historical",
            "synthetic_evidence": "synthetic",
            "static_reference_has_no_traffic_freshness": None,
            "simulation_clock_has_no_wall_freshness": None,
            "evidence_validation_rejected": "unavailable",
            "accepted_snapshot_unavailable": "unavailable",
            "service_notice_forced_unavailable": "unavailable",
            "cached_snapshot_during_service_outage": "stale",
            "source_timestamp_missing": "unavailable",
            "invalid_validity_window": "unavailable",
        }
        if self.truth_state != expected_states[self.reason]:
            raise ValueError("truth state must match the deterministic reason")
        override_reasons = {
            "service_notice_forced_unavailable",
            "cached_snapshot_during_service_outage",
        }
        if self.service_override_applied != (self.reason in override_reasons):
            raise ValueError("service override flag must match the deterministic reason")
        if self.observation_age_seconds is not None:
            if (
                self.source != "bods_siri_vm"
                and not self.source.startswith("national_highways_")
                or self.observed_at_utc is None
            ):
                raise ValueError("only audited UTC live-source evidence may carry an age")
            if self.observation_age_seconds != _elapsed_seconds(
                self.evaluated_at_utc, self.observed_at_utc
            ):
                raise ValueError("observation age must exactly match source time")
        source_reasons: dict[FreshnessReason, frozenset[FreshnessSource]] = {
            "bods_within_live_window": frozenset({"bods_siri_vm"}),
            "bods_observation_too_old": frozenset({"bods_siri_vm"}),
            "bods_validity_expired": frozenset({"bods_siri_vm"}),
            "bods_future_dated": frozenset({"bods_siri_vm"}),
            "national_highways_within_near_live_window": frozenset(
                {
                    "national_highways_closures",
                    "national_highways_speed_limits",
                    "national_highways_vms",
                }
            ),
            "national_highways_publication_too_old": frozenset(
                {
                    "national_highways_closures",
                    "national_highways_speed_limits",
                    "national_highways_vms",
                }
            ),
            "national_highways_publication_future_dated": frozenset(
                {
                    "national_highways_closures",
                    "national_highways_speed_limits",
                    "national_highways_vms",
                }
            ),
            "offline_replay_is_historical": frozenset(
                {
                    "bods_siri_vm",
                    "national_highways_closures",
                    "national_highways_speed_limits",
                    "national_highways_vms",
                }
            ),
            "source_policy_is_historical": frozenset(
                {"dft_raw_counts", "dft_count_points", "dft_aadf", "webtris_daily"}
            ),
            "static_reference_has_no_traffic_freshness": frozenset({"tfgm_signals"}),
            "simulation_clock_has_no_wall_freshness": frozenset({"randy_tos"}),
            "cached_snapshot_during_service_outage": frozenset(
                {
                    "bods_siri_vm",
                    "webtris_daily",
                    "national_highways_closures",
                    "national_highways_speed_limits",
                    "national_highways_vms",
                }
            ),
            "source_timestamp_missing": frozenset(
                {
                    "bods_siri_vm",
                    "national_highways_closures",
                    "national_highways_speed_limits",
                    "national_highways_vms",
                }
            ),
            "invalid_validity_window": frozenset({"bods_siri_vm"}),
        }
        allowed_sources = source_reasons.get(self.reason)
        if allowed_sources is not None and self.source not in allowed_sources:
            raise ValueError("reason is not available for this source")
        return self


def source_freshness_policy(source: FreshnessSource) -> SourceFreshnessPolicy:
    """Return the exact frozen v1 policy for one source family."""

    if source == "bods_siri_vm":
        return SourceFreshnessPolicy(
            source=source,
            source_time_basis="utc_instant",
            expected_observation_field="RecordedAtTime",
            expected_valid_until_field="ValidUntilTime",
            accepted_live_age_seconds=60,
            eligible_truth_states=(
                "live_vehicle",
                "stale",
                "historical",
                "unavailable",
                "synthetic",
            ),
            traffic_freshness_applicable=True,
            missing_timestamp_behaviour="unavailable",
            display_wording="Bus/transit vehicle position; never general road traffic.",
        )
    if source in {"dft_raw_counts", "dft_count_points", "dft_aadf"}:
        basis: Literal["local_clock_hour", "date_only"] = (
            "local_clock_hour" if source == "dft_raw_counts" else "date_only"
        )
        blockers = ("GA-DFT-1",) if source == "dft_raw_counts" else ()
        return SourceFreshnessPolicy(
            source=source,
            source_time_basis=basis,
            eligible_truth_states=("historical", "unavailable", "synthetic"),
            traffic_freshness_applicable=True,
            missing_timestamp_behaviour="unavailable",
            display_wording="Historical DfT survey/statistical evidence; not live.",
            blockers=blockers,
        )
    if source == "webtris_daily":
        return SourceFreshnessPolicy(
            source=source,
            source_time_basis="source_string_undeclared",
            eligible_truth_states=("historical", "stale", "unavailable", "synthetic"),
            traffic_freshness_applicable=True,
            missing_timestamp_behaviour="unavailable",
            display_wording="Historical strategic-road evidence; not city-road live traffic.",
            blockers=("GA-WT-1",),
        )
    if source.startswith("national_highways_"):
        return SourceFreshnessPolicy(
            source=source,
            source_time_basis="utc_instant",
            expected_observation_field="publicationTime",
            accepted_live_age_seconds=NATIONAL_HIGHWAYS_NEAR_LIVE_AGE_SECONDS,
            eligible_truth_states=("near_live", "stale", "historical", "unavailable"),
            traffic_freshness_applicable=True,
            missing_timestamp_behaviour="unavailable",
            display_wording=(
                "Near-live Strategic Road Network operational status; not measured speed, "
                "traffic volume, congestion, or complete Manchester coverage."
            ),
        )
    if source == "tfgm_signals":
        return SourceFreshnessPolicy(
            source=source,
            source_time_basis="date_only",
            eligible_truth_states=("unavailable", "synthetic"),
            traffic_freshness_applicable=False,
            missing_timestamp_behaviour="not_applicable",
            display_wording="Versioned infrastructure reference; no traffic freshness state.",
        )
    if source == "randy_tos":
        return SourceFreshnessPolicy(
            source=source,
            source_time_basis="simulation_clock",
            eligible_truth_states=("unavailable", "synthetic"),
            traffic_freshness_applicable=False,
            missing_timestamp_behaviour="not_applicable",
            display_wording="Simulation evidence; no wall-clock freshness state.",
        )
    return SourceFreshnessPolicy(
        source="synthetic",
        source_time_basis="synthetic_clock",
        eligible_truth_states=("synthetic", "unavailable"),
        traffic_freshness_applicable=True,
        missing_timestamp_behaviour="unavailable",
        display_wording="Synthetic evidence; no observed-Manchester claim.",
    )


def evaluate_source_freshness(
    request: FreshnessEvaluationRequest,
) -> SourceFreshnessEvaluation:
    """Classify one source snapshot without wall-clock or retrieval-time inference."""

    policy = source_freshness_policy(request.source)

    def result(
        status: Literal["classified", "unavailable", "not_applicable"],
        state: FreshnessTruthState | None,
        reason: FreshnessReason,
        *,
        age: Decimal | None = None,
        override_applied: bool = False,
    ) -> SourceFreshnessEvaluation:
        return SourceFreshnessEvaluation(
            source=request.source,
            request_fingerprint=request.fingerprint(),
            policy_fingerprint=policy.fingerprint(),
            evaluation_status=status,
            truth_state=state,
            reason=reason,
            evaluated_at_utc=request.evaluated_at_utc,
            observed_at_utc=request.observed_at_utc,
            valid_until_utc=request.valid_until_utc,
            observation_age_seconds=age,
            service_override_applied=override_applied,
            transit_live_available=state == "live_vehicle",
        )

    if not request.snapshot_available:
        return result("unavailable", "unavailable", "accepted_snapshot_unavailable")
    if request.evidence_validation is ManchesterValidationState.REJECTED:
        return result("unavailable", "unavailable", "evidence_validation_rejected")
    if request.synthetic:
        return result("classified", "synthetic", "synthetic_evidence")
    if request.service_state == "forced_unavailable" and not request.using_cached_snapshot:
        return result(
            "unavailable",
            "unavailable",
            "service_notice_forced_unavailable",
            override_applied=True,
        )
    if request.source == "tfgm_signals":
        return result(
            "not_applicable",
            None,
            "static_reference_has_no_traffic_freshness",
        )
    if request.source == "randy_tos":
        return result(
            "not_applicable",
            None,
            "simulation_clock_has_no_wall_freshness",
        )
    if request.source in {"dft_raw_counts", "dft_count_points", "dft_aadf"}:
        return result("classified", "historical", "source_policy_is_historical")
    if request.source == "webtris_daily":
        if request.service_state == "forced_unavailable":
            return result(
                "classified",
                "stale",
                "cached_snapshot_during_service_outage",
                override_applied=True,
            )
        return result("classified", "historical", "source_policy_is_historical")
    if request.source == "synthetic":
        return result("classified", "synthetic", "synthetic_evidence")

    if request.source.startswith("national_highways_"):
        if request.observed_at_utc is None:
            return result("unavailable", "unavailable", "source_timestamp_missing")
        age = _elapsed_seconds(request.evaluated_at_utc, request.observed_at_utc)
        if request.use_mode != "live":
            return result("classified", "historical", "offline_replay_is_historical", age=age)
        if request.service_state == "forced_unavailable":
            return result(
                "classified",
                "stale",
                "cached_snapshot_during_service_outage",
                age=age,
                override_applied=True,
            )
        if age < 0:
            return result(
                "classified",
                "stale",
                "national_highways_publication_future_dated",
                age=age,
            )
        if age > NATIONAL_HIGHWAYS_NEAR_LIVE_AGE_SECONDS:
            return result(
                "classified",
                "stale",
                "national_highways_publication_too_old",
                age=age,
            )
        return result(
            "classified",
            "near_live",
            "national_highways_within_near_live_window",
            age=age,
        )

    if request.observed_at_utc is None or request.valid_until_utc is None:
        return result("unavailable", "unavailable", "source_timestamp_missing")
    if request.valid_until_utc < request.observed_at_utc:
        return result("unavailable", "unavailable", "invalid_validity_window")
    age = _elapsed_seconds(request.evaluated_at_utc, request.observed_at_utc)
    if request.use_mode != "live":
        return result("classified", "historical", "offline_replay_is_historical", age=age)
    if request.service_state == "forced_unavailable":
        return result(
            "classified",
            "stale",
            "cached_snapshot_during_service_outage",
            age=age,
            override_applied=True,
        )
    if age < 0:
        return result("classified", "stale", "bods_future_dated", age=age)
    if request.evaluated_at_utc > request.valid_until_utc:
        return result("classified", "stale", "bods_validity_expired", age=age)
    if age > BODS_LIVE_AGE_SECONDS:
        return result("classified", "stale", "bods_observation_too_old", age=age)
    return result("classified", "live_vehicle", "bods_within_live_window", age=age)


def _require_utc(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{label} must be explicitly UTC")


def _elapsed_seconds(later: datetime, earlier: datetime) -> Decimal:
    delta = later - earlier
    return Decimal(delta.days * 86_400 + delta.seconds) + Decimal(delta.microseconds) / Decimal(
        1_000_000
    )
