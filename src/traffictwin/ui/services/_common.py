"""Private helpers shared by more than one service module."""

from __future__ import annotations


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
