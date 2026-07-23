"""Adversarial offline tests for the MAN-10 comparison candidate."""

from __future__ import annotations

import json
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.comparison import (
    APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS,
    ComparisonIntervalContent,
    ComparisonLineage,
    ManchesterComparisonError,
    ManchesterComparisonMetricContract,
    ObservedComparisonInterval,
    ObservedSimulationComparison,
    SimulatedComparisonInterval,
    build_observed_comparison_interval,
    build_simulated_comparison_interval,
    compare_observed_and_simulated,
)
from traffictwin.integration.manchester.models import sha256_hex

SNAPSHOT_ID = "synthetic_road-20260722T100000Z-abcdef012345"
PROJECTION_FP = "a" * 64
MAPPING_FP = "b" * 64
CALIBRATION_FP = "c" * 64
NETWORK_FP = "d" * 64
RUN_FP = "e" * 64
SCOPE_FP = "1" * 64
TIME_BASIS_FP = "2" * 64

LINEAGE = ComparisonLineage(
    observed_snapshot_ids=(SNAPSHOT_ID,),
    projection_report_fingerprint=PROJECTION_FP,
    mapping_fingerprint=MAPPING_FP,
    calibration_fingerprint=CALIBRATION_FP,
    network_fingerprint=NETWORK_FP,
    sumo_run_fingerprint=RUN_FP,
)
CONTRACT = ManchesterComparisonMetricContract(
    contract_version="synthetic-dev-1",
    evidence_class="synthetic_development",
    observed_source="synthetic_utc_road",
    scope_label="synthetic_zone",
    scope_fingerprint=SCOPE_FP,
    time_basis_label="utc_day",
    time_basis_fingerprint=TIME_BASIS_FP,
    interval_duration_s=900,
    measure="vehicle_count",
    unit="vehicles_per_interval",
    minimum_observed_coverage=Decimal("0.500"),
    minimum_simulated_coverage=Decimal("0.500"),
)
PRODUCTION_CONTRACT = ManchesterComparisonMetricContract(
    contract_version="production-candidate-1",
    evidence_class="production",
    observed_source="dft_raw_count",
    scope_label="reviewed_zone",
    scope_fingerprint=SCOPE_FP,
    time_basis_label="reviewed_utc",
    time_basis_fingerprint=TIME_BASIS_FP,
    interval_duration_s=900,
    measure="vehicle_count",
    unit="vehicles_per_interval",
    minimum_observed_coverage=Decimal("0.800"),
    minimum_simulated_coverage=Decimal("0.800"),
)


def content(
    value: str,
    *,
    edge: str = "edge:1",
    start: int = 0,
    end: int = 900,
    direction: str = "N",
    vehicle_class: str = "car",
    scope: str = "synthetic_zone",
    scope_fp: str = SCOPE_FP,
    time_basis: str = "utc_day",
    time_basis_fp: str = TIME_BASIS_FP,
    measure: str = "vehicle_count",
    unit: str = "vehicles_per_interval",
) -> ComparisonIntervalContent:
    return ComparisonIntervalContent.model_validate(
        {
            "site_edge_id": edge,
            "interval_start_s": start,
            "interval_end_s": end,
            "direction": direction,
            "vehicle_class": vehicle_class,
            "measure": measure,
            "unit": unit,
            "value": Decimal(value),
            "scope_label": scope,
            "scope_fingerprint": scope_fp,
            "time_basis_label": time_basis,
            "time_basis_fingerprint": time_basis_fp,
        }
    )


def observed(
    value: str,
    *,
    edge: str = "edge:1",
    start: int = 0,
    end: int = 900,
    direction: str = "N",
    vehicle_class: str = "car",
    salt: str = "obs",
    synthetic: bool = True,
    source: str | None = None,
    scope: str | None = None,
    scope_fp: str = SCOPE_FP,
    time_basis: str | None = None,
    time_basis_fp: str = TIME_BASIS_FP,
    measure: str = "vehicle_count",
    unit: str = "vehicles_per_interval",
    projection_fp: str = PROJECTION_FP,
) -> ObservedComparisonInterval:
    selected_source = source or ("synthetic_utc_road" if synthetic else "dft_raw_count")
    selected_scope = scope or ("synthetic_zone" if synthetic else "reviewed_zone")
    selected_time = time_basis or ("utc_day" if synthetic else "reviewed_utc")
    interval = content(
        value,
        edge=edge,
        start=start,
        end=end,
        direction=direction,
        vehicle_class=vehicle_class,
        scope=selected_scope,
        scope_fp=scope_fp,
        time_basis=selected_time,
        time_basis_fp=time_basis_fp,
        measure=measure,
        unit=unit,
    )
    return build_observed_comparison_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(
            f"{salt}-{edge}-{start}-{value}-{selected_source}".encode()
        ),
        synthetic=synthetic,
        source=selected_source,  # type: ignore[arg-type]
        source_snapshot_id=SNAPSHOT_ID,
        projection_report_fingerprint=projection_fp,
        mapping_fingerprint=MAPPING_FP,
    )


def simulated(
    value: str,
    *,
    edge: str = "edge:1",
    start: int = 0,
    end: int = 900,
    direction: str = "N",
    vehicle_class: str = "car",
    salt: str = "sim",
    synthetic: bool = True,
    scope: str | None = None,
    scope_fp: str = SCOPE_FP,
    time_basis: str | None = None,
    time_basis_fp: str = TIME_BASIS_FP,
    measure: str = "vehicle_count",
    unit: str = "vehicles_per_interval",
    run_fp: str = RUN_FP,
) -> SimulatedComparisonInterval:
    selected_scope = scope or ("synthetic_zone" if synthetic else "reviewed_zone")
    selected_time = time_basis or ("utc_day" if synthetic else "reviewed_utc")
    interval = content(
        value,
        edge=edge,
        start=start,
        end=end,
        direction=direction,
        vehicle_class=vehicle_class,
        scope=selected_scope,
        scope_fp=scope_fp,
        time_basis=selected_time,
        time_basis_fp=time_basis_fp,
        measure=measure,
        unit=unit,
    )
    return build_simulated_comparison_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(f"{salt}-{edge}-{start}-{value}".encode()),
        synthetic=synthetic,
        network_fingerprint=NETWORK_FP,
        calibration_fingerprint=CALIBRATION_FP,
        sumo_run_fingerprint=run_fp,
    )


def compare(
    observed_rows: list[ObservedComparisonInterval],
    simulated_rows: list[SimulatedComparisonInterval],
    contract: ManchesterComparisonMetricContract = CONTRACT,
) -> ObservedSimulationComparison:
    return compare_observed_and_simulated(contract, LINEAGE, observed_rows, simulated_rows)


def reasons(result: ObservedSimulationComparison) -> list[tuple[str, str]]:
    return [(item.side, item.reason) for item in result.exclusions]


def test_exact_pair_and_signed_direction() -> None:
    result = compare([observed("10")], [simulated("12")])
    pair = result.pairs[0]
    assert result.paired_intervals == 1
    assert pair.signed_difference == Decimal("2.000")
    assert pair.absolute_difference == Decimal("2.000")
    assert pair.scope_fingerprint == SCOPE_FP
    assert pair.time_basis_fingerprint == TIME_BASIS_FP
    assert result.paired_observed_coverage == Decimal("1.000")
    assert result.paired_simulated_coverage == Decimal("1.000")
    assert result.coverage_requirement_met is True


def test_missing_rows_are_exclusions_never_zero_and_coverage_is_two_sided() -> None:
    result = compare(
        [observed("10"), observed("7", start=900, end=1800)],
        [simulated("12")],
    )
    assert ("observed", "unmatched_no_simulated_counterpart") in reasons(result)
    assert all(item.filled_with_zero is False for item in result.exclusions)
    assert result.paired_observed_coverage == Decimal("0.500")
    assert result.paired_simulated_coverage == Decimal("1.000")
    assert result.observed_input_rows == result.paired_intervals + result.excluded_observed
    assert result.simulated_input_rows == result.paired_intervals + result.excluded_simulated


def test_coverage_below_contract_threshold_keeps_metrics_unavailable() -> None:
    result = compare(
        [
            observed("10"),
            observed("7", start=900, end=1800),
            observed("5", start=1800, end=2700),
        ],
        [simulated("12")],
    )
    assert result.paired_observed_coverage == Decimal("0.333")
    assert result.coverage_requirement_met is False
    assert {metric.reason for metric in result.metrics} == {"coverage_below_contract_minimum"}
    assert all(metric.value is None for metric in result.metrics)


def test_display_rounding_cannot_admit_coverage_below_threshold() -> None:
    contract = ManchesterComparisonMetricContract.model_validate(
        {
            **CONTRACT.model_dump(mode="python"),
            "minimum_observed_coverage": Decimal("0.667"),
        }
    )
    result = compare(
        [
            observed("10"),
            observed("7", start=900, end=1800),
            observed("5", start=1800, end=2700),
        ],
        [simulated("12"), simulated("8", start=900, end=1800)],
        contract,
    )
    assert result.paired_observed_coverage == Decimal("0.667")
    assert result.coverage_requirement_met is False
    assert {metric.reason for metric in result.metrics} == {"coverage_below_contract_minimum"}


def test_numerically_equal_decimal_duplicates_collapse() -> None:
    result = compare(
        [observed("10", salt="one"), observed("10.0", salt="two")],
        [simulated("12")],
    )
    assert result.paired_intervals == 1
    assert reasons(result).count(("observed", "duplicate_identical_row")) == 1


def test_conflicting_duplicate_excludes_every_row_with_key() -> None:
    result = compare(
        [observed("10", salt="one"), observed("11", salt="two")],
        [simulated("12")],
    )
    assert result.paired_intervals == 0
    assert reasons(result).count(("observed", "conflicting_duplicate_rows")) == 2
    assert ("simulated", "unmatched_no_observed_counterpart") in reasons(result)


@pytest.mark.parametrize(
    ("observed_row", "simulated_row", "reason"),
    [
        (
            observed("10", scope="other_scope", scope_fp="3" * 64),
            simulated("12", scope="other_scope", scope_fp="3" * 64),
            "scope_mismatch",
        ),
        (
            observed("10", time_basis="other_time", time_basis_fp="4" * 64),
            simulated("12", time_basis="other_time", time_basis_fp="4" * 64),
            "time_basis_mismatch",
        ),
        (
            observed("10", end=600),
            simulated("12", end=600),
            "interval_duration_mismatch",
        ),
    ],
)
def test_cross_scope_time_basis_and_duration_never_contribute(
    observed_row: ObservedComparisonInterval,
    simulated_row: SimulatedComparisonInterval,
    reason: str,
) -> None:
    result = compare(
        [observed("5"), observed_row],
        [simulated("7"), simulated_row],
    )
    assert result.paired_intervals == 1
    assert reasons(result).count(("observed", reason)) == 1
    assert reasons(result).count(("simulated", reason)) == 1
    assert {pair.scope_fingerprint for pair in result.pairs} == {SCOPE_FP}


def test_cross_source_rows_do_not_enter_one_contract() -> None:
    result = compare(
        [
            observed("10", synthetic=False),
            observed(
                "20",
                start=900,
                end=1800,
                synthetic=False,
                source="webtris_daily",
            ),
        ],
        [
            simulated("12", synthetic=False),
            simulated("24", start=900, end=1800, synthetic=False),
        ],
        PRODUCTION_CONTRACT,
    )
    assert result.paired_intervals == 1
    assert ("observed", "source_mismatch") in reasons(result)
    assert ("simulated", "unmatched_no_observed_counterpart") in reasons(result)
    assert all(metric.reason == "contract_not_admitted" for metric in result.metrics)


def test_dft_raw_count_speed_is_structurally_rejected() -> None:
    interval = content(
        "13.5",
        scope="reviewed_zone",
        time_basis="reviewed_utc",
        measure="average_speed_mps",
        unit="m/s",
    )
    with pytest.raises(ValidationError, match="cannot represent speed"):
        build_observed_comparison_interval(
            interval=interval,
            source_row_fingerprint="3" * 64,
            synthetic=False,
            source="dft_raw_count",
            source_snapshot_id=SNAPSHOT_ID,
            projection_report_fingerprint=PROJECTION_FP,
            mapping_fingerprint=MAPPING_FP,
        )
    with pytest.raises(ValidationError, match="vehicle counts only"):
        ManchesterComparisonMetricContract(
            contract_version="invalid-dft-speed",
            evidence_class="production",
            observed_source="dft_raw_count",
            scope_label="reviewed_zone",
            scope_fingerprint=SCOPE_FP,
            time_basis_label="reviewed_utc",
            time_basis_fingerprint=TIME_BASIS_FP,
            interval_duration_s=900,
            measure="average_speed_mps",
            unit="m/s",
            minimum_observed_coverage=Decimal("1.000"),
            minimum_simulated_coverage=Decimal("1.000"),
        )


def test_direction_class_and_interval_boundaries_do_not_cross_pair() -> None:
    direction = compare([observed("10", direction="N")], [simulated("12", direction="S")])
    vehicle_class = compare(
        [observed("10", vehicle_class="car")],
        [simulated("12", vehicle_class="hgv")],
    )
    boundary = compare([observed("10")], [simulated("12", start=900, end=1800)])
    assert direction.paired_intervals == 0
    assert vehicle_class.paired_intervals == 0
    assert boundary.paired_intervals == 0


def test_measure_mismatch_is_excluded_without_conversion() -> None:
    speed_observed = observed("13.4", measure="average_speed_mps", unit="m/s")
    result = compare([speed_observed], [simulated("12")])
    assert ("observed", "measure_mismatch") in reasons(result)
    assert result.paired_intervals == 0
    assert result.contract.unit_conversion == "none"


def test_non_finite_negative_and_missing_values_are_unrepresentable() -> None:
    for bad in ("NaN", "Infinity", "-Infinity", "-1"):
        with pytest.raises(ValidationError):
            content(bad)
    payload = json.loads(content("10").canonical_json())
    payload["value"] = None
    with pytest.raises(ValidationError):
        ComparisonIntervalContent.model_validate_json(json.dumps(payload))


def test_zero_pairs_keep_metrics_unavailable() -> None:
    result = compare([observed("10")], [simulated("12", start=900, end=1800)])
    assert result.paired_intervals == 0
    assert all(metric.reason == "no_paired_intervals" for metric in result.metrics)


def test_production_contract_fails_closed_and_cannot_self_approve() -> None:
    assert not APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS
    result = compare(
        [observed("10", synthetic=False)],
        [simulated("12", synthetic=False)],
        PRODUCTION_CONTRACT,
    )
    assert result.contract_admitted is False
    assert result.contract_admission == "not_admitted_production_unapproved"
    assert all(metric.reason == "contract_not_admitted" for metric in result.metrics)

    forged = json.loads(result.canonical_json())
    forged["contract_admitted"] = True
    forged["contract_admission"] = "approved_production_contract"
    with pytest.raises(ValidationError):
        ObservedSimulationComparison.model_validate_json(json.dumps(forged))


def test_evidence_class_contract_and_inputs_must_agree() -> None:
    with pytest.raises(ManchesterComparisonError) as production:
        compare([observed("10")], [simulated("12")], PRODUCTION_CONTRACT)
    assert production.value.code == "CONTRACT_EVIDENCE_CLASS_MISMATCH"
    with pytest.raises(ManchesterComparisonError) as synthetic:
        compare([observed("10", synthetic=False)], [simulated("12", synthetic=False)])
    assert synthetic.value.code == "CONTRACT_EVIDENCE_CLASS_MISMATCH"
    with pytest.raises(ManchesterComparisonError) as mixed:
        compare([observed("10")], [simulated("12", synthetic=False)])
    assert mixed.value.code == "MIXED_EVIDENCE"
    with pytest.raises(ManchesterComparisonError) as empty:
        compare([], [])
    assert empty.value.code == "NO_INPUT"


def test_mae_rmse_use_exact_values_then_round_once() -> None:
    result = compare(
        [
            observed("10"),
            observed("5", start=900, end=1800),
            observed("0", start=1800, end=2700),
        ],
        [
            simulated("12"),
            simulated("4", start=900, end=1800),
            simulated("2", start=1800, end=2700),
        ],
    )
    metrics = {metric.metric: metric for metric in result.metrics}
    assert metrics["mae"].value == Decimal("1.667")
    assert metrics["rmse"].value == Decimal("1.732")
    assert [pair.signed_difference for pair in result.pairs] == [
        Decimal("2.000"),
        Decimal("-1.000"),
        Decimal("2.000"),
    ]


def test_ambient_decimal_context_cannot_change_output() -> None:
    observed_rows = [observed("10.1234"), observed("5.9876", start=900, end=1800)]
    simulated_rows = [simulated("12.5678"), simulated("6.1234", start=900, end=1800)]
    baseline = compare(observed_rows, simulated_rows)
    with localcontext() as ambient:
        ambient.prec = 2
        altered = compare(observed_rows, simulated_rows)
    assert altered.canonical_json() == baseline.canonical_json()
    assert altered.fingerprint() == baseline.fingerprint()


def test_input_order_is_canonical_and_invariant() -> None:
    observed_rows = [observed("10"), observed("5", start=900, end=1800)]
    simulated_rows = [simulated("12"), simulated("4", start=900, end=1800)]
    forward = compare(observed_rows, simulated_rows)
    reverse = compare(list(reversed(observed_rows)), list(reversed(simulated_rows)))
    assert forward.canonical_json() == reverse.canonical_json()


def test_canonical_json_round_trip() -> None:
    result = compare([observed("10")], [simulated("12")])
    restored = ObservedSimulationComparison.model_validate_json(result.canonical_json())
    assert restored == result
    assert restored.fingerprint() == result.fingerprint()


def test_coherent_pair_and_metric_rewrite_is_rejected() -> None:
    result = compare([observed("10")], [simulated("12")])
    payload = json.loads(result.canonical_json())
    pair = payload["pairs"][0]
    pair["observed_value"] = "100.000"
    pair["simulated_value"] = "101.000"
    pair["signed_difference"] = "1.000"
    pair["absolute_difference"] = "1.000"
    for metric in payload["metrics"]:
        metric["value"] = "1.000"
    with pytest.raises(ValidationError, match="re-derived"):
        ObservedSimulationComparison.model_validate_json(json.dumps(payload))


def test_synthetic_and_exclusion_reason_relabelling_are_rejected() -> None:
    paired = json.loads(compare([observed("10")], [simulated("12")]).canonical_json())
    paired["synthetic"] = False
    with pytest.raises(ValidationError, match="synthetic"):
        ObservedSimulationComparison.model_validate_json(json.dumps(paired))

    excluded = json.loads(compare([observed("10")], []).canonical_json())
    excluded["exclusions"][0]["reason"] = "measure_mismatch"
    with pytest.raises(ValidationError, match="exclusions"):
        ObservedSimulationComparison.model_validate_json(json.dumps(excluded))


def test_embedded_input_content_and_binding_mutations_are_rejected() -> None:
    payload = json.loads(compare([observed("10")], [simulated("12")]).canonical_json())
    payload["observed_inputs"][0]["interval"]["value"] = "100"
    with pytest.raises(ValidationError, match="interval fingerprint"):
        ObservedSimulationComparison.model_validate_json(json.dumps(payload))

    payload = json.loads(compare([observed("10")], [simulated("12")]).canonical_json())
    changed = ComparisonIntervalContent.model_validate(
        {
            **payload["observed_inputs"][0]["interval"],
            "value": Decimal("100"),
        }
    )
    payload["observed_inputs"][0]["interval"] = json.loads(changed.canonical_json())
    payload["observed_inputs"][0]["interval_fingerprint"] = changed.fingerprint()
    with pytest.raises(ValidationError, match="input binding fingerprint"):
        ObservedSimulationComparison.model_validate_json(json.dumps(payload))


def test_input_inventory_removal_addition_and_reordering_are_rejected() -> None:
    result = compare(
        [observed("10"), observed("5", start=900, end=1800)],
        [simulated("12"), simulated("4", start=900, end=1800)],
    )
    original = json.loads(result.canonical_json())

    removed = json.loads(result.canonical_json())
    removed["observed_inputs"].pop()
    with pytest.raises(ValidationError):
        ObservedSimulationComparison.model_validate_json(json.dumps(removed))

    added = json.loads(result.canonical_json())
    added["observed_inputs"].append(added["observed_inputs"][0])
    with pytest.raises(ValidationError):
        ObservedSimulationComparison.model_validate_json(json.dumps(added))

    original["observed_inputs"].reverse()
    with pytest.raises(ValidationError, match="observed_inputs"):
        ObservedSimulationComparison.model_validate_json(json.dumps(original))


def test_load_bearing_summary_mutations_are_rejected() -> None:
    result = compare([observed("10")], [simulated("12")])
    mutations: list[tuple[str, object]] = [
        ("contract_fingerprint", "0" * 64),
        ("lineage_fingerprint", "0" * 64),
        ("observed_input_set_fingerprint", "0" * 64),
        ("simulated_input_set_fingerprint", "0" * 64),
        ("paired_intervals", 2),
        ("observed_input_rows", 2),
        ("simulated_input_rows", 2),
        ("excluded_observed", 1),
        ("excluded_simulated", 1),
        ("paired_observed_coverage", "0.500"),
        ("paired_simulated_coverage", "0.500"),
        ("coverage_requirement_met", False),
    ]
    for field_name, value in mutations:
        payload = json.loads(result.canonical_json())
        payload[field_name] = value
        with pytest.raises(ValidationError):
            ObservedSimulationComparison.model_validate_json(json.dumps(payload))


def test_speed_contract_golden_value_for_synthetic_source() -> None:
    contract = ManchesterComparisonMetricContract(
        contract_version="synthetic-dev-speed-1",
        evidence_class="synthetic_development",
        observed_source="synthetic_utc_road",
        scope_label="synthetic_zone",
        scope_fingerprint=SCOPE_FP,
        time_basis_label="utc_day",
        time_basis_fingerprint=TIME_BASIS_FP,
        interval_duration_s=900,
        measure="average_speed_mps",
        unit="m/s",
        minimum_observed_coverage=Decimal("1.000"),
        minimum_simulated_coverage=Decimal("1.000"),
    )
    result = compare(
        [observed("13.5", measure="average_speed_mps", unit="m/s")],
        [simulated("12.25", measure="average_speed_mps", unit="m/s")],
        contract,
    )
    assert result.pairs[0].signed_difference == Decimal("-1.250")
    assert {metric.metric: metric.value for metric in result.metrics} == {
        "mae": Decimal("1.250"),
        "rmse": Decimal("1.250"),
    }


def test_no_causal_or_favourability_wording() -> None:
    text = compare([observed("10")], [simulated("12")]).canonical_json().lower()
    for banned in ("better", "accurate", "accuracy", "valid model", "improved", "caused"):
        assert banned not in text
