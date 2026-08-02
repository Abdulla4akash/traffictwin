"""Maximum-coverage live-twin contracts, exercised only with deterministic fakes."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.platform.live_twin import (
    AggregateMobilityUpdate,
    AuthenticatedControlAdapter,
    AuthenticatedControlRequest,
    BodsBridgePolicy,
    CloudExecutionPolicy,
    CommandGrant,
    EventSubscription,
    LiveTwinController,
    LiveTwinError,
    LiveTwinSessionSpec,
    PluginContract,
    ProcessCommandResult,
    PublicApiPolicy,
    TwinCommand,
    TwinEvent,
    mark_scientific_use,
    sumo_argument_vector,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeProcess:
    def __init__(
        self,
        *,
        heartbeat_failures_after: int | None = None,
        aggregates: dict[str, float] | None = None,
        external_effect: bool = False,
    ) -> None:
        self.terminated = False
        self.reads = 0
        self.commands: list[TwinCommand] = []
        self.mobility_updates: list[AggregateMobilityUpdate] = []
        self._heartbeat_failures_after = heartbeat_failures_after
        self._aggregates = aggregates or {
            "simulation_time_s": 12.0,
            "vehicle_count": 41.0,
            "mean_speed_mps": 6.3,
            "road_capacity_index": 0.8,
            "rsu_compute_utilisation": 0.4,
        }
        self._external_effect = external_effect

    def alive(self) -> bool:
        return not self.terminated

    def heartbeat(self) -> bool:
        if self._heartbeat_failures_after is None:
            return True
        return self.reads < self._heartbeat_failures_after

    def read_aggregates(self) -> dict[str, float]:
        self.reads += 1
        return self._aggregates

    def apply_command(self, command: TwinCommand) -> ProcessCommandResult:
        self.commands.append(command)
        return ProcessCommandResult(
            values={"accepted_sequence": command.sequence},
            external_effect_performed=self._external_effect,
        )

    def apply_aggregate_mobility(self, update: AggregateMobilityUpdate) -> ProcessCommandResult:
        self.mobility_updates.append(update)
        return ProcessCommandResult(
            values={"accepted_mobility_sequence": update.sequence},
            external_effect_performed=self._external_effect,
        )

    def terminate(self) -> None:
        self.terminated = True


class FailingProcess(FakeProcess):
    def __init__(self, operation: str, *, termination_fails: bool = False) -> None:
        super().__init__()
        self._operation = operation
        self._termination_fails = termination_fails

    def heartbeat(self) -> bool:
        if self._operation == "health":
            raise RuntimeError("synthetic heartbeat protocol loss")
        return super().heartbeat()

    def read_aggregates(self) -> dict[str, float]:
        if self._operation == "snapshot":
            raise RuntimeError("synthetic snapshot protocol loss")
        return super().read_aggregates()

    def apply_command(self, command: TwinCommand) -> ProcessCommandResult:
        if self._operation == "command":
            raise RuntimeError("synthetic command protocol loss")
        return super().apply_command(command)

    def apply_aggregate_mobility(self, update: AggregateMobilityUpdate) -> ProcessCommandResult:
        if self._operation == "mobility":
            raise RuntimeError("synthetic mobility protocol loss")
        return super().apply_aggregate_mobility(update)

    def terminate(self) -> None:
        if self._termination_fails:
            raise RuntimeError("synthetic shutdown failure")
        super().terminate()


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FakeAuthorizer:
    def __init__(self, accepted: bool = True) -> None:
        self.accepted = accepted

    def authorize(self, request: AuthenticatedControlRequest, policy: PublicApiPolicy) -> bool:
        del request, policy
        return self.accepted


class FakeEventSink:
    def __init__(self, accepted: bool = True) -> None:
        self.accepted = accepted
        self.events: list[TwinEvent] = []

    def publish(self, event: TwinEvent) -> bool:
        self.events.append(event)
        return self.accepted


def _spec(**overrides: object) -> LiveTwinSessionSpec:
    payload: dict[str, object] = {
        "session_id": "session-1",
        "controller_id": "controller-1",
        "network_digest": "a" * 64,
        "scenario_digest": "b" * 64,
        "tool_versions": {"sumo": "1.27.1"},
        "seed": 7,
        "mode": "observe_only",
        "execution_backend": "local_fake",
        "access_surface": "local_library",
        "max_simulation_seconds": 600,
        "max_wall_clock_seconds": 900,
        "max_commands": 0,
        "max_estimated_cost_gbp": 0.0,
        "unattended": True,
        "command_allowlist": (),
    }
    payload.update(overrides)
    return LiveTwinSessionSpec.model_validate(payload)


def _closed_spec(*grants: CommandGrant, **overrides: object) -> LiveTwinSessionSpec:
    payload: dict[str, object] = {
        "mode": "simulation_closed_loop",
        "max_commands": 20,
        "command_allowlist": grants,
    }
    payload.update(overrides)
    return _spec(**payload)


def _command(
    spec: LiveTwinSessionSpec,
    *,
    command_id: str = "command-1",
    idempotency_key: str = "idem-1",
    sequence: int = 1,
    kind: str = "step",
    surface: str = "simulation",
    expected_state: str = "running",
    capacity_domain: str | None = None,
    changes_scientific_treatment: bool = False,
    authority_digest: str | None = None,
    plugin_id: str | None = None,
    estimated_cost_gbp: float = 0.0,
) -> TwinCommand:
    return TwinCommand.model_validate(
        {
            "command_id": command_id,
            "idempotency_key": idempotency_key,
            "session_spec_digest": spec.digest(),
            "sequence": sequence,
            "kind": kind,
            "surface": surface,
            "target": "corridor-segment-a",
            "parameters": {"value": 1.0},
            "capacity_domain": capacity_domain,
            "expected_state": expected_state,
            "authority_digest": authority_digest,
            "changes_scientific_treatment": changes_scientific_treatment,
            "estimated_cost_gbp": estimated_cost_gbp,
            "plugin_id": plugin_id,
        }
    )


def _controller(
    spec: LiveTwinSessionSpec,
    process: FakeProcess,
    clock: Clock,
    *,
    event_sink: FakeEventSink | None = None,
) -> LiveTwinController:
    return LiveTwinController(spec, lambda: process, wall_clock=clock, event_sink=event_sink)


def test_specs_cover_unattended_simulation_public_cloud_and_operator_modes() -> None:
    assert _spec().unattended is True
    with pytest.raises(ValidationError, match="observe-only"):
        _spec(command_allowlist=(CommandGrant(kind="step", surface="simulation"),))

    public = PublicApiPolicy(
        auth_policy_digest="d" * 64,
        allowed_roles=("operator", "orchestrator"),
        maximum_request_age_seconds=30,
    )
    closed = _closed_spec(
        CommandGrant(kind="step", surface="simulation"),
        access_surface="authenticated_public_api",
        public_api=public,
    )
    assert closed.mode == "simulation_closed_loop"
    assert closed.per_command_human_approval_required is False

    cloud = _closed_spec(
        CommandGrant(kind="start_sweep", surface="platform"),
        execution_backend="gcp_batch",
        access_surface="cloud_scheduler",
        max_estimated_cost_gbp=100.0,
        cloud=CloudExecutionPolicy(
            provider="gcp",
            account_scope_digest="e" * 64,
            region_allowlist=("europe-west2",),
            maximum_instances=8,
            maximum_estimated_cost_gbp=100.0,
        ),
    )
    assert cloud.execution_backend == "gcp_batch"

    with pytest.raises(ValidationError, match="bound authority"):
        _spec(
            mode="operator_site_closed_loop",
            execution_backend="operator_site",
            max_commands=5,
        )
    operator = _spec(
        mode="operator_site_closed_loop",
        execution_backend="operator_site",
        max_commands=5,
        command_allowlist=(CommandGrant(kind="set_signal_program", surface="real_infrastructure"),),
        authority_digest="f" * 64,
        operator_policy_digest="1" * 64,
    )
    assert operator.mode == "operator_site_closed_loop"


def test_observe_only_snapshot_and_terminal_receipt_have_no_external_effect() -> None:
    process = FakeProcess()
    controller = _controller(_spec(), process, Clock())
    controller.start()
    snapshot = controller.read_snapshot()
    assert snapshot.snapshot_index == 1
    assert snapshot.evidence is False
    receipt = controller.stop("scheduled completion")
    assert receipt.final_state == "completed"
    assert receipt.commands_applied == 0
    assert receipt.any_external_effect_performed is False
    assert receipt.evidence is False
    assert receipt.scientific_use is False
    assert receipt.production_ready is False
    assert receipt.execution_authority_created is False
    assert process.terminated

    private_reason = _controller(
        _spec(session_id="safe-stop-reason"),
        FakeProcess(),
        Clock(),
    )
    private_reason.start()
    safe_receipt = private_reason.stop("read /Users/example/private-log")
    assert "/Users/" not in safe_receipt.stop_reason
    assert any("withheld" in deviation for deviation in safe_receipt.deviations)


def test_single_owner_heartbeat_and_budgets_fail_safe_with_receipts() -> None:
    spec = _spec()
    first = _controller(spec, FakeProcess(), Clock())
    second = _controller(spec, FakeProcess(), Clock())
    first.start()
    with pytest.raises(LiveTwinError) as owned:
        second.start()
    assert owned.value.code == "SESSION_ALREADY_OWNED"
    first.stop("lock test complete")

    process = FakeProcess(heartbeat_failures_after=1)
    heartbeat = _controller(_spec(session_id="heartbeat"), process, Clock())
    heartbeat.start()
    heartbeat.read_snapshot()
    with pytest.raises(LiveTwinError) as lost:
        heartbeat.read_snapshot()
    assert lost.value.code == "CONTROL_PROTOCOL_LOST"
    assert heartbeat.receipt is not None

    clock = Clock()
    budget = _controller(
        _spec(session_id="budget", max_wall_clock_seconds=10),
        FakeProcess(),
        clock,
    )
    budget.start()
    clock.now = 111.0
    with pytest.raises(LiveTwinError) as exceeded:
        budget.read_snapshot()
    assert exceeded.value.code == "BUDGET_EXCEEDED"
    assert budget.receipt is not None


def test_snapshots_and_commands_screen_private_content_and_keep_capacities_distinct() -> None:
    controller = _controller(
        _spec(session_id="private"),
        FakeProcess(aggregates={"vehicle_count": 3.0, "vehicle_id_1042": 1.0}),
        Clock(),
    )
    controller.start()
    with pytest.raises(LiveTwinError) as private:
        controller.read_snapshot()
    assert private.value.code == "PRIVATE_CONTENT_DETECTED"

    spec = _closed_spec(
        CommandGrant(kind="set_road_capacity", surface="simulation"),
        CommandGrant(kind="set_rsu_compute_capacity", surface="simulation"),
    )
    with pytest.raises(ValidationError, match="road_traffic"):
        _command(
            spec,
            kind="set_road_capacity",
            capacity_domain="rsu_compute",
            changes_scientific_treatment=True,
        )
    with pytest.raises(ValidationError, match="RSU commands"):
        _command(
            spec,
            kind="set_rsu_compute_capacity",
            capacity_domain="road_traffic",
            changes_scientific_treatment=True,
        )


def test_closed_loop_commands_are_sequenced_idempotent_and_deviation_receipted() -> None:
    spec = _closed_spec(
        CommandGrant(kind="pause", surface="simulation"),
        CommandGrant(kind="resume", surface="simulation"),
        CommandGrant(kind="set_road_capacity", surface="simulation"),
    )
    process = FakeProcess()
    controller = _controller(spec, process, Clock())
    controller.start()

    pause = _command(spec, kind="pause")
    first = controller.apply_command(pause)
    retry = controller.apply_command(pause)
    assert first.state_after == "paused"
    assert retry.idempotent_retry is True
    assert len(process.commands) == 1

    resume = _command(
        spec,
        command_id="command-2",
        idempotency_key="idem-2",
        sequence=2,
        kind="resume",
        expected_state="paused",
    )
    assert controller.apply_command(resume).state_after == "running"
    road = _command(
        spec,
        command_id="command-3",
        idempotency_key="idem-3",
        sequence=3,
        kind="set_road_capacity",
        capacity_domain="road_traffic",
        changes_scientific_treatment=True,
    )
    controller.apply_command(road)
    receipt = controller.stop("closed-loop test complete")
    assert receipt.commands_applied == 3
    assert receipt.experiment_use_invalidated is True
    assert "set_road_capacity" in " ".join(receipt.deviations)
    assert receipt.any_external_effect_performed is False


def test_allowlist_sequence_budget_plugin_and_operator_authority_refusals() -> None:
    plugin = PluginContract(
        plugin_id="controller-plugin",
        plugin_digest="2" * 64,
        kind="controller",
        command_grants=(CommandGrant(kind="invoke_plugin", surface="platform"),),
    )
    spec = _closed_spec(
        CommandGrant(kind="step", surface="simulation"),
        CommandGrant(kind="invoke_plugin", surface="platform"),
        plugins=(plugin,),
        max_commands=2,
    )
    controller = _controller(spec, FakeProcess(), Clock())
    controller.start()
    with pytest.raises(LiveTwinError) as sequence:
        controller.apply_command(_command(spec, sequence=2))
    assert sequence.value.code == "STATE_SEQUENCE_MISMATCH"
    with pytest.raises(LiveTwinError) as allowlist:
        controller.apply_command(
            _command(
                spec,
                kind="set_speed_limit",
                changes_scientific_treatment=True,
            )
        )
    assert allowlist.value.code == "COMMAND_NOT_ALLOWLISTED"
    controller.apply_command(_command(spec))
    plugin_command = _command(
        spec,
        command_id="plugin-command",
        idempotency_key="plugin-idem",
        sequence=2,
        kind="invoke_plugin",
        surface="platform",
        changes_scientific_treatment=True,
        plugin_id="controller-plugin",
    )
    controller.apply_command(plugin_command)
    with pytest.raises(LiveTwinError) as budget:
        controller.apply_command(
            _command(
                spec,
                command_id="third",
                idempotency_key="third-idem",
                sequence=3,
            )
        )
    assert budget.value.code == "BUDGET_EXCEEDED"
    assert controller.receipt is not None

    authority = "3" * 64
    operator = _spec(
        session_id="operator",
        mode="operator_site_closed_loop",
        execution_backend="operator_site",
        max_commands=1,
        command_allowlist=(CommandGrant(kind="set_signal_program", surface="real_infrastructure"),),
        authority_digest=authority,
        operator_policy_digest="4" * 64,
    )
    operator_controller = _controller(operator, FakeProcess(external_effect=True), Clock())
    operator_controller.start()
    with pytest.raises(LiveTwinError) as missing:
        operator_controller.apply_command(
            _command(
                operator,
                kind="set_signal_program",
                surface="real_infrastructure",
                changes_scientific_treatment=True,
            )
        )
    assert missing.value.code == "AUTHORITY_MISSING"
    applied = operator_controller.apply_command(
        _command(
            operator,
            kind="set_signal_program",
            surface="real_infrastructure",
            changes_scientific_treatment=True,
            authority_digest=authority,
        )
    )
    assert applied.external_effect_performed is True
    operator_receipt = operator_controller.stop("operator fake test complete")
    assert operator_receipt.any_external_effect_performed is True

    cost_spec = _closed_spec(
        CommandGrant(kind="step", surface="simulation"),
        session_id="cost-budget",
        max_estimated_cost_gbp=1.0,
    )
    cost_controller = _controller(cost_spec, FakeProcess(), Clock())
    cost_controller.start()
    with pytest.raises(LiveTwinError) as cost:
        cost_controller.apply_command(_command(cost_spec, estimated_cost_gbp=1.01))
    assert cost.value.code == "BUDGET_EXCEEDED"
    assert cost_controller.receipt is not None


def test_authenticated_public_adapter_enforces_role_age_and_verification() -> None:
    api = PublicApiPolicy(
        auth_policy_digest="5" * 64,
        allowed_roles=("operator",),
        maximum_request_age_seconds=30,
    )
    spec = _closed_spec(
        CommandGrant(kind="step", surface="simulation"),
        access_surface="authenticated_public_api",
        public_api=api,
    )
    clock = Clock()
    controller = _controller(spec, FakeProcess(), clock)
    controller.start()
    adapter = AuthenticatedControlAdapter(spec, controller, FakeAuthorizer(), wall_clock=clock)
    request = AuthenticatedControlRequest(
        request_id="request-1",
        actor_role="operator",
        auth_context_digest="6" * 64,
        request_time_seconds=100.0,
        command=_command(spec),
    )
    assert adapter.submit(request).sequence == 1

    wrong_role = request.model_copy(update={"actor_role": "viewer"})
    with pytest.raises(LiveTwinError) as role:
        adapter.submit(wrong_role)
    assert role.value.code == "AUTHENTICATION_FAILED"
    expired = request.model_copy(update={"request_time_seconds": 0.0})
    with pytest.raises(LiveTwinError) as age:
        adapter.submit(expired)
    assert age.value.code == "REQUEST_EXPIRED"
    denied = AuthenticatedControlAdapter(
        spec,
        controller,
        FakeAuthorizer(accepted=False),
        wall_clock=clock,
    )
    with pytest.raises(LiveTwinError) as auth:
        denied.submit(request)
    assert auth.value.code == "AUTHENTICATION_FAILED"
    controller.stop("public API contract test complete")


def test_unattended_bods_bridge_is_aggregate_only_upstream_compliant_and_staleness_bound() -> None:
    bridge = BodsBridgePolicy(
        upstream_terms_digest="7" * 64,
        licence_class="synthetic-test",
        aggregate_schema_digest="8" * 64,
        unattended=True,
        max_staleness_seconds=60,
    )
    spec = _spec(session_id="bods", bods_bridge=bridge)
    process = FakeProcess()
    controller = _controller(spec, process, Clock())
    controller.start()
    update = AggregateMobilityUpdate(
        update_id="aggregate-1",
        sequence=1,
        schema_digest="8" * 64,
        source_receipt_digest="9" * 64,
        observed_staleness_seconds=15,
        upstream_retry_after_observed=True,
        aggregates={"vehicle_count": 42.0, "mean_speed_mps": 5.1},
    )
    receipt = controller.apply_aggregate_mobility(update)
    assert receipt.raw_bytes_retained is False
    assert receipt.identifiers_retained is False
    assert process.mobility_updates == [update]
    retry = controller.apply_aggregate_mobility(update)
    assert retry.idempotent_retry is True
    assert process.mobility_updates == [update]
    with pytest.raises(LiveTwinError) as stale:
        controller.apply_aggregate_mobility(
            update.model_copy(
                update={
                    "update_id": "aggregate-2",
                    "sequence": 2,
                    "observed_staleness_seconds": 61,
                }
            )
        )
    assert stale.value.code == "LIVE_INPUT_STALE"
    with pytest.raises(ValidationError, match="non-aggregate"):
        AggregateMobilityUpdate(
            update_id="unsafe",
            sequence=2,
            schema_digest="8" * 64,
            source_receipt_digest="9" * 64,
            observed_staleness_seconds=1,
            upstream_retry_after_observed=False,
            aggregates={"vehicle_id": 1.0},
        )
    controller.stop("BODS bridge contract test complete")


def test_stream_events_are_digest_only_and_delivery_failure_is_receipted() -> None:
    sink = FakeEventSink(accepted=False)
    spec = _spec(
        session_id="stream",
        subscriptions=(
            EventSubscription(
                subscription_id="webhook-1",
                event_types=("session", "snapshot", "terminal"),
                delivery="authenticated_webhook",
                destination_binding_digest="0" * 64,
            ),
        ),
    )
    controller = _controller(spec, FakeProcess(), Clock(), event_sink=sink)
    controller.start()
    controller.read_snapshot()
    receipt = controller.stop("stream test complete")
    assert {event.event_type for event in sink.events} == {"session", "snapshot", "terminal"}
    assert all(len(event.payload_digest) == 64 for event in sink.events)
    assert all(event.external_delivery_attempted for event in sink.events)
    assert any("event delivery failed" in deviation for deviation in receipt.deviations)


def test_inflight_protocol_and_shutdown_failures_are_terminally_receipted() -> None:
    health_spec = _spec(session_id="health-protocol-failure")
    health = _controller(health_spec, FailingProcess("health"), Clock())
    health.start()
    with pytest.raises(LiveTwinError) as health_failure:
        health.read_snapshot()
    assert health_failure.value.code == "CONTROL_PROTOCOL_LOST"
    assert health.receipt is not None
    assert health.receipt.final_state == "refused"

    snapshot_spec = _spec(session_id="snapshot-protocol-failure")
    snapshot = _controller(snapshot_spec, FailingProcess("snapshot"), Clock())
    snapshot.start()
    with pytest.raises(LiveTwinError) as snapshot_failure:
        snapshot.read_snapshot()
    assert snapshot_failure.value.code == "CONTROL_PROTOCOL_LOST"
    assert snapshot.receipt is not None
    assert snapshot.receipt.final_state == "refused"
    assert "aggregate snapshot" in " ".join(snapshot.receipt.deviations)

    command_spec = _closed_spec(
        CommandGrant(kind="step", surface="simulation"),
        session_id="command-protocol-failure",
    )
    command = _controller(command_spec, FailingProcess("command"), Clock())
    command.start()
    with pytest.raises(LiveTwinError) as command_failure:
        command.apply_command(_command(command_spec))
    assert command_failure.value.code == "CONTROL_PROTOCOL_LOST"
    assert command.receipt is not None
    assert command.receipt.commands_applied == 0
    assert command.receipt.final_state == "refused"

    bridge = BodsBridgePolicy(
        upstream_terms_digest="7" * 64,
        licence_class="synthetic-test",
        aggregate_schema_digest="8" * 64,
        unattended=True,
        max_staleness_seconds=60,
    )
    mobility_spec = _spec(session_id="mobility-protocol-failure", bods_bridge=bridge)
    mobility = _controller(mobility_spec, FailingProcess("mobility"), Clock())
    mobility.start()
    update = AggregateMobilityUpdate(
        update_id="aggregate-protocol-failure",
        sequence=1,
        schema_digest="8" * 64,
        source_receipt_digest="9" * 64,
        observed_staleness_seconds=1,
        upstream_retry_after_observed=False,
        aggregates={"vehicle_count": 2.0},
    )
    with pytest.raises(LiveTwinError) as mobility_failure:
        mobility.apply_aggregate_mobility(update)
    assert mobility_failure.value.code == "CONTROL_PROTOCOL_LOST"
    assert mobility.receipt is not None
    assert mobility.receipt.mobility_updates_applied == 0

    shutdown_spec = _spec(session_id="shutdown-protocol-failure")
    shutdown = _controller(
        shutdown_spec,
        FailingProcess("none", termination_fails=True),
        Clock(),
    )
    shutdown.start()
    shutdown_receipt = shutdown.stop("normal shutdown requested")
    assert shutdown_receipt.final_state == "refused"
    assert shutdown_receipt.stop_reason == "CONTROL_PROTOCOL_LOST: shutdown failed"
    assert "termination failed" in " ".join(shutdown_receipt.deviations)


def test_scientific_use_is_not_created_and_sumo_argv_is_bounded() -> None:
    controller = _controller(_spec(session_id="science"), FakeProcess(), Clock())
    controller.start()
    receipt = controller.stop("done")
    with pytest.raises(LiveTwinError) as scientific:
        mark_scientific_use(receipt)
    assert scientific.value.code == "SCIENTIFIC_USE_UNAUTHORISED"

    sumo_spec = _spec(
        session_id="sumo",
        execution_backend="local_sumo",
        unattended=False,
    )
    argv = sumo_argument_vector(sumo_spec, "corridor.net.xml", 51473)
    assert argv[0] == "sumo"
    assert "--remote-port" in argv
    with pytest.raises(LiveTwinError):
        sumo_argument_vector(sumo_spec, "../outside.net.xml", 51473)

    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "live_twin.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("subprocess", "Popen", "requests.", "boto3", "google.cloud"):
        assert forbidden not in source
