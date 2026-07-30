# TrafficTwin — Detailed experiment catalogue (as of 30 July 2026, morning)

**Status: consolidated narrative catalogue. The
[register](../experiments_and_findings_20260728.md) is the authoritative index and each
linked record is the authoritative account; this document adds the design and execution
detail in one place so a reader — or a chapter draft — does not have to reassemble it from
forty files. Every entry is `owner_approved_candidate` at most; exploratory unless marked
CONFIRMED; descriptive and non-causal; nothing is supervisor-approved or externally
validated. Producer code/data use is under recorded permission with citation
([requirements](../producer_citation_requirements.md)).**

The lead's B-BUS Sparse-64 homecoming review and the onset-scaling verdict landed in
commits contemporaneous with this catalogue's first commit; both are reflected below from
their committed records.

---

## A. The capacity programme

**Common apparatus.** Randy's VEC evaluator (audited, pinned checkpoints) driven through
the accepted admission chain (`vec_fresh_admission`, policy
`vec-fresh-run-scientific-admission-1.0`) and the campaign instrument
(`vec_campaign`, `vec-bounded-campaign-1.0`, ADR-063): byte-bound approvals naming the
predeclaration digest, seed-major cell order, receipt-fingerprint reuse on resume,
declared budgets, halt-on-failure. Five audited Manchester traces (ADR-062/-066):
`we` 139 slots, `ev` 175, `wd_pm` 163, `wd_am` 215, and the incident collapse hour
`inc` at 2,488 — the district's lone dense regime. "Capacity" throughout is the
predeclared per-vehicle RSU concurrency control, never physical infrastructure. All
campaigns ran locally on CPU as detached (`start_new_session` + `caffeinate`) jobs with
pid files, surviving session death; every run is admitted to a registry before analysis.

### A1. Capacity-squeeze pilot

- **Aim:** does squeezing RSU capacity produce the hypothesised deadline-degradation
  cliff on the incident trace?
- **Design:** predeclared (digest `7509c7c1…`, D1–D6 resolved as relayed provenance);
  4 arms cap-2.5/1.5/1.0/0.75 × seeds {0,1,2} = 12 cells, `inc` (3,600 steps), `uk2030`
  preset, evaluator seed 0; primary `tos.task.deadline_success.rate`; design fingerprint
  `de474e03…`. ~59 min/cell, ≈12 h.
- **Result:** **the cliff does not exist.** Deadline success flat at ~79.05–79.07% across
  a 3.3× squeeze; mean latency *falls* 9,798.8 → 3,083.6 ms; offloading decisions
  identical across arms. Null published as predeclared.
- **Record:** [pilot results](capacity_pilot_results_20260727.md) ·
  [long-form narrative](capacity_study_detailed_findings.md)

### A2. Held-out confirmatory campaign — CONFIRMED

- **Aim:** confirm the pilot's latency effect on untouched seeds under a signed protocol.
- **Design:** candidate (b) signed pre-data; latency primary declared before any held-out
  cell ran; cap-2.5 vs cap-0.75 × held-out seeds {10–14} = 10 cells. Interrupted twice by
  session kills; the first real resume exposed a re-admission defect (admission clock
  leaking into `stable_fingerprint`), fixed with regression tests, registry never
  contaminated; final launch detached. 10/10 completed (7 executed + 3 resume-confirmed).
- **Result:** **CONFIRMED: mean paired latency difference −8,310.9 ms**, 95% bootstrap
  [−9,097.5, −7,524.3], all five seeds in the predeclared direction, randomisation
  p = 0.0625 (the exact n=5 floor); arm means 12,027.5 → 3,716.6 ms (3.24×). Deadline
  null replicated (0.7709 vs 0.7721, flat-to-rising on all five seeds). Held-out cohort
  now spent for capacity studies.
- **Record:** [confirmatory results](capacity_confirmatory_results_20260728.md)

### A3. Keyed action comparison

- **Design:** element-wise comparison of per-vehicle action arrays over the admitted
  pilot artifacts, 9 arm pairs.
- **Result:** **0 mismatches in 8,956,800 per-vehicle actions**, offload targets
  included — capacity invariance at the literal action level, not just in aggregates.
- **Record:**
  [evidence](../integration/evidence/vec_pilot_keyed_action_comparison_20260728.json)

### A4. Observability-gap probe

- **Design:** compare vehicle-side observation inputs and RSU-side state across arms.
- **Result:** **the policy is blind by observation design** — RSU-side state differs in
  ~41% of cells while every vehicle-side observation input is bit-identical; the
  observation carries no RSU-load term. Recorded with a falsifiable consequence: any
  actor should be equally invariant (tested by A5 and A16).
- **Record:** [evidence](../integration/evidence/vec_pilot_observability_gap_20260728.json)

### A5. B0 baseline-invariance prediction test

- **Design:** predeclared verdict rule (digest `fe3db753…`, fingerprint `2f4e371b…`);
  `baseline_model_c_17` on `ev`, same arms and seeds {50–52} as the grid leg, 12 cells.
- **Result:** **prediction HELD** — the second actor is exactly as capacity-invariant.
  Free descriptive contrast: ukfleettrain slightly better on deadlines and latency;
  baseline offloads ~4 pp more.
- **Record:** [B0 results](baseline_invariance_results_20260728.md)

### A6. Three-trace grid (`we`, `ev`)

- **Design:** pilot design replicated per trace, seeds {50–52}, 24 cells; fingerprints
  `b4da3a5b…` / `efa83a78…`; mechanism predictions recorded in advance (digest
  `93384588…`).
- **Result:** **capacity completely inert off-saturation** — every metric exactly
  identical across all four arms in every seed on both traces (paired differences
  literally 0.000000). `ev` night ≈ weekend at the VEC layer (~93.5% deadlines, ~51 ms):
  the stress is the incident, not the event.
- **Record:** [grid results](capacity_grid_results_20260728.md)

### A7. Five-regime completion (`wd_am`, `wd_pm`)

- **Design:** both weekday peaks probed (reconcile exactly; maxN 215 / 163 — the same low
  band as `we`/`ev`), admitted via ADR-066, then the pilot design per trace; fingerprints
  `2844fde2…` / `635a2cbe…`.
- **Result:** **unanimous — both weekday peaks exactly inert too.** All four normal
  regimes (139–215 slots) are inert; only the 2,488-slot collapse hour binds. That the
  incident hour is the district's lone dense regime is a finding in itself.
- **Record:** [sweep completion](capacity_sweep_completion_results_20260728.md)

### A8. Deep squeeze on `ev` (onset search)

- **Design:** arms cap-0.5/0.25/0.1 — extending the squeeze to 25× — under the
  sweep-completion predeclaration (digest `a2cb0e3d…`); fingerprint `72774544…`.
- **Result:** **the onset is located between cap-0.25 and cap-0.1**: exactly inert at
  10×; at 25× the collapse-hour signature appears in miniature (deadlines faintly up,
  latency down); decisions invariant throughout.
- **Record:** [sweep completion](capacity_sweep_completion_results_20260728.md)

### A9. Timing probes (`ev`, `inc`) and the float64 repair

- **`ev`:** 265.9 s/run, 28 MB, 6,934 s of ceiling margin — closed the ADR-065 runtime
  risk. [Evidence](../integration/evidence/vec_ev_timing_probe_20260728.json)
- **`inc`:** 3,555.96 s (49.4% of the 7,200 s request ceiling), ~100 MB. Its admission
  was initially **refused** by task-join reconciliation at t=2824 — measured cause: the
  verification-side float32 sum's own rounding exceeded the tolerance allowance at `inc`
  magnitudes (~3.9×10⁷ ms sums), while float64 verification passes all 3,600 steps at
  worst relative error 2.4×10⁻⁷ under the unchanged 3×10⁻⁷ tolerance. Fixed with a
  one-word dtype change in the verification path; the real `inc` run is the revert guard.

### A10. Latency-tail analysis

- **Design:** analysis-only, per-arm latency distributions over ~39.2M active tasks/arm.
- **Result:** **p50 is 44.3 ms at every capacity** (−0.10% over the 3.3× squeeze); the
  >1 s population moves −0.07 pp; but p99 falls 69.9% and 97.9–99.4% of latency *mass* is
  in the >1 s tail. The squeeze moves latency only within the already-deadline-failed
  population — which is exactly how a −8.3 s mean coexists with flat deadlines.
- **Record:** [latency tail](latency_tail_analysis_20260728.md)

### A11. Per-RSU load asymmetry

- **Result:** **3 of 10 RSUs carry exactly zero load at every capacity**, a fourth under
  5%, the busiest ~24%; load Gini 0.486→0.467 — the squeeze does not redistribute.
  Placement, not capacity, is the binding infrastructure problem. (A14's attempted
  revision of this reading is withdrawn; this stands.)
- **Record:** [RSU asymmetry](rsu_load_asymmetry_20260728.md)

### A12. Pilot dynamics — the ceiling law and two structural findings

- **Design:** analysis-only over all 12 admitted pilot cells.
- **Result:** **the mechanism in closed form.** (a) The tail-latency ceiling is linear in
  capacity: p95-of-missed ÷ capacity = **39,959 ms** (sample σ 166, relative spread 0.41%
  across all 36 cell×class pairs) — ceilings 100/60/40/30 s at the four arms. With ~99%
  of latency mass at the ceiling, mean latency is linear in capacity (predicting the 3.33
  arm ratio vs the confirmed 3.24), while every deadline (100/500 ms, read empirically
  from the data) sits 60–300× *below* the ceiling — so attainment cannot move.
  (b) **The policy is bimodal, not probabilistic**: counting only occupied slots, seed 0
  splits 1,413 never-offload / 988 always / 87 ever-mixing (seeds 1–2 alike), identical
  at every capacity — the "0.40 offload rate" is a fixed partition, with ~3.5% of slots
  ever switching. (c) **Failure is concentrated by identity, not workload**: failure Gini
  0.616–0.627 with the worst decile carrying 34–36% of all failures, against task-count
  Gini 0.028. Saturation is immediate (~10% into the run).
- **Record:** [pilot dynamics](pilot_dynamics_analysis_20260728.md)

### A13. Offload-partition analysis — what the decision is a function of

- **Design:** analysis-only, 5 admitted cells across 2 campaigns, 4 seeds, capacities
  2.5→0.1; workload and task mix measured as confounds.
- **Result:** **the offload decision is a lookup on vehicle compute tier and nothing else
  measured.** Always-offload = exactly the tier-0 population (100.0% in every cell);
  never-offload contains no tier-0 vehicle anywhere; tier-1/2 vehicles miss a 500 ms
  deadline literally never. Not workload (5,263 vs 5,243 tasks/slot), not task mix
  (identical 20/30/50 shares). Consequences: the ~79% attainment headline is a
  **fleet-composition artifact**. Decomposing the confirmed capacity effect by population
  (2 seeds, 25× squeeze): the never-offload ~60% is **bit-identical** end to end
  (39.6 ms both ends) while always-offload falls 25,625→1,061 and 27,438→1,074 ms — so
  **the confirmed −8,310.9 ms describes no vehicle**, and the ceiling law is an
  **RSU-queue** law (~92% of missed tasks are offloaded ones), absent from
  locally-executing traffic.
- **Record:** [offload partition](offload_partition_analysis_20260729.md)

### A14. RSU association analysis — PARTIALLY WITHDRAWN

- **What stands:** four RSUs run at 95.8–97.9% of the concurrency bound and carry 99.1%
  of load (RSU 8's `rsu_busy_ms` exactly 0.00 throughout); the same four saturate across
  a 25× squeeze and another seed; the producer's association is
  `argmax(all_v2i_q)` — link quality, no load term — read from source.
- **What is withdrawn, same day:** the claim that idle RSUs are frequently selected and
  the cause is therefore the association rule. It rested on per-vehicle-step counting —
  the wrong unit (env `n_v2i` 2,191,339 vs 1,139,481 counted; 22,939 sends attributed to
  an RSU with provably zero busy time). **The cause of the idleness is undetermined**;
  A11's placement reading is restored.
- **Record:** [RSU association](rsu_association_analysis_20260729.md)

### A15. Ceiling-law prediction test — pre-registered, HELD

- **Design:** predicted ceilings 19,980 / 9,990 / 3,996 ms at cap-0.5/0.25/0.1 with a
  ±5% band and a HELD/REFUTED/BOUNDED rule, all frozen before any cell ran (digest
  `78dcd3ce…`); verdict code committed at 2/12 cells, self-tested against the published
  law (the self-test caught a sample-vs-population σ transcription slip). 12 cells,
  `inc`, fresh seeds {60,61,62}, 18.4 h, fingerprint `5331e520…`.
- **Result:** **HELD — 27 of 27 (arm×class×seed) pairs inside the band**, at capacities
  7.5× below the fitted floor. Mean observed K 40,157 / 40,309 / 40,716 vs fitted 39,959.
  The law **sags** systematically rather than failing: error grows monotonically as
  capacity falls (T2: +1.08% → +1.73% → +3.42%), T2 largest in all nine arm×seed
  combinations, seed order 60>61>62 in every row — the predeclared BOUNDED boundary sits
  just below the tested range. Secondaries: partition identical (all seeds); attainment
  finally moved, upward on all three seeds as predeclared; p50 a partial miss (seed 61
  at 45.7–46.2 ms). Scope: per A13 this is a confirmed law about one subsystem exercised
  by ~40% of the fleet.
- **Record:** [prediction results](ceiling_law_prediction_results_20260729.md)

### A16. Actor crossover study (30 July) — no crossover; prediction (3) refuted

- **Design:** crossover rule and publishable null frozen pre-data (candidate digest
  `b8f0efa2…`); the slope band for prediction (3) fixed in a pre-data addendum
  (`a75f90bb…`); `baseline_model_c_17` mirrors the admitted pilot cell-for-cell (12 new
  cells, fingerprint `4784f5fc…`), so the pilot is the other arm. Crossover is only
  *possible* on `inc` — on the four inert traces no ordering can invert.
- **Result:** **no crossover** — the trained actor wins at all four capacities by an
  almost constant +6.09 pp of deadline attainment (margin varies by 0.00011 across the
  range); the baseline is equally deadline-flat (seed 2 bit-identical across arms).
  **Prediction (3) REFUTED**: mean-latency slopes 3,828.2 vs 6,555.4 ms per capacity
  unit — a 52.53% relative contrast against the frozen ≤5% band — so the latency response
  is *not* actor-independent under this design (two live explanations, policy vs preset
  mismatch, predeclared as indistinguishable here). Post-hoc: the baseline's latency
  level is a near-constant 1.67–1.70× multiple of the trained actor's at every capacity.
- **Record:** [crossover results](actor_crossover_results_20260730.md)

### A17. Onset-scaling sweep — pre-registered exact-identity verdict: REFUTED

- **Design:** hypothesis `c_onset = κ × N`, propagated from the `ev` bracket
  (0.1, 0.25] without collapsing it to a point; onset rule = an arm is inert only when
  *every* admitted metric at *every* seed equals cap-2.5 exactly, any nonzero difference
  binds. Legs `we` / `wd_pm` / `wd_am`, 12 cells each, caps 2.5/0.5/0.25/0.1, seeds
  {60–62} (fingerprints `0759b31f…` / `1897f9f4…` / `1d1c6ce6…`); six sharp checks and a
  binary verdict frozen pre-data, verdict code committed before the data existed.
- **Result:** **REFUTED — four of six sharp checks correct.** The load-bearing
  wd_am-binds-at-0.1 prediction held, but `we` and `wd_pm` each broke exact identity at
  cap-0.25 in one seed — by **0.243 and 0.024 microseconds** of latency — and the
  ordering qualifier is false: measured onsets are 0.25 / 0.25 / 0.1 / 0.1 for
  `we`/`wd_pm`/`ev`/`wd_am`, not increasing with slot count (139/163/175/215). Recorded
  narrowly, as the record insists: the exact-identity prediction is refuted; the
  sub-microsecond magnitudes mean the coarse grid and brittle equality rule do **not**
  establish that density is irrelevant. At cap-0.1 all four traces show the familiar
  faint signature (completion +0.0011–0.0043 pp, latency −0.024 to −0.205 ms) with
  offload decisions exactly unchanged.
- **Record:** [onset results](onset_scaling_prediction_results_20260730.md)

---

## B. GPU training track (Codex-led, Colab G4; outputs are non-admitted diagnostics)

All under the recorded code/data/publication permission with citation; archives are
private (`data/gpu-track/`, gitignored) with published SHA-256 identities and
preservation records; nothing here has passed admission or independent review.

| Campaign | Design | Outcome |
|---|---|---|
| **B-CAP smoke** | 17-D control vs 19-D capacity-obs, tiny | Pipeline proven; 17-D invariant, 19-D responds. [Evidence](../integration/evidence/bcap_engineering_smoke_20260728.json) |
| **B-CAP full** | 10 jobs × 5M steps, seeds {100–104}, matched 17-D vs 19-D from scratch | 17-D controls **exactly invariant** — the capacity-invariance mechanism reproduced from scratch training; 19-D demonstrably changes decisions with capacity. Archive `77204c47…` |
| **B-REWARD full** | 10 jobs, seeds {200–204}; α=0.7 balanced vs α=1.0 pure-QoS | Pure-QoS: ≈+0.017 pp completion, +0.04 J energy, +10 pp local execution, slightly lower latency, and *less* capacity-conditioned switching (1.94% vs 3.51%). Archive `316092d9…` |
| **B-MASK full** | 10 jobs, seeds {300–304}; 2×2 feasibility mask in training × deployment | 10/10 complete; zero-infeasible masked-deployment invariant held; treatment contrasts sealed pending review. Archive `cf18bedf…` |
| **B-BUS smokes** | synthetic + IPPO pipeline proofs | Bus-native path and second algorithm family verified on stand-ins. |
| **B-DOMAIN full** | 15 jobs, seeds {400–404}; default / safety-dominant / pilot-inspired procedural domains | 15/15 complete; data-free diagnostic precursor, explicitly not literal trace B4; contrasts pending review. Archive `0d17154e…` |
| **B-DENSITY Phase 1 + cost probe** | engineering gate, then a timed sweep on unpatched producer code (29 Jul) | Gate passed. (a) The frozen design's source transform is **unnecessary** — `VEC_JAX_N_VEHICLES` / `VEC_JAX_RSU_MAX_CONCURRENT` are documented producer knobs with the required allowance semantics; recorded as a deviation. (b) The grid is **unaffordable as frozen**: 5.92 s/update at N=512 → 31.08 at N=2048 (≈N^1.2) → ≈99 GPU-h for 6 densities × 3 seeds at 5M steps — several times the Colab balance. `N_RSUS=2`, not overridable, bounds all claims. [Record](bdensity_phase1_results_20260729.md) |
| **B-BUS corridor dawn→peak** | frozen 750 m landmark-line capsule, 5 seeds | 5/5 on GPU; archive locally integrity-rechecked (`a84b5a16…`), independent homecoming pending. Preliminary non-admitted held-out peak completion: cap-0.75 mean 0.809841 vs cap-2.5 0.809672 — practically invariant. [Settings & preliminaries](bbus_dawn_peak_settings_and_preliminary_results_20260729.md) |
| **B-BUS Sparse-64 dawn→peak** | whole observed fleet, explicitly outside VEC-06 | **GPU compute completed 5/5 through checkpoint recovery; result NON-ADMITTED on an execution deviation.** Retained cap-0.75 peak completion 0.519215 mean (SD 0.088806; T1/T2/T3 0.337793/0.595472/0.545997); cap-2.5 0.519108 — again practically capacity-invariant. After the first return, `launchd` relaunched the supervisor and repeated the fixed peak evaluation **147 times**, overwriting prior archives: no metric selection occurred, but repeat identity is unverifiable and the literal peak-once rule failed. [Homecoming](bbus_sparse64_homecoming_results_20260730.md) · [checkpointed execution](bbus_sparse64_checkpointed_execution_20260729.md) |

---

## C. Live bus observation programme (BODS, owner-attended, session-scoped identity)

All acquisition under the accepted boundary: ≥60 s between requests, one-at-a-time,
human-triggered; per-session salted HMAC identity (operator-scoped v1.1), aggregate-only
outputs; raw refs never leave quarantine.

| Session / study | Result |
|---|---|
| **Night cadence probe** (27 Jul, 15 snapshots) | Median 68 s / p90 75 s per-vehicle update cadence — the decisive unknown for B1's interpolation design, answered. 872 seen / **41 active**; legitimate 28.4 m/s motorway coach → viability speed bound corrected 25→32 m/s before it rejected real service. |
| **Dawn session** (28 Jul, 52 snapshots; acquisition survived a task kill, aggregation done post-hoc) | 1,676 seen / **1,162 active**; median 67 s. Dawn already reaches 81% of peak support. |
| **Morning rush-hour session** (28 Jul, 52 quarantines) | 1,677 seen / **1,433 active**; concurrency 1,216 max / 1,192 median; median 66 s. Two fail-closed parser refusals (see MAN-05 row). |
| **Evening-peak session** (28 Jul, 83 accepted / 2 refused of 85) | The longest clean rush-hour window — it exists only because the rewritten attended runner absorbs fail-closed refusals into a ledger instead of dying. 1,741 seen / 1,522 active (**1,481 on a 52-snapshot window length-matched to the morning**, +3.3%); concurrency 1,250 max / 1,215 median; crest caught at 17:41 BST with a monotone taper to 999 by 18:47. Cadence stable at 66–68 s across all four sessions — **feed cadence does not degrade with fleet size** (a 36× range). [Record](bus_evening_peak_session_20260728.md) |
| **MAN-05 refusal diagnosis** (all five refusals, read-only replay, every member hash-verified) | **One defect**: each refusal is exactly one conflicting group of two activities, always *different operators*, and **zero** conflicts under `(OperatorRef, VehicleRef, RecordedAtTime)` — bare `VehicleRef` is reused across operators (BNGN in all five, ANWE in four; three colliding refs in the overlapping 3000 series). Density-dependent: strikes at 1,588–1,620 activities, never at the 41-vehicle night probe. One-line fix is lead-owned; parser untouched. [Evidence](../integration/evidence/man05_refusal_diagnosis_20260728.json) |
| **Speed–density series** (analysis-only, four sessions) | **Buses at peak move 44% slower than at night** (6.290 → 3.518 m/s session-level). Hourly resolution gives six monotone points (6.290 / 4.523 / 4.358 / 3.850 / 3.518 / 3.369 m/s) and dissolves the apparent evening-faster-than-morning anomaly: hour-for-hour the evening crest (1,462 veh) is both denser and slower than the morning peak (1,429). Explicitly non-causal. [Record](bus_speed_density_20260728.md) |
| **B-BUS trace preparation** (approved; no new acquisition) | Dawn/peak motion traces: 961 / 1,212 retained vehicles, peak concurrency 827 / 1,000; 1,394 / 1,757 speed-violating segments dropped under the frozen 32 m/s rule. VEC-06 placement then **refused** (66,291 / 72,208 occupied cells vs the 2,000 bound) — which is what routed both successors (corridor capsule; Sparse-64 outside VEC-06). [Record](bbus_dawn_peak_trace_preparation_20260728.md) |

A standing measurement worth its own line: **peak bus concurrency (~1,192–1,250) sits
inside the capacity sweep's unresolved density band (215, 2,488]** — the observed fleet
lives exactly where the simulation programme has no data yet.

---

## D. Manchester digital-twin chain (network, observation, demand)

### D1. Demand diagnosis (BETA-D-02 §2) — hypothesis refuted, constraint located

Predeclared diagnosis-first measurements, published regardless of outcome. The alpha.7
demand envelope was reproduced over the restored subnetwork (43,200 trips; 43,200 routes,
88,163,681 B vs recorded 88,163,497 = banner delta; 749,267 sampled vehicles; achievement
91.72% vs recorded 91.32%; 0 overflow). Findings: **the recorded fringe-bias hypothesis
is refuted** — boundary entry is 0.06% of pool routes, *below* the unweighted base rate.
Routes are long (median 8.17 km / 134 edges — reproducing the truncated 25-July survivor's
median exactly). The real constraint is **structural reachability**: 4 counted edges have
zero pool routes and are 100% unmet; the 2 edges carrying 61.4% of the shortfall have
exactly 2 pool routes each vs a median of 395; six edges with coverage ≤2 hold **72.8% of
all unmet vehicles**. All three predeclared repair variants therefore target non-binding
mechanisms; per the predeclaration's own rule the variant order was returned to the owner,
nothing run. [Record](demand_diagnosis_results_20260728.md)

### D2. Counted-edge reachability — the two causes, exactly

(a) Exactly **4 counted edges forbid passenger vehicles** (`allow="bus bicycle"`,
A6/A56/A665) and they are exactly the 4 zero-coverage edges — a passenger-only pool can
never match a bus-lane count at any pool size (DfT counts buses too; a modelling
mismatch, not a sampling failure). (b) The two dominant-shortfall edges are **M56
segments at the clip boundary** — the two southernmost counted edges, one with a single
upstream edge within 8 hops against a typical 208.
[Evidence](../integration/evidence/counted_edge_reachability_20260728.json)

### D3. N1 re-examination — our own claim withdrawn

Identity forensics on the "mutated" Geofabrik source: **no provider ever mutated
anything**. The on-disk PBF (50,502,348 B, md5 `c73b16ec…`) equals the provider's
published md5 and the first acquisition record exactly; a derived artifact's identity (the
decoded XML's) had been written into an evidence record's *source* fields and the
mismatch rationalised instead of failing closed. The full GM network rebuild into durable
storage reproduces the 25-July canonical identity `ce285f85…` **exactly** (raw bytes
differ by 2 — the netconvert banner, by design). Never claim provider mutation in the
dissertation. Guards added (`artifact_integrity.py`) that refuse source/derived identity
collisions — verified to fire on the real July record.
[Evidence](../integration/evidence/n1_reexamination_and_peak_concurrency_20260728.json)

### D4. Observation-chain restoration — regenerability tested, not asserted

When the 25-July session workspace died it took the network, subnetwork, spatial index,
route pool and match rows with it. Regenerating from committed pins reproduced every
reconciled quantity **exactly**: 285,794 study edges of 804,611 (edge ids 100%
preserved; 424,988,852 B vs recorded 424,988,627 = banner), the 305-site match split
byte-for-byte (v1.0 106/178/21; v1.1 131/165/9 with 51 override edges and 1,339 refused),
and both DfT datasets re-acquired with the same raw-fingerprint prefixes as the originals
(342 rows / 39,072 rows over 79 pages) — the DfT historical archive is byte-stable. The
one non-survivor is the instructive one: a published `reconciliation_fingerprint` whose
recipe lived only in the dead session script and is unverifiable forever. **A digest is
only evidence if the code that computes it is committed beside it** — now a register
rule. [Evidence](../integration/evidence/manchester_chain_restoration_20260728.json)

---

## E. Method: what the programme itself demonstrated

The register's [§D](../experiments_and_findings_20260728.md) carries these in full; in
brief: predeclaration discipline held end to end (every campaign under a frozen,
digest-bound design with publishable nulls — and the nulls arrived and were published);
fail-closed integrity held under fire (the resume defect, the float32 repair, the parser
refusals, N1 — each preserved as evidence); aggregate metrics hide mechanism
(decision-level instrumentation was what separated "policy adapts" from "queues change");
verdict code is committed *before its data exists* and re-hashes its frozen
predeclaration; and two same-day self-caught retractions (the coverage-hypothesis
inversion and the RSU-association unit error) are recorded beside the claims they
corrected, not instead of them.

## The synthesis these experiments support

The trained policies cannot see capacity (structural observation gap, A4), which costs
nothing in any normal traffic regime (A6, A7) and is shared by an untrained baseline (A5,
A16). Capacity shapes outcomes only where load saturates the concurrency bound (A1, A8) — and
where that onset sits does not follow slot count proportionally (A17) — and there its
confirmed effect is a large *improvement* in mean latency under degradation (A2) — an improvement that obeys a closed-form ceiling law (A12) validated by
pre-registered extrapolation (A15), that lives entirely inside the already-failed tail
(A10), and that **describes no actual vehicle** (A13). The dissertation headline this
grounds: *standard VEC QoS metrics can be improved by degrading the system* — with
capacity as the instrument, and the platform's evidence discipline as what made every
step checkable.
