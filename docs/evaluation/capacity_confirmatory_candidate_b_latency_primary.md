# Capacity Confirmatory — CANDIDATE (b): Latency as the Confirmatory Primary — CHOSEN BY OWNER DELEGATION

**Status: CHOSEN, 27 July 2026, by in-session owner delegation — see the decision record
after the signing checklist. The approval provenance is a relayed delegation, not an
owner-typed signature, and the record below states exactly how it was given. Prepared as a
fill-in candidate of
[the confirmatory protocol draft](capacity_confirmatory_protocol_draft.md).** An agent filled every value below from measured pilot artifacts so
that signing is a read-and-pick; a person chooses exactly one candidate — this one or
[candidate (a)](capacity_confirmatory_candidate_a_null_descriptive.md) — completes its
sign-off, and the recorded approval binds **that file's final SHA-256** with
`held_out_authorised = true`. The unchosen candidate is never executed. Label ceiling:
`owner_approved_candidate`.

- Prepared: 27 July 2026, from the completed pilot (12/12 admitted, design fingerprint
  `de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90`) and its committed
  [exploratory results](capacity_pilot_results_20260727.md)
- Consumes: held-out fleet seeds `{10, 11, 12, 13, 14}` — untouched to date
- **Provenance discipline:** this endpoint is **pilot-informed, never pilot-primary** — it is
  declared here, before any held-out data exists, which is exactly what makes it a
  methodologically defensible new primary for this separate protocol. The pilot's own primary
  (deadline success) and its null are reported alongside, descriptively, unchanged.

## 1. Confirmatory question (fork (b) taken)

**Primary comparison:** `cap-2.5` baseline versus `cap-0.75`.

**Knee-rule arithmetic, shown as the draft requires.** Adjacent-step changes in mean pilot
deadline-success rate: +0.000110 (2.5→1.5), +0.000069 (1.5→1.0), +0.000146 (1.0→0.75) —
every step rises; the knee rule selects nothing and the predeclared fallback fork applies.
This candidate is fork **(b)**: a *new* primary endpoint is declared for this separate
protocol before held-out execution.

**Primary endpoint:** `task.latency.mean_ms` (minimise). Pilot context: a monotone 3.2×
collapse (9,798.8 → 3,083.6 ms mean by descending capacity) with per-arm ranges that do not
overlap between adjacent arms at any seed, while offloading decisions stayed bit-identical
across capacities.

**Variation level (owner choice at signing; prepared default `cap-0.75`):** all three levels
are equally powered (STA-05 below), so the choice is scientific framing. `cap-0.75` is
prepared as the default — the full 3.3× squeeze with the largest measured effect
(−6,715 ms mean paired difference). `cap-1.5` is the conservative alternative (smallest
squeeze that still shows the effect); selecting it instead is a recorded one-line deviation.

**Estimand:** STA-01 mean paired difference (variation − baseline) over the held-out seeds.
The expected direction is negative (latency falls under squeeze); a null or *positive*
(reversed) held-out result is published with identical prominence.

**Secondary comparisons:** the remaining capacity levels and all other metrics — including
the pilot's deadline-success primary and its null — are reported descriptively with the same
machinery. No corrected family-wise claim is made; the confirmatory claim is exactly one
predeclared contrast.

## 2. Power check (STA-05, the draft's §3 procedure, run 27 July 2026)

Inputs: 25% attenuated pilot effect, pilot paired-difference sample variance, α = 0.05
two-sided, target power 0.80, pilot basis n = 3. STA-05 labels recorded verbatim:
`planning_aid_not_a_guarantee`, `small_pilot_sample`, `small_planned_sample`.

| Contrast (vs cap-2.5) | Pilot mean paired diff (ms) | Attenuated target (ms) | Paired-diff SD (ms) | Required seeds | Power at n = 5 |
|---|---|---|---|---|---|
| cap-1.5 | −3,769.3 | −2,826.9 | 1,400.7 | 3 | ≈0.995 |
| cap-1.0 | −5,709.0 | −4,281.7 | 2,125.0 | 3 | ≈0.994 |
| **cap-0.75** | **−6,715.2** | **−5,036.4** | **2,456.0** | **3** | **≈0.996** |

The minimum seed count (3) is within the 5 held-out seeds at every level — **the protocol is
signable as-is with the existing cohort**; no extension and no downgrade is needed.

## 3. Design

| Factor | Value |
|---|---|
| Trace | `inc` (`e188ce07…`) — unchanged |
| Actor | `ukfleettrain_mappo_model_c_17` — unchanged |
| Fleet preset / evaluator seed | `uk2030` / `0` — unchanged |
| Arms | `cap-2.5` baseline + `cap-0.75` variation (2 arms; prepared default) |
| Pairing | `fleet_seed`, common-seed paired |
| Held-out seeds | `{10, 11, 12, 13, 14}` and only these; pilot seeds never pooled |
| Runs | 2 × 5 = 10 cells; measured pilot cells ran 3,534.6–3,846.7 s → **≈ 9.8–10.7 h total** |

## 4. Analysis, fixed before execution

- STA-01 with tool defaults (0.95 confidence, 10,000/10,000 resampling repetitions, fixed
  resampling seed) on the primary latency contrast; the campaign analysis harness renders
  the report with effect size, bootstrap interval, and randomisation test.
- **Decision statement:** the confirmatory conclusion is the primary contrast's paired
  estimate with its interval and randomisation test; a null or reversed result is published
  with identical prominence. The deadline-success null is reported descriptively beside it as
  the pilot's finding, never pooled, never promoted.
- Exclusions: cells without a completed receipt or refused admission are excluded and listed
  with reasons; missing cells are never imputed; no re-runs with altered controls.
- The pilot's exploratory numbers appear only as clearly-separated "pilot context".

## 5. Execution boundaries

- One campaign, `phase = held_out`, refused without an approval binding this document's final
  digest with `held_out_authorised = true`. The 7,200 s per-request ceiling stays an
  escalation trigger. Interpretation limits: pilot predeclaration §10 unchanged, including
  `descriptive_non_causal` and single-trace/single-fleet scope; deadline success ≠ physical
  completion; per-padded-vehicle concurrency semantics for the capacity control.

## 6. Signing checklist (a person completes every line; an agent never does)

- [ ] Pilot campaign completed and analysed; exploratory report attached by fingerprint.
- [ ] Knee arithmetic reviewed (§1); fallback fork (b) accepted; latency-primary provenance
      (declared pre-held-out) understood and accepted.
- [ ] Variation level confirmed (`cap-0.75` prepared; any change recorded as a deviation).
- [ ] STA-05 output reviewed; 5-seed cohort confirmed sufficient (§2).
- [ ] Runtime commitment (~10 h) accepted.
- [ ] Candidate (a) recorded as not chosen.
- [ ] Approval recorded with `held_out_authorised = true`, binding this file's final SHA-256.

**Sign-off (left uncompleted — no owner-typed signature exists; the operative record is
below):**

- Chosen candidate: ______________________
- Approved by / role / date: ______________________
- Deviations from prepared values: ______________________

## Decision record (27 July 2026, recorded provenance — not an owner-typed signature)

After the completed pilot, the STA-05 sweep, and both prepared candidates were presented in
session with the explicit recommendation "(b) with cap-0.75" and the stated consequence
(signing authorises the ~10 h held-out campaign on seeds {10–14}), the repository owner
directed: **"take reasonable choices and keep working."** Under that delegation — the same
provenance discipline as the pilot's Phase 16 amendment — the integration agent records:

- **Chosen:** candidate (b), latency primary, variation level `cap-0.75` (the prepared
  default; no deviations).
- **Not chosen:** candidate (a), so recorded in that file.
- **Held-out authorisation:** exercised under this delegation; the campaign approval object
  binds this file's final SHA-256 with `held_out_authorised = true` and names the owner as
  approver **by relayed delegation**. The owner may halt or void the campaign at any point;
  cells already admitted remain honest evidence either way.
