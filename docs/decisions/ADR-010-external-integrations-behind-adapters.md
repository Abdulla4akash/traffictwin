# ADR-010: External Integrations Behind Adapters

Status: accepted

## Context

Randy/VEC and SUMO schemas, units, and execution behavior are unconfirmed.

## Decision

Keep external uncertainty behind adapter-specific modules and discovery documents. Do not add Randy-specific behavior to the generic CSV adapter.

## Consequences

- Real integration can be added without weakening existing validation/metrics/rules.
- Unsupported behavior remains unavailable in the UI.
- Phase 6B requires real artifacts before implementation.

## Alternatives Considered

- Infer schemas from design text or synthetic fixtures: rejected because it would fabricate integration evidence.
