# Stadium Event-Night Study — DRAFT (NOT SIGNABLE YET)

**Status: structural draft; cannot be signed, approved, or executed in this form.** Fields
marked `FILL-AT-SIGNING` require decisions no agent may take. This is the predeclared design
for the supervisor's own stadium what-if question, fixed in structure before any `ev`
evidence exists — no `ev` execution has ever been run, and nothing here authorises one.

- Drafted: 27 July 2026, before any `ev` cell executed
- Enabled by: the `ev` trace admission (ADR-065, Phase 31), which explicitly enables **no**
  experiment by itself — "any `ev` study still requires its own predeclaration and an
  approval-gated campaign"
- Policy label ceiling: `owner_approved_candidate`

## 1. Question

**Question.** How do fleet offloading dynamics behave across a stadium event night, and does
the pattern differ from the modelled traffic-collapse hour the pilot already measured?

**Scenario identity, from the admitted record.** The `ev` trace is the Champions League event
night on the Manchester Etihad/Co-op Live event-district network: T = 23,400 steps (6.5
hours) at maxN = 175 vehicle slots, 1,898,428 masked vehicle-seconds across 9,130 occupancy
spans, hash-matched to the Gate-A audit. Scenario provenance cites the producer's sidecar at
upstream commit `6e56393`. All scope language below means that district on that night, never
Manchester generally.

**Contrast with the pilot's trace, stated as context and not as a contrast to be tested.**
The pilot's `inc` trace is one hour (3,600 steps) at 2,488 slots — a dense, short,
deliberately anomalous collapse hour. `ev` is 6.5 hours at 175 slots — sparse, long, and
event-shaped. The two differ in duration, density, and scenario at once.

## 2. Why the `ev`-versus-`inc` comparison is not a paired study

**Recorded tooling constraint (STA-01).** The accepted paired evaluator pairs replicates on
`fleet_seed` within one comparable context and carries a single `algorithm`. Two traces that
differ in T, maxN, and scenario are not exchangeable units, so pairing an `ev` cell against an
`inc` cell would pair on a shared *label* rather than a comparable unit. **A cross-trace
contrast is therefore not an STA-01 paired study and must never be reported as one.**

**Consequence for this design.** Any tested contrast lives *within* the `ev` trace, exactly as
the pilot's arms lived within `inc`. The pilot's numbers enter this study only as descriptive
context, cited with their own provenance and never pooled, differenced, or ranked against
`ev` values.

**Recorded tooling constraint (STA-02).** If the study ranks more than one actor, the accepted
N-way ranking requires a checkpoint expectation per ranked algorithm; the Phase 28 extension
(`checkpoint_by_algorithm`, mutually exclusive with the single `checkpoint`) makes that
possible for distinct trained actors. Whether this study ranks actors at all is `FILL-AT-SIGNING`
(D2); the single-actor form needs no ranking machinery.

## 3. Design

| Factor | Value |
|---|---|
| Trace | `ev` — the admitted event-night trace, unchanged |
| Arms / levels | `FILL-AT-SIGNING`: the control and its levels are a signing decision (D1). The capacity control the pilot used is one candidate; a temporal-window decomposition of the event night is another. Neither is assumed here. |
| Actors | `FILL-AT-SIGNING` (D2): one audited actor, or both under STA-02 per-algorithm checkpoints |
| Fleet preset / evaluator seed | `uk2030` / `0`, matching the pilot so the descriptive context is at least preset-comparable; confirmed or changed at signing |
| Seeds | fresh set `{40, 41, 42, 43, 44}`, proposed and fixed at signing — disjoint from pilot `{0–2}`, held-out `{10–14}`, crossover `{20–24}`, and bus-fleet `{30–34}` |
| Primary endpoint | `FILL-AT-SIGNING` (D3), declared before execution and never chosen after seeing a result |
| Secondaries | descriptive only, never promoted, exactly as in the pilot |

## 4. Publishable null (fixed now, before any evidence)

**"Fleet offloading dynamics across the event night show no arm difference on the declared
primary endpoint" is a reportable outcome of equal standing.** It is published with the same
prominence as any positive result. The pilot has already demonstrated that this commitment is
honoured in practice rather than merely stated: its own predeclared null held and was
published.

A second null is fixed here too: **"the event night's dynamics resemble the collapse hour's"**
is a legitimate descriptive finding. Because §2 forbids testing that comparison, it can only
ever be reported as an observation about two separately measured traces.

## 5. Runtime is unmeasured — the first execution is a timing probe

**No `ev` execution has ever been timed.** ADR-065 records the risk and this design carries it
unchanged.

The recorded evidence is that slot width dominates runtime: the 139-slot weekend full run
measured 225.7 s while the 2,488-slot incident hour measured 3,555.96 s. At 175 slots the
per-step cost should therefore be near the weekend run's, but `ev` is 23,400 steps rather than
3,600 — 6.5× the steps. Extrapolating the recorded slot-scaling across that many steps gives a
minutes-to-low-thousands-of-seconds expectation, **but that is an extrapolation from two
points and is not evidence.**

Binding consequences:

- The **first `ev` cell is a timing measurement**, recorded as such, before any multi-cell
  campaign is scheduled. Its measured wall-clock replaces the extrapolation above at signing.
- The runner's **7,200-second per-request ceiling stays an escalation trigger, never a bound
  to raise.** A cell that reaches it halts and is recorded with its reason.
- The full campaign is re-costed from the measured single-cell figure before approval, and the
  arm × seed grid is sized to that measurement, not to this draft's expectation.
- Nothing is scheduled while another campaign occupies the machine.

## 6. Interpretation limits binding on any output

- One trace, one event night, one district, one fleet preset. Descriptive and non-causal;
  never generalised to Manchester, to stadium events in general, or to another venue.
- Deadline success is never physical completion; reconstructed evaluator behaviour is never an
  observed journey; vehicle slots are time-local and recycled, never tracked individuals.
- The pilot's exploratory numbers stay exploratory forever and are never pooled with `ev`
  results.
- Forbidden labels remain forbidden. Supervisor approval is not claimed by this document or by
  anything it produces; `owner_approved_candidate` is the ceiling.

## 7. Decisions required before execution

| # | Decision | Status |
|---|---|---|
| D1 | The control and its levels (what actually varies across arms) | `FILL-AT-SIGNING` |
| D2 | One actor or both (and therefore whether STA-02 ranking is used) | `FILL-AT-SIGNING` |
| D3 | Primary endpoint, declared before execution | `FILL-AT-SIGNING` |
| D4 | Seed set confirmed as `{40–44}` and disjoint from all four existing cohorts | proposed |
| D5 | Timing-probe cell approved and executed before the campaign is sized | proposed |
| D6 | Scheduling relative to other campaigns | owner decision |

## 8. Signing checklist (a person completes every line)

- [ ] Control, levels, actors, and primary endpoint filled in — none chosen after seeing a result.
- [ ] Seed set fixed and confirmed disjoint from `{0–2}`, `{10–14}`, `{20–24}`, `{30–34}`.
- [ ] Timing probe executed; measured wall-clock recorded; campaign re-costed from it.
- [ ] Grid sized within the 7,200-second ceiling, with the escalation path recorded.
- [ ] Approval recorded binding this document's final SHA-256.

**Sign-off (a person completes this; an agent never does):**

- Approved by: ______________________
- Role: ______________________
- Date: ______________________
- Deviations from the proposed defaults: ______________________
