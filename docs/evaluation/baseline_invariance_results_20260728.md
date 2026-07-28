# Baseline-Actor Invariance Prediction Test (B0) — Results (28 July 2026)

**Status: exploratory `owner_approved_candidate` evidence from the predeclared B0 test
([predeclaration](baseline_invariance_prediction_predeclaration.md), digest `fe3db753…`,
design fingerprint `2f4e371b…`); descriptive, non-causal. The verdict rule was fixed
before execution.**

- Execution: 12/12 cells admitted, zero failures — `baseline_model_c_17` on the
  event-night trace, arms {2.5, 1.5, 1.0, 0.75}, seeds {50, 51, 52} (identical fleets to
  the grid's ev leg by design).

## Verdict: the prediction HOLDS

The observability-gap mechanism predicted that the **baseline actor** — sharing the same
observation design — would be exactly as capacity-invariant as the ukfleettrain actor.
Measured: **every metric is exactly identical across all four capacity arms in every
seed** (paired differences literally 0.000000 with [0, 0] intervals): deadline success
0.928651, mean latency 53.03 ms, offload rate 0.426517 (means over seeds). Per the
predeclared rule, the prediction holds. The mechanism claim now rests on four independent
legs: the pilot's keyed action identity, the located observation-space gap, a
from-scratch GPU-trained control, and a second audited actor.

## Free descriptive actor contrast (identical fleets, ev trace, no ranking claim)

| Actor | Deadline success | Mean latency | Offload rate |
|---|---|---|---|
| `ukfleettrain_mappo_model_c_17` (grid ev leg) | 0.934865 | 51.21 ms | 0.386845 |
| `baseline_model_c_17` (this test) | 0.928651 | 53.03 ms | 0.426517 |

Descriptively, on identical fleets in the unsaturated event-night regime: the
ukfleettrain actor completes slightly more deadlines with slightly lower latency while
offloading less; the baseline actor offloads noticeably more (+4.0 pp). No winner claim —
that is the predeclared crossover study's question, on the saturated trace, under its own
signing.

## Limitations

One trace regime (unsaturated), three seeds, two actors of one architecture family;
exploratory forever; per the predeclaration, no pooling and no ranking.
