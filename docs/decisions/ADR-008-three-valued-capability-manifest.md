# ADR-008: Three-Valued Capability Manifest

Status: accepted

## Context

Some capabilities are unsupported, while others are merely unconfirmed.

## Decision

Represent capabilities as `true`, `false`, or `unknown`.

## Consequences

- UI can disable unknown controls without mislabelling them unsupported.
- Direct launch remains `false` until evidenced.
- Randy/SUMO controls remain `unknown` until artifacts exist.

## Alternatives Considered

- Boolean-only capabilities: rejected because it collapses unknown into false.
