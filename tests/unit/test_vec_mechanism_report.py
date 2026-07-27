"""Unit coverage for the campaign mechanism-evidence report.

Every payload here is synthetic. Nothing reads a registry, launches a campaign,
or touches a real analysis artifact.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collections,
)
from traffictwin.experiments import evaluate_paired_statistical_study
from traffictwin.integration.vec_campaign.mechanism_report import (
    CampaignMechanismReport,
    MechanismReportError,
    build_mechanism_report,
    render_mechanism_report_markdown,
)

FINGERPRINT = "a" * 64


def _descriptive(arm: str, metric: str, seed_values: dict[str, float]) -> dict[str, Any]:
    values = list(seed_values.values())
    return {
        "arm_label": arm,
        "metric_key": metric,
        "seed_values": seed_values,
        "mean": sum(values) / len(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def _analysis() -> dict[str, Any]:
    """Return a fresh synthetic analysis payload; callers mutate their own copy."""

    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "method_version": "vec-campaign-analysis-1.0",
        "experiment_id": "synthetic-campaign",
        "design_fingerprint": FINGERPRINT,
        "campaign_status": "completed",
        "primary_metric_key": "tos.task.deadline_success.rate",
        "baseline_label": "cap-2.5",
        "admitted_collection_count": 6,
        "comparisons": [
            {
                "variation_label": "cap-1.0",
                "study_status": "evaluated",
                "admitted_pair_count": 3,
                "mean_paired_difference": 0.0001,
                "bootstrap_lower": 0.0,
                "bootstrap_upper": 0.0003,
                "randomisation_p_value": 1.0,
                "study": _study(),
            }
        ],
        "primary_descriptives": [
            _descriptive(
                "cap-2.5",
                "tos.task.deadline_success.rate",
                {"0": 0.790, "1": 0.791, "2": 0.792},
            ),
            _descriptive(
                "cap-1.0",
                "tos.task.deadline_success.rate",
                {"0": 0.7901, "1": 0.7911, "2": 0.7921},
            ),
        ],
        "secondary_descriptives": [
            # Latency moves with the control, consistently per seed.
            _descriptive(
                "cap-2.5", "task.latency.mean_ms", {"0": 9000.0, "1": 6000.0, "2": 13000.0}
            ),
            _descriptive(
                "cap-1.0", "task.latency.mean_ms", {"0": 4000.0, "1": 3000.0, "2": 5000.0}
            ),
            # Offload rate is bit-identical across arms within every seed.
            _descriptive("cap-2.5", "task.offload.rate", {"0": 0.402608, "1": 0.406349}),
            _descriptive("cap-1.0", "task.offload.rate", {"0": 0.402608, "1": 0.406349}),
        ],
        "generated_at_utc": "2026-07-27T10:31:00+00:00",
        "research_status": "owner_approved_candidate",
        "confirmatory": False,
        "significance_claimed": False,
        "limitations": ["Exploratory only."],
    }
    return payload


def _study() -> dict[str, Any]:
    """Build a genuine study through the accepted evaluator, not a hand-written one.

    The mechanism report never inspects the nested study, but the analysis model
    requires a real one; producing it through the accepted tool keeps this
    fixture from drifting away from STA-01's actual shape.
    """

    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0, 3.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    payload: dict[str, Any] = json.loads(study.model_dump_json())
    return payload


def _report() -> CampaignMechanismReport:
    return build_mechanism_report(_analysis())


def test_a_payload_that_is_not_an_analysis_is_refused() -> None:
    with pytest.raises(MechanismReportError, match="not a valid campaign analysis"):
        build_mechanism_report({"experiment_id": "incomplete"})


def test_identity_and_arms_come_from_the_analysis_in_its_own_order() -> None:
    report = _report()

    assert report.experiment_id == "synthetic-campaign"
    assert report.design_fingerprint == FINGERPRINT
    assert report.primary_metric_key == "tos.task.deadline_success.rate"
    assert report.baseline_label == "cap-2.5"
    assert report.arm_labels == ["cap-2.5", "cap-1.0"]
    assert report.seed_ids == ["0", "1", "2"]


def test_per_seed_rows_carry_every_arm_for_the_primary_endpoint() -> None:
    report = _report()

    assert len(report.primary_rows) == 3
    first = report.primary_rows[0]
    assert first.metric_key == "tos.task.deadline_success.rate"
    assert first.seed_id == "0"
    assert first.arm_values == {"cap-1.0": 0.7901, "cap-2.5": 0.790}
    assert first.arms_missing_this_seed == []


def test_a_seed_missing_from_an_arm_is_named_not_hidden() -> None:
    payload = _analysis()
    payload["primary_descriptives"][1] = _descriptive(
        "cap-1.0", "tos.task.deadline_success.rate", {"0": 0.7901, "1": 0.7911}
    )

    report = build_mechanism_report(payload)

    seed_two = next(row for row in report.primary_rows if row.seed_id == "2")
    assert seed_two.arms_missing_this_seed == ["cap-1.0"]
    assert "cap-1.0" not in seed_two.arm_values


def test_offload_rate_is_reported_invariant_in_every_seed() -> None:
    report = _report()

    offload = next(item for item in report.invariance if item.metric_key == "task.offload.rate")
    assert offload.seed_count == 2
    assert offload.invariant_seed_count == 2
    assert offload.invariant_in_every_seed is True
    assert all(item.spread == pytest.approx(0.0) for item in offload.per_seed)
    assert all(item.distinct_value_count == 1 for item in offload.per_seed)


def test_a_metric_the_control_moves_is_not_reported_invariant() -> None:
    report = _report()

    latency = next(item for item in report.invariance if item.metric_key == "task.latency.mean_ms")
    assert latency.invariant_in_every_seed is False
    assert latency.invariant_seed_count == 0
    assert latency.per_seed[0].distinct_value_count == 2


def test_a_single_arm_is_never_called_invariant_across_arms() -> None:
    payload = _analysis()
    payload["secondary_descriptives"] = [
        _descriptive("cap-2.5", "task.offload.rate", {"0": 0.4, "1": 0.4})
    ]

    report = build_mechanism_report(payload)

    offload = next(item for item in report.invariance if item.metric_key == "task.offload.rate")
    assert offload.invariant_in_every_seed is False
    assert all(item.compared_arm_count == 1 for item in offload.per_seed)


def test_range_comparison_separates_overlap_from_per_seed_ordering() -> None:
    report = _report()

    latency = next(
        row for row in report.range_comparisons if row.metric_key == "task.latency.mean_ms"
    )
    # cap-2.5 spans [6000, 13000] and cap-1.0 spans [3000, 5000]: disjoint here.
    assert latency.ranges_overlap is False
    assert latency.range_gap == pytest.approx(1000.0)
    assert latency.paired_seed_count == 3
    # Every seed ranks cap-1.0 below cap-2.5, so the ordering is consistent.
    assert latency.seeds_where_upper_exceeds_lower == 0
    assert latency.per_seed_ordering_consistent is True


def test_overlapping_ranges_can_still_have_a_consistent_per_seed_ordering() -> None:
    payload = _analysis()
    payload["secondary_descriptives"] = [
        _descriptive("cap-2.5", "task.latency.mean_ms", {"0": 100.0, "1": 500.0}),
        _descriptive("cap-1.0", "task.latency.mean_ms", {"0": 90.0, "1": 450.0}),
    ]

    report = build_mechanism_report(payload)

    latency = next(
        row for row in report.range_comparisons if row.metric_key == "task.latency.mean_ms"
    )
    assert latency.ranges_overlap is True
    assert latency.range_gap is None
    assert latency.per_seed_ordering_consistent is True
    assert latency.seeds_where_upper_exceeds_lower == 0


def test_an_inconsistent_ordering_is_reported_as_inconsistent() -> None:
    payload = _analysis()
    payload["secondary_descriptives"] = [
        _descriptive("cap-2.5", "task.latency.mean_ms", {"0": 100.0, "1": 400.0}),
        _descriptive("cap-1.0", "task.latency.mean_ms", {"0": 120.0, "1": 300.0}),
    ]

    report = build_mechanism_report(payload)

    latency = next(
        row for row in report.range_comparisons if row.metric_key == "task.latency.mean_ms"
    )
    assert latency.seeds_where_upper_exceeds_lower == 1
    assert latency.per_seed_ordering_consistent is False


def test_status_literals_cannot_be_widened_by_the_caller() -> None:
    report = _report()

    assert report.descriptive_non_causal is True
    assert report.exploratory is True
    assert report.confirmatory is False
    assert report.significance_claimed is False
    assert report.causal_claim is False
    assert report.research_status == "owner_approved_candidate"


def test_the_report_round_trips_and_is_deterministic() -> None:
    first = _report()
    second = _report()

    assert first == second
    assert first.fingerprint() == second.fingerprint()
    restored = CampaignMechanismReport.model_validate_json(first.model_dump_json())
    assert restored == first


def test_a_parsed_model_and_its_dict_produce_the_same_report() -> None:
    from traffictwin.integration.vec_campaign.analysis import VecCampaignAnalysis

    payload = _analysis()
    parsed = VecCampaignAnalysis.model_validate_json(json.dumps(payload))

    assert build_mechanism_report(parsed) == build_mechanism_report(payload)


def test_markdown_highlights_the_invariant_metric_and_states_its_status() -> None:
    rendered = render_mechanism_report_markdown(_report())

    assert "# Mechanism evidence — `synthetic-campaign`" in rendered
    assert "descriptive, non-causal, exploratory" in rendered
    assert "no causal claim" in rendered
    assert "Bit-identical across every arm within every seed: `task.offload.rate`" in rendered
    assert "`task.latency.mean_ms`" in rendered
    assert "| Metric | Seed | `cap-2.5` | `cap-1.0` |" in rendered
    # Deterministic bytes for the same input.
    assert rendered == render_mechanism_report_markdown(_report())


def test_markdown_marks_a_missing_arm_value_unavailable() -> None:
    payload = _analysis()
    payload["primary_descriptives"][1] = _descriptive(
        "cap-1.0", "tos.task.deadline_success.rate", {"0": 0.7901}
    )

    rendered = render_mechanism_report_markdown(build_mechanism_report(payload))

    assert "unavailable" in rendered
