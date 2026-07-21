# ADR-050: Isolated Allowlisted VEC Evaluator Runner

- Status: accepted
- Date: 2026-07-21
- Capability: `VEC-07` design boundary

## Context

VEC-01 identifies a candidate evaluator, actors, dictionary command, and output writers, but the
audited evaluator contains a fixed external import path and depends on JAX, SUMO, a compatible
actor, and an admitted trace. Possessing those files is not evidence that TrafficTwin can safely or
reproducibly execute them.

## Decision

1. VEC-07 accepts only a strict typed request. It never accepts a shell string, arbitrary script,
   unrecognised flag, environment override, or user-selected Python module.
2. Read-only preflight verifies the audited source commit/blobs, clean worktree, VEC-02 contract,
   VEC-06 receipt/trace identity, actor identity and architecture, dependency versions, output
   bounds, and destination safety before creating an execution workspace.
3. The runner stages exact Git blobs and approved immutable inputs in a private workspace. It
   controls the working directory, Python import path, environment, and allowlisted argv without
   editing either external repository.
4. Outputs are written only beneath a new destination. Partial results remain in private staging
   and are never promoted after crash, non-zero exit, timeout, cancellation, validation failure,
   or source/input drift.
5. Capture bounded path-redacted stdout/stderr, exit status, timeout/cancellation state, dependency
   evidence, exact input/source/output hashes, and the constructed redacted argv in a typed receipt.
6. Re-hash source and all approved inputs after execution. Any mutation rejects publication.
7. VEC-07 proves safe local execution only. VEC-08 separately validates output reconciliation and
   numerical reproduction; direct-launch capability remains false until both gates pass.
8. No network operation, package installation, Git mutation, scheduler submission, actor training,
   or persistent queue is part of the runner.

## Consequences

- The hard-coded source import path must be neutralised by controlled import resolution, not by
  editing the audited evaluator.
- Cancellation and timeout are first-class terminal receipts, not silent partial success.
- A valid VEC-06 trace is necessary but insufficient; actor and environment compatibility must also
  pass.
- CLI/UI wiring belongs to VEC-10 and remains thin over the tested library.

## Acceptance Evidence

The implemented `integration.vec_runner` boundary now satisfies this safety design. Its focused
tests cover successful local end-to-end execution, failure, timeout, cancellation, unsafe paths,
dirty source, incompatible actor/input evidence, malformed output, and source/input non-mutation.
The real two-step CPU acceptance run uses the exact audited evaluator, environment, actor, and
trace. This ADR accepts VEC-07 only. VEC-08 has since passed its separate pinned full-case
reproduction gate; product direct launch remains blocked on VEC-10.

## Rejected Alternatives

- Execute Randy's dictionary command as a shell string: rejected because it is not a typed or
  portable trust boundary.
- Patch the external clone in place: rejected because source immutability is required evidence.
- Publish partial outputs for inspection: rejected because downstream consumers could mistake them
  for completed evidence.
- Enable direct launch after preflight alone: rejected because VEC-07 requires a successful run and
  VEC-08 requires output reproduction evidence.
