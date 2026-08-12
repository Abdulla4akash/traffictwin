"""Metric Contract Registry page — closed metadata contract workflow."""

from __future__ import annotations

import json

import streamlit as st
from pydantic import ValidationError

from traffictwin.experiments.resource_strategy import (
    ResourceStrategyAdmissionState,
    ResourceStrategyEvidenceMode,
    ResourceStrategyMetric,
    ResourceStrategyMetricDenominator,
    ResourceStrategyStudy,
    build_resource_strategy_report,
)
from traffictwin.metric_contract_registry.models import (
    MetricContract,
    MetricContractDenominator,
    MetricContractDirection,
    MetricContractRegistry,
)
from traffictwin.metric_contract_registry.service import (
    build_built_in_registry,
    load_registry_from_json,
    registry_to_csv,
    registry_to_json,
    validate_registry,
)
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.tables import table_column_config

try:
    from traffictwin.ui.labels import UiPage
    from traffictwin.ui.navigation import render_page_header

    _HAS_ENUM = hasattr(UiPage, "METRIC_CONTRACT_REGISTRY")
except Exception:
    UiPage = None  # type: ignore[assignment,misc]
    render_page_header = None  # type: ignore[assignment]
    _HAS_ENUM = False


def _render_h1() -> None:
    if _HAS_ENUM and render_page_header is not None and UiPage is not None:
        try:
            render_page_header(UiPage.METRIC_CONTRACT_REGISTRY)  # type: ignore[attr-defined]
            return
        except Exception:  # noqa: S110
            pass
    st.title("Metric Contract Registry")


def _load_registry_from_state() -> MetricContractRegistry | None:
    payload = st.session_state.get("metric_contract_registry_payload")
    if not payload:
        return None
    try:
        return load_registry_from_json(json.dumps(payload))
    except Exception:
        return None


def _synthetic_study_for_preview(
    include_declarations: bool = True,
    arm_b_unit: str | None = None,
) -> ResourceStrategyStudy:
    # Minimal synthetic study with two arms, used for preview
    import hashlib

    from traffictwin.experiments.resource_strategy import (
        ResourceStrategyArm,
        ResourceStrategyLifecycle,
        ResourceStrategyReplication,
    )

    def _lc() -> ResourceStrategyLifecycle:
        return ResourceStrategyLifecycle(
            offered=1000,
            admitted=800,
            rejected=200,
            forwarded=400,
            started=760,
            compute_completed=720,
            returned=700,
            dropped=80,
            deadline_success=680,
        )

    def _rep(rid: str, metrics: dict[str, float] | None = None) -> ResourceStrategyReplication:
        return ResourceStrategyReplication(
            replication_id=rid,
            lifecycle=_lc(),
            metrics=metrics or {},
            queue_length_mean=7.5,
            queue_balance_jain=0.9,
            utilisation_mean=0.69,
            energy_mean_j=40.0,
            resource_cost_units=115.0,
            latency_mean_ms=155.0,
            latency_p95_ms=270.0,
        )

    custom_decl_a = ResourceStrategyMetric(
        metric_key="custom.preview.metric",
        metric_version="1.0",
        unit="ratio",
        denominator=ResourceStrategyMetricDenominator.REPLICATION,
    )
    custom_decl_b = ResourceStrategyMetric(
        metric_key="custom.preview.metric",
        metric_version="1.0",
        unit=arm_b_unit if arm_b_unit is not None else "ratio",
        denominator=ResourceStrategyMetricDenominator.REPLICATION,
    )
    arms = [
        ResourceStrategyArm(
            arm_id="arm_a",
            label="Arm A",
            description="Preview arm A",
            strategy_type="strongest_link_placement",
            replications=[_rep("rep_001"), _rep("rep_002"), _rep("rep_003")],
            metric_declarations=[custom_decl_a] if include_declarations else [],
        ),
        ResourceStrategyArm(
            arm_id="arm_b",
            label="Arm B",
            description="Preview arm B",
            strategy_type="deterministic_jsq",
            replications=[_rep("rep_001"), _rep("rep_002"), _rep("rep_003")],
            metric_declarations=[custom_decl_b] if include_declarations else [],
        ),
    ]
    metric_catalog = [
        ResourceStrategyMetric(
            metric_key="task.completion.rate_offered",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.OFFERED_TASKS,
        ),
        ResourceStrategyMetric(
            metric_key="custom.preview.metric",
            metric_version="1.0",
            unit="ratio",
            denominator=ResourceStrategyMetricDenominator.REPLICATION,
        ),
    ]
    # Need to add metric values for custom metric to replications
    for arm in arms:
        for rep in arm.replications:
            rep.metrics["custom.preview.metric"] = 0.42

    return ResourceStrategyStudy.model_validate(
        {
            "schema_version": "1.0",
            "study_id": "preview_study",
            "source_fingerprint": hashlib.sha256(b"preview").hexdigest(),
            "evidence_mode": ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION.value,
            "admission_state": ResourceStrategyAdmissionState.SYNTHETIC_DEMONSTRATION.value,
            "replication_unit": "replication_id",
            "arms": [a.model_dump(mode="json") for a in arms],
            "common_matched_replication_ids": ["rep_001", "rep_002", "rep_003"],
            "excluded_replication_ids": [],
            "metric_catalog": [m.model_dump(mode="json") for m in metric_catalog],
            "limitations": ["synthetic preview"],
            "provenance": {"preview": "metric_contract_registry"},
            "generated_at": None,
        }
    )


def render(config: object) -> None:  # noqa: ANN001
    _ = config
    _render_h1()
    st.caption(
        "Define closed metadata contracts for custom metrics — not executable formulas. "
        "A custom metric becomes comparable only when the registry contract, study catalog, "
        "and every participating arm's metric declaration agree on version, unit, and denominator. "
        "Registration alone does not establish comparability."
    )
    st.warning(
        "Registration does not implement metric computation. "
        "Contracts describe metadata; they do not execute code, expressions, import paths, or callbacks."  # noqa: E501
    )
    st.info(
        "Evidence and authority boundary: built-in metric contracts remain authoritative. "
        "A custom registry must not silently override a built-in contract. "
        "Identical duplicate is accepted as redundant/reference; conflicting built-in duplicate is rejected. "  # noqa: E501
        "Portable identity excludes wall clock, rendering state, local paths, and secrets."
    )

    # ------------------------------------------------------------------
    # Empty state and registry loading
    # ------------------------------------------------------------------
    if "metric_contract_registry_payload" not in st.session_state:
        st.session_state["metric_contract_registry_payload"] = None
    if "metric_contract_draft" not in st.session_state:
        st.session_state["metric_contract_draft"] = None

    current_registry = _load_registry_from_state()

    # Upload registry JSON
    st.subheader("Load or create registry")
    st.caption(
        "Upload a deterministic registry JSON, or create a new draft from scratch. "
        "The registry is validated on load; conflicting built-in overrides are rejected."
    )
    uploaded = st.file_uploader(
        "Upload registry JSON",
        type=["json"],
        key="metric_contract_registry_uploader",
    )
    col_load, col_new = st.columns(2)
    with col_load:
        if uploaded is not None:
            try:
                text = uploaded.getvalue().decode("utf-8")
                reg = load_registry_from_json(text)
                receipt = validate_registry(reg)
                if receipt.status.value == "rejected":
                    st.error(f"Registry rejected: {receipt.findings}")
                else:
                    st.session_state["metric_contract_registry_payload"] = json.loads(
                        reg.canonical_json()
                    )
                    st.success(
                        f"Loaded registry with {len(reg.deduplicated_contracts())} contracts (fingerprint {fingerprint_summary(reg.fingerprint())})"  # noqa: E501
                    )
                    st.rerun()
            except Exception as exc:
                st.error(f"Failed to load registry: {exc}")
    with col_new:
        if st.button("Create new empty registry", key="metric_contract_new_registry"):
            empty = MetricContractRegistry(registry_version="1.0", contracts=[], supersession=[])
            st.session_state["metric_contract_registry_payload"] = json.loads(
                empty.canonical_json()
            )
            st.success("New empty registry created")
            st.rerun()

    # Show current registry fingerprint if present
    if current_registry is not None:
        with st.container(border=True):
            st.markdown(
                f"**Registry fingerprint:** `{fingerprint_summary(current_registry.fingerprint())}`"
            )
            st.caption(f"Full fingerprint: `{current_registry.fingerprint()}`")
            st.caption(
                f"Registry version: {current_registry.registry_version} | Contracts: {len(current_registry.deduplicated_contracts())} | Supersession: {len(current_registry.supersession)}"  # noqa: E501
            )
    else:
        st.info(
            "No registry loaded. Create a new registry or upload one to begin. "
            "Until a custom contract is registered, custom metrics remain UNAVAILABLE for comparison — "  # noqa: E501
            "this is expected and fail-closed."
        )
        # Provide helpful empty-state guidance
        with st.container(border=True):
            st.markdown("**Get started**")
            st.caption("1. Use the form below to draft a custom contract")
            st.caption("2. Add it to the registry")
            st.caption("3. Validate conflicts against built-in contracts")
            st.caption("4. Preview Resource Strategy compatibility")
            st.caption("5. Download deterministic JSON/CSV")

    st.divider()

    # ------------------------------------------------------------------
    # Create / edit draft contract
    # ------------------------------------------------------------------
    st.subheader("Create or edit a draft contract")
    st.caption(
        "Draft a closed metadata contract — no code, expressions, or import paths are accepted."
    )
    with st.form("metric_contract_draft_form"):
        metric_key = st.text_input(
            "Metric key",
            value="custom.example.metric",
            help="Letter-start, letters/numbers/./_/-/: only, 1-256 chars",
            key="draft_metric_key",
        )
        metric_version = st.text_input("Metric version", value="1.0", key="draft_metric_version")
        unit = st.text_input("Unit", value="ratio", key="draft_unit")
        denom_options = [e.value for e in MetricContractDenominator]
        denom_selected = st.selectbox(
            "Denominator",
            denom_options,
            index=denom_options.index("replication"),
            key="draft_denominator",
        )
        description = st.text_area(
            "Description", value="Example custom metric for preview", key="draft_description"
        )
        c1, c2 = st.columns(2)
        with c1:
            higher = st.selectbox(
                "Higher is better",
                ["true", "false", "neutral (direction)"],
                index=0,
                key="draft_higher",
            )
        with c2:
            direction_options = [e.value for e in MetricContractDirection]
            direction_selected = st.selectbox(
                "Direction", ["(from higher_is_better)"] + direction_options, key="draft_direction"
            )
        time_window = st.checkbox("Time window applicable", value=False, key="draft_time_window")
        c3, c4 = st.columns(2)
        with c3:
            minimum = st.text_input("Minimum (optional, numeric)", value="", key="draft_min")
        with c4:
            maximum = st.text_input("Maximum (optional, numeric)", value="", key="draft_max")
        allowed = st.text_input(
            "Allowed statuses (comma-separated, optional)", value="", key="draft_allowed"
        )
        provenance = st.text_input("Provenance (optional)", value="", key="draft_provenance")
        citation = st.text_input("Citation (optional)", value="", key="draft_citation")
        contract_version = st.text_input(
            "Contract version", value="1.0", key="draft_contract_version"
        )
        submitted = st.form_submit_button("Validate draft")
        draft: MetricContract | None = None
        draft_error: str | None = None  # noqa: F841
        if submitted:
            try:
                # Parse optional fields
                hib: bool | None = None
                dir_val: MetricContractDirection | None = None
                if higher == "true":
                    hib = True
                elif higher == "false":
                    hib = False
                else:
                    # neutral
                    dir_val = MetricContractDirection.NEUTRAL
                if direction_selected != "(from higher_is_better)":
                    dir_val = MetricContractDirection(direction_selected)
                min_val: float | None = float(minimum) if minimum.strip() else None
                max_val: float | None = float(maximum) if maximum.strip() else None
                allowed_list: list[str] | None = None
                if allowed.strip():
                    allowed_list = [s.strip() for s in allowed.split(",") if s.strip()]
                prov = provenance.strip() or None
                cit = citation.strip() or None
                denom = MetricContractDenominator(denom_selected)
                # If hib is None and dir is neutral, keep dir neutral
                if hib is None and dir_val is None:
                    dir_val = MetricContractDirection.NEUTRAL
                draft = MetricContract(
                    metric_key=metric_key.strip(),
                    metric_version=metric_version.strip(),
                    unit=unit.strip(),
                    denominator=denom,
                    description=description.strip(),
                    higher_is_better=hib,
                    direction=dir_val,
                    time_window_applicable=bool(time_window),
                    minimum=min_val,
                    maximum=max_val,
                    allowed_statuses=allowed_list,
                    provenance=prov,
                    citation=cit,
                    contract_version=contract_version.strip(),
                )
                st.session_state["metric_contract_draft"] = draft.model_dump(mode="json")
                st.success("Draft is valid and ready to add to registry")
            except (ValidationError, ValueError) as exc:
                _draft_error = str(exc)  # noqa: F841
                st.error(f"Draft validation failed: {exc}")
            except Exception as exc:
                _draft_error = str(exc)  # noqa: F841
                st.error(f"Draft validation failed: {exc}")
        # Show draft from session if exists
        if st.session_state.get("metric_contract_draft") and not submitted:
            try:
                draft = MetricContract.model_validate(st.session_state["metric_contract_draft"])
                st.info(
                    f"Current draft: {draft.metric_key} v{draft.metric_version} [{draft.unit}/{draft.denominator.value}]"  # noqa: E501
                )
            except Exception:  # noqa: S110
                pass

    # Add draft to registry
    col_add, col_clear = st.columns(2)
    with col_add:
        if st.button("Add draft to registry", key="metric_contract_add_draft"):
            try:
                if st.session_state.get("metric_contract_draft") is None:
                    st.error("No valid draft to add — validate first")
                else:
                    draft_obj = MetricContract.model_validate(
                        st.session_state["metric_contract_draft"]
                    )
                    existing_payload = st.session_state.get("metric_contract_registry_payload")
                    if existing_payload is None:
                        base = MetricContractRegistry(
                            registry_version="1.0", contracts=[], supersession=[]
                        )
                    else:
                        base = load_registry_from_json(json.dumps(existing_payload))
                    # Append and validate
                    new_contracts = list(base.contracts) + [draft_obj]
                    candidate = MetricContractRegistry(
                        registry_version=base.registry_version,
                        contracts=new_contracts,
                        supersession=list(base.supersession),
                    )
                    receipt = validate_registry(candidate)
                    if receipt.status.value == "rejected":
                        st.error(
                            f"Cannot add: {receipt.findings[0].message if receipt.findings else 'rejected'}"  # noqa: E501
                        )
                    else:
                        # Deduplicate identical
                        st.session_state["metric_contract_registry_payload"] = json.loads(
                            candidate.canonical_json()
                        )
                        st.success(
                            f"Added {draft_obj.metric_key} v{draft_obj.metric_version} to registry"
                        )
                        st.rerun()
            except (ValidationError, ValueError) as exc:
                st.error(f"Add failed: {exc}")
            except Exception as exc:
                st.error(f"Add failed: {exc}")
    with col_clear:
        if st.button("Clear draft", key="metric_contract_clear_draft"):
            st.session_state["metric_contract_draft"] = None
            st.rerun()

    st.divider()

    # ------------------------------------------------------------------
    # Validate conflicts and inspect built-in vs custom
    # ------------------------------------------------------------------
    st.subheader("Validate and inspect")
    if current_registry is None:
        st.info("Load or create a registry to inspect built-in versus custom contracts.")
    else:
        registry = current_registry
        receipt = validate_registry(registry)
        with st.container(border=True):
            st.markdown("**Validation findings**")
            if receipt.findings:
                for finding in receipt.findings:
                    if finding.severity.value == "error":
                        st.error(f"{finding.code}: {finding.message}")
                    elif finding.severity.value == "warning":
                        st.warning(f"{finding.code}: {finding.message}")
                    else:
                        st.info(f"{finding.code}: {finding.message}")
            else:
                st.success("No findings — registry is valid")
            st.caption(
                f"Status: {receipt.status.value} | Fingerprint: {receipt.registry_fingerprint[:16]}…"  # noqa: E501
            )

        # Built-in vs custom inspection
        st.markdown("**Built-in versus custom contracts**")
        st.caption("Built-in contracts are authoritative and cannot be silently overridden.")
        built_in = build_built_in_registry()
        built_in_keys = {c.metric_key for c in built_in.contracts}
        custom_contracts = [
            c for c in registry.deduplicated_contracts() if c.metric_key not in built_in_keys
        ]
        built_in_redundant = [
            c for c in registry.deduplicated_contracts() if c.metric_key in built_in_keys
        ]

        col_bi, col_cu = st.columns(2)
        with col_bi:
            st.metric("Built-in contracts (authoritative)", len(built_in.contracts), border=True)
            st.metric(
                "Registry references to built-in (redundant)", len(built_in_redundant), border=True
            )
        with col_cu:
            st.metric("Custom contracts", len(custom_contracts), border=True)
            st.metric("Total deduplicated", len(registry.deduplicated_contracts()), border=True)

        # Table for custom
        if custom_contracts:
            rows = [
                {
                    "metric_key": c.metric_key,
                    "metric_version": c.metric_version,
                    "unit": c.unit,
                    "denominator": c.denominator.value,
                    "description": c.description[:60],
                    "higher_is_better": str(c.higher_is_better)
                    if c.higher_is_better is not None
                    else (c.direction.value if c.direction else ""),
                    "contract_version": c.contract_version,
                }
                for c in sorted(custom_contracts, key=lambda x: (x.metric_key, x.metric_version))
            ]
            st.dataframe(
                rows, hide_index=True, width="stretch", column_config=table_column_config(rows)
            )
        else:
            st.info("No custom contracts yet — draft and add one above.")

        # Also show built-in table in expander
        with st.expander("Show authoritative built-in contracts"):
            bi_rows = [
                {
                    "metric_key": c.metric_key,
                    "metric_version": c.metric_version,
                    "unit": c.unit,
                    "denominator": c.denominator.value,
                }
                for c in sorted(built_in.contracts, key=lambda x: x.metric_key)
            ]
            st.dataframe(
                bi_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(bi_rows),
            )
            st.caption(
                "These 20 keys are the expected canonical contracts; custom must not conflict."
            )

        # Supersession lineage
        if registry.supersession:
            st.markdown("**Supersession lineage**")
            lineage_rows = [
                {
                    "predecessor": f"{s.predecessor_metric_key}:{s.predecessor_metric_version}",
                    "successor": f"{s.successor_metric_key}:{s.successor_metric_version}",
                    "reason": s.reason,
                }
                for s in sorted(
                    registry.supersession,
                    key=lambda x: (x.predecessor_metric_key, x.predecessor_metric_version),
                )
            ]
            st.dataframe(
                lineage_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(lineage_rows),
            )
        else:
            st.caption("No supersession lineage declared.")

    st.divider()

    # ------------------------------------------------------------------
    # Preview Resource Strategy compatibility
    # ------------------------------------------------------------------
    st.subheader("Preview Resource Strategy compatibility")
    st.caption(
        "Preview how a custom metric in a study becomes comparable only with a valid registry and arm agreement."  # noqa: E501
    )
    # Offer preview with synthetic study
    if st.button("Run preview with synthetic study", key="metric_contract_preview"):
        try:
            study = _synthetic_study_for_preview()
            # Without registry
            report_no_reg = build_resource_strategy_report(study)
            no_reg_compat = next(
                (c for c in report_no_reg.compatibility if c.metric_key == "custom.preview.metric"),
                None,
            )
            # With registry if available
            if current_registry is None:
                st.info(
                    "No registry loaded — custom preview metric will be UNAVAILABLE (expected)."
                )
                if no_reg_compat:
                    st.warning(
                        f"Without registry: {no_reg_compat.metric_key} → {no_reg_compat.status.value} ({no_reg_compat.finding})"  # noqa: E501
                    )
            else:
                report_with = build_resource_strategy_report(
                    study, metric_contract_registry=current_registry
                )
                with_compat = next(
                    (
                        c
                        for c in report_with.compatibility
                        if c.metric_key == "custom.preview.metric"
                    ),
                    None,
                )
                col_n, col_w = st.columns(2)
                with col_n:
                    st.markdown("**Without registry**")
                    if no_reg_compat:
                        st.code(
                            f"status: {no_reg_compat.status.value}\nfinding: {no_reg_compat.finding}"  # noqa: E501
                        )
                        if no_reg_compat.status.value != "unavailable":
                            st.error("Expected UNAVAILABLE without registry")
                        else:
                            st.success("Correctly UNAVAILABLE without registry")
                with col_w:
                    st.markdown("**With current registry**")
                    if with_compat:
                        st.code(
                            f"status: {with_compat.status.value}\nfinding: {with_compat.finding}"
                        )
                        # Check if registry contains the preview metric
                        has_preview = any(
                            c.metric_key == "custom.preview.metric"
                            for c in current_registry.deduplicated_contracts()
                        )
                        if has_preview:
                            if with_compat.status.value == "compatible":
                                st.success(
                                    "Custom metric became COMPATIBLE with valid registry and arm agreement"  # noqa: E501
                                )
                            elif with_compat.status.value == "incompatible":
                                st.warning(
                                    "Custom metric is INCOMPATIBLE — check unit/denominator or arm agreement"  # noqa: E501
                                )
                            else:
                                st.info("Still UNAVAILABLE — registry may not contain this metric")
                        else:
                            st.info(
                                "Registry does not contain custom.preview.metric — add it to make metric comparable"  # noqa: E501
                            )
                            if with_compat.status.value == "unavailable":
                                st.success("Correctly UNAVAILABLE (registry missing this key)")
                # Show arm aggregates for preview metric
                if (
                    current_registry is not None
                    and with_compat
                    and with_compat.status.value == "compatible"
                ):
                    for arm in report_with.arm_summaries:
                        agg = next(
                            (
                                a
                                for a in arm.metric_aggregates
                                if a.metric_key == "custom.preview.metric"
                            ),
                            None,
                        )
                        if agg:
                            st.caption(
                                f"Arm {arm.arm_id} aggregate mean: {agg.aggregate_mean} status {agg.status.value}"  # noqa: E501
                            )
                elif current_registry is not None:
                    # Show that incompatible leads to unavailable aggregates
                    for arm in report_with.arm_summaries:
                        agg = next(
                            (
                                a
                                for a in arm.metric_aggregates
                                if a.metric_key == "custom.preview.metric"
                            ),
                            None,
                        )
                        if agg and agg.status.value == "unavailable":
                            st.caption(
                                f"Arm {arm.arm_id} correctly UNAVAILABLE due to incompatibility"
                            )
                # Demonstrate arm mismatch using embedded declarations
                if current_registry is not None and any(
                    c.metric_key == "custom.preview.metric"
                    for c in current_registry.deduplicated_contracts()
                ):
                    study_ok = _synthetic_study_for_preview(
                        include_declarations=True, arm_b_unit="ratio"
                    )
                    study_bad = _synthetic_study_for_preview(
                        include_declarations=True, arm_b_unit="ms"
                    )
                    report_ok = build_resource_strategy_report(
                        study_ok,
                        metric_contract_registry=current_registry,
                    )
                    compat_ok = next(
                        (
                            c
                            for c in report_ok.compatibility
                            if c.metric_key == "custom.preview.metric"
                        ),
                        None,
                    )
                    report_bad = build_resource_strategy_report(
                        study_bad,
                        metric_contract_registry=current_registry,
                    )
                    compat_bad = next(
                        (
                            c
                            for c in report_bad.compatibility
                            if c.metric_key == "custom.preview.metric"
                        ),
                        None,
                    )
                    st.markdown("**Cross-arm consistency check (embedded declarations)**")
                    if compat_ok:
                        st.caption(
                            f"Both arms agree on unit → {compat_ok.status.value} ({compat_ok.finding[:60]})"  # noqa: E501
                        )
                    if compat_bad:
                        if compat_bad.status.value == "incompatible":
                            st.success(
                                f"One arm changes unit → correctly INCOMPATIBLE: {compat_bad.finding[:80]}"  # noqa: E501
                            )
                        else:
                            st.error(
                                f"Arm unit mismatch should be INCOMPATIBLE but got {compat_bad.status.value}"  # noqa: E501
                            )
                    # Also demonstrate missing declaration case
                    study_missing = _synthetic_study_for_preview(include_declarations=False)
                    report_missing = build_resource_strategy_report(
                        study_missing,
                        metric_contract_registry=current_registry,
                    )
                    compat_missing = next(
                        (
                            c
                            for c in report_missing.compatibility
                            if c.metric_key == "custom.preview.metric"
                        ),
                        None,
                    )
                    if compat_missing and compat_missing.status.value == "unavailable":
                        st.info(
                            "Missing arm declarations → correctly UNAVAILABLE: "
                            "per-arm declaration unavailable"
                        )

        except Exception as exc:
            st.error(f"Preview failed: {exc}")

    # Also allow uploading a study JSON for preview
    st.caption(
        "Optionally upload a Resource Strategy study JSON to preview with current registry (not required)."  # noqa: E501
    )
    study_upload = st.file_uploader(
        "Upload Resource Strategy study JSON for compatibility preview",
        type=["json"],
        key="metric_contract_study_preview_uploader",
    )
    if study_upload is not None:
        try:
            text = study_upload.getvalue().decode("utf-8")
            study_dict = json.loads(text)
            study = ResourceStrategyStudy.model_validate(study_dict)
            if current_registry is None:
                report = build_resource_strategy_report(study)
                st.info("No registry — custom metrics will be UNAVAILABLE")
            else:
                report = build_resource_strategy_report(
                    study, metric_contract_registry=current_registry
                )
            # Show compatibility table
            comp_rows = [
                {
                    "metric_key": c.metric_key,
                    "status": c.status.value,
                    "unit": c.unit or "",
                    "denominator": c.denominator.value if c.denominator else "",
                    "finding": c.finding[:100],
                }
                for c in sorted(report.compatibility, key=lambda x: x.metric_key)
            ]
            st.dataframe(
                comp_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(comp_rows),
            )
            st.caption(f"Report fingerprint: {fingerprint_summary(report.report_fingerprint)}")
        except Exception as exc:
            st.error(f"Study preview failed: {exc}")

    st.divider()

    # ------------------------------------------------------------------
    # Download deterministic artifacts
    # ------------------------------------------------------------------
    st.subheader("Download deterministic artifacts")
    st.caption(
        "Exports are deterministic: sorted keys, canonical JSON, stable fingerprint, no path contamination."  # noqa: E501
    )
    if current_registry is None:
        st.info("No registry to export — create or load one first.")
    else:
        registry = current_registry
        col_j, col_c = st.columns(2)
        with col_j:
            st.download_button(
                "Download registry JSON",
                data=registry_to_json(registry),
                file_name="metric_contract_registry.json",
                mime="application/json",
                key="metric_contract_download_json",
            )
            st.caption(f"JSON fingerprint: `{registry.fingerprint()}`")
            st.code(registry.canonical_json()[:400] + "…", language="json")
        with col_c:
            st.download_button(
                "Download registry CSV",
                data=registry_to_csv(registry),
                file_name="metric_contract_registry.csv",
                mime="text/csv",
                key="metric_contract_download_csv",
            )
            csv_text = registry_to_csv(registry)
            lines = csv_text.splitlines()
            st.caption(f"CSV rows: {len(lines) - 1} contracts")
            if len(lines) > 1:
                st.code("\n".join(lines[:5]), language="csv")
        st.caption(
            "Registration does not implement metric computation — contracts are metadata only."
        )

    # Footer authority
    st.divider()
    st.caption(
        "Authority: built-in metric contracts remain authoritative; custom registry is closed and validated. No executable code is stored or run."  # noqa: E501
    )
