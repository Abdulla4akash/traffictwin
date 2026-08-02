"""Concrete bounded local-SUMO transport for the Phase-168 live-twin controller."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Literal, Protocol, TextIO, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.integration.sumo_execution.models import (
    SCENARIO_CONFIG_FILE,
    SCENARIO_NET_FILE,
    SumoExecutionPreset,
    SumoRunPreset,
    SumoRuntimeStatus,
)
from traffictwin.integration.sumo_execution.service import (
    preset_definition,
    preset_scenario_root,
    sumo_runtime_status,
)
from traffictwin.platform.live_twin import (
    AggregateMobilityUpdate,
    CommandKind,
    LiveTwinError,
    LiveTwinSessionSpec,
    ProcessCommandResult,
    TwinCommand,
)

METHOD_VERSION: Literal["local-sumo-live-twin-1.0"] = "local-sumo-live-twin-1.0"
DESIGN_REFERENCE: Literal["docs/platform/local_sumo_live_twin_transport_design.md"] = (
    "docs/platform/local_sumo_live_twin_transport_design.md"
)

_SUPPORTED_COMMANDS: frozenset[CommandKind] = frozenset(
    {
        "pause",
        "resume",
        "step",
        "set_signal_program",
        "set_speed_limit",
        "close_lane",
        "open_lane",
        "inject_incident",
        "clear_incident",
        "set_route_demand",
        "set_vehicle_route_policy",
    }
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "\\Users\\",
    "password",
    "secret",
    "credential",
    "participant_id",
    "vehicle_id",
)
_HASH_CHUNK_BYTES = 1024 * 1024
_MAX_WALL_CLOCK_SECONDS = 600
_MAX_SIMULATION_SECONDS = 120
_MAX_COMMANDS = 100
_MIN_CONTROL_PORT = 1024
_MAX_CONTROL_PORT = 65_535


class LocalSumoTransportError(LiveTwinError):
    """Typed local transport refusal."""


class LocalSumoModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    def digest(self) -> str:
        material = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _validate_safe_id(value: str, *, label: str) -> str:
    lowered = value.lower()
    if not _SAFE_ID.fullmatch(value) or any(
        marker.lower() in lowered for marker in _PRIVATE_MARKERS
    ):
        raise ValueError(f"{label} must be a bounded non-private identifier")
    return value


class SignalProgramGrant(LocalSumoModel):
    signal_id: str
    program_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_grant(self) -> SignalProgramGrant:
        _validate_safe_id(self.signal_id, label="signal id")
        if len(set(self.program_ids)) != len(self.program_ids):
            raise ValueError("signal program ids must be unique")
        for program_id in self.program_ids:
            _validate_safe_id(program_id, label="signal program id")
        return self


class RoutePolicyGrant(LocalSumoModel):
    policy_id: str
    route_id: str

    @model_validator(mode="after")
    def validate_grant(self) -> RoutePolicyGrant:
        _validate_safe_id(self.policy_id, label="route policy id")
        _validate_safe_id(self.route_id, label="route id")
        return self


class LocalSumoCommandPolicy(LocalSumoModel):
    """Digest-bound command targets and parameter bounds for one pinned scenario."""

    scenario_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    edge_ids: tuple[str, ...] = Field(min_length=1)
    lane_ids: tuple[str, ...] = Field(min_length=1)
    route_ids: tuple[str, ...] = Field(min_length=1)
    signal_programs: tuple[SignalProgramGrant, ...] = ()
    route_policies: tuple[RoutePolicyGrant, ...] = Field(min_length=1)
    closed_vehicle_classes: tuple[Literal["passenger"], ...] = ("passenger",)
    maximum_step_batch: int = Field(default=20, ge=1, le=100)
    maximum_added_vehicles_per_command: int = Field(default=4, ge=1, le=20)
    minimum_speed_mps: float = Field(default=0.1, gt=0, le=5)
    maximum_speed_mps: float = Field(default=40.0, ge=5, le=100)
    maximum_demand_multiplier: float = Field(default=3.0, ge=1, le=10)
    maximum_incident_severity: float = Field(default=0.95, gt=0, lt=1)
    maximum_output_bytes: int = Field(default=65_536, ge=1_024, le=1_048_576)
    connection_timeout_seconds: float = Field(default=10.0, ge=0.5, le=30)
    process_grace_seconds: float = Field(default=2.0, ge=0.1, le=10)

    @model_validator(mode="after")
    def validate_policy(self) -> LocalSumoCommandPolicy:
        for label, values in (
            ("edge id", self.edge_ids),
            ("lane id", self.lane_ids),
            ("route id", self.route_ids),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{label}s must be unique")
            for value in values:
                _validate_safe_id(value, label=label)
        signals = [grant.signal_id for grant in self.signal_programs]
        policies = [grant.policy_id for grant in self.route_policies]
        if len(set(signals)) != len(signals):
            raise ValueError("signal grants must be unique")
        if len(set(policies)) != len(policies):
            raise ValueError("route policy grants must be unique")
        if not {grant.route_id for grant in self.route_policies} <= set(self.route_ids):
            raise ValueError("route policies must reference an allowlisted route")
        if self.minimum_speed_mps >= self.maximum_speed_mps:
            raise ValueError("speed bounds must be increasing")
        return self


class LocalSumoInputIdentity(LocalSumoModel):
    name: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_name(self) -> LocalSumoInputIdentity:
        path = PurePosixPath(self.name)
        if (
            path.is_absolute()
            or len(path.parts) != 1
            or self.name in {".", ".."}
            or "\\" in self.name
        ):
            raise ValueError("input identity requires one safe file name")
        return self


class LocalSumoInventory(LocalSumoModel):
    edge_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    signal_ids: tuple[str, ...]


class LocalSumoPreparation(LocalSumoModel):
    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["local-sumo-live-twin-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/local_sumo_live_twin_transport_design.md"] = (
        DESIGN_REFERENCE
    )
    session_spec_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    preset: Literal["synthetic_square_smoke"] = "synthetic_square_smoke"
    preset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_inventory: tuple[LocalSumoInputIdentity, ...] = Field(min_length=1)
    runtime_version: str
    runtime_executable_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    command_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    control_port: int = Field(ge=_MIN_CONTROL_PORT, le=_MAX_CONTROL_PORT)
    argv: tuple[str, ...] = Field(min_length=2, max_length=32)
    loopback_only: Literal[True] = True
    shell: Literal[False] = False
    staged_private_workspace: Literal[True] = True
    synthetic: Literal[True] = True
    manchester_traffic: Literal[False] = False
    randy_vec_evidence: Literal[False] = False
    real_world_validation: Literal[False] = False
    evidence: Literal[False] = False
    scientific_use: Literal[False] = False
    production_ready: Literal[False] = False

    @model_validator(mode="after")
    def validate_argv(self) -> LocalSumoPreparation:
        if self.argv[0] != "sumo" or any(
            Path(item).is_absolute()
            or "/" in item
            or "\\" in item
            or "\x00" in item
            or item in {".", ".."}
            for item in self.argv
        ):
            raise ValueError("preparation argv must be path-free and use the fixed sumo executable")
        return self


class LocalSumoReadiness(LocalSumoModel):
    ready: bool
    reason: str
    runtime: SumoRuntimeStatus
    preset_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    network_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    command_policy_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    transport_version: Literal["local-sumo-live-twin-1.0"] = METHOD_VERSION
    traci_tools_bound: bool
    synthetic_only: Literal[True] = True
    evidence: Literal[False] = False
    scientific_use: Literal[False] = False


@dataclass(frozen=True)
class ResolvedLocalSumoRuntime:
    """Internal activation binding; paths never enter portable models or receipts."""

    status: SumoRuntimeStatus
    executable: Path
    tools_root: Path


class ManagedProcess(Protocol):
    @property
    def stdout(self) -> TextIO | None: ...

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate_group(self) -> None: ...

    def kill_group(self) -> None: ...


class LocalSumoProtocol(Protocol):
    def heartbeat(self) -> bool: ...

    def inventory(self) -> LocalSumoInventory: ...

    def read_aggregates(self) -> Mapping[str, float]: ...

    def step(self, steps: int) -> int: ...

    def set_signal_program(self, signal_id: str, program_id: str) -> int: ...

    def set_speed_limit(self, target: str, speed_mps: float) -> int: ...

    def close_lane(self, lane_id: str, vehicle_classes: tuple[str, ...]) -> int: ...

    def open_lane(self, lane_id: str) -> int: ...

    def inject_incident(self, edge_id: str, severity: float) -> int: ...

    def clear_incident(self, edge_id: str) -> int: ...

    def set_route_demand(
        self, route_id: str, multiplier: float, sequence: int, maximum_added: int
    ) -> int: ...

    def apply_route_policy(self, route_id: str) -> int: ...

    def close(self) -> None: ...


class ProcessLauncher(Protocol):
    def __call__(
        self, argv: tuple[str, ...], working_directory: Path, environment: Mapping[str, str]
    ) -> ManagedProcess: ...


class ProtocolConnector(Protocol):
    def __call__(
        self,
        control_port: int,
        tools_root: Path,
        process: ManagedProcess,
        timeout_seconds: float,
    ) -> LocalSumoProtocol: ...


@dataclass(frozen=True)
class LocalSumoDependencies:
    runtime_resolver: Callable[[], ResolvedLocalSumoRuntime]
    port_allocator: Callable[[], int]
    launcher: ProcessLauncher
    connector: ProtocolConnector


class _SimulationDomain(Protocol):
    def getTime(self) -> float: ...  # noqa: N802 - external TraCI API


class _VehicleDomain(Protocol):
    def getIDList(self) -> tuple[str, ...]: ...  # noqa: N802 - external TraCI API

    def getSpeed(self, vehicle_id: str) -> float: ...  # noqa: N802 - external TraCI API

    def setRouteID(self, vehicle_id: str, route_id: str) -> None: ...  # noqa: N802

    def add(self, vehicle_id: str, route_id: str, *, depart: str) -> None: ...


class _EdgeDomain(Protocol):
    def getIDList(self) -> tuple[str, ...]: ...  # noqa: N802

    def setMaxSpeed(self, edge_id: str, speed: float) -> None: ...  # noqa: N802


class _LaneDomain(Protocol):
    def getIDList(self) -> tuple[str, ...]: ...  # noqa: N802

    def getMaxSpeed(self, lane_id: str) -> float: ...  # noqa: N802

    def setMaxSpeed(self, lane_id: str, speed: float) -> None: ...  # noqa: N802

    def setDisallowed(self, lane_id: str, classes: list[str]) -> None: ...  # noqa: N802


class _RouteDomain(Protocol):
    def getIDList(self) -> tuple[str, ...]: ...  # noqa: N802


class _TrafficLightDomain(Protocol):
    def getIDList(self) -> tuple[str, ...]: ...  # noqa: N802

    def setProgram(self, signal_id: str, program_id: str) -> None: ...  # noqa: N802


class _TraCIConnection(Protocol):
    simulation: _SimulationDomain
    vehicle: _VehicleDomain
    edge: _EdgeDomain
    lane: _LaneDomain
    route: _RouteDomain
    trafficlight: _TrafficLightDomain

    def getVersion(self) -> tuple[int, str]: ...  # noqa: N802

    def simulationStep(self, step: float = 0.0) -> None: ...  # noqa: N802

    def close(self, wait: bool = True) -> None: ...


class _TraCIModule(Protocol):
    def connect(
        self,
        *,
        port: int,
        numRetries: int,  # noqa: N803 - external TraCI API
        host: str,
        proc: None,
        waitBetweenRetries: float,  # noqa: N803 - external TraCI API
        label: str,
    ) -> _TraCIConnection: ...


class _PopenHandle:
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process

    @property
    def stdout(self) -> TextIO | None:
        return cast(TextIO | None, self._process.stdout)

    def poll(self) -> int | None:
        return self._process.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self._process.wait(timeout=timeout)

    def terminate_group(self) -> None:
        try:
            os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return

    def kill_group(self) -> None:
        try:
            os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            return


class _BoundedOutputCollector:
    def __init__(self, stream: TextIO | None, maximum_bytes: int) -> None:
        self._stream = stream
        self._maximum = maximum_bytes
        self._observed = 0
        self._digest = hashlib.sha256()
        self._overflow = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def overflow(self) -> bool:
        with self._lock:
            return self._overflow

    def start(self) -> None:
        if self._stream is None:
            return
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def join(self, timeout: float) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _drain(self) -> None:
        assert self._stream is not None
        while chunk := self._stream.read(4_096):
            payload = chunk.encode("utf-8", errors="replace")
            with self._lock:
                self._observed += len(payload)
                self._digest.update(payload)
                if self._observed > self._maximum:
                    self._overflow = True


class _TraCIProtocolAdapter:
    def __init__(self, connection: _TraCIConnection) -> None:
        self._connection = connection
        self._inventory = LocalSumoInventory(
            edge_ids=tuple(sorted(connection.edge.getIDList())),
            lane_ids=tuple(sorted(connection.lane.getIDList())),
            route_ids=tuple(sorted(connection.route.getIDList())),
            signal_ids=tuple(sorted(connection.trafficlight.getIDList())),
        )
        self._lane_speeds = {
            lane_id: float(connection.lane.getMaxSpeed(lane_id))
            for lane_id in self._inventory.lane_ids
        }
        self._edge_speeds = {
            edge_id: max(
                (
                    speed
                    for lane_id, speed in self._lane_speeds.items()
                    if lane_id.startswith(f"{edge_id}_")
                ),
                default=0.1,
            )
            for edge_id in self._inventory.edge_ids
        }
        self._incident_edges: set[str] = set()

    def heartbeat(self) -> bool:
        try:
            self._connection.getVersion()
        except Exception:
            return False
        return True

    def inventory(self) -> LocalSumoInventory:
        return self._inventory

    def read_aggregates(self) -> Mapping[str, float]:
        vehicle_ids = tuple(self._connection.vehicle.getIDList())
        speeds = tuple(float(self._connection.vehicle.getSpeed(item)) for item in vehicle_ids)
        mean_speed = sum(speeds) / len(speeds) if speeds else 0.0
        queued = sum(1 for speed in speeds if speed <= 0.1)
        return {
            "simulation_time_s": float(self._connection.simulation.getTime()),
            "vehicle_count": float(len(vehicle_ids)),
            "mean_speed_mps": mean_speed,
            "queue_indicator": float(queued),
            "incident_count": float(len(self._incident_edges)),
            "session_healthy": 1.0,
        }

    def step(self, steps: int) -> int:
        for _ in range(steps):
            self._connection.simulationStep()
        return steps

    def set_signal_program(self, signal_id: str, program_id: str) -> int:
        self._connection.trafficlight.setProgram(signal_id, program_id)
        return 1

    def set_speed_limit(self, target: str, speed_mps: float) -> int:
        if target in self._inventory.edge_ids:
            self._connection.edge.setMaxSpeed(target, speed_mps)
        else:
            self._connection.lane.setMaxSpeed(target, speed_mps)
        return 1

    def close_lane(self, lane_id: str, vehicle_classes: tuple[str, ...]) -> int:
        self._connection.lane.setDisallowed(lane_id, list(vehicle_classes))
        return 1

    def open_lane(self, lane_id: str) -> int:
        self._connection.lane.setDisallowed(lane_id, [])
        return 1

    def inject_incident(self, edge_id: str, severity: float) -> int:
        original = self._edge_speeds[edge_id]
        self._connection.edge.setMaxSpeed(edge_id, max(0.1, original * (1.0 - severity)))
        self._incident_edges.add(edge_id)
        return 1

    def clear_incident(self, edge_id: str) -> int:
        self._connection.edge.setMaxSpeed(edge_id, self._edge_speeds[edge_id])
        self._incident_edges.discard(edge_id)
        return 1

    def set_route_demand(
        self, route_id: str, multiplier: float, sequence: int, maximum_added: int
    ) -> int:
        requested = max(0, math.ceil(multiplier) - 1)
        count = min(requested, maximum_added)
        for index in range(count):
            synthetic_id = f"tt-local-demand-{sequence}-{index}"
            self._connection.vehicle.add(synthetic_id, route_id, depart="now")
        return count

    def apply_route_policy(self, route_id: str) -> int:
        vehicle_ids = tuple(self._connection.vehicle.getIDList())
        for vehicle_id in vehicle_ids:
            self._connection.vehicle.setRouteID(vehicle_id, route_id)
        return len(vehicle_ids)

    def close(self) -> None:
        try:
            self._connection.close(wait=False)
        except Exception:
            return


class LocalSumoProcess:
    """Real process/protocol adapter satisfying the existing ``ControlProcess`` contract."""

    def __init__(
        self,
        *,
        preparation: LocalSumoPreparation,
        command_policy: LocalSumoCommandPolicy,
        process: ManagedProcess,
        protocol: LocalSumoProtocol,
        collector: _BoundedOutputCollector,
        staged_root: Path,
        source_root: Path,
        process_grace_seconds: float,
    ) -> None:
        self.preparation = preparation
        self._policy = command_policy
        self._process = process
        self._protocol = protocol
        self._collector = collector
        self._staged_root = staged_root
        self._source_root = source_root
        self._grace = process_grace_seconds
        self._terminated = False
        self._lock = threading.Lock()
        self._validate_inventory(protocol.inventory())

    def _validate_inventory(self, inventory: LocalSumoInventory) -> None:
        signals = {grant.signal_id for grant in self._policy.signal_programs}
        if not set(self._policy.edge_ids) <= set(inventory.edge_ids):
            raise LocalSumoTransportError(
                "SUMO_TARGET_INVENTORY_MISMATCH", "edge allowlist is absent from the live network"
            )
        if not set(self._policy.lane_ids) <= set(inventory.lane_ids):
            raise LocalSumoTransportError(
                "SUMO_TARGET_INVENTORY_MISMATCH", "lane allowlist is absent from the live network"
            )
        if not set(self._policy.route_ids) <= set(inventory.route_ids):
            raise LocalSumoTransportError(
                "SUMO_TARGET_INVENTORY_MISMATCH", "route allowlist is absent from live demand"
            )
        if not signals <= set(inventory.signal_ids):
            raise LocalSumoTransportError(
                "SUMO_TARGET_INVENTORY_MISMATCH", "signal allowlist is absent from the live network"
            )

    def alive(self) -> bool:
        return (
            not self._terminated
            and self._process.poll() is None
            and not self._collector.overflow
            and _inventory_matches(self._source_root, self.preparation.input_inventory)
            and _inventory_matches(self._staged_root, self.preparation.input_inventory)
        )

    def heartbeat(self) -> bool:
        return self.alive() and self._protocol.heartbeat()

    def read_aggregates(self) -> Mapping[str, float]:
        return self._protocol.read_aggregates()

    def apply_command(self, command: TwinCommand) -> ProcessCommandResult:
        if command.kind not in _SUPPORTED_COMMANDS:
            raise LocalSumoTransportError(
                "COMMAND_NOT_ALLOWLISTED", "command has no local-SUMO implementation"
            )
        affected = self._dispatch(command)
        return ProcessCommandResult(
            values={"operation": command.kind, "affected_aggregate_count": affected},
            external_effect_performed=False,
        )

    def _dispatch(self, command: TwinCommand) -> int:
        if command.kind in {"pause", "resume"}:
            _require_no_parameters(command)
            return 0
        if command.kind == "step":
            steps = _integer_parameter(
                command, "steps", minimum=1, maximum=self._policy.maximum_step_batch
            )
            return self._protocol.step(steps)
        if command.kind == "set_signal_program":
            grant = next(
                (item for item in self._policy.signal_programs if item.signal_id == command.target),
                None,
            )
            if grant is None:
                raise _target_refusal("signal")
            program_id = _string_parameter(command, "program_id")
            if program_id not in grant.program_ids:
                raise LocalSumoTransportError(
                    "COMMAND_NOT_ALLOWLISTED", "signal program is not allowlisted"
                )
            return self._protocol.set_signal_program(command.target, program_id)
        if command.kind == "set_speed_limit":
            if command.target not in {*self._policy.edge_ids, *self._policy.lane_ids}:
                raise _target_refusal("speed")
            speed = _number_parameter(
                command,
                "speed_mps",
                minimum=self._policy.minimum_speed_mps,
                maximum=self._policy.maximum_speed_mps,
            )
            return self._protocol.set_speed_limit(command.target, speed)
        if command.kind in {"close_lane", "open_lane"}:
            if command.target not in self._policy.lane_ids:
                raise _target_refusal("lane")
            _require_no_parameters(command)
            if command.kind == "close_lane":
                return self._protocol.close_lane(
                    command.target, tuple(self._policy.closed_vehicle_classes)
                )
            return self._protocol.open_lane(command.target)
        if command.kind in {"inject_incident", "clear_incident"}:
            if command.target not in self._policy.edge_ids:
                raise _target_refusal("incident edge")
            if command.kind == "clear_incident":
                _require_no_parameters(command)
                return self._protocol.clear_incident(command.target)
            severity = _number_parameter(
                command,
                "severity",
                minimum=0.01,
                maximum=self._policy.maximum_incident_severity,
            )
            return self._protocol.inject_incident(command.target, severity)
        if command.kind == "set_route_demand":
            if command.target not in self._policy.route_ids:
                raise _target_refusal("route")
            multiplier = _number_parameter(
                command,
                "demand_multiplier",
                minimum=1.0,
                maximum=self._policy.maximum_demand_multiplier,
            )
            return self._protocol.set_route_demand(
                command.target,
                multiplier,
                command.sequence,
                self._policy.maximum_added_vehicles_per_command,
            )
        if command.kind == "set_vehicle_route_policy":
            policy_id = _string_parameter(command, "route_policy_id")
            route_grant = next(
                (item for item in self._policy.route_policies if item.policy_id == policy_id),
                None,
            )
            if route_grant is None or command.target not in self._policy.route_ids:
                raise _target_refusal("route policy")
            return self._protocol.apply_route_policy(route_grant.route_id)
        raise LocalSumoTransportError(
            "COMMAND_NOT_ALLOWLISTED", "command has no local-SUMO implementation"
        )

    def apply_aggregate_mobility(self, update: AggregateMobilityUpdate) -> ProcessCommandResult:
        del update
        raise LocalSumoTransportError(
            "BODS_BRIDGE_NOT_CONFIGURED", "the local-SUMO transport has no live-input bridge"
        )

    def terminate(self) -> None:
        with self._lock:
            if self._terminated:
                return
            self._terminated = True
        self._protocol.close()
        if self._process.poll() is None:
            self._process.terminate_group()
            try:
                self._process.wait(timeout=self._grace)
            except subprocess.TimeoutExpired:
                self._process.kill_group()
                with suppress(subprocess.TimeoutExpired):
                    self._process.wait(timeout=self._grace)
        self._collector.join(self._grace)
        shutil.rmtree(self._staged_root, ignore_errors=True)


def fixed_local_sumo_command_policy() -> LocalSumoCommandPolicy:
    """Return the closed command policy for the pinned synthetic-square scenario."""

    return LocalSumoCommandPolicy(
        scenario_digest=local_sumo_scenario_digest(),
        edge_ids=("E0",),
        lane_ids=("E0_0",),
        route_ids=("square_loop",),
        signal_programs=(),
        route_policies=(RoutePolicyGrant(policy_id="square_loop", route_id="square_loop"),),
    )


def local_sumo_scenario_digest() -> str:
    """Return the exact pinned preset fingerprint expected by session specs."""

    preset, _ = _validated_fixture()
    return preset.fingerprint()


def local_sumo_network_digest() -> str:
    """Return the exact pinned synthetic network digest expected by session specs."""

    _, inventory = _validated_fixture()
    return next(item.sha256 for item in inventory if item.name == SCENARIO_NET_FILE)


def local_sumo_readiness(
    dependencies: LocalSumoDependencies | None = None,
) -> LocalSumoReadiness:
    """Report path-free runtime and fixture readiness without starting a process."""

    active = dependencies or default_local_sumo_dependencies()
    status = sumo_runtime_status()
    try:
        runtime = active.runtime_resolver()
        preset, inventory = _validated_fixture()
    except LocalSumoTransportError as exc:
        return LocalSumoReadiness(
            ready=False,
            reason=str(exc),
            runtime=status,
            traci_tools_bound=False,
        )
    network = next(item.sha256 for item in inventory if item.name == SCENARIO_NET_FILE)
    return LocalSumoReadiness(
        ready=True,
        reason=f"SUMO {runtime.status.version} and the pinned synthetic fixture are ready",
        runtime=runtime.status,
        preset_digest=preset.fingerprint(),
        network_digest=network,
        command_policy_digest=fixed_local_sumo_command_policy().digest(),
        traci_tools_bound=True,
    )


def prepare_local_sumo_transport(
    spec: LiveTwinSessionSpec,
    *,
    control_port: int,
    command_policy: LocalSumoCommandPolicy | None = None,
    dependencies: LocalSumoDependencies | None = None,
) -> LocalSumoPreparation:
    """Validate and bind a path-free local process preparation without launching."""

    active = dependencies or default_local_sumo_dependencies()
    runtime = active.runtime_resolver()
    return _prepare_with_runtime(
        spec,
        runtime,
        control_port=control_port,
        command_policy=command_policy or fixed_local_sumo_command_policy(),
    )


def start_local_sumo_transport(
    spec: LiveTwinSessionSpec,
    *,
    command_policy: LocalSumoCommandPolicy | None = None,
    dependencies: LocalSumoDependencies | None = None,
) -> LocalSumoProcess:
    """Start the pinned local process and return an injected controller transport."""

    active = dependencies or default_local_sumo_dependencies()
    policy = command_policy or fixed_local_sumo_command_policy()
    runtime = active.runtime_resolver()
    port = active.port_allocator()
    preparation = _prepare_with_runtime(
        spec,
        runtime,
        control_port=port,
        command_policy=policy,
    )
    staged_root = Path(tempfile.mkdtemp(prefix="traffictwin-local-sumo-"))
    process: ManagedProcess | None = None
    collector: _BoundedOutputCollector | None = None
    protocol: LocalSumoProtocol | None = None
    try:
        _stage_fixture(staged_root, preparation.input_inventory)
        if _sha256(
            runtime.executable
        ) != preparation.runtime_executable_digest or not _inventory_matches(
            preset_scenario_root(), preparation.input_inventory
        ):
            raise LocalSumoTransportError(
                "DIGEST_MISMATCH", "runtime or source fixture changed immediately before launch"
            )
        actual_argv = (str(runtime.executable), *preparation.argv[1:])
        process = active.launcher(
            actual_argv,
            staged_root,
            _controlled_environment(runtime, staged_root),
        )
        collector = _BoundedOutputCollector(process.stdout, policy.maximum_output_bytes)
        collector.start()
        protocol = active.connector(
            port,
            runtime.tools_root,
            process,
            policy.connection_timeout_seconds,
        )
        return LocalSumoProcess(
            preparation=preparation,
            command_policy=policy,
            process=process,
            protocol=protocol,
            collector=collector,
            staged_root=staged_root,
            source_root=preset_scenario_root(),
            process_grace_seconds=policy.process_grace_seconds,
        )
    except Exception as exc:
        if protocol is not None:
            protocol.close()
        if process is not None:
            _stop_process(process, policy.process_grace_seconds)
        if collector is not None:
            collector.join(policy.process_grace_seconds)
        shutil.rmtree(staged_root, ignore_errors=True)
        if isinstance(exc, LiveTwinError):
            raise
        raise LocalSumoTransportError(
            "CONTROL_PROTOCOL_LOST", "local SUMO process startup or TraCI connection failed"
        ) from exc


def local_sumo_process_factory(
    spec: LiveTwinSessionSpec,
    *,
    command_policy: LocalSumoCommandPolicy | None = None,
    dependencies: LocalSumoDependencies | None = None,
) -> Callable[[], LocalSumoProcess]:
    """Return the process factory injected into ``LiveTwinController``."""

    return lambda: start_local_sumo_transport(
        spec,
        command_policy=command_policy,
        dependencies=dependencies,
    )


def default_local_sumo_dependencies() -> LocalSumoDependencies:
    return LocalSumoDependencies(
        runtime_resolver=_resolve_runtime,
        port_allocator=_allocate_loopback_port,
        launcher=_launch_process,
        connector=_connect_traci,
    )


def _prepare_with_runtime(
    spec: LiveTwinSessionSpec,
    runtime: ResolvedLocalSumoRuntime,
    *,
    control_port: int,
    command_policy: LocalSumoCommandPolicy,
) -> LocalSumoPreparation:
    if not _MIN_CONTROL_PORT <= control_port <= _MAX_CONTROL_PORT:
        raise LocalSumoTransportError(
            "LOCAL_PORT_INVALID", "loopback control port is outside the bounded range"
        )
    preset, inventory = _validated_fixture()
    scenario_digest = preset.fingerprint()
    network_digest = next(item.sha256 for item in inventory if item.name == SCENARIO_NET_FILE)
    configuration_digest = next(
        item.sha256 for item in inventory if item.name == SCENARIO_CONFIG_FILE
    )
    if spec.execution_backend != "local_sumo" or spec.access_surface != "local_library":
        raise LocalSumoTransportError(
            "BACKEND_MISMATCH", "transport requires local_sumo and local_library"
        )
    if spec.mode not in {"observe_only", "simulation_closed_loop"}:
        raise LocalSumoTransportError(
            "BACKEND_MISMATCH", "local SUMO cannot enter operator-site mode"
        )
    if spec.seed != preset.random_seed:
        raise LocalSumoTransportError("DIGEST_MISMATCH", "session seed differs from the preset")
    if spec.scenario_digest != scenario_digest or spec.network_digest != network_digest:
        raise LocalSumoTransportError(
            "DIGEST_MISMATCH", "session scenario or network differs from the pinned fixture"
        )
    runtime_version = runtime.status.version
    runtime_digest = runtime.status.executable_sha256
    if runtime_version is None or runtime_digest is None or not runtime.status.supported:
        raise LocalSumoTransportError("SUMO_RUNTIME_UNAVAILABLE", "SUMO runtime is unsupported")
    if spec.tool_versions.get("sumo") != runtime_version:
        raise LocalSumoTransportError(
            "DIGEST_MISMATCH", "session tool version differs from the discovered SUMO runtime"
        )
    if command_policy.scenario_digest != scenario_digest:
        raise LocalSumoTransportError(
            "DIGEST_MISMATCH", "command policy targets a different scenario"
        )
    expected_tool_bindings = {
        "local_sumo_transport": METHOD_VERSION,
        "local_sumo_command_policy": command_policy.digest(),
        "sumo_executable_sha256": runtime_digest,
    }
    if any(spec.tool_versions.get(key) != value for key, value in expected_tool_bindings.items()):
        raise LocalSumoTransportError(
            "DIGEST_MISMATCH",
            "session spec does not bind the exact transport, command policy and executable",
        )
    if spec.max_simulation_seconds > min(_MAX_SIMULATION_SECONDS, preset.end_s):
        raise LocalSumoTransportError(
            "BUDGET_EXCEEDED", "simulation-time budget exceeds the pinned fixture window"
        )
    if spec.max_wall_clock_seconds > _MAX_WALL_CLOCK_SECONDS or spec.max_commands > _MAX_COMMANDS:
        raise LocalSumoTransportError(
            "BUDGET_EXCEEDED", "wall-clock or command budget exceeds local transport bounds"
        )
    if spec.max_estimated_cost_gbp != 0:
        raise LocalSumoTransportError(
            "BUDGET_EXCEEDED", "local synthetic transport requires a zero external-cost budget"
        )
    if any(
        grant.surface != "simulation" or grant.kind not in _SUPPORTED_COMMANDS
        for grant in spec.command_allowlist
    ):
        raise LocalSumoTransportError(
            "COMMAND_NOT_ALLOWLISTED", "session grants contain unsupported local commands"
        )
    granted_kinds = {grant.kind for grant in spec.command_allowlist}
    if "set_signal_program" in granted_kinds and not command_policy.signal_programs:
        raise LocalSumoTransportError(
            "COMMAND_NOT_ALLOWLISTED", "session grants signals but no signal target is bound"
        )
    if "set_vehicle_route_policy" in granted_kinds and not command_policy.route_policies:
        raise LocalSumoTransportError(
            "COMMAND_NOT_ALLOWLISTED", "session grants route policy but no policy target is bound"
        )
    if (
        spec.bods_bridge is not None
        or spec.public_api is not None
        or spec.cloud is not None
        or spec.plugins
    ):
        raise LocalSumoTransportError(
            "BACKEND_MISMATCH", "local transport cannot bind BODS, public, cloud or plugins"
        )
    argv = _path_free_argv(spec, control_port)
    return LocalSumoPreparation(
        session_spec_digest=spec.digest(),
        preset_digest=scenario_digest,
        network_digest=network_digest,
        configuration_digest=configuration_digest,
        input_inventory=inventory,
        runtime_version=runtime_version,
        runtime_executable_digest=runtime_digest,
        command_policy_digest=command_policy.digest(),
        control_port=control_port,
        argv=argv,
    )


def _path_free_argv(spec: LiveTwinSessionSpec, control_port: int) -> tuple[str, ...]:
    return (
        "sumo",
        "-c",
        SCENARIO_CONFIG_FILE,
        "--remote-port",
        str(control_port),
        "--seed",
        str(spec.seed),
        "--begin",
        "0",
        "--end",
        str(spec.max_simulation_seconds),
        "--no-step-log",
        "true",
        "--quit-on-end",
        "true",
    )


def _validated_fixture() -> tuple[SumoRunPreset, tuple[LocalSumoInputIdentity, ...]]:
    preset = preset_definition(SumoExecutionPreset.SYNTHETIC_SQUARE_SMOKE)
    root = preset_scenario_root()
    if root.is_symlink() or not root.is_dir():
        raise LocalSumoTransportError(
            "SUMO_FIXTURE_INVALID", "pinned scenario root is missing or unsafe"
        )
    identities: list[LocalSumoInputIdentity] = []
    for item in preset.inputs:
        path = root / item.name
        if (
            path.is_symlink()
            or not path.is_file()
            or path.resolve().parent != root.resolve()
            or path.stat().st_size != item.size_bytes
            or _sha256(path) != item.sha256
        ):
            raise LocalSumoTransportError(
                "SUMO_FIXTURE_INVALID", f"pinned scenario input changed: {item.name}"
            )
        identities.append(
            LocalSumoInputIdentity(
                name=item.name,
                sha256=item.sha256,
                size_bytes=item.size_bytes,
            )
        )
    return preset, tuple(identities)


def _inventory_matches(root: Path, inventory: tuple[LocalSumoInputIdentity, ...]) -> bool:
    try:
        return all(
            not (root / item.name).is_symlink()
            and (root / item.name).is_file()
            and (root / item.name).stat().st_size == item.size_bytes
            and _sha256(root / item.name) == item.sha256
            for item in inventory
        )
    except OSError:
        return False


def _stage_fixture(staged_root: Path, inventory: tuple[LocalSumoInputIdentity, ...]) -> None:
    source = preset_scenario_root()
    for item in inventory:
        target = staged_root / item.name
        shutil.copyfile(source / item.name, target)
        target.chmod(0o444)
    if not _inventory_matches(staged_root, inventory):
        raise LocalSumoTransportError(
            "SUMO_FIXTURE_INVALID", "private staged fixture failed identity verification"
        )


def _resolve_runtime() -> ResolvedLocalSumoRuntime:
    status = sumo_runtime_status()
    located = shutil.which("sumo")
    if not status.supported or located is None:
        raise LocalSumoTransportError("SUMO_RUNTIME_UNAVAILABLE", status.reason)
    try:
        executable = Path(located).resolve(strict=True)
    except OSError as exc:
        raise LocalSumoTransportError(
            "SUMO_RUNTIME_UNAVAILABLE", "the SUMO executable no longer resolves"
        ) from exc
    if executable.is_symlink() or not executable.is_file():
        raise LocalSumoTransportError(
            "SUMO_RUNTIME_UNAVAILABLE", "the SUMO executable is not a regular file"
        )
    if status.executable_sha256 != _sha256(executable):
        raise LocalSumoTransportError(
            "DIGEST_MISMATCH", "the SUMO executable changed after runtime discovery"
        )
    candidates = (
        executable.parent.parent / "tools",
        executable.parent.parent / "share" / "sumo" / "tools",
    )
    tools_root = next(
        (
            candidate.resolve()
            for candidate in candidates
            if candidate.is_dir() and (candidate / "traci" / "__init__.py").is_file()
        ),
        None,
    )
    if tools_root is None:
        raise LocalSumoTransportError(
            "TRACI_TOOLS_UNAVAILABLE", "matching TraCI tools were not found with the SUMO runtime"
        )
    return ResolvedLocalSumoRuntime(
        status=status,
        executable=executable,
        tools_root=tools_root,
    )


def _allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        port = int(handle.getsockname()[1])
    if not _MIN_CONTROL_PORT <= port <= _MAX_CONTROL_PORT:
        raise LocalSumoTransportError(
            "LOCAL_PORT_INVALID", "the OS returned an invalid loopback port"
        )
    return port


def _launch_process(
    argv: tuple[str, ...], working_directory: Path, environment: Mapping[str, str]
) -> ManagedProcess:
    process = subprocess.Popen(  # noqa: S603 - fixed validated argv, never a shell
        argv,
        cwd=working_directory,
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        shell=False,
        close_fds=True,
        start_new_session=True,
    )
    return _PopenHandle(process)


def _controlled_environment(
    runtime: ResolvedLocalSumoRuntime, staged_root: Path
) -> Mapping[str, str]:
    return {
        "PATH": f"{runtime.executable.parent}:/usr/bin:/bin",
        "HOME": str(staged_root),
        "TMPDIR": str(staged_root),
        "SUMO_HOME": str(runtime.tools_root.parent),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }


_TRACI_IMPORT_LOCK = threading.Lock()


def _connect_traci(
    control_port: int,
    tools_root: Path,
    process: ManagedProcess,
    timeout_seconds: float,
) -> LocalSumoProtocol:
    del process
    module = _load_traci(tools_root)
    retries = max(1, math.ceil(timeout_seconds / 0.1))
    try:
        connection = module.connect(
            port=control_port,
            numRetries=retries,
            host="127.0.0.1",
            proc=None,
            waitBetweenRetries=0.1,
            label=f"traffictwin-{control_port}",
        )
    except Exception as exc:
        raise LocalSumoTransportError(
            "CONTROL_PROTOCOL_LOST", "bounded loopback TraCI connection failed"
        ) from exc
    return _TraCIProtocolAdapter(connection)


def _load_traci(tools_root: Path) -> _TraCIModule:
    init_path = (tools_root / "traci" / "__init__.py").resolve()
    if tools_root.resolve() not in init_path.parents or not init_path.is_file():
        raise LocalSumoTransportError(
            "TRACI_TOOLS_UNAVAILABLE", "TraCI module is outside the bound SUMO tools root"
        )
    with _TRACI_IMPORT_LOCK:
        existing = sys.modules.get("traci")
        if existing is not None:
            _validate_traci_module(existing, tools_root)
            return cast(_TraCIModule, existing)
        sys.path.insert(0, str(tools_root))
        try:
            module = importlib.import_module("traci")
        finally:
            with suppress(ValueError):
                sys.path.remove(str(tools_root))
        _validate_traci_module(module, tools_root)
        return cast(_TraCIModule, module)


def _validate_traci_module(module: ModuleType, tools_root: Path) -> None:
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str):
        raise LocalSumoTransportError(
            "TRACI_TOOLS_UNAVAILABLE", "TraCI module has no verifiable source identity"
        )
    resolved = Path(module_file).resolve()
    if tools_root.resolve() not in resolved.parents:
        raise LocalSumoTransportError(
            "TRACI_TOOLS_UNAVAILABLE", "loaded TraCI module differs from the bound SUMO runtime"
        )


def _stop_process(process: ManagedProcess, grace_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate_group()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill_group()
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            return


def _require_no_parameters(command: TwinCommand) -> None:
    if command.parameters:
        raise LocalSumoTransportError("COMMAND_PARAMETER_INVALID", "command accepts no parameters")


def _number_parameter(command: TwinCommand, key: str, *, minimum: float, maximum: float) -> float:
    if set(command.parameters) != {key}:
        raise LocalSumoTransportError(
            "COMMAND_PARAMETER_INVALID", f"command requires only the {key} parameter"
        )
    value = command.parameters[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LocalSumoTransportError("COMMAND_PARAMETER_INVALID", f"{key} must be numeric")
    number = float(value)
    if not minimum <= number <= maximum:
        raise LocalSumoTransportError(
            "COMMAND_PARAMETER_INVALID", f"{key} is outside its bounded range"
        )
    return number


def _integer_parameter(command: TwinCommand, key: str, *, minimum: int, maximum: int) -> int:
    value = _number_parameter(command, key, minimum=minimum, maximum=maximum)
    if not value.is_integer():
        raise LocalSumoTransportError("COMMAND_PARAMETER_INVALID", f"{key} must be an integer")
    return int(value)


def _string_parameter(command: TwinCommand, key: str) -> str:
    if set(command.parameters) != {key}:
        raise LocalSumoTransportError(
            "COMMAND_PARAMETER_INVALID", f"command requires only the {key} parameter"
        )
    value = command.parameters[key]
    if not isinstance(value, str):
        raise LocalSumoTransportError("COMMAND_PARAMETER_INVALID", f"{key} must be a string")
    try:
        return _validate_safe_id(value, label=key)
    except ValueError as exc:
        raise LocalSumoTransportError("COMMAND_PARAMETER_INVALID", str(exc)) from exc


def _target_refusal(target_type: str) -> LocalSumoTransportError:
    return LocalSumoTransportError(
        "COMMAND_NOT_ALLOWLISTED", f"{target_type} target is not allowlisted"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
