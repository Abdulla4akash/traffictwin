# TOS/VEC Source Contract v2 — Observed Schemas and Fixtures

Status: implemented and accepted VEC-02 contract grounded in the **accepted** Gate A audit
([randy-source-snapshot-audit-v0_6.md](randy-source-snapshot-audit-v0_6.md) and its machine record
`docs/reference/generated/vec_source_snapshot_audit.json`). Exact code, synthetic golden/negative
fixtures, ADR-049, public exports, and generated references are complete. The smallest reviewed
permission-manifested real sanitised fixture and aggregate pack now closes Gate B through VEC-11.
This layer itself flips no launch, join, metric, or UI capability.

Module: `src/traffictwin/integration/tos/contract_v2.py`
Fixtures: `tests/tos_v2_helpers.py` (synthetic golden package, T=6, maxN=3, n_rsu=2)
Tests: `tests/unit/test_tos_contract_v2.py`

## Observed contract

`tos_source_contract_v2()` returns a strict, frozen, fingerprinted contract pinning:

- the audited commits (`vec_env 068b4ea…`, `tos-data f6c67ac…`) and the five audited
  producer/evaluator source files with their exact sizes and SHA-256 digests;
- the observed array schemas: the 11-key trace NPZ, the exact 18-key per-step NPZ, the exact
  four-key per-task NPZ (`task_active`, `task_lat_ms`, `task_met`, `task_type` shaped
  `(T, 5, maxN)`), and the `sumo_vehicle_id,slot,t_enter,t_exit` occupancy CSV with **inclusive**
  integer bounds;
- audited semantics: deadline success is never eventual physical completion; targets are eligible
  decision-time values where `-1` means no eligible target and a selected action is never
  transfer proof; `slot_tier`/`slot_is_ev` are fixed per-slot operational assignments; trace time
  grids are contiguous one-second steps with `dt == 1.0`.

Every serialized contract entry now enumerates all keys with the audited exact dtype and shape
family. Dependent validators fail closed when the supplied trace has not passed first.

The contract must declare `per_task_energy_j`, `eventual_physical_completion`, and
`transfer_confirmation` as unavailable (validation fails if any is dropped), and its capability
flags can only be `False` at the library level.

## Validators and typed rows

- `validate_trace_arrays`, `validate_perstep_arrays`, `validate_pertask_arrays` check exact key
  sets, shapes, dtype kinds, value/target/tier ranges, self-V2V exclusion, the one-second time
  grid, active-versus-mask totals, internal task/action/completion reconciliation, and (when a
  run summary is supplied) the audit's aggregate reconciliation with its declared latency
  tolerance. An energy- or completion-named extra key produces an explicit refusal finding that
  cites the audit blocker.
- `parse_occupancy_rows` + `reconcile_occupancy_spans` enforce the exact header, inclusive span
  bounds, duplicate/slot/vehicle overlap rules (spans sharing a boundary second conflict), trace
  range bounds, and the inclusive-visit-seconds-equals-mask-count reconciliation. The VEC-03
  identity join is out of scope.
- Typed rows (`OccupancySpan`, `VecVehicleAttributeObservation`, `VecTaskActionObservation`,
  `VecTripJoin`) encode the audited semantics in the type system: `eventual_completion` can only
  be `"unavailable"`, `transfer_confirmed` can only be `False`, `protected_attribute` can only be
  `False`, an eligible V2V peer is never the source slot, and excluded trips (including
  right-censored boundary vehicles) carry a reason and never filled completion values.

All reports and models are deterministic (sorted findings/collections, canonical JSON, SHA-256
fingerprints) and reject extra fields.

## Fixtures

`tests/tos_v2_helpers.py` writes a complete synthetic golden package (trace, per-step, per-task,
run JSON, occupancy CSV, gzip tripinfo) whose aggregates reconcile exactly, plus the tests derive
negative fixtures by mutation for every failure mode: missing/extra/renamed keys, energy and
eventual-completion key refusal, dtype/shape/range/target/tier violations, self-V2V targets,
time-grid gaps, mask mismatches, internal count inconsistencies, run-summary mismatches,
occupancy header/bounds/overlap/duplicate/range violations, and no-fill trip-join rules.

## Boundaries

- External repositories are never read by this layer; all evidence values come from the accepted
  audit record, and all fixture data is synthetic.
- VEC-03–VEC-10 joins, preprocessing, launching, and metrics are untouched.
- No CLI/UI capability is enabled; those interfaces belong to VEC-10.
- Generated and shared project records expose the contract and bind it to the accepted VEC-11
  real sanitised fixture without expanding its semantics.

## Related documents

- [TrafficTwin v0.6 design](../traffictwin-design-v0_6.md) (§7–§9, Gate B)
- [VEC-01 snapshot audit](randy-source-snapshot-audit-v0_6.md)
- [Generated VEC-02 contract](../reference/generated/tos_source_contract_v2.json)
- [ADR-049 audited VEC semantics](../decisions/ADR-049-audited-vec-contract-and-join-semantics.md)
- [TOS data adapter](tos_data_adapter.md) (implemented v0.5 contract v1)
- [Randy publication policy](randy_publication_policy.md) and
  [accepted VEC-11 pack](vec_dissertation_pack.md)
