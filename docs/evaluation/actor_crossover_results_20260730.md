# Actor crossover result — no reversal, but latency-slope prediction refuted

**Status: exploratory, `owner_approved_candidate` ceiling. Not supervisor-approved, not
confirmatory, no significance claimed. Held-out seeds {10–14} remain spent and untouched.**

The crossover rule was frozen in the
[incident-trace candidate](actor_crossover_candidate_inc_20260728.md), and the 5% rule making
prediction (3) decidable was frozen in the
[slope addendum](crossover_slope_prediction_addendum.md) before the second actor produced a
cell. The committed analysis runner re-hashed both documents before applying those rules.

## Two separate verdicts

1. **Crossover: not detected.** The trained `ukfleettrain_mappo_model_c_17` actor has higher
   mean deadline completion than `baseline_model_c_17` at every capacity. The winner at
   cap-2.5 is therefore still the winner at cap-0.75, with complete three-seed support.
2. **Prediction (3), actor-independent latency slope: REFUTED.** The trained actor's mean-
   latency slope is +3,828.2 ms per capacity unit and the baseline actor's is +6,555.4 ms.
   Their frozen relative contrast is **52.53%**, more than ten times the predeclared ≤5% band.

These answers are compatible: the trained actor retains a nearly constant completion advantage,
so there is no winner reversal, while its latency response rotates materially less steeply than
the baseline actor's.

## Design and provenance

| Property | Value |
|---|---|
| Trace | `inc`, the modelled collapse-hour trace |
| Capacities | 2.5, 1.5, 1.0, 0.75 |
| Seeds | {0, 1, 2}, common to both actors |
| Fleet / evaluator seed | `uk2030` / 0 |
| Trained actor source | Existing admitted capacity-pilot analysis; no rerun |
| Baseline actor source | `vec-crossover-inc-baseline`, 12/12 completed cells, design fingerprint `4784f5fc…` |
| Primary metric | `tos.task.deadline_success.rate` |
| Secondary prediction statistic | OLS slope of `task.latency.mean_ms` over capacity |
| Crossover rule | Winner reverses between highest and lowest capacity with complete support |
| Prediction (3) rule | HELD if relative latency-slope contrast ≤5%, otherwise REFUTED |

The generated verdict JSON is local at
`data/actor-crossover-verdict-20260729/actor_crossover_verdict.json`, sha256
`9d3d73060a0299f421ad6a65dd43baba79de0e99db575aed58672609b71e58da`. The baseline campaign
analysis sha256 is `a87c613125f2bbcb8d39b71245dbfaf26beda7bab3665d6689a0b642ce2156df`.

## Per-capacity results

| Capacity | Trained completion | Baseline completion | Trained − baseline | Trained latency ms | Baseline latency ms | Baseline − trained latency ms |
|---:|---:|---:|---:|---:|---:|---:|
| 2.5 | 0.790412 | 0.729576 | +0.060835 | 9,798.842 | 16,629.512 | +6,830.670 |
| 1.5 | 0.790522 | 0.729576 | +0.060946 | 6,029.587 | 10,177.820 | +4,148.234 |
| 1.0 | 0.790591 | 0.729694 | +0.060898 | 4,089.868 | 6,840.603 | +2,750.735 |
| 0.75 | 0.790737 | 0.729807 | +0.060930 | 3,083.603 | 5,138.898 | +2,055.296 |

The trained actor's completion advantage stays between 6.0835 and 6.0946 percentage points.
Both actors improve slightly in completion as the capacity control is squeezed, and neither
changes its offload rate with capacity. Across every arm the trained actor offloads 0.407713 of
tasks and the baseline actor 0.469997, a 6.2284 percentage-point difference.

The primary completion OLS slopes are −0.000164 and −0.000117 per capacity unit for the trained
and baseline actors respectively. Those small slopes do not reverse the winner. The secondary
latency slopes differ by 2,727.2 ms per capacity unit; the symmetric relative contrast is
52.528%.

## Interpretation

The publishable null for the crossover question is observed: **the trained actor wins at every
studied capacity** on this trace and fleet preset. Squeezing the concurrency control does not
make the untrained baseline overtake it.

Prediction (3) does fail. The latency ceiling is not actor-invariant at the frozen 5% tolerance
under this design. The baseline actor offloads more traffic and has both a higher latency level
and steeper capacity response; that is compatible with greater exposure to the RSU queue, but
the aggregate outputs do not establish that mechanism.

Most importantly, the `uk2030` fleet preset matches the trained actor's training distribution
and not the baseline actor's. The observed slope difference therefore has at least two live
explanations — checkpoint policy or actor/preset mismatch — and this experiment cannot separate
them. It is a comparison of two audited checkpoints on one trace under one preset, not an
algorithm-family result and not a causal estimate.

Verdict code: `scripts/analyse_actor_crossover.py`. Campaign analysis:
`data/vec-fresh/crossover-inc-baseline/campaign_analysis.{json,md}`.
