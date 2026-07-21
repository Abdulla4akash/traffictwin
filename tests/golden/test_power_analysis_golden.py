from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.experiments.power_analysis import (
    PairedVarianceBasis,
    PowerAnalysisConfig,
    TargetEffectBasis,
    evaluate_power_analysis,
)

EXPECTED = Path("tests/golden/expected/power_analysis_known_plan.json")


def test_known_paired_power_plan_matches_golden_projection() -> None:
    analysis = evaluate_power_analysis(
        PowerAnalysisConfig(
            metric_key="task.completion.rate",
            unit="ratio",
            target_effect=0.05,
            paired_difference_variance=0.0025,
            target_effect_basis=TargetEffectBasis.SYNTHETIC,
            target_effect_justification=(
                "Explicit synthetic target for deterministic golden verification"
            ),
            variance_basis=PairedVarianceBasis.SYNTHETIC,
            variance_justification=(
                "Explicit synthetic variance for deterministic golden verification"
            ),
            synthetic=True,
        ),
        clock=lambda: datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
    )
    actual = {
        "analysis_id": analysis.analysis_id,
        "status": analysis.status.value,
        "config": analysis.config.model_dump(mode="json"),
        "config_fingerprint": analysis.config_fingerprint,
        "calculation": analysis.calculation.model_dump(mode="json"),
        "labels": [item.value for item in analysis.labels],
        "provenance": analysis.provenance,
        "warnings": analysis.warnings,
        "assumptions": analysis.assumptions,
        "limitations": analysis.limitations,
        "fingerprint": analysis.fingerprint(),
    }

    assert actual == json.loads(EXPECTED.read_text(encoding="utf-8"))
