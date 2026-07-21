"""Bounded deterministic parameter-sweep composition and local analysis.

The composer can expand supported ScenarioSeed or synthetic-generator fields.  It
only executes TrafficTwin's local synthetic bundle generator and ordinary
validation/metric engine.  External requests are metadata artifacts and are
always recorded as not executed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import shutil
import tempfile
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from enum import StrEnum
from itertools import product
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, field_validator, model_validator

from traffictwin.config.seed_io import write_seed
from traffictwin.domain.scenario import ScenarioSeed, StrictModel, _validate_identifier
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import JsonScalar, MetricStatus
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import SyntheticPolicyProfile, SyntheticScenarioConfig
from traffictwin.synthetic.generator import generate_run_data

PARAMETER_SWEEP_SCHEMA_VERSION: Literal["1.0"] = "1.0"
PARAMETER_SWEEP_METHOD_VERSION: Literal["1.0"] = "1.0"
MAX_SWEEP_AXES = 4
MAX_VALUES_PER_AXIS = 16
MAX_SWEEP_POINTS = 256
MAX_RESPONSE_METRICS = 16
MAX_LOCAL_ESTIMATED_ROWS = 2_000_000


class ParameterSweepMode(StrEnum):
    """Supported sweep materialisation modes."""

    SEED_SNAPSHOTS = "seed_snapshots"
    LOCAL_SYNTHETIC_BUNDLES = "local_synthetic_bundles"
    EXTERNAL_RUN_REQUESTS = "external_run_requests"


class SweepParameter(StrEnum):
    """Closed v1 parameter catalogue.

    Mix-valued fields are deliberately absent because independently sweeping one
    share would violate the declared sum-to-one contract.
    """

    SYNTHETIC_DURATION_S = "synthetic.duration_s"
    SYNTHETIC_SAMPLING_INTERVAL_S = "synthetic.sampling_interval_s"
    SYNTHETIC_VEHICLE_COUNT = "synthetic.vehicle_count"
    SYNTHETIC_TASK_ARRIVAL_RATE = "synthetic.task_arrival_rate"
    SYNTHETIC_RSU_COUNT = "synthetic.rsu_count"
    SYNTHETIC_RSU_CAPACITY = "synthetic.rsu_capacity"
    SYNTHETIC_NETWORK_DELAY_MS = "synthetic.baseline_network_delay_ms"
    SYNTHETIC_CONGESTION_MULTIPLIER = "synthetic.congestion_multiplier"
    SYNTHETIC_POLICY_BEHAVIOR = "synthetic.policy_behavior"
    SYNTHETIC_TRIP_COUNT = "synthetic.trip_count"
    SYNTHETIC_RANDOM_SEED = "synthetic.random_seed"

    SEED_DEMAND_MULTIPLIER = "seed.demand.multiplier"
    SEED_BIRTH_RATE_MULTIPLIER = "seed.workload.birth_rate_multiplier"
    SEED_FLEET_COUNT = "seed.fleet.count"
    SEED_RSU_COUNT = "seed.infrastructure.rsu_count"
    SEED_POLICY_ALGORITHM = "seed.policy.algorithm"
    SEED_RANDOM_SEED = "seed.evaluation.random_seed"
    SEED_LANES_CLOSED = "seed.traffic.lanes_closed"
    SEED_EVENT_DURATION_MIN = "seed.traffic.duration_min"
    SEED_EVENT_DEMAND_MULTIPLIER = "seed.traffic.event_demand_multiplier"


SYNTHETIC_PARAMETER_PATHS = tuple(
    parameter for parameter in SweepParameter if parameter.value.startswith("synthetic.")
)
SEED_PARAMETER_PATHS = tuple(
    parameter for parameter in SweepParameter if parameter.value.startswith("seed.")
)

_INTEGER_PARAMETER_BOUNDS: dict[SweepParameter, tuple[int, int]] = {
    SweepParameter.SYNTHETIC_VEHICLE_COUNT: (1, 500),
    SweepParameter.SYNTHETIC_RSU_COUNT: (1, 100),
    SweepParameter.SYNTHETIC_TRIP_COUNT: (0, 5_000),
    SweepParameter.SYNTHETIC_RANDOM_SEED: (0, 2_147_483_647),
    SweepParameter.SEED_FLEET_COUNT: (0, 100_000),
    SweepParameter.SEED_RSU_COUNT: (0, 10_000),
    SweepParameter.SEED_RANDOM_SEED: (0, 2_147_483_647),
    SweepParameter.SEED_LANES_CLOSED: (0, 1_000),
}

_NUMERIC_PARAMETER_BOUNDS: dict[SweepParameter, tuple[float, float]] = {
    SweepParameter.SYNTHETIC_DURATION_S: (0.1, 3_600.0),
    SweepParameter.SYNTHETIC_SAMPLING_INTERVAL_S: (0.1, 3_600.0),
    SweepParameter.SYNTHETIC_TASK_ARRIVAL_RATE: (0.000001, 2.0),
    SweepParameter.SYNTHETIC_RSU_CAPACITY: (0.001, 10_000.0),
    SweepParameter.SYNTHETIC_NETWORK_DELAY_MS: (0.0, 10_000.0),
    SweepParameter.SYNTHETIC_CONGESTION_MULTIPLIER: (0.01, 100.0),
    SweepParameter.SEED_DEMAND_MULTIPLIER: (0.01, 100.0),
    SweepParameter.SEED_BIRTH_RATE_MULTIPLIER: (0.01, 100.0),
    SweepParameter.SEED_EVENT_DURATION_MIN: (0.0, 10_080.0),
    SweepParameter.SEED_EVENT_DEMAND_MULTIPLIER: (0.01, 100.0),
}


class SweepAxis(StrictModel):
    """One ordered finite parameter axis."""

    parameter_path: SweepParameter
    values: list[JsonScalar] = Field(min_length=1, max_length=MAX_VALUES_PER_AXIS)

    @field_validator("values")
    @classmethod
    def validate_values(cls, values: list[JsonScalar]) -> list[JsonScalar]:
        fingerprints: set[str] = set()
        for value in values:
            if value is None:
                raise ValueError("sweep axis values must not be null")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("sweep axis values must be finite")
            fingerprint = _canonical_json(value)
            if fingerprint in fingerprints:
                raise ValueError("sweep axis values must not contain duplicates")
            fingerprints.add(fingerprint)
        return values


class ParameterSweepRequest(StrictModel):
    """Complete bounded parameter-sweep declaration."""

    schema_version: Literal["1.0"] = PARAMETER_SWEEP_SCHEMA_VERSION
    sweep_id: str
    title: str = Field(min_length=1)
    description: str = ""
    mode: ParameterSweepMode
    base_synthetic_config: SyntheticScenarioConfig | None = None
    base_seed: ScenarioSeed | None = None
    axes: list[SweepAxis] = Field(min_length=1, max_length=MAX_SWEEP_AXES)
    metric_keys: list[str] = Field(default_factory=list, max_length=MAX_RESPONSE_METRICS)

    @field_validator("sweep_id")
    @classmethod
    def validate_sweep_id(cls, value: str) -> str:
        return _validate_identifier(value, "sweep_id") or value

    @model_validator(mode="after")
    def validate_request_contract(self) -> ParameterSweepRequest:
        if (self.base_synthetic_config is None) == (self.base_seed is None):
            raise ValueError("provide exactly one of base_synthetic_config or base_seed")
        if (
            self.mode is ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES
            and self.base_synthetic_config is None
        ):
            raise ValueError("local_synthetic_bundles requires base_synthetic_config")

        axis_paths = [axis.parameter_path for axis in self.axes]
        if len(set(axis_paths)) != len(axis_paths):
            raise ValueError("axes must not repeat a parameter_path")
        allowed = (
            set(SYNTHETIC_PARAMETER_PATHS)
            if self.base_synthetic_config is not None
            else set(SEED_PARAMETER_PATHS)
        )
        unsupported = [path.value for path in axis_paths if path not in allowed]
        if unsupported:
            raise ValueError(
                "axis paths are incompatible with the selected base: " + ", ".join(unsupported)
            )
        for axis in self.axes:
            for value in axis.values:
                _validate_parameter_value(axis.parameter_path, value)
        point_count = math.prod(len(axis.values) for axis in self.axes)
        if point_count > MAX_SWEEP_POINTS:
            raise ValueError(
                f"declared grid has {point_count} points; maximum is {MAX_SWEEP_POINTS}"
            )

        if len(set(self.metric_keys)) != len(self.metric_keys):
            raise ValueError("metric_keys must not contain duplicates")
        known_metrics = set(metric_catalogue())
        unknown_metrics = [key for key in self.metric_keys if key not in known_metrics]
        if unknown_metrics:
            raise ValueError("unknown core metric keys: " + ", ".join(unknown_metrics))
        if self.mode is ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES:
            if not self.metric_keys:
                raise ValueError("local_synthetic_bundles requires at least one metric_key")
        elif self.metric_keys:
            raise ValueError("metric_keys are only valid for local_synthetic_bundles")
        return self

    @property
    def point_count(self) -> int:
        """Return the complete Cartesian-product size."""

        return math.prod(len(axis.values) for axis in self.axes)


class ParameterAssignment(StrictModel):
    """One exact parameter value used at a sweep point."""

    parameter_path: SweepParameter
    value: JsonScalar


class ExternalRunRequest(StrictModel):
    """A coordination artifact that explicitly records no execution."""

    schema_version: Literal["1.0"] = "1.0"
    request_id: str
    sweep_id: str
    point_id: str
    execution_status: Literal["not_executed"] = "not_executed"
    direct_launch_supported: Literal[False] = False
    launcher: None = None
    command: None = None
    seed_id: str
    seed_fingerprint: str
    suggested_run_id: str
    suggested_bundle_id: str
    parameter_provenance: list[ParameterAssignment]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "This is an external coordination request; TrafficTwin did not execute it.",
            "No simulator command, environment, checkpoint, or output path was inferred.",
            "Completed outputs must return through ordinary validation and import.",
        ]
    )


class ParameterSweepPoint(StrictModel):
    """One deterministic grid point and its materialised provenance."""

    point_id: str
    sequence: int = Field(ge=1)
    parameter_provenance: list[ParameterAssignment]
    point_fingerprint: str
    parent_fingerprint: str
    synthetic_evaluation: Literal[True] = True
    config_snapshot: SyntheticScenarioConfig | None = None
    seed_snapshot: ScenarioSeed
    seed_fingerprint: str
    seed_relative_path: str | None = None
    bundle_relative_path: str | None = None
    bundle_fingerprint: str | None = None
    external_request_relative_path: str | None = None
    external_request: ExternalRunRequest | None = None


class SweepResponseRow(StrictModel):
    """One numeric metric response with complete point and bundle provenance."""

    sweep_id: str
    point_id: str
    sequence: int = Field(ge=1)
    parameter_provenance: list[ParameterAssignment]
    metric_key: str
    metric_status: MetricStatus
    response_value: float | None = None
    unit: str
    reason_codes: list[str] = Field(default_factory=list)
    run_id: str
    seed_id: str
    seed_fingerprint: str
    bundle_fingerprint: str
    synthetic_evaluation: Literal[True] = True


class ParameterSweepExpansion(StrictModel):
    """Pure deterministic grid expansion before filesystem materialisation."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["1.0"] = PARAMETER_SWEEP_METHOD_VERSION
    sweep_id: str
    mode: ParameterSweepMode
    request_fingerprint: str
    base_fingerprint: str
    point_count: int
    points: list[ParameterSweepPoint]
    synthetic_evaluation: Literal[True] = True


class ParameterSweepResult(StrictModel):
    """Materialised parameter-sweep manifest and response surface."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["1.0"] = PARAMETER_SWEEP_METHOD_VERSION
    sweep_id: str
    title: str
    generated_at: datetime
    mode: ParameterSweepMode
    status: Literal[
        "expanded_seed_snapshots",
        "completed_local_analysis",
        "external_requests_not_executed",
    ]
    request_fingerprint: str
    base_fingerprint: str
    result_fingerprint: str
    point_count: int
    response_row_count: int
    response_surface_available: bool
    synthetic_evaluation: Literal[True] = True
    direct_launch_supported: Literal[False] = False
    axes: list[SweepAxis]
    metric_keys: list[str]
    points: list[ParameterSweepPoint]
    response_surface: list[SweepResponseRow]
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def canonical_json(self) -> str:
        """Return stable JSON with the generated timestamp normalised."""

        payload = self.model_dump(mode="json", by_alias=True)
        payload["generated_at"] = "<normalised>"
        payload["result_fingerprint"] = ""
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def fingerprint(self) -> str:
        """Recompute the recorded timestamp-independent result fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ParameterSweepContract(StrictModel):
    """Public v1 method and safety contract."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["1.0"] = PARAMETER_SWEEP_METHOD_VERSION
    max_axes: int = MAX_SWEEP_AXES
    max_values_per_axis: int = MAX_VALUES_PER_AXIS
    max_points: int = MAX_SWEEP_POINTS
    max_response_metrics: int = MAX_RESPONSE_METRICS
    max_local_estimated_rows: int = MAX_LOCAL_ESTIMATED_ROWS
    supported_modes: list[ParameterSweepMode]
    synthetic_parameter_paths: list[SweepParameter]
    seed_parameter_paths: list[SweepParameter]
    local_execution_boundary: str
    external_execution_status: Literal["not_executed"] = "not_executed"
    direct_launch_supported: Literal[False] = False
    response_surface_policy: str
    provenance_policy: str
    parameter_value_constraints: dict[str, str]
    limitations: list[str]


class ParameterSweepError(RuntimeError):
    """Raised when a sweep cannot be composed or materialised safely."""


def parameter_sweep_contract() -> ParameterSweepContract:
    """Return the public bounded composer contract."""

    return ParameterSweepContract(
        supported_modes=list(ParameterSweepMode),
        synthetic_parameter_paths=list(SYNTHETIC_PARAMETER_PATHS),
        seed_parameter_paths=list(SEED_PARAMETER_PATHS),
        local_execution_boundary=(
            "Only TrafficTwin's labelled deterministic synthetic bundle generator, validator, "
            "and ordinary core metric engine may execute locally."
        ),
        response_surface_policy=(
            "Rows contain only finite numeric core-metric values; unavailable, partial, invalid, "
            "or non-numeric results retain their explicit status and reason codes."
        ),
        provenance_policy=(
            "Every point records its ordered assignments, parent/request/point/seed fingerprints, "
            "and bundle fingerprint when locally materialised."
        ),
        parameter_value_constraints=_parameter_value_constraints(),
        limitations=[
            "Mix-valued, incident-list, placement, failure-list, and arbitrary nested fields are "
            "outside the v1 closed parameter catalogue.",
            "The composer does not launch SUMO, Randy VEC/TOS, training, or another simulator.",
            "Sweep outputs are synthetic/evaluation evidence and are not real-world validation.",
            "Only core numeric metrics are admitted to the v1 response-surface table.",
            "Local requests whose deterministic declared-row estimate exceeds 2,000,000 are "
            "rejected before output is written.",
            "Empty, symbolic-link, current/home/root, and current/home ancestor destinations are "
            "rejected before expansion.",
        ],
    )


def load_parameter_sweep_request(path: str | Path) -> ParameterSweepRequest:
    """Load a strict YAML or JSON parameter-sweep request."""

    source = Path(path)
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ParameterSweepError(f"could not read parameter-sweep request: {exc}") from exc
    if not isinstance(payload, dict):
        raise ParameterSweepError("parameter-sweep request must be a mapping")
    try:
        return ParameterSweepRequest.model_validate(payload)
    except ValueError as exc:
        raise ParameterSweepError(f"invalid parameter-sweep request: {exc}") from exc


def parameter_sweep_request_to_yaml(request: ParameterSweepRequest) -> str:
    """Serialise a request without inferred or volatile values."""

    return yaml.safe_dump(
        request.model_dump(mode="json", by_alias=True, exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )


def expand_parameter_sweep(request: ParameterSweepRequest) -> ParameterSweepExpansion:
    """Expand and validate the complete Cartesian grid without writing files."""

    request_fingerprint = _fingerprint(request.model_dump(mode="json", by_alias=True))
    base = request.base_synthetic_config or request.base_seed
    if base is None:  # pragma: no cover - guarded by model validation
        raise ParameterSweepError("parameter-sweep request has no base")
    base_fingerprint = _fingerprint(base.model_dump(mode="json", by_alias=True))
    points: list[ParameterSweepPoint] = []
    estimated_local_rows = 0
    for sequence, values in enumerate(product(*(axis.values for axis in request.axes)), start=1):
        assignments = [
            ParameterAssignment(parameter_path=axis.parameter_path, value=value)
            for axis, value in zip(request.axes, values, strict=True)
        ]
        point_fingerprint = _fingerprint(
            {
                "request_fingerprint": request_fingerprint,
                "assignments": [item.model_dump(mode="json") for item in assignments],
            }
        )
        point_id = f"point-{sequence:04d}-{point_fingerprint[:12]}"
        try:
            config_snapshot, seed_snapshot = _materialise_snapshots(
                request,
                assignments,
                point_id=point_id,
                sequence=sequence,
                point_fingerprint=point_fingerprint,
            )
        except ValueError as exc:
            raise ParameterSweepError(f"invalid grid point {sequence} ({point_id}): {exc}") from exc
        seed_fingerprint = _fingerprint(seed_snapshot.model_dump(mode="json", by_alias=True))
        if request.mode is ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES:
            if config_snapshot is None:  # pragma: no cover - request validation guards it
                raise ParameterSweepError("local synthetic point has no config snapshot")
            estimated_local_rows += _estimated_local_rows(config_snapshot)
            if estimated_local_rows > MAX_LOCAL_ESTIMATED_ROWS:
                raise ParameterSweepError(
                    "declared local sweep is estimated to generate "
                    f"{estimated_local_rows:,} rows, exceeding the complete-sweep limit of "
                    f"{MAX_LOCAL_ESTIMATED_ROWS:,}"
                )
        external_request = (
            _external_request(
                request,
                point_id,
                sequence,
                assignments,
                seed_snapshot,
                seed_fingerprint,
            )
            if request.mode is ParameterSweepMode.EXTERNAL_RUN_REQUESTS
            else None
        )
        points.append(
            ParameterSweepPoint(
                point_id=point_id,
                sequence=sequence,
                parameter_provenance=assignments,
                point_fingerprint=point_fingerprint,
                parent_fingerprint=base_fingerprint,
                config_snapshot=config_snapshot,
                seed_snapshot=seed_snapshot,
                seed_fingerprint=seed_fingerprint,
                external_request=external_request,
            )
        )
    return ParameterSweepExpansion(
        sweep_id=request.sweep_id,
        mode=request.mode,
        request_fingerprint=request_fingerprint,
        base_fingerprint=base_fingerprint,
        point_count=len(points),
        points=points,
    )


def execute_parameter_sweep(
    request: ParameterSweepRequest,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
    metric_config: MetricEngineConfig | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ParameterSweepResult:
    """Materialise a sweep transactionally and emit its response-surface artifacts."""

    destination = _validated_destination(output_dir)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"parameter-sweep destination already exists: {destination}")
    if destination.exists() and not destination.is_dir():
        raise ParameterSweepError(f"parameter-sweep destination is not a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    expansion = expand_parameter_sweep(request)
    generated_at = (clock or _utc_now)()
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-sweep-", dir=destination.parent)
    )
    working = temporary_root / "payload"
    working.mkdir()
    try:
        points, responses = _write_expansion(
            request,
            expansion,
            working,
            metric_config=metric_config,
            generated_at=generated_at,
        )
        status = {
            ParameterSweepMode.SEED_SNAPSHOTS: "expanded_seed_snapshots",
            ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES: "completed_local_analysis",
            ParameterSweepMode.EXTERNAL_RUN_REQUESTS: "external_requests_not_executed",
        }[request.mode]
        result_payload: dict[str, Any] = {
            "schema_version": "1.0",
            "method_version": PARAMETER_SWEEP_METHOD_VERSION,
            "sweep_id": request.sweep_id,
            "title": request.title,
            "generated_at": generated_at.isoformat(),
            "mode": request.mode.value,
            "status": status,
            "request_fingerprint": expansion.request_fingerprint,
            "base_fingerprint": expansion.base_fingerprint,
            "result_fingerprint": "",
            "point_count": len(points),
            "response_row_count": len(responses),
            "response_surface_available": bool(responses),
            "synthetic_evaluation": True,
            "direct_launch_supported": False,
            "axes": [axis.model_dump(mode="json") for axis in request.axes],
            "metric_keys": request.metric_keys,
            "points": [point.model_dump(mode="json", by_alias=True) for point in points],
            "response_surface": [row.model_dump(mode="json") for row in responses],
            "warnings": _warnings(request, responses),
            "limitations": _limitations(request),
        }
        result_payload["result_fingerprint"] = _fingerprint(
            {**result_payload, "generated_at": "<normalised>", "result_fingerprint": ""}
        )
        result = ParameterSweepResult.model_validate(result_payload)
        (working / "sweep_result.json").write_text(
            result.model_dump_json(indent=2, by_alias=True) + "\n",
            encoding="utf-8",
        )
        (working / "response_surface.csv").write_text(
            parameter_sweep_response_to_csv(result),
            encoding="utf-8",
        )
        (working / "request.yaml").write_text(
            parameter_sweep_request_to_yaml(request),
            encoding="utf-8",
        )
        if destination.exists():
            shutil.rmtree(destination)
        working.replace(destination)
    except Exception:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise
    shutil.rmtree(temporary_root, ignore_errors=True)
    return result


def parameter_sweep_response_to_csv(result: ParameterSweepResult) -> str:
    """Return a deterministic wide-parameter/long-metric response table."""

    axis_names = [axis.parameter_path.value for axis in result.axes]
    fieldnames = [
        "sweep_id",
        "point_id",
        "sequence",
        *axis_names,
        "metric_key",
        "metric_status",
        "response_value",
        "unit",
        "reason_codes",
        "run_id",
        "seed_id",
        "seed_fingerprint",
        "bundle_fingerprint",
        "synthetic_evaluation",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for response in result.response_surface:
        assignments = {
            item.parameter_path.value: _csv_scalar(item.value)
            for item in response.parameter_provenance
        }
        writer.writerow(
            {
                "sweep_id": response.sweep_id,
                "point_id": response.point_id,
                "sequence": response.sequence,
                **assignments,
                "metric_key": response.metric_key,
                "metric_status": response.metric_status.value,
                "response_value": (
                    "" if response.response_value is None else response.response_value
                ),
                "unit": response.unit,
                "reason_codes": "|".join(response.reason_codes),
                "run_id": response.run_id,
                "seed_id": response.seed_id,
                "seed_fingerprint": response.seed_fingerprint,
                "bundle_fingerprint": response.bundle_fingerprint,
                "synthetic_evaluation": "true",
            }
        )
    return output.getvalue()


def _write_expansion(
    request: ParameterSweepRequest,
    expansion: ParameterSweepExpansion,
    working: Path,
    *,
    metric_config: MetricEngineConfig | None,
    generated_at: datetime,
) -> tuple[list[ParameterSweepPoint], list[SweepResponseRow]]:
    points: list[ParameterSweepPoint] = []
    responses: list[SweepResponseRow] = []
    for point in expansion.points:
        seed_path = working / "seeds" / f"{point.point_id}.yaml"
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        write_seed(point.seed_snapshot, seed_path)
        update: dict[str, Any] = {"seed_relative_path": seed_path.relative_to(working).as_posix()}
        if request.mode is ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES:
            if point.config_snapshot is None:  # pragma: no cover - request validation guards it
                raise ParameterSweepError("local synthetic point has no config snapshot")
            bundle_path = working / "bundles" / point.point_id
            write_synthetic_bundle(point.config_snapshot, bundle_path)
            validation = validate_bundle(bundle_path)
            if not validation.report.may_import or validation.manifest is None:
                raise ParameterSweepError(
                    f"generated point {point.point_id} failed ordinary bundle validation"
                )
            if validation.fingerprint is None:
                raise ParameterSweepError(
                    f"generated point {point.point_id} has no bundle fingerprint"
                )
            update.update(
                {
                    "bundle_relative_path": bundle_path.relative_to(working).as_posix(),
                    "bundle_fingerprint": validation.fingerprint,
                }
            )
            metrics = compute_metrics_for_bundle(
                validation,
                metric_config,
                clock=lambda: generated_at,
            ).by_key()
            for metric_key in request.metric_keys:
                metric = metrics[metric_key]
                response_value, status, reasons = _numeric_response(metric.status, metric.value)
                responses.append(
                    SweepResponseRow(
                        sweep_id=request.sweep_id,
                        point_id=point.point_id,
                        sequence=point.sequence,
                        parameter_provenance=point.parameter_provenance,
                        metric_key=metric_key,
                        metric_status=status,
                        response_value=response_value,
                        unit=metric.unit,
                        reason_codes=[
                            *(reason.value for reason in metric.reason_codes),
                            *reasons,
                        ],
                        run_id=metric.run_id,
                        seed_id=point.seed_snapshot.seed_id,
                        seed_fingerprint=point.seed_fingerprint,
                        bundle_fingerprint=validation.fingerprint,
                    )
                )
        elif request.mode is ParameterSweepMode.EXTERNAL_RUN_REQUESTS:
            external = point.external_request
            if external is None:  # pragma: no cover - expansion contract guards it
                raise ParameterSweepError("external request point has no request artifact")
            request_path = working / "external_requests" / f"{point.point_id}.json"
            request_path.parent.mkdir(parents=True, exist_ok=True)
            request_path.write_text(external.model_dump_json(indent=2) + "\n", encoding="utf-8")
            update["external_request_relative_path"] = request_path.relative_to(working).as_posix()
        points.append(point.model_copy(update=update))
    return points, responses


def _materialise_snapshots(
    request: ParameterSweepRequest,
    assignments: list[ParameterAssignment],
    *,
    point_id: str,
    sequence: int,
    point_fingerprint: str,
) -> tuple[SyntheticScenarioConfig | None, ScenarioSeed]:
    if request.base_synthetic_config is not None:
        payload = request.base_synthetic_config.model_dump(mode="python")
        for assignment in assignments:
            _set_path(
                payload,
                assignment.parameter_path.value.removeprefix("synthetic."),
                assignment.value,
            )
        payload.update(
            {
                "scenario_id": (
                    f"{request.base_synthetic_config.scenario_id}-sw-{point_fingerprint[:10]}"
                ),
                "name": f"{request.base_synthetic_config.name} — sweep point {sequence}",
                "description": (
                    f"{request.base_synthetic_config.description} Labelled synthetic parameter "
                    f"sweep point {point_id}; not real-world evidence."
                ).strip(),
                "experiment_id": request.sweep_id,
                "baseline_seed_id": f"seed-{request.base_synthetic_config.scenario_id}",
                "provenance": {
                    "producer": "TrafficTwin parameter sweep composer",
                    "notes": (
                        "Synthetic parameter-sweep fixture for deterministic robustness analysis; "
                        "not a calibrated simulator or externally validated result."
                    ),
                },
            }
        )
        config = SyntheticScenarioConfig.model_validate(payload)
        return config, generate_run_data(config).seed

    if request.base_seed is None:  # pragma: no cover - request validation guards it
        raise ValueError("base seed is unavailable")
    payload = request.base_seed.model_dump(mode="python", by_alias=False)
    for assignment in assignments:
        _set_path(payload, assignment.parameter_path.value.removeprefix("seed."), assignment.value)
    payload.update(
        {
            "seed_id": f"{request.base_seed.seed_id}-sw-{point_fingerprint[:10]}",
            "name": f"{request.base_seed.name} — sweep point {sequence}",
            "description": (
                f"{request.base_seed.description} Labelled synthetic parameter sweep point "
                f"{point_id}; no external execution has occurred."
            ).strip(),
            "parent_seed_id": request.base_seed.seed_id,
            "compare_against": request.base_seed.seed_id,
            "provenance": {
                "created_by": "TrafficTwin parameter sweep composer",
                "source": f"parameter sweep of {request.base_seed.seed_id}",
            },
        }
    )
    return None, ScenarioSeed.model_validate(payload)


def _external_request(
    request: ParameterSweepRequest,
    point_id: str,
    sequence: int,
    assignments: list[ParameterAssignment],
    seed: ScenarioSeed,
    seed_fingerprint: str,
) -> ExternalRunRequest:
    return ExternalRunRequest(
        request_id=f"request-{request.sweep_id}-{sequence:04d}-{seed_fingerprint[:10]}",
        sweep_id=request.sweep_id,
        point_id=point_id,
        seed_id=seed.seed_id,
        seed_fingerprint=seed_fingerprint,
        suggested_run_id=f"{request.sweep_id}-run-{sequence:04d}",
        suggested_bundle_id=f"bundle-{request.sweep_id}-{sequence:04d}",
        parameter_provenance=assignments,
    )


def _numeric_response(
    status: MetricStatus,
    value: object,
) -> tuple[float | None, MetricStatus, list[str]]:
    if status not in {MetricStatus.AVAILABLE, MetricStatus.PARTIAL}:
        return None, status, []
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, MetricStatus.UNAVAILABLE, ["RESPONSE_VALUE_NON_NUMERIC"]
    numeric = float(value)
    if not math.isfinite(numeric):
        return None, MetricStatus.INVALID, ["RESPONSE_VALUE_NON_FINITE"]
    return numeric, status, []


def _validate_parameter_value(parameter: SweepParameter, value: JsonScalar) -> None:
    integer_bounds = _INTEGER_PARAMETER_BOUNDS.get(parameter)
    if integer_bounds is not None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{parameter.value} values must be integers")
        integer_minimum, integer_maximum = integer_bounds
        if not integer_minimum <= value <= integer_maximum:
            raise ValueError(
                f"{parameter.value} values must be between {integer_minimum} and "
                f"{integer_maximum} inclusive"
            )
        return

    numeric_bounds = _NUMERIC_PARAMETER_BOUNDS.get(parameter)
    if numeric_bounds is not None:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{parameter.value} values must be numeric")
        numeric = float(value)
        numeric_minimum, numeric_maximum = numeric_bounds
        if not numeric_minimum <= numeric <= numeric_maximum:
            raise ValueError(
                f"{parameter.value} values must be between {numeric_minimum} and "
                f"{numeric_maximum} inclusive"
            )
        return

    if parameter is SweepParameter.SYNTHETIC_POLICY_BEHAVIOR:
        allowed = {profile.value for profile in SyntheticPolicyProfile}
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(
                f"{parameter.value} values must be one of: {', '.join(sorted(allowed))}"
            )
        return

    if parameter is SweepParameter.SEED_POLICY_ALGORITHM:
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ValueError(
                f"{parameter.value} values must be non-blank strings of at most 128 characters"
            )
        return

    raise ValueError(f"no value constraint is registered for {parameter.value}")


def _parameter_value_constraints() -> dict[str, str]:
    constraints: dict[str, str] = {}
    for parameter, (integer_minimum, integer_maximum) in _INTEGER_PARAMETER_BOUNDS.items():
        constraints[parameter.value] = f"integer in [{integer_minimum}, {integer_maximum}]"
    for parameter, (numeric_minimum, numeric_maximum) in _NUMERIC_PARAMETER_BOUNDS.items():
        constraints[parameter.value] = f"finite number in [{numeric_minimum}, {numeric_maximum}]"
    constraints[SweepParameter.SYNTHETIC_POLICY_BEHAVIOR.value] = (
        "one documented SyntheticPolicyProfile value"
    )
    constraints[SweepParameter.SEED_POLICY_ALGORITHM.value] = (
        "non-blank string with at most 128 characters"
    )
    return {key: constraints[key] for key in sorted(constraints)}


def _estimated_local_rows(config: SyntheticScenarioConfig) -> int:
    timestamp_count = int(config.duration_s // config.sampling_interval_s) + 1
    task_count = max(1, int(round(config.duration_s * config.task_arrival_rate)))
    total = task_count
    if config.include_infrastructure:
        total += config.rsu_count * timestamp_count
    if config.include_vehicles:
        total += config.vehicle_count * timestamp_count
    if config.include_traffic:
        total += timestamp_count
    if config.include_trips:
        total += config.trip_count
    if config.include_incidents:
        total += len(config.incident_schedule)
    return total


def _validated_destination(output_dir: str | Path) -> Path:
    raw_destination = str(output_dir)
    if not raw_destination.strip():
        raise ParameterSweepError("parameter-sweep destination must not be empty")
    unresolved = Path(output_dir).expanduser()
    if unresolved.is_symlink():
        raise ParameterSweepError(
            f"parameter-sweep destination must not be a symbolic link: {unresolved}"
        )
    destination = unresolved.resolve(strict=False)
    protected_paths = (Path.cwd().resolve(), Path.home().resolve())
    if any(
        destination == protected or protected.is_relative_to(destination)
        for protected in protected_paths
    ):
        raise ParameterSweepError(
            "parameter-sweep destination must not be the current directory, home directory, "
            "filesystem root, or one of their ancestors"
        )
    return destination


def _set_path(payload: dict[str, Any], path: str, value: JsonScalar) -> None:
    segments = path.split(".")
    target = payload
    for segment in segments[:-1]:
        nested = target.get(segment)
        if not isinstance(nested, dict):
            raise ValueError(f"parameter path is not writable: {path}")
        target = nested
    target[segments[-1]] = value


def _warnings(
    request: ParameterSweepRequest,
    responses: Iterable[SweepResponseRow],
) -> list[str]:
    warnings = [
        "Every derived point is labelled synthetic/evaluation evidence, including seed-only and "
        "external-request modes."
    ]
    unavailable = sum(
        row.metric_status not in {MetricStatus.AVAILABLE, MetricStatus.PARTIAL} for row in responses
    )
    if unavailable:
        warnings.append(
            f"{unavailable} response rows are unavailable or invalid; they were not replaced "
            "by zero."
        )
    if request.mode is ParameterSweepMode.EXTERNAL_RUN_REQUESTS:
        warnings.append(
            "External request artifacts were created with status not_executed; no simulator ran."
        )
    return warnings


def _limitations(request: ParameterSweepRequest) -> list[str]:
    limitations = list(parameter_sweep_contract().limitations)
    if request.mode is not ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES:
        limitations.append(
            "No response values exist because this mode does not execute local bundle analysis."
        )
    return limitations


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _csv_scalar(value: JsonScalar) -> str | int | float | bool:
    if value is None:
        return ""
    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)
