# Bounded VEC Campaign Execution

Status: implemented `vec-bounded-campaign-1.0` (ADR-063).

A campaign is the deterministic execution of one **already predeclared and approved** run
matrix. It exists because a multi-cell design previously had to be executed by hand, one
request at a time, with no budget, no resumability, and no record binding the runs to the
design they were supposed to test.

Library: `traffictwin.integration.vec_campaign`

The service composes accepted services and adds nothing scientific: it computes no metric,
selects no threshold, and records no conclusion. Every admitted cell is an owner-approved
candidate fresh-run admission ([ADR-061](../decisions/ADR-061-vec-fresh-run-scientific-admission.md))
with reproduction explicitly ungraded.

## Approval is required, and it is bound to bytes

A `VecCampaignDesign` cannot be constructed without a `VecCampaignApproval` naming a real
approver and role, an approval timestamp, and the **SHA-256 of the predeclaration document**.
Before any cell runs, the service re-hashes that file and refuses with
`PREDECLARATION_CHANGED_AFTER_APPROVAL` if the bytes differ — so a design edited after
approval cannot execute under the old approval.

Code cannot verify that a person truly approved anything. What it can do, and does:

- refuse to run without an explicit approval record (there is no default);
- reject placeholder identities (`TBD`, `n/a`, `agent`, blank);
- refuse if the approved document changed; and
- keep the approver, role, timestamp, and digest in the receipt.

**Held-out seeds need separate authorisation.** A `held_out` phase design is invalid unless
`held_out_authorised` is explicitly set, so an exploratory campaign cannot silently consume
the seeds reserved for the confirmatory estimate.

## Declared bounds

| Bound | Meaning |
|---|---|
| `max_cells` | The design is rejected outright if arms × seeds exceeds it (hard ceiling 200) |
| `max_total_output_bytes` | A cell whose outputs would exceed the remaining budget is skipped and the campaign halts |
| `halt_on_failure` | Default `True`: the first failed or refused cell halts, and remaining cells are recorded as skipped |
| `timeout_seconds` | Per request, passed to the runner (runner ceiling 7,200 s) |

A failure is recorded with its reason and **never retried with altered controls**. Missing
cells stay missing; nothing is imputed.

## Execution model

Sequential and foreground, in the calling process. No background job, detached process,
persistent queue, scheduler, or concurrency is introduced — the accepted VEC-10 prohibitions
are preserved literally, and the receipt carries `background_execution: False` and
`concurrent_execution: False` as type-level literals.

Cells are ordered **seed-major**: every arm for seed 1, then every arm for seed 2, and so on.
An interrupted campaign therefore holds complete arm coverage for the seeds it finished, which
is what a paired study needs; arm-major ordering would leave every seed half-populated and
yield no usable pairs.

**Resumability** follows from that ordering plus identity checking: a cell whose output
directory already holds an intact `completed` receipt for the *same request fingerprint* is
reused rather than re-executed, and its admission is re-confirmed idempotently. Re-running a
campaign after an interruption costs only the unfinished cells.

## Library use

```python
from traffictwin.integration.vec_campaign import execute_campaign

receipt = execute_campaign(
    design,                                   # approved VecCampaignDesign
    input_root="../external/tos-data",
    vec_repo="../external/vec_env",
    tos_data_repo="../external/tos-data",
    output_root="./local-evidence/capacity-pilot",
    registry_path=".demo/registry.sqlite",
    predeclaration_root=".",
)
```

`register_campaign_experiment` is separately callable and idempotent: it registers the plan
(baseline arm, variation arms, common seed set) that STA-01 needs for pairing, and refuses with
`EXPERIMENT_PLAN_CONFLICT` if an existing plan under the same identifier differs from the
design. This closes the gap where no interface existed to register an `Experiment` at all.

## Analysing a completed campaign

`analyze_campaign(design, receipt, registry_path)` evaluates exactly the comparisons the design
predeclared — each variation arm against the single baseline on the single primary endpoint —
with the accepted STA-01 evaluator at its tool defaults, and
`render_campaign_analysis_markdown` produces one deterministic report.

The analysis artifact is structurally exploratory: `confirmatory: False`,
`significance_claimed: False`, and `owner_approved_candidate` are type-level literals, so the
output cannot be represented as a confirmed finding. It refuses a design/receipt fingerprint
mismatch (`ANALYSIS_DESIGN_MISMATCH`), passes STA-01's own `insufficient`/`incompatible`
statuses through untouched, reports secondary metrics descriptively without promotion, and
states — rather than hides — that the comparisons share one baseline without multiplicity
correction. Interval and randomisation outputs appear verbatim as diagnostics of the
exploratory pilot, never as accepted thresholds.

## What a completed campaign is, and is not

A completed campaign means every declared cell executed and was admitted. It is **not** a
finding, an accepted threshold, a reproduction grade, analyst review, or supervisor approval.
Interpreting the admitted metrics is a separate, separately predeclared analysis step.

## Evidence and tests

- Library: `src/traffictwin/integration/vec_campaign/`
- Decision record: `docs/decisions/ADR-063-bounded-vec-campaign-execution.md`
- Tests: `tests/unit/test_vec_campaign.py`
- Consumes: [fresh-run admission](vec_fresh_run_admission.md),
  [VEC-07 runner](vec_evaluator_runner.md)
- First intended design:
  [capacity-squeeze pilot predeclaration](../evaluation/capacity_squeeze_pilot_predeclaration.md)
  (proposed, unsigned — no campaign may run it until it is signed)
