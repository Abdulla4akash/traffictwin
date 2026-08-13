"""Manchester Twin page — Lane 06 closed-loop journey view.

A real independent Streamlit page that shows the deterministic closed-loop
stage journey, exact current standing, blocker and owner action, accepted
versus software-valid distinction, provider-required state, SUMO capability
and output availability, observed/simulated compatibility and limitations,
replay/provenance links as plain product destinations, and truthful
unavailable states.

All fixtures are deterministic synthetic/design-only demonstrations only.
Every such value is labelled prominently. The page never hardcodes
invented Manchester observations, scientific acceptance, execution success,
calibration, or task/RSU telemetry. No subprocess or network call is
launched on render — strictly read-only.
"""

from __future__ import annotations

from decimal import Decimal

import streamlit as st

from traffictwin.integration.manchester.closed_loop_journey import (
    build_closed_loop_journey,
)
from traffictwin.integration.manchester.comparison import (
    ComparisonIntervalContent,
    ComparisonLineage,
    ManchesterComparisonMetricContract,
    build_observed_comparison_interval,
    build_simulated_comparison_interval,
)
from traffictwin.integration.manchester.comparison_workflow import (
    ComparisonWorkflowPrerequisites,
    build_comparison_workflow_request,
    evaluate_comparison_workflow,
)
from traffictwin.integration.manchester.models import sha256_hex
from traffictwin.integration.manchester.sumo_output_pipeline import (
    LIMITATIONS as SUMO_LIMITATIONS,
)
from traffictwin.integration.manchester.sumo_output_pipeline import (
    ManchesterSumoOutputPackage,
    ManchesterSumoOutputReceipt,
    SumoOutputFileDeclaration,
    SumoOutputNetworkIdentity,
    SumoOutputProvenance,
    SumoOutputTimeBasis,
    SumoOutputToolIdentity,
    build_sumo_output_request,
    import_sumo_outputs,
)
from traffictwin.ui.components.badges import badge_row

_SYNTHETIC_FIXTURE_LABEL = "SYNTHETIC_DESIGN_ONLY — deterministic demo, not Manchester observation"
_FIXTURE_RUN_ID = "synthetic-demo-run-01"
_FIXTURE_REQUEST_ID = "synthetic-demo-req-01"
_FIXTURE_SCOPE_FP = "a" * 64
_FIXTURE_TIME_BASIS_FP = "b" * 64
_FIXTURE_NETWORK_FP = "c" * 64
_FIXTURE_DEMAND_FP = "d" * 64
_FIXTURE_CONFIG_FP = "e" * 64


def _synthetic_tool() -> SumoOutputToolIdentity:
    return SumoOutputToolIdentity(
        reported_version="1.27.0",
        executable_sha256="f" * 64,
    )


def _synthetic_network() -> SumoOutputNetworkIdentity:
    return SumoOutputNetworkIdentity(
        network_sha256=_FIXTURE_NETWORK_FP,
        demand_sha256=_FIXTURE_DEMAND_FP,
        config_sha256=_FIXTURE_CONFIG_FP,
        network_file="net.xml",
        demand_file="routes.xml",
        config_file="sumo.sumocfg",
    )


def _synthetic_time_basis() -> SumoOutputTimeBasis:
    return SumoOutputTimeBasis(
        window_start_s=0,
        window_end_s=3600,
        step_length_s=1,
        time_basis_label="synthetic_utc_hour",
        time_basis_fingerprint=_FIXTURE_TIME_BASIS_FP,
    )


def _synthetic_tripinfo_bytes() -> bytes:
    return (
        b"<tripinfos>"
        b'<tripinfo id="synth_v0" depart="0.0" arrival="100.0" '
        b'duration="100.0" routeLength="500.0" waitingTime="5.0" '
        b'timeLoss="10.0" departLane="edgeA_0" arrivalLane="edgeB_0" />'
        b'<tripinfo id="synth_v1" depart="10.0" arrival="150.0" '
        b'duration="140.0" routeLength="600.0" waitingTime="6.0" '
        b'timeLoss="12.0" departLane="edgeA_0" arrivalLane="edgeB_0" />'
        b"</tripinfos>"
    )


def _synthetic_summary_bytes() -> bytes:
    return (
        b"<summary>"
        b'<step time="0.0" running="10" waiting="2" ended="0" '
        b'arrived="0" halting="1" collisions="0" teleports="0" />'
        b'<step time="1.0" running="12" waiting="3" ended="1" '
        b'arrived="1" halting="2" collisions="0" teleports="0" />'
        b"</summary>"
    )


def _build_synthetic_package() -> tuple[ManchesterSumoOutputPackage, ManchesterSumoOutputReceipt]:
    trip_bytes = _synthetic_tripinfo_bytes()
    summ_bytes = _synthetic_summary_bytes()
    tool = _synthetic_tool()
    network = _synthetic_network()
    time_basis = _synthetic_time_basis()
    declarations = [
        SumoOutputFileDeclaration(
            relative_path="tripinfo.xml",
            sha256=sha256_hex(trip_bytes),
            size_bytes=len(trip_bytes),
            required=True,
            media_type="application/xml",
        ),
        SumoOutputFileDeclaration(
            relative_path="summary.xml",
            sha256=sha256_hex(summ_bytes),
            size_bytes=len(summ_bytes),
            required=True,
            media_type="application/xml",
        ),
    ]
    request = build_sumo_output_request(
        request_id=_FIXTURE_REQUEST_ID,
        run_id=_FIXTURE_RUN_ID,
        tool=tool,
        network=network,
        time_basis=time_basis,
        files=declarations,
    )
    package = import_sumo_outputs(
        request,
        {
            "tripinfo.xml": trip_bytes,
            "summary.xml": summ_bytes,
        },
        provenance=SumoOutputProvenance(
            created_at_utc="2026-01-01T00:00:00Z",
            created_by="synthetic-design-fixture",
            parent_fingerprints=(),
        ),
    )
    from traffictwin.integration.manchester.sumo_output_pipeline import (
        build_output_receipt,
    )

    receipt = build_output_receipt(
        receipt_id="synthetic-receipt-01",
        request=request,
        package=package,
    )
    return package, receipt


def _build_synthetic_comparison_availability() -> str:
    contract = ManchesterComparisonMetricContract(
        contract_version="synthetic-demo-1",
        evidence_class="synthetic_development",
        observed_source="synthetic_utc_road",
        scope_label="synthetic_zone",
        scope_fingerprint=_FIXTURE_SCOPE_FP,
        time_basis_label="synthetic_utc_hour",
        time_basis_fingerprint=_FIXTURE_TIME_BASIS_FP,
        interval_duration_s=900,
        measure="vehicle_count",
        unit="vehicles_per_interval",
        minimum_observed_coverage=Decimal("0.500"),
        minimum_simulated_coverage=Decimal("0.500"),
    )
    snapshot_id = "synthetic_road-20260101T000000Z-abcdef012345"
    lineage = ComparisonLineage(
        observed_snapshot_ids=(snapshot_id,),
        projection_report_fingerprint="1" * 64,
        mapping_fingerprint="2" * 64,
        calibration_fingerprint="3" * 64,
        network_fingerprint=_FIXTURE_NETWORK_FP,
        sumo_run_fingerprint="4" * 64,
    )
    interval = ComparisonIntervalContent.model_validate(
        {
            "site_edge_id": "edgeA",
            "interval_start_s": 0,
            "interval_end_s": 900,
            "direction": "N",
            "vehicle_class": "car",
            "measure": "vehicle_count",
            "unit": "vehicles_per_interval",
            "value": Decimal("10"),
            "scope_label": "synthetic_zone",
            "scope_fingerprint": _FIXTURE_SCOPE_FP,
            "time_basis_label": "synthetic_utc_hour",
            "time_basis_fingerprint": _FIXTURE_TIME_BASIS_FP,
        }
    )
    observed = build_observed_comparison_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(b"obs-row-0"),
        synthetic=True,
        source="synthetic_utc_road",
        source_snapshot_id=snapshot_id,
        projection_report_fingerprint="1" * 64,
        mapping_fingerprint="2" * 64,
    )
    simulated = build_simulated_comparison_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(b"sim-row-0"),
        synthetic=True,
        network_fingerprint=_FIXTURE_NETWORK_FP,
        calibration_fingerprint="3" * 64,
        sumo_run_fingerprint="4" * 64,
    )
    prereq = ComparisonWorkflowPrerequisites(
        provider_evidence_available=True,
        map_match_standing="HUMAN_ACCEPTED",
        demand_standing="SYNTHETIC_ENGINEERING_CANDIDATE",
        demand_software_valid=True,
        calibration_accepted=True,
        baseline_accepted=True,
        output_software_valid=True,
        output_fingerprint="9" * 64,
    )
    req = build_comparison_workflow_request(
        workflow_id="synthetic-compare-01",
        contract=contract,
        lineage=lineage,
        observed_inputs=[observed],
        simulated_inputs=[simulated],
        prerequisites=prereq,
    )
    result = evaluate_comparison_workflow(req)
    return result.standing


def render() -> None:
    """Render the Manchester Twin page — no side effects."""

    st.title("Manchester Twin — Closed-Loop Journey")
    badge_row(["OFFLINE", "SECRET-FREE", "DETERMINISTIC", "BOUNDED"])
    st.caption(
        "Deterministic closed-loop stage view over exact identities and receipts. "
        "No SUMO execution, network fetch, or filesystem mutation on render."
    )
    st.warning(_SYNTHETIC_FIXTURE_LABEL)

    st.subheader("Closed-loop stage journey — truthful no-provider state")
    st.caption(
        "Journey is built from deterministic no-provider state: provider data is "
        "PROVIDER_DATA_REQUIRED, while synthetic SUMO remains separately AVAILABLE "
        "when prerequisites present. No scientific acceptance self-claimed."
    )

    journey_no_provider = build_closed_loop_journey(
        journey_id="twin-journey-no-provider",
        source_provider_available=False,
        source_snapshot_id=None,
        baseline_package=None,
        baseline_decision=None,
        baseline_software_validation=None,
        map_workflow=None,
        demand_result=None,
        demand_receipt=None,
        demand_decision=None,
        calibration_result=None,
        calibration_decision=None,
        calibration_receipt=None,
        sumo_request=None,
        sumo_receipt=None,
        output_package=None,
        output_receipt=None,
        comparison_result=None,
    )

    cols = st.columns(3)
    cols[0].metric("Overall standing", journey_no_provider.overall_standing)
    cols[1].metric(
        "Synthetic execution",
        "AVAILABLE" if journey_no_provider.synthetic_execution_available else "UNAVAILABLE",
    )
    cols[2].metric(
        "Scientific acceptance",
        "PRESENT" if journey_no_provider.scientific_acceptance_present else "ABSENT",
    )
    st.caption(
        "Overall PROVIDER_DATA_REQUIRED with synthetic AVAILABLE reflects design — "
        "not scientific claim."
    )

    stage_rows = [
        {
            "stage": s.stage_id,
            "standing": s.standing,
            "blocker": s.blocker_code or "—",
            "owner action": s.owner_action,
            "evidence": s.evidence_class,
        }
        for s in journey_no_provider.stages
    ]
    st.dataframe(stage_rows, hide_index=True, width="stretch")
    st.caption(
        "Accepted vs software-valid: SOFTWARE_VALID is structurally sound; "
        "SCIENTIFICALLY_ACCEPTED_BASELINE needs explicit attributable decision."
    )

    st.subheader("SUMO capability and output availability — synthetic design-only")
    st.warning(_SYNTHETIC_FIXTURE_LABEL)
    pkg, receipt = _build_synthetic_package()
    ecols = st.columns(4)
    ecols[0].metric("Tripinfo records", pkg.counts.tripinfo_records)
    ecols[1].metric("Summary records", pkg.counts.summary_records)
    ecols[2].metric("FCD records", pkg.counts.fcd_records)
    ecols[3].metric("Evidence standing", pkg.evidence_standing)
    st.caption(
        f"Package fingerprint: {pkg.package_fingerprint[:16]}… — software-valid "
        "simulated only, never observed."
    )
    st.caption(
        f"Receipt fingerprint: {receipt.receipt_fingerprint[:16]}… — portable, no private path."
    )
    st.caption("Limitations: " + "; ".join(pkg.limitations[:3]) + "…")
    st.caption(SUMO_LIMITATIONS[2])
    st.caption(
        "VEC task separation: SUMO vehicles are never mapped to VEC tasks, "
        "RSU execution targets, or Dynamic Resource telemetry."
    )

    st.subheader("Observed / simulated compatibility — synthetic demo")
    st.warning(_SYNTHETIC_FIXTURE_LABEL)
    comp_standing = _build_synthetic_comparison_availability()
    st.metric("Synthetic comparison standing", comp_standing)
    st.caption(
        "Compatibility requires exact measure, unit, interval, time basis, scope, "
        "spatial mapping, class, direction, and lineage. Incompatible values are "
        "refused without coercion, resampling, or zero-fill."
    )
    st.caption(
        "Uncertainty unavailable unless scientifically supplied; descriptive "
        "differences are non-causal and do not establish calibration or realism."
    )

    st.subheader("Replay, provenance, and report links — plain destinations")
    st.caption(
        "Links are plain product destinations — they do not launch execution or "
        "imply scientific acceptance."
    )
    st.markdown("- **Replay** → `replay` product destination (historical run replay)")
    st.markdown("- **Provenance** → `provenance` product destination (receipt chain)")
    st.markdown("- **Report** → `reports` product destination (deterministic report)")
    st.caption("When no output or comparison is available, links are UNAVAILABLE — truthfully.")

    st.subheader("Limitations and truthful unavailable states")
    for lim in journey_no_provider.limitations:
        st.caption(f"Limitation: {lim}")
    st.info(
        "No-provider state is truthfully PROVIDER_DATA_REQUIRED. Synthetic outputs "
        "are labelled SYNTHETIC_DESIGN_ONLY and cannot produce "
        "SCIENTIFICALLY_ACCEPTED_BASELINE or Manchester observational claims. "
        "Absent tripinfo/summary/FCD outputs are reported as unavailable."
    )
    st.caption("This page performed no subprocess launch, network call, or filesystem write.")
