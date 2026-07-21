"""Graphical standalone synthetic Scenario Builder."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.domain.enums import TaskClass
from traffictwin.domain.measurement import MeasurementTableKind
from traffictwin.synthetic.config import SyntheticPolicyProfile
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    build_synthetic_config_from_form,
    generate_synthetic_bundle_for_ui,
    incident_variant_for_ui,
    preset_config_for_ui,
    preview_synthetic_scenario,
    scenario_config_to_yaml,
    synthetic_policy_options_for_ui,
    synthetic_preset_names_for_ui,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render the standalone Scenario Builder."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.SCENARIO))
    st.info(
        "Scenario Builder writes deterministic synthetic TrafficTwin bundles. "
        "It does not launch Randy, SUMO, or live data sources."
    )
    badge_row(["SYNTHETIC", "IMPORT-FIRST", "DETERMINISTIC", "BOUNDED EXP-03"])

    presets = synthetic_preset_names_for_ui()
    preset_name = st.selectbox("Duplicate preset", presets, index=0)
    preset = preset_config_for_ui(preset_name)

    with st.form("synthetic_scenario_builder"):
        section_header("General")
        cols = st.columns(3)
        scenario_id = cols[0].text_input("Scenario ID", value=preset.scenario_id)
        name = cols[1].text_input("Scenario name", value=preset.name)
        random_seed = cols[2].number_input(
            "Random seed",
            min_value=0,
            value=preset.random_seed,
            step=1,
            help="Fixed seed for deterministic synthetic generation.",
        )
        description = st.text_area("Description", value=preset.description)
        experiment_id = st.text_input("Experiment ID", value=preset.experiment_id)
        baseline_seed_id = st.text_input("Baseline seed ID", value=preset.baseline_seed_id or "")

        section_header("Traffic")
        cols = st.columns(4)
        duration_s = cols[0].number_input("Duration (s)", min_value=1.0, value=preset.duration_s)
        sampling_interval_s = cols[1].number_input(
            "Sampling interval (s)",
            min_value=1.0,
            value=preset.sampling_interval_s,
        )
        vehicle_count = cols[2].number_input(
            "Vehicle count",
            min_value=1,
            value=preset.vehicle_count,
            step=1,
        )
        trip_count = cols[3].number_input(
            "Trip count",
            min_value=0,
            value=preset.trip_count,
            step=1,
        )
        congestion_multiplier = st.slider(
            "Congestion multiplier",
            min_value=0.25,
            max_value=3.0,
            value=float(preset.congestion_multiplier),
            step=0.05,
        )

        section_header("Incident Or Event")
        default_incident = preset.incident_schedule[0] if preset.incident_schedule else None
        incident_enabled = st.checkbox(
            "Add a synthetic incident/event",
            value=default_incident is not None,
            help=(
                "The authored event is preserved in configuration and canonical incident evidence."
            ),
        )
        cols = st.columns(4)
        incident_type = cols[0].text_input(
            "Event type",
            value=default_incident.incident_type if default_incident else "synthetic_incident",
        )
        incident_location = cols[1].text_input(
            "Location",
            value=default_incident.location or "synthetic-corridor-a"
            if default_incident
            else "synthetic-corridor-a",
        )
        incident_severity = cols[2].text_input(
            "Severity",
            value=default_incident.severity or "moderate" if default_incident else "moderate",
        )
        incident_timestamp_s = cols[3].number_input(
            "Start time (s)",
            min_value=0.0,
            value=default_incident.timestamp_s if default_incident else 60.0,
        )
        cols = st.columns(3)
        incident_duration_s = cols[0].number_input(
            "Duration (s)",
            min_value=1.0,
            value=default_incident.duration_s if default_incident else 60.0,
        )
        incident_lanes_closed = cols[1].number_input(
            "Lanes closed",
            min_value=0,
            value=default_incident.lanes_closed or 0 if default_incident else 0,
            step=1,
        )
        incident_demand_multiplier = cols[2].number_input(
            "Event demand multiplier",
            min_value=0.1,
            value=default_incident.demand_multiplier if default_incident else 1.0,
            step=0.1,
        )
        incident_vehicles_involved = st.text_input(
            "Vehicles involved",
            value=(", ".join(default_incident.vehicles_involved) if default_incident else ""),
            help="Optional comma-separated synthetic vehicle references.",
        )

        section_header("Vehicle Tier Mix")
        cols = st.columns(3)
        vehicle_low_share = cols[0].number_input(
            "Low-tier share",
            min_value=0.0,
            max_value=1.0,
            value=float(preset.vehicle_tier_mix["low"]),
        )
        vehicle_medium_share = cols[1].number_input(
            "Medium-tier share",
            min_value=0.0,
            max_value=1.0,
            value=float(preset.vehicle_tier_mix["medium"]),
        )
        vehicle_high_share = cols[2].number_input(
            "High-tier share",
            min_value=0.0,
            max_value=1.0,
            value=float(preset.vehicle_tier_mix["high"]),
        )

        section_header("Tasks")
        cols = st.columns(4)
        task_arrival_rate = cols[0].number_input(
            "Task arrival rate",
            min_value=0.001,
            value=preset.task_arrival_rate,
            step=0.01,
            format="%.3f",
        )
        task_mix_t1 = cols[1].number_input(
            "T1 share",
            min_value=0.0,
            max_value=1.0,
            value=float(preset.task_class_mix[TaskClass.T1]),
        )
        task_mix_t2 = cols[2].number_input(
            "T2 share",
            min_value=0.0,
            max_value=1.0,
            value=float(preset.task_class_mix[TaskClass.T2]),
        )
        task_mix_t3 = cols[3].number_input(
            "T3 share",
            min_value=0.0,
            max_value=1.0,
            value=float(preset.task_class_mix[TaskClass.T3]),
        )

        section_header("Infrastructure")
        cols = st.columns(3)
        rsu_count = cols[0].number_input("RSU count", min_value=1, value=preset.rsu_count, step=1)
        rsu_capacity = cols[1].number_input(
            "RSU capacity",
            min_value=1.0,
            value=preset.rsu_capacity,
        )
        baseline_network_delay_ms = cols[2].number_input(
            "Baseline latency (ms)",
            min_value=0.0,
            value=preset.baseline_network_delay_ms,
        )

        section_header("Measurement Noise And Dropout (EXP-03)")
        st.caption(
            "Optional deterministic bounded-uniform measurement imperfections. These are "
            "synthetic robustness inputs, not calibrated sensor behavior."
        )
        default_measurement = preset.measurement_imperfections
        measurement_imperfections_enabled = st.checkbox(
            "Enable synthetic measurement imperfections",
            value=default_measurement is not None,
        )
        cols = st.columns(3)
        measurement_random_seed = cols[0].number_input(
            "Measurement model seed",
            min_value=0,
            max_value=2_147_483_647,
            value=default_measurement.random_seed if default_measurement else 17,
            step=1,
        )
        vehicle_position_max_error_m = cols[1].number_input(
            "Vehicle position max error (m)",
            min_value=0.0,
            max_value=100.0,
            value=default_measurement.vehicle_position_max_error_m if default_measurement else 0.0,
        )
        vehicle_speed_max_error_mps = cols[2].number_input(
            "Vehicle speed max error (m/s)",
            min_value=0.0,
            max_value=20.0,
            value=default_measurement.vehicle_speed_max_error_mps if default_measurement else 0.0,
        )
        cols = st.columns(4)
        traffic_speed_max_error_mps = cols[0].number_input(
            "Traffic speed max error (m/s)",
            min_value=0.0,
            max_value=20.0,
            value=default_measurement.traffic_speed_max_error_mps if default_measurement else 0.0,
        )
        traffic_count_max_error = cols[1].number_input(
            "Traffic count max error",
            min_value=0,
            max_value=100,
            value=default_measurement.traffic_count_max_error if default_measurement else 0,
            step=1,
        )
        infrastructure_utilisation_max_error = cols[2].number_input(
            "RSU utilisation max error",
            min_value=0.0,
            max_value=0.5,
            value=default_measurement.infrastructure_utilisation_max_error
            if default_measurement
            else 0.0,
            step=0.01,
        )
        infrastructure_queue_max_error = cols[3].number_input(
            "RSU queue max error",
            min_value=0,
            max_value=100,
            value=default_measurement.infrastructure_queue_max_error if default_measurement else 0,
            step=1,
        )
        dropout_defaults = (
            default_measurement.row_dropout_fraction_by_table if default_measurement else {}
        )
        cols = st.columns(3)
        infrastructure_dropout_fraction = cols[0].number_input(
            "Infrastructure row dropout fraction",
            min_value=0.0,
            max_value=0.95,
            value=float(dropout_defaults.get(MeasurementTableKind.INFRA_STATE, 0.0)),
            step=0.05,
        )
        vehicle_dropout_fraction = cols[1].number_input(
            "Vehicle row dropout fraction",
            min_value=0.0,
            max_value=0.95,
            value=float(dropout_defaults.get(MeasurementTableKind.VEHICLE_STATE, 0.0)),
            step=0.05,
        )
        traffic_dropout_fraction = cols[2].number_input(
            "Traffic row dropout fraction",
            min_value=0.0,
            max_value=0.95,
            value=float(dropout_defaults.get(MeasurementTableKind.TRAFFIC_OBS, 0.0)),
            step=0.05,
        )

        section_header("Policy And Evidence Files")
        policy_behavior = st.selectbox(
            "Synthetic policy profile",
            synthetic_policy_options_for_ui(),
            index=synthetic_policy_options_for_ui().index(
                (preset.policy_behavior or SyntheticPolicyProfile.BALANCED).value
            ),
            help=(
                "Synthetic profile labels control generated records only; "
                "they are not real algorithms."
            ),
        )
        synthetic_faults = st.text_input(
            "Synthetic fault labels",
            value=", ".join(preset.synthetic_faults),
            help="Comma-separated labels used only for generator provenance and demo expectations.",
        )
        cols = st.columns(5)
        include_infrastructure = cols[0].checkbox(
            "Infrastructure",
            value=preset.include_infrastructure,
        )
        include_vehicles = cols[1].checkbox("Vehicles", value=preset.include_vehicles)
        include_traffic = cols[2].checkbox("Traffic", value=preset.include_traffic)
        include_trips = cols[3].checkbox("Trips", value=preset.include_trips)
        include_incidents = cols[4].checkbox("Incidents", value=preset.include_incidents)

        submitted = st.form_submit_button("Validate Preview")

    form_data = {
        "scenario_id": scenario_id,
        "name": name,
        "description": description,
        "experiment_id": experiment_id,
        "baseline_seed_id": baseline_seed_id,
        "random_seed": random_seed,
        "duration_s": duration_s,
        "sampling_interval_s": sampling_interval_s,
        "vehicle_count": vehicle_count,
        "vehicle_low_share": vehicle_low_share,
        "vehicle_medium_share": vehicle_medium_share,
        "vehicle_high_share": vehicle_high_share,
        "task_arrival_rate": task_arrival_rate,
        "task_mix_t1": task_mix_t1,
        "task_mix_t2": task_mix_t2,
        "task_mix_t3": task_mix_t3,
        "rsu_count": rsu_count,
        "rsu_capacity": rsu_capacity,
        "baseline_network_delay_ms": baseline_network_delay_ms,
        "congestion_multiplier": congestion_multiplier,
        "policy_behavior": policy_behavior,
        "trip_count": trip_count,
        "incident_enabled": incident_enabled,
        "incident_type": incident_type,
        "incident_location": incident_location,
        "incident_severity": incident_severity,
        "incident_timestamp_s": incident_timestamp_s,
        "incident_duration_s": incident_duration_s,
        "incident_lanes_closed": incident_lanes_closed,
        "incident_demand_multiplier": incident_demand_multiplier,
        "incident_vehicles_involved": incident_vehicles_involved,
        "synthetic_faults": synthetic_faults,
        "include_infrastructure": include_infrastructure,
        "include_vehicles": include_vehicles,
        "include_traffic": include_traffic,
        "include_trips": include_trips,
        "include_incidents": include_incidents,
        "measurement_imperfections_enabled": measurement_imperfections_enabled,
        "measurement_random_seed": measurement_random_seed,
        "vehicle_position_max_error_m": vehicle_position_max_error_m,
        "vehicle_speed_max_error_mps": vehicle_speed_max_error_mps,
        "traffic_speed_max_error_mps": traffic_speed_max_error_mps,
        "traffic_count_max_error": traffic_count_max_error,
        "infrastructure_utilisation_max_error": infrastructure_utilisation_max_error,
        "infrastructure_queue_max_error": infrastructure_queue_max_error,
        "infrastructure_dropout_fraction": infrastructure_dropout_fraction,
        "vehicle_dropout_fraction": vehicle_dropout_fraction,
        "traffic_dropout_fraction": traffic_dropout_fraction,
    }
    scenario = build_synthetic_config_from_form(form_data)
    if isinstance(scenario, ServiceError):
        if submitted:
            st.error(scenario.message)
            st.code(scenario.detail or "")
        return

    preview = preview_synthetic_scenario(scenario)
    section_header("Preview", "Expected bundle shape before generation.")
    cols = st.columns(3)
    cols[0].metric("Bundle ID", preview.expected_bundle_id)
    cols[1].metric("Run ID", preview.expected_run_id)
    cols[2].metric("Files", len(preview.expected_files))
    st.dataframe(preview.summary_rows, hide_index=True, width="stretch")
    st.write("Expected files:", ", ".join(preview.expected_files))

    yaml_text = scenario_config_to_yaml(scenario)
    with st.expander("Configuration YAML"):
        st.code(yaml_text, language="yaml")
        st.download_button(
            "Download Scenario Config",
            data=yaml_text,
            file_name=f"{scenario.scenario_id}.yaml",
        )
    if scenario.incident_schedule:
        variant = incident_variant_for_ui(scenario)
        if isinstance(variant, ServiceError):
            st.warning(variant.message)
        else:
            with st.expander("Incident-Seeded What-if Variant"):
                st.caption(
                    "This creates a new seed configuration linked to the current scenario as its "
                    "baseline. It remains synthetic and launches nothing."
                )
                variant_yaml = scenario_config_to_yaml(variant)
                st.code(variant_yaml, language="yaml")
                st.download_button(
                    "Download Incident What-if Variant",
                    data=variant_yaml,
                    file_name=f"{variant.scenario_id}.yaml",
                )

    default_output = (
        config.workspace_path / "bundles" / scenario.scenario_id
        if config.workspace_path is not None
        else Path("generated") / scenario.scenario_id
    )
    output_dir = Path(st.text_input("Output bundle directory", value=str(default_output)))
    overwrite = st.checkbox(
        "Overwrite existing bundle directory",
        value=False,
        help="Only enable for an intentional regeneration of this synthetic output directory.",
    )
    if st.button("Generate And Validate Bundle"):
        generated = generate_synthetic_bundle_for_ui(scenario, output_dir, overwrite=overwrite)
        if isinstance(generated, ServiceError):
            st.error(generated.message)
            st.code(generated.detail or "")
        else:
            status = generated.analysis.validation.report.status.value
            st.success(f"Generated {generated.bundle_path} ({status})")
            manifest = generated.analysis.validation.manifest
            audit = manifest.synthetic_measurement_impairment if manifest is not None else None
            if audit is not None:
                st.caption(
                    "EXP-03 audit "
                    f"{audit.audit_fingerprint[:12]} · "
                    f"{len(audit.field_audits)} noisy fields · "
                    f"{sum(item.rows_dropped for item in audit.dropout_audits)} dropped rows"
                )
            st.session_state["selected_bundle_path"] = str(generated.bundle_path)
