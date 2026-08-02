# Design — Benchmark execution infrastructure

**Status: IMPLEMENTED IN PHASE 177. This package operationalises the frozen
Phase-169 candidate protocol for deterministic local inspection and synthetic verification. It
does not sign the predeclaration, implement or train a real actor, submit work, allocate compute,
create a benchmark result, create evidence or admit anything.**

## 1. Purpose and authority boundary

The Phase-169 protocol already fixes the 240 compatible training cells, 2,400 matched training
jobs, algorithm/capacity/action/reward families, budgets and seed namespaces. This slice turns
that immutable plan into a portable package with validation seams that future authorised
producers can implement. It does not change the protocol or manufacture its missing human
signature, actor code, checkpoints, runtime images, domain artifacts, accounts or compute.

There are three deliberately separate products:

1. an unsigned planned-job pack for all 2,400 training jobs;
2. a tiny local synthetic dry-run pack over engineering seeds only; and
3. provider-neutral resource estimates that have no submission method or authority.

Exporting any of these is a local packaging action, not dispatch. The package contains no cloud
client, credential field, shell command, arbitrary plugin import or executable path.

## 2. Contract-only manifests

Every declared family—MAPPO, IPPO, QMIX, VDN, Independent DQN, deterministic heuristic and
random—has one canonical actor-plugin manifest. Each manifest binds the exact Phase-169 candidate
contract digest, algorithm role/paradigm, observation/action/reward adapter contract digests,
checkpoint rule and synthetic-worker interface version. Its binding state is
`contract_only`; `real_implementation_bound`, `scientific_execution_allowed` and
`checkpoint_present` are false.

A canonical local runtime manifest binds only the deterministic in-process synthetic worker,
Python contract version and supported engineering execution class. It has no image, package
installer, network, device or scheduler surface. Manifest identity is the SHA-256 of canonical
JSON; all job and receipt records carry those identities rather than paths or mutable labels.

## 3. Compatible adapters

The infrastructure implements strict, pure adapters for the frozen contract suite:

- observation adaptation delegates capacity construction to the Phase-169 representation and
  envelope rules, preserves base-observation order and records the resulting shape;
- action adaptation maps only indices 0/1/2 to local/V2I/V2V and enforces the feasibility mask
  before returning an action;
- reward adaptation implements one declared deterministic engineering formula for each of the
  four reward tracks and records its adapter digest; and
- all adapter outputs bind the relevant protocol/representation digest and reject NaN, infinite,
  missing, dimensionally incompatible or private content.

These adapters prove interface compatibility. Their synthetic formulas are not literature-backed
training rewards or evidence that a future actor is scientifically valid.

## 4. Planned job pack

The exporter deterministically expands every Phase-169 factorial cell across the exact ten
training seeds. Each of the 2,400 records binds the protocol, factorial-plan, cell, actor-plugin,
runtime, adapter suite, training seed, terminal-checkpoint rule and exactly 5,000,000 matched
interactions. Canonical ordering and newline-delimited canonical JSON yield one reproducible pack
digest.

The pack validator reconstructs the frozen plan and rejects missing/extra/duplicate cells or jobs,
changed budgets, seeds outside the training namespace, mismatched manifests, altered checkpoint
rules, private text and unsigned-dispatch claims. Every planned record is
`proposed_unsigned`, `dispatch_authorised: false` and `evidence: false`.

An atomic local exporter accepts an explicit output root plus a simple filename, refuses symlinks,
traversal, unsafe permissions and overwrite, and returns a path-free byte/digest receipt. It does
not create a queue item or invoke a worker.

## 5. Synthetic worker and return receipts

The dry-run builder creates exactly one representative adapter exercise for each of the seven
algorithm families at each of the three engineering seeds. These 21 jobs are explicitly
`synthetic_dry_run`, have a tiny fixed step budget and are disjoint from the training, tuning and
fresh-evaluation namespaces. The in-process worker uses no actor module, model, optimiser,
simulator, subprocess or network. It emits deterministic endpoint-shaped values, the terminal
synthetic checkpoint and a path-free receipt with `scientific_campaign: false`, `evidence: false`
and `admission_created: false`.

Dispatch validation rechecks the protocol, pack, manifest, adapter, seed and budget immediately
before a synthetic job runs. Return ingestion repeats every check and additionally verifies the
job/attempt/result/checkpoint digests. A duplicate byte-identical receipt is idempotent; a changed
receipt for the same job/attempt refuses. Failed/refused attempts may receive a bounded next
attempt, while completed work cannot be retried.

## 6. Checkpoint inventory and resume

Checkpoint records are content identities, never filesystem locations. Planned learned-family
jobs require the frozen 25/50/75/100 milestone inventory with the terminal checkpoint primary;
evaluation-only controls require no trained checkpoint. The synthetic worker returns only its
separate terminal synthetic checkpoint and cannot satisfy the scientific inventory.

A resume plan is derived solely from the immutable pack plus ingested receipts. It identifies
completed, retryable, exhausted and pending job ids without dispatching them. Seed expansion,
attempt rollback, result mutation and held-out checkpoint selection are typed refusals.

## 7. Resource plan and analysis-input freeze

The provider-neutral resource export reports counts, interactions and the Phase-169 GPU-hour/cost
ceilings as estimates. Provider choices are labels only; `estimate_only: true`, `authority: false`,
`allocation_created: false` and `submission_created: false` are type-level invariants.

Analysis-input freezing accepts only a complete compatible receipt set for the requested execution
class. It sorts records canonically, binds the protocol/job-pack/manifest/result/checkpoint
digests, preserves every deviation and emits an immutable input digest. Synthetic freezes remain
`synthetic_dry_run: true`, `confirmatory: false` and `evidence: false`. A future scientific freeze
must separately prove the exact signed predeclaration and complete planned-job returns; this phase
has no path that weakens that requirement or admits the result.

## 8. Verification and residuals

Focused tests cover all seven manifests, six capacity observations, two action tracks, four reward
tracks, exact 240/2,400 expansion, deterministic export, safe local writing, the 21-job dry run,
dispatch/return budget and namespace enforcement, idempotency, bounded retry/resume, checkpoint
inventory, resource estimates, analysis freezing, private-content screening and adversarial
mutations of digests, seeds, budgets, scope and signature state.

Residuals remain concrete and external: the predeclaration is unsigned; real actor/plugin/runtime
digests, domain artifacts, checkpoint producers, accounts, hardware and separately authorised
campaign execution do not exist. A passing synthetic dry run is software evidence about these
contracts only and is never TrafficTwin benchmark evidence.
