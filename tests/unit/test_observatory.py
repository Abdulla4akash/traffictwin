"""Mechanism and policy observatory (post-v1 O-1, design §6 verification).

Golden pins for the five-fact headline and its wording; negative tests for
Sparse-64 promotion, role mixing, incompatible actors, fabricated
significance, forbidden language, and rendering latency without its
companions. The observatory recalculates nothing and upgrades nothing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.platform.observatory import (
    ConfirmedHeadlineCard,
    ObservatoryBundle,
    ObservatoryError,
    SourceBinding,
    build_observatory_bundle,
    bundle_to_json,
    compare_actors,
    compare_roles,
    render_headline,
    select_mechanism_cards,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_BINDING = SourceBinding(path="docs/example.md", sha256="a" * 64)


@pytest.fixture(scope="module")
def bundle() -> ObservatoryBundle:
    return build_observatory_bundle(REPO_ROOT)


def test_the_headline_golden_pins_all_five_facts(bundle: ObservatoryBundle) -> None:
    card = bundle.headline
    assert card.mean_latency_delta_ms == -8310.9
    assert card.bootstrap_low_ms == -9097.5
    assert card.bootstrap_high_ms == -7524.3
    assert card.unanimous_direction is True
    assert "p=0.0625" in card.sign_test_wording
    assert "conventional significance is not claimed" in card.sign_test_wording
    assert "flat" in card.deadline_attainment_fact
    assert "already-failed" in card.locus_fact
    for binding in card.sources:
        assert (REPO_ROOT / binding.path).is_file()


def test_rendered_headline_carries_every_companion(bundle: ObservatoryBundle) -> None:
    rendered = render_headline(bundle)
    assert "-8310.9" in rendered
    assert "[-9097.5, -7524.3]" in rendered
    assert "p=0.0625" in rendered
    assert "flat" in rendered
    assert "already-failed" in rendered
    assert "bit-identical" in rendered
    assert "producer_citation_requirements.md" in rendered
    # Fabricated significance never appears.
    assert "significant" not in rendered.replace("significance is not claimed", "")


def test_missing_companions_refuse_at_the_model_boundary() -> None:
    with pytest.raises(ValidationError, match="sign-test floor"):
        ConfirmedHeadlineCard(
            mean_latency_delta_ms=-8310.9,
            bootstrap_low_ms=-9097.5,
            bootstrap_high_ms=-7524.3,
            unanimous_direction=True,
            sign_test_wording="looks unanimous",
            deadline_attainment_fact="deadline attainment was effectively flat",
            locus_fact="inside already-failed tasks",
            sources=(_BINDING,),
        )


def test_forbidden_language_refuses_anywhere_in_a_card() -> None:
    with pytest.raises(ValidationError, match="must not carry the term"):
        ConfirmedHeadlineCard(
            mean_latency_delta_ms=-8310.9,
            bootstrap_low_ms=-9097.5,
            bootstrap_high_ms=-7524.3,
            unanimous_direction=True,
            sign_test_wording="p=0.0625; conventional significance is not claimed",
            deadline_attainment_fact="effectively flat",
            locus_fact="inside already-failed tasks; the causal story is settled",
            sources=(_BINDING,),
        )


def test_roles_never_pool_and_the_appendix_never_promotes(
    bundle: ObservatoryBundle,
) -> None:
    with pytest.raises(ObservatoryError) as mixed:
        compare_roles(bundle, "protocol_confirmed", "post_hoc")
    assert mixed.value.code == "EVIDENCE_ROLE_MIXED"
    confirmed = compare_roles(bundle, "protocol_confirmed", "protocol_confirmed")
    assert all(card.evidence_role == "protocol_confirmed" for card in confirmed)
    with pytest.raises(ObservatoryError) as promoted:
        select_mechanism_cards(bundle, evidence_role="post_hoc", include_non_admitted_appendix=True)
    assert promoted.value.code == "NON_ADMITTED_PROMOTION"
    appendix = select_mechanism_cards(
        bundle, evidence_role="descriptive", include_non_admitted_appendix=True
    )
    assert any(card.card_id == "sparse64-appendix" for card in appendix)
    default_view = select_mechanism_cards(bundle)
    assert not any(card.card_id == "sparse64-appendix" for card in default_view)


def test_the_withdrawn_rsu_attribution_stays_a_first_class_limitation(
    bundle: ObservatoryBundle,
) -> None:
    placement = next(card for card in bundle.mechanism_cards if card.card_id == "rsu-placement")
    assert any("WITHDRAWN" in limitation for limitation in placement.limitations)
    assert placement.evidence_role == "exploratory"


def test_policy_contracts_answer_the_capacity_question(
    bundle: ObservatoryBundle,
) -> None:
    for card in bundle.policy_contracts:
        assert card.rsu_capacity_in_observation is False
    comparison = compare_actors(bundle, "ukfleettrain_mappo", "baseline")
    assert "+6.09 pp" in comparison
    assert "preset mismatch" in comparison
    with pytest.raises(ObservatoryError) as excinfo:
        compare_actors(bundle, "ukfleettrain_mappo", "some_new_actor")
    assert excinfo.value.code == "INCOMPATIBLE_ACTORS"


def test_every_card_binds_committed_sources_and_builds_deterministically(
    bundle: ObservatoryBundle,
) -> None:
    for card in (*bundle.mechanism_cards, *bundle.appendix_non_admitted):
        assert card.limitations
        for binding in card.sources:
            assert (REPO_ROOT / binding.path).is_file()
    again = build_observatory_bundle(REPO_ROOT)
    assert bundle_to_json(again) == bundle_to_json(bundle)
    assert again.bundle_digest == bundle.bundle_digest
    assert bundle.studies[0].admission_status == "admitted"
    assert bundle.coherence_checks[0].state == "supported"
    assert set(bundle.coherence_checks[0].required_metrics) == set(
        bundle.coherence_checks[0].present_metrics
    )


def test_missing_sources_refuse(tmp_path: Path) -> None:
    with pytest.raises(ObservatoryError) as excinfo:
        build_observatory_bundle(tmp_path)
    assert excinfo.value.code == "SOURCE_DIGEST_MISMATCH"


def test_changed_source_bytes_refuse_instead_of_rendering_stale_numbers(tmp_path: Path) -> None:
    source = REPO_ROOT / "docs/evaluation/capacity_confirmatory_results_20260728.md"
    target = tmp_path / "docs/evaluation/capacity_confirmatory_results_20260728.md"
    target.parent.mkdir(parents=True)
    shutil.copyfile(source, target)
    target.write_text(target.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
    with pytest.raises(ObservatoryError) as excinfo:
        build_observatory_bundle(tmp_path)
    assert excinfo.value.code == "SOURCE_DIGEST_MISMATCH"


def test_nothing_is_recalculated_in_this_module() -> None:
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "observatory.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("statistics.", "numpy", "bootstrap(", "percentile("):
        assert forbidden not in source
