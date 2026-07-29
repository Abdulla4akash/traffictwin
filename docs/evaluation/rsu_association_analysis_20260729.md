# Why most deployed RSU capacity is unusable — the association rule is load-blind

**Status: exploratory, analysis-only, `owner_approved_candidate` ceiling. Descriptive and
non-causal. Not supervisor-approved, not confirmatory, no significance claimed. No run executed.**

Producer code and data use is covered by the recorded permission with citation — see
[citation requirements](../producer_citation_requirements.md).

## 1. What this revises

The [per-RSU load asymmetry analysis](rsu_load_asymmetry_20260728.md) found that some RSUs carry
no load at any capacity and that squeezing capacity does not redistribute. That measurement
stands. Its *interpretation* — recorded in the register as "placement, not capacity, binds" — is
what this revises. It is not placement.

Two array fields nothing had previously touched settle it: `veh_best_rsu`, which records the RSU
each vehicle selects, and `rsu_load`, the in-flight task count per RSU.

## 2. The idle RSUs are chosen, and empty

At `cap-2.5-fs60`, measured against the environment's own concurrency bound
`RSU_MAX_CONCURRENT = capacity × N_VEHICLES = 2.5 × 2,488 = 6,220`:

| RSU | selected as best | v2i sends | mean concurrent | utilisation |
|---|---|---|---|---|
| 0 | 1,554,341 | 244,076 | 6,091.7 | **97.9%** |
| 1 | 749,975 | 155,302 | 6,002.5 | **96.5%** |
| 2 | 797,632 | 150,692 | 5,964.6 | **95.9%** |
| 6 | 797,298 | 164,051 | 5,958.3 | **95.8%** |
| 3 | **810,931** | 106,196 | 176.5 | 2.8% |
| 5 | 672,870 | 84,323 | 37.5 | 0.6% |
| 9 | 732,556 | 81,273 | 2.9 | 0.0% |
| 4 | 377,855 | 85,109 | 0.5 | 0.0% |
| 7 | 191,887 | 45,520 | 0.0 | 0.0% |
| 8 | 111,077 | 22,939 | 0.0 | **0.0%** |

**Four RSUs run at 95.8–97.9% of the bound; four sit at 0.0%.** The four saturated ones carry
**99.1%** of all load.

The idle ones are not unreachable — RSU 3 is selected as best **more often than RSUs 1, 2 or 6**
and carries 2.8% of their load. They are not full — they are empty. They receive tens of
thousands of `v2i` sends and accumulate nothing.

**And it is not the tier partition either.** Tier-0's share of the vehicles selecting each RSU is
essentially uniform (0.375–0.435 across all ten), and its correlation with total load is +0.31
over ten points — nothing. That hypothesis was tested and rejected before this one was adopted.

## 3. The mechanism, from the producer's source

`jaxmarl/env/vec_jax.py`:

```python
best_rsu_idx = jnp.argmax(all_v2i_q, axis=1)     # line 747
```

**Association is the argmax of link quality. There is no load term in it.** Out-of-range RSUs are
zeroed (`q = jnp.where(in_range, q, 0.0)`), so the choice is over reachable RSUs by signal
strength alone. The environment even computes `best_rsu_load_frac` — but for the *observation*,
not for the association.

So offered work concentrates on whichever RSUs happen to present the best links, and **keeps
concentrating there after they saturate**, because nothing in the selection ever notices. The
adjacent, reachable, empty infrastructure is never preferred.

## 4. It survives a 25× capacity squeeze

| Cell | bound | saturated | idle | load on saturated |
|---|---|---|---|---|
| `cap-2.5-fs60` | 6,220 | 4 | 6 | 99.1% |
| `cap-0.1-fs60` | 249 | 4 | 4 | 92.7% |
| `cap-2.5-fs0` | 6,220 | 4 | 5 | 91.4% |

The *same four* RSUs saturate at both capacities and on a different seed. Squeezing capacity 25×
lowers the bound but does not move which RSUs the work goes to — which is exactly why the earlier
analysis saw no redistribution.

## 5. Why this matters more than the placement reading

Under a placement reading the remedy is civil engineering: move the masts. Under this reading the
remedy is **a load-aware association rule** — a software change, testable in the existing
environment, with 60% of the deployed infrastructure already in range and idle.

It also relocates the capacity finding. The tail-latency ceiling law lives in the RSU queue, and
that queue is effectively **four RSUs**, not ten. Every capacity number in this project is a
statement about the four saturated RSUs the association rule happens to favour.

## 6. Limits

- One trace (`inc`), one producer environment, one actor; three cells analysed.
- `veh_best_rsu` is read as the association the environment records. That it is `argmax` of link
  quality is read from producer source, not re-derived by instrumenting a run.
- Whether a load-aware rule would actually improve outcomes is **not tested here**. It is a
  hypothesis this measurement motivates, not a result.
- Utilisation uses the producer's own `capacity × N_VEHICLES` bound; no independent estimate of
  RSU service capability is made.

Reproduced by `scripts/analyse_rsu_association.py`; evidence at
`data/rsu-association-20260729/rsu_association.json`.
