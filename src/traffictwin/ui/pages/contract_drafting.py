"""Contract Drafting Assistant — multi-sample consensus for draft source data contract.

Thin Streamlit surface rendering typed service outputs. Business logic
lives in ``traffictwin.contract_drafting.service``.

Every page must state its evidence and authority boundary before results.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from traffictwin.contract_drafting.service import (
    build_draft_report,
    export_handoff_json,
    export_report_csv,
    export_report_json,
    prepare_handoff,
)
from traffictwin.ui.state import UiConfig

SESSION_REPORT = "cda_report"
SESSION_HANDOFF = "cda_handoff"


def _empty_state() -> None:
    st.info(
        "No samples profiled yet. Provide 2–20 local tabular sample paths "
        "(CSV, CSV.GZ, or flat Parquet) under the workspace, then select "
        "`Profile samples`. Synthetic fixtures at "
        "`tests/fixtures/bundles/baseline_valid/tasks.csv` and "
        "`tests/fixtures/bundles/variation_valid/tasks.csv` can be used to "
        "explore the workflow."
    )
    st.caption(
        "Supported: plain CSV, gzip CSV (.csv.gz), flat scalar Parquet. "
        "Bounded inspection uses explicit row and byte limits and does not retain raw values."
    )


def render(config: UiConfig) -> None:  # noqa: ARG001
    """Render the Contract Drafting Assistant page."""
    # Authoritative H1 — required for page quality
    st.title("Contract Drafting Assistant")
    st.caption(
        "Profiles 2–20 local tabular samples and produces a reviewable DRAFT source data contract."
    )

    # Evidence / authority boundary — must appear before results
    st.warning(
        "Evidence and authority boundary: This assistant profiles local samples "
        "and drafts a candidate source data contract for human review. It does "
        "not freeze or approve the contract, does not automatically admit "
        "evidence, does not claim causality or optimality, and does not call "
        "external providers. A drafted contract must be reviewed in the "
        "Data Contract Workbench before any freeze."
    )
    st.caption(
        "Portable draft and handoff exports exclude raw categorical values, "
        "absolute paths, retrieval clocks, and secrets. Inspection is bounded "
        "by explicit row and byte limits."
    )

    # ------------------------------------------------------------------
    # Sample selection (2–20)
    # ------------------------------------------------------------------
    st.subheader("1. Select 2–20 bounded local samples")
    st.caption(
        "Enter one path per line (workspace-contained, .csv / .csv.gz / .parquet). "
        "Each sample is validated independently via the existing safe readers."
    )

    # Keep inputs in session state for AppTest determinism — two distinct
    # verified-existing bundled fixtures so first click is valid.
    default_sample_a = "tests/fixtures/bundles/baseline_valid/tasks.csv"
    default_sample_b = "tests/fixtures/bundles/variation_valid/tasks.csv"
    raw_text = st.text_area(
        "Sample paths (2–20, one per line)",
        value=str(
            st.session_state.get("cda_sample_paths_text", f"{default_sample_a}\n{default_sample_b}")
        ),
        height=140,
        key="cda_sample_paths_input",
        help=(
            "Workspace-contained paths; duplicate the fixture with "
            "different rows to explore consensus."
        ),
    )
    st.session_state["cda_sample_paths_text"] = raw_text

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        max_rows = st.number_input(
            "Max rows per sample",
            min_value=1,
            max_value=10000,
            value=int(st.session_state.get("cda_max_rows", 1000)),
            step=100,
            key="cda_max_rows_input",
        )
    with col_b:
        max_bytes = st.number_input(
            "Max bytes per sample",
            min_value=1024,
            max_value=10_000_000,
            value=int(st.session_state.get("cda_max_bytes", 2_000_000)),
            step=1024,
            key="cda_max_bytes_input",
        )
    with col_c:
        source_hint = st.text_input(
            "Source ID hint (optional)",
            value=str(st.session_state.get("cda_source_hint", "")),
            key="cda_source_hint_input",
            placeholder="e.g. sensor_feed_v1",
        )
    st.session_state["cda_max_rows"] = int(max_rows)
    st.session_state["cda_max_bytes"] = int(max_bytes)
    st.session_state["cda_source_hint"] = source_hint

    # User unit suggestions (optional)
    with st.expander("Optional: user unit suggestions (field -> unit)", expanded=False):
        st.caption(
            "Units remain 'unknown' unless you supply a suggestion or an authoritative "
            "contract provides one. Column names alone never imply a unit."
        )
        unit_text = st.text_area(
            "Unit suggestions (one per line: field=unit)",
            value=str(st.session_state.get("cda_unit_suggestions_text", "")),
            key="cda_unit_suggestions_input",
            placeholder="e.g. count=ratio\nlatency_ms=milliseconds",
        )
        st.session_state["cda_unit_suggestions_text"] = unit_text

    def _parse_paths(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _parse_unit_suggestions(text: str) -> dict[str, str] | None:
        if not text.strip():
            return None
        out: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k and v:
                out[k] = v
        return out if out else None

    sample_paths_text = _parse_paths(raw_text)
    unit_suggestions = _parse_unit_suggestions(unit_text)

    # Per-sample validation preview
    if sample_paths_text:
        st.markdown("**Per-sample validation (pre-profile check)**")
        rows = []
        for idx, p in enumerate(sample_paths_text):
            suffix_ok = p.lower().endswith((".csv", ".csv.gz", ".parquet"))
            exists = Path(p).exists()
            # Workspace containment heuristic: show as unavailable if outside cwd/tmp
            if not suffix_ok:
                status = "Refused: unsupported suffix (allowed .csv, .csv.gz, .parquet)"
            elif not exists:
                status = "Unavailable: file not found"
            else:
                status = "Ready: will validate with safe reader on profile"
            rows.append({"#": str(idx + 1), "path": Path(p).name, "validation": status})
        # Avoid UI-side recomputation of consensus; this is only pre-check
        st.dataframe(rows, hide_index=True, width="stretch", key="cda_validation_table")

    st.caption(f"Selected {len(sample_paths_text)} samples (requires 2–20).")

    # Profile action — thin service call
    if st.button("Profile samples", type="primary", key="cda_profile_button"):
        parsed_paths = _parse_paths(st.session_state.get("cda_sample_paths_text", ""))
        if not (2 <= len(parsed_paths) <= 20):
            st.error(f"Provide 2–20 sample paths; got {len(parsed_paths)}.")
        else:
            try:
                paths_as_path = [Path(p) for p in parsed_paths]
                report = build_draft_report(
                    paths_as_path,
                    max_rows=int(st.session_state.get("cda_max_rows", 1000)),
                    max_bytes=int(st.session_state.get("cda_max_bytes", 2_000_000)),
                    source_id_hint=(
                        str(st.session_state.get("cda_source_hint", "")).strip() or None
                    ),
                    user_unit_suggestions=unit_suggestions,
                    authoritative_contract=None,
                )
                st.session_state[SESSION_REPORT] = report.model_dump(mode="json")
                # Also prepare handoff immediately (deterministic, no freeze)
                handoff = prepare_handoff(
                    report,
                    source_id=(str(st.session_state.get("cda_source_hint", "")).strip() or None),
                    contract_version="1.0.0",
                )
                st.session_state[SESSION_HANDOFF] = handoff.model_dump(mode="json")
                st.success(
                    f"Profiled {len(parsed_paths)} samples. "
                    f"Overall confidence: {report.overall_confidence.value}"
                )
            except ValidationError as exc:
                st.error(f"Request validation failed: {exc}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Profiling failed (invalid sample refused): {exc}")

    # ------------------------------------------------------------------
    # Report rendering (if available)
    # ------------------------------------------------------------------
    report_dict = st.session_state.get(SESSION_REPORT)
    if report_dict is None:
        _empty_state()
        # Still show a caption to ensure test can find empty state text
        return

    # Re-hydrate typed report (fail-closed if corrupted)
    try:
        from traffictwin.contract_drafting.models import ContractDraftReport

        report = ContractDraftReport.model_validate(report_dict)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load draft report: {exc}")
        return

    # Evidence boundary already stated above; now results
    st.subheader("2. Consensus across samples")
    st.caption(
        "Field presence frequency, observed logical types, nullable frequency, "
        "timestamp parse-state / timezone consistency, numeric precision/scale ranges, "
        "categorical distinct-count ranges and structural aggregate hashes. "
        "Portable output excludes raw categorical values."
    )

    # Confidence
    st.metric("Overall drafting confidence", report.overall_confidence.value)
    st.caption(
        f"Fingerprint `{report.fingerprint[:12]}…` · "
        f"Structural hash `{report.structural_hash[:12]}…` · "
        f"Samples: {report.total_samples} · "
        f"Draft only: {report.draft_only} · "
        f"Freeze executed: {report.freeze_executed} · "
        f"Human review required: {report.human_review_required}"
    )

    # Consensus table
    consensus_rows: list[dict[str, str]] = []
    for fc in report.field_consensus:
        prec_range = ""
        if fc.numeric_consensus and fc.numeric_consensus.precision_range:
            prec_range = (
                f"{fc.numeric_consensus.precision_min}–{fc.numeric_consensus.precision_max}"
            )
        scale_range = ""
        if fc.numeric_consensus and fc.numeric_consensus.scale_range:
            scale_range = f"{fc.numeric_consensus.scale_min}–{fc.numeric_consensus.scale_max}"
        d_range = ""
        if fc.categorical_consensus and fc.categorical_consensus.distinct_count_range:
            d_range = (  # noqa: E501
                f"{fc.categorical_consensus.distinct_count_min}-"
                f"{fc.categorical_consensus.distinct_count_max}"
            )
        consensus_rows.append(
            {
                "field": fc.field_name,
                "present": f"{fc.presence.present_in_samples}/{fc.presence.total_samples}",
                "frequency": f"{fc.presence.presence_frequency:.2f}",
                "types": ", ".join(t.value for t in fc.type_consensus.observed_types),
                "conflicting": str(fc.type_consensus.is_conflicting),
                "nullable_freq": f"{fc.nullable_frequency:.2f}",
                "tz_mixed": str(fc.timestamp_consensus.is_mixed_timezone)
                if fc.timestamp_consensus
                else "",
                "precision_range": prec_range,
                "scale_range": scale_range,
                "distinct_count_range": d_range,
                "hash_stable": str(fc.categorical_consensus.is_hash_stable)
                if fc.categorical_consensus
                else "",
            }
        )
    st.dataframe(consensus_rows, hide_index=True, width="stretch", key="cda_consensus_table")

    # Download consensus CSV/JSON
    st.download_button(
        "Download consensus CSV",
        data=export_report_csv(report),
        file_name="contract_draft_consensus.csv",
        mime="text/csv",
        key="cda_consensus_csv",
    )
    st.download_button(
        "Download report JSON",
        data=export_report_json(report),
        file_name="contract_draft_report.json",
        mime="application/json",
        key="cda_report_json",
    )

    # Disagreement panel
    st.subheader("3. Disagreements and unresolved items")
    if not report.findings:
        st.info("No disagreements: all fields stable across samples.")
    else:
        for finding in report.findings:
            level = finding.severity.value
            text = f"{finding.code} — {finding.message}"
            if level == "blocked":
                st.error(text)
            elif level == "warning":
                st.warning(text)
            else:
                st.info(text)

    # Confidence detail per field
    st.subheader("4. Draft field recommendations (reviewable, not asserted as fact)")
    st.caption(
        "Each field shows recommended required/optional, candidate logical type, nullable, "
        "timestamp semantics, numeric precision/scale, unit (unknown unless user-supplied), "
        "and privacy-review flag. Edit below is local to this draft and does not freeze."
    )
    draft_rows: list[dict[str, str]] = []
    for df in report.draft_fields:
        draft_rows.append(
            {
                "field": df.field_name,
                "required": str(df.recommended_required),
                "type": df.candidate_logical_type.value,
                "nullable": str(df.recommended_nullable),
                "precision": str(df.numeric_precision) if df.numeric_precision is not None else "",
                "scale": str(df.numeric_scale) if df.numeric_scale is not None else "",
                "unit": df.unit,
                "privacy_review": str(df.privacy_review_required),
                "confidence": df.confidence.value,
                "rationale": df.rationale,
            }
        )
    st.dataframe(draft_rows, hide_index=True, width="stretch", key="cda_draft_table")

    # Draft editor (local, does not mutate report fingerprint unless re-profiled)
    with st.expander("Draft editor (local edits before handoff) — does not freeze", expanded=False):
        st.caption(
            "Edits here are for review only. Changing a value does not automatically "
            "re-profile samples or freeze a contract. Use the handoff download to carry the "
            "draft into the Data Contract Workbench for formal editing and freeze."
        )
        edited_rows = st.data_editor(
            draft_rows,
            hide_index=True,
            width="stretch",
            key="cda_draft_editor",
            disabled=["field"],
        )
        st.caption(f"Edited {len(edited_rows)} draft rows locally (not yet re-fingerprinted).")

    # ------------------------------------------------------------------
    # Handoff
    # ------------------------------------------------------------------
    st.subheader("5. Deterministic handoff to Data Contract Workbench")
    handoff_dict = st.session_state.get(SESSION_HANDOFF)
    if handoff_dict is not None:
        from traffictwin.contract_drafting.models import DraftContractHandoff

        loaded_handoff: DraftContractHandoff | None = None
        try:
            loaded_handoff = DraftContractHandoff.model_validate(handoff_dict)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not load handoff: {exc}")
            loaded_handoff = None
        if loaded_handoff is not None:
            st.info(
                f"Handoff `{loaded_handoff.handoff_id}` · "
                f"Report fingerprint `{loaded_handoff.report_fingerprint[:12]}…` · "
                f"Draft only: {loaded_handoff.draft_only} · "
                f"Freeze executed: {loaded_handoff.freeze_executed} · "
                f"Human review required: {loaded_handoff.human_review_required}"
            )
            st.json(
                {
                    "handoff_id": loaded_handoff.handoff_id,
                    "report_fingerprint": loaded_handoff.report_fingerprint,
                    "fingerprint": loaded_handoff.fingerprint,
                    "draft_only": loaded_handoff.draft_only,
                    "freeze_executed": loaded_handoff.freeze_executed,
                    "human_review_required": loaded_handoff.human_review_required,
                    "created_from_samples": loaded_handoff.created_from_samples,
                }
            )
            st.download_button(
                "Download handoff JSON (draft contract for editing)",
                data=export_handoff_json(loaded_handoff),
                file_name="contract_draft_handoff.json",
                mime="application/json",
                key="cda_handoff_download",
            )
            # Explicit link text for later Data Contract Workbench review
            st.markdown(
                "Open in **Data Contract Workbench** for review and freeze "
                "(copy the downloaded handoff JSON into the Workbench editor; "
                "the draft is not frozen until you explicitly freeze it there)."
            )
            st.caption(
                "Note: This handoff is draft-only and portable. It excludes raw values and paths. "
                "The Data Contract Workbench remains the authority for freezing."
            )

    # ------------------------------------------------------------------
    # Authority footer
    # ------------------------------------------------------------------
    st.divider()
    st.caption(
        "Authority: DRAFT only — freeze_executed=False, human_review_required=True. "
        "To finalize, open the handoff in the Data Contract Workbench and freeze there."
    )
