"""Capture the complete v0.7 UI and run bounded semantic accessibility checks."""

from __future__ import annotations

import argparse
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

from playwright._impl._api_structures import ViewportSize
from playwright.sync_api import Page, sync_playwright

from traffictwin.ui.audit import AccessibilitySnapshot, analyse_accessibility_snapshots
from traffictwin.ui.navigation_v07 import MANCHESTER_PAGE_SPEC, V07_PAGE_SPECS

AuditTheme = Literal["light", "dark", "current"]
AuditViewport = Literal["desktop", "mobile"]

VIEWPORTS: dict[AuditViewport, ViewportSize] = {
    "desktop": {"width": 1440, "height": 1000},
    "mobile": {"width": 390, "height": 844},
}
SMOKE_PATHS = frozenset({"home", "guided-workflow", "replay", "manchester", "about"})


@dataclass(frozen=True, slots=True)
class AuditRoute:
    """One exact v0.7 browser route and its required primary heading."""

    title: str
    url_path: str
    expected_h1: str


_H1_OVERRIDES = {
    "compare": "What-if Compare",
    "diagnostics": "Evidence & Diagnostic Hypotheses",
    "home": "Model a traffic scenario. Run or import it. Compare the evidence.",
    "replay": "Operations View",
}
AUDIT_ROUTES: tuple[AuditRoute, ...] = tuple(
    [
        AuditRoute(
            spec.page.value,
            spec.url_path,
            _H1_OVERRIDES.get(spec.url_path, spec.page.value),
        )
        for spec in V07_PAGE_SPECS
    ]
    + [
        AuditRoute(
            MANCHESTER_PAGE_SPEC.title,
            MANCHESTER_PAGE_SPEC.url_path,
            MANCHESTER_PAGE_SPEC.title,
        )
    ]
)


def main() -> int:
    """Run the browser audit and return a process exit code."""

    arguments = _arguments()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    routes = _selected_routes(arguments.pages)
    viewports = _selected_viewports(arguments.viewports)
    themes = _selected_themes(arguments.theme, external_url=arguments.url is not None)
    snapshots: list[AccessibilitySnapshot] = []

    if arguments.url is not None:
        snapshots.extend(
            _capture(
                arguments.url,
                output,
                routes,
                viewports,
                "current",
                arguments.timeout_seconds,
            )
        )
    else:
        for offset, theme in enumerate(themes):
            port = arguments.port + offset
            url = f"http://127.0.0.1:{port}"
            process = _start_streamlit(port, theme)
            try:
                _wait_for_url(url, arguments.timeout_seconds)
                snapshots.extend(
                    _capture(
                        url,
                        output,
                        routes,
                        viewports,
                        theme,
                        arguments.timeout_seconds,
                    )
                )
            finally:
                _stop_process(process)

    expected_count = len(routes) * len(viewports) * len(themes)
    if len(snapshots) != expected_count:
        raise RuntimeError(
            f"browser audit captured {len(snapshots)} snapshots; expected {expected_count}"
        )
    report = analyse_accessibility_snapshots(snapshots)
    (output / "accessibility-audit.json").write_text(report.to_json(), encoding="utf-8")
    print(f"screenshots: {output}")
    print(f"routes: {len(routes)}")
    print(f"snapshots: {len(snapshots)}")
    print(f"accessibility_passed: {str(report.passed).lower()}")
    print(f"issues: {len(report.issues)}")
    return 0 if report.passed else 1


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture direct v0.7 routes in desktop/mobile and light/dark modes. "
            "This is regression evidence, not WCAG certification."
        )
    )
    parser.add_argument("--url", help="Audit an already-running app using its current theme.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output", type=Path, default=Path("output/ui-audit"))
    parser.add_argument("--pages", choices=("all", "smoke"), default="all")
    parser.add_argument("--viewports", choices=("both", "desktop", "mobile"), default="both")
    parser.add_argument("--theme", choices=("both", "light", "dark"), default="both")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    return parser.parse_args()


def _selected_routes(mode: str) -> tuple[AuditRoute, ...]:
    if mode == "all":
        return AUDIT_ROUTES
    return tuple(route for route in AUDIT_ROUTES if route.url_path in SMOKE_PATHS)


def _selected_viewports(mode: str) -> tuple[AuditViewport, ...]:
    if mode == "both":
        return ("desktop", "mobile")
    return ("desktop",) if mode == "desktop" else ("mobile",)


def _selected_themes(mode: str, *, external_url: bool) -> tuple[AuditTheme, ...]:
    if external_url:
        return ("current",)
    if mode == "both":
        return ("light", "dark")
    return ("light",) if mode == "light" else ("dark",)


def _start_streamlit(port: int, theme: AuditTheme) -> subprocess.Popen[str]:
    if theme == "current":
        raise ValueError("a launched audit must declare light or dark theme")
    command = [
        str(Path(".venv/bin/streamlit").resolve()),
        "run",
        "src/traffictwin/ui/app.py",
        "--server.headless=true",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
        f"--theme.base={theme}",
    ]
    return subprocess.Popen(  # noqa: S603
        command,
        cwd=Path.cwd(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_process(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _wait_for_url(url: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):  # noqa: S310
                return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise TimeoutError(f"Streamlit did not become ready: {url}")


def _capture(
    base_url: str,
    output: Path,
    routes: tuple[AuditRoute, ...],
    viewports: tuple[AuditViewport, ...],
    theme: AuditTheme,
    timeout_seconds: int,
) -> list[AccessibilitySnapshot]:
    snapshots: list[AccessibilitySnapshot] = []
    timeout_ms = timeout_seconds * 1000
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for viewport_name in viewports:
                viewport = VIEWPORTS[viewport_name]
                page = browser.new_page(viewport=viewport)
                try:
                    page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
                    page.locator('[data-testid="stMain"] h1').first.wait_for(
                        state="visible", timeout=timeout_ms
                    )
                    for route in routes:
                        previous_h1 = page.locator('[data-testid="stMain"] h1').first.text_content()
                        _open_navigation(page, timeout_ms)
                        route_link = page.locator(
                            f'[data-testid="stSidebar"] a[href$="/{route.url_path}"]'
                        )
                        route_link.wait_for(state="visible", timeout=timeout_ms)
                        route_link.click()
                        target = urljoin(base_url.rstrip("/") + "/", route.url_path)
                        page.wait_for_url(target, timeout=timeout_ms)
                        main = page.locator('[data-testid="stMain"]')
                        main.wait_for(state="visible", timeout=timeout_ms)
                        page.locator('[data-testid="stMain"] h1').first.wait_for(
                            state="visible", timeout=timeout_ms
                        )
                        if route.expected_h1 != previous_h1:
                            page.wait_for_function(
                                """(previous) => {
                                  const heading = document.querySelector(
                                    '[data-testid="stMain"] h1'
                                  );
                                  const exception = document.querySelector(
                                    '[data-testid="stException"]'
                                  );
                                  return Boolean(exception) ||
                                    (heading?.textContent?.trim() || '') !== previous;
                                }""",
                                arg=previous_h1 or "",
                                timeout=timeout_ms,
                            )
                        page.wait_for_timeout(350)
                        page.screenshot(
                            path=output / f"{theme}-{viewport_name}-{_slug(route.title)}.png",
                            full_page=True,
                        )
                        snapshots.append(
                            _snapshot(
                                page,
                                route,
                                viewport_name,
                                viewport,
                                theme,
                            )
                        )
                finally:
                    page.close()
        finally:
            browser.close()
    return snapshots


def _open_navigation(page: Page, timeout_ms: int) -> None:
    """Expose all native st.navigation links without relying on legacy widgets."""

    sidebar = page.locator('[data-testid="stSidebar"]')
    if not sidebar.is_visible():
        expand = page.locator('[data-testid="stExpandSidebarButton"]')
        expand.wait_for(state="visible", timeout=timeout_ms)
        expand.click()
        sidebar.wait_for(state="visible", timeout=timeout_ms)
    more = sidebar.locator('[data-testid="stSidebarNavViewButton"]')
    more_text = more.text_content() if more.count() and more.is_visible() else None
    if more_text is not None and "more" in more_text:
        more.click()


def _snapshot(
    page: Page,
    route: AuditRoute,
    viewport_name: AuditViewport,
    viewport: ViewportSize,
    theme: AuditTheme,
) -> AccessibilitySnapshot:
    payload: dict[str, Any] = page.evaluate(
        """() => {
          const main = document.querySelector('[data-testid="stMain"]') ||
            document.querySelector('main');
          const interactives = [
            ...document.querySelectorAll('button,input,select,textarea,a[href]')
          ];
          const unnamed = interactives.filter((element) => {
            const style = window.getComputedStyle(element);
            const bounds = element.getBoundingClientRect();
            const visible = element.getClientRects().length > 0 &&
              bounds.width > 1 && bounds.height > 1 && style.display !== 'none' &&
              style.visibility !== 'hidden' && style.opacity !== '0' &&
              style.clipPath !== 'inset(50%)';
            const labelled = element.getAttribute('aria-label') ||
              element.getAttribute('aria-labelledby') || element.getAttribute('title') ||
              element.textContent?.trim() || element.closest('label')?.textContent?.trim() ||
              (element.id && document.querySelector(`label[for="${element.id}"]`)?.textContent);
            return visible && !labelled;
          });
          const ids = [...document.querySelectorAll('[id]')].map((element) => element.id);
          const duplicates = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
          const vendorGridDuplicates = duplicates.filter((id) => id.startsWith('glide-cell-'));
          const mainElements = new Set([
            ...document.querySelectorAll('main,[role="main"],[data-testid="stMain"]')
          ]);
          return {
            page_title: document.title,
            main_h1_texts: [...(main || document).querySelectorAll('h1')]
              .map((heading) => heading.textContent?.trim() || ''),
            main_landmark_count: mainElements.size,
            streamlit_exception_count: (main || document)
              .querySelectorAll('[data-testid="stException"]').length,
            unnamed_interactive_count: unnamed.length,
            unnamed_interactives: unnamed.map((element) => element.outerHTML),
            images_without_alt_count: document.querySelectorAll('img:not([alt])').length,
            duplicate_ids: duplicates.filter((id) => !id.startsWith('glide-cell-')),
            vendor_grid_duplicate_id_count: vendorGridDuplicates.length,
            horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
          };
        }"""
    )
    unnamed_interactives = payload.pop("unnamed_interactives")
    if unnamed_interactives:
        print(
            f"unnamed_interactives[{theme}/{viewport_name}/{route.title}]: {unnamed_interactives}"
        )
    return AccessibilitySnapshot(
        page_name=f"{route.title} [{theme}/{viewport_name}]",
        expected_h1=route.expected_h1,
        url_path=route.url_path,
        viewport=viewport_name,
        viewport_width=viewport["width"],
        viewport_height=viewport["height"],
        requested_theme=theme,
        **payload,
    )


def _slug(value: str) -> str:
    return "-".join(value.lower().replace("&", "and").split())


if __name__ == "__main__":
    raise SystemExit(main())
