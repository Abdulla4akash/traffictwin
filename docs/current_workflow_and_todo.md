# Current workflow and to-do

**Last reconciled:** 3 August 2026

**Repository baseline:** `main` at `49be6a2db8a69409a1b92fb02e954db7cf1441f6`, with the
package, citation and release metadata aligned at `0.7.0`.

**Active release-engineering branch:** `housekeeping/v0.7-completion`.

This is the short operational tracker. Formal capability truth remains in
[implementation status](implementation-status.md), and the difference between the bounded product
surface and the Meetings 1–3 live goal remains in the
[live feature-gap audit](meeting_1_2_3_live_feature_gap_audit.md). Historical alpha plans and phase
records are evidence of their own checkpoints, not current instructions.

## Current objective

Close the safe v0.7 housekeeping track without converting incomplete product work into a release
claim. The dated
[housekeeping completion record](quality/v07_housekeeping_completion_20260803.md) contains the
inventory, exact verification results and residual owner/input blockers.

The housekeeping track covers:

- version, citation, generated-reference and release-metadata agreement;
- current-document reconciliation and local-link navigation;
- locked dependency, formatting, lint, typing, test and fixture health;
- source and wheel builds plus an isolated wheel-install smoke;
- standalone synthetic-demo verification; and
- CI coverage of generated references, documentation links, fixtures, package installation and
  the existing Python 3.11/3.12 matrix.

These checks establish technical repository hygiene only. The owner subsequently authorised the
annotated `v0.7.0` tag at `e840be6`; neither those checks nor that tag accept `REL-01`, create a
GitHub Release, choose a licence, publish a package, validate a real deployment or accept any
`MAN-*`/`UX-*` capability.

## Current capability posture

All 15 formal v0.7 capability rows remain `planned` under the design's complete-gate rule. The
practical labels below describe tested bounded software, not formal acceptance.

| Area | Practical state | Working boundary | Product-completion boundary |
|---|---|---|---|
| Manchester source acquisition and operations | `working_bounded` | Source-specific adapters, immutable snapshots, explicit refresh, BODS/National Highways process-lifetime workers, stale fallback and read-only health views | Accepted populated real workspace, provider/privacy/retention decisions, broader measured-road access and sustained operational evidence |
| Manchester observation-to-SUMO | `foundation_only` | Complete Greater Manchester network foundation, 305 mapping candidates, 174-row review workflow, DfT profile candidate and calibration/baseline contracts | Named-person decisions for all 174 rows, explicit treatment for nine no-candidate sites, signed science choices, viable demand/runs and a human baseline decision |
| Observed-versus-simulated Manchester evaluation | `foundation_only` | Deterministic pairing, coverage, exclusions, lineage and error engines | Registered accepted contract, compatible real intervals/run, accepted comparison and evaluation evidence |
| Manchester SUMO-to-VEC | `foundation_only` | Strict lineage and VEC admission/orchestration foundations | Accepted Manchester baseline, matching FCD/network, complete controlled VEC chain and admitted results |
| What-if and controlled execution | `working_bounded` | Draft-only composer/surrogate workflow and fixed synthetic-square loopback SUMO transport | Approved generic Manchester scenario execution and accepted evidence; no action authority is currently available |
| Capacity benchmark and decision audit | `working_bounded` | Unsigned job-pack contracts, 21-job synthetic worker and synthetic exact-binding/XAI-shaped integrity fixtures | Signed protocol, authorised actors/checkpoints/runtime/compute, real benchmark results and a validated attribution method |
| Forecasting and journey views | `working_bounded` or offline-only | Bounded bus climatology/surrogate and imported-run journey analysis | Held-out accepted real validation and genuinely prospective Manchester traffic/journey/route advice |
| UX and accessibility | `working_bounded` | Task routes, responsive native UI, automated semantics and bounded browser evidence | Human keyboard/screen-reader/zoom/contrast review and any ethics-approved participant evidence |
| Release isolation and migration | `foundation_only` | Separate workspaces, byte-exact compatibility copy, attested same-schema activation, backup/rollback, coexistence, package alignment, technical build/install evidence and owner-authorised final tag | Real owner-selected workspace acceptance, cross-schema work only if schemas diverge, licence/publication decisions and separately authorised GitHub Release/package publication |

## Product-completion queue

These items are deliberately outside housekeeping and must not be implemented or described as
live without their required inputs and authorities:

1. Populate and operate an accepted Manchester workspace using authorised provider credentials,
   exact contracts and an approved retention/publication policy.
2. Obtain DfT/WebTRIS time-basis answers and resolve the remaining BODS identifier/privacy,
   retention and complete Bee-scope questions.
3. Complete the 174-row named-person mapping review, resolve the nine no-candidate sites, approve
   calibration/uncertainty/demand rules and replace the gridlocking demand candidate.
4. Produce an accepted Manchester SUMO baseline, compatible observed/simulated comparison and
   complete Manchester SUMO-to-VEC evidence chain.
5. Decide whether generic what-if execution, route/infrastructure recommendations, capacity-aware
   training and real explainability are in the accepted product scope; then supply the required
   signed protocols, actors, data and scientific evidence.
6. Perform the human accessibility and, if authorised, ethics-supported participant evaluation.
7. Make the remaining owner-only licence, publication, package-upload, GitHub Release and
   deployment decisions; the final Git tag is complete and must not move.

## Immediate next actions

- Review and merge the housekeeping draft PR only under explicit owner authority; its final-head
  Python 3.11/3.12 branch and draft-PR matrices passed.
- Keep the owner-authorised final `v0.7.0` tag immutable. No GitHub Release, package publication or
  deployment follows from the tag without separate owner authority and licence/publication review.
- Choose the next product-completion item from the queue only after its named human, provider,
  credential, dataset or scientific prerequisite is available.
- Update the live feature-gap audit whenever operational evidence changes; code integration alone
  is not evidence that a capability is live.

## Standing constraints

- The immutable `v0.6.0` tag remains at
  `1c50a25246426128ac6e8530240eff362d16be02` and must never move.
- Synthetic fixtures stay labelled synthetic; source-specific transit/infrastructure evidence is
  never relabelled as general road-flow evidence.
- Raw/private evidence, credentials, identifiers and private absolute paths do not enter Git.
- No agent may invent a provider fact, human review, licence, scientific acceptance, production
  evidence, publication permission or deployment authority.
- No direct merge to `main`, movement of the final tag, GitHub Release, package publication, branch
  deletion or public deployment occurs without explicit owner authorisation.
