# Current workflow and to-do

- Last updated: 25 July 2026
- Branch: `claude/complete-v0.7`
- Working head at last update: `c628e66`
- **Current task: phases 9 to 13**

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
| 10 | CLI, service and thin UI integration | **in progress** | five command families; nine workflows still have no CLI |
| 11 | Gate B, C and F closure | **to do** | independent of the demand blocker |
| 12 | Remaining UI presentation | **to do, last** | deliberately after the research chain |
| 13 | Final verified alpha checkpoint | **to do** | not a release; no final `v0.7.0` tag |

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

**In progress.** A read-only `workflow_service` now reports every phase and its blocker, and four
command families exist: `network`, `profile`, `workflow`, `observation`, `match`. Nine workflows
still have no CLI.

Required workflows, from the brief:

| Workflow | CLI today |
|---|---|
| inspect workflow status and blockers | `workflow status`, `workflow decisions` |
| inspect DfT snapshots | `observation snapshots` |
| show the map-match policy | `match policy` |
| build temporal profiles | `profile build`, `profile inspect`, `profile policy` |
| acquire and build the network | `network acquire`, `network decode`, `network build`, and five more |
| acquire DfT evidence | **missing** — module exists, needs an operator-confirmed command |
| measure matching ambiguity | **missing** |
| generate map-match candidates | **missing** |
| review and resume matches | **missing** — must stay non-automatable |
| build candidate demand | **missing** |
| run SUMO | **missing** — runner exists, run is blocked on decision 1 |
| validate FCD and network | **missing** — no FCD exists yet |
| run calibration | **missing** — contract blocked |
| run held-out evaluation | **missing** — contract blocked |
| compare observed and simulated | **missing** — contract unregistered |
| execute eligible VEC stages | **missing** — no FCD pair |
| inspect lineage | **missing** |
| export permission-safe evidence | **missing** |

Constraints: no Streamlit page may compute a scientific metric, fetch implicitly, launch a process,
mutate raw evidence, or hide an unavailable state. Manchester Operations and Guided Demo expose the
workflow through thin service calls only.

### Phase 11 — Gate B, C and F closure

- **Gate B.** Reconcile the real DfT evidence now in use; preserve the unresolved DfT timezone
  semantics outside local-clock simulation; reconcile eligible TfGM, WebTRIS, BODS and National
  Highways evidence. Do not invent provider replies or legal terms.
- **Gate C.** Run the route, AppTest and browser matrices; add automated keyboard-order, label,
  contrast and zoom checks where possible; prepare the manual accessibility checklist. Do not
  fabricate a screen-reader user or a participant study.
- **Gate F / REL-01.** Clean-checkout v0.6/v0.7 side-by-side verification; migration preview, backup,
  interruption, rollback and refusal tests; reconcile versions, schemas, generated references, CLI,
  documentation and CI. Preserve v0.6 workspaces. Do not create a final `v0.7.0` tag.

### Phases 12 and 13

Phase 12, the remaining TOS, Home, Scenario Studio, Search, Settings and Guided Demo presentation
work, comes after the core chain is integrated. Phase 13 produces a proposed annotated alpha
checkpoint name for lead review; it does not create the tag.

## Standing constraints

- `main` is the v0.6 release line and is never updated. No final `v0.7.0` tag. No force-push. No
  moving an existing tag.
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
