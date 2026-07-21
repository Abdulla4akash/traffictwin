# ADR-035 — Explicit Report-Claim Provenance Completeness

Status: accepted and implemented
Date: 20 July 2026
Capability: `PRO-03`

## Context

TrafficTwin can trace metrics and rules, export complete accepted-canonical-row eligibility
ledgers, explain compatible baseline/variation differences, and project bounded provenance graphs.
Those facilities answer questions about a selected artifact, but they do not state how much of a
whole report is traceable to source rows. A completeness percentage calculated from whatever
claims happen to have traces would be misleading: absent or unavailable claims could disappear
from its denominator and make a sparse report look complete.

Rendered prose is not a safe source for the denominator. Headings, warnings, reproduction
commands, and computed results can share the same text format, and wording changes must not alter
scientific classification. Source-row depth also cannot be inferred from one sampled trace node;
the metric ledger must prove that every accepted canonical candidate has a source locator.

## Decision

TrafficTwin adds a versioned typed claim inventory to every supported report template and a
separate `ProvenanceCompletenessReport` schema version 1.0. The inventory is created from the same
metric collection, diagnostic report, and comparison report used by rendering. No prose is parsed.

The supported templates are `run`, `diagnostics`, `comparison`, and `full`. The denominator is
every explicit `ReportClaimReference` for a metric result, diagnostic rule result, or metric
comparison in the selected template. A referenced unavailable result remains in the denominator.
Full reports rebase embedded run and optional comparison references onto one unique report-local
claim-ID sequence.

Named exclusions are published with the score:

- presentation and narrative;
- identity and reproduction metadata;
- validation and evidence-inventory metadata; and
- comparison context for comparison/full reports.

These categories remain visible in the report but are not computed scientific result claims in
the version 1.0 method.

Each denominator claim receives exactly one classification:

- `source_row_complete`: the result is available, its complete accepted-canonical-row ledger is
  non-empty and reconciles, and every candidate has a bundle-relative source file and positive
  logical row. A rule additionally requires every cited metric dependency to satisfy this class,
  a source-row-reachable trace, and no missing-evidence reasons. A comparison requires complete,
  non-empty ledgers on both sides under the existing PRO-01 compatibility decision.
- `aggregate_only`: a typed result exists but complete source-row admission is not established.
  Examples include partial metrics, empty candidate populations, incomplete ledgers, or usable
  rule results that retain missing evidence.
- `unavailable`: the metric/comparison is unavailable or invalid, or the rule is invalid or
  reports insufficient evidence.

Trace depth is separately published as the deepest available node type reachable by following
directed edges outward from the claim root: `source_row`, `source_file`, `canonical_record`,
`canonical_table`, `aggregate`, then `unavailable`. Reaching one source-row node establishes depth
only; it does not replace complete-ledger reconciliation.

The score is:

`source_row_complete_count / denominator_count`

Claims have equal weight. `aggregate_only` and `unavailable` contribute zero, with no partial
credit. The artifact also publishes an `aggregate_or_better_fraction` for transparency. If the
denominator is empty, the score and aggregate fraction are null and status is `no_claims`; an
empty report is never reported as 100% complete.

Artifact and per-claim fingerprints exclude generation timestamps while retaining claim identity,
status, lineage evidence, accepted-row ledger, dependencies, reasons, source fingerprint, and
classification. JSON and CSV export the complete denominator. The Streamlit tables delegate to
the same query service and perform no scoring.

`source_row_complete` means complete for accepted canonical candidates. Raw input rows rejected
before canonicalisation remain validation evidence and do not silently become accepted metric
candidates. Therefore the score measures a precise lineage property, not raw-ingestion yield,
truth, causal validity, scientific importance, report quality, or external validity.

The generic/import-first report pipeline advertises the capability as true. Current SUMO and TOS
source contracts advertise false because neither exposes the exact supported typed report-claim
inventory through this query. External/custom reports default to an unsupported `external` type.

## Consequences

- A low or zero score cannot be improved by dropping unavailable typed results from the selected
  report template.
- The denominator and exclusions can be reviewed independently of the numeric score.
- Report rendering and completeness classification use one shared claim-key catalogue, preventing
  UI/prose drift from changing the inventory.
- A graph may reach a source row while its claim remains aggregate-only; sampled depth and complete
  population coverage are intentionally distinct.
- Adding a computed result to a supported report requires adding its typed claim reference and may
  lower the score until its lineage contract is complete.
- Equal weighting makes the calculation reproducible but does not claim that every result has the
  same scientific importance.

## Rejected Alternatives

- **Count only available claims:** this conceals missing evidence and inflates the result.
- **Parse rendered Markdown/HTML/PDF:** wording and formatting are not typed scientific contracts.
- **Use all trace nodes as the denominator:** nodes represent derivation structure, not report
  claims, and complex claims would receive more weight.
- **Treat one sampled source row as complete:** a sample proves depth, not population coverage.
- **Award partial numeric credit to aggregate-only claims:** the fraction would require an
  arbitrary weighting policy and weaken the simple numerator.
- **Treat an empty denominator as 100%:** no claim has been demonstrated complete.
- **Include validation metadata as result claims:** validation is audited separately and would mix
  pipeline health with scientific result lineage.
- **Let the UI inspect prose and calculate the score:** this would duplicate and weaken the tested
  deterministic service.

## Acceptance Evidence

- Unit tests pin run, partial, comparison, and full-report denominators and exact class counts.
- Tests prove unavailable claims stay in the denominator, partial evidence lowers the score, rule
  dependencies remain strict, and an empty denominator yields null rather than 100%.
- Timestamp-independence tests pin report and claim fingerprints.
- The baseline golden projection pins all 33 claim classifications, statuses, depths, and row
  counts.
- CLI tests cover the method contract, JSON, CSV, text, comparison, and invalid report types.
- UI service and Streamlit AppTest coverage prove both report and comparison views use typed core
  artifacts and expose complete JSON/CSV downloads.
- Synthetic demo initialization writes run and comparison completeness artifacts.
- Generated schemas, CLI help, method contract, capability manifests, architecture, usage,
  security, reproducibility, limitations, status, and traceability documentation are reconciled.
