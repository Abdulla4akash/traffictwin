"""Deterministic transitions between complete accepted National Highways snapshots."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.national_highways import (
    NationalHighwaysParseReport,
    NationalHighwaysProduct,
    NationalHighwaysRecord,
)
from traffictwin.integration.manchester.national_highways_acquisition import (
    NationalHighwaysAcquisition,
)

NATIONAL_HIGHWAYS_TRANSITION_SCHEMA_VERSION: Literal["1.0"] = "1.0"
NATIONAL_HIGHWAYS_TRANSITION_METHOD_VERSION: Literal["national-highways-transitions-1.0"] = (
    "national-highways-transitions-1.0"
)
_ACQUISITION_METHOD_VERSION: Literal["national-highways-acquisition-1.0"] = (
    "national-highways-acquisition-1.0"
)
_SOURCE_SCHEMA_VERSION: Literal["2026-07-24"] = "2026-07-24"
_PARSER_METHOD_VERSION: Literal["national-highways-datex-json-1.0"] = (
    "national-highways-datex-json-1.0"
)
MAX_TRANSITION_RECORDS = 40_000
MAX_SEEN_TOKENS = 100_000

TransitionState = Literal[
    "first_seen",
    "content_changed",
    "unchanged",
    "no_longer_listed",
    "validity_expired",
    "reappeared",
]
ChangedField = Literal[
    "record_updated_at_utc",
    "valid_from_utc",
    "valid_until_utc",
    "latitude",
    "longitude",
    "source_geometry_point_count",
    "source_geometry_sha256",
    "location_description",
    "road_name",
    "direction",
    "operational_type",
    "validity_status",
    "temporary_speed_limit_kph",
    "vms_working_status",
    "vms_description",
    "vms_message_information_types",
    "vms_reason_for_setting",
    "vms_message_set_at_utc",
    "unprojected_source_content",
]
TransitionWording = Literal[
    "New in the accepted feed",
    "Source record changed",
    "Unchanged between accepted snapshots",
    "No longer listed in the latest accepted feed",
    "Source validity expired",
    "Reappeared in the accepted feed",
]

_CHANGED_FIELDS: tuple[ChangedField, ...] = (
    "record_updated_at_utc",
    "valid_from_utc",
    "valid_until_utc",
    "latitude",
    "longitude",
    "source_geometry_point_count",
    "source_geometry_sha256",
    "location_description",
    "road_name",
    "direction",
    "operational_type",
    "validity_status",
    "temporary_speed_limit_kph",
    "vms_working_status",
    "vms_description",
    "vms_message_information_types",
    "vms_reason_for_setting",
    "vms_message_set_at_utc",
)


class NationalHighwaysTransitionError(RuntimeError):
    """Path-free refusal for an ineligible snapshot pair or history state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NationalHighwaysAcceptedTransitionSnapshot(ManchesterSnapshotModel):
    """Exact accepted receipt/report binding used by the comparison service."""

    snapshot_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$")
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    acquisition_method_version: Literal["national-highways-acquisition-1.0"] = (
        _ACQUISITION_METHOD_VERSION
    )
    schema_version: Literal["2026-07-24"] = _SOURCE_SCHEMA_VERSION
    parser_method_version: Literal["national-highways-datex-json-1.0"] = _PARSER_METHOD_VERSION
    report: NationalHighwaysParseReport
    accepted_private_snapshot: Literal[True] = True
    complete_snapshot: Literal[True] = True
    failed_or_partial: Literal[False] = False

    @model_validator(mode="after")
    def validate_binding(self) -> NationalHighwaysAcceptedTransitionSnapshot:
        if self.parser_report_fingerprint != self.report.fingerprint():
            raise ValueError("accepted snapshot must bind the exact parser report")
        if not self.report.complete_reconciliation:
            raise ValueError("transition snapshot must be completely reconciled")
        return self


class NationalHighwaysTransitionHistory(ManchesterSnapshotModel):
    """Opaque prior-presence memory required to distinguish first seen from reappeared."""

    product: NationalHighwaysProduct
    seen_record_tokens: tuple[str, ...] = Field(max_length=MAX_SEEN_TOKENS)
    through_snapshot_id: str | None = Field(default=None, max_length=128)
    through_publication_time_utc: datetime | None = None
    aggregates_only_except_opaque_tokens: Literal[True] = True
    literal_display_text_present: Literal[False] = False

    @model_validator(mode="after")
    def validate_history(self) -> NationalHighwaysTransitionHistory:
        if self.seen_record_tokens != tuple(sorted(set(self.seen_record_tokens))):
            raise ValueError("seen tokens must be sorted and unique")
        if any(
            len(item) != 24 or any(char not in "0123456789abcdef" for char in item)
            for item in self.seen_record_tokens
        ):
            raise ValueError("seen tokens must use the opaque record-token contract")
        return self


class NationalHighwaysRecordTransition(ManchesterSnapshotModel):
    """One private opaque-token transition with exact prior/current lineage."""

    product: NationalHighwaysProduct
    record_token: str = Field(pattern=r"^[0-9a-f]{24}$")
    state: TransitionState
    previous_record_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    current_record_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    previous_publication_time_utc: datetime
    current_publication_time_utc: datetime
    changed_fields: tuple[ChangedField, ...] = ()
    wording: TransitionWording
    previous_snapshot_id: str
    current_snapshot_id: str
    literal_display_text_present: Literal[False] = False
    measured_traffic_claim: Literal[False] = False
    public_row_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_transition(self) -> NationalHighwaysRecordTransition:
        has_previous = self.previous_record_fingerprint is not None
        has_current = self.current_record_fingerprint is not None
        if self.state in {"first_seen", "reappeared"} and (has_previous or not has_current):
            raise ValueError("appearance transition has invalid record sides")
        if self.state in {"no_longer_listed", "validity_expired"} and (
            not has_previous or has_current
        ):
            raise ValueError("absence transition has invalid record sides")
        if self.state in {"content_changed", "unchanged"} and not (has_previous and has_current):
            raise ValueError("continuing transition requires both record sides")
        if (self.state == "content_changed") != bool(self.changed_fields):
            raise ValueError("changed fields exist exactly for content changes")
        return self


class NationalHighwaysTransitionCounts(ManchesterSnapshotModel):
    first_seen: int = Field(ge=0)
    content_changed: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    no_longer_listed: int = Field(ge=0)
    validity_expired: int = Field(ge=0)
    reappeared: int = Field(ge=0)
    total: int = Field(ge=0, le=MAX_TRANSITION_RECORDS)

    @model_validator(mode="after")
    def validate_total(self) -> NationalHighwaysTransitionCounts:
        if self.total != sum(
            getattr(self, field)
            for field in (
                "first_seen",
                "content_changed",
                "unchanged",
                "no_longer_listed",
                "validity_expired",
                "reappeared",
            )
        ):
            raise ValueError("transition counts must reconcile")
        return self


class NationalHighwaysTransitionReport(ManchesterSnapshotModel):
    schema_version: Literal["1.0"] = NATIONAL_HIGHWAYS_TRANSITION_SCHEMA_VERSION
    method_version: Literal["national-highways-transitions-1.0"] = (
        NATIONAL_HIGHWAYS_TRANSITION_METHOD_VERSION
    )
    product: NationalHighwaysProduct
    previous_snapshot_id: str
    current_snapshot_id: str
    previous_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    envelope_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_publication_time_utc: datetime
    current_publication_time_utc: datetime
    transitions: tuple[NationalHighwaysRecordTransition, ...] = Field(
        max_length=MAX_TRANSITION_RECORDS
    )
    counts: NationalHighwaysTransitionCounts
    complete_set_reconciliation: Literal[True] = True
    consecutive_pair_caller_asserted: Literal[True] = True
    strategic_road_network_only: Literal[True] = True
    measured_speed_available: Literal[False] = False
    traffic_volume_available: Literal[False] = False
    literal_display_text_present: Literal[False] = False
    public_rows_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> NationalHighwaysTransitionReport:
        if len(self.transitions) != self.counts.total:
            raise ValueError("transition rows and counts must reconcile")
        keys = tuple((item.record_token, item.state) for item in self.transitions)
        if keys != tuple(sorted(keys)) or len(
            {item.record_token for item in self.transitions}
        ) != len(self.transitions):
            raise ValueError("transition tokens must be unique and stable")
        return self


class NationalHighwaysPublicTransitionAggregate(ManchesterSnapshotModel):
    """Aggregate-only public-candidate projection; publication is still unapproved."""

    product: NationalHighwaysProduct
    previous_publication_time_utc: datetime
    current_publication_time_utc: datetime
    counts: NationalHighwaysTransitionCounts
    source_attribution: Literal["Powered by National Highways’ Transport Data Feeds"] = (
        "Powered by National Highways’ Transport Data Feeds"
    )
    aggregates_only: Literal[True] = True
    opaque_tokens_present: Literal[False] = False
    locations_present: Literal[False] = False
    public_release_approved: Literal[False] = False


def accepted_transition_snapshot(
    acquisition: NationalHighwaysAcquisition,
) -> NationalHighwaysAcceptedTransitionSnapshot:
    """Bind the runtime report to the exact promoted acquisition receipt."""

    result = acquisition.result
    report = acquisition.report
    if (
        result.request.product != report.product
        or result.parser_report_fingerprint != report.fingerprint()
        or result.raw_sha256 != report.raw_sha256
        or result.publication_time_utc != report.publication_time_utc
        or result.records_accepted != len(report.records)
        or result.synthetic != report.synthetic
    ):
        raise NationalHighwaysTransitionError(
            "ACCEPTED_SNAPSHOT_BINDING_MISMATCH",
            "acquisition receipt does not bind the supplied complete report",
        )
    return NationalHighwaysAcceptedTransitionSnapshot(
        snapshot_id=result.snapshot_id,
        snapshot_receipt_fingerprint=result.snapshot_receipt_fingerprint,
        parser_report_fingerprint=result.parser_report_fingerprint,
        report=report,
    )


def compare_national_highways_snapshots(
    previous: NationalHighwaysAcceptedTransitionSnapshot,
    current: NationalHighwaysAcceptedTransitionSnapshot,
    *,
    history: NationalHighwaysTransitionHistory | None = None,
) -> NationalHighwaysTransitionReport:
    """Compare one caller-confirmed consecutive pair with complete set reconciliation."""

    prior = previous.report
    latest = current.report
    _validate_pair(previous, current, history)
    known = frozenset(()) if history is None else frozenset(history.seen_record_tokens)
    prior_by_token = {item.record_token: item for item in prior.records}
    latest_by_token = {item.record_token: item for item in latest.records}
    transitions: list[NationalHighwaysRecordTransition] = []
    for token in sorted(prior_by_token.keys() | latest_by_token.keys()):
        before = prior_by_token.get(token)
        after = latest_by_token.get(token)
        state, fields, wording = _classify(before, after, latest.publication_time_utc, known)
        transitions.append(
            NationalHighwaysRecordTransition(
                product=prior.product,
                record_token=token,
                state=state,
                previous_record_fingerprint=(
                    None if before is None else before.source_record_fingerprint
                ),
                current_record_fingerprint=(
                    None if after is None else after.source_record_fingerprint
                ),
                previous_publication_time_utc=prior.publication_time_utc,
                current_publication_time_utc=latest.publication_time_utc,
                changed_fields=fields,
                wording=wording,
                previous_snapshot_id=previous.snapshot_id,
                current_snapshot_id=current.snapshot_id,
            )
        )
    states = Counter(item.state for item in transitions)
    counts = NationalHighwaysTransitionCounts(
        first_seen=states["first_seen"],
        content_changed=states["content_changed"],
        unchanged=states["unchanged"],
        no_longer_listed=states["no_longer_listed"],
        validity_expired=states["validity_expired"],
        reappeared=states["reappeared"],
        total=len(transitions),
    )
    return NationalHighwaysTransitionReport(
        product=prior.product,
        previous_snapshot_id=previous.snapshot_id,
        current_snapshot_id=current.snapshot_id,
        previous_report_fingerprint=previous.parser_report_fingerprint,
        current_report_fingerprint=current.parser_report_fingerprint,
        envelope_fingerprint=prior.envelope_fingerprint,
        previous_publication_time_utc=prior.publication_time_utc,
        current_publication_time_utc=latest.publication_time_utc,
        transitions=tuple(transitions),
        counts=counts,
    )


def advance_transition_history(
    current: NationalHighwaysAcceptedTransitionSnapshot,
    history: NationalHighwaysTransitionHistory | None = None,
) -> NationalHighwaysTransitionHistory:
    """Return deterministic opaque presence memory without persistence."""

    if history is not None and history.product != current.report.product:
        raise NationalHighwaysTransitionError(
            "TRANSITION_HISTORY_PRODUCT_MISMATCH", "history product differs from the snapshot"
        )
    seen = set(() if history is None else history.seen_record_tokens)
    seen.update(item.record_token for item in current.report.records)
    if len(seen) > MAX_SEEN_TOKENS:
        raise NationalHighwaysTransitionError(
            "TRANSITION_HISTORY_LIMIT", "opaque transition history exceeds its bound"
        )
    return NationalHighwaysTransitionHistory(
        product=current.report.product,
        seen_record_tokens=tuple(sorted(seen)),
        through_snapshot_id=current.snapshot_id,
        through_publication_time_utc=current.report.publication_time_utc,
    )


def public_transition_aggregate(
    report: NationalHighwaysTransitionReport,
) -> NationalHighwaysPublicTransitionAggregate:
    """Remove row identities and locations for an unapproved public candidate."""

    return NationalHighwaysPublicTransitionAggregate(
        product=report.product,
        previous_publication_time_utc=report.previous_publication_time_utc,
        current_publication_time_utc=report.current_publication_time_utc,
        counts=report.counts,
    )


def _validate_pair(
    previous: NationalHighwaysAcceptedTransitionSnapshot,
    current: NationalHighwaysAcceptedTransitionSnapshot,
    history: NationalHighwaysTransitionHistory | None,
) -> None:
    prior = previous.report
    latest = current.report
    if previous.snapshot_id == current.snapshot_id:
        raise NationalHighwaysTransitionError(
            "TRANSITION_PAIR_NOT_DISTINCT", "transition snapshots must be distinct"
        )
    if prior.product != latest.product:
        raise NationalHighwaysTransitionError(
            "TRANSITION_PRODUCT_MISMATCH", "transition products differ"
        )
    if (
        prior.envelope_fingerprint != latest.envelope_fingerprint
        or prior.feed_type != latest.feed_type
        or prior.model_base_version != latest.model_base_version
        or prior.synthetic != latest.synthetic
    ):
        raise NationalHighwaysTransitionError(
            "TRANSITION_SCOPE_CONTRACT_MISMATCH",
            "scope, feed, model, or evidence class changed between snapshots",
        )
    if latest.publication_time_utc <= prior.publication_time_utc:
        raise NationalHighwaysTransitionError(
            "TRANSITION_TIME_NOT_INCREASING", "publication time must increase in UTC"
        )
    if history is not None:
        if history.product != prior.product:
            raise NationalHighwaysTransitionError(
                "TRANSITION_HISTORY_PRODUCT_MISMATCH", "history product differs from the pair"
            )
        if (
            history.through_publication_time_utc is not None
            and history.through_publication_time_utc > prior.publication_time_utc
        ):
            raise NationalHighwaysTransitionError(
                "TRANSITION_HISTORY_AHEAD", "history extends beyond the prior snapshot"
            )


def _classify(
    before: NationalHighwaysRecord | None,
    after: NationalHighwaysRecord | None,
    current_publication: datetime,
    known: frozenset[str],
) -> tuple[TransitionState, tuple[ChangedField, ...], TransitionWording]:
    if before is None and after is not None:
        if after.record_token in known:
            return "reappeared", (), "Reappeared in the accepted feed"
        return "first_seen", (), "New in the accepted feed"
    if before is not None and after is None:
        if before.valid_until_utc is not None and before.valid_until_utc <= current_publication:
            return "validity_expired", (), "Source validity expired"
        return "no_longer_listed", (), "No longer listed in the latest accepted feed"
    if before is None or after is None:
        raise AssertionError("unreachable transition side state")
    if before.source_record_fingerprint == after.source_record_fingerprint:
        return "unchanged", (), "Unchanged between accepted snapshots"
    changed = tuple(
        field for field in _CHANGED_FIELDS if getattr(before, field) != getattr(after, field)
    )
    if not changed:
        changed = ("unprojected_source_content",)
    return "content_changed", changed, "Source record changed"
