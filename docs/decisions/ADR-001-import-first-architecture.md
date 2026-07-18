# ADR-001: Import-First Architecture

Status: accepted

## Context

The design requires TrafficTwin to work even when direct Randy/VEC or SUMO execution is unavailable. Phase 6A found no execution contract.

## Decision

Completed run bundles are the guaranteed workflow. Direct launch is optional and adapter-gated.

## Consequences

- The system can be demonstrated with synthetic and imported bundles.
- External execution claims are not fabricated.
- Future launchers must produce or locate standard run bundles.

## Alternatives Considered

- Launch-first: rejected because no safe external command exists.
- Notebook-only workflow: rejected for reproducibility and hidden state.
