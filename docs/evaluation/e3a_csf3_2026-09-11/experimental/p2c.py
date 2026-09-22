"""E3a fresh-state P2C, native JAX with exact uint64 counter semantics.

The normative E3 contract is reproduced with two uint32 limbs so enabling
64-bit floats globally cannot change the frozen comparator numerics. No JAX
random key is consumed. The five-field counter uses the *dense* padded slot
identity, even across inactive, non-V2I, unavailable, and rejected positions.
Only the fresh, fixed-1x E3a placement is implemented here.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp


def u64(value: int) -> tuple[jax.Array, jax.Array]:
    """Convert a static strict uint64 key to low/high uint32 limbs."""
    if type(value) is not int or not 0 <= value <= (1 << 64) - 1:
        raise ValueError("counter fields must be strict uint64 integers")
    return jnp.uint32(value & 0xFFFFFFFF), jnp.uint32(value >> 32)


def _xor(a, b):
    return a[0] ^ b[0], a[1] ^ b[1]


def _shr(a, bits):
    return (a[0] >> jnp.uint32(bits)) | (a[1] << jnp.uint32(32 - bits)), a[1] >> jnp.uint32(bits)


def _add(a, b):
    low = a[0] + b[0]
    return low, a[1] + b[1] + (low < a[0]).astype(jnp.uint32)


def _mul(a, b):
    # Exact upper half of a 32x32 product using carry-safe 16-bit products.
    mask = jnp.uint32(0xFFFF)
    a0, a1 = a[0] & mask, a[0] >> jnp.uint32(16)
    b0, b1 = b[0] & mask, b[0] >> jnp.uint32(16)
    low_product = a0 * b0
    middle = a1 * b0 + (low_product >> jnp.uint32(16))
    middle2 = a0 * b1 + (middle & mask)
    high_product = a1 * b1 + (middle >> jnp.uint32(16)) + (middle2 >> jnp.uint32(16))
    return a[0] * b[0], high_product + a[1] * b[0] + a[0] * b[1]


def splitmix64(value):
    z = _add(value, u64(0x9E3779B97F4A7C15))
    z = _mul(_xor(z, _shr(z, 30)), u64(0xBF58476D1CE4E5B9))
    z = _mul(_xor(z, _shr(z, 27)), u64(0x94D049BB133111EB))
    return _xor(z, _shr(z, 31))


def mix_keys(fields):
    """Fold low/high limb pairs in the contract's exact five-field order."""
    if len(fields) != 5:
        raise ValueError("exactly five counter fields are required")
    h = u64(0x6A09E667F3BCC909)
    for field in fields:
        h = splitmix64(_xor(h, field))
    return h


def _mod_small(value, divisor):
    """uint64 modulo n for 1<=n<=65535, without overflowing uint32."""
    d = divisor.astype(jnp.uint32)
    mask = jnp.uint32(0xFFFF)
    remainder = jnp.uint32(0)
    for limb in (
        value[1] >> jnp.uint32(16),
        value[1] & mask,
        value[0] >> jnp.uint32(16),
        value[0] & mask,
    ):
        remainder = ((remainder << jnp.uint32(16)) + limb) % d
    return remainder.astype(jnp.int32)


def pair_indices(fields, count):
    """Caller guarantees count>=2; n=0/1 never execute either hash."""
    h = mix_keys(fields)
    first = _mod_small(h, count)
    second = _mod_small(splitmix64(h), count - jnp.int32(1))
    return first, second + (second >= first).astype(jnp.int32)


class P2CPlacement(NamedTuple):
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
    feasible_count: jax.Array
    sampled_pair: jax.Array
    feasibility_workload_checks: jax.Array
    ranking_workload_inspections: jax.Array
    unique_workload_values_observed: jax.Array
    sequential_task_ordinal: jax.Array


def p2c_sequential(
    *,
    attempts,
    ingress_radio_viable,
    deadlines_ms,
    service_work_ms_by_rsu,
    base_busy_ms,
    base_load,
    capacity,
    reconciliation_iterations,
    evaluator_seed,
    fleet_seed,
    outer_tick,
    task_slot,
):
    """Feasibility-first pair placement with immediate admitted reservations.

    Work and load updates use the same float32/int32 causal operations as E2d.
    The N0 rejection precedence is radio unavailable, no deadline-feasible
    RSU, then all deadline-feasible RSUs full. No target is selected on N0.
    The coarse_candidate field is an adapter for the frozen outcome encoder:
    it means radio-viable attempt here, so N0 gate/cap retain their own class.
    """
    width = attempts.shape[0]
    count_rsus = base_busy_ms.shape[0]
    if not 1 <= count_rsus <= 65535:
        raise ValueError("uint64 modulo implementation requires 1..65535 RSUs")
    seed_fields = (u64(evaluator_seed), u64(fleet_seed))
    ordinals = task_slot.astype(jnp.int32) * width + jnp.arange(width, dtype=jnp.int32)

    def one_pass():
        def place(carry, candidate):
            busy, load = carry
            attempt, radio, deadline, service, ordinal = candidate
            eligible = attempt & radio
            deadline_ok = busy < deadline
            feasible = deadline_ok & (load < jnp.int32(capacity)) & eligible
            count = jnp.sum(feasible.astype(jnp.int32))
            # Nonzero returns ascending padded IDs; only positions <count used.
            candidates = jnp.nonzero(feasible, size=count_rsus, fill_value=0)[0].astype(jnp.int32)

            def choose_pair(_):
                fields = seed_fields + (
                    (outer_tick.astype(jnp.uint32), jnp.uint32(0)),
                    (task_slot.astype(jnp.uint32), jnp.uint32(0)),
                    (ordinal.astype(jnp.uint32), jnp.uint32(0)),
                )
                first, second = pair_indices(fields, count)
                a, b = candidates[first], candidates[second]
                lo, hi = jnp.minimum(a, b), jnp.maximum(a, b)
                target = jnp.where(busy[lo] <= busy[hi], lo, hi)
                return target, jnp.stack((lo, hi))

            target, pair = jax.lax.cond(
                count >= 2,
                choose_pair,
                lambda _: (
                    jnp.where(count == 1, candidates[0], jnp.int32(-1)),
                    jnp.full((2,), -1, dtype=jnp.int32),
                ),
                operand=None,
            )
            admitted = eligible & (count > 0)
            gate_rejected = eligible & ~jnp.any(deadline_ok)
            cap_rejected = eligible & ~gate_rejected & (count == 0)
            # Safe gather only: this fallback has no selected/execution meaning.
            safe_target = jnp.maximum(target, 0)
            work = service[safe_target]
            before = jnp.where(admitted, busy[safe_target], jnp.float32(-1.0))
            offset = jnp.where(
                admitted, busy[safe_target] - base_busy_ms[safe_target], jnp.float32(0.0)
            )
            busy = busy.at[safe_target].add(jnp.where(admitted, work, jnp.float32(0.0)))
            load = load.at[safe_target].add(admitted.astype(jnp.int32))
            checks = jnp.where(eligible, count_rsus, 0).astype(jnp.int32)
            rankings = jnp.minimum(count, jnp.int32(2))
            return (busy, load), (
                target,
                admitted,
                eligible,
                gate_rejected,
                cap_rejected,
                offset,
                work,
                before,
                count,
                pair,
                checks,
                rankings,
                checks,
                ordinal,
            )

        final, out = jax.lax.scan(
            place,
            (base_busy_ms, base_load),
            (attempts, ingress_radio_viable, deadlines_ms, service_work_ms_by_rsu, ordinals),
        )
        return P2CPlacement(*out[:7], *final, *out[7:])

    result = None
    for _ in range(max(reconciliation_iterations, 1)):
        result = one_pass()
    return result
