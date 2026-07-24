"""Provenance display components."""

from __future__ import annotations

import streamlit as st

from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.results import MetricCollection
from traffictwin.ui.tables import table_column_config


def render_run_provenance(
    validation: BundleValidationResult | None,
    metrics: MetricCollection | None,
) -> None:
    """Render run and bundle provenance."""

    if validation is None or validation.manifest is None:
        st.info("No run provenance loaded.")
        return
    manifest = validation.manifest
    rows = [
        {"field": "run_id", "value": manifest.run.run_id},
        {"field": "experiment_id", "value": manifest.run.experiment_id},
        {"field": "seed_id", "value": manifest.run.seed_id},
        {"field": "algorithm", "value": manifest.run.algorithm},
        {"field": "checkpoint", "value": manifest.run.checkpoint or "None"},
        {"field": "random_seed", "value": str(manifest.run.random_seed)},
        {"field": "environment", "value": manifest.environment.name},
        {"field": "environment_version", "value": manifest.environment.version or "Unknown"},
        {"field": "bundle_fingerprint", "value": validation.fingerprint or "Unavailable"},
        {
            "field": "metric_version",
            "value": metrics.metric_version if metrics is not None else "Unavailable",
        },
    ]
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config=table_column_config(rows),
    )
