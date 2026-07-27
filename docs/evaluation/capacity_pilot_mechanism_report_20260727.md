# Campaign mechanism exhibit — `vec-capacity-squeeze-pilot`

Status: **exploratory, owner_approved_candidate, descriptive non-causal.** Owner-approved-candidate is not supervisor approval,
not ethics approval, not validation, and not a causal claim. Every value in this
exhibit was recorded by the campaign analysis and is re-presented here, not
recomputed.

## Source identity

| Field | Value |
|---|---|
| Source analysis file | `campaign_analysis.json` |
| Source SHA-256 | `7507639a41ad8b287e5a6f4103ba3739a323adf5382a772d29e13849e9421ac9` |
| Experiment | `vec-capacity-squeeze-pilot` |
| Design fingerprint | `de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90` |
| Campaign status | `completed` |
| Analysis method version | `vec-campaign-analysis-1.0` |
| Analysis generated at | `2026-07-27T09:31:46.676341+00:00` |
| Primary endpoint | `tos.task.deadline_success.rate` |
| Baseline arm | `cap-2.5` |
| Admitted collections | 12 |
| Confirmatory | `False` |
| Significance claimed | `False` |

**Reading the adjacent-arm range comparison.** Pooled per-arm ranges and per-seed ordering answer different questions. Ranges pooled across seeds can overlap whenever between-seed variation exceeds adjacent-arm separation, while every individual seed still ranks the two arms the same way. The paired within-seed contrast is what the statistical machinery uses. Citing only the pooled ranges understates the evidence; citing only the ordering overstates it. The table below reports both, separately, and neither is a claim about cause.

## Related records

- Corrected pilot results record: [capacity_pilot_results_20260727.md](capacity_pilot_results_20260727.md) — §2 records the 27 July 2026 correction to the range-overlap wording that this exhibit follows.
- Pilot predeclaration: [capacity_squeeze_pilot_predeclaration.md](capacity_squeeze_pilot_predeclaration.md).

## Limitations, copied from the analysis

- Exploratory owner-approved-candidate evidence only; no confirmatory claim, no significance claim, and no scientific acceptance is made by this analysis.
- The comparisons share one baseline without multiplicity correction; the predeclaration reserves any corrected claim for the separately signed confirmatory protocol on the held-out seeds.
- Deadline success is never physical completion; reconstructed evaluator behaviour is never an observed journey; results describe one audited policy on one reviewed trace with one fleet preset.
- Interval and randomisation outputs are reported verbatim as STA-01 diagnostics of the exploratory pilot, not as accepted thresholds.

---

Everything below is the accepted mechanism renderer's output, verbatim.

# Mechanism evidence — `vec-capacity-squeeze-pilot`

**Status: descriptive, non-causal, exploratory owner-approved-candidate evidence.** This report re-presents values the campaign analysis already recorded. It makes no confirmatory claim, no significance claim, and no causal claim.

- Method: `vec-campaign-mechanism-report-1.0` (schema 1.0)
- Design fingerprint: `de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90`
- Campaign status: `completed`
- Primary endpoint: `tos.task.deadline_success.rate` (baseline arm `cap-2.5`)
- Arms: `cap-2.5`, `cap-1.5`, `cap-1.0`, `cap-0.75`
- Seeds: 0, 1, 2

## Per-seed values, primary endpoint

| Metric | Seed | `cap-2.5` | `cap-1.5` | `cap-1.0` | `cap-0.75` |
|---|---:|---:|---:|---:|---:|
| `tos.task.deadline_success.rate` | 0 | 0.792485 | 0.792816 | 0.793023 | 0.793179 |
| `tos.task.deadline_success.rate` | 1 | 0.812794 | 0.812794 | 0.812794 | 0.813074 |
| `tos.task.deadline_success.rate` | 2 | 0.765957 | 0.765957 | 0.765957 | 0.765957 |

## Per-seed values, secondary metrics (never promoted)

| Metric | Seed | `cap-2.5` | `cap-1.5` | `cap-1.0` | `cap-0.75` |
|---|---:|---:|---:|---:|---:|
| `task.latency.mean_ms` | 0 | 9942.563798 | 6061.686519 | 4067.958672 | 3060.747361 |
| `task.latency.mean_ms` | 1 | 6277.913026 | 3961.823668 | 2771.938781 | 2097.706373 |
| `task.latency.mean_ms` | 2 | 13176.048910 | 8065.249630 | 5429.706271 | 4092.354953 |
| `task.offload.rate` | 0 | 0.402608 | 0.402608 | 0.402608 | 0.402608 |
| `task.offload.rate` | 1 | 0.406350 | 0.406350 | 0.406350 | 0.406350 |
| `task.offload.rate` | 2 | 0.414181 | 0.414181 | 0.414181 | 0.414181 |
| `tos.task.no_eligible_target.rate_among_offload` | 0 | 0.000020 | 0.000020 | 0.000020 | 0.000020 |
| `tos.task.no_eligible_target.rate_among_offload` | 1 | 0.000016 | 0.000016 | 0.000016 | 0.000016 |
| `tos.task.no_eligible_target.rate_among_offload` | 2 | 0.000037 | 0.000037 | 0.000037 | 0.000037 |

## Invariance to the control

A metric is invariant in a seed when every arm recorded exactly the same value — the control moved the arms, and the metric did not follow.

| Metric | Seeds | Invariant seeds | Invariant in every seed | Max spread |
|---|---:|---:|:---:|---:|
| `tos.task.deadline_success.rate` | 3 | 1 | no | 0.000694 |
| `task.latency.mean_ms` | 3 | 0 | no | 9083.693957 |
| `task.offload.rate` | 3 | 3 | **yes** | 0.000000 |
| `tos.task.no_eligible_target.rate_among_offload` | 3 | 3 | **yes** | 0.000000 |

Bit-identical across every arm within every seed: `task.offload.rate`, `tos.task.no_eligible_target.rate_among_offload`. In this grid the control did not move these metrics at all.

## Adjacent-arm range comparison

Range overlap compares each arm's across-seed minimum and maximum. Per-seed ordering asks whether every shared seed ranks the pair the same way. The two answer different questions and can differ.

| Metric | Lower arm | Upper arm | Lower range | Upper range | Ranges overlap | Pairs | Ordering consistent |
|---|---|---|---|---|:---:|---:|:---:|
| `tos.task.deadline_success.rate` | `cap-2.5` | `cap-1.5` | [0.765957, 0.812794] | [0.765957, 0.812794] | yes | 3 | no |
| `tos.task.deadline_success.rate` | `cap-1.5` | `cap-1.0` | [0.765957, 0.812794] | [0.765957, 0.812794] | yes | 3 | no |
| `tos.task.deadline_success.rate` | `cap-1.0` | `cap-0.75` | [0.765957, 0.812794] | [0.765957, 0.813074] | yes | 3 | no |
| `task.latency.mean_ms` | `cap-2.5` | `cap-1.5` | [6277.913026, 13176.048910] | [3961.823668, 8065.249630] | yes | 3 | yes |
| `task.latency.mean_ms` | `cap-1.5` | `cap-1.0` | [3961.823668, 8065.249630] | [2771.938781, 5429.706271] | yes | 3 | yes |
| `task.latency.mean_ms` | `cap-1.0` | `cap-0.75` | [2771.938781, 5429.706271] | [2097.706373, 4092.354953] | yes | 3 | yes |
| `task.offload.rate` | `cap-2.5` | `cap-1.5` | [0.402608, 0.414181] | [0.402608, 0.414181] | yes | 3 | yes |
| `task.offload.rate` | `cap-1.5` | `cap-1.0` | [0.402608, 0.414181] | [0.402608, 0.414181] | yes | 3 | yes |
| `task.offload.rate` | `cap-1.0` | `cap-0.75` | [0.402608, 0.414181] | [0.402608, 0.414181] | yes | 3 | yes |
| `tos.task.no_eligible_target.rate_among_offload` | `cap-2.5` | `cap-1.5` | [0.000016, 0.000037] | [0.000016, 0.000037] | yes | 3 | yes |
| `tos.task.no_eligible_target.rate_among_offload` | `cap-1.5` | `cap-1.0` | [0.000016, 0.000037] | [0.000016, 0.000037] | yes | 3 | yes |
| `tos.task.no_eligible_target.rate_among_offload` | `cap-1.0` | `cap-0.75` | [0.000016, 0.000037] | [0.000016, 0.000037] | yes | 3 | yes |

## Limitations

- Descriptive, non-causal, exploratory re-presentation of values the campaign analysis already recorded; it establishes no mechanism, only the evidence a person reads a mechanism from.
- Invariance is measured as exact equality of the recorded values across arms within a seed. It shows the control did not move the metric in this grid; it does not prove the metric cannot move.
- Range overlap and per-seed ordering are distinct: overlapping across-seed ranges do not contradict a consistent per-seed ordering, and neither is a significance statement.
- Owner-approved-candidate status throughout — not supervisor approval, not validated, not causal, not generalisable beyond the studied grid.
