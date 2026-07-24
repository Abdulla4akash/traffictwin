"""Framework-independent guided research workflow definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.ui.labels import UiPage


class DemoTrack(StrEnum):
    """Evidence tracks available in the guided demo."""

    STANDALONE = "Standalone synthetic"
    TOS = "Randy/TOS imported simulation"


class GuidedCompletionMode(StrEnum):
    """How one guided step can be completed."""

    REVIEW = "review"
    ACTION = "action"


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
    instruction: str
    completion_mode: GuidedCompletionMode = GuidedCompletionMode.REVIEW
    completion_action: str | None = None

    def __post_init__(self) -> None:
        """Require an action key only for action-completed stages."""

        if self.completion_mode is GuidedCompletionMode.ACTION:
            if not self.completion_action:
                raise ValueError("action-completed guided stages require an action key")
        elif self.completion_action is not None:
            raise ValueError("review-completed guided stages cannot declare an action key")


STANDALONE_STEPS: tuple[GuidedDemoStep, ...] = (
    GuidedDemoStep(
        key="plan",
        title="Frame a reproducible experiment",
        target_page=UiPage.EXPERIMENT_PLANNER,
        input_label="Registered scenario seeds, policy labels, and common random seeds.",
        operation_label="Validate the comparison design and build a bounded run-matrix preview.",
        output_label="A versioned planned Experiment record and downloadable YAML definition.",
        boundary="Saving a plan does not create runs or launch a simulator.",
        instruction=(
            "Validate the proposed experiment, inspect its run matrix, then register the planned "
            "experiment. The guide advances only after registration succeeds."
        ),
        completion_mode=GuidedCompletionMode.ACTION,
        completion_action="register_experiment_plan",
    ),
    GuidedDemoStep(
        key="validate",
        title="Validate a run bundle",
        target_page=UiPage.BUNDLE_IMPORT,
        input_label="Synthetic baseline bundle with manifest, seed, and CSV records.",
        operation_label="Validate schemas, units, rows, evidence availability, and provenance.",
        output_label="Machine-readable validation report and canonical in-memory records.",
        boundary="The bundle is synthetic and does not represent observed Manchester traffic.",
        instruction=(
            "Validate the selected synthetic bundle and inspect its validation findings and "
            "evidence availability. Continue after you have reviewed the result."
        ),
    ),
    GuidedDemoStep(
        key="metrics",
        title="Inspect deterministic metrics",
        target_page=UiPage.RUN_OVERVIEW,
        input_label="Accepted canonical task, infrastructure, traffic, and trip records.",
        operation_label="Apply the versioned Phase 3 metric catalogue.",
        output_label="Available metric values plus explicit unavailable-reason codes.",
        boundary="Metric values describe this generated run; they are not external validation.",
        instruction=(
            "Inspect the primary task metrics and at least one unavailable or partial metric so "
            "you can explain what the run does and does not evidence."
        ),
    ),
    GuidedDemoStep(
        key="compare",
        title="Compare baseline and stress",
        target_page=UiPage.COMPARE,
        input_label="Seed-aligned baseline and stressed synthetic runs.",
        operation_label="Check compatibility and calculate deterministic deltas.",
        output_label="Absolute and relative changes with both runs' provenance.",
        boundary="A change is not automatically labelled better, worse, or causal.",
        instruction=(
            "Inspect the compatibility result and one deterministic difference. Confirm that "
            "the page does not turn a difference into a causal or quality claim."
        ),
    ),
    GuidedDemoStep(
        key="replay",
        title="Replay historical records",
        target_page=UiPage.OPERATIONS,
        input_label="Timestamped canonical records from the selected run bundle.",
        operation_label="Advance a logical clock and filter records to the selected window.",
        output_label="Deterministic traffic, vehicle, task, incident, and RSU timelines.",
        boundary="Historical replay does not create a live stream or simulate missing data.",
        instruction=(
            "Move the replay clock or select a filter, then inspect how the historical window "
            "changes without creating new observations."
        ),
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
        instruction=(
            "Inspect the readiness state and one deterministic hypothesis, including its "
            "alternatives, missing evidence, or verification steps."
        ),
    ),
    GuidedDemoStep(
        key="trace",
        title="Trace a result to source evidence",
        target_page=UiPage.PROVENANCE,
        input_label="A displayed metric or diagnostic rule result.",
        operation_label="Follow stable evidence keys through canonical records and source rows.",
        output_label="Read-only JSON or Markdown lineage with explicit missing links.",
        boundary="Provenance supports auditability; it does not establish real-world causality.",
        instruction=(
            "Choose one metric or diagnostic result and follow it to its available source rows "
            "or explicit missing links."
        ),
    ),
    GuidedDemoStep(
        key="report",
        title="Export a research report",
        target_page=UiPage.REPORTS,
        input_label="Existing validation, metrics, evidence, diagnostics, and provenance outputs.",
        operation_label="Render deterministic Markdown or self-contained HTML templates.",
        output_label="A reproducible report with limitations and source context.",
        boundary="Report prose is template-based and introduces no new findings.",
        instruction=(
            "Regenerate one deterministic report. The guide finishes automatically only after "
            "the report service succeeds."
        ),
        completion_mode=GuidedCompletionMode.ACTION,
        completion_action="regenerate_report",
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
        instruction=(
            "Inspect the configured package and review its inventory, findings, capabilities, "
            "and immutable package fingerprint."
        ),
    ),
    GuidedDemoStep(
        key="tos-results",
        title="Explore the evaluation matrix",
        target_page=UiPage.TOS_RESULTS,
        input_label="Validated source evaluation rows across campaigns, cells, fleets, and seeds.",
        operation_label="Group source-reported outcomes and align compatible campaign pairs.",
        output_label="Evaluation matrix, paired deltas, and documented domain labels.",
        boundary="TrafficTwin preserves source definitions rather than silently redefining them.",
        instruction=(
            "Choose one source measure and inspect its matrix, sample counts, unit, and "
            "documented limitations."
        ),
    ),
    GuidedDemoStep(
        key="tos-replay",
        title="Replay mobility and RSU evidence",
        target_page=UiPage.TOS_REPLAY,
        input_label="Documented trace and per-step NPZ arrays from matched runs.",
        operation_label="Read bounded historical windows using confirmed source units.",
        output_label="Mobility, action, task, and RSU pressure views for source steps.",
        boundary="The replay is historical and file-backed; it is not live SUMO telemetry.",
        instruction=(
            "Select an instrumented run, move its source-step replay, and inspect one mobility, "
            "task, or RSU view."
        ),
    ),
    GuidedDemoStep(
        key="tos-audit",
        title="Audit training and reproducibility",
        target_page=UiPage.TOS_TRAINING,
        input_label="Training histories, greedy summaries, actors, records, and source commits.",
        operation_label="Cross-reference source artifacts and preserve unresolved gaps.",
        output_label="Reproducibility audit and research-safe supervisor exports.",
        boundary="TrafficTwin inspects existing training artifacts and does not train a model.",
        instruction=(
            "Inspect one training history and the reproducibility audit, then review which "
            "claims remain unavailable."
        ),
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


class GuidedDemoProgress(BaseModel):
    """Framework-independent progress for one per-session guided workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track: DemoTrack
    step_index: int = Field(default=0, ge=0)
    completed_step_keys: tuple[str, ...] = ()
    skipped_step_keys: tuple[str, ...] = ()
    active: bool = True
    finished: bool = False

    @model_validator(mode="after")
    def validate_progress(self) -> GuidedDemoProgress:
        """Bind progress to the exact stable stage inventory."""

        steps = steps_for_track(self.track)
        if self.step_index >= len(steps):
            raise ValueError("guided stage index is outside the selected track")
        valid_keys = {step.key for step in steps}
        completed = set(self.completed_step_keys)
        skipped = set(self.skipped_step_keys)
        if not completed <= valid_keys or not skipped <= valid_keys:
            raise ValueError("guided progress contains an unknown stage key")
        if completed & skipped:
            raise ValueError("a guided stage cannot be both completed and skipped")
        if len(completed) != len(self.completed_step_keys) or len(skipped) != len(
            self.skipped_step_keys
        ):
            raise ValueError("guided stage outcomes cannot be duplicated")
        if self.active and self.finished:
            raise ValueError("a finished guided workflow cannot remain active")
        outcomes = completed | skipped
        required_predecessors = {step.key for step in steps[: self.step_index]}
        if not required_predecessors <= outcomes:
            raise ValueError("every preceding guided stage must have a recorded outcome")
        if self.finished and self.step_index != len(steps) - 1:
            raise ValueError("a finished guided workflow must remain on its final stage")
        if self.finished and outcomes != valid_keys:
            raise ValueError("a finished guided workflow must record every stage outcome")
        return self

    @property
    def current_step(self) -> GuidedDemoStep:
        """Return the current stable stage definition."""

        return steps_for_track(self.track)[self.step_index]

    def complete_current(self) -> GuidedDemoProgress:
        """Record the current stage as complete and advance once."""

        return self._advance(completed=True)

    def skip_current(self) -> GuidedDemoProgress:
        """Record an explicit skip and advance once."""

        return self._advance(completed=False)

    def previous(self) -> GuidedDemoProgress:
        """Return to the preceding stage without erasing recorded outcomes."""

        return self.model_copy(
            update={
                "step_index": max(0, self.step_index - 1),
                "active": True,
                "finished": False,
            }
        )

    def exit(self) -> GuidedDemoProgress:
        """Pause guidance on the current stage."""

        return self.model_copy(update={"active": False, "finished": False})

    def resume(self) -> GuidedDemoProgress:
        """Resume guidance on the retained stage."""

        return self.model_copy(update={"active": True, "finished": False})

    def _advance(self, *, completed: bool) -> GuidedDemoProgress:
        steps = steps_for_track(self.track)
        key = self.current_step.key
        completed_keys = list(self.completed_step_keys)
        skipped_keys = list(self.skipped_step_keys)
        target = completed_keys if completed else skipped_keys
        other = skipped_keys if completed else completed_keys
        if key in other:
            other.remove(key)
        if key not in target:
            target.append(key)
        is_last = self.step_index == len(steps) - 1
        return self.model_copy(
            update={
                "step_index": self.step_index if is_last else self.step_index + 1,
                "completed_step_keys": tuple(completed_keys),
                "skipped_step_keys": tuple(skipped_keys),
                "active": not is_last,
                "finished": is_last,
            }
        )


def start_guided_progress(track: DemoTrack) -> GuidedDemoProgress:
    """Start one clean guided workflow for the selected evidence track."""

    return GuidedDemoProgress(track=track)
