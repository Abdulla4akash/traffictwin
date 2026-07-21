# ADR-022 — Temporal Evidence and R6 Semantics

Status: accepted and implemented
Date: 20 July 2026
Capability: `DIA-01`

## Context

`MET-01` provides deterministic fixed-window metric collections, but an ordinary `EvidencePack`
contains only a whole-run collection. R6 must identify sustained within-run deterioration and
describe post-event recovery without reading raw rows, treating absent intervals as zero, or
silently selecting event boundaries. The diagnostic boundary remains `EvidencePack`.

The v0.5 design does not provide calibrated universal temporal thresholds. Metric direction,
window coverage, baseline choice, event alignment, sustained duration, and recovery horizon must
therefore be explicit and versioned. Results are diagnostic candidates, not causal incident
attribution or proof of drift.

## Decision

TrafficTwin adds a typed `TemporalEvidence` section that can be attached to an ordinary
`EvidencePack`. It is built only from one existing `WindowedMetricSeries` and one
`TemporalEvidenceConfig`; R6 receives the resulting pack and cannot access canonical or raw data.

The evidence contract records:

- the selected scalar, window-applicable metric, unit, implementation version, and objective
  direction from its validated metric definition;
- the complete ordered fixed-window grid, including excluded, low-coverage, unavailable, partial,
  invalid, and non-numeric observations;
- the minimum admitted requested-range coverage;
- the window configuration, boundary, anchor-policy version, series fingerprint, and raw bundle
  fingerprint;
- an optional researcher-declared event time and label, resolved with the existing half-open
  containing-window rule; and
- explicit status/reason codes when the series, direction, metric, event, run, fingerprint, or
  eligible observations are unusable.

An event is context, not a causal label. TrafficTwin does not infer an event from a metric change
or from incident counts. An event exactly at a window end belongs to the later window. It must fall
inside the effective requested interval. Without a declared event, R6 can evaluate general
within-run deterioration but reports recovery as not applicable.

R6 v1.0 uses a versioned `R6Config`:

- `baseline_window_count`: exact consecutive leading windows, or exact consecutive windows
  immediately before the event window;
- `minimum_evaluable_windows`: minimum eligible observations across the temporal artifact;
- `minimum_deterioration_delta`: adverse absolute change in the metric's declared unit from the
  arithmetic baseline mean;
- `sustained_window_count`: consecutive eligible windows that must meet the adverse-change
  threshold;
- `recovery_tolerance`: maximum adverse absolute change from baseline treated as returned to the
  baseline band; and
- `recovery_horizon_windows`: declared total number of grid positions considered by the rule,
  beginning with the event-containing window.

For a lower-is-better metric, adverse change is `window - baseline`; for a higher-is-better metric,
it is `baseline - window`. Metrics without a declared objective direction are unavailable for R6.
The defaults target a bounded rate-like synthetic development case and are explicitly provisional,
not externally calibrated defaults.

Missing, excluded, low-coverage, partial, invalid, and non-numeric windows are never assigned a
value and break consecutive runs. Required baseline gaps make R6 insufficient. If a sustained
episode is observed, R6 can trigger despite other visible gaps, with reduced confidence. If no
episode is observed and the observation region contains gaps, R6 is insufficient rather than
not-triggered. This prevents missing intervals from masquerading as either deterioration or
stability.

For a declared event, recovery is assessed only after an observed sustained episode and within the
declared horizon. It is classified as recovered, recovered after an evidence gap, not recovered
within the horizon, indeterminate because of gaps, or not assessed. The result reports exact
baseline, episode, recovery, missing, and horizon ordinals. A degradation trigger remains a
candidate even if later recovery is observed.

## Consequences

- R6 is deterministic for equal EvidencePack, configuration, and clock inputs.
- Ordinary EvidencePacks remain schema-compatible; R6 returns `insufficient_evidence` when their
  optional temporal section is absent.
- Window gaps remain visible and cannot support a trigger.
- Thresholds are expressed in the selected metric's unit, so changing the metric requires an
  explicit compatible rule configuration.
- The temporal and diagnostic fingerprints link R6 to the complete window artifact. Existing
  per-window provenance and contribution commands provide accepted-row lineage for reported
  ordinals; this is not causal attribution.
- Event-aligned metric recomputation, automatic change-point detection, statistical trend tests,
  seasonality modelling, and inferred incidents are outside R6 v1.0.

## Rejected Alternatives

- **Read window JSON directly inside R6:** violates the EvidencePack boundary.
- **Skip unavailable windows and join the remaining values:** hides temporal gaps and can create a
  false consecutive episode.
- **Treat empty windows as zero:** violates the unavailable-is-not-zero rule.
- **Infer event time from the largest metric change:** fabricates context and encourages causal
  interpretation.
- **Use percentage change for every metric:** is undefined or unstable at a zero baseline and is
  not meaningful for every unit.
- **Fit an uncalibrated regression/change-point model:** adds method assumptions not approved for
  this capability.

## Acceptance Evidence

- Unit tests cover direction, exact baselines, sustained episodes, gaps, coverage, event boundary
  alignment, recovery states, insufficiency, invalid compatibility, and determinism.
- Integration and golden tests pin the temporal CLI artifact and an R6 report projection.
- UI service and Streamlit tests verify that the Temporal Metrics page delegates construction and
  evaluation to typed library code.
- Generated schemas, rule catalogue, capability manifests, documentation, and repository quality
  gates are reconciled in the same increment.
