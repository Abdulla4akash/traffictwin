"""Capture TrafficTwin UI screenshots and basic semantic accessibility checks."""

from __future__ import annotations

import argparse
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

from traffictwin.ui.audit import (
    AccessibilitySnapshot,
    analyse_accessibility_snapshots,
)

PAGES = [
    "Home",
    "Replay",
    "Diagnostics & Evidence",
    "Threshold Sensitivity",
    "Statistical Study",
    "Parameter Sweep",
    "Scenario Builder",
    "Scenario Mutations",
    "Comparison",
    "Provenance Explorer",
    "Reports",
    "Search",
    "Mock Evaluation Analysis",
]

PAGE_HEADINGS = {
    "Home": "TrafficTwin",
    "Replay": "Operations View",
    "Diagnostics & Evidence": "Evidence & Diagnostic Hypotheses",
    "Comparison": "What-if Compare",
}


def main() -> int:
    """Run the browser audit and return a process exit code."""

    arguments = _arguments()
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    process: subprocess.Popen[str] | None = None
    url = arguments.url
    if url is None:
        url = f"http://127.0.0.1:{arguments.port}"
        command = [
            str(Path(".venv/bin/streamlit").resolve()),
            "run",
            "src/traffictwin/ui/app.py",
            "--server.headless=true",
            f"--server.port={arguments.port}",
            "--browser.gatherUsageStats=false",
        ]
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=Path.cwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_for_url(url)
    snapshots: list[AccessibilitySnapshot] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(url, wait_until="networkidle")
            for page_name in PAGES:
                _select_page(page, page_name)
                page.screenshot(
                    path=output / f"{_slug(page_name)}-desktop.png",
                    full_page=True,
                )
                snapshots.append(_snapshot(page, page_name))
            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            mobile.goto(url, wait_until="networkidle")
            mobile.screenshot(path=output / "home-mobile.png", full_page=True)
            browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    report = analyse_accessibility_snapshots(snapshots)
    (output / "accessibility-audit.json").write_text(report.to_json(), encoding="utf-8")
    print(f"screenshots: {output}")
    print(f"accessibility_passed: {str(report.passed).lower()}")
    print(f"issues: {len(report.issues)}")
    return 0 if report.passed else 1


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output", type=Path, default=Path("output/ui-audit"))
    return parser.parse_args()


def _wait_for_url(url: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):  # noqa: S310
                return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise TimeoutError(f"Streamlit did not become ready: {url}")


def _select_page(page: Page, page_name: str) -> None:
    navigation = page.get_by_role("radiogroup", name="Navigation", exact=True)
    navigation.wait_for(state="visible", timeout=10_000)
    if navigation.count() != 1:
        raise ValueError("expected one Navigation radio group")
    option = navigation.get_by_text(page_name, exact=True)
    if option.count() != 1:
        raise ValueError(f"expected one visible navigation label for {page_name}")
    option.click()
    main = page.locator('[data-testid="stMain"]')
    if main.count() != 1:
        raise ValueError("expected one Streamlit main region")
    heading = main.get_by_role(
        "heading",
        name=PAGE_HEADINGS.get(page_name, page_name),
        exact=True,
    )
    heading.wait_for(state="visible", timeout=10_000)
    if heading.count() != 1:
        raise ValueError(f"expected one main heading for {page_name}")
    page.wait_for_timeout(250)


def _snapshot(page: Page, page_name: str) -> AccessibilitySnapshot:
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
          return {
            page_title: document.title,
            main_h1_texts: [...(main || document).querySelectorAll('h1')]
              .map((heading) => heading.textContent?.trim() || ''),
            unnamed_interactive_count: unnamed.length,
            unnamed_interactives: unnamed.map((element) => element.outerHTML),
            images_without_alt_count: document.querySelectorAll('img:not([alt])').length,
            duplicate_ids: duplicates,
            horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
          };
        }"""
    )
    unnamed_interactives = payload.pop("unnamed_interactives")
    if unnamed_interactives:
        print(f"unnamed_interactives[{page_name}]: {unnamed_interactives}")
    return AccessibilitySnapshot(page_name=page_name, **payload)


def _slug(value: str) -> str:
    return "-".join(value.lower().replace("&", "and").split())


if __name__ == "__main__":
    raise SystemExit(main())
