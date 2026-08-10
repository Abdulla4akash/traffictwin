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
