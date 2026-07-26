# Capacity-Squeeze Pilot — Predeclaration (PROPOSED, UNSIGNED)

**Status: PROPOSED. Not approved, not executed.** No run described here has been performed.
This document must be signed by the repository owner before any sweep executes; it exists so the
design is fixed *before* results are visible, which is the only thing that makes the eventual
finding defensible rather than selected.

- Proposed: 26 July 2026
- Policy label if approved: `owner_approved_candidate` (not supervisor approval; the
  [supervisor contract decision form](supervisor_contract_decision_form.md) remains unsigned)
- Executes through: VEC-07 runner → fresh-run admission
  ([ADR-061](../decisions/ADR-061-vec-fresh-run-scientific-admission.md)) → STA-01
- Trace: `inc` incident trace, admitted by
  [ADR-062](../decisions/ADR-062-inc-trace-allowlist-extension.md)

## 1. Question and hypothesis

**Question.** Does reducing per-vehicle RSU task capacity degrade deadline success on the
Manchester incident trace, and is the degradation graceful or a cliff?

**Predeclared hypothesis (H1).** Deadline-success rate falls monotonically as
`--rsu-cap-per-veh` decreases, and at least one adjacent capacity step shows a
disproportionately large drop (a knee) rather than a linear decline.

**Null outcome (H0), declared publishable in advance.** If deadline success is flat across the
capacity grid, or declines without any disproportionate step, that is a reportable result: it
would mean the audited policy is insensitive to this control over the tested range. This
document commits to publishing that outcome with the same prominence as a positive one.

## 2. What the evaluator control actually means

`--rsu-cap-per-veh` is the source evaluator's **per-padded-vehicle concurrent task capacity
bound**. It is not CPU capacity, not bandwidth, not physical RSU hardware capacity, and not a
count of RSUs. Every reported result must carry that wording. RSU positions are fixed inside
the trace and are not varied here.

## 3. Design constraint discovered in the tooling (shapes this design)

STA-01 (`PairedStudyConfig`) carries a **single `algorithm` field**, so both arms of a paired
study must share one actor. Consequences, recorded before any run:

- **Capacity effect within one actor** is a valid STA-01 paired study: arms are capacity
  labels, paired on a common seed. This pilot does exactly that.
- **Actor-versus-actor crossover** — the "expected winner loses" upset — is **not** an STA-01
  paired comparison. It requires either N-way ranking per capacity level, or a descriptive
  comparison of two separately estimated capacity-degradation slopes. Whichever is chosen must
  be predeclared in its own document; this pilot does not settle it and must not be reported
  as evidence about it.

## 4. Fixed factors

| Factor | Value | Why fixed |
|---|---|---|
| Trace | `inc` (`e188ce07…`, T=3,600, maxN=2,488) | The reviewed incident scenario; peak load is the phenomenon of interest |
| Actor | `ukfleettrain_mappo_model_c_17` | One actor per paired study (§3); the UK-2030-trained actor matches the fleet below |
| Fleet preset | `uk2030` | Held constant so capacity is the only varied control |
| Evaluator seed | `0` | Fixed; the fleet seed carries replication |
| Steps | `3600` (full trace) | Truncated runs are inadmissible by ADR-061 |

## 5. Arms and pairing

- **Pairing variable:** `fleet_seed`, declared to fresh-run admission as
  `pairing_seed_source = fleet_seed`. The same fleet draw is evaluated at every capacity, so a
  paired difference isolates capacity from fleet composition.
- **Baseline arm:** `cap-2.5` (the audited source default).
- **Variation arms:** `cap-1.5`, `cap-1.0`, `cap-0.75`.
- **Comparisons:** three, each variation against the single baseline.

Arm labels are the registry `seed_id` values and are fixed here so they cannot be renamed
after results are seen.

## 6. Endpoints

- **Primary:** `tos.task.deadline_success.rate` (objective: maximise). One primary endpoint,
  declared before execution.
- **Secondary, reported but never promoted to primary:** `task.latency.mean_ms`,
  `task.offload.rate`, `task.decision_share.*`,
  `tos.task.no_eligible_target.rate_among_offload`.
- **Structurally unavailable and never substituted:** physical task completion, per-task
  energy, canonical utilisation/queue, confirmed-target completion, protected-attribute
  fairness. GEH does not appear in this design at all.

## 7. Pilot and held-out split

Two **disjoint** fleet-seed sets, fixed now:

- **Pilot seeds: `{0, 1, 2}`** — exploratory. Used to check the chain end to end, measure
  runtime, and locate any response region. Pilot numbers may inform the confirmatory design
  but **may never be pooled into the confirmatory estimate or reported as the finding.**
- **Held-out seeds: `{10, 11, 12, 13, 14}`** — reserved. Untouched until the confirmatory
  protocol is separately signed. The confirmatory estimate comes from these only.

STA-01 hard-requires a minimum of 3 pairs, so the pilot's three seeds are the smallest
runnable design; three pairs is **adequate for a feasibility check and inadequate for a
confirmatory claim**, which is exactly why the split exists.

## 8. Pilot scope and compute budget

Pilot = 4 arms × 3 pilot seeds = **12 full-length `inc` executions**.

The per-run cost must come from measurement, not assumption. Reference points already
measured on this machine: the full 32,400-step weekend run took **225.7 s**; the first
full-length `inc` run is the timing probe required by ADR-062 and its elapsed time fills the
table below before this document is signed.

| Measured `inc` run time | 12-run pilot wall-clock (serial) | Action |
|---|---|---|
| ≤ 10 min | ≤ 2 h | Proceed locally |
| 10–30 min | 2–6 h | Proceed locally, overnight |
| 30–60 min | 6–12 h | Proceed locally but re-cost the confirmatory design before signing it |
| approaching 7,200 s ceiling | — | **Stop and escalate to the owner.** Do not raise the runner's timeout to fit a design |

Execution is one foreground request at a time; no background queue, no SLURM, no detached
recovery. Runs are invoked through the VEC-07 library runner (the one-click CLI presets only
cover the weekend trace).

## 9. Analysis plan, fixed before results

- Estimator: STA-01 paired mean difference (variation − baseline) on the primary endpoint,
  with its deterministic percentile-bootstrap interval and two-sided sign-flip randomisation
  test, at the tool defaults (confidence 0.95, 10,000 repetitions, fixed resampling seed).
- **Multiplicity:** three comparisons share one baseline. The pilot is explicitly
  exploratory, so no significance claim is made from it at all. The confirmatory protocol must
  declare its multiplicity handling before it runs; this document does not pre-authorise an
  uncorrected three-comparison claim.
- **Power:** the STA-05 prospective helper will size the confirmatory seed count using the
  pilot's observed paired-difference variance, with its normal-approximation and small-pilot
  qualifications recorded. Five seeds is a source recommendation, not a power calculation.
- **Stopping rule:** the pilot stops when all 12 runs terminate or a run fails; a failure is
  reported, not retried with altered controls. There is no "run more seeds until it looks
  clearer" path.
- **Exclusions:** any run that does not reach a `completed` receipt, or whose admission
  refuses, is excluded and reported with its reason. Missing cells are never imputed.

## 10. Interpretation limits binding on any output

- A capacity effect on this trace is descriptive and **non-causal** with respect to real
  offloading deployments.
- Results describe the audited policy on one reviewed trace with one fleet preset. They are
  not evidence about the other four scenarios, other fleets, other policies, real Manchester
  traffic, or Randy's broader algorithm set.
- Deadline success is never physical completion. Reconstructed evaluator behaviour is never an
  observed journey.
- Nothing here is `scientifically_validated`, `ground_truth`, `publication_approved`,
  `causal`, or `production_deployment_ready`.

## 11. Owner decisions required before execution

| # | Decision | Proposed default |
|---|---|---|
| D1 | Capacity grid | `{2.5, 1.5, 1.0, 0.75}` — four arms; drop or add a level? |
| D2 | Actor for the pilot | `ukfleettrain_mappo_model_c_17` |
| D3 | Pilot seeds / held-out seeds | `{0,1,2}` / `{10,11,12,13,14}` |
| D4 | Primary endpoint | `tos.task.deadline_success.rate` |
| D5 | Crossover approach for the later actor comparison (§3) | N-way ranking per capacity level |
| D6 | Escalation if runtime nears the 7,200 s ceiling | Stop and ask, never raise the bound |

**Sign-off (to be completed by a person, never by an agent):**

- Approved by: ______________________
- Role: ______________________
- Date: ______________________
- Deviations from the proposed defaults: ______________________
