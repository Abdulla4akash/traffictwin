"""Manchester Twin app wrapper — thin delegating script, no navigation edits."""

from __future__ import annotations

from traffictwin.ui.pages.manchester_twin import render


def main() -> None:
    """Entry point for the app_pages router."""

    render()


if __name__ == "__main__":
    main()
