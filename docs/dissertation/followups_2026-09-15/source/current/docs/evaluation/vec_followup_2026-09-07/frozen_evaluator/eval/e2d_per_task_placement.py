"""Pure per-task sequential least-busy placement for the E2d evaluator mode.

The selector operates on remaining RSU compute workload in milliseconds.  It
contains no random-number operation and is called only by ``per_task_dla``.
Existing evaluator modes retain their inherited placement and admission code.
"""

from __future__ import annotations

from typing import NamedTuple

import jax
import jax.numpy as jnp


class PerTaskPlacement(NamedTuple):
    """Deterministic task-order placement and admission result."""

    selected_rsu: jax.Array
    admitted: jax.Array
    coarse_candidate: jax.Array
    gate_rejected: jax.Array
    cap_rejected: jax.Array
    queue_offset_ms: jax.Array
    selected_service_work_ms: jax.Array
    effective_busy_ms: jax.Array
    effective_load: jax.Array
    placement_busy_before_ms: jax.Array


def _one_sequential_pass(
    *,
    attempts: jax.Array,
    ingress_radio_viable: jax.Array,
    deadlines_ms: jax.Array,
    service_work_ms_by_rsu: jax.Array,
    base_busy_ms: jax.Array,
    base_load: jax.Array,
    capacity: int,
    placement_busy_ms: jax.Array | None = None,
) -> PerTaskPlacement:
    """Run one causal pass in ascending padded-vehicle-slot order."""

    def place_one(
        carry: tuple[jax.Array, ...],
        candidate: tuple[jax.Array, jax.Array, jax.Array, jax.Array],
    ) -> tuple[tuple[jax.Array, ...], tuple[jax.Array, ...]]:
        effective_busy_ms, effective_load = carry[:2]
        # Only placement sees the delayed report. The selected RSU applies
        # the inherited gate/cap checks against its actual queue.
        decision_busy_ms = (effective_busy_ms if placement_busy_ms is None
                            else carry[2])
        attempt, radio_viable, deadline_ms, service_by_rsu = candidate

        # jnp.argmin deterministically selects the lowest RSU index on ties.
        selected_rsu = jnp.argmin(decision_busy_ms).astype(jnp.int32)
        placement_busy_before_ms = decision_busy_ms[selected_rsu]
        selected_work_ms = service_by_rsu[selected_rsu]
        queue_offset_ms = effective_busy_ms[selected_rsu] - base_busy_ms[selected_rsu]

        # Match inherited DLA's two-stage cap semantics.  A target already at
        # cap at substep entry fails the coarse availability check; a target
        # filled by earlier admitted candidates is an in-batch cap rejection.
        coarse_candidate = (
            attempt & radio_viable & (base_load[selected_rsu] < jnp.int32(capacity))
        )
        gate_ok = effective_busy_ms[selected_rsu] < deadline_ms
        cap_ok = effective_load[selected_rsu] < jnp.int32(capacity)
        gate_rejected = coarse_candidate & ~gate_ok
        cap_rejected = coarse_candidate & gate_ok & ~cap_ok
        admitted = coarse_candidate & gate_ok & cap_ok

        effective_busy_ms = effective_busy_ms.at[selected_rsu].add(
            jnp.where(admitted, selected_work_ms, jnp.float32(0.0))
        )
        effective_load = effective_load.at[selected_rsu].add(admitted.astype(jnp.int32))
        outputs = (
            selected_rsu,
            admitted,
            coarse_candidate,
            gate_rejected,
            cap_rejected,
            queue_offset_ms,
            selected_work_ms,
            placement_busy_before_ms,
        )
        next_carry = (effective_busy_ms, effective_load)
        if placement_busy_ms is not None:
            decision_busy_ms = decision_busy_ms.at[selected_rsu].add(
                jnp.where(admitted, selected_work_ms, jnp.float32(0.0)))
            next_carry += (decision_busy_ms,)
        return next_carry, outputs

    initial = (base_busy_ms, base_load)
    if placement_busy_ms is not None:
        initial += (placement_busy_ms,)
    final, outputs = jax.lax.scan(
        place_one,
        initial,
        (attempts, ingress_radio_viable, deadlines_ms, service_work_ms_by_rsu),
    )
    (
        selected_rsu,
        admitted,
        coarse_candidate,
        gate_rejected,
        cap_rejected,
        queue_offset_ms,
        selected_service_work_ms,
        placement_busy_before_ms,
    ) = outputs
    return PerTaskPlacement(
        selected_rsu=selected_rsu,
        admitted=admitted,
        coarse_candidate=coarse_candidate,
        gate_rejected=gate_rejected,
        cap_rejected=cap_rejected,
        queue_offset_ms=queue_offset_ms,
        selected_service_work_ms=selected_service_work_ms,
        effective_busy_ms=final[0],
        effective_load=final[1],
        placement_busy_before_ms=placement_busy_before_ms,
    )


def per_task_sequential_least_busy(
    *,
    attempts: jax.Array,
    ingress_radio_viable: jax.Array,
    deadlines_ms: jax.Array,
    service_work_ms_by_rsu: jax.Array,
    base_busy_ms: jax.Array,
    base_load: jax.Array,
    capacity: int,
    reconciliation_iterations: int,
    placement_busy_ms: jax.Array | None = None,
) -> PerTaskPlacement:
    """Place and admit candidates using a causal shortest-workload scan.

    Candidate order is ascending padded vehicle-slot index.  Target selection
    spans the same domain as inherited DLA: every RSU.  The deadline gate is
    the same strict backlog-only test, ``effective_busy_ms[target] < deadline``.

    Common-target DLA needs fixed-point reconciliation because later rejected
    work is removed from vectorised offsets.  This causal scan never reserves
    rejected work, so one pass is already self-consistent.  To retain the
    configured reconciliation contract, the same pass is repeated from the
    identical live substep state and the final (idempotent) result is used.

    Optional placement_busy_ms is an older workload report plus this tick's
    acknowledged admissions. It affects selection only; admission and queue
    offsets always use base_busy_ms/base_load and accepted work. Omitting it
    retains the original fresh-state branch and arithmetic.
    """

    result: PerTaskPlacement | None = None
    for _ in range(max(reconciliation_iterations, 1)):
        result = _one_sequential_pass(
            attempts=attempts,
            ingress_radio_viable=ingress_radio_viable,
            deadlines_ms=deadlines_ms,
            service_work_ms_by_rsu=service_work_ms_by_rsu,
            base_busy_ms=base_busy_ms,
            base_load=base_load,
            capacity=capacity,
            placement_busy_ms=placement_busy_ms,
        )
    assert result is not None
    return result
