"""Confirmation-gated CSV manifest inference wizard."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ingestion.manifest_inference import (
    CanonicalisationManifest,
    FileSelection,
    ManifestInferenceSelections,
    SuggestionStatus,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    apply_manifest_inference_for_ui,
    confirm_manifest_inference_for_ui,
    infer_manifest_for_ui,
    manifest_file_fragment_for_ui,
)
from traffictwin.ui.state import UiConfig

UNMAPPED = "— unmapped —"
SELECT_KIND = "— select file kind —"
SELECT_UNIT = "— select unit —"


def render(config: UiConfig) -> None:
    """Render inference evidence, mapping edits, and explicit confirmation downloads."""

    del config
    render_page_header(UiPage.MANIFEST_WIZARD)
    st.warning(
        "Suggestions are deterministic drafts, not analysis inputs. Confirm or edit every file "
        "mapping explicitly; ambiguous files are never selected automatically."
    )
    fixture = Path.cwd() / "tests/fixtures/manifest_inference/value_patterns"
    default_source = fixture if fixture.is_dir() else Path.cwd()
    source = Path(
        st.text_input(
            "CSV source directory",
            value=str(st.session_state.get("manifest_inference_source", default_source)),
        )
    )
    st.session_state["manifest_inference_source"] = str(source)
    if not source.is_dir():
        st.error(f"CSV source directory does not exist: {source}")
        return

    draft = infer_manifest_for_ui(source)
    if isinstance(draft, ServiceError):
        st.error(draft.message)
        if draft.detail:
            st.code(draft.detail)
        return
    badge_row(["DRAFT", "CONFIRMATION REQUIRED", "ANALYSIS DISABLED"])
    st.json(
        {
            "source_label": draft.source_label,
            "source_fingerprint": draft.source_fingerprint,
            "draft_fingerprint": draft.draft_fingerprint,
            "analysis_ready": draft.analysis_ready,
            "sample_limits": draft.limits.model_dump(mode="json"),
        }
    )
    if draft.findings:
        st.subheader("Inference findings")
        st.dataframe(
            [
                {
                    "severity": finding.severity.value,
                    "code": finding.code.value,
                    "file": finding.file,
                    "message": finding.message,
                }
                for finding in draft.findings
            ],
            hide_index=True,
            width="stretch",
        )

    st.subheader("Review and edit mappings")
    selections: dict[str, FileSelection] = {}
    for file_index, file in enumerate(draft.files):
        with st.expander(
            f"{file.path} — {file.status.value}",
            expanded=file_index == 0,
        ):
            include = st.checkbox(
                "Include this CSV",
                value=True,
                key=f"manifest-include-{file.path}",
            )
            if not include:
                selections[file.path] = FileSelection(include=False)
                continue
            candidate_kinds = [candidate.kind for candidate in file.kind_candidates]
            if file.suggested_kind is None:
                kind_options = [SELECT_KIND, *candidate_kinds]
                kind_index = 0
            else:
                kind_options = [file.suggested_kind] + [
                    kind for kind in candidate_kinds if kind != file.suggested_kind
                ]
                kind_index = 0
            selected_kind = st.selectbox(
                "File kind",
                kind_options,
                index=kind_index,
                key=f"manifest-kind-{file.path}",
            )
            if file.status is SuggestionStatus.AMBIGUOUS:
                eligible = [
                    candidate.kind for candidate in file.kind_candidates if candidate.eligible
                ]
                st.warning("Ambiguous eligible kinds: " + ", ".join(eligible))
            if selected_kind == SELECT_KIND:
                selections[file.path] = FileSelection(kind=None)
                continue
            candidate = file.by_kind()[selected_kind]
            st.caption(
                f"Required coverage: {len(candidate.required_fields_mapped)}/"
                f"{len(candidate.required_fields)}; deterministic score: {candidate.score}. "
                "The score orders evidence—it is not a probability."
            )
            selected_map: dict[str, str] = {}
            unmap: list[str] = []
            selected_units: dict[str, str] = {}
            for field in candidate.fields:
                source_options = [UNMAPPED, *file.headers]
                source_index = (
                    source_options.index(field.suggested_source_column)
                    if field.suggested_source_column in source_options
                    else 0
                )
                label = field.canonical_field + (" (required)" if field.required else "")
                selected_source = st.selectbox(
                    label,
                    source_options,
                    index=source_index,
                    key=f"manifest-field-{file.path}-{selected_kind}-{field.canonical_field}",
                )
                if selected_source == UNMAPPED:
                    if field.suggested_source_column is not None:
                        unmap.append(field.canonical_field)
                    continue
                selected_map[field.canonical_field] = selected_source
                if field.supported_units:
                    unit_options = [SELECT_UNIT, *field.supported_units]
                    unit_index = (
                        unit_options.index(field.suggested_unit)
                        if field.suggested_unit in unit_options
                        else 0
                    )
                    selected_unit = st.selectbox(
                        f"Unit for {field.canonical_field}",
                        unit_options,
                        index=unit_index,
                        key=f"manifest-unit-{file.path}-{selected_kind}-{field.canonical_field}",
                    )
                    if selected_unit != SELECT_UNIT:
                        selected_units[field.canonical_field] = selected_unit
            selections[file.path] = FileSelection(
                kind=selected_kind,
                column_map=selected_map,
                unmapped_fields=unmap,
                units=selected_units,
            )

    confirmed_by = st.text_input(
        "Confirmed by (name or role label)",
        value="",
        help="Stored as mapping provenance; do not enter sensitive personal data.",
    )
    acknowledged = st.checkbox(
        "I have reviewed the selected file kinds, columns, and units.",
        value=False,
    )
    if st.button("Confirm Selected Mappings", type="primary", disabled=not acknowledged):
        confirmation_result = confirm_manifest_inference_for_ui(
            draft,
            source,
            confirmed_by=confirmed_by,
            selections=ManifestInferenceSelections(files=selections),
        )
        if isinstance(confirmation_result, ServiceError):
            st.error(confirmation_result.message)
            if confirmation_result.detail:
                st.code(confirmation_result.detail)
        else:
            st.session_state["confirmed_manifest_inference"] = confirmation_result.model_dump(
                mode="json"
            )
            st.success(
                f"Mappings confirmed as {confirmation_result.confirmation_state.value}; "
                "analysis-ready "
                "mapping artifact created."
            )

    confirmed_current = _confirmed_for_current_draft(draft.draft_fingerprint)
    if confirmed_current is None:
        return
    st.subheader("Confirmed outputs")
    badge_row(["CONFIRMED", confirmed_current.confirmation_state.value.upper(), "DOWNLOADABLE"])
    st.download_button(
        "Download canonicalisation.yaml",
        data=confirmed_current.to_yaml(),
        file_name="canonicalisation.yaml",
        mime="application/yaml",
    )
    st.download_button(
        "Download manifest files fragment",
        data=manifest_file_fragment_for_ui(confirmed_current),
        file_name="manifest-files.yaml",
        mime="application/yaml",
    )
    template_default = source / "manifest-template.yaml"
    template_path = Path(
        st.text_input(
            "Complete bundle metadata template (optional)",
            value=str(template_default if template_default.is_file() else ""),
        )
    )
    if template_path.is_file():
        rendered = apply_manifest_inference_for_ui(confirmed_current, template_path)
        if isinstance(rendered, ServiceError):
            st.error(rendered.message)
            if rendered.detail:
                st.code(rendered.detail)
        else:
            st.download_button(
                "Download confirmed manifest.yaml",
                data=rendered,
                file_name="manifest.yaml",
                mime="application/yaml",
            )
            st.info(
                "Place manifest.yaml beside the unchanged CSV files and required seed.yaml, then "
                "validate it through Bundle Import & Validation. Downloading does not import or "
                "analyse the source."
            )


def _confirmed_for_current_draft(draft_fingerprint: str | None) -> CanonicalisationManifest | None:
    payload = st.session_state.get("confirmed_manifest_inference")
    if not isinstance(payload, dict):
        return None
    confirmed = CanonicalisationManifest.model_validate(payload)
    return confirmed if confirmed.draft_fingerprint == draft_fingerprint else None
