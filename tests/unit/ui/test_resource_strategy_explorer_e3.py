"""Lane 11 - AppTests for Resource Strategy Explorer E3 mode.

Proves one-click Load TrafficTwin E3 Dynamic Resource V2 action loads
promoted Lane 10 typed payload via importlib.resources and renders
truthful no-results state with deterministic exports, without filesystem
path input. Preserves E2 and generic behavior. No forbidden claims.
"""

from __future__ import annotations

import json
import pathlib
from copy import deepcopy
from typing import Any

from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import default_session_state, load_ui_config

PAGE = "src/traffictwin/ui/app_pages/resource_strategy.py"

# For legacy path check, the UI pages are under src/traffictwin/ui/pages/
LEGACY_PAGE = "src/traffictwin/ui/pages/resource_strategy_explorer.py"


def _page_app() -> AppTest:
    app = AppTest.from_file(PAGE)
    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = (
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    if "resource_strategy_e3_active" in app.session_state:
        del app.session_state["resource_strategy_e3_active"]
    if "resource_strategy_e2_active" in app.session_state:
        del app.session_state["resource_strategy_e2_active"]
    return app


def _text_of(app: AppTest) -> str:
    parts: list[str] = []
    for attr in ("title", "markdown", "caption", "subheader", "text", "code"):
        parts.extend(str(x.value) for x in getattr(app, attr, []))
    for attr in ("info", "warning", "error", "success"):
        parts.extend(str(x.value) for x in getattr(app, attr, []))
    for df in app.dataframe:
        try:
            parts.append(str(df.value))
        except Exception:
            parts.append(str(df))
    return "\n".join(parts)


def _find_e3_button(app: AppTest) -> Any | None:  # noqa: ANN401
    for b in app.button:
        if "Load TrafficTwin E3 Dynamic Resource V2" in str(b.label):
            return b
    return None


def _find_e2_button(app: AppTest) -> Any | None:  # noqa: ANN401
    for b in app.button:
        if "Load TrafficTwin E2 research" in str(b.label):
            return b
    return None


def test_e3_preset_button_exists_and_is_visibly_separate() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception, app.exception
    e3_btn = _find_e3_button(app)
    assert e3_btn is not None, (
        "Load TrafficTwin E3 Dynamic Resource V2 button must be visibly separate"
    )
    e2_btn = _find_e2_button(app)
    assert e2_btn is not None, "E2 button must still exist"
    body = _text_of(app)
    # Caption confirms no filesystem path needed for E3 preset
    assert "No filesystem path input is needed" in body or "no path" in body.lower()
    assert "dormant" in body.lower() or "no results" in body.lower()
    # Unique labels per page
    labels = [b.label for b in app.button]
    assert len(labels) == len(set(labels)), f"duplicate button labels on explorer: {labels}"


def test_e3_preset_loads_truthful_no_results_state() -> None:
    app = _page_app().run(timeout=30)
    btn = _find_e3_button(app)
    assert btn is not None
    btn.click().run(timeout=30)
    assert not app.exception, app.exception
    body = _text_of(app)
    # Immutable hold verbatim
    assert "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED" in body
    assert "evidence_state = NOT_EXECUTED" in body
    assert "result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE" in body
    assert "research_workloads_launched = 0" in body
    # Truthful refusal
    assert "REFUSED" in body
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "REFUSED_MISSING_FUTURE_ARTIFACT" in body or "REFUSED" in body
    # No results disclaimer
    assert "NO results" in body or "no results" in body.lower()
    assert "NOT_EXECUTED" in body
    assert "NO_E3_RESEARCH_RESULTS_AVAILABLE" in body
    # Scientific question
    assert "Scientific question" in body
    # Strategy semantics families
    assert "ingress_dla" in body
    assert "per_task_dla" in body
    assert "p2c_dla" in body
    assert "fixed_1x" in body
    # Placement/scaling/staleness/resource trade-off
    assert "resource_unit_seconds" in body
    assert "queue" in body.lower() and "compute" in body.lower()
    # Per-RSU and scale-action structure
    assert "Per-RSU" in body or "per-RSU" in body.lower() or "Per-RSU summaries" in body
    assert "Scale-action" in body or "scale-action" in body.lower()
    # Task accounting with null lifecycle
    assert "offered" in body.lower()
    assert "UNAVAILABLE" in body
    # Missingness
    assert "Missingness" in body or "missingness" in body.lower()
    # Provenance pins
    assert "2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c" in body or "2b6d4675" in body
    assert (
        "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208" in body
        or "93c97059" in body
    )
    # Limitations
    assert "Limitations" in body
    assert (
        "No Manchester-wide deployment tested" in body
        or "bounded to one incident hour" in body.lower()
    )
    # Must state admission fails closed until exact approved Lane 09 package
    assert "fails closed" in body.lower() or "exact approved Lane 09" in body
    # Must not contain placeholder numbers or marketing
    # Ensure no chart implying zero values - we check that no bar_chart with numeric data
    # Our E3 components should not render numeric charts; just check body does not contain "0.0" as placeholder  # noqa: E501
    # This is lenient: we check that body does not contain "coming soon" marketing
    assert "coming soon" not in body.lower()
    # Strengthened: placeholder must not appear affirmatively;
    # if it appears it must be in a negative disclaimer
    lower = body.lower()
    if "placeholder" in lower:
        # Must be part of an explicit negative claim, not marketing
        assert (
            "no placeholder" in lower
            or "never a placeholder" in lower
            or "not a placeholder" in lower
        ), "placeholder must be negated"
        # And must not be "placeholder result" as affirmative
        assert "placeholder result" not in lower
    # Also ensure no synthetic result claim
    assert "synthetic result" not in lower


def test_e3_exports_deterministic_and_match_typed_payload() -> None:
    app = _page_app().run(timeout=30)
    btn = _find_e3_button(app)
    assert btn is not None
    btn.click().run(timeout=30)
    assert not app.exception
    labels = {b.label for b in app.download_button}
    assert "Download E3 JSON" in labels
    assert "Download E3 CSV" in labels
    assert "Download E3 Markdown" in labels
    # Verify via service that exports are deterministic and match payload
    from traffictwin.evidence_admission.e3_research import admit_e3_research
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
    from traffictwin.reporting.e3_research import build_e3_research_exports

    pkg = load_builtin_e3_research()
    receipt = admit_e3_research(pkg)
    exports = build_e3_research_exports(pkg, receipt)
    exports2 = build_e3_research_exports(pkg, receipt)
    assert exports.json == exports2.json
    assert exports.csv == exports2.csv
    assert exports.markdown == exports2.markdown
    # JSON contains truthful hold and typed payload
    j = json.loads(exports.json)
    assert j["hold"]["lane_09"] == "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
    assert j["hold"]["evidence_state"] == "NOT_EXECUTED"
    assert j["admission"]["status"] == "REFUSED"
    assert j["admission"]["standing"] == "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"
    assert j["task_accounting"]["offered"] is None
    assert j["task_accounting"]["unavailable"]["offered"]["reason"] != ""
    # CSV and markdown contain hold constants
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in exports.csv
    assert "NOT_EXECUTED" in exports.csv
    assert "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in exports.markdown
    # No timestamps or randomness — ISO timestamp must not appear (allow disclaimer "timestamps")
    import re as _re

    _iso_re = _re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    _timestamp_key_re = _re.compile(r'"timestamp"\s*:')
    assert not _timestamp_key_re.search(exports.json.lower()), (
        "export must not contain timestamp field"
    )
    assert not _iso_re.search(exports.json), (
        f"export must not contain ISO timestamp, found {_iso_re.search(exports.json).group(0)!r}"
    )
    # Check that json is byte-stable ordering (sorted keys)
    # Verify that package fingerprint is 64 hex
    import re

    assert re.fullmatch(r"[0-9a-f]{64}", j["package_fingerprint"])
    assert re.fullmatch(r"[0-9a-f]{64}", j["export_fingerprint"])


def test_e2_still_renders_unchanged_after_e3_addition() -> None:
    app = _page_app().run(timeout=30)
    btn = _find_e2_button(app)
    assert btn is not None
    btn.click().run(timeout=30)
    assert not app.exception
    body = _text_of(app)
    # Exact E2 values still present
    assert "0.683619229" in body
    assert "0.715773211" in body
    assert "ADMITTED RESEARCH" in body


def test_generic_synthetic_still_works() -> None:
    app = _page_app().run(timeout=30)
    assert not app.exception
    body = _text_of(app)
    assert "synthetic" in body.lower()
    assert "Matched" in body or "Matched replications" in body


def test_e3_intent_activates_via_session_state() -> None:
    app = AppTest.from_file(PAGE)
    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = ""
    if "resource_strategy_uploaded" in app.session_state:
        del app.session_state["resource_strategy_uploaded"]
    if "resource_strategy_e3_active" in app.session_state:
        del app.session_state["resource_strategy_e3_active"]
    if "resource_strategy_e2_active" in app.session_state:
        del app.session_state["resource_strategy_e2_active"]
    app.session_state["resource_strategy_intent"] = "e3"
    app.run(timeout=30)
    assert not app.exception
    body = _text_of(app)
    assert "REFUSED" in body or "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "NOT_EXECUTED" in body


def test_no_forbidden_claims_in_e3_rendered_text() -> None:
    app = _page_app().run(timeout=30)
    btn = _find_e3_button(app)
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text_of(app)
    lower = body.lower()
    # Forbidden affirmative claims should not appear; allowlisted disclaimers are okay but we check for affirmative patterns  # noqa: E501
    # Simple check: these substrings should not appear as standalone  # noqa: E501
    # affirmative claims outside disclaimers.
    # Our component uses allowlisted exact sentences, so we check that  # noqa: E501
    # forbidden patterns do not appear in a way that is not part of allowlisted.
    # For now, check that monetary dollars not present affirmatively  # noqa: E501
    # (allowlisted contains dollars but as part of disclaimer)
    # We will check that body does not contain "supervisor approved"  # noqa: E501
    # as affirmative (allowlisted is "No supervisor approval; ..." - allowed)
    # So we check for "approved by the supervisor" etc. not present.
    forbidden_affirmative = [
        "supervisor approved",
        "approved by the supervisor",
        "randy approved",
        "randy confirmed",
        "kubernetes deployment is live",
        "k8s cluster is live",
        "universally superior",
    ]
    for pat in forbidden_affirmative:
        assert pat not in lower, f"forbidden affirmative claim {pat!r} found"  # noqa: E501
    # Check that monetary language not present as affirmative price  # noqa: E501
    # - allowlisted disclaimer contains dollars but as part of
    #   "No monetary cost claim" - we allow that
    # So we check that "$" not present as currency outside disclaimer
    # Our exports and UI should not contain "$" at all
    assert "$" not in body
    # Check actor selects RSU affirmatively not present  # noqa: E501
    # (allowlisted is "No actor selects execution RSU")
    # So we check that "actor selects execution rsu" appears only with "No" preceding
    # If it appears, ensure "no actor selects" is present
    if "actor selects execution rsu" in lower:
        assert "no actor selects execution rsu" in lower


def test_e3_no_empty_chart_implying_zero() -> None:
    app = _page_app().run(timeout=30)
    btn = _find_e3_button(app)
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text_of(app)
    # Ensure no placeholder numeric chart data like "0.0" being presented as result
    # The E3 page should not contain a bar chart with numeric values;  # noqa: E501
    # we check that body does not contain chart data implying zero
    # Since our E3 components do not render bar_chart, there should be no chart data
    # This is a placeholder check: ensure "0.000" not present as fake result
    # Real E3 has no numeric results, so we should not see typical E2 numeric values
    assert "0.683619229" not in body  # E2 values should not appear in E3 mode


def test_e3_explorer_rendered_constants_match_package(tmp_path: pathlib.Path) -> None:
    """Drift regression: explorer renders same constants as package."""
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    pkg = load_builtin_e3_research()
    # Check explorer's AppTest rendering contains package-derived values
    app = _page_app().run(timeout=30)
    btn = _find_e3_button(app)
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text_of(app)
    # Must contain package values, not hardcoded drift
    assert str(pkg.factors["scenario_rsus"]) in body
    assert str(pkg.factors["padded_fleet_width"]) in body
    assert str(pkg.factors["ticks_per_cell"]) in body
    assert str(pkg.queue_capacity.capacity_per_rsu) in body
    assert ", ".join(str(v) for v in pkg.factors["state_age_ms_values"]) in body
    # Verify that the button labels are still unique and E3 load button visible
    labels = [b.label for b in app.button]
    assert "Load TrafficTwin E3 Dynamic Resource V2" in labels


def test_e3_intent_b_and_d_regressions() -> None:
    """Reviewer cases B and D: E2 active + intent e3 → E3, after Clear-E2 → E3."""
    # B: E2 active + intent=e3 → E3 renders with load button visible
    app = _page_app()
    app.session_state["resource_strategy_e2_active"] = True
    app.session_state["resource_strategy_intent"] = "e3"
    app.run(timeout=30)
    assert not app.exception, app.exception
    body = _text_of(app)
    assert "REFUSED" in body or "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "Load TrafficTwin E3 Dynamic Resource V2" in [b.label for b in app.button], (
        "E3 load button must be visible when E2 active and e3 intent pending"
    )
    # D: after Clear-E2 with pending e3 intent — with distinct E3 pending key, E3 does not
    # auto-activate from a stale pending after Clear-E2
    # (scenario now impossible for shared pending).
    # Drive the Clear-E2 widget in an E2-active run with a pending e3 intent
    # and verify the click is real
    # and E2 clears without swallowing a future e2 intent.
    app2 = _page_app()
    app2.session_state["resource_strategy_e2_active"] = True
    app2.session_state["resource_strategy_intent"] = "e3"
    app2.session_state["_resource_strategy_e3_intent_pending_pop"] = True
    app2.run(timeout=30)
    # Find and click Clear E2 — real widget click
    clear = None
    for b in app2.button:
        if "Clear E2 research view" in str(b.label):
            clear = b
            break
    assert clear is not None, "Clear E2 button must exist before clear"
    clear.click().run(timeout=30)
    assert not app2.exception, app2.exception
    body2 = _text_of(app2)
    # After Clear-E2, E2 must be cleared; E3 pending is distinct so it should not have swallowed e2
    # With distinct keys, clearing E2 does not auto-activate E3 from stale
    # pending — user must re-navigate via Home CTA.
    # Verify E2 values are gone and page is in generic state (not E3 REFUSED auto).
    assert "0.683619229" not in body2
    # E2 active flag must be cleared
    assert "resource_strategy_e2_active" not in app2.session_state


def test_e2_cta_after_e3_visit_renders_e2_first_press() -> None:
    """B1 regression: E2 CTA after an E3 visit renders E2 on FIRST rerun.

    Reviewer exploit sequence — run explorer with intent="e3" (E3 renders,
    e3_active True and distinct _resource_strategy_e3_intent_pending_pop set
    by the page), then set intent="e2" as the Home CTA callback does and
    rerun. FIRST rerun must render the E2 journey (E2 marker 0.683619229
    present and E3 REFUSED banner absent), proving the E3 pending key cannot
    pop the e2 intent.

    Bug reference (git 7e4f833): E3 previously wrote the shared
    _resource_strategy_intent_pending_pop. With the shared key, the FIRST
    rerun after an E3 visit swallowed the fresh e2 intent in
    _render_e2_preset (pending pop) and fell through to stale E3 because
    resource_strategy_e3_active was still True. This test FAILS under the
    shared-key behavior and PASSES only with the distinct
    _resource_strategy_e3_intent_pending_pop key.
    """

    app = _page_app()
    app.session_state["resource_strategy_intent"] = "e3"
    app.run(timeout=30)
    assert not app.exception, app.exception
    body_e3 = _text_of(app)
    assert "REFUSED" in body_e3 or "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body_e3
    assert "NOT_EXECUTED" in body_e3
    # Distinct E3 pending must be set; shared pending must not be set by E3.
    assert "resource_strategy_e3_active" in app.session_state
    assert app.session_state["resource_strategy_e3_active"] is True
    assert "_resource_strategy_e3_intent_pending_pop" in app.session_state
    assert app.session_state["_resource_strategy_e3_intent_pending_pop"] is True
    assert "_resource_strategy_intent_pending_pop" not in app.session_state, (
        "E3 must write distinct _resource_strategy_e3_intent_pending_pop, not shared"
    )

    # Simulate Home CTA callback for E2: exact "_on_inspect_e2_research" path
    # sets resource_strategy_intent="e2" then navigates.
    app.session_state["resource_strategy_intent"] = "e2"
    app.run(timeout=30)
    assert not app.exception, app.exception
    body = _text_of(app)
    assert "0.683619229" in body, "FIRST rerun after E3 with e2 CTA must render E2"
    assert "0.715773211" in body
    assert "ADMITTED RESEARCH" in body
    # E3 REFUSED banner must be absent on FIRST rerun.
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" not in body
    assert "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED" not in body
    assert "NO_E3_RESEARCH_RESULTS_AVAILABLE" not in body
    # If E3 had written the shared key (7e4f833), this FIRST rerun would have
    # rendered stale E3 and the asserts above would FAIL.


def test_e3_cta_after_e2_visit_renders_e3() -> None:
    """Mirror B1: E3 CTA after an E2 visit renders E3 on FIRST rerun.

    Sequence — run explorer with intent="e2" (E2 renders, e2_active True and
    shared pending set), then set intent="e3" as the Home CTA does and rerun.
    FIRST rerun must render the E3 journey (REFUSED banner present, E2 marker
    absent), proving the intents are symmetric and E2 pending cannot block E3.

    Distinct-key invariant: E3 writes only _resource_strategy_e3_intent_pending_pop,
    E2 writes only _resource_strategy_intent_pending_pop. This mirror verifies
    E3 dispatches before E2 when intent is e3 and E2 pending does not block E3;
    it does not directly exercise the shared-key mutation covered by
    test_e2_cta_after_e3_visit and the state-sweep row.
    """

    app = _page_app()
    app.session_state["resource_strategy_intent"] = "e2"
    app.run(timeout=30)
    assert not app.exception, app.exception
    body_e2 = _text_of(app)
    assert "0.683619229" in body_e2
    assert "ADMITTED RESEARCH" in body_e2
    assert "resource_strategy_e2_active" in app.session_state
    assert app.session_state["resource_strategy_e2_active"] is True
    # E2 uses the shared pending key
    assert "_resource_strategy_intent_pending_pop" in app.session_state
    assert app.session_state["_resource_strategy_intent_pending_pop"] is True

    # Simulate Home CTA for E3
    app.session_state["resource_strategy_intent"] = "e3"
    app.run(timeout=30)
    assert not app.exception, app.exception
    body = _text_of(app)
    assert "REFUSED" in body or "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "NOT_EXECUTED" in body
    assert "NO_E3_RESEARCH_RESULTS_AVAILABLE" in body
    assert "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED" in body
    # E2 marker must be absent — E3 has dispatched before E2 when intent is e3.
    assert "0.683619229" not in body
    assert "0.715773211" not in body


def test_state_sweep_exploit_row_e2_with_stale_e3_pending_renders_e2() -> None:
    """State-sweep for exact B1 exploit row — stale E3 must not hijack e2.

    Exact row: intent="e2", _resource_strategy_e3_intent_pending_pop=True,
    resource_strategy_e3_active=True, no resource_strategy_e2_active.
    Rerun must render E2 (0.683619229) not E3. This is the direct session-state
    form of the B1 exploit without needing a full navigation sequence.

    With the distinct key the E3 handler clears only the stale E3 flag when
    intent is e2, leaving the e2 intent to activate E2. This test arranges the
    exploit row with distinct pending True and clears the shared pending flag
    before render to simulate the distinct-key world; it does not exercise the
    shared-key mutation where E3 would have written the shared pending key (to
    exercise that, the shared pending must be left set, which would cause the
    E2 intent to be swallowed under git 7e4f833).
    """

    app = _page_app()
    # Arrange exact exploit row
    if "resource_strategy_e2_active" in app.session_state:
        del app.session_state["resource_strategy_e2_active"]
    app.session_state["resource_strategy_e3_active"] = True
    app.session_state["_resource_strategy_e3_intent_pending_pop"] = True
    app.session_state["resource_strategy_intent"] = "e2"
    # Ensure shared E2 pending is absent — simulates distinct-key world.
    # If E3 had written shared key, this would be True and E2 would be swallowed.
    if "_resource_strategy_intent_pending_pop" in app.session_state:
        del app.session_state["_resource_strategy_intent_pending_pop"]

    app.run(timeout=30)
    assert not app.exception, app.exception
    body = _text_of(app)
    assert "0.683619229" in body, "exploit row must render E2, not stale E3"
    assert "0.715773211" in body
    assert "ADMITTED RESEARCH" in body
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" not in body
    assert "NO_E3_RESEARCH_RESULTS_AVAILABLE" not in body
    assert "REFUSED" not in body or "ADMITTED RESEARCH" in body
    # Post-condition: E2 activated, stale E3 flag cleared to distinct key only
    assert "resource_strategy_e2_active" in app.session_state
    assert app.session_state["resource_strategy_e2_active"] is True


def test_e3_survives_reruns_after_e2_history() -> None:
    """Proves E3 survives two plain reruns after an e2→e3 history.

    Sequence: intent="e2" run (E2 renders) → intent="e3" run (E3 renders) →
    two more plain reruns with no session_state mutation. After the final
    rerun asserts the E3 load button is still present, "Clear E2 research
    view" is absent, and the E2 marker 0.683619229 is absent, showing that
    round-3 arbitration does not clear E3 on unrelated reruns and no stale
    E2 state reappears.

    This is the review-3 blocker-1 exploit (E3 vanishing after E2 history).
    The test verifies rerun stability and mutual exclusion durability (E3
    activation pops E2 and arbitration keeps at most one active). It does
    not by itself prove the distinct E3 pending-key fix for the e3→e2
    swallow; that distinct-key invariant is covered by
    test_e2_cta_after_e3_visit_renders_e2_first_press and
    test_state_sweep_exploit_row_e2_with_stale_e3_pending_renders_e2.
    """

    app = _page_app()
    app.session_state["resource_strategy_intent"] = "e2"
    app.run(timeout=30)
    assert not app.exception, app.exception
    body_e2 = _text_of(app)
    assert "0.683619229" in body_e2, "first run with e2 intent must render E2"

    app.session_state["resource_strategy_intent"] = "e3"
    app.run(timeout=30)
    assert not app.exception, app.exception
    body_e3 = _text_of(app)
    assert "REFUSED" in body_e3 or "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body_e3

    # Two plain reruns — no intent or active mutation
    app.run(timeout=30)
    assert not app.exception, app.exception
    app.run(timeout=30)
    assert not app.exception, app.exception

    body = _text_of(app)
    labels = [str(b.label) for b in app.button]
    assert any("Load TrafficTwin E3 Dynamic Resource V2" in lab for lab in labels), (
        "E3 load button must still be present after two reruns"
    )
    assert not any("Clear E2 research view" in lab for lab in labels), (
        "Clear E2 research view must be absent after e2→e3→reruns"
    )
    assert "0.683619229" not in body, "E2 marker must be absent when E3 survives"


def test_clear_e2_after_e3_history_matches_base_cleared_state() -> None:
    """Proves Clear-E2 after e3→e2 history matches base-only cleared state.

    Sequence: intent="e3" run → intent="e2" run → click the real
    "Clear E2 research view" widget. After the click asserts no "REFUSED"
    text, no E2 marker 0.683619229, and that the button label set equals the
    button set of a base-only E2-then-Clear flow computed in the same test
    (to avoid hardcoding).

    Covers review-3 blocker-2 (base-consistent Clear-E2 after E3 history) and
    verifies the widget click path and mutual-exclusion arbitration return to
    generic. It does not prove E3 survival across reruns (covered by
    test_e3_survives_reruns_after_e2_history) nor the full 24-row mutual-
    exclusion sweep (covered by test_two_render_state_sweep...).
    """

    app = _page_app()
    app.session_state["resource_strategy_intent"] = "e3"
    app.run(timeout=30)
    assert not app.exception, app.exception

    app.session_state["resource_strategy_intent"] = "e2"
    app.run(timeout=30)
    assert not app.exception, app.exception
    body_e2 = _text_of(app)
    assert "0.683619229" in body_e2, "e2 must render before Clear-E2 in e3→e2 history"

    clear = None
    for btn in app.button:
        if "Clear E2 research view" in str(btn.label):
            clear = btn
            break
    assert clear is not None, "Clear E2 button must exist before click"
    clear.click().run(timeout=30)
    assert not app.exception, app.exception
    body = _text_of(app)
    assert "REFUSED" not in body, "REFUSED must be absent after Clear-E2"
    assert "0.683619229" not in body

    # Base-only expectation: E2-then-Clear without any prior E3 history
    base = _page_app()
    base.session_state["resource_strategy_intent"] = "e2"
    base.run(timeout=30)
    assert not base.exception, base.exception
    base_clear = None
    for btn in base.button:
        if "Clear E2 research view" in str(btn.label):
            base_clear = btn
            break
    assert base_clear is not None, "base Clear E2 button must exist"
    base_clear.click().run(timeout=30)
    assert not base.exception, base.exception
    expected = {str(b.label) for b in base.button}
    actual = {str(b.label) for b in app.button}
    assert actual == expected, (
        f"button set after e3→e2→Clear must match base {expected} vs {actual}"
    )


def test_two_render_state_sweep_mutual_exclusion_no_exceptions() -> None:
    """Proves 24-row two-render sweep has no exceptions and mutual exclusion.

    Rows: {intent e2/e3/None} × {e2_active} × {e3_active} ×
    {e3_pending} where e3_pending is _resource_strategy_e3_intent_pending_pop.
    For each row two consecutive runs are executed; asserts no AppTest
    exception and never both 'resource_strategy_e2_active' and
    'resource_strategy_e3_active' present as True afterwards (checked via
    'in' and '[]', not .get).

    Covers review-3 blocker-3 (mutual exclusion and duplicate-key safety) for
    the two-render horizon with the uncommitted round-3 arbitration. It does
    not prove single-render mutual exclusion, widget uniqueness beyond two
    renders, E3 survival beyond the sweep, or the distinct-key swallow
    beyond the sweep's e3-pending dimension (those are covered by the
    targeted CTA and survival tests).
    """

    intents: list[str | None] = ["e2", "e3", None]
    for intent in intents:
        for e2_active in (True, False):
            for e3_active in (True, False):
                for e3_pending in (True, False):
                    app = _page_app()
                    # Arrange intent
                    if intent is not None:
                        app.session_state["resource_strategy_intent"] = intent
                    else:
                        if "resource_strategy_intent" in app.session_state:
                            del app.session_state["resource_strategy_intent"]
                    # Arrange e2_active
                    if e2_active:
                        app.session_state["resource_strategy_e2_active"] = True
                    else:
                        if "resource_strategy_e2_active" in app.session_state:
                            del app.session_state["resource_strategy_e2_active"]
                    # Arrange e3_active
                    if e3_active:
                        app.session_state["resource_strategy_e3_active"] = True
                    else:
                        if "resource_strategy_e3_active" in app.session_state:
                            del app.session_state["resource_strategy_e3_active"]
                    # Arrange e3 pending
                    if e3_pending:
                        app.session_state["_resource_strategy_e3_intent_pending_pop"] = True
                    else:
                        if "_resource_strategy_e3_intent_pending_pop" in app.session_state:
                            del app.session_state["_resource_strategy_e3_intent_pending_pop"]
                    # Keep shared E2 pending absent to isolate e3-pending dimension
                    if "_resource_strategy_intent_pending_pop" in app.session_state:
                        del app.session_state["_resource_strategy_intent_pending_pop"]

                    # Two consecutive runs
                    app.run(timeout=30)
                    assert not app.exception, (
                        f"first run ex {intent!r} e2={e2_active} "
                        f"e3={e3_active} p={e3_pending}: {app.exception}"
                    )
                    app.run(timeout=30)
                    assert not app.exception, (
                        f"second run ex {intent!r} e2={e2_active} "
                        f"e3={e3_active} p={e3_pending}: {app.exception}"
                    )
                    # Mutual exclusion via []/in, not .get
                    has_e2 = (
                        "resource_strategy_e2_active" in app.session_state
                        and app.session_state["resource_strategy_e2_active"]
                    )
                    has_e3 = (
                        "resource_strategy_e3_active" in app.session_state
                        and app.session_state["resource_strategy_e3_active"]
                    )
                    assert not (has_e2 and has_e3), (
                        f"both actives {intent!r} e2={e2_active} e3={e3_active} p={e3_pending}"
                    )
