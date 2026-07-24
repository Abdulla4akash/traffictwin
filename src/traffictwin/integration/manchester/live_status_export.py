"""Privacy-safe metadata-only status export for Manchester operational sources."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.bods_acquisition import BODS_ATTRIBUTION_TEXT
from traffictwin.integration.manchester.bods_live_control import BodsLiveControlState
from traffictwin.integration.manchester.map_layers import NATIONAL_HIGHWAYS_ATTRIBUTION
from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.national_highways_live import (
    NationalHighwaysControlState,
)

MANCHESTER_LIVE_STATUS_SCHEMA_VERSION = "1.0"
MANCHESTER_LIVE_STATUS_METHOD_VERSION = "manchester-live-status-metadata-1.0"

LiveStatusSource: TypeAlias = Literal["bods_siri_vm", "national_highways_operational"]
LiveStatusState: TypeAlias = Literal[
    "never_attempted",
    "in_progress_with_cached_success",
    "in_progress_without_success",
    "succeeded",
    "failed_with_cached_success",
    "failed_without_success",
]
LiveStatusMetricName: TypeAlias = Literal[
    "accepted_bus_positions",
    "live_bus_positions",
    "stale_bus_positions",
    "synthetic_bus_positions",
    "closures_and_incidents",
    "temporary_speed_restrictions",
    "digital_vms_statuses",
]


class ManchesterLiveStatusMetric(ManchesterSnapshotModel):
    """One non-negative aggregate with a fixed non-traffic-total meaning."""

    metric: LiveStatusMetricName
    value: int = Field(ge=0)
    unit: Literal["records"] = "records"


class ManchesterLiveSourceStatus(ManchesterSnapshotModel):
    """Metadata-only status for one source family."""

    source: LiveStatusSource
    status: LiveStatusState
    last_attempt_at_utc: datetime | None
    latest_success_at_utc: datetime | None
    metrics: tuple[ManchesterLiveStatusMetric, ...]
    geographic_scope: Literal["request_bounding_box", "strategic_road_network"]
    evidence_meaning: Literal[
        "bus_position_records",
        "closures_restrictions_and_sign_status",
    ]
    attribution: str
    source_data_embedded: Literal[False] = False
    coordinates_embedded: Literal[False] = False
    identifiers_embedded: Literal[False] = False
    credentials_embedded: Literal[False] = False
    complete_manchester_coverage: Literal[False] = False

    @model_validator(mode="after")
    def validate_source(self) -> ManchesterLiveSourceStatus:
        expected_identity = {
            "bods_siri_vm": (
                "request_bounding_box",
                "bus_position_records",
                BODS_ATTRIBUTION_TEXT,
                (
                    "accepted_bus_positions",
                    "live_bus_positions",
                    "stale_bus_positions",
                    "synthetic_bus_positions",
                ),
            ),
            "national_highways_operational": (
                "strategic_road_network",
                "closures_restrictions_and_sign_status",
                NATIONAL_HIGHWAYS_ATTRIBUTION,
                (
                    "closures_and_incidents",
                    "temporary_speed_restrictions",
                    "digital_vms_statuses",
                ),
            ),
        }[self.source]
        observed_identity = (
            self.geographic_scope,
            self.evidence_meaning,
            self.attribution,
        )
        if observed_identity != expected_identity[:3]:
            raise ValueError("live-status source identity must match the reviewed source boundary")
        metric_names = tuple(metric.metric for metric in self.metrics)
        if self.status == "never_attempted":
            if self.last_attempt_at_utc is not None:
                raise ValueError("a never-attempted source cannot have an attempt timestamp")
        elif self.last_attempt_at_utc is None:
            raise ValueError("an attempted source requires its last-attempt timestamp")
        if self.latest_success_at_utc is None:
            if self.metrics or self.status not in {
                "never_attempted",
                "in_progress_without_success",
                "failed_without_success",
            }:
                raise ValueError("a source without success cannot publish aggregate metrics")
        else:
            if self.status not in {
                "in_progress_with_cached_success",
                "succeeded",
                "failed_with_cached_success",
            }:
                raise ValueError("a source with cached success must declare that evidence state")
            if metric_names != expected_identity[3]:
                raise ValueError(
                    "successful source status requires the exact safe metric inventory"
                )
        if self.source == "bods_siri_vm" and self.metrics:
            values = {metric.metric: metric.value for metric in self.metrics}
            if values["accepted_bus_positions"] != (
                values["live_bus_positions"]
                + values["stale_bus_positions"]
                + values["synthetic_bus_positions"]
            ):
                raise ValueError("BODS aggregate status counts must reconcile")
        for value in (self.last_attempt_at_utc, self.latest_success_at_utc):
            if value is not None and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
                raise ValueError("live-status timestamps must be UTC")
        return self


class ManchesterLiveStatusExport(ManchesterSnapshotModel):
    """Locally downloadable status with every public-hosting claim refused."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["manchester-live-status-metadata-1.0"] = (
        "manchester-live-status-metadata-1.0"
    )
    generated_at_utc: datetime
    sources: tuple[ManchesterLiveSourceStatus, ManchesterLiveSourceStatus]
    publication_class: Literal["metadata_only"] = "metadata_only"
    local_metadata_download_available: Literal[True] = True
    public_metadata_hosting_accepted: Literal[False] = False
    public_raw_snapshot_available: Literal[False] = False
    public_position_export_available: Literal[False] = False
    public_live_scene_hosting_accepted: Literal[False] = False
    licence_terms_recheck_required_before_hosting: Literal[True] = True
    raw_payloads_embedded: Literal[False] = False
    coordinates_embedded: Literal[False] = False
    vehicle_identifiers_embedded: Literal[False] = False
    bee_network_reference_table_embedded: Literal[False] = False
    credentials_embedded: Literal[False] = False
    official_boundary_context_available: Literal[True] = True
    external_basemap_available: Literal[False] = False
    complete_bee_network_coverage_available: Literal[False] = False
    continuous_city_road_telemetry_available: Literal[False] = False
    live_signal_state_available: Literal[False] = False
    complete_manchester_coverage_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_export(self) -> ManchesterLiveStatusExport:
        generated_offset = self.generated_at_utc.utcoffset()
        if self.generated_at_utc.tzinfo is None or generated_offset != timedelta(0):
            raise ValueError("live-status generation time must be UTC")
        if tuple(source.source for source in self.sources) != (
            "bods_siri_vm",
            "national_highways_operational",
        ):
            raise ValueError("live-status sources must use the fixed source order")
        source_times = tuple(
            value
            for source in self.sources
            for value in (source.last_attempt_at_utc, source.latest_success_at_utc)
            if value is not None
        )
        if any(value > self.generated_at_utc for value in source_times):
            raise ValueError("live-status generation time cannot precede source evidence")
        return self


def build_live_status_export(
    *,
    generated_at_utc: datetime,
    bods: BodsLiveControlState,
    national_highways: NationalHighwaysControlState,
) -> ManchesterLiveStatusExport:
    """Project private control states into a coordinate- and identifier-free manifest."""

    return ManchesterLiveStatusExport(
        generated_at_utc=generated_at_utc,
        sources=(
            _bods_status(bods),
            _national_highways_status(national_highways),
        ),
    )


def _bods_status(state: BodsLiveControlState) -> ManchesterLiveSourceStatus:
    latest = state.latest_success
    metrics: tuple[ManchesterLiveStatusMetric, ...] = ()
    if latest is not None:
        metrics = (
            ManchesterLiveStatusMetric(
                metric="accepted_bus_positions", value=latest.records_accepted
            ),
            ManchesterLiveStatusMetric(metric="live_bus_positions", value=latest.live_vehicle),
            ManchesterLiveStatusMetric(metric="stale_bus_positions", value=latest.stale),
            ManchesterLiveStatusMetric(
                metric="synthetic_bus_positions", value=latest.synthetic_records
            ),
        )
    return ManchesterLiveSourceStatus(
        source="bods_siri_vm",
        status=_status(state.last_attempt_status, latest is not None),
        last_attempt_at_utc=state.last_attempt_at_utc,
        latest_success_at_utc=None if latest is None else latest.evaluated_at_utc,
        metrics=metrics,
        geographic_scope="request_bounding_box",
        evidence_meaning="bus_position_records",
        attribution=BODS_ATTRIBUTION_TEXT,
    )


def _national_highways_status(
    state: NationalHighwaysControlState,
) -> ManchesterLiveSourceStatus:
    latest = None if not state.history else state.history[-1]
    metrics: tuple[ManchesterLiveStatusMetric, ...] = ()
    if latest is not None:
        counts = {item.product: item.records_accepted for item in latest.products}
        metrics = (
            ManchesterLiveStatusMetric(metric="closures_and_incidents", value=counts["closures"]),
            ManchesterLiveStatusMetric(
                metric="temporary_speed_restrictions", value=counts["speed_limits"]
            ),
            ManchesterLiveStatusMetric(metric="digital_vms_statuses", value=counts["vms"]),
        )
    return ManchesterLiveSourceStatus(
        source="national_highways_operational",
        status=_status(state.last_attempt_status, latest is not None),
        last_attempt_at_utc=state.last_attempt_at_utc,
        latest_success_at_utc=None if latest is None else latest.evaluated_at_utc,
        metrics=metrics,
        geographic_scope="strategic_road_network",
        evidence_meaning="closures_restrictions_and_sign_status",
        attribution=NATIONAL_HIGHWAYS_ATTRIBUTION,
    )


def _status(last_attempt_status: str, has_success: bool) -> LiveStatusState:
    if last_attempt_status == "never":
        return "never_attempted"
    if last_attempt_status == "in_progress":
        return "in_progress_with_cached_success" if has_success else "in_progress_without_success"
    if last_attempt_status == "succeeded":
        return "succeeded"
    return "failed_with_cached_success" if has_success else "failed_without_success"
