"""Data Contract Workbench — versioned source-contract workflow and drift comparison."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import yaml
from pydantic import ValidationError

from traffictwin.data_contract.drift import compare_contracts, compare_observation_to_contract
from traffictwin.data_contract.exports import (
    export_contract_json,
    export_contract_yaml,
    export_drift_csv,
    export_drift_json,
    export_observation_csv,
    export_observation_json,
)
from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.models import (
    FieldContract,
    LogicalType,
    PublicationClass,
    RightsAndRetentionContract,
    SchemaDriftReport,
    SchemaDriftSeverity,
    SchemaObservation,
    SourceContractVersion,
    SourceDataContract,
    TimeBasis,
    TimestampContract,
    TimezoneSemantics,
    UnitContract,
)
from traffictwin.data_contract.service import (
    create_frozen_version,
    create_new_version_from_parent,
    prepare_handoff_to_manifest,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import table_column_config

SESSION_OBS = "dcw_observation"
SESSION_CONTRACT = "dcw_draft_contract"
SESSION_FROZEN = "dcw_frozen_version"
SESSION_DRIFT = "dcw_drift_report"
SESSION_CANDIDATE_OBS = "dcw_candidate_observation"


def render(config: UiConfig) -> None:
    """Render the Data Contract Workbench."""

    del config
    render_page_header(UiPage.DATA_CONTRACT_WORKBENCH)
    st.warning(
        "This workbench preserves what a source is expected to provide and explains how a later "
        "sample differs. It does not import data, does not call external providers, and does not "
        "claim scientific acceptance."
    )
    st.caption(
        "Portable contract and drift exports exclude raw row values, absolute paths, retrieval "
        "clocks, and secrets. Bounded inspection uses explicit row and byte limits."
    )

    # ------------------------------------------------------------------
    # 1. Sample selection and bounded inspection
    # ------------------------------------------------------------------
    st.subheader("1. Select and inspect a bounded local sample")
    st.caption(
        "Supported: plain CSV, gzip CSV (.csv.gz), flat scalar Parquet. "
        "Inspection is bounded by explicit row and byte limits and does not retain raw values."
    )
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        raw_path = st.text_input(
            "Sample path (local tabular file)",
            value=str(
                st.session_state.get(
                    "dcw_sample_path",
                    "tests/fixtures/manifest_inference/value_patterns/tasks_expected.csv",
                )
            ),
        )
    with col_b:
        max_rows = st.number_input(
            "Max rows",
            min_value=1,
            max_value=10000,
            value=int(st.session_state.get("dcw_max_rows", 1000)),
            step=100,
        )
    with col_c:
        max_bytes = st.number_input(
            "Max bytes",
            min_value=1024,
            max_value=10_000_000,
            value=int(st.session_state.get("dcw_max_bytes", 2_000_000)),
            step=1024,
        )
    st.session_state["dcw_sample_path"] = raw_path
    st.session_state["dcw_max_rows"] = int(max_rows)
    st.session_state["dcw_max_bytes"] = int(max_bytes)

    if st.button("Inspect sample", type="primary", key="dcw_inspect"):
        try:
            path = Path(raw_path)
            obs = inspect_tabular_sample(
                path,
                max_rows=int(max_rows),
                max_bytes=int(max_bytes),
                observation_id="obs_001",
                source_label=str(path),
            )
            st.session_state[SESSION_OBS] = obs.model_dump(mode="json")
            st.success(
                f"Inspected {obs.total_observed_rows} rows, {len(obs.field_observations)} fields"
            )
            if obs.truncated:
                st.warning("Sample was truncated to the configured limits; observation is bounded.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Inspection failed: {exc}")

    observation = _load_observation_from_session()
    if observation is not None:
        st.markdown("**Schema observation (deterministic, schema-only)**")
        badge_row(
            ["OBSERVED", "BOUNDED", "NO RAW VALUES" if not observation.truncated else "TRUNCATED"]
        )
        with st.container(border=True):
            st.caption(
                f"Observation fingerprint `{fingerprint_summary(observation.fingerprint)}` · "
                f"Rows observed: {observation.total_observed_rows} · "
                f"Fields: {len(observation.field_observations)}"
            )
            if observation.truncated:
                st.warning("Observation was truncated at the configured limits.")
        obs_rows = [
            {
                "field_name": fo.field_name,
                "observed_logical_type": fo.observed_logical_type.value,
                "nullable": str(fo.nullable),
                "observed_count": str(fo.observed_count),
                "null_count": str(fo.null_count),
                "timestamp_parse_state": fo.timestamp_parse_state or "",
                "categorical_digest": ", ".join(fo.categorical_digest or []),
                "precision": str(fo.precision) if fo.precision is not None else "",
                "scale": str(fo.scale) if fo.scale is not None else "",
            }
            for fo in observation.field_observations
        ]
        st.dataframe(
            obs_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(obs_rows),
        )
        with st.expander("Advanced: observation identity"):
            st.json(
                {
                    "observation_id": observation.observation_id,
                    "source_label_redacted": observation.source_label_redacted,
                    "fingerprint": observation.fingerprint,
                    "truncated": observation.truncated,
                }
            )
        # Download observation JSON/CSV (no raw values)
        st.download_button(
            "Download observation JSON",
            data=export_observation_json(observation),
            file_name="schema_observation.json",
            mime="application/json",
            key="dcw_obs_json",
        )
        st.download_button(
            "Download observation CSV",
            data=export_observation_csv(observation),
            file_name="schema_observation.csv",
            mime="text/csv",
            key="dcw_obs_csv",
        )

    # ------------------------------------------------------------------
    # 2. Contract editor
    # ------------------------------------------------------------------
    st.subheader("2. Author or confirm the source contract")
    st.caption(
        "Confirm field identity, required/optional, logical type, unit, timestamp semantics, "
        "source identifier, and privacy/publication classification before freezing."
    )
    draft_contract = _load_draft_from_session(observation)
    # Build editable form
    with st.form("dcw_contract_form"):
        source_id = st.text_input(
            "Source identifier",
            value=draft_contract.source_id if draft_contract else "example_source",
        )
        contract_version = st.text_input(
            "Contract version (X.Y.Z)",
            value=draft_contract.contract_version if draft_contract else "1.0.0",
        )
        pub_class_options = [e.value for e in PublicationClass]
        current_pub = (
            draft_contract.rights.publication_class.value
            if draft_contract
            else PublicationClass.PRIVATE.value
        )
        pub_index = pub_class_options.index(current_pub) if current_pub in pub_class_options else 0
        pub_class = st.selectbox(
            "Publication / privacy classification", pub_class_options, index=pub_index
        )
        contains_personal = st.checkbox(
            "Contains personal data",
            value=draft_contract.rights.contains_personal_data if draft_contract else False,
        )
        notes = st.text_area(
            "Notes (optional)",
            value=draft_contract.notes or "" if draft_contract and draft_contract.notes else "",
        )
        st.markdown("**Fields**")
        st.caption("Edit each field's required state, logical type, unit, and timestamp semantics.")
        # Prepare editable field rows
        fields_for_edit = (
            draft_contract.fields
            if draft_contract
            else _default_fields_from_observation(observation)
        )
        edited_fields: list[FieldContract] = []
        # Use session to hold dynamic field edits? For simplicity, render up to 12 fields
        for idx, field in enumerate(fields_for_edit[:12]):
            with st.expander(f"Field {idx + 1}: {field.field_name}", expanded=idx == 0):
                fname = st.text_input(
                    f"Field name {idx}", value=field.field_name, key=f"dcw_fname_{idx}"
                )
                req = st.checkbox(f"Required {idx}", value=field.required, key=f"dcw_req_{idx}")
                ltype_options = [e.value for e in LogicalType]
                ltype_idx = (
                    ltype_options.index(field.logical_type.value)
                    if field.logical_type.value in ltype_options
                    else 0
                )
                ltype = st.selectbox(
                    f"Logical type {idx}", ltype_options, index=ltype_idx, key=f"dcw_ltype_{idx}"
                )
                unit_val = st.text_input(
                    f"Unit (optional) {idx}",
                    value=field.unit.unit if field.unit else "",
                    key=f"dcw_unit_{idx}",
                )
                unit_dim = st.text_input(
                    f"Unit dimension (optional) {idx}",
                    value=field.unit.dimension if field.unit and field.unit.dimension else "",
                    key=f"dcw_udim_{idx}",
                )
                # Timestamp semantics
                is_ts = ltype == LogicalType.TIMESTAMP.value
                if is_ts:
                    basis_options = [e.value for e in TimeBasis]
                    current_basis = (
                        field.timestamp.time_basis.value
                        if field.timestamp
                        else TimeBasis.ISO8601.value
                    )
                    basis_idx = (
                        basis_options.index(current_basis) if current_basis in basis_options else 0
                    )
                    basis = st.selectbox(
                        f"Time basis {idx}", basis_options, index=basis_idx, key=f"dcw_basis_{idx}"
                    )
                    tz_options = [e.value for e in TimezoneSemantics]
                    current_tz = (
                        field.timestamp.timezone.value
                        if field.timestamp
                        else TimezoneSemantics.UTC.value
                    )
                    tz_idx = tz_options.index(current_tz) if current_tz in tz_options else 0
                    tz = st.selectbox(
                        f"Timezone semantics {idx}", tz_options, index=tz_idx, key=f"dcw_tz_{idx}"
                    )
                    fmt = st.text_input(
                        f"Format hint (optional) {idx}",
                        value=field.timestamp.format_hint
                        if field.timestamp and field.timestamp.format_hint
                        else "",
                        key=f"dcw_fmt_{idx}",
                    )
                    req_tz = st.checkbox(
                        f"Requires timezone {idx}",
                        value=field.timestamp.requires_timezone if field.timestamp else False,
                        key=f"dcw_reqtz_{idx}",
                    )
                else:
                    basis = None
                    tz = None
                    fmt = None
                    req_tz = False
                # Build FieldContract for preview (validation will happen on submit)
                try:
                    unit_obj = None
                    if unit_val.strip():
                        unit_obj = UnitContract(
                            unit=unit_val.strip(), dimension=unit_dim.strip() or None
                        )
                    ts_obj = None
                    if is_ts:
                        ts_obj = TimestampContract(
                            time_basis=TimeBasis(basis),
                            timezone=TimezoneSemantics(tz),
                            format_hint=fmt.strip() or None,
                            requires_timezone=req_tz,
                        )
                    fc = FieldContract(
                        field_name=fname.strip() or field.field_name,
                        required=req,
                        logical_type=LogicalType(ltype),
                        unit=unit_obj,
                        timestamp=ts_obj,
                    )
                    edited_fields.append(fc)
                except ValidationError as ve:
                    st.error(f"Field {idx} validation: {ve}")

        submitted = st.form_submit_button("Save draft contract")
        if submitted:
            try:
                rights = RightsAndRetentionContract(
                    publication_class=PublicationClass(pub_class),
                    contains_personal_data=contains_personal,
                )
                contract = SourceDataContract(
                    source_id=source_id.strip(),
                    contract_version=contract_version.strip(),
                    fields=edited_fields if edited_fields else fields_for_edit,
                    rights=rights,
                    notes=notes.strip() or None,
                )
                st.session_state[SESSION_CONTRACT] = contract.model_dump(mode="json")
                st.success("Draft contract saved (not yet frozen)")
            except ValidationError as ve:
                st.error(f"Contract validation failed: {ve}")

    draft = _load_draft_from_session(observation)
    if draft is not None:
        st.markdown("**Draft contract preview (not frozen)**")
        badge_row(["DRAFT", "EDITABLE", "NOT FROZEN"])
        with st.container(border=True):
            st.json(draft.model_dump(mode="json"))
        st.download_button(
            "Download draft contract JSON",
            data=export_contract_json(draft),
            file_name="source_contract_draft.json",
            mime="application/json",
            key="dcw_draft_json",
        )
        st.download_button(
            "Download draft contract YAML",
            data=export_contract_yaml(draft),
            file_name="source_contract_draft.yaml",
            mime="text/yaml",
            key="dcw_draft_yaml",
        )

    # ------------------------------------------------------------------
    # 3. Freeze action
    # ------------------------------------------------------------------
    st.subheader("3. Freeze a versioned source contract")
    st.caption(
        "A frozen contract is immutable; a change creates a new version linked to its parent."
    )
    frozen = _load_frozen_from_session()
    draft_for_freeze = _load_draft_from_session(observation)
    if frozen is not None:
        st.info(
            f"Current frozen version: {frozen.version} (fingerprint {fingerprint_summary(frozen.fingerprint)})"
        )
        with st.expander("Advanced: frozen lineage"):
            st.json(
                {
                    "version": frozen.version,
                    "fingerprint": frozen.fingerprint,
                    "parent_fingerprint": frozen.parent_fingerprint,
                    "amendment_reason": frozen.amendment_reason,
                    "is_frozen": frozen.is_frozen,
                }
            )
    amendment = st.text_input(
        "Amendment reason (required when updating a frozen contract)",
        value=str(st.session_state.get("dcw_amendment", "")),
        key="dcw_amendment_input",
    )
    st.session_state["dcw_amendment"] = amendment
    col_freeze, col_new = st.columns(2)
    with col_freeze:
        if st.button("Freeze draft as new version", type="primary", key="dcw_freeze"):
            if draft_for_freeze is None:
                st.error("No draft contract to freeze")
            else:
                try:
                    if frozen is None:
                        new_version = create_frozen_version(draft_for_freeze)
                    else:
                        new_version = create_new_version_from_parent(
                            frozen,
                            draft_for_freeze,
                            amendment_reason=amendment.strip() or "initial freeze",
                        )
                    st.session_state[SESSION_FROZEN] = new_version.model_dump(mode="json")
                    st.success(
                        f"Frozen version {new_version.version} created: {fingerprint_summary(new_version.fingerprint)}"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Freeze failed: {exc}")
    with col_new:
        if st.button("Clear frozen version (demo only)", key="dcw_clear"):
            st.session_state.pop(SESSION_FROZEN, None)
            st.success("Frozen version cleared")

    if frozen is not None:
        st.download_button(
            "Download frozen contract JSON",
            data=json.dumps(frozen.model_dump(mode="json"), indent=2, sort_keys=True),
            file_name=f"frozen_contract_{frozen.version}.json",
            mime="application/json",
            key="dcw_frozen_json",
        )
        st.download_button(
            "Download frozen contract YAML",
            data=yaml.safe_dump(frozen.model_dump(mode="json"), sort_keys=True),
            file_name=f"frozen_contract_{frozen.version}.yaml",
            mime="text/yaml",
            key="dcw_frozen_yaml",
        )

    # ------------------------------------------------------------------
    # 4. Candidate comparison
    # ------------------------------------------------------------------
    st.subheader("4. Compare a later sample or candidate contract")
    st.caption("Receive typed compatible, review-required, and blocked drift findings.")
    cand_path = st.text_input(
        "Candidate sample path (optional, local tabular file)",
        value=str(st.session_state.get("dcw_candidate_path", "")),
        key="dcw_candidate_path_input",
    )
    st.session_state["dcw_candidate_path"] = cand_path
    cand_max_rows = st.number_input(
        "Candidate max rows",
        min_value=1,
        max_value=10000,
        value=int(st.session_state.get("dcw_cand_max_rows", 1000)),
        key="dcw_cand_max_rows_input",
    )
    st.session_state["dcw_cand_max_rows"] = int(cand_max_rows)
    if st.button("Compare candidate to frozen contract", key="dcw_compare"):
        if frozen is None:
            st.error("Freeze a contract before comparing")
        elif not cand_path.strip():
            st.error("Provide a candidate sample path")
        else:
            try:
                cand_obs = inspect_tabular_sample(
                    Path(cand_path.strip()),
                    max_rows=int(cand_max_rows),
                    max_bytes=int(st.session_state.get("dcw_max_bytes", 2_000_000)),
                    observation_id="obs_candidate",
                    source_label=str(cand_path),
                )
                st.session_state[SESSION_CANDIDATE_OBS] = cand_obs.model_dump(mode="json")
                # Try to load candidate contract from session if authoring one; otherwise use observation only
                cand_contract = _load_draft_from_session(observation)
                # If draft was from frozen, synthesize candidate contract from observation? Use drift with observation only
                # Here we compare observation to frozen; if candidate draft exists and differs, use contract comparison
                if (
                    cand_contract is not None
                    and cand_contract.source_id != frozen.contract.source_id
                ):
                    # Source identity differs – pass candidate contract for source drift detection
                    report = compare_contracts(
                        frozen, cand_contract, candidate_observation=cand_obs
                    )
                else:
                    report = compare_observation_to_contract(frozen, cand_obs)
                st.session_state[SESSION_DRIFT] = report.model_dump(mode="json")
                st.success(
                    f"Comparison complete: {report.overall_severity.value} ({len(report.findings)} findings)"
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Comparison failed: {exc}")

    drift = _load_drift_from_session()
    if drift is not None:
        st.markdown("**Drift report (deterministic)**")
        severity = drift.overall_severity.value
        if severity == SchemaDriftSeverity.BLOCKED.value:
            badge_row(["BLOCKED", "ACTION REQUIRED"])
            st.error(
                f"Overall: BLOCKED — {drift.summary.get('blocked', 0)} blocked, {drift.summary.get('review_required', 0)} review-required"
            )
        elif severity == SchemaDriftSeverity.REVIEW_REQUIRED.value:
            badge_row(["REVIEW REQUIRED", "MANUAL CHECK"])
            st.warning(
                f"Overall: REVIEW_REQUIRED — {drift.summary.get('review_required', 0)} review-required, {drift.summary.get('compatible', 0)} compatible"
            )
        else:
            badge_row(["COMPATIBLE", "NO ACTION"])
            st.success(f"Overall: COMPATIBLE — {drift.summary.get('compatible', 0)} findings")
        # Severity summary
        cols = st.columns(4)
        cols[0].metric("Blocked", drift.summary.get("blocked", 0))
        cols[1].metric("Review required", drift.summary.get("review_required", 0))
        cols[2].metric("Compatible", drift.summary.get("compatible", 0))
        cols[3].metric("Total", drift.summary.get("total", 0))
        # Findings table
        finding_rows = [
            {
                "field_name": f.field_name or "—",
                "severity": f.severity.value,
                "code": f.code,
                "message": f.message,
            }
            for f in drift.findings
        ]
        st.dataframe(
            finding_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(finding_rows),
        )
        with st.expander("Advanced: drift identity and fingerprints"):
            st.json(
                {
                    "contract_fingerprint": drift.contract_fingerprint,
                    "candidate_fingerprint": drift.candidate_fingerprint,
                    "fingerprint": drift.fingerprint,
                    "summary": drift.summary,
                }
            )
        # Warnings for source/time/unit/rights
        for finding in drift.findings:
            if finding.code in {
                "SOURCE_IDENTITY_CHANGED",
                "TIME_BASIS_CHANGED",
                "TIMEZONE_SEMANTICS_CHANGED",
                "UNIT_CHANGED_INCOMPATIBLY",
                "PRIVACY_CLASSIFICATION_WEAKENED",
            }:
                st.warning(f"⚠ {finding.code}: {finding.message}")
        # Downloads
        st.download_button(
            "Download drift JSON",
            data=export_drift_json(drift),
            file_name="drift_report.json",
            mime="application/json",
            key="dcw_drift_json",
        )
        st.download_button(
            "Download drift CSV (formula-safe)",
            data=export_drift_csv(drift),
            file_name="drift_report.csv",
            mime="text/csv",
            key="dcw_drift_csv",
        )

    # ------------------------------------------------------------------
    # 5. Handoff
    # ------------------------------------------------------------------
    st.subheader("5. Handoff to Manifest Inference / Bundle Import")
    st.caption("Prepares a confirmation payload without automatically importing the sample.")
    if st.button("Prepare handoff payload", key="dcw_handoff"):
        if frozen is None:
            st.error("Freeze a contract before preparing handoff")
        else:
            cand_obs = _load_candidate_observation()
            payload = prepare_handoff_to_manifest(frozen, observation=cand_obs or observation)
            st.session_state["dcw_handoff_payload"] = payload
            st.success("Handoff payload prepared (import not executed)")
    handoff = st.session_state.get("dcw_handoff_payload")
    if handoff is not None:
        st.json(handoff)
        st.caption(
            "This payload can be used to pre-populate the Manifest Inference Wizard or Bundle Import workflow."
        )
        st.download_button(
            "Download handoff JSON",
            data=json.dumps(handoff, indent=2, sort_keys=True),
            file_name="handoff_payload.json",
            mime="application/json",
            key="dcw_handoff_json",
        )
        st.info(
            "No data was imported automatically. Use the Manifest Inference Wizard or Bundle Import page to continue."
        )


def _load_observation_from_session() -> SchemaObservation | None:
    raw = st.session_state.get(SESSION_OBS)
    if raw is None:
        return None
    try:
        from traffictwin.data_contract.models import SchemaObservation as SO

        return SO.model_validate(raw)
    except Exception:
        return None


def _load_candidate_observation() -> SchemaObservation | None:
    raw = st.session_state.get(SESSION_CANDIDATE_OBS)
    if raw is None:
        return None
    try:
        from traffictwin.data_contract.models import SchemaObservation as SO

        return SO.model_validate(raw)
    except Exception:
        return None


def _load_draft_from_session(observation: SchemaObservation | None) -> SourceDataContract | None:
    raw = st.session_state.get(SESSION_CONTRACT)
    if raw is not None:
        try:
            return SourceDataContract.model_validate(raw)
        except Exception:
            pass
    # Synthesize draft from observation if available
    if observation is None:
        return None
    fields = []
    for fo in observation.field_observations:
        # Map observed logical type to contract logical type (string fallback)
        ltype = fo.observed_logical_type
        # For demo, keep same type
        try:
            fc = FieldContract(
                field_name=fo.field_name,
                required=not fo.nullable,
                logical_type=ltype,
            )
            fields.append(fc)
        except Exception:
            continue
    if not fields:
        return None
    try:
        return SourceDataContract(
            source_id="example_source",
            contract_version="1.0.0",
            fields=fields,
            rights=RightsAndRetentionContract(publication_class=PublicationClass.PRIVATE),
        )
    except Exception:
        return None


def _default_fields_from_observation(observation: SchemaObservation | None) -> list[FieldContract]:
    if observation is None:
        # Minimal default for first-time users
        return [
            FieldContract(
                field_name="timestamp",
                required=True,
                logical_type=LogicalType.TIMESTAMP,
                timestamp=TimestampContract(
                    time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC
                ),
            ),
            FieldContract(field_name="vehicle_id", required=True, logical_type=LogicalType.STRING),
            FieldContract(
                field_name="speed",
                required=False,
                logical_type=LogicalType.FLOAT,
                unit=UnitContract(unit="mps", dimension="speed"),
            ),
        ]
    fields: list[FieldContract] = []
    for fo in observation.field_observations:
        is_ts = fo.observed_logical_type is LogicalType.TIMESTAMP
        ts = None
        if is_ts:
            ts = TimestampContract(time_basis=TimeBasis.ISO8601, timezone=TimezoneSemantics.UTC)
        try:
            fc = FieldContract(
                field_name=fo.field_name,
                required=not fo.nullable,
                logical_type=fo.observed_logical_type,
                timestamp=ts,
            )
            fields.append(fc)
        except Exception:
            continue
    return fields


def _load_frozen_from_session() -> SourceContractVersion | None:
    raw = st.session_state.get(SESSION_FROZEN)
    if raw is None:
        return None
    try:
        return SourceContractVersion.model_validate(raw)
    except Exception:
        return None


def _load_drift_from_session() -> SchemaDriftReport | None:
    raw = st.session_state.get(SESSION_DRIFT)
    if raw is None:
        return None
    try:
        from traffictwin.data_contract.models import SchemaDriftReport as SDR

        return SDR.model_validate(raw)
    except Exception:
        return None


def _export_observation_json_local(observation: SchemaObservation) -> str:
    """Local helper to export observation JSON deterministically."""
    return export_observation_json(observation)
