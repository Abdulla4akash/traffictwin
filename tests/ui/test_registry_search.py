from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from traffictwin.demo.workspace import initialise_workspace
from traffictwin.registry_search import RegistrySearchResult, SearchCategory
from traffictwin.ui.services import search_for_ui


def test_registry_search_ui_service_exposes_typed_ranked_results(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)

    result = search_for_ui(
        "completion",
        workspace / "registry.sqlite",
        workspace,
        categories=[SearchCategory.REPORT, SearchCategory.EVIDENCE_REFERENCE],
        limit=10,
    )

    assert isinstance(result, RegistrySearchResult)
    assert result.hits
    assert all(
        hit.category in {SearchCategory.REPORT, SearchCategory.EVIDENCE_REFERENCE}
        for hit in result.hits
    )
    assert result.returned_count <= 10


def test_search_page_exposes_rep05_scope_ranking_and_redaction() -> None:
    source = Path("src/traffictwin/ui/pages/search.py").read_text(encoding="utf-8")

    assert "REP-05" in source
    assert "Categories" in source
    assert "Result limit" in source
    assert '"score": hit.score' in source
    assert 'summary[3].metric("Redactions"' in source


def test_registry_search_page_runs_query_with_apptest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(workspace / "bundles"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Search").run(timeout=10)
    query = next(
        item for item in app.text_input if item.label.startswith("Search findings, annotations")
    )
    query.set_value("completion").run(timeout=10)

    assert not app.exception
    assert len(app.dataframe) == 1
    assert any(item.label == "Matches" and int(item.value) > 0 for item in app.metric)
    assert any(item.label == "Redactions" for item in app.metric)
    assert any(item.label == "Categories" for item in app.multiselect)
