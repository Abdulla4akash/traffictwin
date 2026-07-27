# Capacity Confirmatory — CANDIDATE (a): Descriptive Null Confirmation — PROPOSED, UNSIGNED

**Status: prepared fill-in candidate of
[the confirmatory protocol draft](capacity_confirmatory_protocol_draft.md). NOT signed, NOT
approved, NOT executable.** An agent filled every value below from measured pilot artifacts so
that signing is a read-and-pick; a person chooses exactly one candidate — this one or
[candidate (b)](capacity_confirmatory_candidate_b_latency_primary.md) — completes its sign-off,
and the recorded approval binds **that file's final SHA-256** with `held_out_authorised = true`.
The unchosen candidate is never executed. Label ceiling: `owner_approved_candidate`.

- Prepared: 27 July 2026, from the completed pilot (12/12 admitted, design fingerprint
  `de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90`) and its committed
  [exploratory results](capacity_pilot_results_20260727.md)
- Consumes: held-out fleet seeds `{10, 11, 12, 13, 14}` — untouched to date

## 1. Confirmatory question (fork (a) taken)

**The finding to confirm:** on the collapse-hour `inc` trace, a 3.3× capacity squeeze does not
reduce deadline attainment. The pilot's predeclared null held; this candidate publishes the
null as the finding, with a **descriptive** held-out confirmation.

**Knee-rule arithmetic, shown as the draft requires.** Adjacent-step changes in mean pilot
deadline-success rate are +0.000110 (2.5→1.5), +0.000069 (1.5→1.0), +0.000146 (1.0→0.75) —
every step *rises*; no drop exists, so the knee rule selects nothing and the predeclared
fallback fork applies. This candidate is fork **(a)**.

**Variation level (fallback selection, not knee-selected):** `cap-0.75` — the full 3.3×
squeeze, chosen as the strongest descriptive test of the null: if degradation exists anywhere
on the studied grid, the extreme level is where a fresh cohort would show it.

**Primary endpoint:** `tos.task.deadline_success.rate` (maximise) — unchanged from the pilot.

**Statistical status, fixed by the STA-05 rule.** The draft's §3 procedure was run on
27 July 2026 (25% attenuated pilot effect, pilot paired-difference variance, α = 0.05
two-sided, target power 0.80, pilot basis n = 3, STA-05 labels
`planning_aid_not_a_guarantee` and `small_pilot_sample` recorded verbatim):

| Contrast (vs cap-2.5) | Pilot mean paired diff | Attenuated target | Paired-diff SD | Required seeds |
|---|---|---|---|---|
| cap-1.5 | +0.000111 | +0.0000829 | 0.000191 | 42 |
| cap-1.0 | +0.000180 | +0.000135 | 0.000311 | 42 |
| cap-0.75 | +0.000325 | +0.000244 | 0.000349 | **17** |

Every level requires more than the 5 held-out seeds (achieved power at n = 5 would be only
≈0.34 at cap-0.75 and ≈0.16 elsewhere), so per the draft's own §3 rule **the confirmatory
claim is downgraded to a descriptive report — that downgrade is this candidate.** The
held-out result is reported with the full STA-01 machinery, verbatim, as descriptive
evidence; **no significance claim is made in any direction.** A supporting honesty note is
recorded: the pilot's tiny positive differences rest almost entirely on fleet seed 0 — seeds
1 and 2 produced exactly zero paired difference at two of the three levels.

## 2. Design

| Factor | Value |
|---|---|
| Trace | `inc` (`e188ce07…`) — unchanged |
| Actor | `ukfleettrain_mappo_model_c_17` — unchanged |
| Fleet preset / evaluator seed | `uk2030` / `0` — unchanged |
| Arms | `cap-2.5` baseline + `cap-0.75` variation (2 arms) |
| Pairing | `fleet_seed`, common-seed paired |
| Held-out seeds | `{10, 11, 12, 13, 14}` and only these; pilot seeds never pooled |
| Runs | 2 × 5 = 10 cells; measured pilot cells ran 3,534.6–3,846.7 s → **≈ 9.8–10.7 h total** |
| Secondary reporting | `task.latency.mean_ms`, `task.offload.rate`, no-target rate — descriptive only |

## 3. Analysis, fixed before execution

- STA-01 with tool defaults (0.95 confidence, 10,000/10,000 resampling, fixed resampling
  seed) on the primary contrast; the campaign analysis harness renders the report; every
  number is descriptive.
- **Decision statement:** the published conclusion is the held-out paired estimate with its
  bootstrap interval and randomisation diagnostic, labelled descriptive throughout. The null
  standing (flat deadline attainment) is confirmed *descriptively* if the held-out estimate
  is materially consistent with the pilot's; any degradation appearing in the fresh cohort is
  published with identical prominence as a contradiction of the pilot.
- Exclusions: cells without a completed receipt or refused admission are excluded and listed;
  nothing is imputed; no re-runs with altered controls.
- Pilot numbers appear only as clearly-separated "pilot context".

## 4. Execution boundaries

- One campaign, `phase = held_out`, refused without an approval binding this document's final
  digest with `held_out_authorised = true`. The 7,200 s per-request ceiling stays an
  escalation trigger. Interpretation limits: pilot predeclaration §10 unchanged, including
  `descriptive_non_causal` and single-trace/single-fleet scope.

## 5. Signing checklist (a person completes every line; an agent never does)

- [ ] Pilot campaign completed and analysed; exploratory report attached by fingerprint.
- [ ] Knee arithmetic reviewed (§1); fallback fork (a) and level cap-0.75 accepted or amended.
- [ ] STA-05 output reviewed; descriptive downgrade under the §3 rule accepted.
- [ ] Runtime commitment (~10 h) accepted.
- [ ] Candidate (b) recorded as not chosen.
- [ ] Approval recorded with `held_out_authorised = true`, binding this file's final SHA-256.

**Sign-off:**

- Chosen candidate: ______________________
- Approved by / role / date: ______________________
- Deviations from prepared values: ______________________
