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
    GUIDED_DEMO = "Guided Demo"
    EXPERIMENT_PLANNER = "Experiment Planner"
    PARAMETER_SWEEP = "Parameter Sweep"
    SCENARIO_MUTATION = "Scenario Mutations"
    SCENARIO = "Scenario Builder"
    BUNDLE_IMPORT = "Bundle Import & Validation"
    MANIFEST_WIZARD = "Manifest Inference Wizard"
    SUMO_IMPORT = "SUMO Output Import"
    TOS_DATA = "TOS Data Import"
    TOS_RESULTS = "TOS Results"
    TOS_REPLAY = "TOS Mobility & RSU Replay"
    TOS_TRAINING = "TOS Training & Audit"
    EXPERIMENT_MANAGER = "Experiment Manager"
    TRIVIALITY = "Triviality & Winner Map"
    OPERATIONS = "Replay"
    RUN_OVERVIEW = "Run Overview"
    TEMPORAL_METRICS = "Temporal Metrics"
    ENERGY = "Energy Evidence"
    FAIRNESS = "Fairness Evidence"
    THRESHOLD_SENSITIVITY = "Threshold Sensitivity"
    STATISTICAL_STUDY = "Statistical Study"
    SPATIAL_RSU = "Spatial & RSU Evidence"
    INFRASTRUCTURE = "Infrastructure & Congestion"
    COMPARE = "Comparison"
    JOURNEY_TIME = "Journey-Time Lens"
    EVIDENCE = "Diagnostics & Evidence"
    PROVENANCE = "Provenance Explorer"
    REPORTS = "Reports"
    PARTICIPANT_EVALUATION = "Mock Evaluation Analysis"
    SEARCH = "Search"
    SETTINGS = "Settings"
    ABOUT = "About"


PAGE_DESCRIPTIONS: dict[UiPage, str] = {
    UiPage.HOME: "Workspace status, quick actions, and current prototype limits.",
    UiPage.GUIDED_DEMO: (
        "Follow the validated synthetic or imported-simulation evidence workflow stage by stage."
    ),
    UiPage.EXPERIMENT_PLANNER: (
        "Define a reproducible comparison plan from registered seeds, policies, and random seeds."
    ),
    UiPage.PARAMETER_SWEEP: (
        "Expand bounded parameter grids into labelled seeds, local synthetic bundles, or "
        "unexecuted external requests."
    ),
    UiPage.SCENARIO_MUTATION: (
        "Apply one deterministic mutation to a copied synthetic/evaluation bundle with an exact "
        "change ledger."
    ),
    UiPage.SCENARIO: "Author deterministic synthetic scenario configurations and bundles.",
    UiPage.BUNDLE_IMPORT: "Validate and import TrafficTwin run bundles.",
    UiPage.MANIFEST_WIZARD: (
        "Suggest CSV mappings deterministically, edit them, and confirm before analysis."
    ),
    UiPage.SUMO_IMPORT: (
        "Validate and import immutable SUMO tripinfo and summary XML outputs without launching "
        "SUMO."
    ),
    UiPage.TOS_DATA: (
        "Inspect and import documented TOS evaluation summaries and historical source arrays."
    ),
    UiPage.TOS_RESULTS: (
        "Explore the imported evaluation matrix, paired campaign deltas, and domain labels."
    ),
    UiPage.TOS_REPLAY: (
        "Replay documented source steps and inspect processed mobility, RSU, and task evidence."
    ),
    UiPage.TOS_TRAINING: (
        "Inspect source training histories, reproducibility checks, and research-safe exports."
    ),
    UiPage.EXPERIMENT_MANAGER: (
        "Browse experiments, runs, seeds, comparisons, and provenance links."
    ),
    UiPage.TRIVIALITY: (
        "Inspect experiment-level triviality evidence, policy winners, regret, and portfolio "
        "output."
    ),
    UiPage.OPERATIONS: "Inspect imported data through deterministic historical replay controls.",
    UiPage.RUN_OVERVIEW: "Review run-level metrics computed by the Phase 3 engine.",
    UiPage.TEMPORAL_METRICS: (
        "Compute deterministic metrics over declared aligned half-open time windows."
    ),
    UiPage.ENERGY: (
        "Inspect contract-gated task energy and evaluate the deterministic R8 candidate."
    ),
    UiPage.FAIRNESS: (
        "Inspect evidence-gated operational vehicle-tier and RSU disparity measures."
    ),
    UiPage.THRESHOLD_SENSITIVITY: (
        "Sweep provisional R5/R7/R8 thresholds without silently changing rule defaults."
    ),
    UiPage.STATISTICAL_STUDY: (
        "Evaluate paired comparisons, N-way rankings, TOST equivalence, regression gates, and "
        "prospective power plans."
    ),
    UiPage.SPATIAL_RSU: (
        "Inspect exact V2I execution-target outcomes and contracted source-frame spatial cells."
    ),
    UiPage.INFRASTRUCTURE: "Inspect RSU queue, utilisation, and saturation summaries.",
    UiPage.COMPARE: "Compare baseline and variation runs without causal labels.",
    UiPage.JOURNEY_TIME: "Review imported or synthetic trip-duration evidence.",
    UiPage.EVIDENCE: "Inspect evidence availability and deterministic diagnostic hypotheses.",
    UiPage.PROVENANCE: "Trace displayed results back to source rows and bundle context.",
    UiPage.REPORTS: "Find, download, and deliberately regenerate deterministic reports.",
    UiPage.PARTICIPANT_EVALUATION: (
        "Analyse explicitly labelled synthetic mock evaluation results; no participant data."
    ),
    UiPage.SEARCH: (
        "Search findings, annotations, reports, runs, experiments, and evidence references."
    ),
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
