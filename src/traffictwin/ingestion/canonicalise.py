"""Canonicalisation entry points."""

from __future__ import annotations

from pathlib import Path

from traffictwin.adapters.generic_csv import GenericTabularAdapter
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.validation.reconciliation import reconcile_tables
from traffictwin.validation.report import ValidationReport


def canonicalise_bundle(
    root: Path,
    manifest: BundleManifest,
    report: ValidationReport,
) -> CanonicalTables:
    """Canonicalise a bundle using the generic declared-tabular adapter."""

    tables = GenericTabularAdapter().canonicalise(root, manifest, report)
    reconcile_tables(tables, report)
    return tables
