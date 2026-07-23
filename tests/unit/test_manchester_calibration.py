"""Adversarial unit tests for the MAN-09 calibration-candidate evaluator.

Every row below is a clearly labelled synthetic software fixture except the
typed fail-closed production-boundary tests, which use real-shaped fixtures
only to prove refusal. No test reads a clock, touches the network, launches
SUMO, or claims Manchester realism.
"""

from __future__ import annotations

import decimal
import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.calibration import (
    APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS,
    CalibrationCandidateEvaluation,
    CalibrationCandidateInput,
    CalibrationIntervalContent,
    CalibrationMeasure,
    CalibrationParameterBound,
    CalibrationParameterValue,
    CalibrationUnit,
    ManchesterCalibrationContract,
    ManchesterCalibrationError,
    ManchesterCalibrationReport,
    ObservedCalibrationInterval,
    ObservedSource,
    ScopeKind,
    SimulatedCalibrationInterval,
    build_observed_calibration_interval,
    build_simulated_calibration_interval,
    evaluate_calibration_candidates,
)
from traffictwin.integration.manchester.models import sha256_hex

SCOPE_FP = "1" * 64
TIME_FP = "2" * 64
SRC_FP = "3" * 64
PROJ_FP = "4" * 64
MAP_FP = "5" * 64
NET_FP = "6" * 64
RUN_A = "a" * 64
RUN_B = "b" * 64
SNAPSHOT_ID = "synthetic_road-20260722T100000Z-abcdef012345"
REAL_SNAPSHOT_ID = "webtris_daily-20260301T000000Z-abcdef012345"
DFT_SNAPSHOT_ID = "dft_raw-20260722T100000Z-abcdef012345"

PARAM_BOUND = CalibrationParameterBound(
    name="demand_scale",
    unit="ratio",
    lower_bound=Decimal("0.5"),
    upper_bound=Decimal("2.0"),
    permitted_values=(Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), Decimal("2.0")),
)


def make_contract(**overrides: object) -> ManchesterCalibrationContract:
    payload: dict[str, Any] = {
        "contract_version": "synthetic-dev-1",
        "evidence_class": "synthetic_development",
        "observed_source": "synthetic_utc_road",
        "scope_kind": "synthetic_zone",
        "scope_label": "synthetic_zone",
        "scope_fingerprint": SCOPE_FP,
        "time_basis_label": "synthetic_utc",
        "time_basis_fingerprint": TIME_FP,
        "source_fingerprint": SRC_FP,
        "projection_report_fingerprint": PROJ_FP,
        "mapping_fingerprint": MAP_FP,
        "network_fingerprint": NET_FP,
        "interval_duration_s": 900,
        "measure": "vehicle_count",
        "unit": "vehicles_per_interval",
        "objective": "mean_absolute_error",
        "minimum_observed_coverage": Decimal("0.000"),
        "minimum_simulated_coverage": Decimal("0.000"),
        "parameters": (PARAM_BOUND,),
    }
    payload.update(overrides)
    return ManchesterCalibrationContract.model_validate(payload)


CONTRACT = make_contract()
PRODUCTION_CONTRACT = make_contract(
    contract_version="production-candidate-1",
    evidence_class="production",
    observed_source="webtris_daily",
    scope_kind="strategic_road_site",
    scope_label="m56_site_8150a",
)


def content(
    value: str,
    *,
    edge: str = "edge:1",
    start: int = 0,
    end: int = 900,
    direction: str = "N",
    vehicle_class: str = "car",
    measure: CalibrationMeasure = "vehicle_count",
    unit: CalibrationUnit = "vehicles_per_interval",
    scope_kind: ScopeKind = "synthetic_zone",
    scope_label: str = "synthetic_zone",
    scope_fp: str = SCOPE_FP,
    time_label: str = "synthetic_utc",
    time_fp: str = TIME_FP,
) -> CalibrationIntervalContent:
    return CalibrationIntervalContent.model_validate(
        {
            "site_edge_id": edge,
            "interval_start_s": start,
            "interval_end_s": end,
            "direction": direction,
            "vehicle_class": vehicle_class,
            "measure": measure,
            "unit": unit,
            "value": Decimal(value),
            "scope_kind": scope_kind,
            "scope_label": scope_label,
            "scope_fingerprint": scope_fp,
            "time_basis_label": time_label,
            "time_basis_fingerprint": time_fp,
        }
    )


def observed(
    value: str,
    *,
    salt: str = "obs",
    synthetic: bool = True,
    source: ObservedSource = "synthetic_utc_road",
    snapshot_id: str = SNAPSHOT_ID,
    source_fp: str = SRC_FP,
    projection_fp: str = PROJ_FP,
    mapping_fp: str = MAP_FP,
    start: int = 0,
    end: int = 900,
    measure: CalibrationMeasure = "vehicle_count",
    unit: CalibrationUnit = "vehicles_per_interval",
    scope_kind: ScopeKind = "synthetic_zone",
    scope_label: str = "synthetic_zone",
    scope_fp: str = SCOPE_FP,
    time_fp: str = TIME_FP,
) -> ObservedCalibrationInterval:
    interval = content(
        value,
        start=start,
        end=end,
        measure=measure,
        unit=unit,
        scope_kind=scope_kind,
        scope_label=scope_label,
        scope_fp=scope_fp,
        time_fp=time_fp,
    )
    return build_observed_calibration_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(f"{salt}-{interval.site_edge_id}-{value}".encode()),
        synthetic=synthetic,
        source=source,
        source_snapshot_id=snapshot_id,
        source_fingerprint=source_fp,
        projection_report_fingerprint=projection_fp,
        mapping_fingerprint=mapping_fp,
    )


def simulated(
    value: str,
    *,
    salt: str = "sim",
    synthetic: bool = True,
    network_fp: str = NET_FP,
    run_fp: str = RUN_A,
    start: int = 0,
    end: int = 900,
    measure: CalibrationMeasure = "vehicle_count",
    unit: CalibrationUnit = "vehicles_per_interval",
    scope_kind: ScopeKind = "synthetic_zone",
    scope_label: str = "synthetic_zone",
) -> SimulatedCalibrationInterval:
    interval = content(
        value,
        start=start,
        end=end,
        measure=measure,
        unit=unit,
        scope_kind=scope_kind,
        scope_label=scope_label,
    )
    return build_simulated_calibration_interval(
        interval=interval,
        source_row_fingerprint=sha256_hex(f"{salt}-{interval.site_edge_id}-{value}".encode()),
        synthetic=synthetic,
        network_fingerprint=network_fp,
        sumo_run_fingerprint=run_fp,
    )


def candidate(
    label: str,
    sims: list[SimulatedCalibrationInterval],
    *,
    run_fp: str = RUN_A,
    value: Decimal = Decimal("1.0"),
    name: str = "demand_scale",
) -> CalibrationCandidateInput:
    return CalibrationCandidateInput(
        candidate_label=label,
        parameter_values=(CalibrationParameterValue(name=name, value=value),),
        sumo_run_fingerprint=run_fp,
        simulated_inputs=tuple(sims),
    )


def real_observed(value: str) -> ObservedCalibrationInterval:
    return observed(
        value,
        synthetic=False,
        source="webtris_daily",
        snapshot_id=REAL_SNAPSHOT_ID,
        scope_kind="strategic_road_site",
        scope_label="m56_site_8150a",
    )


def golden_report(
    contract: ManchesterCalibrationContract = CONTRACT,
) -> ManchesterCalibrationReport:
    observed_rows = [
        observed("10"),
        observed("8", start=900, end=1800),
        observed("5", start=1800, end=2700),
    ]
    cand_a = candidate(
        "cand-a",
        [
            simulated("12", run_fp=RUN_A),
            simulated("7", start=900, end=1800, run_fp=RUN_A),
            simulated("7", start=1800, end=2700, run_fp=RUN_A),
        ],
        run_fp=RUN_A,
    )
    cand_b = candidate(
        "cand-b",
        [
            simulated("11", run_fp=RUN_B),
            simulated("8", start=900, end=1800, run_fp=RUN_B),
            simulated("5", start=1800, end=2700, run_fp=RUN_B),
        ],
        run_fp=RUN_B,
        value=Decimal("1.5"),
    )
    return evaluate_calibration_candidates(contract, observed_rows, [cand_a, cand_b])


def mutation_report() -> ManchesterCalibrationReport:
    observed_rows = [observed("10"), observed("8", start=900, end=1800)]
    cand_a = candidate(
        "cand-a",
        [simulated("12", run_fp=RUN_A), simulated("7", start=900, end=1800, run_fp=RUN_A)],
        run_fp=RUN_A,
    )
    cand_b = candidate(
        "cand-b",
        [simulated("11", run_fp=RUN_B)],
        run_fp=RUN_B,
        value=Decimal("1.5"),
    )
    return evaluate_calibration_candidates(CONTRACT, observed_rows, [cand_a, cand_b])


def report_data(report: ManchesterCalibrationReport) -> dict[str, Any]:
    data = json.loads(report.model_dump_json())
    assert isinstance(data, dict)
    return data


def expect_reload_failure(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ManchesterCalibrationReport.model_validate_json(json.dumps(data))


def evaluation(report: ManchesterCalibrationReport, label: str) -> CalibrationCandidateEvaluation:
    for item in report.candidate_evaluations:
        if item.candidate_label == label:
            return item
    raise AssertionError(f"no evaluation {label!r}")


def test_golden_objective_values_and_ranking() -> None:
    report = golden_report()
    eval_a = evaluation(report, "cand-a")
    eval_b = evaluation(report, "cand-b")
    assert eval_a.objective_result.status == "available"
    assert eval_a.objective_result.value == Decimal("1.667")
    assert eval_b.objective_result.value == Decimal("0.333")
    assert report.ranking == ("cand-b", "cand-a")
    assert report.selected_candidate_label == "cand-b"
    assert report.selection_status == "candidate_selected_for_analyst_review"
    assert report.automatic_acceptance is False
    assert report.baseline_available is False
    assert report.contract_admission == "synthetic_development_inputs"


def test_rmse_objective_golden_value() -> None:
    report = golden_report(make_contract(objective="root_mean_square_error"))
    eval_a = evaluation(report, "cand-a")
    assert eval_a.objective_result.objective == "root_mean_square_error"
    assert eval_a.objective_result.value == Decimal("1.732")


def test_signed_residual_direction_is_simulated_minus_observed() -> None:
    report = golden_report()
    pair = evaluation(report, "cand-a").pairs[0]
    assert pair.residual_direction == "simulated_minus_observed"
    assert pair.signed_residual == Decimal("2.000")
    assert pair.absolute_residual == Decimal("2.000")


def test_deterministic_fingerprint_tie_break() -> None:
    observed_rows = [observed("10")]
    cand_one = candidate("cand-one", [simulated("12", run_fp=RUN_A)], run_fp=RUN_A)
    cand_two = candidate("cand-two", [simulated("12", run_fp=RUN_B)], run_fp=RUN_B)
    report = evaluate_calibration_candidates(CONTRACT, observed_rows, [cand_one, cand_two])
    values = {
        item.candidate_label: item.objective_result.value for item in report.candidate_evaluations
    }
    assert values["cand-one"] == values["cand-two"]
    fingerprints = {
        item.candidate_label: item.candidate_binding_fingerprint
        for item in report.candidate_evaluations
    }
    expected = tuple(sorted(fingerprints, key=lambda label: fingerprints[label]))
    assert report.ranking == expected


def test_ambient_decimal_context_cannot_change_output() -> None:
    baseline = golden_report()
    canonical = baseline.canonical_json()
    fingerprint = baseline.fingerprint()
    original = decimal.getcontext()
    try:
        decimal.setcontext(decimal.Context(prec=5, rounding=decimal.ROUND_CEILING))
        perturbed = golden_report()
        perturbed_canonical = perturbed.canonical_json()
        perturbed_fingerprint = perturbed.fingerprint()
    finally:
        decimal.setcontext(original)
    assert perturbed_canonical == canonical
    assert perturbed_fingerprint == fingerprint


def test_parameter_bound_and_grid_refusals() -> None:
    for bad_value, code in (
        (Decimal("2.5"), "PARAMETER_OUT_OF_BOUNDS"),
        (Decimal("0.1"), "PARAMETER_OUT_OF_BOUNDS"),
        (Decimal("0.75"), "PARAMETER_NOT_IN_PERMITTED_GRID"),
    ):
        with pytest.raises(ManchesterCalibrationError) as exc_info:
            evaluate_calibration_candidates(
                CONTRACT,
                [observed("10")],
                [candidate("cand-a", [simulated("12")], value=bad_value)],
            )
        assert exc_info.value.code == code
    with pytest.raises(ManchesterCalibrationError) as exc_info:
        evaluate_calibration_candidates(
            CONTRACT,
            [observed("10")],
            [candidate("cand-a", [simulated("12")], name="other_name")],
        )
    assert exc_info.value.code == "PARAMETER_CONTRACT_MISMATCH"


def test_duplicate_parameter_and_invalid_grid_refusals() -> None:
    with pytest.raises(ValidationError):
        CalibrationCandidateInput(
            candidate_label="cand-a",
            parameter_values=(
                CalibrationParameterValue(name="demand_scale", value=Decimal("1.0")),
                CalibrationParameterValue(name="demand_scale", value=Decimal("1.5")),
            ),
            sumo_run_fingerprint=RUN_A,
            simulated_inputs=(),
        )
    with pytest.raises(ValidationError):
        CalibrationParameterBound(
            name="demand_scale",
            unit="ratio",
            lower_bound=Decimal("0.5"),
            upper_bound=Decimal("2.0"),
            permitted_values=(Decimal("1.0"), Decimal("1.0")),
        )
    with pytest.raises(ValidationError):
        CalibrationParameterBound(
            name="demand_scale",
            unit="ratio",
            lower_bound=Decimal("0.5"),
            upper_bound=Decimal("2.0"),
            permitted_values=(Decimal("3.0"),),
        )
    with pytest.raises(ValidationError):
        make_contract(parameters=(PARAM_BOUND, PARAM_BOUND))


def test_duplicate_candidate_label_refused() -> None:
    with pytest.raises(ManchesterCalibrationError) as exc_info:
        evaluate_calibration_candidates(
            CONTRACT,
            [observed("10")],
            [candidate("cand-a", [simulated("12")]), candidate("cand-a", [])],
        )
    assert exc_info.value.code == "DUPLICATE_CANDIDATE_LABEL"


def test_missing_simulated_interval_is_exclusion_never_zero() -> None:
    observed_rows = [observed("10"), observed("8", start=900, end=1800)]
    report = evaluate_calibration_candidates(
        CONTRACT, observed_rows, [candidate("cand-a", [simulated("12")])]
    )
    item = evaluation(report, "cand-a")
    reasons = [(entry.side, entry.reason) for entry in item.exclusions]
    assert ("observed", "unmatched_no_simulated_counterpart") in reasons
    assert report.observed_input_rows == item.paired_intervals + item.excluded_observed
    assert all(entry.filled_with_zero is False for entry in item.exclusions)


def test_missing_observed_interval_is_exclusion() -> None:
    report = evaluate_calibration_candidates(
        CONTRACT,
        [observed("10")],
        [candidate("cand-a", [simulated("12"), simulated("3", start=900, end=1800)])],
    )
    item = evaluation(report, "cand-a")
    reasons = [(entry.side, entry.reason) for entry in item.exclusions]
    assert ("simulated", "unmatched_no_observed_counterpart") in reasons
    assert item.simulated_input_rows == item.paired_intervals + item.excluded_simulated


def test_numeric_duplicates_collapse_and_conflicts_refuse() -> None:
    report = evaluate_calibration_candidates(
        CONTRACT,
        [observed("10", salt="one"), observed("10.0", salt="two")],
        [candidate("cand-a", [simulated("12")])],
    )
    item = evaluation(report, "cand-a")
    reasons = [entry.reason for entry in item.exclusions]
    assert reasons.count("duplicate_identical_row") == 1
    assert "conflicting_duplicate_rows" not in reasons
    assert item.paired_intervals == 1

    conflicted = evaluate_calibration_candidates(
        CONTRACT,
        [observed("10", salt="one"), observed("11", salt="two")],
        [candidate("cand-a", [simulated("12")])],
    )
    item = evaluation(conflicted, "cand-a")
    reasons = [entry.reason for entry in item.exclusions]
    assert reasons.count("conflicting_duplicate_rows") == 2
    assert item.paired_intervals == 0


def test_cross_scope_time_basis_and_duration_refusal() -> None:
    report = evaluate_calibration_candidates(
        CONTRACT,
        [
            observed("10", scope_fp="7" * 64),
            observed("8", start=900, end=1800, time_fp="8" * 64),
            observed("5", start=1800, end=3600),
        ],
        [candidate("cand-a", [])],
    )
    reasons = {entry.reason for entry in evaluation(report, "cand-a").exclusions}
    assert "scope_mismatch" in reasons
    assert "time_basis_mismatch" in reasons
    assert "interval_duration_mismatch" in reasons
    assert evaluation(report, "cand-a").paired_intervals == 0


def test_cross_network_mapping_and_run_lineage_refusal() -> None:
    report = evaluate_calibration_candidates(
        CONTRACT,
        [observed("10"), observed("8", start=900, end=1800, mapping_fp="9" * 64)],
        [
            candidate(
                "cand-a",
                [
                    simulated("12", network_fp="9" * 64, run_fp=RUN_A),
                    simulated("7", start=900, end=1800, run_fp=RUN_B),
                ],
                run_fp=RUN_A,
            )
        ],
    )
    item = evaluation(report, "cand-a")
    lineage_reasons = [
        entry.reason for entry in item.exclusions if entry.reason == "lineage_fingerprint_mismatch"
    ]
    assert len(lineage_reasons) == 3
    assert item.paired_intervals == 0


def test_cross_source_rows_are_refused_not_fused() -> None:
    dft_row = observed(
        "10",
        synthetic=False,
        source="dft_raw_count",
        snapshot_id=DFT_SNAPSHOT_ID,
        scope_kind="urban_zone",
        scope_label="dft_zone",
    )
    report = evaluate_calibration_candidates(
        PRODUCTION_CONTRACT,
        [dft_row, real_observed("10")],
        [
            candidate(
                "cand-a",
                [
                    simulated(
                        "12",
                        synthetic=False,
                        scope_kind="strategic_road_site",
                        scope_label="m56_site_8150a",
                    )
                ],
            )
        ],
    )
    item = evaluation(report, "cand-a")
    assert ("observed", "source_mismatch") in [(e.side, e.reason) for e in item.exclusions]


def test_count_and_speed_evidence_never_share_an_objective() -> None:
    speed_row = observed("13.4", measure="average_speed_mps", unit="m/s")
    report = evaluate_calibration_candidates(
        CONTRACT, [speed_row, observed("10")], [candidate("cand-a", [simulated("12")])]
    )
    item = evaluation(report, "cand-a")
    assert ("observed", "measure_mismatch") in [(e.side, e.reason) for e in item.exclusions]
    assert item.paired_intervals == 1
    with pytest.raises(ValidationError):
        make_contract(measure="average_speed_mps")  # unit stays vehicles_per_interval


def test_dft_raw_count_speed_is_structurally_impossible() -> None:
    with pytest.raises(ValidationError):
        make_contract(
            observed_source="dft_raw_count",
            scope_kind="urban_zone",
            evidence_class="production",
            measure="average_speed_mps",
            unit="m/s",
        )
    with pytest.raises(ValidationError):
        observed(
            "13.4",
            synthetic=False,
            source="dft_raw_count",
            snapshot_id=DFT_SNAPSHOT_ID,
            scope_kind="urban_zone",
            scope_label="dft_zone",
            measure="average_speed_mps",
            unit="m/s",
        )


def test_insufficient_coverage_gives_typed_unavailability() -> None:
    contract = make_contract(minimum_observed_coverage=Decimal("0.800"))
    report = evaluate_calibration_candidates(
        contract,
        [observed("10"), observed("8", start=900, end=1800), observed("5", start=1800, end=2700)],
        [candidate("cand-a", [simulated("12")])],
    )
    item = evaluation(report, "cand-a")
    assert item.paired_observed_coverage == Decimal("0.333")
    assert item.coverage_requirement_met is False
    assert item.objective_result.status == "unavailable"
    assert item.objective_result.reason == "coverage_below_contract_minimum"
    assert item.objective_result.value is None


def test_display_rounding_cannot_admit_coverage_below_threshold() -> None:
    contract = make_contract(minimum_observed_coverage=Decimal("0.667"))
    report = evaluate_calibration_candidates(
        contract,
        [observed("10"), observed("8", start=900, end=1800), observed("5", start=1800, end=2700)],
        [
            candidate(
                "cand-a",
                [simulated("12"), simulated("7", start=900, end=1800)],
            )
        ],
    )
    item = evaluation(report, "cand-a")
    assert item.paired_observed_coverage == Decimal("0.667")
    assert item.coverage_requirement_met is False
    assert item.objective_result.reason == "coverage_below_contract_minimum"


def test_empty_pair_set_gives_typed_unavailability() -> None:
    report = evaluate_calibration_candidates(CONTRACT, [observed("10")], [candidate("cand-a", [])])
    item = evaluation(report, "cand-a")
    assert item.objective_result.status == "unavailable"
    assert item.objective_result.reason == "no_paired_intervals"
    assert item.objective_result.sample_size == 0
    assert item.paired_simulated_coverage == Decimal("0.000")
    assert report.selection_status == "no_candidate_available"
    assert report.selected_candidate_label is None


def test_production_objective_remains_unavailable() -> None:
    assert not APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS
    report = evaluate_calibration_candidates(
        PRODUCTION_CONTRACT,
        [real_observed("10")],
        [
            candidate(
                "cand-a",
                [
                    simulated(
                        "12",
                        synthetic=False,
                        scope_kind="strategic_road_site",
                        scope_label="m56_site_8150a",
                    )
                ],
            )
        ],
    )
    assert report.contract_admitted is False
    assert report.contract_admission == "not_admitted_production_unapproved"
    item = evaluation(report, "cand-a")
    assert item.objective_result.status == "unavailable"
    assert item.objective_result.reason == "contract_not_admitted"
    assert item.paired_intervals == 1  # pairing is inspectable; the objective is not
    assert report.ranking == ()
    assert report.selection_status == "no_candidate_available"


def test_production_self_approval_forgery_fails_reload() -> None:
    report = evaluate_calibration_candidates(
        PRODUCTION_CONTRACT,
        [real_observed("10")],
        [
            candidate(
                "cand-a",
                [
                    simulated(
                        "12",
                        synthetic=False,
                        scope_kind="strategic_road_site",
                        scope_label="m56_site_8150a",
                    )
                ],
            )
        ],
    )
    data = report_data(report)
    data["contract_admitted"] = True
    data["contract_admission"] = "approved_production_contract"
    expect_reload_failure(data)


def test_mixed_and_mismatched_evidence_classes_are_refused() -> None:
    with pytest.raises(ManchesterCalibrationError) as exc_info:
        evaluate_calibration_candidates(
            CONTRACT,
            [observed("10")],
            [
                candidate(
                    "cand-a",
                    [
                        simulated(
                            "12",
                            synthetic=False,
                            scope_kind="strategic_road_site",
                            scope_label="m56_site_8150a",
                        )
                    ],
                )
            ],
        )
    assert exc_info.value.code == "MIXED_EVIDENCE"

    with pytest.raises(ManchesterCalibrationError) as exc_info:
        evaluate_calibration_candidates(
            CONTRACT,
            [real_observed("10")],
            [candidate("cand-a", [simulated("12", synthetic=False)])],
        )
    assert exc_info.value.code == "CONTRACT_EVIDENCE_CLASS_MISMATCH"

    with pytest.raises(ManchesterCalibrationError) as exc_info:
        evaluate_calibration_candidates(
            PRODUCTION_CONTRACT,
            [observed("10")],
            [candidate("cand-a", [simulated("12")])],
        )
    assert exc_info.value.code == "CONTRACT_EVIDENCE_CLASS_MISMATCH"


def test_coherent_objective_and_ranking_rewrite_fails_reload() -> None:
    data = report_data(golden_report())
    data["ranking"] = ["cand-a", "cand-b"]
    data["selected_candidate_label"] = "cand-a"
    values = {
        item["candidate_label"]: item["objective_result"]["value"]
        for item in data["candidate_evaluations"]
    }
    for item in data["candidate_evaluations"]:
        other = "cand-b" if item["candidate_label"] == "cand-a" else "cand-a"
        item["objective_result"]["value"] = values[other]
    expect_reload_failure(data)


def test_reload_mutations_are_rejected() -> None:
    baseline = mutation_report()

    def mutate(apply: Callable[[dict[str, Any]], None]) -> None:
        data = report_data(baseline)
        apply(data)
        expect_reload_failure(data)

    def set_pair_field(data: dict[str, Any], field: str, value: str) -> None:
        data["candidate_evaluations"][0]["pairs"][0][field] = value

    mutate(lambda d: d.update(synthetic=False))
    mutate(lambda d: d.update(automatic_acceptance=True))
    mutate(lambda d: d.update(baseline_available=True))
    mutate(lambda d: d.update(observed_input_rows=3))
    mutate(lambda d: d.update(observed_input_set_fingerprint="0" * 64))
    mutate(lambda d: d.update(ranking=[]))
    mutate(lambda d: d.update(selected_candidate_label="cand-a"))
    mutate(lambda d: d["observed_inputs"][0]["interval"].update(value="99"))
    mutate(lambda d: d["observed_inputs"][0].update(synthetic=False))
    mutate(lambda d: d["observed_inputs"].pop(0))
    mutate(lambda d: d["observed_inputs"].append(d["observed_inputs"][0]))
    mutate(lambda d: d["observed_inputs"].reverse())
    mutate(lambda d: d["candidate_evaluations"].reverse())
    mutate(lambda d: d["candidate_evaluations"][0]["parameter_values"][0].update(value="1.5"))
    mutate(lambda d: set_pair_field(d, "signed_residual", "5.000"))
    mutate(lambda d: set_pair_field(d, "observed_value", "9"))
    mutate(lambda d: d["candidate_evaluations"][0].update(paired_intervals=1))
    mutate(lambda d: d["candidate_evaluations"][0].update(paired_observed_coverage="0.500"))
    mutate(lambda d: d["candidate_evaluations"][0].update(candidate_binding_fingerprint="0" * 64))
    mutate(
        lambda d: d["candidate_evaluations"][1]["exclusions"][0].update(
            reason="duplicate_identical_row"
        )
    )
    mutate(
        lambda d: d["candidate_evaluations"][1]["simulated_inputs"][0]["interval"].update(
            value="10"
        )
    )
    mutate(lambda d: d["candidate_evaluations"][0]["objective_result"].update(value="0.100"))


def test_altered_input_content_cannot_keep_old_binding() -> None:
    row = observed("10")
    data = json.loads(row.model_dump_json())
    data["interval"]["value"] = "11"
    with pytest.raises(ValidationError):
        ObservedCalibrationInterval.model_validate_json(json.dumps(data))


def test_input_and_candidate_order_invariance() -> None:
    observed_rows = [
        observed("10"),
        observed("8", start=900, end=1800),
        observed("5", start=1800, end=2700),
    ]
    cand_a = candidate(
        "cand-a",
        [
            simulated("12", run_fp=RUN_A),
            simulated("7", start=900, end=1800, run_fp=RUN_A),
            simulated("7", start=1800, end=2700, run_fp=RUN_A),
        ],
        run_fp=RUN_A,
    )
    cand_b = candidate(
        "cand-b",
        [
            simulated("11", run_fp=RUN_B),
            simulated("8", start=900, end=1800, run_fp=RUN_B),
            simulated("5", start=1800, end=2700, run_fp=RUN_B),
        ],
        run_fp=RUN_B,
        value=Decimal("1.5"),
    )
    forward = evaluate_calibration_candidates(CONTRACT, observed_rows, [cand_a, cand_b])
    shuffled = evaluate_calibration_candidates(
        CONTRACT, list(reversed(observed_rows)), [cand_b, cand_a]
    )
    assert forward.canonical_json() == shuffled.canonical_json()
    assert forward.fingerprint() == shuffled.fingerprint()


def test_canonical_json_round_trip() -> None:
    report = mutation_report()
    reloaded = ManchesterCalibrationReport.model_validate_json(report.model_dump_json())
    assert reloaded.canonical_json() == report.canonical_json()
    assert reloaded.fingerprint() == report.fingerprint()


def test_no_input_refusal() -> None:
    with pytest.raises(ManchesterCalibrationError) as exc_info:
        evaluate_calibration_candidates(CONTRACT, [], [candidate("cand-a", [])])
    assert exc_info.value.code == "NO_INPUT"
    with pytest.raises(ManchesterCalibrationError) as exc_info:
        evaluate_calibration_candidates(CONTRACT, [observed("10")], [])
    assert exc_info.value.code == "NO_INPUT"


def test_no_causal_or_favourability_wording() -> None:
    text = golden_report().canonical_json().lower()
    for token in ("better", "accurate", "improved", "valid model", "realistic", "proves"):
        assert token not in text
    assert "candidate_selected_for_analyst_review" in text
