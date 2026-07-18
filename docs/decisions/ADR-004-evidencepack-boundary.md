# ADR-004: EvidencePack Boundary

Status: accepted

## Context

Diagnostic rules need structured inputs without reading raw files or recomputing metrics.

## Decision

EvidencePack is the only supported handoff from metrics/validation into diagnostics.

## Consequences

- Rules cite stable metric keys.
- Rule inputs are serialisable and fingerprintable.
- Future prose rendering can consume structured findings without inventing evidence.

## Alternatives Considered

- Let rules query raw records: rejected because it would blur metric and diagnostic responsibilities.
