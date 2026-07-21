"""Synthetic golden and refusal tests for VEC-04 joins."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from tests.tos_v2_helpers import (
    V2_SCENARIO,
    build_v2_occupancy_rows,
    build_v2_perstep,
    build_v2_pertask,
    build_v2_trace,
)
from traffictwin.domain.enums import Decision
from traffictwin.integration.vec_identity import (
    VecIdentitySnapshot,
    build_vehicle_identity_snapshot,
)
from traffictwin.integration.vec_task_join import (
    VecJoinedTaskObservation,
    VecTargetAvailability,
    VecTaskJoinError,
    VecTaskJoinReport,
    build_task_join_report,
    iter_joined_tasks,
    vec_task_join_contract,
)


def _identity() -> VecIdentitySnapshot:
    header, rows = build_v2_occupancy_rows()
    return build_vehicle_identity_snapshot(build_v2_trace(), header, rows, scenario=V2_SCENARIO)


def _report() -> VecTaskJoinReport:
    return build_task_join_report(
        build_v2_trace(),
        build_v2_perstep(),
        build_v2_pertask(),
        _identity(),
        run_label="synthetic_golden",
    )


def test_golden_join_reconciles_all_count_families() -> None:
    report = _report()

    assert report.total_tasks == 7
    assert report.deadline_met_tasks == 5
    assert sum(report.task_class_counts.values()) == 7
    assert report.action_counts == {
        Decision.LOCAL: 3,
        Decision.V2I: 3,
        Decision.V2V: 1,
    }
    assert report.target_availability_counts == {
        VecTargetAvailability.NOT_APPLICABLE_LOCAL: 3,
        VecTargetAvailability.ELIGIBLE_TARGET: 4,
        VecTargetAvailability.NO_ELIGIBLE_TARGET: 0,
    }
    assert report.no_target_is_failure is False
    assert report.action_is_transfer_confirmation is False
    assert vec_task_join_contract().fingerprint() == vec_task_join_contract().fingerprint()


def test_joined_rows_have_exact_vehicle_and_fixed_slot_attributes() -> None:
    rows = list(
        iter_joined_tasks(
            build_v2_trace(),
            build_v2_perstep(),
            build_v2_pertask(),
            _identity(),
            _report(),
        )
    )

    assert len(rows) == 7
    recycled = [row for row in rows if row.time_index == 3 and row.slot == 0]
    assert recycled[0].sumo_vehicle_id == "veh_synthetic_c"
    assert recycled[0].slot_tier == 0
    assert all(row.transfer_confirmed is False for row in rows)
    assert all(row.eventual_completion == "unavailable" for row in rows)


def test_no_eligible_target_is_visible_but_not_called_failure() -> None:
    perstep = build_v2_perstep()
    perstep["veh_best_rsu"] = np.asarray(perstep["veh_best_rsu"]).copy()
    perstep["veh_best_rsu"][0, 1] = -1
    report = build_task_join_report(
        build_v2_trace(), perstep, build_v2_pertask(), _identity(), run_label="no_target"
    )
    rows = list(
        iter_joined_tasks(build_v2_trace(), perstep, build_v2_pertask(), _identity(), report)
    )
    row = next(item for item in rows if item.time_index == 0 and item.slot == 1)

    assert row.action is Decision.V2I
    assert row.target_availability is VecTargetAvailability.NO_ELIGIBLE_TARGET
    assert row.selected_target_index is None
    assert row.failure_inferred is False


def test_task_count_deadline_and_latency_mismatches_fail_closed() -> None:
    for key, position, value, message in (
        ("task_active", (0, 1, 0), False, "active counts"),
        ("task_met", (0, 0, 0), False, "deadline successes"),
        ("task_lat_ms", (0, 0, 0), np.float32(71.0), "latency"),
    ):
        pertask = build_v2_pertask()
        pertask[key] = np.asarray(pertask[key]).copy()
        pertask[key][position] = value
        with pytest.raises(VecTaskJoinError, match=message):
            build_task_join_report(
                build_v2_trace(),
                build_v2_perstep(),
                pertask,
                _identity(),
                run_label="bad",
            )


def test_task_outside_occupancy_and_changed_artifact_are_refused() -> None:
    pertask = build_v2_pertask()
    pertask["task_active"] = np.asarray(pertask["task_active"]).copy()
    pertask["task_active"][0, 0, 2] = True
    with pytest.raises(VecTaskJoinError):
        build_task_join_report(
            build_v2_trace(), build_v2_perstep(), pertask, _identity(), run_label="bad"
        )

    perstep = build_v2_perstep()
    perstep["veh_queue_ms"] = np.asarray(perstep["veh_queue_ms"]).copy()
    report = _report()
    perstep["veh_queue_ms"][0, 0] = np.float32(1.0)
    with pytest.raises(VecTaskJoinError, match="does not match"):
        list(iter_joined_tasks(build_v2_trace(), perstep, build_v2_pertask(), _identity(), report))


def test_semantic_claims_cannot_be_strengthened() -> None:
    row = next(
        iter_joined_tasks(
            build_v2_trace(),
            build_v2_perstep(),
            build_v2_pertask(),
            _identity(),
            _report(),
        )
    )
    payload = row.model_dump(mode="json")
    payload["transfer_confirmed"] = True
    with pytest.raises(ValidationError, match="transfer_confirmed"):
        VecJoinedTaskObservation.model_validate(payload)
