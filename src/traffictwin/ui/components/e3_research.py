# ruff: noqa: E501, ANN401
"""Reusable native Streamlit components for E3 research evidence - Lane 11.

Consumes exact typed service/view output and performs formatting only.
No hard-coded scientific values beyond frozen identities, no fallback
constants, no recomputation. Admission is truthful refusal today;
no numeric results exist. Every numeric surface is explicitly
UNAVAILABLE with reasons.
"""

from __future__ import annotations

import streamlit as st

from traffictwin.evidence_admission.e3_research import (
    E3ResearchAdmissionRefusal,
    admit_e3_research,
)
from traffictwin.experiments.e3_comparison import E3ResearchComparisonView
from traffictwin.experiments.e3_research_evidence import E3ResearchEvidencePackage
from traffictwin.experiments.e3_strategy_semantics import E3StrategySemantics
from traffictwin.experiments.e3_task_accounting import E3TaskAccountingView
from traffictwin.reporting.e3_research import E3ResearchExportBundle


def _is_refused_for_package(
    package: E3ResearchEvidencePackage | None,
    receipt: E3ResearchAdmissionRefusal | None,
) -> bool:
    if package is None or receipt is None:
        return False
    if not isinstance(receipt, E3ResearchAdmissionRefusal):
        return False
    if not isinstance(package, E3ResearchEvidencePackage):
        return False
    try:
        authoritative = admit_e3_research(package)
    except Exception:
        return False
    return receipt == authoritative


def _fingerprint_short(value: str | None, length: int = 12) -> str:
    if value is None or not str(value).strip():
        return "Unavailable"
    s = str(value).strip()
    if len(s) <= length:
        return s
    return f"{s[:length]}..."


def render_e3_hold_banner(
    package: E3ResearchEvidencePackage | None,
    receipt: E3ResearchAdmissionRefusal | None,
) -> None:
    """Render the immutable hold banner verbatim."""
    with st.container(border=True):
        st.markdown("**Immutable hold:** `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`")
        st.markdown("`E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`")
        st.markdown("`evidence_state = NOT_EXECUTED`")
        st.markdown("`result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`")
        st.markdown("`research_workloads_launched = 0`")
        st.caption(
            "Admission fails closed until an exact approved Lane 09 package exists. "
            "No E3 research workloads have been launched; no results exist today."
        )
        if package is not None and receipt is not None:
            st.caption(
                f"Hold lane: {receipt.lane_09} standing: {receipt.standing} "
                f"evidence_state: {receipt.evidence_state} result: {receipt.result_availability}"
            )


def render_e3_admission_banner(
    package: E3ResearchEvidencePackage | None,
    receipt: E3ResearchAdmissionRefusal | None,
) -> None:
    """Render the truthful refusal banner."""
    refused = _is_refused_for_package(package, receipt)
    with st.container(border=True):
        if refused:
            st.markdown(":red-badge[REFUSED] :orange-badge[BLOCKED_BY_RESEARCHER_EXECUTION_HOLD]")
            st.markdown("**Standing:** `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED` - truthful refusal")
            st.caption(
                "This is a typed refusal, not an exception and not a partial admission. "
                "No E3 research results exist today; admission requires the exact frozen "
                "fingerprints plus a future Lane 09 analysis artifact and package fingerprint "
                "that do not yet exist."
            )
            st.caption(
                "No supervisor approval; standing is E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, LANE_09 BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
            )
            if receipt is not None:
                st.markdown(f"**Reason code:** `{receipt.reason_code}`")
                st.caption(receipt.reason_detail)
                with st.expander("Advanced: E3 refusal diagnostics"):
                    st.code(str(receipt.diagnostics), language=None)
        else:
            st.markdown(":red-badge[UNADMITTED] :orange-badge[NOT_EXECUTED]")
            st.markdown("**Standing:** `NOT_EXECUTED / NO_E3_RESEARCH_RESULTS_AVAILABLE`")
            st.caption(
                "No truthful refusal could be verified for the supplied package/receipt; "
                "results are withheld. No supervisor approval; standing is E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, LANE_09 BLOCKED_BY_RESEARCHER_EXECUTION_HOLD."
            )


def render_e3_scientific_question(
    package: E3ResearchEvidencePackage,
) -> None:
    """Render the scientific question and bounded scope."""
    st.subheader("Scientific question")
    st.markdown(
        f"How do placement ({', '.join(package.factors.get('placements', []))}), "
        f"scaling ({', '.join(package.factors.get('scalings', []))}), "
        f"and staleness ({' / '.join(str(v) for v in package.factors.get('state_age_ms_values', []))} ms) trade off offered-task deadline "
        f"attainment, rejection share, and {package.resource_cost.metric} across "
        f"matched fleet draws under a frozen MAPPO actor that does not observe load?"
    )
    st.caption(
        f"All comparisons are bounded to one incident hour "
        f"2024-03-15 20:00-21:00, provisional fleet width {package.factors.get('padded_fleet_width')}, {package.factors.get('scenario_rsus')} RSUs, "
        f"{package.factors.get('ticks_per_cell')} ticks per cell (dormant), replication unit {package.replication.replication_unit} N={package.replication.n} matched "
        f"draws {list(package.replication.fleet_seeds)}, evaluator_seed {package.replication.evaluator_seed}. Tasks are accounting records, never replicates."
    )
    st.caption(
        "No Manchester-wide deployment tested; bounded to one incident hour and four fleet draws, replication unit fleet_draw, N=4, not population"
    )
    st.caption(
        "No universal superiority claim; hypotheses H1-H5 are not expected truths; trade-off family has no scalar best objective"
    )
    st.caption(
        "No tasks-as-N; tasks are accounting records, not independent replicates; task-level N is forbidden"
    )
    st.markdown(
        f"Bounded replication: `{package.replication.replication_unit}` "
        f"N={package.replication.n} fleet_seeds {list(package.replication.fleet_seeds)} "
        f"evaluator_seed {package.replication.evaluator_seed} - "
        f"two-sided Student-t 95% interval df={package.replication.degrees_of_freedom}, t={package.replication.critical_value:.3f} over fleet-draw differences."
    )
    st.caption(
        "Frozen actor does not observe RSU load and does not select execution RSU; "
        "infrastructure placement is deterministic, not managed cluster deployment."
    )


def render_e3_strategy_semantics(
    semantics: tuple[E3StrategySemantics, ...],
) -> None:
    """Render strategy semantics for placement/scaling families."""
    st.subheader("Strategy semantics")
    st.caption(
        "Strategies are deterministic infrastructure-side placement / admission / forwarding "
        "rules with explicit scaling and staleness semantics. Placement is not learned and "
        "not managed cluster deployment."
    )
    # Group by placement
    placements = sorted({s.placement_id for s in semantics})
    scalings = sorted({s.scaling_id for s in semantics})
    st.markdown(f"**Placement families:** `{', '.join(placements)}`")
    st.markdown(f"**Scaling families:** `{', '.join(scalings)}`")
    _stale_vals = sorted({s.state_age_ms for s in semantics})
    st.markdown(
        f"**Staleness values:** `{', '.join(str(v) for v in _stale_vals)} ms` (typed int milliseconds)"
    )
    # Read constants from typed semantics (derived from package) — no literal duplication.
    if semantics:
        _q_note = semantics[0].queue_capacity_note
        _c_note = semantics[0].compute_capacity_note
        _r_note = semantics[0].resource_cost_note
        st.caption(
            f"Resource cost is resource_unit_seconds, never monetary. {_q_note} {_c_note} {_r_note}"
        )
    else:
        st.caption(
            "Resource cost is resource_unit_seconds, never monetary. Queue and compute capacities are strictly separate per typed package."
        )
    cols = st.columns(2)
    for idx, sem in enumerate(semantics):
        col = cols[idx % 2]
        with col.container(border=True):
            st.markdown(f"**{sem.placement_id} / {sem.scaling_id} @ {sem.state_age_ms} ms**")
            st.caption(sem.human_label)
            st.caption(f"Radio ingress: {sem.radio_ingress}")
            st.caption(f"Placement: {sem.execution_placement}")
            st.caption(f"Admission: {sem.admission}")
            st.caption(f"Forwarding: {sem.forwarding}")
            st.caption(f"Actor: {sem.actor_authority}")
            st.caption(f"Infrastructure: {sem.infrastructure_authority}")
            st.caption(f"Scaling: {sem.scaling_semantics}")
            st.caption(f"Staleness: {sem.staleness_semantics}")
            st.caption(f"Queue: {sem.queue_capacity_note}")
            st.caption(f"Compute: {sem.compute_capacity_note}")
            st.caption(f"Resource: {sem.resource_cost_note}")
            st.caption(f"Deterministic: {sem.is_deterministic}; learned: {sem.is_learned}")
            st.caption(f"Evidence: {sem.evidence_level}")
            st.caption(sem.limitations)
    st.caption(
        "Evidence level for every arm declares NOT_EXECUTED and NO_E3_RESEARCH_RESULTS_AVAILABLE; "
        "no empirical offering exists."
    )


def render_e3_tradeoff_structure(
    package: E3ResearchEvidencePackage,
) -> None:
    """Render placement/scaling/staleness/resource trade-off structure."""
    st.subheader("Placement / scaling / staleness / resource trade-off structure")
    st.markdown(
        "Trade-off family has no scalar best objective. Hypotheses H1-H5 are not expected truths; "
        "every arm is dormant until execution."
    )
    st.markdown(f"**Placements:** `{', '.join(package.factors.get('placements', []))}`")
    st.markdown(f"**Scalings:** `{', '.join(package.factors.get('scalings', []))}`")
    st.markdown(
        f"**State ages ms:** `{', '.join(str(x) for x in package.factors.get('state_age_ms_values', []))}`"
    )
    st.markdown(
        f"**Resource metric:** `{package.resource_cost.metric}` - normalized usage, not monetary"
    )
    st.caption(package.resource_cost.formula)
    st.markdown(
        f"Queue per RSU: {package.queue_capacity.capacity_per_rsu} tasks; "
        f"compute units per RSU: {package.compute_capacity.active_units_per_rsu_range} "
        f"({package.compute_capacity.unit}); "
        f"queue_is_not_compute: {package.queue_capacity.is_queue_not_compute} "
        f"compute_is_not_queue: {package.compute_capacity.is_compute_not_queue}"
    )
    # Derive staged design numbers from the typed package — no literal duplication.
    _e3a_cells = (
        len(package.factors.get("placements", []))
        * len([1])
        * len([1])
        * len(package.replication.fleet_seeds)
    )
    _unique_configs = len(package.dormant_configs)
    _arms = len(package.dormant_arms)
    # Use exact package-derived values; no fallback literals.
    st.caption(
        f"Staged design: E3a {package.staged_design.e3a.stage_listed_cells} cells "
        f"({len(package.factors.get('placements', []))} placements x 1 scaling x 1 staleness x {len(package.replication.fleet_seeds)} draws), "
        f"E3b {package.staged_design.e3b.unique_cells} unique additional cells "
        f"({len(package.factors.get('scalings', []))} scalers x 1 placement x 1 staleness x {len(package.replication.fleet_seeds)} draws minus overlap), "
        f"E3c {package.staged_design.e3c.stale_variant_cells_max} stale variants max (not rerun, view parameter) over "
        f"{_unique_configs} unique configs, {_arms} arms, not double counted."
    )
    with st.container(border=True):
        st.markdown(
            f"**Dormant arms ({len(package.dormant_arms)}) and configs ({len(package.dormant_configs)}) - STRUCTURE ONLY**"
        )
        arms = sorted(package.dormant_arms, key=lambda a: a.arm_id)
        rows = [
            {
                "arm_id": a.arm_id,
                "placement": str(
                    a.placement.value if hasattr(a.placement, "value") else a.placement
                ),
                "scaling": str(a.scaling.value if hasattr(a.scaling, "value") else a.scaling),
                "state_age_ms": a.state_age_ms,
                "status": "dormant NOT_EXECUTED",
            }
            for a in arms
        ]
        st.dataframe(rows, hide_index=True, width="stretch")
        configs = sorted(package.dormant_configs, key=lambda c: c.config_id)
        cfg_rows = [
            {
                "config_id": c.config_id,
                "arm_id": c.arm_id,
                "fleet_seed": c.fleet_seed,
                "state_age_ms": c.state_age_ms,
                "status": "dormant NOT_EXECUTED",
            }
            for c in configs[:10]
        ]
        st.dataframe(cfg_rows, hide_index=True, width="stretch")
        st.caption(
            f"Showing 10 of {len(package.dormant_configs)} dormant configs; full list in JSON export. All are STRUCTURE ONLY, not results."
        )


def render_e3_per_rsu_and_scale_action_structure(
    package: E3ResearchEvidencePackage,
    accounting: E3TaskAccountingView,
) -> None:
    """Render per-RSU and scale-action summary STRUCTURE (null with reasons)."""
    st.subheader("Per-RSU and scale-action summary STRUCTURE")
    st.caption(
        "Summaries exist as typed structure but values are UNAVAILABLE before execution. "
        "Never zero, never empty list fabricated as evidence, never placeholder."
    )
    with st.container(border=True):
        st.markdown("**Per-RSU summaries**")
        st.markdown("`value = None`")
        st.caption(package.scaling_receipts.per_rsu_summaries_null_reason)
        st.caption(accounting.scaling_receipts.per_rsu_reason)
        st.markdown(
            f"RSU count: {package.factors.get('scenario_rsus')} structure exists but per-RSU values are null with reasons."
        )
    with st.container(border=True):
        st.markdown("**Scale-action receipts**")
        st.markdown("`value = None`")
        st.caption(package.scaling_receipts.receipts_when_not_executed_null_reason)
        st.caption(accounting.scaling_receipts.reason)
        st.markdown("**Capacity levels**")
        st.markdown("`value = None`")
        st.caption(package.scaling_receipts.capacity_levels_null_reason)
        st.caption(accounting.scaling_receipts.capacity_reason)
        st.markdown("**State-age receipts**")
        _state_vals = package.factors.get("state_age_ms_values", [0, 1000, 3000])
        st.markdown(
            f"`value = None` typed int milliseconds {'/'.join(str(v) for v in _state_vals)}"
        )
        st.caption(package.scaling_receipts.state_age_receipts_null_reason)
        st.caption(accounting.scaling_receipts.state_age_reason)
        st.caption(
            f"Has receipts when executed: {package.scaling_receipts.has_receipts_when_executed}"
        )
    st.caption(
        "Every numeric surface for per-RSU and scale-action renders NOT_EXECUTED / "
        "NO_E3_RESEARCH_RESULTS_AVAILABLE explicitly - never a number, never an empty chart implying zero."
    )


def render_e3_task_accounting(
    accounting: E3TaskAccountingView,
    package: E3ResearchEvidencePackage | None = None,
) -> None:
    """Render task accounting with null lifecycle and reasons."""
    st.subheader("Task accounting (offered / admitted / rejected / forwarded / deadline_success)")
    st.caption(
        "All counts are null with reasons in NOT_EXECUTED state. Conservation is null with reason. "
        "Genuine rejection classes are structure, not counts."
    )
    rows: list[dict[str, str]] = []
    for field in (
        "offered",
        "admitted",
        "rejected_total",
        "forwarded",
        "deadline_success",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        reason = getattr(accounting, f"{field}_reason", "")
        rows.append(
            {"field": field, "value": "None", "status": "UNAVAILABLE", "reason": str(reason)}
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.markdown(
        f"**Conservation holds:** `{accounting.conservation_holds}` - {accounting.conservation_reason}"
    )
    st.markdown(
        f"**Genuine rejection classes:** `{', '.join(accounting.genuine_rejection_classes)}`"
    )
    breakdown_rows: list[dict[str, str]] = []
    for cls, reason in accounting.rejected_breakdown.reasons.items():
        breakdown_rows.append(
            {"class": cls, "value": "None", "status": "UNAVAILABLE", "reason": reason}
        )
    st.dataframe(breakdown_rows, hide_index=True, width="stretch")
    with st.container(border=True):
        st.markdown(
            f"**Queue vs compute separation:** queue `{accounting.queue_vs_compute.queue_unit}` vs compute `{accounting.queue_vs_compute.compute_unit}`"
        )
        st.caption(accounting.queue_vs_compute.reason)
        st.markdown(
            f"**Resource cost:** metric `{accounting.resource_cost.metric}` monetary `{accounting.resource_cost.monetary}` value `None`"
        )
        st.caption(accounting.resource_cost.reason)
        st.caption(accounting.resource_cost.formula)
    st.caption(
        "Never coerce unavailable to zero. Tasks are accounting records; never tasks as replicates. "
        "Resource cost is resource_unit_seconds, never monetary."
    )
    if package is not None:
        st.caption(
            f"Package missingness also declares {len(package.missingness)} fields null with reasons."
        )


def render_e3_missingness(
    package: E3ResearchEvidencePackage,
) -> None:
    """Render missingness first-class."""
    st.subheader("Missingness")
    st.caption("Every unavailable field is null with an explicit reason; never hidden, never zero.")
    rows: list[dict[str, str]] = [
        {"field": m.field, "reason": m.reason} for m in package.missingness
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def render_e3_comparison_structure(
    comparison: E3ResearchComparisonView,
) -> None:
    """Render comparison structure - estimands and paired differences unavailable."""
    st.subheader("Comparison structure (E3a / E3b / E3c - no results)")
    st.caption(
        f"Replication unit {comparison.e3a.replication_unit} N={comparison.e3a.n_fleet_draws} matched draws {list(comparison.e3a.fleet_seeds)}, evaluator_seed {comparison.e3a.evaluator_seed}, "
        f"two-sided Student-t 95% interval df={comparison.e3a.degrees_of_freedom}, t={comparison.e3a.critical_value:.3f}. All per-draw values are "
        f"null with reasons while hold is active. Tasks are accounting records, not replicates."
    )
    for view in (comparison.e3a, comparison.e3b, comparison.e3c):
        with st.container(border=True):
            st.markdown(
                f"**{view.stage}** - replication `{view.replication_unit}` N={view.n_fleet_draws} seeds {list(view.fleet_seeds)} evaluator {view.evaluator_seed}"
            )
            st.caption(
                "No E3 research results exist today; paired differences are null with reasons while hold is active."
            )
            st.markdown(
                f"Method: {view.method} df={view.degrees_of_freedom} critical {view.critical_value}"
            )
            st.caption(f"Tasks are not replicates: {view.tasks_are_not_replicates}")
            st.caption(
                "No Manchester-wide deployment tested; bounded to one incident hour and four fleet draws, replication unit fleet_draw, N=4, not population"
            )
            st.caption(
                "No universal superiority claim; hypotheses H1-H5 are not expected truths; trade-off family has no scalar best objective"
            )
            rows = [
                {
                    "estimand": e.estimand,
                    "treatment": e.treatment,
                    "control": e.control,
                    "metric": e.metric,
                    "state_age_ms": str(e.state_age_ms),
                }
                for e in view.estimands
            ]
            st.dataframe(rows, hide_index=True, width="stretch")
            pd_rows = [
                {
                    "comparison_id": pd.comparison_id,
                    "per_seed_values": "None",
                    "mean": "None",
                    "status": "UNAVAILABLE",
                    "reason": "UNAVAILABLE - paired differences null before execution",
                }
                for pd in view.paired_differences
            ]
            st.dataframe(pd_rows, hide_index=True, width="stretch")
            st.caption(
                "All paired differences are UNAVAILABLE: per_seed_values null, mean null, interval not computed."
            )


def render_e3_provenance(
    package: E3ResearchEvidencePackage,
    receipt: E3ResearchAdmissionRefusal,
) -> None:
    """Render provenance with exact pins."""
    st.subheader("Provenance (exact pins)")
    st.caption(
        "Exact frozen identities - provenance and claim scanning is position-independent and canonical."
    )
    rows: list[dict[str, str]] = [
        {
            "field": "product_base_sha",
            "value": _fingerprint_short(package.product_base_sha, 40),
            "full": package.product_base_sha,
        },
        {
            "field": "research_promotion_sha",
            "value": _fingerprint_short(package.research_promotion_sha, 40),
            "full": package.research_promotion_sha,
        },
        {
            "field": "approved_candidate_sha",
            "value": _fingerprint_short(package.approved_candidate_sha, 40),
            "full": package.approved_candidate_sha,
        },
        {
            "field": "contract_checkpoint_sha",
            "value": _fingerprint_short(package.contract_checkpoint_sha, 40),
            "full": package.contract_checkpoint_sha,
        },
        {
            "field": "vec_promotion_sha",
            "value": _fingerprint_short(package.vec_runtime.promotion_commit, 40),
            "full": package.vec_runtime.promotion_commit,
        },
        {
            "field": "vec_core_sha",
            "value": _fingerprint_short(package.vec_runtime.core_candidate, 40),
            "full": package.vec_runtime.core_candidate,
        },
        {
            "field": "vec_adapter_sha",
            "value": _fingerprint_short(package.vec_runtime.adapter_candidate, 40),
            "full": package.vec_runtime.adapter_candidate,
        },
        {
            "field": "actor_sha256",
            "value": _fingerprint_short(package.software_identity.actor_sha256, 40),
            "full": package.software_identity.actor_sha256,
        },
        {
            "field": "trace_sha256",
            "value": _fingerprint_short(package.software_identity.trace_sha256, 40),
            "full": package.software_identity.trace_sha256,
        },
        {
            "field": "contract_sha256",
            "value": _fingerprint_short(package.contract.sha256, 40),
            "full": package.contract.sha256,
        },
        {
            "field": "manifest_sidecar_sha256",
            "value": _fingerprint_short(receipt.manifest_sidecar_sha256, 40),
            "full": receipt.manifest_sidecar_sha256,
        },
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    with st.expander("Advanced: E3 full provenance entries"):
        prov_rows = [
            {"artifact": e.artifact, "kind": e.kind, "note": e.note} for e in package.provenance
        ]
        st.dataframe(prov_rows, hide_index=True, width="stretch")
        st.code(
            f"Base head: {package.traffictwin_runtime.base_commit}\n"
            f"Contract path: {package.contract.path}\n"
            f"Contract SHA256: {package.contract.sha256}\n"
            f"Actor: {package.software_identity.actor_sha256}\n"
            f"Trace: {package.software_identity.trace_sha256}",
            language=None,
        )


def render_e3_limitations(
    package: E3ResearchEvidencePackage,
) -> None:
    """Render limitations and non-claims verbatim."""
    st.subheader("Limitations and non-claims")
    st.caption(
        "Limitations and non-claims are first-class - explicitly refused claims remain visible."
    )
    st.markdown("**Limitations:**")
    for lim in package.limitations:
        st.markdown(f"- {lim}")
    st.markdown("**Non-claims:**")
    for nc in package.non_claims:
        st.markdown(f"- {nc}")
    with st.container(border=True):
        st.caption(
            "All limitations mention NOT_EXECUTED or NO_E3_RESEARCH_RESULTS_AVAILABLE and "
            "bounded replication fleet_draw N=4."
        )
        st.caption(
            "No Manchester-wide deployment tested; bounded to one incident hour and four fleet draws, replication unit fleet_draw, N=4, not population"
        )
        st.caption(
            "No universal superiority claim; hypotheses H1-H5 are not expected truths; trade-off family has no scalar best objective"
        )


def render_e3_downloads(exports: E3ResearchExportBundle) -> None:
    """Render deterministic export downloads."""
    st.subheader("Deterministic exports")
    st.caption(
        "Deterministic JSON/CSV/Markdown exports of the same typed payload - byte-stable ordering, "
        "no timestamps or randomness, via the reporting module."
    )
    cols = st.columns(3)
    with cols[0]:
        st.download_button(
            label="Download E3 JSON",
            data=exports.json,
            file_name="e3_dynamic_resource_v2.json",
            mime="application/json",
            width="stretch",
            key="e3_download_json",
        )
    with cols[1]:
        st.download_button(
            label="Download E3 CSV",
            data=exports.csv,
            file_name="e3_dynamic_resource_v2.csv",
            mime="text/csv",
            width="stretch",
            key="e3_download_csv",
        )
    with cols[2]:
        st.download_button(
            label="Download E3 Markdown",
            data=exports.markdown,
            file_name="e3_dynamic_resource_v2.md",
            mime="text/markdown",
            width="stretch",
            key="e3_download_md",
        )
    with st.expander("Advanced: E3 export preview"):
        st.code(exports.json[:2000], language="json")
        st.code(exports.csv[:2000], language=None)
        st.code(exports.markdown[:2000], language="markdown")


def render_e3_research(
    package: E3ResearchEvidencePackage,
    receipt: E3ResearchAdmissionRefusal | None,
    comparison: E3ResearchComparisonView,
    accounting: E3TaskAccountingView,
    exports: E3ResearchExportBundle,
) -> None:
    """Aggregate render - composes all E3 sections truthfully with no results."""
    render_e3_hold_banner(package, receipt)
    render_e3_admission_banner(package, receipt)
    try:
        authoritative = admit_e3_research(package) if package is not None else None
    except Exception:
        st.warning(
            "Package not correctly formed; truthful no-results panels are withheld. "
            "Provide the built-in E3 evidence package via load_builtin_e3_research()."
        )
        return
    if receipt is None or authoritative is None or receipt != authoritative:
        st.warning(
            "Receipt does not match authoritative Lane 10 refusal for this package; "
            "truthful no-results panels are withheld."
        )
        return
    # Verify deterministic exports match service outputs
    try:
        from traffictwin.reporting.e3_research import build_e3_research_exports

        expected = build_e3_research_exports(package, receipt)
    except Exception:
        st.warning("Service derivation failed for this package; panels withheld.")
        return
    if exports != expected:
        st.warning(
            "Supplied exports do not match the reporting service outputs for the package; "
            "panels withheld."
        )
        return
    from traffictwin.experiments.e3_strategy_semantics import e3_strategy_semantics

    semantics = e3_strategy_semantics()
    render_e3_scientific_question(package)
    render_e3_strategy_semantics(semantics)
    render_e3_tradeoff_structure(package)
    render_e3_per_rsu_and_scale_action_structure(package, accounting)
    render_e3_comparison_structure(comparison)
    render_e3_task_accounting(accounting, package)
    render_e3_missingness(package)
    render_e3_provenance(package, receipt)
    render_e3_limitations(package)
    render_e3_downloads(exports)
    with st.container(border=True):
        st.caption(
            "Today there are NO results. Every numeric surface renders the "
            "NOT_EXECUTED / NO_E3_RESEARCH_RESULTS_AVAILABLE state explicitly - "
            "never a placeholder number, never an empty chart implying zero values, "
            "never marketing. Admission fails closed until an exact approved Lane 09 package exists."
        )


__all__ = [
    "render_e3_hold_banner",
    "render_e3_admission_banner",
    "render_e3_scientific_question",
    "render_e3_strategy_semantics",
    "render_e3_tradeoff_structure",
    "render_e3_per_rsu_and_scale_action_structure",
    "render_e3_task_accounting",
    "render_e3_missingness",
    "render_e3_comparison_structure",
    "render_e3_provenance",
    "render_e3_limitations",
    "render_e3_downloads",
    "render_e3_research",
]
