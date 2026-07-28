# Five-Regime Completion + Deep-Squeeze Onset — Results (28 July 2026)

**Status: exploratory `owner_approved_candidate` evidence from the predeclared design
([predeclaration](capacity_sweep_completion_predeclaration.md), digest `a2cb0e3d…`);
descriptive, non-causal. Predictions were recorded before any cell ran.**

- Execution: three campaigns, 12/12 cells each, zero failures — `wd-am` (fp `2844fde2…`),
  `wd-pm` (fp `635a2cbe…`), `ev-deep` (fp `72774544…`); seeds {50, 51, 52}; registry
  `.demo/registry-capacity-grid.sqlite`; analyses under `data/vec-fresh/` (local).

## Legs 1–2: the five-regime sweep is complete and unanimous

Both weekday peaks behave exactly like the weekend and event night: **every metric
exactly identical across all four standard capacity arms in every seed** (paired
differences literally 0.000000). With the pilot's collapse-hour leg, the sweep now reads:
capacity is completely inert in ALL FOUR normal regimes (139/163/175/215 slots) and
outcome-active only in the 2,488-slot collapse hour. Both predeclared predictions held.

## Leg 3: the binding onset, located

Extending the squeeze on the event-night regime (175 slots): **cap-0.5 and cap-0.25 are
still exactly identical to baseline** — inert at a 10× squeeze — but **cap-0.1 (25×)
finally binds**: deadline success +0.000011 [0.000001, 0.000018] (each seed faintly UP),
mean latency down ~0.02 ms (51.205 → 51.181). The first non-identical outcomes ever
measured in a normal regime, and in the same direction as the collapse hour's pattern
(deadlines flat-to-up, latency down) — a miniature of the confirmed finding, consistent
with the queue-truncation reading. Decisions remain invariant throughout (the policy is
blind at every level, as the mechanism requires).

## Interpretation (descriptive)

The capacity control's outcome-relevance is governed by load saturation: on this
district's traces it requires either extreme vehicle density (collapse hour) or an
extreme squeeze (≤0.1 per-slot on a normal night — onset between 0.25 and 0.1). The
per-padded-vehicle semantics and single-actor/single-district scope bind as always.

## Artifacts

Launcher `scripts/capacity_grid_campaign.py {wd-am,wd-pm,ev-deep}`; grid context:
[three-trace results](capacity_grid_results_20260728.md); mechanism:
[observability gap](../integration/evidence/vec_pilot_observability_gap_20260728.json).
