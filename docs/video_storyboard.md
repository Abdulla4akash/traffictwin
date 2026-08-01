# Dissertation video storyboard — metric-to-mechanism cut (7 minutes)

**Reconciled:** 1 August 2026
**Companion:** `video_narration_script.md`
**Target:** 7:00 inside the recorded 6–8 minute submission window.

The report explains the complete method. The video uses motion and interaction to make one result
understandable: reducing an RSU capacity control makes mean latency look better without improving
deadline attainment. It then walks from the aggregate to the vehicles and evidence that explain
it. This replaces the earlier feature-tour emphasis.

## Editorial rules

- Use one central claim, not a catalogue of 39 routes.
- Put the limitation beside each result, not in a final disclaimer montage.
- Keep protocol-confirmed, post-hoc, exploratory and non-admitted evidence visually distinct.
- Any result frame must name its committed record and carry the Putra/SUMO source credit.
- Buses are labelled public-transport vehicles; never use them as general-traffic footage.
- Screen captures must contain no raw vehicle reference, API key, session token, private path or
  producer repository content.

## Shot list

| # | Time | Length | Picture | Purpose only video can serve |
|---:|---|---:|---|---|
| 1 | 0:00–0:30 | 0:30 | Talking head over a two-line animated contrast: capacity 2.5 → 0.75; latency ↓; deadlines flat | Immediate intellectual hook |
| 2 | 0:30–1:00 | 0:30 | Event-district trace extent, then source/provenance card | Establish the exact, non-city-wide scope visually |
| 3 | 1:00–1:40 | 0:40 | Signed protocol digest → `/campaigns` receipt → held-out result | Demonstrate pre-result commitment and complete cells |
| 4 | 1:40–2:20 | 0:40 | Paired latency-by-seed figure, one seed highlighted at a time | Show that all five paired directions agree |
| 5 | 2:20–3:00 | 0:40 | Deadline plot stays flat while mean/p99/p50 layers appear | Make the metric reversal visible |
| 6 | 3:00–3:45 | 0:45 | Action-invariance figure → actor observation fields | Show why the policy did not adapt |
| 7 | 3:45–4:35 | 0:50 | Split-screen vehicle partition: never-offload vs always-offload; animate 2.5 → 0.1 | Reveal that the aggregate describes neither population |
| 8 | 4:35–5:10 | 0:35 | `/rsu-monitor`, saturated four versus idle four | Show queue concentration while refusing a causal story |
| 9 | 5:10–5:50 | 0:40 | One continuous provenance walk: metric → definition → canonical row → source row | Demonstrate auditability rather than asserting it |
| 10 | 5:50–6:20 | 0:30 | Three cards: 27/27 held; actor slope refuted; onset 4/6 refuted | Show falsifiability and limits |
| 11 | 6:20–6:40 | 0:20 | Dawn/peak bus paths with `DESCRIPTIVE / NON-ADMITTED` banner | Bound the captured-mobility successor |
| 12 | 6:40–7:00 | 0:20 | Talking head; four evidence labels collapse into the conclusion | State contribution and stop |

Total: **7:00**.

## Shot directions

### 1 — Hook

Open with the question, not the platform name. Animate the capacity setting shrinking from 2.5 to
0.75. Mean latency moves down; deadline attainment remains a horizontal line. Do not say “less
capacity is better”. Say that the ordinary mean *looks* better and the experiment asks why.

### 2 — Scope and source

Show the Etihad/Co-op Live event-district extent and the `inc` trace label. Keep “modelled collapse
hour”, “20:00–21:00”, “SUMO seed 43” and “not city-wide Manchester” simultaneously readable.
Transition to a source card naming Randy Prasetia Putra, the pinned environment/trace commits and
SUMO. Do not show private repository contents.

### 3 — Experiment instrument

Use one continuous motion from the signed candidate-B protocol digest to the campaign receipt and
its ten terminal cells, then to the results record. The point is not blockchain theatre; the
digest shows that changing the design after approval would invalidate execution. Say “confirmed
within this signed project protocol”, never “scientifically validated” or “supervisor-approved”.

### 4 — Paired result

Use the committed paired/latency figure. Highlight seeds 10–14 sequentially so the viewer sees five
negative differences instead of being asked to trust an average. Finish with the −8,310.9 ms
estimate and interval. Put `n=5; exact two-sided sign p=0.0625` in the lower third; do not hide it.

### 5 — Metric reversal

Hold the deadline series still. Layer p50 at 44.3 ms, then p99 falling 69.9%, then the
97.9–99.4% tail-mass annotation. The animation should make the logic spatial: the middle does not
move; the already-late tail compresses; the mean follows the tail.

### 6 — Decisions and observations

Start on the exact action comparison: zero mismatches, with “8,956,800 keyed decisions per pilot
pair; nine pairs” visible. Move to the actor observation field list and highlight the absence of
RSU load. Do not infer that adding load would improve the policy; only show why this actor could
not respond to this intervention through that field.

### 7 — Vehicle partition

This is the explanatory centre of the film. Split the screen into `never offload ≈60%` and
`always offload ≈40% / tier 0`. Animate capacity 2.5 to 0.1. The left latency remains 39.6 ms; the
right falls from about 26 seconds to about 1.1 seconds. Then place the fleet mean between them and
cross it out as “experienced by neither group”. Keep “post-hoc mechanism” visible.

### 8 — RSU monitor

Select a saturated RSU and then an idle one. Define pressure as in-flight tasks relative to the
recorded concurrency bound, not CPU utilisation. Show four RSUs carrying 99.1% of load. End the
shot with “cause undetermined”: the earlier association explanation was withdrawn after a counting
unit failed cross-checks.

### 9 — Provenance walk

One take, no cut: result metric, definition, canonical table, bounded row sample and source-row
view. Speak the limit exactly: provenance supports traceability and auditability, not proof of
correctness or causality. This is the highest-value use-of-medium shot.

### 10 — Predictions and refutations

Use three equal cards, not a victory list. Card one: ceiling prediction held 27/27 within ±5%.
Card two: actor latency-slope prediction refuted (52.53% contrast). Card three: exact onset scaling
refuted (4/6), with the sub-microsecond misses disclosed. The viewer should see that the workflow
can say “wrong”.

### 11 — Captured buses

Show dawn and peak paths or replay for no more than twenty seconds. Overlay the retained counts
961/1,212 and the Sparse-64 coverage of about 45%. Keep `DESCRIPTIVE / NON-ADMITTED` on screen for
the full shot. State that mobility is observed but tasks, equipment and sites are synthetic, and
that a duplicate-return deviation prevents admission.

### 12 — Conclusion

Return to the opening contrast and collapse the four labels—confirmed result, post-hoc mechanism,
refuted extensions, non-admitted transfer—into one sentence: aggregate QoS can reward resource
degradation unless the affected population is audited. End on the contribution, then stop; do not
add a feature montage.

## Spoken/visible caveat checklist

- [ ] Central trace is one modelled event-district collapse hour, not city-wide Manchester.
- [ ] Deadline completion is a source-defined compute-task threshold, not physical completion.
- [ ] Held-out finding is confirmed only within the signed project protocol.
- [ ] n=5 and exact sign-test p=0.0625 are visible.
- [ ] Tail and vehicle decomposition is labelled post-hoc.
- [ ] RSU pressure is not CPU utilisation; the asymmetry's cause is undetermined.
- [ ] Provenance is traceability, not truth or causality.
- [ ] Failed predictions are shown with the same prominence as the held prediction.
- [ ] Buses are transit vehicles; the VEC overlay is synthetic and non-admitted.
- [ ] No supervisor approval, ethics approval, participant finding or external validation is
  claimed.
- [ ] Producer/environment/trace and SUMO citations are visible on result frames.

## Recording notes

- Capture at 1920×1080 with fixed zoom, theme and window size.
- Record narration separately and leave short silences for the paired-seed and provenance motion.
- Use one continuous take for shot 9 and no more than one deliberate interaction per other shot.
- Hide terminal paths, browser profiles, notifications, raw identifiers and credentials.
- If the video will be public beyond assessment, use only sanitised/static result artifacts and
  the authorised public demonstration track.
- Watch the export once at full speed and once muted. The first checks pace/audio; the second
  checks whether the evidence hierarchy is visually understandable.

## Required assets

- `docs/dissertation_appendices/figures/capacity_latency_by_seed.svg`
- `docs/dissertation_appendices/figures/capacity_deadline_success_by_seed.svg`
- `docs/dissertation_appendices/figures/capacity_offload_invariance.svg`
- `docs/evaluation/capacity_confirmatory_results_20260728.md`
- `docs/evaluation/latency_tail_analysis_20260728.md`
- `docs/evaluation/offload_partition_analysis_20260729.md`
- `/campaigns`, `/rsu-monitor` and the provenance route in the local app
- B-BUS aggregate/session visuals only; no raw payloads
