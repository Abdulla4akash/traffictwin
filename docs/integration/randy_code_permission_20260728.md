# Producer Code-Use Permission — Recorded Provenance (28 July 2026)

> **SUPERSEDED IN SCOPE, 29 July 2026.** The three items listed below as *NOT covered* — data
> blobs leaving the machine, publication of data-derived aggregates, and republication of
> repository content — are now recorded as covered by a written producer permission relayed by
> the owner. See
> [`randy_data_and_publication_permission_20260729.md`](randy_data_and_publication_permission_20260729.md).
> **This document is retained unchanged below** because frozen predeclarations link to it by
> path and it records the state under which those campaigns were approved.

**Status: relayed permission, recorded exactly as received; not yet a written contract.**
Shortly after midnight on 28 July 2026 the owner relayed the producer's (Randy Putra's)
statement, given directly to the owner: **"okay — [the owner] can use all the code as
long as it is cited."** The channel was owner–producer direct communication; the exact
wording above is the owner's relay. Converting this into a written record (a one-line
email reply from the producer) remains an open action in the owner action pack, and this
document must be superseded by that written form when it exists.

## Scope — read conservatively

**Covered by the statement (code, with citation):**

- Use of the producer's **code** — the `vec_env` repository (environments, training
  scripts, SLURM launchers, evaluation pipeline) and code files within `tos-data` — for
  this project's research, including execution on owner-managed third-party compute
  (Colab) and CSF, **with citation in every output that uses it**.

**NOT covered — remain open asks in the drafted producer email:**

- The **data blobs** (traces, occupancy, instrumented arrays, checkpoints as data)
  leaving the local machine or CSF for third-party cloud storage or compute.
- **Publication of data-derived aggregates** (metric tables, paired differences, the
  capacity-study numbers) in the dissertation or any public output — the separate
  written data-use permission the drafted email requests.
- Republication or rehosting of any producer repository content.

## Citation obligations this creates

Every artifact that uses the producer's code cites: the repositories
(`gitlab.cs.man.ac.uk/e62992rp/{vec_env,tos-data}`), the pinned commits and engine
version (`v2_post_nrsus_fix`), and the producer's Year-1 report where its findings are
discussed. The dissertation's reference list carries these as first-class entries; the
appendix quick-start already names the repositories.

## What this unlocks immediately

- **B-CAP on real code, on Colab, now**: capacity-aware retraining uses the synthetic
  training environment — code only, no producer data required — so the owner's Colab
  compute units are usable for real runs the moment the harness dry-runs pass.
- **B-BUS unchanged in principle, unblocked in practice**: our bus-derived trace is our
  own artifact; training on it uses only the producer's code.
- **Trace-replay training on the producer's traces** (the train-×-evaluate matrix)
  remains local/CSF-only until the data half is explicitly covered.

## Boundaries unchanged by this permission

The pinned external clones are still never fetched; checkpoints returning from any venue
still become evidence only through the reviewed pinned-actor extension and fresh-run
admission; every experiment still requires its own predeclaration; all label ceilings
stand.
