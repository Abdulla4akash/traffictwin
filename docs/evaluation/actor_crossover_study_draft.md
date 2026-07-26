# Actor Crossover Study — DRAFT (NOT SIGNABLE YET)

**Status: structural draft; cannot be signed, approved, or executed in this form.** Fields
marked `FILL-FROM-PILOT` require the completed capacity pilot's measured values. This is the
predeclared design for the dissertation's "expected winner loses" question, fixed in structure
before any evidence about actor ordering exists.

- Drafted: 26 July 2026, before any pilot cell completed
- Decision provenance: pilot predeclaration D5 (owner delegation, 26 July 2026) selected
  **N-way ranking per capacity level** as the crossover method
- Policy label ceiling: `owner_approved_candidate`

## 1. Question and why STA-01 cannot answer it

**Question.** Does the actor that wins at comfortable capacity lose under squeeze — i.e. does
the deadline-success ranking of `baseline_model_c_17` versus `ukfleettrain_mappo_model_c_17`
invert between capacity levels on the incident trace?

**Method constraint, recorded from the tooling.** STA-01's paired design carries a single
`algorithm`, so an actor-versus-actor contrast is structurally not an STA-01 paired study.
The predeclared method is therefore the accepted **N-way ranking** machinery evaluated
separately at each capacity level, with actors as the ranked policies and fleet seeds as the
common replicates.

**Crossover rule (fixed now).** A crossover is claimed only if, on the study's own seeds, the
winner-map order of the two actors at the **highest** studied capacity is the reverse of the
order at the **lowest** studied capacity, and each of those two rankings is supported by its
level's complete common-seed set with no missing replicate. Any weaker pattern — partial
flips at interior levels, ties, incomplete seed coverage — is reported descriptively and is
**not** called a crossover.

**Publishable null (fixed now).** "The same actor wins at every studied capacity" is a
reportable outcome of equal standing: it would say the training-distribution advantage
survives resource pressure, which contradicts the distribution-shift motivation and is
therefore itself a finding.

## 2. Design

| Factor | Value |
|---|---|
| Trace | `inc` (`e188ce07…`) — unchanged from the pilot |
| Actors | `baseline_model_c_17` and `ukfleettrain_mappo_model_c_17` — both, that being the point |
| Fleet preset / evaluator seed | `uk2030` / `0` — held fixed; note this matches one actor's training distribution and not the other's, which is part of what is being tested and must be stated in every report |
| Capacity levels | `FILL-FROM-PILOT`: the pilot baseline (2.5) plus the confirmatory knee level; a third interior level only if the pilot shows a non-monotonic region |
| Seeds | fresh set, disjoint from pilot `{0,1,2}` and held-out `{10–14}`; proposed `{20, 21, 22, 23, 24}`, fixed at signing |
| Endpoint | `tos.task.deadline_success.rate` — unchanged; secondaries descriptive only |
| Runs | 2 actors × levels × 5 seeds; re-cost at signing from the measured 3,555.96 s figure (2 levels ⇒ 20 runs ≈ two overnight campaigns) |

## 3. Execution and analysis, fixed in structure

- Two campaigns (one per actor) over identical levels and seeds, each approval-gated against
  this document's final digest; or one campaign per actor per level if partitioning is needed
  for the runtime budget — the partition choice is made at signing, never mid-run.
- Admission through the fresh-run policy as usual; each actor's cells carry its own
  `algorithm`, which is exactly why ranking rather than pairing is the method.
- N-way ranking with tool defaults at each level; winner maps, rank uncertainty, and regret
  reported verbatim. No significance language; the crossover rule of §1 is the only claim
  gate, and it is binary and predeclared.
- Exclusions and missing cells reported as in the pilot; a level with incomplete seed
  coverage cannot support a crossover claim by the rule above.

## 4. Interpretation limits binding on any output

- A crossover, if found, is descriptive for this trace, fleet preset, and capacity control;
  it is not causal, not a training-quality verdict, and not generalisable beyond the studied
  grid.
- The fleet preset matching one actor's training distribution is a stated asymmetry of the
  design, not a bug discovered afterwards.
- Forbidden labels remain forbidden; supervisor approval is not claimed.

## 5. Signing checklist (a person completes every line)

- [ ] Pilot analysed; capacity levels filled by the confirmatory protocol's knee arithmetic.
- [ ] Seed set fixed and confirmed disjoint from pilot and held-out sets.
- [ ] Runtime re-costed; owner accepts the wall-clock commitment (~two overnight campaigns).
- [ ] Campaign partitioning chosen and recorded.
- [ ] Approval recorded binding this document's final SHA-256.
