"""Pure helper for AppTest cold-start timeout policy.

This module is test-only and contains no Streamlit import at import time,
so it does not slow non-UI unit tests. The timeout selection logic is
intentionally pure and deterministic for unit testing without sleeping.
"""

from __future__ import annotations

COLD_FLOOR_SECONDS: int = 60
DEFAULT_TIMEOUT_SECONDS: int = 10


def effective_timeout(
    requested: int | None,
    is_first: bool,
    cold_floor: int = COLD_FLOOR_SECONDS,
    default: int = DEFAULT_TIMEOUT_SECONDS,
) -> int:
    """Return the effective AppTest.run timeout.

    - First AppTest run in a pytest process: max(requested, cold_floor)
    - Subsequent runs: requested unchanged
    - None is treated as default (10) before applying the floor
    - Never reduces a timeout that is already above the floor
    """
    req = requested if requested is not None else default
    if is_first:
        return req if req > cold_floor else cold_floor
    return req
