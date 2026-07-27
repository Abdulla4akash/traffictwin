"""Project status and registry read/store services."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from traffictwin.config.capabilities import default_export_import_manifest
from traffictwin.domain.run import Run
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricCollection
from traffictwin.storage.registry import (
    Registry,
)
from traffictwin.ui.services.models import ProjectStatus


def load_project_status(registry_path: str | Path) -> ProjectStatus:
    """Load project and registry status for the Home page."""

    path = Path(registry_path)
    summary = Registry(path).inspect() if path.exists() else None
    return ProjectStatus(
        registry_path=path,
        registry_exists=path.exists(),
        registry_summary=summary,
        latest_runs=list_registered_runs(path)[:5] if path.exists() else [],
        capability_manifest=default_export_import_manifest(),
    )


def list_registered_runs(registry_path: str | Path) -> list[Run]:
    """List registered runs from the SQLite registry."""

    path = Path(registry_path)
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT payload FROM runs ORDER BY updated_at DESC, created_at DESC, run_id"
        ).fetchall()
    return [Run.model_validate_json(cast(str, row["payload"])) for row in rows]


def load_registered_metric_collection(
    registry_path: str | Path,
    run_id: str,
) -> MetricCollection | None:
    """Load a stored metric collection from the registry."""

    path = Path(registry_path)
    if not path.exists():
        return None
    try:
        payload = Registry(path).get_metric_collection_json(run_id)
    except Exception:
        return None
    return MetricCollection.model_validate_json(payload)


def store_metrics_for_ui(registry_path: str | Path, metrics: MetricCollection) -> bool:
    """Store metric collection JSON in the registry."""

    return Registry(registry_path).store_metric_collection(
        run_id=metrics.run_id,
        metric_version=metrics.metric_version,
        source_fingerprint=metrics.input_fingerprint,
        payload_json=metrics.model_dump_json(),
    )


def store_evidence_for_ui(registry_path: str | Path, pack: EvidencePack) -> bool:
    """Store evidence pack JSON in the registry."""

    return Registry(registry_path).store_evidence_pack(
        pack_id=pack.pack_id,
        run_id=str(pack.run_context.get("run_id", "unknown")),
        source_fingerprint=pack.source_bundle_fingerprint,
        payload_json=pack.to_json(),
    )
