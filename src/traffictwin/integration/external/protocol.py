"""Runtime-checkable interface for external result-package adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from traffictwin.integration.external.models import (
    ExternalAdapterContract,
    ExternalProvenanceObservation,
    ExternalSourceDiscovery,
    ExternalValidationSummary,
)


@runtime_checkable
class ExternalSourceAdapter(Protocol):
    """Evidence-only adapter interface; implementations never imply source equivalence."""

    adapter_id: str
    adapter_version: str

    def discover(self, source: Path) -> ExternalSourceDiscovery:
        """Match exact source markers without mutating or deeply parsing the source."""

    def contract(self) -> ExternalAdapterContract:
        """Return the adapter's versioned semantics, capability, and conversion contract."""

    def validate(
        self,
        source: Path,
        *,
        deep: bool = False,
    ) -> tuple[ExternalValidationSummary, list[ExternalProvenanceObservation]]:
        """Run the adapter's existing source-specific read-only validator."""

    def inspect(
        self,
        source: Path,
        *,
        deep: bool = False,
    ) -> tuple[ExternalValidationSummary, list[ExternalProvenanceObservation]]:
        """Alias the portable inspection payload supplied by ``validate``."""
