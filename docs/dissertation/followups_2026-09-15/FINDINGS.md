# Experiments 7–9: findings and research-question implications

**Completed: 72 new full runs, all validated, with 32 verified historical controls.** Each study uses the same eight previously examined fleet/evaluator seed pairs and the same morning trace. Every full run covers 10,800 simulation steps. There were no failed full attempts, retries or exclusions.

## What happened

The outcome is the percentage of **all offered tasks** that meet their deadline; rejected tasks remain in the denominator. Differences below are **percentage points (pp)**. All intervals in this summary adjust across the ten new comparisons. The [full results](RESULTS.md) retain every declared comparison, and the CSV/JSON also retain individual and within-study intervals.

| Suggestion | Main result | Meaning for the hypothesis | Full execution time |
|---|---|---|---|
| **7 — Native two-choice** | Per-task exceeded two-choice by **+0.649 pp**, 95% interval **[+0.517, +0.781]**. | The per-task advantage extends to this additional workload-aware implementation. | **26.9 min**, 8 runs |
| **8 — Half-speed servers** | The per-task/round-robin gap increased from **0.631 to 0.824 pp**. The paired increase was **+0.193 pp**, interval **[+0.034, +0.352]**. | Supports the specific prediction that the advantage grows when modeled RSU service rate is halved at unchanged offered demand. | **107.5 min**, 32 runs |
| **9 — Second actor** | Per-task exceeded ingress by **+3.539 pp** and round-robin by **+0.550 pp**; intervals **[+2.861, +4.217]** and **[+0.432, +0.668]**. | The positive comparisons recur with the UK-fleet-trained checkpoint. | **100.6 min**, 32 runs |

Full execution and validation took **3 hours 55 minutes** in total. These times exclude preparation, short qualification runs, final analysis, independent audits and reporting. Exact timestamps and timing definitions are in [TIMINGS.json](evidence/TIMINGS.json).

### 7 — Another comparator, with a clear boundary

Two-choice exceeded ingress by **+3.488 pp** [**+2.869, +4.107**]. Its difference from round-robin was **−0.018 pp** [**−0.048, +0.012**], which is inconclusive after adjustment; this does not establish equivalence.

The implemented two-choice policy samples with replacement and uses the backlog at the start of each substep. Causal per-task placement sees reservations made by earlier tasks. The comparison therefore covers both candidate sampling and reservation visibility; it cannot isolate the effect of considering two servers versus all servers.

### 8 — A measured increase under reduced processing capacity

Half-speed per-task attainment was **89.051%**, versus **88.227%** for round-robin and **84.836%** for ingress. Common-target remained **3.396 pp below ingress**. The per-task/round-robin gap increase was tested directly within each block, rather than inferred from separate significance tests. Its adjusted interval excludes zero.

The raw arrays confirm that RSU service work doubled exactly while local service work remained unchanged. This tests one reduction in processing capacity with fixed demand, count capacity and the existing admission model. It does not establish a general load-response curve or persistent congestion.

### 9 — Broader actor coverage

Under the second actor, the ranking remained **common-target < ingress < round-robin < per-task**. Common-target was **3.440 pp below ingress**. The actor change affected decisions on task-bearing vehicle-seconds, and all matched exogenous inputs and service arrays were preserved.

The two checkpoints share training seed 100 and differ in their documented fleet-training distributions. The evidence now covers two checkpoints; independent training-seed replication and wider actor generalisation remain open. This actor study uses normal server speed, so it does not test the combined second-actor/half-speed condition.

## What to do with the hypothesis and research questions

**Retain the central implementation-dependent placement hypothesis.** These results add support across an extra comparator and two separately varied conditions. Describe them as follow-up tests declared before their new full outcomes, using the existing eight blocks. Keep the original confirmation family and these new tests distinguishable.

- **RQ1:** Its central answer is reinforced. Common-target remains below ingress while causal per-task remains above ingress under both new sensitivity conditions. Keep the implementation-semantics focus.
- **RQ2:** Extend its comparator and sensitivity coverage. A possible revised wording is: *“Does the reversal recur in separate morning samples, does causal per-task placement add benefit over cyclic and sampled alternatives at baseline, and does its benefit over cyclic spreading persist under separate changes to RSU service capacity and actor training distribution?”* The original separate morning samples provide replication; the new follow-ups reuse the eight joint blocks.
- **RQ3:** Its existing information-age and forwarding-cost answer remains bounded by those completed models. Report the new capacity boundary alongside the extended RQ2 analysis and in the limitations; it supplies no additional evidence about communication delay or forwarding cost.

The intervals use eight equal-weight paired effects and Student-t uncertainty with seven degrees of freedom. Their interpretation is conditional on the selected trace, actors, simulator and paired-effect model. These additions strengthen the evidence within that scope.

## Verification and files

All 72 new cells passed accounting and control validation. Independent raw-data audits covered every new cell; the second-actor audit directly matched all 14 exogenous fields to the historical controls. A separate arithmetic implementation checked **104 table rows, 80 block effects and all 30 interval sets** across the ten contrasts.

- [Results chart](RESULTS_CHART.png) · [Scalable chart](RESULTS_CHART.svg)
- [Full results](RESULTS.md) · [Cell data](CELL_RESULTS.csv) · [Paired effects](PAIRED_EFFECTS.csv)
- [Protocol](PROTOCOL.md) · [Independent arithmetic audit](evidence/FINAL_ANALYSIS_AUDIT.json)
- [Packet file map](PACKET_MANIFEST.json)
