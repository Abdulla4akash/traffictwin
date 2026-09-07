# Generalisation pilot: completed analysis

Fresh per-task placement achieved **94.02844%** offered-task deadline attainment, compared with **91.07548%** for ingress. The difference was **+2.95296 percentage points** (+51,503 deadline-met tasks).

| Condition | Offered tasks | Deadline-met tasks | Attainment | V2I gate rejections | Forwarded tasks |
|---|---:|---:|---:|---:|---:|
| fresh | 1,744,116 | 1,639,965 | 94.02844% | 417 | 280,857 |
| ingress | 1,744,116 | 1,588,462 | 91.07548% | 43,602 | 0 |

## What this establishes

The per-task result was higher than ingress within this one matched working-day fleet draw. This is a descriptive result; tasks are not independent replications and the pilot supplies no replicate-level confidence interval. The result must not be used to claim universal superiority, equivalence, or a geographical generalisation.

The full Tuesday 15 October 2024 08:00–11:00 window contains 10,800 seconds, 215 padded vehicle slots and nine canonical RSUs. Both conditions share the actor, task stream, fleet draw, vehicle-entry queue resets and all controls except the placement rule. The actor remains the original frozen onehot17 MAPPO seed100 checkpoint. The primary denominator contains all offered tasks, including rejections and unavailable tasks.

Compared with the old incident scenario, traffic density, date, window length, RSU placement/count, slot assignment and availability of entry markers differ. Therefore the cross-scenario change in the size of the placement effect cannot be attributed to traffic alone. This study tests transfer to another scenario in the same Manchester simulation network. Capacity was kept at an absolute 6,220 tasks per RSU, service at 1×, forwarding at 0 ms and scaling off.

V2I gate rejections fell from 43,602 to 417, while V2I admissions rose from 273,317 to 316,502. Neither condition had capacity rejections. Per-task execution counts were more evenly distributed across the nine RSUs; the exact counts are in the analysis receipt. These diagnostics are consistent with placement reducing concentrated queue demand.

## Task types

| Type | Offered tasks per condition | Fresh attainment | Ingress attainment | Difference (pp) |
|---|---:|---:|---:|---:|
| T1 | 349,045 | 82.20115% | 76.65344% | +5.54771 |
| T2 | 523,060 | 98.92001% | 98.91867% | +0.00134 |
| T3 | 872,011 | 95.82849% | 92.14368% | +3.68482 |

## Validation and runtime

The trace and source FCD matched their published checksums; source reconstruction matched positions, speed, activity, entry markers and timestamps for every row. Both 300-step probes passed before the full runs. Each full task prefix matched its same-arm probe. Full runs passed task-count, outcome, rejection, queue/path, finite-value and paired input checks. Actor actions, task types, task activity, fleet and ingress identity matched between arms, with actor logits within the predeclared absolute 0.00001 tolerance. The fresh arm additionally passed the recorded RSU workload endpoint conservation check.

Full evaluator wall time total: **5.22 minutes**. Runner time including probes, polling, export and validation: **6.03 minutes**. These times exclude input preparation. The original hours-long estimate was based on the much wider incident trace; this smaller fleet requires substantially less computation.

See [experiment plan](README.md), [manifest](manifest.json), [metrics](metrics.csv), [analysis validation](analysis_validation.json), and [input validation](input_validation.json). Raw run archives and per-run validation receipts are retained in `cells/`. Earlier incident and forwarding records were preserved.
