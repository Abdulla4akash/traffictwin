# ruff: noqa: ANN001,ANN002,ANN003,ANN201,ANN202
"""Root conftest for cold-test opt-in — ensures --run-cold-apptest is known for all test paths."""

from __future__ import annotations

import pytest


def pytest_addoption(parser):  # type: ignore[no-untyped-def]
    group = parser.getgroup("traffictwin")
    import contextlib

    with contextlib.suppress(ValueError):
        group.addoption(
            "--run-cold-apptest",
            action="store_true",
            default=False,
            help="run expensive cold AppTest controls (requires --run-cold-apptest)",
        )


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    if config.getoption("--run-cold-apptest", default=False):
        return
    skip = pytest.mark.skip(reason="cold AppTest control requires --run-cold-apptest")
    for item in items:
        if item.get_closest_marker("cold_apptest"):
            item.add_marker(skip)
