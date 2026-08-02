# Design — Manchester Gate-D decision support

## Status and purpose

- Phase: 184
- Date: 2 August 2026
- State: implemented as a non-executing decision-support pack
- Evidence class: engineering decision support over committed records

Phase 179 exposes the exact Gate-D dependencies but cannot perform the human/scientific steps. This
phase packages the maximum safe work around the three immediate blockers: the 174-row analyst
review, a production calibration design, and the gridlocking demand candidate. It makes each next
decision answerable without taking the decision.

## Exact owned paths

- `docs/integration/manchester_gate_d_decision_support_20260802.md`
- `docs/integration/evidence/manchester_gate_d_decision_support_20260802.json`
- `tests/unit/test_manchester_gate_d_decision_support.py`
- `docs/index.md`
- `docs/implementation-status.md`
- `docs/current_progress_v0_7.md`
- `CHANGELOG.md`
- `AGENTS.md`

## Source boundary

Only committed public/project records enter the packet. Each source is bound by repository-relative
path and SHA-256. Private network, match-ledger, route-pool, SUMO-output and temporal-profile bytes
stay unopened. The packet copies only bounded counts, status, decision questions and non-claims;
it does not promote an upstream record's evidence class.

The mandatory source set covers the map-policy worksheet, v1.0/v1.1 reconciliations, temporal
profile, chain restoration, original candidate-demand/reconstruction records, saturation and
reachability diagnoses, and the unsigned demand predeclaration/result narrative.

## Reviewer support design

The pack must reconcile 305 offered observations as 131 owner-policy-accepted candidates plus a
174-row queue: 165 awaiting manual review and nine explicit no-suitable-candidate rows. It must
state that zero rows have a human decision. It may provide the permitted decision vocabulary,
required lineage and completion invariants, but must not provide a reviewer identity, preselect a
row outcome or mark a no-candidate row reviewed.

## Calibration support design

The pack must distinguish fixed software-contract choices from choices still needing scientific
approval. Fixed: DfT `vehicle_count`/`vehicles_per_interval`, 3,600-second exact intervals,
simulated-minus-observed residuals, equal-interval weighting, explicit exclusions, no source fusion,
minimum coverage and deterministic rounding. Open: production objective, parameters, bounds/grid,
uncertainty treatment, held-out use, viability/admission rule and contract registration. No default
is silently selected and the frozen production registry remains empty.

## Demand engineering design

The original demand is a refusal: one hour gridlocked. The later diagnosis identifies structural
counted-edge reachability, not fringe weighting or pool size, as the binding constraint. The pack
may define a non-executing coverage-targeted variant contract that requires every counted edge to
have a declared route-support floor, preserves zero/near-zero coverage and the exact seed/network/
input identities, and fails closed before simulation. It must not choose the support floor, edit the
unsigned predeclaration or execute V1–V3/a new variant.

The 1,788-cell/149-edge/2,024,123-vehicle original lineage and the committed
1,800-cell/150-edge/2,027,275-vehicle lineage remain separate. Their 12-cell/one-edge/3,152-vehicle
discrepancy is unresolved; no pack field may average or prefer them.

## Acceptance

Static tests must bind every input digest, reconcile all published counts, keep every human/
supervisor/scientific/contract-registration/run/baseline/comparison flag false, forbid private paths
and credentials, and ensure every open decision has an explicit authority and blocking effect. The
result remains decision support, not a decision, execution receipt or evidence artifact.

## Reconciled reviewer handoff

The review surface is ready for a real named person, but no review has occurred. The queue binds
policy v1.1 and accounts for every row:

| Inventory | Rows |
|---|---:|
| Observations offered | 305 |
| Owner-policy-accepted candidates | 131 |
| Awaiting manual review | 165 |
| No suitable candidate, preserved in the queue | 9 |
| Queue total | 174 |
| Live human decisions | **0** |

The existing sealed-ledger contract permits one `accept_group`, `reject_all_candidates` or `defer`
decision at a time. Every decision requires a real name, role, reason and UTC timestamp; an accepted
group must exist in that exact row. A revised decision supersedes an earlier fingerprint instead of
overwriting it. The safe next action is therefore a named reviewer session over the existing Match
Review page, followed by seal verification and the existing full-queue reconciliation—not a bulk
default. This pack deliberately contains no row ids, candidate group keys, person or decision.

## Calibration decision sheet

The pure evaluator is ready for already-completed compatible candidates. Its production registry
is intentionally empty. These are the remaining choices; none has been filled by Phase 184.

| ID | Choice still required | Why it cannot be inferred | Authority / blocks |
|---|---|---|---|
| C1 | MAE or RMSE as the predeclared production objective | Both are implemented and express different loss sensitivity | Scientific lead; contract admission |
| C2 | Parameter names, units, bounds and finite permitted grids | A runnable search space is a scientific/model choice, not a software default | Scientific lead; candidate generation |
| C3 | Uncertainty treatment and reporting | One selected point estimate cannot establish robustness | Scientific lead/supervisor; baseline review |
| C4 | Development/held-out use and leakage controls | The source supplies a fixed site-coherent split, but its use must be declared before results | Scientific lead; candidate evaluation |
| C5 | Viability/admission rule beyond objective ranking | Lowest error alone does not establish a usable traffic state | Scientific lead; baseline eligibility |
| C6 | Exact production-contract fingerprint registration | Registration is an authority act after C1–C5, not proof by self-declaration | Integrating lead after approval; real objectives |

Already fixed and not reopened here: DfT raw `vehicle_count`, `vehicles_per_interval`, exact
3,600-second intervals, local-clock-hour labels, no resampling/source fusion/zero filling,
simulated-minus-observed residual direction, equal-interval weighting, explicit per-side coverage,
0.001 half-even output precision and descriptive non-causal interpretation. The open DfT hour
timezone question still prevents a UTC projection, but it does not erase the declared local-clock
calibration basis.

## Demand engineering diagnosis and build-ready boundary

The original 746,440-vehicle candidate achieved 91.32% of counts and zero overflow, yet its bounded
one-hour diagnostic admitted only 8.1% of demand, reached 88.8% halting and teleported 35.7% of
inserted vehicles. It is a refusal, not a calibration baseline.

The later deterministic reproduction confirmed that the recorded fringe hypothesis is not the
binding mechanism. Only 28/43,200 pool routes begin on an entry-fringe edge. Instead, four of 150
counted edges have zero pool coverage; two more have only two covering routes. Those six edges
account for 122,235 unmet vehicles, 72.79% of all unmet demand. Doubling a coverage of zero cannot
repair it.

The safe engineering design for a future coverage-targeted variant is now explicit:

1. bind one exact observation input, accepted study network, counted-edge inventory, tool/runtime,
   seed and generation policy before route creation;
2. declare a per-counted-edge route-support criterion before measuring the new pool;
3. retain zero- and near-zero-coverage edges individually and refuse the candidate if the declared
   support contract is not met—never average them into the network median;
4. preserve generated routes as synthetic/count-constrained candidates, never observed journeys;
5. run the already proposed bounded viability checks only after an amended protocol is approved;
6. preserve every mismatch, exclusion, teleport and non-insertion outcome; and
7. admit nothing to calibration or comparison until the review, viability and production-contract
   gates are separately complete.

This is design, not protocol amendment or execution. The route-support criterion and E1–E5
predeclaration choices remain for the owner/scientific lead.

## Non-reconciling input lineages

| Field | Original alpha.7 record | Later committed reconstruction | Difference |
|---|---:|---:|---:|
| Counted edges | 149 | 150 | 1 |
| Cells | 1,788 | 1,800 | 12 |
| Observed vehicles | 2,024,123 | 2,027,275 | 3,152 |
| Measured-zero cells | 11 | 11 | 0 |

No single committed edge totals 3,152 vehicles, so removing one edge cannot reproduce the original
record. This is an exact-input blocker, not rounding noise. A future protocol must bind one
recovered/accepted input identity; Phase 184 neither chooses a lineage nor claims the missing bytes
exist.

## What can happen next, in dependency order

1. A named person completes and seals the 174-row review ledger.
2. The exact observation input discrepancy is resolved from authorised source artifacts or remains
   a declared refusal.
3. The owner/scientific lead amends and signs the demand protocol, including route-support and
   viability rules, before any new pool is generated.
4. A compatible bounded candidate passes the full viability contract with all deviations retained.
5. C1–C5 are predeclared, the exact calibration fingerprint is registered under authority, and
   compatible candidates are evaluated against development/held-out evidence.
6. A person accepts or refuses a versioned baseline; only then can the separate comparison contract
   produce descriptive Manchester results.

Work on steps 1–6 needs concrete human authority, private input bytes or execution evidence. The
code/contracts already refuse to manufacture them.

## Verification result

The companion JSON binds all 15 source digests and machine-checks the queue, calibration, demand
and non-claim invariants. The seven-file decision-support, Gate-D, observation-review,
calibration and demand regression passed all 198 tests. Ruff format/check, repository-wide strict
mypy across 891 configured files, JSON parsing, privacy and diff gates passed.
