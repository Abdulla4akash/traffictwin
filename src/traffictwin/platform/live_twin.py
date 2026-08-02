"""Maximum-coverage controlled live-twin contracts with deterministic fakes.

The adapter supports observe-only, closed-loop simulation and preauthorised
operator-site sessions.  It also models authenticated public access,
unattended cloud scheduling, aggregate upstream-compliant mobility updates,
stream events and allowlisted plugins.  This module itself performs no
network request, cloud allocation, live acquisition or road actuation: those
effects require an injected adapter and exact authority bindings.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

METHOD_VERSION: Literal["live-twin-adapter-2.0"] = "live-twin-adapter-2.0"
DESIGN_REFERENCE: Literal["docs/platform/controlled_live_twin_adapter_design.md"] = (
    "docs/platform/controlled_live_twin_adapter_design.md"
)

SessionMode = Literal["observe_only", "simulation_closed_loop", "operator_site_closed_loop"]
SessionState = Literal["prepared", "running", "paused", "stopping", "completed", "refused"]
ExecutionBackend = Literal["local_fake", "local_sumo", "gcp_batch", "aws_batch", "operator_site"]
AccessSurface = Literal["local_library", "authenticated_public_api", "cloud_scheduler"]
CommandSurface = Literal["simulation", "real_infrastructure", "platform"]
CapacityDomain = Literal["road_traffic", "rsu_compute"]
PluginKind = Literal["traffic_model", "vec_model", "controller", "metric", "event_sink"]
CloudProvider = Literal["gcp", "aws"]
EventType = Literal["session", "snapshot", "command", "mobility", "heartbeat", "terminal"]
CommandKind = Literal[
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
    "set_road_capacity",
    "set_rsu_compute_capacity",
    "set_actor_family",
    "set_observation_contract",
    "set_action_contract",
    "set_reward_contract",
    "set_seed_namespace",
    "load_scenario_revision",
    "set_budget",
    "checkpoint",
    "restore_checkpoint",
    "start_sweep",
    "stop_sweep",
    "inject_fault",
    "publish_recommendation",
    "select_default",
    "apply_instruction_draft",
    "invoke_plugin",
]

ALLOWED_SNAPSHOT_KEYS = (
    "simulation_time_s",
    "vehicle_count",
    "mean_speed_mps",
    "queue_indicator",
    "incident_count",
    "road_capacity_index",
    "rsu_compute_utilisation",
    "deadline_completion_rate",
    "mean_latency_ms",
    "mean_energy_j",
    "session_healthy",
)
ALLOWED_MOBILITY_AGGREGATE_KEYS = (
    "vehicle_count",
    "mean_speed_mps",
    "queue_indicator",
    "incident_count",
    "route_demand_index",
)
ALLOWED_COMMAND_PARAMETER_KEYS = (
    "value",
    "steps",
    "program_id",
    "speed_mps",
    "lane_group",
    "severity",
    "demand_multiplier",
    "route_policy_id",
    "actor_family",
    "contract_digest",
    "seed_namespace",
    "scenario_revision_digest",
    "budget_digest",
    "checkpoint_digest",
    "sweep_digest",
    "fault_profile_id",
    "recommendation_digest",
    "default_option_id",
    "instruction_draft_digest",
    "plugin_request_digest",
)
_PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "\\Users\\",
    "password",
    "secret",
    "token",
    "credential",
    "vehicle_id",
    "operator_id",
)
_REAL_ACTUATION_KINDS: set[CommandKind] = {
    "set_signal_program",
    "set_speed_limit",
    "close_lane",
    "open_lane",
    "inject_incident",
    "clear_incident",
    "set_road_capacity",
    "set_rsu_compute_capacity",
}
_TREATMENT_COMMANDS: set[CommandKind] = {
    "set_signal_program",
    "set_speed_limit",
    "close_lane",
    "open_lane",
    "inject_incident",
    "clear_incident",
    "set_route_demand",
    "set_vehicle_route_policy",
    "set_road_capacity",
    "set_rsu_compute_capacity",
    "set_actor_family",
    "set_observation_contract",
    "set_action_contract",
    "set_reward_contract",
    "set_seed_namespace",
    "load_scenario_revision",
    "set_budget",
    "restore_checkpoint",
    "start_sweep",
    "inject_fault",
    "apply_instruction_draft",
    "invoke_plugin",
}
_ACTIVE_SESSION_DIGESTS: set[str] = set()


class LiveTwinError(RuntimeError):
    """Typed refusal; the adapter fails closed and receipts terminal paths."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TwinModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


def _contains_private_material(value: object) -> bool:
    material = json.dumps(value, sort_keys=True).lower()
    return any(marker.lower() in material for marker in _PRIVATE_MARKERS)


class CommandGrant(TwinModel):
    kind: CommandKind
    surface: CommandSurface

    @model_validator(mode="after")
    def validate_surface(self) -> CommandGrant:
        if self.surface == "real_infrastructure" and self.kind not in _REAL_ACTUATION_KINDS:
            raise ValueError("real-infrastructure grants require an infrastructure command")
        return self


class BodsBridgePolicy(TwinModel):
    upstream_terms_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    licence_class: str
    aggregate_schema_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    unattended: bool
    respects_upstream_rate_policy: Literal[True] = True
    honours_retry_after: Literal[True] = True
    exponential_backoff: Literal[True] = True
    self_imposed_rate_limit: None = None
    raw_bytes_retained: Literal[False] = False
    identifiers_retained: Literal[False] = False
    max_staleness_seconds: int = Field(ge=1)


class PublicApiPolicy(TwinModel):
    auth_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authentication_required: Literal[True] = True
    tls_required: Literal[True] = True
    request_signing_required: Literal[True] = True
    idempotency_required: Literal[True] = True
    allowed_roles: tuple[str, ...] = Field(min_length=1)
    maximum_request_age_seconds: int = Field(ge=1)


class CloudExecutionPolicy(TwinModel):
    provider: CloudProvider
    account_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    region_allowlist: tuple[str, ...] = Field(min_length=1)
    maximum_instances: int = Field(ge=1)
    maximum_estimated_cost_gbp: float = Field(ge=0)
    unattended: Literal[True] = True
    spend_authority_external: Literal[True] = True


class PluginContract(TwinModel):
    plugin_id: str
    plugin_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: PluginKind
    command_grants: tuple[CommandGrant, ...] = ()
    arbitrary_code_from_request: Literal[False] = False


class EventSubscription(TwinModel):
    subscription_id: str
    event_types: tuple[EventType, ...] = Field(min_length=1)
    delivery: Literal["local_stream", "authenticated_webhook"]
    destination_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class LiveTwinSessionSpec(TwinModel):
    """All capability, authority and budgets bound before startup."""

    session_id: str
    controller_id: str
    network_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_versions: dict[str, str]
    seed: int = Field(ge=0)
    mode: SessionMode
    execution_backend: ExecutionBackend
    access_surface: AccessSurface
    max_simulation_seconds: int = Field(ge=1)
    max_wall_clock_seconds: int = Field(ge=1)
    max_commands: int = Field(ge=0)
    max_estimated_cost_gbp: float = Field(ge=0)
    unattended: bool
    per_command_human_approval_required: Literal[False] = False
    command_allowlist: tuple[CommandGrant, ...] = ()
    authority_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    operator_policy_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    bods_bridge: BodsBridgePolicy | None = None
    public_api: PublicApiPolicy | None = None
    cloud: CloudExecutionPolicy | None = None
    plugins: tuple[PluginContract, ...] = ()
    subscriptions: tuple[EventSubscription, ...] = ()
    fail_safe_policy: Literal["stop_on_budget_heartbeat_or_policy_loss"] = (
        "stop_on_budget_heartbeat_or_policy_loss"
    )

    @model_validator(mode="after")
    def validate_spec(self) -> LiveTwinSessionSpec:
        if _contains_private_material(self.model_dump(mode="json")):
            raise ValueError("session spec contains private, identity or credential material")
        grants = [(grant.kind, grant.surface) for grant in self.command_allowlist]
        if len(set(grants)) != len(grants):
            raise ValueError("command grants must be unique")
        if self.mode == "observe_only" and self.command_allowlist:
            raise ValueError("observe-only sessions cannot carry command grants")
        if self.mode == "simulation_closed_loop" and any(
            grant.surface == "real_infrastructure" for grant in self.command_allowlist
        ):
            raise ValueError("simulation sessions cannot carry real-infrastructure grants")
        if self.mode == "operator_site_closed_loop":
            if self.execution_backend != "operator_site":
                raise ValueError("operator-site mode requires the operator-site backend")
            if self.authority_digest is None or self.operator_policy_digest is None:
                raise ValueError("operator-site mode requires bound authority and operator policy")
        if self.execution_backend == "operator_site" and self.mode != "operator_site_closed_loop":
            raise ValueError("the operator-site backend requires operator-site mode")
        if self.execution_backend in {"gcp_batch", "aws_batch"}:
            if self.cloud is None:
                raise ValueError("cloud backends require a bounded cloud execution policy")
            expected = "gcp" if self.execution_backend == "gcp_batch" else "aws"
            if self.cloud.provider != expected:
                raise ValueError("cloud backend and provider must match")
            if self.max_estimated_cost_gbp > self.cloud.maximum_estimated_cost_gbp:
                raise ValueError("session cost budget exceeds its external cloud authority")
        elif self.cloud is not None:
            raise ValueError("a cloud policy is valid only for a cloud backend")
        if self.access_surface == "authenticated_public_api" and self.public_api is None:
            raise ValueError("public API access requires an authentication policy")
        if self.access_surface != "authenticated_public_api" and self.public_api is not None:
            raise ValueError("public API policy supplied for a non-public surface")
        if self.bods_bridge is not None and self.bods_bridge.unattended != self.unattended:
            raise ValueError("BODS bridge attendance must match the session")
        plugin_ids = [plugin.plugin_id for plugin in self.plugins]
        if len(set(plugin_ids)) != len(plugin_ids):
            raise ValueError("plugin ids must be unique")
        subscription_ids = [item.subscription_id for item in self.subscriptions]
        if len(set(subscription_ids)) != len(subscription_ids):
            raise ValueError("event subscription ids must be unique")
        return self

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class TwinSnapshot(TwinModel):
    snapshot_index: int = Field(ge=1)
    values: dict[str, float]
    evidence: Literal[False] = False
    scientific_use: Literal[False] = False

    @model_validator(mode="after")
    def validate_values(self) -> TwinSnapshot:
        if not set(self.values) <= set(ALLOWED_SNAPSHOT_KEYS) or _contains_private_material(
            self.values
        ):
            raise ValueError("snapshot contains a non-aggregate field")
        return self


class TwinCommand(TwinModel):
    command_id: str
    idempotency_key: str
    session_spec_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sequence: int = Field(ge=1)
    kind: CommandKind
    surface: CommandSurface
    target: str
    parameters: dict[str, str | int | float | bool]
    capacity_domain: CapacityDomain | None = None
    expected_state: Literal["running", "paused"]
    authority_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    changes_scientific_treatment: bool
    estimated_cost_gbp: float = Field(ge=0)
    plugin_id: str | None = None

    @model_validator(mode="after")
    def validate_command(self) -> TwinCommand:
        if _contains_private_material(self.model_dump(mode="json")):
            raise ValueError("command contains private, identity or credential material")
        if not set(self.parameters) <= set(ALLOWED_COMMAND_PARAMETER_KEYS):
            raise ValueError("command parameters contain a key outside the typed allowlist")
        if self.surface == "real_infrastructure" and self.kind not in _REAL_ACTUATION_KINDS:
            raise ValueError("command is not a real-infrastructure operation")
        if self.kind == "set_road_capacity" and self.capacity_domain != "road_traffic":
            raise ValueError("road capacity commands require capacity_domain=road_traffic")
        if self.kind == "set_rsu_compute_capacity" and self.capacity_domain != "rsu_compute":
            raise ValueError("RSU commands require capacity_domain=rsu_compute")
        if self.kind not in {"set_road_capacity", "set_rsu_compute_capacity"} and (
            self.capacity_domain is not None
        ):
            raise ValueError("capacity_domain is valid only on an explicit capacity command")
        if self.kind in _TREATMENT_COMMANDS and not self.changes_scientific_treatment:
            raise ValueError("treatment-changing commands must declare the change")
        if self.kind == "invoke_plugin" and self.plugin_id is None:
            raise ValueError("invoke_plugin requires a plugin id")
        if self.kind != "invoke_plugin" and self.plugin_id is not None:
            raise ValueError("plugin id is valid only for invoke_plugin")
        return self

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class ProcessCommandResult(TwinModel):
    values: dict[str, str | int | float | bool]
    external_effect_performed: bool

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class CommandReceipt(TwinModel):
    command_id: str
    command_digest: str
    sequence: int
    state_after: SessionState
    process_result_digest: str
    external_effect_performed: bool
    estimated_cost_gbp: float
    idempotent_retry: bool
    evidence: Literal[False] = False
    creates_scientific_evidence: Literal[False] = False


class AggregateMobilityUpdate(TwinModel):
    update_id: str
    sequence: int = Field(ge=1)
    schema_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_staleness_seconds: int = Field(ge=0)
    upstream_retry_after_observed: bool
    aggregates: dict[str, float]
    raw_bytes_present: Literal[False] = False
    identifiers_present: Literal[False] = False

    @model_validator(mode="after")
    def validate_aggregates(self) -> AggregateMobilityUpdate:
        for key in self.aggregates:
            lowered = key.lower()
            if key not in ALLOWED_MOBILITY_AGGREGATE_KEYS or any(
                marker.lower() in lowered for marker in _PRIVATE_MARKERS
            ):
                raise ValueError("mobility update contains a non-aggregate field")
        return self

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AggregateMobilityReceipt(TwinModel):
    update_id: str
    sequence: int
    source_receipt_digest: str
    process_result_digest: str
    idempotent_retry: bool
    evidence: Literal[False] = False
    raw_bytes_retained: Literal[False] = False
    identifiers_retained: Literal[False] = False


class TwinEvent(TwinModel):
    event_type: EventType
    session_spec_digest: str
    sequence: int = Field(ge=0)
    payload_digest: str
    external_delivery_attempted: bool


class LiveTwinReceipt(TwinModel):
    schema_version: Literal["2.0"] = "2.0"
    method_version: Literal["live-twin-adapter-2.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/controlled_live_twin_adapter_design.md"] = (
        DESIGN_REFERENCE
    )
    spec_digest: str
    final_state: Literal["completed", "refused"]
    stop_reason: str
    snapshots_emitted: int = Field(ge=0)
    mobility_updates_applied: int = Field(ge=0)
    commands_applied: int = Field(ge=0)
    estimated_cost_gbp: float = Field(ge=0)
    command_ledger_digest: str
    deviations: tuple[str, ...]
    experiment_use_invalidated: bool
    any_external_effect_performed: bool
    evidence: Literal[False] = False
    scientific_use: Literal[False] = False
    production_ready: Literal[False] = False
    execution_authority_created: Literal[False] = False
    engineering_label: Literal["controlled engineering/operations receipt"] = (
        "controlled engineering/operations receipt"
    )

    @model_validator(mode="after")
    def validate_safe_receipt(self) -> LiveTwinReceipt:
        if _contains_private_material(self.model_dump(mode="json")):
            raise ValueError("terminal receipt contains private material")
        return self


class AuthenticatedControlRequest(TwinModel):
    request_id: str
    actor_role: str
    auth_context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_time_seconds: float
    command: TwinCommand


class ControlProcess(Protocol):
    def alive(self) -> bool: ...

    def heartbeat(self) -> bool: ...

    def read_aggregates(self) -> Mapping[str, float]: ...

    def apply_command(self, command: TwinCommand) -> ProcessCommandResult: ...

    def apply_aggregate_mobility(self, update: AggregateMobilityUpdate) -> ProcessCommandResult: ...

    def terminate(self) -> None: ...


class RequestAuthorizer(Protocol):
    def authorize(self, request: AuthenticatedControlRequest, policy: PublicApiPolicy) -> bool: ...


class EventSink(Protocol):
    def publish(self, event: TwinEvent) -> bool: ...


def sumo_argument_vector(
    spec: LiveTwinSessionSpec, network_file_name: str, control_port: int
) -> list[str]:
    """Bounded local SUMO argv; never a shell string or caller executable."""

    if spec.execution_backend != "local_sumo":
        raise LiveTwinError("BACKEND_MISMATCH", "SUMO argv requires the local_sumo backend")
    if "/" in network_file_name or network_file_name.startswith("."):
        raise LiveTwinError(
            "PRIVATE_CONTENT_DETECTED",
            "the network must be a bare file name in the prepared workspace",
        )
    return [
        "sumo",
        "--net-file",
        network_file_name,
        "--seed",
        str(spec.seed),
        "--remote-port",
        str(control_port),
        "--no-step-log",
        "--end",
        str(spec.max_simulation_seconds),
    ]


class LiveTwinController:
    """Single-owner state machine with idempotent commands and terminal receipts."""

    def __init__(
        self,
        spec: LiveTwinSessionSpec,
        process_factory: Callable[[], ControlProcess],
        *,
        wall_clock: Callable[[], float],
        event_sink: EventSink | None = None,
    ) -> None:
        self._spec = spec
        self._factory = process_factory
        self._clock = wall_clock
        self._event_sink = event_sink
        self._state: SessionState = "prepared"
        self._process: ControlProcess | None = None
        self._started_at: float | None = None
        self._snapshots = 0
        self._mobility_sequence = 0
        self._mobility_receipts: dict[str, AggregateMobilityReceipt] = {}
        self._mobility_digests: dict[str, str] = {}
        self._command_sequence = 0
        self._ledger: list[str] = []
        self._command_receipts: dict[str, CommandReceipt] = {}
        self._command_digests: dict[str, str] = {}
        self._deviations: list[str] = []
        self._external_effect = False
        self._estimated_cost_gbp = 0.0
        self._receipt: LiveTwinReceipt | None = None
        self._owned = False
        self._session_digest = spec.digest()

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def receipt(self) -> LiveTwinReceipt | None:
        return self._receipt

    def _emit_event(self, event_type: EventType, payload: str) -> None:
        if self._event_sink is None:
            return
        subscriptions = [
            item for item in self._spec.subscriptions if event_type in item.event_types
        ]
        if not subscriptions:
            return
        event = TwinEvent(
            event_type=event_type,
            session_spec_digest=self._session_digest,
            sequence=self._command_sequence,
            payload_digest=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            external_delivery_attempted=any(
                item.delivery == "authenticated_webhook" for item in subscriptions
            ),
        )
        if not self._event_sink.publish(event):
            self._deviations.append(f"event delivery failed: {event_type}")

    def start(self) -> str:
        if (
            self._owned
            or self._state != "prepared"
            or self._session_digest in _ACTIVE_SESSION_DIGESTS
        ):
            raise LiveTwinError("SESSION_ALREADY_OWNED", "exactly one controller owns a session")
        _ACTIVE_SESSION_DIGESTS.add(self._session_digest)
        self._owned = True
        try:
            self._process = self._factory()
        except Exception as exc:
            _ACTIVE_SESSION_DIGESTS.discard(self._session_digest)
            self._state = "refused"
            self._emit_receipt("refused", "CONTROL_PROTOCOL_LOST: process startup failed")
            raise LiveTwinError("CONTROL_PROTOCOL_LOST", "control process startup failed") from exc
        self._started_at = self._clock()
        self._state = "running"
        self._emit_event("session", "started")
        return self._session_digest

    def _require_active(self) -> ControlProcess:
        if self._state not in {"running", "paused"} or self._process is None:
            raise LiveTwinError("CONTROL_PROTOCOL_LOST", f"session is '{self._state}', not active")
        return self._process

    def _check_health(self, process: ControlProcess) -> None:
        assert self._started_at is not None
        if self._clock() - self._started_at > self._spec.max_wall_clock_seconds:
            self._fail_safe_stop("BUDGET_EXCEEDED: wall-clock budget breached")
            raise LiveTwinError("BUDGET_EXCEEDED", "wall-clock budget breached")
        if not process.alive() or not process.heartbeat():
            self._fail_safe_stop("CONTROL_PROTOCOL_LOST: heartbeat lost")
            raise LiveTwinError("CONTROL_PROTOCOL_LOST", "control heartbeat lost")
        self._emit_event("heartbeat", "healthy")

    def read_snapshot(self) -> TwinSnapshot:
        process = self._require_active()
        self._check_health(process)
        raw = dict(process.read_aggregates())
        for key in raw:
            lowered = key.lower()
            if key not in ALLOWED_SNAPSHOT_KEYS or any(
                marker.lower() in lowered for marker in _PRIVATE_MARKERS
            ):
                self._fail_safe_stop("PRIVATE_CONTENT_DETECTED: non-aggregate snapshot key")
                raise LiveTwinError(
                    "PRIVATE_CONTENT_DETECTED",
                    "control process emitted a non-aggregate snapshot key",
                )
        if raw.get("simulation_time_s", 0.0) > self._spec.max_simulation_seconds:
            self._fail_safe_stop("BUDGET_EXCEEDED: simulation-time budget breached")
            raise LiveTwinError("BUDGET_EXCEEDED", "simulation-time budget breached")
        self._snapshots += 1
        snapshot = TwinSnapshot(snapshot_index=self._snapshots, values=raw)
        self._emit_event("snapshot", snapshot.model_dump_json())
        return snapshot

    def _grant_for(self, command: TwinCommand) -> CommandGrant | None:
        return next(
            (
                grant
                for grant in self._spec.command_allowlist
                if grant.kind == command.kind and grant.surface == command.surface
            ),
            None,
        )

    def apply_command(self, command: TwinCommand) -> CommandReceipt:
        process = self._require_active()
        self._check_health(process)
        if self._spec.mode == "observe_only":
            raise LiveTwinError("COMMAND_NOT_ALLOWLISTED", "observe-only mode accepts no commands")
        if command.session_spec_digest != self._session_digest:
            raise LiveTwinError("DIGEST_MISMATCH", "command targets a different session spec")
        digest = command.digest()
        previous_digest = self._command_digests.get(command.idempotency_key)
        if previous_digest is not None:
            if previous_digest != digest:
                raise LiveTwinError(
                    "IDEMPOTENCY_CONFLICT", "idempotency key was reused with changes"
                )
            previous = self._command_receipts[command.idempotency_key]
            return previous.model_copy(update={"idempotent_retry": True})
        if command.sequence != self._command_sequence + 1:
            raise LiveTwinError("STATE_SEQUENCE_MISMATCH", "command sequence is not next")
        if command.expected_state != self._state:
            raise LiveTwinError("STATE_SEQUENCE_MISMATCH", "command expected a different state")
        if self._grant_for(command) is None:
            raise LiveTwinError("COMMAND_NOT_ALLOWLISTED", "command kind/surface is not granted")
        if command.surface == "real_infrastructure":
            if self._spec.mode != "operator_site_closed_loop":
                raise LiveTwinError(
                    "AUTHORITY_MISSING", "real actuation requires operator-site mode"
                )
            if command.authority_digest != self._spec.authority_digest:
                raise LiveTwinError(
                    "AUTHORITY_MISSING", "command lacks the bound operator authority"
                )
        if self._command_sequence >= self._spec.max_commands:
            self._fail_safe_stop("BUDGET_EXCEEDED: command budget breached")
            raise LiveTwinError("BUDGET_EXCEEDED", "command budget breached")
        if (
            self._estimated_cost_gbp + command.estimated_cost_gbp
            > self._spec.max_estimated_cost_gbp
        ):
            self._fail_safe_stop("BUDGET_EXCEEDED: estimated-cost budget breached")
            raise LiveTwinError("BUDGET_EXCEEDED", "estimated-cost budget breached")
        if command.kind == "invoke_plugin" and command.plugin_id not in {
            plugin.plugin_id for plugin in self._spec.plugins
        }:
            raise LiveTwinError("PLUGIN_NOT_ALLOWLISTED", "plugin is not bound to the session")

        result = process.apply_command(command)
        self._command_sequence = command.sequence
        if command.kind == "pause":
            self._state = "paused"
        elif command.kind == "resume":
            self._state = "running"
        if command.changes_scientific_treatment:
            self._deviations.append(f"command {command.sequence} changed treatment: {command.kind}")
        self._external_effect = self._external_effect or result.external_effect_performed
        self._estimated_cost_gbp += command.estimated_cost_gbp
        self._ledger.append(digest)
        receipt = CommandReceipt(
            command_id=command.command_id,
            command_digest=digest,
            sequence=command.sequence,
            state_after=self._state,
            process_result_digest=result.digest(),
            external_effect_performed=result.external_effect_performed,
            estimated_cost_gbp=command.estimated_cost_gbp,
            idempotent_retry=False,
        )
        self._command_digests[command.idempotency_key] = digest
        self._command_receipts[command.idempotency_key] = receipt
        self._emit_event("command", receipt.model_dump_json())
        return receipt

    def apply_aggregate_mobility(self, update: AggregateMobilityUpdate) -> AggregateMobilityReceipt:
        process = self._require_active()
        self._check_health(process)
        policy = self._spec.bods_bridge
        if policy is None:
            raise LiveTwinError(
                "BODS_BRIDGE_NOT_CONFIGURED", "session has no aggregate BODS bridge"
            )
        digest = update.digest()
        previous_digest = self._mobility_digests.get(update.update_id)
        if previous_digest is not None:
            if previous_digest != digest:
                raise LiveTwinError(
                    "IDEMPOTENCY_CONFLICT", "mobility update id was reused with changes"
                )
            previous = self._mobility_receipts[update.update_id]
            return previous.model_copy(update={"idempotent_retry": True})
        if update.sequence != self._mobility_sequence + 1:
            raise LiveTwinError("STATE_SEQUENCE_MISMATCH", "mobility sequence is not next")
        if update.schema_digest != policy.aggregate_schema_digest:
            raise LiveTwinError("DIGEST_MISMATCH", "mobility aggregate schema changed")
        if update.observed_staleness_seconds > policy.max_staleness_seconds:
            raise LiveTwinError("LIVE_INPUT_STALE", "mobility aggregate exceeded staleness policy")
        result = process.apply_aggregate_mobility(update)
        self._mobility_sequence = update.sequence
        self._external_effect = self._external_effect or result.external_effect_performed
        receipt = AggregateMobilityReceipt(
            update_id=update.update_id,
            sequence=update.sequence,
            source_receipt_digest=update.source_receipt_digest,
            process_result_digest=result.digest(),
            idempotent_retry=False,
        )
        self._mobility_digests[update.update_id] = digest
        self._mobility_receipts[update.update_id] = receipt
        self._emit_event("mobility", receipt.model_dump_json())
        return receipt

    def _fail_safe_stop(self, reason: str) -> None:
        if self._process is not None:
            self._process.terminate()
        self._state = "refused"
        _ACTIVE_SESSION_DIGESTS.discard(self._session_digest)
        self._emit_receipt("refused", reason)

    def stop(self, reason: str) -> LiveTwinReceipt:
        if _contains_private_material(reason):
            self._deviations.append(
                "supplied stop reason contained private material and was withheld"
            )
            reason = "PRIVATE_CONTENT_DETECTED: supplied stop reason withheld"
        if self._state in {"running", "paused"} and self._process is not None:
            self._state = "stopping"
            self._process.terminate()
            self._state = "completed"
            _ACTIVE_SESSION_DIGESTS.discard(self._session_digest)
            self._emit_receipt("completed", reason)
        if self._receipt is None:
            raise LiveTwinError("CONTROL_PROTOCOL_LOST", "no session ran; nothing to receipt")
        return self._receipt

    def _emit_receipt(self, final_state: Literal["completed", "refused"], reason: str) -> None:
        ledger_digest = hashlib.sha256("\n".join(self._ledger).encode("utf-8")).hexdigest()
        self._receipt = LiveTwinReceipt(
            spec_digest=self._session_digest,
            final_state=final_state,
            stop_reason=reason,
            snapshots_emitted=self._snapshots,
            mobility_updates_applied=self._mobility_sequence,
            commands_applied=self._command_sequence,
            estimated_cost_gbp=self._estimated_cost_gbp,
            command_ledger_digest=ledger_digest,
            deviations=tuple(self._deviations),
            experiment_use_invalidated=bool(self._deviations),
            any_external_effect_performed=self._external_effect,
        )
        self._emit_event("terminal", self._receipt.model_dump_json())


class AuthenticatedControlAdapter:
    """Authentication boundary for a public API transport supplied elsewhere."""

    def __init__(
        self,
        spec: LiveTwinSessionSpec,
        controller: LiveTwinController,
        authorizer: RequestAuthorizer,
        *,
        wall_clock: Callable[[], float],
    ) -> None:
        if spec.public_api is None or spec.access_surface != "authenticated_public_api":
            raise LiveTwinError("PUBLIC_API_NOT_CONFIGURED", "session has no public API policy")
        self._spec = spec
        self._controller = controller
        self._authorizer = authorizer
        self._clock = wall_clock

    def submit(self, request: AuthenticatedControlRequest) -> CommandReceipt:
        policy = self._spec.public_api
        assert policy is not None
        if request.actor_role not in policy.allowed_roles:
            raise LiveTwinError("AUTHENTICATION_FAILED", "actor role is not allowed")
        age = self._clock() - request.request_time_seconds
        if age < 0 or age > policy.maximum_request_age_seconds:
            raise LiveTwinError("REQUEST_EXPIRED", "authenticated request is outside its age bound")
        if not self._authorizer.authorize(request, policy):
            raise LiveTwinError("AUTHENTICATION_FAILED", "request proof did not verify")
        return self._controller.apply_command(request.command)


def mark_scientific_use(receipt: LiveTwinReceipt) -> None:
    """A control receipt does not itself admit a scientific result."""

    del receipt
    raise LiveTwinError(
        "SCIENTIFIC_USE_UNAUTHORISED",
        "engineering/operations receipts create no scientific evidence or admission",
    )
