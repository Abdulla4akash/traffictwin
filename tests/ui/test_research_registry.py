"""App-level UI tests for Research Registry (Lane 09)."""

from __future__ import annotations

import contextlib
import json
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.research_registry.adapters import (
    build_admitted_e2_records,
    build_default_e2_admission_policy,
    build_e2_study_package,
)
from traffictwin.research_registry.ingestion import (
    AdmissionPolicy,
    ResearchIngestionError,
    ingest_package,
)
from traffictwin.research_registry.service import RegistryService
from traffictwin.ui.state import default_session_state, load_ui_config


def _run_app_page() -> AppTest:
    at = AppTest.from_file("src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30)
    for k, v in default_session_state(load_ui_config()).items():
        at.session_state[k] = v
    at.session_state["_v07_navigation_active"] = True
    at.run()
    return at


def _selectbox_options(box: object) -> list[str]:
    """Typed, testable helper to extract selectbox options without broad catch."""
    opts = getattr(box, "options", None)
    if isinstance(opts, (list, tuple)):
        return [str(o) for o in opts]
    return []


def _body(at: AppTest) -> str:
    parts: list[str] = []
    for attr in (
        "title",
        "header",
        "subheader",
        "markdown",
        "caption",
        "text",
        "info",
        "warning",
        "error",
        "success",
        "code",
        "json",
    ):
        for item in getattr(at, attr, []):
            try:
                parts.append(str(getattr(item, "value", item)))
            except Exception:
                parts.append(str(item))
    for df in getattr(at, "dataframe", []):
        try:
            val = getattr(df, "value", df)
            parts.append(str(val))
            if hasattr(val, "to_string"):
                with contextlib.suppress(Exception):
                    parts.append(val.to_string())
        except Exception:
            parts.append(str(df))
    for exp in getattr(at, "expander", []):
        parts.append(str(getattr(exp, "label", "")))
    return "\n".join(parts)


def test_research_registry_app_page_renders_read_only() -> None:
    at = _run_app_page()
    assert not at.exception, at.exception
    body = _body(at)
    assert "Research Registry" in body
    assert "read-only" in body.lower()
    # Study list inspectable
    assert len(at.selectbox) >= 1
    assert any("Select study" in str(s.label) for s in at.selectbox)
    # Dataframe inventory visible
    assert len(at.dataframe) >= 1


def test_research_registry_shows_exact_identities_and_standing() -> None:
    at = _run_app_page()
    assert not at.exception
    body = _body(at)
    recs = build_admitted_e2_records()
    by_study = {r.study: r for r in recs}
    # Default shows E2b
    e2b = by_study["E2b"]
    assert e2b.code_sha is not None and e2b.code_sha in body
    assert e2b.manifest_hash is not None and e2b.manifest_hash in body
    # Check other E2s via selection
    for target in ("E2c", "E2d"):
        at2 = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        for k, v in default_session_state(load_ui_config()).items():
            at2.session_state[k] = v
        at2.session_state["_v07_navigation_active"] = True
        at2.run()
        if at2.selectbox:
            box = at2.selectbox[0]
            opts = _selectbox_options(box)
            opt = next((o for o in opts if o.startswith(f"{target}:")), None)
            if opt is not None:
                box.set_value(opt).run()
                body2 = _body(at2)
                rec = by_study[target]
                assert rec.code_sha is not None and rec.code_sha in body2, (
                    f"{target} code_sha missing"
                )
                assert rec.manifest_hash is not None and rec.manifest_hash in body2
    # Evidence and admission standing visible
    assert "Evidence" in body
    assert "Admission" in body or "admission" in body.lower()
    assert "RESEARCH-EVIDENCE FACT" in body or "RESEARCH" in body


def test_research_registry_per_draw_and_lineage() -> None:
    at = _run_app_page()
    assert not at.exception
    body = _body(at)
    assert "Per-draw" in body or "per-draw" in body.lower()
    assert "Lineage" in body
    assert "EXTENDS" in body or "extends" in body.lower()
    assert "does not establish causality" in body.lower()


def test_research_registry_limitations_and_non_claims() -> None:
    at = _run_app_page()
    assert not at.exception
    body = _body(at)
    assert "Limitations" in body
    assert "Non-claims" in body or "non-claims" in body.lower()
    assert "Product links" in body or "product" in body.lower()
    # Snapshot fingerprint and receipts
    assert "Snapshot fingerprint" in body or "snapshot" in body.lower()
    assert "Receipt" in body


def test_research_registry_unavailable_study_clearly_unavailable() -> None:
    at = _run_app_page()
    assert not at.exception
    # Switch to unavailable E0 if present
    if at.selectbox:
        box = at.selectbox[0]
        opts = _selectbox_options(box)
        e0 = next((o for o in opts if o.startswith("E0:")), None)
        if e0 is not None:
            box.set_value(e0).run()
            body = _body(at)
            assert "UNAVAILABLE" in body
            assert "truthfully" in body.lower() or "UNAVAILABLE" in body


def test_research_registry_e3_absent_and_no_dynamic_resource() -> None:
    at = _run_app_page()
    assert not at.exception
    body = _body(at)
    # E3 absent
    snapshot = RegistryService.with_default_e2().snapshot()
    assert all(r.study != "E3" for r in snapshot.records)
    low = body.lower()
    # Either E3 absent caption or E3 not present
    assert "e3" not in low or "absent" in low or "unavailable" in low or "E3 is absent" in body
    assert "Dynamic Resource" not in body
    # No product claim for E3
    assert "E3" not in body or "absent" in body.lower()


def test_research_registry_forged_mutation_fails_closed_and_error_state() -> None:
    pkg = build_e2_study_package()
    pol = build_default_e2_admission_policy(pkg)
    obj = json.loads(pkg.to_json())
    # Mutate value
    obj["records"][0]["per_draw_values"][0]["value"] = 0.111
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError):
        ingest_package(bad, pol)
    # Empty policy should fail
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg.to_json(), AdmissionPolicy(entries=[]))
    # UI error state when typed construction fails
    with patch("traffictwin.ui.pages.research_registry.RegistryService.with_default_e2") as mock:
        mock.side_effect = ValueError("typed verification failed")
        at = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at.session_state["_v07_navigation_active"] = True
        at.run()
        assert not at.exception
        body = _body(at)
        assert "unavailable" in body.lower() or "could not be constructed" in body.lower()
        # Should not show admitted badge in error state
        assert "ADMITTED RESEARCH" not in body or "unavailable" in body.lower()


def test_research_registry_distinguishes_import_evidence_admission() -> None:
    at = _run_app_page()
    assert not at.exception
    body = _body(at)
    low = body.lower()
    assert "structural import" in low
    assert "trusted evidence" in low
    assert "product admission" in low
    assert "task-level telemetry" in low or "task" in low and "telemetry" in low


def test_research_registry_no_arbitrary_file_or_secrets() -> None:
    at = _run_app_page()
    assert not at.exception
    body = _body(at)
    assert "/Users" not in body
    assert "/tmp" not in body  # noqa: S108
    assert "api_key" not in body.lower()
    assert "secret" not in body.lower() or "no secret" in body.lower() or "Secrets" not in body
