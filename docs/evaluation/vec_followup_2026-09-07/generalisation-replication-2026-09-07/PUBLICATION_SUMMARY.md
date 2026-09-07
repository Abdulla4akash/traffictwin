# Replication of the dispatch-implementation ranking reversal

The twelve-run working-day replication reproduced the ordering
**common-target < ingress < sequential per-task placement in all four new
fleet draws**. The primary analysis excludes the previously inspected pilot.

| Infrastructure arm | Mean offered-task deadline attainment |
|---|---:|
| Ingress execution with deadline-aware admission | 88.88685% |
| Common-target least-busy with inherited deadline-aware admission | 85.65460% |
| Sequential per-task least-busy with inherited deadline-aware admission | 92.78537% |

The paired mean advantage of per-task over ingress was **3.89852
percentage points**. Common-target was **3.23225 points below
ingress**, and per-task was **7.13078 points above common-target**.

![Primary paired replication](figures/primary_replication.png)

*Figure 1. The left panel connects the three conditions within each fleet
draw. The right panel shows draw-level differences, their means and the
prespecified simultaneous intervals. The four new fleet seeds are 0, 2, 3
and 4; exploratory pilot seed 1 is excluded.*

## Design and uncertainty

The primary sample is four matched fleet draws, each evaluated under all
three arms. The full canonical Manchester working-day trace covers
15 October 2024, 08:00–11:00: 10,800 one-second steps, 215 padded vehicle
slots and nine RSUs. The frozen MAPPO actor, evaluator seed 0, UK2030 fleet
preset, task stream, canonical slot/entry convention and all resource
settings were fixed within each matched comparison. Capacity remained an
absolute 6,220 tasks per RSU, service 1×, forwarding cost 0 ms, arrival rate
1.5 and scaling off. Vehicle queues used per-visit resets. The inherited
common-target and per-task algorithms retained their respective three-pass
reconciliation semantics; the evaluator source was not modified.

The primary outcome includes every offered task in its denominator,
including rejected and unavailable tasks. The unit of replication is the
fleet draw. The intervals below use paired differences across the four
draws, with three degrees of freedom. The family intervals apply the
prespecified Bonferroni correction across all three contrasts.

| Paired contrast | Mean difference (pp) | Simultaneous 95% family interval (pp) |
|---|---:|---:|
| Per-task − ingress | +3.89852 | [+2.67129, +5.12575] |
| Common-target − ingress | -3.23225 | [-4.67178, -1.79273] |
| Per-task − common-target | +7.13078 | [+4.46611, +9.79544] |

Both signs needed for the historical reversal remain beyond zero in these
simultaneous intervals. This meets the criterion written before the new
outcomes were inspected. The intervals are small-sample parametric estimates,
conditional on assumptions about fleet-draw differences and on the fixed
scenario/task seed. They do not measure uncertainty across dates, traffic
generators or geographic settings. Individual tasks are not treated as
independent replications.

## Workload diagnostic

Common-target admitted work occupied RSUs 0–4 in the recorded runs. Its mean
work shares were approximately 48.34%, 30.33%, 14.63%, 5.21% and 1.48%,
respectively; RSUs 5–8 received no admitted compute work. Per-task placement
spread work almost evenly across all nine RSUs, about 11.1% each.

Mean V2I deadline-gate rejections per draw were 127,921 under common-target,
66,948.5 under ingress and 1,942 under per-task placement. These are diagnostic
averages across draws, not fractional tasks in an individual run. The
workload distributions are consistent with the observed advantage of the
per-task dispatch implementation under this one-second batched model.

![RSU workload distributions](figures/rsu_workload_distribution.png)

*Figure 2. Mean admitted service-work share at each RSU across the four new
draws. Whiskers show observed minima and maxima across draws, not inferential
intervals. The dashed line indicates equal allocation across nine RSUs.*

## Pilot and interpretation boundary

The positive seed-1 pilot influenced the decision to replicate, so its two
completed cells were preserved and excluded from primary inference. The
separate five-draw, two-arm descriptive summary gives a per-task-minus-ingress
mean of **+3.70941 pp**.
It is explicitly labelled as including the exploratory pilot. No common-target
pilot cell was added, inferred or imputed.

This replication strengthens evidence that dispatch implementation can
reverse the comparison with ingress in another Manchester operating scenario.
It does not establish independent geographical generalisation. The morning
and incident scenarios also differ in date/window, density, RSU layout/count,
slot assignment and entry-marker availability, so their effect-size difference
cannot be attributed to a single cross-scenario change. No physical backhaul
network or Kubernetes deployment was evaluated.

## Validation and evidence

All twelve preflight probes and twelve full runs passed the declared checks.
Within each draw, actor actions, task types/activity, fleet and ingress matched;
actor logits met the prespecified absolute 0.00001 tolerance. Task counts,
rejections, paths, workload ledgers and full-run prefixes passed. Independent
work reconstruction matched saved RSU queue endpoints exactly in all twelve
runs; task-count carry was exact, and every checked common target was a
minimum-workload RSU. Maximum absolute service-work balance error was below
0.002 ms across a full run, within the declared floating-point tolerances.

The runner took **41.43 minutes**, including probes, output handling,
validation and statistical analysis; preparation and figure production are
additional. Full evaluator compute time totalled
**36.88 minutes**.

The [prespecified protocol](PROTOCOL.md), [frozen manifest](manifest.json),
[complete results and individual intervals](RESULTS.md),
[per-draw comparisons](paired_differences.csv),
[RSU workload data](rsu_workload_distribution.csv),
[per-run rejection and energy data](runs.csv),
[task-type outcomes](task_types.csv),
[pilot-inclusive supplementary table](supplementary_five_draws.csv), and
[analysis receipt](analysis_validation.json) accompany this summary. Figures
are also available as [primary SVG](figures/primary_replication.svg) and
[workload SVG](figures/rsu_workload_distribution.svg).
