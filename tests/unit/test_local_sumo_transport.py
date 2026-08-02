"""Concrete local-SUMO transport tests with injected fakes and one bounded real smoke."""

from __future__ import annotations

import io
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

import pytest

from traffictwin.integration.sumo_execution.models import SumoRuntimeStatus
from traffictwin.integration.sumo_execution.service import preset_scenario_root
from traffictwin.platform.live_twin import (
    CommandGrant,
    LiveTwinController,
    LiveTwinError,
    LiveTwinSessionSpec,
    TwinCommand,
)
from traffictwin.platform.local_sumo_transport import (
    LocalSumoCommandPolicy,
    LocalSumoDependencies,
    LocalSumoInventory,
    LocalSumoPreparation,
    LocalSumoProtocol,
    LocalSumoTransportError,
    ResolvedLocalSumoRuntime,
    RoutePolicyGrant,
    SignalProgramGrant,
    fixed_local_sumo_command_policy,
    local_sumo_network_digest,
    local_sumo_process_factory,
    local_sumo_readiness,
    local_sumo_scenario_digest,
    prepare_local_sumo_transport,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FakeManagedProcess:
    def __init__(self, output: str = "", *, stubborn: bool = False) -> None:
        self._exit_code: int | None = None
        self._stubborn = stubborn
        self.stdout = io.StringIO(output)
        self.terminate_calls = 0
        self.kill_calls = 0

    def poll(self) -> int | None:
        return self._exit_code

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self._exit_code is None:
            raise subprocess.TimeoutExpired("sumo", 0.01)
        return self._exit_code

    def terminate_group(self) -> None:
        self.terminate_calls += 1
        if not self._stubborn:
            self._exit_code = -15

    def kill_group(self) -> None:
        self.kill_calls += 1
        self._exit_code = -9

    def crash(self) -> None:
        self._exit_code = 2


class FakeProtocol(LocalSumoProtocol):
    def __init__(
        self,
        *,
        inventory: LocalSumoInventory | None = None,
        aggregates: Mapping[str, float] | None = None,
        healthy: bool = True,
    ) -> None:
        self._inventory = inventory or LocalSumoInventory(
            edge_ids=("E0",),
            lane_ids=("E0_0",),
            route_ids=("square_loop",),
            signal_ids=(),
        )
        self.aggregates = dict(
            aggregates
            or {
                "simulation_time_s": 0.0,
                "vehicle_count": 0.0,
                "mean_speed_mps": 0.0,
                "queue_indicator": 0.0,
                "incident_count": 0.0,
                "session_healthy": 1.0,
            }
        )
        self.healthy = healthy
        self.closed = False
        self.calls: list[tuple[object, ...]] = []

    def heartbeat(self) -> bool:
        return self.healthy

    def inventory(self) -> LocalSumoInventory:
        return self._inventory

    def read_aggregates(self) -> Mapping[str, float]:
        return self.aggregates

    def step(self, steps: int) -> int:
        self.calls.append(("step", steps))
        self.aggregates["simulation_time_s"] += float(steps)
        return steps

    def set_signal_program(self, signal_id: str, program_id: str) -> int:
        self.calls.append(("signal", signal_id, program_id))
        return 1

    def set_speed_limit(self, target: str, speed_mps: float) -> int:
        self.calls.append(("speed", target, speed_mps))
        return 1

    def close_lane(self, lane_id: str, vehicle_classes: tuple[str, ...]) -> int:
        self.calls.append(("close_lane", lane_id, vehicle_classes))
        return 1

    def open_lane(self, lane_id: str) -> int:
        self.calls.append(("open_lane", lane_id))
        return 1

    def inject_incident(self, edge_id: str, severity: float) -> int:
        self.calls.append(("inject_incident", edge_id, severity))
        self.aggregates["incident_count"] = 1.0
        return 1

    def clear_incident(self, edge_id: str) -> int:
        self.calls.append(("clear_incident", edge_id))
        self.aggregates["incident_count"] = 0.0
        return 1

    def set_route_demand(
        self, route_id: str, multiplier: float, sequence: int, maximum_added: int
    ) -> int:
        self.calls.append(("route_demand", route_id, multiplier, sequence, maximum_added))
        return 1

    def apply_route_policy(self, route_id: str) -> int:
        self.calls.append(("route_policy", route_id))
        return 3

    def close(self) -> None:
        self.closed = True


class FakeLauncher:
    def __init__(self, process: FakeManagedProcess) -> None:
        self.process = process
        self.argv: tuple[str, ...] | None = None
        self.working_directory: Path | None = None
        self.environment: Mapping[str, str] | None = None

    def __call__(
        self, argv: tuple[str, ...], working_directory: Path, environment: Mapping[str, str]
    ) -> FakeManagedProcess:
        self.argv = argv
        self.working_directory = working_directory
        self.environment = environment
        return self.process


class FakeConnector:
    def __init__(self, protocol: FakeProtocol, *, fail: bool = False) -> None:
        self.protocol = protocol
        self.fail = fail
        self.calls: list[tuple[int, Path, float]] = []

    def __call__(
        self,
        control_port: int,
        tools_root: Path,
        process: object,
        timeout_seconds: float,
    ) -> FakeProtocol:
        del process
        self.calls.append((control_port, tools_root, timeout_seconds))
        if self.fail:
            raise RuntimeError("synthetic connection failure")
        return self.protocol


def _runtime(tmp_path: Path) -> ResolvedLocalSumoRuntime:
    return ResolvedLocalSumoRuntime(
        status=SumoRuntimeStatus(
            available=True,
            executable_name="sumo",
            executable_sha256=local_sumo_network_digest(),
            version="1.27.1",
            supported=True,
            reason="synthetic bound runtime",
        ),
        executable=preset_scenario_root() / "square.net.xml",
        tools_root=tmp_path / "runtime" / "tools",
    )


def _dependencies(
    tmp_path: Path,
    process: FakeManagedProcess,
    protocol: FakeProtocol,
    *,
    connector_fail: bool = False,
) -> tuple[LocalSumoDependencies, FakeLauncher, FakeConnector]:
    launcher = FakeLauncher(process)
    connector = FakeConnector(protocol, fail=connector_fail)
    runtime = _runtime(tmp_path)
    return (
        LocalSumoDependencies(
            runtime_resolver=lambda: runtime,
            port_allocator=lambda: 51_473,
            launcher=launcher,
            connector=connector,
        ),
        launcher,
        connector,
    )


def _spec(
    *grants: CommandGrant,
    command_policy: LocalSumoCommandPolicy | None = None,
    runtime_digest: str = local_sumo_network_digest(),
    **overrides: object,
) -> LiveTwinSessionSpec:
    policy = command_policy or fixed_local_sumo_command_policy()
    payload: dict[str, object] = {
        "session_id": "local-sumo-session",
        "controller_id": "local-owner",
        "network_digest": local_sumo_network_digest(),
        "scenario_digest": local_sumo_scenario_digest(),
        "tool_versions": {
            "sumo": "1.27.1",
            "local_sumo_transport": "local-sumo-live-twin-1.0",
            "local_sumo_command_policy": policy.digest(),
            "sumo_executable_sha256": runtime_digest,
        },
        "seed": 42,
        "mode": "simulation_closed_loop" if grants else "observe_only",
        "execution_backend": "local_sumo",
        "access_surface": "local_library",
        "max_simulation_seconds": 120,
        "max_wall_clock_seconds": 120,
        "max_commands": len(grants) + 5 if grants else 0,
        "max_estimated_cost_gbp": 0.0,
        "unattended": False,
        "command_allowlist": grants,
    }
    payload.update(overrides)
    return LiveTwinSessionSpec.model_validate(payload)


def _command(
    spec: LiveTwinSessionSpec,
    *,
    sequence: int,
    kind: str,
    target: str,
    parameters: Mapping[str, str | int | float | bool] | None = None,
    expected_state: str = "running",
) -> TwinCommand:
    treatment = kind not in {"pause", "resume", "step"}
    return TwinCommand.model_validate(
        {
            "command_id": f"command-{sequence}",
            "idempotency_key": f"idem-{sequence}",
            "session_spec_digest": spec.digest(),
            "sequence": sequence,
            "kind": kind,
            "surface": "simulation",
            "target": target,
            "parameters": dict(parameters or {}),
            "expected_state": expected_state,
            "changes_scientific_treatment": treatment,
            "estimated_cost_gbp": 0.0,
        }
    )


def _policy_with_signal() -> LocalSumoCommandPolicy:
    base = fixed_local_sumo_command_policy()
    return base.model_copy(
        update={
            "signal_programs": (SignalProgramGrant(signal_id="TL0", program_ids=("P0",)),),
            "route_policies": (RoutePolicyGrant(policy_id="square_loop", route_id="square_loop"),),
        }
    )


def test_preparation_is_path_free_fixed_and_digest_bound(tmp_path: Path) -> None:
    process = FakeManagedProcess()
    protocol = FakeProtocol()
    dependencies, _, _ = _dependencies(tmp_path, process, protocol)
    spec = _spec(CommandGrant(kind="step", surface="simulation"))
    preparation = prepare_local_sumo_transport(
        spec,
        control_port=51_473,
        dependencies=dependencies,
    )
    assert isinstance(preparation, LocalSumoPreparation)
    assert preparation.session_spec_digest == spec.digest()
    assert preparation.network_digest == local_sumo_network_digest()
    assert preparation.preset_digest == local_sumo_scenario_digest()
    assert preparation.argv[0] == "sumo"
    assert preparation.argv == (
        "sumo",
        "-c",
        "square.sumocfg",
        "--remote-port",
        "51473",
        "--seed",
        "42",
        "--begin",
        "0",
        "--end",
        "120",
        "--no-step-log",
        "true",
        "--quit-on-end",
        "true",
    )
    assert preparation.shell is False
    assert preparation.evidence is False
    assert all(not Path(item).is_absolute() for item in preparation.argv)
    serialised = preparation.model_dump_json()
    assert str(tmp_path) not in serialised
    assert "/Users/" not in serialised


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"seed": 7}, "DIGEST_MISMATCH"),
        ({"scenario_digest": "f" * 64}, "DIGEST_MISMATCH"),
        ({"tool_versions": {"sumo": "1.26.0"}}, "DIGEST_MISMATCH"),
        ({"max_simulation_seconds": 121}, "BUDGET_EXCEEDED"),
        ({"max_wall_clock_seconds": 601}, "BUDGET_EXCEEDED"),
        ({"max_estimated_cost_gbp": 0.01}, "BUDGET_EXCEEDED"),
    ],
)
def test_preparation_refuses_changed_fixture_runtime_and_budgets(
    tmp_path: Path, overrides: Mapping[str, object], code: str
) -> None:
    dependencies, _, _ = _dependencies(tmp_path, FakeManagedProcess(), FakeProtocol())
    payload = _spec(CommandGrant(kind="step", surface="simulation")).model_dump(mode="python")
    payload.update(overrides)
    spec = LiveTwinSessionSpec.model_validate(payload)
    with pytest.raises(LocalSumoTransportError) as refused:
        prepare_local_sumo_transport(spec, control_port=51_473, dependencies=dependencies)
    assert refused.value.code == code


def test_preparation_refuses_capacity_and_unbound_signal_grants(tmp_path: Path) -> None:
    dependencies, _, _ = _dependencies(tmp_path, FakeManagedProcess(), FakeProtocol())
    capacity = _spec(
        CommandGrant(kind="set_rsu_compute_capacity", surface="simulation"),
    )
    with pytest.raises(LocalSumoTransportError) as refused:
        prepare_local_sumo_transport(capacity, control_port=51_473, dependencies=dependencies)
    assert refused.value.code == "COMMAND_NOT_ALLOWLISTED"

    signal = _spec(CommandGrant(kind="set_signal_program", surface="simulation"))
    with pytest.raises(LocalSumoTransportError) as unbound_signal:
        prepare_local_sumo_transport(signal, control_port=51_473, dependencies=dependencies)
    assert unbound_signal.value.code == "COMMAND_NOT_ALLOWLISTED"


def test_controller_lifecycle_all_command_families_idempotency_and_cleanup(tmp_path: Path) -> None:
    grants = tuple(
        CommandGrant(kind=kind, surface="simulation")
        for kind in (
            "step",
            "pause",
            "resume",
            "set_signal_program",
            "set_speed_limit",
            "close_lane",
            "open_lane",
            "inject_incident",
            "clear_incident",
            "set_route_demand",
            "set_vehicle_route_policy",
        )
    )
    policy = _policy_with_signal()
    spec = _spec(*grants, command_policy=policy, max_commands=11)
    process = FakeManagedProcess()
    protocol = FakeProtocol(
        inventory=LocalSumoInventory(
            edge_ids=("E0",),
            lane_ids=("E0_0",),
            route_ids=("square_loop",),
            signal_ids=("TL0",),
        )
    )
    dependencies, launcher, connector = _dependencies(tmp_path, process, protocol)
    controller = LiveTwinController(
        spec,
        local_sumo_process_factory(
            spec,
            command_policy=policy,
            dependencies=dependencies,
        ),
        wall_clock=Clock(),
    )
    controller.start()
    assert controller.read_snapshot().values["session_healthy"] == 1.0
    step = _command(spec, sequence=1, kind="step", target="simulation", parameters={"steps": 3})
    assert controller.apply_command(step).state_after == "running"
    assert controller.apply_command(step).idempotent_retry is True
    controller.apply_command(_command(spec, sequence=2, kind="pause", target="session"))
    controller.apply_command(
        _command(
            spec,
            sequence=3,
            kind="resume",
            target="session",
            expected_state="paused",
        )
    )
    controller.apply_command(
        _command(
            spec,
            sequence=4,
            kind="set_signal_program",
            target="TL0",
            parameters={"program_id": "P0"},
        )
    )
    controller.apply_command(
        _command(
            spec,
            sequence=5,
            kind="set_speed_limit",
            target="E0",
            parameters={"speed_mps": 8.0},
        )
    )
    controller.apply_command(_command(spec, sequence=6, kind="close_lane", target="E0_0"))
    controller.apply_command(_command(spec, sequence=7, kind="open_lane", target="E0_0"))
    controller.apply_command(
        _command(
            spec,
            sequence=8,
            kind="inject_incident",
            target="E0",
            parameters={"severity": 0.5},
        )
    )
    controller.apply_command(_command(spec, sequence=9, kind="clear_incident", target="E0"))
    controller.apply_command(
        _command(
            spec,
            sequence=10,
            kind="set_route_demand",
            target="square_loop",
            parameters={"demand_multiplier": 2.0},
        )
    )
    controller.apply_command(
        _command(
            spec,
            sequence=11,
            kind="set_vehicle_route_policy",
            target="square_loop",
            parameters={"route_policy_id": "square_loop"},
        )
    )
    receipt = controller.stop("bounded synthetic command-family test complete")
    assert receipt.final_state == "completed"
    assert receipt.commands_applied == 11
    assert receipt.experiment_use_invalidated is True
    assert receipt.evidence is False
    assert receipt.scientific_use is False
    assert receipt.production_ready is False
    assert receipt.any_external_effect_performed is False
    assert protocol.calls == [
        ("step", 3),
        ("signal", "TL0", "P0"),
        ("speed", "E0", 8.0),
        ("close_lane", "E0_0", ("passenger",)),
        ("open_lane", "E0_0"),
        ("inject_incident", "E0", 0.5),
        ("clear_incident", "E0"),
        ("route_demand", "square_loop", 2.0, 10, 4),
        ("route_policy", "square_loop"),
    ]
    assert connector.calls == [(51_473, _runtime(tmp_path).tools_root, 10.0)]
    assert launcher.argv is not None and launcher.argv[0] == str(_runtime(tmp_path).executable)
    assert launcher.environment is not None
    assert set(launcher.environment) == {"PATH", "HOME", "TMPDIR", "SUMO_HOME", "LC_ALL", "LANG"}
    assert launcher.working_directory is not None
    assert not launcher.working_directory.exists()
    assert protocol.closed
    assert process.terminate_calls == 1


def test_command_targets_parameters_sequence_and_capacity_conflation_refuse(tmp_path: Path) -> None:
    spec = _spec(
        CommandGrant(kind="set_speed_limit", surface="simulation"),
        max_commands=2,
    )
    process = FakeManagedProcess()
    protocol = FakeProtocol()
    dependencies, _, _ = _dependencies(tmp_path, process, protocol)
    controller = LiveTwinController(
        spec,
        local_sumo_process_factory(spec, dependencies=dependencies),
        wall_clock=Clock(),
    )
    controller.start()
    with pytest.raises(LocalSumoTransportError) as target:
        controller.apply_command(
            _command(
                spec,
                sequence=1,
                kind="set_speed_limit",
                target="outside-edge",
                parameters={"speed_mps": 8.0},
            )
        )
    assert target.value.code == "COMMAND_NOT_ALLOWLISTED"
    with pytest.raises(LocalSumoTransportError) as parameter:
        controller.apply_command(
            _command(
                spec,
                sequence=1,
                kind="set_speed_limit",
                target="E0",
                parameters={"speed_mps": 80.0},
            )
        )
    assert parameter.value.code == "COMMAND_PARAMETER_INVALID"
    controller.stop("refusal test complete")


def test_inventory_mismatch_and_connection_failure_cleanup_and_receipt(tmp_path: Path) -> None:
    spec = _spec(CommandGrant(kind="step", surface="simulation"))
    process = FakeManagedProcess()
    protocol = FakeProtocol(
        inventory=LocalSumoInventory(edge_ids=(), lane_ids=(), route_ids=(), signal_ids=())
    )
    dependencies, launcher, _ = _dependencies(tmp_path, process, protocol)
    controller = LiveTwinController(
        spec,
        local_sumo_process_factory(spec, dependencies=dependencies),
        wall_clock=Clock(),
    )
    with pytest.raises(LiveTwinError) as mismatch:
        controller.start()
    assert mismatch.value.code == "CONTROL_PROTOCOL_LOST"
    assert controller.receipt is not None
    assert controller.receipt.final_state == "refused"
    assert launcher.working_directory is not None
    assert not launcher.working_directory.exists()
    assert process.terminate_calls == 1
    assert protocol.closed

    second_process = FakeManagedProcess()
    failed_dependencies, failed_launcher, _ = _dependencies(
        tmp_path,
        second_process,
        FakeProtocol(),
        connector_fail=True,
    )
    failed = LiveTwinController(
        spec.model_copy(update={"session_id": "connection-failure"}),
        local_sumo_process_factory(
            spec.model_copy(update={"session_id": "connection-failure"}),
            dependencies=failed_dependencies,
        ),
        wall_clock=Clock(),
    )
    with pytest.raises(LiveTwinError):
        failed.start()
    assert failed.receipt is not None
    assert failed_launcher.working_directory is not None
    assert not failed_launcher.working_directory.exists()
    assert second_process.terminate_calls == 1


@pytest.mark.parametrize("failure", ["process", "heartbeat", "private", "output"])
def test_crash_protocol_privacy_and_output_bounds_fail_safe(tmp_path: Path, failure: str) -> None:
    output = "x" * 2_048 if failure == "output" else ""
    process = FakeManagedProcess(output=output)
    aggregates: Mapping[str, float] | None = (
        {"vehicle_id": 1.0, "simulation_time_s": 0.0} if failure == "private" else None
    )
    protocol = FakeProtocol(aggregates=aggregates, healthy=failure != "heartbeat")
    dependencies, _, _ = _dependencies(tmp_path, process, protocol)
    policy = fixed_local_sumo_command_policy().model_copy(update={"maximum_output_bytes": 1_024})
    spec = _spec(command_policy=policy, session_id=f"failure-{failure}")
    controller = LiveTwinController(
        spec,
        local_sumo_process_factory(
            spec,
            command_policy=policy,
            dependencies=dependencies,
        ),
        wall_clock=Clock(),
    )
    controller.start()
    if failure == "process":
        process.crash()
    if failure == "output":
        deadline = time.monotonic() + 1.0
        while not controller.receipt and time.monotonic() < deadline:
            try:
                controller.read_snapshot()
            except LiveTwinError:
                break
    else:
        with pytest.raises(LiveTwinError):
            controller.read_snapshot()
    assert controller.receipt is not None
    assert controller.receipt.final_state == "refused"
    assert controller.receipt.evidence is False
    assert protocol.closed


def test_single_owner_budget_and_process_escalation_are_preserved(tmp_path: Path) -> None:
    spec = _spec(CommandGrant(kind="step", surface="simulation"), max_commands=1)
    first_process = FakeManagedProcess(stubborn=True)
    dependencies, _, _ = _dependencies(tmp_path, first_process, FakeProtocol())
    clock = Clock()
    first = LiveTwinController(
        spec,
        local_sumo_process_factory(spec, dependencies=dependencies),
        wall_clock=clock,
    )
    second = LiveTwinController(
        spec,
        local_sumo_process_factory(spec, dependencies=dependencies),
        wall_clock=clock,
    )
    first.start()
    with pytest.raises(LiveTwinError) as owned:
        second.start()
    assert owned.value.code == "SESSION_ALREADY_OWNED"
    first.stop("single-owner test complete")
    assert first_process.terminate_calls == 1
    assert first_process.kill_calls == 1

    budget_process = FakeManagedProcess()
    budget_dependencies, _, _ = _dependencies(tmp_path, budget_process, FakeProtocol())
    budget_spec = _spec(session_id="wall-budget", max_wall_clock_seconds=1)
    budget = LiveTwinController(
        budget_spec,
        local_sumo_process_factory(budget_spec, dependencies=budget_dependencies),
        wall_clock=clock,
    )
    budget.start()
    clock.now += 2
    with pytest.raises(LiveTwinError) as exceeded:
        budget.read_snapshot()
    assert exceeded.value.code == "BUDGET_EXCEEDED"
    assert budget.receipt is not None


def test_real_pinned_local_sumo_smoke_when_runtime_is_available() -> None:
    readiness = local_sumo_readiness()
    if (
        not readiness.ready
        or readiness.runtime.version is None
        or readiness.runtime.executable_sha256 is None
    ):
        pytest.skip(readiness.reason)
    spec = _spec(
        CommandGrant(kind="step", surface="simulation"),
        session_id="phase176-real-local-sumo-smoke",
        max_simulation_seconds=30,
        max_wall_clock_seconds=30,
        max_commands=1,
        runtime_digest=readiness.runtime.executable_sha256,
        tool_versions={
            "sumo": readiness.runtime.version,
            "local_sumo_transport": "local-sumo-live-twin-1.0",
            "local_sumo_command_policy": fixed_local_sumo_command_policy().digest(),
            "sumo_executable_sha256": readiness.runtime.executable_sha256,
        },
    )
    controller = LiveTwinController(
        spec,
        local_sumo_process_factory(spec),
        wall_clock=time.monotonic,
    )
    controller.start()
    before = controller.read_snapshot()
    controller.apply_command(
        _command(spec, sequence=1, kind="step", target="simulation", parameters={"steps": 5})
    )
    after = controller.read_snapshot()
    receipt = controller.stop("bounded synthetic local smoke complete")
    assert before.values["simulation_time_s"] == 0.0
    assert after.values["simulation_time_s"] == 5.0
    assert set(after.values) == {
        "simulation_time_s",
        "vehicle_count",
        "mean_speed_mps",
        "queue_indicator",
        "incident_count",
        "session_healthy",
    }
    assert receipt.final_state == "completed"
    assert receipt.commands_applied == 1
    assert receipt.snapshots_emitted == 2
    assert receipt.any_external_effect_performed is False
    assert receipt.evidence is False
    assert receipt.scientific_use is False
    assert receipt.production_ready is False


def test_transport_source_has_no_broadened_external_surface() -> None:
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "local_sumo_transport.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "shell=True",
        "requests.",
        "httpx.",
        "boto3",
        "google.cloud",
        "sumo-gui",
        "TRAFFICTWIN_BODS",
        'set_rsu_compute_capacity":',
    ):
        assert forbidden not in source
