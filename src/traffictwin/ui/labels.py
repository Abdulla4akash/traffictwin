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
    EVIDENCE = "Evidence & Diagnostic Readiness"


REQUIRED_PROTOTYPE_NOTICE = (
    "Current prototype supports synthetic fixtures, imported run bundles, and historical replay. "
    "Direct simulator launch, live data, and diagnostic rules are not yet implemented."
)

DIAGNOSTIC_NOTICE = (
    "Deterministic diagnostic hypotheses R1-R3 are planned for Phase 5 and are not active "
    "in this version."
)
