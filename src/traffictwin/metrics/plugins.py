"""Trusted local custom-metric contracts, registry, and isolated execution."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.canonical.records import (
    CanonicalRecord,
    IncidentRecord,
    InfrastructureRecord,
    TaskRecord,
    TrafficObservationRecord,
    TripRecord,
    VehicleStateRecord,
)
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.definitions import MetricDefinition, MetricDomain
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    JsonObject,
    JsonScalar,
    JsonValue,
    MetricStatus,
    MetricValue,
    RunMetricContext,
    UnavailableReason,
)

PLUGIN_CONTRACT_VERSION: Literal["1.0"] = "1.0"
PLUGIN_API_VERSION: Literal["1.0"] = "1.0"


class PluginContractModel(BaseModel):
    """Strict base model for custom-metric artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CanonicalTableName(StrEnum):
    """Canonical tables that a trusted metric may declare as input."""

    TASKS = "tasks"
    INFRASTRUCTURE = "infrastructure"
    VEHICLES = "vehicles"
    TRAFFIC = "traffic"
    TRIPS = "trips"
    INCIDENTS = "incidents"


class PluginRowPolicy(StrEnum):
    """How missing declared fields affect plugin admission and row lineage."""

    REQUIRE_COMPLETE = "require_complete"
    DROP_INCOMPLETE = "drop_incomplete"


class PluginOutputKind(StrEnum):
    """Supported closed output shapes."""

    SCALAR = "scalar"
    GROUPED = "grouped"


class PluginScalarType(StrEnum):
    """Supported JSON scalar types."""

    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"


_TABLE_MODELS: dict[CanonicalTableName, type[CanonicalRecord]] = {
    CanonicalTableName.TASKS: TaskRecord,
    CanonicalTableName.INFRASTRUCTURE: InfrastructureRecord,
    CanonicalTableName.VEHICLES: VehicleStateRecord,
    CanonicalTableName.TRAFFIC: TrafficObservationRecord,
    CanonicalTableName.TRIPS: TripRecord,
    CanonicalTableName.INCIDENTS: IncidentRecord,
}

_TABLE_TIME_ANCHORS: dict[CanonicalTableName, str] = {
    CanonicalTableName.TASKS: "arrival_time_s",
    CanonicalTableName.INFRASTRUCTURE: "timestamp_s",
    CanonicalTableName.VEHICLES: "timestamp_s",
    CanonicalTableName.TRAFFIC: "timestamp_s",
    CanonicalTableName.TRIPS: "departure_time_s",
    CanonicalTableName.INCIDENTS: "timestamp_s",
}


class PluginTableRequirement(PluginContractModel):
    """One declared canonical input and its deterministic availability rule."""

    table: CanonicalTableName
    required_fields: list[str] = Field(default_factory=list)
    row_policy: PluginRowPolicy = PluginRowPolicy.REQUIRE_COMPLETE
    minimum_eligible_rows: int = Field(default=1, ge=1)
    required_evidence_status: Literal["available"] = "available"

    @field_validator("required_fields")
    @classmethod
    def validate_required_fields(cls, fields: list[str]) -> list[str]:
        if len(fields) != len(set(fields)):
            raise ValueError("plugin required_fields must be unique")
        return sorted(fields)

    @model_validator(mode="after")
    def validate_fields_exist(self) -> PluginTableRequirement:
        known = _TABLE_MODELS[self.table].model_fields
        unknown = sorted(set(self.required_fields) - set(known))
        if unknown:
            raise ValueError(
                f"unknown canonical fields for {self.table.value}: {', '.join(unknown)}"
            )
        return self


class PluginOutputSchema(PluginContractModel):
    """Closed JSON output contract validated after every plugin execution."""

    kind: PluginOutputKind
    scalar_type: PluginScalarType
    allow_null_group_values: bool = False
    minimum_group_count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_shape_options(self) -> PluginOutputSchema:
        if self.kind is PluginOutputKind.SCALAR and self.allow_null_group_values:
            raise ValueError("scalar plugin output cannot allow null group values")
        return self


class PluginMetricContract(PluginContractModel):
    """Complete admission contract for one trusted deterministic metric function."""

    schema_version: Literal["1.0"] = PLUGIN_CONTRACT_VERSION
    plugin_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    plugin_version: str = Field(min_length=1, max_length=64)
    definition: MetricDefinition
    inputs: list[PluginTableRequirement] = Field(min_length=1)
    output_schema: PluginOutputSchema
    trust_boundary: Literal["trusted_local_code"] = "trusted_local_code"
    determinism_contract: Literal["repeatable_pure_function_v1"] = "repeatable_pure_function_v1"
    unavailable_behavior: Literal["explicit_null_reason_v1"] = "explicit_null_reason_v1"
    provenance_mapping: Literal["declared_input_rows_v1"] = "declared_input_rows_v1"

    @model_validator(mode="after")
    def validate_contract_alignment(self) -> PluginMetricContract:
        expected_prefix = f"plugin.{self.plugin_id}."
        if not self.definition.key.startswith(expected_prefix):
            raise ValueError(f"plugin metric key must start with {expected_prefix}")
        if self.definition.domain is not MetricDomain.CUSTOM:
            raise ValueError("plugin metric domain must be custom")
        tables = [requirement.table.value for requirement in self.inputs]
        if len(tables) != len(set(tables)):
            raise ValueError("plugin input tables must be unique")
        if set(self.definition.required_tables) != set(tables):
            raise ValueError("metric definition required_tables must exactly match plugin inputs")
        if len(self.definition.required_tables) != len(set(self.definition.required_tables)):
            raise ValueError("metric definition required_tables must be unique")
        expected_fields = {
            requirement.table.value: requirement.required_fields
            for requirement in self.inputs
            if requirement.required_fields
        }
        actual_fields = {
            table: sorted(fields)
            for table, fields in self.definition.required_fields.items()
            if fields
        }
        if actual_fields != expected_fields:
            raise ValueError("metric definition required_fields must exactly match plugin inputs")
        if self.definition.time_window_applicable:
            allowed_anchors = {
                f"{requirement.table.value}.{_TABLE_TIME_ANCHORS[requirement.table]}"
                for requirement in self.inputs
            }
            if self.definition.time_anchor not in allowed_anchors:
                raise ValueError(
                    "window-applicable plugin metric must use a canonical input time anchor"
                )
        elif self.definition.time_anchor is not None:
            raise ValueError("non-windowed plugin metric cannot declare a time anchor")
        return self

    def fingerprint(self) -> str:
        """Return a stable fingerprint over the complete contract."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PluginMetricResult(PluginContractModel):
    """Plugin-authored payload before the engine supplies ordinary metric provenance."""

    status: MetricStatus = MetricStatus.AVAILABLE
    value: JsonValue = None
    dimensions: dict[str, JsonScalar] = Field(default_factory=dict)
    missing_evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_status_and_value(self) -> PluginMetricResult:
        if self.status is MetricStatus.INVALID:
            raise ValueError("plugins cannot declare invalid source data")
        if self.status is MetricStatus.UNAVAILABLE:
            if self.value is not None:
                raise ValueError("unavailable plugin result must have a null value")
            if not self.missing_evidence:
                raise ValueError("unavailable plugin result must declare missing evidence")
        elif self.value is None:
            raise ValueError("available or partial plugin result must have a value")
        return self


@dataclass(frozen=True)
class PluginMetricInput:
    """Bounded canonical input passed to trusted plugin code."""

    tables: CanonicalTables
    run_context: RunMetricContext
    engine_config: MetricEngineConfig


MetricPluginFunction: TypeAlias = Callable[[PluginMetricInput], PluginMetricResult]


@dataclass(frozen=True)
class RegisteredMetricPlugin:
    """One admitted contract/callable pair."""

    contract: PluginMetricContract
    compute: MetricPluginFunction


class MetricPluginRegistryError(ValueError):
    """Raised when a local metric extension cannot be admitted."""


class MetricPluginRegistryReport(PluginContractModel):
    """Deterministic inventory of an explicitly constructed plugin registry."""

    schema_version: Literal["1.0"] = PLUGIN_API_VERSION
    registry_fingerprint: str
    metric_count: int = Field(ge=0)
    contracts: list[PluginMetricContract]


class MetricPluginApiContract(PluginContractModel):
    """Machine-readable public boundary of the MET-06 extension API."""

    schema_version: Literal["1.0"] = PLUGIN_API_VERSION
    registration_mode: Literal["explicit_trusted_in_process"] = "explicit_trusted_in_process"
    dynamic_file_import: Literal[False] = False
    uploaded_code_execution: Literal[False] = False
    sandboxed_execution: Literal[False] = False
    determinism_verification_runs: Literal[2] = 2
    execution_failure_policy: Literal["isolate_as_unavailable"] = "isolate_as_unavailable"
    duplicate_key_policy: Literal["reject_before_evaluation"] = "reject_before_evaluation"
    provenance_policy: Literal["complete_declared_input_row_ledger"] = (
        "complete_declared_input_row_ledger"
    )
    supported_tables: list[CanonicalTableName]
    supported_output_kinds: list[PluginOutputKind]
    limitations: list[str]


class MetricPluginRegistry:
    """Explicit, trusted, in-process registry for custom deterministic metric functions."""

    def __init__(self) -> None:
        self._plugins: dict[str, RegisteredMetricPlugin] = {}

    def register(
        self,
        contract: PluginMetricContract,
        compute: MetricPluginFunction,
    ) -> None:
        """Validate and register one contract/callable pair before evaluation."""

        from traffictwin.metrics.catalogue import METRIC_DEFINITIONS

        key = contract.definition.key
        if key in METRIC_DEFINITIONS:
            raise MetricPluginRegistryError(f"plugin metric key collides with core metric: {key}")
        if key in self._plugins:
            raise MetricPluginRegistryError(f"duplicate plugin metric key: {key}")
        snapshot = PluginMetricContract.model_validate(contract.model_dump(mode="python"))
        key = snapshot.definition.key
        if not callable(compute):
            raise MetricPluginRegistryError("plugin compute object must be callable")
        versions = {
            plugin.contract.plugin_version
            for plugin in self._plugins.values()
            if plugin.contract.plugin_id == snapshot.plugin_id
        }
        if versions and versions != {snapshot.plugin_version}:
            raise MetricPluginRegistryError(
                f"plugin {snapshot.plugin_id} cannot register mixed plugin versions"
            )
        self._plugins[key] = RegisteredMetricPlugin(contract=snapshot, compute=compute)

    def registered(self) -> list[RegisteredMetricPlugin]:
        """Return admitted plugins in stable metric-key order."""

        return [
            RegisteredMetricPlugin(
                contract=self._plugins[key].contract.model_copy(deep=True),
                compute=self._plugins[key].compute,
            )
            for key in sorted(self._plugins)
        ]

    def window_applicable(self) -> MetricPluginRegistry:
        """Return an independent registry containing only anchored window metrics."""

        registry = MetricPluginRegistry()
        for plugin in self.registered():
            if plugin.contract.definition.time_window_applicable:
                registry.register(plugin.contract, plugin.compute)
        return registry

    def definitions(self) -> dict[str, MetricDefinition]:
        """Return admitted metric definitions in stable order."""

        return {
            plugin.contract.definition.key: plugin.contract.definition
            for plugin in self.registered()
        }

    def report(self) -> MetricPluginRegistryReport:
        """Return a stable registry inventory and fingerprint."""

        contracts = [plugin.contract for plugin in self.registered()]
        payload = json.dumps(
            [contract.model_dump(mode="json") for contract in contracts],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return MetricPluginRegistryReport(
            registry_fingerprint=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            metric_count=len(contracts),
            contracts=contracts,
        )

    def __len__(self) -> int:
        return len(self._plugins)


def metric_plugin_api_contract() -> MetricPluginApiContract:
    """Return the static public contract for trusted local metric extensions."""

    return MetricPluginApiContract(
        supported_tables=list(CanonicalTableName),
        supported_output_kinds=list(PluginOutputKind),
        limitations=[
            "Plugin code is trusted local Python and is not sandboxed.",
            "TrafficTwin does not load uploaded files or arbitrary module paths as metric code.",
            "Two equal results establish repeatability for the evaluated input, not a proof of "
            "global purity or scientific validity.",
            "Plugins receive only declared canonical input rows; they cannot read raw bundle files "
            "through this API.",
        ],
    )


def compute_plugin_metrics(
    registry: MetricPluginRegistry,
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    """Evaluate every admitted plugin independently with repeatability verification."""

    return [
        _compute_plugin(plugin, tables, context, evidence, config, computed_at)
        for plugin in registry.registered()
    ]


def invalid_plugin_metrics(
    registry: MetricPluginRegistry,
    context: RunMetricContext,
    computed_at: datetime,
) -> list[MetricValue]:
    """Represent every admitted plugin as invalid when source validation forbids analysis."""

    return [
        _metric_value(
            plugin.contract,
            context,
            computed_at,
            status=MetricStatus.INVALID,
            value=None,
            missing=["validation"],
            reasons=[UnavailableReason.INVALID_SOURCE_DATA],
            warnings=[],
            dimensions={},
            metadata=_plugin_metadata(
                plugin.contract,
                input_counts={},
                eligible_counts={},
                execution_attempted=False,
                determinism_verified=False,
                verification_runs=0,
            ),
        )
        for plugin in registry.registered()
    ]


def plugin_contract_from_metric(metric: MetricValue) -> PluginMetricContract | None:
    """Recover a validated embedded plugin contract from an ordinary metric result."""

    payload = metric.metadata.get("plugin_contract")
    if not isinstance(payload, dict):
        return None
    try:
        return PluginMetricContract.model_validate(payload)
    except ValueError:
        return None


def _compute_plugin(
    plugin: RegisteredMetricPlugin,
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> MetricValue:
    contract = plugin.contract
    prepared, input_counts, eligible_counts, missing = _prepare_inputs(contract, tables, evidence)
    base_metadata = _plugin_metadata(
        contract,
        input_counts=input_counts,
        eligible_counts=eligible_counts,
        execution_attempted=not missing,
        determinism_verified=False,
        verification_runs=0,
    )
    if missing:
        return _metric_value(
            contract,
            context,
            computed_at,
            status=MetricStatus.UNAVAILABLE,
            value=None,
            missing=missing,
            reasons=[UnavailableReason.PLUGIN_AVAILABILITY_REQUIREMENT_UNMET],
            warnings=[
                "The custom metric was not executed because its declared availability contract "
                "was not satisfied."
            ],
            dimensions={},
            metadata=base_metadata,
        )

    first, first_error = _invoke_plugin(plugin, prepared, context, config)
    if first_error is not None or first is None:
        return _plugin_failure_metric(
            contract,
            context,
            computed_at,
            UnavailableReason.PLUGIN_EXECUTION_FAILED,
            first_error or "PluginExecutionError",
            _plugin_metadata(
                contract,
                input_counts=input_counts,
                eligible_counts=eligible_counts,
                execution_attempted=True,
                determinism_verified=False,
                verification_runs=1,
            ),
        )
    second, second_error = _invoke_plugin(plugin, prepared, context, config)
    if second_error is not None or second is None:
        return _plugin_failure_metric(
            contract,
            context,
            computed_at,
            UnavailableReason.PLUGIN_NONDETERMINISTIC,
            second_error or "PluginRepeatabilityError",
            _plugin_metadata(
                contract,
                input_counts=input_counts,
                eligible_counts=eligible_counts,
                execution_attempted=True,
                determinism_verified=False,
                verification_runs=2,
            ),
        )
    try:
        first_payload = _canonical_plugin_result(first)
        second_payload = _canonical_plugin_result(second)
        if first_payload != second_payload:
            raise _PluginNonDeterministicError
        value = _validated_output_value(contract.output_schema, first)
    except _PluginNonDeterministicError:
        return _plugin_failure_metric(
            contract,
            context,
            computed_at,
            UnavailableReason.PLUGIN_NONDETERMINISTIC,
            "PluginResultMismatch",
            _plugin_metadata(
                contract,
                input_counts=input_counts,
                eligible_counts=eligible_counts,
                execution_attempted=True,
                determinism_verified=False,
                verification_runs=2,
            ),
        )
    except (TypeError, ValueError, OverflowError) as exc:
        return _plugin_failure_metric(
            contract,
            context,
            computed_at,
            UnavailableReason.PLUGIN_OUTPUT_INVALID,
            type(exc).__name__,
            _plugin_metadata(
                contract,
                input_counts=input_counts,
                eligible_counts=eligible_counts,
                execution_attempted=True,
                determinism_verified=False,
                verification_runs=2,
            ),
        )

    metadata = {
        **_plugin_metadata(
            contract,
            input_counts=input_counts,
            eligible_counts=eligible_counts,
            execution_attempted=True,
            determinism_verified=True,
            verification_runs=2,
        ),
        "plugin_output_metadata": first.metadata,
    }
    reasons = (
        [UnavailableReason.PLUGIN_DECLARED_UNAVAILABLE]
        if first.status is MetricStatus.UNAVAILABLE
        else []
    )
    return _metric_value(
        contract,
        context,
        computed_at,
        status=first.status,
        value=value,
        missing=first.missing_evidence,
        reasons=reasons,
        warnings=[
            *first.warnings,
            "Computed by explicitly registered trusted local code; repeatability was verified "
            "twice for this input, but plugin code is not sandboxed.",
        ],
        dimensions=first.dimensions,
        metadata=metadata,
    )


def _prepare_inputs(
    contract: PluginMetricContract,
    tables: CanonicalTables,
    evidence: EvidenceAvailability,
) -> tuple[CanonicalTables, dict[str, int], dict[str, int], list[str]]:
    prepared = CanonicalTables()
    input_counts: dict[str, int] = {}
    eligible_counts: dict[str, int] = {}
    missing: list[str] = []
    for requirement in contract.inputs:
        table = requirement.table.value
        records = list(getattr(tables, table))
        input_counts[table] = len(records)
        status = getattr(evidence, table)
        if status is not EvidenceStatus.AVAILABLE:
            eligible_counts[table] = 0
            missing.append(f"{table} evidence status available")
            continue
        complete_rows = [
            record for record in records if _fields_present(record, requirement.required_fields)
        ]
        if requirement.row_policy is PluginRowPolicy.REQUIRE_COMPLETE:
            eligible = records if len(complete_rows) == len(records) else []
            if len(complete_rows) != len(records):
                missing.append(f"complete {table} fields: {', '.join(requirement.required_fields)}")
        else:
            eligible = complete_rows
        eligible_counts[table] = len(eligible)
        if len(eligible) < requirement.minimum_eligible_rows:
            missing.append(f"{table} minimum eligible rows: {requirement.minimum_eligible_rows}")
        setattr(prepared, table, [record.model_copy(deep=True) for record in eligible])
    return prepared, input_counts, eligible_counts, sorted(set(missing))


def _invoke_plugin(
    plugin: RegisteredMetricPlugin,
    prepared: CanonicalTables,
    context: RunMetricContext,
    config: MetricEngineConfig,
) -> tuple[PluginMetricResult | None, str | None]:
    try:
        raw = plugin.compute(
            PluginMetricInput(
                tables=prepared.model_copy(deep=True),
                run_context=context.model_copy(deep=True),
                engine_config=config.model_copy(deep=True),
            )
        )
        return PluginMetricResult.model_validate(raw), None
    except Exception as exc:  # trusted extensions are isolated at the metric boundary
        return None, type(exc).__name__


def _validated_output_value(
    schema: PluginOutputSchema,
    result: PluginMetricResult,
) -> JsonValue:
    if result.status is MetricStatus.UNAVAILABLE:
        return None
    value = result.value
    if schema.kind is PluginOutputKind.SCALAR:
        _validate_scalar(value, schema.scalar_type)
        _assert_json(value)
        return value
    if not isinstance(value, dict):
        raise ValueError("grouped plugin output must be an object")
    if len(value) < schema.minimum_group_count:
        raise ValueError("grouped plugin output has too few groups")
    normalised: dict[str, JsonScalar] = {}
    for group, item in sorted(value.items()):
        if not isinstance(group, str) or not group:
            raise ValueError("plugin output group keys must be non-empty strings")
        if item is None:
            if not schema.allow_null_group_values or result.status is not MetricStatus.PARTIAL:
                raise ValueError("null group values require a partial result and explicit schema")
        else:
            _validate_scalar(item, schema.scalar_type)
        normalised[group] = item
    _assert_json(normalised)
    return normalised


def _validate_scalar(value: object, scalar_type: PluginScalarType) -> None:
    if scalar_type is PluginScalarType.NUMBER:
        if (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ValueError("plugin output must be a finite number")
    elif scalar_type is PluginScalarType.INTEGER:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("plugin output must be an integer")
    elif scalar_type is PluginScalarType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValueError("plugin output must be a boolean")
    elif not isinstance(value, str):
        raise ValueError("plugin output must be a string")


def _canonical_plugin_result(result: PluginMetricResult) -> str:
    return json.dumps(
        result.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _assert_json(value: object) -> None:
    json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fields_present(record: CanonicalRecord, fields: list[str]) -> bool:
    return all(getattr(record, field) is not None for field in fields)


def _plugin_failure_metric(
    contract: PluginMetricContract,
    context: RunMetricContext,
    computed_at: datetime,
    reason: UnavailableReason,
    failure_type: str,
    base_metadata: JsonObject,
) -> MetricValue:
    label = {
        UnavailableReason.PLUGIN_EXECUTION_FAILED: "execution failed",
        UnavailableReason.PLUGIN_NONDETERMINISTIC: "repeatability verification failed",
        UnavailableReason.PLUGIN_OUTPUT_INVALID: "output contract validation failed",
    }[reason]
    return _metric_value(
        contract,
        context,
        computed_at,
        status=MetricStatus.UNAVAILABLE,
        value=None,
        missing=[f"valid deterministic output from {contract.definition.key}"],
        reasons=[reason],
        warnings=[f"Custom metric {label}; the failure was isolated from all other metrics."],
        dimensions={},
        metadata={**base_metadata, "plugin_failure_type": failure_type},
    )


def _plugin_metadata(
    contract: PluginMetricContract,
    *,
    input_counts: dict[str, int],
    eligible_counts: dict[str, int],
    execution_attempted: bool,
    determinism_verified: bool,
    verification_runs: int,
) -> JsonObject:
    return {
        "plugin_id": contract.plugin_id,
        "plugin_version": contract.plugin_version,
        "plugin_contract_version": contract.schema_version,
        "plugin_contract_fingerprint": contract.fingerprint(),
        "plugin_contract": contract.model_dump(mode="json"),
        "plugin_input_record_counts": dict(sorted(input_counts.items())),
        "plugin_eligible_record_counts": dict(sorted(eligible_counts.items())),
        "plugin_execution_attempted": execution_attempted,
        "plugin_determinism_verification_runs": verification_runs,
        "plugin_determinism_verified": determinism_verified,
        "plugin_provenance_mapping": contract.provenance_mapping,
        "plugin_trust_boundary": contract.trust_boundary,
    }


def _metric_value(
    contract: PluginMetricContract,
    context: RunMetricContext,
    computed_at: datetime,
    *,
    status: MetricStatus,
    value: JsonValue,
    missing: list[str],
    reasons: list[UnavailableReason],
    warnings: list[str],
    dimensions: dict[str, JsonScalar],
    metadata: JsonObject,
) -> MetricValue:
    definition = contract.definition
    return MetricValue(
        metric_key=definition.key,
        status=status,
        value=value,
        unit=definition.unit,
        scope=definition.aggregation_scope.value,
        dimensions=dimensions,
        required_evidence=definition.required_tables,
        missing_evidence=missing,
        reason_codes=reasons,
        warnings=warnings,
        implementation_version=definition.implementation_version,
        run_id=context.run_id,
        experiment_id=context.experiment_id,
        seed_id=context.seed_id,
        algorithm=context.algorithm,
        checkpoint=context.checkpoint,
        random_seed=context.random_seed,
        synthetic=context.synthetic,
        environment=context.environment,
        environment_version=context.environment_version,
        environment_commit=context.environment_commit,
        computed_at=computed_at,
        metadata=metadata,
    )


class _PluginNonDeterministicError(RuntimeError):
    """Internal sentinel for unequal repeated plugin results."""
