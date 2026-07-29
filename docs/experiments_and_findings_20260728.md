# TrafficTwin — All Experiments and Findings (as of 28 July 2026, 14:44)

**Status: consolidated register. Every entry is `owner_approved_candidate` at most;
exploratory unless marked CONFIRMED; descriptive, non-causal; nothing is supervisor-
approved or externally validated. Each row links its full record.**

## A. The capacity programme (local, Randy's evaluator on audited Manchester traces)

| # | Experiment | Design | Finding |
|---|---|---|---|
| 1 | **Capacity-squeeze pilot** (predeclared, 12 cells, `inc` collapse-hour trace, seeds {0–2}) | 4 capacity arms 2.5→0.75 | **The predicted degradation cliff does not exist**: deadline success flat ~79.1%; mean latency collapses 3.2× (9,799→3,084 ms); offloading decisions identical across arms. [Record](evaluation/capacity_pilot_results_20260727.md) · [full narrative](evaluation/capacity_study_detailed_findings.md) |
| 2 | **Held-out confirmatory** (signed protocol, latency primary declared pre-data, seeds {10–14}) | cap-2.5 vs cap-0.75, 10 cells | **CONFIRMED: −8,310.9 ms mean paired latency [−9,097.5, −7,524.3], all five seeds agree**; deadline null replicated. [Record](evaluation/capacity_confirmatory_results_20260728.md) |
| 3 | **Keyed action comparison** (probe over admitted pilot artifacts) | element-wise, 9 arm pairs | **0 mismatches in 8,956,800 per-vehicle actions** incl. targets — invariance at the literal action level. [Evidence](integration/evidence/vec_pilot_keyed_action_comparison_20260728.json) |
| 4 | **Observability-gap probe** (mechanism) | vehicle-side vs RSU-side state across arms | **The policy is blind by observation design**: RSU-side state differs in ~41% of cells, every vehicle-side observation input identical; no RSU-load term in the observation. [Evidence](integration/evidence/vec_pilot_observability_gap_20260728.json) |
| 5 | **B0 prediction test** (baseline actor, `ev` trace, seeds {50–52}) | 4 arms, predeclared verdict rule | **Prediction HELD**: second actor exactly as capacity-invariant; mechanism now on four independent legs. Free actor contrast: ukfleettrain slightly better deadlines/latency, baseline offloads +4pp. [Record](evaluation/baseline_invariance_results_20260728.md) |
| 6 | **Three-trace grid** (`we`, `ev`, seeds {50–52}) | pilot design per trace | **Capacity completely inert off-saturation** — every metric exactly identical across arms on both traces. [Record](evaluation/capacity_grid_results_20260728.md) |
| 7 | **Five-regime completion** (`wd_am`, `wd_pm` after ADR-066 admission) | pilot design per trace | **Unanimous**: both weekday peaks exactly inert too. All four normal regimes (139–215 slots) inert; only the 2,488-slot collapse hour binds. [Record](evaluation/capacity_sweep_completion_results_20260728.md) |
| 8 | **Deep-squeeze onset** (`ev`, arms 0.5/0.25/0.1) | extend squeeze 25× | **Onset located between cap-0.25 and cap-0.1**: inert at 10×; at 25× the collapse-hour signature appears in miniature (deadlines faintly up, latency down); decisions invariant throughout. [Record](evaluation/capacity_sweep_completion_results_20260728.md) |
| 9 | **ev timing probe** | one full run | 265.9 s/run, 6,934 s ceiling margin — ADR-065 risk closed. [Evidence](integration/evidence/vec_ev_timing_probe_20260728.json) |

| 9b | **Latency-tail analysis** (analysis-only, 39.2M active tasks/arm) | per-arm distribution | **The mechanism, measured**: p50 is 44.3 ms at every capacity (−0.10% over the 3.3× squeeze), the >1 s population moves −0.07 pp, but p99 falls 69.9% and 97.9–99.4% of latency mass is tail. The squeeze moves latency only within the already-deadline-failed population. [Record](evaluation/latency_tail_analysis_20260728.md) |
| 9c | **Per-RSU load asymmetry** (analysis-only) | 10 RSUs, 2 arms | **3 of 10 RSUs carry exactly zero load** at every capacity, a fourth under 5%, busiest ~24%; Gini 0.486→0.467 — the squeeze does not redistribute. Placement, not capacity, binds. (Row 9j attempted to revise this reading and **its revision is withdrawn** — see 9j.) [Record](evaluation/rsu_load_asymmetry_20260728.md) |
| 9d | **N1 re-examination + peak concurrency** (offline) | identity forensics; 52 quarantines | **N1 withdrawn** — no provider mutation; the "lost" source identity was the decoded XML's, and the network rebuild reproduces the original canonical identity exactly. Peak bus concurrency **1,216 max**, inside the capacity sweep's unresolved band. [Evidence](integration/evidence/n1_reexamination_and_peak_concurrency_20260728.json) |
| 9e | **Observation-chain restoration** (regeneration, not recovery) | clip → index → 305-row v1.1 match, all from committed pins after the session workspace died | **Regenerability held exactly**: 285,794 study edges of 804,611 with every edge id preserved; the match split reproduces 106/178/21 (v1.0) and 131/165/9 (v1.1) including the 51 override and 1,339 refused edge denominators; the Match Review page loads 174 queued rows, all pending. Both DfT datasets re-acquired byte-stable (342 rows / 79 pages / 39,072 rows). [Evidence](integration/evidence/manchester_chain_restoration_20260728.json) |
| 9f | **BETA-D-02 §2 demand diagnosis** (predeclared measurements, published regardless of outcome) | alpha.7 envelope reproduced at seed 42; pool and sampled demand measured | **The hypothesis is refuted and the real constraint located.** Fringe entry is **0.06%** of pool routes — below the unweighted base rate. Routes *are* long (demand median 8.17 km / 134 edges). But **4 counted edges are traversed by no pool route and are 100% unmet, and the two edges carrying 61.4% of the shortfall are traversed by 2 routes each against a median of 395**; six edges with coverage ≤2 hold 72.8% of all unmet vehicles. The binding constraint is structural reachability, so all three predeclared variants target non-binding mechanisms — variant order returned to the owner per §2. [Record](evaluation/demand_diagnosis_results_20260728.md) · [evidence](integration/evidence/manchester_demand_diagnosis_20260728.json) |
| 9g | **Pilot dynamics** (analysis-only, all 12 admitted cells) | ceiling law, per-vehicle heterogeneity, per-class slack, within-run series | **The mechanism in closed form**: the tail-latency ceiling is **linear in capacity** — p95-of-misses ÷ capacity = **39,959 ms, σ 166, 0.41% spread across all 36 cell×class pairs** (100/60/40/30 s). With ~99% of mass at the ceiling this makes mean latency linear in capacity while every deadline sits 60–300× below it, so attainment cannot move. Also: the policy is **bimodal** (only ~3.5% of slots ever switch; the split is identical at every capacity), failure is concentrated (Gini 0.62, worst decile carries 35%) though tasks are evenly spread (Gini 0.028), and saturation is immediate. [Record](evaluation/pilot_dynamics_analysis_20260728.md) |
| 9h | **Counted-edge reachability** (analysis-only, topology + permission audit) | why 6 of 150 counted edges hold 72.8% of the demand shortfall | **Two structural causes, both fatal to the predeclared variants.** (a) Exactly **4 counted edges forbid passenger vehicles** (`allow="bus bicycle"` on A6/A56/A665) and they are **exactly** the 4 zero-coverage edges — a passenger-only pool can never match a bus-lane count, at any pool size. (b) The 2 edges carrying 61.4% of the shortfall are **M56 segments at the clip boundary** — the 1st and 2nd southernmost counted edges, one with a single upstream edge within 8 hops against a typical 208. [Evidence](integration/evidence/counted_edge_reachability_20260728.json) |

| 9i | **Offload-partition analysis** (analysis-only, 5 admitted cells, 2 campaigns, 4 seeds, capacities 2.5-0.1) | what the bimodal offload decision is a function of; workload and task mix measured as confounds | **The trained policy's offload decision is a function of vehicle compute tier and nothing else measured.** The always-offload group is **exactly** the tier-0 population (100.0% in every cell) and the never-offload group contains **no tier-0 vehicle in any cell**; tier 0 is ~13x weaker than tier 2. Failure follows it: 2.8% (never) vs ~48-53% (always), with the worst-failing decile **100% always-offload in every cell**. Not workload (5,263 vs 5,243 tasks/slot) and not task mix (identical 20/30/50 shares, with failure diverging within every class -- tier-1/2 vehicles miss a 500 ms deadline **literally never**). Consequences: the ~79% attainment headline is a **fleet-composition artifact**, and capacity invariance has a simpler cause than the observation gap. Whether offloading *helps* those vehicles is a counterfactual left to the queued crossover campaign. **Decomposing the capacity effect by population** (2 seeds, 25x squeeze): never-offload mean latency is **bit-identical** at 39.6 ms, with p50, p95-of-missed and attainment also unchanged to the last decimal, while always-offload falls 25,625->1,061 ms and 27,438->1,074 ms. So the confirmed fleet-mean -8,310.9 ms **describes no vehicle** -- ~40% got an order of magnitude more, ~60% got exactly nothing -- and the ceiling law is an **RSU-queue** law, absent entirely from locally-executing traffic. [Record](evaluation/offload_partition_analysis_20260729.md) |

| 9j | **RSU association analysis** (analysis-only, 3 cells) — **PARTIALLY WITHDRAWN 29 Jul** | why RSUs sit idle | **What stands:** four RSUs run at **95.8–97.9%** of the concurrency bound while the rest sit at **~0%** (RSU 8: mean and max `rsu_busy_ms` both exactly 0.00), the saturated four carry **99.1%** of load, and the *same four* saturate across a 25× squeeze and another seed. Measured directly from `rsu_load`/`rsu_busy_ms`. The producer's association is `best_rsu_idx = jnp.argmax(all_v2i_q)` — link quality, no load term — read from source. **What is withdrawn:** the claim that idle RSUs are *frequently selected* and therefore in range, and hence the conclusion that the cause is the association rule rather than placement. That rested on counting `veh_best_rsu` per vehicle-step, which is the **wrong unit** (env-reported `n_v2i` is 2,191,339 against my 1,139,481) and which attributes 22,939 sends to an RSU with provably zero busy time. **The cause of the asymmetry is undetermined**; the original placement reading in 9c is restored as the standing interpretation. [Record](evaluation/rsu_association_analysis_20260729.md) |

**One-sentence synthesis:** the trained policies cannot see capacity (structural
observation gap), this costs nothing in any normal traffic regime, and capacity only
shapes outcomes where load saturates the concurrency bound — with the confirmed effect
being a large latency *reduction* under squeeze, not the hypothesised deadline cliff.

**The mechanism, in closed form (28 July).** The above is now a quantitative statement
rather than a narrative:

> **L(c) ≈ 39,959 ms × c** — the tail-latency ceiling is linear in per-vehicle capacity,
> to 0.41% across all 36 (cell × task-class) pairs.

Everything follows from that one relation and two facts already measured. Because ~99% of
latency mass sits *at* the ceiling, mean latency is linear in capacity — predicting the 3.33
arm ratio against the confirmed 3.24. Because every deadline (100 ms, 500 ms) lies 60–300×
*below* the ceiling at every capacity, a task at the ceiling misses at cap-2.5 and still
misses at cap-0.75. **The squeeze compresses the failed population without ever moving a
task across a deadline**, so the large confirmed latency effect and the flat deadline null
were never in tension.

Two structural findings sit beneath it. The policy is **bimodal, not probabilistic** — the
~0.40 offload rate is a fixed partition of vehicles (never / always / ~3.5% ever switching),
identical at every capacity — so on this trace it barely makes a situational decision at
all. And deadline failure is **concentrated by identity, not workload**: failure Gini ~0.62
with the worst decile carrying ~35% of failures, while tasks are spread almost perfectly
evenly (Gini 0.028). "79% attainment" is near-perfect service for most vehicles and
near-total failure for a persistent minority.

*The law is currently an interpolation across a 3.3× range. A pre-registered test of its
extrapolation 7.5× below that floor is running ([predeclaration](evaluation/ceiling_law_prediction_predeclaration.md),
digest `78dcd3ce…`), with the predicted ceilings and a ±5% pass band frozen before any cell
ran.*

## B. GPU training track (Codex, Colab G4, real producer code under recorded citation permission; all outputs non-admitted diagnostics)

| # | Campaign | Design | Finding |
|---|---|---|---|
| 10 | **B-CAP engineering smoke** | 17-D control vs 19-D capacity-obs, tiny | Pipeline proven; 17-D invariant, 19-D responds. [Evidence](integration/evidence/bcap_engineering_smoke_20260728.json) |
| 11 | **B-CAP full** (10 jobs × 5M steps, seeds {100–104}) | matched 17-D vs 19-D from scratch | 17-D controls **exactly invariant** (mechanism reproduced from scratch); 19-D demonstrably changes decisions with capacity. Archive sha `77204c47…` (data/gpu-track/, local) |
| 12 | **B-REWARD full** (10 jobs, seeds {200–204}) | α=0.7 balanced vs α=1.0 pure-QoS | Pure-QoS: ≈+0.017pp completion, +0.04 J energy, +10pp local execution, slightly lower latency, and **less capacity-conditioned switching** (1.94% vs 3.51%). Archive sha `316092d9…` |
| 13 | **B-MASK full** (10 jobs, seeds {300–304}) | 2×2: feasibility mask in training × in deployment | Completed 10/10 with the zero-infeasible masked-deployment invariant holding; treatment contrasts sealed in the archive pending review. Archive sha `cf18bedf…` (private, gitignored). [Preservation record](integration/evidence/bmask_full_campaign_preservation_20260728.json) |
| 14 | **B-BUS synthetic + IPPO smokes** | pipeline proofs | Bus-native training path and second algorithm family verified on stand-ins. |
| 15 | **B-DOMAIN full** (15 jobs, seeds {400–404}) | default / safety-dominant / pilot-inspired procedural domains | Completed 15/15; data-free diagnostic precursor only, explicitly not literal trace B4. Descriptive contrasts remain pending independent review. Archive sha `0d17154e…` (private, gitignored). [Preservation record](integration/evidence/bdomain_full_campaign_preservation_20260728.json) |

| 15b | **B-DENSITY Phase 1 + Phase 2 cost probe** (owner-directed Colab G4 via the CLI, 29 July) | engineering smoke, then a timed sweep of the frozen density grid on unpatched producer code | **Phase 1 gate passed** — density axis responds at both smoke capacities on a real GPU backend; manifest digest printed on the VM re-verified byte-exactly after download. **Two findings beyond the gate.** (a) *The frozen design's method is unnecessary*: `VEC_JAX_N_VEHICLES` and `VEC_JAX_RSU_MAX_CONCURRENT` are already documented producer knobs, and the producer's own comment says the latter exists to "match the eval engine's per-RSU concurrency scaling (2.5 × fleet)" — the allowance semantics the design demands — so no source transform is needed and the environment runs unpatched. Recorded as an explicit deviation. (b) *The grid is unaffordable as frozen*: steady-state cost decomposes to **5.92 s/update at N=512 and 31.08 s/update at N=2048** (compile 35.1 s / 71.2 s), scaling as ≈N^1.2, so 6 densities × 3 seeds at B-CAP's 5M timesteps is **≈99 GPU-hours** — several times the whole Colab balance. N=1536 and N=2048 alone are 70% of that cost. Also bounded what the environment can claim: `N_RSUS = 2`, not overridable, on a 2,000 m corridor. [Record](evaluation/bdensity_phase1_results_20260729.md) |

## C. Real bus data (BODS, owner-attended sessions, session-scoped identity)

| # | Session | Result |
|---|---|---|
| 16 | Night cadence probe (27 Jul, 15 snaps) | Median 68 s / p90 75 s update cadence; 872 seen / **41 active**; 28.4 m/s maximum. Reprocessed under corrected v1.1 identity with the same numbers. [Three-session record](evaluation/bus_session_results_20260728.md) |
| 17 | Shallow dawn session (28 Jul, 52 snapshots) | **1,676 seen / 1,162 active**; median 67 s / p90 76 s. Dawn already reaches 81.1% of peak active support. [Record](evaluation/bus_session_results_20260728.md) |
| 18 | Rush-hour session (28 Jul, 52 verified quarantines; 51 promoted) | **1,677 seen / 1,433 active**; median 66 s / p90 75 s. Peak is 35.0× night and 23.3% above dawn. Both fail-closed refusals are one two-activity cross-operator `VehicleRef` conflict (`CONFLICTING_ACTIVITY`); MAN-05 remains untouched. [Record](evaluation/bus_session_results_20260728.md) |
| 18b | **Evening-peak session** (28 Jul, owner-attended, 83 accepted / 2 refused) | **1,741 seen / 1,522 active** (1,481 on a 52-snapshot window matched to the morning session, vs 1,433); concurrency **1,250 max / 1,215 median** vs morning's 1,216 / 1,192; median cadence 66 s. Captured the crest at 17:41 BST and a clean taper to 999 by 18:47. The longest clean rush-hour window to date — it exists only because the new runner absorbs fail-closed refusals instead of discarding the window. [Record](evaluation/bus_evening_peak_session_20260728.md) |
| 18c | **MAN-05 refusal diagnosis** (all five 28 Jul refusals, read-only replay, every member hash-verified) | **One defect**: exactly one conflicting group of two activities per refusal, always different operators, **zero** conflicts under `(OperatorRef, VehicleRef, RecordedAtTime)`. BNGN in all five, ANWE in four; three of four colliding refs sit in the overlapping 3000 series. Density-dependent — 1,588–1,620 activities each time, never at the 41-vehicle night probe. [Evidence](integration/evidence/man05_refusal_diagnosis_20260728.json) |
| 19 | **B-BUS dawn→peak trace preparation** (approved; no new acquisition) | Both private motion traces completed: **961 dawn / 1,212 peak retained vehicles**, peak concurrency 827 / 1,000; 1,394 / 1,757 speed-violating segments dropped under the frozen 32 m/s rule. VEC-06 placement then refused at **66,291 / 72,208 occupied cells vs 2,000 bound**. No Colab pack, GPU run, checkpoint, or held-out verdict exists. [Result and refusal](evaluation/bbus_dawn_peak_trace_preparation_20260728.md) |
| 20 | **B-BUS corridor dawn→peak** (owner approved; frozen 750 m landmark-line capsule) | **GPU campaign completed 5/5; returned archive locally integrity-rechecked, independent homecoming pending.** Preliminary non-admitted held-out peak completion at cap-0.75: **0.809841 mean** (SD 0.053436; range 0.746932–0.854758). T1/T2/T3 means: 0.623084/0.944427/0.803651. Cap-2.5 mean 0.809672: practically invariant, not an infrastructure benefit. Archive sha `a84b5a16…`; actor admission false. [Detailed settings and preliminary result](evaluation/bbus_dawn_peak_settings_and_preliminary_results_20260729.md) |
| 21 | **B-BUS Sparse-64 dawn→peak** (owner approved; whole fleet, outside VEC-06) | **Checkpointed rerun live; no scientific result yet.** Two earlier G4 sessions were lost before a seed completed; observed throughput still projects **8.49–8.59 h (mean 8.53 h)** plus setup/evaluation. The repaired execution retains the frozen design and atomically mirrors complete state every 50 updates. G4 smoke: exact state restoration and exact scientific curve, but explicitly non-bitwise subsequent cross-process float32 execution (max actor difference 0.00598 after two smoke updates; no post-hoc tolerance). A browser-independent supervisor started all five seeds at ~10:29:54 UTC on 29 July and will retrieve/stop or resume after loss. Coverage remains **45.01% dawn / 46.00% peak**. [Checkpointed execution](evaluation/bbus_sparse64_checkpointed_execution_20260729.md) · [Detailed settings](evaluation/bbus_dawn_peak_settings_and_preliminary_results_20260729.md) |

| 22 | **Bus speed–density series** (analysis-only, four sessions, 36× fleet range) | per-segment B2 progression speed vs fleet size | **Buses at peak move 44% slower than at night** (6.290 → 3.518 m/s). Resolved hourly the series is monotone across six points (6.290/4.523/4.358/3.850/3.518/3.369 m/s); the apparent evening-faster-than-morning anomaly dissolves hour-for-hour, where the evening crest (1,462 veh, 3.369 m/s) is both denser and slower than the morning peak (1,429, 3.518). Explicitly non-causal. [Record](evaluation/bus_speed_density_20260728.md) |

**Bus status:** all four density points are processed under aggregate-only, operator-scoped
session identity. The owner approved dawn training and peak held-out evaluation with the
120 s / 15 m / 80% / 32 m/s drop-and-count rules, capacities 2.5/0.75, and seeds 30–34.
Map matching and both parent motion traces are complete. The owner selected both successors:
the corridor trace now passes exact full coverage, and the whole-fleet Sparse-64 trace is ready
under its explicitly non-VEC-06 infrastructure rule. Both separate private Colab packs are
verified. The corridor GPU arm has returned preliminary non-admitted results; the Sparse-64
checkpointed rerun is live through the Colab CLI. No browser extension or open browser tab is
required. Sparse-64 has no held-out result at this cutoff.

## D. Methodological findings (dissertation-grade in their own right)

- **Predeclaration discipline end to end**: every experiment above ran under a frozen,
  digest-bound design with publishable nulls — and the nulls arrived and were published.
- **Fail-closed integrity held under fire**: the repeat-admission resume defect (found by
  the first real interruption, fixed with regression tests, registry never contaminated);
  the float32 verification repair; the rush-hour parser refusals; the N1 identity-recording
  bug — each preserved as evidence, not papered over. N1 is the sharpest of them, because
  investigating it **withdrew our own earlier claim**: no provider ever mutated a dated
  file; a derived artifact's identity had been written into an evidence record's source
  fields, and the resulting checksum mismatch was rationalised instead of failing closed.
- **Aggregate metrics hide mechanism**: only decision-level instrumentation (keyed action
  arrays, per-side state comparison) could distinguish "policy adapts" from "queues
  change" — the platform's core justification, demonstrated.
- **Long sessions found an identity-scope defect**: bare `VehicleRef` is reused across
  operators (7 dawn / 9 peak values), manufacturing impossible 17–19 km/s jumps and the
  two strict-parser conflicts. Operator scoping removes the false merges while preserving
  the per-session privacy boundary.
- **Regenerability beats retention, and it was tested rather than asserted**: when the
  25-July session workspace died it took the network, subnetwork, index, route pool, and
  match rows with it. The audit claimed all of them were regenerable from committed pins;
  regenerating them reproduced every reconciled quantity exactly, down to override
  denominators nobody would have noticed diverging. The one thing that did *not* survive
  is instructive — a published `reconciliation_fingerprint` whose recipe lived only in the
  session script, so it can never be checked against anything. **A digest is only evidence
  if the code that computes it is committed beside it.**
- **The same argument applied to verdicts, not just digests.** For the three campaigns running
  overnight on 28–29 July, the code that computes each pre-registered verdict was committed
  *before its data existed* — while `inc-deep` was 2 of 12 cells in and both other legs were
  still queued at zero. Each re-hashes its frozen predeclaration and refuses on a mismatch, and
  each re-derives its transcribed constants from the law they encode so a typo cannot widen a
  pass band. Two gaps were closed the same way rather than left to be filled after the arms
  were visible: the onset-scaling hypothesis had **no operational definition of onset**, and
  the crossover candidate named prediction (3) as *the* interesting outcome while stating it as
  "the slope contrast should be small" — neither decidable. Both thresholds were fixed in
  advance and transcribed from tolerances the project had already committed to elsewhere, never
  chosen for the comparison at hand.
- **A self-test caught the author, which is the point of having one.** The ceiling-law verdict
  code recomputes the fitted constant from the published pilot analysis before it is allowed to
  judge new data. Its first run reproduced K (39,959.07) and the 0.41% relative spread but not
  the published σ of 166 ms — because the original statistic is the **sample** standard
  deviation, and the population estimator gives 163.4 over those 36 pairs. A transcription that
  looked right was wrong, and only an executable check against the published numbers exposed
  it. The recipe was corrected to the one that produced the law, with the reason recorded in
  the code rather than reconciled away.
