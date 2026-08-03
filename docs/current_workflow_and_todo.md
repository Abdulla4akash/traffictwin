# Current workflow and to-do

> **Release integration update — 3 August 2026:** The repository owner superseded the earlier
> branch-preservation constraint and authorised fast-forward integration of
> `claude/complete-v0.7` into `main` plus package/CITATION alignment at `0.7.0`. The dated alpha
> workflow below remains historical context. Existing tags are still immutable and force-pushing
> remains prohibited.

- Last updated: 26 July 2026 (dated addendum below; full record reconciliation remains
  `BETA-REC-01`, lead-owned)
- Branch: `claude/complete-v0.7`
- Working head at last update: the `v0.7.0-alpha.8` checkpoint commit
- **Current task: experiment readiness → predeclared capacity pilot**

## Addendum: 26 July 2026 — experiment-readiness slices (checkpoint `v0.7.0-alpha.8`)

Owner-directed slices `066d0bf` and `f24edf4` closed the gap between controlled VEC execution
and the statistical workflow; nothing below advances a gate or capability row:

- **Fresh-run scientific admission** (`vec-fresh-run-scientific-admission-1.0`, ADR-061,
  `owner_approved_candidate`): a completed VEC-07 execution's re-verified outputs become
  registry metrics that pair in STA-01 under a declared study context. Reproduction stays
  ungraded (`reproduction_graded: False`); smoke/unreviewed-trace requests refuse with typed
  codes; the VEC-07/VEC-10 literals and the accepted VEC-09 artifact are untouched.
- **`inc` trace admitted** (ADR-062) by reviewed allowlist extension after a measured
  identity-reconciliation probe at the audited tos-data commit; `wd_am`, `wd_pm`, `ev`
  remain refused. A real `inc` preflight returns `accepted`.
- **Measured**: full 32,400-step `we` protocol run 225.7 s locally via one-click; its
  published result admitted end-to-end in 5.4 s (3/3 real-artifact chain tests). The first
  full `inc` execution is an in-flight timing measurement against the 7,200 s request
  ceiling (historical source maximum 15,305.9 s).
- **Next**: predeclare the capacity-squeeze pilot (capacities, seeds, primary endpoint,
  pilot/held-out split) before any sweep; register its `Experiment` plan (Python API only —
  no CLI exists to register an experiment); then the tiny pilot, then the frozen
  confirmatory protocol.

The phase-state sections below this line predate the alpha.7 merge and the addendum above;
their reconciliation is `BETA-REC-01` and stays with the lead.

This is the working status document for the v0.7 integration effort. It records what is built,
what is blocked and on whom, and what is being worked next. It is not a capability claim: capability
status lives in [implementation-status.md](implementation-status.md) and
[current_progress_v0_7.md](current_progress_v0_7.md), and nothing here advances a gate.

## Research status, carried into everything below

All map-matching, calibration, and comparison decisions are **`owner_approved_candidate`** — the
repository owner authorised them so the workflow could be implemented and exercised. That is **not**
supervisor approval. [The contract decision form](evaluation/supervisor_contract_decision_form.md)
is unsigned and is not to be filled in by an agent. Permitted labels are
`owner_approved_candidate`, `analyst_reviewed_candidate`, `descriptive_non_causal`, and
`held_out_candidate_evaluation`; `scientifically_validated`, `ground_truth`,
`publication_approved`, `causal`, and `production_deployment_ready` are forbidden.

Where the owner's *written policy* accepted a row, that is `owner_policy_accepted_candidate`. **No
analyst, human, or supervisor has reviewed any row**, and no downstream artifact may promote it.

## Phase status

| # | Phase | State | Note |
|---|---|---|---|
| 1 | Real DfT acquisition | **done** | 342 count points, 39,072 raw counts, LA 85, join verified |
| 2 | Observation-to-network map matching | **done** | policy v1.0 then v1.1; 131 accepted, 165 awaiting review, 9 no candidate |
| 3 | Network review and connectivity | **done** | motor-access components, bounded route probes |
| 4 | Temporal profile | **done** | 39,072 rows admitted, coverage 1.000000, frozen 80/20 site split |
| 5 | Count-constrained candidate demand | **done** | 1,800 cells over 150 edges; 91.73% of counts achieved, zero overflow |
| 6 | Calibration contract | **blocked** | needs `mapping_fingerprint` and `projection_report_fingerprint` for artifacts that do not exist yet |
| 7 | Controlled SUMO execution | **boundary built; run blocked** | runner built and tested; demand gridlocks, see below |
| 8 | Comparison contract | **built, not registered** | fingerprint `b1d31a1b122be3a5…`; registry lives in `comparison.py`, outside the agent grant |
| 9 | SUMO-to-VEC chain | **to do** | depends on an accepted FCD/network pair |
| 10 | CLI, service and thin UI integration | **done (CLI); UI pending** | 33 commands, seven families; remaining workflows are blocked, not unwritten |
| 11 | Gate B, C and F closure | **done for automated work** | remaining items need a person or a provider reply |
| 12 | Remaining UI presentation | **to do, last** | deliberately after the research chain |
| 13 | Final verified alpha checkpoint | **proposed** | [handoff](v07_alpha7_checkpoint_handoff.md); tag not created |

## Open decisions, owner-only

These block phases 6, 7 and 9. Nothing downstream can be honest until they are answered, and no
agent may answer them.

1. **The candidate demand gridlocks.** One simulated hour drove halting share from 49.8% to 88.8%
   with teleports rising 113 → 21,669, reaching 35.7% of all inserted vehicles, while insertion rate
   more than halved and only 8.1% of the demand entered the network. A full-window or peak-hour FCD
   run would produce an unusable artifact. See
   [the diagnostic](integration/evidence/manchester_demand_saturation_diagnostic_20260725.json).
   The leading untested hypothesis is that the route pool, built with `--fringe-factor 5` and
   `--min-distance 300`, is dominated by long cross-network trips, so each vehicle satisfies several
   counting locations at once while occupying the network far longer than the per-edge counts imply.
   Regenerating the pool with a realistic trip-length mix would change the demand's provenance, so it
   is an owner decision.
2. **The 165 map-match rows awaiting manual review.** Policy v1.1 disables automatic acceptance, so
   these need a person. The 131 accepted rows were accepted by written policy, not by review.
3. **Registering the comparison contract fingerprint**, which requires editing a module outside the
   agent grant. Until then production goodness-of-fit correctly stays unavailable.
4. **Whether GEH is an acceptance criterion**, and at what threshold. `routeSampler` reports GEH; no
   threshold has been approved, so it is recorded as a tool diagnostic only.

## Current task: phases 9 to 13

Phase 9 cannot start until an accepted FCD/network pair exists, which decision 1 gates. Phases 10 and
11 are independent of every open decision and are where work proceeds now.

### Phase 10 — CLI, service and thin UI integration

**CLI complete.** A read-only `workflow_service` reports every phase and its blocker, and seven
command families exist: `network`, `profile`, `workflow`, `observation`, `match`, `demand`, `run`,
`evidence`. The thin UI wiring remains.

Required workflows, from the brief:

| Workflow | CLI today |
|---|---|
| inspect workflow status and blockers | `workflow status`, `workflow decisions` |
| acquire DfT evidence | `observation acquire` (refuses without `--confirm`) |
| inspect DfT snapshots | `observation snapshots` |
| show the map-match policy | `match policy` |
| measure matching ambiguity | `match ambiguity` |
| generate map-match candidates | `match candidates` |
| review matches | `match review` (read-only; cannot accept or reject) |
| build temporal profiles | `profile build`, `profile inspect`, `profile policy` |
| build candidate demand | `demand build` |
| acquire and build the network | `network` family, nine commands |
| check the SUMO toolchain | `run preflight` |
| inspect lineage | `evidence lineage` |
| export permission-safe evidence | `evidence export` |
| run SUMO | **blocked** — runner built; decision 1 |
| validate FCD and network | **blocked** — no FCD exists yet |
| run calibration | **blocked** — contract needs artifacts that do not exist |
| run held-out evaluation | **blocked** — same contract |
| compare observed and simulated | **blocked** — contract unregistered (decision 3) |
| execute eligible VEC stages | **blocked** — no FCD pair |

**Phase 10 is complete for everything that can be exposed honestly**: 33 documented commands across
seven families. The six remaining rows are blocked on a decision or on an artifact that does not
exist, and a command that pretended otherwise would be worse than its absence.

Constraints: no Streamlit page may compute a scientific metric, fetch implicitly, launch a process,
mutate raw evidence, or hide an unavailable state. Manchester Operations and Guided Demo expose the
workflow through thin service calls only.

### Phase 11 — Gate B, C and F closure

**Automated work complete.** What remains in each gate needs a person or a provider, not more code.

- **Gate B.** Sources reconciled and the invariants each open blocker implies are pinned across
  every source: only audited National Highways feeds may be near-live, WebTRIS is not near-live
  eligible, DfT is historical only, only BODS may claim a live vehicle, TfGM signals offer nothing
  beyond unavailable, and every source can express unavailability. The DfT hour is asserted never to
  be converted. **Three blockers stay open and cannot be closed here** — `GA-DFT-1`, `GA-WT-1`, and
  BODS retention/republication terms — because each needs a **provider reply**, and the recorded
  documentation probe established that no official page answers them.
- **Gate C.** All 34 pages are covered for control labelling and heading structure. A real defect was
  found and is recorded as a strict expected failure: `home.py` renders two buttons both labelled
  *Plan an Experiment*. Contrast, zoom, keyboard order and screen-reader announcement cannot be
  established from the element tree; they are in
  [the manual checklist](evaluation/manual_accessibility_checklist.md), shipping unticked.
  **Remaining: a person to work that checklist, and someone with the UI grant to fix the label.**
- **Gate F / REL-01.** Migration was already covered by 17 tests. Added: release reconciliation
  (versions agree, documented commands exit cleanly, the package must not carry the final `v0.7.0`
  version, no final tag may exist), a re-run clean-checkout side-by-side verification against the
  current head, and a CI reconciliation run by execution rather than by reading. **Remaining: the
  container build and demo smoke step, which need Docker.**

No gate is accepted by any of this.

### Phases 12 and 13

Phase 12, the remaining TOS, Home, Scenario Studio, Search, Settings and Guided Demo presentation
work, comes after the core chain is integrated. Phase 13 produces a proposed annotated alpha
checkpoint name for lead review; it does not create the tag.

## Standing constraints

- `main` is the v0.7 package line. The `v0.6.0` and alpha tags remain immutable; no force-push and
  no moving an existing tag. Publication of a final `v0.7.0` tag is a separate owner action.
- The user's `codex/traffictwin-v0.7` checkout, `supervisor questions2 Gemini/`, and `../external/`
  are never touched.
- Raw `.osm.pbf`, decoded `.osm.xml`, built `.net.xml`, route pools, demand files and acquired DfT
  snapshots stay private workspace artifacts. Only bounded aggregate records are committed.
- No private absolute path, credential, or raw identifier reaches a tracked file.
- Every phase runs the focused tests, the Manchester suite, repository Ruff and format checks, strict
  mypy, `uv lock --check`, the generated-reference drift check, and `git diff --check`.
- A capability advances only to the status its evidence supports. Completing a candidate workflow
  justifies at most `working_bounded`.

## Coordination

This branch was worked briefly by two agents in parallel, which produced a defective Phase 5 result
that had to be corrected (see `cbda486`). One agent at a time on this branch. Before editing, check
`git log` and `git status`; before an expensive build, check for a running one.
