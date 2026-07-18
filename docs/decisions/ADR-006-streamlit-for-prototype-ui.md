# ADR-006: Streamlit For Prototype UI

Status: accepted

## Context

The project needs an easy research UI without building a production web stack.

## Decision

Use Streamlit as a thin UI over library services.

## Consequences

- Fast local demonstration.
- Simple launch command.
- UI tests focus on services, state, and chart data.

## Alternatives Considered

- React/FastAPI: rejected as unnecessary infrastructure for the current prototype.
- CLI only: rejected because supervisor feedback asked for buttons and screens.
