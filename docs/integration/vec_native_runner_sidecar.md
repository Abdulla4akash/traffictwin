# Native VEC runner sidecar boundary v1

**Implemented:** 6 August 2026
**Method:** `vec-native-runner-sidecar-1.0`
**Status:** provisional read-only structural integration; current pinned evaluator emits no native
sidecars and no scientific evidence is created

## Why this boundary exists

The audited VEC-07 runner safely executes the pinned evaluator and validates `run.json`,
`per-step.npz` and `per-task.npz`. That evaluator has no flags or outputs for stable task identity,
admission/rejection, reservations, forwarding, execution, physical return or dispatcher decisions.
Those events cannot be reconstructed from `task_met` or modelled latency.

The native-runner sidecar adds a future-facing validation boundary without modifying or wrapping
the pinned external source. A future native evaluator or reviewed adapter may write a separate
sidecar directory. TrafficTwin can then exact-bind and structurally validate those bytes against a
successful existing `VecExecutionReceipt`.

The sidecar verifier is additive. It does not write into a completed read-only runner directory,
add evaluator flags, launch a run, modify either external repository or claim that the current
evaluator already implements the new contract.

## Manifest and exact files

`native-manifest.json` binds exactly three non-empty JSONL files:

| Role | Record model | Purpose |
|---|---|---|
| `lifecycle_events` | `VecTaskLifecycleEvent` | complete per-task offered-to-terminal ledger |
| `dispatch_requests` | `VecDispatchRequest` | common candidate state/cost snapshot for each V2I task |
| `dispatch_decisions` | `VecDispatchDecision` | recorded deterministic execution-RSU reservation decision |

Every binding includes a safe relative `.jsonl` path, byte size, SHA-256 and exact media type.
The manifest also records producer id/version/kind, declared semantics status, deterministic policy
and the provisional rule that an unavailable execution target maps to one explicit ingress
rejection.

The manifest exact-binds one successful runner receipt through:

- `run_id`;
- runner request fingerprint;
- runner output fingerprint; and
- complete runner receipt fingerprint.

The validator refuses unsuccessful or unpublished receipts. A matching fingerprint establishes
identity, not producer authenticity or scientific truth.

## Read-only safety controls

`validate_vec_native_sidecar()`:

- requires a direct readable directory;
- accepts only bounded POSIX-relative manifest and JSONL paths;
- rejects symbolic links, missing files, root escapes and non-regular files;
- limits the manifest to 1 MB;
- limits each role file to 256 MB, the combined sidecar to 512 MB, each role to one million
  records and each line to 1 MB;
- verifies declared size and SHA-256 before parsing;
- uses strict frozen Pydantic record models; and
- performs no writes, process launch, network access or external-repository access.

Private source identities, raw mobility traces, checkpoints and machine paths are neither required
nor published by this contract.

## Replay and joins

Validation proceeds in four independent stages:

1. strict manifest and runner-receipt binding;
2. complete lifecycle replay through `validate_vec_task_lifecycle()`;
3. reservation-aware policy replay through `dispatch_vec_batch()`; and
4. exact V2I task and node joins between both artifacts.

The recorded decisions must equal deterministic replay byte-for-model after canonical ordering.
Every lifecycle task whose action is V2I must have exactly one request and one decision; local and
V2V tasks are not dispatched through this interface.

For a selected target, the join checks:

- request ingress equals lifecycle ingress;
- no-forwarding produces one retained path at ingress;
- forwarding begins at ingress and ends at the selected execution RSU;
- any execution/start/completion/drop node equals the selected RSU; and
- any result-return or return-failure source equals the selected RSU.

The join permits explicit drop and result-return failure. A selection is not relabelled as physical
success.

For `no_execution_target`, v1 requires one explicit `rejected` event at the ingress. This is a
manifest-declared provisional rule, not a claim about current upstream behaviour. A later producer
semantics version must change the contract if unavailable work should instead queue, retry, fall
back, forward elsewhere or take another outcome.

Reports reconcile:

```text
V2I lifecycle tasks = dispatcher requests = dispatcher decisions
V2I tasks = selected lifecycle paths + explicit unavailable rejections
```

They also retain the lifecycle and dispatcher task/reservation conservation reports.

## Current implementation result

Synthetic tests prove the sidecar validator can accept:

- the exact strong-link-full/weaker-link-idle two-RSU selected/forwarded case;
- strongest-link/no-forwarding with explicit ingress rejection; and
- a selected path that reaches explicit result-return failure rather than success.

Tests fail closed for file-byte drift, receipt-binding drift, unsuccessful receipts, recorded
decision tampering, V2I task-set mismatch, lifecycle execution-target mismatch and symbolic links.

The report structurally declares:

- `current_pinned_evaluator_emits_sidecars = false`;
- `producer_authenticated = false`; and
- `scientific_evidence = false`.

## What remains before a native run exists

The runner-side validation boundary is built. Actual native production remains unbuilt because the
pinned evaluator is restricted and emits none of the required files. Completion requires one of:

1. upstream producer confirmation plus a reviewed native evaluator revision that emits the exact
   contract; or
2. an authorised, reviewed adapter operating from genuinely available native events rather than
   legacy aggregate arrays.

After that, a separate integration must supply the sidecar during an authorised run, preserve the
producer provenance, validate it here, and only then consider runner/admission wiring. A matched
policy campaign, scientific metrics, learned scheduler and actor retraining remain later separate
work. The implemented [matched dispatch study](vec_matched_dispatch_study.md) compares all three
policies only on exact-matched synthetic request batches; it does not substitute for those native
events or a realised policy campaign.

No campaign, registry, checkpoint, approval, evidence or digest-bound artifact is read or changed
by this module.
