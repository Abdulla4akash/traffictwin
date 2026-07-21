# ADR-005: Deterministic Diagnostics Before LLM Rendering

Status: accepted

## Context

The design allows optional prose rendering later but forbids LLM-calculated metrics or invented findings.

## Decision

Diagnostic hypotheses R0-R5 are deterministic rules over EvidencePacks. No LLM dependency is included.

## Consequences

- Rule outputs are testable.
- Confidence is categorical, not probabilistic.
- Recommendations remain conditional.

## Alternatives Considered

- Prompt an LLM with CSV/metrics: rejected because it could invent unsupported conclusions.
