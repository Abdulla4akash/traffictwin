"""Application state and logical replay clock."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.metrics.engine_config import MetricEngineConfig


class UiConfig(BaseModel):
    """Simple UI configuration."""

    model_config = ConfigDict(extra="forbid")

    registry_path: Path = Path("data/registry/traffictwin.sqlite")
    default_fixture_path: Path = Path("tests/fixtures/bundles")
    workspace_path: Path | None = None
    tos_data_path: Path | None = None
    debug: bool = False
    page_title: str = "TrafficTwin"
    replay_default_speed: float = Field(default=1.0, gt=0)
    default_report_format: str = "markdown"
    preferred_export_directory: Path = Path("exports")
    metric_engine_config: MetricEngineConfig = Field(default_factory=MetricEngineConfig)
    file_upload_size_guidance: str = "Use small ZIP or directory bundles for the Phase 4 prototype."


class ReplayClockState(BaseModel):
    """Framework-independent logical replay clock."""

    model_config = ConfigDict(extra="forbid")

    min_timestamp_s: float = 0.0
    max_timestamp_s: float = 0.0
    current_timestamp_s: float = 0.0
    playback_speed: float = Field(default=1.0, gt=0)
    playing: bool = False

    def reset(self) -> ReplayClockState:
        """Return a reset clock."""

        return self.model_copy(
            update={"current_timestamp_s": self.min_timestamp_s, "playing": False}
        )

    def pause(self) -> ReplayClockState:
        """Return a paused clock."""

        return self.model_copy(update={"playing": False})

    def play(self) -> ReplayClockState:
        """Return a playing clock."""

        return self.model_copy(update={"playing": True})

    def resume(self) -> ReplayClockState:
        """Return a resumed clock."""

        return self.play()

    def step(self, delta_s: float) -> ReplayClockState:
        """Return a clock advanced by a logical delta."""

        next_timestamp = min(
            self.max_timestamp_s,
            max(self.min_timestamp_s, self.current_timestamp_s + delta_s * self.playback_speed),
        )
        return self.model_copy(update={"current_timestamp_s": next_timestamp})

    def scrub(self, timestamp_s: float) -> ReplayClockState:
        """Return a clock set to a bounded timestamp."""

        bounded = min(self.max_timestamp_s, max(self.min_timestamp_s, timestamp_s))
        return self.model_copy(update={"current_timestamp_s": bounded})

    def restart(self) -> ReplayClockState:
        """Return a restarted, playing clock from the first timestamp."""

        return self.model_copy(
            update={"current_timestamp_s": self.min_timestamp_s, "playing": True}
        )


class ReplayFilters(BaseModel):
    """Framework-independent replay filters."""

    model_config = ConfigDict(extra="forbid")

    vehicle_id: str | None = None
    rsu_id: str | None = None
    task_class: str | None = None
    incident_type: str | None = None


DEFAULT_SESSION_STATE: dict[str, object] = {
    "active_registry_path": "data/registry/traffictwin.sqlite",
    "selected_bundle_path": "tests/fixtures/bundles/baseline_valid",
    "selected_run_id": None,
    "selected_baseline_run": "tests/fixtures/bundles/baseline_valid",
    "selected_variation_run": "tests/fixtures/bundles/variation_valid",
    "selected_tos_data_path": "",
    "latest_tos_package_view": None,
    "active_seed_draft": None,
    "latest_validation_report": None,
    "latest_metric_collection": None,
    "latest_evidence_pack": None,
    "threshold_sweep_rule_config": None,
    "threshold_sensitivity_report": None,
    "threshold_sweep_source_config": None,
    "replay_clock": ReplayClockState().model_dump(mode="json"),
    "replay_filters": ReplayFilters().model_dump(mode="json"),
    "display_preferences": {"show_metric_keys": False},
    "data_mode_label": "SYNTHETIC",
    "guided_demo_step": 0,
    "guided_demo_track": "Standalone synthetic",
    "guided_demo_progress": None,
    "latest_experiment_plan": None,
    "latest_registered_experiment_id": None,
    "ui_settings": {
        "theme": "Research",
        "default_replay_speed": 1.0,
        "default_report_format": "markdown",
        "preferred_export_directory": "exports",
        "demo_auto_initialise": True,
    },
}


def load_ui_config() -> UiConfig:
    """Load minimal configuration from environment variables."""

    return UiConfig(
        registry_path=Path(
            os.getenv("TRAFFICTWIN_REGISTRY_PATH", "data/registry/traffictwin.sqlite")
        ),
        default_fixture_path=Path(os.getenv("TRAFFICTWIN_FIXTURE_PATH", "tests/fixtures/bundles")),
        workspace_path=(
            Path(value) if (value := os.getenv("TRAFFICTWIN_WORKSPACE_PATH")) else None
        ),
        tos_data_path=(Path(value) if (value := os.getenv("TRAFFICTWIN_TOS_DATA_PATH")) else None),
        debug=os.getenv("TRAFFICTWIN_DEBUG", "false").lower() in {"1", "true", "yes"},
    )


def default_session_state(config: UiConfig | None = None) -> dict[str, object]:
    """Return session defaults, honouring configured registry and data paths.

    The static fallbacks apply only when no configuration is supplied; a
    configured registry (for example the demo launcher's
    ``TRAFFICTWIN_REGISTRY_PATH``) must seed ``active_registry_path`` so pages
    never silently fall back to ``data/registry/traffictwin.sqlite``.
    """

    defaults = dict(DEFAULT_SESSION_STATE)
    if config is not None:
        defaults["active_registry_path"] = str(config.registry_path)
        if config.tos_data_path is not None:
            defaults["selected_tos_data_path"] = str(config.tos_data_path)
    return defaults


def ensure_session_state(
    state: MutableMapping[str, object],
    config: UiConfig | None = None,
) -> None:
    """Populate missing Streamlit session-state keys without overwriting user choices."""

    for key, value in default_session_state(config).items():
        state.setdefault(key, value)


def replay_clock_from_tables(
    tables: CanonicalTables,
    *,
    speed: float = 1.0,
) -> ReplayClockState:
    """Build replay bounds from canonical timestamps."""

    timestamps = canonical_timestamps(tables)
    if not timestamps:
        return ReplayClockState(playback_speed=speed)
    minimum = min(timestamps)
    maximum = max(timestamps)
    return ReplayClockState(
        min_timestamp_s=minimum,
        max_timestamp_s=maximum,
        current_timestamp_s=minimum,
        playback_speed=speed,
    )


def canonical_timestamps(tables: CanonicalTables) -> list[float]:
    """Return all canonical timestamps relevant to historical replay."""

    values: list[float] = []
    values.extend(task.arrival_time_s for task in tables.tasks)
    values.extend(
        task.completion_time_s for task in tables.tasks if task.completion_time_s is not None
    )
    values.extend(record.timestamp_s for record in tables.infrastructure)
    values.extend(record.timestamp_s for record in tables.vehicles)
    values.extend(record.timestamp_s for record in tables.traffic)
    values.extend(trip.departure_time_s for trip in tables.trips)
    values.extend(trip.arrival_time_s for trip in tables.trips if trip.arrival_time_s is not None)
    values.extend(incident.timestamp_s for incident in tables.incidents)
    return sorted(values)


def replay_window_counts(
    tables: CanonicalTables,
    current_timestamp_s: float,
    *,
    window_s: float = 60.0,
    filters: ReplayFilters | None = None,
) -> dict[str, int]:
    """Return simple counts for records visible in the current replay window."""

    start = max(0.0, current_timestamp_s - window_s)
    active_filters = filters or ReplayFilters()
    return {
        "task_arrivals": sum(
            start <= task.arrival_time_s <= current_timestamp_s
            and _task_matches(task, active_filters)
            for task in tables.tasks
        ),
        "task_completions": sum(
            task.completion_time_s is not None
            and start <= task.completion_time_s <= current_timestamp_s
            and _task_matches(task, active_filters)
            for task in tables.tasks
        ),
        "traffic_observations": sum(
            start <= record.timestamp_s <= current_timestamp_s for record in tables.traffic
        ),
        "infrastructure_observations": sum(
            start <= record.timestamp_s <= current_timestamp_s
            and (active_filters.rsu_id is None or record.rsu_id == active_filters.rsu_id)
            for record in tables.infrastructure
        ),
        "vehicle_observations": sum(
            start <= record.timestamp_s <= current_timestamp_s
            and (
                active_filters.vehicle_id is None or record.vehicle_id == active_filters.vehicle_id
            )
            for record in tables.vehicles
        ),
        "incidents": sum(
            start <= incident.timestamp_s <= current_timestamp_s
            for incident in tables.incidents
            if (
                active_filters.incident_type is None
                or incident.incident_type == active_filters.incident_type
            )
        ),
    }


def replay_filter_options(tables: CanonicalTables) -> dict[str, list[str]]:
    """Return deterministic filter options for replay controls."""

    return {
        "vehicles": sorted({record.vehicle_id for record in tables.vehicles}),
        "rsus": sorted({record.rsu_id for record in tables.infrastructure}),
        "task_classes": sorted({record.task_class.value for record in tables.tasks}),
        "incident_types": sorted({record.incident_type for record in tables.incidents}),
    }


def _task_matches(task: object, filters: ReplayFilters) -> bool:
    task_vehicle = getattr(task, "vehicle_id", None)
    task_class = getattr(getattr(task, "task_class", None), "value", None)
    return (filters.vehicle_id is None or task_vehicle == filters.vehicle_id) and (
        filters.task_class is None or task_class == filters.task_class
    )
