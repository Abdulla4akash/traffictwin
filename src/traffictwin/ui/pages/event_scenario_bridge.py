"""Deterministic Event-to-Scenario Bridge — unexecuted what-if design preview."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import streamlit as st
from pydantic import ValidationError

from traffictwin.event_scenario_bridge.models import (
    DeclaredEventReference,
    EventImpactEnvelope,
    EventScenarioBridgeRequest,
    EvidenceStanding,
    MutationKind,
    ScenarioMutationProposal,
)
from traffictwin.event_scenario_bridge.service import (
    EventScenarioBridgeError,
    build_event_scenario_bridge_manifest,
    export_bridge_csv,
    export_bridge_json,
)
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.components.cards import fingerprint_summary, section_header

EVIDENCE_BOUNDARY_TEXT = (
    "This page builds an **unexecuted, reviewable what-if design** from a declared authored event. "
    "It does not run SUMO, VEC, or any simulator; it does not create evidence or admission; "
    "and the synthetic design does **not** represent the real event. Findings are descriptive "
    "for declared [start,end) windows, not causal claims."
)

LIMITATIONS_TEXT = (
    "All four handoffs — scenario seed/mutation, Event-Aligned spec, preregistration draft, "
    "and experiment plan — bind the same event and baseline fingerprints, use half-open "
    "[start,end) windows, and remain `not_executed` with `evidence_created=false` and "
    "`admission_created=false`. Mutations are limited to closed, bounded types already "
    "supported on main (bounded demand change, lane closure, road clearing, RSU removal, "
    "timestamp/event-window adjustment)."
)

_SUPPORTED_METRICS_FOR_UI = [
    "task.completion.rate",
    "task.latency.mean_ms",
    "task.energy.mean_per_observed_task_j",
    "infra.queue_length.mean",
    "infra.utilisation.mean",
    "trip.duration.mean_s",
    "trip.completion.rate",
    "traffic.speed.mean_mps",
]

_WINDOW_OPTIONS = ["pre", "event", "post", "baseline", "comparison"]

_MUTATION_LABELS: dict[str, str] = {
    MutationKind.BOUNDED_DEMAND_CHANGE.value: "Bounded demand change",
    MutationKind.LANE_CLOSURE.value: "Lane closure",
    MutationKind.ROAD_CLEARING.value: "Road clearing",
    MutationKind.RSU_REMOVAL.value: "RSU removal",
    MutationKind.TIMESTAMP_EVENT_WINDOW_ADJUSTMENT.value: "Timestamp / event-window adjustment",
}


def _parse_iso_utc(raw: str) -> datetime | EventScenarioBridgeError:
    try:
        value = raw.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return EventScenarioBridgeError(
                "Anchor time must be timezone-aware (e.g. 2026-07-17T12:00:00Z)"
            )
        return dt.astimezone(UTC)
    except EventScenarioBridgeError:
        raise
    except Exception as exc:  # noqa: BLE001
        return EventScenarioBridgeError(f"Anchor time must be ISO8601 UTC: {exc}")


def _form_input_fingerprint(
    *,
    event_id: str,
    event_kind: str,
    anchor_raw: str,
    source_label: str,
    provenance_detail: str,
    artifact_fp: str,
    bundle_id: str,
    baseline_seed_id: str,
    baseline_fp: str,
    area_label: str,
    affected_links_raw: str,
    pre_s: float,
    event_s: float,
    post_s: float,
    bin_w: float,
    mutation_inputs: list[dict[str, object]],
    intended_metrics: list[str],
    intended_windows: list[str],
    bridge_id: str,
    bridge_title: str,
    bridge_desc: str,
    evidence_standing: str,
) -> str:
    payload = {
        "affected_links_raw": affected_links_raw,
        "anchor_raw": anchor_raw,
        "area_label": area_label,
        "artifact_fp": artifact_fp,
        "baseline_fp": baseline_fp,
        "baseline_seed_id": baseline_seed_id,
        "bin_w": bin_w,
        "bridge_desc": bridge_desc,
        "bridge_id": bridge_id,
        "bridge_title": bridge_title,
        "bundle_id": bundle_id,
        "event_id": event_id,
        "event_kind": event_kind,
        "event_s": event_s,
        "evidence_standing": evidence_standing,
        "intended_metrics": sorted(intended_metrics),
        "intended_windows": sorted(intended_windows),
        "mutation_inputs": mutation_inputs,
        "post_s": post_s,
        "pre_s": pre_s,
        "provenance_detail": provenance_detail,
        "source_label": source_label,
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _metric_options() -> list[str]:
    return _SUPPORTED_METRICS_FOR_UI


def render() -> None:  # noqa: C901,PLR0915 — UI is intentionally verbose but bounded
    st.title("Event-to-Scenario Bridge")
    st.caption(
        "Deterministic bridge from a declared authored event into an unexecuted, "
        "reviewable what-if study design — connecting Event-Aligned concepts, "
        "Scenario Mutations, What-If Studio, and Preregistration Studio without "
        "launching simulation."
    )
    badge_row(["UNEXECUTED", "REVIEWABLE", "NOT_MANCHESTER", "NO_SIMULATION"])
    st.warning(EVIDENCE_BOUNDARY_TEXT)
    st.info(LIMITATIONS_TEXT)

    with st.container(border=True):
        section_header(
            "What this page does NOT do",
            "No Run button. No simulator is executed; no evidence is created or admitted.",
        )
        st.markdown(
            f"- `{badge_markdown('not_executed')}` every handoff\n"
            f"- `evidence_created=false`, `admission_created=false`\n"
            f"- Windows are `[start,end)` half-open; no interpolation or zero-fill\n"
            f"- No automatic evidence admission, no scientific approval, no causality claims"
        )

    # -------------------------------------------------------------------
    # Form — all inputs bounded, local, no execution
    # -------------------------------------------------------------------
    section_header("Declare event", "Authored event reference — labelled authored, not observed.")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        event_id = c1.text_input(
            "Event ID",
            value="event-authored-001",
            key="esb_event_id",
            help="Stable authored identifier (alphanumeric, dots, hyphens, colons)",
        )
        event_kind = c2.selectbox(
            "Authored event kind",
            [
                "Authored road closure",
                "Authored demand surge",
                "Authored incident",
                "Authored manual timestamp",
            ],
            index=0,
            key="esb_event_kind",
        )
        c3, c4 = st.columns(2)
        anchor_raw = c3.text_input(
            "Anchor time (UTC ISO8601)",
            value="2026-07-17T12:00:00Z",
            key="esb_anchor",
            help="Timezone-aware UTC timestamp, e.g. 2026-07-17T12:00:00Z",
        )
        source_label = c4.text_input(
            "Authored source label",
            value="Authored \u2014 Manual timestamp",
            key="esb_source_label",
            help="Must not be labelled observed",
        )
        provenance_detail = st.text_input(
            "Provenance detail (optional)",
            value="Declared for what-if planning review",
            key="esb_provenance",
        )
        col_artifact, col_bundle = st.columns(2)
        artifact_fp = col_artifact.text_input(
            "Event artifact fingerprint (optional, 64 hex)",
            value="",
            key="esb_artifact_fp",
            placeholder="leave blank if no existing artifact",
        )
        bundle_id = col_bundle.text_input(
            "Bundle ID (optional)",
            value="",
            key="esb_bundle_id",
            placeholder="source bundle if event came from artifact",
        )

    section_header(
        "Baseline scenario seed", "Fingerprint-bound baseline; missing baseline is refused."
    )
    with st.container(border=True):
        c5, c6 = st.columns(2)
        baseline_seed_id = c5.text_input(
            "Baseline seed ID",
            value="seed-baseline",
            key="esb_baseline_seed_id",
        )
        baseline_fp = c6.text_input(
            "Baseline seed fingerprint (64 hex)",
            value="a" * 64,
            key="esb_baseline_fp",
            help="Stable SHA-256 identity for the baseline seed handoff binding",
        )

    section_header(
        "Affected area & windows", "Half-open [start,end) windows anchored to the event time."
    )
    with st.container(border=True):
        area_label = st.text_input(
            "Affected area label (optional)",
            value="Central corridor",
            key="esb_area_label",
            placeholder="e.g. Central corridor, J12\u2013J14",
        )
        affected_links_raw = st.text_input(
            "Affected links (comma-separated)",
            value="link-a, link-b",
            key="esb_links",
            help="Declared scope labels, not validated against network",
        )
        c7, c8, c9, c10 = st.columns(4)
        pre_s = c7.number_input(
            "Pre duration (s)",
            min_value=1.0,
            max_value=1_000_000.0,
            value=600.0,
            step=60.0,
            key="esb_pre",
        )
        event_s = c8.number_input(
            "Event duration (s)",
            min_value=1.0,
            max_value=1_000_000.0,
            value=600.0,
            step=60.0,
            key="esb_event",
        )
        post_s = c9.number_input(
            "Post duration (s)",
            min_value=1.0,
            max_value=1_000_000.0,
            value=600.0,
            step=60.0,
            key="esb_post",
        )
        bin_w = c10.number_input(
            "Bin width (s)",
            min_value=1.0,
            max_value=1_000_000.0,
            value=60.0,
            step=30.0,
            key="esb_bin",
        )

    section_header(
        "Mutation selection",
        "Only closed bounded types already supported on main. No arbitrary parameters.",
    )
    with st.container(border=True):
        mutation_count = st.selectbox(
            "How many ordered mutations?",
            [1, 2, 3],
            index=0,
            key="esb_mutation_count",
            help="Ordered list; joint physical effect is not modelled",
        )
        mutation_inputs: list[dict[str, object]] = []
        for idx in range(int(mutation_count)):
            st.markdown(f"**Mutation {idx + 1}**")
            mc1, mc2 = st.columns(2)
            kind = mc1.selectbox(
                f"Mutation {idx + 1} kind",
                list(_MUTATION_LABELS.keys()),
                format_func=lambda k: _MUTATION_LABELS[k],
                key=f"esb_mut_kind_{idx}",
            )
            target = mc2.text_input(
                f"Mutation {idx + 1} target description",
                value=f"what-if change {idx + 1}",
                key=f"esb_mut_target_{idx}",
            )
            row = st.columns(4)
            lanes = row[0].number_input(
                f"Mutation {idx + 1} lanes closed",
                min_value=0,
                max_value=16,
                value=1,
                step=1,
                key=f"esb_mut_lanes_{idx}",
            )
            demand = row[1].number_input(
                f"Mutation {idx + 1} demand multiplier",
                min_value=0.01,
                max_value=100.0,
                value=1.5,
                step=0.1,
                key=f"esb_mut_demand_{idx}",
            )
            rsu = row[2].text_input(
                f"Mutation {idx + 1} RSU ID", value="rsu-1", key=f"esb_mut_rsu_{idx}"
            )
            jitter = row[3].number_input(
                f"Mutation {idx + 1} timestamp jitter (s)",
                min_value=0.1,
                max_value=3600.0,
                value=60.0,
                step=10.0,
                key=f"esb_mut_jitter_{idx}",
            )
            mutation_inputs.append(
                {
                    "kind": kind,
                    "target": target,
                    "lanes": int(lanes),
                    "demand": float(demand),
                    "rsu": rsu.strip(),
                    "jitter": float(jitter),
                }
            )

    section_header(
        "Intended metrics & windows", "Authored labels for the four unexecuted handoffs."
    )
    with st.container(border=True):
        intended_metrics = st.multiselect(
            "Intended metrics",
            _metric_options(),
            default=["task.completion.rate", "trip.duration.mean_s"],
            key="esb_metrics",
        )
        intended_windows = st.multiselect(
            "Intended windows",
            _WINDOW_OPTIONS,
            default=["pre", "event", "post"],
            key="esb_windows",
        )
        bridge_id = st.text_input("Bridge ID", value="bridge-demo-001", key="esb_bridge_id")
        bridge_title = st.text_input(
            "Study title",
            value="What-if study for authored event — unexecuted design",
            key="esb_title",
        )
        bridge_desc = st.text_area(
            "Study description (optional)",
            value="Deterministic handoffs for review before any simulation.",
            key="esb_desc",
        )
        evidence_standing = st.selectbox(
            "Evidence standing",
            [e.value for e in EvidenceStanding],
            index=0,
            key="esb_standing",
            help="Authored configuration standing — unadmitted until reviewed",
        )

    # -------------------------------------------------------------------
    # Preview — deterministic handoffs, no execution
    # -------------------------------------------------------------------
    # Compute current form fingerprint for stale-preview guard
    current_form_fp = _form_input_fingerprint(
        event_id=event_id,
        event_kind=event_kind,
        anchor_raw=anchor_raw,
        source_label=source_label,
        provenance_detail=provenance_detail,
        artifact_fp=artifact_fp,
        bundle_id=bundle_id,
        baseline_seed_id=baseline_seed_id,
        baseline_fp=baseline_fp,
        area_label=area_label,
        affected_links_raw=affected_links_raw,
        pre_s=float(pre_s),
        event_s=float(event_s),
        post_s=float(post_s),
        bin_w=float(bin_w),
        mutation_inputs=mutation_inputs,
        intended_metrics=intended_metrics,
        intended_windows=intended_windows,
        bridge_id=bridge_id,
        bridge_title=bridge_title,
        bridge_desc=bridge_desc,
        evidence_standing=evidence_standing,
    )

    if st.button("Preview bridge handoffs", type="primary", key="esb_preview"):
        error_msg = _build_and_store(
            event_id=event_id,
            event_kind=event_kind,
            anchor_raw=anchor_raw,
            source_label=source_label,
            provenance_detail=provenance_detail,
            artifact_fp=artifact_fp,
            bundle_id=bundle_id,
            baseline_seed_id=baseline_seed_id,
            baseline_fp=baseline_fp,
            area_label=area_label,
            affected_links_raw=affected_links_raw,
            pre_s=float(pre_s),
            event_s=float(event_s),
            post_s=float(post_s),
            bin_w=float(bin_w),
            mutation_inputs=mutation_inputs,
            intended_metrics=intended_metrics,
            intended_windows=intended_windows,
            bridge_id=bridge_id,
            bridge_title=bridge_title,
            bridge_desc=bridge_desc,
            evidence_standing=evidence_standing,
        )
        if error_msg is not None:
            st.error(error_msg)
        else:
            # On successful preview, store current form fingerprint alongside manifest
            st.session_state["event_scenario_bridge_form_fingerprint"] = current_form_fp

    stored = st.session_state.get("event_scenario_bridge_manifest")
    stored_fp = st.session_state.get("event_scenario_bridge_form_fingerprint")
    if stored is not None:
        # Stale-preview guard: if form changed since last preview, withhold preview/exports
        if stored_fp is not None and current_form_fp != stored_fp:
            st.warning(
                "Inputs changed since the last preview. The previous fingerprint-bound preview is stale; "  # noqa: E501
                "preview again to regenerate it."
            )
        else:
            _render_handoffs(stored)


def _build_and_store(  # noqa: PLR0913
    *,
    event_id: str,
    event_kind: str,
    anchor_raw: str,
    source_label: str,
    provenance_detail: str,
    artifact_fp: str,
    bundle_id: str,
    baseline_seed_id: str,
    baseline_fp: str,
    area_label: str,
    affected_links_raw: str,
    pre_s: float,
    event_s: float,
    post_s: float,
    bin_w: float,
    mutation_inputs: list[dict[str, object]],
    intended_metrics: list[str],
    intended_windows: list[str],
    bridge_id: str,
    bridge_title: str,
    bridge_desc: str,
    evidence_standing: str,
) -> str | None:
    parsed_anchor = _parse_iso_utc(anchor_raw)
    if isinstance(parsed_anchor, EventScenarioBridgeError):
        st.session_state["event_scenario_bridge_manifest"] = None
        st.session_state["event_scenario_bridge_form_fingerprint"] = None
        return str(parsed_anchor)
    # Validate baseline fingerprint early with a friendlier message
    if not baseline_fp.strip():
        st.session_state["event_scenario_bridge_manifest"] = None
        st.session_state["event_scenario_bridge_form_fingerprint"] = None
        return "Baseline seed fingerprint is required — missing baseline is refused."
    affected_links = (
        [s.strip() for s in affected_links_raw.split(",") if s.strip()]
        if affected_links_raw.strip()
        else []
    )
    try:
        event_ref = DeclaredEventReference(
            event_id=event_id.strip(),
            event_kind=event_kind.strip(),
            anchor_time_utc=parsed_anchor,
            source_label=source_label.strip(),
            provenance_detail=provenance_detail.strip() or None,
            artifact_fingerprint=artifact_fp.strip() or None,
            bundle_id=bundle_id.strip() or None,
        )
        envelope = EventImpactEnvelope(
            affected_links=affected_links,
            affected_area_label=area_label.strip() or None,
            pre_duration_s=pre_s,
            event_duration_s=event_s,
            post_duration_s=post_s,
            bin_width_s=bin_w,
        )
        proposals: list[ScenarioMutationProposal] = []
        for inp in mutation_inputs:
            kind = str(inp["kind"])
            target = str(inp["target"]).strip()
            if kind == MutationKind.BOUNDED_DEMAND_CHANGE.value:
                proposals.append(
                    ScenarioMutationProposal(
                        mutation_kind=MutationKind.BOUNDED_DEMAND_CHANGE,
                        target_description=target,
                        demand_multiplier=float(str(inp["demand"])),
                    )
                )
            elif kind == MutationKind.LANE_CLOSURE.value:
                proposals.append(
                    ScenarioMutationProposal(
                        mutation_kind=MutationKind.LANE_CLOSURE,
                        target_description=target,
                        lanes_closed=int(str(inp["lanes"])),
                    )
                )
            elif kind == MutationKind.ROAD_CLEARING.value:
                proposals.append(
                    ScenarioMutationProposal(
                        mutation_kind=MutationKind.ROAD_CLEARING,
                        target_description=target,
                    )
                )
            elif kind == MutationKind.RSU_REMOVAL.value:
                rsu_id = str(inp["rsu"]).strip()
                if not rsu_id:
                    st.session_state["event_scenario_bridge_manifest"] = None
                    st.session_state["event_scenario_bridge_form_fingerprint"] = None
                    return "RSU removal requires an RSU ID."
                proposals.append(
                    ScenarioMutationProposal(
                        mutation_kind=MutationKind.RSU_REMOVAL,
                        target_description=target,
                        rsu_id=rsu_id,
                    )
                )
            elif kind == MutationKind.TIMESTAMP_EVENT_WINDOW_ADJUSTMENT.value:
                proposals.append(
                    ScenarioMutationProposal(
                        mutation_kind=MutationKind.TIMESTAMP_EVENT_WINDOW_ADJUSTMENT,
                        target_description=target,
                        timestamp_jitter_s=float(str(inp["jitter"])),
                    )
                )
            else:
                st.session_state["event_scenario_bridge_manifest"] = None
                st.session_state["event_scenario_bridge_form_fingerprint"] = None
                return f"Unsupported mutation kind: {kind}"
        if not intended_metrics:
            st.session_state["event_scenario_bridge_manifest"] = None
            st.session_state["event_scenario_bridge_form_fingerprint"] = None
            return "Select at least one intended metric."
        request = EventScenarioBridgeRequest(
            bridge_id=bridge_id.strip(),
            title=bridge_title.strip(),
            description=bridge_desc.strip(),
            event_reference=event_ref,
            baseline_seed_fingerprint=baseline_fp.strip(),
            baseline_seed_id=baseline_seed_id.strip(),
            impact_envelope=envelope,
            mutation_proposals=proposals,
            intended_metrics=intended_metrics,
            intended_windows=intended_windows,
            evidence_standing=EvidenceStanding(evidence_standing),
        )
        manifest = build_event_scenario_bridge_manifest(request)
        st.session_state["event_scenario_bridge_manifest"] = manifest
        return None
    except ValidationError as exc:
        st.session_state["event_scenario_bridge_manifest"] = None
        st.session_state["event_scenario_bridge_form_fingerprint"] = None
        try:
            err = exc.errors()[0]
            loc = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", str(exc))
            if loc:
                return (  # noqa: E501
                    f"Study title is invalid: {msg}"
                    if "title" in loc
                    else f"{loc} is invalid: {msg}"
                )
            return f"The bridge request is invalid: {msg}"
        except Exception:
            return f"The bridge request is invalid: {exc}"
    except EventScenarioBridgeError as exc:
        st.session_state["event_scenario_bridge_manifest"] = None
        st.session_state["event_scenario_bridge_form_fingerprint"] = None
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        st.session_state["event_scenario_bridge_manifest"] = None
        st.session_state["event_scenario_bridge_form_fingerprint"] = None
        return f"The bridge request is invalid: {exc}"


def _render_handoffs(manifest: object) -> None:  # noqa: C901
    from traffictwin.event_scenario_bridge.models import EventScenarioBridgeManifest

    if not isinstance(manifest, EventScenarioBridgeManifest):
        raise TypeError("manifest must be an EventScenarioBridgeManifest")
    st.divider()
    section_header(
        "Bridge handoff preview", "Deterministic, unexecuted — review before any execution."
    )
    st.caption(
        f"Bridge fingerprint: `{fingerprint_summary(manifest.bridge_fingerprint)}` · "
        f"Event fingerprint: `{fingerprint_summary(manifest.event_fingerprint)}` · "
        f"Baseline fingerprint: `{fingerprint_summary(manifest.baseline_seed_fingerprint)}`"
    )
    with st.expander("Advanced: full fingerprints"):
        st.code(
            f"bridge: {manifest.bridge_fingerprint}\nevent:  {manifest.event_fingerprint}\n"
            f"baseline: {manifest.baseline_seed_fingerprint}\nmanifest_id: {manifest.manifest_id}",
            language=None,
        )
    st.markdown(
        f"**Identity check:** all four handoffs bind the same event and baseline — "
        f"`bridge_fingerprint={fingerprint_summary(manifest.bridge_fingerprint)}` · "
        f"`event_fingerprint={fingerprint_summary(manifest.event_fingerprint)}`"
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Execution status", manifest.execution_status)
    c2.metric("Evidence created", str(manifest.evidence_created))
    c3.metric("Admission created", str(manifest.admission_created))
    st.caption(
        "Every output remains `not_executed`; `evidence_created=false`, `admission_created=false`. "
        "No simulator command was built."
    )

    # Window preview — half-open guarantee
    with st.container(border=True):
        st.markdown("**Half-open window preview `[start,end)`**")
        preview = manifest.request.impact_envelope.preview_windows(
            manifest.request.event_reference.anchor_time_utc
        )
        st.dataframe(
            [
                {
                    "phase": phase,
                    "start_utc": window[0].isoformat().replace("+00:00", "Z"),
                    "end_utc": window[1].isoformat().replace("+00:00", "Z"),
                    "duration_s": (window[1] - window[0]).total_seconds(),
                }
                for phase, window in preview.items()
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Guarantee: `pre.end == event.start` and `event.end == post.start` — "
            "a row on an exact boundary falls in exactly one bin."
        )

    # Four handoffs
    tabs = st.tabs(
        [
            "1 · Scenario seed/mutation",
            "2 · Event-Aligned spec",
            "3 · Prereg draft",
            "4 · Experiment plan",
        ]
    )
    with tabs[0]:
        h = manifest.scenario_seed_handoff
        st.markdown(f"**{h.handoff_id}** — `{h.handoff_kind}`")
        st.caption(f"Derived seed: `{h.derived_seed_id}` · Baseline: `{h.baseline_seed_id}`")
        st.dataframe(
            [
                {"kind": p.mutation_kind.value, "target": p.target_description}
                for p in h.mutation_proposals
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            f"`{h.execution_status}` · `evidence_created={h.evidence_created}` · `admission_created={h.admission_created}`"  # noqa: E501
        )
        st.json(h.model_dump(mode="json"), expanded=False)
    with tabs[1]:
        h2 = manifest.event_aligned_handoff
        st.markdown(f"**{h2.handoff_id}** — `{h2.handoff_kind}`")
        st.caption(f"Anchor: `{h2.anchor_time_utc}` · Boundary: `{h2.bin_boundary}`")
        st.dataframe(
            [
                {
                    "pre_s": h2.impact_envelope.pre_duration_s,
                    "event_s": h2.impact_envelope.event_duration_s,
                    "post_s": h2.impact_envelope.post_duration_s,
                    "bin_width_s": h2.impact_envelope.bin_width_s,
                    "links": ", ".join(h2.impact_envelope.affected_links) or "(none)",
                }
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            f"`{h2.execution_status}` · `evidence_created={h2.evidence_created}` · `admission_created={h2.admission_created}`"  # noqa: E501
        )
        st.json(h2.model_dump(mode="json"), expanded=False)
    with tabs[2]:
        h3 = manifest.preregistration_draft_handoff
        st.markdown(f"**{h3.handoff_id}** — `{h3.handoff_kind}`")
        st.markdown(f"**Study question:** {h3.study_question}")
        st.caption(f"Standing: `{h3.evidence_standing.value}`")
        st.json(h3.model_dump(mode="json"), expanded=False)
        st.caption(
            f"`{h3.execution_status}` · `evidence_created={h3.evidence_created}` · `admission_created={h3.admission_created}`"  # noqa: E501
        )
    with tabs[3]:
        h4 = manifest.experiment_plan_handoff
        st.markdown(f"**{h4.handoff_id}** — `{h4.handoff_kind}`")
        st.caption(f"Derived seed: `{h4.derived_seed_id}` · Planned cells: {len(h4.planned_cells)}")
        if h4.planned_cells:
            st.dataframe(h4.planned_cells, hide_index=True, width="stretch")
        st.json(h4.model_dump(mode="json"), expanded=False)
        st.caption(
            f"`{h4.execution_status}` · `evidence_created={h4.evidence_created}` · `admission_created={h4.admission_created}`"  # noqa: E501
        )

    # Findings & limitations
    section_header("Findings", "Descriptive, not causal; limitations travel with every handoff.")
    st.dataframe(
        [
            {"finding_id": f.finding_id, "severity": f.severity, "description": f.description}
            for f in manifest.findings
        ],
        hide_index=True,
        width="stretch",
    )
    for warning in manifest.warnings:
        st.warning(warning)
    for lim in manifest.limitations:
        st.caption(f"Limitation: {lim}")

    # Exports — JSON + CSV
    section_header("Export", "Portable JSON and CSV (deterministic, no absolute paths).")
    col_a, col_b = st.columns(2)
    col_a.download_button(
        "Download bridge JSON",
        data=export_bridge_json(manifest),
        file_name=f"{manifest.manifest_id}.json",
        mime="application/json",
        key="esb_download_json",
        width="stretch",
    )
    col_b.download_button(
        "Download handoff summary CSV",
        data=export_bridge_csv(manifest),
        file_name=f"{manifest.manifest_id}.csv",
        mime="text/csv",
        key="esb_download_csv",
        width="stretch",
    )
    with st.expander("Full manifest JSON preview"):
        st.code(export_bridge_json(manifest), language="json")
    with st.expander("Handoff summary CSV preview"):
        st.code(export_bridge_csv(manifest), language="csv")

    st.caption(
        "This bridge is unexecuted — no simulation, no execution status change, "
        "no evidence or admission. Re-run Preview to regenerate the same fingerprints."
    )
