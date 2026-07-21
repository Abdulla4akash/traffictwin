from __future__ import annotations

from traffictwin.experiments.power_analysis import (
    PairedVarianceBasis,
    PowerAnalysis,
    PowerAnalysisConfig,
    PowerAnalysisReasonCode,
    PowerAnalysisStatus,
    TargetEffectBasis,
)
from traffictwin.ui.services import evaluate_power_analysis_for_ui


def _config(target_effect: float = 0.5) -> PowerAnalysisConfig:
    return PowerAnalysisConfig(
        metric_key="task.completion.rate",
        unit="ratio",
        target_effect=target_effect,
        paired_difference_variance=1.0,
        target_effect_basis=TargetEffectBasis.PRACTICAL_THRESHOLD,
        target_effect_justification="A predeclared practically meaningful difference",
        variance_basis=PairedVarianceBasis.PROVISIONAL_DESIGN,
        variance_justification="A predeclared conservative planning variance",
    )


def test_power_analysis_ui_service_delegates_complete_plan() -> None:
    result = evaluate_power_analysis_for_ui(_config())

    assert isinstance(result, PowerAnalysis)
    assert result.status is PowerAnalysisStatus.AVAILABLE
    assert result.calculation.required_common_seed_replicates == 32


def test_power_analysis_ui_service_retains_typed_unavailable_result() -> None:
    result = evaluate_power_analysis_for_ui(_config(target_effect=0.0))

    assert isinstance(result, PowerAnalysis)
    assert result.status is PowerAnalysisStatus.UNAVAILABLE
    assert result.calculation.reason_code is PowerAnalysisReasonCode.ZERO_TARGET_EFFECT
