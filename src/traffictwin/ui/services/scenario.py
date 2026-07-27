"""Synthetic scenario, parameter sweep, mutation, and seed services."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from traffictwin.config.seed_io import SeedIOError, dump_seed, load_seed
from traffictwin.domain.enums import (
    Decision,
    FleetTierMix,
    RsuCapacityMode,
    TaskClass,
    WorkloadOrdering,
)
from traffictwin.domain.measurement import (
    MeasurementImpairmentContract,
    MeasurementTableKind,
    SyntheticMeasurementImpairmentConfig,
    measurement_impairment_contract,
)
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.parameter_sweep import (
    ParameterSweepMode,
    ParameterSweepRequest,
    ParameterSweepResult,
    SweepAxis,
    SweepParameter,
    execute_parameter_sweep,
    expand_parameter_sweep,
    parameter_sweep_contract,
    parameter_sweep_response_to_csv,
)
from traffictwin.experiments.scenario_mutation import (
    MutationOperator,
    MutationSpec,
    MutationTableKind,
    RowDropoutMutation,
    RsuRemovalMutation,
    ScenarioMutationRequest,
    ScenarioMutationResult,
    TimestampJitterMutation,
    execute_scenario_mutation,
    plan_scenario_mutation,
    scenario_mutation_contract,
)
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.results import JsonScalar
from traffictwin.storage.registry import (
    Registry,
)
from traffictwin.synthetic.bundles import (
    synthetic_bundle_id,
    synthetic_run_id,
    write_synthetic_bundle,
)
from traffictwin.synthetic.config import (
    SyntheticPolicyProfile,
    SyntheticScenarioConfig,
    synthetic_scenario_config_to_yaml,
)
from traffictwin.synthetic.scenarios import (
    incident_variant_config,
    list_preset_names,
    preset_config,
)
from traffictwin.ui.services._common import _split_csv
from traffictwin.ui.services.bundles import validate_bundle_for_ui
from traffictwin.ui.services.models import (
    ParameterSweepUiCatalog,
    ScenarioGenerationResult,
    ScenarioMutationUiCatalog,
    ScenarioPreview,
    ServiceError,
)


def synthetic_preset_names_for_ui() -> list[str]:
    """Return synthetic presets available to the Scenario Builder."""

    return list_preset_names()


def synthetic_policy_options_for_ui() -> list[str]:
    """Return documented synthetic policy labels."""

    return [profile.value for profile in SyntheticPolicyProfile]


def preset_config_for_ui(name: str, *, random_seed: int = 7) -> SyntheticScenarioConfig:
    """Return a preset config for UI editing."""

    return preset_config(name, random_seed=random_seed)


def build_synthetic_config_from_form(
    data: dict[str, object],
) -> SyntheticScenarioConfig | ServiceError:
    """Validate Scenario Builder form data with the generator config model."""

    try:
        config = SyntheticScenarioConfig.model_validate(
            {
                "scenario_id": str(data["scenario_id"]),
                "name": str(data["name"]),
                "description": str(data["description"]),
                "experiment_id": str(data.get("experiment_id") or "exp-standalone-demo"),
                "baseline_seed_id": str(data.get("baseline_seed_id") or "") or None,
                "random_seed": _as_int(data["random_seed"]),
                "duration_s": _as_float(data["duration_s"]),
                "sampling_interval_s": _as_float(data["sampling_interval_s"]),
                "vehicle_count": _as_int(data["vehicle_count"]),
                "vehicle_tier_mix": {
                    "low": _as_float(data["vehicle_low_share"]),
                    "medium": _as_float(data["vehicle_medium_share"]),
                    "high": _as_float(data["vehicle_high_share"]),
                },
                "task_arrival_rate": _as_float(data["task_arrival_rate"]),
                "task_class_mix": {
                    TaskClass.T1.value: _as_float(data["task_mix_t1"]),
                    TaskClass.T2.value: _as_float(data["task_mix_t2"]),
                    TaskClass.T3.value: _as_float(data["task_mix_t3"]),
                },
                "rsu_count": _as_int(data["rsu_count"]),
                "rsu_capacity": _as_float(data["rsu_capacity"]),
                "baseline_network_delay_ms": _as_float(data["baseline_network_delay_ms"]),
                "congestion_multiplier": _as_float(data["congestion_multiplier"]),
                "policy_behavior": str(data["policy_behavior"]),
                "trip_count": _as_int(data["trip_count"]),
                "incident_schedule": (
                    [
                        {
                            "timestamp_s": _as_float(data.get("incident_timestamp_s", 0.0)),
                            "incident_type": str(data.get("incident_type") or "synthetic_incident"),
                            "location": str(data.get("incident_location") or "") or None,
                            "severity": str(data.get("incident_severity") or "") or None,
                            "duration_s": _as_float(data.get("incident_duration_s", 60.0)),
                            "lanes_closed": (
                                _as_int(data["incident_lanes_closed"])
                                if data.get("incident_lanes_closed") is not None
                                else None
                            ),
                            "demand_multiplier": _as_float(
                                data.get("incident_demand_multiplier", 1.0)
                            ),
                            "vehicles_involved": _split_csv(
                                str(data.get("incident_vehicles_involved", ""))
                            ),
                        }
                    ]
                    if bool(data.get("incident_enabled", False))
                    else []
                ),
                "synthetic_faults": _split_csv(str(data.get("synthetic_faults", ""))),
                "include_infrastructure": bool(data.get("include_infrastructure", True)),
                "include_vehicles": bool(data.get("include_vehicles", True)),
                "include_traffic": bool(data.get("include_traffic", True)),
                "include_trips": bool(data.get("include_trips", True)),
                "include_incidents": bool(data.get("include_incidents", True)),
                "measurement_imperfections": _measurement_config_from_form(data),
            }
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return ServiceError("Synthetic scenario configuration is invalid.", str(exc))
    return config


def _measurement_config_from_form(
    data: dict[str, object],
) -> SyntheticMeasurementImpairmentConfig | None:
    if not bool(data.get("measurement_imperfections_enabled", False)):
        return None
    dropout_values = {
        MeasurementTableKind.INFRA_STATE: _as_float(
            data.get("infrastructure_dropout_fraction", 0.0)
        ),
        MeasurementTableKind.VEHICLE_STATE: _as_float(data.get("vehicle_dropout_fraction", 0.0)),
        MeasurementTableKind.TRAFFIC_OBS: _as_float(data.get("traffic_dropout_fraction", 0.0)),
    }
    return SyntheticMeasurementImpairmentConfig(
        random_seed=_as_int(data.get("measurement_random_seed", 17)),
        vehicle_position_max_error_m=_as_float(data.get("vehicle_position_max_error_m", 0.0)),
        vehicle_speed_max_error_mps=_as_float(data.get("vehicle_speed_max_error_mps", 0.0)),
        traffic_speed_max_error_mps=_as_float(data.get("traffic_speed_max_error_mps", 0.0)),
        traffic_count_max_error=_as_int(data.get("traffic_count_max_error", 0)),
        infrastructure_utilisation_max_error=_as_float(
            data.get("infrastructure_utilisation_max_error", 0.0)
        ),
        infrastructure_queue_max_error=_as_int(data.get("infrastructure_queue_max_error", 0)),
        row_dropout_fraction_by_table={
            table: fraction for table, fraction in dropout_values.items() if fraction > 0.0
        },
    )


def scenario_config_to_yaml(config: SyntheticScenarioConfig) -> str:
    """Return deterministic YAML for a synthetic generator configuration."""

    return synthetic_scenario_config_to_yaml(config)


def incident_variant_for_ui(
    config: SyntheticScenarioConfig,
) -> SyntheticScenarioConfig | ServiceError:
    """Create an explicit synthetic what-if variation from the authored incident."""

    try:
        return incident_variant_config(config)
    except ValueError as exc:
        return ServiceError("Incident what-if variant could not be created.", str(exc))


def preview_synthetic_scenario(config: SyntheticScenarioConfig) -> ScenarioPreview:
    """Return a file and metadata preview without writing a bundle."""

    expected_files = ["manifest.yaml", "seed.yaml", "tasks.csv"]
    if config.include_infrastructure:
        expected_files.append("infra_state.csv")
    if config.include_vehicles:
        expected_files.append("vehicle_state.csv")
    if config.include_traffic:
        expected_files.append("traffic_obs.csv")
    if config.include_trips:
        expected_files.append("trips.csv")
    if config.include_incidents:
        expected_files.append("incidents.csv")
    summary: list[dict[str, object]] = [
        {"field": "scenario_id", "value": config.scenario_id},
        {"field": "random_seed", "value": config.random_seed},
        {"field": "policy_profile", "value": config.policy_behavior.value},
        {"field": "vehicle_count", "value": config.vehicle_count},
        {"field": "task_arrival_rate", "value": config.task_arrival_rate},
        {"field": "rsu_count", "value": config.rsu_count},
        {"field": "rsu_capacity", "value": config.rsu_capacity},
        {"field": "incident_count", "value": len(config.incident_schedule)},
        {"field": "synthetic_faults", "value": ", ".join(config.synthetic_faults) or "none"},
        {
            "field": "measurement_imperfections",
            "value": (
                config.measurement_imperfections.fingerprint()
                if config.measurement_imperfections is not None
                else "disabled"
            ),
        },
    ]
    return ScenarioPreview(
        config=config,
        expected_bundle_id=synthetic_bundle_id(config),
        expected_run_id=synthetic_run_id(config),
        expected_files=expected_files,
        summary_rows=summary,
    )


def generate_synthetic_bundle_for_ui(
    config: SyntheticScenarioConfig,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ScenarioGenerationResult | ServiceError:
    """Generate a synthetic bundle and validate it through Phase 2 services."""

    try:
        bundle_path = write_synthetic_bundle(config, output_dir, overwrite=overwrite)
        analysis = validate_bundle_for_ui(bundle_path)
    except Exception as exc:
        return ServiceError("Synthetic bundle could not be generated.", str(exc))
    return ScenarioGenerationResult(bundle_path=bundle_path, analysis=analysis)


def measurement_impairment_contract_for_ui() -> MeasurementImpairmentContract:
    """Return the typed EXP-03 contract for thin UI rendering."""

    return measurement_impairment_contract()


def parameter_sweep_catalog_for_ui() -> ParameterSweepUiCatalog:
    """Return the public EXP-01 inputs without defining UI-only capabilities."""

    contract = parameter_sweep_contract()
    return ParameterSweepUiCatalog(
        preset_names=list_preset_names(),
        modes=contract.supported_modes,
        parameter_paths=contract.synthetic_parameter_paths,
        metric_keys=sorted(metric_catalogue()),
        max_axes=contract.max_axes,
        max_points=contract.max_points,
    )


def prepare_parameter_sweep_for_ui(
    *,
    sweep_id: str,
    title: str,
    description: str,
    mode: str,
    preset_name: str,
    axes: list[tuple[str, str]],
    metric_keys: list[str],
) -> ParameterSweepRequest | ServiceError:
    """Parse bounded form values and validate every grid point in the library layer."""

    try:
        parsed_axes = [
            SweepAxis(
                parameter_path=SweepParameter(path),
                values=_parse_sweep_values(values),
            )
            for path, values in axes
            if path and values.strip()
        ]
        request = ParameterSweepRequest(
            sweep_id=sweep_id.strip(),
            title=title.strip(),
            description=description.strip(),
            mode=ParameterSweepMode(mode),
            base_synthetic_config=preset_config(preset_name),
            axes=parsed_axes,
            metric_keys=(
                metric_keys if mode == ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES.value else []
            ),
        )
        expand_parameter_sweep(request)
    except (TypeError, ValueError) as exc:
        return ServiceError("The parameter sweep is invalid.", str(exc))
    return request


def execute_parameter_sweep_for_ui(
    request: ParameterSweepRequest,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ParameterSweepResult | ServiceError:
    """Materialise one already validated request through the EXP-01 service."""

    try:
        return execute_parameter_sweep(request, output_dir, overwrite=overwrite)
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        return ServiceError("The parameter sweep could not be materialised.", str(exc))


def parameter_sweep_result_json_for_ui(result: ParameterSweepResult) -> str:
    """Return the typed sweep result as JSON."""

    return result.model_dump_json(indent=2, by_alias=True) + "\n"


def parameter_sweep_response_csv_for_ui(result: ParameterSweepResult) -> str:
    """Return the library-produced response surface as CSV."""

    return parameter_sweep_response_to_csv(result)


def scenario_mutation_catalog_for_ui() -> ScenarioMutationUiCatalog:
    """Return the public EXP-02 inputs without defining UI-only mutation semantics."""

    contract = scenario_mutation_contract()
    return ScenarioMutationUiCatalog(
        operators=contract.supported_operators,
        table_kinds=contract.supported_tables,
        max_changed_rows=contract.max_changed_rows,
        max_absolute_jitter_s=contract.max_absolute_jitter_s,
    )


def prepare_scenario_mutation_for_ui(
    *,
    parent_bundle: str | Path,
    mutation_id: str,
    title: str,
    description: str,
    operator: str,
    table_kind: str,
    drop_fraction: float,
    max_absolute_jitter_s: float,
    rsu_id: str,
    random_seed: int,
) -> ScenarioMutationRequest | ServiceError:
    """Build and fully plan one closed EXP-02 request through the library layer."""

    try:
        selected_operator = MutationOperator(operator)
        mutation: MutationSpec
        if selected_operator is MutationOperator.ROW_DROPOUT:
            mutation = RowDropoutMutation(
                table_kind=MutationTableKind(table_kind),
                drop_fraction=drop_fraction,
                random_seed=random_seed,
            )
        elif selected_operator is MutationOperator.TIMESTAMP_JITTER:
            mutation = TimestampJitterMutation(
                table_kind=MutationTableKind(table_kind),
                max_absolute_jitter_s=max_absolute_jitter_s,
                random_seed=random_seed,
            )
        else:
            mutation = RsuRemovalMutation(rsu_id=rsu_id.strip())
        request = ScenarioMutationRequest(
            mutation_id=mutation_id.strip(),
            title=title.strip(),
            description=description.strip(),
            mutation=mutation,
        )
        plan_scenario_mutation(parent_bundle, request)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return ServiceError("The scenario mutation is invalid.", str(exc))
    return request


def execute_scenario_mutation_for_ui(
    parent_bundle: str | Path,
    request: ScenarioMutationRequest,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ScenarioMutationResult | ServiceError:
    """Materialise one planned EXP-02 request through the typed library service."""

    try:
        return execute_scenario_mutation(
            parent_bundle,
            request,
            output_dir,
            overwrite=overwrite,
        )
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        return ServiceError("The scenario mutation could not be materialised.", str(exc))


def scenario_mutation_result_json_for_ui(result: ScenarioMutationResult) -> str:
    """Return the typed mutation manifest as JSON."""

    return result.model_dump_json(indent=2) + "\n"


def export_seed_for_ui(seed: ScenarioSeed) -> str:
    """Serialise a seed through the Phase 1 seed I/O layer."""

    return dump_seed(seed)


def load_seed_for_ui(path: str | Path) -> ScenarioSeed | ServiceError:
    """Load a seed for the Scenario Studio."""

    try:
        return load_seed(path)
    except SeedIOError as exc:
        return ServiceError("Seed could not be loaded.", str(exc))


def build_seed_from_form(data: dict[str, object]) -> ScenarioSeed | ServiceError:
    """Validate a scenario seed draft from form data."""

    try:
        seed = ScenarioSeed.model_validate(
            {
                "id": str(data["seed_id"]),
                "name": str(data["name"]),
                "description": str(data["description"]),
                "base": str(data["parent_seed_id"]) or None,
                "preset_id": str(data["preset_id"]) or None,
                "demand": {"multiplier": _as_float(data["demand_multiplier"])},
                "workload": {
                    "birth_rate_multiplier": _as_float(data["birth_rate_multiplier"]),
                    "class_mix": {
                        TaskClass.T1.value: _as_float(data["class_mix_t1"]),
                        TaskClass.T2.value: _as_float(data["class_mix_t2"]),
                        TaskClass.T3.value: _as_float(data["class_mix_t3"]),
                    },
                    "ordering": WorkloadOrdering(str(data["workload_ordering"])).value,
                },
                "fleet": {
                    "count": _optional_int(data["fleet_count"]),
                    "tier_mix": FleetTierMix(str(data["fleet_tier_mix"])).value,
                },
                "infrastructure": {
                    "rsu_count": _optional_int(data["rsu_count"]),
                    "rsu_capacity_mode": RsuCapacityMode(str(data["rsu_capacity_mode"])).value,
                    "failed_rsus": _split_csv(str(data["failed_rsus"])),
                },
                "allowed_decisions": [
                    Decision(value).value for value in _as_str_list(data["allowed_decisions"])
                ],
                "policy": {
                    "algorithm": str(data["algorithm"]),
                    "checkpoint": str(data["checkpoint"]) or None,
                },
                "evaluation": {"random_seed": _as_int(data["random_seed"])},
                "compare_against": str(data["compare_against"]) or None,
                "provenance": {
                    "created_by": str(data["created_by"]),
                    "source": str(data["source"]),
                },
            }
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return ServiceError("Seed draft is invalid.", str(exc))
    return seed


def default_seed_form_data() -> dict[str, object]:
    """Return default Scenario Studio form values."""

    return {
        "seed_id": "s1-ui-demo",
        "name": "Synthetic UI demo seed",
        "description": "Synthetic seed drafted in TrafficTwin Scenario Studio.",
        "parent_seed_id": "s1-gridlock-baseline",
        "preset_id": "S1",
        "demand_multiplier": 1.0,
        "birth_rate_multiplier": 1.0,
        "class_mix_t1": 0.30,
        "class_mix_t2": 0.30,
        "class_mix_t3": 0.40,
        "workload_ordering": WorkloadOrdering.MIXED.value,
        "fleet_count": "",
        "fleet_tier_mix": FleetTierMix.MIXED.value,
        "rsu_count": 2,
        "rsu_capacity_mode": RsuCapacityMode.STANDARD.value,
        "failed_rsus": "",
        "allowed_decisions": [Decision.LOCAL.value, Decision.V2I.value, Decision.V2V.value],
        "algorithm": "MAPPO",
        "checkpoint": "",
        "random_seed": 7,
        "compare_against": "",
        "created_by": "Abdulla Al Mamun Akash",
        "source": "TrafficTwin Scenario Studio",
    }


def register_seed_for_ui(seed: ScenarioSeed, registry_path: str | Path) -> ServiceError | None:
    """Register a seed in the metadata registry."""

    try:
        Registry(registry_path).add_seed(seed)
    except Exception as exc:
        return ServiceError("Seed could not be registered.", str(exc))
    return None


def _optional_int(value: object) -> int | None:
    if value in {"", None}:
        return None
    return _as_int(value)


def _parse_sweep_values(value: str) -> list[JsonScalar]:
    tokens = _split_csv(value)
    if not tokens:
        raise ValueError("every enabled sweep axis requires at least one value")
    parsed: list[JsonScalar] = []
    for token in tokens:
        try:
            item = yaml.safe_load(token)
        except yaml.YAMLError as exc:
            raise ValueError("sweep values must be comma-separated scalar YAML values") from exc
        if not isinstance(item, str | int | float | bool):
            raise ValueError("sweep values must be non-null scalar YAML values")
        parsed.append(item)
    return parsed


def _as_float(value: object) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return float(str(value))


def _as_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return int(str(value))


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
