# ADR-040 — Append-Only Analyst Annotations

Status: accepted and implemented
Date: 21 July 2026
Capability: `REP-02`

## Context

Researchers need to record interpretation, review decisions, caveats, and follow-up work beside
TrafficTwin artifacts. That commentary must remain attributable and ordered without being confused
with deterministic metrics, rules, statistics, provenance, or findings. Editing an earlier note or
embedding it inside a computed payload would weaken the audit trail and could change what a report
appears to claim.

## Decision

REP-02 version 1.0 stores analyst annotations as a separate append-only SQLite stream. An
`AnalystArtifactReference` selects one closed target kind, a path-free artifact identifier, and an
optional exact SHA-256 artifact fingerprint. Registry-resident experiment, run, bundle-import,
metric-collection, EvidencePack, experiment-EvidencePack, and protocol targets must exist before an
annotation can be appended. Diagnostic, comparison, statistical-study, and research-report targets
are explicit detached typed references because those generated artifacts are not all registry
rows; such a reference does not itself prove that the artifact is stored.

Each `AnalystAnnotation` contains the author label, exact note, human decision label, UTC creation
timestamp, typed target, and SQLite-assigned monotonic sequence. Its identifier binds the exact
content and timestamp. Notes are bounded to 4,000 characters, authors to 120 characters, target
identifiers to 256 path-free characters, pages to 500 records, and report attachment to 500 unique
records. Reads are ascending and expose `after_sequence`, `limit`, and `has_more`.

The public registry API exposes append and read operations only. SQLite `BEFORE UPDATE` and
`BEFORE DELETE` triggers abort direct mutation attempts. Existing registry tables are unchanged;
initialisation adds the annotation table, index, and guards without rewriting old rows.

`ResearchReport.annotation_targets` declares which references a report may display. Matching
unbound annotations and exact-fingerprint annotations are loaded in sequence order. If the complete
matching history exceeds the report bound, rendering refuses instead of silently omitting entries.
Attached annotations live in `analyst_annotations`, not `sections` or `claim_references`.
Markdown, HTML, and PDF render a dedicated **Analyst Annotations — Non-computed** area with an
explicit evidence-separation warning. Analyst text is escaped for the output surface.

## Consequences

- Earlier annotations cannot be corrected in place; a later entry records any correction or
  superseding decision while preserving history.
- Annotation IDs and history fingerprints detect content/order drift but are not scientific
  evidence fingerprints.
- Reports can carry review context without changing computed sections, claim counts, provenance,
  or diagnostic confidence.
- Optional target fingerprints can bind commentary to one artifact version; unbound commentary
  intentionally applies to that typed identity across versions.
- Generated-artifact references remain useful without pretending that every export is registered.
- The registry is not an identity or access-management system; author labels are declared text,
  not authenticated signatures.

## Rejected Alternatives

- **Store notes inside metrics, EvidencePacks, or DiagnosticReports:** would rewrite computed
  evidence and change scientific identities.
- **Allow edit/delete with only an audit log:** creates two histories and makes the displayed note
  mutable; v1.0 uses correction-by-append instead.
- **Accept arbitrary target strings or file paths:** loses type safety and risks local-path leakage.
- **Require every exported report to have a registry row:** would fabricate persistence that the
  current report architecture does not provide.
- **Include annotations in provenance-completeness claim counts:** analyst commentary is not a
  computed result claim.
- **Use an LLM to classify or summarise notes:** REP-02 stores and renders exact authored content
  only.
- **Silently truncate report history:** conceals potentially important review context.

## Acceptance Evidence

- Unit tests cover contract identity, validation, stored/detached targets, exact/unbound matching,
  pagination, ordering, history fingerprints, content identity, and unrelated-target rejection.
- Raw SQLite update/delete tests prove the database guards abort mutation.
- Rendering tests prove computed sections and claim references remain unchanged and verify escaped,
  visibly separate Markdown, standalone HTML, and parseable deterministic PDF output.
- CLI integration covers contract, append, list, missing-target refusal, and annotated report
  generation.
- UI service and Streamlit AppTest coverage exercise append, history, report inclusion, and all
  editable Reports-page controls.
- A golden history pins ordered IDs, labels, timestamps, targets, and exact note content.
- Generated schemas, CLI help, machine-readable contract, capability manifest, usage guide,
  architecture, and implementation records expose the same boundary.
