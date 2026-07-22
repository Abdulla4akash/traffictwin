"""MAN-07 candidate: evidence-compatible Manchester road projection.

Source adapters are converted into a strict intermediate record before any
canonical projection. Only a documented UTC source instant can enter the
existing ``TrafficObservationRecord`` shape. Current DfT and WebTRIS source
times therefore remain preserved exclusions while their Gate-A timezone
blockers are open.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal, TypeAlias, cast

from pydantic import Field, model_validator

from traffictwin.canonical.records import TrafficObservationRecord
from traffictwin.integration.manchester.dft import DftRawCountRecord
from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    canonical_json,
    sha256_hex,
)
from traffictwin.integration.manchester.time_basis import (
    LocalClockHourTime,
    ManchesterSourceTime,
    ManchesterTimeBasis,
    ManchesterTimeProjection,
    UndeclaredSourceStringTime,
    UtcInstantTime,
    project_source_time,
)
from traffictwin.integration.manchester.webtris import (
    MPH_TO_MPS,
    WebtrisDailyObservation,
)

MANCHESTER_PROJECTION_SCHEMA_VERSION = "1.0"
MANCHESTER_PROJECTION_METHOD_VERSION = "manchester-road-projection-1.0"
MANCHESTER_PROJECTION_CAPABILITY_ID = "MAN-07"

RoadObservationSource: TypeAlias = Literal[
    "dft_raw_count",
    "webtris_daily",
    "synthetic_utc_road",
]
RoadGeographicScope: TypeAlias = Literal[
    "manchester_local_authority",
    "strategic_approaches",
    "synthetic",
]
RoadQualityState: TypeAlias = Literal[
    "verified",
    "warning",
    "unavailable",
    "synthetic",
]
ProjectionExclusionReason: TypeAlias = Literal[
    "outside_half_open_window",
    "undocumented_source_timezone_ga_dft_1",
    "undocumented_source_timezone_ga_wt_1",
    "date_only_has_no_instant",
    "simulation_clock_is_not_wall_clock",
    "source_measurement_missing",
]

_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_MEMBER_PATH_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}(/[A-Za-z0-9][A-Za-z0-9._-]{0,99}){0,9}$"


class ManchesterProjectionError(ValueError):
    """Raised for caller-side lineage or duplicate-input misuse."""


class ManchesterProjectionModel(ManchesterSnapshotModel):
    """Strict frozen base for deterministic MAN-07 projection artifacts."""


class ManchesterRoadObservation(ManchesterProjectionModel):
    """Source-specific road evidence preserved before canonical admission."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    source: RoadObservationSource
    source_snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    source_member_path: str = Field(pattern=_MEMBER_PATH_PATTERN)
    source_member_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_row: int = Field(ge=1)
    source_row_identity: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
    source_time: ManchesterSourceTime
    sensor_id: str = Field(min_length=1, max_length=200)
    geographic_scope: RoadGeographicScope
    count: int | None = Field(default=None, ge=0)
    average_speed_mps: Decimal | None = Field(default=None, ge=0)
    original_average_speed: Decimal | None = Field(default=None, ge=0)
    original_speed_unit: Literal["mph", "m/s", "unavailable"]
    nominal_interval_seconds: int | None = Field(default=None, gt=0, le=86_400)
    location_label: str | None = Field(default=None, max_length=300)
    measurement_state: Literal["observed", "missing"]
    quality_state: RoadQualityState
    synthetic: bool
    retrieval_time_used: Literal[False] = False

    @model_validator(mode="after")
    def validate_source_semantics(self) -> ManchesterRoadObservation:
        missing = self.count is None and self.average_speed_mps is None
        if missing != (self.measurement_state == "missing"):
            raise ValueError("measurement state must match count/speed availability")
        if missing != (self.quality_state == "unavailable") and not self.synthetic:
            raise ValueError("missing observed-source measurements must be unavailable")
        if self.synthetic != (self.quality_state == "synthetic"):
            raise ValueError("synthetic marker and quality state must agree")
        if self.source == "dft_raw_count":
            if not isinstance(self.source_time, LocalClockHourTime):
                raise ValueError("DfT raw counts require the unresolved local-hour basis")
            if self.geographic_scope != "manchester_local_authority":
                raise ValueError("DfT raw counts require Manchester local-authority scope")
            if (
                self.average_speed_mps is not None
                or self.original_average_speed is not None
                or self.original_speed_unit != "unavailable"
            ):
                raise ValueError("DfT raw counts cannot acquire an unevidenced speed")
            if self.nominal_interval_seconds != 3_600:
                raise ValueError("DfT survey-hour records require a 3600-second interval")
        elif self.source == "webtris_daily":
            if not isinstance(self.source_time, UndeclaredSourceStringTime):
                raise ValueError("WebTRIS requires its undeclared source strings")
            if self.geographic_scope != "strategic_approaches":
                raise ValueError("WebTRIS requires strategic-approaches scope")
            if self.nominal_interval_seconds != 900:
                raise ValueError("WebTRIS daily rows require a 900-second interval")
            if (self.original_average_speed is None) != (self.average_speed_mps is None):
                raise ValueError("WebTRIS original and converted speeds must coexist")
            if self.original_average_speed is None:
                if self.original_speed_unit != "unavailable":
                    raise ValueError("missing WebTRIS speed must retain unavailable units")
            elif (
                self.original_speed_unit != "mph"
                or self.average_speed_mps != self.original_average_speed * MPH_TO_MPS
            ):
                raise ValueError("WebTRIS speed must preserve exact mph conversion")
        else:
            if not isinstance(self.source_time, UtcInstantTime):
                raise ValueError("synthetic UTC road evidence requires a UTC instant")
            if not self.synthetic or self.geographic_scope != "synthetic":
                raise ValueError("synthetic UTC road evidence must remain synthetic")
            if self.original_speed_unit == "mph" and (
                self.original_average_speed is None
                or self.average_speed_mps != self.original_average_speed * MPH_TO_MPS
            ):
                raise ValueError("synthetic mph speed must use the exact conversion")
            if self.original_speed_unit == "m/s" and (
                self.original_average_speed is None
                or self.average_speed_mps != self.original_average_speed
            ):
                raise ValueError("synthetic m/s speed must preserve its source value")
            if self.original_speed_unit == "unavailable" and (
                self.original_average_speed is not None
            ):
                raise ValueError("unavailable source speed cannot carry a value")
        return self


class ManchesterProjectedRoadRow(ManchesterProjectionModel):
    """Immutable wrapper whose payload maps exactly to the existing canonical model."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["manchester-road-projection-1.0"] = "manchester-road-projection-1.0"
    canonical_schema: Literal["TrafficObservationRecord"] = "TrafficObservationRecord"
    input_observation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    time_projection: ManchesterTimeProjection
    time_projection_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_file: str = Field(min_length=1, max_length=500)
    source_row: int = Field(ge=1)
    timestamp_s: float = Field(ge=0)
    sensor_id: str = Field(min_length=1, max_length=200)
    count: int | None = Field(default=None, ge=0)
    average_speed_mps: float | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=300)
    source_value_preserved: Literal[True] = True
    retrieval_clock_used: Literal[False] = False

    @model_validator(mode="after")
    def validate_canonical_payload(self) -> ManchesterProjectedRoadRow:
        self.to_canonical_record()
        if self.count is None and self.average_speed_mps is None:
            raise ValueError("an admitted canonical row needs count or speed evidence")
        if self.time_projection.status != "admitted":
            raise ValueError("canonical row requires an admitted time projection")
        if self.time_projection_fingerprint != self.time_projection.fingerprint():
            raise ValueError("time-projection fingerprint does not match its evidence")
        if self.time_projection.timestamp_s is None or self.timestamp_s != float(
            self.time_projection.timestamp_s
        ):
            raise ValueError("canonical timestamp must match the admitted time projection")
        return self

    def to_canonical_record(self) -> TrafficObservationRecord:
        """Materialise the existing canonical record without adding schema fields."""

        return TrafficObservationRecord(
            source_file=self.source_file,
            source_row=self.source_row,
            timestamp_s=self.timestamp_s,
            sensor_id=self.sensor_id,
            count=self.count,
            average_speed_mps=self.average_speed_mps,
            location=self.location,
        )


class ManchesterProjectionExclusion(ManchesterProjectionModel):
    """One source row retained outside the canonical table with an exact reason."""

    input_observation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_row_identity: str = Field(min_length=1, max_length=200)
    reason: ProjectionExclusionReason
    time_projection: ManchesterTimeProjection
    measurement_available: bool
    source_value_preserved: Literal[True] = True
    fabricated_timestamp: Literal[False] = False

    @model_validator(mode="after")
    def validate_exclusion(self) -> ManchesterProjectionExclusion:
        if self.reason == "source_measurement_missing":
            if self.measurement_available:
                raise ValueError("missing-measurement exclusion cannot claim a measurement")
        elif self.reason != self.time_projection.reason:
            raise ValueError("time exclusion reason must match the time projection")
        if (
            self.time_projection.status == "admitted"
            and self.reason != "source_measurement_missing"
        ):
            raise ValueError("admitted time cannot carry a time-basis exclusion")
        return self


class ManchesterProjectionCounts(ManchesterProjectionModel):
    """Complete input accounting for one projection request."""

    inputs_seen: int = Field(ge=0)
    rows_admitted: int = Field(ge=0)
    rows_excluded: int = Field(ge=0)
    missing_measurements: int = Field(ge=0)
    time_basis_exclusions: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> ManchesterProjectionCounts:
        if self.inputs_seen != self.rows_admitted + self.rows_excluded:
            raise ValueError("projection counts must reconcile to inputs")
        if self.rows_excluded != self.missing_measurements + self.time_basis_exclusions:
            raise ValueError("exclusion categories must reconcile")
        return self


class ManchesterProjectionReport(ManchesterProjectionModel):
    """Deterministic projection result with complete admitted/excluded reconciliation."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    method_version: Literal["manchester-road-projection-1.0"] = "manchester-road-projection-1.0"
    time_basis: ManchesterTimeBasis
    time_basis_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_set_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_observation_fingerprints: tuple[str, ...]
    source_record_fingerprints: tuple[str, ...]
    status: Literal["available", "partial", "unavailable"]
    counts: ManchesterProjectionCounts
    rows: tuple[ManchesterProjectedRoadRow, ...] = ()
    exclusions: tuple[ManchesterProjectionExclusion, ...] = ()
    complete_reconciliation: Literal[True] = True
    canonical_schema_extended: Literal[False] = False
    retrieval_clock_used: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> ManchesterProjectionReport:
        if self.time_basis_fingerprint != self.time_basis.fingerprint():
            raise ValueError("time-basis fingerprint does not match the embedded basis")
        if (
            tuple(sorted(self.input_observation_fingerprints))
            != self.input_observation_fingerprints
        ):
            raise ValueError("input observation fingerprints must be sorted")
        if len(set(self.input_observation_fingerprints)) != len(
            self.input_observation_fingerprints
        ):
            raise ValueError("input observation fingerprints must be unique")
        if tuple(sorted(self.source_record_fingerprints)) != self.source_record_fingerprints:
            raise ValueError("source-record fingerprints must be sorted")
        if len(set(self.source_record_fingerprints)) != len(self.source_record_fingerprints):
            raise ValueError("source-record fingerprints must be unique")
        expected_input_fingerprint = _input_set_fingerprint(
            self.time_basis_fingerprint,
            self.input_observation_fingerprints,
            self.source_record_fingerprints,
        )
        if self.input_set_fingerprint != expected_input_fingerprint:
            raise ValueError("input-set fingerprint does not reconcile")
        row_fingerprints = tuple(row.input_observation_fingerprint for row in self.rows)
        exclusion_fingerprints = tuple(
            exclusion.input_observation_fingerprint for exclusion in self.exclusions
        )
        accounted = tuple(sorted((*row_fingerprints, *exclusion_fingerprints)))
        if accounted != self.input_observation_fingerprints:
            raise ValueError("admitted and excluded rows must account for every input exactly once")
        accounted_sources = tuple(
            sorted(
                (
                    *(row.source_record_fingerprint for row in self.rows),
                    *(exclusion.source_record_fingerprint for exclusion in self.exclusions),
                )
            )
        )
        if accounted_sources != self.source_record_fingerprints:
            raise ValueError("projection outcomes must retain every source-record fingerprint")
        if any(
            row.time_projection.time_basis_fingerprint != self.time_basis_fingerprint
            for row in self.rows
        ) or any(
            exclusion.time_projection.time_basis_fingerprint != self.time_basis_fingerprint
            for exclusion in self.exclusions
        ):
            raise ValueError("every time projection must bind the report time basis")
        if self.counts.rows_admitted != len(self.rows):
            raise ValueError("admitted count must match rows")
        if self.counts.rows_excluded != len(self.exclusions):
            raise ValueError("excluded count must match exclusions")
        missing = sum(
            exclusion.reason == "source_measurement_missing" for exclusion in self.exclusions
        )
        if self.counts.missing_measurements != missing:
            raise ValueError("missing-measurement count must match exclusions")
        expected_status = (
            "unavailable" if not self.rows else "available" if not self.exclusions else "partial"
        )
        if self.status != expected_status:
            raise ValueError("status must match admitted and excluded rows")
        return self


def dft_raw_count_observation(record: DftRawCountRecord) -> ManchesterRoadObservation:
    """Preserve one DfT row without inventing its unresolved UTC instant or speed."""

    count = record.counts.all_motor_vehicles
    quality: RoadQualityState = (
        "synthetic"
        if record.source.synthetic
        else "unavailable"
        if count is None
        else "verified"
        if record.counts.is_complete()
        else "warning"
    )
    return ManchesterRoadObservation(
        source="dft_raw_count",
        source_snapshot_id=record.source.snapshot_id,
        source_member_path=record.source.member_path,
        source_member_sha256=record.source.member_sha256,
        source_record_fingerprint=record.fingerprint(),
        source_row=record.row_index + 1,
        source_row_identity=f"dft-raw-count:{record.source_row_id}",
        source_time=LocalClockHourTime(
            source_date=record.count_date,
            hour_label=record.hour,
        ),
        sensor_id=str(record.count_point_id),
        geographic_scope="manchester_local_authority",
        count=count,
        average_speed_mps=None,
        original_average_speed=None,
        original_speed_unit="unavailable",
        nominal_interval_seconds=3_600,
        location_label=record.location.road_name,
        measurement_state="missing" if count is None else "observed",
        quality_state=quality,
        synthetic=record.source.synthetic,
    )


def webtris_daily_observation(
    record: WebtrisDailyObservation,
) -> ManchesterRoadObservation:
    """Preserve one strategic-road interval and its undeclared source time strings."""

    missing = record.measurement_state == "missing"
    reconciliations = (record.length_total_reconciled, record.speed_total_reconciled)
    quality: RoadQualityState = (
        "synthetic"
        if record.source.synthetic
        else "unavailable"
        if missing
        else "verified"
        if all(value is True for value in reconciliations)
        else "warning"
    )
    return ManchesterRoadObservation(
        source="webtris_daily",
        source_snapshot_id=record.source.snapshot_id,
        source_member_path=record.source.member_path,
        source_member_sha256=record.source.member_sha256,
        source_record_fingerprint=record.fingerprint(),
        source_row=record.row_index + 1,
        source_row_identity=(
            f"webtris:{record.site_id}:{record.report_date.isoformat()}:{record.interval_index}"
        ),
        source_time=UndeclaredSourceStringTime(
            source_date_raw=record.report_date_raw,
            source_time_raw=record.time_period_ending_raw,
        ),
        sensor_id=record.site_id,
        geographic_scope="strategic_approaches",
        count=record.total_volume,
        average_speed_mps=record.average_speed_mps,
        original_average_speed=record.average_speed_mph,
        original_speed_unit=("unavailable" if record.average_speed_mph is None else "mph"),
        nominal_interval_seconds=record.nominal_interval_seconds,
        location_label=record.site_name,
        measurement_state=record.measurement_state,
        quality_state=quality,
        synthetic=record.source.synthetic,
    )


def project_road_observations(
    observations: Sequence[ManchesterRoadObservation],
    time_basis: ManchesterTimeBasis,
) -> ManchesterProjectionReport:
    """Project compatible observations and reconcile every input or exclusion."""

    ordered = tuple(sorted(observations, key=lambda observation: observation.fingerprint()))
    observation_fingerprints = tuple(observation.fingerprint() for observation in ordered)
    source_fingerprints = tuple(
        sorted(observation.source_record_fingerprint for observation in ordered)
    )
    if len(set(observation_fingerprints)) != len(observation_fingerprints):
        raise ManchesterProjectionError("duplicate source observations are not admissible")
    if len(set(source_fingerprints)) != len(source_fingerprints):
        raise ManchesterProjectionError("one source record cannot be projected more than once")
    rows: list[ManchesterProjectedRoadRow] = []
    exclusions: list[ManchesterProjectionExclusion] = []
    for observation in ordered:
        source_fingerprint = observation.fingerprint()
        time_projection = project_source_time(observation.source_time, time_basis)
        measurement_available = observation.measurement_state == "observed"
        if not measurement_available:
            exclusions.append(
                ManchesterProjectionExclusion(
                    input_observation_fingerprint=source_fingerprint,
                    source_record_fingerprint=observation.source_record_fingerprint,
                    source_row_identity=observation.source_row_identity,
                    reason="source_measurement_missing",
                    time_projection=time_projection,
                    measurement_available=False,
                )
            )
            continue
        if time_projection.status == "excluded":
            exclusions.append(
                ManchesterProjectionExclusion(
                    input_observation_fingerprint=source_fingerprint,
                    source_record_fingerprint=observation.source_record_fingerprint,
                    source_row_identity=observation.source_row_identity,
                    reason=cast(ProjectionExclusionReason, time_projection.reason),
                    time_projection=time_projection,
                    measurement_available=True,
                )
            )
            continue
        if time_projection.timestamp_s is None:
            raise ManchesterProjectionError("admitted source time omitted canonical seconds")
        rows.append(
            ManchesterProjectedRoadRow(
                input_observation_fingerprint=source_fingerprint,
                source_record_fingerprint=observation.source_record_fingerprint,
                time_projection=time_projection,
                time_projection_fingerprint=time_projection.fingerprint(),
                source_file=(f"{observation.source_snapshot_id}/{observation.source_member_path}"),
                source_row=observation.source_row,
                timestamp_s=float(time_projection.timestamp_s),
                sensor_id=observation.sensor_id,
                count=observation.count,
                average_speed_mps=(
                    None
                    if observation.average_speed_mps is None
                    else float(observation.average_speed_mps)
                ),
                location=observation.location_label,
            )
        )
    missing = sum(exclusion.reason == "source_measurement_missing" for exclusion in exclusions)
    counts = ManchesterProjectionCounts(
        inputs_seen=len(ordered),
        rows_admitted=len(rows),
        rows_excluded=len(exclusions),
        missing_measurements=missing,
        time_basis_exclusions=len(exclusions) - missing,
    )
    status: Literal["available", "partial", "unavailable"] = (
        "unavailable" if not rows else "available" if not exclusions else "partial"
    )
    basis_fingerprint = time_basis.fingerprint()
    return ManchesterProjectionReport(
        time_basis=time_basis,
        time_basis_fingerprint=basis_fingerprint,
        input_set_fingerprint=_input_set_fingerprint(
            basis_fingerprint,
            observation_fingerprints,
            source_fingerprints,
        ),
        input_observation_fingerprints=observation_fingerprints,
        source_record_fingerprints=source_fingerprints,
        status=status,
        counts=counts,
        rows=tuple(rows),
        exclusions=tuple(exclusions),
    )


def _input_set_fingerprint(
    time_basis_fingerprint: str,
    input_observation_fingerprints: tuple[str, ...],
    source_record_fingerprints: tuple[str, ...],
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "time_basis_fingerprint": time_basis_fingerprint,
                "input_observation_fingerprints": input_observation_fingerprints,
                "source_record_fingerprints": source_record_fingerprints,
            }
        ).encode("utf-8")
    )
