# Proposed alpha checkpoint handoff — `v0.7.0-alpha.7`

- Prepared: 25 July 2026
- Branch: `claude/complete-v0.7`
- Range: `b6aa9a9` (`v0.7.0-alpha.6`) → `b50f27d`, **47 commits**, 57 files, +21,071 / −98
- **Proposed tag name: `v0.7.0-alpha.7`**
- **Status: proposal only. No tag has been created.** Creating it is the lead's action after review.

## Proposed annotated tag message

```
TrafficTwin v0.7 alpha 7 — real observation-to-network research chain

Carries the v0.7 work from the network baseline through real DfT acquisition,
map matching under an owner-approved candidate policy, network connectivity
review, a temporal profile, count-constrained candidate demand, a controlled
SUMO execution boundary, and a 33-command Manchester CLI, plus Gate B, C and F
reconciliation.

This is an alpha development checkpoint. MAN-09 remains planned, Gate D and
Gate E remain foundation_only, and no capability was advanced by this work. It
is not the final v0.7 release.
```

## What was built

| Phase | Outcome |
|---|---|
| 1 Real DfT acquisition | 342 count points, 39,072 raw counts, LA 85, join verified, 0 orphaned |
| 2 Map matching | policy v1.0 then v1.1; 131 accepted, 165 awaiting review, 9 no candidate |
| 3 Network review | motor-access components, bounded route probes |
| 4 Temporal profile | 39,072 rows admitted, coverage 1.000000, frozen 80/20 site split |
| 5 Candidate demand | 1,788 cells over 149 edges; 91.32% of counts achieved, zero overflow |
| 6 Calibration contract | **blocked** — binds fingerprints for artifacts that do not exist |
| 7 SUMO execution | boundary built and tested; **run blocked**, demand gridlocks |
| 8 Comparison contract | built and fingerprinted; **not registered**, registry outside grant |
| 9 VEC chain | **not started** — needs an accepted FCD/network pair |
| 10 CLI and service | 33 documented commands across seven families |
| 11 Gates B, C, F | reconciled; remaining items need a person or a provider |

Nine new library modules: `network_geometry`, `network_connectivity`,
`observation_matching`, `observation_matching_v11`, `dft_temporal_profile`,
`demand_reconstruction`, `sumo_run`, `owner_candidate_contracts`, `workflow_service`.

## Real source identities

| Artifact | Fingerprint |
|---|---|
| DfT count points | `053491696819f2f0767851a24805b1f921fdd8b254f8b8cc04f52e8c396b92b9` |
| DfT raw counts | `61965dc5c182ae335a4bc266664fc808bea35bd35bc9d30740897d8c2b39a33c` |
| Comparison contract (unregistered) | `b1d31a1b122be3a50756ec8e51d1fb17cb6a79c684d48848f1f5df60e45aba3b` |

Source: `roadtraffic.dft.gov.uk`, OGL-v3.0, Manchester local authority `85` (ONS `E08000003`), bound
as a literal so no caller can widen the scope.

## Map matching and analyst review

Policy `manchester-dft-map-match-owner-policy-1.1`, research status
`owner_approved_candidate`. Over 305 real count points: **131 accepted, 165 awaiting manual review,
9 no suitable candidate**.

**No analyst, human, or supervisor has reviewed any row.** The 131 were accepted by the owner's
*written policy*, labelled `owner_policy_accepted_candidate`, and every downstream artifact carries
that basis forward. The design brief's phrase "analyst-accepted matches" is **not yet satisfied by a
person**. `match review` is read-only by construction and offers no accept, reject, or bulk option.

## Demand generation and mismatch

`routeSampler`, not `dfrouter`, per SUMO's warning about implausible routes in meshed city networks.
Route pool of 43,200 routes, seed 42, envelope recorded.

Sampled demand: **746,440 vehicles**, achieving **91.32%** of observed counts, **zero overflow**
anywhere. All 1,788 cells appear in the mismatch output; 159 underflow. The shortfall is
concentrated: 18 of 149 edges underflow at all, and two carry 59% of it.

## Calibration, comparison and uncertainty

**None performed.** No calibration ran, no held-out evaluation ran, no observed-versus-simulated
comparison ran, and no uncertainty result exists. Each is blocked as recorded above, and no
placeholder was produced for any of them.

## SUMO and FCD

The controlled boundary is built and tested: frozen command, one-second step, one-second FCD, seeded,
no shell, atomic promotion only after a zero exit and a digested FCD.

**No accepted simulation output exists.** A one-hour diagnostic found the candidate demand gridlocks:
halting share climbed 49.8% → 88.8%, teleports rose 113 → 21,669 reaching 35.7% of inserted vehicles,
insertion rate more than halved, and only 8.1% of the demand entered the network. A full-window run
would have produced tens of gigabytes describing a stationary network. It was not run.

## VEC stages

**None executed.** VEC-06 through VEC-12 need an accepted one-second FCD and network pair, which does
not exist.

## Checks

| Check | Result |
|---|---|
| Full test suite | **3,087 passed, 1 xfailed** |
| Ruff lint and format | clean repository-wide, 746 files |
| Strict mypy | clean, 728 files |
| `uv lock --check` | unchanged |
| Generated reference | no drift |
| `git diff --check` | clean |
| Fixture immutability | unchanged |
| Private paths in tracked files | none |
| Container build / demo smoke | **not run** — needs Docker |

The single expected failure is a real defect: `home.py` renders two buttons both labelled *Plan an
Experiment*. Marked **strict**, so the suite fails when it is fixed.

## Capability and gate status

**Nothing was advanced.** `MAN-09` remains `planned`. Gate D and Gate E remain `foundation_only`.
`MAN-10`, `MAN-11` and Gate F are unchanged. Completing a candidate workflow justifies at most
`working_bounded`, and that was not claimed either.

## Remaining blockers

**Owner decisions:**

1. The candidate demand gridlocks; regenerating the route pool with a realistic trip-length mix
   changes its provenance.
2. 165 map-match rows await manual review; policy v1.1 requires a person.
3. Whether GEH is an acceptance criterion, and at what threshold.

**Lead action:** register the comparison contract fingerprint; the registry is outside the agent
grant.

**Provider replies:** `GA-DFT-1` (DfT hour timezone), `GA-WT-1` (WebTRIS clock semantics), BODS
retention and republication terms. The documentation probe established that no official page answers
these.

**Human evidence:** the manual accessibility checklist, shipping unticked and unsigned.

## Boundaries confirmed

| Ref | State |
|---|---|
| `main` | `1c50a25`, unchanged, still the v0.6.0 release line |
| `v0.6.0` | `bb1fef2`, unmoved |
| `v0.7.0-alpha.4` | `e2cf844`, unmoved |
| `v0.7.0-alpha.5` | `c826624`, unmoved |
| `v0.7.0-alpha.6` | `8da5546`, unmoved |
| final `v0.7.0` tag | does not exist |
| user checkout `~/AntigravityTest/diss` | `4e95a5d`, untouched, only its pre-existing untracked directory |
| `supervisor questions2 Gemini/` | untouched |
| `../external/` | untouched |

Nothing was force-pushed. No tag was created or moved.

## What the lead is asked to decide

1. Whether to create `v0.7.0-alpha.7` at `b50f27d`, and whether that name is right.
2. Whether to fast-forward `codex/traffictwin-v0.7` as was done for alpha.6.

Neither has been done. The tag does not exist and no branch was moved.
