# ADR-039 — Deterministic LaTeX And Static Figure Exports

Status: accepted and implemented
Date: 21 July 2026
Capability: `REP-01`

## Context

TrafficTwin needs dissertation-ready tables and static figures without creating a second metric,
statistical, or diagnostic implementation. Research outputs must preserve unavailable and
synthetic states, compile in a minimal LaTeX document, avoid leaking local paths, and be exactly
reproducible from the same computed artifact.

## Decision

REP-01 version 1.0 is a renderer-only layer over four typed artifacts: `MetricCollection`,
`ComparisonReport`, STA-01 `StatisticalStudy`, and `DiagnosticReport`. Each artifact has one
projector into a bounded `ResearchExportProjection`. No projector computes a new scientific
measure, test, confidence, finding, or recommendation.

One projection drives an escaped LaTeX2e table fragment and an optional SVG or PDF figure. Its
canonical SHA-256 fingerprint is embedded in both renderings. Metric, comparison, and statistical
figures show already-present finite values on a signed linear scale whose direction does not imply
favourability. Diagnostic figures retain categorical rule status and never convert confidence to
probability.

Table fragments use only `table`, `tabular`, `hline`, and standard LaTeX2e text commands. SVG is
self-contained and script-free. PDF uses fixed ReportLab geometry and invariant metadata. The
contract admits at most 200 rows, 8 columns, 160 characters per cell, and 64 figure entries;
truncation is visible in projection warnings.

All LaTeX-special text is escaped. Absolute POSIX and Windows paths are rendered as basename-only
local-path markers; normal URLs are preserved. The stable evidence-pack ID identifies diagnostic
exports so a different evaluation clock cannot alter the same evidence projection. Every output
states synthetic, imported/non-synthetic, or unresolved source mode.

Publication uses exact `.tex` and optional `.svg`/`.pdf` paths, sibling staging files, atomic
per-file replacement, explicit overwrite, unique targets, and symbolic-link refusal. Receipts
contain the shared projection fingerprint, filenames, formats, byte sizes, and SHA-256 checksums,
not absolute paths.

## Consequences

- Tables and figures cannot disagree about the projected typed evidence without changing their
  shared fingerprint.
- The reporting layer remains thin and testable; scientific calculation stays in existing metric,
  comparison, study, and rule code.
- Synthetic, unavailable, insufficient, and warning states remain visible.
- Outputs can be regenerated exactly and checked with independent hashes.
- Researchers retain control of dissertation document class and final layout.
- Compact figures are descriptive summaries and cannot establish desirability, significance,
  probability, or causality.

## Rejected Alternatives

- **Recompute values in a plotting or LaTeX layer:** creates conflicting scientific logic.
- **Ask an LLM to compose tables or charts:** cannot guarantee exact values, bounds, or
  reproducibility.
- **Export rendered prose as the data source:** loses typed availability, unit, and rule status.
- **Treat rule confidence as a numeric probability:** no such calibration exists.
- **Use hidden package-heavy LaTeX templates:** makes minimal compilation and integration harder.
- **Embed browser chart screenshots:** layout and metadata are not stable evidence artifacts.
- **Include absolute source/output paths:** leaks local environment details and breaks portable
  builds.
- **Silently truncate:** conceals omitted evidence.

## Acceptance Evidence

- Unit tests cover all four typed projectors, bounds, mixed-mode refusal, escaping, URL handling,
  local-path redaction, stable diagnostic identity, deterministic SVG/PDF, checksums, overwrite,
  suffixes, and symbolic-link refusal.
- Golden tests pin an exact LaTeX fragment and exact self-contained SVG.
- A real Tectonic test compiles a special-character fragment inside a minimal document.
- CLI integration covers every artifact family, SVG/PDF outputs, saved statistical studies,
  overwrite refusal, and suffix validation.
- UI service and Streamlit AppTest coverage exercise editable Reports-page controls and generation.
- Generated Pydantic schemas, CLI help, the machine-readable contract, usage documentation, design
  records, and project status expose the same closed boundary.
