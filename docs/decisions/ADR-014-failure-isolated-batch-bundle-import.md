# ADR-014: Failure-Isolated Batch Bundle Import

Status: accepted

## Context

TrafficTwin v0.5 `ING-04` requires one explicit path/glob request to validate or import multiple
run bundles. The ordinary single-bundle validator and registry operation already define accepted,
rejected, idempotent, and identifier-conflict behavior. Batch orchestration must preserve those
semantics, raw identity, and immutable inputs. It must also prevent one malformed or conflicting
candidate from corrupting, relabelling, or rolling back valid neighbours.

Unbounded filesystem discovery would be unsafe and non-reproducible. A single all-or-nothing
transaction would also contradict the required failure isolation: a late conflict could erase
earlier valid imports even though those bundle transactions were independently sound.

## Decision

- Accept only caller-supplied literal paths and glob patterns. Do not scan for bundles beyond those
  references. The CLI requires shell globs to be quoted so TrafficTwin, rather than the shell,
  performs expansion.
- Expand `~`, support recursive glob syntax, resolve paths, deduplicate overlaps, retain every
  originating reference in `matched_by`, and process unique candidates in lexicographic resolved-
  path order.
- Limit a request to 64 input references and 256 unique candidates. Reject an over-limit request
  before validating or mutating any candidate.
- Treat an unmatched glob as a batch input issue while continuing with matched neighbours. Treat a
  missing literal as an individual candidate so normal bundle validation records its rejection.
- Validate each candidate exactly once in a batch operation. Batch import passes that validated
  artifact to the unchanged registry registration semantics.
- Use one ordinary registry transaction per accepted candidate. Invalid candidates never reach the
  registry; conflicts and registry failures are captured as that candidate's outcome, and later
  candidates continue.
- Preserve exact single-import idempotency and conflict rules. Reimporting an identical bundle is
  idempotent; reusing a bundle or run identifier with changed raw identity remains a conflict.
- Publish a typed versioned summary containing input issues, consolidated counts, and ordered
  per-bundle outcomes. Text and JSON include consolidated issues; CSV is a per-bundle table.
- Return a non-zero CLI exit status for `partial` or `failed`, even when some candidates imported.
  Automation must inspect the summary rather than interpret exit `1` as “nothing happened.”
- Keep metric, EvidencePack, and diagnostic generation out of the batch registry operation. Those
  existing deterministic workflows remain explicit downstream actions.

## Consequences

- A rejected or conflicting candidate cannot undo or alter a successfully imported neighbour.
- A batch is deliberately not one atomic unit. The summary is the audit artifact that explains
  which independent operations committed.
- Repeating a mixed batch can move prior successful entries to `idempotent` while the same invalid
  or conflicting entries remain visibly unsuccessful.
- Deterministic ordering and deduplication make summaries reproducible for an unchanged filesystem
  and input set.
- JSON summaries include resolved local paths and may expose workstation directory names. Review or
  redact them before public release.
- Broad globs can match ordinary files as candidates; users should scope patterns to bundle
  directories or ZIP archives.

## Acceptance Evidence

- Unit tests cover sorting, overlap deduplication, unmatched globs, missing literals, preflight
  limits, mixed accepted/rejected input, repeated idempotent import, conflict isolation, and CSV.
- CLI tests cover partial JSON, isolated import, idempotent reruns, CSV export, and unsupported
  formats. UI-service tests cover the same shared orchestration path.
- A golden test fixes the consolidated/per-bundle projection for a mixed validation request.
- The local fixture benchmark publishes source size, runtime, peak traced memory, and exact
  equivalence with sequential calls to `validate_bundle`.

## Alternatives Considered

- Make the whole batch atomic: rejected because it couples independent evidence and violates the
  requirement that one failure not affect valid neighbours.
- Continue after an input/candidate limit is exceeded: rejected because partial resolution would
  make filesystem traversal order affect which bundles run.
- Infer bundle roots by scanning a directory tree: rejected because the feature requires an
  explicit path set and silent discovery weakens reproducibility.
- Reimplement registry conflict logic in the batch layer: rejected because it risks divergent
  idempotency and relabelling behavior.
