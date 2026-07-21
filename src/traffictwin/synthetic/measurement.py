"""Deterministic EXP-03 measurement noise and observation dropout."""

from __future__ import annotations

import math
from dataclasses import dataclass

from traffictwin.domain.measurement import (
    MeasurementDropoutAudit,
    MeasurementFieldAudit,
    MeasurementTableKind,
    SyntheticMeasurementImpairmentAudit,
    SyntheticMeasurementImpairmentConfig,
    build_measurement_impairment_audit,
    stable_measurement_fingerprint,
)


@dataclass(frozen=True)
class _FloatNoiseSpec:
    table_kind: MeasurementTableKind
    field: str
    unit: str
    maximum: float
    clamp_minimum: float | None = None
    clamp_maximum: float | None = None


@dataclass(frozen=True)
class _IntegerNoiseSpec:
    table_kind: MeasurementTableKind
    field: str
    unit: str
    maximum: int
    clamp_minimum: int = 0


def apply_measurement_imperfections(
    rows: dict[str, list[dict[str, object | None]]],
    configuration: SyntheticMeasurementImpairmentConfig,
) -> tuple[
    dict[str, list[dict[str, object | None]]],
    SyntheticMeasurementImpairmentAudit,
]:
    """Apply one closed deterministic measurement model to copied generated rows."""

    output: dict[str, list[dict[str, object | None]]] = {
        kind: [dict(row) for row in table_rows] for kind, table_rows in rows.items()
    }
    original_indices = {
        kind: list(range(1, len(table_rows) + 1)) for kind, table_rows in output.items()
    }
    dropout_audits: list[MeasurementDropoutAudit] = []
    for table_kind in MeasurementTableKind:
        fraction = configuration.row_dropout_fraction_by_table.get(table_kind, 0.0)
        if fraction <= 0.0:
            continue
        table_name = table_kind.value
        table_rows = output.get(table_name, [])
        retained, retained_indices, dropout_audit = _drop_rows(
            table_rows,
            original_indices.get(table_name, []),
            table_kind,
            fraction,
            configuration.random_seed,
        )
        output[table_name] = retained
        original_indices[table_name] = retained_indices
        dropout_audits.append(dropout_audit)

    noise_reference = {
        kind: [dict(row) for row in table_rows] for kind, table_rows in output.items()
    }
    field_audits: list[MeasurementFieldAudit] = []
    for float_spec in _float_specs(configuration):
        if float_spec.maximum <= 0:
            continue
        field_audits.append(
            _apply_float_noise(
                output.get(float_spec.table_kind.value, []),
                noise_reference.get(float_spec.table_kind.value, []),
                original_indices.get(float_spec.table_kind.value, []),
                float_spec,
                configuration.random_seed,
            )
        )
    for integer_spec in _integer_specs(configuration):
        if integer_spec.maximum <= 0:
            continue
        field_audits.append(
            _apply_integer_noise(
                output.get(integer_spec.table_kind.value, []),
                noise_reference.get(integer_spec.table_kind.value, []),
                original_indices.get(integer_spec.table_kind.value, []),
                integer_spec,
                configuration.random_seed,
            )
        )
    final_audit = build_measurement_impairment_audit(
        configuration,
        field_audits,
        dropout_audits,
    )
    return output, final_audit


def _drop_rows(
    rows: list[dict[str, object | None]],
    original_indices: list[int],
    table_kind: MeasurementTableKind,
    fraction: float,
    random_seed: int,
) -> tuple[
    list[dict[str, object | None]],
    list[int],
    MeasurementDropoutAudit,
]:
    if not rows:
        selected: set[int] = set()
    else:
        requested = max(1, math.floor(len(rows) * fraction))
        count = min(max(0, len(rows) - 1), requested)
        ranked = sorted(
            range(len(rows)),
            key=lambda index: _selection_score(
                random_seed,
                table_kind,
                original_indices[index],
                rows[index],
            ),
        )
        selected = set(ranked[:count])
    retained = [row for index, row in enumerate(rows) if index not in selected]
    retained_indices = [
        row_index for index, row_index in enumerate(original_indices) if index not in selected
    ]
    dropped_indices = sorted(original_indices[index] for index in selected)
    audit = MeasurementDropoutAudit(
        table_kind=table_kind,
        requested_fraction=fraction,
        rows_before=len(rows),
        rows_dropped=len(selected),
        rows_retained=len(retained),
        selection_fingerprint=stable_measurement_fingerprint(
            {
                "method": "exact_seeded_sha256_generated_row_dropout_v1",
                "random_seed": random_seed,
                "table_kind": table_kind.value,
                "dropped_generated_rows": dropped_indices,
            }
        ),
    )
    return retained, retained_indices, audit


def _apply_float_noise(
    rows: list[dict[str, object | None]],
    reference_rows: list[dict[str, object | None]],
    original_indices: list[int],
    spec: _FloatNoiseSpec,
    random_seed: int,
) -> MeasurementFieldAudit:
    errors: list[float] = []
    perturbed = 0
    for row, reference_row, original_index in zip(
        rows,
        reference_rows,
        original_indices,
        strict=True,
    ):
        raw_value = row.get(spec.field)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int | float):
            raise ValueError(f"generated {spec.table_kind.value}.{spec.field} must be numeric")
        before = float(raw_value)
        requested_error = _bounded_uniform_error(
            random_seed,
            spec.table_kind,
            spec.field,
            original_index,
            reference_row,
            spec.maximum,
        )
        after = before + requested_error
        if spec.clamp_minimum is not None:
            after = max(spec.clamp_minimum, after)
        if spec.clamp_maximum is not None:
            after = min(spec.clamp_maximum, after)
        after = round(after, 6)
        applied = round(after - before, 6)
        row[spec.field] = after
        errors.append(applied)
        if applied != 0.0:
            perturbed += 1
    return MeasurementFieldAudit(
        table_kind=spec.table_kind,
        field=spec.field,
        unit=spec.unit,
        maximum_absolute_error=spec.maximum,
        eligible_rows=len(errors),
        perturbed_rows=perturbed,
        minimum_applied_error=min(errors) if errors else None,
        maximum_applied_error=max(errors) if errors else None,
        clamp_minimum=spec.clamp_minimum,
        clamp_maximum=spec.clamp_maximum,
    )


def _apply_integer_noise(
    rows: list[dict[str, object | None]],
    reference_rows: list[dict[str, object | None]],
    original_indices: list[int],
    spec: _IntegerNoiseSpec,
    random_seed: int,
) -> MeasurementFieldAudit:
    errors: list[int] = []
    perturbed = 0
    for row, reference_row, original_index in zip(
        rows,
        reference_rows,
        original_indices,
        strict=True,
    ):
        raw_value = row.get(spec.field)
        if raw_value is None:
            continue
        if not isinstance(raw_value, int | float):
            raise ValueError(f"generated {spec.table_kind.value}.{spec.field} must be numeric")
        before = int(raw_value)
        requested_error = _bounded_integer_error(
            random_seed,
            spec.table_kind,
            spec.field,
            original_index,
            reference_row,
            spec.maximum,
        )
        after = max(spec.clamp_minimum, before + requested_error)
        applied = after - before
        row[spec.field] = after
        errors.append(applied)
        if applied != 0:
            perturbed += 1
    return MeasurementFieldAudit(
        table_kind=spec.table_kind,
        field=spec.field,
        unit=spec.unit,
        maximum_absolute_error=float(spec.maximum),
        eligible_rows=len(errors),
        perturbed_rows=perturbed,
        minimum_applied_error=float(min(errors)) if errors else None,
        maximum_applied_error=float(max(errors)) if errors else None,
        clamp_minimum=float(spec.clamp_minimum),
    )


def _float_specs(
    config: SyntheticMeasurementImpairmentConfig,
) -> list[_FloatNoiseSpec]:
    return [
        _FloatNoiseSpec(
            MeasurementTableKind.VEHICLE_STATE,
            "x",
            "m",
            config.vehicle_position_max_error_m,
        ),
        _FloatNoiseSpec(
            MeasurementTableKind.VEHICLE_STATE,
            "y",
            "m",
            config.vehicle_position_max_error_m,
        ),
        _FloatNoiseSpec(
            MeasurementTableKind.VEHICLE_STATE,
            "speed",
            "m/s",
            config.vehicle_speed_max_error_mps,
            clamp_minimum=0.0,
        ),
        _FloatNoiseSpec(
            MeasurementTableKind.TRAFFIC_OBS,
            "average_speed",
            "m/s",
            config.traffic_speed_max_error_mps,
            clamp_minimum=0.0,
        ),
        _FloatNoiseSpec(
            MeasurementTableKind.INFRA_STATE,
            "utilisation",
            "fraction",
            config.infrastructure_utilisation_max_error,
            clamp_minimum=0.0,
            clamp_maximum=1.0,
        ),
    ]


def _integer_specs(
    config: SyntheticMeasurementImpairmentConfig,
) -> list[_IntegerNoiseSpec]:
    return [
        _IntegerNoiseSpec(
            MeasurementTableKind.TRAFFIC_OBS,
            "count",
            "count",
            config.traffic_count_max_error,
        ),
        _IntegerNoiseSpec(
            MeasurementTableKind.INFRA_STATE,
            "queue_length",
            "count",
            config.infrastructure_queue_max_error,
        ),
    ]


def _selection_score(
    random_seed: int,
    table_kind: MeasurementTableKind,
    original_index: int,
    row: dict[str, object | None],
) -> str:
    return stable_measurement_fingerprint(
        {
            "method": "seeded_sha256_generated_row_order_v1",
            "random_seed": random_seed,
            "table_kind": table_kind.value,
            "generated_row": original_index,
            "row": row,
        }
    )


def _bounded_uniform_error(
    random_seed: int,
    table_kind: MeasurementTableKind,
    field: str,
    original_index: int,
    row: dict[str, object | None],
    maximum: float,
) -> float:
    digest = stable_measurement_fingerprint(
        {
            "method": "bounded_uniform_sha256_v1",
            "random_seed": random_seed,
            "table_kind": table_kind.value,
            "field": field,
            "generated_row": original_index,
            "row": row,
        }
    )
    fraction = int(digest[:16], 16) / ((1 << 64) - 1)
    return round((2.0 * fraction - 1.0) * maximum, 6)


def _bounded_integer_error(
    random_seed: int,
    table_kind: MeasurementTableKind,
    field: str,
    original_index: int,
    row: dict[str, object | None],
    maximum: int,
) -> int:
    digest = stable_measurement_fingerprint(
        {
            "method": "bounded_integer_sha256_v1",
            "random_seed": random_seed,
            "table_kind": table_kind.value,
            "field": field,
            "generated_row": original_index,
            "row": row,
        }
    )
    return int(digest[:16], 16) % (2 * maximum + 1) - maximum


def measurement_bundle_suffix(
    configuration: SyntheticMeasurementImpairmentConfig | None,
) -> str:
    """Return the stable optional bundle/run ID suffix for an impairment config."""

    return "" if configuration is None else f"-imp-{configuration.fingerprint()[:12]}"
