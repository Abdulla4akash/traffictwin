"""Multi-Objective Trade-Off Explorer page — Pareto/constraint explorer over compatible policy arms."""  # noqa: E501

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.experiments.resource_strategy import (
    ResourceStrategyAdmissionState,
    ResourceStrategyEvidenceMode,
    ResourceStrategyStudy,
    load_resource_strategy_study_from_json,
)
from traffictwin.experiments.tradeoff_explorer import (
    TradeoffAdmissionState,
    TradeoffConstraint,
    TradeoffConstraintOperator,
    TradeoffDirection,
    TradeoffEvidenceMode,
    TradeoffStudy,
    build_tradeoff_report,
    load_tradeoff_study_from_json,
    tradeoff_frontier_to_csv,
    tradeoff_report_to_csv,
    tradeoff_report_to_json,
    tradeoff_report_to_markdown,
    tradeoff_study_from_resource_strategy_study,
)
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.components.first_run import first_run_guidance
from traffictwin.ui.labels import UiPage
from traffictwin.ui.tables import table_column_config


def _badge_for_evidence(mode: object) -> str:
    val = str(getattr(mode, "value", mode)).lower()
    if "synthetic" in val:
        return badge_markdown("synthetic")
    if "admitted" in val and "unadmitted" not in val:
        return ":green-badge[ADMITTED RESEARCH]"
    if "unadmitted" in val:
        return ":red-badge[UNADMITTED RESEARCH]"
    if "imported" in val:
        return ":blue-badge[IMPORTED]"
    if "historical" in val:
        return ":violet-badge[HISTORICAL]"
    return ":gray-badge[UNAVAILABLE]"


def _badge_for_admission(state: object) -> str:
    val = str(getattr(state, "value", state)).lower()
    if "synthetic" in val:
        return badge_markdown("synthetic")
    if val == "admitted":
        return ":green-badge[ADMITTED]"
    if val == "unadmitted":
        return ":red-badge[UNADMITTED]"
    if val == "rejected":
        return ":red-badge[REJECTED]"
    if val == "pending":
        return ":orange-badge[PENDING]"
    return ":gray-badge[UNAVAILABLE]"


def _format_float(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{value:.6g}"


def _try_load_tradeoff_study(text: str) -> TradeoffStudy | ResourceStrategyStudy | str:
    try:
        return load_tradeoff_study_from_json(text)
    except Exception:  # noqa: S110
        pass
    try:
        return load_resource_strategy_study_from_json(text)
    except Exception as exc:
        return f"Study artifact is invalid: {exc}"


def _load_study_from_path(path: Path) -> TradeoffStudy | ResourceStrategyStudy | str:
    if not path.exists():
        return f"Study artifact not found: {path}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Could not read study artifact: {exc}"
    return _try_load_tradeoff_study(text)


def _load_study_from_upload(uploaded: str) -> TradeoffStudy | ResourceStrategyStudy | str:
    return _try_load_tradeoff_study(uploaded)


def _study_or_empty_state() -> TradeoffStudy | ResourceStrategyStudy | None:
    default_fixture = Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    study_path_str = str(st.session_state.get("tradeoff_study_path", str(default_fixture)))
    col_a, col_b = st.columns([3, 1])
    with col_a:
        new_path = st.text_input(
            "Study artifact path",
            value=study_path_str,
            help="Path to a validated TradeoffStudy or ResourceStrategy study JSON.",
            key="tradeoff_path_input",
        )
        if new_path != study_path_str:
            st.session_state["tradeoff_study_path"] = new_path
    with col_b:
        if st.button("Load synthetic fixture", key="tradeoff_load_fixture"):
            st.session_state["tradeoff_study_path"] = str(default_fixture)
            st.session_state.pop("tradeoff_uploaded", None)
            st.rerun()

    uploaded_file = st.file_uploader(
        "Or upload a study JSON (TradeoffStudy or ResourceStrategy-style)",
        type=["json"],
        key="tradeoff_uploader",
    )
    uploaded_text: str | None = None
    if uploaded_file is not None:
        try:
            uploaded_text = uploaded_file.getvalue().decode("utf-8")
            st.session_state["tradeoff_uploaded"] = uploaded_text
        except Exception as exc:
            st.error(f"Could not read uploaded file: {exc}")
            return None
    else:
        uploaded_text = st.session_state.get("tradeoff_uploaded")

    if uploaded_text:
        result = _load_study_from_upload(uploaded_text)
        if isinstance(result, str):
            st.error(result)
            return None
        return result

    path_str = str(st.session_state.get("tradeoff_study_path", "") or "")
    if not path_str.strip():
        st.info(
            "No study artifact selected. Enter a path to a validated TradeoffStudy JSON or "
            "a ResourceStrategy-style matched-cohort JSON, or upload one. The synthetic "
            "demonstration fixture is available at `tests/fixtures/resource_strategy/synthetic_study_v1.json`."  # noqa: E501
        )
        first_run_guidance(
            actions=[(UiPage.HOME, UiPage.HOME), (UiPage.GUIDED_DEMO, UiPage.GUIDED_DEMO)],
            message=(
                "A Trade-Off Explorer study needs a validated artifact. Use the synthetic "
                "demonstration fixture to explore the workflow, or provide your own admitted study."
            ),
            key_prefix="tradeoff_empty",
        )
        return None

    result2 = _load_study_from_path(Path(path_str))
    if isinstance(result2, str):
        if "not found" in result2.lower():
            st.info(
                "No admitted study exists at the selected path. The page has a useful "
                "empty state when no admitted study exists. Provide a validated "
                "admitted or synthetic demonstration artifact to continue."
            )
            first_run_guidance(
                actions=[(UiPage.HOME, UiPage.HOME)],
                message=result2,
                key_prefix="tradeoff_not_found",
            )
            return None
        st.error(result2)
        return None
    return result2


def _render_limitations(limitations: list[str]) -> None:
    if limitations:
        for lim in limitations:
            st.markdown(f"- {lim}")
    else:
        st.info("No limitations declared.")


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


def render(config: object) -> None:  # noqa: ANN001
    # One authoritative H1 — do not duplicate via shared navigation header (page not yet in UiPage enum; Fable registers via JSON)  # noqa: E501
    st.caption("TrafficTwin / Multi-Objective Trade-Off Explorer")
    st.title("Multi-Objective Trade-Off Explorer")

    st.caption(
        "Within-study multi-objective comparison across compatible policy arms. "
        "This is a Pareto/constraint explorer. It does not invent a single winner unless a fully declared scalar decision rule explicitly selects one. "  # noqa: E501
        "No metric is weighted or normalised silently."
    )

    st.warning(
        "Evidence boundary: Synthetic demonstration evidence is labelled synthetic and must not be presented as the actual E2 result. "  # noqa: E501
        "An unadmitted study is not admitted; results are withheld until admission is explicit. "
        "Unknown or incompatible metrics are withheld and produce no numeric aggregate for that metric. "  # noqa: E501
        "Differences are descriptive, not causal, and no best, optimal, winner, or recommended claim is made without a declared decision contract."  # noqa: E501
    )

    st.info(
        "Authority boundary: This explorer is descriptive. Frontier means non-dominated under declared metrics and feasible constraints. "  # noqa: E501
        "Feasible means feasible under declared constraints; infeasible means violates declared constraint. "  # noqa: E501
        "Use limitations, provenance, and compatibility audit before interpreting any frontier."
    )

    study_input = _study_or_empty_state()
    if study_input is None:
        return

    # Determine if input is TradeoffStudy or ResourceStrategyStudy
    tradeoff_study: TradeoffStudy | None = None
    rs_study: ResourceStrategyStudy | None = None
    if isinstance(study_input, TradeoffStudy):
        tradeoff_study = study_input
        st.subheader("Study and admission")
        banner_cols = st.columns(4)
        banner_cols[0].markdown(
            f"**Evidence mode:** {_badge_for_evidence(tradeoff_study.evidence_mode)}"
        )
        banner_cols[1].markdown(
            f"**Admission state:** {_badge_for_admission(tradeoff_study.admission_state)}"
        )
        banner_cols[2].metric("Study ID", tradeoff_study.study_id, border=True)
        banner_cols[3].metric("Arms", str(len(tradeoff_study.arms)), border=True)
        with st.container(border=True):
            st.markdown(
                f"**Source fingerprint:** `{fingerprint_summary(tradeoff_study.source_fingerprint)}`"  # noqa: E501
            )
            st.caption(f"Full source fingerprint: `{tradeoff_study.source_fingerprint}`")
            st.markdown(
                f"**Study fingerprint:** `{fingerprint_summary(tradeoff_study.fingerprint())}`"
            )
            st.caption(f"Full study fingerprint: `{tradeoff_study.fingerprint()}`")
            st.caption(
                f"Schema version: {tradeoff_study.schema_version} | Matched replications: {len(tradeoff_study.matched_replication_ids)}"  # noqa: E501
            )
            if tradeoff_study.evidence_mode == TradeoffEvidenceMode.SYNTHETIC_DEMONSTRATION:
                st.info(
                    "SYNTHETIC DEMONSTRATION — This is synthetic demonstration evidence. It is not the actual E2 result and not Manchester observation."  # noqa: E501
                )
        # Refusal for unadmitted
        if tradeoff_study.admission_state in (
            TradeoffAdmissionState.UNADMITTED,
            TradeoffAdmissionState.REJECTED,
            TradeoffAdmissionState.PENDING,
            TradeoffAdmissionState.UNAVAILABLE,
        ):
            st.error(
                f"Study admission state is `{tradeoff_study.admission_state.value}`. Results are withheld; an unadmitted study must not be treated as admitted."  # noqa: E501
            )
            _render_limitations(tradeoff_study.limitations)
            _render_provenance(
                dict(tradeoff_study.provenance),
                tradeoff_study.source_fingerprint,
                tradeoff_study.fingerprint(),
            )
            return
        # Direct tradeoff study — build report immediately with its declared specs
        try:
            report = build_tradeoff_report(tradeoff_study)
        except Exception as exc:
            st.error(f"Report could not be built (fail-closed): {exc}")
            return
        _render_report(report, tradeoff_study)

    elif isinstance(study_input, ResourceStrategyStudy):
        rs_study = study_input
        st.subheader("Study and admission (ResourceStrategy source)")
        banner_cols = st.columns(4)
        banner_cols[0].markdown(f"**Evidence mode:** {_badge_for_evidence(rs_study.evidence_mode)}")
        banner_cols[1].markdown(
            f"**Admission state:** {_badge_for_admission(rs_study.admission_state)}"
        )
        banner_cols[2].metric("Study ID", rs_study.study_id, border=True)
        banner_cols[3].metric("Arms", str(len(rs_study.arms)), border=True)
        with st.container(border=True):
            st.markdown(
                f"**Source fingerprint:** `{fingerprint_summary(rs_study.source_fingerprint)}`"
            )
            st.caption(f"Full source fingerprint: `{rs_study.source_fingerprint}`")
            st.markdown(f"**Study fingerprint:** `{fingerprint_summary(rs_study.fingerprint())}`")
            st.caption(f"Full study fingerprint: `{rs_study.fingerprint()}`")
            st.caption(
                f"Schema version: {rs_study.schema_version} | Matched replications: {len(rs_study.common_matched_replication_ids)}"  # noqa: E501
            )
            if rs_study.evidence_mode == ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION:
                st.info(
                    "SYNTHETIC DEMONSTRATION — This is synthetic demonstration evidence resembling strongest-link, deterministic JSQ, and JSQ + deadline-aware admission. It is not the actual E2 result and not Manchester observation."  # noqa: E501
                )
        if rs_study.admission_state in (
            ResourceStrategyAdmissionState.UNADMITTED,
            ResourceStrategyAdmissionState.REJECTED,
            ResourceStrategyAdmissionState.PENDING,
            ResourceStrategyAdmissionState.UNAVAILABLE,
        ):
            st.error(
                f"Study admission state is `{rs_study.admission_state.value}`. Results are withheld; an unadmitted study must not be treated as admitted."  # noqa: E501
            )
            _render_limitations(rs_study.limitations)
            _render_provenance(
                dict(rs_study.provenance), rs_study.source_fingerprint, rs_study.fingerprint()
            )
            return

        # Metric selection for tradeoff
        catalog_keys = sorted(m.metric_key for m in rs_study.metric_catalog)
        st.subheader("1. Select metrics for trade-off (2–6)")
        st.caption(
            "Choose 2–6 compatible metrics. Direction and optional hard constraints are confirmed below; no metric is weighted or normalised silently."  # noqa: E501
        )
        # Default selection: up to 3 compatible metrics with known directions
        try:
            from traffictwin.experiments.resource_strategy import (
                build_resource_strategy_report as _build_rs_report,
            )  # noqa: PLC0415

            _rs_report = _build_rs_report(rs_study)
            compat_ok = [
                c.metric_key for c in _rs_report.compatibility if c.status.value == "compatible"
            ]
            default_metrics = sorted(compat_ok)[:4] if len(compat_ok) >= 2 else catalog_keys[:3]
        except Exception:
            default_metrics = catalog_keys[:3]
        if len(default_metrics) < 2 and len(catalog_keys) >= 2:
            default_metrics = catalog_keys[:2]
        # Ensure default within bounds
        if len(default_metrics) > 6:
            default_metrics = default_metrics[:6]

        selected_metrics = st.multiselect(
            "Metrics for Pareto frontier (2–6)",
            catalog_keys,
            default=default_metrics,
            key="tradeoff_selected_metrics",
        )
        if len(selected_metrics) < 2:
            st.info(
                "Select at least two metrics to build the trade-off explorer. One metric cannot define a trade-off."  # noqa: E501
            )
            return
        if len(selected_metrics) > 6:
            st.error("Select at most 6 metrics.")
            return

        st.subheader("2. Confirm direction and optional hard constraints")
        st.caption(
            "Direction must be declared per metric. Optional hard constraints make an arm infeasible when violated. Violates declared constraint is the only infeasibility wording."  # noqa: E501
        )
        # Build direction and constraint inputs
        direction_choices: dict[str, TradeoffDirection] = {}
        constraint_inputs: dict[str, TradeoffConstraint | None] = {}
        for metric_key in sorted(selected_metrics):
            # Find catalog entry for default direction
            cat = next((m for m in rs_study.metric_catalog if m.metric_key == metric_key), None)
            default_direction = (
                "minimize"
                if cat
                and any(x in metric_key for x in ("latency", "energy", "cost", "queue"))
                and "jain" not in metric_key
                else "maximize"
            )
            # Override with authoritative higher_is_better if known
            try:
                from traffictwin.metrics.catalogue import METRIC_DEFINITIONS  # noqa: PLC0415

                defn = METRIC_DEFINITIONS.get(metric_key)
                if defn is not None and defn.higher_is_better is not None:
                    default_direction = "maximize" if defn.higher_is_better else "minimize"
                elif metric_key in (
                    "infra.load_balance.jain",
                    "task.completion.rate_offered",
                    "task.completion.rate_admitted",
                    "task.deadline_success.rate_offered",
                ):
                    default_direction = "maximize"
                elif metric_key in (
                    "infra.queue_length.mean",
                    "task.latency.mean_ms",
                    "task.latency.p95_ms",
                    "task.energy.mean_j",
                    "resource.cost.units",
                ):
                    default_direction = "minimize"
            except Exception:  # noqa: S110
                pass
            col_d, col_op, col_thr = st.columns([2, 2, 2])
            with col_d:
                dir_label = st.selectbox(
                    f"Direction for {metric_key}",
                    ["maximize", "minimize"],
                    index=0 if default_direction == "maximize" else 1,
                    key=f"tradeoff_dir_{metric_key}",
                    help="maximize = higher is better; minimize = lower is better. No weighting is applied.",  # noqa: E501
                )
                direction_choices[metric_key] = (
                    TradeoffDirection.MAXIMIZE
                    if dir_label == "maximize"
                    else TradeoffDirection.MINIMIZE
                )
            with col_op:
                op_choice = st.selectbox(
                    f"Constraint operator for {metric_key} (or none)",
                    ["none", "<=", ">=", "<", ">"],
                    index=0,
                    key=f"tradeoff_op_{metric_key}",
                )
            with col_thr:
                thr_val = st.number_input(
                    f"Threshold for {metric_key}",
                    value=0.0,
                    step=1.0,
                    key=f"tradeoff_thr_{metric_key}",
                    help="Threshold for hard constraint; leave operator as none for no constraint.",
                )
            if op_choice != "none":
                try:
                    op_enum = TradeoffConstraintOperator(op_choice)
                    constraint_inputs[metric_key] = TradeoffConstraint(
                        metric_key=metric_key,
                        operator=op_enum,
                        threshold=float(thr_val),
                        reason="declared hard constraint",
                    )
                except Exception as exc:
                    st.error(f"Invalid constraint for {metric_key}: {exc}")
                    return
            else:
                constraint_inputs[metric_key] = None
            st.caption(
                f"Declared: {metric_key} | version `{cat.metric_version if cat else '?'}` | unit `{cat.unit if cat else '?'}` | denominator `{cat.denominator.value if cat and hasattr(cat.denominator, 'value') else '?'}` | direction `{dir_label}`"  # noqa: E501
            )
            if op_choice != "none":
                st.caption(
                    f"Hard constraint: {metric_key} {op_choice} {thr_val:.6g} — infeasible when violated"  # noqa: E501
                )

        # Build tradeoff study via adapter
        directions_map = dict(direction_choices)
        constraints_map = {k: v for k, v in constraint_inputs.items() if v is not None}
        try:
            tradeoff_study_adapted = tradeoff_study_from_resource_strategy_study(
                rs_study,
                metric_keys=sorted(selected_metrics),
                directions=directions_map,
                constraints=constraints_map if constraints_map else None,
            )
        except Exception as exc:
            st.error(f"Trade-off study could not be adapted (fail-closed): {exc}")
            return

        # Build report — thin UI, delegates to typed service
        try:
            report = build_tradeoff_report(tradeoff_study_adapted)
        except Exception as exc:
            st.error(f"Trade-off report could not be built (fail-closed): {exc}")
            return
        _render_report(report, tradeoff_study_adapted, rs_source=True)
    else:
        st.error("Unsupported study artifact type.")
        return


def _render_report(report: object, study: TradeoffStudy, rs_source: bool = False) -> None:
    # Narrow type
    from traffictwin.experiments.tradeoff_explorer import TradeoffReport  # noqa: PLC0415

    assert isinstance(report, TradeoffReport)

    # Compatibility audit
    st.subheader("Compatibility audit")
    st.caption(
        "Authoritative compatibility is checked against the registered contract on main. Unknown or incompatible metrics are explicit and withheld from numeric aggregates."  # noqa: E501
    )
    if report.compatibility:
        comp_rows = []
        for comp in sorted(report.compatibility, key=lambda c: c.metric_key):
            comp_rows.append(
                {
                    "metric_key": comp.metric_key,
                    "status": comp.status.value,
                    "finding": comp.finding,
                    "expected_version": comp.expected_version or "",
                    "expected_unit": comp.expected_unit or "",
                }
            )
        st.dataframe(
            comp_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(comp_rows),
        )
        for comp in report.compatibility:
            if comp.status.value == "incompatible":
                st.warning(
                    f"`{comp.metric_key}` is incompatible ({comp.finding}); numeric aggregate withheld for that metric."  # noqa: E501
                )
            elif comp.status.value == "unavailable":
                st.info(
                    f"`{comp.metric_key}` has no registered compatibility contract; treated as unavailable unless input carried an authoritative compatible contract."  # noqa: E501
                )
    else:
        st.info("No compatibility findings.")

    # Feasibility table
    st.subheader("Per-arm feasibility and constraint violations")
    st.caption(
        "Feasible means feasible under declared metrics and constraints; infeasible means violates declared constraint. Incompatible or unavailable metrics are withheld."  # noqa: E501
    )
    feas_rows = []
    for feas in sorted(report.feasibility, key=lambda f: f.arm_id):
        feas_rows.append(
            {
                "arm_id": feas.arm_id,
                "status": feas.status.value,
                "is_feasible": str(feas.is_feasible),
                "violations": "; ".join(feas.violation_messages)
                if feas.violation_messages
                else "none",
                "unavailable_metrics": ", ".join(feas.unavailable_metrics)
                if feas.unavailable_metrics
                else "none",
                "incompatible_metrics": ", ".join(feas.incompatible_metrics)
                if feas.incompatible_metrics
                else "none",
                "reason": feas.reason,
            }
        )
    st.dataframe(
        feas_rows, hide_index=True, width="stretch", column_config=table_column_config(feas_rows)
    )
    feasible_count = sum(1 for f in report.feasibility if f.is_feasible)
    st.caption(
        f"Feasible arms: {feasible_count} of {len(report.feasibility)} — descriptive only, not a winner selection."  # noqa: E501
    )

    # Pareto chart
    st.subheader("Pareto frontier (descriptive frontier)")
    st.caption(
        "Non-dominated among feasible arms under declared metrics. Descriptive frontier only; no best, optimal, winner, or recommended claim is made."  # noqa: E501
    )
    if not report.frontier.frontier_arm_ids and feasible_count == 0:
        st.info(
            "No feasible arms to display a Pareto frontier. All arms are infeasible or unavailable under declared constraints and metrics."  # noqa: E501
        )
    elif len(report.metric_specs) == 2 and feasible_count >= 1:
        # 2D scatter
        try:
            import plotly.graph_objects as go  # noqa: PLC0415

            specs = sorted(report.metric_specs, key=lambda s: s.metric_key)
            kx, ky = specs[0].metric_key, specs[1].metric_key
            # Need values per arm
            # Recover values from study's observations
            arm_vals: dict[str, dict[str, float | None]] = {}
            for arm in study.arms:
                d = {o.metric_key: o.value for o in arm.observations}
                arm_vals[arm.arm_id] = d
            # Separate frontier vs dominated feasible vs infeasible
            fig = go.Figure()
            for feas in sorted(report.feasibility, key=lambda f: f.arm_id):
                aid = feas.arm_id
                vals = arm_vals.get(aid, {})
                vx = vals.get(kx)
                vy = vals.get(ky)
                if vx is None or vy is None:
                    continue
                is_frontier = aid in report.frontier.frontier_arm_ids
                is_feasible = feas.is_feasible
                if is_frontier:
                    color = "green"
                    symbol = "diamond"
                    name = f"{aid} — non-dominated (feasible)"
                elif is_feasible:
                    color = "blue"
                    symbol = "circle"
                    name = f"{aid} — feasible dominated"
                else:
                    color = "red"
                    symbol = "x"
                    name = f"{aid} — infeasible/unavailable ({feas.status.value})"
                fig.add_trace(
                    go.Scatter(
                        x=[vx],
                        y=[vy],
                        mode="markers",
                        marker={
                            "color": color,
                            "size": 14,
                            "symbol": symbol,
                            "line": {"width": 1, "color": "black"},
                        },  # noqa: E501
                        name=name,
                        hovertemplate=f"{aid}<br>{kx}: %{{x:.6g}}<br>{ky}: %{{y:.6g}}<extra></extra>",  # noqa: E501
                    )
                )
            fig.update_layout(
                title=f"Descriptive Pareto (feasible arms) — {kx} vs {ky}",
                xaxis_title=f"{kx} ({specs[0].unit}, {specs[0].direction.value})",
                yaxis_title=f"{ky} ({specs[1].unit}, {specs[1].direction.value})",
                legend={
                    "orientation": "h",
                    "yanchor": "bottom",
                    "y": -0.3,
                    "xanchor": "center",
                    "x": 0.5,
                },  # noqa: E501
                height=500,
            )
            st.plotly_chart(fig, width="stretch", key="tradeoff_pareto_chart")
            # Also show sorted table for screen readers
            chart_rows = []
            for feas in sorted(report.feasibility, key=lambda f: f.arm_id):
                vals = arm_vals.get(feas.arm_id, {})
                chart_rows.append(
                    {
                        "arm_id": feas.arm_id,
                        "status": feas.status.value,
                        "is_feasible": str(feas.is_feasible),
                        "on_frontier": str(feas.arm_id in report.frontier.frontier_arm_ids),
                        kx: _format_float(vals.get(kx)),
                        ky: _format_float(vals.get(ky)),
                    }
                )
            st.dataframe(
                chart_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(chart_rows),
            )
        except Exception as exc:  # noqa: BLE001
            st.caption(f"Pareto chart unavailable: {exc}")
            # Fallback table
            arm_vals_fallback: dict[str, dict[str, float | None]] = {}
            for arm in study.arms:
                arm_vals_fallback[arm.arm_id] = {o.metric_key: o.value for o in arm.observations}
            rows = []
            for feas in sorted(report.feasibility, key=lambda f: f.arm_id):
                vals = arm_vals_fallback.get(feas.arm_id, {})
                rows.append(
                    {
                        "arm_id": feas.arm_id,
                        "feasible": str(feas.is_feasible),
                        "on_frontier": str(feas.arm_id in report.frontier.frontier_arm_ids),
                        **{k: _format_float(v) for k, v in vals.items()},
                    }
                )
            st.dataframe(
                rows, hide_index=True, width="stretch", column_config=table_column_config(rows)
            )
    else:
        # N>2 or single feasible case: table + dominated-by
        st.caption(
            f"Pareto frontier shown as table for {len(report.metric_specs)} metrics (descriptive)."
        )
        arm_vals_multi: dict[str, dict[str, float | None]] = {}
        for arm in study.arms:
            arm_vals_multi[arm.arm_id] = {o.metric_key: o.value for o in arm.observations}
        frontier_rows = []
        for feas in sorted(report.feasibility, key=lambda f: f.arm_id):
            row: dict[str, object] = {
                "arm_id": feas.arm_id,
                "status": feas.status.value,
                "is_feasible": str(feas.is_feasible),
                "on_frontier": str(feas.arm_id in report.frontier.frontier_arm_ids),
                "dominated_by": ", ".join(report.frontier.dominated_by.get(feas.arm_id, []))
                or "none",
            }
            for spec in sorted(report.metric_specs, key=lambda s: s.metric_key):
                row[spec.metric_key] = _format_float(
                    arm_vals_multi.get(feas.arm_id, {}).get(spec.metric_key)
                )
            frontier_rows.append(row)
        st.dataframe(
            frontier_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(frontier_rows),
        )
        st.caption(
            f"Descriptive frontier arms: {', '.join(report.frontier.frontier_arm_ids) if report.frontier.frontier_arm_ids else 'none'}"  # noqa: E501
        )
        if report.frontier.dominated_arm_ids:
            st.caption(f"Dominated arms: {', '.join(report.frontier.dominated_arm_ids)}")

    # Dominance matrix
    st.subheader("Dominance matrix (descriptive, feasible arms only)")
    st.caption(
        "Rows dominate columns when the row arm dominates under declared metrics. Dominates under declared metrics is the only dominance wording."  # noqa: E501
    )
    if report.dominance:
        # Build matrix table
        feasible_ids = sorted(
            report.frontier.all_feasible_arm_ids
            or [f.arm_id for f in report.feasibility if f.is_feasible]
        )
        if feasible_ids:
            matrix_rows = []
            dom_lookup = {
                (d.dominator_arm_id, d.dominated_arm_id): d.dominates for d in report.dominance
            }
            for row_id in feasible_ids:
                r: dict[str, object] = {"dominator \\ dominated": row_id}
                for col_id in feasible_ids:
                    if row_id == col_id:
                        r[col_id] = "—"
                    else:
                        dominates = dom_lookup.get((row_id, col_id), False)
                        r[col_id] = (
                            "dominates under declared metrics" if dominates else "does not dominate"
                        )
                matrix_rows.append(r)
            st.dataframe(
                matrix_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(matrix_rows),
            )
            # Also show dominated-by list
            with st.expander("Advanced: per-arm dominated-by detail"):
                for arm_id in sorted(report.frontier.dominated_by):
                    dominators = report.frontier.dominated_by.get(arm_id, [])
                    if dominators:
                        st.markdown(
                            f"`{arm_id}` is dominated by `{', '.join(dominators)}` under declared metrics"  # noqa: E501
                        )
                    else:
                        st.markdown(f"`{arm_id}` is non-dominated (feasible)")
        else:
            st.info("No feasible arms to compute pairwise dominance.")
        # Also raw dominance list
        with st.expander("Advanced: raw dominance relationships"):
            dom_rows = []
            for dom in sorted(
                report.dominance, key=lambda d: (d.dominator_arm_id, d.dominated_arm_id)
            ):
                dom_rows.append(
                    {
                        "dominator": dom.dominator_arm_id,
                        "dominated": dom.dominated_arm_id,
                        "dominates": str(dom.dominates),
                        "reason": dom.reason,
                    }
                )
            st.dataframe(
                dom_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(dom_rows),
            )
    else:
        st.info("Dominance matrix unavailable (fewer than two feasible arms).")

    # Matched-replication stability
    st.subheader("Matched-replication stability")
    st.caption(
        "Per-replication descriptive frontier stability over the matched cohort. Unavailable when per-replication values are not disclosed."  # noqa: E501
    )
    # Distinguish None (unavailable) from 0.0 (genuine zero)  # noqa: E501
    # Only consider numeric stabilities for chart; unavailable is not 0.0
    numeric_stabs = {k: v for k, v in report.replication_stability.items() if v is not None}
    has_any_stability_key = bool(report.replication_stability)
    if has_any_stability_key:
        stab_rows = []
        for arm_id, stab in sorted(report.replication_stability.items()):
            stab_display = f"{stab:.3f}" if stab is not None else "Unavailable"
            stab_rows.append(
                {
                    "arm_id": arm_id,
                    "stability_on_frontier": stab_display,
                    "is_feasible": str(
                        any(f.arm_id == arm_id and f.is_feasible for f in report.feasibility)
                    ),
                }
            )
        st.dataframe(
            stab_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(stab_rows),
        )
        # Bar chart only numeric values; None excluded
        try:
            chart_data = {k: float(v) for k, v in numeric_stabs.items()}
            if chart_data:
                st.bar_chart(chart_data, horizontal=False)
                st.caption(
                    "Stability = proportion of matched replications where the arm was on the descriptive frontier (feasible arms only). Unavailable is not zero."  # noqa: E501
                )
            elif has_any_stability_key:
                st.info(
                    "Matched-replication stability unavailable for all arms (no complete per-replication evidence); no bar chart rendered."  # noqa: E501
                )
        except Exception:  # noqa: S110
            pass
    else:
        st.info("Matched-replication stability unavailable for this study.")
    # Findings for stability
    stability_findings = [f for f in report.findings if "REPLICATION_STABILITY" in f.code]
    if stability_findings:
        with st.expander("Advanced: stability findings"):
            for f in stability_findings:
                st.markdown(f"- `{f.code}`: {f.message}")

    # Sensitivity
    if report.sensitivity:
        st.subheader("Sensitivity to declared constraints")
        st.caption(
            "Descriptive frontier with versus without hard constraints — sensitivity is descriptive, not a recommendation."  # noqa: E501
        )
        st.markdown(
            f"**Frontier with constraints:** `{', '.join(report.sensitivity.get('frontier_with_constraints', []) or ['none'])}`"  # noqa: E501
        )
        st.markdown(
            f"**Frontier without constraints:** `{', '.join(report.sensitivity.get('frontier_without_constraints', []) or ['none'])}`"  # noqa: E501
        )
        if report.sensitivity.get("frontier_with_constraints") != report.sensitivity.get(
            "frontier_without_constraints"
        ):
            st.info(
                "Descriptive frontier changes when declared constraints are removed (see finding)."
            )
        else:
            st.caption("Descriptive frontier unchanged when declared constraints are removed.")

    # Findings: missing/incompatible
    st.subheader("Missing and incompatible metric reasons")
    finding_rows = []
    for finding in sorted(
        report.findings, key=lambda f: (f.code, f.arm_id or "", f.metric_key or "")
    ):
        if finding.code in (
            "MISSING_METRIC_UNAVAILABLE",
            "INCOMPATIBLE_METRIC_WITHHELD",
            "UNAVAILABLE_METRIC_EXCLUDED",
            "CONSTRAINT_VIOLATED",
            "CONSTRAINT_SENSITIVITY_UNAVAILABLE",
        ):
            finding_rows.append(
                {
                    "code": finding.code,
                    "arm_id": finding.arm_id or "—",
                    "metric": finding.metric_key or "—",
                    "message": finding.message,
                }
            )
    if finding_rows:
        st.dataframe(
            finding_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(finding_rows),
        )
    else:
        st.caption(
            "No missing or incompatible metrics beyond feasibility table; all selected metrics were available and compatible for feasible arms."  # noqa: E501
        )

    # Limitations
    st.subheader("Exclusions, incompatibilities, and limitations")
    _render_limitations(report.limitations)
    if report.findings:
        with st.expander("Advanced: all findings"):
            for finding in sorted(
                report.findings, key=lambda f: (f.code, f.arm_id or "", f.metric_key or "")
            ):
                st.markdown(f"- `{finding.code}` ({finding.severity}): {finding.message}")
    st.caption(
        "Incompatible metric versions fail closed; they do not silently enter the report. No numeric aggregate is produced for an incompatible metric."  # noqa: E501
    )

    # Provenance and fingerprints
    st.subheader("Provenance and fingerprints")
    _render_provenance(dict(report.provenance), report.source_fingerprint, report.study_fingerprint)
    with st.container(border=True):
        st.markdown(f"**Report fingerprint:** `{fingerprint_summary(report.report_fingerprint)}`")
        st.caption(f"Full report fingerprint: `{report.report_fingerprint}`")
        st.caption(
            "Fingerprint binds every scientifically meaningful field; excludes wall clock, rendering state, local paths, and secrets."  # noqa: E501
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

    # Exports
    st.subheader("Portable export")
    st.caption(
        "The JSON download is the exact portable report used by the page; it excludes local paths and secrets."  # noqa: E501
    )
    report_json = tradeoff_report_to_json(report)
    st.download_button(
        label="Download TradeoffReport JSON",
        data=report_json,
        file_name=f"{report.study_id}_tradeoff_report.json",
        mime="application/json",
        key="tradeoff_download_json",
    )
    csv_data = tradeoff_report_to_csv(report)
    st.download_button(
        label="Download CSV (arm × metric feasibility)",
        data=csv_data,
        file_name=f"{report.study_id}_tradeoff_report.csv",
        mime="text/csv",
        key="tradeoff_download_csv",
    )
    frontier_csv = tradeoff_frontier_to_csv(report)
    st.download_button(
        label="Download CSV (frontier)",
        data=frontier_csv,
        file_name=f"{report.study_id}_frontier.csv",
        mime="text/csv",
        key="tradeoff_download_frontier_csv",
    )
    md_data = tradeoff_report_to_markdown(report)
    st.download_button(
        label="Download Markdown report",
        data=md_data,
        file_name=f"{report.study_id}_tradeoff_report.md",
        mime="text/markdown",
        key="tradeoff_download_md",
    )
    with st.container(border=True):
        st.caption(
            "Direct policy comparison is descriptive. A scalar decision rule must be fully declared to select a single policy; otherwise the explorer shows the descriptive frontier only."  # noqa: E501
        )
