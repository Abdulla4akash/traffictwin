"""What-if composer (platform slice 3, design §2 guardrails + §5 test list).

Each guardrail in the design has a test here: draft-only (the executor is
never imported), held-out seed refusal, cite-only-committed rendering, the
``prediction_available: false`` path for refused scenarios, and budget
honesty. The worked example drafts the 3.3x inc scenario end-to-end and
checks its predeclaration against the structure of the actual signed pilot
predeclaration. Tests read only committed artifacts — never ``data/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import traffictwin.platform.whatif_composer as composer_module
from traffictwin.platform.outcome_predictor import (
    BASELINE_ACTOR,
    TRAINED_ACTOR,
    LoadedFit,
    load_outcome_predictor_fit,
)
from traffictwin.platform.whatif_composer import (
    DRAFT_BANNER,
    HELD_OUT_SEEDS,
    TRACE_EXECUTION_SPECS,
    ComposerForm,
    WhatifComposerError,
    compose_from_natural_language,
    compose_scenario,
    llm_socket_status,
    render_honesty_exhibit,
    render_prediction_card,
    render_result_card,
    verify_card_numbers,
    write_draft,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIT_ARTIFACT = REPO_ROOT / "docs" / "platform" / "outcome_predictor_fit.json"
PILOT_PREDECLARATION = (
    REPO_ROOT / "docs" / "evaluation" / "capacity_squeeze_pilot_predeclaration.md"
)

GENERATED_AT = "2026-08-01T18:00:00+00:00"


@pytest.fixture(scope="module")
def loaded() -> LoadedFit:
    return load_outcome_predictor_fit(FIT_ARTIFACT)


def _form(
    trace: str = "inc",
    capacity: float | None = 0.75,
    *,
    reduce_factor: float | None = None,
    actor: str = TRAINED_ACTOR,
    fleet_seeds: tuple[int, ...] = (0, 1, 2),
    comparison_capacity: float | None = None,
) -> ComposerForm:
    return ComposerForm(
        trace=trace,
        capacity=capacity,
        reduce_factor=reduce_factor,
        actor=actor,
        fleet_seeds=fleet_seeds,
        comparison_capacity=comparison_capacity,
    )


# --- guardrail: draft-only ---------------------------------------------------


def test_the_executor_is_never_imported_or_referenced() -> None:
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "whatif_composer.py").read_text(
        encoding="utf-8"
    )
    assert "execute_campaign" not in source
    assert "vec_campaign.service" not in source
    assert not hasattr(composer_module, "execute_campaign")


# --- guardrail: seed protection ----------------------------------------------


def test_held_out_seeds_are_refused_in_any_mixture(loaded: LoadedFit) -> None:
    for seeds in ((10, 11, 12), (0, 1, 10), (0, 1, 2, 14)):
        with pytest.raises(WhatifComposerError) as excinfo:
            compose_scenario(_form(fleet_seeds=seeds), loaded, generated_at_utc=GENERATED_AT)
        assert excinfo.value.code == "COMPOSER_HELD_OUT_REFUSED"
    assert frozenset({10, 11, 12, 13, 14}) == HELD_OUT_SEEDS


# --- form validation ---------------------------------------------------------


def test_the_form_takes_exactly_one_capacity_expression() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        _form(capacity=1.0, reduce_factor=2.0)
    with pytest.raises(ValueError, match="exactly one"):
        _form(capacity=None)
    reduced = _form(capacity=None, reduce_factor=2.5)
    assert reduced.requested_capacity == pytest.approx(1.0)


def test_composer_refuses_identical_arms_and_bad_seed_sets(loaded: LoadedFit) -> None:
    with pytest.raises(WhatifComposerError) as identical:
        compose_scenario(_form(capacity=2.5), loaded, generated_at_utc=GENERATED_AT)
    assert identical.value.code == "COMPOSER_ARMS_IDENTICAL"
    with pytest.raises(WhatifComposerError) as short:
        compose_scenario(_form(fleet_seeds=(0, 1)), loaded, generated_at_utc=GENERATED_AT)
    assert short.value.code == "COMPOSER_SEEDS_INSUFFICIENT"
    with pytest.raises(WhatifComposerError) as duplicated:
        compose_scenario(_form(fleet_seeds=(0, 1, 1)), loaded, generated_at_utc=GENERATED_AT)
    assert duplicated.value.code == "COMPOSER_SEEDS_DUPLICATED"
    with pytest.raises(WhatifComposerError) as unknown:
        compose_scenario(_form(trace="berlin"), loaded, generated_at_utc=GENERATED_AT)
    assert unknown.value.code == "COMPOSER_TRACE_UNKNOWN"


# --- the worked example (design §5 integration) ------------------------------


def test_worked_example_drafts_the_pilot_squeeze_end_to_end(loaded: LoadedFit) -> None:
    draft = compose_scenario(_form(), loaded, generated_at_utc=GENERATED_AT)
    assert draft.prediction_available
    assert draft.prediction is not None
    assert draft.prediction.regime == "saturated"
    assert draft.fit_digest == loaded.digest

    design = draft.design_draft
    assert design["status"] == "DRAFT_UNSIGNED"
    assert design["trace_sha256"] == TRACE_EXECUTION_SPECS["inc"].trace_sha256
    assert design["max_steps"] == 3600
    baseline = design["baseline_arm"]
    variation = design["variation_arms"]
    assert isinstance(baseline, dict)
    assert isinstance(variation, list)
    assert baseline["label"] == "cap-2.5"
    assert variation[0]["label"] == "cap-0.75"
    assert design["fleet_seeds"] == [0, 1, 2]
    approval = design["approval"]
    assert isinstance(approval, dict)
    assert approval["status"] == "UNSIGNED"
    assert "approved_by" not in approval

    # The drafted predeclaration mirrors the structure of the ACTUAL signed
    # pilot predeclaration: the house sections appear in both documents.
    pilot_text = PILOT_PREDECLARATION.read_text(encoding="utf-8")
    for heading in (
        "Question and hypothesis",
        "What the evaluator control actually means",
        "Fixed factors",
        "Arms and pairing",
        "Endpoints",
        "Analysis plan, fixed before results",
        "Interpretation limits binding on any output",
    ):
        assert heading in draft.predeclaration_markdown
        assert heading in pilot_text
    assert DRAFT_BANNER in draft.predeclaration_markdown
    assert "Sign-off (EMPTY" in draft.predeclaration_markdown


def test_a_real_design_cannot_be_built_from_the_draft_without_a_human(
    loaded: LoadedFit,
) -> None:
    from pydantic import ValidationError

    from traffictwin.integration.vec_campaign.models import (
        VecCampaignApproval,
    )

    draft = compose_scenario(_form(), loaded, generated_at_utc=GENERATED_AT)
    assert draft.design_draft["approval"] == {
        "status": "UNSIGNED",
        "note": draft.design_draft["approval"]["note"],  # type: ignore[index]
    }
    # The instrument's approval model refuses placeholder identities, so the
    # unsigned draft cannot be promoted by an agent filling in a placeholder.
    with pytest.raises(ValidationError):
        VecCampaignApproval(
            predeclaration_path="docs/evaluation/drafts/x.md",
            predeclaration_sha256="0" * 64,
            approved_by="TBD",
            approved_role="agent",
            approved_at_utc=GENERATED_AT,
            held_out_authorised=False,
        )


# --- guardrail: no silent envelope escape ------------------------------------


def test_a_refused_scenario_is_still_draftable_with_the_refusal_embedded(
    loaded: LoadedFit,
) -> None:
    draft = compose_scenario(_form(capacity=3.0), loaded, generated_at_utc=GENERATED_AT)
    assert not draft.prediction_available
    assert draft.prediction is None
    assert draft.prediction_refusal is not None
    assert draft.prediction_refusal.code == "CAPACITY_OUT_OF_ENVELOPE"
    assert "prediction_available: false" in draft.predeclaration_markdown
    assert "CAPACITY_OUT_OF_ENVELOPE" in draft.predeclaration_markdown
    assert "MEASUREMENT" in draft.predeclaration_markdown
    baseline_actor_draft = compose_scenario(
        _form(trace="we", capacity=1.0, actor=BASELINE_ACTOR),
        loaded,
        generated_at_utc=GENERATED_AT,
    )
    assert not baseline_actor_draft.prediction_available
    assert baseline_actor_draft.prediction_refusal is not None
    assert baseline_actor_draft.prediction_refusal.code == "ACTOR_NOT_MEASURED"


# --- guardrail: budget honesty -----------------------------------------------


def test_drafted_budgets_embed_the_measured_per_cell_cost(loaded: LoadedFit) -> None:
    draft = compose_scenario(_form(), loaded, generated_at_utc=GENERATED_AT)
    assert draft.cost.per_cell_seconds == pytest.approx(3555.96)
    assert "measured" in draft.cost.per_cell_seconds_provenance
    assert draft.cost.cells == 6
    assert draft.cost.total_seconds == pytest.approx(6 * 3555.96)
    assert str(draft.cost.per_cell_seconds) in json.dumps(draft.design_draft)
    ev_draft = compose_scenario(
        _form(trace="ev", capacity=1.0), loaded, generated_at_utc=GENERATED_AT
    )
    assert ev_draft.cost.per_cell_seconds == pytest.approx(265.9)
    wd_draft = compose_scenario(
        _form(trace="wd_am", capacity=1.0), loaded, generated_at_utc=GENERATED_AT
    )
    assert "ESTIMATE" in wd_draft.cost.per_cell_seconds_provenance


# --- guardrail: cite-only-committed ------------------------------------------


def _analysis_payload() -> dict[str, object]:
    return {
        "experiment_id": "vec-example",
        "campaign_status": "completed",
        "research_status": "owner_approved_candidate",
        "primary_descriptives": [
            {
                "arm_label": "cap-2.5",
                "metric_key": "tos.task.deadline_success.rate",
                "seed_values": {"0": 0.7924845945705774, "1": 0.8127939588722564},
                "mean": 0.8026392767214169,
                "minimum": 0.7924845945705774,
                "maximum": 0.8127939588722564,
            }
        ],
        "secondary_descriptives": [],
        "comparisons": [{"variation_label": "cap-0.75", "mean_paired_difference": -8310.9}],
    }


def test_result_card_cites_only_numbers_in_the_analysis(tmp_path: Path) -> None:
    path = tmp_path / "campaign_analysis.json"
    path.write_text(json.dumps(_analysis_payload()), encoding="utf-8")
    card = render_result_card(path)
    assert "0.8026392767214169" in card
    assert "-8310.9" in card
    assert "MEASURED — committed campaign analysis" in card
    assert "sha256" in card


def test_an_invented_number_is_a_typed_failure_not_a_card(tmp_path: Path) -> None:
    path = tmp_path / "campaign_analysis.json"
    path.write_text(json.dumps(_analysis_payload()), encoding="utf-8")
    card = render_result_card(path)
    with pytest.raises(WhatifComposerError) as excinfo:
        verify_card_numbers(card + "\n- invented improvement: 99.999", path.read_text())
    assert excinfo.value.code == "CARD_NUMBER_NOT_IN_ANALYSIS"


def test_result_card_refuses_a_file_without_descriptives(tmp_path: Path) -> None:
    path = tmp_path / "not_an_analysis.json"
    path.write_text(json.dumps({"anything": 1}), encoding="utf-8")
    with pytest.raises(WhatifComposerError) as excinfo:
        render_result_card(path)
    assert excinfo.value.code == "ANALYSIS_INVALID"


def test_honesty_exhibit_pairs_prediction_with_measurement(
    loaded: LoadedFit, tmp_path: Path
) -> None:
    from traffictwin.platform.outcome_predictor import VecScenario, predict

    path = tmp_path / "campaign_analysis.json"
    path.write_text(json.dumps(_analysis_payload()), encoding="utf-8")
    outcome = predict(VecScenario(trace="inc", capacity=2.5, actor=TRAINED_ACTOR), loaded)
    exhibit = render_honesty_exhibit(outcome, path)
    assert "PREDICTION — NOT EVIDENCE" in exhibit
    assert "MEASURED — committed campaign analysis" in exhibit


# --- the tier-1 card ---------------------------------------------------------


def test_prediction_card_banners_and_refusal_card_names_the_gap(
    loaded: LoadedFit,
) -> None:
    from traffictwin.platform.outcome_predictor import VecScenario, predict

    record = predict(VecScenario(trace="we", capacity=1.0, actor=TRAINED_ACTOR), loaded)
    card = render_prediction_card(record)
    assert card.startswith("**PREDICTION — NOT EVIDENCE**")
    assert "unavailable" in card
    refusal = predict(
        VecScenario(trace="inc", capacity=1.0, actor=TRAINED_ACTOR, fleet_size=1216),
        loaded,
    )
    refusal_card = render_prediction_card(refusal)
    assert "DENSITY_GAP" in refusal_card
    assert "close it" in refusal_card


# --- drafts on disk ----------------------------------------------------------


def test_write_draft_lands_dated_bannered_files(loaded: LoadedFit, tmp_path: Path) -> None:
    draft = compose_scenario(_form(), loaded, generated_at_utc=GENERATED_AT)
    design_path, predeclaration_path = write_draft(draft, tmp_path)
    assert design_path.parent == tmp_path / "docs" / "evaluation" / "drafts"
    assert design_path.name == "whatif_inc_cap0p75_20260801_design_draft.json"
    assert predeclaration_path.name == "whatif_inc_cap0p75_20260801_predeclaration_draft.md"
    payload = json.loads(design_path.read_text(encoding="utf-8"))
    assert payload["status"] == "DRAFT_UNSIGNED"
    assert DRAFT_BANNER in predeclaration_path.read_text(encoding="utf-8")


# --- the dormant LLM socket --------------------------------------------------


def test_the_llm_socket_is_dormant_and_typed(loaded: LoadedFit) -> None:
    del loaded
    with pytest.raises(WhatifComposerError) as excinfo:
        compose_from_natural_language("what if capacity halves on the incident trace?")
    assert excinfo.value.code == "LLM_SOCKET_DORMANT"
    status = llm_socket_status()
    assert status["available"] is False
    assert status["mode"] == "template"
