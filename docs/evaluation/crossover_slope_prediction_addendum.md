# Predeclaration addendum — making crossover prediction (3) decidable

**Status: PROPOSED, exploratory. `owner_approved_candidate` ceiling. Not supervisor-approved,
not confirmatory, no significance claimed. Seeds {0, 1, 2}; the held-out cohort {10–14} is
spent and untouched.**

Written **before any cell of the `inc-baseline` crossover campaign had run** — at the time of
writing `data/vec-fresh/crossover-inc-baseline` holds 0 of 12 cells and the leg is still
queued behind `inc-deep`. Checkable against git history.

## 1. What is already decidable, and what is not

`actor_crossover_candidate_inc_20260728.md` §4 fixes the crossover rule itself, and that rule
is implemented and tested in the accepted `vec_campaign/slope_comparison.py`: a crossover is
claimed only if the winner order at the highest studied capacity reverses at the lowest, with
complete seed support at both. Nothing needs adding there.

Its §5 prediction (3) is different:

> If the ceiling is `≈ 39,959 ms × c` regardless of actor, both actors' mean-latency slopes
> should be close to proportional to capacity, and the *slope contrast* should be small even
> where the *level* contrast is not. A large slope difference between actors would be a genuine
> surprise […] **The interesting outcome here is a refutation of (3).**

"Small" and "large" are not decidable, and this is the prediction the candidate itself names as
the interesting one. Left as written, the threshold would be chosen after both curves are
visible. This addendum fixes it in advance.

**The candidate document is not edited.** It is byte-bound at `b8f0efa2…` into the launched
`inc-baseline` campaign design; moving it would break that campaign's approval check and its
resume.

## 2. The statistic

For each actor, the ordinary-least-squares slope of `task.latency.mean_ms` over capacity,
computed from that actor's own campaign analysis at the four shared levels
(2.5 / 1.5 / 1.0 / 0.75) — the same OLS the accepted module applies to the primary endpoint,
applied to the secondary latency series.

The contrast is reported **relative**, because the actors' absolute latency levels differ and
an absolute millisecond difference would not be interpretable:

    relative_slope_contrast = |slope_A − slope_B| / ((|slope_A| + |slope_B|) / 2)

Already measured and published for the admitted pilot actor
(`ukfleettrain_mappo_model_c_17`): **3,828.2 ms per capacity unit**. The second actor's slope
does not exist yet.

## 3. The band, transcribed

**Pass band: relative slope contrast ≤ 5%.**

The 5% is not chosen for this comparison — it is the tolerance the ceiling-law predeclaration
already fixed for the same underlying quantity, where it was deliberately set 12× wider than
the 0.41% spread the law was fitted at. Reusing it keeps the tolerance out of this document's
hands.

- **HELD** — relative slope contrast ≤ 5%. The latency response to capacity is actor-independent
  at this tolerance, consistent with a ceiling that is a property of the control.
- **REFUTED** — relative slope contrast > 5%. The latency response is actor-dependent, meaning
  the ceiling is not purely a property of the control. Per the candidate, this is the more
  interesting outcome and it reopens the mechanism.

If either campaign analysis is missing, or either curve lacks complete seed support at any
level, the result is **INCOMPLETE** and the gap is named. Missing support is never read as a
pass.

## 4. What a refutation would and would not establish

**The fleet preset matches one actor's training distribution and not the other's.** That
asymmetry is part of the design, stated in the candidate §7, and it means an actor-dependent
slope has at least two live explanations — the policy itself, or the preset mismatch — which
this comparison **cannot distinguish**. A refutation therefore establishes that the latency
slope is not actor-invariant under this design; it does not establish which of the two causes
produced it. Stated now so it cannot be quietly dropped from a report later.

Also binding, from the candidate's own limits: exploratory, descriptive, non-causal; a
statement about two audited checkpoints on one trace under one fleet preset, never about
algorithm families.

## 5. State at the time of writing (checkable against git)

| Fact | Value |
|---|---|
| `data/vec-fresh/crossover-inc-baseline` | 0 of 12 cells run; leg queued behind `inc-deep` |
| Candidate digest | `b8f0efa29f4c41210b44447595a53b2975e47af913f3057c1ac1e1540c885492` (unmodified) |
| Pilot actor slope | 3,828.2 ms per capacity unit (published) |
| Second actor slope | does not exist |
| Verdict code | `scripts/analyse_actor_crossover.py`, committed with this file |

## Sign-off

| Field | Value |
|---|---|
| Proposed by | primary research/integration agent |
| Approved by | *(relayed delegation, recorded at execution; not an owner-typed signature)* |
| Supervisor approval | **none — not sought, not implied** |
