# E2d per-task placement robustness report — 11 August 2026

## Status

All eight existing-mode replay probes, eight new-arm smokes and four ordered 3,600-step
`per_task_dla` cells passed. The replication unit is fleet seed; tasks are not independent
replicates. E2c `ingress_dla` and common-target `dla` records were reused by exact hash.

## Per-seed observations

| Seed | Arm | Offered | Admitted | Deadline met | Offered attainment | V2I admitted | Forwarded |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `ingress_dla` | 13,076,234 | 10,522,739 | 9,415,317 | 0.720032771 | 596,254 | 0 |
| 1 | `dla` | 13,076,234 | 10,202,339 | 9,126,371 | 0.697935736 | 275,854 | 234,143 |
| 1 | `per_task_dla` | 13,076,234 | 10,594,205 | 9,475,948 | 0.724669503 | 667,720 | 600,885 |
| 2 | `ingress_dla` | 13,076,234 | 10,289,555 | 9,201,589 | 0.703688004 | 578,334 | 0 |
| 2 | `dla` | 13,076,234 | 9,991,939 | 8,933,276 | 0.683168870 | 280,718 | 240,486 |
| 2 | `per_task_dla` | 13,076,234 | 10,378,506 | 9,278,311 | 0.709555289 | 667,285 | 600,181 |
| 3 | `ingress_dla` | 13,076,234 | 10,266,497 | 9,192,285 | 0.702976484 | 591,688 | 0 |
| 3 | `dla` | 13,076,234 | 9,955,511 | 8,911,834 | 0.681529101 | 280,702 | 238,385 |
| 3 | `per_task_dla` | 13,076,234 | 10,342,346 | 9,258,605 | 0.708048281 | 667,537 | 601,402 |
| 4 | `ingress_dla` | 13,076,234 | 10,285,520 | 9,269,409 | 0.708874512 | 584,747 | 0 |
| 4 | `dla` | 13,076,234 | 9,982,922 | 8,997,090 | 0.688049021 | 282,149 | 241,809 |
| 4 | `per_task_dla` | 13,076,234 | 10,367,858 | 9,341,458 | 0.714384432 | 667,085 | 600,755 |

| Seed | per_task_dla - ingress_dla | per_task_dla - dla |
|---:|---:|---:|
| 1 | +0.004636732564 | +0.026733767536 |
| 2 | +0.005867285642 | +0.026386419821 |
| 3 | +0.005071796666 | +0.026519179758 |
| 4 | +0.005509919752 | +0.026335411251 |

## Primary strongest-link comparison

- Mean: `+0.005271433656`; sample SD: `0.000533733895`;
  SE: `0.000266866947`.
- Two-sided 95% Student-t interval, df=3:
  `[+0.004422143925, +0.006120723387]`.
- Median: `+0.005290858209`; range:
  `[+0.004636732564, +0.005867285642]`.
- Decision: `directional_advantage_for_per_task_placement_within_bounded_draws`.

## Secondary common-target comparison

- Mean: `+0.026493694591`; sample SD: `0.000177807016`;
  SE: `0.000088903508`.
- Separately labelled two-sided 95% Student-t interval, df=3:
  `[+0.026210763951, +0.026776625232]`.
- Median: `+0.026452799789`; range:
  `[+0.026335411251, +0.026733767536]`.

## Mechanism, conservation and limitations

The mechanism record reports per-RSU selected targets, actual execution, gate rejection,
forwarding and ingress-to-execution matrices, plus deterministic per-substep candidate counts,
unique targets, target switches and maximum target concentration. No unrecorded backlog was
inferred. All task, path, V2I-work and vehicle-work ledgers passed.

This is four matched provisional `uk2030` fleet draws, fixed evaluator seed 0, one Manchester
incident hour, one 2.5x/6,220-task cap, fixed 1x service and zero-cost backhaul. The frozen actor
does not observe RSU load or select execution RSUs. The inherited gate is a backlog-only
simulator rule; deadline attainment is not confirmed physical result return. There is no
ordinary-traffic control, physical/Kubernetes deployment, task-level inference, equivalence,
population-wide or Manchester-wide claim. E2d stops for independent post-run review.
