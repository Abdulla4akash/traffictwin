"""Decision Audit: synthetic XAI instrumentation with real attribution unavailable."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import streamlit as st

from traffictwin.platform.xai_instrumentation import ActionName, browse_disagreements
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.state import UiConfig
from traffictwin.ui.xai_services import XaiConsoleError, load_xai_console


def render(config: UiConfig) -> None:
    del config
    st.title("Decision Audit")
    badge_row(["SYNTHETIC FIXTURE", "NOT CAUSAL", "REAL ATTRIBUTION UNAVAILABLE"])
    st.caption(
        "Auditable decision-time contracts, simple engineering-baseline replays and "
        "attribution-shaped schema fixtures. No real actor or checkpoint is opened; the page does "
        "not establish feature influence, faithfulness, validation, optimality or evidence."
    )
    try:
        console = load_xai_console(Path.cwd())
    except XaiConsoleError as error:
        st.warning(f"Decision Audit unavailable: {error}")
        return
    bundle = console.bundle

    for notice in bundle.notices:
        st.warning(notice)

    st.subheader("Exact synthetic source, actor and checkpoint binding")
    snapshot = bundle.snapshots[0]
    binding_columns = st.columns(4)
    binding_columns[0].metric("Snapshots", len(bundle.snapshots))
    binding_columns[1].metric("Baseline replays", len(bundle.replay_results))
    binding_columns[2].metric("Disagreement rows", len(bundle.disagreement_rows))
    binding_columns[3].metric("Real attribution", "unavailable")
    st.dataframe(
        [
            {
                "bundle digest": bundle.digest(),
                "source artifact": snapshot.source_artifact_digest,
                "actor": snapshot.actor_id,
                "actor contract": snapshot.actor_contract_digest,
                "checkpoint": snapshot.checkpoint_digest,
                "observation contract": snapshot.observation_contract_digest,
                "action vocabulary": snapshot.action_vocabulary_digest,
                "synthetic": snapshot.synthetic_fixture,
                "evidence": snapshot.evidence,
            }
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Policy-disagreement browser")
    disagreement_only = st.checkbox("Show policy disagreements only", value=False)
    selected_action = st.selectbox(
        "Recorded action filter", ("all", "local", "v2i", "v2v"), index=0
    )
    action_filter = cast(ActionName | Literal["all"], selected_action)
    browser = browse_disagreements(
        bundle.disagreement_rows,
        disagreement_only=disagreement_only,
        recorded_action=action_filter,
    )
    st.caption(
        f"Showing {browser.total_rows} immutable rows; {browser.disagreement_rows} contain a "
        "descriptive action difference. A difference does not identify a correct action."
    )
    st.dataframe(
        [
            {
                "snapshot": row.snapshot_id,
                "snapshot digest": row.snapshot_digest,
                "recorded actor": row.recorded_actor_id,
                "recorded checkpoint": row.recorded_checkpoint_digest,
                "recorded action": row.recorded_action,
                "baseline": row.replay_adapter_id,
                "baseline manifest": row.replay_manifest_digest,
                "baseline action": row.replay_action,
                "disagreement": row.disagreement,
                "interpretation": row.interpretation,
                "correct action identified": row.correct_action_identified,
            }
            for row in browser.rows
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Behavioural fingerprints versus declared load")
    st.caption(
        "Action shares are descriptive over 12 synthetic snapshots per policy. Empty bins remain "
        "unavailable; these profiles do not establish sensitivity, generalisation or ranking."
    )
    st.dataframe(
        [
            {
                "policy": fingerprint.policy_id,
                "decision-set digest": fingerprint.decision_set_digest,
                "load bin": row.label,
                "interval": f"[{row.lower_inclusive:.2f}, {row.upper_exclusive:.2f})",
                "support": row.support,
                "local share": row.local_share,
                "V2I share": row.v2i_share,
                "V2V share": row.v2v_share,
                "availability": row.availability,
                "evidence": fingerprint.evidence,
            }
            for fingerprint in bundle.fingerprints
            for row in fingerprint.bins
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Attribution-shaped fixtures — integrity checks only")
    for artifact in bundle.attribution_artifacts:
        with st.expander(f"Inspect {artifact.method}"):
            st.caption(
                f"Snapshot `{artifact.snapshot_id}` / `{artifact.snapshot_digest}`; actor "
                f"`{artifact.actor_id}` / `{artifact.actor_contract_digest}`; checkpoint "
                f"`{artifact.checkpoint_digest}`; artifact `{artifact.artifact_id}`."
            )
            st.dataframe(
                [
                    {
                        "feature": row.feature_name,
                        "synthetic value": row.feature_value,
                        "fixture contribution": row.contribution,
                    }
                    for row in artifact.contributions
                ],
                hide_index=True,
                width="stretch",
            )
            st.caption(
                f"Baseline {artifact.baseline_value:.3f}; synthetic output "
                f"{artifact.output_value:.3f}; reconstruction error "
                f"{artifact.quality.fidelity_value:.3f}; repeat max delta "
                f"{artifact.quality.stability_value:.3f} across "
                f"{artifact.quality.repeats} identical fixture repeats. "
                "Faithfulness validated: false; real actor: false; scientific evidence: false."
            )

    st.subheader("Real-attribution availability")
    st.dataframe(
        [
            {
                "method": capability.method,
                "status": capability.status,
                "missing requirements": " | ".join(capability.missing_requirements),
                "zero substituted": capability.zero_substituted,
                "evidence": capability.evidence,
            }
            for capability in bundle.attribution_capabilities
        ],
        hide_index=True,
        width="stretch",
    )
    st.info(
        "Unavailable means unavailable: no all-zero attribution is substituted for the missing "
        "producer hook, authorised model access or validated application method."
    )

    st.subheader("Source support, limitations and citations")
    st.dataframe(
        [
            {
                "support id": support.support_id,
                "role": support.role,
                "source": support.source_ref,
                "source digest": support.source_digest,
                "binding": support.binding_kind,
                "support scope": support.support_scope,
                "limitation": support.limitation,
                "evidence": support.evidence,
                "LLM output": support.llm_output,
            }
            for support in bundle.source_support
        ],
        hide_index=True,
        width="stretch",
    )
    for link in console.source_links:
        st.markdown(f"- [{link.label}]({link.url}) — SHA-256 `{link.sha256}`; {link.binding}.")
    st.caption(
        "Method-reference identities define artifact families only. Literature evidence, project "
        "measurements and synthetic fixture output remain separate."
    )
