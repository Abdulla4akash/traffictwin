"""Controlled live-twin adapter (post-v1 L-1): bounded, attended, receipted.

Implements ``docs/platform/controlled_live_twin_adapter_design.md``: a
tightly bounded interactive engineering session over a process-backed SUMO
simulation. "Live" means owner-attended foreground with controlled state
exchange — never a live city replica, never production control, never
authority to run an experiment, and never a daemon: this module contains no
detach surface at all.

The non-negotiables are structural:

- the session spec binds network/scenario digests, tool versions, seed,
  mode, allowlist and REQUIRED resource budgets before anything starts;
- default mode is observe-only; a mutation allowlist exists only behind a
  policy-valid human approval, and every command carries the scenario digest
  and a monotonic sequence — stale or unlisted commands refuse;
- exactly one controller owns a session; the state machine is
  ``prepared -> running -> stopping -> completed/refused`` and EVERY
  terminal path emits a typed receipt (heartbeat loss, budget breach,
  protocol mismatch, clean stop);
- snapshots are aggregate-only and identifier-screened; no vehicle identity
  leaves the adapter;
- TraCI traffic state is never described as VEC RSU compute capacity — a
  capacity-named command refuses by name, because traffic capacity, signal
  control and RSU compute capacity are different variables;
- a session is an engineering demonstration, ``evidence: false``; scientific
  use refuses without a separately frozen protocol and human approval.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

METHOD_VERSION: Literal["live-twin-adapter-1.0"] = "live-twin-adapter-1.0"
DESIGN_REFERENCE: Literal["docs/platform/controlled_live_twin_adapter_design.md"] = (
    "docs/platform/controlled_live_twin_adapter_design.md"
)

SessionMode = Literal["observe_only", "controlled_intervention"]
SessionState = Literal["prepared", "running", "stopping", "completed", "refused"]

#: Snapshot keys the adapter may emit — aggregates only.
ALLOWED_SNAPSHOT_KEYS = (
    "simulation_time_s",
    "vehicle_count",
    "mean_speed_mps",
    "queue_indicator",
    "session_healthy",
)
#: Key fragments that would leak identity or private content.
_FORBIDDEN_SNAPSHOT_MARKERS = ("vehicle_id", "ref", "token", "/Users/", "/home/")
_FORBIDDEN_IDENTITY_MARKERS = ("agent", "tbd", "n/a", "claude", "codex", "llm", "auto")
#: Command names that would conflate traffic state with VEC compute capacity.
_CAPACITY_CONFLATION_MARKERS = ("rsu_capacity", "compute_capacity", "vec_capacity")


class LiveTwinError(RuntimeError):
    """Typed refusal; the adapter fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TwinModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class MutationApproval(TwinModel):
    """The separate owner opt-in a mutation allowlist requires."""

    approved_by: str = Field(min_length=1, max_length=200)
    approved_at_utc: str
    scope_note: str

    @model_validator(mode="after")
    def refuse_agent_identities(self) -> MutationApproval:
        lowered = self.approved_by.lower()
        for marker in _FORBIDDEN_IDENTITY_MARKERS:
            if marker in lowered:
                raise ValueError(
                    "mutation scope needs a policy-valid human approval; agent "
                    "identities and placeholders are never approval"
                )
        return self


class LiveTwinSessionSpec(TwinModel):
    """Everything bound BEFORE startup; budgets are required, not optional."""

    network_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    scenario_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_versions: dict[str, str]
    seed: int = Field(ge=0)
    mode: SessionMode = "observe_only"
    command_allowlist: tuple[str, ...] = ()
    mutation_approval: MutationApproval | None = None
    max_simulation_seconds: int = Field(ge=1)
    max_wall_clock_seconds: int = Field(ge=1)
    owner_attended: bool
    fail_safe_policy: Literal["stop_on_close"] = "stop_on_close"

    @model_validator(mode="after")
    def validate_spec(self) -> LiveTwinSessionSpec:
        if not self.owner_attended:
            raise ValueError(
                "OWNER_PRESENCE_REQUIRED: live-twin sessions are owner-attended foreground only"
            )
        if self.mode == "observe_only" and self.command_allowlist:
            raise ValueError("observe-only sessions carry no command allowlist")
        if self.mode == "controlled_intervention":
            if not self.command_allowlist:
                raise ValueError("controlled intervention needs a versioned allowlist")
            if self.mutation_approval is None:
                raise ValueError(
                    "APPROVAL_MISSING: a mutation allowlist exists only behind a "
                    "separate owner approval"
                )
        for command in self.command_allowlist:
            lowered = command.lower()
            for marker in _CAPACITY_CONFLATION_MARKERS:
                if marker in lowered:
                    raise ValueError(
                        f"command '{command}' conflates traffic state with VEC RSU "
                        "compute capacity; the variables are different and no "
                        "reviewed integration model maps them"
                    )
        return self

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class TwinSnapshot(TwinModel):
    """Aggregate-only view of the running simulation."""

    snapshot_index: int = Field(ge=1)
    values: dict[str, float]
    evidence: Literal[False] = False


class TwinCommand(TwinModel):
    name: str
    scenario_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_sequence: int = Field(ge=1)
    changes_treatment: bool = False
    actor_class: Literal["owner_ui"] = "owner_ui"


class CommandReceipt(TwinModel):
    name: str
    sequence: int
    deviation_recorded: bool


class LiveTwinReceipt(TwinModel):
    """The terminal receipt every session path must emit."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["live-twin-adapter-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/controlled_live_twin_adapter_design.md"] = (
        DESIGN_REFERENCE
    )
    spec_digest: str
    final_state: Literal["completed", "refused"]
    stop_reason: str
    snapshots_emitted: int = Field(ge=0)
    commands_applied: int = Field(ge=0)
    command_ledger_digest: str
    deviations: tuple[str, ...]
    experiment_use_invalidated: bool
    evidence: Literal[False] = False
    scientific_use: Literal[False] = False
    engineering_label: Literal["engineering demonstration only"] = "engineering demonstration only"


class ControlProcess(Protocol):
    """The bounded process contract; tests supply a deterministic fake."""

    def alive(self) -> bool: ...

    def heartbeat(self) -> bool: ...

    def read_aggregates(self) -> Mapping[str, float]: ...

    def terminate(self) -> None: ...


def sumo_argument_vector(
    spec: LiveTwinSessionSpec, network_file_name: str, control_port: int
) -> list[str]:
    """The exact bounded SUMO argv — fixed executable, never a shell string."""

    if "/" in network_file_name or network_file_name.startswith("."):
        raise LiveTwinError(
            "PRIVATE_CONTENT_DETECTED",
            "the network is referenced by bare file name inside the session "
            "workspace, never by path",
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
    """Exactly one controller per session; every exit path is receipted."""

    def __init__(
        self,
        spec: LiveTwinSessionSpec,
        process_factory: Callable[[], ControlProcess],
        *,
        wall_clock: Callable[[], float],
    ) -> None:
        self._spec = spec
        self._factory = process_factory
        self._clock = wall_clock
        self._state: SessionState = "prepared"
        self._process: ControlProcess | None = None
        self._started_at: float | None = None
        self._snapshots = 0
        self._sequence = 0
        self._ledger: list[str] = []
        self._deviations: list[str] = []
        self._receipt: LiveTwinReceipt | None = None
        self._owned = False

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def receipt(self) -> LiveTwinReceipt | None:
        return self._receipt

    def start(self) -> str:
        if self._owned or self._state != "prepared":
            raise LiveTwinError(
                "SESSION_ALREADY_OWNED",
                "exactly one controller owns a session; this one already started",
            )
        self._owned = True
        self._process = self._factory()
        self._started_at = self._clock()
        self._state = "running"
        return self._spec.digest()

    def _require_running(self) -> ControlProcess:
        if self._state != "running" or self._process is None:
            raise LiveTwinError(
                "CONTROL_PROTOCOL_LOST", f"the session is '{self._state}', not running"
            )
        return self._process

    def _check_health(self, process: ControlProcess) -> None:
        assert self._started_at is not None
        if self._clock() - self._started_at > self._spec.max_wall_clock_seconds:
            self._fail_safe_stop("BUDGET_EXCEEDED: wall-clock budget breached")
            raise LiveTwinError(
                "BUDGET_EXCEEDED", "the wall-clock budget was breached; fail-safe stop"
            )
        if not process.alive() or not process.heartbeat():
            self._fail_safe_stop("CONTROL_PROTOCOL_LOST: heartbeat lost")
            raise LiveTwinError(
                "CONTROL_PROTOCOL_LOST", "the control heartbeat was lost; fail-safe stop"
            )

    def read_snapshot(self) -> TwinSnapshot:
        process = self._require_running()
        self._check_health(process)
        raw = dict(process.read_aggregates())
        for key in raw:
            lowered = key.lower()
            if key not in ALLOWED_SNAPSHOT_KEYS or any(
                marker in lowered for marker in _FORBIDDEN_SNAPSHOT_MARKERS
            ):
                self._fail_safe_stop("PRIVATE_CONTENT_DETECTED: non-aggregate key")
                raise LiveTwinError(
                    "PRIVATE_CONTENT_DETECTED",
                    f"the control process emitted a non-aggregate key '{key}'; no "
                    "identifier leaves the adapter",
                )
        self._snapshots += 1
        return TwinSnapshot(snapshot_index=self._snapshots, values=raw)

    def apply_command(self, command: TwinCommand) -> CommandReceipt:
        process = self._require_running()
        self._check_health(process)
        if self._spec.mode == "observe_only":
            raise LiveTwinError(
                "COMMAND_NOT_ALLOWLISTED",
                "observe-only sessions accept no command at all; mutation is a "
                "separate owner opt-in",
            )
        if command.name not in self._spec.command_allowlist:
            raise LiveTwinError(
                "COMMAND_NOT_ALLOWLISTED",
                f"'{command.name}' is not on the approved allowlist",
            )
        if command.scenario_digest != self._spec.scenario_digest:
            raise LiveTwinError(
                "DIGEST_MISMATCH",
                "the command binds a different scenario digest than this session",
            )
        if command.expected_sequence != self._sequence + 1:
            raise LiveTwinError(
                "STATE_SEQUENCE_MISMATCH",
                f"expected sequence {self._sequence + 1}, got "
                f"{command.expected_sequence}; stale commands refuse",
            )
        self._sequence += 1
        deviation = False
        if command.changes_treatment:
            deviation = True
            self._deviations.append(
                f"treatment-changing command '{command.name}' at sequence "
                f"{self._sequence}: experiment use invalidated"
            )
        self._ledger.append(f"{self._sequence}:{command.name}")
        return CommandReceipt(
            name=command.name, sequence=self._sequence, deviation_recorded=deviation
        )

    def _fail_safe_stop(self, reason: str) -> None:
        if self._process is not None:
            self._process.terminate()
        self._state = "refused"
        self._emit_receipt("refused", reason)

    def stop(self, reason: str) -> LiveTwinReceipt:
        if self._state == "running" and self._process is not None:
            self._state = "stopping"
            self._process.terminate()
            self._state = "completed"
            self._emit_receipt("completed", reason)
        if self._receipt is None:
            raise LiveTwinError("CONTROL_PROTOCOL_LOST", "no session ran; nothing to receipt")
        return self._receipt

    def _emit_receipt(self, final_state: Literal["completed", "refused"], reason: str) -> None:
        ledger_digest = hashlib.sha256("\n".join(self._ledger).encode("utf-8")).hexdigest()
        self._receipt = LiveTwinReceipt(
            spec_digest=self._spec.digest(),
            final_state=final_state,
            stop_reason=reason,
            snapshots_emitted=self._snapshots,
            commands_applied=self._sequence,
            command_ledger_digest=ledger_digest,
            deviations=tuple(self._deviations),
            experiment_use_invalidated=bool(self._deviations),
        )


def mark_scientific_use(receipt: LiveTwinReceipt) -> None:
    """Scientific standing is not this adapter's to grant — ever."""

    del receipt
    raise LiveTwinError(
        "SCIENTIFIC_USE_UNAUTHORISED",
        "an interactive session is an engineering demonstration; scientific use "
        "requires a separately frozen protocol, accepted human approval, the "
        "unmodified instrument boundary, and an admission decision",
    )
