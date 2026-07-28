# Three-Trace Capacity Grid — Exploratory Predeclaration (A1)

**Status: exploratory predeclaration under the standing in-session owner delegation
("take reasonable choices and keep working"; reaffirmed 28 July 2026, "I want to do some
experimenting now"). Approval is recorded as relayed delegation, never an owner-typed
signature. Label ceiling `owner_approved_candidate`; results are exploratory and
descriptive; every outcome below is publishable with equal prominence.**

- Predeclared: 28 July 2026, before any grid cell executed
- Question: **is the capacity-invariance / latency-collapse pattern a property of the
  collapse-hour traffic regime, or of the policy across regimes?** The pilot measured it
  on `inc` only; this grid runs the identical design on the other two admitted traces.
- Mechanism prediction (recorded in advance, falsifiable): the located observability gap
  ([evidence](../integration/evidence/vec_pilot_observability_gap_20260728.json)) predicts
  on BOTH traces: (i) per-seed offload decisions invariant across capacity arms,
  (ii) within-seed mean latency non-increasing as capacity tightens, (iii) deadline
  success flat. Any deviation from (i)–(iii) is a finding of equal standing and would
  localise the mechanism claim.

## Design (mirrors the pilot exactly, per trace)

| Factor | Value |
|---|---|
| Traces | `we` (`a2612865…`, 32,400 steps) and `ev` (`70d6d12f…`, 23,400 steps); `inc` is covered by the completed pilot and is never re-run or pooled — cross-trace comparison is descriptive across studies |
| Actor / fleet / evaluator seed | `ukfleettrain_mappo_model_c_17` / `uk2030` / `0` — unchanged |
| Arms | cap-2.5 (baseline), cap-1.5, cap-1.0, cap-0.75 |
| Fleet seeds | **{50, 51, 52}** — fresh, disjoint from {0–2}, {10–14}, {20–24}, {30–34}, {40–44} |
| Primary endpoint | `tos.task.deadline_success.rate` (pilot symmetry); `task.latency.mean_ms` and `task.offload.rate` reported alongside; all exploratory |
| Execution | two approval-gated campaigns (one per trace), 12 cells each, seed-major, halt-on-failure, ≤3 GB output each, 7,200 s request ceiling (escalation trigger, never raised) |
| Cost basis | `we` full run measured 225.7 s → ~50 min campaign; `ev` per-cell cost from the timing probe (`scripts/ev_timing_probe.py`, evidence committed) before launch |
| Analysis | the exploratory campaign analysis harness per trace (STA-01 defaults, type-level `confirmatory: False`); descriptive cross-trace table afterwards |

## Boundaries

Held-out seeds are not touched (`held_out_authorised = False`; {10–14} are spent and
never reused). No metric is promoted; no significance claim; no pooling across traces or
with pilot/confirmatory estimates; deadline success ≠ physical completion;
per-padded-vehicle capacity semantics; one actor, one district. Campaign approvals bind
this document's committed SHA-256; editing it afterwards refuses execution.

**Sign-off (relayed delegation, recorded by the agent — not an owner-typed signature):**
decisions resolved to the defaults above under the standing delegation of 27–28 July
2026; the owner may halt or void either campaign at any time.
