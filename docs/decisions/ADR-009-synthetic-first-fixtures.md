# ADR-009: Synthetic-First Fixtures

Status: accepted

## Context

No real Randy/VEC or SUMO artifacts are present, but the vertical slice needs testable data.

## Decision

Use small, labelled synthetic fixtures for golden tests, integration tests, UI demo, and diagnostic fault injection.

## Consequences

- The pipeline is demonstrable without external services.
- Expected outputs are hand-auditable.
- Synthetic results cannot be reported as real experimental findings.

## Alternatives Considered

- Block all implementation until real data arrives: rejected because the import-first contract can be built independently.
