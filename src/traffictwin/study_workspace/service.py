# ruff: noqa: E501
"""Deterministic service for validation, lifecycle derivation, fingerprinting and guidance.

Business logic lives outside Streamlit. Thin UI renders typed outputs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from traffictwin.study_workspace.models import (
    KIND_SUPPORTED_VERSIONS,
    SINGLETON_KINDS,
    SUPPORTED_SCHEMA_VERSIONS,
    StudyWorkspaceManifest,
    WorkspaceAction,
    WorkspaceArtifactKind,
    WorkspaceBlocker,
    WorkspaceBlockerSeverity,
    WorkspaceCompatibilityStanding,
    WorkspaceLifecycleStage,
    WorkspaceValidationReport,
    _contains_absolute_path,
)

# ---------------------------------------------------------------------------
# Canonical helpers
# ---------------------------------------------------------------------------


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_manifest(manifest: StudyWorkspaceManifest) -> str:
    """Return stable SHA-256 fingerprint for one manifest (artifact-order-independent)."""
    # Delegates to model's deterministic fingerprint.
    return manifest.fingerprint()


def canonical_manifest_dict(manifest: StudyWorkspaceManifest) -> dict[str, Any]:
    return manifest.canonical_dict()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _is_hex64(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"[0-9a-f]{64}", value.lower()))


def validate_workspace(manifest: StudyWorkspaceManifest) -> WorkspaceValidationReport:
    """Validate one manifest and produce exact blockers and warnings.

    Never silently drops a bad reference; always surfaces a finding.
    """
    blockers: list[WorkspaceBlocker] = []
    warnings: list[WorkspaceBlocker] = []

    fingerprints = [a.fingerprint for a in manifest.artifacts]
    fp_set = set(fingerprints)

    # 1. Duplicate fingerprints
    seen: set[str] = set()
    dupes: set[str] = set()
    for fp in fingerprints:
        if fp in seen:
            dupes.add(fp)
        seen.add(fp)
    for fp in sorted(dupes):
        blockers.append(
            WorkspaceBlocker(
                severity=WorkspaceBlockerSeverity.BLOCKER,
                code="duplicate_fingerprint",
                message=f"duplicate artifact fingerprint: {fp}",
                related_fingerprints=[fp],
            )
        )

    # 2. Duplicate singleton artifact roles
    kind_counts: dict[WorkspaceArtifactKind, list[str]] = {}
    for art in manifest.artifacts:
        if art.kind in SINGLETON_KINDS:
            kind_counts.setdefault(art.kind, []).append(art.fingerprint)
    for kind, fps in kind_counts.items():
        if len(fps) > 1:
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="duplicate_singleton",
                    message=(
                        f"duplicate singleton artifact role: {kind.value} appears "
                        f"{len(fps)} times; expected at most one"
                    ),
                    related_fingerprints=sorted(fps),
                )
            )

    # 3. Missing referenced parent fingerprints (dangling parent)
    for art in manifest.artifacts:
        if art.parent_fingerprint is not None and art.parent_fingerprint not in fp_set:
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="missing_parent",
                    message=(
                        f"artifact {art.fingerprint[:12]} ({art.kind.value}) "
                        f"references unknown parent {art.parent_fingerprint[:12]}"
                    ),
                    related_fingerprints=[art.fingerprint, art.parent_fingerprint],
                )
            )

    # 4. Incompatible schema versions
    for art in manifest.artifacts:
        allowed = KIND_SUPPORTED_VERSIONS.get(art.kind, SUPPORTED_SCHEMA_VERSIONS)
        if art.schema_version not in allowed:
            # Incompatible is a blocker; unknown version also blocker.
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="incompatible_schema_version",
                    message=(
                        f"artifact {art.fingerprint[:12]} ({art.kind.value}) "
                        f"has unsupported schema version {art.schema_version!r}; "
                        f"expected one of {sorted(allowed)}"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )
        elif art.compatibility_standing is WorkspaceCompatibilityStanding.INCOMPATIBLE:
            # Standing claims incompatible while version matches -> warning for consistency
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="standing_incompatible",
                    message=(
                        f"artifact {art.fingerprint[:12]} declares compatibility_standing "
                        f"incompatible but schema_version {art.schema_version!r} is supported"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )

    # 5. Plan/report fingerprint mismatches
    # If any report has a parent, parent should be a plan or contract-like artifact.
    # Also detect when multiple reports claim same wrong parent.
    plan_fps = {
        a.fingerprint
        for a in manifest.artifacts
        if a.kind is WorkspaceArtifactKind.PREREGISTRATION_PLAN
    }
    report_kinds = {
        WorkspaceArtifactKind.EVENT_ALIGNED_REPORT,
        WorkspaceArtifactKind.RESOURCE_STRATEGY_REPORT,
        WorkspaceArtifactKind.STATISTICAL_STUDY_REPORT,
        WorkspaceArtifactKind.GENERIC_REPORT,
    }
    for art in manifest.artifacts:
        if (
            art.kind in report_kinds
            and art.parent_fingerprint is not None
            and plan_fps
            and art.parent_fingerprint not in plan_fps
        ):
            # Find parent kind if present
            parent_kind = next(
                (
                    p.kind.value
                    for p in manifest.artifacts
                    if p.fingerprint == art.parent_fingerprint
                ),
                "unknown",
            )
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="plan_report_mismatch",
                    message=(
                        f"report {art.fingerprint[:12]} ({art.kind.value}) parent "
                        f"{art.parent_fingerprint[:12]} ({parent_kind}) is not the "
                        f"declared preregistration plan"
                    ),
                    related_fingerprints=[art.fingerprint, art.parent_fingerprint],
                )
            )

    # 6. Evidence references absent from the plan
    # Evidence attachments should reference a plan parent; if they do not, warn.
    evidence_artifacts = [
        a for a in manifest.artifacts if a.kind is WorkspaceArtifactKind.EVIDENCE_ATTACHMENT
    ]
    for art in evidence_artifacts:
        if art.parent_fingerprint is None:
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="evidence_without_plan_link",
                    message=(
                        f"evidence attachment {art.fingerprint[:12]} has no parent plan linkage; "
                        f"evidence references absent from plan cannot be verified"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )
        elif art.parent_fingerprint not in fp_set:
            # Already flagged as missing_parent, but also evidence-specific
            pass
        elif plan_fps and art.parent_fingerprint not in plan_fps:
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="evidence_plan_mismatch",
                    message=(
                        f"evidence {art.fingerprint[:12]} parent {art.parent_fingerprint[:12]} "
                        f"is not the preregistration plan"
                    ),
                    related_fingerprints=[art.fingerprint, art.parent_fingerprint],
                )
            )

    # 7. Capsule references to unknown artifacts
    capsule_artifacts = [
        a
        for a in manifest.artifacts
        if a.kind
        in {
            WorkspaceArtifactKind.STUDY_CAPSULE_MANIFEST,
            WorkspaceArtifactKind.STUDY_CAPSULE_RECEIPT,
        }
    ]
    for art in capsule_artifacts:
        if art.parent_fingerprint is not None and art.parent_fingerprint not in fp_set:
            # Already flagged missing_parent, but capsule-specific message
            # Avoid duplicate; the missing_parent blocker already covers this.
            pass
        # Additionally, if capsule claims compatibility blocked but still available, warn.
        if (
            art.compatibility_standing is WorkspaceCompatibilityStanding.BLOCKED
            and art.availability.value == "available"
        ):
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="capsule_blocked_but_available",
                    message=(
                        f"capsule {art.fingerprint[:12]} declares blocked compatibility "
                        f"but availability is available"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )

    # 8. Contradictory lifecycle claims
    derived = _derive_stage_internal(manifest, blockers)
    if manifest.declared_stage is not None and manifest.declared_stage != derived:
        # If derived is BLOCKED, declared != BLOCKED => contradictory
        # Otherwise any mismatch is contradictory
        blockers.append(
            WorkspaceBlocker(
                severity=WorkspaceBlockerSeverity.BLOCKER,
                code="contradictory_lifecycle",
                message=(
                    f"declared stage {manifest.declared_stage.value} contradicts "
                    f"derived stage {derived.value} from artifact standings"
                ),
                related_fingerprints=[],
            )
        )

    # Additional contradictory standing: if two artifacts share same kind+label but different standing
    label_kind_map: dict[tuple[str, str], set[str]] = {}
    for art in manifest.artifacts:
        key = (art.kind.value, art.label)
        label_kind_map.setdefault(key, set()).add(art.standing.value)
    for (kind_val, label), standings in label_kind_map.items():
        if len(standings) > 1:
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="contradictory_standing",
                    message=(
                        f"artifacts with kind {kind_val!r} and label {label!r} carry "
                        f"contradictory standings {sorted(standings)}"
                    ),
                    related_fingerprints=[
                        a.fingerprint
                        for a in manifest.artifacts
                        if a.kind.value == kind_val and a.label == label
                    ],
                )
            )

    # Availability coherence: blockers make derived blocked, but also check local path in reason/label
    for art in manifest.artifacts:
        if art.reason is not None and _contains_absolute_path(art.reason):
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="local_path_in_reason",
                    message=f"artifact {art.fingerprint[:12]} reason contains absolute local path",
                    related_fingerprints=[art.fingerprint],
                )
            )
        if _contains_absolute_path(art.label):
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="local_path_in_label",
                    message=f"artifact {art.fingerprint[:12]} label contains absolute local path",
                    related_fingerprints=[art.fingerprint],
                )
            )

    is_valid = len(blockers) == 0
    # Fingerprint of manifest for this validation (deterministic)
    fp = fingerprint_manifest(manifest)
    # Derived stage is BLOCKED if blockers exist, else internal derivation
    final_stage = WorkspaceLifecycleStage.BLOCKED if blockers else derived
    return WorkspaceValidationReport(
        is_valid=is_valid,
        blockers=blockers,
        warnings=warnings,
        derived_stage=final_stage,
        fingerprint=fp,
    )


# ---------------------------------------------------------------------------
# Lifecycle derivation (descriptive only from explicit standings)
# ---------------------------------------------------------------------------


def _derive_stage_internal(
    manifest: StudyWorkspaceManifest, blockers: list[WorkspaceBlocker] | None = None
) -> WorkspaceLifecycleStage:
    """Infer descriptive stage only from explicit artifact standings."""

    if blockers and any(b.code in {"duplicate_fingerprint", "missing_parent"} for b in blockers):
        return WorkspaceLifecycleStage.BLOCKED

    kinds_present = {a.kind for a in manifest.artifacts}

    has_plan = WorkspaceArtifactKind.PREREGISTRATION_PLAN in kinds_present
    has_contract = (
        WorkspaceArtifactKind.SOURCE_CONTRACT in kinds_present
        or WorkspaceArtifactKind.SOURCE_CONTRACT_VERSION in kinds_present
    )
    has_evidence = WorkspaceArtifactKind.EVIDENCE_ATTACHMENT in kinds_present
    has_event_report = WorkspaceArtifactKind.EVENT_ALIGNED_REPORT in kinds_present
    has_resource_report = WorkspaceArtifactKind.RESOURCE_STRATEGY_REPORT in kinds_present
    has_study_report = WorkspaceArtifactKind.STATISTICAL_STUDY_REPORT in kinds_present
    has_capsule = WorkspaceArtifactKind.STUDY_CAPSULE_MANIFEST in kinds_present

    # No artifacts -> draft
    if not manifest.artifacts:
        return WorkspaceLifecycleStage.DRAFT

    # Archived is explicit only via declared stage; we don't infer archived from standings alone.
    # If no plan and no contract -> draft
    if not has_plan and not has_contract:
        return WorkspaceLifecycleStage.DRAFT

    # Contracted: has contract but no plan
    if has_contract and not has_plan:
        return WorkspaceLifecycleStage.CONTRACTED

    # Preregistered: has plan, no evidence, no reports
    if (
        has_plan
        and not has_evidence
        and not has_event_report
        and not has_resource_report
        and not has_study_report
    ):
        return WorkspaceLifecycleStage.PREREGISTERED

    # Collecting: has plan + evidence attachments that are still pending/unavailable
    if has_plan and has_evidence:
        # If any evidence is unavailable or pending review, collecting
        evidence_unavailable = any(
            a.availability.value in {"unavailable", "pending_review"}
            for a in manifest.artifacts
            if a.kind is WorkspaceArtifactKind.EVIDENCE_ATTACHMENT
        )
        if evidence_unavailable:
            return WorkspaceLifecycleStage.COLLECTING
        # If evidence exists and is available but no reports yet -> evidence_review
        if not has_event_report and not has_resource_report and not has_study_report:
            return WorkspaceLifecycleStage.EVIDENCE_REVIEW

    # Analysis stages
    if has_plan and has_evidence:
        has_any_report = has_event_report or has_resource_report or has_study_report
        if has_any_report:
            # Check if reports are available vs pending
            reports_available = any(
                a.availability.value == "available"
                for a in manifest.artifacts
                if a.kind
                in {
                    WorkspaceArtifactKind.EVENT_ALIGNED_REPORT,
                    WorkspaceArtifactKind.RESOURCE_STRATEGY_REPORT,
                    WorkspaceArtifactKind.STATISTICAL_STUDY_REPORT,
                }
            )
            if reports_available:
                # If all reports are available, analysis_complete, otherwise analysis_ready
                all_reports_available = all(
                    a.availability.value == "available"
                    for a in manifest.artifacts
                    if a.kind
                    in {
                        WorkspaceArtifactKind.EVENT_ALIGNED_REPORT,
                        WorkspaceArtifactKind.RESOURCE_STRATEGY_REPORT,
                        WorkspaceArtifactKind.STATISTICAL_STUDY_REPORT,
                    }
                )
                if all_reports_available:
                    if has_capsule:
                        return WorkspaceLifecycleStage.REVIEW_READY
                    return WorkspaceLifecycleStage.ANALYSIS_COMPLETE
                return WorkspaceLifecycleStage.ANALYSIS_READY
            return WorkspaceLifecycleStage.ANALYSIS_READY

    # If we have a capsule with review ready conditions, else collecting etc.
    if has_capsule:
        return WorkspaceLifecycleStage.REVIEW_READY

    # Fallback
    return WorkspaceLifecycleStage.DRAFT


def derive_lifecycle_stage(manifest: StudyWorkspaceManifest) -> WorkspaceLifecycleStage:
    """Public descriptive lifecycle inference (no mutation, no approval)."""
    report = validate_workspace(manifest)
    return report.derived_stage


# ---------------------------------------------------------------------------
# Next-action engine (guidance records only, never invokes services)
# ---------------------------------------------------------------------------


def next_actions(
    manifest: StudyWorkspaceManifest, validation: WorkspaceValidationReport | None = None
) -> list[WorkspaceAction]:
    """Produce typed, non-executable next actions from manifest and validation."""
    if validation is None:
        validation = validate_workspace(manifest)

    actions: list[WorkspaceAction] = []

    # If blockers exist, surface fixing those first
    blocker_codes = {b.code for b in validation.blockers}
    if "duplicate_fingerprint" in blocker_codes:
        actions.append(
            WorkspaceAction(
                action="resolve_duplicate_fingerprints",
                label="Resolve duplicate fingerprints",
                description="Remove or replace artifacts sharing the same fingerprint; each reference must be unique.",
                priority=1,
                related_fingerprints=[],
            )
        )
    if "duplicate_singleton" in blocker_codes:
        dup_single = [b for b in validation.blockers if b.code == "duplicate_singleton"]
        fps_dup: list[str] = []
        for b in dup_single:
            fps_dup.extend(b.related_fingerprints)
        actions.append(
            WorkspaceAction(
                action="resolve_duplicate_singleton",
                label="Resolve duplicate singleton artifact role",
                description="Only one artifact of this singleton kind may exist; keep the authoritative version and remove the duplicate.",
                priority=1,
                related_fingerprints=sorted(set(fps_dup)),
            )
        )
    if "missing_parent" in blocker_codes:
        missing = [b for b in validation.blockers if b.code == "missing_parent"]
        fps_missing: list[str] = []
        for b in missing:
            fps_missing.extend(b.related_fingerprints)
        actions.append(
            WorkspaceAction(
                action="resolve_missing_parent",
                label="Resolve missing parent fingerprints",
                description="Add the missing parent artifact or correct the parent_fingerprint linkage.",
                priority=1,
                related_fingerprints=sorted(set(fps_missing)),
            )
        )
    if "incompatible_schema_version" in blocker_codes:
        inc = [b for b in validation.blockers if b.code == "incompatible_schema_version"]
        fps_inc: list[str] = []
        for b in inc:
            fps_inc.extend(b.related_fingerprints)
        actions.append(
            WorkspaceAction(
                action="resolve_incompatible_schema",
                label="Resolve incompatible schema versions",
                description="Update or replace artifacts with unsupported schema versions, or add a compatible adapter.",
                priority=2,
                related_fingerprints=sorted(set(fps_inc)),
            )
        )
    if "contradictory_lifecycle" in blocker_codes:
        actions.append(
            WorkspaceAction(
                action="correct_declared_stage",
                label="Correct declared lifecycle stage",
                description="Declared stage contradicts derived stage from artifact standings; update declaration to match evidence or add required artifacts.",
                priority=2,
                related_fingerprints=[],
            )
        )

    # If still blocked, stop here and offer inspect provenance guidance
    if validation.blockers:
        actions.append(
            WorkspaceAction(
                action="inspect_provenance",
                label="Inspect provenance",
                description="Open the provenance view to trace artifact lineage and blockers.",
                priority=10,
                related_fingerprints=[],
            )
        )
        return sorted(actions, key=lambda a: a.priority)

    # No blockers: guidance based on lifecycle
    stage = validation.derived_stage
    kinds = {a.kind for a in manifest.artifacts}

    if stage is WorkspaceLifecycleStage.DRAFT:
        if WorkspaceArtifactKind.SOURCE_CONTRACT not in kinds:
            actions.append(
                WorkspaceAction(
                    action="add_or_validate_source_contract",
                    label="Add or validate a source contract",
                    description="Author and freeze a source data contract before collecting evidence.",
                    priority=3,
                    related_fingerprints=[],
                )
            )
        else:
            actions.append(
                WorkspaceAction(
                    action="freeze_preregistration_plan",
                    label="Freeze a preregistration plan",
                    description="Freeze the preregistration plan to establish the scientific commitment before evidence collection.",
                    priority=3,
                    related_fingerprints=[],
                )
            )

    if stage is WorkspaceLifecycleStage.CONTRACTED:
        actions.append(
            WorkspaceAction(
                action="freeze_preregistration_plan",
                label="Freeze a preregistration plan",
                description="Freeze the preregistration plan; a frozen plan is immutable and carries a parent fingerprint.",
                priority=3,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.PREREGISTERED:
        actions.append(
            WorkspaceAction(
                action="collect_evidence",
                label="Collect evidence for preregistered cells",
                description="Collect evidence artifacts matching the preregistered run matrix cells.",
                priority=4,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.COLLECTING:
        actions.append(
            WorkspaceAction(
                action="review_pending_evidence",
                label="Review pending evidence",
                description="Review evidence attachments that are still unavailable or pending; do not zero-fill missing evidence.",
                priority=4,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.EVIDENCE_REVIEW:
        # Check for incompatible evidence
        has_incompatible = any(
            a.compatibility_standing is WorkspaceCompatibilityStanding.INCOMPATIBLE
            for a in manifest.artifacts
        )
        if has_incompatible:
            actions.append(
                WorkspaceAction(
                    action="resolve_incompatible_evidence",
                    label="Resolve incompatible evidence",
                    description="Replace or reconcile evidence marked incompatible before analysis.",
                    priority=4,
                    related_fingerprints=[
                        a.fingerprint
                        for a in manifest.artifacts
                        if a.compatibility_standing is WorkspaceCompatibilityStanding.INCOMPATIBLE
                    ],
                )
            )
        else:
            actions.append(
                WorkspaceAction(
                    action="review_pending_evidence",
                    label="Review pending evidence",
                    description="Complete evidence review; all referenced evidence must be admitted or explicitly marked synthetic/unadmitted.",
                    priority=4,
                    related_fingerprints=[],
                )
            )

    if stage in {WorkspaceLifecycleStage.EVIDENCE_REVIEW, WorkspaceLifecycleStage.ANALYSIS_READY}:
        actions.append(
            WorkspaceAction(
                action="run_supported_analysis",
                label="Run an already-supported analysis manually",
                description="Manually run a supported analysis (event-aligned, resource strategy, or statistical study) outside the workspace; link the resulting report fingerprint back.",
                priority=5,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.ANALYSIS_COMPLETE:
        actions.append(
            WorkspaceAction(
                action="prepare_study_capsule",
                label="Prepare a Study Capsule",
                description="Assemble a Study Capsule referencing the validated reports for offline review; do not claim production readiness.",
                priority=6,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.REVIEW_READY:
        actions.append(
            WorkspaceAction(
                action="inspect_provenance",
                label="Inspect provenance",
                description="Inspect provenance traces for all bound artifacts before archiving.",
                priority=7,
                related_fingerprints=[],
            )
        )
        actions.append(
            WorkspaceAction(
                action="archive_workspace",
                label="Archive workspace",
                description="Archive the workspace when review is complete; archived workspaces remain immutable references.",
                priority=8,
                related_fingerprints=[],
            )
        )

    # Always offer provenance inspection as non-blocking guidance when valid
    if not any(a.action == "inspect_provenance" for a in actions):
        actions.append(
            WorkspaceAction(
                action="inspect_provenance",
                label="Inspect provenance",
                description="Inspect provenance for any bound artifact to verify derivation without claiming causality.",
                priority=20,
                related_fingerprints=[],
            )
        )

    return sorted(actions, key=lambda a: a.priority)
