"""Thin UI wrapper over :mod:`traffictwin.synthetic.whatif_pair`."""

from __future__ import annotations

from pathlib import Path

from traffictwin.synthetic.whatif_pair import (
    WhatIfChangedParameter,
    WhatIfPairError,
    WhatIfPairReceipt,
    WhatIfPairRequest,
    WhatIfVariationOverrides,
    build_whatif_configs,
    compute_changed_ledger,
    generate_whatif_pair,
    pair_id_for_request,
    request_fingerprint,
    sanitise_pair_name,
    whatif_ledger_to_yaml,
)
from traffictwin.ui.services.models import ServiceError

__all__ = [
    "WhatIfChangedParameter",
    "WhatIfPairError",
    "WhatIfPairReceipt",
    "WhatIfPairRequest",
    "WhatIfVariationOverrides",
    "build_whatif_configs",
    "compute_changed_ledger",
    "generate_whatif_pair_for_ui",
    "pair_id_for_request",
    "preview_whatif_ledger_for_ui",
    "request_fingerprint",
    "sanitise_pair_name",
    "whatif_ledger_to_yaml",
]


def generate_whatif_pair_for_ui(
    request: WhatIfPairRequest,
    registry_path: str | Path,
    workspace_path: str | Path | None = None,
) -> WhatIfPairReceipt | ServiceError:
    """Call the transactional pair service and map failures to :class:`ServiceError`."""

    try:
        return generate_whatif_pair(
            request,
            registry_path=Path(registry_path),
            workspace_path=Path(workspace_path) if workspace_path is not None else None,
        )
    except WhatIfPairError as exc:
        detail = exc.detail or ""
        # preserve code in message for UI telemetry but keep user wording
        return ServiceError(f"{exc}", detail)
    except (OSError, ValueError, RuntimeError) as exc:
        return ServiceError("What-if pair could not be generated.", str(exc))


def preview_whatif_ledger_for_ui(
    request: WhatIfPairRequest,
) -> list[WhatIfChangedParameter] | ServiceError:
    """Return the deterministic ledger preview without generating bundles."""

    try:
        baseline, variation = build_whatif_configs(request)
        return compute_changed_ledger(baseline, variation)
    except WhatIfPairError as exc:
        return ServiceError(str(exc), exc.detail)
    except (ValueError, RuntimeError) as exc:
        return ServiceError("What-if ledger could not be computed.", str(exc))
