"""Consistent UI labels."""

from __future__ import annotations

from enum import StrEnum


class DataMode(StrEnum):
    """Visible data-mode labels."""

    SYNTHETIC = "SYNTHETIC"
    IMPORTED = "IMPORTED"
    HISTORICAL_REPLAY = "HISTORICAL REPLAY"
    NEAR_LIVE = "NEAR-LIVE"
    TRUE_LIVE = "TRUE LIVE"


class UiPage(StrEnum):
    """Application pages."""

    HOME = "Home / Project Status"
    SCENARIO = "Scenario Studio"
    BUNDLE_IMPORT = "Bundle Import & Validation"
    OPERATIONS = "Operations View"
    RUN_OVERVIEW = "Run Overview"
    INFRASTRUCTURE = "Infrastructure & Congestion"
    COMPARE = "What-if Compare"
    JOURNEY_TIME = "Journey-Time Lens"
    EVIDENCE = "Evidence & Diagnostic Hypotheses"
    PROVENANCE = "Provenance Explorer"


REQUIRED_PROTOTYPE_NOTICE = (
    "Current prototype supports synthetic fixtures, imported run bundles, historical replay, and "
    "deterministic diagnostic hypotheses. Direct simulator launch and live data are not yet "
    "implemented."
)

DIAGNOSTIC_NOTICE = (
    "These are deterministic, evidence-based diagnostic hypotheses. They are not proven root "
    "causes and should be verified through controlled follow-up experiments."
)
