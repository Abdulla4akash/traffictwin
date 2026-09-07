# Forwarding-cost sensitivity: completed results

The per-task placement advantage remained positive at every tested forwarding
cost. At 10 ms, it was **0.28251 percentage points**
above ingress, compared with **0.46367 points** at zero cost.
There was no crossing at the tested costs between 0 and 10 ms.

| Added forwarding latency | Deadline attainment | Advantage over ingress (pp) | Additional misses versus 0 ms |
|---|---:|---:|---:|
| 0 ms | 72.46695% | +0.46367 | 0 |
| 1 ms | 72.44783% | +0.44455 | 2,500 |
| 2.5 ms | 72.41882% | +0.41554 | 6,294 |
| 5 ms | 72.37240% | +0.36912 | 12,364 |
| 10 ms | 72.28579% | +0.28251 | 23,689 |

These results use all **13,076,234 offered tasks** in the completed Manchester
incident pilot (fleet seed 1). The fixed ingress baseline achieved **72.00328%**.
At 10 ms, **23,689** additional tasks miss their deadlines,
but **36,942** more tasks still meet deadlines than under ingress.

![Forwarding sensitivity](figures/forwarding_sensitivity.png)

## What was run and checked

Four new ten-step direct evaluator probes were run at 1, 2.5, 5 and 10 ms.
Each matched the saved-log transformation exactly for task latencies,
deadline outcomes, execution paths and forwarding fields. Actor outputs,
actions, admission, queues, task inputs and energy stayed unchanged. The
zero-cost reconstruction and the archived full-run prefix also matched
exactly. **No new full-length simulations were needed.**

The full-data deadline calculation passed exact zero-outcome/count checks,
monotonicity checks, and checks preserving rejection and non-forwarded-task
behavior. The analysis applies float32 latency addition and the evaluator's
inclusive deadline rule (`latency <= deadline`). Ten focused tests passed;
see [unit validation](unit_validation.xml), [direct qualification](qualification.json)
and [full analysis validation](analysis_validation.json).

## Interpretation limits

This is one fleet draw under the simulator's fixed-overhead forwarding model.
It is not a replicated significance or equivalence result. The costs are
controlled sensitivity values, not measured backhaul latencies. They add to
latency after placement and live admission; they do not delay queue admission,
create network congestion or change forwarding topology.

The archive contains 104 already-missed forwarded tasks with latency equal
to a failure penalty. Their underlying point latencies cannot be uniquely
recovered. Their deadline outcomes remain misses under every nonnegative
cost, so they stay in the denominator and the exact outcome calculation.
Positive-cost point latencies for those tasks are explicitly treated as
unknown; no derived mean-latency claim is made.

## Deliverables

- [Dissertation section](DISSERTATION_SECTION.md), including the completed state-delay pilot.
- [Full forwarding table](forwarding_sensitivity.csv), including per-task-type outcomes.
- [Analysis script](forwarding_analysis.py), [manifest](manifest.json) and qualification records.
- [SVG figure](figures/forwarding_sensitivity.svg), [timing diagram](figures/state_delay_timing.svg), and PNG versions.

The original code, pilot manifests, task archives and their validation
receipts were preserved. The initial latency-guard manifest is retained as
`manifest_initial_latency_guard.json`; the final method was fixed before
positive-cost full-data results were calculated.
