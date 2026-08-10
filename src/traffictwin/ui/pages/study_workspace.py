# ruff: noqa: E501
"""Study Workspace & Research Lifecycle Cockpit — thin UI over typed workspace services."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from traffictwin.study_workspace.exports import (
    export_artifacts_csv,
    export_lineage_csv,
    export_workspace_json,
    export_workspace_pretty_json,
)
from traffictwin.study_workspace.models import (
    StudyWorkspaceManifest,
    WorkspaceArtifactKind,
    WorkspaceArtifactRef,
    WorkspaceArtifactStanding,
    WorkspaceAvailabilityState,
    WorkspaceCompatibilityStanding,
    WorkspaceLifecycleStage,
)
from traffictwin.study_workspace.service import (
    fingerprint_manifest,
    next_actions,
    validate_workspace,
)
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import table_column_config

EVIDENCE_BOUNDARY = (
    "This workspace references and explains existing TrafficTwin research artifacts "
    "without copying or silently modifying them. It never admits evidence, freezes a plan, "
    "executes analysis, or promotes a baseline automatically. All descriptive lifecycle stages "
    "are inferred only from explicit artifact standings."
)

AUTHORITY_BOUNDARY = (
    "Evidence and authority standing are shown before any results. Synthetic evidence is never "
    "relabelled as observed; missing evidence is never zero-filled; descriptive differences "
    "never claim causality or optimality without a declared decision contract."
)


def _default_manifest() -> StudyWorkspaceManifest:
    # Provide a tiny synthetic example for empty-state guidance, not auto-loaded.
    # Use deterministic hard-coded fingerprints (no local hash recomputation in UI).
    example_fp = "a" * 64
    contract_fp = "b" * 64
    return StudyWorkspaceManifest(
        workspace_id="ws-demo-001",
        workspace_version="1.0",
        study_id="study-demo-001",
        study_title="Manchester What-If: Demand Surge",
        description="Synthetic workspace seed for local preview. Replace with your admitted manifest.",
        artifacts=[
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.SOURCE_CONTRACT,
                fingerprint=contract_fp,
                schema_version="1.0",
                label="source-contract-tasks",
                standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.PREREGISTRATION_PLAN,
                fingerprint=example_fp,
                schema_version="1.0",
                label="plan-demo-001",
                standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                parent_fingerprint=contract_fp,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
        ],
        limitations=[
            "synthetic demonstration only — no Manchester evidence claimed",
            "not production ready",
        ],
    )


def _load_manifest_from_path(path: Path) -> StudyWorkspaceManifest | str:
    if not path.exists():
        return f"Workspace manifest not found: {path}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Could not read workspace manifest: {exc}"
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data.pop("workspace_fingerprint", None)
        return StudyWorkspaceManifest.model_validate(data)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return f"Workspace manifest is invalid: {exc}"


def _load_manifest_from_upload(uploaded_text: str) -> StudyWorkspaceManifest | str:
    try:
        data = json.loads(uploaded_text)
        if isinstance(data, dict):
            data.pop("workspace_fingerprint", None)
        return StudyWorkspaceManifest.model_validate(data)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return f"Uploaded workspace JSON is invalid: {exc}"


def _badge_for_standing(standing: WorkspaceArtifactStanding) -> str:
    mapping = {
        WorkspaceArtifactStanding.SYNTHETIC_EVIDENCE: badge_markdown("synthetic"),
        WorkspaceArtifactStanding.IMPORTED_EVIDENCE: ":blue-badge[IMPORTED]",
        WorkspaceArtifactStanding.HISTORICAL_OBSERVATION: ":violet-badge[HISTORICAL]",
        WorkspaceArtifactStanding.ADMITTED_RESEARCH: ":green-badge[ADMITTED RESEARCH]",
        WorkspaceArtifactStanding.UNADMITTED_RESEARCH: ":red-badge[UNADMITTED]",
        WorkspaceArtifactStanding.AUTHORED_CONFIGURATION: ":gray-badge[AUTHORED]",
        WorkspaceArtifactStanding.STATIC_GEOGRAPHIC: ":gray-badge[STATIC]",
        WorkspaceArtifactStanding.UNAVAILABLE: ":red-badge[UNAVAILABLE]",
        WorkspaceArtifactStanding.NOT_APPLICABLE: ":gray-badge[N/A]",
        WorkspaceArtifactStanding.NEAR_LIVE_OPERATIONAL: ":blue-badge[NEAR-LIVE]",
    }
    return mapping.get(standing, f":gray-badge[{standing.value.upper()}]")


def _badge_for_compatibility(standing: WorkspaceCompatibilityStanding) -> str:
    mapping = {
        WorkspaceCompatibilityStanding.COMPATIBLE: ":green-badge[COMPATIBLE]",
        WorkspaceCompatibilityStanding.INCOMPATIBLE: ":red-badge[INCOMPATIBLE]",
        WorkspaceCompatibilityStanding.UNKNOWN: ":gray-badge[UNKNOWN]",
        WorkspaceCompatibilityStanding.REVIEW_REQUIRED: ":orange-badge[REVIEW]",
        WorkspaceCompatibilityStanding.NOT_APPLICABLE: ":gray-badge[N/A]",
        WorkspaceCompatibilityStanding.BLOCKED: ":red-badge[BLOCKED]",
    }
    return mapping.get(standing, f":gray-badge[{standing.value.upper()}]")


def _badge_for_availability(state: WorkspaceAvailabilityState) -> str:
    mapping = {
        WorkspaceAvailabilityState.AVAILABLE: ":green-badge[AVAILABLE]",
        WorkspaceAvailabilityState.UNAVAILABLE: ":red-badge[UNAVAILABLE]",
        WorkspaceAvailabilityState.PARTIAL: ":yellow-badge[PARTIAL]",
        WorkspaceAvailabilityState.INVALID: ":red-badge[INVALID]",
        WorkspaceAvailabilityState.PENDING_REVIEW: ":orange-badge[PENDING REVIEW]",
    }
    return mapping.get(state, f":gray-badge[{state.value.upper()}]")


def _badge_for_stage(stage: WorkspaceLifecycleStage) -> str:
    colors = {
        WorkspaceLifecycleStage.DRAFT: ":gray-badge[DRAFT]",
        WorkspaceLifecycleStage.CONTRACTED: ":blue-badge[CONTRACTED]",
        WorkspaceLifecycleStage.PREREGISTERED: ":blue-badge[PREREGISTERED]",
        WorkspaceLifecycleStage.COLLECTING: ":orange-badge[COLLECTING]",
        WorkspaceLifecycleStage.EVIDENCE_REVIEW: ":orange-badge[EVIDENCE REVIEW]",
        WorkspaceLifecycleStage.ANALYSIS_READY: ":yellow-badge[ANALYSIS READY]",
        WorkspaceLifecycleStage.ANALYSIS_COMPLETE: ":green-badge[ANALYSIS COMPLETE]",
        WorkspaceLifecycleStage.REVIEW_READY: ":green-badge[REVIEW READY]",
        WorkspaceLifecycleStage.ARCHIVED: ":violet-badge[ARCHIVED]",
        WorkspaceLifecycleStage.BLOCKED: ":red-badge[BLOCKED]",
    }
    return colors.get(stage, f":gray-badge[{stage.value.upper()}]")


def render(config: UiConfig) -> None:  # noqa: ARG001
    """Render the Study Workspace lifecycle cockpit."""
    # Authoritative H1 — use fallback header when enum not yet registered (isolated commits).
    target = getattr(UiPage, "STUDY_WORKSPACE", None)
    if target is not None:
        render_page_header(target)
    else:
        st.caption("TrafficTwin / Study Workspace")
        st.title("Study Workspace")

    # Evidence and authority boundary before any results (required by claim boundaries)
    st.warning(EVIDENCE_BOUNDARY)
    st.info(AUTHORITY_BOUNDARY)
    st.caption(
        "This page is the research-project front door. It explains which artifacts are present, "
        "their fingerprint, schema, and standing — it does not re-derive results or reinterpret evidence."
    )

    # ------------------------------------------------------------------
    # Manifest selection — upload or local path
    # ------------------------------------------------------------------
    st.subheader("1. Load a study workspace manifest")
    st.caption(
        "Provide a portable workspace manifest JSON (no local paths, no wall-clock in identity). "
        "Upload or enter a path; no payloads are stored inside the manifest — only fingerprint references."
    )

    default_path = Path("tests/fixtures/study_workspace/synthetic_workspace_v1.json")
    path_str = st.session_state.get("study_workspace_path", str(default_path))

    col_a, col_b = st.columns([3, 1])
    with col_a:
        new_path = st.text_input(
            "Workspace manifest path",
            value=str(path_str),
            help="Path to a validated workspace manifest JSON (portable, no local filesystem paths).",
            key="study_workspace_path_input",
        )
        if new_path != path_str:
            st.session_state["study_workspace_path"] = new_path
            st.session_state.pop("study_workspace_uploaded_text", None)

    with col_b:
        if st.button("Load synthetic fixture", key="study_workspace_load_fixture"):
            # Create or point at synthetic fixture if exists; otherwise build demo.
            st.session_state["study_workspace_path"] = str(default_path)
            st.session_state.pop("study_workspace_uploaded_text", None)
            st.rerun()

    uploaded = st.file_uploader(
        "Or upload a workspace manifest JSON",
        type=["json"],
        key="study_workspace_uploader",
    )
    uploaded_text: str | None = None
    if uploaded is not None:
        try:
            uploaded_text = uploaded.getvalue().decode("utf-8")
            st.session_state["study_workspace_uploaded_text"] = uploaded_text
            # Clear path-based selection to avoid confusion
            st.session_state["study_workspace_path"] = ""
        except Exception as exc:
            st.error(f"Could not read uploaded file: {exc}")
            return
    else:
        uploaded_text = st.session_state.get("study_workspace_uploaded_text")
        # Cast to proper type: session state may hold Any
        if uploaded_text is not None and not isinstance(uploaded_text, str):
            uploaded_text = str(uploaded_text)

    manifest: StudyWorkspaceManifest | None = None
    if uploaded_text:
        result = _load_manifest_from_upload(uploaded_text)
        if isinstance(result, str):
            st.error(result)
            return
        manifest = result
    else:
        current_path_str = st.session_state.get("study_workspace_path", "")
        if not current_path_str or not str(current_path_str).strip():
            # Empty state — guidance, not error
            st.info(
                "No workspace manifest selected. Enter a path to a validated workspace JSON or upload one. "
                "Use the synthetic fixture to explore the workflow, or provide your own admitted workspace."
            )
            with st.container(border=True):
                st.markdown("**Empty workspace — next actions**")
                st.caption(
                    "The workspace is the front door that lists every referenced artifact by fingerprint. "
                    "Example synthetic manifest shows a source contract and a preregistration plan."
                )
                demo = _default_manifest()
                st.json(demo.model_dump(mode="json"))
                st.download_button(
                    "Download example workspace JSON",
                    data=export_workspace_pretty_json(demo),
                    file_name="example_workspace.json",
                    mime="application/json",
                    key="study_workspace_download_example",
                )
            return

        result2 = _load_manifest_from_path(Path(str(current_path_str)))
        if isinstance(result2, str):
            if "not found" in result2.lower():
                st.info(
                    "No admitted workspace exists at the selected path. The page has a useful empty state when no admitted workspace exists. "
                    "Provide a validated workspace manifest or switch to the synthetic fixture."
                )
                # Show empty-state example anyway
                demo2 = _default_manifest()
                st.json(demo2.model_dump(mode="json"))
            else:
                st.error(result2)
            return
        manifest = result2

    if manifest is None:
        st.error("Unable to load workspace manifest.")
        return

    # ------------------------------------------------------------------
    # Study identity banner (typed service output, no recomputation)
    # ------------------------------------------------------------------
    st.subheader("2. Study identity")
    validation = validate_workspace(manifest)
    fp = fingerprint_manifest(manifest)
    derived_stage = validation.derived_stage

    with st.container(border=True):
        id_cols = st.columns(4)
        id_cols[0].metric("Study", manifest.study_id)
        id_cols[1].metric("Workspace", manifest.workspace_id)
        id_cols[2].metric("Version", manifest.workspace_version)
        id_cols[3].metric("Artifacts", str(len(manifest.artifacts)))
        st.caption(f"Workspace fingerprint: `{fp}`")
        st.caption(
            f"Derived lifecycle stage: {derived_stage.value}  {_badge_for_stage(derived_stage)}"
        )
        if manifest.study_title:
            st.markdown(f"**Title:** {manifest.study_title}")
        if manifest.description:
            st.caption(manifest.description)
        if manifest.limitations:
            st.markdown("**Limitations**")
            for lim in manifest.limitations:
                st.markdown(f"- {lim}")

    # Evidence / authority standing before results (again, before inventory)
    st.caption(
        "Standing and availability below describe what is actually referenced, not what is desired. "
        "Unavailable remains unavailable; synthetic and imported are never relabelled as admitted."
    )

    # ------------------------------------------------------------------
    # Lifecycle stage panel
    # ------------------------------------------------------------------
    st.subheader("3. Lifecycle stage")
    with st.container(border=True):
        st.markdown(f"{_badge_for_stage(derived_stage)} **{derived_stage.value.upper()}**")
        if manifest.declared_stage is not None:
            st.caption(
                f"Declared stage: `{manifest.declared_stage.value}` · Derived stage: `{derived_stage.value}`"
            )
            if manifest.declared_stage != derived_stage:
                st.error("Declared stage contradicts derived stage — see blocker panel.")
        else:
            st.caption(
                f"Inferred from explicit artifact standings; no declared stage supplied. Derived: `{derived_stage.value}`"
            )
        # Small stage progression hint
        all_stages = [s.value for s in WorkspaceLifecycleStage]
        st.caption(f"Lifecycle order: {' → '.join(all_stages)}")

    # ------------------------------------------------------------------
    # Artifact inventory grouped by role
    # ------------------------------------------------------------------
    st.subheader("4. Artifact inventory grouped by role")
    if not manifest.artifacts:
        st.info(
            "No artifacts referenced yet — the workspace is in draft. Add a source contract and preregistration plan to advance."
        )
    else:
        # Group by kind
        grouped: dict[str, list[WorkspaceArtifactRef]] = {}
        for art in manifest.artifacts:
            grouped.setdefault(art.kind.value, []).append(art)

        for kind_value in sorted(grouped.keys()):
            refs = sorted(grouped[kind_value], key=lambda a: a.fingerprint)
            with st.expander(f"{kind_value} — {len(refs)} artifact(s)", expanded=True):
                rows = [
                    {
                        "fingerprint": r.fingerprint[:12] + "…",
                        "full_fingerprint": r.fingerprint,
                        "label": r.label,
                        "schema_version": r.schema_version,
                        "standing": r.standing.value,
                        "compatibility": r.compatibility_standing.value,
                        "availability": r.availability.value,
                        "parent": (r.parent_fingerprint[:12] + "…" if r.parent_fingerprint else ""),
                        "reason": r.reason or "",
                    }
                    for r in refs
                ]
                # Show standing badges per row as caption rather than per-cell badges (table keeps raw values)
                st.dataframe(
                    rows,
                    hide_index=True,
                    width="stretch",
                    column_config=table_column_config(rows),
                    key=f"study_workspace_inventory_{kind_value}",
                )
                # Badge summary row
                badge_cols = st.columns(len(refs))
                for col, ref in zip(badge_cols, refs, strict=False):
                    with col:
                        st.caption(_badge_for_standing(ref.standing))
                        st.caption(_badge_for_compatibility(ref.compatibility_standing))
                        st.caption(_badge_for_availability(ref.availability))

    # ------------------------------------------------------------------
    # Evidence / admission standing summary (before blockers)
    # ------------------------------------------------------------------
    st.subheader("5. Evidence and admission standing")
    if manifest.artifacts:
        standing_rows = [
            {
                "fingerprint": a.fingerprint[:12] + "…",
                "kind": a.kind.value,
                "label": a.label,
                "standing": a.standing.value,
                "compatibility": a.compatibility_standing.value,
                "availability": a.availability.value,
                "reason": a.reason or "",
            }
            for a in sorted(manifest.artifacts, key=lambda a: (a.kind.value, a.fingerprint))
        ]
        st.dataframe(
            standing_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(standing_rows),
            key="study_workspace_standing_table",
        )
        st.caption(
            "No synthetic evidence is relabelled as observed; incompatibilities fail closed."
        )
    else:
        st.info("No evidence standing to show — the workspace is empty.")

    # ------------------------------------------------------------------
    # Blocker panel (exact blockers and warnings, never silently dropped)
    # ------------------------------------------------------------------
    st.subheader("6. Validation — blockers and warnings")
    if validation.is_valid and not validation.warnings:
        st.success("Workspace manifest is valid — no blockers or warnings.")
    else:
        if validation.blockers:
            st.error(
                f"{len(validation.blockers)} blocker(s) — the workspace cannot advance until resolved."
            )
            for blk in validation.blockers:
                with st.container(border=True):
                    st.markdown(f"**{blk.code}** — {blk.severity.value}")
                    st.caption(blk.message)
                    if blk.related_fingerprints:
                        st.caption(
                            f"Related: {', '.join(fp[:12] + '…' for fp in blk.related_fingerprints)}"
                        )
                    st.caption(
                        f"Full fingerprints: {', '.join(blk.related_fingerprints) or 'none'}"
                    )
        else:
            st.success("No blockers — the workspace is not blocked.")

        if validation.warnings:
            st.warning(f"{len(validation.warnings)} warning(s)")
            for warn in validation.warnings:
                with st.container(border=True):
                    st.markdown(f"**{warn.code}** — {warn.severity.value}")
                    st.caption(warn.message)
                    if warn.related_fingerprints:
                        st.caption(
                            f"Related: {', '.join(fp[:12] + '…' for fp in warn.related_fingerprints)}"
                        )

        with st.expander("Advanced: full validation report JSON"):
            st.json(validation.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Next valid actions (guidance records only)
    # ------------------------------------------------------------------
    st.subheader("7. Next valid actions")
    st.caption("Guidance only — no action invokes another service automatically.")
    actions = next_actions(manifest, validation)
    if not actions:
        st.info("No next actions — the workspace appears complete.")
    else:
        for act in actions:
            with st.container(border=True):
                st.markdown(f"**{act.label}** — `{act.action}`")
                st.caption(act.description)
                st.caption(f"Priority: {act.priority}")
                if act.related_fingerprints:
                    st.caption(
                        f"Related: {', '.join(fp[:12] + '…' for fp in act.related_fingerprints)}"
                    )

    # ------------------------------------------------------------------
    # Lineage graph / bounded relation table
    # ------------------------------------------------------------------
    st.subheader("8. Lineage and relations")
    st.caption(
        "Bounded parent linkages between referenced artifacts. Missing parents are explicit blockers, not hidden."
    )
    lineage_rows = []
    fp_to_ref = {a.fingerprint: a for a in manifest.artifacts}
    for art in sorted(manifest.artifacts, key=lambda a: a.fingerprint):
        if art.parent_fingerprint is None:
            continue
        parent = fp_to_ref.get(art.parent_fingerprint)
        lineage_rows.append(
            {
                "child_fp": art.fingerprint[:12] + "…",
                "child_kind": art.kind.value,
                "child_label": art.label,
                "parent_fp": art.parent_fingerprint[:12] + "…",
                "parent_kind": parent.kind.value if parent else "unavailable",
                "parent_label": parent.label if parent else "missing",
            }
        )
    if lineage_rows:
        st.dataframe(
            lineage_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(lineage_rows),
            key="study_workspace_lineage_table",
        )
        with st.expander("Advanced: lineage as full fingerprints"):
            full_rows: list[dict[str, str | None]] = []
            for a in sorted(manifest.artifacts, key=lambda a: a.fingerprint):
                if not a.parent_fingerprint:
                    continue
                parent = fp_to_ref.get(a.parent_fingerprint)
                parent_kind = parent.kind.value if parent is not None else "unknown"
                full_rows.append(
                    {
                        "child_fingerprint": a.fingerprint,
                        "child_kind": a.kind.value,
                        "parent_fingerprint": a.parent_fingerprint,
                        "parent_kind": parent_kind,
                    }
                )
            st.dataframe(
                full_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(full_rows),
                key="study_workspace_lineage_full",
            )
    else:
        st.info("No parent linkages declared — all artifacts are roots or orphans.")

    # Optional tiny lineage "graph" via text
    with st.container(border=True):
        st.caption("Lineage graph (bounded, text-based)")
        if not lineage_rows:
            st.caption("No edges to display.")
        else:
            for row in lineage_rows:
                st.caption(f"`{row['child_label']}` → `[{row['parent_label']}]`")

    # ------------------------------------------------------------------
    # Provenance and fingerprints
    # ------------------------------------------------------------------
    st.subheader("9. Provenance and fingerprints")
    with st.container(border=True):
        st.markdown(f"**Workspace fingerprint:** `{fingerprint_summary(fp)}`")
        st.caption(f"Full fingerprint: `{fp}`")
        st.caption(
            "Fingerprint binds all semantic fields, sorted for order independence; excludes wall clock and local paths."
        )
        if manifest.provenance:
            prov_rows = [{"key": k, "value": v} for k, v in sorted(manifest.provenance.items())]
            st.dataframe(
                prov_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(prov_rows),
                key="study_workspace_provenance",
            )
        else:
            st.info("No provenance entries supplied.")
        with st.expander("Advanced: full canonical JSON"):
            canonical = export_workspace_pretty_json(manifest)
            st.code(
                canonical[:4000] + ("\n… truncated" if len(canonical) > 4000 else ""),
                language="json",
            )

    # ------------------------------------------------------------------
    # Portable downloads — exact portable artifacts used by page
    # ------------------------------------------------------------------
    st.subheader("10. Portable exports")
    st.caption(
        "JSON export is the exact portable workspace manifest used by the page; CSV exports are tabular inventories."
    )
    st.download_button(
        "Download workspace JSON",
        data=export_workspace_json(manifest),
        file_name=f"{manifest.workspace_id}_workspace.json",
        mime="application/json",
        key="study_workspace_download_json",
    )
    st.download_button(
        "Download artifact inventory CSV",
        data=export_artifacts_csv(manifest),
        file_name=f"{manifest.workspace_id}_artifacts.csv",
        mime="text/csv",
        key="study_workspace_download_csv",
    )
    st.download_button(
        "Download lineage CSV",
        data=export_lineage_csv(manifest),
        file_name=f"{manifest.workspace_id}_lineage.csv",
        mime="text/csv",
        key="study_workspace_download_lineage",
    )

    st.caption(
        "Portable JSON contains no absolute paths, credentials, or wall-clock timestamps in its fingerprint. "
        "Local filesystem paths never enter the canonical identity."
    )
