# Capacity-Squeeze Confirmatory Protocol — DRAFT (NOT SIGNABLE YET)

**Status: structural draft. This document cannot be signed, approved, or executed in its
current form** — the fields marked `FILL-FROM-PILOT` require measured pilot values that do not
exist yet, and campaign tooling refuses held-out execution without a signed approval binding
this document's final digest. It exists now so the confirmatory decision is a fill-in of
predeclared structure rather than a design written while looking at results.

- Drafted: 26 July 2026, before any pilot cell completed
- Prerequisite: the completed pilot campaign for
  [the pilot predeclaration](capacity_squeeze_pilot_predeclaration.md) and its exploratory
  analysis report
- Consumes: held-out fleet seeds `{10, 11, 12, 13, 14}` — untouched to date, and requiring
  explicit `held_out_authorised` approval to execute
- Policy label ceiling: `owner_approved_candidate`; supervisor approval is not claimed

## 1. Confirmatory question

One primary contrast, fixed here in structure and fixed in value at signing:

- **Primary comparison:** baseline `cap-2.5` versus **one** variation capacity level,
  selected by the knee rule below. **Measured 27 July 2026, pilot complete (12/12 admitted):
  the knee rule selects NOTHING.** Adjacent-step changes in mean deadline-success rate are
  +0.000110 (2.5→1.5), +0.000069 (1.5→1.0), +0.000146 (1.0→0.75) — every step *rises*
  slightly; no drop exists anywhere on the grid. The pilot therefore lands on this protocol's
  predeclared fallback fork, an owner decision at signing:
  **(a)** publish the null as the finding — capacity squeeze does not reduce deadline
  attainment on the collapse-hour trace — with a descriptive held-out confirmation; or
  **(b)** declare a *new* primary endpoint for this separate protocol before any held-out data
  exists: `task.latency.mean_ms` (minimise), where the pilot measured a monotone 3.2×
  collapse (9,799 → 3,084 ms mean) with non-overlapping per-arm ranges across all seeds while
  offloading decisions stayed bit-identical across capacities. Naming latency here is
  methodologically defensible precisely because it happens before held-out execution; it must
  be recorded as pilot-informed, never as the pilot's own primary.
- **Knee rule (fixed now):** rank adjacent capacity steps by absolute drop in mean pilot
  deadline-success rate; the confirmatory variation level is the lower capacity of the
  top-ranked step. Ties resolve to the higher capacity (the more conservative squeeze).
- **Primary endpoint:** `tos.task.deadline_success.rate` (maximise) — unchanged from the
  pilot; no promotion of any secondary metric.
- **Estimand:** STA-01 mean paired difference (variation − baseline) over the held-out seeds.

Secondary comparisons (the remaining capacity levels) are reported descriptively with the same
STA-01 machinery but are **not** confirmatory claims; no corrected family-wise claim is made
unless a multiplicity policy is added at signing and recorded here.

## 2. Design

| Factor | Value |
|---|---|
| Trace | `inc` (`e188ce07…`) — unchanged |
| Actor | `ukfleettrain_mappo_model_c_17` — unchanged |
| Fleet preset / evaluator seed | `uk2030` / `0` — unchanged |
| Arms | `cap-2.5` baseline + `FILL-AT-SIGNING` (primary level; other levels optional secondaries) |
| Pairing | `fleet_seed`, common-seed paired |
| Held-out seeds | `{10, 11, 12, 13, 14}` and only these; pilot seeds are never pooled in |
| Runs | arms × 5 seeds; re-cost against the measured 3,555.96 s per-run figure at signing |

## 3. Power check (STA-05, fixed procedure)

Before signing, run the STA-05 prospective helper with:

- target effect `FILL-FROM-PILOT` (the pilot's primary-comparison mean paired difference for
  the chosen level, attenuated by 25% as a conservatism margin);
- prospective paired-difference standard deviation `FILL-FROM-PILOT` (the pilot's sample SD
  for that comparison, with STA-05's small-pilot qualification recorded verbatim);
- alpha 0.05 two-sided, target power 0.80.

If the minimum seed count exceeds 5, the protocol is **not signable as-is**: either the
held-out set is extended by a new owner decision (new seeds, still disjoint from the pilot's)
or the confirmatory claim is downgraded to a descriptive report — chosen at signing, not
after results.

## 4. Analysis, fixed before execution

- STA-01 with tool defaults (0.95 confidence, 10,000/10,000 resampling repetitions, fixed
  resampling seed) on the primary contrast; the campaign analysis harness renders the report.
- **Decision statement fixed now:** the confirmatory conclusion is the primary contrast's
  paired estimate with its bootstrap interval and randomisation test, reported with effect
  size; a null or reversed result is published with identical prominence.
- Exclusions: cells without a completed receipt or refused admission are excluded and listed
  with reasons; missing cells are never imputed; no re-runs with altered controls.
- The pilot's exploratory numbers appear only as "pilot context", clearly separated from the
  held-out estimate.

## 5. Execution boundaries

- One campaign, `phase = held_out`, refused without `held_out_authorised` approval binding
  this document's **final** digest (the digest changes when the FILL fields are completed —
  approval attaches to the completed document, not this skeleton).
- The 7,200 s per-request ceiling remains an escalation trigger, never a bound to raise.
- Interpretation limits are the pilot predeclaration's §10, unchanged, including
  `descriptive_non_causal` and the single-trace/single-fleet scope.

## 6. Signing checklist (a person completes every line)

- [ ] Pilot campaign completed and analysed; exploratory report attached by fingerprint.
- [ ] Primary variation level filled by the knee rule, with the rule's arithmetic shown.
- [ ] STA-05 output attached; seed count confirmed sufficient, or the fallback decision made.
- [ ] Multiplicity policy for secondary levels chosen and recorded.
- [ ] Runtime re-costed; owner accepts the wall-clock commitment.
- [ ] Approval recorded with `held_out_authorised = true`, binding this document's final
      SHA-256.
