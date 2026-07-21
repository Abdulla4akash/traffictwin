# ADR-042 - Deterministic One-page Executive Summary

Status: accepted and implemented
Date: 21 July 2026
Capability: `REP-04`

## Context

Supervisors need a compact view of a completed report, but a page limit creates pressure to hide
unavailable evidence, caveats, or provenance. Summarising rendered prose would also make wording a
scientific input, while an LLM could invent emphasis or interpretation. REP-04 therefore needs a
bounded renderer projection over the typed report contract established for REP-03.

## Decision

REP-04 v1.0 consumes one saved, compatible `ResearchReport` JSON payload. Supported source types
are run, diagnostics, comparison, and full. The source must pass the existing schema, report-type,
source-mode, denominator, and complete claim-reference/snapshot inventory checks. The projector
does no scientific recomputation and excludes analyst annotations.

The projection publishes exact total, available, unavailable, and per-claim-kind counts. It
selects no more than five existing claims using a closed quota policy: at most two triggered rules,
at most two available non-unchanged comparisons, at most one unavailable claim, and at most one
remaining rule, then available metrics, remaining comparisons, remaining rules, and other claims.
Earlier selections consume the shared five-slot capacity. Every tie uses the report-independent
scientific claim key. The number of claims beyond the highlight set and the complete selection
policy remain visible.

Scalar values are rendered from the typed snapshot. Mapping/list values receive a neutral
structure-count display and a link to the exact claim; long typed strings receive a neutral
follow-link display. Neither case is parsed into a new finding. Each selected claim retains status,
availability, unit, reason codes, claim ID, scientific key, and scientific-payload fingerprint.

Every projection contains three mandatory warnings: renderer-only/non-causal scope, exact source
mode, and bounded-selection disclosure. All source report warnings are appended unchanged. All
items in exact top-level `Limitations` sections are retained; absence is stated explicitly. Inputs
over 100 source warnings or 100 limitations are refused rather than shortened.

The projection contains a relative source-report link plus one relative source-claim link for each
highlight. It also retains separate complete-payload and scientific-content fingerprints.
Absolute source display paths are reduced to a basename. These are auditable local references, not
fabricated network endpoints.

JSON is the complete machine-readable projection. Markdown and self-contained print-oriented HTML
render the same fields. The invariant ReportLab A4 renderer builds all content and uses `pypdf` to
verify exactly one page. A multi-page result raises a typed layout error. The renderer never omits,
truncates, or conceals warnings or limitations to fit the page.

## Consequences

- Supervisors receive a compact deterministic index into the full report, with source mode,
  evidence gaps, caveats, and provenance visible.
- The bounded claim selection is reproducible and inspectable, but is not an importance ranking or
  recommendation.
- Scientific results remain owned by metric, diagnostic, comparison, and report builders.
- A report with excessive caveat text may produce Markdown/HTML/JSON but will fail one-page PDF
  export; that failure is safer than a misleadingly incomplete page.
- Presentation-only or incomplete legacy report payloads must be regenerated before use.
- Source annotations cannot influence selection, availability, warnings, fingerprints, or page
  content.

## Rejected Alternatives

- **LLM-generated supervisor synopsis:** could invent emphasis, values, explanations, or claims.
- **Summarise rendered section prose:** treats wording as evidence and loses typed availability.
- **Choose the five largest numeric changes:** duplicates scientific interpretation, mixes units,
  and implies desirability.
- **Show only available results:** conceals evidence gaps.
- **Drop warnings or limitations until the PDF fits:** directly violates REP-04 and can mislead.
- **Use an arbitrarily tiny font:** preserves bytes but defeats legibility and supervisor use.
- **Allow a second caveat page while calling the result one-page:** makes the page guarantee false.
- **Link to an assumed hosted provenance service:** invents deployment and routing capabilities.

## Acceptance Evidence

- Unit tests cover the contract, capabilities, deterministic quota selection, exact availability
  reconciliation, warning/limitation retention, escaping, relative links, path redaction,
  deterministic fingerprinting, incomplete inventory, single-page A4 output, and overflow refusal.
- Golden coverage fixes the complete baseline projection.
- CLI integration covers contract inspection plus JSON, Markdown, HTML, and one-page PDF output.
- UI service and Streamlit AppTest coverage exercise the source control and complete download set.
- The final PDF is rendered through Poppler and visually inspected for legibility, clipping,
  overlap, headers, footers, and page count.
- Generated Pydantic schemas, CLI help, the machine-readable contract, capability manifests,
  architecture, traceability, assumptions, open decisions, and usage documentation expose the same
  boundary.
