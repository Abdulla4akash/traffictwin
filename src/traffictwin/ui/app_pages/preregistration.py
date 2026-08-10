from traffictwin.ui.labels import UiPage
from traffictwin.ui.page_runtime import run_page_script

# This wrapper becomes active after the final registration commit adds UiPage.PREREGISTRATION_STUDIO.
# Before that, keep the import safe so feature tests can run without the navigation registry.
try:
    target = UiPage.PREREGISTRATION_STUDIO  # type: ignore[attr-defined]
except AttributeError:
    from traffictwin.ui.labels import UiPage as _UiPage

    # Fallback: run the preregistration page directly via its module path
    # The page itself handles missing enum gracefully.
    from traffictwin.ui.pages.preregistration_studio import render as _render
    from traffictwin.ui.state import UiConfig

    # Direct render fallback not needed in normal navigation; keep as no-op.
    target = None  # type: ignore

if target is not None:
    run_page_script(target)
