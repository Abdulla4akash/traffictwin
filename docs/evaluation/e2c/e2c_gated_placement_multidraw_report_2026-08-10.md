# E2c gated-placement matched multi-draw report — 10 August 2026

## Status and evidence boundary

All 16 predeclared ten-step smokes and all eight new 3,600-step cells passed. The primary
replication sample is the four new matched fleet draws 1–4. Seed 0 is prior pilot evidence and was
excluded from the primary interval. Individual tasks were not treated as independent replicates.

## New full-cell observations

| Fleet seed | Arm | Offered | Admitted | Deadline met | Offered attainment | Admitted attainment | Latency/offered (ms) | V2I admitted | Forwarded |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `ingress_dla` | 13,076,234 | 10,522,739 | 9,415,317 | 0.720032771 | 0.894759150 | 421.078 | 596,254 | 0 |
| 1 | `dla` | 13,076,234 | 10,202,339 | 9,126,371 | 0.697935736 | 0.894537125 | 510.441 | 275,854 | 234,143 |
| 2 | `ingress_dla` | 13,076,234 | 10,289,555 | 9,201,589 | 0.703688004 | 0.894265010 | 463.708 | 578,334 | 0 |
| 2 | `dla` | 13,076,234 | 9,991,939 | 8,933,276 | 0.683168870 | 0.894048292 | 545.896 | 280,718 | 240,486 |
| 3 | `ingress_dla` | 13,076,234 | 10,266,497 | 9,192,285 | 0.702976484 | 0.895367232 | 464.889 | 591,688 | 0 |
| 3 | `dla` | 13,076,234 | 9,955,511 | 8,911,834 | 0.681529101 | 0.895165904 | 551.713 | 280,702 | 238,385 |
| 4 | `ingress_dla` | 13,076,234 | 10,285,520 | 9,269,409 | 0.708874512 | 0.901209565 | 460.618 | 584,747 | 0 |
| 4 | `dla` | 13,076,234 | 9,982,922 | 8,997,090 | 0.688049021 | 0.901248152 | 544.342 | 282,149 | 241,809 |

## Primary matched replication

The estimand is `dla - ingress_dla`, holding the live deadline-aware admission gate fixed.

| Fleet seed | ingress_dla | dla | Paired difference |
|---:|---:|---:|---:|
| 1 | 0.720032771 | 0.697935736 | -0.022097035 |
| 2 | 0.703688004 | 0.683168870 | -0.020519134 |
| 3 | 0.702976484 | 0.681529101 | -0.021447383 |
| 4 | 0.708874512 | 0.688049021 | -0.020825491 |

- Negative / zero / positive draws: 4 / 0 / 0.
- Mean: `-0.021222260935`.
- Sample SD: `0.000699457605`.
- Standard error: `0.000349728802`.
- Two-sided 95% Student-t interval, df=3: `[-0.022335254070, -0.020109267800]`.
- Median / minimum / maximum: `-0.021136437295 / -0.022097034972 / -0.020519134179`.
- Predeclared decision: `evidence_of_directional_difference_within_bounded_four_draw_replication`.

This decision applies only to the bounded four-draw replication. It is not an equivalence,
non-inferiority, population-wide or general controller-superiority claim.

## Combined descriptive pilot-plus-replication summary

This separately labelled description includes seeds 0–4 and is not a held-out confirmatory test.
The five raw differences are `-0.020833291910, -0.022097034972, -0.020519134179, -0.021447383092, -0.020825491499`; their
descriptive mean is `-0.021144467130`, median
`-0.020833291910`, range
`[-0.022097034972, -0.020519134179]`, and sign consistency is
`all_negative`.

## Secondary paired outcomes (`dla - ingress_dla`)

Raw fleet-seed differences precede the descriptive mean.

| Outcome | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Mean |
|---|---:|---:|---:|---:|---:|
| `admitted_task_deadline_attainment` | -0.000222024424 | -0.000216717188 | -0.000201328292 | +3.85870793e-05 | -0.000150370706 |
| `deadline_met_task_count` | -288946 | -268313 | -280451 | -272319 | -277507.25 |
| `admitted_task_count` | -320400 | -297616 | -310986 | -302598 | -307900 |
| `v2i_admitted_count` | -320400 | -297616 | -310986 | -302598 | -307900 |
| `gate_rejected_count` | +320400 | +297616 | +310986 | +302598 | +307900 |
| `cap_rejected_count` | +0 | +0 | +0 | +0 | +0 |
| `offered_task_latency_ms` | +89.3624877 | +82.1876464 | +86.8248127 | +83.723149 | +85.524524 |
| `admitted_task_latency_ms` | -4.45571328 | -3.98675032 | -4.42741377 | -4.22369542 | -4.2733932 |
| `deadline_met_latency_ms` | -4.98301541 | -4.54840088 | -4.99946599 | -4.65626799 | -4.79678757 |
| `energy_j_per_offered_task` | -1.71685517e-05 | -1.59067205e-05 | -1.51802117e-05 | -1.56008221e-05 | -1.59640765e-05 |
| `forwarded_count` | +234143 | +240486 | +238385 | +241809 | +238705.75 |
| `forwarded_share` | +0.848793202 | +0.856681795 | +0.849245819 | +0.857025898 | +0.852936678 |
| `execution_share_range` | +0.181311635 | +0.165271543 | +0.167842122 | +0.169335413 | +0.170940178 |
| `maximum_execution_share` | +0.130189126 | +0.122451995 | +0.125483649 | +0.122333889 | +0.125114665 |

## Mechanism and conservation

The machine-readable mechanism summary reports, by arm and fleet seed, selected targets, actual
execution, gate rejection, deadline-met admitted V2I tasks, admitted-V2I latency and attainment by
execution RSU, forwarding, execution imbalance and the complete ingress-to-execution matrix.
Observed redistribution is described only as associated with the paired deadline direction. No
unrecorded decision-time backlog was inferred.

Every cell passed task accounting, task-outcome reconciliation, native path consistency, V2I
service-work conservation and vehicle service-work conservation. `ingress_dla` selected and
executed only at ingress, forwarded zero tasks and charged zero forwarding latency. `dla` recorded
forwarding only for admitted tasks whose execution differed from ingress; rejected work was never
executed or forwarded. Backhaul latency was zero by design.

## Limitations and stop

- Four new provisional fleet draws, one fixed evaluator seed and one Manchester incident hour.
- One cap, fixed 1x service, ideal zero-cost backhaul and no ordinary-traffic control.
- The frozen actor does not observe current RSU load or select an execution RSU.
- In the inherited evaluator, DLA chooses one common `argmin(rsu_busy_ms)` JSQ target per
  substep, so that substep's eligible V2I traffic shares one selected target; execution-imbalance
  and deadline observations must be read under this convention.
- Deadline attainment is evaluator success, not confirmed physical task-result return.
- No physical deployment, Kubernetes execution, scaling, P2C, learning, prediction or retraining.
- The controlled simulator intervention does not establish real-world causality or
  Manchester-wide generalisation.
- Close numerical values are not equivalence.

E2c stops here. The exact next gate is researcher review.
