# ADR-012: Confirmation-Gated Manifest Inference

Status: accepted

## Context

TrafficTwin v0.5 `ING-02` requires deterministic CSV mapping suggestions from headers and bounded
value patterns. A suggestion must never become analysis input without explicit confirmation or an
edit. The existing generic CSV adapter already treats `manifest.yaml` as authoritative, so the
inference workflow must remain separate from validation and canonicalisation until confirmation.

Headers can provide useful structural evidence, but numeric values do not establish physical
units. Similar two-column files can also satisfy several canonical file kinds. Presenting a score
as a probability or silently choosing a tied candidate would fabricate certainty.

## Decision

- Introduce a strict, versioned `ManifestInferenceDraft`. It is always
  `analysis_ready: false` and `confirmation_required: true`.
- Inspect at most 32 CSV files, 128 columns per file, 100 data rows per file, and 256 characters per
  sampled value. Hash complete files; sampling bounds inference work, not integrity evidence.
- Match fields using a closed, versioned catalogue with three ordered methods: exact normalised
  header, documented header alias, and a bounded distinctive value pattern.
- Restrict value-only patterns to the existing task-class (`T1`/`T2`/`T3`), decision
  (`local`/`v2i`/`v2v`), and boolean-completion vocabularies. Do not infer identifiers, timestamps,
  numeric meaning, or units from generic ranges.
- Consider a file kind eligible only when every required canonical field has one unambiguous
  source column. Equal top file-kind scores remain ambiguous and have no selected kind.
- Treat deterministic scores as evidence-ordering values, never probabilities or confidence.
- Suggest a unit only when the header has an explicit supported suffix or word, such as `ms`,
  `seconds`, `kmh`, `bytes`, or `joules`. Otherwise require the user to select the unit.
- Require an explicit confirmation command or UI acknowledgement. Allow the user to change file
  kinds, map/unmap fields, select units, or exclude a file.
- Recompute the complete source fingerprint during confirmation and reject stale drafts.
- Emit a separate checksummed `CanonicalisationManifest` only after confirmation. Applying it to a
  complete metadata template creates an ordinary `BundleManifest` with embedded confirmation
  provenance. Normal bundle validation remains the gate before analysis or import.
- Never modify source CSV files. Refuse duplicate headers, unsafe/symlinked paths, invalid CSV,
  duplicate selected source columns, unsupported mappings/units, unresolved required fields, and
  multiple files mapped to the same current manifest kind.

## Consequences

- External CSV names can be mapped without embedding source-specific assumptions in the generic
  adapter.
- Drafts are safe to inspect and export because neither metrics nor canonicalisation accepts them.
- Users must supply bundle/run/environment/provenance metadata through a complete template; the
  wizard does not invent it.
- Current bundle schema supports one file per canonical kind, so confirming two CSVs as the same
  kind is rejected.
- Header aliases and value vocabularies are versioned code and require tests/documentation when
  extended.
- Format inference remains out of scope. Declared Parquet/gzip admission is implemented separately
  by `ING-03`/ADR-013; batch and streaming remain separate `ING-04`/`ING-05` capabilities.

## Acceptance Evidence

- Synthetic fixtures for alias/value-pattern resolution and deliberate multi-kind ambiguity.
- Golden projections proving stable suggestions, fingerprints, methods, units, and ambiguity.
- Unit tests for bounded sampling, explicit confirmation, optional unmapping, stale-source
  invalidation, duplicate headers, and explicit ambiguity edits.
- Integration tests proving CLI draft/confirm/apply flows and normal bundle validation after
  confirmation.
- Streamlit service and page-render tests over the same typed library workflow.

## Alternatives Considered

- Automatically write `manifest.yaml` after inference: rejected because an inferred mapping would
  silently become analysis-capable.
- Resolve ties by filename or arbitrary candidate order: rejected because filenames are not
  semantic evidence and order would conceal ambiguity.
- Infer seconds, milliseconds, fractions, or energy units from numeric magnitude: rejected because
  plausible ranges do not prove units.
- Put heuristics inside `GenericCsvAdapter`: rejected because validation/canonicalisation must obey
  confirmed declarations rather than suggestions.
- Use probabilistic/LLM schema matching: rejected because the capability requires deterministic,
  testable suggestions and no LLM-derived scientific semantics.
