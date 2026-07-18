# ADR-003: Deterministic Metric Engine

Status: accepted

## Context

The project requires all numbers to come from deterministic code.

## Decision

Metrics are registered with stable keys and computed from canonical records only.

## Consequences

- Metric outputs are testable and reproducible.
- Missing evidence is explicit.
- UI and rules do not calculate metrics.

## Alternatives Considered

- Spreadsheet or notebook metrics: rejected for weaker reproducibility.
- LLM-assisted calculation: rejected by project constraints.
