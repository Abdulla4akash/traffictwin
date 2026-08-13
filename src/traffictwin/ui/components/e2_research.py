"""Reusable native Streamlit components for E2 research evidence.

Consumes exact typed service/view output and performs formatting only.
No hard-coded scientific values, no fallback constants, no recomputation.
Admission fails closed via Lane 04 authority: no result panels without
exact owner-authorized admitted receipt bound to the supplied package.
UNAVAILABLE reasons are rendered verbatim from the validated typed objects.
"""

from __future__ import annotations

import streamlit as st

from traffictwin.evidence_admission.e2_research import (
    E2ResearchAdmissionReceipt,
    admit_e2_research,
)
from traffictwin.experiments.e2_comparison import E2ResearchComparisonView
from traffictwin.experiments.e2_research_evidence import E2ResearchEvidencePackage
from traffictwin.experiments.e2_strategy_semantics import E2StrategySemantics
from traffictwin.experiments.e2_task_accounting import E2TaskAccountingView
from traffictwin.reporting.e2_research import E2ResearchExportBundle


def _is_owner_authorized_admitted(
    receipt: E2ResearchAdmissionReceipt | None,
) -> bool:
    if receipt is None:
        return False
    if not isinstance(receipt, E2ResearchAdmissionReceipt):
        return False
    try:
        receipt.verify()
    except Exception:
        return False
    return (
        receipt.standing == "OWNER-AUTHORIZED PRODUCT ADMISSION"
        and receipt.admission_mode == "ADMITTED_RESEARCH"
    )


def _is_admitted_for_package(
    package: E2ResearchEvidencePackage | None,
    receipt: E2ResearchAdmissionReceipt | None,
) -> bool:
    if package is None or receipt is None:
        return False
    if not isinstance(receipt, E2ResearchAdmissionReceipt):
        return False
    if not isinstance(package, E2ResearchEvidencePackage):
        return False
    try:
        authoritative = admit_e2_research(package)
    except Exception:
        return False
    if receipt != authoritative:
        return False
    return _is_owner_authorized_admitted(receipt)


def _fingerprint_short(value: str | None, length: int = 12) -> str:
    if value is None or not str(value).strip():
        return "Unavailable"
    s = str(value).strip()
    if len(s) <= length:
        return s
    return f"{s[:length]}…"


def render_e2_admission_banner(
    package: E2ResearchEvidencePackage | None,
    receipt: E2ResearchAdmissionReceipt | None,
) -> None:
    """Render the admission banner.

    Shows ADMITTED only after `admit_e2_research(package)` succeeds and
    receipt equals the authoritative receipt. Otherwise shows UNADMITTED.
    A forged self-consistent receipt will not receive a green banner.
    """
    admitted = _is_admitted_for_package(package, receipt)
    with st.container(border=True):
        if admitted:
            st.markdown(
                ":green-badge[ADMITTED RESEARCH] :green-badge[OWNER-AUTHORIZED PRODUCT ADMISSION]"
            )
            st.markdown("**Standing:** ADMITTED RESEARCH — OWNER-AUTHORIZED PRODUCT ADMISSION")
            st.caption("This is not supervisor approval and not Randy confirmation.")
        else:
            st.markdown(":red-badge[UNADMITTED RESEARCH]")
            st.markdown("**Standing:** UNADMITTED RESEARCH")
            st.caption(
                "Results are withheld; an unadmitted study must not be "
                "treated as admitted. This is not supervisor approval and "
                "not Randy confirmation."
            )


def render_e2_question_motivation(
    package: E2ResearchEvidencePackage,
) -> None:
    """Render the research question and bounded motivation.

    Static wording describes the bounded question; any configuration that
    can drift is taken from the typed package.
    """
    st.subheader("Research question")
    st.markdown(
        "Does the choice of RSU placement target (strongest-link ingress vs "
        "least-busy) and granularity (one common-target per substep vs "
        "sequential per-task least-busy feasible placement) change "
        "offered-task deadline attainment under the same deadline-aware "
        "admission gate and over matched fleet draws?"
    )
    st.caption(
        "Motivation: The frozen MAPPO actor does not observe current RSU "
        "load and does not select an execution RSU; infrastructure load "
        "management is supervisor-identified (S-035) and implemented as "
        "deterministic infrastructure-side RSU selection."
    )
    st.markdown(
        f"All comparisons are bounded to the matched incident-hour fleet draws "
        f"declared in the evidence package (replication unit "
        f"{package.replication_unit}, evaluator seed "
        f"{package.evaluator_seed})."
    )
    st.caption(
        "One Manchester incident hour, provisional fleet, and the waiting-room "
        "and service configuration are as declared in the provenance and "
        "accounting views."
    )


def render_e2_strategy_cards(
    semantics: tuple[E2StrategySemantics, ...],
) -> None:
    """Render strategy cards from typed semantics."""
    st.subheader("Strategy cards")
    st.caption(
        "Strategies are deterministic infrastructure-side placement/admission "
        "rules; placement is not learned and not Kubernetes deployment."
    )
    cols = st.columns(2)
    for idx, sem in enumerate(semantics):
        col = cols[idx % 2]
        with col.container(border=True):
            st.markdown(f"**{sem.strategy_id}**")
            st.caption(sem.human_label)
            st.caption(f"Radio ingress: {sem.radio_ingress}")
            st.caption(f"Execution placement: {sem.execution_placement}")
            st.caption(f"Admission: {sem.admission}")
            st.caption(f"Forwarding: {sem.forwarding}")
            st.caption(f"Actor authority: {sem.actor_authority}")
            st.caption(f"Infrastructure authority: {sem.infrastructure_authority}")
            st.caption(f"Deterministic: {sem.is_deterministic}; learned: {sem.is_learned}")
            st.caption(f"Evidence: {sem.evidence_level}")
            st.caption(f"Limitations: {sem.limitations}")
    st.caption(
        "Placement is deterministic infrastructure-side RSU load management, "
        "optionally termed Kubernetes-inspired deterministic scheduling; it "
        "is not learned and not Kubernetes deployment. MAPPO is frozen and "
        "does not observe RSU load or choose execution RSU."
    )


def render_e2b_table(comparison: E2ResearchComparisonView) -> None:
    """Render exact E2b offered-task deadline attainment table."""
    st.subheader("E2b — offered-task deadline attainment (one draw descriptive)")
    e2b = comparison.e2b
    st.caption(
        f"Metric: {e2b.metric}; "
        f"replication_unit: {e2b.replication_unit}; "
        f"evaluator_seed: {e2b.evaluator_seed}; "
        f"no population inference; one Manchester incident hour."
    )
    rows: list[dict[str, str]] = [
        {
            "arm": "off",
            "offered_task_deadline_attainment": str(e2b.off),
            "fleet_seed": str(e2b.fleet_seed),
            "standing": e2b.standing,
        },
        {
            "arm": "jsq",
            "offered_task_deadline_attainment": str(e2b.jsq),
            "fleet_seed": str(e2b.fleet_seed),
            "standing": e2b.standing,
        },
        {
            "arm": "ingress_dla",
            "offered_task_deadline_attainment": str(e2b.ingress_dla),
            "fleet_seed": str(e2b.fleet_seed),
            "standing": e2b.standing,
        },
        {
            "arm": "dla",
            "offered_task_deadline_attainment": str(e2b.dla),
            "fleet_seed": str(e2b.fleet_seed),
            "standing": e2b.standing,
        },
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        f"E2b attribution: offered-task deadline attainment, one draw "
        f"descriptive: off {e2b.off}, jsq {e2b.jsq}, "
        f"ingress_dla {e2b.ingress_dla}, common-target dla {e2b.dla}. "
        f"No population inference."
    )
    with st.expander("Evidence / Advanced — E2b identities"):
        st.code(
            f"E2b head: {e2b.code_commit}\n"
            f"E2b manifest: {e2b.manifest_sha256}\n"
            f"Actor SHA-256: {e2b.actor_sha256}\n"
            f"Trace SHA-256: {e2b.trace_sha256}\n"
            f"Replication unit: {e2b.replication_unit}; "
            f"evaluator seed: {e2b.evaluator_seed}",
            language=None,
        )


def render_e2c_table(comparison: E2ResearchComparisonView) -> None:
    """Render exact E2c common-target dla minus ingress_dla table."""
    st.subheader("E2c — common-target dla minus ingress_dla (matched fleet draws)")
    e2c = comparison.e2c
    st.caption(
        f"Paired fleet-draw differences; tasks are accounting records, not "
        f"statistical replications. Replication unit: {e2c.replication_unit}; "
        f"evaluator seed: {e2c.evaluator_seed}; n={e2c.n_fleet_draws}."
    )
    rows: list[dict[str, str]] = []
    for seed, val in zip(e2c.fleet_seeds, e2c.per_seed_values, strict=True):
        rows.append(
            {
                "fleet_seed": str(seed),
                "dla_minus_ingress_dla": str(val),
            }
        )
    rows.append({"fleet_seed": "mean", "dla_minus_ingress_dla": str(e2c.mean)})
    st.dataframe(rows, hide_index=True, width="stretch")
    st.markdown(
        f"Declared mean: {e2c.mean} ; 95% CI [{e2c.lower}, {e2c.upper}] ; "
        f"sign: {'negative' if e2c.all_negative else 'not all negative'}; "
        f"includes_zero={e2c.includes_zero}."
    )
    st.caption(
        f"E2c declared mean {e2c.mean}; declared 95% CI "
        f"[{e2c.lower}, {e2c.upper}]; sign: "
        f"{'all negative' if e2c.all_negative else 'mixed'}."
    )
    per_seed_c = ", ".join(
        f"{seed} {val}" for seed, val in zip(e2c.fleet_seeds, e2c.per_seed_values, strict=True)
    )
    st.caption(f"Per-seed dla_minus_ingress_dla: {per_seed_c}")
    st.caption(
        f"Method: {e2c.method}; df={e2c.degrees_of_freedom}; "
        f"includes_zero={e2c.includes_zero}; decision={e2c.decision}; "
        f"standing: {e2c.standing}"
    )
    with st.expander("Evidence / Advanced — E2c identities"):
        st.code(
            f"E2c head: {e2c.code_commit}\n"
            f"E2c manifest: {e2c.manifest_sha256}\n"
            f"Actor SHA-256: {e2c.actor_sha256}\n"
            f"Trace SHA-256: {e2c.trace_sha256}\n"
            f"Replication unit: {e2c.replication_unit}; "
            f"evaluator seed: {e2c.evaluator_seed}",
            language=None,
        )


def render_e2d_table(comparison: E2ResearchComparisonView) -> None:
    """Render exact E2d per_task_dla minus ingress_dla table."""
    st.subheader("E2d — per_task_dla minus ingress_dla (matched fleet draws)")
    e2d = comparison.e2d
    st.caption(
        f"Paired fleet-draw differences; bounded to matched incident-hour "
        f"fleet draws. Replication unit: {e2d.replication_unit}; "
        f"evaluator seed: {e2d.evaluator_seed}; n={e2d.n_fleet_draws}."
    )
    rows: list[dict[str, str]] = []
    for seed, val in zip(e2d.fleet_seeds, e2d.per_seed_values, strict=True):
        rows.append(
            {
                "fleet_seed": str(seed),
                "per_task_dla_minus_ingress_dla": str(val),
            }
        )
    rows.append(
        {
            "fleet_seed": "mean",
            "per_task_dla_minus_ingress_dla": str(e2d.mean),
        }
    )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.markdown(
        f"Declared mean: {e2d.mean} ; 95% CI [{e2d.lower}, {e2d.upper}] ; "
        f"sign: {'positive' if e2d.all_positive else 'not all positive'}; "
        f"includes_zero={e2d.includes_zero}."
    )
    st.caption(
        f"E2d declared mean {e2d.mean}; declared 95% CI "
        f"[{e2d.lower}, {e2d.upper}]; sign: "
        f"{'all positive' if e2d.all_positive else 'mixed'}."
    )
    per_seed_d = ", ".join(
        f"{seed} {val}" for seed, val in zip(e2d.fleet_seeds, e2d.per_seed_values, strict=True)
    )
    st.caption(f"Per-seed per_task_minus_ingress: {per_seed_d}")
    vs = comparison.e2d_vs_common_target
    st.markdown(
        f"Per_task_dla minus inherited common-target DLA: declared mean "
        f"{vs.mean}; declared 95% CI [{vs.lower}, {vs.upper}]; "
        f"standing: {vs.standing}."
    )
    with st.expander("Evidence / Advanced — E2d identities"):
        st.code(
            f"E2d head: {e2d.code_commit}\n"
            f"E2d manifest: {e2d.manifest_sha256}\n"
            f"Actor SHA-256: {e2d.actor_sha256}\n"
            f"Trace SHA-256: {e2d.trace_sha256}\n"
            f"Replication unit: {e2d.replication_unit}; "
            f"evaluator seed: {e2d.evaluator_seed}",
            language=None,
        )


def render_e2_direction_reversal_summary(
    comparison: E2ResearchComparisonView,
) -> None:
    """Render bounded direction-reversal summary."""
    st.subheader("Direction-reversal summary")
    st.markdown(comparison.direction_reversal.statement)
    st.caption(
        f"Replication unit: {comparison.direction_reversal.replication_unit}; "
        f"reversed: {comparison.direction_reversal.reversed}."
    )
    e2c = comparison.e2c
    e2d = comparison.e2d
    st.markdown(
        f"E2c (common-target vs ingress): {e2c.n_fleet_draws} paired "
        f"differences {'all negative' if e2c.all_negative else 'mixed'}; "
        f"E2d (per-task vs ingress): {e2d.n_fleet_draws} paired differences "
        f"{'all positive' if e2d.all_positive else 'mixed'}."
    )
    st.caption(
        f"E2c mean {e2c.mean} includes_zero={e2c.includes_zero}; "
        f"E2d mean {e2d.mean} includes_zero={e2d.includes_zero}; tasks are "
        f"accounting records, not statistical replications."
    )
    st.caption(f"Bounded to: {comparison.direction_reversal.bounded_to}")
    st.caption(
        f"E2c decision: {e2c.decision}; E2d decision: {e2d.decision}; standing: {e2c.standing}"
    )


def render_e2_task_accounting(
    accounting: E2TaskAccountingView,
) -> None:
    """Render E2d seed-1 accounting and missingness.

    Exact UNAVAILABLE reasons are rendered verbatim from the typed view;
    never synthesized or implied as zero. Explicit typed field access, no
    dynamic getattr.
    """
    st.subheader("Accounting (E2d seed 1) and missingness")
    st.caption("Conservation check and unavailable instrumentation.")
    st.caption(
        "Single matched fleet-draw (seed 1) accounting record; not a "
        "replication summary and not a basis for population inference."
    )
    rows: list[dict[str, str]] = [
        {"field": "offered", "value": str(accounting.offered)},
        {"field": "admitted", "value": str(accounting.admitted)},
        {
            "field": "rejected_total",
            "value": str(accounting.rejected_total),
        },
        {"field": "forwarded", "value": str(accounting.forwarded)},
        {
            "field": "deadline_success",
            "value": str(accounting.deadline_success),
        },
        {
            "field": "offered deadline attainment",
            "value": str(accounting.offered_deadline_attainment),
        },
        {
            "field": "admitted conditional diagnostic",
            "value": str(accounting.admitted_deadline_attainment),
        },
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        f"rejected_total = offered - admitted is "
        f"{accounting.rejected_total_status} where the source says so, "
        f"not directly observed. Derivation: "
        f"{accounting.rejected_total_derivation}"
    )
    st.caption(
        f"Conservation: {accounting.conservation_formula} holds={accounting.conservation_holds}"
    )
    st.caption(f"Headline rule: {accounting.headline_rule}")
    st.markdown("**Missingness / unavailable instrumentation**")
    gate_entry = accounting.unavailable["gate_rejected"]
    capacity_entry = accounting.unavailable["capacity_rejected"]
    started_entry = accounting.unavailable["started"]
    compute_entry = accounting.unavailable["compute_completed"]
    returned_entry = accounting.unavailable["returned"]
    dropped_entry = accounting.unavailable["dropped"]
    missing_rows: list[dict[str, str]] = [
        {
            "field": "gate_rejected",
            "value": str(gate_entry.value),
            "status": gate_entry.status,
            "reason": accounting.gate_rejected_reason,
        },
        {
            "field": "capacity_rejected",
            "value": str(capacity_entry.value),
            "status": capacity_entry.status,
            "reason": accounting.capacity_rejected_reason,
        },
        {
            "field": "started",
            "value": str(started_entry.value),
            "status": started_entry.status,
            "reason": accounting.started_reason,
        },
        {
            "field": "compute_completed",
            "value": str(compute_entry.value),
            "status": compute_entry.status,
            "reason": accounting.compute_completed_reason,
        },
        {
            "field": "returned",
            "value": str(returned_entry.value),
            "status": returned_entry.status,
            "reason": accounting.returned_reason,
        },
        {
            "field": "dropped",
            "value": str(dropped_entry.value),
            "status": dropped_entry.status,
            "reason": accounting.dropped_reason,
        },
    ]
    if accounting.gate_rejected_reason != gate_entry.reason:
        st.warning("Reason mismatch for gate_rejected: direct vs dict")
    if accounting.capacity_rejected_reason != capacity_entry.reason:
        st.warning("Reason mismatch for capacity_rejected: direct vs dict")
    if accounting.started_reason != started_entry.reason:
        st.warning("Reason mismatch for started: direct vs dict")
    if accounting.compute_completed_reason != compute_entry.reason:
        st.warning("Reason mismatch for compute_completed: direct vs dict")
    if accounting.returned_reason != returned_entry.reason:
        st.warning("Reason mismatch for returned: direct vs dict")
    if accounting.dropped_reason != dropped_entry.reason:
        st.warning("Reason mismatch for dropped: direct vs dict")
    st.dataframe(missing_rows, hide_index=True, width="stretch")
    st.caption(
        "Do not turn unavailable into zero, claim started==admitted "
        "measured, or treat deadline success as physical return proof."
    )
    st.markdown(
        f"Conservation: {accounting.conservation.formula} holds="
        f"{accounting.conservation.holds}; {accounting.conservation.derivation}"
    )
    st.caption(accounting.rejected_latency_note)
    st.caption(accounting.physical_return_note)
    st.caption(accounting.waiting_room_note)
    with st.expander("Evidence / Advanced — accounting provenance"):
        st.code(
            f"offered {accounting.offered}; admitted {accounting.admitted}; "
            f"rejected_total {accounting.rejected_total} "
            f"(= offered - admitted DERIVED)\n"
            f"forwarded {accounting.forwarded}; "
            f"deadline_success {accounting.deadline_success}\n"
            f"offered attainment {accounting.offered_deadline_attainment}; "
            f"admitted conditional {accounting.admitted_deadline_attainment}\n"
            f"source head {accounting.source_head}; "
            f"manifest {accounting.manifest_sha}",
            language=None,
        )


def render_e2_provenance(
    package: E2ResearchEvidencePackage,
    receipt: E2ResearchAdmissionReceipt,
) -> None:
    """Render provenance details from typed package and receipt."""
    st.subheader("Provenance")
    st.caption("Traceability: code commit, manifest, actor, trace, seeds, and replication unit.")
    si = package.source_identities
    rows: list[dict[str, str]] = [
        {
            "field": "actor SHA-256",
            "value": _fingerprint_short(si.actor.sha256),
        },
        {
            "field": "trace SHA-256",
            "value": _fingerprint_short(si.trace.sha256),
        },
        {"field": "base SHA", "value": _fingerprint_short(si.base_sha)},
        {"field": "replication unit", "value": package.replication_unit},
        {"field": "evaluator seed", "value": str(package.evaluator_seed)},
        {
            "field": "E2b head",
            "value": _fingerprint_short(si.research_heads.e2b),
        },
        {
            "field": "E2c head",
            "value": _fingerprint_short(si.research_heads.e2c),
        },
        {
            "field": "E2d head",
            "value": _fingerprint_short(si.research_heads.e2d),
        },
        {
            "field": "E2b manifest",
            "value": _fingerprint_short(si.manifest_sha256_by_study["e2b"]),
        },
        {
            "field": "E2c manifest",
            "value": _fingerprint_short(si.manifest_sha256_by_study["e2c"]),
        },
        {
            "field": "E2d manifest",
            "value": _fingerprint_short(si.manifest_sha256_by_study["e2d"]),
        },
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        f"Replication unit: {package.replication_unit}; "
        f"evaluator seed: {package.evaluator_seed}; "
        f"individual tasks are never statistical replications."
    )
    with st.expander("Evidence / Advanced — full identities"):
        st.code(
            f"Actor SHA-256: {si.actor.sha256}\n"
            f"Trace SHA-256: {si.trace.sha256}\n"
            f"Base SHA: {si.base_sha}\n"
            f"E2b head: {si.research_heads.e2b}\n"
            f"E2b manifest: {si.manifest_sha256_by_study['e2b']}\n"
            f"E2c head: {si.research_heads.e2c}\n"
            f"E2c manifest: {si.manifest_sha256_by_study['e2c']}\n"
            f"E2d head: {si.research_heads.e2d}\n"
            f"E2d manifest: {si.manifest_sha256_by_study['e2d']}\n"
            f"Replication unit: {package.replication_unit}; "
            f"evaluator seed: {package.evaluator_seed}\n"
            f"Receipt fingerprint: {receipt.receipt_fingerprint}\n"
            f"Package fingerprint: {receipt.package_fingerprint}",
            language=None,
        )


def render_e2_limitations(
    package: E2ResearchEvidencePackage,
) -> None:
    """Render limitations and explicit non-claims from typed package.

    Verbatim from package.limitations / package.non_claims with neutral
    headings only; no duplicated authoritative list.
    """
    st.subheader("Limitations and non-claims")
    st.caption("Explicitly refused claims — must remain visible.")
    st.markdown("**Limitations:**")
    for lim in package.limitations:
        st.markdown(f"- {lim}")
    st.markdown("**Non-claims:**")
    for nc in package.non_claims:
        st.markdown(f"- {nc}")


def render_e2_downloads(exports: E2ResearchExportBundle) -> None:
    """Render JSON/CSV/Markdown download controls from typed bundle."""
    st.subheader("Downloads")
    st.caption("Deterministic exports for reproducibility.")
    cols = st.columns(3)
    with cols[0]:
        st.download_button(
            label="Download JSON",
            data=exports.json,
            file_name="e2_research.json",
            mime="application/json",
            width="stretch",
        )
    with cols[1]:
        st.download_button(
            label="Download CSV",
            data=exports.csv,
            file_name="e2_research.csv",
            mime="text/csv",
            width="stretch",
        )
    with cols[2]:
        st.download_button(
            label="Download Markdown",
            data=exports.markdown,
            file_name="e2_research.md",
            mime="text/markdown",
            width="stretch",
        )
    with st.expander("Evidence / Advanced — export preview"):
        st.code(exports.json[:2000], language="json")
        st.code(exports.csv[:2000], language=None)
        st.code(exports.markdown[:2000], language="markdown")


def render_e2_research(
    package: E2ResearchEvidencePackage,
    receipt: E2ResearchAdmissionReceipt | None,
    comparison: E2ResearchComparisonView,
    accounting: E2TaskAccountingView,
    exports: E2ResearchExportBundle,
) -> None:
    """Aggregate render API — composes all sections.

    Consumes exact typed service/view output; does not calculate science.
    Fails closed via Lane 04 authority and service validation: package must
    be owner-authorized, receipt must equal the authoritative receipt for
    that package, and comparison/accounting/exports must equal the service
    outputs derived for that admitted package/receipt. No panels on mismatch.
    """
    render_e2_admission_banner(package, receipt)
    try:
        authoritative = admit_e2_research(package)
    except Exception:
        st.warning(
            "Package not owner-authorized; results are withheld. No result "
            "panels or downloads are shown for this package."
        )
        return
    if receipt is None or receipt != authoritative:
        st.warning(
            "Receipt does not match authoritative admission for this package; "
            "results are withheld. No result panels or downloads are shown."
        )
        return
    if not _is_owner_authorized_admitted(receipt):
        st.warning(
            "Evidence is not admitted. Results are withheld; an "
            "unadmitted study must not be treated as admitted research."
        )
        return
    try:
        from traffictwin.experiments.e2_comparison import build_e2_comparison_view
        from traffictwin.experiments.e2_task_accounting import (
            build_e2_seed1_task_accounting,
        )
        from traffictwin.reporting.e2_research import build_e2_research_exports

        expected_comparison = build_e2_comparison_view(package)
        expected_accounting = build_e2_seed1_task_accounting(package)
        expected_exports = build_e2_research_exports(package, receipt)
    except Exception:
        st.warning("Service derivation failed for this package; results are withheld.")
        return
    if (
        comparison != expected_comparison
        or accounting != expected_accounting
        or exports != expected_exports
    ):
        st.warning(
            "Supplied comparison/accounting/exports do not match the service "
            "outputs for the admitted package; results are withheld. No result "
            "panels or downloads are shown."
        )
        return
    from traffictwin.experiments.e2_strategy_semantics import e2_strategy_semantics

    semantics = e2_strategy_semantics()
    render_e2_question_motivation(package)
    render_e2_strategy_cards(semantics)
    render_e2b_table(comparison)
    render_e2c_table(comparison)
    render_e2d_table(comparison)
    render_e2_direction_reversal_summary(comparison)
    render_e2_task_accounting(accounting)
    render_e2_provenance(package, receipt)
    render_e2_limitations(package)
    render_e2_downloads(exports)


__all__ = [
    "render_e2_admission_banner",
    "render_e2_direction_reversal_summary",
    "render_e2_downloads",
    "render_e2_limitations",
    "render_e2_provenance",
    "render_e2_question_motivation",
    "render_e2_strategy_cards",
    "render_e2_task_accounting",
    "render_e2b_table",
    "render_e2c_table",
    "render_e2d_table",
    "render_e2_research",
]
