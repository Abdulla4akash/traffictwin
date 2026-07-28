# Predeclaration — the tail-latency ceiling law, tested by prediction

**Status: PROPOSED, exploratory. `owner_approved_candidate` ceiling. Not supervisor-approved,
not confirmatory, no significance claimed. Held-out seeds {10–14} are spent and are not
touched; this uses fresh seeds {60, 61, 62}.**

Predeclared **before** any deep-squeeze cell runs on the incident trace. The prediction, the
tolerance and the verdict rule below are fixed in advance, exactly as the B0 baseline-actor
prediction test was, and the result publishes whichever way it falls.

## 1. What the pilot measured

Analysis of all 12 admitted pilot cells
([record](pilot_dynamics_analysis_20260728.md)) found that missed tasks pile against a
ceiling, and that the ceiling is **linear in per-vehicle RSU capacity**:

> p95 latency of missed tasks ÷ capacity = **39,959 ms**, standard deviation **166 ms**,
> relative spread **0.41%**, across all 36 (cell × task-class) pairs at capacities
> 2.5 / 1.5 / 1.0 / 0.75 and seeds {0, 1, 2}.

Written as a law:

> **L(c) ≈ K · c, with K = 39,959 ms per unit capacity.**

This is an *interpolation* across a 3.3× range. It has never been tested outside it, and a
law fitted inside a range is worth exactly nothing until it predicts outside one.

## 2. The prediction

Extending the squeeze to 0.5 / 0.25 / 0.1 — a further 7.5× below the pilot's floor, and 25×
below its baseline — the law predicts, **before any cell runs**:

| Arm | Capacity | Predicted ceiling L(c) = 39,959 · c |
|---|---|---|
| cap-2.5 (reference) | 2.5 | 99,898 ms |
| cap-0.5 | 0.5 | **19,980 ms** |
| cap-0.25 | 0.25 | **9,990 ms** |
| cap-0.1 | 0.1 | **3,996 ms** |

Measured as p95 of missed-task latency, per task class, exactly as in the pilot analysis.

## 3. Tolerance and verdict rule, fixed now

**Pass band: ±5% of the predicted ceiling**, i.e. observed p95 ÷ capacity must fall within
37,961 – 41,957 ms. The pilot's own spread was 0.41%, so ±5% is deliberately generous: it
lets the law fail honestly rather than being rescued by a wide band.

- **HELD** — all three deep arms fall inside the band, for all three task classes.
- **REFUTED** — any arm × class falls outside.
- **BOUNDED** — the law holds at cap-0.5 but fails at cap-0.25 and/or cap-0.1. This is
  recorded as a *distinct* outcome, not as a refutation: it would locate a lower bound below
  which the ceiling is no longer capacity-determined, which is itself a finding.

No outcome is a failure of the experiment. A refutation would be more interesting than a
confirmation, because the law is currently an unexplained empirical regularity.

## 4. Secondary predictions, also fixed now

1. **Decision partition unchanged.** The never/always/mixed offload split will be identical
   across all four arms within each seed, as it was at every pilot capacity. A change here
   would contradict the observability-gap mechanism on four prior legs.
2. **Deadline attainment may finally move at cap-0.1, and this is the one arm where it
   could.** At cap-0.1 the predicted ceiling is 3,996 ms — only 8× the T2 deadline of 500 ms
   and 40× the T1/T3 deadline of 100 ms, against 200–1,000× at pilot capacities. If deadline
   attainment is going to respond to capacity anywhere on this trace, this is where. **A
   rise in attainment at cap-0.1 is predicted as possible and is not a surprise; a fall would
   contradict every prior arm.**
3. **p50 latency stays ~44 ms** at every arm, as it did across the whole pilot squeeze.

## 5. Design

| | |
|---|---|
| Trace | `traces/trace_inc_fullrsu.npz`, sha256 `e188ce07…` (audited, ADR-062) |
| Steps | 3,600 (full collapse hour) |
| Actor | `ukfleettrain_mappo_model_c_17` |
| Arms | baseline cap-2.5; variations cap-0.5, cap-0.25, cap-0.1 |
| Seeds | **{60, 61, 62}** — fresh; the held-out cohort {10–14} is spent and untouched |
| Cells | 12 (4 arms × 3 seeds), ~59 min each, ≈ 12 h |
| Pairing | `fleet_seed` |
| Primary metric (campaign) | `tos.task.deadline_success.rate` — unchanged from the pilot |
| Ceiling measurement | analysis-only, post hoc, over the admitted cells' per-task arrays |
| Phase | pilot / exploratory; `held_out_authorised` = False |

The campaign's own primary metric stays the predeclared deadline rate so the design is
directly comparable to the pilot; **the ceiling test is a separate analysis-only measurement
over the same admitted artifacts** and claims no significance.

## 6. Why this is worth 12 hours

The capacity programme is otherwise closed. Its central result — a large confirmed latency
reduction with a flat deadline null — is currently explained by a regularity discovered
*after* the fact, inside the range that produced it. Testing that regularity outside its
range is the difference between a post-hoc description and a mechanism with predictive
content. If the law holds at 25× below baseline it becomes the quantitative statement of the
whole finding; if it breaks, where it breaks is the more interesting result.

## 7. Boundaries

- Exploratory; no significance claimed; nothing here is confirmatory.
- Held-out seeds {10–14} stay spent and untouched; `held_out_authorised` is False.
- The `inc` trace remains the audited artifact; nothing is re-derived or modified.
- Capacity is the predeclared per-vehicle RSU capacity control, never a claim about physical
  infrastructure.
- Approval provenance is relayed owner delegation, **never an owner-typed signature**.

## Sign-off

| Field | Value |
|---|---|
| Proposed by | primary research/integration agent |
| Approved by | *(relayed delegation, recorded at execution; not an owner-typed signature)* |
| Supervisor approval | **none — not sought, not implied** |
