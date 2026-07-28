# Three-Trace Capacity Grid — Exploratory Results (28 July 2026)

**Status: exploratory `owner_approved_candidate` evidence from the predeclared A1 grid
([predeclaration](capacity_grid_predeclaration.md), digest `93384588…`); descriptive,
non-causal, no significance claims. The predeclaration recorded the mechanism's
predictions before any cell executed; this record reports them tested.**

- Execution: two campaigns, 12/12 cells each, zero failures — `we` (design fp
  `b4da3a5b…`, ~1.0 h) and `ev` (design fp `efa83a78…`, 0.78 h) — fresh seeds
  {50, 51, 52}, arms {2.5, 1.5, 1.0, 0.75}, all cells admitted through fresh-run
  admission; registry `.demo/registry-capacity-grid.sqlite`; analyses at
  `data/vec-fresh/capacity-grid-{we,ev}/campaign_analysis.{json,md}`.
- The `inc` leg of the grid is the completed pilot (12 cells, seeds {0–2}) and the
  held-out confirmatory (10 cells, seeds {10–14}); nothing is pooled across studies.

## Result: on both non-incident traces, capacity is completely inert

On the weekend trace AND the event-night trace, **every metric is exactly identical
across all four capacity arms in every seed** — paired differences are literally
0.000000 with [0, 0] bootstrap intervals:

| Trace | Deadline success (mean over seeds) | Mean latency | Offload rate | Any metric differs across arms? |
|---|---|---|---|---|
| `we` weekend | 0.931624 | 52.0 ms | 0.399934 | **No — all arms identical** |
| `ev` event night | 0.934865 | 51.2 ms | 0.386845 | **No — all arms identical** |
| `inc` collapse hour (pilot/confirmatory context) | ~0.79 flat across arms | 9,799 → 3,084 ms (pilot); 12,027 → 3,717 ms (held-out) | identical across arms within seed | **Latency only** |

## Predictions verdict (recorded in advance in the predeclaration)

- (i) **Per-seed decision invariance across arms — HELD on both traces** (trivially: the
  entire outcome vector is identical, which subsumes decision invariance).
- (ii) **Within-seed latency non-increasing under squeeze — HELD** (as exact equality).
- (iii) **Deadline success flat — HELD** (exact equality).

## Interpretation (descriptive, confidence-labelled)

The three regimes now separate two different facts that the pilot alone could not:

1. **The policy is capacity-blind everywhere** — structural, by observation design
   (established separately from the pilot artifacts; the grid is consistent with it).
2. **Capacity only affects *outcomes* where load saturates the concurrency bound.** The
   collapse hour carries up to 2,488 concurrent vehicle slots and shows a 3.2× latency
   swing under squeeze; the weekend (139 slots) and the event night (175 slots) never
   drive RSU load into the bound at any tested level, so the knob is inert end to end.
   Vehicle density — not event status — is the moderator: notably, the Champions-League
   night behaves like the quiet Sunday at the VEC layer (~93.5% deadlines, ~51 ms mean
   latency), while the *incident* hour is a different world (~79%, seconds-scale). The
   "saturation threshold between 175 and 2,488 slots" is bracketed, not located; locating
   it would need intermediate-density scenarios and is future work.

## Limitations (binding)

One actor, one fleet preset, three admitted traces of one district, three seeds per
trace, four capacity levels; exact-equality results depend on the evaluator's
deterministic replay semantics; per-padded-vehicle capacity semantics; deadline success ≠
physical completion; exploratory forever — never pooled into any confirmatory estimate.

## Artifacts

Launcher `scripts/capacity_grid_campaign.py`; predeclaration + digest above; per-leg
analyses and receipts under `data/vec-fresh/capacity-grid-{we,ev}/` (local); the ev
per-run cost basis is the committed timing probe (265.9 s,
[evidence](../integration/evidence/vec_ev_timing_probe_20260728.json)).
