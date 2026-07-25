"""DfT temporal-profile candidate for Manchester local authority.

This builds the sixth of ``MAN-09``'s seven acceptance components — "build
temporal profile" — under the versioned candidate policy
``manchester-dft-temporal-profile-owner-candidate-1.0``.

Real versus synthetic is carried, not assumed.  The builder accepts either an
accepted real snapshot or a labelled synthetic fixture and records which in
``evidence_class``; only :func:`open_real_raw_count_evidence` establishes real
evidence, by refusing a synthetic snapshot at the accepted-storage boundary.
A profile can therefore never quietly present fixture rows as Manchester
measurements.

**Exploratory candidate software evidence.**  Not supervisor approval, not
scientific validation.  ``docs/evaluation/supervisor_contract_decision_form.md``
is unsigned, and a later review may revise every rule here without changing any
raw evidence.

The profile says nothing the source does not
=============================================

Deliberately, this module adds exactly two things to the observations: a
**simulation-clock origin** and an **accounting**.  It does not smooth, average,
interpolate, or fill, and it never aggregates across a site, a date, a season,
or a direction of travel.  A cell is one site, one direction, one survey date,
one clock hour — the same grain the source records.

Why there is no UTC anywhere
============================

ADR-055 types the DfT raw-count ``hour`` as ``local_clock_hour``: the provider
documents it as a local clock range ("7 represents between 7am and 8am") with no
timezone, and ``GA-DFT-1`` is open.  A local clock hour is therefore never
promoted to an instant here.  DfT's neutral-day survey dates fall almost
entirely inside BST, which makes the missing timezone material rather than
theoretical: assuming Europe/London would shift every hour near a DST boundary
and be indistinguishable from correct data afterwards.

The simulation clock is a **declared mapping, not a discovered instant**: 07:00
local is simulation second zero, and hour *h* becomes the half-open interval
``[(h-7)*3600, (h-7+1)*3600)``.  That is a modelling convention the operator
chose, and it stays labelled as one.

Missing, zero, and the difference between them
==============================================

A cell with no row is ``missing_no_row`` and carries no value.  A cell whose
``all_motor_vehicles`` is null is a typed exclusion, not a zero.  A cell whose
source value *is* zero is admitted as zero and flagged ``measured_zero``,
because a road that was observed to carry nothing is a measurement and deleting
it would bias every mean computed downstream.  Nothing is ever filled.

What is refused outright
========================

*   **AADF** is an annual statistical estimate, not a survey hour.  It is
    contextual evidence and is refused as a profile input rather than silently
    fused.  The ``Counted``/``Estimated`` marker exists only on AADF, so using
    raw counts preserves that distinction structurally rather than by
    convention.
*   **WebTRIS** stays out while ``GA-WT-1`` leaves its clock basis unresolved.
    Mixing an undeclared clock into an hourly profile would produce rows that
    look comparable and are not.
"""

from __future__ import annotations

import datetime as dt
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Literal, NamedTuple, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.dft import (
    DftManchesterScope,
    DftRawCountRecord,
    DirectionCode,
    RoadType,
)
from traffictwin.integration.manchester.dft_acquisition import open_accepted_dft_snapshot
from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    ManchesterValidationState,
    sha256_hex,
)
from traffictwin.integration.manchester.temporal_profile import (
    DayType,
    Season,
    day_type_for,
    season_for,
)

PROFILE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
PROFILE_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"
PROFILE_METHOD_VERSION: Literal["manchester-dft-temporal-profile-1.0"] = (
    "manchester-dft-temporal-profile-1.0"
)
PROFILE_POLICY_ID: Literal["manchester-dft-temporal-profile-owner-candidate-1.0"] = (
    "manchester-dft-temporal-profile-owner-candidate-1.0"
)
RESEARCH_STATUS: Literal["owner_approved_candidate"] = "owner_approved_candidate"

#: 07:00 local is simulation second zero.  A declared modelling convention, not
#: a discovered instant.
SIMULATION_ORIGIN_LOCAL_HOUR: Literal[7] = 7

#: Exactly one hour, half-open: ``[start, start + 3600)``.
INTERVAL_SECONDS: Literal[3600] = 3600

#: The declared profile window, 07:00 to 19:00 local.  Measured on the real
#: Manchester acquisition, the hours present are exactly 7 through 18, which
#: independently confirms the window rather than defining it.
PROFILE_HOURS: tuple[int, ...] = tuple(range(7, 19))

#: Fixed salt for the site partition.  Named and versioned so the split is
#: reproducible by anyone and cannot drift silently between runs.
SPLIT_SALT: Literal["manchester-dft-temporal-profile-split-1.0"] = (
    "manchester-dft-temporal-profile-split-1.0"
)

#: Held-out share as basis points of 10,000: 2,000 = 20%.
HELD_OUT_BASIS_POINTS: Literal[2000] = 2000
SPLIT_BUCKETS: Literal[10000] = 10000

#: The only evidence kind admitted as profile input.
ADMITTED_EVIDENCE_KIND: Literal["survey_hour_raw_count"] = "survey_hour_raw_count"

#: The single calibration measure.  DfT's own column, not a derived quantity.
PROFILE_MEASURE: Literal["all_motor_vehicles"] = "all_motor_vehicles"

MAX_PROFILE_OBSERVATIONS = 500_000
MAX_PROFILE_SERIES = 50_000

#: Bound on a stored profile artifact. The real Manchester profile serialises
#: to about 7 MB; this leaves generous headroom while keeping an unbounded read
#: of an arbitrary path impossible.
MAX_PROFILE_ARTIFACT_BYTES = 64_000_000

_COVERAGE_QUANTUM = Decimal("0.000001")

Partition: TypeAlias = Literal["development", "held_out"]

PARTITIONS: tuple[Partition, ...] = ("development", "held_out")

CellState: TypeAlias = Literal[
    "observed",
    "missing_no_row",
    "excluded_null_value",
    "excluded_conflicting_duplicate",
]

ProfileExclusionReason: TypeAlias = Literal[
    "hour_outside_declared_window",
    "null_all_motor_vehicles",
    "conflicting_duplicate_rows",
    "out_of_scope_local_authority",
]

EvidenceClass: TypeAlias = Literal["accepted_real_snapshot", "labelled_synthetic_fixture"]

ProfileAdmission: TypeAlias = Literal[
    "admitted_candidate",
    "not_admitted_insufficient_coverage",
    "not_admitted_empty_partition",
]


class DftTemporalProfileError(ValueError):
    """Typed refusal for an unsupported or inconsistent profile request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class DftTemporalProfileModel(ManchesterSnapshotModel):
    """Strict frozen base for real temporal-profile artifacts."""


def simulation_interval_for_hour(hour: int) -> tuple[int, int]:
    """Map one local clock hour to its half-open simulation-second interval.

    Refuses an hour outside the declared window rather than extrapolating: the
    window is a policy statement about which hours the profile covers, and
    silently extending it would publish a cell no observation supports.
    """

    if hour not in PROFILE_HOURS:
        raise DftTemporalProfileError(
            "HOUR_OUTSIDE_DECLARED_WINDOW",
            f"local clock hour {hour} is outside the declared profile window "
            f"{PROFILE_HOURS[0]}-{PROFILE_HOURS[-1]}",
        )
    start = (hour - SIMULATION_ORIGIN_LOCAL_HOUR) * INTERVAL_SECONDS
    return start, start + INTERVAL_SECONDS


def partition_for_site(count_point_id: int, *, salt: str = SPLIT_SALT) -> Partition:
    """Assign one count-point site to a partition, deterministically.

    Hashing the *site* rather than the row is what keeps every hour, direction,
    and date from one site on the same side. Splitting by row would let the same
    road appear in development and held-out at once, and a held-out score would
    then be measuring memorisation.
    """

    digest = sha256_hex(f"{salt}:{count_point_id}".encode())
    bucket = int(digest[:8], 16) % SPLIT_BUCKETS
    return "held_out" if bucket < HELD_OUT_BASIS_POINTS else "development"


class DftTemporalProfilePolicy(DftTemporalProfileModel):
    """The versioned candidate policy, as a checkable artifact."""

    schema_version: Literal["1.0"] = PROFILE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = PROFILE_CAPABILITY_ID
    method_version: Literal["manchester-dft-temporal-profile-1.0"] = PROFILE_METHOD_VERSION
    policy_id: Literal["manchester-dft-temporal-profile-owner-candidate-1.0"] = PROFILE_POLICY_ID
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS

    scope: DftManchesterScope = DftManchesterScope()
    measure: Literal["all_motor_vehicles"] = PROFILE_MEASURE
    unit: Literal["vehicles_per_hour_interval"] = "vehicles_per_hour_interval"

    #: ADR-055: the DfT hour is a local clock label and GA-DFT-1 is open.
    time_basis: Literal["local_clock_hour"] = "local_clock_hour"
    utc_projection_available: Literal[False] = False
    simulation_origin_local_hour: Literal[7] = SIMULATION_ORIGIN_LOCAL_HOUR
    interval_seconds: Literal[3600] = INTERVAL_SECONDS
    interval_convention: Literal["half_open_start_inclusive_end_exclusive"] = (
        "half_open_start_inclusive_end_exclusive"
    )
    profile_hours: tuple[int, ...] = PROFILE_HOURS

    #: The grain, stated so that no consumer has to infer it.
    series_key: Literal["count_point_id + direction_of_travel + count_date"] = (
        "count_point_id + direction_of_travel + count_date"
    )
    direction_preserved: Literal[True] = True
    fuses_across_sites: Literal[False] = False
    fuses_across_dates: Literal[False] = False
    fuses_across_seasons: Literal[False] = False
    fuses_across_directions: Literal[False] = False

    missing_as_zero: Literal[False] = False
    interpolation: Literal["unavailable"] = "unavailable"
    measured_zero_preserved: Literal[True] = True

    aadf_admitted: Literal[False] = False
    webtris_admitted: Literal[False] = False
    webtris_blocker: Literal["GA-WT-1"] = "GA-WT-1"
    dft_hour_timezone_blocker: Literal["GA-DFT-1"] = "GA-DFT-1"

    split_unit: Literal["count_point_site"] = "count_point_site"
    split_rule: Literal["sha256_site_identity_v1"] = "sha256_site_identity_v1"
    split_salt: Literal["manchester-dft-temporal-profile-split-1.0"] = SPLIT_SALT
    held_out_basis_points: Literal[2000] = HELD_OUT_BASIS_POINTS
    minimum_partition_coverage: Decimal = Decimal("0.800")

    season_rule: Literal["meteorological_month_v1"] = "meteorological_month_v1"
    day_type_rule: Literal["iso_weekday_saturday_sunday_v1"] = "iso_weekday_saturday_sunday_v1"

    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False
    exploratory_candidate_software_evidence: Literal[True] = True

    @model_validator(mode="after")
    def validate_policy(self) -> DftTemporalProfilePolicy:
        if self.profile_hours != PROFILE_HOURS:
            raise ValueError("the declared profile window is fixed by this policy version")
        if self.simulation_origin_local_hour not in self.profile_hours:
            raise ValueError("the simulation origin must be inside the declared window")
        if not Decimal("0") < self.minimum_partition_coverage <= Decimal("1"):
            raise ValueError("minimum coverage must be a fraction above zero and at most one")
        return self

    def fingerprint(self) -> str:
        """Bind a profile to the exact policy that produced it."""

        return sha256_hex(self.canonical_json().encode("utf-8"))


class ProfileSourceBinding(DftTemporalProfileModel):
    """The exact snapshot a profile was built from, and what class it is.

    Without this a profile is just numbers: it could have come from any parse of
    anything. Binding the raw, manifest, receipt, and parser fingerprints makes
    "real Manchester evidence" a checkable claim rather than a label.

    ``evidence_class`` follows from ``synthetic`` and cannot be set against it.
    A synthetic fixture is a legitimate thing to build a profile from — the
    algorithm tests do exactly that — but it must say so, and it must not be
    able to dress itself as an accepted real snapshot.
    """

    snapshot_id: str = Field(min_length=1, max_length=200)
    dataset: Literal["raw_counts"] = "raw_counts"
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records_accepted: int = Field(ge=0)
    parser_status: ManchesterValidationState
    synthetic: bool
    evidence_class: EvidenceClass

    @model_validator(mode="after")
    def validate_binding(self) -> ProfileSourceBinding:
        expected: EvidenceClass = (
            "labelled_synthetic_fixture" if self.synthetic else "accepted_real_snapshot"
        )
        if self.evidence_class != expected:
            raise ValueError(
                "evidence_class must follow from the synthetic flag; a synthetic "
                "fixture can never present itself as an accepted real snapshot"
            )
        if self.parser_status == ManchesterValidationState.REJECTED:
            raise ValueError(
                "a profile cannot be based on a rejected parse; the rows behind a "
                "rejected report are not evidence of anything"
            )
        return self

    def lineage_fingerprint(self) -> str:
        """Digest the whole lineage, so two profiles can be compared exactly."""

        return sha256_hex(self.canonical_json().encode("utf-8"))


class ProfileHourCell(DftTemporalProfileModel):
    """One site-direction-date-hour cell, with missing kept distinct from zero."""

    local_clock_hour: int = Field(ge=0, le=23)
    simulation_second_start: int = Field(ge=0)
    simulation_second_end_exclusive: int = Field(ge=1)
    state: CellState
    all_motor_vehicles: int | None = Field(default=None, ge=0)
    #: True only when the source stated zero. Never true for an absent cell.
    measured_zero: bool = False

    @model_validator(mode="after")
    def validate_cell(self) -> ProfileHourCell:
        expected_start, expected_end = simulation_interval_for_hour(self.local_clock_hour)
        if (self.simulation_second_start, self.simulation_second_end_exclusive) != (
            expected_start,
            expected_end,
        ):
            raise ValueError("the simulation interval must follow from the local clock hour")
        if self.state == "observed":
            if self.all_motor_vehicles is None:
                raise ValueError("an observed cell must carry its measured value")
            if self.measured_zero != (self.all_motor_vehicles == 0):
                raise ValueError("measured_zero must follow from the measured value")
        else:
            if self.all_motor_vehicles is not None:
                raise ValueError("only an observed cell may carry a value; missing is never zero")
            if self.measured_zero:
                raise ValueError("an unobserved cell was never measured as zero")
        return self


class ProfileSeries(DftTemporalProfileModel):
    """One site, one direction, one survey date: the profile's grain.

    Season and day type are recorded because a later analysis will want them.
    They are attributes of the series, never keys it is aggregated over.
    """

    count_point_id: int = Field(ge=1)
    direction_of_travel: DirectionCode
    count_date: dt.date
    road_type: RoadType
    partition: Partition
    day_type: DayType
    season: Season
    cells: tuple[ProfileHourCell, ...] = Field(min_length=1)
    observed_cells: int = Field(ge=0)
    missing_cells: int = Field(ge=0)
    excluded_cells: int = Field(ge=0)
    measured_zero_cells: int = Field(ge=0)
    coverage: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_series(self) -> ProfileSeries:
        hours = [cell.local_clock_hour for cell in self.cells]
        if hours != sorted(hours) or len(set(hours)) != len(hours):
            raise ValueError("cells must be unique and ordered by local clock hour")
        if tuple(hours) != PROFILE_HOURS:
            raise ValueError("a series must cover the complete declared window")
        counted = {
            "observed": 0,
            "missing_no_row": 0,
            "excluded_null_value": 0,
            "excluded_conflicting_duplicate": 0,
        }
        for cell in self.cells:
            counted[cell.state] += 1
        if counted["observed"] != self.observed_cells:
            raise ValueError("observed_cells must match the cells")
        if counted["missing_no_row"] != self.missing_cells:
            raise ValueError("missing_cells must match the cells")
        excluded = counted["excluded_null_value"] + counted["excluded_conflicting_duplicate"]
        if excluded != self.excluded_cells:
            raise ValueError("excluded_cells must match the cells")
        if sum(1 for cell in self.cells if cell.measured_zero) != self.measured_zero_cells:
            raise ValueError("measured_zero_cells must match the cells")
        expected = _coverage(self.observed_cells, len(self.cells))
        if self.coverage != expected:
            raise ValueError("coverage must follow from observed cells over the declared window")
        return self


class ProfileExclusion(DftTemporalProfileModel):
    """One excluded **input row**, identified well enough to go and find it.

    Cell-level entries would be indistinguishable from one another when two
    rows are excluded from the same cell, which is exactly the case a reviewer
    most needs to inspect: a conflicting duplicate. Carrying the row's own
    identity and the member it came from makes each exclusion traceable back to
    a byte range in an accepted snapshot.
    """

    reason: ProfileExclusionReason
    count_point_id: int = Field(ge=0)
    direction_of_travel: str = Field(min_length=1, max_length=8)
    count_date: dt.date
    local_clock_hour: int = Field(ge=0, le=23)
    source_row_id: int = Field(ge=0)
    row_index: int = Field(ge=0)
    member_path: str = Field(min_length=1, max_length=300)
    member_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: The value the row carried, when it carried one. ``None`` is the whole
    #: reason a null row was excluded, so it stays visible rather than omitted.
    rejected_value: int | None = Field(default=None, ge=0)


class PartitionSummary(DftTemporalProfileModel):
    """Denominators for one side of the split, published rather than implied."""

    partition: Partition
    sites: int = Field(ge=0)
    series: int = Field(ge=0)
    expected_cells: int = Field(ge=0)
    observed_cells: int = Field(ge=0)
    missing_cells: int = Field(ge=0)
    excluded_cells: int = Field(ge=0)
    measured_zero_cells: int = Field(ge=0)
    coverage: Decimal = Field(ge=0, le=1)
    meets_minimum_coverage: bool

    @model_validator(mode="after")
    def validate_summary(self) -> PartitionSummary:
        if self.observed_cells + self.missing_cells + self.excluded_cells != self.expected_cells:
            raise ValueError("observed, missing, and excluded cells must account for the window")
        if self.coverage != _coverage(self.observed_cells, self.expected_cells):
            raise ValueError("coverage must follow from observed cells over expected cells")
        if self.measured_zero_cells > self.observed_cells:
            raise ValueError("measured zeros are a subset of observed cells")
        return self


class ManchesterDftTemporalProfile(DftTemporalProfileModel):
    """One complete DfT temporal-profile candidate, real or labelled synthetic.

    ``evidence_class`` says which, and every published summary is re-derived
    from the embedded series during validation rather than trusted, so a stored
    artifact cannot be edited into agreeing with itself.
    """

    schema_version: Literal["1.0"] = PROFILE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = PROFILE_CAPABILITY_ID
    method_version: Literal["manchester-dft-temporal-profile-1.0"] = PROFILE_METHOD_VERSION
    capability_status: Literal["planned"] = "planned"
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS

    policy: DftTemporalProfilePolicy
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: The exact accepted snapshot this rests on. Without it the artifact would
    #: call itself real Manchester evidence on no more than its own say-so.
    source: ProfileSourceBinding
    #: Mirrors the source, so a reader sees at the top level whether this is
    #: real evidence or a labelled synthetic fixture.
    evidence_class: EvidenceClass
    admission: ProfileAdmission

    series: tuple[ProfileSeries, ...] = Field(max_length=MAX_PROFILE_SERIES)
    exclusions: tuple[ProfileExclusion, ...] = ()
    partitions: tuple[PartitionSummary, ...] = Field(min_length=2, max_length=2)

    offered_rows: int = Field(ge=0)
    admitted_rows: int = Field(ge=0)
    excluded_rows: int = Field(ge=0)
    sites_total: int = Field(ge=0)
    series_total: int = Field(ge=0)
    expected_cells: int = Field(ge=0)
    observed_cells: int = Field(ge=0)
    missing_cells: int = Field(ge=0)
    measured_zero_cells: int = Field(ge=0)
    coverage: Decimal = Field(ge=0, le=1)

    #: What this artifact is not, fixed structurally rather than in prose.
    utc_instant_available: Literal[False] = False
    calibration_use_available: Literal[False] = False
    sumo_demand_available: Literal[False] = False
    baseline_available: Literal[False] = False
    aadf_fused: Literal[False] = False
    webtris_included: Literal[False] = False
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False
    exploratory_candidate_software_evidence: Literal[True] = True

    @model_validator(mode="after")
    def validate_profile(self) -> ManchesterDftTemporalProfile:
        if self.policy_fingerprint != self.policy.fingerprint():
            raise ValueError("policy fingerprint does not match the embedded policy")
        if self.offered_rows != self.admitted_rows + self.excluded_rows:
            raise ValueError("admitted and excluded rows must account for every offered row")
        if len(self.exclusions) != self.excluded_rows:
            raise ValueError("the exclusion ledger must carry one entry per excluded row")
        if self.source.records_accepted != self.offered_rows:
            raise ValueError(
                "the bound snapshot's accepted-record count must equal the rows offered; "
                "a profile cannot rest on a snapshot it did not read in full"
            )
        if self.evidence_class != self.source.evidence_class:
            raise ValueError("the profile's evidence class must follow from its bound source")
        if len(self.series) != self.series_total:
            raise ValueError("series_total must match the published series")
        if {item.partition for item in self.partitions} != set(PARTITIONS):
            raise ValueError("both partitions must be summarised exactly once")
        # Every series must classify itself the way its own site and date
        # require. A forged label would put a road on the wrong side of the
        # split, or date it into the wrong season, while the totals still added
        # up.
        for item in self.series:
            if item.partition != partition_for_site(
                item.count_point_id, salt=self.policy.split_salt
            ):
                raise ValueError(
                    "a series' partition must follow from its site identity and the policy salt"
                )
            if item.day_type != day_type_for(item.count_date):
                raise ValueError("a series' day type must follow from its survey date")
            if item.season != season_for(item.count_date, self.policy.season_rule):
                raise ValueError("a series' season must follow from its survey date and policy")
        if self.sites_total != len({item.count_point_id for item in self.series}):
            raise ValueError("sites_total must be the distinct sites present in the series")
        # Recompute every partition summary from the series rather than trusting
        # the stored one. Otherwise a coherent forgery could move the coverage
        # gate and its denominators together and pass every arithmetic check.
        recomputed = tuple(
            _summarise_partition(partition, self.series, self.policy) for partition in PARTITIONS
        )
        published = {summary.partition: summary for summary in self.partitions}
        for derived in recomputed:
            if published[derived.partition] != derived:
                raise ValueError(
                    f"the published {derived.partition} summary does not match the one its "
                    "own series produce"
                )
        totals = {
            "expected": sum(item.expected_cells for item in self.partitions),
            "observed": sum(item.observed_cells for item in self.partitions),
            "missing": sum(item.missing_cells for item in self.partitions),
            "zero": sum(item.measured_zero_cells for item in self.partitions),
        }
        if totals["expected"] != self.expected_cells:
            raise ValueError("partition expected cells must account for the whole profile")
        if totals["observed"] != self.observed_cells:
            raise ValueError("partition observed cells must account for the whole profile")
        if totals["missing"] != self.missing_cells:
            raise ValueError("partition missing cells must account for the whole profile")
        if totals["zero"] != self.measured_zero_cells:
            raise ValueError("partition measured zeros must account for the whole profile")
        if self.coverage != _coverage(self.observed_cells, self.expected_cells):
            raise ValueError("coverage must follow from observed cells over expected cells")
        if self.admission != _admission(recomputed):
            raise ValueError("admission must follow from the recomputed partition coverage")
        return self

    def fingerprint_of_inputs(self) -> str:
        """Digest the exact lineage and content this profile rests on.

        Counts alone would collide: two different snapshots with the same row
        totals would fingerprint identically, and the digest would certify
        nothing. Binding the source snapshot's raw, manifest, receipt, and
        parser fingerprints together with the policy and the series content
        makes this identify *this* evidence and no other.
        """

        content = sha256_hex(
            "\n".join(item.canonical_json() for item in self.series).encode("utf-8")
        )
        return sha256_hex(
            "|".join(
                (
                    self.policy_fingerprint,
                    self.source.lineage_fingerprint(),
                    self.source.raw_fingerprint,
                    self.source.parser_report_fingerprint,
                    content,
                    str(self.offered_rows),
                    str(self.admitted_rows),
                    str(self.excluded_rows),
                    str(self.observed_cells),
                    str(self.expected_cells),
                )
            ).encode("utf-8")
        )

    def partition_summary(self, partition: Partition) -> PartitionSummary:
        for item in self.partitions:
            if item.partition == partition:
                return item
        raise DftTemporalProfileError(
            "PARTITION_ABSENT", f"no summary exists for partition {partition!r}"
        )


def _coverage(part: int, whole: int) -> Decimal:
    if whole <= 0:
        return Decimal("0")
    return (Decimal(part) / Decimal(whole)).quantize(_COVERAGE_QUANTUM)


def refuse_unadmitted_source(source_id: str) -> None:
    """Refuse any source this policy does not admit, naming its blocker.

    WebTRIS gets its own message because its exclusion is a *time* decision:
    its clock basis is undeclared under ``GA-WT-1``, and mixing an undeclared
    clock into an hourly profile produces rows that look comparable and are not.
    """

    if source_id == "webtris":
        raise DftTemporalProfileError(
            "WEBTRIS_CLOCK_BASIS_UNRESOLVED",
            "WebTRIS is excluded from the hourly profile while GA-WT-1 leaves its clock "
            "basis undeclared; an undeclared clock cannot be aligned to a local clock hour",
        )
    if source_id == "dft_aadf":
        raise DftTemporalProfileError(
            "AADF_IS_NOT_A_SURVEY_HOUR",
            "AADF is an annual average daily flow, a statistical estimate rather than a "
            "survey-hour observation; it is contextual evidence and is never fused into "
            "the hourly profile",
        )
    if source_id != "dft_raw_count":
        raise DftTemporalProfileError(
            "SOURCE_NOT_ADMITTED",
            f"the profile admits dft_raw_count only, not {source_id!r}",
        )


def _admit_record(
    record: DftRawCountRecord, scope: DftManchesterScope, source: ProfileSourceBinding
) -> None:
    """Refuse a record that is not an in-scope Manchester survey-hour count.

    The row must also come from the snapshot the profile claims to rest on.
    Without that check, real-looking lineage could be pinned onto rows from
    somewhere else entirely, which is the one way an artifact could call itself
    real Manchester evidence without being it.
    """

    kind = getattr(record, "evidence_kind", None)
    if kind != ADMITTED_EVIDENCE_KIND:
        raise DftTemporalProfileError(
            "EVIDENCE_KIND_NOT_ADMITTED",
            f"the profile admits {ADMITTED_EVIDENCE_KIND!r} rows only, not {kind!r}; "
            "AADF and other families are contextual and are never fused",
        )
    if getattr(record, "time_basis", None) != "local_clock_hour":
        raise DftTemporalProfileError(
            "TIME_BASIS_NOT_LOCAL_CLOCK_HOUR",
            "the profile is built on local clock hours and refuses any other basis",
        )
    # Both identifiers are checked. The ONS code and the numeric DfT id are two
    # independent statements of the same boundary, and a row agreeing with only
    # one of them is a row whose scope is in doubt.
    if record.ons_code != scope.ons_code:
        raise DftTemporalProfileError(
            "OUT_OF_SCOPE_LOCAL_AUTHORITY",
            f"row {record.count_point_id} carries ONS code {record.ons_code!r}, "
            f"not Manchester {scope.ons_code}",
        )
    if getattr(record, "local_authority_id", None) != scope.local_authority_id:
        raise DftTemporalProfileError(
            "OUT_OF_SCOPE_LOCAL_AUTHORITY",
            f"row {record.count_point_id} carries DfT local authority "
            f"{getattr(record, 'local_authority_id', None)!r}, not Manchester "
            f"{scope.local_authority_id}",
        )
    origin = getattr(record, "source", None)
    if origin is None or origin.snapshot_id != source.snapshot_id:
        raise DftTemporalProfileError(
            "ROW_SNAPSHOT_MISMATCH",
            f"row {record.count_point_id} came from snapshot "
            f"{getattr(origin, 'snapshot_id', None)!r}, not the bound "
            f"{source.snapshot_id!r}",
        )
    if origin.synthetic != source.synthetic:
        raise DftTemporalProfileError(
            "ROW_EVIDENCE_CLASS_MISMATCH",
            "a row's synthetic flag disagrees with the bound source, so the profile "
            "would misstate whether it rests on real or synthetic evidence",
        )


SeriesKey: TypeAlias = tuple[int, DirectionCode, dt.date]


def build_dft_temporal_profile(
    records: Sequence[DftRawCountRecord],
    source: ProfileSourceBinding,
    policy: DftTemporalProfilePolicy | None = None,
) -> ManchesterDftTemporalProfile:
    """Build a temporal-profile candidate from already-parsed raw counts.

    A pure transformation of completed evidence: no network access, no
    filesystem discovery, no wall clock, no subprocess.

    This builder works over **either** an accepted real snapshot or a labelled
    synthetic fixture, and says which in ``evidence_class``. It does not, and
    cannot, establish that evidence is real — only
    :func:`open_real_raw_count_evidence` does that, by refusing a synthetic
    snapshot at the accepted-storage boundary. Every row must agree with the
    bound source on both snapshot id and synthetic flag, so a real-looking
    binding cannot be pinned onto rows from anywhere else.
    """

    active = policy if policy is not None else DftTemporalProfilePolicy()
    if len(records) > MAX_PROFILE_OBSERVATIONS:
        raise DftTemporalProfileError(
            "PROFILE_OBSERVATIONS_UNBOUNDED",
            f"the profile admits at most {MAX_PROFILE_OBSERVATIONS} rows",
        )

    exclusions: list[ProfileExclusion] = []
    admitted_rows = 0
    # (site, direction, date) -> hour -> value, keeping conflicts visible.
    grouped: dict[SeriesKey, dict[int, list[DftRawCountRecord]]] = {}
    context: dict[SeriesKey, RoadType] = {}

    for record in records:
        _admit_record(record, active.scope, source)
        key: SeriesKey = (record.count_point_id, record.direction_of_travel, record.count_date)
        if record.hour not in active.profile_hours:
            exclusions.append(_exclusion_for(record, "hour_outside_declared_window"))
            continue
        context.setdefault(key, record.location.road_type)
        grouped.setdefault(key, {}).setdefault(record.hour, []).append(record)

    if len(grouped) > MAX_PROFILE_SERIES:
        raise DftTemporalProfileError(
            "PROFILE_SERIES_UNBOUNDED",
            f"the profile admits at most {MAX_PROFILE_SERIES} series",
        )

    series: list[ProfileSeries] = []
    for key in sorted(grouped):
        count_point_id, direction, count_date = key
        hours = grouped[key]
        cells: list[ProfileHourCell] = []
        for hour in active.profile_hours:
            start, end = simulation_interval_for_hour(hour)
            offered = hours.get(hour)
            resolution = _resolve_cell(offered)
            admitted_rows += resolution.admitted_rows
            # One ledger entry per excluded input row, each identifying the row
            # it came from, so the ledger length is the excluded-row count and
            # two exclusions from one cell stay distinguishable.
            exclusions.extend(_exclusion_for(row, reason) for row, reason in resolution.excluded)
            cells.append(
                ProfileHourCell(
                    local_clock_hour=hour,
                    simulation_second_start=start,
                    simulation_second_end_exclusive=end,
                    state=resolution.state,
                    all_motor_vehicles=resolution.value,
                    measured_zero=resolution.state == "observed" and resolution.value == 0,
                )
            )
        observed = sum(1 for cell in cells if cell.state == "observed")
        missing = sum(1 for cell in cells if cell.state == "missing_no_row")
        series.append(
            ProfileSeries(
                count_point_id=count_point_id,
                direction_of_travel=direction,
                count_date=count_date,
                road_type=context[key],
                partition=partition_for_site(count_point_id, salt=active.split_salt),
                day_type=day_type_for(count_date),
                season=season_for(count_date, active.season_rule),
                cells=tuple(cells),
                observed_cells=observed,
                missing_cells=missing,
                excluded_cells=len(cells) - observed - missing,
                measured_zero_cells=sum(1 for cell in cells if cell.measured_zero),
                coverage=_coverage(observed, len(cells)),
            )
        )

    partitions = tuple(_summarise_partition(partition, series, active) for partition in PARTITIONS)
    expected = sum(item.expected_cells for item in partitions)
    observed_total = sum(item.observed_cells for item in partitions)

    return ManchesterDftTemporalProfile(
        policy=active,
        policy_fingerprint=active.fingerprint(),
        source=source,
        evidence_class=source.evidence_class,
        admission=_admission(partitions),
        series=tuple(series),
        exclusions=tuple(exclusions),
        partitions=partitions,
        offered_rows=len(records),
        admitted_rows=admitted_rows,
        excluded_rows=len(records) - admitted_rows,
        sites_total=len({item.count_point_id for item in series}),
        series_total=len(series),
        expected_cells=expected,
        observed_cells=observed_total,
        missing_cells=sum(item.missing_cells for item in partitions),
        measured_zero_cells=sum(item.measured_zero_cells for item in partitions),
        coverage=_coverage(observed_total, expected),
    )


class CellResolution(NamedTuple):
    """One cell's outcome, with the input rows it admitted and excluded.

    Row counts are carried out of here rather than recomputed, because a null
    row sitting beside a real value is easy to lose: the cell is observed, but
    that null row was still an input row that did not contribute, and counting
    it as admitted would overstate the evidence behind the profile.
    """

    state: CellState
    value: int | None
    admitted_rows: int
    #: The exact rows excluded from this cell, so each keeps its own identity.
    excluded: tuple[tuple[DftRawCountRecord, ProfileExclusionReason], ...]


def _exclusion_for(record: DftRawCountRecord, reason: ProfileExclusionReason) -> ProfileExclusion:
    """Describe one excluded input row well enough to go and find it again."""

    return ProfileExclusion(
        reason=reason,
        count_point_id=record.count_point_id,
        direction_of_travel=record.direction_of_travel,
        count_date=record.count_date,
        local_clock_hour=record.hour,
        source_row_id=record.source_row_id,
        row_index=record.row_index,
        member_path=record.source.member_path,
        member_sha256=record.source.member_sha256,
        rejected_value=record.counts.all_motor_vehicles,
    )


def _resolve_cell(offered: list[DftRawCountRecord] | None) -> CellResolution:
    """Decide one cell's state from the rows the source supplied for it."""

    null_reason: ProfileExclusionReason = "null_all_motor_vehicles"
    conflict_reason: ProfileExclusionReason = "conflicting_duplicate_rows"
    if offered is None:
        return CellResolution("missing_no_row", None, 0, ())
    present = [row for row in offered if row.counts.all_motor_vehicles is not None]
    nulls: tuple[tuple[DftRawCountRecord, ProfileExclusionReason], ...] = tuple(
        (row, null_reason) for row in offered if row.counts.all_motor_vehicles is None
    )
    if not present:
        # The rows exist but state no value. A typed exclusion, never a zero:
        # the survey recorded no measurement, not a measurement of none.
        return CellResolution("excluded_null_value", None, 0, nulls)
    values = {row.counts.all_motor_vehicles for row in present}
    if len(values) > 1:
        # Two rows disagree about the same site, direction, date, and hour.
        # Neither is preferred; every row is excluded and every one keeps its
        # own identity, so the disagreement is inspectable rather than resolved.
        conflicting: tuple[tuple[DftRawCountRecord, ProfileExclusionReason], ...] = tuple(
            (row, conflict_reason) for row in present
        )
        return CellResolution("excluded_conflicting_duplicate", None, 0, conflicting + nulls)
    # Observed, but any null rows alongside are still excluded input rows.
    return CellResolution("observed", present[0].counts.all_motor_vehicles, len(present), nulls)


def _summarise_partition(
    partition: Partition,
    series: Sequence[ProfileSeries],
    policy: DftTemporalProfilePolicy,
) -> PartitionSummary:
    members = [item for item in series if item.partition == partition]
    expected = sum(len(item.cells) for item in members)
    observed = sum(item.observed_cells for item in members)
    coverage = _coverage(observed, expected)
    return PartitionSummary(
        partition=partition,
        sites=len({item.count_point_id for item in members}),
        series=len(members),
        expected_cells=expected,
        observed_cells=observed,
        missing_cells=sum(item.missing_cells for item in members),
        excluded_cells=sum(item.excluded_cells for item in members),
        measured_zero_cells=sum(item.measured_zero_cells for item in members),
        coverage=coverage,
        # Gated on the exact integer ratio, never on the published six-place
        # figure. A partition at 7999/10000 displays as 0.799900 but one at
        # 79999/100000 would round to 0.800000 and be admitted on a display
        # artefact. Cross-multiplying keeps the comparison exact.
        meets_minimum_coverage=bool(members)
        and observed * policy.minimum_partition_coverage.as_integer_ratio()[1]
        >= expected * policy.minimum_partition_coverage.as_integer_ratio()[0],
    )


def _admission(partitions: Sequence[PartitionSummary]) -> ProfileAdmission:
    if not all(item.series for item in partitions):
        return "not_admitted_empty_partition"
    if all(item.meets_minimum_coverage for item in partitions):
        return "admitted_candidate"
    return "not_admitted_insufficient_coverage"


class ProfileServiceStatus(DftTemporalProfileModel):
    """Read-only status a UI renders without fetching or computing anything.

    The profile is built by an operator-invoked CLI over accepted local
    snapshots. A page reads this; it never acquires, and an ordinary rerun
    therefore cannot reach the provider.
    """

    schema_version: Literal["1.0"] = PROFILE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = PROFILE_CAPABILITY_ID
    capability_status: Literal["planned"] = "planned"
    practical_state: Literal["foundation_only"] = "foundation_only"
    policy_id: Literal["manchester-dft-temporal-profile-owner-candidate-1.0"] = PROFILE_POLICY_ID
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_available: bool
    #: Real or synthetic, surfaced where a reader will actually look.
    evidence_class: EvidenceClass | None = None
    admission: ProfileAdmission | None = None
    sites_total: int = Field(ge=0)
    series_total: int = Field(ge=0)
    coverage: Decimal | None = Field(default=None, ge=0, le=1)
    unavailable_reasons: tuple[str, ...]
    performs_network_access: Literal[False] = False
    performs_acquisition: Literal[False] = False
    utc_instant_available: Literal[False] = False
    calibration_use_available: Literal[False] = False


def profile_service_status(
    profile: ManchesterDftTemporalProfile | None,
    policy: DftTemporalProfilePolicy | None = None,
) -> ProfileServiceStatus:
    """Summarise an already-built profile for display. Never builds one."""

    active = policy if policy is not None else (profile.policy if profile else None)
    resolved = active if active is not None else DftTemporalProfilePolicy()
    reasons = [
        "The DfT hour is a local clock label under ADR-055; GA-DFT-1 leaves its "
        "timezone undeclared, so no UTC instant is available.",
        "07:00 local maps to simulation second zero as a declared modelling "
        "convention, not as a discovered instant.",
        "AADF is contextual annual evidence and is never fused into this profile.",
        "WebTRIS is excluded while GA-WT-1 leaves its clock basis unresolved.",
        "No calibration objective is approved, so this profile cannot become "
        "SUMO demand or a baseline.",
    ]
    if profile is None:
        reasons.insert(0, "No temporal profile has been built in this workspace.")
    return ProfileServiceStatus(
        policy_fingerprint=resolved.fingerprint(),
        profile_available=profile is not None,
        evidence_class=profile.evidence_class if profile else None,
        admission=profile.admission if profile else None,
        sites_total=profile.sites_total if profile else 0,
        series_total=profile.series_total if profile else 0,
        coverage=profile.coverage if profile else None,
        unavailable_reasons=tuple(reasons),
    )


def open_real_raw_count_evidence(
    workspace_root: str | Path, snapshot_id: str
) -> tuple[tuple[DftRawCountRecord, ...], ProfileSourceBinding]:
    """Open one accepted raw-counts snapshot as real evidence, with its lineage.

    Goes through the existing ``open_accepted_dft_snapshot`` boundary rather
    than reading a directory the caller names: that boundary already verifies
    the manifest, receipt, and raw tree, and it returns the fingerprints this
    profile has to bind itself to.

    Two admissions are enforced here and nowhere else is enough. The dataset
    must be ``raw_counts``, because count points and AADF are different
    evidence families. And ``synthetic`` must be false: an artifact that calls
    itself a *real* Manchester profile while resting on labelled-synthetic rows
    would be the single most misleading thing this module could produce.
    """

    load = open_accepted_dft_snapshot(workspace_root, snapshot_id)
    summary = load.summary
    if summary.dataset != "raw_counts":
        raise DftTemporalProfileError(
            "DATASET_NOT_RAW_COUNTS",
            f"the profile is built from raw_counts only, not {summary.dataset!r}; "
            "count points are reference geometry and AADF is contextual annual evidence",
        )
    if summary.synthetic:
        raise DftTemporalProfileError(
            "SYNTHETIC_EVIDENCE_REFUSED",
            "this snapshot is labelled synthetic, so it cannot produce a real Manchester "
            "temporal profile; synthetic fixtures never become real evidence",
        )
    records = tuple(
        record for record in load.report.records if isinstance(record, DftRawCountRecord)
    )
    if len(records) != len(load.report.records):
        raise DftTemporalProfileError(
            "UNEXPECTED_RECORD_FAMILY",
            "the accepted raw-counts snapshot yielded a record that is not a survey-hour count",
        )
    binding = ProfileSourceBinding(
        snapshot_id=summary.snapshot_id,
        dataset=summary.dataset,
        raw_fingerprint=summary.raw_fingerprint,
        manifest_fingerprint=summary.manifest_fingerprint,
        snapshot_receipt_fingerprint=summary.snapshot_receipt_fingerprint,
        parser_report_fingerprint=summary.parser_report_fingerprint,
        records_accepted=summary.records_accepted,
        parser_status=summary.parser_status,
        synthetic=False,
        evidence_class="accepted_real_snapshot",
    )
    return records, binding


def write_profile_record(target: str | Path, profile: ManchesterDftTemporalProfile) -> Path:
    """Persist one profile atomically, within the bound the reader will accept.

    Mirrors the connectivity record's boundary. Refusing an oversized payload
    before writing matters here for a specific reason: ``profile inspect``
    refuses anything past the same bound, so a build that wrote past it would
    leave an artifact its own CLI could never read back.

    A symlink is refused even when the caller asked to overwrite: following one
    would write through to a path the operator did not name.
    """

    destination = Path(target)
    if destination.is_symlink():
        raise DftTemporalProfileError(
            "PROFILE_OUTPUT_SYMLINK",
            "the profile output path is a symlink, which is refused rather than followed",
        )
    payload = profile.canonical_json().encode("utf-8")
    if len(payload) > MAX_PROFILE_ARTIFACT_BYTES:
        raise DftTemporalProfileError(
            "PROFILE_ARTIFACT_OVERSIZED",
            f"the profile serialises to {len(payload)} bytes, beyond the "
            f"{MAX_PROFILE_ARTIFACT_BYTES}-byte bound that `profile inspect` admits, "
            "so it is not written",
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def summarise_hours_present(records: Iterable[DftRawCountRecord]) -> Mapping[int, int]:
    """Count rows per local clock hour, for measuring a window rather than assuming one."""

    counts: dict[int, int] = {}
    for record in records:
        counts[record.hour] = counts.get(record.hour, 0) + 1
    return dict(sorted(counts.items()))


__all__ = [
    "ADMITTED_EVIDENCE_KIND",
    "HELD_OUT_BASIS_POINTS",
    "MAX_PROFILE_ARTIFACT_BYTES",
    "INTERVAL_SECONDS",
    "PARTITIONS",
    "PROFILE_HOURS",
    "PROFILE_MEASURE",
    "PROFILE_POLICY_ID",
    "SIMULATION_ORIGIN_LOCAL_HOUR",
    "SPLIT_SALT",
    "CellState",
    "DftTemporalProfileError",
    "DftTemporalProfilePolicy",
    "EvidenceClass",
    "ManchesterDftTemporalProfile",
    "Partition",
    "PartitionSummary",
    "ProfileExclusion",
    "ProfileHourCell",
    "ProfileSeries",
    "ProfileServiceStatus",
    "ProfileSourceBinding",
    "build_dft_temporal_profile",
    "open_real_raw_count_evidence",
    "partition_for_site",
    "profile_service_status",
    "refuse_unadmitted_source",
    "simulation_interval_for_hour",
    "summarise_hours_present",
    "write_profile_record",
]
