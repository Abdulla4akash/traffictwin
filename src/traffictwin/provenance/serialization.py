"""Provenance serialisation helpers."""

from __future__ import annotations

from traffictwin.provenance.models import ProvenanceTrace


def trace_to_json(trace: ProvenanceTrace) -> str:
    """Return a machine-readable provenance trace JSON document."""

    return trace.to_json()
