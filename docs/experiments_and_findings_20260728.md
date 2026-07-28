# TrafficTwin — All Experiments and Findings (as of 28 July 2026, 12:30)

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
| 13 | **B-MASK full** (10 jobs, seeds {300–304}) | 2×2: feasibility mask in training × in deployment | Completed 10/10 with the zero-infeasible masked-deployment invariant holding; treatment contrasts sealed in the archive pending review. |
| 14 | **B-BUS synthetic + IPPO smokes** | pipeline proofs | Bus-native training path and second algorithm family verified on stand-ins. |
| 15 | **B-DOMAIN** | predeclared 28 Jul (commit `a08e73f`) | In progress / pending report. |

## C. Real bus data (BODS, owner-attended sessions, session-scoped identity)

| # | Session | Result |
|---|---|---|
| 16 | Night cadence probe (27 Jul, 15 snaps) | Median 68 s / p90 75 s update cadence; 872 seen / 41 active; 28.4 m/s legit coach → B1 speed bound corrected. |
| 17 | Shallow dawn session (28 Jul, 52 receipted snapshots) | Captured; aggregation pending (session interrupted before its final step; data durable). |
| 18 | Rush-hour session (28 Jul, ~52 receipted snapshots) | Captured 08:03–09:00; **halted twice by fail-closed `PARSE_REJECTED`** — a recurring rush-hour feed-shape gap in the strict parser, preserved as a data-quality finding. Aggregation pending. |

**Bus status:** three density points captured (night/dawn/peak); processing pending; no
bus experiment run yet (B1 awaits G1–G5 signing after processing).

## D. Methodological findings (dissertation-grade in their own right)

- **Predeclaration discipline end to end**: every experiment above ran under a frozen,
  digest-bound design with publishable nulls — and the nulls arrived and were published.
- **Fail-closed integrity held under fire**: the repeat-admission resume defect (found by
  the first real interruption, fixed with regression tests, registry never contaminated);
  the float32 verification repair; the rush-hour parser refusals; the Geofabrik dated-file
  mutation (N1) — each preserved as evidence, not papered over.
- **Aggregate metrics hide mechanism**: only decision-level instrumentation (keyed action
  arrays, per-side state comparison) could distinguish "policy adapts" from "queues
  change" — the platform's core justification, demonstrated.
