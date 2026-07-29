# Producer Data-Use and Publication Permission — Recorded Provenance (29 July 2026)

**Status: relayed by the owner as having been given in writing. Supersedes the scope limits in
[the 28 July code-use record](randy_code_permission_20260728.md), which remains in place as the
earlier state and must not be deleted — several frozen predeclarations link to it by path.**

## What changed

On 29 July 2026 the owner stated that the producer (Randy Putra) has granted permission
covering **code, data, and publication** — i.e. all three items the 28 July record listed as
open asks are now covered — and that this was given **in writing** (email or message).

The three previously-excluded items, now covered:

1. **Data blobs** — traces, occupancy arrays, instrumented arrays, checkpoints-as-data — may
   leave the local machine for CSF and for owner-managed third-party cloud compute.
2. **Publication of data-derived aggregates** — metric tables, paired differences, **the
   capacity-study numbers** — in the dissertation and other public output.
3. Republication or rehosting of producer repository content, to the extent the written
   statement covers it.

## Provenance, stated honestly

**The written artifact is not in this repository and this agent has not seen it.** What is
recorded here is the owner's relay that a written permission exists, which is one step stronger
than the 28 July verbal relay but is still second-hand at the point of recording.

**Open action, and it is small:** paste the message text — or a quoted excerpt with its date and
channel — into this document. That converts it from a relayed claim into citable evidence. It is
worth doing **before the dissertation cites any producer-derived number**, because the
dissertation's provenance chain is exactly the sort of thing an examiner may probe, and "the
owner said there was an email" is weaker than the email.

Until that happens, this record is `owner_approved_candidate` provenance like every other
approval in this project: relayed delegation, **never an owner-typed signature** and never a
producer signature.

## What this unblocks

- **The dissertation may publish the capacity-study numbers**, with citation. This is the
  consequential change — the confirmed −8,310.9 ms result, the ceiling law, and every figure in
  the experiments register were previously outside the recorded permission for public output.
  This gates the write-up, not the compute, which is why it matters more than the Colab question
  that surfaced it.
- **Trace-replay work may run on CSF and on third-party cloud compute.** The train-×-evaluate
  matrix is no longer local-only.

## What this does *not* change

- **Budget.** Permission removes a boundary, not a cost. The remaining local campaign queue is
  ~26 GPU-hours ≈ **460 compute units against a ~196.6 balance**, so Colab is still not a viable
  home for it. The campaigns stay local, where they are running free and have proven more
  reliable than Colab over the last twelve hours.
- **The admission boundary.** GPU-track and third-party-venue outputs remain non-admitted
  diagnostics; checkpoints returning from any venue become evidence only through the reviewed
  pinned-actor extension and fresh-run admission. That is this project's internal rule and is
  unaffected by the producer's permission.
- **Label ceilings.** `owner_approved_candidate` stands. This permission concerns intellectual
  property and data use; it says nothing about scientific validation, and it is not supervisor
  approval.
- **Citation obligations**, which now bind *more* output, not less. Every published artifact
  citing producer-derived numbers carries the repositories
  (`gitlab.cs.man.ac.uk/e62992rp/{vec_env,tos-data}`), the pinned commits and engine version
  (`v2_post_nrsus_fix`), and the producer's Year-1 report where its findings are discussed.
- **Pinned clones are still never fetched**, and every experiment still requires its own
  predeclaration.
