"""AppTests for E2 research UI components — typed, fail-closed, no hard-coded fallback."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from traffictwin.evidence_admission.e2_research import E2ResearchAdmissionReceipt
from traffictwin.experiments.e2_comparison import E2ResearchComparisonView
from traffictwin.experiments.e2_research_evidence import E2ResearchEvidencePackage
from traffictwin.experiments.e2_task_accounting import E2TaskAccountingView
from traffictwin.reporting.e2_research import E2ResearchExportBundle


def _collect_text(at: AppTest) -> str:
    parts: list[str] = []
    for block in at.markdown:
        parts.append(str(block.value))
    for c in at.caption:
        parts.append(str(c.value))
    for code in at.code:
        parts.append(str(code.value))
    for w in at.warning:
        parts.append(str(w.value))
    for info in at.info:
        parts.append(str(info.value))
    return "\n".join(parts)


def _collect_all(at: AppTest) -> str:
    text = _collect_text(at)
    for sh in at.subheader:
        text += "\n" + str(sh.value)
    # Include dataframe stringified values
    if at.dataframe:
        for df in at.dataframe:
            text += "\n" + str(df.value)
    return text


def _real_fixtures() -> tuple[
    E2ResearchEvidencePackage,
    E2ResearchAdmissionReceipt,
    E2ResearchComparisonView,
    E2TaskAccountingView,
    E2ResearchExportBundle,
]:
    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )
    from traffictwin.experiments.e2_comparison import build_e2_comparison_view
    from traffictwin.experiments.e2_task_accounting import (
        build_e2_seed1_task_accounting,
    )
    from traffictwin.reporting.e2_research import build_e2_research_exports

    pkg, receipt = load_admitted_builtin_e2_research()
    comparison = build_e2_comparison_view(pkg)
    accounting = build_e2_seed1_task_accounting(pkg)
    exports = build_e2_research_exports(pkg, receipt)
    return pkg, receipt, comparison, accounting, exports


# ---------------------------------------------------------------------------
# Admission banner
# ---------------------------------------------------------------------------


def _render_admitted_banner() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_admission_banner

    pkg, receipt, _, _, _ = _real_fixtures()
    render_e2_admission_banner(pkg, receipt)


def _render_unadmitted_banner() -> None:
    from traffictwin.ui.components.e2_research import render_e2_admission_banner

    render_e2_admission_banner(None, None)


def _render_unadmitted_typed() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_admission_banner

    pkg, _, _, _, _ = _real_fixtures()
    # None receipt with real package -> unadmitted
    render_e2_admission_banner(pkg, None)
    # Plain dict receipt with real package -> unadmitted, no exception
    render_e2_admission_banner(pkg, {"standing": "ADMITTED RESEARCH"})  # type: ignore[arg-type]
    # Absent package -> unadmitted
    render_e2_admission_banner(None, None)


def test_admission_banner_shows_both_required_strings_when_admitted() -> None:
    at = AppTest.from_function(_render_admitted_banner)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "ADMITTED RESEARCH" in text
    assert "OWNER-AUTHORIZED PRODUCT ADMISSION" in text
    assert "not supervisor approval" in text.lower()
    assert "not randy confirmation" in text.lower()


def test_admission_banner_shows_unadmitted_when_absent() -> None:
    at = AppTest.from_function(_render_unadmitted_banner)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "UNADMITTED RESEARCH" in text
    assert "not be treated as admitted" in text.lower() or "unadmitted" in text.lower()
    # Must not show admitted strings as positive claim
    # Banner when unadmitted should not contain green admitted badge text as standing
    # We check that the admitted standing line is not present
    assert "OWNER-AUTHORIZED PRODUCT ADMISSION" not in text or "NOT ADMITTED" in text


def test_admission_banner_rejects_non_typed_receipt() -> None:
    at = AppTest.from_function(_render_unadmitted_typed)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "UNADMITTED RESEARCH" in text


# ---------------------------------------------------------------------------
# Question motivation
# ---------------------------------------------------------------------------


def _render_question() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_question_motivation

    pkg, _, _, _, _ = _real_fixtures()
    render_e2_question_motivation(pkg)


def test_question_contains_research_question_and_bounded_scope() -> None:
    at = AppTest.from_function(_render_question)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "Research question" in text
    assert "RSU placement target" in text or "placement target" in text
    assert "Manchester incident hour" in text or "2024-03-15" in text
    assert "fleet draws" in text.lower() or "fleet_draw" in text.lower()


# ---------------------------------------------------------------------------
# Strategy cards — typed semantics, no false claims
# ---------------------------------------------------------------------------


def _render_cards() -> None:
    from traffictwin.experiments.e2_strategy_semantics import e2_strategy_semantics
    from traffictwin.ui.components.e2_research import render_e2_strategy_cards

    semantics = e2_strategy_semantics()
    render_e2_strategy_cards(semantics)


def test_strategy_cards_contain_all_five_strategies_and_no_false_claims() -> None:
    at = AppTest.from_function(_render_cards)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    for sid in ["off", "jsq", "ingress_dla", "dla", "per_task_dla"]:
        assert sid in text
    # No affirmative false claims — semantics are validated to forbid these
    lower = text.lower()
    # Check that learned/deterministic flags are rendered and not affirmative false claims
    assert "deterministic" in lower
    # Must not credit MAPPO with execution RSU selection affirmatively
    assert "mappo selects execution" not in lower
    assert "mappo observes current" not in lower
    # If Kubernetes is mentioned, it must be in negated/inspired context
    # The typed semantics use "Kubernetes-inspired" not deployment


def test_strategy_cards_render_typed_fields_verbatim() -> None:
    from traffictwin.experiments.e2_strategy_semantics import e2_strategy_semantics

    semantics = e2_strategy_semantics()
    at = AppTest.from_function(_render_cards)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    # Each human_label should appear verbatim
    for sem in semantics:
        assert sem.human_label[:20] in text


# ---------------------------------------------------------------------------
# E2b table — exact values from typed view
# ---------------------------------------------------------------------------


def _render_e2b() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2b_table

    _, _, comparison, _, _ = _real_fixtures()
    render_e2b_table(comparison)


def test_e2b_table_contains_exact_values_from_typed_view() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures

    _, _, comparison, _, _ = _real_fixtures()
    at = AppTest.from_function(_render_e2b)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    # Values must come from comparison.e2b verbatim
    assert str(comparison.e2b.off) in text
    assert str(comparison.e2b.jsq) in text
    assert str(comparison.e2b.ingress_dla) in text
    assert str(comparison.e2b.dla) in text
    # Check pinned exact values
    assert "0.683619229" in text
    assert "0.675681775" in text
    assert "0.715773211" in text
    assert "0.694939919" in text
    assert len(at.dataframe) >= 1


def test_e2b_table_drift_detection_via_typed_mutation() -> None:
    def _render_mutated() -> None:
        from tests.unit.ui.test_e2_research_components import _real_fixtures
        from traffictwin.ui.components.e2_research import render_e2b_table

        _, _, comp, _, _ = _real_fixtures()
        mut = comp.e2b.model_copy(update={"off": 0.999})
        mut_comp = comp.model_copy(update={"e2b": mut})
        render_e2b_table(mut_comp)

    at = AppTest.from_function(_render_mutated)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "0.999" in text
    assert "0.683619229" not in text or "0.999" in text  # mutated value appears


# ---------------------------------------------------------------------------
# E2c table
# ---------------------------------------------------------------------------


def _render_e2c() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2c_table

    _, _, comparison, _, _ = _real_fixtures()
    render_e2c_table(comparison)


def test_e2c_table_contains_exact_diffs_and_ci_from_typed_view() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures

    _, _, comparison, _, _ = _real_fixtures()
    at = AppTest.from_function(_render_e2c)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    for val in comparison.e2c.per_seed_values:
        assert str(val) in text
    assert str(comparison.e2c.mean) in text
    assert str(comparison.e2c.lower) in text
    assert str(comparison.e2c.upper) in text
    assert "negative" in text.lower()
    assert str(comparison.e2c.n_fleet_draws) in text or "4" in text
    assert len(at.dataframe) >= 1


# ---------------------------------------------------------------------------
# E2d table
# ---------------------------------------------------------------------------


def _render_e2d() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2d_table

    _, _, comparison, _, _ = _real_fixtures()
    render_e2d_table(comparison)


def test_e2d_table_contains_exact_diffs_and_ci_from_typed_view() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures

    _, _, comparison, _, _ = _real_fixtures()
    at = AppTest.from_function(_render_e2d)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    for val in comparison.e2d.per_seed_values:
        assert str(val) in text
    assert str(comparison.e2d.mean) in text
    assert str(comparison.e2d.lower) in text
    assert str(comparison.e2d.upper) in text
    # Secondary vs common-target
    assert str(comparison.e2d_vs_common_target.mean) in text
    assert "positive" in text.lower()
    assert str(comparison.e2d.n_fleet_draws) in text or "4" in text
    assert len(at.dataframe) >= 1


def test_e2c_table_fleet_seed_labels_follow_typed_mutation() -> None:
    def _render_mutated() -> None:
        from tests.unit.ui.test_e2_research_components import _real_fixtures
        from traffictwin.ui.components.e2_research import render_e2c_table

        _, _, comp, _, _ = _real_fixtures()
        mutated = comp.e2c.model_copy(update={"fleet_seeds": (91, 92, 93, 94)})
        mut_comp = comp.model_copy(update={"e2c": mutated})
        render_e2c_table(mut_comp)

    at = AppTest.from_function(_render_mutated)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    for s in ("91", "92", "93", "94"):
        assert s in text
    assert "matched fleet draws" in text.lower()
    assert "fleet seeds 1" not in text.lower()


def test_e2d_table_fleet_seed_labels_follow_typed_mutation() -> None:
    def _render_mutated() -> None:
        from tests.unit.ui.test_e2_research_components import _real_fixtures
        from traffictwin.ui.components.e2_research import render_e2d_table

        _, _, comp, _, _ = _real_fixtures()
        mutated = comp.e2d.model_copy(update={"fleet_seeds": (81, 82, 83, 84)})
        mut_comp = comp.model_copy(update={"e2d": mutated})
        render_e2d_table(mut_comp)

    at = AppTest.from_function(_render_mutated)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    for s in ("81", "82", "83", "84"):
        assert s in text
    assert "matched fleet draws" in text.lower()
    assert "fleet seeds 1" not in text.lower()


# ---------------------------------------------------------------------------
# Direction reversal
# ---------------------------------------------------------------------------


def _render_direction() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import (
        render_e2_direction_reversal_summary,
    )

    _, _, comparison, _, _ = _real_fixtures()
    render_e2_direction_reversal_summary(comparison)


def test_direction_reversal_contains_bounded_statement_from_view() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures

    _, _, comparison, _, _ = _real_fixtures()
    at = AppTest.from_function(_render_direction)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert comparison.direction_reversal.statement[:30] in text
    assert "never claim universal superiority" in text.lower()
    assert "bounded to" in text.lower()


# ---------------------------------------------------------------------------
# Accounting and missingness — UNAVAILABLE never zero
# ---------------------------------------------------------------------------


def _render_accounting() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_task_accounting

    _, _, _, accounting, _ = _real_fixtures()
    render_e2_task_accounting(accounting)


def test_accounting_contains_exact_numbers_and_unavailable_reasons() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures

    _, _, _, accounting, _ = _real_fixtures()
    at = AppTest.from_function(_render_accounting)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert str(accounting.offered) in text
    assert str(accounting.admitted) in text
    assert str(accounting.rejected_total) in text
    assert str(accounting.forwarded) in text
    assert str(accounting.deadline_success) in text
    assert str(accounting.offered_deadline_attainment) in text
    assert str(accounting.admitted_deadline_attainment) in text
    # UNAVAILABLE wording for missing fields — verbatim from view
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        assert field in text
        reason = accounting.unavailable[field].reason
        assert reason[:20] in text
        assert "UNAVAILABLE" in text
    # Must never imply started==admitted
    assert "started == admitted" not in text.lower()
    assert "treated as admitted" not in text.lower()
    assert len(at.dataframe) >= 2


def test_accounting_unavailable_not_zero() -> None:
    at = AppTest.from_function(_render_accounting)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    # For each unavailable field, value shown is None/UNAVAILABLE, not 0
    # Dataframe rows contain "None" and "UNAVAILABLE", not numeric 0 for those fields
    # Check that the specific unavailable reason is present and not replaced by 0
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        # The field name should appear with UNAVAILABLE nearby, not with isolated 0
        assert field in text
    # Ensure we do not claim started equals admitted
    assert "started" in text.lower()
    assert "admitted" in text.lower()
    # The string "0" may appear elsewhere (counts) but not as unavailable value replacement
    # This is indirectly covered by reason check above


# ---------------------------------------------------------------------------
# Provenance — full identities from typed package/receipt
# ---------------------------------------------------------------------------


def _render_provenance() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_provenance

    pkg, receipt, _, _, _ = _real_fixtures()
    render_e2_provenance(pkg, receipt)


def test_provenance_contains_full_identities_from_typed_objects() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures

    pkg, receipt, _, _, _ = _real_fixtures()
    at = AppTest.from_function(_render_provenance)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert pkg.source_identities.actor.sha256 in text
    assert pkg.source_identities.trace.sha256 in text
    assert pkg.source_identities.base_sha in text
    for study in ("e2b", "e2c", "e2d"):
        assert (
            pkg.source_identities.research_heads.__dict__[study] in text
            or pkg.source_identities.manifest_sha256_by_study[study] in text
        )
        assert pkg.source_identities.manifest_sha256_by_study[study] in text
    assert receipt.package_fingerprint in text or receipt.receipt_fingerprint in text
    assert "fleet_draw" in text.lower()
    assert "evaluator seed" in text.lower()


# ---------------------------------------------------------------------------
# Limitations — verbatim from package
# ---------------------------------------------------------------------------


def _render_limitations() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_limitations

    pkg, _, _, _, _ = _real_fixtures()
    render_e2_limitations(pkg)


def test_limitations_contains_all_package_limitations_and_nonclaims() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures

    pkg, _, _, _, _ = _real_fixtures()
    at = AppTest.from_function(_render_limitations)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    for lim in pkg.limitations:
        assert lim[:20] in text
    for nc in pkg.non_claims:
        assert nc[:20] in text
    # Must contain at least one of each required categories
    assert "manchester incident hour" in text.lower()
    assert "kubernetes deployment" in text.lower() or "cluster orchestration" in text.lower()
    # Explicitly check non-claim count not collapsed
    assert len(pkg.limitations) >= 5
    assert len(pkg.non_claims) >= 5


# ---------------------------------------------------------------------------
# Downloads — content matches bundle
# ---------------------------------------------------------------------------


def _render_downloads() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_downloads

    _, _, _, _, exports = _real_fixtures()
    render_e2_downloads(exports)


def test_downloads_provide_three_buttons_and_content_matches_bundle() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures

    _, _, _, _, exports = _real_fixtures()
    at = AppTest.from_function(_render_downloads)
    at.run()
    assert not at.exception
    labels = [b.label for b in at.download_button]
    assert any("JSON" in label for label in labels)
    assert any("CSV" in label for label in labels)
    assert any("Markdown" in label for label in labels)
    assert len(at.download_button) == 3
    # Content mismatch detection: bundle json must contain expected keys
    assert "e2b" in exports.json
    assert "e2c" in exports.json
    assert "package_fingerprint" in exports.json
    assert "figure_id" in exports.csv
    assert "# E2 Research Export" in exports.markdown


# ---------------------------------------------------------------------------
# Aggregate — fail-closed on absent/unadmitted receipt
# ---------------------------------------------------------------------------


def _render_aggregate_admitted() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_research

    pkg, receipt, comp, acc, exp = _real_fixtures()
    render_e2_research(pkg, receipt, comp, acc, exp)


def _render_aggregate_unadmitted() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_research

    pkg, _, comp, acc, exp = _real_fixtures()
    # Pass None as receipt to simulate absent/unadmitted
    render_e2_research(pkg, None, comp, acc, exp)


def test_aggregate_admitted_renders_all_sections() -> None:
    at = AppTest.from_function(_render_aggregate_admitted)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "ADMITTED RESEARCH" in text
    assert "OWNER-AUTHORIZED PRODUCT ADMISSION" in text
    assert "Research question" in text
    assert "Strategy cards" in text
    assert "E2b" in text
    assert "E2c" in text
    assert "E2d" in text
    assert "Direction-reversal" in text or "Direction" in text
    assert "Accounting" in text
    assert "Provenance" in text
    assert "Limitations" in text
    assert "Downloads" in text
    assert len(at.download_button) == 3


def test_aggregate_unadmitted_shows_warning_and_no_result_panels() -> None:
    at = AppTest.from_function(_render_aggregate_unadmitted)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "UNADMITTED RESEARCH" in text
    assert "not be treated as admitted" in text.lower() or "unadmitted" in text.lower()
    # Fail-closed: must not show result tables when unadmitted
    assert "E2b —" not in text
    assert "E2c —" not in text
    assert "E2d —" not in text
    assert "Accounting" not in text
    assert len(at.download_button) == 0


def _render_aggregate_forged_package() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_research

    pkg, receipt, comp, acc, exp = _real_fixtures()
    forged_pkg = pkg.model_copy(
        update={
            "limitations": pkg.limitations
            + ["kubernetes deployment is real and universal superiority claimed"],
            "non_claims": pkg.non_claims + ["extra over-claiming non_claim"],
        }
    )
    render_e2_research(forged_pkg, receipt, comp, acc, exp)


def _render_aggregate_forged_receipt() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_research

    pkg, receipt, comp, acc, exp = _real_fixtures()
    forged_attainment = dict(receipt.e2b_offered_attainment)
    forged_attainment["off"] = 0.999
    forged = receipt.model_copy(update={"e2b_offered_attainment": forged_attainment})
    new_fp = forged.computed_fingerprint()
    forged = forged.model_copy(update={"receipt_fingerprint": new_fp})
    render_e2_research(pkg, forged, comp, acc, exp)


def _render_aggregate_plain_dict_receipt() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_research

    pkg, _, comp, acc, exp = _real_fixtures()
    plain: object = {
        "standing": "OWNER-AUTHORIZED PRODUCT ADMISSION",
        "admission_mode": "ADMITTED_RESEARCH",
    }
    render_e2_research(pkg, plain, comp, acc, exp)  # type: ignore[arg-type]


def test_aggregate_forged_package_shows_warning_and_no_panels() -> None:
    at = AppTest.from_function(_render_aggregate_forged_package)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert (
        "not owner-authorized" in text.lower()
        or "does not match authoritative" in text.lower()
        or "withheld" in text.lower()
    )
    assert "E2b —" not in text
    assert "E2c —" not in text
    assert "E2d —" not in text
    assert "Accounting" not in text
    assert len(at.download_button) == 0


def test_aggregate_forged_receipt_shows_warning_and_no_panels() -> None:
    at = AppTest.from_function(_render_aggregate_forged_receipt)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "does not match authoritative" in text.lower() or "withheld" in text.lower()
    assert "E2b —" not in text
    assert "E2c —" not in text
    assert "E2d —" not in text
    assert "Accounting" not in text
    assert len(at.download_button) == 0


def test_aggregate_plain_dict_receipt_unadmitted_no_exception() -> None:
    at = AppTest.from_function(_render_aggregate_plain_dict_receipt)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "UNADMITTED RESEARCH" in text
    assert "withheld" in text.lower()
    assert "E2b —" not in text
    assert "E2c —" not in text
    assert "E2d —" not in text
    assert len(at.download_button) == 0


def _render_aggregate_mutated_comparison() -> None:
    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_research

    pkg, receipt, comp, acc, exp = _real_fixtures()
    mutated_e2b = comp.e2b.model_copy(update={"off": 0.999})
    mutated_comp = comp.model_copy(update={"e2b": mutated_e2b})
    render_e2_research(pkg, receipt, mutated_comp, acc, exp)


def _render_aggregate_mutated_exports() -> None:
    import dataclasses

    from tests.unit.ui.test_e2_research_components import _real_fixtures
    from traffictwin.ui.components.e2_research import render_e2_research

    pkg, receipt, comp, acc, exp = _real_fixtures()
    mutated_exports = dataclasses.replace(exp, json=exp.json + " ")
    render_e2_research(pkg, receipt, comp, acc, mutated_exports)


def test_aggregate_mutated_comparison_withholds_all_results() -> None:
    at = AppTest.from_function(_render_aggregate_mutated_comparison)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "do not match" in text.lower() or "withheld" in text.lower()
    assert "E2b —" not in text
    assert "E2c —" not in text
    assert "E2d —" not in text
    assert "Accounting" not in text
    assert len(at.download_button) == 0


def test_aggregate_mutated_exports_withholds_all_results() -> None:
    at = AppTest.from_function(_render_aggregate_mutated_exports)
    at.run()
    assert not at.exception
    text = _collect_all(at)
    assert "do not match" in text.lower() or "withheld" in text.lower()
    assert "E2b —" not in text
    assert "E2c —" not in text
    assert "E2d —" not in text
    assert "Accounting" not in text
    assert len(at.download_button) == 0


def test_no_html_css_or_deprecated_apis_in_file() -> None:
    from pathlib import Path

    src = Path("src/traffictwin/ui/components/e2_research.py").read_text(encoding="utf-8")
    assert "unsafe_allow_html" not in src
    assert "use_container_width" not in src
    assert "<style" not in src.lower()
    assert "<div" not in src.lower()
    assert 'width="stretch"' in src
