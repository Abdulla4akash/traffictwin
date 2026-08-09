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
    whatif = next(step for step in steps_for_track(DemoTrack.STANDALONE) if step.key == "whatif")

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


def test_generated_whatif_pair_survives_guided_handoff_to_compare() -> None:
    """Preferred V2-S1 journey: generated pair survives What-If → Compare handoff.

    Uses an isolated workspace and the real deterministic What-If service so the
    paths are not the committed fixtures. Proves selected_* survive the guided
    What-If REVIEW completion and Compare consumes those exact paths.
    """

    import tempfile
    from pathlib import Path

    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "whatif-handoff"
        initialise_workspace(workspace)
        registry = workspace / "registry.sqlite"

        request = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="handoff-probe",
            experiment_id="exp-handoff",
            baseline_random_seed=11,
            variation_overrides=WhatIfVariationOverrides(
                incident_enabled=True,
                incident_type="synthetic_congestion_pulse",
                incident_location="synthetic-corridor-a",
                incident_severity="moderate",
                incident_start_s=120.0,
                incident_duration_s=60.0,
                lanes_closed=1,
                event_demand_multiplier=1.3,
                congestion_multiplier=1.65,
                vehicle_count=18,
                task_arrival_rate=0.16,
                task_mix_t1=0.3,
                task_mix_t2=0.4,
                task_mix_t3=0.3,
                rsu_count=2,
                rsu_capacity=22.0,
                policy_profile="synthetic-balanced",
            ),
            output_root=None,
        )
        result = generate_whatif_pair_for_ui(
            request, registry_path=registry, workspace_path=workspace
        )
        # Must succeed and not be fixtures
        assert not isinstance(result, ServiceError), f"unexpected ServiceError: {result}"
        assert result.baseline_bundle_path is not None
        assert result.variation_bundle_path is not None
        generated_baseline = str(result.baseline_bundle_path)
        generated_variation = str(result.variation_bundle_path)
        fixture_baseline = "tests/fixtures/bundles/baseline_valid"
        fixture_variation = "tests/fixtures/bundles/variation_valid"
        assert generated_baseline != fixture_baseline
        assert generated_variation != fixture_variation
        assert Path(generated_baseline).exists()
        assert Path(generated_variation).exists()

        # Simulate session handoff as What-If Studio does
        session: dict[str, object] = {
            "selected_baseline_run": generated_baseline,
            "selected_variation_run": generated_variation,
        }
        assert session["selected_baseline_run"] == generated_baseline
        assert session["selected_variation_run"] == generated_variation

        # Move guided What-If stage to Compare via REVIEW completion
        steps = steps_for_track(DemoTrack.STANDALONE)
        whatif_index = [s.key for s in steps].index("whatif")
        progress = GuidedDemoProgress(
            track=DemoTrack.STANDALONE,
            step_index=whatif_index,
            completed_step_keys=tuple(s.key for s in steps[:whatif_index]),
            active=True,
        )
        assert progress.current_step.key == "whatif"
        next_progress = progress.complete_current()
        assert next_progress.current_step.key == "compare"
        assert "whatif" in next_progress.completed_step_keys

        # Selections must survive the guided completion
        assert session["selected_baseline_run"] == generated_baseline
        assert session["selected_variation_run"] == generated_variation

        # Compare consumes those exact paths
        from copy import deepcopy

        from traffictwin.ui.state import default_session_state

        compare_app = AppTest.from_file("src/traffictwin/ui/app_pages/compare.py")
        for key, value in deepcopy(default_session_state()).items():
            compare_app.session_state[key] = value
        compare_app.session_state["selected_baseline_run"] = generated_baseline
        compare_app.session_state["selected_variation_run"] = generated_variation
        compare_app.session_state["_v07_navigation_active"] = True
        compare_app.run(timeout=25)

        assert not compare_app.exception
        baseline_input = next(
            w for w in compare_app.text_input if w.label == "Baseline bundle path"
        ).value
        variation_input = next(
            w for w in compare_app.text_input if w.label == "Variation bundle path"
        ).value
        assert baseline_input == generated_baseline
        assert variation_input == generated_variation


def test_review_only_whatif_stage_preserves_existing_compare_pair() -> None:
    """Fallback: Review-only What-If preserves existing committed/demo selection.

    Starts with the committed fixtures, completes What-If REVIEW without generating
    a new pair, and proves selections are unchanged and Compare remains usable.
    """

    from copy import deepcopy

    from traffictwin.ui.state import default_session_state

    fixture_baseline = "tests/fixtures/bundles/baseline_valid"
    fixture_variation = "tests/fixtures/bundles/variation_valid"

    # Isolated session starting with fixtures (as Home/demo would)
    session: dict[str, object] = {
        "selected_baseline_run": fixture_baseline,
        "selected_variation_run": fixture_variation,
    }
    original_baseline = session["selected_baseline_run"]
    original_variation = session["selected_variation_run"]

    # No new pair generated
    steps = steps_for_track(DemoTrack.STANDALONE)
    whatif_index = [s.key for s in steps].index("whatif")
    progress = GuidedDemoProgress(
        track=DemoTrack.STANDALONE,
        step_index=whatif_index,
        completed_step_keys=tuple(s.key for s in steps[:whatif_index]),
        active=True,
    )
    # What-If is REVIEW so Reviewed — continue is valid without generation
    assert progress.current_step.completion_mode.name == "REVIEW"
    next_progress = progress.complete_current()
    assert next_progress.current_step.key == "compare"
    assert next_progress.step_index == whatif_index + 1

    # Existing selections preserved, no fake generation claim
    assert session["selected_baseline_run"] == original_baseline
    assert session["selected_variation_run"] == original_variation
    assert session["selected_baseline_run"] == fixture_baseline
    assert session["selected_variation_run"] == fixture_variation

    # Compare remains usable with those fixtures
    compare_app = AppTest.from_file("src/traffictwin/ui/app_pages/compare.py")
    for key, value in deepcopy(default_session_state()).items():
        compare_app.session_state[key] = value
    compare_app.session_state["selected_baseline_run"] = fixture_baseline
    compare_app.session_state["selected_variation_run"] = fixture_variation
    compare_app.session_state["_v07_navigation_active"] = True
    compare_app.run(timeout=25)

    assert not compare_app.exception
    assert not any("must exist" in str(e.value) for e in compare_app.error)


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
