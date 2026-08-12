# ruff: noqa: E501, F841, S108, B017
"""UI / AppTest coverage for Study Workspace page."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from traffictwin.study_workspace.models import (
    StudyWorkspaceManifest,
    WorkspaceArtifactKind,
    WorkspaceArtifactRef,
    WorkspaceArtifactStanding,
    WorkspaceAvailabilityState,
    WorkspaceCompatibilityStanding,
    WorkspaceLifecycleStage,
)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _demo_manifest() -> StudyWorkspaceManifest:
    return StudyWorkspaceManifest(
        workspace_id="ws-ui-001",
        workspace_version="1.0",
        study_id="study-ui-001",
        study_title="UI Test Workspace",
        description="Synthetic workspace for UI AppTest.",
        artifacts=[
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.SOURCE_CONTRACT,
                fingerprint=_fp("ui-contract"),
                schema_version="1.0",
                label="source-contract-ui",
                standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.PREREGISTRATION_PLAN,
                fingerprint=_fp("ui-plan"),
                schema_version="1.0",
                label="plan-ui",
                parent_fingerprint=_fp("ui-contract"),
                standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.EVIDENCE_ATTACHMENT,
                fingerprint=_fp("ui-evidence"),
                schema_version="1.0",
                label="evidence-ui",
                parent_fingerprint=_fp("ui-plan"),
                standing=WorkspaceArtifactStanding.SYNTHETIC_EVIDENCE,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
        ],
        limitations=["synthetic only"],
    )


def test_ui_page_is_thin_calls_production() -> None:
    """Page must delegate to typed service, not recompute results."""
    source = Path("src/traffictwin/ui/pages/study_workspace.py").read_text(encoding="utf-8")
    assert "from traffictwin.study_workspace.service import" in source
    assert "validate_workspace" in source
    assert "fingerprint_manifest" in source
    assert "def _canonical_json" not in source
    assert "hashlib.sha256" not in source  # page should not recompute fingerprint


def test_ui_manifest_load_and_validate_round_trip(tmp_path: Path) -> None:
    from traffictwin.study_workspace.exports import export_workspace_json
    from traffictwin.study_workspace.service import validate_workspace

    manifest = _demo_manifest()
    json_str = export_workspace_json(manifest)
    data = json.loads(json_str)
    # Portable export includes workspace_fingerprint for convenience; loader must handle it
    assert "workspace_fingerprint" in data
    data.pop("workspace_fingerprint", None)
    # Simulate file save/load
    p = tmp_path / "workspace.json"
    p.write_text(json_str, encoding="utf-8")
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw.pop("workspace_fingerprint", None)
    loaded = StudyWorkspaceManifest.model_validate(raw)
    assert loaded.workspace_id == manifest.workspace_id
    assert validate_workspace(loaded).is_valid


def test_apptest_renders_study_workspace_page() -> None:
    """AppTest smoke: Study Workspace renders without exception and shows key labels."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")

    # Use the wrapper script; the fallback wrapper handles missing enum gracefully
    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    try:
        from traffictwin.ui.state import UiConfig, default_session_state, load_ui_config

        try:
            config = load_ui_config()
        except Exception:
            config = UiConfig()
        try:
            state = default_session_state(config)
        except Exception:
            state = {}
        for k, v in state.items():
            app.session_state[k] = v
        app.session_state["_v07_navigation_active"] = False
    except Exception:  # noqa: S110
        pass

    result = app.run(timeout=30)
    assert not result.exception, f"Study Workspace page raised: {result.exception}"

    # Collect rendered texts
    texts: list[str] = []
    for coll in (
        result.title,
        result.subheader,
        result.markdown,
        result.caption,
        result.info,
        result.warning,
        result.error,
        result.success,
    ):
        try:
            texts.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    joined = " ".join(texts)

    # Must use one authoritative H1
    h1_count = len(list(result.title))
    assert h1_count == 1, f"expected exactly one H1, got {h1_count}"
    assert "Study Workspace" in joined

    # Evidence / authority boundary must be visible before results
    assert (
        "references and explains existing TrafficTwin research artifacts" in joined
        or "Evidence and authority" in joined
        or "This workspace references" in joined
    )

    # Must show empty state guidance or identity banner
    assert (
        "No workspace manifest" in joined
        or "Study identity" in joined
        or "Lifecycle stage" in joined
    )

    # Accessibility: check heading count — at least one subheader grouping must exist
    subheaders = list(result.subheader)
    assert len(subheaders) >= 1


def test_apptest_empty_state_shows_guidance() -> None:
    """When no manifest is loaded, the page shows useful empty state, not a crash."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")

    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    try:
        app.session_state["study_workspace_path"] = ""
        app.session_state["study_workspace_uploaded_text"] = None
        app.session_state["_v07_navigation_active"] = False
    except Exception:  # noqa: S110
        pass
    result = app.run(timeout=30)
    assert not result.exception
    texts: list[str] = []
    for coll in (result.caption, result.info, result.markdown, result.warning):
        try:
            texts.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    joined = " ".join(texts)
    assert "No workspace manifest" in joined or "synthetic fixture" in joined.lower()


def test_page_renders_with_uploaded_manifest(tmp_path: Path) -> None:
    """Page renders correctly when a valid manifest is uploaded via session state."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")

    manifest = _demo_manifest()
    json_str = json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False)
    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    app.session_state["study_workspace_uploaded_text"] = json_str
    app.session_state["_v07_navigation_active"] = False
    result = app.run(timeout=30)
    assert not result.exception
    texts2: list[str] = []
    for coll in (result.caption, result.markdown, result.info, result.warning, result.subheader):
        try:
            texts2.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    joined = " ".join(texts2)
    assert "Study identity" in joined or "Lifecycle stage" in joined
    # Standing must be shown
    assert "synthetic" in joined.lower() or "authored" in joined.lower()


def test_no_duplicate_widget_keys_in_page_source() -> None:
    source = Path("src/traffictwin/ui/pages/study_workspace.py").read_text(encoding="utf-8")
    # Extract keys= values
    import re

    keys = re.findall(r'key="([^"]+)"', source)
    assert len(keys) == len(set(keys)), f"duplicate widget keys found: {keys}"


def test_page_preserves_unavailable_states() -> None:
    # Build a manifest with unavailable artifact and ensure page would surface it
    unavailable = StudyWorkspaceManifest(
        workspace_id="ws-unavail-ui",
        workspace_version="1.0",
        study_id="study-unavail-ui",
        artifacts=[
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.METRIC_COLLECTION,
                fingerprint=_fp("unavail-ui"),
                schema_version="1.0",
                label="missing-metric",
                standing=WorkspaceArtifactStanding.UNAVAILABLE,
                compatibility_standing=WorkspaceCompatibilityStanding.NOT_APPLICABLE,
                availability=WorkspaceAvailabilityState.UNAVAILABLE,
                reason="metric collection not generated — unavailable, not zero",
            )
        ],
        limitations=["synthetic"],
    )
    # Export and check unavailable preserved
    from traffictwin.study_workspace.exports import export_workspace_json

    j = export_workspace_json(unavailable)
    data = json.loads(j)
    assert any(a["availability"] == "unavailable" for a in data["artifacts"])
    assert any("not generated" in (a.get("reason") or "") for a in data["artifacts"])


def test_page_has_accessibility_heading() -> None:
    source = Path("src/traffictwin/ui/pages/study_workspace.py").read_text(encoding="utf-8")
    # Must have at least one subheader call (which renders h2/h3 for navigation)
    assert "st.subheader(" in source
    # Must have caption before results explaining evidence boundary
    assert "Evidence and authority" in source or "evidence" in source.lower()


def test_synthetic_fixture_button_loads_workspace() -> None:
    """First-click loads the built-in synthetic workspace via typed boundary."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")

    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    app.session_state["study_workspace_path"] = ""
    app.session_state["study_workspace_uploaded_text"] = None
    app.session_state["_v07_navigation_active"] = False
    result = app.run(timeout=30)
    assert not result.exception
    # Honest empty state before click
    texts_before: list[str] = []
    for coll in (result.caption, result.info, result.markdown):
        try:
            texts_before.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    joined_before = " ".join(texts_before)
    assert "No workspace manifest" in joined_before
    # Path input should be blank (honest)
    # AppTest text_input value check: find the path input
    path_inputs = [w for w in result.text_input if w.key == "study_workspace_path_input"]
    if path_inputs:
        assert path_inputs[0].value == "" or path_inputs[0].value is None

    # Click Load synthetic fixture
    btn = next((b for b in result.button if b.key == "study_workspace_load_fixture"), None)
    assert btn is not None, "Load synthetic fixture button not found"
    btn.click()
    result2 = app.run(timeout=30)
    assert not result2.exception, f"After click raised: {result2.exception}"
    texts2: list[str] = []
    for coll in (  # type: ignore[assignment]
        result2.caption,
        result2.markdown,
        result2.info,
        result2.subheader,
        result2.success,
    ):
        try:
            texts2.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    joined2 = " ".join(texts2)
    assert "Study identity" in joined2 or "Lifecycle stage" in joined2
    assert "No workspace manifest" not in joined2 or "Study identity" in joined2  # no longer empty
    assert "manifest not found" not in joined2.lower()


def test_initial_empty_state_is_honest() -> None:
    """Path blank and empty state are consistent; no phantom fixture path shown."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")
    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    app.session_state["study_workspace_path"] = ""
    app.session_state["study_workspace_uploaded_text"] = None
    app.session_state["_v07_navigation_active"] = False
    result = app.run(timeout=30)
    assert not result.exception
    # Path input blank
    path_inputs = [w for w in result.text_input if w.key == "study_workspace_path_input"]
    assert path_inputs and path_inputs[0].value == ""
    # Empty state visible
    texts: list[str] = []
    for coll in (result.info, result.caption):
        try:
            texts.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    assert "No workspace manifest" in " ".join(texts)


def test_bounded_columns_large_group_renders() -> None:
    """Large artifact group (20) renders with bounded layout, no 20-column fan-out."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")
    # Build a manifest with 20 generic artifacts (same kind, different fingerprints)
    arts = [
        WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.GENERIC_REPORT,
            fingerprint=hashlib.sha256(f"large-{i}".encode()).hexdigest(),
            schema_version="1.0",
            label=f"large-{i}",
            standing=WorkspaceArtifactStanding.SYNTHETIC_EVIDENCE,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
        for i in range(20)
    ]
    manifest = StudyWorkspaceManifest(
        workspace_id="ws-large",
        workspace_version="1.0",
        study_id="study-large",
        artifacts=arts,
        limitations=["synthetic"],
    )
    json_str = manifest.model_dump_json()
    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    app.session_state["study_workspace_uploaded_text"] = json_str
    app.session_state["study_workspace_path"] = ""
    app.session_state["_v07_navigation_active"] = False
    result = app.run(timeout=30)
    assert not result.exception, f"Large group raised: {result.exception}"
    # Source must contain bounded logic
    source = Path("src/traffictwin/ui/pages/study_workspace.py").read_text(encoding="utf-8")
    assert "max_cols = 4" in source
    assert "st.columns(len(refs))" not in source or "max_cols" in source
    # Page should still show inventory
    texts: list[str] = []
    for coll in (result.caption, result.markdown, result.subheader):
        try:
            texts.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    assert "Artifact inventory" in " ".join(texts)


def test_progression_excludes_blocked() -> None:
    source = Path("src/traffictwin/ui/pages/study_workspace.py").read_text(encoding="utf-8")
    # Normal progression should be explicit without BLOCKED
    assert "normal_progression" in source
    assert "BLOCKED is a validation state" in source
    # Ensure the old unbounded progression string not present
    # The new progression lists 9 stages, blocked separate
    assert "draft" in source.lower()
    assert "archived" in source.lower()


def test_synthetic_fixture_clears_non_empty_path_input() -> None:
    """B4: Load synthetic fixture must override a non-empty path."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")

    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    app.session_state["study_workspace_path"] = ""
    app.session_state["study_workspace_uploaded_text"] = None
    app.session_state["_v07_navigation_active"] = False
    result = app.run(timeout=30)
    assert not result.exception
    # Set non-empty path via text_input
    path_inputs = [w for w in result.text_input if w.key == "study_workspace_path_input"]
    assert path_inputs, "path input not found"
    # Simulate typing non-empty value
    path_inputs[0].set_value("some-non-empty-value.json").run(timeout=30)
    # After rerun, there will be a new result with non-empty path
    result_after_typing = app.run(timeout=30)
    # Now click Load synthetic fixture
    btn = next(
        (b for b in result_after_typing.button if b.key == "study_workspace_load_fixture"), None
    )
    assert btn is not None, "Load synthetic fixture button not found after typing"
    btn.click()
    result2 = app.run(timeout=30)
    assert not result2.exception, f"After click with non-empty path raised: {result2.exception}"
    # Path input must be empty
    path_inputs2 = [w for w in result2.text_input if w.key == "study_workspace_path_input"]
    assert path_inputs2, "path input missing after fixture"
    # The widget value should be empty string
    assert path_inputs2[0].value == "" or path_inputs2[0].value is None, (
        f"path not cleared: {path_inputs2[0].value!r}"
    )
    # Synthetic manifest remains loaded
    try:
        uploaded = app.session_state["study_workspace_uploaded_text"]
    except KeyError:
        uploaded = None
    assert uploaded, "uploaded_text should remain after clearing path"
    # Synthetic workspace content is rendered
    texts2: list[str] = []
    for coll in (
        result2.caption,
        result2.markdown,
        result2.info,
        result2.subheader,
        result2.success,
    ):
        try:
            texts2.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    joined2 = " ".join(texts2)
    assert "Study identity" in joined2 or "Lifecycle stage" in joined2, (
        f"Missing workspace render: {joined2[:500]}"
    )
    # Ensure not popped by stale path logic: still shows synthetic, not empty
    assert "No workspace manifest" not in joined2 or "Study identity" in joined2


def test_app_pages_wrapper_is_direct_and_no_fallback() -> None:
    """B5 intent, registered form: no swallowed exception, no fallback config.

    The wrapper was pinned as a direct ``render(load_ui_config())`` call while
    the page was unregistered. V4 final integration registered the page, so
    the wrapper now takes the one central runtime path every registered page
    uses (``run_page_script``), which loads the real config via
    ``load_ui_config()`` and propagates renderer exceptions unchanged. The
    B5 guarantees this test protects are unchanged; only the wrapper form is.
    """
    source = Path("src/traffictwin/ui/app_pages/study_workspace.py").read_text(encoding="utf-8")
    assert "run_page_script(UiPage.STUDY_WORKSPACE)" in source
    assert "except Exception" not in source
    assert "UiConfig()" not in source  # no fallback UiConfig()


def test_wrapper_renders_with_one_h1_and_boundaries() -> None:
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")
    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    app.session_state["_v07_navigation_active"] = False
    result = app.run(timeout=30)
    assert not result.exception, f"Wrapper raised: {result.exception}"
    # One H1
    h1_count = len(result.title)  # title corresponds to H1
    # Alternative: check header
    assert h1_count == 1, f"Expected 1 H1, got {h1_count}: {[t.value for t in result.title]}"
    texts: list[str] = []
    for coll in (result.caption, result.info, result.markdown, result.warning):
        try:
            texts.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    joined = " ".join(texts)
    assert (
        "without copying or silently modifying" in joined.lower()
        or "evidence and authority" in joined.lower()
        or "synthetic" in joined.lower()
    )
    # Boundaries visible
    assert (
        "never admits evidence" in joined.lower()
        or "synthetic evidence is never" in joined.lower()
        or "without copying" in joined.lower()
    )


def test_wrapper_does_not_swallow_renderer_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """B5: prove wrapper no longer swallows renderer exceptions."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")

    # Patch the registered renderer entry the central runtime dispatches to.
    from traffictwin.ui.labels import UiPage
    from traffictwin.ui.page_runtime import PAGE_RENDERERS

    def _failing_render(_config: object) -> None:  # noqa: ANN001
        raise RuntimeError("synthetic renderer failure for test")

    monkeypatch.setitem(PAGE_RENDERERS, UiPage.STUDY_WORKSPACE, _failing_render)
    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    app.session_state["_v07_navigation_active"] = False
    result = app.run(timeout=30)
    # Should have exception, not be swallowed
    assert result.exception is not None, "Wrapper swallowed exception, expected propagation"
    assert "synthetic renderer failure" in str(result.exception)


def test_declared_derived_stage_caption_shows_actual_values() -> None:
    """Regression for lost f-prefix: caption must show real stages, not literals."""
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"AppTest not available: {exc}")

    # Build a manifest where derived stage is known and declared_stage is explicit.
    # Use plan + report + capsule -> derived REVIEW_READY, declared REVIEW_READY.
    c_fp = _fp("ui-cap-c")
    p_fp = _fp("ui-cap-p")
    rep_fp = _fp("ui-cap-rep")
    cap_fp = _fp("ui-cap-cap")
    manifest = StudyWorkspaceManifest(
        workspace_id="ws-ui-declared",
        workspace_version="1.0",
        study_id="study-ui-declared",
        artifacts=[
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.SOURCE_CONTRACT,
                fingerprint=c_fp,
                schema_version="1.0",
                label="contract-declared",
                standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.PREREGISTRATION_PLAN,
                fingerprint=p_fp,
                schema_version="1.0",
                label="plan-declared",
                parent_fingerprint=c_fp,
                standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.EVENT_ALIGNED_REPORT,
                fingerprint=rep_fp,
                schema_version="1.0",
                label="report-declared",
                parent_fingerprint=p_fp,
                standing=WorkspaceArtifactStanding.NOT_APPLICABLE,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
            WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.STUDY_CAPSULE_MANIFEST,
                fingerprint=cap_fp,
                schema_version="1.0",
                label="capsule-declared",
                standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            ),
        ],
        declared_stage=WorkspaceLifecycleStage.REVIEW_READY,
    )
    # Also need to ensure derived is REVIEW_READY: with plan+report+capsule and compatible/unavailable resolved, it should be REVIEW_READY
    # Provide explicit JSON via uploaded_text path
    json_str = manifest.model_dump_json()
    app = AppTest.from_file("src/traffictwin/ui/app_pages/study_workspace.py")
    app.session_state["study_workspace_uploaded_text"] = json_str
    app.session_state["study_workspace_path"] = ""
    app.session_state["_v07_navigation_active"] = False
    result = app.run(timeout=30)
    assert not result.exception, f"Render raised: {result.exception}"
    # Find caption containing Declared stage
    texts: list[str] = []
    for coll in (result.caption, result.info, result.markdown, result.warning):
        try:
            texts.extend(str(getattr(item, "value", "")) for item in coll)
        except Exception:  # noqa: S112
            continue
    joined = " ".join(texts)
    # Concrete values must appear
    assert "review_ready" in joined.lower() or "REVIEW_READY" in joined, (
        f"Missing review_ready in {joined[:800]}"
    )
    # Also check literal placeholders do NOT appear
    assert "{manifest.declared_stage.value}" not in joined, (
        f"Literal placeholder leaked: {joined[:800]}"
    )
    assert "{derived_stage.value}" not in joined, f"Literal placeholder leaked: {joined[:800]}"
    # Ensure the caption shows both declared and derived
    assert "Declared stage:" in joined
    assert "Derived stage:" in joined
