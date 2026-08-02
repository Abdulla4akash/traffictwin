"""Read-only Manchester Gate-D contract and comparison-readiness browser."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.manchester_gate_d_services import (
    ManchesterGateDConsoleError,
    load_manchester_gate_d_console,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    del config
    st.title("Manchester Gate-D")
    badge_row(["FOUNDATION ONLY", "OWNER-APPROVED CANDIDATE CEILING", "NO REAL COMPARISON"])
    st.caption(
        "Read-only integration of committed mapping, temporal-profile and contract records. "
        "It performs no human review, threshold choice, calibration, SUMO run, baseline "
        "acceptance, contract registration or comparison calculation."
    )
    try:
        console = load_manchester_gate_d_console(Path.cwd())
    except ManchesterGateDConsoleError as error:
        st.warning(f"Manchester Gate-D integration unavailable: {error}")
        return
    packet = console.packet

    st.subheader("Exact source bindings")
    st.dataframe(
        [
            {
                "source id": source.source_id,
                "repository record": source.repository_ref,
                "SHA-256": source.sha256,
                "role": source.role,
                "evidence class": source.evidence_class,
                "support scope": source.support_scope,
                "limitation": source.limitation,
                "LLM output": source.llm_output,
            }
            for source in packet.source_bindings
        ],
        hide_index=True,
        width="stretch",
    )

    mapping = packet.mapping_policy
    st.subheader("Observation-to-network mapping decision support")
    columns = st.columns(4)
    columns[0].metric("Observations", mapping.observations)
    columns[1].metric("Owner-policy candidates", mapping.owner_policy_accepted)
    columns[2].metric("Awaiting manual review", mapping.awaiting_manual_review)
    columns[3].metric("No suitable candidate", mapping.no_suitable_candidate)
    st.caption(
        f"Policy `{mapping.policy_id}` / `{mapping.policy_fingerprint}`. Owner-policy acceptance "
        "is not human, analyst or supervisor acceptance."
    )
    st.dataframe(
        [
            {
                "retrieval radius (m)": mapping.outer_search_radius_m,
                "native eligibility (m)": mapping.native_eligibility_m,
                "fallback eligibility (m)": mapping.fallback_eligibility_m,
                "native strict-clear (m)": mapping.strict_clear_native_m,
                "fallback strict-clear (m)": mapping.strict_clear_fallback_m,
                "direction tolerance (degrees)": mapping.direction_tolerance_degrees,
                "exact-reference override (m)": mapping.exact_reference_override_m,
                "automatic acceptance": mapping.automatic_acceptance,
            }
        ],
        hide_index=True,
        width="stretch",
    )

    for table in packet.sensitivity_tables:
        with st.expander(f"Measured sensitivity — {table.population_id}"):
            st.caption(
                f"Population n={table.population}. These rows support threshold review; they do "
                "not select or validate a threshold."
            )
            st.dataframe(
                [
                    {
                        "radius (m)": row.radius_m,
                        "sites with candidate": row.sites_with_candidate,
                        "population": row.population,
                        "mean candidates": row.mean_candidates,
                        "median": row.median_candidates,
                        "p90": row.p90_candidates,
                        "maximum": row.max_candidates,
                        "multi-road-class (%)": row.multi_road_class_percent,
                    }
                    for row in table.rows
                ],
                hide_index=True,
                width="stretch",
            )

    st.subheader("Policy reconciliation and human-review boundary")
    st.dataframe(
        [
            {
                "acceptance path": "strict_v1_0_clear",
                "rows": mapping.strict_acceptances,
                "analyst accepted": mapping.analyst_accepted,
            },
            {
                "acceptance path": "exact_reference_family_override",
                "rows": mapping.override_acceptances,
                "analyst accepted": mapping.analyst_accepted,
            },
            {
                "acceptance path": "awaiting_manual_review",
                "rows": mapping.awaiting_manual_review,
                "analyst accepted": mapping.analyst_accepted,
            },
            {
                "acceptance path": "no_suitable_candidate",
                "rows": mapping.no_suitable_candidate,
                "analyst accepted": mapping.analyst_accepted,
            },
        ],
        hide_index=True,
        width="stretch",
    )
    review = packet.analyst_review
    st.warning(
        f"Named-person review remains pending: {review.pending_total}/{review.queue_total} queued "
        f"rows have no decision. This includes {review.awaiting_manual_review} ambiguous rows and "
        f"preserves {review.no_candidate_preserved_total} no-candidate rows. The sealed ledger "
        "contract exists; this page cannot edit it."
    )

    profile = packet.temporal_profile
    st.subheader("Temporal-profile connection")
    st.caption(
        f"Policy `{profile.policy_id}` / `{profile.policy_fingerprint}` binds snapshot "
        f"`{profile.source_snapshot_id}`. The source uses local clock labels; no UTC instant is "
        "created. Coverage measures completeness, not accuracy or representativeness."
    )
    profile_columns = st.columns(4)
    profile_columns[0].metric("Sites", profile.sites)
    profile_columns[1].metric("Series", profile.series)
    profile_columns[2].metric("Observed cells", profile.observed_cells)
    profile_columns[3].metric("Measured zeros", profile.measured_zero_cells)
    st.dataframe(
        [partition.model_dump(mode="json") for partition in profile.partitions],
        hide_index=True,
        width="stretch",
    )
    st.info(
        "One observed hourly cell may be represented only as one exact 3,600-second "
        "vehicles-per-interval input. No timezone conversion, resampling, interpolation, source "
        "fusion or missing-as-zero step is available. DfT time semantics remain blocked by "
        f"{profile.dft_time_semantics_blocker}; WebTRIS remains separate and blocked by "
        f"{profile.webtris_time_semantics_blocker}."
    )

    st.subheader("Calibration orchestration")
    st.dataframe(
        [
            {
                "dependency": dependency.title,
                "state": dependency.state,
                "blocker owner": dependency.blocker_owner,
                "satisfied downstream": dependency.satisfied_for_downstream,
                "source fingerprint": dependency.source_fingerprint or "unavailable",
                "summary": dependency.summary,
            }
            for dependency in packet.calibration.dependencies
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "No calibration objective or ranking exists. The production calibration registry remains "
        "empty, and the preserved demand candidate failed feasibility through gridlock."
    )

    st.subheader("Versioned baseline-candidate workflow")
    st.dataframe(
        [
            {"position": index, "required stage": stage}
            for index, stage in enumerate(packet.baseline.required_order, start=1)
        ],
        hide_index=True,
        width="stretch",
    )
    for requirement in packet.baseline.missing_requirements:
        st.warning(f"Baseline unavailable — {requirement}.")
    st.caption(
        "Baseline created: false · baseline accepted: false · SUMO executed: false · automatic "
        "acceptance: false · scientific evidence: false."
    )

    comparison = packet.comparison
    contract = comparison.contract
    st.subheader("Observed-versus-simulated comparison contract")
    st.caption(
        f"Owner-candidate contract `{contract.contract_version}` / "
        f"`{comparison.contract_fingerprint}`. Registration: {comparison.registration_state}; "
        "no compatible real result is available."
    )
    st.dataframe(
        [
            {
                "source": contract.observed_source,
                "scope": contract.scope_label,
                "time basis": contract.time_basis_label,
                "interval seconds": contract.interval_duration_s,
                "measure": contract.measure,
                "unit": contract.unit,
                "pairing keys": " | ".join(contract.pairing_key_fields),
                "weighting": contract.weighting_policy,
                "missing": contract.missing_policy,
                "observed minimum coverage": contract.minimum_observed_coverage,
                "simulated minimum coverage": contract.minimum_simulated_coverage,
                "metrics": " | ".join(contract.goodness_of_fit_metrics),
                "precision": contract.result_quantum,
                "interpretation": contract.interpretation_policy,
            }
        ],
        hide_index=True,
        width="stretch",
    )
    st.dataframe(
        [metric.model_dump(mode="json") for metric in comparison.metrics],
        hide_index=True,
        width="stretch",
    )
    for requirement in comparison.missing_requirements:
        st.warning(f"Comparison unavailable — {requirement}.")
    st.caption(
        "GEH is outside this frozen contract and no GEH threshold exists. A future low error "
        "would remain descriptive and would not establish causality, realism or model validity."
    )

    st.subheader("Complete Gate-D lineage")
    st.dataframe(
        [
            {
                "position": stage.position,
                "stage": stage.stage,
                "state": stage.state,
                "artifact fingerprint": stage.artifact_fingerprint or "unavailable",
                "waits on": " | ".join(stage.waits_on) or "none",
                "summary": stage.summary,
                "accepted capability": stage.accepted_capability,
            }
            for stage in packet.lineage
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"Packet digest `{packet.digest()}`. Formal capability status remains "
        f"`{packet.capability_status}` and Gate D remains `{packet.gate_d_state}`."
    )

    st.subheader("Repository citations")
    for link in console.source_links:
        st.markdown(f"- [{link.label}]({link.url}) — SHA-256 `{link.sha256}`; {link.role}.")
    st.caption(
        "Project measurements, candidate contracts, software receipts and any later scientific "
        "evidence remain separate. This page and its prose are not evidence."
    )
