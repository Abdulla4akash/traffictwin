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
| 9c | **Per-RSU load asymmetry** (analysis-only) | 10 RSUs, 2 arms | **3 of 10 RSUs carry exactly zero load** at every capacity, a fourth under 5%, busiest ~24%; Gini 0.486→0.467 — the squeeze does not redistribute. Placement, not capacity, binds. [Record](evaluation/rsu_load_asymmetry_20260728.md) |
| 9d | **N1 re-examination + peak concurrency** (offline) | identity forensics; 52 quarantines | **N1 withdrawn** — no provider mutation; the "lost" source identity was the decoded XML's, and the network rebuild reproduces the original canonical identity exactly. Peak bus concurrency **1,216 max**, inside the capacity sweep's unresolved band. [Evidence](integration/evidence/n1_reexamination_and_peak_concurrency_20260728.json) |
| 9e | **Observation-chain restoration** (regeneration, not recovery) | clip → index → 305-row v1.1 match, all from committed pins after the session workspace died | **Regenerability held exactly**: 285,794 study edges of 804,611 with every edge id preserved; the match split reproduces 106/178/21 (v1.0) and 131/165/9 (v1.1) including the 51 override and 1,339 refused edge denominators; the Match Review page loads 174 queued rows, all pending. Both DfT datasets re-acquired byte-stable (342 rows / 79 pages / 39,072 rows). [Evidence](integration/evidence/manchester_chain_restoration_20260728.json) |
| 9f | **BETA-D-02 §2 demand diagnosis** (predeclared measurements, published regardless of outcome) | alpha.7 envelope reproduced at seed 42; pool and sampled demand measured | **The hypothesis is refuted and the real constraint located.** Fringe entry is **0.06%** of pool routes — below the unweighted base rate. Routes *are* long (demand median 8.17 km / 134 edges). But **4 counted edges are traversed by no pool route and are 100% unmet, and the two edges carrying 61.4% of the shortfall are traversed by 2 routes each against a median of 395**; six edges with coverage ≤2 hold 72.8% of all unmet vehicles. The binding constraint is structural reachability, so all three predeclared variants target non-binding mechanisms — variant order returned to the owner per §2. [Record](evaluation/demand_diagnosis_results_20260728.md) · [evidence](integration/evidence/manchester_demand_diagnosis_20260728.json) |

**One-sentence synthesis:** the trained policies cannot see capacity (structural
observation gap), this costs nothing in any normal traffic regime, and capacity only
shapes outcomes where load saturates the concurrency bound — with the confirmed effect
being a large latency *reduction* under squeeze, not the hypothesised deadline cliff.

## B. GPU training track (Codex, Colab G4, real producer code under recorded citation permission; all outputs non-admitted diagnostics)

| # | Campaign | Design | Finding |
|---|---|---|---|
| 10 | **B-CAP engineering smoke** | 17-D control vs 19-D capacity-obs, tiny | Pipeline proven; 17-D invariant, 19-D responds. [Evidence](integration/evidence/bcap_engineering_smoke_20260728.json) |
| 11 | **B-CAP full** (10 jobs × 5M steps, seeds {100–104}) | matched 17-D vs 19-D from scratch | 17-D controls **exactly invariant** (mechanism reproduced from scratch); 19-D demonstrably changes decisions with capacity. Archive sha `77204c47…` (data/gpu-track/, local) |
| 12 | **B-REWARD full** (10 jobs, seeds {200–204}) | α=0.7 balanced vs α=1.0 pure-QoS | Pure-QoS: ≈+0.017pp completion, +0.04 J energy, +10pp local execution, slightly lower latency, and **less capacity-conditioned switching** (1.94% vs 3.51%). Archive sha `316092d9…` |
| 13 | **B-MASK full** (10 jobs, seeds {300–304}) | 2×2: feasibility mask in training × in deployment | Completed 10/10 with the zero-infeasible masked-deployment invariant holding; treatment contrasts sealed in the archive pending review. Archive sha `cf18bedf…` (private, gitignored). [Preservation record](integration/evidence/bmask_full_campaign_preservation_20260728.json) |
| 14 | **B-BUS synthetic + IPPO smokes** | pipeline proofs | Bus-native training path and second algorithm family verified on stand-ins. |
| 15 | **B-DOMAIN full** (15 jobs, seeds {400–404}) | default / safety-dominant / pilot-inspired procedural domains | Completed 15/15; data-free diagnostic precursor only, explicitly not literal trace B4. Descriptive contrasts remain pending independent review. Archive sha `0d17154e…` (private, gitignored). [Preservation record](integration/evidence/bdomain_full_campaign_preservation_20260728.json) |

## C. Real bus data (BODS, owner-attended sessions, session-scoped identity)

| # | Session | Result |
|---|---|---|
| 16 | Night cadence probe (27 Jul, 15 snaps) | Median 68 s / p90 75 s update cadence; 872 seen / **41 active**; 28.4 m/s maximum. Reprocessed under corrected v1.1 identity with the same numbers. [Three-session record](evaluation/bus_session_results_20260728.md) |
| 17 | Shallow dawn session (28 Jul, 52 snapshots) | **1,676 seen / 1,162 active**; median 67 s / p90 76 s. Dawn already reaches 81.1% of peak active support. [Record](evaluation/bus_session_results_20260728.md) |
| 18 | Rush-hour session (28 Jul, 52 verified quarantines; 51 promoted) | **1,677 seen / 1,433 active**; median 66 s / p90 75 s. Peak is 35.0× night and 23.3% above dawn. Both fail-closed refusals are one two-activity cross-operator `VehicleRef` conflict (`CONFLICTING_ACTIVITY`); MAN-05 remains untouched. [Record](evaluation/bus_session_results_20260728.md) |
| 19 | **B-BUS dawn→peak trace preparation** (approved; no new acquisition) | Both private motion traces completed: **961 dawn / 1,212 peak retained vehicles**, peak concurrency 827 / 1,000; 1,394 / 1,757 speed-violating segments dropped under the frozen 32 m/s rule. VEC-06 placement then refused at **66,291 / 72,208 occupied cells vs 2,000 bound**. No Colab pack, GPU run, checkpoint, or held-out verdict exists. [Result and refusal](evaluation/bbus_dawn_peak_trace_preparation_20260728.md) |
| 20 | **B-BUS corridor successor preparation** (owner approved; frozen 750 m landmark-line capsule) | **Trace + private Colab pack ready:** 161,654 dawn / 281,265 peak vehicle-seconds; peak concurrency 67 / 98; 831 / 893 occupied cells. The pinned full-cover method used 12 generated sites per window and reverified **100% exact coverage**. Pack sha `8aa1b554…`; placement-contract compatible, but no VEC-06 receipt or GPU result. [Trace record](evaluation/bbus_successor_trace_preparation_20260728.md) · [pack record](evaluation/bbus_colab_pack_preparation_20260728.md) |
| 21 | **B-BUS Sparse-64 successor preparation** (owner approved; whole fleet) | **Trace + private Colab pack ready, exploratory outside VEC-06:** one dawn-weighted 64-site array reused unchanged at peak covers **45.01% dawn / 46.00% peak** vehicle-seconds at 500 m while retaining all 827 / 1,000 peak-concurrent buses. Pack sha `04e8f5db…`; peak did not influence placement; no GPU result. [Trace record](evaluation/bbus_successor_trace_preparation_20260728.md) · [pack record](evaluation/bbus_colab_pack_preparation_20260728.md) |

**Bus status:** all three density points are processed under aggregate-only, operator-scoped
session identity. The owner approved dawn training and peak held-out evaluation with the
120 s / 15 m / 80% / 32 m/s drop-and-count rules, capacities 2.5/0.75, and seeds 30–34.
Map matching and both parent motion traces are complete. The owner selected both successors:
the corridor trace now passes exact full coverage, and the whole-fleet Sparse-64 trace is ready
under its explicitly non-VEC-06 infrastructure rule. Both separate private Colab packs are
verified. No bus GPU experiment has run yet; upload is pending one local Chrome-extension file
permission, not a protocol or data change.

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
