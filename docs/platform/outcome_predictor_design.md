# Design — VEC outcome predictor (platform P-1, tier 1)

**Status: IMPLEMENTED in Phase 140 (`c85538c`) at the
`owner_approved_candidate` ceiling, with the review-conformance items in §§1, 4 and 7
still required before the composer may treat every accepted scenario as inside a measured
actor-specific envelope. The surrogate is fitted on the project's own admitted cells,
predicts instantly, and refuses outside its declared domain. Every output is typed
`prediction` and is NEVER evidence — binding, type-level.**

## 1. Scenario coordinates and outputs

Input: `(trace, capacity, actor, fleet_preset, fleet_size?)` with
`trace ∈ {we, ev, wd_am, wd_pm, inc}`, `capacity ∈ [0.1, 2.5]`,
`actor ∈ {ukfleettrain_mappo_model_c_17, baseline_model_c_17}`, fleet preset fixed
`uk2030`, and optional `fleet_size` required to equal the selected trace's measured slot
count when supplied. Output: a `PredictionRecord` containing point + interval for every
metric available in that actor/trace regime, a typed `metrics_unavailable` reason for the
rest, `evidence: False`, `confirmatory: False`, the fit digest, and the regime. It must
never imply that all five metrics exist for every scenario: p50 and tail-ceiling inputs
are `inc`-only and trained-actor-only in the current fit.

The measured domain is not a Cartesian product. The trained actor has admitted cells on
all five traces and the deep `inc` range down to cap-0.1. The baseline actor has an `ev`
grid and `inc` cells only at cap-0.75/1.0/1.5/2.5. Any other actor/trace pair or baseline
`inc` capacity below 0.75 is outside that actor's measured envelope even though it lies
inside the global numeric range. The current Phase-140 implementation already refuses
unmeasured actor/trace pairs, but still line-extrapolates baseline `inc` below 0.75; that
case is a review gap and must refuse before composer integration.

## 2. Model structure — the measured laws, packaged (three regimes)

1. **Off-saturation** (`we`/`ev`/`wd_am`/`wd_pm` above their measured onsets): return
   a prediction derived from the measured cap-2.5 descriptives for a measured trace/actor
   pair. The *capacity contrast* was exactly zero in the relevant paired cells, but seed
   variation in the predicted level is not zero; the record says
   `regime: "measured_inert"` and exposes its seed interval.
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
least squares in numpy, deterministic apart from the generated timestamp, and quick to
refit when a newly admitted campaign is explicitly reviewed. A completed campaign never
joins the fit automatically.

## 3. Uncertainty

Intervals are uncertainty summaries from seed spread — the dominant measured variation
(baseline deadline rate spans 0.719–0.742 *across seeds*, far larger than any
off-saturation capacity effect): per measured point, min/max plus a t-interval over its
3–5 seeds. Below cap-0.5 on `inc`,
widen by the ceiling law's measured sag trend (+1.1 → +3.4% as capacity falls, per the
prediction-test record) — the model inherits the law's own documented error growth.
These are not calibrated predictive intervals, population confidence bounds, or a basis
for significance claims; the interval method and seed support travel with every metric.

## 4. Refusals — first-class outputs

Typed, each naming its gap and the campaign that would close it:

| Refusal | Trigger |
|---|---|
| `TRACE_NOT_MEASURED` | trace outside the five |
| `CAPACITY_OUT_OF_ENVELOPE` | c < 0.1 or > 2.5 (extrapolating *beyond* the tested range is exactly what the BOUNDED verdict warns against) |
| `FLEET_PRESET_NOT_MEASURED` | any preset but `uk2030` (lifts if the fleet-composition campaign runs) |
| `DENSITY_GAP` | an input fleet size strictly between the measured endpoints 215 and 2,488; the saturation-onset bracket is conventionally written (215, 2,488], but 2,488 itself is the measured `inc` endpoint |
| `ACTOR_NOT_MEASURED` | an unknown checkpoint or a trace/actor pair with no admitted cells |
| `ACTOR_CAPACITY_NOT_MEASURED` | a capacity outside that actor/trace pair's measured range, notably baseline `inc` below 0.75 |

A refusal is a success mode: the composer's response to one is the tier-2 draft offer.
Adding `ACTOR_CAPACITY_NOT_MEASURED` (or an equally specific typed refusal) and its test is
a review-conformance change; the composer must not work around it with a global-envelope
check.

## 5. Fit provenance and the self-test gate

The fit reads only digest-bound local analyses from the explicit admitted-campaign registry
(never raw cells). The campaign-analysis files under `data/vec-fresh/` are local and
gitignored, not committed; the committed fit artifact preserves their repository-relative
logical paths, content digests, experiment identifiers and design fingerprints. Admission
is inherited, not re-decided: **non-admitted diagnostics never enter the fit** — no
GPU-track output, no execution-deviated run (both Sparse-64 returns carry `NON_ADMITTED`
status in their own evidence records), and no unregistered experiment. Absolute/private
paths, credentials and raw identities are forbidden in the fit artifact.

Source standing remains distinct inside the fit: the signed held-out contrast is
protocol-confirmed at its recorded ceiling; the ceiling mechanism and tail composition are
post-hoc or prediction-test inputs; the grids and crossover are exploratory/descriptive.
Fitting them together does not promote any source or make the output evidence. Because the
numbers derive from producer code/data, published prediction cards and fit documentation
must carry the citation set in
[`producer_citation_requirements.md`](../producer_citation_requirements.md); private
permission text is never stored.

Before the model is allowed to predict, a self-test must reproduce the published constants:
K = 39,959 (sample σ 166, the estimator-choice lesson from the verdict-code self-test
applies), both latency slopes, the +6.09 pp crossover margin, p50 = 44.3 ms.
Mismatch ⇒ the module refuses to load the fit. Same pattern as the verdict scripts:
the code checks itself against the published record before judging anything new.

## 6. API and integration

`fit_outcome_predictor(analysis_paths) -> FitArtifact` (JSON, committed);
`predict(scenario, fit) -> PredictionRecord | PredictionRefusal`. Consumed by the
[composer](whatif_composer_design.md) and the forecast page. When a tier-2 verification
completes and is admitted, the pair (prediction, admitted analysis) may be stored
side-by-side without changing either artifact's evidence type — the platform's honesty
exhibit. New cells join only a separately reviewed refit.

## 7. Testing

Phase 140 records 19 unit tests against the committed fit artifact: self-test tampering,
regression pins at measured points, refusal rows, fit-boundary refusals, and the property
that no input emerges unlabelled (`prediction` xor `refusal`). Review acceptance adds a
coverage-matrix test: every trace/actor/capacity combination is either backed by that
combination's measured range or produces the specific actor-capacity refusal. It must pin
baseline `inc` cap-0.1/0.25/0.5 as refusals and prove unavailable p50/ceiling metrics never
appear as values. Citation fields and private-path rejection also require tests before the
predictor is exposed through the dashboard.

## 8. Why not a neural net (recorded for the report)

154 cells whose variation is mostly structured zeros would be memorised, and a net
could extrapolate confidently exactly where this design must refuse. No neural comparison
has been run, so no accuracy advantage is claimed. The small model is auditable and can
encode refusal at the measured boundary — the reason for choosing it here.
