# The tail-latency ceiling law survives extrapolation — pre-registered verdict: HELD

**Status: exploratory, `owner_approved_candidate` ceiling. Not supervisor-approved, not
confirmatory, no significance claimed. Held-out seeds {10–14} were not touched; this used fresh
seeds {60, 61, 62}.**

The prediction, the ±5% band and the HELD / REFUTED / BOUNDED rule were frozen in
[the predeclaration](ceiling_law_prediction_predeclaration.md) (digest `78dcd3ce…`) **before any
cell ran**, and the code computing the verdict was committed while the campaign stood at 2 of 12
cells. Producer code and data use is covered by the recorded permission with citation — see
[citation requirements](../producer_citation_requirements.md).

## 1. Verdict

**HELD — 27 of 27 (arm × class × seed) pairs inside the band, none outside.**

Campaign `vec-capacity-deep-inc`: 12/12 cells admitted, 18.4 h compute, design fingerprint
`5331e5207ef2eae2…` as launched.

The law was fitted across the pilot's 3.3× capacity range. These arms sit **7.5× below its
fitted floor and 25× below its baseline**, and it still predicts the ceiling to within 5% —
in fact to within 3.5% at the worst pair.

| Arm | Predicted ceiling | Mean observed K (9 pairs) | Fitted K |
|---|---|---|---|
| cap-0.5 | 19,980 ms | 40,157.4 | 39,959 |
| cap-0.25 | 9,990 ms | 40,308.6 | 39,959 |
| cap-0.1 | 3,996 ms | 40,715.9 | 39,959 |

The in-range reference arm reproduces the constant at three fresh seeds: K = 39,878–40,146
across all nine cap-2.5 measurements, against a fitted 39,959.

## 2. The law sags, systematically, and that is the interesting part

Relative error against prediction, all 27 pairs:

| Arm | Class | seed 60 | seed 61 | seed 62 | mean |
|---|---|---|---|---|---|
| 0.5 | T1 | +0.37% | +0.14% | −0.09% | +0.14% |
| 0.5 | T2 | +1.25% | +1.09% | +0.89% | **+1.08%** |
| 0.5 | T3 | +0.47% | +0.27% | +0.05% | +0.27% |
| 0.25 | T1 | +0.77% | +0.48% | +0.05% | +0.43% |
| 0.25 | T2 | +1.93% | +1.75% | +1.49% | **+1.73%** |
| 0.25 | T3 | +0.76% | +0.48% | +0.13% | +0.46% |
| 0.1 | T1 | +1.94% | +1.37% | +0.59% | +1.30% |
| 0.1 | T2 | +3.79% | +3.44% | +3.02% | **+3.42%** |
| 0.1 | T3 | +1.49% | +0.95% | +0.43% | +0.96% |

Three structures repeat on every seed:

1. **Error grows monotonically as capacity falls**, for all three classes — T2 runs +1.08% →
   +1.73% → +3.42% across a 5× reduction. The law does not fail; it *sags*, and it sags further
   the further it is extrapolated.
2. **T2 carries the largest error at every one of the nine arm × seed combinations.** T2 is the
   500 ms class; T1 and T3 are 100 ms. Their relative order is *not* stable — T3 exceeds T1 at
   cap-0.5 and the order inverts at cap-0.25 and cap-0.1 — so only the T2 result should be
   claimed.
3. **A consistent seed ordering**, 60 > 61 > 62 in every one of the nine rows. Seeds shift the
   level of the sag but not its shape.

**The predeclared BOUNDED outcome sits just below the tested range.** At cap-0.1 the T2 error
averages +3.42% against a ±5% band, and the trend is still rising. One further halving of
capacity would plausibly break the law — and locating *where* it breaks is a distinct finding
the predeclaration already names.

## 3. Secondary predictions

**Decision partition identical across arms within each seed — held, all three seeds.** Consistent
with the [offload-partition analysis](offload_partition_analysis_20260729.md), which found the
partition is a lookup on vehicle compute tier and therefore cannot respond to capacity.

**Deadline attainment may move at cap-0.1, upward — held, and it moved on all three seeds.**

| Seed | cap-2.5 | cap-0.1 | change |
|---|---|---|---|
| 60 | 0.787221 | 0.787708 | +0.000487 |
| 61 | 0.776630 | 0.780791 | +0.004161 |
| 62 | 0.785754 | 0.787602 | +0.001848 |

Always upward, as the predeclaration fixed in advance as the unsurprising direction; a fall would
have contradicted every prior arm. Magnitudes are small and vary ~8× across seeds — the
[effect decomposition](offload_partition_analysis_20260729.md) attributes that to how much the
tier-0 population gained, diluted by its ~41% share.

**p50 latency stays ~44 ms — partially held.** Measured 44.6–44.9 ms on seeds 60 and 62, but
**45.7–46.2 ms on seed 61**, about 4% above the predicted value and drifting slightly with
capacity there. Recorded as a partial miss on a loosely-stated secondary prediction, not as a
pass.

## 4. What the result means, and what it does not

The law's status changes from *a regularity found after the fact, inside the range that produced
it* to *a relation with predictive content outside that range*. That is the whole reason the test
was worth 18 hours.

But its scope is narrower than "the system obeys `L(c) = K·c`". The
[effect decomposition](offload_partition_analysis_20260729.md) shows the ceiling is a property of
**the RSU queue**: locally-executing vehicles show no capacity relationship at all, with p95 of
missed latency bit-identical across a 25× squeeze. The pooled measurement recovers the law only
because ~92% of missed tasks belong to the offloading population. So this is a confirmed law
about one subsystem, exercised by ~40% of the fleet.

Also binding: one trace (`inc`, the modelled collapse hour), one actor, one producer environment.
Nothing here is confirmatory and no significance is claimed.

Verdict computed by `scripts/verify_ceiling_law_prediction.py`; evidence at
`data/ceiling-law-verdict-20260729/final/ceiling_law_verdict.json`. Campaign analysis at
`data/vec-fresh/capacity-deep-inc/campaign_analysis.{json,md}`.
