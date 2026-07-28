# Baseline-Actor Invariance Prediction Test (B0) — Exploratory Predeclaration

**Status: exploratory predeclaration under the standing in-session owner delegation
("run some more tasks", 28 July 2026). Approval recorded as relayed delegation, never an
owner-typed signature. Label ceiling `owner_approved_candidate`; every outcome is
publishable with equal prominence.**

- Predeclared: 28 July 2026, before any cell executed
- **The falsifiable prediction under test** (recorded 28 July in
  [the observability-gap evidence](../integration/evidence/vec_pilot_observability_gap_20260728.json)):
  because both audited actors share the same observation design, the **baseline actor**
  (`baseline_model_c_17`) should be exactly as capacity-invariant as the ukfleettrain
  actor. If its decisions or outcomes vary across capacity arms, the mechanism claim is
  localised to the ukfleettrain training run and must be revised.

## Design

| Factor | Value |
|---|---|
| Actor | `baseline_model_c_17` (the second pinned actor) |
| Trace | `ev` (`70d6d12f…`, 23,400 steps) — chosen for cost (265.9 s/run measured) |
| Arms | cap-2.5 (baseline), cap-1.5, cap-1.0, cap-0.75 |
| Fleet seeds | **{50, 51, 52}** — deliberately the same seeds as the grid's ev leg, so the two actors face identical fleets and a descriptive actor contrast comes free; the crossover draft's reserved seeds {20–24} are untouched |
| Everything else | grid design unchanged: uk2030 fleet, evaluator seed 0, 12 cells, seed-major, halt-on-failure, ≤3 GB, 7,200 s ceiling |
| Primary endpoint | `tos.task.deadline_success.rate`; latency and offload alongside; all exploratory |
| Verdict rule (fixed now) | the prediction HOLDS iff per-seed offload rates and latency are invariant across arms exactly as in the grid's ev leg; any cross-arm variation is a published localisation finding |

## Boundaries

This is not the crossover study (which compares winners on `inc` with seeds {20–24} under
its own signable draft); no ranking or winner claim is made here; no pooling with any
other study; held-out seeds untouched; campaign approval binds this document's committed
SHA-256.

**Sign-off (relayed delegation, recorded by the agent — not an owner-typed signature):**
defaults above resolved under the standing delegation; the owner may halt at any time.
