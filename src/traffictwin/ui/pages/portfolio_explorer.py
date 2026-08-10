"""Portfolio Explorer page — transparent selector over synthetic portfolio evidence."""

from __future__ import annotations

import json

import streamlit as st

from traffictwin.experiments.portfolio import default_synthetic_portfolio_rules
from traffictwin.ui.challenge_whatif_bridge import (
    PENDING_WHATIF_CHALLENGE_DRAFT_KEY,
    build_challenge_whatif_draft,
    draft_to_handoff_dict,
)
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.portfolio_explorer import (
    ChallengeExecutionStatus,
    build_portfolio_explorer_view,
    get_challenge_seed_library,
    is_selector_input,
)
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def _format_value(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def render() -> None:
    """Render Portfolio Explorer."""

    st.title("Portfolio Explorer")

    st.warning(
        "This explorer demonstrates transparent portfolio selection over available "
        "TrafficTwin scenario evidence. Synthetic studies are not production scheduling "
        "evidence and do not establish an optimal policy. No Kubernetes deployment, "
        "no live Manchester control, and no causal claim is made."
    )
    badge_row(["SYNTHETIC", "TRANSPARENT RULES", "DETERMINISTIC", "BOUNDED"])

    st.caption(
        "Selector: ordered deterministic rules over load intensity, T1 share, fleet tier mix "
        "and infrastructure capacity mode. The selected strategy is the first matching rule or the explicit fallback."  # noqa: E501
    )

    # Challenge Seed Library
    st.subheader("Challenge Seed Library")
    st.caption(
        "Supervisor-requested what-if situations encoded as deterministic ScenarioSeed overrides. "
        "All fields reuse validated ScenarioSeed schema; waiting-room capacity is not conflated with compute."  # noqa: E501
    )
    library = get_challenge_seed_library()
    challenge_ids = [c.challenge_id for c in library]
    challenge_titles = [f"{c.challenge_id} — {c.title}" for c in library]
    default_idx = 0
    selected_title = st.selectbox(
        "Choose challenge seed",
        challenge_titles,
        index=default_idx,
        key="portfolio_challenge_select",
    )
    selected_id = (
        challenge_ids[challenge_titles.index(selected_title)]
        if selected_title
        else challenge_ids[0]
    )
    st.session_state["selected_challenge_id"] = selected_id
    selected = next(c for c in library if c.challenge_id == selected_id)

    with st.container(border=True):
        st.markdown(f"**{selected.title}** (`{selected.challenge_id}`)")
        st.caption(selected.purpose)
        st.markdown(f"**Why challenging:** {selected.why_challenging}")
        st.markdown(f"**Evidence standing:** {selected.evidence_standing}")
        # Status: truthful tri-state
        if selected.status == ChallengeExecutionStatus.EXECUTABLE:
            st.success("Executable via current ScenarioSeed schema.")
        elif selected.status == ChallengeExecutionStatus.REPRESENTABLE_ONLY:
            st.info(
                "Representable as a validated ScenarioSeed. TrafficTwin does not currently "
                "provide a generic ScenarioSeed-to-run execution path for this challenge."
            )
        else:
            reason = selected.not_yet_executable_reason or "Not yet executable."
            st.warning(f"NOT YET EXECUTABLE: {reason}")
        st.markdown(f"**Execution status:** `{selected.status.value}`")
        if selected.parameter_overrides:
            param_rows = [
                {
                    "parameter": k,
                    "value": json.dumps(v) if isinstance(v, dict) else str(v),
                    "selector_input": "SELECTOR INPUT — affects current selector"
                    if is_selector_input(k)
                    else "RECORDED IN SEED — not consumed by current selector",
                }
                for k, v in selected.parameter_overrides.items()
            ]
            st.dataframe(
                param_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(
                    param_rows,
                    overrides={
                        "parameter": ColumnDisplay(key="parameter", label="Parameter"),
                        "value": ColumnDisplay(key="value", label="Value"),
                        "selector_input": ColumnDisplay(
                            key="selector_input", label="Selector relevance"
                        ),
                    },
                ),
            )
            st.caption(
                "Parameter relevance derived from authoritative selector-consumed-field contract: "
                "demand.multiplier, workload.birth_rate_multiplier, workload.class_mix[T1], "
                "fleet.tier_mix, infrastructure.rsu_capacity_mode, workload.ordering. Other valid "
                "ScenarioSeed fields are recorded but do not affect the current selector."
            )
        else:
            st.info("No parameter overrides.")
        if selected.target_evidence_surfaces:
            st.caption(
                "Target evidence surfaces (intended to probe if executed): "
                + ", ".join(selected.target_evidence_surfaces)
            )
        for lim in selected.limitations:
            st.caption(f"Limitation: {lim}")
        st.info(
            "Waiting-room / queue capacity, service/compute capacity, worker count, task arrival and in-flight capacity "  # noqa: E501
            "are distinct where represented. Current product exposes only `infrastructure.rsu_capacity_mode` (STANDARD/REDUCED) "  # noqa: E501
            "and `infrastructure.rsu_count`; it does not expose separate waiting-room seats or compute cores. Labels follow the current contract."  # noqa: E501
        )
        navigation_button(
            st.button,
            "Open Scenario Builder",
            UiPage.SCENARIO,
            key="portfolio_open_scenario_builder",
        )
        st.caption(
            "Values shown are not automatically prefilled in Scenario Builder; apply them manually if you continue there."  # noqa: E501
        )

        # --- Challenge → What-If bridge: prepare supported values ---
        draft = build_challenge_whatif_draft(selected)
        st.subheader("What-If Bridge")
        st.caption(
            "Transfer supported challenge parameters to What-If Studio. "
            "Unsupported fields are shown explicitly and not silently dropped."
        )
        with st.container(border=True):
            st.markdown(
                f"**{draft.challenge_title}** (`{draft.challenge_id}`) · "
                f"Status: `{draft.mapping_status.value}`"
            )
            st.caption(
                f"Supported in What-If Studio: {len(draft.supported_fields)} · "
                f"Not represented by current What-If controls: {len(draft.unsupported_fields)}"
            )
            if draft.supported_fields:
                sup_rows = [
                    {
                        "challenge_path": f.challenge_path,
                        "challenge_value": json.dumps(f.challenge_value)
                        if isinstance(f.challenge_value, dict)
                        else str(f.challenge_value),
                        "whatif_field": f.whatif_field,
                        "mapped_value": json.dumps(f.mapped_value)
                        if isinstance(f.mapped_value, dict)
                        else str(f.mapped_value),
                    }
                    for f in draft.supported_fields
                ]
                st.markdown("**Supported — will be prefilled:**")
                st.dataframe(
                    sup_rows,
                    hide_index=True,
                    width="stretch",
                    column_config=table_column_config(sup_rows),
                )
            else:
                st.info("No challenge fields are representable with current What-If controls.")

            if draft.unsupported_fields:
                unsup_rows = [
                    {
                        "challenge_path": f.challenge_path,
                        "challenge_value": json.dumps(f.challenge_value)
                        if isinstance(f.challenge_value, dict)
                        else str(f.challenge_value),
                        "reason": f.reason,
                    }
                    for f in draft.unsupported_fields
                ]
                st.markdown("**Not applied — unsupported by current What-If controls:**")
                st.dataframe(
                    unsup_rows,
                    hide_index=True,
                    width="stretch",
                    column_config=table_column_config(unsup_rows),
                )
                st.warning(
                    "Only the supported subset will be prefilled. "
                    "The generated What-If pair must not be interpreted as exact "
                    "execution of the original challenge."
                )
            for w in draft.warnings:
                st.caption(f"Bridge: {w}")
            st.caption(
                "Challenge parameters are applied as intervention inputs against the "
                "baseline preset you choose in What-If Studio."
            )
            # Prepare button — writes handoff and navigates
            if st.button(
                "Prepare supported values in What-If Studio",
                key="portfolio_prepare_whatif",
                disabled=(draft.mapping_status == "NOT_MAPPABLE" and not draft.supported_fields),
            ):
                st.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] = draft_to_handoff_dict(draft)
                # Reset fingerprint so What-If Studio will seed this exact draft once
                st.session_state["whatif_challenge_prefill_applied_fingerprint"] = None
                st.session_state["whatif_challenge_prefill_applied"] = False
                # Navigate via pending key (works inside callbacks and direct)
                st.session_state["_v07_pending_page"] = UiPage.WHATIF_STUDIO.value
                st.success(
                    f"Prepared {len(draft.supported_fields)} supported field(s) from "
                    f"{draft.challenge_id}. Opening What-If Studio…"
                )
                st.rerun()
            if draft.mapping_status.value == "NOT_MAPPABLE" and not draft.supported_fields:
                st.caption(
                    "No supported What-If fields for this challenge. "
                    "Manual Scenario Builder remains available."
                )

    with st.expander("Advanced: full challenge library"):
        lib_rows = [
            {
                "challenge_id": c.challenge_id,
                "title": c.title,
                "purpose": c.purpose,
                "status": c.status.value,
                "standing": c.evidence_standing,
            }
            for c in library
        ]
        st.dataframe(
            lib_rows, hide_index=True, width="stretch", column_config=table_column_config(lib_rows)
        )

    view = build_portfolio_explorer_view(selected_id)
    selection = view.selection
    if selection is None:
        st.error("Selected challenge has no portfolio selection available.")
        st.caption("Unavailable remains unavailable; no synthetic data was inferred.")
        return

    st.subheader("Scenario context")
    with st.container(border=True):
        cols = st.columns(2)
        cols[0].metric(
            "Load intensity", _format_value(selection.scenario_features.get("load_intensity"))
        )
        t1 = selection.scenario_features.get("t1_share")
        cols[1].metric("T1 share", _format_value(t1) if t1 is not None else "—")
        feat_rows = [
            {"feature": k, "value": _format_value(v)}
            for k, v in selection.scenario_features.items()
        ]
        st.dataframe(
            feat_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                feat_rows, overrides={"feature": ColumnDisplay(key="feature", label="Feature")}
            ),
        )
        st.caption(
            f"Scenario seed: `{selection.scenario_seed_id}` · Synthetic demonstration only: `{selection.synthetic_demonstration_only}`"  # noqa: E501
        )

    st.subheader("Selector decision")
    with st.container(border=True):
        st.markdown(f"**Selected strategy:** `{selection.selected_algorithm}`")
        rule = selection.matched_rule_id or "fallback"
        st.markdown(f"**Matched rule:** `{rule}`")
        st.markdown(f"**Rationale:** {selection.rationale}")
        st.markdown(f"**Selector:** `{selection.selector_id}`")
        ruleset = default_synthetic_portfolio_rules()
        rule_rows = [
            {
                "rule_id": r.rule_id,
                "selected_algorithm": r.selected_algorithm,
                "rationale": r.rationale,
            }
            for r in ruleset.rules
        ]
        rule_rows.append(
            {
                "rule_id": "fallback",
                "selected_algorithm": ruleset.fallback_algorithm,
                "rationale": "No rule matched; the explicit fallback was selected.",
            }
        )
        st.dataframe(
            rule_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(rule_rows),
        )
        for w in selection.warnings:
            st.caption(f"Selector limitation: {w}")

    st.subheader("Candidate strategies")
    if view.candidate_views:
        cand_rows = [
            {
                "algorithm": c.algorithm,
                "rank": _format_value(c.rank),
                "winner_or_tie_rate": _format_value(c.winner_or_tie_rate),
                "mean_score": _format_value(c.mean_score),
                "mean_regret": _format_value(c.mean_regret),
                "available_seeds": c.available_seed_count,
                "seeds_not_won": ", ".join(c.seeds_not_won) or "none",
            }
            for c in view.candidate_views
        ]
        st.dataframe(
            cand_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                cand_rows,
                overrides={
                    "seeds_not_won": ColumnDisplay(
                        key="seeds_not_won",
                        label="Seeds where strategy was not winner-or-tie",
                    )
                },
            ),
        )
        st.caption(
            "Ranking is by mean regret (lower is better) on held-out synthetic seeds; winner/tie rate is descriptive, not optimal. "  # noqa: E501
            "Seeds where strategy was not winner-or-tie are counted per constituent (not execution failures)."  # noqa: E501
        )
    else:
        st.warning("No candidate strategies available for this context.")
        st.caption("Unavailable remains unavailable; synthetic provenance is preserved.")

    st.subheader("Regret / dominance")
    study = view.study_report
    if study is not None:
        held = study.held_out_evaluation
        cols = st.columns(3)
        cols[0].metric("Winner/tie rate", _format_value(held.winner_or_tie_rate))
        cols[1].metric("Mean regret", _format_value(held.mean_regret))
        cols[2].metric("Mean selected score", _format_value(held.mean_selected_score))
        st.caption(
            f"Held-out seeds: {len(study.held_out_seed_ids)} · Development seeds: {len(study.development_seed_ids)} · Metric: `{study.metric_key}`"  # noqa: E501
        )
        # n=2 limitation: compute best constituent and compare
        if study.held_out_constituents:
            best = max(
                study.held_out_constituents,
                key=lambda c: c.winner_or_tie_rate if c.winner_or_tie_rate is not None else -1,
            )
            held_rate = held.winner_or_tie_rate
            best_rate = best.winner_or_tie_rate
            n_held = len(study.held_out_seed_ids)
            if n_held == 2 and held_rate is not None and best_rate is not None:
                if held_rate <= best_rate:
                    best_label = best.algorithm
                    st.warning(
                        f"Illustrative held-out set: n={n_held}. On these two synthetic seeds, the rule "  # noqa: E501
                        f"selector (winner/tie {held_rate:.2f}) does not outperform the strongest single "  # noqa: E501
                        f"constituent `{best_label}` (winner/tie {best_rate:.2f})."
                    )
                else:
                    st.info(
                        f"Held-out set: n={n_held}. Selector and best constituent winner/tie rates shown above."  # noqa: E501
                    )
        st.caption(
            "The development split does not train the default rules; rules are predeclared and fixed before held-out evaluation."  # noqa: E501
        )
        if study.dominance_matrix:
            dom_rows = [
                {
                    "algorithm": d.algorithm,
                    "comparator": d.comparator,
                    "wins": d.wins,
                    "ties": d.ties,
                    "losses": d.losses,
                    "available": d.available_seed_count,
                }
                for d in study.dominance_matrix
            ]
            with st.expander("Advanced: dominance matrix"):
                st.dataframe(
                    dom_rows,
                    hide_index=True,
                    width="stretch",
                    column_config=table_column_config(dom_rows),
                )
        else:
            st.info("Dominance matrix unavailable for this study.")
        synthetic_badge = badge_markdown("synthetic")
        st.markdown(
            f"**Evidence standing:** {synthetic_badge} synthetic demonstration only · Held-out study verifies workflow, not external performance."  # noqa: E501
        )
        for w in study.warnings:
            st.caption(f"Study warning: {w}")
    else:
        st.warning("Regret and dominance are unavailable for the selected challenge context.")
        st.caption("Unavailable remains unavailable; no network or provider dependency.")

    st.subheader("Limitations")
    st.info(
        "Transparent rule selector, not a learned optimal controller. Synthetic result unless source explicitly differs. "  # noqa: E501
        "No Kubernetes deployment. No live Manchester control. No causal claim. Waiting-room capacity is not compute."  # noqa: E501
    )
    for w in view.warnings:
        st.caption(w)

    st.subheader("Next actions")
    cols = st.columns(4)
    navigation_button(
        cols[0].button, "Scenario Builder", UiPage.SCENARIO, key="portfolio_next_scenario"
    )
    navigation_button(
        cols[1].button, "Experiments", UiPage.EXPERIMENT_MANAGER, key="portfolio_next_experiments"
    )
    navigation_button(cols[2].button, "Compare", UiPage.COMPARE, key="portfolio_next_compare")
    navigation_button(
        cols[3].button, "Provenance", UiPage.PROVENANCE, key="portfolio_next_provenance"
    )
    st.caption(
        "Compare and Reports consume the same validated bundles; What-If Studio integration uses stable session paths."  # noqa: E501
    )

    with st.expander("Advanced: portfolio view JSON"):
        st.download_button(
            "Download portfolio view JSON",
            data=json.dumps(view.model_dump(mode="json"), indent=2),
            file_name=f"{view.fingerprint[:12]}-portfolio.json"
            if view.fingerprint
            else "portfolio.json",
            mime="application/json",
            key="portfolio_download_json",
        )
        st.json(view.model_dump(mode="json"))

    st.caption(
        "Direction/optimality is not implied; variation − baseline and winner/tie are descriptive. Challenge fingerprints are deterministic."  # noqa: E501
    )
