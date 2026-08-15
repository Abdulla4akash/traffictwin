"""Research Registry — read-only, typed Lane 07/08 registry.

Read-only surface backed exclusively by the typed Lane 07/08 registry service
and the current admitted E2 adapter. No duplicate E2 validators, no hard-coded
scientific results, no arbitrary file import or network retrieval, no E3.
E0/E1 appear only with truthful typed UNAVAILABLE standing supplied by the
adapter.
"""

from __future__ import annotations

import json

import streamlit as st

from traffictwin.research_registry.adapters import (
    E2B_STUDY,
    E2C_STUDY,
    E2D_STUDY,
)
from traffictwin.research_registry.models import (
    AdmissionStatus,
    EvidenceStanding,
    ResearchStudyRecord,
)
from traffictwin.research_registry.service import RegistryService, RegistrySnapshot
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.components.unavailable import render_unavailable_panel

SESSION_KEY_SELECTED = "research_registry_selected"


def _load_snapshot() -> RegistrySnapshot:
    """Load typed snapshot via Lane 07/08 service and current E2 adapter.

    Uses the typed service exclusively; verification is delegated to the
    adapter/service. No fallback heuristic.
    """
    service = RegistryService.with_default_e2()
    snapshot = service.snapshot()
    # Canonical revalidation at boundary
    return RegistrySnapshot.model_validate(snapshot.model_dump(mode="json"))


def _badge_for_standing(evidence: EvidenceStanding, admission: AdmissionStatus) -> str:
    if (
        admission == AdmissionStatus.ADMITTED
        and evidence == EvidenceStanding.RESEARCH_EVIDENCE_FACT
    ):
        return ":green-badge[ADMITTED RESEARCH]"
    if evidence == EvidenceStanding.UNAVAILABLE:
        return badge_markdown("unavailable")
    if admission == AdmissionStatus.NOT_ADMITTED:
        return ":red-badge[NOT ADMITTED]"
    if admission == AdmissionStatus.PENDING:
        return ":orange-badge[PENDING]"
    return badge_markdown(evidence.value)


def _render_boundaries() -> None:
    with st.container(border=True):
        st.subheader("Import, evidence, and product admission")
        st.caption(
            "Structural import verifies package fingerprint, sorted identities, and deterministic "
            "receipt binding. It proves the package was processed as declared."
        )
        st.caption(
            "Trusted evidence requires the current admitted E2 adapter: exact code SHA "
            "(40-hex), manifest hash (64-hex), and owner-authorized standing "
            "RESEARCH-EVIDENCE FACT."
        )
        st.caption(
            "Product admission is the standing field plus the typed receipt. "
            "It does not establish external validity or follow-on deployment."
        )
        st.caption(
            "Digest is binding, not cryptographic authenticity; policy distribution "
            "must be verified separately."
        )


def _render_lineage_warning() -> None:
    st.caption(
        "Lineage declares explicit typed relationships only. It does not establish causality, "
        "and aggregate E2 study results do not supply task-level telemetry."
    )


def _render_unavailable_snapshot_error(exc: Exception) -> None:
    del exc
    st.error("Research Registry snapshot could not be constructed: REGISTRY_CONSTRUCTION_FAILED")
    render_unavailable_panel(
        "Research Registry unavailable",
        ["Typed registry construction or verification failed — snapshot unavailable"],
        ["REGISTRY_CONSTRUCTION_FAILED"],
    )
    st.caption(
        "This truthful unavailable state reflects a typed service failure, not a successful "
        "registry. Check adapter, policy, and receipt verification."
    )


def _all_records(snapshot: RegistrySnapshot) -> list[ResearchStudyRecord]:
    combined = list(snapshot.records) + list(snapshot.unavailable_records)
    return sorted(combined, key=lambda r: (r.study, r.version))


def _record_label(record: ResearchStudyRecord) -> str:
    return f"{record.study} v{record.version} — {record.title[:60]}"


def _render_study_list(snapshot: RegistrySnapshot) -> ResearchStudyRecord | None:
    st.subheader("Study inventory")
    st.caption(
        "Inspectable list of admitted and truthful UNAVAILABLE studies. Select one to inspect."
    )
    all_recs = _all_records(snapshot)
    if not all_recs:
        st.info("No studies in registry. Snapshot contains no admitted or unavailable records.")
        return None
    # E3 must be absent — render explicit note if absent (which is expected)
    studies_present = {r.study for r in all_recs}
    if "E3" not in studies_present:
        st.caption("E3 is absent/unavailable by default; no future E3 record is fabricated.")
    options = [f"{r.study}:{r.version}" for r in all_recs]
    labels = {f"{r.study}:{r.version}": _record_label(r) for r in all_recs}
    # Preserve selection in session_state — prefer admitted E2b/E2c/E2d when no prior selection
    preferred = next((o for o in options if o.startswith(f"{E2B_STUDY}:")), None)
    if preferred is None:
        preferred = next((o for o in options if o.startswith(f"{E2C_STUDY}:")), None)
    if preferred is None:
        preferred = next((o for o in options if o.startswith(f"{E2D_STUDY}:")), None)
    default_key = preferred or options[0]
    current = st.session_state.get(SESSION_KEY_SELECTED, default_key)
    if current not in options:
        current = default_key
    selected_key = st.selectbox(
        "Select study",
        options=options,
        index=options.index(current),
        format_func=lambda k: labels.get(k, k),
        key="research_registry_selectbox",
    )
    st.session_state[SESSION_KEY_SELECTED] = selected_key
    study, version = selected_key.split(":", 1)
    found = snapshot.get_by_identity(study, version)
    if found is None:
        st.warning(f"Selected study {selected_key} not found in snapshot.")
        return None
    # Truthful unavailable/not-claim coverage: small table
    rows = []
    for rec in all_recs:
        rows.append(
            {
                "study": rec.study,
                "version": rec.version,
                "status": rec.status.value,
                "evidence": rec.evidence_standing.value,
                "admission": rec.admission_status.value,
                "replication_unit": rec.replication_unit or "Unavailable",
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        "Structural import identities are sorted canonical; trusted evidence appears only "
        "for exact admitted E2 studies."
    )
    return found


def _render_question_hypothesis(record: ResearchStudyRecord) -> None:
    st.subheader("Research question, hypothesis, and mechanism")
    st.markdown(f"**Study:** {record.study} **Version:** {record.version}")
    st.markdown(f"**Title:** {record.title}")
    st.markdown(f"**Research question:** {record.question}")
    if record.hypothesis is not None:
        st.markdown(f"**Hypothesis:** {record.hypothesis}")
    else:
        st.caption("Hypothesis: Unavailable — no hypothesis declared for this study.")
    st.caption(
        "Mechanism description is taken only from typed record fields where available; "
        "no mechanism is inferred or fabricated for unavailable studies."
    )


def _render_identities(record: ResearchStudyRecord) -> None:
    st.subheader("Provenance and reproducibility identities")
    st.caption(
        "Exact study/version/code/manifest/evaluator/actor/trace identities. "
        "Unavailable fields stay visible as Unavailable, never hidden or zero-filled."
    )
    rows = [
        {"field": "study", "value": record.study},
        {"field": "version", "value": record.version},
        {"field": "code_sha (40-hex)", "value": record.code_sha or "Unavailable"},
        {"field": "manifest_hash (64-hex)", "value": record.manifest_hash or "Unavailable"},
        {"field": "evaluator_id", "value": record.evaluator_id or "Unavailable"},
        {"field": "actor_id (64-hex)", "value": record.actor_id or "Unavailable"},
        {"field": "checkpoint_id (64-hex)", "value": record.checkpoint_id or "Unavailable"},
        {"field": "trace_id (64-hex)", "value": record.trace_id or "Unavailable"},
        {"field": "replication_unit", "value": record.replication_unit or "Unavailable"},
        {"field": "status", "value": record.status.value},
        {"field": "evidence_standing", "value": record.evidence_standing.value},
        {"field": "admission_status", "value": record.admission_status.value},
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    for rec_field in ("code_sha", "manifest_hash", "actor_id", "checkpoint_id", "trace_id"):
        val = getattr(record, rec_field)
        if val:
            with st.expander(f"Advanced: full {rec_field}"):
                st.code(val, language=None)
                st.caption(f"Fingerprint summary: `{fingerprint_summary(val)}`")
    # Also show snapshot fingerprint binding if available via outer scope
    st.caption("Identities are verified at typed service boundaries.")


def _render_design(record: ResearchStudyRecord) -> None:
    st.subheader("Experimental design")
    st.caption("Draws, arms, estimand, and primary versus secondary metrics.")
    if record.evidence_standing == EvidenceStanding.UNAVAILABLE:
        render_unavailable_panel(
            "Experimental design unavailable",
            [
                f"Study {record.study} v{record.version} has UNAVAILABLE evidence standing",
                "No draws, arms, estimand, or metrics are declared for unavailable studies",
            ],
            ["DESIGN_UNAVAILABLE"],
        )
        return
    design_rows = [
        {
            "field": "seeds",
            "value": str(record.seeds) if record.seeds is not None else "Unavailable",
        },
        {
            "field": "draws",
            "value": str(record.draws) if record.draws is not None else "Unavailable",
        },
        {"field": "arms", "value": str(record.arms) if record.arms is not None else "Unavailable"},
        {"field": "estimand", "value": record.estimand or "Unavailable"},
        {
            "field": "primary_metrics",
            "value": str(record.primary_metrics) if record.primary_metrics else "Unavailable",
        },
        {
            "field": "secondary_metrics",
            "value": str(record.secondary_metrics) if record.secondary_metrics else "None declared",
        },
    ]
    st.dataframe(design_rows, hide_index=True, width="stretch")
    # Derive caption from typed replication_unit, never hardcode fleet_draw
    if record.replication_unit:
        st.caption(
            f"Replication unit is {record.replication_unit}; tasks are accounting records, "
            "not independent replicates."
        )
    else:
        st.caption(
            "Replication unit unavailable; tasks are accounting records, "
            "not independent replicates."
        )


def _render_per_draw_and_summary(record: ResearchStudyRecord) -> None:
    st.subheader("Per-draw values, summary, and declared interval")
    st.caption(
        "Per-draw values carry exact arm and metric identity where declared; declared interval "
        "is reproduced verbatim from the typed record."
    )
    if record.per_draw_values is None:
        render_unavailable_panel(
            "Per-draw values unavailable",
            [f"Study {record.study} v{record.version} has no per-draw values"],
            ["PER_DRAW_UNAVAILABLE"],
        )
    else:
        rows: list[dict[str, str]] = []
        for v in record.per_draw_values:
            rows.append(
                {
                    "draw": str(v.draw),
                    "arm": v.arm or "—",
                    "metric": v.metric or "—",
                    "value": str(v.value),
                }
            )
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption(f"Total per-draw rows: {len(rows)}")
        st.caption("Aggregate values do not supply task-level telemetry.")
    if record.declared_summary is None:
        st.caption("Declared summary: Unavailable — no summary declared for this study.")
    else:
        s = record.declared_summary
        st.markdown(f"**Estimate:** `{s.estimate}`")
        if s.ci_lower is not None and s.ci_upper is not None:
            # Generic label: Declared interval unless typed coverage exists
            st.markdown(f"**Declared interval:** `[{s.ci_lower}, {s.ci_upper}]`")
        else:
            st.caption("Declared interval: Unavailable")
        if s.method:
            st.caption(f"Method: {s.method}")
        if s.arm:
            st.caption(f"Summary arm: {s.arm}")
        if s.metric:
            st.caption(f"Summary metric: {s.metric}")
        with st.expander("Advanced: summary payload"):
            st.code(json.dumps(s.model_dump(mode="json"), indent=2), language="json")


def _render_evidence_admission(record: ResearchStudyRecord) -> None:
    st.subheader("Evidence and admission standing")
    st.markdown(_badge_for_standing(record.evidence_standing, record.admission_status))
    st.markdown(
        f"**Evidence standing:** `{record.evidence_standing.value}`  "
        f"**Admission status:** `{record.admission_status.value}`"
    )
    if record.evidence_standing == EvidenceStanding.RESEARCH_EVIDENCE_FACT:
        st.caption(
            "Trusted evidence: RESEARCH-EVIDENCE FACT with exact code SHA and manifest binding."
        )
    elif record.evidence_standing == EvidenceStanding.UNAVAILABLE:
        st.caption(
            "Truthful UNAVAILABLE standing supplied by the typed adapter; no fabricated "
            "evidence, SHA, or outcome is presented."
        )
    if record.admission_status == AdmissionStatus.ADMITTED:
        st.caption("Product admission: ADMITTED — explicit admission via typed policy and receipt.")
    else:
        st.caption(f"Product admission: {record.admission_status.value} — not product-admitted.")


def _render_lineage(snapshot: RegistrySnapshot, record: ResearchStudyRecord) -> None:
    st.subheader("Lineage")
    st.caption(
        "Explicit typed relationships only, each with declared relationship, "
        "rationale, and source. Lineage does not establish causality."
    )
    # Find edges incident to this study
    relevant = [
        e
        for e in snapshot.lineage.edges
        if (e.source_study == record.study and e.source_version == record.version)
        or (e.target_study == record.study and e.target_version == record.version)
    ]
    if not relevant:
        if record.evidence_standing == EvidenceStanding.UNAVAILABLE:
            st.caption(
                f"Study {record.study} v{record.version} has no lineage edges — unavailable "
                "studies carry no inferred lineage."
            )
        else:
            st.caption(f"Study {record.study} v{record.version} has no lineage edges.")
        # Still show full graph for inspectability
        with st.expander("Advanced: full lineage graph"):
            if snapshot.lineage.edges:
                edge_rows = [
                    {
                        "source": f"{e.source_study}:{e.source_version}",
                        "target": f"{e.target_study}:{e.target_version}",
                        "relationship": e.relationship.value,
                        "declared_source": e.declared_source,
                    }
                    for e in snapshot.lineage.edges
                ]
                st.dataframe(edge_rows, hide_index=True, width="stretch")
                for e in snapshot.lineage.edges:
                    st.code(
                        f"{e.source_study}:{e.source_version} --[{e.relationship.value}]--> "
                        f"{e.target_study}:{e.target_version}\n"
                        f"Declared source: {e.declared_source}\n"
                        f"Provenance identity: {e.provenance_identity}\n"
                        f"Rationale: {e.rationale}\n"
                        f"Fingerprint: {e.fingerprint[:16]}…",
                        language=None,
                    )
            else:
                st.caption("Lineage graph contains no edges.")
        return
    for edge in relevant:
        with st.container(border=True):
            st.markdown(
                f"**{edge.source_study}:{edge.source_version}** --[{edge.relationship.value}]--> "
                f"**{edge.target_study}:{edge.target_version}**"
            )
            st.caption(f"Declared source: {edge.declared_source}")
            st.caption(f"Provenance identity: {edge.provenance_identity}")
            st.caption(f"Rationale: {edge.rationale}")
            with st.expander("Advanced: edge fingerprint"):
                st.code(edge.fingerprint, language=None)
    with st.expander("Advanced: full lineage graph"):
        edge_rows = [
            {
                "source": f"{e.source_study}:{e.source_version}",
                "target": f"{e.target_study}:{e.target_version}",
                "relationship": e.relationship.value,
                "declared_source": e.declared_source,
                "rationale": e.rationale[:80],
            }
            for e in snapshot.lineage.edges
        ]
        st.dataframe(edge_rows, hide_index=True, width="stretch")
    _render_lineage_warning()


def _render_limitations(record: ResearchStudyRecord) -> None:
    st.subheader("Limitations, non-claims, and product links")
    if record.limitations:
        st.markdown("**Limitations:**")
        for item in record.limitations:
            st.markdown(f"- {item}")
    else:
        st.caption("Limitations: Unavailable — no limitations declared.")
    if record.non_claims:
        st.markdown("**Non-claims:**")
        for item in record.non_claims:
            st.markdown(f"- {item}")
    else:
        st.caption("Non-claims: None declared.")
    if record.product_links:
        st.markdown("**Product links:**")
        for link in record.product_links:
            st.markdown(f"- `{link}`")
    else:
        st.caption("Product links: None — no product links declared for this study.")
    st.caption(
        "Limitations and non-claims are reproduced verbatim from the typed adapter; "
        "they are not invented in the UI."
    )


def _render_receipts(snapshot: RegistrySnapshot) -> None:
    st.subheader("Structural import and receipts")
    st.caption("Package fingerprint, receipt fingerprint, and binding note.")
    st.markdown(f"**Snapshot fingerprint:** `{fingerprint_summary(snapshot.snapshot_fingerprint)}`")
    with st.expander("Advanced: full snapshot fingerprint"):
        st.code(snapshot.snapshot_fingerprint, language=None)
    if snapshot.receipts:
        for receipt in snapshot.receipts:
            with st.container(border=True):
                st.markdown(f"**Receipt:** `{fingerprint_summary(receipt.receipt_fingerprint)}`")
                st.caption(f"Package fingerprint: `{receipt.package_fingerprint}`")
                st.caption(f"Policy fingerprint: `{receipt.policy_fingerprint}`")
                st.caption(f"Record fingerprints: {', '.join(receipt.record_fingerprints)}")
                if receipt.lineage_fingerprint:
                    st.caption(f"Lineage fingerprint: `{receipt.lineage_fingerprint}`")
                st.caption(receipt.note)
                with st.expander("Advanced: receipt JSON"):
                    st.code(json.dumps(receipt.model_dump(mode="json"), indent=2), language="json")
    else:
        render_unavailable_panel(
            "Import receipts unavailable",
            ["No import receipts in snapshot"],
            ["RECEIPT_UNAVAILABLE"],
        )
    # Also show lineage fingerprint
    if snapshot.lineage.edges:
        with st.expander("Advanced: lineage graph fingerprint"):
            st.code(snapshot.lineage.fingerprint(), language=None)
    st.caption("No dynamic-resource semantics are claimed or displayed here.")
    st.caption("Forked receipt or mutated record fails closed at typed service validation.")


def render(config: object) -> None:  # noqa: ANN001, ARG001
    """Render the Research Registry page."""
    del config
    # Page header: prefer typed UiPage if available, else fallback to st.title
    try:
        from traffictwin.ui.labels import UiPage
        from traffictwin.ui.navigation import render_page_header

        page_enum = getattr(UiPage, "RESEARCH_REGISTRY", None)
        if page_enum is not None:
            render_page_header(page_enum)
        else:
            st.title("Research Registry")
            st.caption("TrafficTwin / Research Registry")
    except Exception:
        st.title("Research Registry")
        st.caption("TrafficTwin / Research Registry")

    st.caption(
        "Read-only registry backed exclusively by the typed Lane 07/08 registry service "
        "and the current admitted E2 adapter. No file import, no network retrieval, no E3."
    )
    st.warning(
        "This is a read-only registry view. It reproduces only the exact typed records "
        "and receipts supplied by the adapter; it does not admit new studies or infer causality "
        "from lineage."
    )

    # Attempt typed construction; render truthful unavailable/error on failure
    try:
        snapshot = _load_snapshot()
    except Exception as exc:  # typed verification failure — surface as unavailable, not success
        _render_unavailable_snapshot_error(exc)
        # Also ensure lineage causality and telemetry warnings remain visible even in error
        _render_lineage_warning()
        st.caption("E3 is absent by default; no E3 record, policy, or claim is created.")
        st.caption("No dynamic-resource semantics.")
        return

    _render_boundaries()
    _render_lineage_warning()

    selected = _render_study_list(snapshot)
    if selected is None:
        st.info("Select a study above to inspect its typed record.")
        _render_receipts(snapshot)
        return

    # Distinguish admitted vs unavailable clearly
    if selected.evidence_standing == EvidenceStanding.UNAVAILABLE:
        st.info(
            f"Study {selected.study} v{selected.version} is truthfully UNAVAILABLE: "
            "no code SHA, manifest, or outcomes are presented."
        )

    _render_question_hypothesis(selected)
    _render_identities(selected)
    _render_evidence_admission(selected)
    _render_design(selected)
    _render_per_draw_and_summary(selected)
    _render_lineage(snapshot, selected)
    _render_limitations(selected)
    _render_receipts(snapshot)

    # Footer: reproducibility identities summary
    with st.expander("Advanced: raw record JSON"):
        st.code(json.dumps(selected.model_dump(mode="json"), indent=2), language="json")
    with st.expander("Advanced: reproduction identities"):
        st.caption(
            "Reproducibility identities are the exact code SHA, manifest hash, evaluator, "
            "actor, trace, and replication seeds rendered above; no additional identifiers "
            "are fabricated."
        )
        st.code(
            json.dumps(
                {
                    "study": selected.study,
                    "version": selected.version,
                    "code_sha": selected.code_sha,
                    "manifest_hash": selected.manifest_hash,
                    "evaluator_id": selected.evaluator_id,
                    "actor_id": selected.actor_id,
                    "trace_id": selected.trace_id,
                    "replication_unit": selected.replication_unit,
                    "seeds": selected.seeds,
                    "draws": selected.draws,
                },
                indent=2,
            ),
            language="json",
        )
