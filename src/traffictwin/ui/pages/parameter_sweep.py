"""Bounded deterministic parameter-sweep composer page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.experiments.parameter_sweep import ParameterSweepMode, ParameterSweepResult
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    execute_parameter_sweep_for_ui,
    parameter_sweep_catalog_for_ui,
    parameter_sweep_response_csv_for_ui,
    parameter_sweep_result_json_for_ui,
    prepare_parameter_sweep_for_ui,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render EXP-01 through the typed library service."""

    render_page_header(UiPage.PARAMETER_SWEEP)
    badge_row(["SYNTHETIC EVALUATION", "BOUNDED GRID", "NO DIRECT LAUNCH"])
    st.info(
        "Compose up to four declared axes. Local mode generates labelled TrafficTwin synthetic "
        "bundles and computes ordinary metrics; external-request mode only writes coordination "
        "artifacts with status NOT EXECUTED."
    )
    catalog = parameter_sweep_catalog_for_ui()

    default_output = (
        config.workspace_path / "exports" / "parameter-sweeps" / "sweep-ui"
        if config.workspace_path is not None
        else Path("generated/parameter-sweeps/sweep-ui")
    )
    mode_order = [
        ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES,
        ParameterSweepMode.SEED_SNAPSHOTS,
        ParameterSweepMode.EXTERNAL_RUN_REQUESTS,
    ]
    path_values = [parameter.value for parameter in catalog.parameter_paths]
    default_paths = [
        "synthetic.task_arrival_rate",
        "",
        "",
        "",
    ]
    default_values = ["0.08, 0.12, 0.16", "", "", ""]

    section_header(
        "Sweep Declaration",
        f"Hard limit: {catalog.max_axes} axes and {catalog.max_points} complete grid points.",
    )
    with st.form("parameter-sweep-form"):
        sweep_id = st.text_input("Sweep ID", value="sweep-ui")
        title = st.text_input("Title", value="Synthetic demand response surface")
        description = st.text_area(
            "Purpose",
            value="Inspect deterministic metric responses over declared synthetic parameters.",
        )
        mode = st.selectbox(
            "Materialisation mode",
            [item.value for item in mode_order],
            format_func=_mode_label,
        )
        preset_name = st.selectbox("Base synthetic preset", catalog.preset_names)
        axes: list[tuple[str, str]] = []
        for index in range(catalog.max_axes):
            columns = st.columns([2, 3])
            options = ["", *path_values]
            selected = columns[0].selectbox(
                f"Axis {index + 1}",
                options,
                index=options.index(default_paths[index]),
                format_func=lambda value: value or "Not used",
                key=f"parameter-sweep-axis-{index + 1}",
            )
            values = columns[1].text_input(
                f"Axis {index + 1} values",
                value=default_values[index],
                placeholder="Comma-separated scalar values",
                key=f"parameter-sweep-values-{index + 1}",
                disabled=not selected,
            )
            if selected:
                axes.append((selected, values))
        metric_keys = st.multiselect(
            "Response metrics",
            catalog.metric_keys,
            default=[
                key
                for key in ["task.completion.rate", "infra.utilisation.mean"]
                if key in catalog.metric_keys
            ],
            help="Used only in local synthetic-bundle mode. Non-numeric metrics stay unavailable.",
        )
        output_dir = st.text_input("Output directory", value=str(default_output))
        overwrite = st.checkbox("Replace this exact output directory if it exists", value=False)
        submitted = st.form_submit_button("Build Parameter Sweep", type="primary")

    if submitted:
        request = prepare_parameter_sweep_for_ui(
            sweep_id=sweep_id,
            title=title,
            description=description,
            mode=mode,
            preset_name=preset_name,
            axes=axes,
            metric_keys=metric_keys,
        )
        if isinstance(request, ServiceError):
            st.session_state["latest_parameter_sweep"] = None
            st.error(request.message)
            if request.detail:
                st.caption(request.detail)
        else:
            result = execute_parameter_sweep_for_ui(
                request,
                output_dir.strip(),
                overwrite=overwrite,
            )
            if isinstance(result, ServiceError):
                st.session_state["latest_parameter_sweep"] = None
                st.error(result.message)
                if result.detail:
                    st.caption(result.detail)
            else:
                st.session_state["latest_parameter_sweep"] = result
                st.session_state["latest_parameter_sweep_output"] = output_dir.strip()
                st.success(
                    f"Built {result.point_count} points with status {result.status}. "
                    "All outputs remain labelled synthetic/evaluation evidence."
                )

    result = st.session_state.get("latest_parameter_sweep")
    if isinstance(result, ParameterSweepResult):
        _render_result(result, str(st.session_state.get("latest_parameter_sweep_output", "")))


def _render_result(result: ParameterSweepResult, output_dir: str) -> None:
    section_header("Sweep Result", "Typed point provenance and response-surface artifacts.")
    columns = st.columns(4)
    columns[0].metric("Grid points", result.point_count)
    columns[1].metric("Response rows", result.response_row_count)
    columns[2].metric("Mode", _mode_label(result.mode.value))
    columns[3].metric("Direct launch", "Unsupported")
    st.caption(f"Output: {output_dir}")
    st.dataframe(
        [
            {
                "point_id": point.point_id,
                "sequence": point.sequence,
                **{item.parameter_path.value: item.value for item in point.parameter_provenance},
                "seed_id": point.seed_snapshot.seed_id,
                "bundle_fingerprint": point.bundle_fingerprint or "Unavailable",
                "execution": (
                    point.external_request.execution_status
                    if point.external_request is not None
                    else "local"
                    if point.bundle_fingerprint
                    else "not executed"
                ),
            }
            for point in result.points
        ],
        hide_index=True,
        width="stretch",
    )
    if result.response_surface:
        section_header("Response Surface")
        st.dataframe(
            [
                {
                    "point_id": row.point_id,
                    **{item.parameter_path.value: item.value for item in row.parameter_provenance},
                    "metric_key": row.metric_key,
                    "status": row.metric_status.value,
                    "value": row.response_value,
                    "unit": row.unit,
                    "reason_codes": ", ".join(row.reason_codes),
                }
                for row in result.response_surface
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.warning("No response values were computed in this non-executing mode.")
    for warning in result.warnings:
        st.warning(warning)
    downloads = st.columns(2)
    downloads[0].download_button(
        "Download Sweep JSON",
        data=parameter_sweep_result_json_for_ui(result),
        file_name=f"{result.sweep_id}.json",
        mime="application/json",
        use_container_width=True,
    )
    downloads[1].download_button(
        "Download Response CSV",
        data=parameter_sweep_response_csv_for_ui(result),
        file_name=f"{result.sweep_id}-response.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _mode_label(value: str) -> str:
    return {
        ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES.value: "Local synthetic bundles + metrics",
        ParameterSweepMode.SEED_SNAPSHOTS.value: "Seed snapshots only",
        ParameterSweepMode.EXTERNAL_RUN_REQUESTS.value: "External requests (not executed)",
    }[value]
