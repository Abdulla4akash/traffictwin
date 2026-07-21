# ADR-013: Declared Tabular Formats and Raw Identity

Status: accepted

## Context

TrafficTwin v0.5 `ING-03` requires Parquet and gzip-compressed CSV inputs to pass through the same
manifest, validation, fingerprint, unit, canonicalisation, metric, and provenance contracts as
plain CSV. Raw inputs must remain immutable, and compression must not silently introduce a second
or incompatible bundle-identity rule.

File suffixes do not establish encoding reliably. Parquet can also contain nested, temporal, or
binary values that do not fit the existing scalar canonical mapping. Compressed inputs need a
decoded-size boundary so a small raw file cannot expand without limit.

## Decision

- Every `FileDeclaration` has an explicit `format`: `csv` (the backward-compatible default) or
  `parquet`.
- CSV may additionally declare `compression: gzip`. Outer compression is rejected for Parquet;
  normal Parquet column-chunk compression remains part of the Parquet file itself.
- Do not infer format or compression from a filename. The manifest is authoritative, and a
  declaration that does not match the bytes is rejected during decoding.
- Admit only flat Parquet scalar columns whose values are string, boolean, integer,
  floating-point, decimal, or null. Reject nested, binary, date/time, and other unresolved types
  with a stable code instead of inventing conversion semantics.
- Convert admitted physical values to the same scalar-text boundary used by the generic adapter,
  then apply the existing required-column, column-map, unit, semantic, canonical-record, and
  reconciliation logic unchanged.
- Reject duplicate columns in all supported tabular encodings.
- Cap one decoded generic table at 10,000,000 bytes. For gzip this is counted while decompressing;
  for Parquet both metadata and the decoded Arrow table are checked. The later implemented
  `ING-05`/ADR-015 opt-in path handles larger memory-bounded ingestion without changing this
  ordinary limit.
- Keep `source_row` as the logical tabular record locator: one-based data-record ordinal plus the
  historical header offset, so the first data record is `2` in CSV, gzip-CSV, and Parquet. This
  preserves equivalent row lineage across representations without claiming a physical Parquet
  line number.
- Preserve and checksum the original file bytes. The existing bundle fingerprint remains an exact
  hash over relative paths and raw-file hashes. Therefore recompression or conversion changes the
  bundle fingerprint and registry identity even when canonical evidence is equivalent. No second
  “logical bundle ID” is introduced. Golden equivalence tests compare canonical records and
  deterministic metrics instead.
- Keep the `ING-02` inference wizard scoped to plain CSV. A confirmation created from that wizard
  cannot be relabelled as compressed or Parquet evidence.

## Consequences

- A bundle may mix plain CSV, gzip-CSV, and Parquet declarations while using one generic adapter.
- Existing manifests remain valid because omitted `format` means plain CSV and omitted
  `compression` means no outer compression.
- Raw evidence provenance stays exact and audit-friendly; semantically equivalent encodings are
  deliberately not idempotent imports of one another.
- Canonical records, metric values, CLI validation, Streamlit analysis, and row previews reconcile
  across representations, while their `source_file` and raw fingerprints correctly differ.
- Users must flatten or explicitly convert unsupported Parquet types outside TrafficTwin and
  document that preprocessing as source provenance.

## Acceptance Evidence

- Golden tests convert every declared baseline table to deterministic gzip-CSV and Parquet,
  compare canonical semantic projections and the complete metric projection with CSV, and verify
  row-level provenance previews.
- Unit tests cover legacy defaults, declared-format validation, malformed gzip, nested Parquet,
  duplicate columns, checksum mismatch, evidence invalidation, and the decoded-size limit.
- CLI and UI-service tests validate and analyse both representations through existing entry points.
- Generated Pydantic and validation-code references expose the new manifest fields and stable
  failure codes.

## Alternatives Considered

- Detect encoding from suffix or magic bytes: rejected because silent detection weakens the
  manifest contract and makes mismatches harder to audit.
- Treat equivalent decoded content as the same bundle fingerprint: rejected because it would hide
  changes to the immutable raw evidence and complicate registry conflict/idempotency semantics.
- Use pandas as the ingestion boundary: rejected because the adapter needs a smaller explicit type
  admission contract; PyArrow reads Parquet directly and deterministically.
- Admit nested or timestamp Parquet columns automatically: rejected because the current canonical
  fields require explicit numeric units and flat scalar mappings.
