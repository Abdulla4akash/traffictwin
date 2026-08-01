# Design — VEC outcome predictor (platform P-1, tier 1)

**Status: PROPOSED design, `owner_approved_candidate` ceiling. The surrogate model the
owner directed (30 July): fit on the project's own admitted cells, predict instantly,
refuse outside the measured envelope. Every output is typed `prediction` and is NEVER
evidence — binding, type-level.**

## 1. Scenario coordinates and outputs

Input: `(trace, capacity, actor)` with `trace ∈ {we, ev, wd_am, wd_pm, inc}`,
`capacity ∈ [0.1, 2.5]`, `actor ∈ {ukfleettrain_mappo_model_c_17, baseline_model_c_17}`;
fleet preset fixed `uk2030` (the only measured one). Output: a `PredictionRecord` —
point + interval per metric (deadline attainment, mean latency, p50 latency, tail
ceiling, offload rate), `evidence: False`, `confirmatory: False`, the fit digest, and
the regime the prediction came from. Anything else in, a typed refusal out.

## 2. Model structure — the measured laws, packaged (three regimes)

1. **Off-saturation** (`we`/`ev`/`wd_am`/`wd_pm` above their measured onsets): return
   the measured cap-2.5 descriptives for that trace/actor. Capacity uncertainty ~0
   because the paired differences were measured *exactly zero*; the record says
   `regime: "measured_inert"` — an honest lookup that declares itself one.
2. **Near onset** (at/below the measured per-trace onsets 0.25/0.25/0.1/0.1): the faint
   measured signature (completion +0.001–0.004 pp, latency −0.02–0.2 ms) as corrections,
   with the onset-scaling REFUTED verdict cited — onsets are per-trace lookups, never
   interpolated across traces.
3. **Saturated (`inc`)**: ceiling `p95-of-missed = K × c`, `K = 39,959 ms`; mean latency
   linear per actor (slopes 3,828.2 / 6,555.4 ms per capacity unit; levels per the
   crossover analysis); p50 pinned ≈ 44.3 ms; offload rate constant per actor
   (0.408 / 0.470); attainment flat with the measured faint deep-squeeze rise below
   cap-0.5.

Roughly two dozen parameters total. No sklearn, no iterative training — closed-form
least squares in numpy, deterministic, refit-in-milliseconds when new campaigns land.

## 3. Uncertainty

Intervals from seed spread — the dominant real noise (baseline deadline rate spans
0.719–0.742 *across seeds*, far larger than any off-saturation capacity effect): per
measured point, min/max plus a t-interval over its 3–5 seeds. Below cap-0.5 on `inc`,
widen by the ceiling law's measured sag trend (+1.1 → +3.4% as capacity falls, per the
prediction-test record) — the model inherits the law's own documented error growth.

## 4. Refusals — first-class outputs

Typed, each naming its gap and the campaign that would close it:

| Refusal | Trigger |
|---|---|
| `TRACE_NOT_MEASURED` | trace outside the five |
| `CAPACITY_OUT_OF_ENVELOPE` | c < 0.1 or > 2.5 (extrapolating *beyond* the tested range is exactly what the BOUNDED verdict warns against) |
| `FLEET_PRESET_NOT_MEASURED` | any preset but `uk2030` (lifts if the fleet-composition campaign runs) |
| `DENSITY_GAP` | any fleet size in (215, 2,488] — where the real bus fleet lives; named explicitly so the composer can offer the measuring campaign |
| `ACTOR_NOT_MEASURED` | any other checkpoint |

A refusal is a success mode: the composer's response to one is the tier-2 offer.

## 5. Fit provenance and the self-test gate

The fit reads only **committed campaign analyses** (never raw cells), records each
source digest into the fit artifact, and — before the model is allowed to predict — a
self-test must reproduce the published constants: K = 39,959 (sample σ 166, the
estimator-choice lesson from the verdict-code self-test applies), both latency slopes,
the +6.09 pp crossover margin, p50 = 44.3 ms. Mismatch ⇒ the module refuses to load the
fit. Same pattern as the verdict scripts: the code checks itself against the published
record before judging anything new.

## 6. API and integration

`fit_outcome_predictor(analysis_paths) -> FitArtifact` (JSON, committed);
`predict(scenario, fit) -> PredictionRecord | PredictionRefusal`. Consumed by the
[composer](whatif_composer_design.md) and the forecast page. When a tier-2 verification
completes, the pair (prediction, admitted analysis) is stored side-by-side — the
platform's honesty exhibit — and the new cells join the next fit.

## 7. Testing

Self-test gate (above); regression tests pinning predictions at every measured point to
the measured values; refusal tests for each taxonomy row; a property test that no input
inside the envelope can emerge unlabelled (`prediction` xor `refusal`).

## 8. Why not a neural net (recorded for the report)

154 cells whose variation is mostly structured zeros would be memorised, and a net
extrapolates confidently exactly where this design must refuse. The small model is more
accurate *and* more honest here — and one line of the dissertation's platform chapter.
