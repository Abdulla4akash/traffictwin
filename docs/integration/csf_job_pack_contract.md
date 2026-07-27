# CSF Job-Pack Contract

Status: implemented `vec-csf-job-pack-1.0` — **contract only, no executor**.

Library: `traffictwin.integration.vec_campaign.job_pack`

University compute (CSF3) has been requested and is not granted. This module exists before
that access does, deliberately, because the order in which the two arrive decides whether
remote results are ever trustworthy. Written first, the contract says what a remote site is
asked to run and what must come back. Written second — after an executor already works — it
would only ever describe whatever the executor happened to produce.

So there is no executor here. No SSH, no network call, no scheduler, no SLURM submission, no
file transfer, and no clock. Two pure directions over supplied models: **export** a pack,
**verify** what comes back.

## Export: one approved design, named inputs, declared cells

`build_job_pack` takes a `VecCampaignDesign` that is *already approved* — approval is the
ADR-063 mechanism and this function does not relax, edit, or re-open it — and returns a
`VecJobPack` containing:

| Part | What it is |
|---|---|
| `design` + `design_fingerprint` | The approved design verbatim, plus the SHA-256 of its canonical form |
| `inputs` | Every input named by repository, audited commit, path, SHA-256, and size |
| `cells` | Exactly arms × fleet seeds, each with the run id and the **request fingerprint the local runner would have produced** |
| `required_output_names` | The payload files a completed cell must return (`per-step.npz`, `per-task.npz`, `run.json`) |
| `limitations` | Carried in the artifact, not only in this document |

`created_at_utc` is a caller-supplied argument rather than a read clock, so the same design
and manifest always produce the same pack bytes. A pack that cannot be reproduced cannot be
checked.

### Identities travel; bytes do not

`external_repository_bytes_included` is a type-level `False`. The manifest tells a remote
site *what to check out and what it must hash to*; it never carries the checkout. A copied
repository is a repository nobody audited, and the whole admission chain rests on the audited
`vec_env` and `tos-data` commits being the ones actually used.

Every `VecJobPackInputRef` is refused unless its `audited_commit` equals the runner's pin for
that repository. Re-pinning is an approval decision (the queued R1 question), not an argument
somebody passes to a pack builder — when a re-pin is approved the runner constants move and
newly built packs follow them.

The manifest is refused unless it names exactly what the design needs: the design's own
reviewed trace (path *and* hash), the pinned actor checkpoint for the design's `actor_id`,
and every pinned evaluator source file with its audited hash.

## Import: are these the runs this pack asked for, intact?

`verify_job_pack_import` takes the pack and the returned `VecExecutionReceipt` set (models,
or the plain dicts of them) and checks, in full, before reporting:

- the returned design fingerprint, when the remote site reported one, matches the pack's;
- every receipt's `request_fingerprint` is one of the pack's declared cells;
- no cell was returned twice, and no receipt is for a cell this pack never declared;
- each completed cell carries every required output file, with no duplicate paths;
- the recorded `output_fingerprint` **recomputes** from the per-file hashes rather than being
  taken on trust; and
- no receipt reports modified audited sources or modified raw inputs.

Cells that did not come back are named in `unfulfilled_run_ids`, never quietly dropped. A
remote run that failed or timed out is recorded with its terminal status and counted as
unfulfilled — reported, not counted as evidence.

| Status | Meaning |
|---|---|
| `verified` | Every declared cell returned, intact, with zero findings |
| `partial` | Nothing is wrong, but at least one declared cell is unfulfilled |
| `refused` | At least one finding: a mismatch, a duplicate, an undeclared cell, a missing output, or an unreadable receipt |

An unreadable receipt is a finding rather than an exception. An importer that dies on the
first malformed payload tells the reader less than one that refuses the whole set and names
what was wrong with it.

## A verified import is not an admission

`admission_granted`, `scientific_admission`, and `registry_write_performed` are type-level
`False` on `VecJobPackImportVerification`, and there is no code path that can set them.

Verification establishes one thing: these artifacts are the ones this pack asked for, and
they came back intact. That is a **precondition** for a scientific decision, not the
decision. Scientific admission remains the existing fresh-run path
([ADR-061](../decisions/ADR-061-vec-fresh-run-scientific-admission.md)), run locally against
the returned artifacts by a person who chose to run it.

Verification also cannot say whether remote compute reproduced local numerics. That is the
separate VEC-08 reconciliation question, and it is still open. A `verified` import from a GPU
node is not evidence that the GPU node computed what a CPU run would have computed.

## What this deliberately does not do

- It does not submit, schedule, queue, poll, cancel, or transfer anything.
- It holds no credential, host name, account, or path on a remote system.
- It writes to no registry and grants no capability.
- It makes no scientific claim about any returned number.

When CSF access is granted, the executor is a separate, separately reviewed piece of work.
This contract is what it will have to satisfy.
