from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import fixed_clock
from tests.unit.test_experiment_planning import _experiment, _seeds
from traffictwin.experiments.protocol import build_experiment_protocol
from traffictwin.experiments.tracking import (
    InvalidProtocolSlotTransitionError,
    ProtocolSlotStatus,
    ProtocolTracker,
)


def test_protocol_tracker_persists_explicit_slot_lifecycle(tmp_path: Path) -> None:
    protocol = build_experiment_protocol(_experiment(), _seeds(), clock=fixed_clock)
    tracker = ProtocolTracker(tmp_path / "registry.sqlite")

    assert tracker.register_protocol(protocol, clock=fixed_clock)
    assert not tracker.register_protocol(protocol, clock=fixed_clock)
    assert tracker.summary(protocol.protocol_id).counts_by_status["planned"] == 8

    record = tracker.update_slot(
        protocol.protocol_id,
        "slot-0001",
        ProtocolSlotStatus.RECEIVED,
        observed_run_id="external-run-1",
        clock=fixed_clock,
    )
    assert record.status is ProtocolSlotStatus.RECEIVED
    assert record.observed_run_id == "external-run-1"

    tracker.update_slot(
        protocol.protocol_id,
        "slot-0001",
        ProtocolSlotStatus.VALIDATED,
        clock=fixed_clock,
    )
    tracker.update_slot(
        protocol.protocol_id,
        "slot-0001",
        ProtocolSlotStatus.MATCHED,
        observed_bundle_id="bundle-external-1",
        clock=fixed_clock,
    )
    completed = tracker.update_slot(
        protocol.protocol_id,
        "slot-0001",
        ProtocolSlotStatus.COMPLETE,
        clock=fixed_clock,
    )
    assert completed.status is ProtocolSlotStatus.COMPLETE

    with pytest.raises(InvalidProtocolSlotTransitionError):
        tracker.update_slot(
            protocol.protocol_id,
            "slot-0002",
            ProtocolSlotStatus.COMPLETE,
            clock=fixed_clock,
        )
