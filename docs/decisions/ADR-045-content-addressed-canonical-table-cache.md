# ADR-045: Content-addressed Canonical-table Cache

- Status: accepted
- Date: 2026-07-21
- Capability: `OPS-02`

## Context

Ordinary generic-bundle validation reopens declared CSV, gzip-CSV, or Parquet sources, validates
their mappings and units, creates strict canonical records, performs reconciliation, and builds an
evidence/validation result on every use. This repeated work is useful for cold validation but
unnecessary when the exact raw bytes and every code/schema identity remain unchanged.

A cache is only an operational optimisation. It cannot become evidence, hide changes to a source,
weaken validation, overwrite raw files, or make a stale result look current. A path-only cache key
would be unsafe because a bundle can change in place. A raw fingerprint alone is also insufficient
because mappings and canonicalisation code can change while source bytes remain the same.

## Decision

Implement `traffictwin.ingestion.cache` and the cache-aware orchestration in
`traffictwin.ingestion.bundle` with these rules:

1. Build the content-addressed key from the exact raw bundle fingerprint, adapter identifier and
   version, validator version, complete manifest mapping/contract fingerprint, canonical Pydantic
   plus Arrow schema fingerprint, and cache-format version.
2. Reopen and fingerprint the raw directory or ZIP on every lookup. Parse the current raw manifest
   before deriving the key. A cache hit never bypasses raw identity verification.
3. Require an explicit cache root and reject it when it is the raw directory bundle or lies below
   that bundle. Cache files are derived data and never enter the raw bundle fingerprint.
4. Store all six canonical tables as typed Apache Parquet 2.6 files. Store the accepted manifest,
   seed, evidence availability, insufficient-evidence summary, and validation report separately in
   strict JSON. Do not store raw source bytes in the cache.
5. Publish a strict `entry.json` containing the complete key, exact file inventory, SHA-256 digest,
   byte size, row count, table name, and record-model identity. Verify every payload checksum,
   Parquet schema, bounded decoded size, typed record, validation summary, evidence summary, and
   canonical count before reuse.
6. Admit only ordinary accepted generic-bundle results. Rejected results, SUMO source results, TOS
   source results, and streaming summaries are not cacheable under this contract.
7. Write into a private temporary sibling directory, sync the completed files, reread and compare
   the full canonical payload, then atomically rename it to the key. Never rewrite a valid existing
   entry. If a concurrent writer wins, verify and reuse its entry and remove only the losing
   invocation's unpublished temporary directory.
8. Treat raw or manifest-mapping differences as a miss/new key. Classify an entry found under the
   expected key as stale, incompatible, corrupt, or hit. Never automatically delete or overwrite a
   stale, incompatible, corrupt, unexpected, or symlinked entry.
9. On a bad cache entry, the cache-aware library path may still perform ordinary cold validation so
   the raw evidence remains usable, but it returns the bad cache state and does not publish over it.
   The cache CLI exits non-zero unless it produces a verified `hit` or `written` state.
10. Bound one cache entry to 512,000,000 stored bytes, 1,000,000,000 decoded bytes per table,
    5,000,000 rows per table, and 50,000,000 validation-metadata bytes. These are safety limits, not
    dissertation workload claims.

The public surfaces are:

- `canonical_cache_contract()`;
- `inspect_bundle_cache(path, cache_root)` for read-only status;
- `validate_bundle_cached(path, cache_root)` for cold publication or verified warm reuse;
- `traffictwin bundle cache-contract`, `cache-status`, and `cache-validate`.

## Consequences

- The warm result is exactly the accepted cold `BundleValidationResult`, including its original
  validation timestamp, findings, evidence state, source-row provenance, and canonical order.
- Changing any raw file, even non-mapping manifest metadata, produces a different raw fingerprint
  and therefore a miss. Mapping, adapter, validator, schema, and format identities are independently
  visible in the key.
- Cache status reads and hashes the raw bundle but does not perform complete cold validation on a
  miss. A miss therefore says only that no reusable entry exists.
- Parquet reduces repeated decoding/canonical conversion work but warm reuse still incurs raw
  hashing, checksum verification, Parquet decoding, and strict Pydantic row validation.
- Content-addressed historical entries can accumulate. Retention, quota-based eviction, shared
  cache coordination, and operator backup are not part of v1.
- The cache is not a persistent canonical evidence store, registry table, cross-adapter interchange
  format, or substitute for raw evidence.

## Acceptance Evidence

Unit and CLI tests cover exact cold/warm validation and metric equivalence; raw and cache
byte-idempotency; directory and ZIP bundles; all six Parquet table schemas; raw, mapping, adapter,
validator, canonical-schema, and cache-format key changes; stale/incompatible/corrupt/symlink
rejection; no overwrite of a corrupt entry; explicit bundle/cache separation; and no partial
publication after an injected write failure.

The generated 20,000-task local implementation benchmark records cold publication, five warm hits,
exact validation-result equality, unchanged raw files, peak Python-traced memory, a changed-raw
miss, and a separate rebuilt key. It is documented in
[canonical cache benchmark](../evaluation/canonical_cache_benchmark.md).

## Rejected Alternatives

- Cache by source path or modification time: rejected because neither identifies raw content.
- Key only by raw fingerprint: rejected because adapter, validation, mapping, schema, and format
  contracts can change independently.
- Put `.cache` inside a directory bundle: rejected because it mutates the evidence inventory and
  raw fingerprint.
- Cache Python pickle objects: rejected because pickle is not a safe, portable, typed evidence
  boundary.
- Trust Parquet metadata without checksums and Pydantic validation: rejected because corrupt or
  incompatible rows could silently enter metrics.
- Automatically repair/delete a bad entry: rejected because silent destructive recovery obscures
  the operational failure and may race another process.
- Add the cache to SQLite: rejected because canonical rows are large derived tables and OPS-01's
  registry intentionally stores metadata/JSON artifacts rather than analytical rows.
- Cache streaming chunks under the same contract: rejected because streaming owns different
  bounded-memory and reconciliation semantics and needs separate acceptance evidence.
