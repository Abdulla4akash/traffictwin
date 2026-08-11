"""UI tests for Baseline Registry."""

from __future__ import annotations

import pathlib
import re
import tempfile

from streamlit.testing.v1 import AppTest


def _run_baseline_page(script: str) -> AppTest:
    """Helper to run a temporary Streamlit script."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    runner = tmp / "runner.py"
    runner.write_text(script, encoding="utf-8")
    at = AppTest.from_file(str(runner), default_timeout=30)
    at.run()
    return at


def test_baseline_registry_page_renders() -> None:
    at = _run_baseline_page(
        """
from traffictwin.ui.pages.baseline_registry import render
from traffictwin.ui.state import load_ui_config
render(load_ui_config())
"""
    )
    assert not at.exception, f"Page raised: {at.exception}"
    titles = [str(t.value) for t in at.title]
    assert any("Baseline Registry" in t for t in titles), f"titles: {titles}"
    all_warnings = [str(w.value) for w in at.warning]
    all_captions = [str(c.value) for c in at.caption]
    assert any("never promoted automatically" in w for w in all_warnings) or any(
        "never promoted automatically" in c for c in all_captions
    )
    subheaders = [str(s.value) for s in at.subheader]
    assert any("Current active baselines" in s for s in subheaders)
    assert any("Candidates" in s for s in subheaders)
    all_text = " ".join([str(x.value) for x in at.markdown] + all_captions + all_warnings)
    assert "explicit approval" in all_text.lower() or "promotion requires" in all_text.lower()


def test_baseline_registry_app_page_renders() -> None:
    at = AppTest.from_file("src/traffictwin/ui/app_pages/baseline_registry.py", default_timeout=30)
    at.run()
    assert not at.exception


def test_baseline_registry_page_has_useful_empty_state(monkeypatch: object) -> None:  # noqa: ANN001
    at = _run_baseline_page(
        """
from traffictwin.baseline_registry.service import create_empty_registry
import streamlit as st
st.session_state["baseline_registry_state"] = create_empty_registry()
from traffictwin.ui.pages.baseline_registry import render
from traffictwin.ui.state import load_ui_config
render(load_ui_config())
"""
    )
    assert not at.exception
    infos = [str(i.value) for i in at.info]
    captions = [str(c.value) for c in at.caption]
    assert any(
        "No baseline candidate" in i or "No active baseline" in c for i in infos for c in captions
    ) or any("No active baseline" in c for c in captions)


def test_baseline_registry_cli_commands() -> None:
    import json

    from typer.testing import CliRunner

    from traffictwin.baseline_registry.cli import app

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        reg_path = pathlib.Path(td) / "reg.json"
        result = runner.invoke(app, ["init", "--registry", str(reg_path)])
        assert result.exit_code == 0, result.output
        result = runner.invoke(app, ["validate", "--registry", str(reg_path)])
        assert result.exit_code == 0, result.output
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
        result = runner.invoke(
            app,
            ["approve", "--candidate-id", "cli-cand-001", "--registry", str(reg_path)],
        )
        assert result.exit_code == 0, result.output
        result = runner.invoke(
            app,
            ["promote", "--candidate-id", "cli-cand-001", "--registry", str(reg_path)],
        )
        assert result.exit_code == 0, result.output
        result = runner.invoke(app, ["show", "--registry", str(reg_path)])
        assert result.exit_code == 0
        assert "cli-cand-001" in result.output
        out = pathlib.Path(td) / "out.json"
        result = runner.invoke(
            app, ["export", "--registry", str(reg_path), "--output", str(out), "--format", "json"]
        )
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert "candidates" in data


def test_baseline_registry_cli_missing_path_fails() -> None:
    from typer.testing import CliRunner

    from traffictwin.baseline_registry.cli import app

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        missing = pathlib.Path(td) / "typo.json"
        for args in [
            ["show", "--registry", str(missing)],
            ["approve", "--candidate-id", "x", "--registry", str(missing)],
            ["promote", "--candidate-id", "x", "--registry", str(missing)],
            ["supersede", "--scope-id", "s", "--candidate-id", "x", "--registry", str(missing)],
            ["restore", "--scope-id", "s", "--candidate-id", "x", "--registry", str(missing)],
            ["validate", "--registry", str(missing)],
        ]:
            result = runner.invoke(app, args)
            assert result.exit_code != 0, (
                f"expected non-zero for {args} got {result.exit_code} output {result.output}"
            )


def test_baseline_registry_cli_init_and_register_flow() -> None:
    from typer.testing import CliRunner

    from traffictwin.baseline_registry.cli import app

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as td:
        reg_path = pathlib.Path(td) / "reg.json"
        result = runner.invoke(app, ["init", "--registry", str(reg_path)])
        assert result.exit_code == 0
        assert reg_path.exists()
        result = runner.invoke(app, ["init", "--registry", str(reg_path)])
        assert result.exit_code != 0
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


def test_baseline_registry_page_no_duplicate_labels() -> None:
    def normalize(label: str) -> str:
        return re.sub(r"\s+", " ", label.strip().lower())

    at = _run_baseline_page(
        """
from traffictwin.ui.pages.baseline_registry import render
from traffictwin.ui.state import load_ui_config
render(load_ui_config())
"""
    )
    assert not at.exception
    labels: list[str] = []
    for w in at.text_input:
        labels.append(str(w.label))
    for w2 in at.selectbox:
        labels.append(str(w2.label))
    normed = [normalize(lbl) for lbl in labels if lbl]
    seen: dict[str, int] = {}
    dups: list[str] = []
    for n in normed:
        seen[n] = seen.get(n, 0) + 1
        if seen[n] == 2:
            dups.append(n)
    assert not dups, f"duplicate normalized labels found: {dups} raw labels {labels}"
    titles = [str(t.value) for t in at.title]
    assert len([t for t in titles if "Baseline Registry" in t]) >= 1
    warnings = [str(w.value) for w in at.warning]
    assert any("never promoted automatically" in w for w in warnings)


def test_baseline_registry_page_renders_withdrawn_limitation() -> None:
    at = _run_baseline_page(
        """
from traffictwin.ui.pages.baseline_registry import render
from traffictwin.ui.state import load_ui_config
render(load_ui_config())
"""
    )
    assert not at.exception
    texts: list[str] = []
    for col in [at.markdown, at.caption, at.expander, at.warning]:
        for v in col:  # type: ignore[attr-defined]
            texts.append(str(v.value) if hasattr(v, "value") else str(v))
    combined = " ".join(texts).lower()
    assert "does not deactivate" in combined and "withdraw" in combined, (
        f"withdrawn-active limitation not rendered: {combined[:2000]}"
    )
    assert "no separate deactivate" in combined


def test_baseline_registry_page_withdraw_active_shows_warning_and_flags() -> None:
    """Withdrawing the active candidate must warn and show withdrawn flags in tables."""
    at = _run_baseline_page(
        """
from datetime import UTC, datetime
import streamlit as st
from traffictwin.baseline_registry.models import BaselineScope
from traffictwin.baseline_registry.models import (
    BaselinePromotionOperation,
    BaselinePromotionRequest,
)
from traffictwin.baseline_registry.service import (
    approve_candidate,
    build_candidate,
    create_empty_registry,
    promote_baseline,
    register_candidate,
)
from traffictwin.ui.pages.baseline_registry import render
from traffictwin.ui.state import load_ui_config

def _fixed():
    return datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

scope = BaselineScope(
    scope_id="scope-a",
    purpose="Traffic corridor evaluation for synthetic baseline demonstration",
    cohort_definition="Matched random seeds 1..5 under synthetic plan A",
    allowed_evidence_standings=("admitted_research",),
)
reg = create_empty_registry(clock=_fixed)
cand = build_candidate(
    candidate_id="cand-active",
    scope=scope,
    artifact_fingerprint="a"*64,
    artifact_type="metric_collection",
    schema_version="1.0.0",
    metric_contracts=["task.completion.rate@1.0"],
    cohort_definition=scope.cohort_definition,
    evidence_standing="admitted_research",
    source_standing="verified",
    regression_gate_policy="STA-04 exact synthetic baseline policy",
    limitations="Synthetic demonstration only; no causal claim.",
    clock=_fixed,
)
reg = register_candidate(reg, cand, clock=_fixed)
reg, appr = approve_candidate(
    reg,
    candidate_id="cand-active",
    approver="alice",
    approval_note="Approval note with sufficient length for gate.",
    clock=_fixed,
)
req = BaselinePromotionRequest(
    candidate_id="cand-active",
    scope_id=scope.scope_id,
    artifact_fingerprint="a"*64,
    approval_fingerprint=appr.approval_fingerprint,
    registry_parent_fingerprint=reg.registry_fingerprint,
    requested_by="operator",
    requested_at=_fixed(),
    operation=BaselinePromotionOperation.PROMOTE,
)
reg, _ = promote_baseline(reg, req, clock=_fixed)
if "baseline_registry_state" not in st.session_state:
    st.session_state["baseline_registry_state"] = reg
render(load_ui_config())
"""
    )
    assert not at.exception, f"setup failed: {at.exception}"

    # Verify initial active and not withdrawn before interaction (prove scaffold not hiding)
    # Inspect state via page's session state after first render
    # Use direct AppTest session state: the registry should have active candidate not withdrawn
    # We check via dataframe before withdraw to ensure test is not vacuous
    initial_found = False
    for df in at.dataframe:
        val = df.value if hasattr(df, "value") else None
        if val is not None:
            import pandas as pd  # type: ignore[import-untyped]

            if (
                isinstance(val, pd.DataFrame)
                and "candidate_id" in val.columns
                and (val["candidate_id"] == "cand-active").any()
            ):
                initial_found = True
                if "candidate_withdrawn" in val.columns:
                    row = val[val["candidate_id"] == "cand-active"]
                    assert not row.empty
                    assert bool(row.iloc[0]["candidate_withdrawn"]) is False, (
                        "initially should not be withdrawn"
                    )
                if "withdrawn" in val.columns:
                    row2 = val[val["candidate_id"] == "cand-active"]
                    if not row2.empty and "withdrawn" in val.columns:
                        # candidates table withdrawn flag should be False initially
                        assert bool(row2.iloc[0]["withdrawn"]) is False or str(
                            row2.iloc[0]["withdrawn"]
                        ).lower() in ("false", "no")
    assert initial_found, "cand-active not found in initial tables — scaffold failed"

    at.text_input(key="baseline_withdraw_cand").set_value("cand-active").run()
    at.text_input(key="baseline_withdraw_actor").set_value("operator").run()
    at.button(key="baseline_withdraw_button").click().run()

    warnings = [str(w.value) for w in at.warning]
    combined_warn = " ".join(warnings).lower()
    assert "withdrawn" in combined_warn, f"warning missing withdrawn: {warnings}"
    assert "remains active" in combined_warn, f"warning missing remains active: {warnings}"
    assert "supersed" in combined_warn

    # Prove warning explicitly says it remains active until superseded (not just generic)
    assert "remains active" in combined_warn and "until" in combined_warn

    # Inspect ledger and active record directly via session state after rerun
    import streamlit as st  # noqa: F401

    # Retrieve registry from AppTest session_state (survives rerun)
    reg_after = at.session_state["baseline_registry_state"]
    # Ledger must contain new WITHDRAWN
    from traffictwin.baseline_registry.models import BaselineLedgerEventKind

    assert len(reg_after.ledger) >= 1
    # Find delta: last event should be WITHDRAWN for cand-active
    # Since initial ledger had promote, the new event is at end
    last = reg_after.ledger[-1]
    assert last.event_kind is BaselineLedgerEventKind.WITHDRAWN
    assert last.candidate_id == "cand-active"
    assert last.scope_id == "scope-a"
    # Active baseline still references that candidate
    assert "scope-a" in reg_after.active_baselines
    assert reg_after.active_baselines["scope-a"].candidate_id == "cand-active"

    # Check that active table still shows withdrawn flag — now without swallowing
    found_active = False
    found_candidate = False
    for df in at.dataframe:
        val = df.value if hasattr(df, "value") else None
        if val is None:
            continue
        import pandas as pd

        if not isinstance(val, pd.DataFrame):
            continue
        if "candidate_id" not in val.columns:
            continue
        # Active baselines table has candidate_withdrawn column
        if "candidate_withdrawn" in val.columns and (val["candidate_id"] == "cand-active").any():
            found_active = True
            row = val[val["candidate_id"] == "cand-active"]
            assert not row.empty, "active baseline row for cand-active missing"
            assert "candidate_withdrawn" in val.columns, (
                "candidate_withdrawn column missing in active table"
            )
            assert bool(row.iloc[0]["candidate_withdrawn"]) is True, (
                "active row candidate_withdrawn must be True"
            )
            assert row.iloc[0]["status"] == "active", (
                f"status should be active, got {row.iloc[0]['status']}"
            )
        # Candidates table has withdrawn column
        if "withdrawn" in val.columns and (val["candidate_id"] == "cand-active").any():
            found_candidate = True
            row2 = val[val["candidate_id"] == "cand-active"]
            assert not row2.empty, "candidate row for cand-active missing"
            assert "withdrawn" in val.columns, "withdrawn column missing in candidates table"
            assert (
                bool(row2.iloc[0]["withdrawn"]) is True
                or str(row2.iloc[0]["withdrawn"]).lower() == "true"
            ), "candidates withdrawn must be True"
            # active flag should still be yes/True in candidates table
            if "active" in val.columns:
                assert str(row2.iloc[0]["active"]).lower() in ("yes", "true"), (
                    f"active flag should be yes/True, got {row2.iloc[0]['active']}"
                )

    assert found_active, (
        "active-baselines dataframe row for cand-active with candidate_withdrawn=True not found"
    )
    assert found_candidate, "candidates dataframe row for cand-active with withdrawn=True not found"
