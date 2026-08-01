"""Controlled live-twin adapter (post-v1 L-1, design §8 verification list).

A deterministic fake control process throughout — no SUMO, no network, no
acquisition. Tested: spec binding with required budgets and attended-only
rule, approval-gated mutation scope, single-owner locking, state
transitions with a receipt on every terminal path, allowlist and stale
command refusal, heartbeat loss, budget stop, aggregate-only snapshot
screening, the capacity-conflation refusal, and the scientific-use wall.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.platform.live_twin import (
    LiveTwinController,
    LiveTwinError,
    LiveTwinSessionSpec,
    TwinCommand,
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
    ) -> None:
        self.terminated = False
        self.reads = 0
        self._heartbeat_failures_after = heartbeat_failures_after
        self._aggregates = aggregates or {
            "simulation_time_s": 12.0,
            "vehicle_count": 41.0,
            "mean_speed_mps": 6.3,
        }

    def alive(self) -> bool:
        return not self.terminated

    def heartbeat(self) -> bool:
        if self._heartbeat_failures_after is None:
            return True
        return self.reads < self._heartbeat_failures_after

    def read_aggregates(self) -> dict[str, float]:
        self.reads += 1
        return self._aggregates

    def terminate(self) -> None:
        self.terminated = True


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _spec(**overrides: object) -> LiveTwinSessionSpec:
    payload: dict[str, object] = {
        "network_digest": "a" * 64,
        "scenario_digest": "b" * 64,
        "tool_versions": {"sumo": "1.27.1"},
        "seed": 7,
        "mode": "observe_only",
        "max_simulation_seconds": 600,
        "max_wall_clock_seconds": 900,
        "owner_attended": True,
    }
    payload.update(overrides)
    return LiveTwinSessionSpec.model_validate(payload)


def _controller(
    spec: LiveTwinSessionSpec, process: FakeProcess, clock: Clock
) -> LiveTwinController:
    return LiveTwinController(spec, lambda: process, wall_clock=clock)


def test_spec_binds_budgets_attendance_and_approval() -> None:
    with pytest.raises(ValidationError, match="OWNER_PRESENCE_REQUIRED"):
        _spec(owner_attended=False)
    with pytest.raises(ValidationError):
        _spec(max_wall_clock_seconds=0)
    with pytest.raises(ValidationError, match="no command allowlist"):
        _spec(command_allowlist=("pause",))
    with pytest.raises(ValidationError, match="APPROVAL_MISSING"):
        _spec(mode="controlled_intervention", command_allowlist=("pause", "resume"))
    with pytest.raises(ValidationError, match="never approval"):
        _spec(
            mode="controlled_intervention",
            command_allowlist=("pause",),
            mutation_approval={
                "approved_by": "agent",
                "approved_at_utc": "2026-08-01T22:00:00+00:00",
                "scope_note": "x",
            },
        )


def test_capacity_conflation_refuses_by_name() -> None:
    with pytest.raises(ValidationError, match="different"):
        _spec(
            mode="controlled_intervention",
            command_allowlist=("set_rsu_capacity",),
            mutation_approval={
                "approved_by": "Abdulla (owner)",
                "approved_at_utc": "2026-08-01T22:00:00+00:00",
                "scope_note": "probe",
            },
        )


def test_observe_only_happy_path_emits_receipt() -> None:
    process = FakeProcess()
    controller = _controller(_spec(), process, Clock())
    controller.start()
    snapshot = controller.read_snapshot()
    assert snapshot.snapshot_index == 1
    assert snapshot.evidence is False
    receipt = controller.stop("owner closed the session")
    assert receipt.final_state == "completed"
    assert receipt.snapshots_emitted == 1
    assert receipt.commands_applied == 0
    assert receipt.evidence is False
    assert receipt.scientific_use is False
    assert receipt.engineering_label == "engineering demonstration only"
    assert process.terminated


def test_single_owner_locking() -> None:
    controller = _controller(_spec(), FakeProcess(), Clock())
    controller.start()
    with pytest.raises(LiveTwinError) as excinfo:
        controller.start()
    assert excinfo.value.code == "SESSION_ALREADY_OWNED"


def test_observe_only_accepts_no_command_at_all() -> None:
    controller = _controller(_spec(), FakeProcess(), Clock())
    controller.start()
    with pytest.raises(LiveTwinError) as excinfo:
        controller.apply_command(
            TwinCommand(name="pause", scenario_digest="b" * 64, expected_sequence=1)
        )
    assert excinfo.value.code == "COMMAND_NOT_ALLOWLISTED"


def _intervention_spec() -> LiveTwinSessionSpec:
    return _spec(
        mode="controlled_intervention",
        command_allowlist=("pause", "resume", "select_demand_scenario"),
        mutation_approval={
            "approved_by": "Abdulla (repository owner)",
            "approved_at_utc": "2026-08-01T22:00:00+00:00",
            "scope_note": "pause/resume and predeclared scenario selection only",
        },
    )


def test_intervention_commands_enforce_allowlist_digest_and_sequence() -> None:
    controller = _controller(_intervention_spec(), FakeProcess(), Clock())
    controller.start()
    with pytest.raises(LiveTwinError) as unlisted:
        controller.apply_command(
            TwinCommand(name="teleport", scenario_digest="b" * 64, expected_sequence=1)
        )
    assert unlisted.value.code == "COMMAND_NOT_ALLOWLISTED"
    with pytest.raises(LiveTwinError) as drifted:
        controller.apply_command(
            TwinCommand(name="pause", scenario_digest="0" * 64, expected_sequence=1)
        )
    assert drifted.value.code == "DIGEST_MISMATCH"
    first = controller.apply_command(
        TwinCommand(name="pause", scenario_digest="b" * 64, expected_sequence=1)
    )
    assert first.sequence == 1
    with pytest.raises(LiveTwinError) as stale:
        controller.apply_command(
            TwinCommand(name="resume", scenario_digest="b" * 64, expected_sequence=1)
        )
    assert stale.value.code == "STATE_SEQUENCE_MISMATCH"


def test_treatment_changes_record_deviations_and_invalidate_experiment_use() -> None:
    controller = _controller(_intervention_spec(), FakeProcess(), Clock())
    controller.start()
    receipt = controller.apply_command(
        TwinCommand(
            name="select_demand_scenario",
            scenario_digest="b" * 64,
            expected_sequence=1,
            changes_treatment=True,
        )
    )
    assert receipt.deviation_recorded
    final = controller.stop("done")
    assert final.experiment_use_invalidated
    assert any("invalidated" in deviation for deviation in final.deviations)


def test_heartbeat_loss_fails_safe_with_a_receipt() -> None:
    process = FakeProcess(heartbeat_failures_after=1)
    controller = _controller(_spec(), process, Clock())
    controller.start()
    controller.read_snapshot()
    with pytest.raises(LiveTwinError) as excinfo:
        controller.read_snapshot()
    assert excinfo.value.code == "CONTROL_PROTOCOL_LOST"
    assert controller.state == "refused"
    assert controller.receipt is not None
    assert controller.receipt.final_state == "refused"
    assert process.terminated


def test_budget_breach_fails_safe_with_a_receipt() -> None:
    clock = Clock()
    controller = _controller(_spec(max_wall_clock_seconds=10), FakeProcess(), clock)
    controller.start()
    clock.now = 11.0
    with pytest.raises(LiveTwinError) as excinfo:
        controller.read_snapshot()
    assert excinfo.value.code == "BUDGET_EXCEEDED"
    assert controller.receipt is not None
    assert controller.receipt.final_state == "refused"


def test_snapshots_are_aggregate_only() -> None:
    process = FakeProcess(aggregates={"vehicle_count": 3.0, "vehicle_id_1042": 1.0})
    controller = _controller(_spec(), process, Clock())
    controller.start()
    with pytest.raises(LiveTwinError) as excinfo:
        controller.read_snapshot()
    assert excinfo.value.code == "PRIVATE_CONTENT_DETECTED"
    assert controller.receipt is not None


def test_scientific_use_is_never_this_adapters_to_grant() -> None:
    controller = _controller(_spec(), FakeProcess(), Clock())
    controller.start()
    receipt = controller.stop("done")
    with pytest.raises(LiveTwinError) as excinfo:
        mark_scientific_use(receipt)
    assert excinfo.value.code == "SCIENTIFIC_USE_UNAUTHORISED"


def test_argv_is_bounded_and_the_module_has_no_detach_surface() -> None:
    argv = sumo_argument_vector(_spec(), "corridor.net.xml", 51473)
    assert argv[0] == "sumo"
    assert "--remote-port" in argv
    with pytest.raises(LiveTwinError):
        sumo_argument_vector(_spec(), "../outside.net.xml", 51473)
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "live_twin.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("start_new_session", "daemon=", "subprocess", "Popen", "os.fork"):
        assert forbidden not in source
