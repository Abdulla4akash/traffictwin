"""Deterministic service for the Event-to-Scenario Bridge."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from typing import Any

from traffictwin.data_contract.fingerprint import sanitise_for_csv
from traffictwin.event_scenario_bridge.models import (
    BridgeFinding,
    BridgeStatus,
    DeclaredEventReference,
    EventAlignedHandoff,
    EventScenarioBridgeManifest,
    EventScenarioBridgeRequest,
    ExperimentPlanHandoff,
    PreregistrationDraftHandoff,
    ScenarioSeedHandoff,
)

# Absolute-path patterns to reject in portable text
_WINDOWS_PATH = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)")
_FILE_URI = re.compile(r"(?i)file://[^\s\"'<>]+")
_HOME_PATH = re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+")
_POSIX_ABS = re.compile(r"(?<![/:\w])/(?!/)[^\s\"'<>]+")

_SUPPORTED_METRIC_KEYS = frozenset(
    {
        "task.completion.rate",
        "task.completion.rate_by_class",
        "task.incomplete.rate",
        "task.latency.mean_ms",
        "task.latency.p50_ms",
        "task.latency.p95_ms",
        "task.energy.mean_per_observed_task_j",
        "infra.queue_length.mean",
        "infra.utilisation.mean",
        "trip.duration.mean_s",
        "trip.completion.rate",
        "traffic.speed.mean_mps",
        "traffic.count.total",
    }
)

_KNOWN_WINDOWS = frozenset({"pre", "event", "post", "baseline", "comparison"})


class EventScenarioBridgeError(ValueError):
    """Raised when a bridge request cannot be satisfied."""


def _fingerprint(payload: object) -> str:  # noqa: ANN401
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _event_fingerprint(event: DeclaredEventReference) -> str:
    return _fingerprint(event.canonical_dict())


def _assert_no_absolute_path(value: str, field_name: str) -> None:
    if (
        _WINDOWS_PATH.search(value)
        or _FILE_URI.search(value)
        or _HOME_PATH.search(value)
        or _POSIX_ABS.search(value)
    ):
        msg = f"{field_name} must not contain an absolute path or file URI"
        raise EventScenarioBridgeError(msg)


def _validate_no_path_in_request(request: EventScenarioBridgeRequest) -> None:
    for field_name, value in [
        ("title", request.title),
        ("description", request.description),
        ("event_reference.event_kind", request.event_reference.event_kind),
        ("event_reference.source_label", request.event_reference.source_label),
        ("event_reference.provenance_detail", request.event_reference.provenance_detail or ""),
        ("event_reference.bundle_id", request.event_reference.bundle_id or ""),
        ("event_reference.incident_id", request.event_reference.incident_id or ""),
        ("impact_envelope.affected_area_label", request.impact_envelope.affected_area_label or ""),
    ]:
        _assert_no_absolute_path(value, field_name)
    for proposal in request.mutation_proposals:
        _assert_no_absolute_path(proposal.target_description, "mutation target_description")
        if proposal.table_kind is not None:
            table_kind = proposal.table_kind
            _assert_no_absolute_path(table_kind, "mutation table_kind")
    for metric in request.intended_metrics:
        _assert_no_absolute_path(metric, "intended_metrics item")
    for window in request.intended_windows:
        _assert_no_absolute_path(window, "intended_windows item")


def _limitations() -> list[str]:
    return [
        "Unexecuted design only — no simulation or VEC was launched.",
        "Synthetic design does not represent the real event.",
        "Evidence is not created or admitted; admission remains false.",
        "Windows use half-open semantics [start,end); no interpolation or zero-fill.",
        "Findings are descriptive during declared windows, not causal claims.",
        "Mutations are restricted to closed, bounded types already supported on main.",
        "Portable output contains no absolute paths, wall-clock, or credentials.",
    ]


def _build_findings(
    request: EventScenarioBridgeRequest,
) -> tuple[list[BridgeFinding], list[str]]:
    findings: list[BridgeFinding] = []
    warnings: list[str] = []

    findings.append(
        BridgeFinding(
            finding_id="bridge-unexecuted",
            description="This bridge is an unexecuted design; the scenario has not been run.",
            severity="info",
        )
    )
    findings.append(
        BridgeFinding(
            finding_id="bridge-no-causality",
            description=(
                "Any future comparison of before, during, and after windows is descriptive "
                "for the declared anchor; it does not establish causal attribution."
            ),
            severity="limitation",
        )
    )
    findings.append(
        BridgeFinding(
            finding_id="bridge-half-open",
            description=(
                "Aligned windows use [start,end) half-open bins "  # noqa: E501
                "anchored to the authored event time; "
                "rows on exact boundaries fall in exactly one bin."
            ),
            severity="info",
        )
    )
    # One finding per mutation to preserve provenance
    for idx, proposal in enumerate(request.mutation_proposals):
        findings.append(
            BridgeFinding(
                finding_id=f"bridge-mutation-{idx + 1:02d}",
                description=(
                    f"Mutation {idx + 1}: {proposal.mutation_kind.value} targeting "
                    f"{proposal.target_description} — closed, bounded, unexecuted."
                ),
                severity="info",
            )
        )

    if len(request.mutation_proposals) > 1:
        warnings.append(
            "Multiple ordered mutations are declared; their joint effect is not "
            "modelled or simulated."
        )
    if request.impact_envelope.affected_links:
        count = len(request.impact_envelope.affected_links)
        warnings.append(
            f"Affected links ({count}) are declared scope labels; network feasibility "
            "is not checked."
        )
    return findings, warnings


def build_event_scenario_bridge_manifest(
    request: EventScenarioBridgeRequest,
    *,
    clock: datetime | None = None,
) -> EventScenarioBridgeManifest:
    """Build a deterministic, unexecuted bridge manifest.

    Fail-closed checks:
    - baseline fingerprint and seed_id are required (validated by model);
    - mutations are limited to the closed MutationKind set;
    - all portable text is checked for absolute paths;
    - metric/window compatibility is advisory (warn not refuse) but closed kinds are strict.
    """
    _validate_no_path_in_request(request)

    # Validate metric keys against catalogue (advisory warn if unknown, not refused;
    # but we enforce known-set for determinism — unknown metrics produce a finding)
    effective_metrics = list(request.intended_metrics)
    extra_warnings: list[str] = []
    unknown_metrics = [m for m in effective_metrics if m not in _SUPPORTED_METRIC_KEYS]
    if unknown_metrics:
        extra_warnings.append(
            "Some intended metrics are not in the bounded reference catalogue; "
            "they are recorded as authored labels, not validated engine outputs."
        )

    # Validate windows (advisory)
    unknown_windows = [w for w in request.intended_windows if w not in _KNOWN_WINDOWS]
    if unknown_windows and request.intended_windows:
        extra_warnings.append(
            "Some intended windows use non-standard labels; they are recorded as authored scope."
        )

    event_fp = _event_fingerprint(request.event_reference)
    # Use a request-derived deterministic prefix for identifiers; the true
    # bridge_fingerprint will be the manifest canonical hash (stable, portable).
    request_prefix = _fingerprint(request.canonical_dict())

    manifest_id = f"bridge-{request_prefix[:12]}"
    derived_seed_id = f"{request.baseline_seed_id}-bridge-{request_prefix[:8]}"

    # Build four handoffs — all bind the same fingerprints and remain not_executed
    handoff_base_limits = _limitations()

    # Temporary placeholder fingerprint — will be replaced after manifest canonical is known.
    _placeholder = "0" * 64

    # --- Handoff 1: scenario seed / mutation ---
    seed_handoff = ScenarioSeedHandoff(
        handoff_id=f"{manifest_id}-seed",
        baseline_seed_id=request.baseline_seed_id,
        baseline_seed_fingerprint=request.baseline_seed_fingerprint,
        event_fingerprint=event_fp,
        bridge_fingerprint=_placeholder,
        derived_seed_id=derived_seed_id,
        mutation_proposals=list(request.mutation_proposals),
        limitations=list(handoff_base_limits),
    )

    # --- Handoff 2: Event-Aligned spec ---
    anchor_iso = request.event_reference.anchor_time_utc.isoformat().replace("+00:00", "Z")
    aligned_handoff = EventAlignedHandoff(
        handoff_id=f"{manifest_id}-aligned",
        event_fingerprint=event_fp,
        bridge_fingerprint=_placeholder,
        baseline_seed_id=request.baseline_seed_id,
        baseline_seed_fingerprint=request.baseline_seed_fingerprint,
        anchor_time_utc=anchor_iso,
        impact_envelope=request.impact_envelope,
        intended_metrics=list(request.intended_metrics),
        limitations=list(handoff_base_limits),
    )

    # --- Handoff 3: preregistration draft ---
    # Study question is authored from the request title/description
    question_text = request.title.strip()
    # Ensure at least 12 chars; use description fallback if title too short
    if len(question_text) < 12:
        question_text = (request.description.strip() or request.title.strip())[:200]
        if len(question_text) < 12:
            evt_id = request.event_reference.event_id  # noqa: E501
            question_text = f"How does the declared event {evt_id} relate to outcomes?"

    prereg_handoff = PreregistrationDraftHandoff(
        handoff_id=f"{manifest_id}-prereg",
        event_fingerprint=event_fp,
        bridge_fingerprint=_placeholder,
        baseline_seed_id=request.baseline_seed_id,
        baseline_seed_fingerprint=request.baseline_seed_fingerprint,
        study_question=question_text,
        planned_metrics=list(effective_metrics),
        planned_windows=list(request.intended_windows)
        if request.intended_windows
        else ["pre", "event", "post"],
        planned_mutations=list(request.mutation_proposals),
        evidence_standing=request.evidence_standing,
        limitations=list(handoff_base_limits),
    )

    # --- Handoff 4: experiment plan ---
    # Planned cells: one per mutation × one per metric (bounded, display-only)
    cells: list[dict[str, Any]] = []
    for idx, proposal in enumerate(request.mutation_proposals):
        for metric in effective_metrics[:4]:  # bounded preview
            cells.append(
                {
                    "cell_id": f"cell-{idx + 1:02d}-{metric}",
                    "mutation_kind": proposal.mutation_kind.value,
                    "target": proposal.target_description,
                    "metric_key": metric,
                    "seed_id": derived_seed_id,
                    "role": "variation" if idx > 0 else "baseline_variation",
                }
            )

    plan_handoff = ExperimentPlanHandoff(
        handoff_id=f"{manifest_id}-plan",
        event_fingerprint=event_fp,
        bridge_fingerprint=_placeholder,
        baseline_seed_id=request.baseline_seed_id,
        baseline_seed_fingerprint=request.baseline_seed_fingerprint,
        derived_seed_id=derived_seed_id,
        planned_metrics=list(effective_metrics),
        planned_cells=cells,
        limitations=list(handoff_base_limits),
    )

    findings, warnings = _build_findings(request)
    warnings.extend(extra_warnings)

    # First pass with placeholder fingerprints — computes stable manifest fingerprint
    # (canonical excludes bridge_fingerprint from manifest and all handoffs, so
    # stamping does not change the hash).
    tentative = EventScenarioBridgeManifest(
        manifest_id=manifest_id,
        bridge_fingerprint=_placeholder,
        event_fingerprint=event_fp,
        baseline_seed_fingerprint=request.baseline_seed_fingerprint,
        baseline_seed_id=request.baseline_seed_id,
        request=request,
        scenario_seed_handoff=seed_handoff,
        event_aligned_handoff=aligned_handoff,
        preregistration_draft_handoff=prereg_handoff,
        experiment_plan_handoff=plan_handoff,
        findings=findings,
        status=BridgeStatus.OK,
        limitations=list(handoff_base_limits),
        warnings=warnings,
        created_at_utc=clock.astimezone(UTC) if clock is not None else None,
    )
    bridge_fp = tentative.computed_fingerprint()
    # Stamp deterministic binding fingerprint into every handoff + manifest.
    # Because canonical excludes bridge_fingerprint, this does not alter the hash.
    seed_handoff = seed_handoff.model_copy(update={"bridge_fingerprint": bridge_fp})
    aligned_handoff = aligned_handoff.model_copy(update={"bridge_fingerprint": bridge_fp})
    prereg_handoff = prereg_handoff.model_copy(update={"bridge_fingerprint": bridge_fp})
    plan_handoff = plan_handoff.model_copy(update={"bridge_fingerprint": bridge_fp})
    final = tentative.model_copy(
        update={
            "bridge_fingerprint": bridge_fp,
            "scenario_seed_handoff": seed_handoff,
            "event_aligned_handoff": aligned_handoff,
            "preregistration_draft_handoff": prereg_handoff,
            "experiment_plan_handoff": plan_handoff,
        }
    )
    if not final.verify_fingerprint():
        raise EventScenarioBridgeError("internal bridge fingerprint verification failed")
    return final


def export_bridge_json(manifest: EventScenarioBridgeManifest) -> str:
    """Return deterministic pretty JSON for download."""
    return json.dumps(manifest.to_portable_dict(), indent=2, sort_keys=True) + "\n"


def export_bridge_csv(manifest: EventScenarioBridgeManifest) -> str:
    """Return deterministic CSV for handoff summary (tabular export)."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

    writer.writerow(
        [
            "handoff_id",
            "handoff_kind",
            "execution_status",
            "evidence_created",
            "admission_created",
            "bridge_fingerprint",
            "event_fingerprint",
        ]
    )
    for handoff in (
        manifest.scenario_seed_handoff,
        manifest.event_aligned_handoff,
        manifest.preregistration_draft_handoff,
        manifest.experiment_plan_handoff,
    ):
        writer.writerow(
            [
                sanitise_for_csv(handoff.handoff_id),
                sanitise_for_csv(handoff.handoff_kind),
                sanitise_for_csv(handoff.execution_status),
                str(handoff.evidence_created),
                str(handoff.admission_created),
                sanitise_for_csv(handoff.bridge_fingerprint[:16] + "…"),
                sanitise_for_csv(handoff.event_fingerprint[:16] + "…"),
            ]
        )
    # Findings rows
    writer.writerow([])
    writer.writerow(["finding_id", "severity", "description"])
    for finding in sorted(manifest.findings, key=lambda f: f.finding_id):
        writer.writerow(
            [
                sanitise_for_csv(finding.finding_id),
                sanitise_for_csv(finding.severity),
                sanitise_for_csv(finding.description),
            ]
        )
    return output.getvalue()
