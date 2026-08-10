"""What-If Studio — one-click deterministic baseline/variation pair orchestration (V2-S1)."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from traffictwin.synthetic.whatif_pair import (
    STUDIO_EVIDENCE_SENTENCE,
    receipt_to_portable_dict,
)
from traffictwin.ui.challenge_whatif_bridge import (
    PENDING_WHATIF_CHALLENGE_DRAFT_KEY,
    ChallengeWhatIfDraft,
    draft_from_handoff_dict,
    is_valid_handoff_dict,
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
from traffictwin.ui.whatif_controls import (
    DEFAULT_WHATIF_WIDGET_VALUES,
    WHATIF_CONTROL_SPEC,
    WHATIF_WIDGET_KEYS,
)


def _ensure_whatif_widget_defaults() -> None:
    for key, default in DEFAULT_WHATIF_WIDGET_VALUES.items():
        if key not in st.session_state:
            # Deep-copy mutable defaults (no mutable containers currently, but guard future)
            import copy

            st.session_state[key] = copy.deepcopy(default)


def _reset_whatif_widgets_to_defaults() -> None:
    """Reset the complete What-If control set to authoritative stock defaults."""
    import copy

    for key, default in DEFAULT_WHATIF_WIDGET_VALUES.items():
        st.session_state[key] = copy.deepcopy(default)


def _seed_widgets_from_draft(draft: ChallengeWhatIfDraft) -> None:
    ov = draft.whatif_overrides
    mapping = {
        "congestion_multiplier": WHATIF_WIDGET_KEYS["congestion_multiplier"],
        "task_arrival_rate": WHATIF_WIDGET_KEYS["task_arrival_rate"],
        "vehicle_count": WHATIF_WIDGET_KEYS["vehicle_count"],
        "rsu_count": WHATIF_WIDGET_KEYS["rsu_count"],
        "rsu_capacity": WHATIF_WIDGET_KEYS["rsu_capacity"],
        "random_seed": WHATIF_WIDGET_KEYS["random_seed"],
        "incident_type": WHATIF_WIDGET_KEYS["incident_type"],
        "incident_location": WHATIF_WIDGET_KEYS["incident_location"],
        "incident_start_s": WHATIF_WIDGET_KEYS["incident_start_s"],
        "incident_duration_s": WHATIF_WIDGET_KEYS["incident_duration_s"],
        "lanes_closed": WHATIF_WIDGET_KEYS["lanes_closed"],
        "event_demand_multiplier": WHATIF_WIDGET_KEYS["event_demand_multiplier"],
        "incident_enabled": WHATIF_WIDGET_KEYS["incident_enabled"],
    }
    for field, widget_key in mapping.items():
        if field in ov:
            st.session_state[widget_key] = ov[field]
    if "task_mix_t1" in ov:
        st.session_state[WHATIF_WIDGET_KEYS["task_mix_t1"]] = ov["task_mix_t1"]
    if "task_mix_t2" in ov:
        st.session_state[WHATIF_WIDGET_KEYS["task_mix_t2"]] = ov["task_mix_t2"]
    if "task_mix_t3" in ov:
        st.session_state[WHATIF_WIDGET_KEYS["task_mix_t3"]] = ov["task_mix_t3"]
    # Policy profile text if ever mapped (not currently)
    if "policy_profile" in ov:
        st.session_state[WHATIF_WIDGET_KEYS["policy_profile"]] = ov["policy_profile"]


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

    # --- Ensure defaults and challenge prefill (stable keyed widget state) ---
    _ensure_whatif_widget_defaults()

    pending_raw = st.session_state.get(PENDING_WHATIF_CHALLENGE_DRAFT_KEY)
    challenge_draft: ChallengeWhatIfDraft | None = None
    if pending_raw is not None and is_valid_handoff_dict(pending_raw):
        try:
            challenge_draft = draft_from_handoff_dict(pending_raw)
        except Exception:  # noqa: BLE001 - defensive handoff parse
            challenge_draft = None

    # Apply prefill exactly once per draft fingerprint — full reset then overlay
    applied_fp = st.session_state.get("whatif_challenge_prefill_applied_fingerprint")
    if challenge_draft is not None and applied_fp != challenge_draft.fingerprint:
        _reset_whatif_widgets_to_defaults()
        _seed_widgets_from_draft(challenge_draft)
        st.session_state["whatif_challenge_prefill_applied_fingerprint"] = (
            challenge_draft.fingerprint
        )
        st.session_state["whatif_challenge_prefill_applied"] = True

    if challenge_draft is not None:
        with st.container(border=True):
            st.markdown(
                f"**Prepared from {challenge_draft.challenge_id} — "
                f"{challenge_draft.challenge_title}**"
            )
            st.markdown(f"Status: `{challenge_draft.mapping_status.value}`")
            st.caption(
                f"Supported in What-If Studio: {len(challenge_draft.supported_fields)} · "
                f"Not represented by current What-If controls: "
                f"{len(challenge_draft.unsupported_fields)}"
            )
            if challenge_draft.supported_fields:
                st.markdown("**Applied automatically:**")
                for fld in challenge_draft.supported_fields:
                    st.caption(
                        f"`{fld.challenge_path}` → `{fld.whatif_field}` = "
                        f"`{fld.mapped_value}` — {fld.rationale}"
                    )
            if challenge_draft.unsupported_fields:
                st.markdown("**Not applied — unsupported by current What-If controls:**")
                for ufld in challenge_draft.unsupported_fields:
                    st.caption(
                        f"`{ufld.challenge_path}` = `{ufld.challenge_value}` — {ufld.reason}"
                    )
                st.warning(
                    "Only the supported subset will be prefilled. "
                    "The generated What-If pair must not be interpreted as exact "
                    "execution of the original challenge."
                )
            for w in challenge_draft.warnings:
                st.caption(f"Bridge: {w}")
            st.caption(
                "Challenge parameters are applied as intervention inputs against the "
                "baseline preset you choose."
            )
            st.caption("Unmapped controls keep ordinary What-If Studio defaults.")
            st.caption("The actual generated ledger is authoritative.")
            st.caption(f"Bridge fingerprint: `{challenge_draft.fingerprint[:12]}`")
            if st.button("Reset to stock defaults", key="whatif_clear_challenge_prefill"):
                st.session_state.pop(PENDING_WHATIF_CHALLENGE_DRAFT_KEY, None)
                st.session_state["whatif_challenge_prefill_applied_fingerprint"] = None
                st.session_state["whatif_challenge_prefill_applied"] = False
                _reset_whatif_widgets_to_defaults()
                st.rerun()

    # Single form — keyed widgets, no redundant value= (session_state is truth)
    # Ensure preset/policy validity before widget creation
    presets = synthetic_preset_names_for_ui()
    if st.session_state[WHATIF_WIDGET_KEYS["baseline_preset"]] not in presets:
        st.session_state[WHATIF_WIDGET_KEYS["baseline_preset"]] = presets[0]
    policy_options = synthetic_policy_options_for_ui()
    if st.session_state[WHATIF_WIDGET_KEYS["policy_profile"]] not in policy_options:
        st.session_state[WHATIF_WIDGET_KEYS["policy_profile"]] = policy_options[0]
    with st.form("whatif_form"):
        section_header("Stage 1 · choose baseline", "Existing supported synthetic preset.")
        baseline_preset = st.selectbox(
            "Baseline preset",
            presets,
            key=WHATIF_WIDGET_KEYS["baseline_preset"],
        )
        st.caption(
            f"Baseline preset `{st.session_state[WHATIF_WIDGET_KEYS['baseline_preset']]}` "
            "is a deterministic synthetic starting point. Nothing is executed yet."
        )

        section_header("Pair identity", "Stable pair identifier and experiment grouping.")
        cols = st.columns(2)
        pair_name = cols[0].text_input(
            "Pair name (sanitised, e.g. congestion-pulse)",
            key=WHATIF_WIDGET_KEYS["pair_name"],
        )
        experiment_id = cols[1].text_input(
            "Experiment ID",
            key=WHATIF_WIDGET_KEYS["experiment_id"],
        )
        baseline_seed = st.number_input(
            "Baseline random seed",
            min_value=WHATIF_CONTROL_SPEC["baseline_random_seed"]["min"],
            step=1,
            key=WHATIF_WIDGET_KEYS["baseline_random_seed"],
        )

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
        incident_enabled = c1.checkbox(
            "Enable synthetic incident/event",
            key=WHATIF_WIDGET_KEYS["incident_enabled"],
        )
        incident_type = c2.text_input(
            "Event type",
            key=WHATIF_WIDGET_KEYS["incident_type"],
        )
        incident_location = c3.text_input(
            "Location",
            key=WHATIF_WIDGET_KEYS["incident_location"],
        )
        incident_severity = c4.text_input(
            "Severity",
            key=WHATIF_WIDGET_KEYS["incident_severity"],
        )
        c1, c2, c3, c4 = st.columns(4)
        incident_start = c1.number_input(
            "Start time (s)",
            min_value=float(WHATIF_CONTROL_SPEC["incident_start_s"]["min"]),
            key=WHATIF_WIDGET_KEYS["incident_start_s"],
        )
        incident_duration = c2.number_input(
            "Duration (s)",
            min_value=float(WHATIF_CONTROL_SPEC["incident_duration_s"]["min"]),
            key=WHATIF_WIDGET_KEYS["incident_duration_s"],
        )
        lanes_closed = c3.number_input(
            "Lanes closed",
            min_value=int(WHATIF_CONTROL_SPEC["lanes_closed"]["min"]),
            step=1,
            key=WHATIF_WIDGET_KEYS["lanes_closed"],
        )
        event_demand_multiplier = c4.number_input(
            "Event demand multiplier",
            min_value=float(WHATIF_CONTROL_SPEC["event_demand_multiplier"]["min"]),
            step=float(WHATIF_CONTROL_SPEC["event_demand_multiplier"]["step"] or 0.1),
            key=WHATIF_WIDGET_KEYS["event_demand_multiplier"],
        )

        st.markdown("**Demand / congestion**")
        c1, c2, c3 = st.columns(3)
        congestion_multiplier = c1.number_input(
            "Congestion multiplier",
            min_value=float(WHATIF_CONTROL_SPEC["congestion_multiplier"]["min"]),
            max_value=float(WHATIF_CONTROL_SPEC["congestion_multiplier"]["max"]),
            step=float(WHATIF_CONTROL_SPEC["congestion_multiplier"]["step"] or 0.05),
            key=WHATIF_WIDGET_KEYS["congestion_multiplier"],
        )
        vehicle_count = c2.number_input(
            "Vehicle count",
            min_value=int(WHATIF_CONTROL_SPEC["vehicle_count"]["min"]),
            step=1,
            key=WHATIF_WIDGET_KEYS["vehicle_count"],
        )
        task_arrival_rate = c3.number_input(
            "Task arrival rate",
            min_value=float(WHATIF_CONTROL_SPEC["task_arrival_rate"]["min"]),
            step=float(WHATIF_CONTROL_SPEC["task_arrival_rate"]["step"] or 0.01),
            format="%.3f",
            key=WHATIF_WIDGET_KEYS["task_arrival_rate"],
        )

        st.markdown("**Task mix (must sum to 1.0)**")
        c1, c2, c3 = st.columns(3)
        task_t1 = c1.number_input(
            "T1 share",
            min_value=float(WHATIF_CONTROL_SPEC["task_mix_t1"]["min"]),
            max_value=float(WHATIF_CONTROL_SPEC["task_mix_t1"]["max"]),
            step=float(WHATIF_CONTROL_SPEC["task_mix_t1"]["step"] or 0.05),
            key=WHATIF_WIDGET_KEYS["task_mix_t1"],
        )
        task_t2 = c2.number_input(
            "T2 share",
            min_value=float(WHATIF_CONTROL_SPEC["task_mix_t2"]["min"]),
            max_value=float(WHATIF_CONTROL_SPEC["task_mix_t2"]["max"]),
            step=float(WHATIF_CONTROL_SPEC["task_mix_t2"]["step"] or 0.05),
            key=WHATIF_WIDGET_KEYS["task_mix_t2"],
        )
        task_t3 = c3.number_input(
            "T3 share",
            min_value=float(WHATIF_CONTROL_SPEC["task_mix_t3"]["min"]),
            max_value=float(WHATIF_CONTROL_SPEC["task_mix_t3"]["max"]),
            step=float(WHATIF_CONTROL_SPEC["task_mix_t3"]["step"] or 0.05),
            key=WHATIF_WIDGET_KEYS["task_mix_t3"],
        )

        st.markdown("**Infrastructure / policy**")
        c1, c2, c3 = st.columns(3)
        rsu_count = c1.number_input(
            "RSU count",
            min_value=int(WHATIF_CONTROL_SPEC["rsu_count"]["min"]),
            step=1,
            key=WHATIF_WIDGET_KEYS["rsu_count"],
        )
        rsu_capacity = c2.number_input(
            "RSU capacity",
            min_value=float(WHATIF_CONTROL_SPEC["rsu_capacity"]["min"]),
            key=WHATIF_WIDGET_KEYS["rsu_capacity"],
        )
        policy_profile = c3.selectbox(
            "Synthetic policy profile",
            policy_options,
            key=WHATIF_WIDGET_KEYS["policy_profile"],
        )

        # Two submit buttons operating on the same current form values
        cols = st.columns(2)
        preview_submitted = cols[0].form_submit_button("Preview changed ledger")
        generate_submitted = cols[1].form_submit_button("Generate comparison")

    # Build request from widget return values (post-form, reflect session_state)
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
                # Capture generation-bound challenge context (HIGH-2)
                gen_context: dict[str, object] | None = None
                if (
                    challenge_draft is not None
                    and st.session_state.get("whatif_challenge_prefill_applied_fingerprint")
                    == challenge_draft.fingerprint
                ):
                    # Check if user edited after prefill
                    drafted = challenge_draft.whatif_overrides
                    actual = request.variation_overrides.model_dump(exclude_none=True)
                    # Compare drafted fields to actual; any mismatch = user edited
                    edited = False
                    for k, v in drafted.items():
                        if k not in actual:
                            edited = True
                            break
                        av = actual.get(k)
                        # float tolerance
                        if isinstance(v, float) and isinstance(av, float):
                            if abs(float(v) - float(av)) > 1e-9:
                                edited = True
                                break
                        elif v != av:
                            edited = True
                            break
                    gen_context = {
                        "challenge_id": challenge_draft.challenge_id,
                        "challenge_title": challenge_draft.challenge_title,
                        "challenge_fingerprint": challenge_draft.fingerprint,
                        "mapping_status": challenge_draft.mapping_status.value,
                        "supported_count": len(challenge_draft.supported_fields),
                        "unsupported_count": len(challenge_draft.unsupported_fields),
                        "pair_id": result.pair_id,
                        "request_fingerprint": result.request_fingerprint,
                        "user_edited": edited,
                    }
                else:
                    gen_context = None
                st.session_state["last_whatif_generation_challenge_context"] = gen_context
                st.rerun()

    # Also handle preview submission feedback (ledger already shown above, no extra action needed)
    if preview_submitted and can_generate:
        st.info("Ledger preview updated from current form values.")

    # Show challenge source vs actual ledger distinction before generation
    if challenge_draft is not None and can_generate:
        st.info(
            "Challenge source fields above are separate from the actual What-If "
            "changed-parameter ledger below. Only the ledger determines what will be "
            "generated."
        )

    # Success state display (survives reruns)
    receipt_raw = st.session_state.get("whatif_pair_receipt")
    if receipt_raw:
        try:
            from traffictwin.synthetic.whatif_pair import WhatIfPairReceipt as _Receipt

            receipt = _Receipt.model_validate(receipt_raw)
        except Exception:  # noqa: BLE001 - defensive receipt parse
            receipt = None
        if receipt is not None:
            status_label = "already exists" if receipt.status == "already_exists" else "generated"
            # Generation-bound provenance (HIGH-2): read captured context, not current draft
            gen_ctx = st.session_state.get("last_whatif_generation_challenge_context")
            _challenge_note = ""
            _challenge_for_receipt: ChallengeWhatIfDraft | dict[str, object] | None = None
            # Only show challenge wording when context belongs to this receipt
            if (
                isinstance(gen_ctx, dict)
                and gen_ctx.get("pair_id") == receipt.pair_id
                and gen_ctx.get("challenge_id")
            ):
                cid = str(gen_ctx.get("challenge_id"))
                mapped = int(gen_ctx.get("supported_count") or 0)
                unsup = int(gen_ctx.get("unsupported_count") or 0)
                edited = bool(gen_ctx.get("user_edited"))
                if unsup > 0:
                    if edited:
                        _challenge_note = (
                            f" Started from the supported subset of {cid} "
                            f"({mapped} mapped, {unsup} unsupported); "
                            f"user-editable What-If values and the generated "
                            f"ledger are authoritative. "
                            f"This must not be interpreted as exact execution of {cid}."
                        )
                    else:
                        _challenge_note = (
                            f" Generated from the supported subset of {cid} "
                            f"({mapped} mapped, {unsup} unsupported). "
                            f"This must not be interpreted as exact execution of {cid}."
                        )
                else:
                    if edited:
                        _challenge_note = (
                            f" Started from the supported {cid} prefill "
                            f"({mapped} field(s)); user-editable What-If values and the "
                            f"generated ledger are authoritative."
                        )
                    else:
                        _challenge_note = f" Generated from supported fields of {cid}."
                _challenge_for_receipt = gen_ctx  # truthy marker
            st.success(
                f"What-if pair {status_label}: `{receipt.pair_id}` · "
                f"request fingerprint `{receipt.request_fingerprint[:12]}`"
                + (_challenge_note or "")
            )
            if _challenge_note and isinstance(gen_ctx, dict):
                cid = str(gen_ctx.get("challenge_id"))
                mapped = int(gen_ctx.get("supported_count") or 0)
                unsup = int(gen_ctx.get("unsupported_count") or 0)
                edited = bool(gen_ctx.get("user_edited"))
                if unsup > 0:
                    if edited:
                        st.warning(
                            f"Started from the supported subset of {cid} — "
                            f"{mapped} field(s) mapped, {unsup} field(s) not "
                            f"representable by current What-If controls; "
                            f"user edits were applied before generation. "
                            f"User-editable What-If values and the generated "
                            f"ledger are authoritative. "
                            f"This is not exact execution of the original challenge."
                        )
                    else:
                        st.warning(
                            f"Generated a What-If pair prepared from the supported subset of "
                            f"{cid} — "
                            f"{mapped} field(s) mapped, "
                            f"{unsup} field(s) not "
                            f"representable by current What-If controls. "
                            f"This is not exact execution of the original challenge."
                        )
                else:
                    if edited:
                        st.info(
                            f"Started from the supported {cid} prefill "
                            f"({mapped} field(s)); user-editable What-If values and the "
                            f"generated ledger are authoritative."
                        )
                    else:
                        st.info(
                            f"Generated a What-If pair prepared from "
                            f"{mapped} "
                            f"supported field(s) of {cid}."
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
