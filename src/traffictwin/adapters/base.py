"""Adapter protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.validation.report import ValidationReport


class BundleAdapter(Protocol):
    """Protocol for bundle adapters."""

    def canonicalise(
        self,
        root: Path,
        manifest: BundleManifest,
        report: ValidationReport,
    ) -> CanonicalTables:
        """Convert source files into canonical in-memory records."""
