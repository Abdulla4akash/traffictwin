"""S4A Guided Demo — What-If Studio stage discoverability."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from traffictwin.ui.guided import DemoTrack, GuidedDemoProgress, steps_for_track
from traffictwin.ui.labels import UiPage

GUIDED_APP = "src/traffictwin/ui/app_pages/guided_demo.py"


def test_standalone_contains_whatif_step() -> None:
    steps = steps_for_track(DemoTrack.STANDALONE)

    assert any(step.key == "whatif" for step in steps)
    whatif = next(step for step in steps if step.key == "whatif")
    assert whatif.title == "Build a what-if experiment"
    assert whatif.target_page is UiPage.WHATIF_STUDIO
    # All steps must remain distinct
    assert len({step.key for step in steps}) == len(steps)


def test_whatif_target_is_whatif_studio() -> None:
    whatif = next(
        step for step in steps_for_track(DemoTrack.STANDALONE) if step.key == "whatif"
    )

    assert whatif.target_page is UiPage.WHATIF_STUDIO
    assert whatif.target_page != UiPage.COMPARE  # type: ignore[comparison-overlap]


def test_whatif_before_compare_and_consecutive_or_near() -> None:
    steps = steps_for_track(DemoTrack.STANDALONE)
    keys = [step.key for step in steps]

    assert keys.index("whatif") < keys.index("compare")
    # After whatif, Compare should be next (V2 journey continuity)
    assert keys[keys.index("whatif") + 1] == "compare"


def test_whatif_instructions_describe_deterministic_synthetic() -> None:
    whatif = next(step for step in steps_for_track(DemoTrack.STANDALONE) if step.key == "whatif")

    combined = " ".join(
        [
            whatif.input_label,
            whatif.operation_label,
            whatif.output_label,
            whatif.instruction,
            whatif.boundary,
        ]
    ).lower()
    assert "deterministic" in combined
    assert "synthetic" in combined
    assert "baseline" in combined
    assert "intervention" in combined or "variation" in combined
    assert "ledger" in combined
    assert "generate" in combined
    assert "selected_baseline_run" in whatif.instruction
    assert "selected_variation_run" in whatif.instruction


def test_whatif_distinguishes_studio_and_composer() -> None:
    whatif = next(step for step in steps_for_track(DemoTrack.STANDALONE) if step.key == "whatif")

    assert "What-If Studio" in whatif.boundary
    assert "Platform" in whatif.boundary
    assert "What-If Composer" in whatif.boundary
    assert "not" in whatif.boundary.lower() or "cannot" in whatif.boundary.lower()
    # Must not blur: Studio is executable local deterministic synthetic
    assert (
        "draft" in whatif.boundary.lower()
        or "prediction" in whatif.boundary.lower()
        or "surrogate" in whatif.boundary.lower()
    )


def test_whatif_no_sumo_vec_provider_research_dependency() -> None:
    whatif = next(step for step in steps_for_track(DemoTrack.STANDALONE) if step.key == "whatif")

    text = " ".join([whatif.instruction, whatif.boundary, whatif.operation_label])
    # Must explicitly state it does NOT require those
    lower = text.lower()
    assert "does not run sumo" in lower
    assert "vec" in lower
    assert "provider" in lower or "research campaign" in lower


def test_fallback_remains_functional() -> None:
    steps = steps_for_track(DemoTrack.STANDALONE)

    # Old stages still present
    assert any(step.key == "validate" for step in steps)
    assert any(step.key == "metrics" for step in steps)
    assert any(step.key == "compare" for step in steps)
    # whatif is REVIEW, so can be skipped and Compare still reachable via fallback
    whatif = next(step for step in steps if step.key == "whatif")
    from traffictwin.ui.guided import GuidedCompletionMode

    assert whatif.completion_mode is GuidedCompletionMode.REVIEW
    # Instruction mentions Skip + Bundle Import fallback
    assert "Skip" in whatif.instruction
    assert "Bundle Import" in whatif.instruction
    assert "Compare reachable" in whatif.instruction or "keeps Compare" in whatif.instruction


def test_no_dead_route_to_consequence_or_portfolio() -> None:
    steps = steps_for_track(DemoTrack.STANDALONE)
    targets = {step.target_page for step in steps}

    # Must not reference unmerged pages
    for page in targets:
        assert page.value != "Consequence Lenses"
        assert page.value != "Portfolio Explorer"
    # UiPage enum does not have those, but also ensure no literal mention
    combined = " ".join(step.title + step.instruction for step in steps)
    assert "Consequence Lenses" not in combined
    assert "Portfolio Explorer" not in combined


def test_compare_reachable_after_selected_paths() -> None:
    # Simulate progress just before whatif, set selected paths, then advance
    steps = steps_for_track(DemoTrack.STANDALONE)
    whatif_index = [s.key for s in steps].index("whatif")
    # progress at whatif step
    progress = GuidedDemoProgress(
        track=DemoTrack.STANDALONE,
        step_index=whatif_index,
        completed_step_keys=tuple(s.key for s in steps[:whatif_index]),
        active=True,
    )
    assert progress.current_step.key == "whatif"
    # completing whatif (reviewed) moves to compare
    next_progress = progress.complete_current()
    assert next_progress.current_step.key == "compare"
    assert next_progress.step_index == whatif_index + 1
    assert "whatif" in next_progress.completed_step_keys


def test_progress_persistence_deterministic() -> None:
    progress = GuidedDemoProgress(track=DemoTrack.STANDALONE, step_index=0)
    dumped = progress.model_dump(mode="json")
    restored = GuidedDemoProgress.model_validate(dumped)

    assert restored == progress
    # Re-serialize round-trip
    assert restored.model_dump(mode="json") == dumped


def test_reset_resume_behavior_preserved() -> None:
    progress = GuidedDemoProgress(
        track=DemoTrack.STANDALONE,
        step_index=2,
        completed_step_keys=("plan", "validate"),
        active=True,
    )
    exited = progress.exit()
    assert exited.active is False
    resumed = exited.resume()
    assert resumed.active is True
    assert resumed.step_index == 2
    previous = resumed.previous()
    assert previous.step_index == 1


def test_standalone_guided_page_renders_whatif_stage() -> None:
    # AppTest for guided demo should list 9 stages and show whatif instruction
    from copy import deepcopy

    from traffictwin.ui.state import default_session_state

    app = AppTest.from_file(GUIDED_APP)
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=25)

    assert not app.exception
    # Expand full journey should mention Build a what-if experiment
    full = " ".join(str(m.value) for m in app.markdown)
    captions = " ".join(str(c.value) for c in app.caption)
    assert (
        "Build a what-if experiment" in full
        or "Build a what-if experiment" in captions
        or "whatif" in full.lower()
    )
    # Verify stage count reflects 9
    # The header in guided_demo page shows Stage X of N
    subheaders = " ".join(str(s.value) for s in app.subheader)
    # Initially should be Stage 1 of 9
    assert "Stage 1 of 9" in subheaders
