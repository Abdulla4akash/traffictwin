"""Typed EXP-03 synthetic measurement-imperfection contracts."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MEASUREMENT_MODEL_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MEASUREMENT_MODEL_VERSION: Literal["1.0"] = "1.0"
MAX_MEASUREMENT_RANDOM_SEED = 2_147_483_647
MAX_MEASUREMENT_DROPOUT_FRACTION = 0.95


class MeasurementModel(BaseModel):
    """Strict base for measurement-model inputs and audit artifacts."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class MeasurementDistribution(StrEnum):
    """Closed distributions implemented by EXP-03 v1.0."""

    BOUNDED_UNIFORM = "bounded_uniform"


class MeasurementTableKind(StrEnum):
    """Synthetic observation streams admitted for row dropout."""

    INFRA_STATE = "infra_state"
    VEHICLE_STATE = "vehicle_state"
    TRAFFIC_OBS = "traffic_obs"


class SyntheticMeasurementImpairmentConfig(MeasurementModel):
    """Bounded deterministic measurement-noise and row-dropout inputs."""

    schema_version: Literal["1.0"] = MEASUREMENT_MODEL_SCHEMA_VERSION
    model_version: Literal["1.0"] = MEASUREMENT_MODEL_VERSION
    distribution: Literal[MeasurementDistribution.BOUNDED_UNIFORM] = (
        MeasurementDistribution.BOUNDED_UNIFORM
    )
    random_seed: int = Field(default=17, ge=0, le=MAX_MEASUREMENT_RANDOM_SEED)
    vehicle_position_max_error_m: float = Field(default=0.0, ge=0.0, le=100.0)
    vehicle_speed_max_error_mps: float = Field(default=0.0, ge=0.0, le=20.0)
    traffic_speed_max_error_mps: float = Field(default=0.0, ge=0.0, le=20.0)
    traffic_count_max_error: int = Field(default=0, ge=0, le=100)
    infrastructure_utilisation_max_error: float = Field(default=0.0, ge=0.0, le=0.5)
    infrastructure_queue_max_error: int = Field(default=0, ge=0, le=100)
    row_dropout_fraction_by_table: dict[MeasurementTableKind, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_active_and_dropout_bounds(self) -> SyntheticMeasurementImpairmentConfig:
        invalid = [
            table.value
            for table, fraction in self.row_dropout_fraction_by_table.items()
            if fraction < 0.0 or fraction > MAX_MEASUREMENT_DROPOUT_FRACTION
        ]
        if invalid:
            raise ValueError(
                "row dropout fractions must be between 0 and "
                f"{MAX_MEASUREMENT_DROPOUT_FRACTION:.2f}: {', '.join(sorted(invalid))}"
            )
        if not self.active:
            raise ValueError("measurement impairment configuration must enable noise or dropout")
        return self

    @property
    def active(self) -> bool:
        """Return whether any declared measurement impairment is non-zero."""

        return any(
            value > 0
            for value in (
                self.vehicle_position_max_error_m,
                self.vehicle_speed_max_error_mps,
                self.traffic_speed_max_error_mps,
                self.traffic_count_max_error,
                self.infrastructure_utilisation_max_error,
                self.infrastructure_queue_max_error,
                *self.row_dropout_fraction_by_table.values(),
            )
        )

    def fingerprint(self) -> str:
        """Return a stable identity for every declared model parameter."""

        return _fingerprint(self.model_dump(mode="json"))


class MeasurementFieldAudit(MeasurementModel):
    """Observed bounds for one enabled measurement-noise field."""

    table_kind: MeasurementTableKind
    field: str
    unit: str
    maximum_absolute_error: float = Field(gt=0)
    eligible_rows: int = Field(ge=0)
    perturbed_rows: int = Field(ge=0)
    minimum_applied_error: float | None = None
    maximum_applied_error: float | None = None
    clamp_minimum: float | None = None
    clamp_maximum: float | None = None

    @model_validator(mode="after")
    def validate_counts_and_bounds(self) -> MeasurementFieldAudit:
        if self.perturbed_rows > self.eligible_rows:
            raise ValueError("perturbed_rows must not exceed eligible_rows")
        for value in (self.minimum_applied_error, self.maximum_applied_error):
            if value is not None and abs(value) > self.maximum_absolute_error + 1e-9:
                raise ValueError("applied measurement error exceeds its declared bound")
        if (
            self.minimum_applied_error is not None
            and self.maximum_applied_error is not None
            and self.minimum_applied_error > self.maximum_applied_error
        ):
            raise ValueError("minimum_applied_error must not exceed maximum_applied_error")
        return self


class MeasurementDropoutAudit(MeasurementModel):
    """Exact count and selection identity for one observation-stream dropout."""

    table_kind: MeasurementTableKind
    requested_fraction: float = Field(gt=0, le=MAX_MEASUREMENT_DROPOUT_FRACTION)
    rows_before: int = Field(ge=0)
    rows_dropped: int = Field(ge=0)
    rows_retained: int = Field(ge=0)
    selection_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_row_reconciliation(self) -> MeasurementDropoutAudit:
        if self.rows_before != self.rows_dropped + self.rows_retained:
            raise ValueError("dropout row counts do not reconcile")
        if self.rows_before > 0 and self.rows_retained < 1:
            raise ValueError("measurement dropout must retain at least one observation")
        return self


class SyntheticMeasurementImpairmentAudit(MeasurementModel):
    """Machine-readable measurement model embedded in a synthetic bundle manifest."""

    schema_version: Literal["1.0"] = MEASUREMENT_MODEL_SCHEMA_VERSION
    model_version: Literal["1.0"] = MEASUREMENT_MODEL_VERSION
    configuration: SyntheticMeasurementImpairmentConfig
    configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    field_audits: list[MeasurementFieldAudit] = Field(default_factory=list)
    dropout_audits: list[MeasurementDropoutAudit] = Field(default_factory=list)
    audit_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    synthetic_evaluation: Literal[True] = True
    calibrated_sensor_model: Literal[False] = False
    raw_source_mutated: Literal[False] = False
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contract_and_fingerprints(self) -> SyntheticMeasurementImpairmentAudit:
        expected_fields = _expected_field_audits(self.configuration)
        actual_fields = {(item.table_kind, item.field): item for item in self.field_audits}
        if len(actual_fields) != len(self.field_audits):
            raise ValueError("measurement field audits must not contain duplicate fields")
        if set(actual_fields) != set(expected_fields):
            raise ValueError("measurement field audits do not match the enabled noise parameters")
        for key, (unit, maximum, clamp_minimum, clamp_maximum) in expected_fields.items():
            item = actual_fields[key]
            if (
                item.unit != unit
                or abs(item.maximum_absolute_error - maximum) > 1e-9
                or item.clamp_minimum != clamp_minimum
                or item.clamp_maximum != clamp_maximum
            ):
                raise ValueError(
                    "measurement field audit semantics do not match the enabled noise parameter"
                )

        expected_dropout = {
            table: fraction
            for table, fraction in self.configuration.row_dropout_fraction_by_table.items()
            if fraction > 0.0
        }
        actual_dropout = {item.table_kind: item for item in self.dropout_audits}
        if len(actual_dropout) != len(self.dropout_audits):
            raise ValueError("measurement dropout audits must not contain duplicate tables")
        if set(actual_dropout) != set(expected_dropout):
            raise ValueError("measurement dropout audits do not match the enabled dropout tables")
        for table, fraction in expected_dropout.items():
            dropout_item = actual_dropout[table]
            if abs(dropout_item.requested_fraction - fraction) > 1e-12:
                raise ValueError(
                    "measurement dropout audit fraction does not match its configuration"
                )

        eligible_by_table: dict[MeasurementTableKind, int] = {}
        for item in self.field_audits:
            previous = eligible_by_table.setdefault(item.table_kind, item.eligible_rows)
            if previous != item.eligible_rows:
                raise ValueError("measurement field eligible-row counts disagree within a table")
        for table, dropout_item in actual_dropout.items():
            eligible = eligible_by_table.get(table)
            if eligible is not None and eligible != dropout_item.rows_retained:
                raise ValueError(
                    "measurement field eligible rows must equal retained rows after dropout"
                )

        if self.configuration_fingerprint != self.configuration.fingerprint():
            raise ValueError("measurement configuration fingerprint does not match parameters")
        if self.audit_fingerprint != self.fingerprint():
            raise ValueError("measurement audit fingerprint does not match contents")
        return self

    def fingerprint(self) -> str:
        """Recompute the timestamp-free audit identity."""

        payload = self.model_dump(mode="json")
        payload["audit_fingerprint"] = ""
        return _fingerprint(payload)


class MeasurementImpairmentContract(MeasurementModel):
    """Public EXP-03 v1.0 capability and interpretation boundary."""

    schema_version: Literal["1.0"] = MEASUREMENT_MODEL_SCHEMA_VERSION
    model_version: Literal["1.0"] = MEASUREMENT_MODEL_VERSION
    distribution: Literal[MeasurementDistribution.BOUNDED_UNIFORM] = (
        MeasurementDistribution.BOUNDED_UNIFORM
    )
    supported_noise_fields: dict[MeasurementTableKind, list[str]]
    supported_dropout_tables: list[MeasurementTableKind]
    maximum_bounds: dict[str, float]
    maximum_dropout_fraction: float = MAX_MEASUREMENT_DROPOUT_FRACTION
    selection_policy: str
    clamp_policy: str
    direct_launch_supported: Literal[False] = False
    synthetic_only: Literal[True] = True
    calibrated_sensor_model: Literal[False] = False
    limitations: list[str]


def measurement_impairment_contract() -> MeasurementImpairmentContract:
    """Return the closed bounded EXP-03 model contract."""

    return MeasurementImpairmentContract(
        supported_noise_fields={
            MeasurementTableKind.INFRA_STATE: ["queue_length", "utilisation"],
            MeasurementTableKind.VEHICLE_STATE: ["x", "y", "speed"],
            MeasurementTableKind.TRAFFIC_OBS: ["count", "average_speed"],
        },
        supported_dropout_tables=list(MeasurementTableKind),
        maximum_bounds={
            "vehicle_position_max_error_m": 100.0,
            "vehicle_speed_max_error_mps": 20.0,
            "traffic_speed_max_error_mps": 20.0,
            "traffic_count_max_error": 100.0,
            "infrastructure_utilisation_max_error": 0.5,
            "infrastructure_queue_max_error": 100.0,
        },
        selection_policy=(
            "For each enabled non-empty table, drop an exact min(rows - 1, max(1, "
            "floor(rows * fraction))) stable SHA-256-ranked subset while retaining at least one "
            "generated observation row."
        ),
        clamp_policy=(
            "Counts, queues, and speeds clamp at zero; utilisation clamps to [0,1]; synthetic "
            "source-frame coordinates are not clamped."
        ),
        limitations=measurement_impairment_limitations(),
    )


def measurement_impairment_limitations() -> list[str]:
    """Return mandatory research-integrity limitations for EXP-03 artifacts."""

    return [
        "The bounded-uniform errors are deterministic software robustness fixtures, not a "
        "calibrated sensor, network, traffic, or physical-error model.",
        "Only generated infrastructure, vehicle, and traffic observation measurements are "
        "eligible; tasks, trips, incidents, timestamps, decisions, completion, and routing are "
        "unchanged.",
        "Dropout uses exact deterministic generated-row selection and retains at least one row; "
        "it is not a learned or empirical missingness process.",
        "Every output remains labelled synthetic/evaluation evidence and cannot establish "
        "external validity or real-world robustness.",
        "No configuration launches SUMO, Randy VEC/TOS, training, or another external simulator.",
    ]


def build_measurement_impairment_audit(
    configuration: SyntheticMeasurementImpairmentConfig,
    field_audits: list[MeasurementFieldAudit],
    dropout_audits: list[MeasurementDropoutAudit],
) -> SyntheticMeasurementImpairmentAudit:
    """Construct and fingerprint one complete deterministic impairment audit."""

    payload = {
        "schema_version": MEASUREMENT_MODEL_SCHEMA_VERSION,
        "model_version": MEASUREMENT_MODEL_VERSION,
        "configuration": configuration.model_dump(mode="json"),
        "configuration_fingerprint": configuration.fingerprint(),
        "field_audits": [item.model_dump(mode="json") for item in field_audits],
        "dropout_audits": [item.model_dump(mode="json") for item in dropout_audits],
        "audit_fingerprint": "",
        "synthetic_evaluation": True,
        "calibrated_sensor_model": False,
        "raw_source_mutated": False,
        "warnings": [
            "Synthetic measurement imperfections are controlled evaluation inputs, not real "
            "sensor observations or calibrated error distributions."
        ],
        "limitations": measurement_impairment_limitations(),
    }
    payload["audit_fingerprint"] = _fingerprint(payload)
    return SyntheticMeasurementImpairmentAudit.model_validate(payload)


def _expected_field_audits(
    configuration: SyntheticMeasurementImpairmentConfig,
) -> dict[
    tuple[MeasurementTableKind, str],
    tuple[str, float, float | None, float | None],
]:
    expected: dict[
        tuple[MeasurementTableKind, str],
        tuple[str, float, float | None, float | None],
    ] = {}
    if configuration.vehicle_position_max_error_m > 0.0:
        for field in ("x", "y"):
            expected[(MeasurementTableKind.VEHICLE_STATE, field)] = (
                "m",
                configuration.vehicle_position_max_error_m,
                None,
                None,
            )
    if configuration.vehicle_speed_max_error_mps > 0.0:
        expected[(MeasurementTableKind.VEHICLE_STATE, "speed")] = (
            "m/s",
            configuration.vehicle_speed_max_error_mps,
            0.0,
            None,
        )
    if configuration.traffic_speed_max_error_mps > 0.0:
        expected[(MeasurementTableKind.TRAFFIC_OBS, "average_speed")] = (
            "m/s",
            configuration.traffic_speed_max_error_mps,
            0.0,
            None,
        )
    if configuration.traffic_count_max_error > 0:
        expected[(MeasurementTableKind.TRAFFIC_OBS, "count")] = (
            "count",
            float(configuration.traffic_count_max_error),
            0.0,
            None,
        )
    if configuration.infrastructure_utilisation_max_error > 0.0:
        expected[(MeasurementTableKind.INFRA_STATE, "utilisation")] = (
            "fraction",
            configuration.infrastructure_utilisation_max_error,
            0.0,
            1.0,
        )
    if configuration.infrastructure_queue_max_error > 0:
        expected[(MeasurementTableKind.INFRA_STATE, "queue_length")] = (
            "count",
            float(configuration.infrastructure_queue_max_error),
            0.0,
            None,
        )
    return expected


def stable_measurement_fingerprint(payload: object) -> str:
    """Expose a stable hash helper for deterministic row selection/application."""

    return _fingerprint(payload)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
