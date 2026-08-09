"""Portfolio Explorer page — transparent selector over synthetic portfolio evidence."""

from __future__ import annotations

import json

import streamlit as st

from traffictwin.experiments.portfolio import default_synthetic_portfolio_rules
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.portfolio_explorer import (
    build_portfolio_explorer_view,
    get_challenge_seed_library,
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

    # Evidence banner
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
    # Use session state for selection to allow Scenario Builder prefill later
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
    # Persist for potential What-If Studio integration after merge
    st.session_state["selected_challenge_id"] = selected_id
    selected = next(c for c in library if c.challenge_id == selected_id)

    # Show selected challenge details
    with st.container(border=True):
        st.markdown(f"**{selected.title}** (`{selected.challenge_id}`)")
        st.caption(selected.purpose)
        st.markdown(f"**Why challenging:** {selected.why_challenging}")
        st.markdown(f"**Evidence standing:** {selected.evidence_standing}")
        # Parameter overrides table
        if selected.parameter_overrides:
            param_rows = [
                {"parameter": k, "value": json.dumps(v) if isinstance(v, dict) else str(v)}
                for k, v in selected.parameter_overrides.items()
            ]
            st.dataframe(
                param_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(param_rows),
            )
        else:
            st.info("No parameter overrides.")
        if selected.expected_evidence_surfaces:
            st.caption(
                "Expected evidence surfaces: " + ", ".join(selected.expected_evidence_surfaces)
            )
        for lim in selected.limitations:
            st.caption(f"Limitation: {lim}")
        # Capacity semantics note
        st.info(
            "Waiting-room / queue capacity, service/compute capacity, worker count, task arrival and in-flight capacity "  # noqa: E501
            "are distinct where represented. Current product exposes only `infrastructure.rsu_capacity_mode` (STANDARD/REDUCED) "  # noqa: E501
            "and `infrastructure.rsu_count`; it does not expose separate waiting-room seats or compute cores. Labels follow the current contract."  # noqa: E501
        )
        if not selected.executable_now:
            st.warning(
                f"NOT YET EXECUTABLE: {selected.not_yet_executable_reason or 'Unsupported fields.'}"
            )
        else:
            st.success("Executable now via current ScenarioSeed schema.")
        # Action: open Scenario Builder (stable path)
        navigation_button(
            st.button,
            "Open Scenario Builder",
            UiPage.SCENARIO,
            key="portfolio_open_scenario_builder",
        )

    # Show full library table
    with st.expander("Advanced: full challenge library"):
        lib_rows = [
            {
                "challenge_id": c.challenge_id,
                "title": c.title,
                "purpose": c.purpose,
                "executable": "YES" if c.executable_now else "NO",
                "standing": c.evidence_standing,
            }
            for c in library
        ]
        st.dataframe(
            lib_rows, hide_index=True, width="stretch", column_config=table_column_config(lib_rows)
        )

    # Portfolio view for selected challenge
    view = build_portfolio_explorer_view(selected_id)
    selection = view.selection
    assert selection is not None

    # Scenario / challenge context
    st.subheader("Scenario context")
    with st.container(border=True):
        cols = st.columns(2)
        cols[0].metric(
            "Load intensity", _format_value(selection.scenario_features.get("load_intensity"))
        )
        t1 = selection.scenario_features.get("t1_share")
        cols[1].metric("T1 share", _format_value(t1) if t1 is not None else "—")
        # Features table
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

    # Selector decision
    st.subheader("Selector decision")
    with st.container(border=True):
        st.markdown(f"**Selected strategy:** `{selection.selected_algorithm}`")
        rule = selection.matched_rule_id or "fallback"
        st.markdown(f"**Matched rule:** `{rule}`")
        st.markdown(f"**Rationale:** {selection.rationale}")
        st.markdown(f"**Selector:** `{selection.selector_id}`")
        # Show ordered rules
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

    # Candidate strategies
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
                "failures": ", ".join(c.failure_seed_ids) or "none",
            }
            for c in view.candidate_views
        ]
        st.dataframe(
            cand_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(cand_rows),
        )
        st.caption(
            "Ranking is by mean regret (lower is better) on held-out synthetic seeds; winner/tie rate is descriptive, not optimal."  # noqa: E501
        )
    else:
        st.warning("No candidate strategies available for this context.")
        st.caption("Unavailable remains unavailable; synthetic provenance is preserved.")

    # Regret / dominance
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
        # Dominance matrix
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
        # Synthetic standing
        synthetic_badge = badge_markdown("synthetic")
        st.markdown(
            f"**Evidence standing:** {synthetic_badge} synthetic demonstration only · Held-out study verifies workflow, not external performance."  # noqa: E501
        )
        for w in study.warnings:
            st.caption(f"Study warning: {w}")
    else:
        st.warning("Regret and dominance are unavailable for the selected challenge context.")
        st.caption("Unavailable remains unavailable; no network or provider dependency.")

    # Limitations (prominent)
    st.subheader("Limitations")
    st.info(
        "Transparent rule selector, not a learned optimal controller. Synthetic result unless source explicitly differs. "  # noqa: E501
        "No Kubernetes deployment. No live Manchester control. No causal claim. Waiting-room capacity is not compute."  # noqa: E501
    )
    for w in view.warnings:
        st.caption(w)

    # Next actions
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
        "Compare and Reports consume the same validated bundles; What-If Studio integration will use stable session paths after PR #11 merges."  # noqa: E501
    )

    # Advanced export
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
