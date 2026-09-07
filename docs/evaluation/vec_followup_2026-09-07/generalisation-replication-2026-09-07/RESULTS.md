# Three-arm morning replication: results

Primary analysis uses only the four new fleet draws: **0, 2, 3 and 4**. All twelve full runs passed the declared validation. The earlier seed-1 pilot is kept in a separate supplementary summary.

| Arm | Mean deadline attainment | SD across fleet draws |
|---|---:|---:|
| ingress | 88.88685% | 1.06005 pp |
| common_target | 85.65460% | 1.64874 pp |
| per_task | 92.78537% | 0.56174 pp |

## Paired primary comparisons

| Contrast | Mean difference (pp) | Paired 95% t interval | Simultaneous 95% family interval |
|---|---:|---:|---:|
| per_task_minus_ingress | +3.89852 | [+3.09435, +4.70270] | [+2.67129, +5.12575] |
| common_target_minus_ingress | -3.23225 | [-4.17554, -2.28897] | [-4.67178, -1.79273] |
| per_task_minus_common_target | +7.13078 | [+5.38469, +8.87686] | [+4.46611, +9.79544] |

The intervals use paired fleet-draw differences (n=4, df=3), never individual tasks. Family intervals use the predeclared Bonferroni correction across the three contrasts. These small-sample parametric intervals depend on assumptions about the draw-level distribution; they do not represent uncertainty across traffic dates, task seeds or geographic settings.

## Each new draw

| Fleet seed | Ingress | Common-target | Per-task | Per-task − ingress (pp) | Common − ingress (pp) | Per-task − common (pp) |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 88.81657% | 85.65961% | 92.70461% | +3.88804 | -3.15696 | +7.04500 |
| 2 | 87.53575% | 83.53716% | 92.05970% | +4.52395 | -3.99859 | +8.52254 |
| 3 | 89.08249% | 85.86218% | 92.97839% | +3.89590 | -3.22031 | +7.11621 |
| 4 | 90.11258% | 87.55943% | 93.39878% | +3.28619 | -2.55316 | +5.83935 |

## Ranking question

The historical ordering **common-target < ingress < per-task** occurred in **4 of 4** new draws. It did hold for the arm means. The simultaneous-interval criterion for that reversal was met.

A different ordering is retained as evidence about the scope of the implementation effect. Cross-scenario changes in that ordering cannot identify which difference caused them: the morning and incident cases also differ in density, date/window, RSU layout/count, and slot/entry conventions.

## Supplementary five-draw two-arm summary

This table includes the already inspected pilot, which influenced the decision to replicate. It is descriptive and is not five previously unseen confirmation draws. No pilot common-target cell was added or imputed.

| Seed | Role | Ingress | Per-task | Difference (pp) |
|---|---|---:|---:|---:|
| 0 | new primary draw | 88.81657% | 92.70461% | +3.88804 |
| 1 | already inspected exploratory pilot | 91.07548% | 94.02844% | +2.95296 |
| 2 | new primary draw | 87.53575% | 92.05970% | +4.52395 |
| 3 | new primary draw | 89.08249% | 92.97839% | +3.89590 |
| 4 | new primary draw | 90.11258% | 93.39878% | +3.28619 |

Descriptive five-draw mean difference: **+3.70941 pp**; range **[+2.95296, +4.52395] pp**.

## Controls, diagnostics and reproducibility

All arms used the same canonical 10,800-second morning trace, nine RSUs, frozen actor, absolute 6,220-task RSU capacity, 1× service, zero forwarding cost and per-visit vehicle queue resets. The three arms retained their frozen admission implementations and three reconciliation passes. This tests fleet variability within another Manchester scenario, not independent geographic generalisation.

All arms passed matched input/action checks, exact task accounting and RSU workload reconstruction, including service-work conservation and per-second task-count carry. Common-target broadcast and least-workload selection were checked. Exact errors and input/output hashes are retained with each run.

Total full-evaluator wall time: **36.88 minutes**, excluding probes, export and validation.

See [prespecified protocol](PROTOCOL.md), [manifest](manifest.json), [per-run metrics](runs.csv), [rejection counts](runs.csv), [RSU workload distribution](rsu_workload_distribution.csv), [task-type outcomes](task_types.csv), and [analysis receipt](analysis_validation.json).
