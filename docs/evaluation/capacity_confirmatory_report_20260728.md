# Confirmatory result — `vec-capacity-confirmatory`

**One predeclared contrast, reported under a signed protocol on the reserved held-out cohort.** Every number outside the confirmatory section below is descriptive context and carries no confirmatory standing.

- Method: `vec-campaign-confirmatory-report-1.0`
- Research status: `owner_approved_candidate` — not supervisor approval, not scientific validation.

## Signed predeclaration and design identity

- Predeclaration: `docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`
- Predeclaration SHA-256: `ac9d6cb7cd24f19ba683352cd3d12d91cbd610343ac392028feb53797bbae2a8`
- Verified unchanged at execution: True
- Approved by: Abdulla (repository owner; delegation relayed in session, 27 July 2026: 'take reasonable choices and keep working' — see the candidate file's decision record; not an owner-typed signature) (repository owner), 2026-07-27T13:30:00+00:00
- Held-out cohort authorised: True
- Design fingerprint: `f289db31ce28b6361f91911485c36483b068fdee1ed73aa1d4ef0a8b57bc1754`
- Phase: `held_out`
- Predeclared research question: Does tightening per-vehicle RSU task capacity from 2.5 to 0.75 reduce mean task latency on the Manchester incident trace, confirmed on held-out seeds with the latency primary declared before any held-out data existed?

The campaign-analysis artifact this report reads is itself typed `confirmatory: false`, and that is correct: running the harness is not what makes a result confirmatory. The signed predeclaration, the bound digest, the authorised held-out cohort, and the completed declared matrix are — and this report renders only after verifying all four.

## The confirmatory result

Predeclared primary endpoint `task.latency.mean_ms`, arm `cap-0.75` against baseline arm `cap-2.5`, paired on the declared seed cohort.

| Quantity | Value |
|---|---|
| STA-01 study status | `available` |
| Admitted pairs | 5 |
| Estimate (variation − baseline) | -8310.902397 |
| Bootstrap interval | [-9097.525837, -7524.278957] |
| Randomisation p-value | 0.0625 |
| Effect direction | variation below baseline |

Direction is the sign of the estimate and nothing more. Whether that direction is desirable is a reading of the endpoint, which this report does not make. The interval and p-value are STA-01's own outputs, reproduced verbatim; no threshold is applied to them here.

## Descriptive context (not the confirmatory result)

Every value below is descriptive. The predeclared contrast is the one above; nothing here is a second result, and the design's 2 arms are reported for completeness only.

### Primary endpoint per arm — descriptive (`task.latency.mean_ms`)

| Arm | Metric | Seeds | Mean | Min | Max |
|---|---|---:|---:|---:|---:|
| `cap-2.5` | `task.latency.mean_ms` | 5 | 12027.492993 | 10372.393341 | 13446.381830 |
| `cap-0.75` | `task.latency.mean_ms` | 5 | 3716.590596 | 3283.107716 | 4182.427360 |

### Secondary metrics per arm — descriptive, never promoted

| Arm | Metric | Seeds | Mean | Min | Max |
|---|---|---:|---:|---:|---:|
| `cap-2.5` | `task.latency.mean_ms` | 5 | 12027.492993 | 10372.393341 | 13446.381830 |
| `cap-0.75` | `task.latency.mean_ms` | 5 | 3716.590596 | 3283.107716 | 4182.427360 |
| `cap-2.5` | `task.offload.rate` | 5 | 0.406864 | 0.398963 | 0.414890 |
| `cap-0.75` | `task.offload.rate` | 5 | 0.406864 | 0.398963 | 0.414890 |
| `cap-2.5` | `tos.task.no_eligible_target.rate_among_offload` | 5 | 0.000022 | 0.000013 | 0.000031 |
| `cap-0.75` | `tos.task.no_eligible_target.rate_among_offload` | 5 | 0.000022 | 0.000013 | 0.000031 |

## Campaign execution evidence

- Campaign status: `completed`
- Declared cells: 10 (admitted 7, reused 3, failed 0, skipped 0)
- Admitted metric collections analysed: 10
- Trace: `traces/trace_inc_fullrsu.npz` (`e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`)
- Actor: `ukfleettrain_mappo_model_c_17`, fleet preset `uk2030`, evaluator seed 0
- Declared fleet-seed cohort size: 5
- Analysis generated at: 2026-07-27T23:33:37.258443+00:00

## What this report does not claim

- It does not claim supervisor approval, ethics approval, or scientific validation.
- It does not claim causality: the contrast isolates one declared evaluator control, not a mechanism.
- It does not declare a result significant, meaningful, or practically important; the only inferential numbers are STA-01's, printed as it produced them.
- It does not generalise beyond this trace, this actor, this fleet preset, and this declared seed cohort.

## Limitations

- Label ceiling `owner_approved_candidate`. This is not supervisor approval, not scientific validation, and not a causal claim.
- Exactly one contrast is confirmatory: the predeclared primary endpoint, baseline against the single variation arm. Every other number in this report is descriptive context and carries no confirmatory standing.
- The estimate, interval, and randomisation p-value are STA-01's own outputs, reproduced verbatim. This report adds no threshold, no verdict, and no significance language of its own.
- A null or reversed primary result is reported with the same prominence as any other, per the predeclaration's publishable-null commitment.
- Deadline success is never physical completion; reconstructed evaluator behaviour is never an observed journey; the result describes one audited policy on one reviewed trace with one fleet preset.

## Predeclared limitations carried from the analysis

- Exploratory owner-approved-candidate evidence only; no confirmatory claim, no significance claim, and no scientific acceptance is made by this analysis.
- The comparisons share one baseline without multiplicity correction; the predeclaration reserves any corrected claim for the separately signed confirmatory protocol on the held-out seeds.
- Deadline success is never physical completion; reconstructed evaluator behaviour is never an observed journey; results describe one audited policy on one reviewed trace with one fleet preset.
- Interval and randomisation outputs are reported verbatim as STA-01 diagnostics of the exploratory pilot, not as accepted thresholds.
