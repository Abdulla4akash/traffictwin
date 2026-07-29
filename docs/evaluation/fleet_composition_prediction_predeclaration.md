# Predeclaration — is deadline attainment a property of the fleet, not the algorithm?

**Status: PROPOSED, exploratory. `owner_approved_candidate` ceiling. Not supervisor-approved,
not confirmatory, no significance claimed. Written before any run of this design exists, and
before any decision to run it — the prediction below is worth recording whether or not the
campaign is ever executed.**

Held-out seeds {10–14} are spent and untouched.

## 1. The claim under test

The [offload-partition analysis](offload_partition_analysis_20260729.md) found that the trained
policy partitions vehicles by compute tier and that the two halves have very different outcomes.
It concluded that the project's headline "≈79% deadline attainment" is a **fleet-composition
artifact** — a property of the tier mix rather than of the algorithm.

That conclusion was reached by *decomposing the data that produced it*, which is exactly the kind
of reasoning that deserves a prediction test rather than a second look at the same arrays.

## 2. The prediction, derived before running

Every campaign so far used the `uk2030` fleet preset. The evaluator implements six others, and
`synthetic` — the fleet the actor was **trained** on — carries nearly double the tier-0 share:

| Preset | tier_probs (tier0, tier1, tier2) | EV |
|---|---|---|
| `uk2030` | 0.40 / 0.35 / 0.25 | 0.22 |
| `synthetic` | **0.70** / 0.25 / 0.05 | 0.30 |

Measured per-group attainment at `cap-2.5`, both available seeds:

| Seed | tier-0 (always-offload) | tier-1/2 (never-offload) | mixed |
|---|---|---|---|
| 60 | 0.5103 | 0.9720 | 0.9552 |
| 61 | 0.4926 | 0.9715 | 0.9448 |

If attainment is a mixture of these two populations weighted by fleet composition, then holding
the actor, trace, capacity and seeds fixed and changing **only** the fleet preset gives:

> **Predicted `synthetic` fleet attainment = 0.70 × 0.50 + 0.30 × 0.97 ≈ 0.65**

against a measured `uk2030` attainment of **0.787**. A drop of roughly **14 percentage points
from fleet composition alone**, with no change to the algorithm.

**Pass band: ±0.03 absolute** (0.62 – 0.68), chosen to be wide enough that the mixture model is
not credited for a lucky point estimate — the per-tier rates themselves vary by ~0.02 between
seeds, so a tighter band would be measuring noise.

## 3. Verdict rule, fixed now

- **HELD** — mean attainment across seeds falls inside 0.62–0.68.
- **REFUTED** — it falls outside. Attainment is then *not* a simple mixture of the two tier
  populations, and something about the policy or the environment responds to fleet composition
  in a way the decomposition missed. That would be the more interesting outcome, and it would
  weaken the "fleet-composition artifact" framing that is currently headed for the write-up.

Reported alongside, not as gates: per-tier attainment under the new mix (do the two populations
keep their own rates, or do they shift?), and whether the tier partition itself still holds at
100% under a fleet where tier-0 is the majority.

## 4. The second question this answers for free

`synthetic` is the **training** fleet. Every result in this project evaluates the actor on
`uk2030`, i.e. off its training distribution. Running `synthetic` moves it *closer* to where it
was trained, which speaks directly to the distribution-shift concern the producer's Year-1 report
raised and which this project inherited.

Note the prediction is agnostic about this: it assumes the per-tier rates carry over unchanged.
If the actor performs *better* per-tier on its training fleet, attainment will land above the
band and the prediction fails — for an interesting reason. That possibility is named here in
advance rather than offered as an explanation afterwards.

## 5. Design

| | |
|---|---|
| Trace | `traces/trace_inc_fullrsu.npz` (audited, ADR-062) |
| Actor | `ukfleettrain_mappo_model_c_17` — unchanged |
| Capacity | cap-2.5 only; the question is about fleet, not capacity |
| Fleet | `synthetic` (contrast: the admitted `uk2030` cells) |
| Seeds | {60, 61, 62} — matching the deep campaign, so the contrast is seed-paired |
| Cells | 3 |
| Interface | `fleet` is a parameter of `VecRunRequest`, an **accepted** interface — no patched evaluator, no code transform |

## 6. Limits

- One trace, one actor, one capacity level.
- Fleet presets are a **modelling assumption** in the producer (`per-country fleet composition
  presets … tied to fleet-modernity proxies, not a measured statistic`), so this tests the
  mixture model, not any claim about real UK or synthetic vehicle populations.
- Changing fleet changes EV share too (0.22 → 0.30), which is not controlled. EV share showed no
  relationship with tier or outcome in the partition analysis, but it is a confound and is named.
- Exploratory; nothing here is confirmatory and no significance is claimed.

## Sign-off

| Field | Value |
|---|---|
| Proposed by | primary research/integration agent |
| Approved by | *(not approved; no decision to run has been taken)* |
| Supervisor approval | **none — not sought, not implied** |
