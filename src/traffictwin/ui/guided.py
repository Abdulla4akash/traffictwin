"""Framework-independent guided research workflow definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from traffictwin.ui.labels import UiPage


class DemoTrack(StrEnum):
    """Evidence tracks available in the guided demo."""

    STANDALONE = "Standalone synthetic"
    TOS = "Randy/TOS imported simulation"


@dataclass(frozen=True)
class GuidedDemoStep:
    """One stage in a guided research workflow."""

    key: str
    title: str
    target_page: UiPage
    input_label: str
    operation_label: str
    output_label: str
    boundary: str


STANDALONE_STEPS: tuple[GuidedDemoStep, ...] = (
    GuidedDemoStep(
        key="validate",
        title="Validate a run bundle",
        target_page=UiPage.BUNDLE_IMPORT,
        input_label="Synthetic baseline bundle with manifest, seed, and CSV records.",
        operation_label="Validate schemas, units, rows, evidence availability, and provenance.",
        output_label="Machine-readable validation report and canonical in-memory records.",
        boundary="The bundle is synthetic and does not represent observed Manchester traffic.",
    ),
    GuidedDemoStep(
        key="metrics",
        title="Inspect deterministic metrics",
        target_page=UiPage.RUN_OVERVIEW,
        input_label="Accepted canonical task, infrastructure, traffic, and trip records.",
        operation_label="Apply the versioned Phase 3 metric catalogue.",
        output_label="Available metric values plus explicit unavailable-reason codes.",
        boundary="Metric values describe this generated run; they are not external validation.",
    ),
    GuidedDemoStep(
        key="compare",
        title="Compare baseline and stress",
        target_page=UiPage.COMPARE,
        input_label="Seed-aligned baseline and stressed synthetic runs.",
        operation_label="Check compatibility and calculate deterministic deltas.",
        output_label="Absolute and relative changes with both runs' provenance.",
        boundary="A change is not automatically labelled better, worse, or causal.",
    ),
    GuidedDemoStep(
        key="replay",
        title="Replay historical records",
        target_page=UiPage.OPERATIONS,
        input_label="Timestamped canonical records from the selected run bundle.",
        operation_label="Advance a logical clock and filter records to the selected window.",
        output_label="Deterministic traffic, vehicle, task, incident, and RSU timelines.",
        boundary="Historical replay does not create a live stream or simulate missing data.",
    ),
    GuidedDemoStep(
        key="diagnose",
        title="Inspect candidate hypotheses",
        target_page=UiPage.EVIDENCE,
        input_label="A versioned EvidencePack containing validated metric results.",
        operation_label="Evaluate deterministic rules R0-R3 with recorded thresholds.",
        output_label=(
            "Candidate hypotheses, alternatives, missing evidence, and verification steps."
        ),
        boundary="Diagnostic hypotheses are not proven root causes.",
    ),
    GuidedDemoStep(
        key="trace",
        title="Trace a result to source evidence",
        target_page=UiPage.PROVENANCE,
        input_label="A displayed metric or diagnostic rule result.",
        operation_label="Follow stable evidence keys through canonical records and source rows.",
        output_label="Read-only JSON or Markdown lineage with explicit missing links.",
        boundary="Provenance supports auditability; it does not establish real-world causality.",
    ),
    GuidedDemoStep(
        key="report",
        title="Export a research report",
        target_page=UiPage.REPORTS,
        input_label="Existing validation, metrics, evidence, diagnostics, and provenance outputs.",
        operation_label="Render deterministic Markdown or self-contained HTML templates.",
        output_label="A reproducible report with limitations and source context.",
        boundary="Report prose is template-based and introduces no new findings.",
    ),
)


TOS_STEPS: tuple[GuidedDemoStep, ...] = (
    GuidedDemoStep(
        key="tos-inspect",
        title="Inspect Randy's artifact package",
        target_page=UiPage.TOS_DATA,
        input_label="Evaluation CSV, NPZ arrays, JSON summaries, traces, and training records.",
        operation_label="Validate documented contracts without modifying the source package.",
        output_label="Artifact inventory, source findings, capabilities, and package fingerprint.",
        boundary="This is imported simulation evidence, not a direct simulator connection.",
    ),
    GuidedDemoStep(
        key="tos-results",
        title="Explore the evaluation matrix",
        target_page=UiPage.TOS_RESULTS,
        input_label="Validated source evaluation rows across campaigns, cells, fleets, and seeds.",
        operation_label="Group source-reported outcomes and align compatible campaign pairs.",
        output_label="Evaluation matrix, paired deltas, and documented domain labels.",
        boundary="TrafficTwin preserves source definitions rather than silently redefining them.",
    ),
    GuidedDemoStep(
        key="tos-replay",
        title="Replay mobility and RSU evidence",
        target_page=UiPage.TOS_REPLAY,
        input_label="Documented trace and per-step NPZ arrays from matched runs.",
        operation_label="Read bounded historical windows using confirmed source units.",
        output_label="Mobility, action, task, and RSU pressure views for source steps.",
        boundary="The replay is historical and file-backed; it is not live SUMO telemetry.",
    ),
    GuidedDemoStep(
        key="tos-audit",
        title="Audit training and reproducibility",
        target_page=UiPage.TOS_TRAINING,
        input_label="Training histories, greedy summaries, actors, records, and source commits.",
        operation_label="Cross-reference source artifacts and preserve unresolved gaps.",
        output_label="Reproducibility audit and research-safe supervisor exports.",
        boundary="TrafficTwin inspects existing training artifacts and does not train a model.",
    ),
)


def steps_for_track(track: DemoTrack) -> tuple[GuidedDemoStep, ...]:
    """Return the stable stages for an evidence track."""

    if track is DemoTrack.TOS:
        return TOS_STEPS
    return STANDALONE_STEPS


def bounded_step(index: int, step_count: int) -> int:
    """Clamp a stage index to the available workflow."""

    if step_count <= 0:
        return 0
    return max(0, min(index, step_count - 1))
