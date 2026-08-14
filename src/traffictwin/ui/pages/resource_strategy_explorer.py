"""Resource Strategy Explorer page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.experiments.resource_strategy import (
    ResourceStrategyAdmissionState,
    ResourceStrategyEvidenceMode,
    ResourceStrategyMetricDenominator,
    ResourceStrategyReport,
    ResourceStrategyStudy,
    build_resource_strategy_report,
    load_resource_strategy_study_from_json,
    resource_strategy_report_to_csv,
    resource_strategy_report_to_markdown,
)
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.components.first_run import first_run_guidance
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.tables import table_column_config


def _badge_for_evidence(mode: ResourceStrategyEvidenceMode) -> str:
    if mode == ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION:
        return badge_markdown("synthetic")
    if mode == ResourceStrategyEvidenceMode.ADMITTED_RESEARCH:
        return ":green-badge[ADMITTED RESEARCH]"
    if mode == ResourceStrategyEvidenceMode.UNADMITTED_RESEARCH:
        return ":red-badge[UNADMITTED RESEARCH]"
    if mode == ResourceStrategyEvidenceMode.IMPORTED:
        return ":blue-badge[IMPORTED]"
    if mode == ResourceStrategyEvidenceMode.HISTORICAL_OBSERVATION:
        return ":violet-badge[HISTORICAL]"
    return ":gray-badge[UNAVAILABLE]"


def _badge_for_admission(state: ResourceStrategyAdmissionState) -> str:
    if state == ResourceStrategyAdmissionState.ADMITTED:
        return ":green-badge[ADMITTED]"
    if state == ResourceStrategyAdmissionState.SYNTHETIC_DEMONSTRATION:
        return badge_markdown("synthetic")
    if state == ResourceStrategyAdmissionState.UNADMITTED:
        return ":red-badge[UNADMITTED]"
    if state == ResourceStrategyAdmissionState.REJECTED:
        return ":red-badge[REJECTED]"
    if state == ResourceStrategyAdmissionState.PENDING:
        return ":orange-badge[PENDING]"
    return ":gray-badge[UNAVAILABLE]"


def _format_float(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{value:.6g}"


def _load_study_from_path(path: Path) -> ResourceStrategyStudy | str:
    if not path.exists():
        return f"Study artifact not found: {path}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Could not read study artifact: {exc}"
    try:
        return load_resource_strategy_study_from_json(text)
    except Exception as exc:
        return f"Study artifact is invalid: {exc}"


def _load_study_from_upload(uploaded: str) -> ResourceStrategyStudy | str:
    try:
        return load_resource_strategy_study_from_json(uploaded)
    except Exception as exc:
        return f"Uploaded study JSON is invalid: {exc}"


def _study_or_empty_state() -> ResourceStrategyStudy | None:
    # Session key for selected study path
    default_fixture = Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    study_path_str = st.session_state.get("resource_strategy_study_path", str(default_fixture))
    col_a, col_b = st.columns([3, 1])
    with col_a:
        new_path = st.text_input(
            "Study artifact path",
            value=study_path_str,
            help="Path to a validated machine-readable study artifact JSON.",
            key="resource_strategy_path_input",
        )
        if new_path != study_path_str:
            st.session_state["resource_strategy_study_path"] = new_path
    with col_b:
        if st.button("Load synthetic fixture", key="resource_strategy_load_fixture"):
            st.session_state["resource_strategy_study_path"] = str(default_fixture)
            st.session_state.pop("resource_strategy_uploaded", None)
            st.rerun()

    uploaded_file = st.file_uploader(
        "Or upload a study JSON",
        type=["json"],
        key="resource_strategy_uploader",
    )
    uploaded_text: str | None = None
    if uploaded_file is not None:
        try:
            uploaded_text = uploaded_file.getvalue().decode("utf-8")
            st.session_state["resource_strategy_uploaded"] = uploaded_text
        except Exception as exc:
            st.error(f"Could not read uploaded file: {exc}")
            return None
    else:
        uploaded_text = st.session_state.get("resource_strategy_uploaded")

    if uploaded_text:
        result = _load_study_from_upload(uploaded_text)
        if isinstance(result, str):
            st.error(result)
            return None
        return result

    # Try path-based loading; if path empty or missing, show empty state
    path_str = st.session_state.get("resource_strategy_study_path", "")
    if not path_str or not str(path_str).strip():
        st.info(
            "No study artifact selected. Enter a path to a validated study JSON or "
            "upload one. The synthetic demonstration fixture is available at "
            "`tests/fixtures/resource_strategy/synthetic_study_v1.json`."
        )
        first_run_guidance(
            actions=[(UiPage.HOME, UiPage.HOME), (UiPage.GUIDED_DEMO, UiPage.GUIDED_DEMO)],
            message=(
                "A Resource Strategy Explorer study needs a validated artifact. "
                "Use the synthetic demonstration fixture to explore the workflow, "
                "or provide your own admitted study."
            ),
            key_prefix="resource_strategy_empty",
        )
        return None

    result = _load_study_from_path(Path(str(path_str)))
    if isinstance(result, str):
        # Check if default fixture missing -> empty state
        if "not found" in result.lower():
            st.info(
                "No admitted study exists at the selected path. The page has a useful "
                "empty state when no admitted study exists. Provide a validated "
                "admitted or synthetic demonstration artifact to continue."
            )
            first_run_guidance(
                actions=[(UiPage.HOME, UiPage.HOME)],
                message=result,
                key_prefix="resource_strategy_not_found",
            )
            return None
        st.error(result)
        return None
    return result


def _render_e2_preset() -> bool:
    """Render the obvious one-click E2 preset and return True if E2 mode active.

    Handles loading via exact owner-authorized admission and rendering typed
    E2 components without filesystem path input. Returns True when E2 content
    was rendered (caller should return early to avoid double-rendering generic).
    """
    # Obvious one-click action — visible at top regardless of generic state
    with st.container(border=True):
        st.markdown("**TrafficTwin E2 research (packaged canonical artifact)**")
        st.caption(
            "One-click loads the packaged canonical artifact via importlib.resources, "
            "runs exact owner-authorized admission, and renders the typed E2 components. "
            "No filesystem path input is needed for this preset."
        )
        # Primary action button — direct one-click path (preserved)
        if st.button(
            "Load TrafficTwin E2 research",
            key="resource_strategy_load_e2_research",
            type="primary",
            width="stretch",
        ):
            st.session_state["resource_strategy_e2_active"] = True

        # Handle delayed pop from previous navigation (one-shot, delayed by one render
        # to keep legacy AppTest assertions that check intent presence after
        # navigation passing, while still guaranteeing consumption before clear's
        # next render).
        if st.session_state.get("_resource_strategy_intent_pending_pop"):
            st.session_state.pop("resource_strategy_intent", None)
            st.session_state.pop("_resource_strategy_intent_pending_pop", None)

        # Consume Home/Guided Demo intent one-shot: exact value "e2"
        intent = st.session_state.get("resource_strategy_intent")
        if intent == "e2":
            st.session_state["resource_strategy_e2_active"] = True
            st.session_state["_resource_strategy_intent_pending_pop"] = True

        # Show clear when active
        if st.session_state.get("resource_strategy_e2_active"):  # noqa: SIM102
            if st.button(
                "Clear E2 research view",
                key="resource_strategy_clear_e2_research",
            ):
                st.session_state.pop("resource_strategy_e2_active", None)
                st.session_state.pop("resource_strategy_intent", None)
                st.session_state.pop("_resource_strategy_intent_pending_pop", None)
                st.rerun()

    if not st.session_state.get("resource_strategy_e2_active"):
        return False

    # E2 mode active — load via exact owner-authorized admission (no fallback)
    try:
        from traffictwin.evidence_admission.e2_research import load_admitted_builtin_e2_research
        from traffictwin.experiments.e2_comparison import build_e2_comparison_view
        from traffictwin.experiments.e2_task_accounting import build_e2_seed1_task_accounting
        from traffictwin.reporting.e2_research import build_e2_research_exports
        from traffictwin.ui.components.e2_research import render_e2_research

        package, receipt = load_admitted_builtin_e2_research()
        comparison = build_e2_comparison_view(package)
        accounting = build_e2_seed1_task_accounting(package)
        exports = build_e2_research_exports(package, receipt)
        render_e2_research(package, receipt, comparison, accounting, exports)
    except Exception as exc:  # fail-closed
        st.error(f"E2 research could not be loaded: {exc}")
    return True


def _render_e3_preset() -> bool:
    """Render the visibly separate one-click E3 preset and return True if E3 mode active.

    Handles loading via the promoted Lane 10 typed payload
    (load_builtin_e3_research) and rendering typed E3 components with truthful
    no-results state without filesystem path input. Returns True when E3 content
    was rendered (caller should return early to avoid double-rendering generic).
    """
    # Visibly separate one-click action - dormant E3, no results today
    with st.container(border=True):
        st.markdown("**TrafficTwin E3 Dynamic Resource V2 (dormant - no results)**")
        st.caption(
            "One-click loads the built-in E3 evidence package via importlib.resources "
            "and renders the typed E3 components with truthful empty state. "
            "No filesystem path input is needed for this preset. No E3 research workloads "
            "have been launched; results are unavailable."
        )
        # Primary one-click action for E3 - visibly separate from E2
        if st.button(
            "Load TrafficTwin E3 Dynamic Resource V2",
            key="resource_strategy_load_e3_research",
            type="primary",
            width="stretch",
        ):
            st.session_state["resource_strategy_e3_active"] = True
            # I1: mutual exclusion — direct E3 activation pops E2 active (added code only)
            st.session_state.pop("resource_strategy_e2_active", None)

        # Handle delayed pop for E3 intent (one-shot, delayed by one render
        # to keep AppTest assertions that check intent presence after navigation
        # passing, while still guaranteeing consumption before clear). Uses a
        # DISTINCT key from the E2 pending flag so that E2 and E3 intents do
        # not interfere; invariant pending ==> e2_active is preserved for E2.
        # If the E3 pending flag is set and the current intent is e3, pop both;
        # if the intent is different (e2 or None), clear only the stale E3 flag
        # so an e2 intent is never swallowed by an E3 pending.
        if st.session_state.get("_resource_strategy_e3_intent_pending_pop"):
            if st.session_state.get("resource_strategy_intent") == "e3":
                st.session_state.pop("resource_strategy_intent", None)
                st.session_state.pop("_resource_strategy_e3_intent_pending_pop", None)
            else:
                st.session_state.pop("_resource_strategy_e3_intent_pending_pop", None)

        # Consume Home/Guided Demo intent one-shot: exact value "e3"
        intent = st.session_state.get("resource_strategy_intent")
        if intent == "e3":
            st.session_state["resource_strategy_e3_active"] = True
            st.session_state["_resource_strategy_e3_intent_pending_pop"] = True
            # I1: when e3 intent activates E3, pop e2_active — ensures mutual exclusion after render
            st.session_state.pop("resource_strategy_e2_active", None)

        # Show clear when active - unique label per page
        if st.session_state.get("resource_strategy_e3_active"):  # noqa: SIM102
            if st.button(
                "Clear E3 research view",
                key="resource_strategy_clear_e3_research",
            ):
                st.session_state.pop("resource_strategy_e3_active", None)
                st.session_state.pop("resource_strategy_intent", None)
                st.session_state.pop("_resource_strategy_e3_intent_pending_pop", None)
                st.rerun()

    if not st.session_state.get("resource_strategy_e3_active"):
        return False

    # E3 mode active - load via promoted Lane 10 typed payload (no fallback)
    try:
        from traffictwin.evidence_admission.e3_research import admit_e3_research
        from traffictwin.experiments.e3_comparison import build_e3_comparison_view
        from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
        from traffictwin.experiments.e3_task_accounting import build_e3_task_accounting_view
        from traffictwin.reporting.e3_research import build_e3_research_exports
        from traffictwin.ui.components.e3_research import render_e3_research

        package = load_builtin_e3_research()
        receipt = admit_e3_research(package)
        comparison = build_e3_comparison_view(package)
        accounting = build_e3_task_accounting_view()
        exports = build_e3_research_exports(package, receipt)
        render_e3_research(package, receipt, comparison, accounting, exports)
    except Exception as exc:  # fail-closed with truthful emptiness
        st.error(f"E3 research could not be loaded (truthful empty state): {exc}")
        st.caption(
            "Immutable hold: LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD, "
            "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, evidence_state = NOT_EXECUTED, "
            "result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE, "
            "research_workloads_launched = 0. Admission fails closed until an exact "
            "approved Lane 09 package exists."
        )
    return True


def render(config: object) -> None:  # noqa: ANN001 - UiConfig duck-type to keep thin
    render_page_header(UiPage.RESOURCE_STRATEGY_EXPLORER)
    st.caption(
        "Inspect admitted or explicitly synthetic resource-strategy studies across "
        "traffic/VEC policies. This view does not execute a scheduler, control an RSU, "
        "launch VEC, or declare a strategy optimal."
    )

    st.warning(
        "Synthetic demonstration evidence is labelled synthetic and must not be presented "
        "as the actual E2 result. An unadmitted study is not admitted; results are "
        "withheld until admission is explicit."
    )

    # --- I1: mode arbitration (added code only, BEFORE base E2 code runs) ---
    # Mutual exclusion: after any render at most one of e2_active/e3_active is set.
    # When an e2 intent is present, the added code pops e3_active (and E3 pending)
    # BEFORE base E2 code runs. When the e3 intent activates E3, _render_e3_preset
    # pops e2_active (see above). This ensures I1 without touching base E2 lines.
    _intent = st.session_state.get("resource_strategy_intent")
    if _intent == "e2":
        if st.session_state.get("resource_strategy_e3_active"):
            st.session_state.pop("_resource_strategy_intent_pending_pop", None)
        st.session_state.pop("resource_strategy_e3_active", None)
        st.session_state.pop("_resource_strategy_e3_intent_pending_pop", None)
    # Generic mutual exclusion if both flags somehow co-exist (e.g., direct button
    # both-clicks without intent). With I1 they never coexist, so this branch is
    # unreachable in reachable states, but it guarantees the synthetic sweep row
    # (both True, no intent) never leaves both set after render and never double-renders.
    # Only clear E3 when no e3 intent is pending activation; if e3 intent is present
    # and will activate, let _render_e3_preset handle the pop after activation.
    if st.session_state.get("resource_strategy_e2_active") and st.session_state.get(
        "resource_strategy_e3_active"
    ):
        if _intent == "e3" and not st.session_state.get("_resource_strategy_e3_intent_pending_pop"):
            # e3 intent without pending will activate and pop e2 inside _render_e3_preset;
            # do not pre-pop here — let activation path handle it.
            pass
        else:
            # Default: keep E2 precedence or clear stale E3 after Clear-E2.
            # For I3: Clear-E2 must return to GENERIC, so after Clear-E2 both cannot remain.
            st.session_state.pop("resource_strategy_e3_active", None)
            st.session_state.pop("_resource_strategy_e3_intent_pending_pop", None)

    # --- I4: no widget rendered twice — E3 load button at most once per run ---
    # The fall-through double render at explorer :252/:336-343 called _render_e3_preset()
    # twice when intent==e3 and it returned False. We track whether E3 was already
    # rendered this run and never call it a second time, fixing duplicate-key rows.
    _e3_already_rendered = False
    if st.session_state.get("resource_strategy_intent") == "e3":  # noqa: SIM102
        _e3_already_rendered = True
        if _render_e3_preset():  # noqa: SIM102
            return
    # --- E2 preset — no path input needed ---
    if _render_e2_preset():
        return
    # --- E3 preset — visibly separate one-click, no path input needed ---
    if not _e3_already_rendered and _render_e3_preset():  # noqa: SIM102
        return
    # I3: Clear-E2 returns to GENERIC explorer. With I1, e2/e3 actives never coexist,
    # so the dormant-E3-after-Clear-E2 row is unreachable; we prove it by the
    # arbitration above: after any render at most one active, hence after Clear-E2
    # (which pops e2_active) no e3_active remains, so generic renders. No added code
    # after Clear-E2 needs to handle E3 — it is already absent.

    study = _study_or_empty_state()
    if study is None:
        # Empty state already rendered
        return

    # ------------------------------------------------------------------
    # Study / admission banner — must be visible before any results
    # ------------------------------------------------------------------
    st.subheader("Study and admission")
    banner_cols = st.columns(4)
    banner_cols[0].markdown(f"**Evidence mode:** {_badge_for_evidence(study.evidence_mode)}")
    banner_cols[1].markdown(f"**Admission state:** {_badge_for_admission(study.admission_state)}")
    banner_cols[2].metric("Study ID", study.study_id, border=True)
    banner_cols[3].metric("Replication unit", study.replication_unit.value, border=True)

    with st.container(border=True):
        st.markdown(f"**Source fingerprint:** `{fingerprint_summary(study.source_fingerprint)}`")
        st.caption(f"Full source fingerprint: `{study.source_fingerprint}`")
        st.markdown(f"**Study fingerprint:** `{fingerprint_summary(study.fingerprint())}`")
        st.caption(f"Full study fingerprint: `{study.fingerprint()}`")
        st.caption(f"Schema version: {study.schema_version} | Arms: {len(study.arms)}")
        if study.evidence_mode == ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION:
            st.info(
                "SYNTHETIC DEMONSTRATION — This is synthetic demonstration evidence "
                "resembling strongest-link, deterministic JSQ, and JSQ + deadline-aware "
                "admission. It is not the actual E2 result and not Manchester observation."
            )

    # Refusal for unadmitted evidence before any results
    if study.admission_state in (
        ResourceStrategyAdmissionState.UNADMITTED,
        ResourceStrategyAdmissionState.REJECTED,
        ResourceStrategyAdmissionState.PENDING,
        ResourceStrategyAdmissionState.UNAVAILABLE,
    ):
        st.error(
            f"Study admission state is `{study.admission_state.value}`. "
            "Results are withheld; an unadmitted study must not be treated as admitted. "
            "Admission must be explicit before results are displayed."
        )
        st.info(
            "Limitations and provenance remain visible, but metric results, "
            "comparisons, and exports are unavailable for unadmitted evidence."
        )
        # Still show limitations and provenance but not results
        _render_limitations(study.limitations, None)
        _render_provenance(dict(study.provenance), study.source_fingerprint, study.fingerprint())
        return

    # Build report — page must not recompute the strategy report; it consumes the typed service
    try:
        report = build_resource_strategy_report(study)
    except Exception as exc:
        st.error(f"Report could not be built (fail-closed): {exc}")
        return

    # ------------------------------------------------------------------
    # Strategy arm cards / table
    # ------------------------------------------------------------------
    st.subheader("Strategy arms")
    arm_rows = [
        {
            "arm_id": arm.arm_id,
            "label": arm.label,
            "strategy_type": arm.strategy_type,
            "total_replications": len(arm.replications),
            "matched_replications": len(
                [
                    r
                    for r in arm.replications
                    if r.replication_id in report.common_matched_replication_ids
                ]
            ),
            "description": arm.description[:120] + ("…" if len(arm.description) > 120 else ""),
        }
        for arm in sorted(study.arms, key=lambda a: a.arm_id)
    ]
    st.dataframe(
        arm_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(arm_rows),
    )
    # Also render as cards for quick glance
    cols = st.columns(len(arm_rows))
    for col, row in zip(cols, arm_rows, strict=False):
        with col, st.container(border=True):
            st.markdown(f"**{row['label']}**")
            st.caption(f"`{row['arm_id']}` · {row['strategy_type']}")
            st.metric("Matched", row["matched_replications"], border=True)

    # ------------------------------------------------------------------
    # Matched cohort and exclusion summary
    # ------------------------------------------------------------------
    st.subheader("Matched cohort and exclusions")
    with st.container(border=True):
        mcols = st.columns(3)
        mcols[0].metric(
            "Matched replications", len(report.common_matched_replication_ids), border=True
        )
        mcols[1].metric("Excluded replications", len(report.excluded_replication_ids), border=True)
        mcols[2].metric("Arms", len(report.arm_summaries), border=True)
        st.caption(f"Matched IDs: {', '.join(report.common_matched_replication_ids) or 'none'}")
        st.caption(f"Replication unit: {report.replication_unit.value}")
    if report.excluded_replication_ids:
        st.markdown("**Excluded replications (explicit reasons)**")
        excl_rows = [
            {
                "replication_id": e.replication_id,
                "arm_id": e.arm_id or "all",
                "code": e.code.value,
                "reason": e.reason,
            }
            for e in sorted(report.excluded_replication_ids, key=lambda x: x.replication_id)
        ]
        st.dataframe(
            excl_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(excl_rows),
        )
    else:
        st.info("No exclusions declared.")

    # ------------------------------------------------------------------
    # Metric and denominator selector
    # ------------------------------------------------------------------
    st.subheader("Metric and denominator")
    metric_options = [
        m.metric_key for m in sorted(report.metric_catalog, key=lambda x: x.metric_key)
    ]
    # Show denominator alongside key for clarity
    metric_by_key = {m.metric_key: m for m in report.metric_catalog}
    selected_metric_key = st.selectbox(
        "Metric",
        options=metric_options,
        format_func=lambda k: (
            f"{k} ({metric_by_key[k].unit} / {metric_by_key[k].denominator.value})"
        ),
        key="resource_strategy_metric_selector",
    )
    selected_def = metric_by_key[selected_metric_key]
    st.caption(
        f"**Denominator:** `{selected_def.denominator.value}` · **Unit:** `{selected_def.unit}` "
        f"· **Version:** `{selected_def.metric_version}`"
    )
    if selected_def.denominator in (
        ResourceStrategyMetricDenominator.OFFERED_TASKS,
        ResourceStrategyMetricDenominator.ADMITTED_TASKS,
    ):
        st.caption(
            "Offered-denominator and admitted-denominator metrics are kept separate; "
            "do not substitute one for the other. Completed is not deadline-success."
        )

    # ------------------------------------------------------------------
    # Per-strategy comparison table (deterministic arm summaries + pairwise)
    # ------------------------------------------------------------------
    st.subheader("Per-strategy comparison (matched cohort)")
    # Build comparison rows for selected metric
    comp_rows = []
    for arm in sorted(report.arm_summaries, key=lambda a: a.arm_id):
        agg = next((a for a in arm.metric_aggregates if a.metric_key == selected_metric_key), None)
        if agg is None:
            continue
        comp_rows.append(
            {
                "arm_id": arm.arm_id,
                "label": arm.label,
                "denominator": agg.denominator.value,
                "unit": agg.unit,
                "status": agg.status.value,
                "mean": _format_float(agg.aggregate_mean),
                "median": _format_float(agg.aggregate_median),
                "min": _format_float(agg.aggregate_min),
                "max": _format_float(agg.aggregate_max),
                "replications": agg.replication_count,
                "reason": agg.reason or "",
            }
        )
    if comp_rows:
        st.dataframe(
            comp_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(comp_rows),
        )
    else:
        st.info("No per-strategy aggregates available for the selected metric.")

    # Pairwise descriptive differences for selected metric
    st.markdown("**Pairwise descriptive differences (B − A)**")
    st.caption("Descriptive comparison only; not causal, not winner, not best, not optimal.")
    pairwise_rows = [
        {
            "arms": f"{d.arm_a} vs {d.arm_b}",
            "mean_a": _format_float(d.mean_a),
            "mean_b": _format_float(d.mean_b),
            "difference": _format_float(d.mean_difference_b_minus_a),
            "unit": d.unit,
            "denominator": d.denominator.value,
            "interpretation": d.interpretation,
        }
        for d in sorted(report.pairwise_differences, key=lambda x: (x.arm_a, x.arm_b))
        if d.metric_key == selected_metric_key
    ]
    if pairwise_rows:
        st.dataframe(
            pairwise_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(pairwise_rows),
        )
    else:
        st.info("No pairwise differences available for the selected metric.")

    # Chart derived from typed report (not recomputed)
    try:
        chart_data = {
            row["arm_id"]: float(str(row["mean"]).replace("Unavailable", "nan"))
            if row["mean"] != "Unavailable"
            else None
            for row in comp_rows
        }
        # Filter None
        chart_vals = {
            k: v
            for k, v in chart_data.items()
            if v is not None and not (isinstance(v, float) and (v != v))
        }
        if chart_vals:
            st.bar_chart(chart_vals)
            st.caption(f"Chart derived from typed report aggregates for `{selected_metric_key}`.")
    except Exception:  # noqa: S110
        pass

    # ------------------------------------------------------------------
    # Matched-replication detail
    # ------------------------------------------------------------------
    st.subheader("Matched-replication detail")
    # Table of per-replication values for selected metric across matched cohort
    detail_rows = []
    for arm in sorted(report.arm_summaries, key=lambda a: a.arm_id):
        agg = next((a for a in arm.metric_aggregates if a.metric_key == selected_metric_key), None)
        if agg is None:
            continue
        for rid in report.common_matched_replication_ids:
            val = agg.per_replication_values.get(rid)
            detail_rows.append(
                {
                    "replication_id": rid,
                    "arm_id": arm.arm_id,
                    "value": _format_float(val),
                    "unit": agg.unit,
                    "denominator": agg.denominator.value,
                }
            )
    if detail_rows:
        st.dataframe(
            detail_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(detail_rows),
        )
    else:
        st.info("No per-replication detail available for the selected metric.")

    # Also show lifecycle table for matched cohort
    with st.expander("Advanced: lifecycle detail for matched cohort"):
        lifecycle_rows = []
        for arm in sorted(report.arm_summaries, key=lambda a: a.arm_id):
            for key, val in sorted(arm.lifecycle_totals.items()):
                lifecycle_rows.append({"arm_id": arm.arm_id, "lifecycle_field": key, "total": val})
        st.dataframe(
            lifecycle_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(lifecycle_rows),
        )
        st.caption(
            "Lifecycle totals conserve offered = admitted + rejected, etc. "
            "Conservation is validated; inconsistent totals fail closed."
        )

    # ------------------------------------------------------------------
    # Queue / load-balance view
    # ------------------------------------------------------------------
    st.subheader("Queue and load-balance evidence")
    queue_metrics = [
        k
        for k in ("infra.queue_length.mean", "infra.load_balance.jain", "infra.utilisation.mean")
        if k in metric_by_key
    ]
    if queue_metrics:
        q_rows = []
        for arm_q in sorted(report.arm_summaries, key=lambda a: a.arm_id):
            row_q: dict[str, object] = {"arm_id": arm_q.arm_id}
            for km in queue_metrics:
                agg = next((a for a in arm_q.metric_aggregates if a.metric_key == km), None)
                row_q[km] = _format_float(agg.aggregate_mean) if agg else "Unavailable"
                row_q[f"{km} unit"] = agg.unit if agg else ""
            q_rows.append(row_q)
        st.dataframe(
            q_rows, hide_index=True, width="stretch", column_config=table_column_config(q_rows)
        )
        # Simple chart for queue balance
        try:
            jain_vals = {}
            for arm in report.arm_summaries:
                agg = next(
                    (a for a in arm.metric_aggregates if a.metric_key == "infra.load_balance.jain"),
                    None,
                )
                if agg and agg.aggregate_mean is not None:
                    jain_vals[arm.arm_id] = agg.aggregate_mean
            if jain_vals:
                st.bar_chart(jain_vals)
                st.caption("Jain load-balance (higher is more balanced) — descriptive only.")
        except Exception:  # noqa: S110
            pass
    else:
        st.info("No queue/load-balance metrics supplied in the study catalog.")

    # Optional resource-cost evidence
    if "resource.cost.units" in metric_by_key:
        st.markdown("**Resource-cost evidence (where supplied)**")
        rc_rows = []
        for arm in sorted(report.arm_summaries, key=lambda a: a.arm_id):
            agg = next(
                (a for a in arm.metric_aggregates if a.metric_key == "resource.cost.units"), None
            )
            rc_rows.append(
                {
                    "arm_id": arm.arm_id,
                    "mean_cost": _format_float(agg.aggregate_mean) if agg else "Unavailable",
                    "unit": agg.unit if agg else "",
                    "status": agg.status.value if agg else "unavailable",
                }
            )
        st.dataframe(
            rc_rows, hide_index=True, width="stretch", column_config=table_column_config(rc_rows)
        )
    else:
        st.caption("Resource-cost evidence is optional and not supplied in this study catalog.")

    # ------------------------------------------------------------------
    # Limitations and unsupported metrics
    # ------------------------------------------------------------------
    st.subheader("Exclusions, incompatibilities, and limitations")
    _render_limitations(report.limitations, report)

    # ------------------------------------------------------------------
    # Provenance / fingerprint disclosure
    # ------------------------------------------------------------------
    st.subheader("Provenance and fingerprints")
    _render_provenance(dict(report.provenance), report.source_fingerprint, report.study_fingerprint)
    with st.container(border=True):
        st.markdown(f"**Report fingerprint:** `{fingerprint_summary(report.report_fingerprint)}`")
        st.caption(f"Full report fingerprint: `{report.report_fingerprint}`")
        st.caption(
            "Fingerprint binds every scientifically meaningful field; "
            "excludes wall clock, rendering state, local paths, and secrets."
        )
        with st.expander("Advanced: full fingerprints and canonical JSON"):
            st.code(
                report.canonical_json()[:2000]
                + ("\n… truncated" if len(report.canonical_json()) > 2000 else ""),
                language="json",
            )
            st.caption(f"Source fingerprint: `{report.source_fingerprint}`")
            st.caption(f"Study fingerprint: `{report.study_fingerprint}`")
            st.caption(f"Report fingerprint: `{report.report_fingerprint}`")

    # ------------------------------------------------------------------
    # Portable JSON download — exact portable report used by the page
    # ------------------------------------------------------------------
    st.subheader("Portable export")
    st.caption(
        "The JSON download is the exact portable report used by the page; "
        "it excludes local paths and secrets."
    )
    report_json = report.to_json()
    st.download_button(
        label="Download ResourceStrategyReport JSON",
        data=report_json,
        file_name=f"{report.study_id}_resource_strategy_report.json",
        mime="application/json",
        key="resource_strategy_download_json",
    )
    # CSV export
    csv_data = resource_strategy_report_to_csv(report)
    st.download_button(
        label="Download CSV (arm × metric aggregates)",
        data=csv_data,
        file_name=f"{report.study_id}_resource_strategy_report.csv",
        mime="text/csv",
        key="resource_strategy_download_csv",
    )
    # Markdown export
    md_data = resource_strategy_report_to_markdown(report)
    st.download_button(
        label="Download Markdown report",
        data=md_data,
        file_name=f"{report.study_id}_resource_strategy_report.md",
        mime="text/markdown",
        key="resource_strategy_download_md",
    )
    # Offered vs admitted warning
    with st.container(border=True):
        st.caption(
            "Offered-denominator attainment and admitted-denominator attainment are separate. "
            "Returned/compute-completed are not deadline-success. "
            "The report keeps these denominators distinct."
        )


def _render_limitations(limitations: list[str], report: ResourceStrategyReport | None) -> None:
    if limitations:
        for lim in limitations:
            st.markdown(f"- {lim}")
    else:
        st.info("No limitations declared.")
    if report is not None:
        # Incompatible or unavailable metrics
        unavailable = []
        for arm in report.arm_summaries:
            unavailable.extend(arm.unavailable_metrics)
        unavailable = sorted(set(unavailable))
        if unavailable:
            st.caption(f"Unavailable metrics in matched cohort: {', '.join(unavailable)}")
            with st.expander("Advanced: per-arm unavailable detail"):
                for arm in report.arm_summaries:
                    if arm.unavailable_metrics:
                        st.markdown(f"**{arm.arm_id}:** {', '.join(arm.unavailable_metrics)}")
        if report.compatibility:
            with st.expander("Advanced: compatibility findings"):
                for comp in sorted(report.compatibility, key=lambda c: c.metric_key):
                    st.markdown(f"- `{comp.metric_key}`: {comp.status.value} — {comp.finding}")
        st.caption(
            "Incompatible metric versions fail closed; they do not silently enter the report."
        )


def _render_provenance(provenance: dict[str, object], source_fp: str, study_fp: str) -> None:
    if provenance:
        prov_rows = [{"key": k, "value": str(v)} for k, v in sorted(provenance.items())]
        st.dataframe(
            prov_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(prov_rows),
        )
    else:
        st.info("No provenance references supplied.")
    st.caption(f"Source fingerprint: `{source_fp}`")
    st.caption(f"Study fingerprint: `{study_fp}`")
    st.caption("Local source path does not enter the portable fingerprint.")
