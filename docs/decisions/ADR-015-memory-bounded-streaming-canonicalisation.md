# ADR-015: Memory-Bounded Streaming Canonicalisation

Status: accepted

## Context

TrafficTwin v0.5 `ING-05` requires canonicalisation whose parser working set is bounded and whose
results do not depend on chunk boundaries. The ordinary importer deliberately retains a
10,000,000-byte decoded-table limit and materialises complete canonical tables. Merely increasing
that limit would admit larger files without making parsing memory-bounded.

Streaming must preserve the established manifest, checksum, raw fingerprint, units, source-row,
validation, evidence, and registry contracts. Some validations are global: duplicate task IDs and
task references can cross both chunk and file boundaries. A bounded implementation therefore
cannot replace exact checks with a probabilistic set or silently skip reconciliation.

## Decision

- Keep ordinary ingestion and its 10,000,000-byte table bound unchanged. Streaming is an explicit
  opt-in path through `bundle stream-validate`, `bundle stream-import`, the Bundle Import UI, or
  the Python API.
- Decode declared CSV, gzip-CSV, and flat scalar Parquet through one ordered chunk iterator. Bound
  each chunk by both row count and estimated decoded bytes; also enforce explicit per-table and
  ZIP-expanded-bundle limits. A single row larger than the chunk bound is rejected with
  `TABULAR_CHUNK_SIZE_EXCEEDED`.
- Preserve the logical source locator across chunks: the first data record is row `2` and later
  chunks continue the same sequence. Chunk boundaries do not enter canonical records, findings,
  fingerprints, or evidence decisions.
- Decode each declared table once before emission to establish readable structure, table bounds,
  and columns, then decode it again for canonical chunk emission. Chunks are delivered
  synchronously and are provisional until the final validation report permits import. Consumers
  must stage or discard provisional output if the final report rejects the bundle.
- Use a temporary SQLite reconciliation index for exact cross-chunk duplicate task and
  vehicle/RSU-reference checks. It has a small configured cache, uses disk-backed temporary state,
  preserves finding order, and is removed at the end of the operation.
- Do not retain canonical chunks in the streaming validator or streaming registry import. The
  optional `collect_bundle_streaming` helper intentionally materialises all rows for equivalence
  testing and downstream analysis when the result fits memory; it is not the bounded-output mode.
- Keep registry import metadata-only and reuse the ordinary idempotency/conflict transaction. A
  streaming import does not automatically compute or store metrics, EvidencePacks, or diagnostics.
- Continue to fingerprint the exact immutable raw files. Streaming changes the decoder strategy,
  not evidence identity.
- Mark `streaming_canonicalisation=true` only for the generic tabular capability manifest. The
  separate SUMO and read-only TOS adapters remain `false` for this capability.

## Bounds And Measurement Semantics

Defaults are 1,000 source rows and 4,000,000 estimated decoded bytes per chunk,
1,000,000,000 uncompressed bytes per table, and 2,000,000,000 expanded bytes per bundle. The
configuration model enforces nested and absolute upper bounds.

For CSV, the decoded estimate is the UTF-8 byte length of admitted header/value scalars; gzip's
table limit counts decoded text lines. For Parquet, the table limit uses uncompressed row-group
metadata and chunk estimates use Arrow record-batch bytes. These are deterministic admission and
working-set controls, not a promise about total process RSS. The validation report and a caller's
consumer may themselves grow; `tracemalloc` also excludes some native Arrow allocations.

## Consequences

- Large generic tables can be validated without materialising all canonical records in memory.
- Exact global checks remain available at the cost of temporary disk I/O and a second decode pass.
- Streaming is expected to be slower than ordinary ingestion on small inputs.
- A caller that needs full in-memory metrics can use collected mode, but loses the memory-bound
  property. A genuinely streamed metric accumulator is a separate metric-layer capability.
- Raw files must not be edited during validation. A concurrent edit between the two passes can
  invalidate provisional output and is outside the immutable-input contract.
- ZIP safety rules are unchanged; extracted temporary evidence and reconciliation state are
  cleaned after use.

## Acceptance Evidence

- Property-style tests compare ordinary and streaming canonical tables, validation reports,
  evidence availability, counts, and deterministic metrics across several chunk sizes.
- Golden tests repeat the equivalence checks for CSV, gzip-CSV, and Parquet.
- Tests cover a duplicate task ID spanning chunks, exact reference reconciliation, oversized
  rows, a table above the ordinary limit, ZIP equivalence, CLI output/import, UI services, and
  Streamlit controls.
- The generated-large-fixture benchmark records raw size, runtime, peak traced memory, canonical
  digests, validation equivalence, counts, and maximum observed chunk bounds.

## Alternatives Considered

- Raise the ordinary table limit: rejected because it still materialises the complete table.
- Keep all task and reference IDs in Python sets: rejected because global validation state would
  scale with input size in process memory.
- Use Bloom filters or sampled duplicate checks: rejected because they cannot preserve exact
  validation output.
- Emit before any full-table structural pass and call chunks final: rejected because a late decode
  failure could leave a consumer treating rejected partial evidence as accepted.
- Change raw identity to a canonical digest: rejected because encoding and compression are part of
  immutable source provenance.
