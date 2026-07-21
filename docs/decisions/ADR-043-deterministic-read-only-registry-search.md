# ADR-043: Deterministic Read-only Registry Search

- Status: accepted
- Date: 2026-07-21
- Capability: `REP-05`

## Context

TrafficTwin needs one local search surface covering findings, analyst annotations, report
metadata/text, runs, experiments, and evidence references. Existing UI search used independent
substring scans across a few metadata catalogues and filenames. It did not cover the REP-05
inventory, expose one ranking contract, guarantee a read-only SQLite connection, bound report
text, or apply the provenance source-path redaction policy before matching.

A mutable SQLite FTS index would add schema/migration state immediately before `OPS-01` defines
versioned migrations. External search and embeddings would weaken offline reproducibility and
could disclose research content. Ranking must not be presented as scientific importance.

## Decision

Implement an on-demand typed projection in `traffictwin.registry_search`:

1. Open an existing registry with SQLite `mode=ro`, immutable mode, and
   `PRAGMA query_only=ON`; never initialise, migrate, create sidecar state, or persist an index.
2. Project six closed categories: finding, annotation, report, run, experiment, and
   evidence-reference.
3. Reject a symlinked `workspace/reports` directory and read only sorted direct non-symlink files
   beneath it; search bounded UTF-8 text for Markdown, HTML, JSON, SVG, and LaTeX, and metadata
   only for PDF.
4. Redact absolute POSIX, Windows, home-relative, and file-URI paths before normalisation,
   matching, scoring, snippets, or result serialisation.
5. Use Unicode NFKC case-folded lexical `AND` matching and the published integer field/phrase/token
   weights. Resolve ties by score, category declaration order, normalised title, and reference.
6. Enforce query, result, candidate, report-count, report-byte, document-text, recursion, and
   snippet bounds. Refuse an excessive inventory rather than silently returning a partial index.
7. Publish category labels, counts, omissions, skipped reports, redactions, score, typed reference,
   bounded snippet, canonical JSON, and exact result fingerprint.
8. Keep the CLI and Streamlit page thin over the same library result. No UI or LLM calculates a
   match or score.

## Consequences

- An unchanged registry/workspace and request produce the same ordering and fingerprint.
- Search creates no migration burden, WAL mutation, cache, external request, or background state.
- Paths cannot influence a match after redaction and cannot appear in returned snippets.
- Every term is required, which is predictable but less recall-oriented than fuzzy/semantic
  search.
- Rebuilding the bounded projection per request is suitable for the prototype inventory but is not
  a large multi-user search architecture.
- PDF body text, raw rows, nested report directories, and external content remain unavailable.
- Scores are lexical relevance only and must never be interpreted as severity, confidence,
  causality, correctness, or importance.

## Rejected Alternatives

- SQLite FTS schema and triggers: rejected until ordered migrations and index lifecycle are
  designed under `OPS-01`.
- Web or hosted search: rejected because the guaranteed workflow is local/import-first and source
  disclosure permission is unknown.
- Embeddings or LLM query expansion: rejected because output would not be a closed deterministic
  lexical contract and could introduce unsupported terms.
- Searching raw bundle rows: rejected because REP-05 is registry/report discovery and raw inputs
  must remain protected and unchanged.
- Unbounded recursive workspace scan: rejected for path, disclosure, latency, and reproducibility
  reasons.
