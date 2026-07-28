# Actor crossover study — prepared candidate, incident trace

**Status: PROPOSED, exploratory, `owner_approved_candidate` ceiling. Not supervisor-approved,
not confirmatory, no significance claimed. Fills
[the crossover draft](actor_crossover_study_draft.md) with measured values and resolves G6.
Approval provenance is relayed owner delegation, never an owner-typed signature.**

## 1. Why the incident trace, and only the incident trace

The draft left the capacity levels as `FILL-FROM-PILOT`. The completed sweep now settles
something stronger: **a crossover is only possible on `inc`.**

On `we`, `ev`, `wd_am` and `wd_pm` every metric is *exactly* identical across all capacity
arms — paired differences of literally 0.000000. If nothing about an actor's outcome changes
with capacity, no ordering between two actors can change with capacity either. A crossover
study on those traces is not a null result; it is structurally impossible, and running one
would be theatre.

`inc` is the only regime where capacity moves outcomes at all, so it is the only place the
question "does the winner at comfortable capacity lose under squeeze?" has content.

## 2. What already exists, and what this adds

| Actor | Trace | Arms | Seeds | Status |
|---|---|---|---|---|
| `ukfleettrain_mappo_model_c_17` | `inc` | 2.5 / 1.5 / 1.0 / 0.75 | {0, 1, 2} | **already admitted** — the completed capacity pilot |
| `baseline_model_c_17` | `inc` | 2.5 / 1.5 / 1.0 / 0.75 | {0, 1, 2} | **this campaign**, 12 cells |

The drafted design was 2 actors × levels × 5 seeds ≈ 20 runs across two overnight campaigns.
Mirroring the pilot exactly instead — same trace, same arms, same seeds, same fleet preset,
same evaluator seed — means **the pilot is one arm of the contrast and only 12 new cells are
needed**, roughly 12 hours rather than 20. Nothing about the pilot is re-run or altered.

A free second data point already exists on `ev`: B0 ran `baseline_model_c_17` over the same
arms and seeds as the `ev` grid leg. It is reported alongside as the inert-regime control,
where the predicted answer is "no crossover, because nothing moves".

## 3. G6 resolved

The draft left the cross-actor comparison method open because STA-01 cannot express an
actor contrast and STA-02 carries a single-checkpoint constraint. **G6 is resolved to the
already-proposed slope method**, implemented in the accepted
`vec_campaign/slope_comparison.py`: per-actor ordinary-least-squares capacity slopes derived
from each campaign's own analysis descriptives, with per-level winners and the binary
crossover rule gated on complete seed support. The alternative — descriptive comparison of
separately estimated per-actor curves — is reported beside it, never instead of it.

Recorded as a delegated resolution, not an owner-typed signature.

## 4. Crossover rule, fixed before any cell runs

A crossover is claimed **only** if, on this study's own seeds, the winner order of the two
actors at the **highest** studied capacity (2.5) is the reverse of the winner order at the
**lowest** (0.75), on the primary metric, with complete seed support at both levels.
Anything else is reported descriptively and is not a crossover.

**Publishable null, fixed now:** "the same actor wins at every studied capacity" is a
complete and publishable result.

## 5. What this study predicts, given everything now known

The mechanism has been measured on five independent legs, and the pilot dynamics analysis
adds two more constraints. Stating the expectation in advance:

1. **A crossover is unlikely.** Both actors are capacity-invariant in their decisions — B0
   established this for `baseline_model_c_17` directly. If neither actor's policy responds
   to capacity, their ordering is unlikely to invert with it.
2. **The likely finding is a level shift, not a rotation**: one actor better at every
   capacity, by roughly the margin B0 already measured on `ev` (ukfleettrain slightly better
   on deadlines and latency; baseline offloading about 4 pp more).
3. **The ceiling law predicts the latency slopes.** If the ceiling is `≈ 39,959 ms × c`
   regardless of actor, both actors' mean-latency slopes should be close to proportional to
   capacity, and the *slope contrast* should be small even where the *level* contrast is not.
   A large slope difference between actors would be a genuine surprise and would mean the
   ceiling is actor-dependent — which the pilot analysis says it is not, within 0.41%.

**The interesting outcome here is a refutation of (3).** That would show the ceiling is a
property of the policy rather than of the control, and would reopen the mechanism.

## 6. Design

| | |
|---|---|
| Trace | `traces/trace_inc_fullrsu.npz`, sha256 `e188ce07…` (audited, ADR-062) |
| Steps | 3,600 |
| Actor | `baseline_model_c_17` (the second audited actor; contrast is the admitted pilot) |
| Arms | baseline cap-2.5; variations cap-1.5, cap-1.0, cap-0.75 — identical to the pilot |
| Seeds | {0, 1, 2} — identical to the pilot, so the contrast is seed-paired |
| Fleet preset / evaluator seed | `uk2030` / `0` — identical to the pilot |
| Cells | 12, ~59 min each, ≈ 12 h |
| Phase | pilot / exploratory; `held_out_authorised` = **False** |
| Primary metric | `tos.task.deadline_success.rate` |

## 7. Interpretation limits binding on any output

- The fleet preset matches one actor's training distribution and not the other's. **This
  asymmetry is stated in every report** — it is part of what is being tested, not a flaw
  quietly carried.
- Exploratory: no significance is claimed and nothing is confirmatory.
- Held-out seeds {10–14} remain spent and are not touched.
- Capacity is the predeclared per-vehicle RSU control, never physical infrastructure.
- A crossover, if found, is a statement about two audited checkpoints on one trace under one
  fleet preset — never about algorithm families.

## Sign-off

| Field | Value |
|---|---|
| Proposed by | primary research/integration agent |
| Approved by | *(relayed delegation, recorded at execution; not an owner-typed signature)* |
| Supervisor approval | **none — not sought, not implied** |
