# ADR-002: Canonical Internal Data Model

Status: accepted

## Context

Randy/VEC, SUMO, and generic CSV sources may use different schemas and units.

## Decision

Map source artifacts into canonical in-memory records before metrics run.

## Consequences

- Metrics can be source-agnostic.
- Source file and row provenance is preserved.
- Missing optional fields remain null or unavailable.

## Alternatives Considered

- Compute directly from each raw format: rejected because it would duplicate metric logic.
