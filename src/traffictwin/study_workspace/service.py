"""Deterministic service for validation, lifecycle derivation, fingerprinting
and guidance. Business logic lives outside Streamlit.
"""

from __future__ import annotations

from typing import Any

from traffictwin.study_workspace.models import (
    KIND_SUPPORTED_VERSIONS,
    SINGLETON_KINDS,
    SUPPORTED_SCHEMA_VERSIONS,
    StudyWorkspaceManifest,
    WorkspaceAction,
    WorkspaceArtifactKind,
    WorkspaceArtifactStanding,
    WorkspaceAvailabilityState,
    WorkspaceBlocker,
    WorkspaceBlockerSeverity,
    WorkspaceCompatibilityStanding,
    WorkspaceLifecycleStage,
    WorkspaceValidationReport,
)


def fingerprint_manifest(manifest: StudyWorkspaceManifest) -> str:
    """Return stable SHA-256 fingerprint for one manifest."""
    return manifest.fingerprint()


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

EVIDENCE_LIKE_STANDINGS: frozenset[WorkspaceArtifactStanding] = frozenset(
    {
        WorkspaceArtifactStanding.SYNTHETIC_EVIDENCE,
        WorkspaceArtifactStanding.IMPORTED_EVIDENCE,
        WorkspaceArtifactStanding.HISTORICAL_OBSERVATION,
        WorkspaceArtifactStanding.NEAR_LIVE_OPERATIONAL,
        WorkspaceArtifactStanding.ADMITTED_RESEARCH,
        WorkspaceArtifactStanding.UNADMITTED_RESEARCH,
    }
)

REPORT_KINDS: frozenset[WorkspaceArtifactKind] = frozenset(
    {
        WorkspaceArtifactKind.EVENT_ALIGNED_REPORT,
        WorkspaceArtifactKind.RESOURCE_STRATEGY_REPORT,
        WorkspaceArtifactKind.STATISTICAL_STUDY_REPORT,
    }
)

CAPSULE_KINDS: frozenset[WorkspaceArtifactKind] = frozenset(
    {
        WorkspaceArtifactKind.STUDY_CAPSULE_MANIFEST,
        WorkspaceArtifactKind.STUDY_CAPSULE_RECEIPT,
        WorkspaceArtifactKind.RESEARCH_OBJECT_MANIFEST,
    }
)

EVIDENCE_UNRESOLVED: frozenset[WorkspaceAvailabilityState] = frozenset(
    {
        WorkspaceAvailabilityState.PENDING_REVIEW,
        WorkspaceAvailabilityState.UNAVAILABLE,
        WorkspaceAvailabilityState.PARTIAL,
    }
)

COMPATIBILITY_BLOCKERS: frozenset[WorkspaceCompatibilityStanding] = frozenset(
    {
        WorkspaceCompatibilityStanding.INCOMPATIBLE,
        WorkspaceCompatibilityStanding.BLOCKED,
        WorkspaceCompatibilityStanding.REVIEW_REQUIRED,
    }
)


def _is_evidence_like(ref: Any) -> bool:  # noqa: ANN401
    return ref.standing in EVIDENCE_LIKE_STANDINGS


def _has_evidence_like(manifest: StudyWorkspaceManifest) -> bool:
    return any(_is_evidence_like(a) for a in manifest.artifacts)


def _evidence_like_refs(manifest: StudyWorkspaceManifest) -> list[Any]:
    return [a for a in manifest.artifacts if _is_evidence_like(a)]


def _report_refs(manifest: StudyWorkspaceManifest) -> list[Any]:
    return [a for a in manifest.artifacts if a.kind in REPORT_KINDS]


def _capsule_refs(manifest: StudyWorkspaceManifest) -> list[Any]:
    return [a for a in manifest.artifacts if a.kind in CAPSULE_KINDS]


def _has_unresolved_evidence(manifest: StudyWorkspaceManifest) -> bool:
    return any(a.availability in EVIDENCE_UNRESOLVED for a in _evidence_like_refs(manifest))


def _has_invalid_evidence(manifest: StudyWorkspaceManifest) -> bool:
    return any(
        a.availability is WorkspaceAvailabilityState.INVALID for a in _evidence_like_refs(manifest)
    )


def _has_usable_capsule(manifest: StudyWorkspaceManifest) -> bool:
    for art in _capsule_refs(manifest):
        if art.availability is not WorkspaceAvailabilityState.AVAILABLE:
            continue
        if art.compatibility_standing in COMPATIBILITY_BLOCKERS:
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_workspace(manifest: StudyWorkspaceManifest) -> WorkspaceValidationReport:
    """Validate one manifest and produce exact blockers and warnings."""
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
                        f"duplicate singleton artifact role: {kind.value} "
                        f"appears {len(fps)} times; expected at most one"
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
                        f"references unknown parent "
                        f"{art.parent_fingerprint[:12]}"
                    ),
                    related_fingerprints=[
                        art.fingerprint,
                        art.parent_fingerprint,
                    ],
                )
            )

    # 4. Incompatible schema versions
    for art in manifest.artifacts:
        allowed = KIND_SUPPORTED_VERSIONS.get(art.kind, SUPPORTED_SCHEMA_VERSIONS)
        if art.schema_version not in allowed:
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="incompatible_schema_version",
                    message=(
                        f"artifact {art.fingerprint[:12]} ({art.kind.value}) "
                        f"has unsupported schema version "
                        f"{art.schema_version!r}; expected one of "
                        f"{sorted(allowed)}"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )
        elif art.compatibility_standing is WorkspaceCompatibilityStanding.INCOMPATIBLE:
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="standing_incompatible",
                    message=(
                        f"artifact {art.fingerprint[:12]} declares "
                        f"compatibility_standing incompatible but "
                        f"schema_version {art.schema_version!r} is supported"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )

    # 4b. Evidence INVALID is hard blocker
    for art in _evidence_like_refs(manifest):
        if art.availability is WorkspaceAvailabilityState.INVALID:
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="availability_invalid",
                    message=(
                        f"evidence {art.fingerprint[:12]} ({art.kind.value}) "
                        f"has availability INVALID; unresolved evidence "
                        f"must be resolved before progression"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )

    # 4c. Compatibility fail-closed for lifecycle participants
    for art in manifest.artifacts:
        participates = art.kind in REPORT_KINDS or art.kind in CAPSULE_KINDS
        if not participates:
            continue
        if art.compatibility_standing is WorkspaceCompatibilityStanding.INCOMPATIBLE:
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="compatibility_incompatible",
                    message=(
                        f"artifact {art.fingerprint[:12]} ({art.kind.value}) "
                        f"declares compatibility INCOMPATIBLE"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )
        elif art.compatibility_standing is WorkspaceCompatibilityStanding.BLOCKED:
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="compatibility_blocked",
                    message=(
                        f"artifact {art.fingerprint[:12]} ({art.kind.value}) "
                        f"declares compatibility BLOCKED"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )
        elif art.compatibility_standing is WorkspaceCompatibilityStanding.REVIEW_REQUIRED:
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="compatibility_review_required",
                    message=(
                        f"artifact {art.fingerprint[:12]} ({art.kind.value}) "
                        f"declares compatibility REVIEW_REQUIRED"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )

    # 5. Plan/report fingerprint mismatches
    plan_fps = {
        a.fingerprint
        for a in manifest.artifacts
        if a.kind is WorkspaceArtifactKind.PREREGISTRATION_PLAN
    }
    for art in manifest.artifacts:
        if (
            art.kind in REPORT_KINDS
            and art.parent_fingerprint is not None
            and plan_fps
            and art.parent_fingerprint not in plan_fps
        ):
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
                        f"report {art.fingerprint[:12]} ({art.kind.value}) "
                        f"parent {art.parent_fingerprint[:12]} ({parent_kind}) "
                        f"is not the declared preregistration plan"
                    ),
                    related_fingerprints=[
                        art.fingerprint,
                        art.parent_fingerprint,
                    ],
                )
            )

    # 6. Evidence references absent from the plan
    evidence_like = _evidence_like_refs(manifest)
    for art in evidence_like:
        if art.parent_fingerprint is None:
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="evidence_without_plan_link",
                    message=(
                        f"evidence {art.fingerprint[:12]} ({art.kind.value}) "
                        f"has no parent plan linkage; evidence references "
                        f"absent from plan cannot be verified"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )
        elif plan_fps and art.parent_fingerprint not in plan_fps:
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="evidence_plan_mismatch",
                    message=(
                        f"evidence {art.fingerprint[:12]} parent "
                        f"{art.parent_fingerprint[:12]} is not the "
                        f"preregistration plan"
                    ),
                    related_fingerprints=[
                        art.fingerprint,
                        art.parent_fingerprint,
                    ],
                )
            )

    # 7. Capsule blocked but available warning (now also blocker above)
    for art in _capsule_refs(manifest):
        if (
            art.compatibility_standing is WorkspaceCompatibilityStanding.BLOCKED
            and art.availability == WorkspaceAvailabilityState.AVAILABLE
        ):
            warnings.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.WARNING,
                    code="capsule_blocked_but_available",
                    message=(
                        f"capsule {art.fingerprint[:12]} declares blocked "
                        f"compatibility but availability is available"
                    ),
                    related_fingerprints=[art.fingerprint],
                )
            )

    # 8. Derive underlying stage without trusting declared_stage
    underlying = _derive_stage_internal(manifest, blockers)

    # 9. Handle explicit ARCHIVED governance state
    derived: WorkspaceLifecycleStage
    if manifest.declared_stage is WorkspaceLifecycleStage.ARCHIVED:
        if underlying is WorkspaceLifecycleStage.REVIEW_READY:
            derived = WorkspaceLifecycleStage.ARCHIVED
        else:
            blockers.append(
                WorkspaceBlocker(
                    severity=WorkspaceBlockerSeverity.BLOCKER,
                    code="contradictory_lifecycle",
                    message=(
                        f"declared stage archived contradicts derived stage "
                        f"{underlying.value} from artifact standings; only "
                        f"review-ready workspaces may be archived"
                    ),
                    related_fingerprints=[],
                )
            )
            derived = WorkspaceLifecycleStage.BLOCKED
    elif manifest.declared_stage is not None and manifest.declared_stage != underlying:
        blockers.append(
            WorkspaceBlocker(
                severity=WorkspaceBlockerSeverity.BLOCKER,
                code="contradictory_lifecycle",
                message=(
                    f"declared stage {manifest.declared_stage.value} "
                    f"contradicts derived stage {underlying.value} "
                    f"from artifact standings"
                ),
                related_fingerprints=[],
            )
        )
        derived = WorkspaceLifecycleStage.BLOCKED
    else:
        derived = underlying
        if blockers:
            derived = WorkspaceLifecycleStage.BLOCKED

    # Additional contradictory standing: same kind+label different standing
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
                        f"artifacts with kind {kind_val!r} and label {label!r} "
                        f"carry contradictory standings {sorted(standings)}"
                    ),
                    related_fingerprints=[
                        a.fingerprint
                        for a in manifest.artifacts
                        if a.kind.value == kind_val and a.label == label
                    ],
                )
            )

    is_valid = len(blockers) == 0
    fp = fingerprint_manifest(manifest)
    final_stage = WorkspaceLifecycleStage.BLOCKED if not is_valid else derived

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
    manifest: StudyWorkspaceManifest,
    blockers: list[WorkspaceBlocker] | None = None,
) -> WorkspaceLifecycleStage:
    """Infer descriptive stage only from explicit artifact standings."""
    if blockers and any(
        b.code
        in {
            "duplicate_fingerprint",
            "missing_parent",
            "availability_invalid",
            "compatibility_incompatible",
            "compatibility_blocked",
            "compatibility_review_required",
        }
        for b in blockers
    ):
        return WorkspaceLifecycleStage.BLOCKED

    kinds_present = {a.kind for a in manifest.artifacts}
    has_plan = WorkspaceArtifactKind.PREREGISTRATION_PLAN in kinds_present
    has_contract = (
        WorkspaceArtifactKind.SOURCE_CONTRACT in kinds_present
        or WorkspaceArtifactKind.SOURCE_CONTRACT_VERSION in kinds_present
    )
    has_report = bool(_report_refs(manifest))

    if not manifest.artifacts:
        return WorkspaceLifecycleStage.DRAFT

    if not has_plan and not has_contract:
        return WorkspaceLifecycleStage.DRAFT

    # Contract but no plan -> contracted
    if has_contract and not has_plan:
        return WorkspaceLifecycleStage.CONTRACTED

    # Plan, no evidence-like, no report -> preregistered
    if has_plan and not _has_evidence_like(manifest) and not has_report:
        return WorkspaceLifecycleStage.PREREGISTERED

    # Plan + evidence-like, no report -> collecting or evidence_review
    if has_plan and _has_evidence_like(manifest) and not has_report:
        evidence_unavailable = any(
            a.availability in EVIDENCE_UNRESOLVED
            or a.availability is WorkspaceAvailabilityState.INVALID
            for a in _evidence_like_refs(manifest)
        )
        if evidence_unavailable:
            return WorkspaceLifecycleStage.COLLECTING
        return WorkspaceLifecycleStage.EVIDENCE_REVIEW

    # Plan + report(s) -> analysis stages
    if has_plan and has_report:
        report_artifacts = _report_refs(manifest)
        # Reports must be AVAILABLE and not blocked by compatibility
        all_reports_usable = all(
            a.availability is WorkspaceAvailabilityState.AVAILABLE
            and a.compatibility_standing not in COMPATIBILITY_BLOCKERS
            for a in report_artifacts
        )
        if not all_reports_usable:
            return WorkspaceLifecycleStage.ANALYSIS_READY
        # Evidence availability gates progression
        if _has_invalid_evidence(manifest):
            return WorkspaceLifecycleStage.BLOCKED
        if _has_unresolved_evidence(manifest):
            return WorkspaceLifecycleStage.ANALYSIS_READY
        # Capsule usable gates REVIEW_READY
        if _has_usable_capsule(manifest):
            return WorkspaceLifecycleStage.REVIEW_READY
        return WorkspaceLifecycleStage.ANALYSIS_COMPLETE

    return WorkspaceLifecycleStage.DRAFT


def derive_lifecycle_stage(manifest: StudyWorkspaceManifest) -> WorkspaceLifecycleStage:
    """Public descriptive lifecycle inference (no mutation, no approval)."""
    report = validate_workspace(manifest)
    return report.derived_stage


# ---------------------------------------------------------------------------
# Next-action engine (guidance records only, never invokes services)
# ---------------------------------------------------------------------------


def next_actions(
    manifest: StudyWorkspaceManifest,
    validation: WorkspaceValidationReport | None = None,
) -> list[WorkspaceAction]:
    """Produce typed, non-executable next actions."""
    if validation is None:
        validation = validate_workspace(manifest)

    actions: list[WorkspaceAction] = []

    blocker_codes = {b.code for b in validation.blockers}
    if "duplicate_fingerprint" in blocker_codes:
        actions.append(
            WorkspaceAction(
                action="resolve_duplicate_fingerprints",
                label="Resolve duplicate fingerprints",
                description=(
                    "Remove or replace artifacts sharing the same fingerprint; "
                    "each reference must be unique."
                ),
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
                description=(
                    "Only one artifact of this singleton kind may exist; "
                    "keep the authoritative version and remove the duplicate."
                ),
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
                description=(
                    "Add the missing parent artifact or correct the parent_fingerprint linkage."
                ),
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
                description=(
                    "Update or replace artifacts with unsupported schema versions, "
                    "or add a compatible adapter."
                ),
                priority=2,
                related_fingerprints=sorted(set(fps_inc)),
            )
        )
    if "availability_invalid" in blocker_codes:
        actions.append(
            WorkspaceAction(
                action="resolve_invalid_evidence",
                label="Resolve invalid evidence",
                description=(
                    "Evidence marked INVALID must be repaired or removed before "
                    "progression; invalid evidence blocks analysis completion."
                ),
                priority=1,
                related_fingerprints=[],
            )
        )
    if "compatibility_incompatible" in blocker_codes:
        actions.append(
            WorkspaceAction(
                action="resolve_compatibility_incompatible",
                label="Resolve incompatible compatibility",
                description=(
                    "An artifact declares compatibility INCOMPATIBLE; "
                    "resolve compatibility before advancing."
                ),
                priority=1,
                related_fingerprints=[],
            )
        )
    if "compatibility_blocked" in blocker_codes:
        actions.append(
            WorkspaceAction(
                action="resolve_compatibility_blocked",
                label="Resolve blocked compatibility",
                description=(
                    "An artifact declares compatibility BLOCKED; "
                    "unblock or replace it before advancing."
                ),
                priority=1,
                related_fingerprints=[],
            )
        )
    if "compatibility_review_required" in blocker_codes:
        actions.append(
            WorkspaceAction(
                action="resolve_compatibility_review",
                label="Resolve review-required compatibility",
                description=(
                    "An artifact requires compatibility review; complete review before advancing."
                ),
                priority=2,
                related_fingerprints=[],
            )
        )
    if "contradictory_lifecycle" in blocker_codes:
        actions.append(
            WorkspaceAction(
                action="correct_declared_stage",
                label="Correct declared lifecycle stage",
                description=(
                    "Declared stage contradicts derived stage from artifact "
                    "standings; update declaration to match evidence or add "
                    "required artifacts."
                ),
                priority=2,
                related_fingerprints=[],
            )
        )

    if validation.blockers:
        actions.append(
            WorkspaceAction(
                action="inspect_provenance",
                label="Inspect provenance",
                description=("Open the provenance view to trace artifact lineage and blockers."),
                priority=10,
                related_fingerprints=[],
            )
        )
        return sorted(actions, key=lambda a: a.priority)

    stage = validation.derived_stage
    kinds = {a.kind for a in manifest.artifacts}

    if stage is WorkspaceLifecycleStage.ARCHIVED:
        actions.append(
            WorkspaceAction(
                action="inspect_provenance",
                label="Inspect provenance",
                description=(
                    "Inspect provenance for any bound artifact to verify "
                    "derivation without claiming causality."
                ),
                priority=20,
                related_fingerprints=[],
            )
        )
        return sorted(actions, key=lambda a: a.priority)

    if stage is WorkspaceLifecycleStage.DRAFT:
        if (
            WorkspaceArtifactKind.SOURCE_CONTRACT not in kinds
            and WorkspaceArtifactKind.SOURCE_CONTRACT_VERSION not in kinds
        ):
            actions.append(
                WorkspaceAction(
                    action="add_or_validate_source_contract",
                    label="Add or validate a source contract",
                    description=(
                        "Author and freeze a source data contract before collecting evidence."
                    ),
                    priority=3,
                    related_fingerprints=[],
                )
            )
        else:
            actions.append(
                WorkspaceAction(
                    action="freeze_preregistration_plan",
                    label="Freeze a preregistration plan",
                    description=(
                        "Freeze the preregistration plan to establish the "
                        "scientific commitment before evidence collection."
                    ),
                    priority=3,
                    related_fingerprints=[],
                )
            )

    if stage is WorkspaceLifecycleStage.CONTRACTED:
        actions.append(
            WorkspaceAction(
                action="freeze_preregistration_plan",
                label="Freeze a preregistration plan",
                description=(
                    "Freeze the preregistration plan; a frozen plan is immutable "
                    "and carries a parent fingerprint."
                ),
                priority=3,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.PREREGISTERED:
        actions.append(
            WorkspaceAction(
                action="collect_evidence",
                label="Collect evidence for preregistered cells",
                description=(
                    "Collect evidence artifacts matching the preregistered run matrix cells."
                ),
                priority=4,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.COLLECTING:
        actions.append(
            WorkspaceAction(
                action="review_pending_evidence",
                label="Review pending evidence",
                description=(
                    "Review evidence attachments that are still unavailable or "
                    "pending; do not zero-fill missing evidence."
                ),
                priority=4,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.EVIDENCE_REVIEW:
        has_incompatible = any(
            a.compatibility_standing is WorkspaceCompatibilityStanding.INCOMPATIBLE
            for a in manifest.artifacts
        )
        if has_incompatible:
            actions.append(
                WorkspaceAction(
                    action="resolve_incompatible_evidence",
                    label="Resolve incompatible evidence",
                    description=(
                        "Replace or reconcile evidence marked incompatible before analysis."
                    ),
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
                    description=(
                        "Complete evidence review; all referenced evidence must be "
                        "admitted or explicitly marked synthetic/unadmitted."
                    ),
                    priority=4,
                    related_fingerprints=[],
                )
            )

    if stage in {
        WorkspaceLifecycleStage.EVIDENCE_REVIEW,
        WorkspaceLifecycleStage.ANALYSIS_READY,
    }:
        actions.append(
            WorkspaceAction(
                action="run_supported_analysis",
                label="Run an already-supported analysis manually",
                description=(
                    "Manually run a supported analysis (event-aligned, resource "
                    "strategy, or statistical study) outside the workspace; link "
                    "the resulting report fingerprint back."
                ),
                priority=5,
                related_fingerprints=[],
            )
        )

    if stage is WorkspaceLifecycleStage.ANALYSIS_COMPLETE:
        actions.append(
            WorkspaceAction(
                action="prepare_study_capsule",
                label="Prepare a Study Capsule",
                description=(
                    "Assemble a Study Capsule referencing the validated reports for "
                    "offline review; do not claim production readiness."
                ),
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
                description=(
                    "Archive the workspace when review is complete; archived "
                    "workspaces remain immutable references."
                ),
                priority=8,
                related_fingerprints=[],
            )
        )

    if not any(a.action == "inspect_provenance" for a in actions):
        actions.append(
            WorkspaceAction(
                action="inspect_provenance",
                label="Inspect provenance",
                description=(
                    "Inspect provenance for any bound artifact to verify "
                    "derivation without claiming causality."
                ),
                priority=20,
                related_fingerprints=[],
            )
        )

    return sorted(actions, key=lambda a: a.priority)
