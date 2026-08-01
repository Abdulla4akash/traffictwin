"""What-If Composer page: scenario form, prediction card, draft download.

The composer UI over :mod:`traffictwin.platform.whatif_composer`. The page
writes no repository, workspace, or registry file and spends no compute:
drafts leave only as deterministic downloads, and signing and execution are
instructions for a human outside the app — never buttons or background
calls. The external-LLM field is absent (the socket is dormant, P-D1); the
form/template path is complete without it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from traffictwin.platform.outcome_predictor import (
    BASELINE_ACTOR,
    TRACE_SLOTS,
    TRAINED_ACTOR,
    LoadedFit,
    OutcomePredictorError,
    load_outcome_predictor_fit,
)
from traffictwin.platform.whatif_composer import (
    ComposerForm,
    WhatifComposerError,
    compose_scenario,
    render_prediction_card,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.platform_services import FIT_ARTIFACT_RELATIVE_PATH
from traffictwin.ui.state import UiConfig


def _load_fit() -> LoadedFit | str:
    path = Path.cwd() / FIT_ARTIFACT_RELATIVE_PATH
    if not path.is_file():
        return (
            "the committed outcome-predictor fit artifact is not present at "
            "docs/platform/outcome_predictor_fit.json in this checkout"
        )
    try:
        return load_outcome_predictor_fit(path)
    except OutcomePredictorError as error:
        return str(error)


def render(config: UiConfig) -> None:
    del config
    st.title("What-If Composer")
    badge_row(["PREDICTION — NOT EVIDENCE", "DRAFT-ONLY", "NO EXECUTION"])
    st.caption(
        "What this page claims: instant predictions from the committed surrogate "
        "fit, and downloadable DRAFT/UNSIGNED campaign documents. What it does "
        "not claim: evidence, approval, or execution — signing is a human act "
        "outside this app, the campaign instrument's byte-bound approval is the "
        "only route to execution, and this page writes no file and spends no "
        "compute."
    )
    loaded = _load_fit()
    if isinstance(loaded, str):
        st.info(
            f"The composer is unavailable: {loaded}. Nothing is predicted from "
            "memory or invented in its place."
        )
        return

    with st.form("whatif-scenario-form"):
        trace = st.selectbox("Trace", sorted(TRACE_SLOTS), index=sorted(TRACE_SLOTS).index("inc"))
        capacity = st.number_input(
            "Capacity (rsu_capacity_per_vehicle)",
            min_value=0.01,
            max_value=5.0,
            value=0.75,
            step=0.05,
        )
        actor = st.selectbox("Actor checkpoint", (TRAINED_ACTOR, BASELINE_ACTOR))
        seeds_text = st.text_input(
            "Proposed fresh fleet seeds (comma-separated; a human fixes them at signing)",
            value="30, 31, 32",
        )
        submitted = st.form_submit_button("Predict and draft")

    if not submitted:
        _render_honesty_table()
        return

    try:
        seeds = tuple(int(part.strip()) for part in seeds_text.split(",") if part.strip())
    except ValueError:
        st.warning("Seeds must be integers separated by commas; nothing was drafted.")
        _render_honesty_table()
        return
    try:
        form = ComposerForm(
            trace=str(trace), capacity=float(capacity), actor=str(actor), fleet_seeds=seeds
        )
        draft = compose_scenario(form, loaded, generated_at_utc=datetime.now(UTC).isoformat())
    except (WhatifComposerError, ValueError) as error:
        st.warning(f"The composer refused: {error}")
        _render_honesty_table()
        return

    outcome = draft.prediction if draft.prediction is not None else draft.prediction_refusal
    assert outcome is not None
    st.markdown(render_prediction_card(outcome))
    st.subheader("Draft the campaign that would verify or measure this")
    st.caption(
        "Both documents are DRAFT/UNSIGNED and deterministic. Signing requires a "
        "typed human approver and the predeclaration's final SHA-256 in the "
        "campaign instrument; execution happens outside this app after a "
        "separate explicit owner decision."
    )
    st.download_button(
        "Download design draft (JSON)",
        data=json.dumps(draft.model_dump(mode="json"), indent=2, sort_keys=True),
        file_name=f"{draft.slug}_design_draft.json",
        mime="application/json",
    )
    st.download_button(
        "Download predeclaration draft (Markdown)",
        data=draft.predeclaration_markdown,
        file_name=f"{draft.slug}_predeclaration_draft.md",
        mime="text/markdown",
    )
    _render_honesty_table()


def _render_honesty_table() -> None:
    st.subheader("Predictions versus measurements")
    st.caption(
        "Empty, and visibly so: this table grows only from admitted campaign "
        "comparisons, each side keeping its own type and standing. "
        "Execution-deviated NON_ADMITTED bus/GPU results never populate it. "
        "Producer-derived cards carry the citation set in "
        "docs/producer_citation_requirements.md."
    )
