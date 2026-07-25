"""Scenario Studio page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.domain.enums import Decision, FleetTierMix, RsuCapacityMode, WorkloadOrdering
from traffictwin.ui.services import (
    ServiceError,
    build_seed_from_form,
    default_seed_form_data,
    export_seed_for_ui,
    load_seed_for_ui,
    register_seed_for_ui,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render Scenario Studio."""

    st.title("Scenario Studio")
    st.caption("Create and export a versioned ScenarioSeed YAML document.")
    manifest = default_export_import_manifest()
    supports = manifest.supports

    st.warning("Direct launch is unavailable for the current environment adapter.")
    st.button(
        "Run",
        disabled=True,
        help="Direct launch is unavailable for the current environment adapter.",
    )

    load_path = Path(
        st.text_input("Load existing seed path", value="examples/seeds/arena_gridlock.yaml")
    )
    if st.button("Load Seed"):
        loaded = load_seed_for_ui(load_path)
        if isinstance(loaded, ServiceError):
            st.error(loaded.message)
            st.write(loaded.detail)
        else:
            st.session_state["active_seed_draft"] = loaded.model_dump(mode="json", by_alias=True)
            st.success(f"Loaded seed {loaded.seed_id}")

    defaults = default_seed_form_data()
    with st.form("scenario_seed_form"):
        seed_id = st.text_input("Seed ID", value=str(defaults["seed_id"]))
        name = st.text_input("Name", value=str(defaults["name"]))
        description = st.text_area("Description", value=str(defaults["description"]))
        parent_seed_id = st.text_input("Parent/base seed", value=str(defaults["parent_seed_id"]))
        preset_id = st.text_input("Base preset", value=str(defaults["preset_id"]))

        demand_multiplier = st.number_input(
            "Demand multiplier",
            min_value=0.01,
            value=1.0,
            disabled=_disabled(supports.task_arrival_multiplier),
            help=_capability_help(supports.task_arrival_multiplier),
        )
        birth_rate_multiplier = st.number_input(
            "Workload birth-rate multiplier",
            min_value=0.01,
            value=1.0,
            disabled=_disabled(supports.task_arrival_multiplier),
            help=_capability_help(supports.task_arrival_multiplier),
        )
        cols = st.columns(3)
        class_mix_t1 = cols[0].number_input("T1 share", min_value=0.0, max_value=1.0, value=0.30)
        class_mix_t2 = cols[1].number_input("T2 share", min_value=0.0, max_value=1.0, value=0.30)
        class_mix_t3 = cols[2].number_input("T3 share", min_value=0.0, max_value=1.0, value=0.40)
        workload_ordering = st.selectbox(
            "Workload ordering",
            [item.value for item in WorkloadOrdering],
            disabled=_disabled(supports.workload_ordering),
            help=_capability_help(supports.workload_ordering),
        )
        fleet_count = st.text_input(
            "Fleet count",
            value=str(defaults["fleet_count"]),
            disabled=_disabled(supports.vehicle_count),
            help=_capability_help(supports.vehicle_count),
        )
        fleet_tier_mix = st.selectbox(
            "Fleet tier mix",
            [item.value for item in FleetTierMix],
            disabled=_disabled(supports.vehicle_tier_mix),
            help=_capability_help(supports.vehicle_tier_mix),
        )
        rsu_count = st.number_input(
            "RSU count",
            min_value=0,
            value=2,
            disabled=_disabled(supports.rsu_count),
            help=_capability_help(supports.rsu_count),
        )
        rsu_capacity_mode = st.selectbox(
            "RSU capacity mode",
            [item.value for item in RsuCapacityMode],
            disabled=_disabled(supports.rsu_capacity),
            help=_capability_help(supports.rsu_capacity),
        )
        failed_rsus = st.text_input(
            "Failed RSUs",
            value=str(defaults["failed_rsus"]),
            disabled=_disabled(supports.rsu_failure),
            help="Comma-separated RSU IDs. " + _capability_help(supports.rsu_failure),
        )
        allowed_decisions = st.multiselect(
            "Allowed decisions",
            [item.value for item in Decision if item is not Decision.UNKNOWN],
            default=[Decision.LOCAL.value, Decision.V2I.value, Decision.V2V.value],
            disabled=_disabled(supports.action_toggles),
            help=_capability_help(supports.action_toggles),
        )
        algorithm = st.text_input("Policy algorithm", value=str(defaults["algorithm"]))
        checkpoint = st.text_input("Checkpoint reference", value=str(defaults["checkpoint"]))
        random_seed = st.number_input("Evaluation random seed", min_value=0, value=7, step=1)
        compare_against = st.text_input(
            "Baseline reference", value=str(defaults["compare_against"])
        )
        created_by = st.text_input("Created by", value=str(defaults["created_by"]))
        source = st.text_input("Source", value=str(defaults["source"]))
        submitted = st.form_submit_button("Validate Seed")

    form_data = {
        "seed_id": seed_id,
        "name": name,
        "description": description,
        "parent_seed_id": parent_seed_id,
        "preset_id": preset_id,
        "demand_multiplier": demand_multiplier,
        "birth_rate_multiplier": birth_rate_multiplier,
        "class_mix_t1": class_mix_t1,
        "class_mix_t2": class_mix_t2,
        "class_mix_t3": class_mix_t3,
        "workload_ordering": workload_ordering,
        "fleet_count": fleet_count,
        "fleet_tier_mix": fleet_tier_mix,
        "rsu_count": rsu_count,
        "rsu_capacity_mode": rsu_capacity_mode,
        "failed_rsus": failed_rsus,
        "allowed_decisions": allowed_decisions,
        "algorithm": algorithm,
        "checkpoint": checkpoint,
        "random_seed": random_seed,
        "compare_against": compare_against,
        "created_by": created_by,
        "source": source,
    }
    seed = build_seed_from_form(form_data)
    if isinstance(seed, ServiceError):
        if submitted:
            st.error(seed.message)
            st.write(seed.detail)
        return

    yaml_text = export_seed_for_ui(seed)
    st.subheader("YAML preview")
    st.code(yaml_text, language="yaml")
    st.download_button("Download Seed YAML", data=yaml_text, file_name=f"{seed.seed_id}.yaml")

    registry_path = Path(str(st.session_state.get("active_registry_path", config.registry_path)))
    if st.button("Register Seed"):
        error = register_seed_for_ui(seed, registry_path)
        if error is None:
            st.success(f"Registered seed {seed.seed_id}")
        else:
            st.error(error.message)
            st.write(error.detail)


def _disabled(value: CapabilitySupport) -> bool:
    return value is not CapabilitySupport.TRUE


def _capability_help(value: CapabilitySupport) -> str:
    if value is CapabilitySupport.TRUE:
        return "Supported by the current adapter."
    if value is CapabilitySupport.FALSE:
        return "Unsupported by the current adapter."
    return "Unknown for the current adapter; disabled until adapter evidence is supplied."
