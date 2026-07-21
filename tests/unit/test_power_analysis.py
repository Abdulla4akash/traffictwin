from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from traffictwin.experiments.power_analysis import (
    PairedVarianceBasis,
    PowerAnalysisConfig,
    PowerAnalysisReasonCode,
    PowerAnalysisStatus,
    PowerEstimateLabel,
    TargetEffectBasis,
    evaluate_power_analysis,
    power_analysis_method_contract,
    power_analysis_to_csv,
    power_analysis_to_markdown,
)

FIXED_TIME = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def _config(**overrides: object) -> PowerAnalysisConfig:
    values: dict[str, object] = {
        "metric_key": "task.completion.rate",
        "unit": "ratio",
        "target_effect": 0.5,
        "paired_difference_variance": 1.0,
        "target_effect_basis": TargetEffectBasis.PRACTICAL_THRESHOLD,
        "target_effect_justification": "A predeclared practically meaningful difference",
        "variance_basis": PairedVarianceBasis.PROVISIONAL_DESIGN,
        "variance_justification": "A predeclared conservative planning variance",
    }
    values.update(overrides)
    return PowerAnalysisConfig(**values)


def test_known_normal_reference_requires_32_pairs() -> None:
    analysis = evaluate_power_analysis(_config(), clock=lambda: FIXED_TIME)
    result = analysis.calculation

    assert analysis.status is PowerAnalysisStatus.AVAILABLE
    assert result.required_common_seed_replicates == 32
    assert result.required_total_policy_runs == 64
    assert result.two_sided_critical_value == pytest.approx(1.9599639845400536)
    assert result.achieved_power == pytest.approx(0.8074304194325573)
    assert result.preceding_replicate_count == 31
    assert result.preceding_power == pytest.approx(0.7950080284018122)
    assert result.standardised_effect_magnitude == pytest.approx(0.5)


def test_result_is_the_smallest_integer_meeting_target() -> None:
    analysis = evaluate_power_analysis(_config(target_effect=0.2), clock=lambda: FIXED_TIME)
    result = analysis.calculation

    assert result.required_common_seed_replicates == 197
    assert result.achieved_power is not None and result.achieved_power >= 0.8
    assert result.preceding_power is not None and result.preceding_power < 0.8


def test_two_sided_power_is_symmetric_in_effect_sign() -> None:
    positive = evaluate_power_analysis(_config(target_effect=0.5), clock=lambda: FIXED_TIME)
    negative = evaluate_power_analysis(_config(target_effect=-0.5), clock=lambda: FIXED_TIME)

    assert positive.calculation.required_common_seed_replicates == (
        negative.calculation.required_common_seed_replicates
    )
    assert positive.calculation.achieved_power == negative.calculation.achieved_power
    assert any("absolute magnitude" in warning for warning in negative.warnings)


def test_minimum_bound_has_no_preceding_result() -> None:
    analysis = evaluate_power_analysis(_config(target_effect=10.0), clock=lambda: FIXED_TIME)

    assert analysis.calculation.required_common_seed_replicates == 3
    assert analysis.calculation.preceding_replicate_count is None
    assert analysis.calculation.preceding_power is None


def test_larger_effect_needs_no_more_pairs() -> None:
    smaller = evaluate_power_analysis(_config(target_effect=0.25), clock=lambda: FIXED_TIME)
    larger = evaluate_power_analysis(_config(target_effect=0.5), clock=lambda: FIXED_TIME)

    assert smaller.calculation.required_common_seed_replicates is not None
    assert larger.calculation.required_common_seed_replicates is not None
    assert larger.calculation.required_common_seed_replicates < (
        smaller.calculation.required_common_seed_replicates
    )


def test_stricter_power_or_alpha_needs_more_pairs() -> None:
    ordinary = evaluate_power_analysis(_config(), clock=lambda: FIXED_TIME)
    higher_power = evaluate_power_analysis(_config(target_power=0.9), clock=lambda: FIXED_TIME)
    lower_alpha = evaluate_power_analysis(_config(alpha=0.01), clock=lambda: FIXED_TIME)

    ordinary_n = ordinary.calculation.required_common_seed_replicates
    assert ordinary_n is not None
    assert higher_power.calculation.required_common_seed_replicates is not None
    assert lower_alpha.calculation.required_common_seed_replicates is not None
    assert higher_power.calculation.required_common_seed_replicates > ordinary_n
    assert lower_alpha.calculation.required_common_seed_replicates > ordinary_n


def test_zero_effect_is_typed_unavailable() -> None:
    analysis = evaluate_power_analysis(_config(target_effect=0.0), clock=lambda: FIXED_TIME)

    assert analysis.status is PowerAnalysisStatus.UNAVAILABLE
    assert analysis.calculation.reason_code is PowerAnalysisReasonCode.ZERO_TARGET_EFFECT
    assert analysis.calculation.required_common_seed_replicates is None


def test_zero_variance_is_typed_unavailable() -> None:
    analysis = evaluate_power_analysis(
        _config(paired_difference_variance=0.0),
        clock=lambda: FIXED_TIME,
    )

    assert analysis.status is PowerAnalysisStatus.UNAVAILABLE
    assert analysis.calculation.reason_code is PowerAnalysisReasonCode.NON_POSITIVE_VARIANCE
    assert analysis.calculation.standardised_effect_magnitude is None


def test_declared_maximum_can_make_result_unavailable() -> None:
    analysis = evaluate_power_analysis(
        _config(target_effect=0.01, maximum_replicates=3),
        clock=lambda: FIXED_TIME,
    )

    assert analysis.status is PowerAnalysisStatus.UNAVAILABLE
    assert analysis.calculation.reason_code is PowerAnalysisReasonCode.MAXIMUM_REPLICATES_EXCEEDED
    assert "maximum of 3" in (analysis.calculation.reason or "")


def test_small_planned_sample_is_labelled() -> None:
    analysis = evaluate_power_analysis(_config(target_effect=1.0), clock=lambda: FIXED_TIME)

    assert PowerEstimateLabel.PLANNING_AID in analysis.labels
    assert PowerEstimateLabel.SMALL_PLANNED_SAMPLE in analysis.labels
    assert any("normal approximation" in warning for warning in analysis.warnings)


def test_small_pilot_sample_is_labelled() -> None:
    analysis = evaluate_power_analysis(
        _config(
            variance_basis=PairedVarianceBasis.PILOT_STUDY,
            pilot_sample_size=8,
        ),
        clock=lambda: FIXED_TIME,
    )

    assert PowerEstimateLabel.SMALL_PILOT_SAMPLE in analysis.labels
    assert any("fewer than 30 pairs" in warning for warning in analysis.warnings)


def test_synthetic_and_provisional_inputs_are_labelled() -> None:
    analysis = evaluate_power_analysis(
        _config(
            target_effect_basis=TargetEffectBasis.SYNTHETIC,
            variance_basis=PairedVarianceBasis.SYNTHETIC,
            synthetic=True,
        ),
        clock=lambda: FIXED_TIME,
    )
    provisional = evaluate_power_analysis(_config(), clock=lambda: FIXED_TIME)

    assert PowerEstimateLabel.SYNTHETIC_INPUT in analysis.labels
    assert PowerEstimateLabel.PROVISIONAL_INPUT in provisional.labels


def test_pilot_and_synthetic_bases_require_their_labels() -> None:
    with pytest.raises(ValidationError, match="pilot_sample_size is required"):
        _config(variance_basis=PairedVarianceBasis.PILOT_STUDY)
    with pytest.raises(ValidationError, match="synthetic must be true"):
        _config(variance_basis=PairedVarianceBasis.SYNTHETIC)


def test_literature_bases_require_references() -> None:
    with pytest.raises(ValidationError, match="target_effect_reference is required"):
        _config(target_effect_basis=TargetEffectBasis.LITERATURE)
    with pytest.raises(ValidationError, match="variance_reference is required"):
        _config(variance_basis=PairedVarianceBasis.LITERATURE)

    config = _config(
        target_effect_basis=TargetEffectBasis.LITERATURE,
        target_effect_reference="Effect source",
        variance_basis=PairedVarianceBasis.LITERATURE,
        variance_reference="Variance source",
    )
    assert config.target_effect_reference == "Effect source"
    assert config.variance_reference == "Variance source"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_effect", float("nan")),
        ("target_effect", float("inf")),
        ("paired_difference_variance", float("inf")),
        ("alpha", 0.0),
        ("target_power", 1.0),
        ("maximum_replicates", 1_000_001),
    ],
)
def test_non_finite_and_out_of_range_inputs_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _config(**{field: value})


def test_justifications_are_trimmed_and_bounded() -> None:
    config = _config(
        target_effect_justification="  sufficiently detailed effect basis  ",
        variance_justification="  sufficiently detailed variance basis  ",
    )

    assert config.target_effect_justification == "sufficiently detailed effect basis"
    assert config.variance_justification == "sufficiently detailed variance basis"
    with pytest.raises(ValidationError, match="at least 12"):
        _config(target_effect_justification="too short")


def test_evaluation_is_deterministic_timestamp_normalised_and_immutable() -> None:
    config = _config()
    before = config.model_dump(mode="json")
    first = evaluate_power_analysis(config, clock=lambda: FIXED_TIME)
    second = evaluate_power_analysis(config, clock=lambda: FIXED_TIME + timedelta(days=1))

    assert first.model_dump(mode="json") != second.model_dump(mode="json")
    assert first.fingerprint() == second.fingerprint()
    assert first.analysis_id == second.analysis_id
    assert config.model_dump(mode="json") == before


def test_json_markdown_and_csv_reconcile() -> None:
    analysis = evaluate_power_analysis(_config(), clock=lambda: FIXED_TIME)

    payload = json.loads(analysis.to_json())
    markdown = power_analysis_to_markdown(analysis)
    rows = list(csv.DictReader(io.StringIO(power_analysis_to_csv(analysis))))

    assert payload["calculation"]["required_common_seed_replicates"] == 32
    assert "Required common-seed replicates: `32`" in markdown
    assert rows[0]["required_common_seed_replicates"] == "32"
    assert rows[0]["analysis_fingerprint"] == analysis.fingerprint()


def test_method_contract_publishes_bounds_and_unsupported_scope() -> None:
    contract = power_analysis_method_contract()

    assert contract.replicate_bounds == {"minimum": 3, "maximum": 1_000_000}
    assert contract.target_power_bounds == {"minimum": 0.5, "maximum": 0.999}
    assert "smallest integer" in contract.decision_rule.lower()
    assert any("retrospective" in item for item in contract.unsupported)
    assert len(contract.fingerprint()) == 64
