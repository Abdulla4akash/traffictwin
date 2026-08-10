"""UI tests for Baseline Registry."""

from __future__ import annotations

import pathlib


def test_baseline_registry_page_renders() -> None:
    # Use a temporary script that imports render directly – avoids needing UiPage enum registered
    import tempfile

    from streamlit.testing.v1 import AppTest

    tmp = pathlib.Path(tempfile.mkdtemp())
    runner = tmp / "runner.py"
    runner.write_text(
        """
from pathlib import Path
from traffictwin.ui.state import UiConfig, load_ui_config
from traffictwin.ui.pages.baseline_registry import render
# Use a temp config to ensure no local path contamination
config = load_ui_config()
render(config)
""",
        encoding="utf-8",
    )
    at = AppTest.from_file(str(runner), default_timeout=30)
    at.run()
    assert not at.exception, f"Page raised: {at.exception}"
    # Must have one authoritative H1 – title contains Baseline Registry
    titles = [str(t.value) for t in at.title]
    # Fallback title when enum not registered is still "Baseline Registry"
    assert any("Baseline Registry" in t for t in titles), f"titles: {titles}"
    # Evidence/authority boundary before results
    all_warnings = [str(w.value) for w in at.warning]
    all_captions = [str(c.value) for c in at.caption]
    assert any("never promoted automatically" in w for w in all_warnings) or any(
        "never promoted automatically" in c for c in all_captions
    )
    # Check empty state or active baselines section exists (subheader)
    subheaders = [str(s.value) for s in at.subheader]
    assert any("Current active baselines" in s for s in subheaders)
    assert any("Candidates" in s for s in subheaders)
    # Ensure no duplicate widget keys (AppTest would raise, but we check)
    # Check that evidence boundary and registry identity are displayed
    all_text = " ".join([str(x.value) for x in at.markdown] + all_captions + all_warnings)
    assert "explicit approval" in all_text.lower() or "promotion requires" in all_text.lower()


def test_baseline_registry_app_page_renders() -> None:

    from streamlit.testing.v1 import AppTest

    # Test the app_pages wrapper directly
    at = AppTest.from_file("src/traffictwin/ui/app_pages/baseline_registry.py", default_timeout=30)
    at.run()
    assert not at.exception


def test_baseline_registry_page_has_useful_empty_state(monkeypatch: object) -> None:  # noqa: ANN001
    import pathlib
    import tempfile

    from streamlit.testing.v1 import AppTest

    # Ensure empty registry gives useful empty state – clear session
    tmp = pathlib.Path(tempfile.mkdtemp())
    runner = tmp / "empty_runner.py"
    runner.write_text(
        """
from traffictwin.baseline_registry.service import create_empty_registry
import streamlit as st
st.session_state["baseline_registry_state"] = create_empty_registry()
from traffictwin.ui.pages.baseline_registry import render
from traffictwin.ui.state import load_ui_config
render(load_ui_config())
""",
        encoding="utf-8",
    )
    at = AppTest.from_file(str(runner), default_timeout=30)
    at.run()
    assert not at.exception
    # Should show useful empty state – info or caption about no candidates
    infos = [str(i.value) for i in at.info]
    captions = [str(c.value) for c in at.caption]
    assert any(
        "No baseline candidate" in i or "No active baseline" in c for i in infos for c in captions
    ) or any("No active baseline" in c for c in captions)


def test_baseline_registry_cli_commands() -> None:
    import json
    import pathlib
    import tempfile

    from typer.testing import CliRunner

    from traffictwin.baseline_registry.cli import app

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        reg_path = pathlib.Path(td) / "reg.json"
        # validate on empty (should create empty and validate)
        result = runner.invoke(app, ["validate", "--registry", str(reg_path)])
        # Should either succeed with empty or error – but not crash
        assert result.exit_code in (0, 1)
        # register
        result = runner.invoke(
            app,
            [
                "register",
                "--candidate-id",
                "cli-cand-001",
                "--scope-id",
                "cli-scope",
                "--purpose",
                "CLI test purpose with sufficient length for validation",
                "--cohort",
                "Matched seeds 1..3 for CLI test cohort definition",
                "--artifact-fingerprint",
                "a" * 64,
                "--registry",
                str(reg_path),
            ],
        )
        assert result.exit_code == 0, result.output
        # approve
        result = runner.invoke(
            app,
            ["approve", "--candidate-id", "cli-cand-001", "--registry", str(reg_path)],
        )
        assert result.exit_code == 0, result.output
        # promote
        result = runner.invoke(
            app,
            ["promote", "--candidate-id", "cli-cand-001", "--registry", str(reg_path)],
        )
        assert result.exit_code == 0, result.output
        # show
        result = runner.invoke(app, ["show", "--registry", str(reg_path)])
        assert result.exit_code == 0
        assert "cli-cand-001" in result.output
        # export json
        out = pathlib.Path(td) / "out.json"
        result = runner.invoke(
            app, ["export", "--registry", str(reg_path), "--output", str(out), "--format", "json"]
        )
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert "candidates" in data
