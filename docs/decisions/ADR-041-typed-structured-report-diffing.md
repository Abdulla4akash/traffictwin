# ADR-041 — Typed Structured Report Diffing

Status: accepted and implemented
Date: 21 July 2026
Capability: `REP-03`

## Context

TrafficTwin reports contain computed metric, diagnostic-rule, and comparison claims, but their
section bodies are presentation strings. Comparing Markdown, HTML, PDF, titles, timestamps, or
analyst commentary would mix rendering changes with scientific changes and could make a wording
edit look like new evidence. REP-03 therefore needs a renderer-independent comparison boundary
that preserves unavailable states and can refuse incompatible payloads.

## Decision

REP-03 version 1.0 adds a bounded `ReportClaimSnapshot` beside every typed
`ReportClaimReference`. A snapshot contains the report-independent claim key, availability,
machine status, exact typed value, unit, stable reason codes, and a closed artifact-specific
detail payload. Metric snapshots retain implementation version, scope, and dimensions. Rule
snapshots retain rule version, categorical status/confidence, evidence keys, typed observed
values, missing-evidence keys, and scalar metadata; they exclude hypotheses, recommendation text,
and finding prose. Comparison snapshots retain existing baseline, variation, delta, direction,
status, unit, and reason codes. The report builder projects these values from already-computed
artifacts and performs no new scientific calculation.

Two reports are compatible only when their payload schema, report type, source mode, claim
denominator definition, supported type, and claim-reference/snapshot inventory agree. An
incompatible pair returns a typed `unavailable` result with stable reason codes; it is not coerced
into a textual diff. Supported v1.0 report types are run, diagnostics, comparison, and full.

Compatible reports are compared by section title and report-independent claim key. Claim payloads
are canonical JSON and recursively compared at JSON Pointer paths. Claims and sections use one
closed classification: `unchanged`, `added`, `removed`, `changed`, or `unavailable`. A matched
claim is unavailable if either side lacks eligible evidence. A matched section with no typed
claims is unavailable with `NO_TYPED_CLAIMS`; its body is never compared. Added and removed
section titles are structural changes. A matched section is changed only by added, removed, or
changed typed claims.

Scientific report fingerprints include schema, report type, source mode, denominator, ordered
section titles, claim keys, and typed snapshots. They exclude report ID, title, generation time,
source display reference, warnings, section bodies, claim labels, exclusions, annotation targets,
and analyst annotations. The complete diff has its own deterministic fingerprint.

Inputs are capped at 2,000,000 bytes, 100 sections, 500 claims, 2,000 field changes, ten nested
JSON levels, and finite JSON values. Duplicate section titles, claim IDs, or scientific claim keys
are rejected. JSON is the complete machine-readable export; Markdown is a visibly non-causal
presentation and marks any shortened display value as truncated.

The CLI can save a structured report with a `.json` output suffix, inspect the diff contract, and
compare two saved payloads to JSON or Markdown. The Reports page uses the same service and offers
downloadable JSON/Markdown results. Neither surface contains comparison logic.

## Consequences

- A wording, layout, timestamp, annotation, or reproduction-command change cannot become a
  scientific report difference.
- Metric, rule, and comparison changes remain exact, typed, availability-aware, and traceable to
  their existing claim identities.
- Narrative-only sections are visible as unavailable for scientific diffing rather than silently
  ignored or text-compared.
- Reports generated before typed claim snapshots cannot be scientifically diffed until
  regenerated; the result is explicitly unavailable.
- Report diffs describe evidence changes and do not establish desirability, significance,
  attribution, or causality.
- The additive report schema preserves existing Markdown, HTML, PDF, and LaTeX rendering.

## Rejected Alternatives

- **Diff rendered Markdown/HTML/PDF:** confuses formatting and prose with evidence and is not
  stable across renderers.
- **Parse values back out of section strings:** duplicates formatting rules, loses types and
  unavailable semantics, and is brittle.
- **Compare claim IDs directly:** IDs are report-scoped and can change when a report is rebased;
  v1.0 uses kind plus artifact key.
- **Treat every section-body change as scientific:** headings, caveats, commands, and narrative are
  intentionally outside the scientific claim denominator.
- **Flatten unavailable to `null` or zero:** hides why a comparison cannot be made.
- **Use an LLM to summarise or classify changes:** REP-03 classifications and paths are
  deterministic code outputs only.
- **Calculate new metric deltas in the report layer:** scientific calculations remain in their
  original typed metric/comparison/statistical services.

## Acceptance Evidence

- Unit tests cover the contract, capabilities, complete builder snapshots, prose/annotation/time
  exclusion, real typed metric changes, all five classifications, incompatible source/type
  handling, parser bounds, and duplicate rejection.
- Golden coverage pins exact section, claim, JSON Pointer, fingerprint, unavailable, exclusion,
  and warning output.
- CLI integration covers structured report JSON generation, contract inspection, JSON/Markdown
  diff export, and typed incompatible output.
- UI service and Streamlit AppTest coverage exercise saved-payload comparison and editable Reports
  controls.
- Generated Pydantic schemas, CLI help, machine-readable contract, capability manifests, usage
  documentation, architecture, traceability, assumptions, open decisions, and implementation
  status expose the same boundary.
