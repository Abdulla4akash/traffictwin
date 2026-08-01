"""Decision-safety layer (post-v1 D-1, design §8 adversarial list).

The layer detects unsafe interpretation and refuses; it never picks. Tested
adversarially: ranking requests, lower-latency-is-better claims without
companions, Sparse-64 promotion, fabricated significance, envelope and
actor-range escapes, undisclosed deviations, causal wording, private
content, and the digest-pinned confirmed-capacity notice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.platform.decision_safety import (
    CONFIRMATORY_RECORD_PATH,
    DecisionOption,
    DecisionSafetyError,
    assess,
    assessment_to_json,
    confirmed_capacity_notice,
    ruleset_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _option(option_id: str = "opt-a", **overrides: object) -> DecisionOption:
    payload: dict[str, object] = {
        "option_id": option_id,
        "kind": "prediction",
        "source_digest": "a" * 64,
        "trace": "inc",
        "actor": "ukfleettrain_mappo_model_c_17",
        "capacity": 0.75,
        "inside_measured_envelope": True,
        "actor_capacity_measured": True,
        "support_count": 5,
        "interval_status": "available",
        "headline_improvement_claimed": False,
        "companions_present": (),
    }
    payload.update(overrides)
    return DecisionOption.model_validate(payload)


def test_a_presentable_assessment_carries_cautions_never_a_choice() -> None:
    assessment = assess((_option("opt-a"), _option("opt-b", capacity=2.5)))
    assert assessment.status == "presentable_with_cautions"
    assert assessment.recommendation is False
    assert assessment.evidence is False
    assert assessment.causal is False
    # Input order is preserved; nothing is sorted by any value.
    assert assessment.compatible_option_ids == ("opt-a", "opt-b")
    assert assessment.ruleset_digest == ruleset_digest()
    assert any(notice.code == "SMALL_SAMPLE_LIMIT" for notice in assessment.notices)
    assert "p=0.0625" in assessment_to_json(assessment)


def test_ranking_requests_are_forbidden_by_name() -> None:
    with pytest.raises(DecisionSafetyError) as excinfo:
        assess((_option(),), request_ranking=True)
    assert excinfo.value.code == "RECOMMENDATION_REQUEST_FORBIDDEN"
    with pytest.raises(DecisionSafetyError) as wording:
        assess((_option(wording="pick the best option for deployment"),))
    assert wording.value.code == "RECOMMENDATION_REQUEST_FORBIDDEN"


def test_lower_latency_needs_its_companions() -> None:
    with pytest.raises(DecisionSafetyError) as excinfo:
        assess(
            (
                _option(
                    headline_improvement_claimed=True,
                    companions_present=("deadline_attainment",),
                ),
            )
        )
    assert excinfo.value.code == "COMPANION_METRIC_MISSING"
    complete = assess(
        (
            _option(
                headline_improvement_claimed=True,
                companions_present=(
                    "deadline_attainment",
                    "action_change",
                    "failure_locus",
                ),
            ),
        )
    )
    assert complete.status == "presentable_with_cautions"


def test_non_admitted_inputs_and_mixed_standing_refuse() -> None:
    with pytest.raises(DecisionSafetyError) as promoted:
        assess((_option(), _option("sparse", kind="non_admitted")))
    assert promoted.value.code == "NON_ADMITTED_INPUT"
    with pytest.raises(DecisionSafetyError) as mixed:
        assess((_option(), _option("real", kind="admitted_analysis")))
    assert mixed.value.code == "INCOMPATIBLE_EVIDENCE"


def test_envelope_and_actor_range_escapes_are_excluded_with_reasons() -> None:
    assessment = assess(
        (
            _option("inside"),
            _option("outside", inside_measured_envelope=False),
            _option("baseline-deep", actor_capacity_measured=False),
            _option("thin", support_count=1),
        )
    )
    assert assessment.compatible_option_ids == ("inside",)
    assert "OUTSIDE_MEASURED_ENVELOPE" in assessment.exclusions["outside"]
    assert "ACTOR_CAPACITY_NOT_MEASURED" in assessment.exclusions["baseline-deep"]
    assert "SUPPORT_INSUFFICIENT" in assessment.exclusions["thin"]


def test_all_options_excluded_is_a_refused_status_not_an_empty_win() -> None:
    assessment = assess((_option("out", inside_measured_envelope=False),))
    assert assessment.status == "refused"
    assert assessment.compatible_option_ids == ()
    assert assessment.exclusions


def test_uncertainty_unavailable_is_not_zero_width() -> None:
    assessment = assess(
        (
            _option("with-interval", interval_status="zero_width"),
            _option("without", interval_status="unavailable"),
        )
    )
    unavailable = [
        notice for notice in assessment.notices if notice.code == "UNCERTAINTY_UNAVAILABLE"
    ]
    assert len(unavailable) == 1
    assert "without" in unavailable[0].text


def test_deviations_propagate_and_undisclosed_ones_refuse() -> None:
    assessment = assess((_option(execution_deviations=("cell retried after interruption",)),))
    assert any(notice.code == "EXECUTION_DEVIATION" for notice in assessment.notices)
    with pytest.raises(DecisionSafetyError) as excinfo:
        assess(
            (
                _option(
                    execution_deviations=("relaunch repeated the peak eval",),
                    deviations_disclosed=False,
                ),
            )
        )
    assert excinfo.value.code == "EXECUTION_DEVIATION_UNACKNOWLEDGED"


def test_causal_wording_and_private_content_refuse() -> None:
    with pytest.raises(DecisionSafetyError) as causal:
        assess((_option(wording="lower capacity causes better service"),))
    assert causal.value.code == "CAUSAL_WORDING_FORBIDDEN"
    with pytest.raises(DecisionSafetyError) as private:
        assess((_option(wording="see /Users/someone/secret.txt"),))
    assert private.value.code == "PRIVATE_CONTENT_DETECTED"


def test_the_confirmed_notice_is_digest_pinned() -> None:
    notice = confirmed_capacity_notice(REPO_ROOT)
    assert "8,310.9" in notice.text
    assert "[-9,097.5, -7,524.3]" in notice.text
    assert "p=0.0625" in notice.text
    assert "effectively flat" in notice.text
    assert "already-failed tasks" in notice.text
    assert "not a reason to degrade capacity" in notice.text
    assert (REPO_ROOT / CONFIRMATORY_RECORD_PATH).is_file()


def test_stale_or_missing_records_refuse_rather_than_reproduce(tmp_path: Path) -> None:
    with pytest.raises(DecisionSafetyError) as missing:
        confirmed_capacity_notice(tmp_path)
    assert missing.value.code == "INPUT_DIGEST_MISMATCH"
    stale_root = tmp_path / "stale"
    record = stale_root / CONFIRMATORY_RECORD_PATH
    record.parent.mkdir(parents=True)
    record.write_text("tampered", encoding="utf-8")
    with pytest.raises(DecisionSafetyError) as stale:
        confirmed_capacity_notice(stale_root)
    assert stale.value.code == "INPUT_DIGEST_MISMATCH"


def test_no_execution_surface_exists() -> None:
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "decision_safety.py").read_text(
        encoding="utf-8"
    )
    assert "subprocess" not in source
    assert "execute_campaign" not in source
