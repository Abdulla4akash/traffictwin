# Three-trace generalisation study — 16 September 2026

## Authority and status

Claude proposed this design. The owner explicitly authorised the task in
`OWNER_TASK.md`: three new Manchester traces, five arms, eight paired blocks,
120 full cells and the specified 18 qualification attempts. The purpose is
paper evidence. No manuscript changes, new training or additional studies are
authorised. The starting commit is
`5cbe568c9260c432f3e3ae42b45dcfba7f1a8dbe`, on the requested guarded follow-up
branch; the new branch is `research/dissertation-traces-2026-09-16`.

**Pre-execution draft: not sealed, no evaluator attempts launched.** The
inventory and unchanged runtime preflight are complete. `SOURCE_COMPATIBILITY.md`
records conflicts between the literal task and the sealed code. The proposed
clarification below is awaiting owner confirmation; it is not an approved
amendment and must not be treated as execution authority. An execution seal
must bind the final protocol, source/configuration identities, qualification
receipts and independent source review before any full outcomes.

## Trace selection

All eight local candidates were inventoried. The three candidate files on
the fetched vec_env GitHub `main` at
`0f01f4d2082d3e8b735e74a873095ab8eeba37cc` are byte-identical to local files;
the cached `origin/main` resolves to that same commit. Complete file and array
hashes, embedded window, SUMO seed and selection ranks are in
`TRACE_INVENTORY.json`.

| Trace | Local date/window | T | N | R | Selected file | Queue convention |
|---|---|---:|---:|---:|---|---|
| Weekend `we` | Sun 2024-09-15, 12:00–21:00 | 32,400 | 139 | 9 | `trace_we_wdrsu.npz` | Per-visit entry reset |
| PM `wd_pm` | Tue 2024-10-15, 14:00–21:00 | 25,200 | 163 | 10 | `trace_wd_pm_fullrsu.npz` | Legacy mask-only reset |
| Event `ev` | Wed 2024-09-18, 17:30–24:00 | 23,400 | 175 | 12 | `trace_ev_fullrsu.npz` | Legacy mask-only reset |

All three embed SUMO seed 42. Preference is fixed wdrsu with `enter`, then
fullrsu with `enter`, then legacy fullrsu. R differs across scenarios by design.
The inputs are preserved unchanged; no trace reconstruction is authorised.

The PM and event inputs retain the earlier convention without the same entry
channel, as the dissertation documents for the incident trace. A slot may be
immediately reused while its mask remains true, allowing the new visit to
inherit queue backlog. Conserved queues do not eliminate that trace limitation.
Comparisons are conditional on each selected scenario and convention; density,
RSU count, slot assignment and entry semantics can differ across traces.

The tos-data morning fullrsu file is **not array-identical** to the confirmation
wdrsu input. It lacks `enter`; mask, x/y positions and speed differ. T, N,
timestamps, dt, RSU coordinates, embedded window and SUMO seed agree. Exact
changed-element counts, maximum absolute numeric differences and per-array
hashes are recorded in the inventory. The existing morning result uses its
original confirmation trace; it is not rerun or relabelled as the tos-data file.

## Fixed intervention design

Arms in base order: `ingress_dla`, `dla` (common-target), `per_task_dla`,
`causal_round_robin`, `dla_p2c`. Rotate this list left by block index modulo
five. Each trace uses blocks 0–7 with fleet/evaluator pairs (100,200) through
(107,207): 40 full cells per trace, 120 total, 24 complete blocks.

Original actor SHA-256:
`93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`.
UK2030 fleet; arrival 1.5; absolute per-RSU count capacity 6,220; RSU service
multiplier 1; zero forwarding latency charge; scaling off; sequential queue
accounting with three reconciliation iterations; cap mode reject; conserved
vehicle queues; K=5. Actor weights are frozen; observations, logits and actions
may respond endogenously to the scheduler intervention.

`--ignore-enter` is **false/absent** and `--reset-soc-on-enter` is
**false/absent**, exactly as in the morning command. Therefore `enter_reset`
is true for weekend and false for the two legacy inputs. SoC persists across
slot reuse for all traces. This follows the unchanged evaluator's existing
input-dependent behaviour.

Runtime: the venv at
`~/Downloads/diss_mat/vec_env-state-delay/.venv`, CPython 3.11.15,
JAX/JAXlib 0.4.30, NumPy 1.26.4, CPU, x64 off. Reuse the numerical environment
from the morning seal. Keep the versioned `evaluator_v2.py`, scheduling kernels,
service equations and validation tolerances unchanged.

Primary outcome: 100 × deadline successes / all offered tasks. Rejected tasks
remain in the denominator. Equal weighting applies to block effects, not to
pooled task counts. Deadline comparison is inclusive; rejected tasks retain the
ten-times-deadline penalty.

## Qualification and proposed clarification

Literal B.4 requires five 300-step instrumented cells and one fresh-process
150-step `per_task_dla` restart per trace, fleet/evaluator pair (1,0). All three
traces must finish their qualification decision before any full run. Failure
stops the affected trace with incomplete evidence retained; no repair of
scientific code, retry or seed substitution is authorised.

**Pending owner amendment:** use the sealed 14 exogenous input hashes to
require exact cross-arm matching; record endogenous differences. Require the
complete 59-array instrumented schema (43 per-step, 16 per-task) and exact
150-step restart prefix equality. The historical “83 shared scientific fields”
count belongs to same-arm frozen/instrumented comparisons including summary
fields, not cross-arm equality or prefix summary equality. No additional
reference runs are proposed. Trace-specific dimensions and entry-channel
expectations must be configuration parameters in validation and two-choice
replay; all arithmetic and tolerances remain fixed.

Keep exact discrete/count checks, 1e-6-task reconstructed-summary tolerance,
0.01 ms absolute per-queue service conservation, and drain absolute 0.001 ms
plus relative 1e-6. Preserve queue reset/carry, service/count conservation,
round-robin progression and native two-choice proposal replay checks. Do not
relax tolerances in response to outcomes.

## Execution controls

Three independent runner processes, one per trace, serial internally. Raw
roots: `~/Downloads/diss_mat/traffictwin-traces-raw-2026-09-16/<trace>/`, each
with its own exclusive lock. Check at least 40 GB free before start and 10 GB
before each attempt; conservative GiB thresholds may be used. Timeout is
10,800 seconds per cell. Verify peak RSS on the first cell per trace; if any
exceeds 4.5 GB, limit concurrency to two while preserving active attempts.
No platform-capture task runs concurrently. The 3–4 hour estimate is a planning
estimate, not measured completion evidence.

Retain each command, allowed numerical environment, source/input hashes,
timestamps, logs, arrays, summary and validation/failure receipt. Bind five
cell receipts and cross-arm controls into each block receipt. No overwrite,
retry, extra full cells or seed substitution. Qualification failures cannot
be hidden by launching replacement attempts.

## Analysis fixed before outcomes

For each trace, compute these five contrasts from eight equal-weight paired
block differences, using sample SD and Student-t with df=7:

1. Per-task − ingress.
2. Common-target − ingress.
3. Per-task − round-robin.
4. Per-task − two-choice.
5. Two-choice − round-robin.

Report individual 95% intervals, within-trace Bonferroni simultaneous 95%
intervals (family 5), and conservative Bonferroni simultaneous 95% intervals
across all 15 contrasts. The critical value is t(1−0.05/(2m),7), m=1,5,15.
No cross-trace pooling or test, task-level test, outcome-driven expansion or
equivalence claim from non-significance. Report every result, including
negative and inconclusive estimates. A stopped trace has unavailable outcomes,
not zero effects or an eight-block estimate based on fewer completed blocks.

Descriptive plots relate per-task-minus-ingress and per-task-minus-round-robin
margins to mean active vehicles per second across the five scenarios. Existing
incident and morning points retain their archived designs: four incident fleet
draws versus eight morning joint-seed blocks. E2c/E2d have no round-robin arm.
**Pending clarification:** mark the incident round-robin margin unavailable;
do not create a value or run an unauthorised incident cell. The incident
per-task-minus-ingress point is available. Use the confirmation trace, rather
than tos-data's differing morning array, for the morning density coordinate.

## Deliverables and reporting

The completed study requires qualification receipts, 120 cell receipts,
24 block receipts, `CELL_RESULTS.csv`, `PAIRED_EFFECTS.csv`, `ANALYSIS.json`,
independent `FINAL_ANALYSIS_AUDIT.json`, `RESULTS.md`, `FINDINGS.md`, a
three-panel contrast dot plot and descriptive density plot. Raw arrays stay
local, listed by `RAW_INVENTORY.json`. Place the compact packet ZIP and checksums
under `~/Desktop/Dissertation/Experiments 10-12 - 2026-09-16/`.

Commit and push the protocol, configuration and results on the new branch;
open a draft PR and do not merge. Final reporting must distinguish attempted,
validated, failed and unstarted cells, give measured wall time per trace and
all 15 contrasts with all-15 intervals. Until execution completes these are
unavailable, and no result-complete status or fabricated result files may be
issued.
