# Capacity-onset scaling result — predeclared exact-equality verdict: REFUTED

**Status: exploratory, `owner_approved_candidate` ceiling. Not supervisor-approved, not
confirmatory, no significance claimed. Fresh seeds {60, 61, 62}; held-out seeds {10–14} were
not touched.**

The onset definition, density-proportional prediction, six sharp checks and binary verdict were
frozen in the [predeclaration addendum](onset_scaling_prediction_predeclaration.md) before any
cell of the three tested legs ran. The committed verdict code re-hashed that addendum and the
campaign-bound source memo before reading the completed analyses.

## Verdict

**REFUTED — four of six sharp predictions correct, two wrong.** The load-bearing prediction
that weekday-AM binds at cap-0.1 held, but the prediction also required both weekend and
weekday-PM to remain exactly inert at cap-0.25. Each had a nonzero latency difference in one
seed, so both fail the predeclared exact-identity rule.

The measured-onset ordering qualifier is also false. On this grid the onsets are 0.25, 0.25,
0.1 and 0.1 for `we`, `wd_pm`, `ev` and `wd_am`, rather than increasing with padded slot count
139, 163, 175 and 215.

## Frozen rule and completed design

- Hypothesis: `c_onset = kappa × N`, propagated from event night's bracket
  `c_onset(ev) ∈ (0.1, 0.25]` without collapsing it to a point.
- Onset rule: an arm is inert only when every admitted metric at every seed equals cap-2.5
  exactly; any nonzero difference binds. The measured onset is the largest binding capacity.
- Tested traces: `we`, `wd_pm`, `wd_am`; 12/12 cells each, capacities 2.5/0.5/0.25/0.1 and
  seeds {60,61,62}. `ev` supplies the original bracket and is not counted as a test.
- All four campaign analyses report completed status. No tolerance was introduced after seeing
  the outputs.

## Observed onset table

| Trace | Slots | cap-0.5 | cap-0.25 | cap-0.1 | Measured onset |
|---|---:|---|---|---|---:|
| `we` | 139 | inert | **binds: latency only** | binds: completion + latency | 0.25 |
| `wd_pm` | 163 | inert | **binds: latency only** | binds: completion + latency | 0.25 |
| `ev` | 175 | inert | inert | binds: completion + latency | 0.1 |
| `wd_am` | 215 | inert | inert | binds: completion + latency | 0.1 |

The two cap-0.25 failures are numerically tiny and must be described precisely:

- `we`: seeds 60 and 61 are exactly identical to baseline; seed 62 latency is lower by
  **0.000242979 ms** (0.243 microseconds). Completion, offload and no-eligible-target rate are
  exactly identical at all three seeds.
- `wd_pm`: seeds 61 and 62 are exactly identical to baseline; seed 60 latency is lower by
  **0.000024348 ms** (0.024 microseconds). The other three metrics are exactly identical.

Those values are enough to refute the rule that was actually frozen. They are not evidence of
an operationally meaningful onset at 0.25. This distinction is not a post-hoc tolerance: the
binary verdict remains REFUTED, while the magnitude is reported so a reader can see that the
exact-equality definition is scientifically brittle at floating-point resolution.

## Cap-0.1 outcome scale

| Trace | Baseline completion | cap-0.1 completion | Change | Baseline latency ms | cap-0.1 latency ms | Change ms |
|---|---:|---:|---:|---:|---:|---:|
| `we` | 0.920365 | 0.920397 | +0.000031 | 55.353903 | 55.149112 | −0.204792 |
| `wd_pm` | 0.918405 | 0.918442 | +0.000037 | 56.090369 | 55.964687 | −0.125682 |
| `ev` | 0.934865 | 0.934876 | +0.000011 | 51.205190 | 51.180848 | −0.024342 |
| `wd_am` | 0.922483 | 0.922525 | +0.000043 | 55.074882 | 55.032406 | −0.042475 |

All four traces show the previously observed direction at cap-0.1: completion moves faintly
up and mean latency down. Offload rate and no-eligible-target rate remain exactly unchanged,
consistent with a policy that does not respond to capacity.

## Interpretation

The proposed proportional law does not explain the exact onset classification across these
normal-density traces. The predeclared ordering fails, not merely its calibrated constant.
However, the two sharp-check failures are sub-microsecond latency differences, while the
clearest visible response still starts at cap-0.1. The honest conclusion is therefore narrow:
**the exact-identity onset-scaling prediction is refuted; the coarse grid and brittle equality
rule do not establish that density is irrelevant.**

The load-bearing `wd_am` cap-0.1 prediction held, but it cannot replace the frozen all-six rule.
The result also reinforces that these low-density regimes are far from the collapse-hour
behaviour: even a 25× squeeze changes deadline completion by only 0.0011–0.0043 percentage
points and latency by 0.024–0.205 ms.

Verdict JSON is local at
`data/onset-scaling-verdict-20260729/onset_scaling_verdict.json`, sha256
`3c3d1abcec8f9d93c1c1bd89ad5845f12bd1ebf44deb161e1460d193a4c081ff`. Verdict code:
`scripts/verify_onset_scaling_prediction.py`. Analyses:
`data/vec-fresh/capacity-deep-{we,wd-pm,wd-am}/campaign_analysis.{json,md}`.
