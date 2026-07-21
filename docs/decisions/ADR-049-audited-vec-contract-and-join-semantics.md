# ADR-049: Audited VEC Contract and Join Semantics

- Status: accepted
- Date: 2026-07-21
- Capability: `VEC-02` contract foundation for `VEC-03`–`VEC-05`

## Context

The accepted VEC-01 audit establishes exact trace, per-step, per-task, occupancy, and tripinfo
evidence. Several source names are easy to over-interpret: `completion`, `done`, and `task_met`
measure deadline success; action values do not prove that a transfer occurred; vehicle slots are
reused; and tripinfo coverage is incomplete outside explicitly matched cohorts.

The contract must preserve the observed evidence without turning source labels into stronger
canonical or causal claims.

## Decision

1. Publish exact audited commits, source-script hashes, keys, dtypes, shapes, units, and semantic
   blockers in the VEC-02 machine contract.
2. Treat occupancy `t_enter` and `t_exit` as inclusive integer time indices. A vehicle identity is
   valid only for its admitted span. A slot is never a persistent vehicle identifier.
3. Treat `slot_tier` and `slot_is_ev` as fixed per-slot operational assignments for one run.
   Recycled occupants inherit those assignments; neither is a protected or demographic attribute.
4. Map `task_type` codes only as `0=T1`, `1=T2`, and `2=T3` after exact schema validation.
5. Name `task_met`, per-step `done`, and aggregate `completion` as deadline success. Eventual
   physical completion remains explicitly unavailable.
6. Preserve `veh_action` as the policy decision. Preserve `veh_best_rsu` and `veh_best_v2v` as
   eligible decision-time targets, including `-1` for no eligible target. A selected action is not
   transfer confirmation.
7. Admit a trip only through exact `sumo_vehicle_id` matching and a declared eligibility state.
   Right-censored, missing-before-boundary, and unmatched vehicles keep explicit exclusions; no
   arrival, duration, distance, cause, or zero value is invented.
8. Keep per-task energy unavailable. Source aggregate joules per arrival cannot be distributed
   across tasks or relabelled as completed-task energy.
9. Return deterministic typed findings for every mismatch. Dependent validators fail closed when
   their trace artifact has not first passed the exact contract.

## Consequences

- VEC-03 can build identity only inside reconciled inclusive spans.
- VEC-04 can expose action and eligible-target evidence without claiming transfers or failures.
- VEC-05 can compute journey metrics only for an explicitly eligible complete cohort.
- Canonical metrics and rules remain unavailable until their own contracts and coverage gates pass.
- New source fields require a new audited contract version rather than permissive extra-key loading.

## Acceptance Evidence

- `docs/integration/randy-source-snapshot-audit-v0_6.md`
- `docs/reference/generated/vec_source_snapshot_audit.json`
- `src/traffictwin/integration/tos/contract_v2.py`
- `tests/tos_v2_helpers.py`
- `tests/unit/test_tos_contract_v2.py`

VEC-02 is now complete: the accepted VEC-11 permission-manifested three-row/aggregate pack closes
its real-sanitised-fixture gate. This ADR accepts the observed semantic boundary; VEC-11 does not
broaden it.

## Rejected Alternatives

- Treat occupancy as half-open: rejected because every audited table uses inclusive bounds and
  exactly reconstructs the trace mask with `t_exit - t_enter + 1` seconds.
- Treat action as completed offload: rejected because audited V2I/V2V action rows can have target
  `-1`.
- Treat deadline success as eventual completion: rejected because no such field exists.
- Fill unmatched trip rows: rejected because missingness and boundary censoring are evidence.
- Derive per-task energy from a run aggregate: rejected because no compatible allocation or
  denominator contract exists.
