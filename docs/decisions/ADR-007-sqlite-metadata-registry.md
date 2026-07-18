# ADR-007: SQLite Metadata Registry

Status: accepted

## Context

The prototype needs persistent metadata but has no real data-volume evidence.

## Decision

Use SQLite for seeds, experiments, runs, bundle imports, and JSON references.

## Consequences

- Local, dependency-light persistence.
- Idempotent bundle import support.
- Row-level analytics can be deferred.

## Alternatives Considered

- DuckDB/Parquet now: deferred until real volumes justify it.
- ORM: rejected as unnecessary for the current simple schema.
