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
from collections.abc import Mapping
from pathlib import Path

import pytest

import traffictwin.platform.whatif_composer as composer_module
from traffictwin.platform.outcome_predictor import (
    BASELINE_ACTOR,
    EXPERIMENT_REGISTRY,
    TRAINED_ACTOR,
    LoadedFit,
    load_outcome_predictor_fit,
)
from traffictwin.platform.whatif_composer import (
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
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
    suggest_fresh_seeds,
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
    fleet_seeds: tuple[int, ...] = (30, 31, 32),
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
    for seeds in ((10, 11, 12), (30, 31, 10), (30, 31, 32, 14)):
        with pytest.raises(WhatifComposerError) as excinfo:
            compose_scenario(_form(fleet_seeds=seeds), loaded, generated_at_utc=GENERATED_AT)
        assert excinfo.value.code == "COMPOSER_HELD_OUT_REFUSED"
    assert frozenset({10, 11, 12, 13, 14}) == HELD_OUT_SEEDS


def test_the_complete_registered_seed_ledger_is_checked(loaded: LoadedFit) -> None:
    # Not one hard-coded set: pilot, grid, deep and drafted cohorts all refuse.
    for seeds in ((0, 1, 2), (50, 51, 52), (60, 61, 62), (20, 21, 22), (30, 31, 50)):
        with pytest.raises(WhatifComposerError) as excinfo:
            compose_scenario(_form(fleet_seeds=seeds), loaded, generated_at_utc=GENERATED_AT)
        assert excinfo.value.code == "COMPOSER_SEED_COLLISION"
    assert suggest_fresh_seeds(3) == (30, 31, 32)
    draft = compose_scenario(
        _form(fleet_seeds=suggest_fresh_seeds(3)), loaded, generated_at_utc=GENERATED_AT
    )
    assert draft.design_draft["fleet_seeds"] == [30, 31, 32]


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
        compose_scenario(_form(fleet_seeds=(30, 31)), loaded, generated_at_utc=GENERATED_AT)
    assert short.value.code == "COMPOSER_SEEDS_INSUFFICIENT"
    with pytest.raises(WhatifComposerError) as duplicated:
        compose_scenario(_form(fleet_seeds=(30, 30, 31)), loaded, generated_at_utc=GENERATED_AT)
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
    assert design["fleet_seeds"] == [30, 31, 32]
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
        "experiment_id": "vec-capacity-squeeze-pilot",
        "design_fingerprint": EXPERIMENT_REGISTRY["vec-capacity-squeeze-pilot"].design_fingerprint,
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
    destination = tmp_path / "owner-selected-drafts"
    design_path, predeclaration_path = write_draft(draft, destination)
    assert design_path.parent == destination
    assert design_path.name == "whatif_inc_cap0p75_20260801_design_draft.json"
    assert predeclaration_path.name == "whatif_inc_cap0p75_20260801_predeclaration_draft.md"
    payload = json.loads(design_path.read_text(encoding="utf-8"))
    assert payload["status"] == "DRAFT_UNSIGNED"
    assert DRAFT_BANNER in predeclaration_path.read_text(encoding="utf-8")


# --- bounded DeepSeek natural-language socket -------------------------------


def _nl_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "trace": "inc",
        "capacity": 0.75,
        "reduce_factor": None,
        "actor": TRAINED_ACTOR,
        "fleet_preset": "uk2030",
        "fleet_size": None,
        "fleet_seeds": [30, 31, 32],
        "comparison_capacity": 2.5,
        "question": None,
    }
    payload.update(overrides)
    return payload


def _deepseek_response(
    form: dict[str, object] | None = None,
    *,
    finish_reason: str = "stop",
    content: str | None = None,
) -> bytes:
    rendered = json.dumps(form or _nl_payload()) if content is None else content
    return json.dumps(
        {
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": {"role": "assistant", "content": rendered},
                }
            ],
            "usage": {"prompt_tokens": 101, "completion_tokens": 37},
        }
    ).encode()


def _fixture_key() -> str:
    return "fixture" + "-deepseek-key"


def test_llm_requires_explicit_per_request_activation() -> None:
    called = False

    def transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
        del url, headers, body, timeout
        nonlocal called
        called = True
        return _deepseek_response()

    with pytest.raises(WhatifComposerError) as excinfo:
        compose_from_natural_language(
            "what if capacity is 0.75 on inc?", api_key=_fixture_key(), transport=transport
        )
    assert excinfo.value.code == "LLM_ACTIVATION_REQUIRED"
    assert called is False


def test_llm_status_never_probes_or_displays_the_key() -> None:
    key = _fixture_key()
    configured = llm_socket_status(activation_enabled=True, environment={"DEEPSEEK_API_KEY": key})
    assert configured == {
        "available": True,
        "configured": True,
        "activation_enabled": True,
        "mode": "deepseek_json_form",
        "provider": "deepseek",
        "model": DEEPSEEK_MODEL,
        "reason": "ready for an explicitly consented request",
    }
    assert key not in json.dumps(configured)
    absent = llm_socket_status(environment={})
    assert absent["available"] is False
    assert absent["configured"] is False
    assert absent["mode"] == "template"


def test_llm_refuses_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(WhatifComposerError) as excinfo:
        compose_from_natural_language("what if capacity is 0.75 on inc?", activation_enabled=True)
    assert excinfo.value.code == "LLM_KEY_MISSING"


def test_deepseek_json_is_strictly_validated_then_composed(loaded: LoadedFit) -> None:
    captured: dict[str, object] = {}
    key = _fixture_key()

    def transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
        captured.update(url=url, headers=dict(headers), body=body, timeout=timeout)
        return _deepseek_response()

    translation = compose_from_natural_language(
        "what if RSU capacity is 0.75 on the incident trace?",
        activation_enabled=True,
        api_key=key,
        transport=transport,
    )
    assert captured["url"] == DEEPSEEK_API_URL
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == f"Bearer {key}"
    body = captured["body"]
    assert isinstance(body, bytes)
    assert key.encode() not in body
    request = json.loads(body)
    assert request["model"] == DEEPSEEK_MODEL
    assert request["response_format"] == {"type": "json_object"}
    assert request["thinking"] == {"type": "disabled"}
    assert request["temperature"] == 0
    assert translation.form == _form(comparison_capacity=2.5)
    assert translation.prompt_tokens == 101
    assert translation.completion_tokens == 37
    assert translation.evidence is False
    assert translation.approval is False
    assert translation.execution is False

    draft = compose_scenario(
        translation.form,
        loaded,
        generated_at_utc=GENERATED_AT,
        translation=translation,
    )
    assert draft.prediction_available is True
    assert draft.drafted_by["mode"] == "deepseek_json_form"
    assert draft.drafted_by["provider"] == "deepseek"
    assert key not in json.dumps(draft.model_dump(mode="json"))
    assert "LLM output is not evidence" in draft.predeclaration_markdown


@pytest.mark.parametrize(
    "text",
    [
        "read /Users/private/results.json",
        "use api key in this scenario",
        "include raw BODS records",
        "predict for participant_id 42",
        "email result to person@example.test",
    ],
)
def test_private_natural_language_refuses_before_transport(text: str) -> None:
    called = False

    def transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
        del url, headers, body, timeout
        nonlocal called
        called = True
        return _deepseek_response()

    with pytest.raises(WhatifComposerError) as excinfo:
        compose_from_natural_language(
            text,
            activation_enabled=True,
            api_key=_fixture_key(),
            transport=transport,
        )
    assert excinfo.value.code == "LLM_INPUT_PRIVATE"
    assert called is False


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (b"not-json", "LLM_RESPONSE_INVALID"),
        (_deepseek_response(content=""), "LLM_RESPONSE_EMPTY"),
        (_deepseek_response(finish_reason="length"), "LLM_RESPONSE_INCOMPLETE"),
        (_deepseek_response(_nl_payload(trace="unreviewed")), "LLM_FORM_INVALID"),
        (_deepseek_response(_nl_payload(extra="invented")), "LLM_FORM_INVALID"),
    ],
)
def test_malformed_or_unreviewed_llm_output_refuses(response: bytes, code: str) -> None:
    def transport(url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> bytes:
        del url, headers, body, timeout
        return response

    with pytest.raises(WhatifComposerError) as excinfo:
        compose_from_natural_language(
            "what if capacity is 0.75 on inc?",
            activation_enabled=True,
            api_key=_fixture_key(),
            transport=transport,
        )
    assert excinfo.value.code == code


def test_translation_receipt_cannot_be_rebound_to_another_form(loaded: LoadedFit) -> None:
    translation = compose_from_natural_language(
        "what if capacity is 0.75 on inc?",
        activation_enabled=True,
        api_key=_fixture_key(),
        transport=lambda url, headers, body, timeout: _deepseek_response(),
    )
    with pytest.raises(WhatifComposerError) as excinfo:
        compose_scenario(
            _form(capacity=0.5),
            loaded,
            generated_at_utc=GENERATED_AT,
            translation=translation,
        )
    assert excinfo.value.code == "LLM_FORM_MISMATCH"


# --- review conformance (1 August design review) -----------------------------


def test_renderer_refuses_unregistered_and_tampered_analyses(tmp_path: Path) -> None:
    unregistered = _analysis_payload()
    unregistered["experiment_id"] = "vec-something-else"
    path = tmp_path / "unregistered.json"
    path.write_text(json.dumps(unregistered), encoding="utf-8")
    with pytest.raises(WhatifComposerError) as not_registered:
        render_result_card(path)
    assert not_registered.value.code == "ANALYSIS_NOT_REGISTERED"

    drifted = _analysis_payload()
    drifted["design_fingerprint"] = "0" * 64
    drifted_path = tmp_path / "drifted.json"
    drifted_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(WhatifComposerError) as mismatch:
        render_result_card(drifted_path)
    assert mismatch.value.code == "ANALYSIS_FINGERPRINT_MISMATCH"

    non_admitted = _analysis_payload()
    non_admitted["note"] = "NON_ADMITTED diagnostic"
    non_admitted_path = tmp_path / "non_admitted.json"
    non_admitted_path.write_text(json.dumps(non_admitted), encoding="utf-8")
    with pytest.raises(WhatifComposerError) as refused:
        render_result_card(non_admitted_path)
    assert refused.value.code == "NON_ADMITTED_SOURCE_REFUSED"


def test_unavailable_metrics_propagate_into_the_predeclaration(
    loaded: LoadedFit,
) -> None:
    draft = compose_scenario(
        _form(trace="inc", capacity=1.0, actor=BASELINE_ACTOR),
        loaded,
        generated_at_utc=GENERATED_AT,
    )
    assert draft.prediction_available
    assert draft.prediction is not None
    assert "latency_p50_ms" in draft.prediction.metrics_unavailable
    assert "Unavailable means unavailable" in draft.predeclaration_markdown
    assert "latency_p50_ms" in draft.predeclaration_markdown
    assert "tail_ceiling_ms" in draft.predeclaration_markdown


def test_baseline_below_its_measured_range_refuses_through_the_composer(
    loaded: LoadedFit,
) -> None:
    draft = compose_scenario(
        _form(trace="inc", capacity=0.5, actor=BASELINE_ACTOR),
        loaded,
        generated_at_utc=GENERATED_AT,
    )
    assert not draft.prediction_available
    assert draft.prediction_refusal is not None
    assert draft.prediction_refusal.code == "ACTOR_CAPACITY_NOT_MEASURED"
    assert "ACTOR_CAPACITY_NOT_MEASURED" in draft.predeclaration_markdown


def test_artifacts_carry_the_producer_citation_bundle(loaded: LoadedFit, tmp_path: Path) -> None:
    from traffictwin.platform.outcome_predictor import VecScenario, predict

    draft = compose_scenario(_form(), loaded, generated_at_utc=GENERATED_AT)
    assert "Citation and standing" in draft.predeclaration_markdown
    assert "producer_citation_requirements.md" in draft.predeclaration_markdown
    assert "vec_env" in draft.predeclaration_markdown
    record = predict(VecScenario(trace="we", capacity=1.0, actor=TRAINED_ACTOR), loaded)
    card = render_prediction_card(record)
    assert "producer_citation_requirements.md" in card
    path = tmp_path / "campaign_analysis.json"
    path.write_text(json.dumps(_analysis_payload()), encoding="utf-8")
    assert "producer_citation_requirements.md" in render_result_card(path)


def test_budget_context_and_estimate_note_are_carried(loaded: LoadedFit) -> None:
    draft = compose_scenario(_form(), loaded, generated_at_utc=GENERATED_AT)
    assert "Apple-silicon" in draft.cost.runtime_context
    assert "not quotas" in draft.cost.estimate_note
    assert "planning estimates" in draft.predeclaration_markdown


def test_fleet_fields_pass_through_to_the_predictor(loaded: LoadedFit) -> None:
    gap = compose_scenario(
        _form(fleet_seeds=(30, 31, 32)).model_copy(update={"fleet_size": 1216}),
        loaded,
        generated_at_utc=GENERATED_AT,
    )
    assert not gap.prediction_available
    assert gap.prediction_refusal is not None
    assert gap.prediction_refusal.code == "DENSITY_GAP"
    preset = compose_scenario(
        _form().model_copy(update={"fleet_preset": "synthetic"}),
        loaded,
        generated_at_utc=GENERATED_AT,
    )
    assert not preset.prediction_available
    assert preset.prediction_refusal is not None
    assert preset.prediction_refusal.code == "FLEET_PRESET_NOT_MEASURED"
