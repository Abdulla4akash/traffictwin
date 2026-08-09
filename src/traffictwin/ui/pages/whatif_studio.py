"""What-If Studio — one-click deterministic baseline/variation pair orchestration (V2-S1)."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from traffictwin.synthetic.config import SyntheticPolicyProfile
from traffictwin.synthetic.whatif_pair import (
    STUDIO_EVIDENCE_SENTENCE,
    receipt_to_portable_dict,
)
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.demo_workspace_service import resolve_effective_demo_paths
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    WhatIfPairRequest,
    WhatIfVariationOverrides,
    generate_whatif_pair_for_ui,
    preview_whatif_ledger_for_ui,
    synthetic_policy_options_for_ui,
    synthetic_preset_names_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import table_column_config


def render(config: UiConfig) -> None:
    render_page_header(st.session_state.get("_active_ui_page", UiPage.WHATIF_STUDIO))
    badge_row(["SYNTHETIC", "DETERMINISTIC", "LOCAL", "NOT_MANCHESTER"])
    st.info(STUDIO_EVIDENCE_SENTENCE)
    st.caption(
        "This studio generates a deterministic synthetic baseline and intervention through "
        "TrafficTwin's local generator. It does not run SUMO, VEC, a provider feed or an "
        "admitted research campaign. "
        "Every surface is labelled synthetic and not Manchester observation, not a live "
        "traffic forecast, not SUMO or VEC execution, not research admission."
    )
    with st.container(border=True):
        st.markdown(
            f"{badge_markdown('synthetic')} **What-If Studio** creates validated "
            "baseline/variation bundles, registers the pair, and continues to Compare. "
            f"{badge_markdown('draft')} **Platform → What-If Composer** predicts from "
            "bounded existing fits and drafts unsigned research campaigns; it cannot "
            "approve or execute campaigns."
        )
        st.caption(
            "Do not confuse these pages: Studio is deterministic local synthetic generation "
            "(software evidence); Composer is prediction from a surrogate fit plus draft campaign."
        )

    workspace, registry = resolve_effective_demo_paths(config)
    effective_workspace_path = workspace
    effective_registry_path = registry

    st.caption(
        f"Active workspace: `{effective_workspace_path}` | Registry: `{effective_registry_path}`"
    )

    # Single form for all inputs — one authoritative value flow, no session_state read
    with st.form("whatif_form"):
        section_header("Stage 1 · choose baseline", "Existing supported synthetic preset.")
        presets = synthetic_preset_names_for_ui()
        baseline_preset = st.selectbox("Baseline preset", presets, index=0)
        st.caption(
            f"Baseline preset `{baseline_preset}` is a deterministic synthetic "
            "starting point. Nothing is executed yet."
        )

        section_header("Pair identity", "Stable pair identifier and experiment grouping.")
        cols = st.columns(2)
        pair_name = cols[0].text_input(
            "Pair name (sanitised, e.g. congestion-pulse)", value="congestion-pulse"
        )
        experiment_id = cols[1].text_input("Experiment ID", value="exp-whatif-demo")
        baseline_seed = st.number_input("Baseline random seed", min_value=0, value=7, step=1)

        section_header(
            "Stage 2 · define variation",
            "Closed intervention set; unchanged fields remain byte-consistent "
            "where the generator permits.",
        )
        st.caption(
            "Edit a small closed set of intervention parameters. Only changed "
            "fields will appear in the ledger."
        )

        st.markdown("**Incident / event**")
        c1, c2, c3, c4 = st.columns(4)
        incident_enabled = c1.checkbox("Enable synthetic incident/event", value=True)
        incident_type = c2.text_input("Event type", value="synthetic_congestion_pulse")
        incident_location = c3.text_input("Location", value="synthetic-corridor-a")
        incident_severity = c4.text_input("Severity", value="moderate")
        c1, c2, c3, c4 = st.columns(4)
        incident_start = c1.number_input("Start time (s)", min_value=0.0, value=120.0)
        incident_duration = c2.number_input("Duration (s)", min_value=1.0, value=60.0)
        lanes_closed = c3.number_input("Lanes closed", min_value=0, value=1, step=1)
        event_demand_multiplier = c4.number_input(
            "Event demand multiplier", min_value=0.1, value=1.3, step=0.1
        )

        st.markdown("**Demand / congestion**")
        c1, c2, c3 = st.columns(3)
        congestion_multiplier = c1.number_input(
            "Congestion multiplier", min_value=0.25, max_value=3.0, value=1.65, step=0.05
        )
        vehicle_count = c2.number_input("Vehicle count", min_value=1, value=20, step=1)
        task_arrival_rate = c3.number_input(
            "Task arrival rate", min_value=0.001, value=0.18, step=0.01, format="%.3f"
        )

        st.markdown("**Task mix (must sum to 1.0)**")
        c1, c2, c3 = st.columns(3)
        task_t1 = c1.number_input("T1 share", min_value=0.0, max_value=1.0, value=0.30, step=0.05)
        task_t2 = c2.number_input("T2 share", min_value=0.0, max_value=1.0, value=0.40, step=0.05)
        task_t3 = c3.number_input("T3 share", min_value=0.0, max_value=1.0, value=0.30, step=0.05)

        st.markdown("**Infrastructure / policy**")
        c1, c2, c3 = st.columns(3)
        rsu_count = c1.number_input("RSU count", min_value=1, value=2, step=1)
        rsu_capacity = c2.number_input("RSU capacity", min_value=1.0, value=22.0)
        policy_options = synthetic_policy_options_for_ui()
        policy_profile = c3.selectbox(
            "Synthetic policy profile",
            policy_options,
            index=policy_options.index(SyntheticPolicyProfile.BALANCED.value)
            if SyntheticPolicyProfile.BALANCED.value in policy_options
            else 0,
        )

        # Two submit buttons operating on the same current form values
        cols = st.columns(2)
        preview_submitted = cols[0].form_submit_button("Preview changed ledger")
        generate_submitted = cols[1].form_submit_button("Generate comparison")

    # Build request directly from widget return values (single source of truth)
    def _build_request() -> WhatIfPairRequest | ServiceError:
        try:
            overrides = WhatIfVariationOverrides(
                incident_enabled=bool(incident_enabled),
                incident_type=str(incident_type),
                incident_location=str(incident_location),
                incident_severity=str(incident_severity),
                incident_start_s=float(incident_start),
                incident_duration_s=float(incident_duration),
                lanes_closed=int(lanes_closed),
                event_demand_multiplier=float(event_demand_multiplier),
                congestion_multiplier=float(congestion_multiplier),
                vehicle_count=int(vehicle_count),
                task_arrival_rate=float(task_arrival_rate),
                task_mix_t1=float(task_t1),
                task_mix_t2=float(task_t2),
                task_mix_t3=float(task_t3),
                rsu_count=int(rsu_count),
                rsu_capacity=float(rsu_capacity),
                policy_profile=str(policy_profile),
            )
            return WhatIfPairRequest(
                baseline_preset=str(baseline_preset),
                pair_name=str(pair_name),
                experiment_id=str(experiment_id),
                baseline_random_seed=int(baseline_seed),
                variation_overrides=overrides,
                output_root=None,
            )
        except Exception as exc:
            return ServiceError("What-if request is invalid.", str(exc))

    request = _build_request()
    if isinstance(request, ServiceError):
        st.error(request.message)
        if request.detail:
            st.code(request.detail)
        return

    # Stage 3: changed-parameter ledger preview (always based on current submitted values)
    section_header(
        "Stage 3 · review changed parameters",
        "Deterministic ledger: every meaningful change, ordered, no unchanged rows, no LLM prose.",
    )
    ledger = preview_whatif_ledger_for_ui(request)
    if isinstance(ledger, ServiceError):
        st.error(ledger.message)
        if ledger.detail:
            st.code(ledger.detail)
        st.warning(
            "Baseline and variation would be identical, or request is invalid. "
            "Generation is refused."
        )
        can_generate = False
    else:
        if not ledger:
            st.warning(
                "No meaningful field changed — baseline and variation would be "
                "identical. Change at least one intervention before generating."
            )
            can_generate = False
        else:
            st.success(f"{len(ledger)} changed field(s) — preview is deterministic and ordered.")
            rows = [
                {
                    "field_path": p.field_path,
                    "baseline": str(p.baseline_value),
                    "variation": str(p.variation_value),
                    "unit": p.unit or "",
                    "label": p.semantic_label or "",
                }
                for p in ledger
            ]
            st.dataframe(
                rows, hide_index=True, width="stretch", column_config=table_column_config(rows)
            )
            with st.expander("Advanced: ledger JSON"):
                st.json([p.model_dump(mode="json") for p in ledger])
            st.download_button(
                "Download changed ledger JSON",
                data=json.dumps(
                    [p.model_dump(mode="json") for p in ledger], indent=2, sort_keys=True
                ),
                file_name="whatif_changed_ledger.json",
                mime="application/json",
            )
            can_generate = True

    # Stage 4: generate (uses same submitted values; no stale read)
    section_header(
        "Stage 4 · generate comparison",
        "Stages and validates both bundles, publishes only when the complete pair "
        "succeeds, registers both, sets selected paths.",
    )
    st.caption(
        "One click generates the complete pair. No manual import, no YAML "
        "editing, no terminal, no restart."
    )

    # Handle Generate submission from the same form
    if generate_submitted:
        if not can_generate:
            st.error(
                "No meaningful field changed — baseline and variation would be "
                "identical. Change at least one intervention before generating."
            )
        else:
            workspace_path = effective_workspace_path
            registry_path = effective_registry_path
            if workspace_path is None:
                try:
                    workspace_path = (
                        Path(registry_path).parent.parent
                        if Path(registry_path).name == "registry.sqlite"
                        else Path(registry_path).parent
                    )
                except Exception:
                    workspace_path = None
            result = generate_whatif_pair_for_ui(
                request, registry_path=registry_path, workspace_path=workspace_path
            )
            if isinstance(result, ServiceError):
                st.error(result.message)
                if result.detail:
                    st.code(result.detail)
                st.session_state.pop("whatif_pair_receipt", None)
                st.session_state.pop("whatif_pair_success", None)
            else:
                st.session_state["whatif_pair_receipt"] = result.model_dump(mode="json")
                st.session_state["whatif_pair_success"] = True
                st.session_state["selected_bundle_path"] = result.baseline_bundle_path or str(
                    workspace_path
                )
                st.session_state["selected_baseline_run"] = result.baseline_bundle_path or ""
                st.session_state["selected_variation_run"] = result.variation_bundle_path or ""
                st.session_state["whatif_pair_receipt_path"] = result.receipt_path or ""
                st.rerun()

    # Also handle preview submission feedback (ledger already shown above, no extra action needed)
    if preview_submitted and can_generate:
        st.info("Ledger preview updated from current form values.")

    # Success state display (survives reruns)
    receipt_raw = st.session_state.get("whatif_pair_receipt")
    if receipt_raw:
        try:
            from traffictwin.synthetic.whatif_pair import WhatIfPairReceipt as _Receipt

            receipt = _Receipt.model_validate(receipt_raw)
        except Exception:
            receipt = None
        if receipt is not None:
            status_label = "already exists" if receipt.status == "already_exists" else "generated"
            st.success(
                f"What-if pair {status_label}: `{receipt.pair_id}` · "
                f"request fingerprint `{receipt.request_fingerprint[:12]}`"
            )
            with st.container(border=True):
                st.markdown(f"{badge_markdown('synthetic')} **Pair receipt** · `{receipt.pair_id}`")
                cols = st.columns(3)
                cols[0].metric("Experiment", receipt.experiment_id)
                cols[1].metric("Baseline scenario", receipt.baseline_scenario_id)
                cols[2].metric("Variation scenario", receipt.variation_scenario_id)
                cols2 = st.columns(3)
                cols2[0].metric("Baseline bundle", receipt.baseline_bundle_id or "—")
                cols2[1].metric("Variation bundle", receipt.variation_bundle_id or "—")
                cols2[2].metric("Validation", receipt.validation_standing)
                st.caption(f"Baseline path: `{receipt.baseline_bundle_path}`")
                st.caption(f"Variation path: `{receipt.variation_bundle_path}`")
                st.caption(
                    f"Pair fingerprint: `{receipt.pair_fingerprint[:12]}` · "
                    f"Synthetic: {', '.join(receipt.evidence_labels[:3])}"
                )
                st.caption(STUDIO_EVIDENCE_SENTENCE)
                if receipt.warnings:
                    st.warning("\n".join(receipt.warnings))
                if receipt.changed_parameters:
                    st.markdown("**Changed-parameter ledger (from receipt)**")
                    rows = [
                        {
                            "field_path": p.field_path,
                            "baseline": str(p.baseline_value),
                            "variation": str(p.variation_value),
                        }
                        for p in receipt.changed_parameters
                    ]
                    st.dataframe(
                        rows,
                        hide_index=True,
                        width="stretch",
                        column_config=table_column_config(rows),
                    )
                with st.expander("Advanced: full receipt JSON"):
                    st.json(receipt.model_dump(mode="json"))
                # Portable download must not expose absolute local paths
                portable_receipt = receipt_to_portable_dict(
                    receipt,
                    workspace_path=Path(effective_workspace_path)
                    if effective_workspace_path
                    else None,
                )
                st.download_button(
                    "Download pair receipt JSON",
                    data=json.dumps(portable_receipt, indent=2, sort_keys=True),
                    file_name=f"{receipt.pair_id}_receipt.json",
                    mime="application/json",
                )
                st.download_button(
                    "Download ledger JSON",
                    data=json.dumps(
                        [p.model_dump(mode="json") for p in receipt.changed_parameters],
                        indent=2,
                        sort_keys=True,
                    ),
                    file_name=f"{receipt.pair_id}_ledger.json",
                    mime="application/json",
                )
            st.info(
                "Next: open Compare to inspect deterministic comparable output, "
                "or inspect either Run Overview. Compare will be pre-filled "
                "with this pair."
            )
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Open Compare (pre-filled)", key="whatif_open_compare"):
                    st.session_state["selected_baseline_run"] = receipt.baseline_bundle_path or ""
                    st.session_state["selected_variation_run"] = receipt.variation_bundle_path or ""
                    st.success(
                        "Compare paths set. Use sidebar → Compare & test → "
                        "Comparison to view results."
                    )
            with c2:
                if st.button("Inspect baseline Run Overview", key="whatif_inspect_baseline"):
                    st.session_state["selected_bundle_path"] = receipt.baseline_bundle_path or ""
                    st.success("Baseline selected. Use Results → Run Overview to inspect.")
            with c3:
                if st.button("Inspect variation Run Overview", key="whatif_inspect_variation"):
                    st.session_state["selected_bundle_path"] = receipt.variation_bundle_path or ""
                    st.success("Variation selected. Use Results → Run Overview to inspect.")
