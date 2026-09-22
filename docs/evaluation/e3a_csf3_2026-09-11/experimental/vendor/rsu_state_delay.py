"""Sub-second workload reports for Model C's one-second admission batches.

All K_MAX slots execute at the same logical batch time. Between batches,
remaining service workload decreases at one ms per ms, clipped at zero.
This module reconstructs that historical workload; it never advances the
live queues or interpolates between a past state and a future admission.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp


TICK_MS = 1000


class WorkloadReport(NamedTuple):
    busy_ms: jax.Array
    observed_at_ms: jax.Array
    captured_at_ms: jax.Array
    actual_age_ms: jax.Array
    warmup: jax.Array


def validate_delay_ms(delay_ms: int) -> int:
    if type(delay_ms) is not int or not 0 <= delay_ms <= TICK_MS:
        raise ValueError("RSU state delay must be an integer from 0 to 1000 ms")
    return delay_ms


def workload_report(*, previous_post_admission_busy_ms: jax.Array,
                    live_busy_ms: jax.Array, step_index: jax.Array,
                    delay_ms: int) -> WorkloadReport:
    """Read W(t-delay), before this tick's admissions, for 0 <= delay <= 1s.

    The previous post-admission state is right-continuous at (t-1000)+.
    A 1000ms report therefore includes that previous batch. At startup there
    is no prehistory: use the live initial state and report actual age zero.
    delay_ms is a static, validated configuration value under JIT.
    """
    validate_delay_ms(delay_ms)
    now = step_index * jnp.int32(TICK_MS)
    warmup = (step_index == 0) & (delay_ms > 0)
    if delay_ms == 0:
        busy = live_busy_ms
    else:
        elapsed = jnp.float32(TICK_MS - delay_ms)
        previous = previous_post_admission_busy_ms
        historical = previous - jnp.minimum(previous, elapsed)
        busy = jnp.where(warmup, live_busy_ms, historical)
    age = jnp.where(warmup, jnp.int32(0), jnp.int32(delay_ms))
    return WorkloadReport(busy, now, now - age, age, warmup)
