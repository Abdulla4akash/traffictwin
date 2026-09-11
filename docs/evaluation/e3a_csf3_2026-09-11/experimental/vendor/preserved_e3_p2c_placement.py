"""Sequential deadline-aware Power-of-Two-Choices (P2C) primitives for E3.

Scope and deadline contract
---------------------------
Feasibility is **upstream**. Callers must compute the feasible candidate set
before invoking this module, using the valid comparator's deadline contract:
the same strict backlog test used by the E2/E2d evaluator,

    effective_busy_ms[rsu] < TASK_DEADLINE_MS[task_type]

as implemented in ``eval/e2d_per_task_placement.py`` and
``jaxmarl/env/vec_jax.py`` (``TASK_DEADLINE_MS = [100, 500, 100]`` ms).
This module **does not** recompute feasibility, does not infer deadlines
from task type, and does not change the gate formula. It receives the
already-filtered feasible list and treats it as authoritative. Any deadline
re-evaluation belongs to the evaluator; Lane 08 owns the JAX/evaluator
integration.

P2C mechanics (sequential, reservation-aware)
---------------------------------------------
* No feasible candidates -> rejection (no selection, no reservation).
* One feasible candidate -> select it (inspection_count=1); hashing is skipped.
* >=2 feasible candidates -> sample two distinct candidates **without
  replacement** via the contract deterministic rule keyed by
  ``(evaluator_seed, fleet_seed, outer_tick, task_slot,
  sequential_task_ordinal)`` in that exact order. No ``hash()``, no ``random``,
  no mutable/global RNG, no JAX, no string/byte serialization.
  Fold: ``h_init=0x6A09E667F3BCC909``; for each field
  ``h=splitmix64(h xor uint64(field))`` with unsigned uint64 wrapping
  (mod 2^64 after every operation). Pair indices on the ascending-unique
  feasible list: ``first=h%n``, ``j=splitmix64(h)%(n-1)``,
  ``second=j if j<first else j+1``; then sort only the resulting two RSU IDs
  for telemetry (candidate list stays ascending, pair sorting is telemetry-only,
  not before indexing). Modulo reduction has negligible bias, not mathematically
  exact-uniform — no uniformity claim. Because the mixer includes
  ``sequential_task_ordinal``, the sampled pair varies with task ordinal
  (not necessarily every adjacent ordinal, but the construction cannot
  reuse a single pair for all ordinals when ``n >= 3``).

* Compare **only** the sampled pair on current declared/reserved workload
  (``declared_workloads[rsu] + reservation_overlay[rsu]``). Lower workload
  wins; on tie the stable lowest RSU-id wins. This intentionally ignores any
  third globally least-busy RSU outside the pair — a correct P2C must not
  degenerate to global least-busy.

* Immediately update an explicit ``reservation_overlay`` dict
  (``overlay[chosen] += task_work_ms``) before the next sequential call
  within the same outer tick. Rejected tasks never reserve or execute.

* No actor attribution: the decision uses only RSU ids, workloads and the
  counter-based key; actor/vehicle identity is never consulted.

Typed receipt
-------------
Every call returns a :class:`P2CReceipt` containing feasible count, sampled
pair, inspection count, chosen RSU, reserved work, the five key fields,
``state_age_ms`` and a rejection reason (or ``None`` on success). Invalid
inputs are sanitized: the offending typed field is ``None`` in the receipt
rather than leaking a negative/coerced value as an apparently valid fact.
Do not fabricate ``0`` as a fresh age.

Pure logic
----------
This module is pure Python 3.11 compatible, typed, and has no JAX,
evaluator or global-state dependencies.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, MutableMapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Constants / rejection reason vocabulary
# ---------------------------------------------------------------------------

REJECTION_NO_FEASIBLE = "no_feasible_candidates"
REJECTION_INVALID_STATE_AGE = "invalid_state_age_ms"
REJECTION_INVALID_WORKLOAD = "invalid_declared_workload"
REJECTION_INVALID_TASK_WORK = "invalid_task_work_ms"
REJECTION_INVALID_KEY = "invalid_key"
REJECTION_INVALID_OVERLAY = "invalid_reservation_overlay"

# Module-owned invariant error for reservation rollback failures.
# All rollback/post-restore verification failures raise this type with a
# stable message prefix independent of any adversarial overlay exception text.


class P2CInvariantError(RuntimeError):
    """Reservation overlay invariant violation (module-owned)."""


_INVARIANT_PREFIX = "reservation overlay invariant violation"

# Sentinel for deliberate Exception suppression via contextlib.suppress.
# Any helper that uses ``suppress(Exception)`` stores its result in a
# variable initialised to this sentinel; ``is _UNSET`` therefore means
# the operation raised and was suppressed, without an ``except Exception``
# clause (BLE001).
_UNSET: object = object()

TICK_MS = 1000

MASK64 = (1 << 64) - 1
_SPLITMIX_CONST1 = 0xBF58476D1CE4E5B9
_SPLITMIX_CONST2 = 0x94D049BB133111EB
_SPLITMIX_INCREMENT = 0x9E3779B97F4A7C15
_H_INIT = 0x6A09E667F3BCC909


def _splitmix64(x: int) -> int:
    """Deterministic SplitMix64 mixer (counter-based, no global RNG).

    Contract steps (mod 2^64 after every operation):
        z = (x + 0x9E3779B97F4A7C15) mod 2^64
        z = ((z xor (z>>30)) * 0xBF58476D1CE4E5B9) mod 2^64
        z = ((z xor (z>>27)) * 0x94D049BB133111EB) mod 2^64
        return z xor (z>>31)
    """

    x = (x + _SPLITMIX_INCREMENT) & MASK64
    z = x
    z = (z ^ (z >> 30)) * _SPLITMIX_CONST1 & MASK64
    z = (z ^ (z >> 27)) * _SPLITMIX_CONST2 & MASK64
    return (z ^ (z >> 31)) & MASK64


def _mix_keys(
    evaluator_seed: int,
    fleet_seed: int,
    outer_tick: int,
    task_slot: int,
    sequential_task_ordinal: int,
) -> int:
    """Combine five integer key fields into a 64-bit pseudo-random value.

    Contract fold (exact):
        h_init = 0x6A09E667F3BCC909
        fields ordered exactly (evaluator_seed, fleet_seed, outer_tick,
            task_slot, sequential_task_ordinal)
        for each field: h = splitmix64(h xor uint64(field))
        unsigned uint64 with modulo 2^64 after every operation.
    """

    h = _H_INIT
    for v in (
        evaluator_seed,
        fleet_seed,
        outer_tick,
        task_slot,
        sequential_task_ordinal,
    ):
        vv = int(v) & MASK64
        h = _splitmix64((h ^ vv) & MASK64)
    return h


def _deterministic_pair(
    sorted_unique: Sequence[int],
    evaluator_seed: int,
    fleet_seed: int,
    outer_tick: int,
    task_slot: int,
    sequential_task_ordinal: int,
) -> tuple[int, int]:
    """Sample two distinct candidates without replacement deterministically.

    Contract pair indices (for n>=2 on ascending-unique candidate list):
        first = h % n
        j = splitmix64(h) % (n-1)
        second = j if j < first else j+1
    where h is the contract fold. Index the ascending-unique list, then
    sort only the resulting two RSU IDs for telemetry. Modulo reduction has
    negligible bias, not mathematically exact-uniform (no uniformity claim).
    """

    n = len(sorted_unique)
    assert n >= 2
    h = _mix_keys(
        evaluator_seed, fleet_seed, outer_tick, task_slot, sequential_task_ordinal
    )
    i = h % n
    h2 = _splitmix64(h)
    j = h2 % (n - 1)
    if j >= i:
        j += 1
    a = int(sorted_unique[i])
    b = int(sorted_unique[j])
    if a < b:
        return (a, b)
    return (b, a)


def _is_strict_int(x: object) -> bool:
    return type(x) is int


def _is_strict_int_nonnegative(x: object) -> bool:
    return type(x) is int and x >= 0


def _is_strict_workload_value(x: object) -> bool:
    if type(x) is bool:
        return False
    if type(x) not in (int, float):
        return False
    fv = float(x)  # type: ignore[arg-type]
    return math.isfinite(fv) and fv >= 0.0


def _is_strict_positive_finite(x: object) -> bool:
    if type(x) is bool:
        return False
    if type(x) not in (int, float):
        return False
    fv = float(x)  # type: ignore[arg-type]
    return math.isfinite(fv) and fv > 0.0


# ---------------------------------------------------------------------------
# Typed receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class P2CReceipt:
    """Typed receipt for a single sequential P2C placement decision."""

    feasible_count: int | None
    sampled_pair: tuple[int, int] | None
    inspection_count: int
    chosen_rsu: int | None
    reserved_work_ms: float | None
    evaluator_seed: int | None
    fleet_seed: int | None
    outer_tick: int | None
    task_slot: int | None
    sequential_task_ordinal: int | None
    state_age_ms: int | None
    rejection_reason: str | None


# ---------------------------------------------------------------------------
# Internal helpers: centralized sanitization and transaction
# ---------------------------------------------------------------------------


def _sanitize_state_age(state_age_ms: object) -> tuple[int | None, bool]:
    """Return (sanitized_value, is_valid). Sanitized is None when invalid."""
    if not _is_strict_int(state_age_ms):
        return None, False
    v = int(state_age_ms)  # type: ignore[call-overload]
    if v < 0 or v % TICK_MS != 0:
        return None, False
    return v, True


def _sanitize_key(value: object) -> tuple[int | None, bool]:
    if type(value) is bool:
        return None, False
    if type(value) is not int:
        return None, False
    v = int(value)
    if v < 0 or v > MASK64:
        return None, False
    return v, True


def _validate_candidates(
    candidates: object,
) -> tuple[list[int] | None, int | None, str | None]:
    """Validate feasible_candidates without exception guards.

    Returns (sorted_unique, feasible_count, rejection_reason).
    Rejection is REJECTION_INVALID_KEY when candidates is wrong type or
    contains non-strict IDs.
    """
    if not isinstance(candidates, Sequence):
        return None, None, REJECTION_INVALID_KEY
    if isinstance(candidates, (str, bytes, bytearray)):
        return None, None, REJECTION_INVALID_KEY
    validated: list[int] = []
    for c in candidates:
        if not _is_strict_int_nonnegative(c):
            return None, None, REJECTION_INVALID_KEY
        validated.append(int(c))
    sorted_unique = sorted(set(validated))
    return sorted_unique, len(sorted_unique), None


def _make_rejection(
    rejection_reason: str,
    *,
    feasible_count: int | None,
    sampled_pair: tuple[int, int] | None,
    inspection_count: int,
    evaluator_seed: int | None,
    fleet_seed: int | None,
    outer_tick: int | None,
    task_slot: int | None,
    sequential_task_ordinal: int | None,
    state_age_ms: int | None,
) -> P2CReceipt:
    """Centralized rejection receipt construction (no leakage)."""
    return P2CReceipt(
        feasible_count=feasible_count,
        sampled_pair=sampled_pair,
        inspection_count=inspection_count,
        chosen_rsu=None,
        reserved_work_ms=None,
        evaluator_seed=evaluator_seed,
        fleet_seed=fleet_seed,
        outer_tick=outer_tick,
        task_slot=task_slot,
        sequential_task_ordinal=sequential_task_ordinal,
        state_age_ms=state_age_ms,
        rejection_reason=rejection_reason,
    )


def _overlay_contains(
    mapping: MutableMapping[int, float], key: int
) -> tuple[bool, bool]:
    """Deliberate ``key in mapping`` with ``suppress(Exception)``.

    Returns ``(ok, present)`` where ``ok`` is ``False`` iff ``Exception``
    was suppressed (BLE001 avoided via ``suppress`` + ``_UNSET`` sentinel).
    """
    result: object = _UNSET
    with suppress(Exception):
        result = key in mapping
    if result is _UNSET:
        return (False, False)
    return (True, bool(result))


def _overlay_get(mapping: MutableMapping[int, float], key: int) -> tuple[bool, Any]:
    """Deliberate ``mapping[key]`` with ``suppress(Exception)``.

    Returns ``(ok, value)`` where ``ok`` is ``False`` iff ``Exception`` was
    suppressed. ``value`` is only valid when ``ok`` is ``True``.
    """
    result: object = _UNSET
    with suppress(Exception):
        result = mapping[key]
    if result is _UNSET:
        return (False, _UNSET)
    return (True, result)


def _overlay_set(mapping: MutableMapping[int, float], key: int, value: float) -> bool:
    """Deliberate ``mapping[key] = value`` with ``suppress(Exception)``.

    Returns ``True`` iff the write succeeded without ``Exception``.
    """
    done: object = _UNSET
    with suppress(Exception):
        mapping[key] = value
        done = None
    return done is not _UNSET


def _try_reserve(
    overlay: MutableMapping[int, float],
    chosen: int,
    task_work_ms: float,
    captured_had_key: bool,
    captured_prior: float | None,
) -> str | None:
    """Attempt to reserve using captured overlay state; rollback on failure.

    Caller must have validated overlay presence/value exactly once and passed
    the captured ``captured_had_key``/``captured_prior``. This function never
    performs a second validation-dependent lookup (no ``chosen in overlay`` or
    ``overlay[chosen]`` to compute the base). The new reserved value is
    computed only from captured finite non-negative inputs and verified finite
    non-negative before mutation.

    Returns None on success, rejection reason on handled write failure.
    Raises P2CInvariantError with stable module-owned prefix on any
    rollback/write/delete/postcondition failure, including adversarial
    ``P2CInvariantError`` with forged text (never leaked).
    """
    # Verify captured inputs are finite non-negative (defensive, caller validated).
    base: float
    if captured_had_key:
        assert captured_prior is not None
        if not (math.isfinite(captured_prior) and captured_prior >= 0.0):
            return REJECTION_INVALID_OVERLAY
        base = float(captured_prior)
    else:
        base = 0.0
    if not (math.isfinite(task_work_ms) and task_work_ms > 0.0):
        return REJECTION_INVALID_OVERLAY
    new_val = base + float(task_work_ms)
    if not (math.isfinite(new_val) and new_val >= 0.0):
        return REJECTION_INVALID_OVERLAY
    if _overlay_set(overlay, chosen, float(new_val)):
        return None
    # Deliberate suppression path (no BLE001): write raised Exception.
    # Attempt rollback using only captured state; never leak write exception text.
    try:
        if captured_had_key:
            assert captured_prior is not None
            try:
                overlay[chosen] = float(captured_prior)
            except Exception as e:
                raise P2CInvariantError(f"{_INVARIANT_PREFIX}: rollback failed") from e
            try:
                cur = overlay[chosen]
            except Exception as e:
                raise P2CInvariantError(f"{_INVARIANT_PREFIX}: rollback failed") from e
            try:
                ok = _is_strict_workload_value(cur) and float(cur) == float(
                    captured_prior
                )
            except Exception as e:
                raise P2CInvariantError(f"{_INVARIANT_PREFIX}: restore mismatch") from e
            if not ok:
                raise P2CInvariantError(f"{_INVARIANT_PREFIX}: restore mismatch")
        else:
            try:
                present = chosen in overlay
            except Exception as e:
                raise P2CInvariantError(f"{_INVARIANT_PREFIX}: rollback failed") from e
            if present:
                try:
                    del overlay[chosen]
                except Exception as e:
                    raise P2CInvariantError(
                        f"{_INVARIANT_PREFIX}: rollback failed"
                    ) from e
            try:
                still_present = chosen in overlay
            except Exception as e:
                raise P2CInvariantError(f"{_INVARIANT_PREFIX}: rollback failed") from e
            if still_present:
                raise P2CInvariantError(
                    f"{_INVARIANT_PREFIX}: key still present after rollback"
                )
    except P2CInvariantError as inv_e:
        msg = str(inv_e)
        if msg.startswith(_INVARIANT_PREFIX):
            raise
        raise P2CInvariantError(f"{_INVARIANT_PREFIX}: rollback failed") from inv_e
    except Exception as rollback_e:
        raise P2CInvariantError(f"{_INVARIANT_PREFIX}: rollback failed") from rollback_e
    return REJECTION_INVALID_OVERLAY


# ---------------------------------------------------------------------------
# Core primitive
# ---------------------------------------------------------------------------


def p2c_select(
    feasible_candidates: Sequence[int],
    declared_workloads: Mapping[int, float],
    reservation_overlay: MutableMapping[int, float],
    state_age_ms: int,
    evaluator_seed: int,
    fleet_seed: int,
    outer_tick: int,
    task_slot: int,
    sequential_task_ordinal: int,
    task_work_ms: float,
) -> P2CReceipt:
    """Sequential deadline-aware P2C selection for a single offered task.

    Args:
        feasible_candidates: already-computed feasible RSU ids (upstream
            feasibility must use the valid comparator's deadline contract).
            Duplicates are deduplicated; order is ignored (sorted) so shuffled
            input order cannot affect the outcome. Each entry must be a strict
            nonnegative int (bool/float/string rejected, no coercion).
        declared_workloads: mapping RSU id -> current declared workload (ms).
            Only the selected candidate(s) are read/validated; a hidden global
            scan is forbidden. Missing workload for a selected candidate is
            rejected. Values must be strict finite nonnegative numbers
            (bool/nonfinite/negative rejected).
        reservation_overlay: explicit required mutable dict RSU id ->
            reserved work (ms). Only selected overlay entries are validated
            (bool/nonfinite/negative rejected). Rejected tasks never mutate it.
        state_age_ms: typed strict int, nonnegative, exactly divisible by
            tick_ms=1000. Reject bool/float/10ms/200ms/NaN etc.
        evaluator_seed, fleet_seed, outer_tick, task_slot,
        sequential_task_ordinal: counter-based key for deterministic pair
            sampling. Each must be strict Python int in inclusive [0, 2^64-1]
            (bool/float/string/negative/>2^64-1 rejected, no coercion and no
            silent wrapping; 2^64-1 remains valid). Invalid key fields yield
            invalid_key with None sanitization and no mutation.
        task_work_ms: explicit finite positive workload to reserve for the
            chosen RSU (ms). No default fabrication.

    Returns:
        P2CReceipt with all key fields, rejection reason, and reservation
        details. Invalid typed fields are ``None`` in the receipt (no
        fabricated ``0`` age or coerced keys).
    """
    # Sanitize state_age and keys centrally (no coercion leakage)
    sanitized_age, valid_age = _sanitize_state_age(state_age_ms)
    sanitized_es, valid_es = _sanitize_key(evaluator_seed)
    sanitized_fs, valid_fs = _sanitize_key(fleet_seed)
    sanitized_ot, valid_ot = _sanitize_key(outer_tick)
    sanitized_ts, valid_ts = _sanitize_key(task_slot)
    sanitized_ord, valid_ord = _sanitize_key(sequential_task_ordinal)

    # Validate candidates without exception guards (explicit typed check)
    sorted_unique, feasible_count, cand_rejection = _validate_candidates(
        feasible_candidates
    )
    # sanitized feasible_count: None if invalid else int
    sanitized_feasible: int | None = feasible_count

    # Helper to build rejection with sanitized fields
    def reject(
        reason: str, *, sampled_pair: tuple[int, int] | None = None, inspection: int = 0
    ) -> P2CReceipt:
        return _make_rejection(
            reason,
            feasible_count=sanitized_feasible,
            sampled_pair=sampled_pair,
            inspection_count=inspection,
            evaluator_seed=sanitized_es,
            fleet_seed=sanitized_fs,
            outer_tick=sanitized_ot,
            task_slot=sanitized_ts,
            sequential_task_ordinal=sanitized_ord,
            state_age_ms=sanitized_age,
        )

    # Validate reservation_overlay is MutableMapping (no workload scan)
    if not isinstance(reservation_overlay, MutableMapping):
        return reject(REJECTION_INVALID_OVERLAY)

    # Validate task_work_ms before mutation
    if not _is_strict_positive_finite(task_work_ms):
        return reject(REJECTION_INVALID_TASK_WORK)

    # Validate state_age_ms
    if not valid_age:
        return reject(REJECTION_INVALID_STATE_AGE)

    # Validate counter-key fields strictly
    if not (valid_es and valid_fs and valid_ot and valid_ts and valid_ord):
        return reject(REJECTION_INVALID_KEY)

    # Validate declared_workloads is Mapping (no iteration yet)
    if not isinstance(declared_workloads, Mapping):
        return reject(REJECTION_INVALID_WORKLOAD)

    # Candidates validation already done; handle its rejection
    if cand_rejection is not None:
        return reject(cand_rejection)

    # At this point sorted_unique and feasible_count are not None
    assert sorted_unique is not None
    assert feasible_count is not None

    if feasible_count == 0:
        return P2CReceipt(
            feasible_count=0,
            sampled_pair=None,
            inspection_count=0,
            chosen_rsu=None,
            reserved_work_ms=None,
            evaluator_seed=sanitized_es,
            fleet_seed=sanitized_fs,
            outer_tick=sanitized_ot,
            task_slot=sanitized_ts,
            sequential_task_ordinal=sanitized_ord,
            state_age_ms=sanitized_age,
            rejection_reason=REJECTION_NO_FEASIBLE,
        )

    # Single candidate -> select it, validate only that candidate.
    if feasible_count == 1:
        chosen = int(sorted_unique[0])
        if chosen not in declared_workloads:
            return _make_rejection(
                REJECTION_INVALID_WORKLOAD,
                feasible_count=feasible_count,
                sampled_pair=None,
                inspection_count=1,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        raw_w = declared_workloads[chosen]
        if not _is_strict_workload_value(raw_w):
            return _make_rejection(
                REJECTION_INVALID_WORKLOAD,
                feasible_count=feasible_count,
                sampled_pair=None,
                inspection_count=1,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        # Capture overlay once; treat access failures as invalid overlay.
        # Deliberate suppression via helper (no BLE001 try/except here).
        _ok_single, captured_had_key_single = _overlay_contains(
            reservation_overlay, chosen
        )
        if not _ok_single:
            return _make_rejection(
                REJECTION_INVALID_OVERLAY,
                feasible_count=feasible_count,
                sampled_pair=None,
                inspection_count=1,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        captured_prior_single: float | None = None
        if captured_had_key_single:
            _ok_get_single, raw_o = _overlay_get(reservation_overlay, chosen)
            if not _ok_get_single:
                return _make_rejection(
                    REJECTION_INVALID_OVERLAY,
                    feasible_count=feasible_count,
                    sampled_pair=None,
                    inspection_count=1,
                    evaluator_seed=sanitized_es,
                    fleet_seed=sanitized_fs,
                    outer_tick=sanitized_ot,
                    task_slot=sanitized_ts,
                    sequential_task_ordinal=sanitized_ord,
                    state_age_ms=sanitized_age,
                )
            if not _is_strict_workload_value(raw_o):
                return _make_rejection(
                    REJECTION_INVALID_OVERLAY,
                    feasible_count=feasible_count,
                    sampled_pair=None,
                    inspection_count=1,
                    evaluator_seed=sanitized_es,
                    fleet_seed=sanitized_fs,
                    outer_tick=sanitized_ot,
                    task_slot=sanitized_ts,
                    sequential_task_ordinal=sanitized_ord,
                    state_age_ms=sanitized_age,
                )
            captured_prior_single = float(raw_o)
        # Immediate reservation with transactional rollback using captured state
        err = _try_reserve(
            reservation_overlay,
            chosen,
            float(task_work_ms),
            captured_had_key_single,
            captured_prior_single,
        )
        if err is not None:
            return _make_rejection(
                err,
                feasible_count=feasible_count,
                sampled_pair=None,
                inspection_count=1,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        return P2CReceipt(
            feasible_count=feasible_count,
            sampled_pair=None,
            inspection_count=1,
            chosen_rsu=chosen,
            reserved_work_ms=float(task_work_ms),
            evaluator_seed=sanitized_es,
            fleet_seed=sanitized_fs,
            outer_tick=sanitized_ot,
            task_slot=sanitized_ts,
            sequential_task_ordinal=sanitized_ord,
            state_age_ms=sanitized_age,
            rejection_reason=None,
        )

    # >=2 -> deterministic pair sampling without replacement
    # Use sanitized keys (they are valid ints)
    assert sanitized_es is not None
    assert sanitized_fs is not None
    assert sanitized_ot is not None
    assert sanitized_ts is not None
    assert sanitized_ord is not None
    pair = _deterministic_pair(
        sorted_unique,
        sanitized_es,
        sanitized_fs,
        sanitized_ot,
        sanitized_ts,
        sanitized_ord,
    )
    a, b = pair

    # Capture validated declared workloads once (TOCTOU fix): validated numeric
    # values are reused for selection, never re-read from the mapping.
    captured_declared: dict[int, float] = {}
    for rsu in (a, b):
        if rsu not in declared_workloads:
            return _make_rejection(
                REJECTION_INVALID_WORKLOAD,
                feasible_count=feasible_count,
                sampled_pair=pair,
                inspection_count=2,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        raw_w = declared_workloads[rsu]
        if not _is_strict_workload_value(raw_w):
            return _make_rejection(
                REJECTION_INVALID_WORKLOAD,
                feasible_count=feasible_count,
                sampled_pair=pair,
                inspection_count=2,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        captured_declared[rsu] = float(raw_w)

    # Capture overlay once per pair member; access failures -> invalid.
    # Deliberate suppression via helper (no BLE001).
    _ok_a, had_a = _overlay_contains(reservation_overlay, a)
    if not _ok_a:
        return _make_rejection(
            REJECTION_INVALID_OVERLAY,
            feasible_count=feasible_count,
            sampled_pair=pair,
            inspection_count=2,
            evaluator_seed=sanitized_es,
            fleet_seed=sanitized_fs,
            outer_tick=sanitized_ot,
            task_slot=sanitized_ts,
            sequential_task_ordinal=sanitized_ord,
            state_age_ms=sanitized_age,
        )
    captured_prior_a: float | None = None
    eff_a_overlay = 0.0
    if had_a:
        _ok_get_a, raw_a = _overlay_get(reservation_overlay, a)
        if not _ok_get_a:
            return _make_rejection(
                REJECTION_INVALID_OVERLAY,
                feasible_count=feasible_count,
                sampled_pair=pair,
                inspection_count=2,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        if not _is_strict_workload_value(raw_a):
            return _make_rejection(
                REJECTION_INVALID_OVERLAY,
                feasible_count=feasible_count,
                sampled_pair=pair,
                inspection_count=2,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        captured_prior_a = float(raw_a)
        eff_a_overlay = float(captured_prior_a)
    _ok_b, had_b = _overlay_contains(reservation_overlay, b)
    if not _ok_b:
        return _make_rejection(
            REJECTION_INVALID_OVERLAY,
            feasible_count=feasible_count,
            sampled_pair=pair,
            inspection_count=2,
            evaluator_seed=sanitized_es,
            fleet_seed=sanitized_fs,
            outer_tick=sanitized_ot,
            task_slot=sanitized_ts,
            sequential_task_ordinal=sanitized_ord,
            state_age_ms=sanitized_age,
        )
    captured_prior_b: float | None = None
    eff_b_overlay = 0.0
    if had_b:
        _ok_get_b, raw_b = _overlay_get(reservation_overlay, b)
        if not _ok_get_b:
            return _make_rejection(
                REJECTION_INVALID_OVERLAY,
                feasible_count=feasible_count,
                sampled_pair=pair,
                inspection_count=2,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        if not _is_strict_workload_value(raw_b):
            return _make_rejection(
                REJECTION_INVALID_OVERLAY,
                feasible_count=feasible_count,
                sampled_pair=pair,
                inspection_count=2,
                evaluator_seed=sanitized_es,
                fleet_seed=sanitized_fs,
                outer_tick=sanitized_ot,
                task_slot=sanitized_ts,
                sequential_task_ordinal=sanitized_ord,
                state_age_ms=sanitized_age,
            )
        captured_prior_b = float(raw_b)
        eff_b_overlay = float(captured_prior_b)

    eff_a = captured_declared[a] + eff_a_overlay
    eff_b = captured_declared[b] + eff_b_overlay
    if not (math.isfinite(eff_a) and math.isfinite(eff_b)):
        return _make_rejection(
            REJECTION_INVALID_WORKLOAD,
            feasible_count=feasible_count,
            sampled_pair=pair,
            inspection_count=2,
            evaluator_seed=sanitized_es,
            fleet_seed=sanitized_fs,
            outer_tick=sanitized_ot,
            task_slot=sanitized_ts,
            sequential_task_ordinal=sanitized_ord,
            state_age_ms=sanitized_age,
        )
    if eff_a < eff_b:
        chosen = a
    elif eff_b < eff_a:
        chosen = b
    else:
        chosen = min(a, b)

    # Pass captured chosen state; new reserved from captured inputs only.
    if chosen == a:
        captured_had_key_pair = had_a
        captured_prior_pair = captured_prior_a
    else:
        captured_had_key_pair = had_b
        captured_prior_pair = captured_prior_b
    err = _try_reserve(
        reservation_overlay,
        chosen,
        float(task_work_ms),
        captured_had_key_pair,
        captured_prior_pair,
    )
    if err is not None:
        return _make_rejection(
            err,
            feasible_count=feasible_count,
            sampled_pair=pair,
            inspection_count=2,
            evaluator_seed=sanitized_es,
            fleet_seed=sanitized_fs,
            outer_tick=sanitized_ot,
            task_slot=sanitized_ts,
            sequential_task_ordinal=sanitized_ord,
            state_age_ms=sanitized_age,
        )

    return P2CReceipt(
        feasible_count=feasible_count,
        sampled_pair=pair,
        inspection_count=2,
        chosen_rsu=chosen,
        reserved_work_ms=float(task_work_ms),
        evaluator_seed=sanitized_es,
        fleet_seed=sanitized_fs,
        outer_tick=sanitized_ot,
        task_slot=sanitized_ts,
        sequential_task_ordinal=sanitized_ord,
        state_age_ms=sanitized_age,
        rejection_reason=None,
    )


# ---------------------------------------------------------------------------
# Sequential tracker (explicit reservation overlay owner)
# ---------------------------------------------------------------------------


class SequentialP2CTracker:
    """Owner of an explicit reservation overlay for sequential P2C calls."""

    def __init__(
        self,
        evaluator_seed: int,
        fleet_seed: int,
    ) -> None:
        if type(evaluator_seed) is bool or type(evaluator_seed) is not int:
            raise ValueError(
                "evaluator_seed must be strict nonnegative int in [0, 2^64-1]"
            )
        if int(evaluator_seed) < 0 or int(evaluator_seed) > MASK64:
            raise ValueError(
                "evaluator_seed must be strict nonnegative int in [0, 2^64-1]"
            )
        if type(fleet_seed) is bool or type(fleet_seed) is not int:
            raise ValueError("fleet_seed must be strict nonnegative int in [0, 2^64-1]")
        if int(fleet_seed) < 0 or int(fleet_seed) > MASK64:
            raise ValueError("fleet_seed must be strict nonnegative int in [0, 2^64-1]")
        self.evaluator_seed: int = evaluator_seed
        self.fleet_seed: int = fleet_seed
        self.reservation_overlay: dict[int, float] = {}

    def select(
        self,
        feasible_candidates: Sequence[int],
        declared_workloads: Mapping[int, float],
        state_age_ms: int,
        outer_tick: int,
        task_slot: int,
        sequential_task_ordinal: int,
        task_work_ms: float,
    ) -> P2CReceipt:
        return p2c_select(
            feasible_candidates=feasible_candidates,
            declared_workloads=declared_workloads,
            reservation_overlay=self.reservation_overlay,
            state_age_ms=state_age_ms,
            evaluator_seed=self.evaluator_seed,
            fleet_seed=self.fleet_seed,
            outer_tick=outer_tick,
            task_slot=task_slot,
            sequential_task_ordinal=sequential_task_ordinal,
            task_work_ms=task_work_ms,
        )

    def reset(self) -> None:
        """Clear reservation overlay (e.g., at next outer_tick)."""
        self.reservation_overlay.clear()


__all__ = [
    "REJECTION_INVALID_KEY",
    "REJECTION_INVALID_OVERLAY",
    "REJECTION_INVALID_STATE_AGE",
    "REJECTION_INVALID_TASK_WORK",
    "REJECTION_INVALID_WORKLOAD",
    "REJECTION_NO_FEASIBLE",
    "P2CInvariantError",
    "P2CReceipt",
    "SequentialP2CTracker",
    "p2c_select",
]
