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

    HOME = "Home"
    SCENARIO = "Scenario Builder"
    BUNDLE_IMPORT = "Bundle Import & Validation"
    TOS_DATA = "TOS Data Import"
    EXPERIMENT_MANAGER = "Experiment Manager"
    OPERATIONS = "Replay"
    RUN_OVERVIEW = "Run Overview"
    INFRASTRUCTURE = "Infrastructure & Congestion"
    COMPARE = "Comparison"
    JOURNEY_TIME = "Journey-Time Lens"
    EVIDENCE = "Diagnostics & Evidence"
    PROVENANCE = "Provenance Explorer"
    REPORTS = "Reports"
    SEARCH = "Search"
    SETTINGS = "Settings"
    ABOUT = "About"


PAGE_DESCRIPTIONS: dict[UiPage, str] = {
    UiPage.HOME: "Workspace status, quick actions, and current prototype limits.",
    UiPage.SCENARIO: "Author deterministic synthetic scenario configurations and bundles.",
    UiPage.BUNDLE_IMPORT: "Validate and import TrafficTwin run bundles.",
    UiPage.TOS_DATA: (
        "Inspect and import documented TOS evaluation summaries and historical source arrays."
    ),
    UiPage.EXPERIMENT_MANAGER: (
        "Browse experiments, runs, seeds, comparisons, and provenance links."
    ),
    UiPage.OPERATIONS: "Inspect imported data through deterministic historical replay controls.",
    UiPage.RUN_OVERVIEW: "Review run-level metrics computed by the Phase 3 engine.",
    UiPage.INFRASTRUCTURE: "Inspect RSU queue, utilisation, and saturation summaries.",
    UiPage.COMPARE: "Compare baseline and variation runs without causal labels.",
    UiPage.JOURNEY_TIME: "Review imported or synthetic trip-duration evidence.",
    UiPage.EVIDENCE: "Inspect evidence availability and deterministic diagnostic hypotheses.",
    UiPage.PROVENANCE: "Trace displayed results back to source rows and bundle context.",
    UiPage.REPORTS: "Find, download, and deliberately regenerate deterministic reports.",
    UiPage.SEARCH: "Search local runs, experiments, metrics, rules, reports, and source files.",
    UiPage.SETTINGS: "Adjust local UI preferences for replay, reports, and demo workflow.",
    UiPage.ABOUT: "Review package, schema, metric, diagnostic, and generator versions.",
}


REQUIRED_PROTOTYPE_NOTICE = (
    "Current prototype supports synthetic fixtures, imported run bundles, historical replay, and "
    "deterministic diagnostic hypotheses. Direct simulator launch and live data are not yet "
    "implemented."
)

DIAGNOSTIC_NOTICE = (
    "These are deterministic, evidence-based diagnostic hypotheses. They are not proven root "
    "causes and should be verified through controlled follow-up experiments."
)
