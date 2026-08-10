"""Direct Streamlit page script for the Metric Contract Registry."""

from traffictwin.ui.page_runtime import run_page_script

try:
    from traffictwin.ui.labels import UiPage

    _PAGE = getattr(UiPage, "METRIC_CONTRACT_REGISTRY", "metric_contract_registry")
    # Verify that page has required descriptors before using runtime
    from traffictwin.ui.labels import PAGE_DESCRIPTIONS

    if _PAGE not in PAGE_DESCRIPTIONS:
        raise KeyError(f"PAGE_DESCRIPTIONS missing {_PAGE}")
    run_page_script(_PAGE)  # type: ignore[arg-type]
except Exception:
    # Fallback for local dev / AppTest before Fable integration — render directly
    from traffictwin.ui.pages.metric_contract_registry import render
    from traffictwin.ui.state import load_ui_config

    render(load_ui_config())
