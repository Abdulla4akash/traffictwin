"""Deterministic Manchester Evidence Hub projection — hardened M1."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.integration.manchester.freshness import FreshnessTruthState


class ManchesterSourceReadiness(BaseModel):
    """One source readiness row with four-state separation."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    evidence_ceiling: str = Field(min_length=1)
    coverage_scope: str = Field(min_length=1)
    freshness_state: FreshnessTruthState = Field()
    software_support_state: str = Field(min_length=1)
    configuration_state: str = Field(min_length=1)
    local_evidence_state: str = Field(min_length=1)
    acquisition_readiness: str = Field(min_length=1)
    rights_retention_state: str = Field(min_length=1)
    scientific_gate_state: str = Field(min_length=1)
    last_receipt_summary: str | None = None
    blockers: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class ManchesterEvidenceHubView(BaseModel):
    """Aggregated hub view."""

    model_config = ConfigDict(extra="forbid")

    sources: list[ManchesterSourceReadiness] = Field(default_factory=list)
    available_count: int = 0
    blocked_count: int = 0
    unavailable_count: int = 0
    accepted_evidence_count: int = 0
    known_source_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    workspace_state: str = Field(min_length=1)
    fingerprint: str = ""
    generated_at: str = ""


def _env_configured(key: str) -> bool:
    val = os.environ.get(key, "")
    return bool(val and val.strip())


def _workspace_has_accepted(workspace: Path | None, subpath: str) -> bool:
    if workspace is None or not workspace.exists():
        return False
    target = workspace / subpath
    return target.exists()


def _source_definitions(workspace: Path | None) -> list[ManchesterSourceReadiness]:
    bods_configured = _env_configured("BODS_API_KEY")
    nh_configured = _env_configured("NATIONAL_HIGHWAYS_API_KEY")
    dft_accepted = _workspace_has_accepted(workspace, "evidence/dft") or _workspace_has_accepted(
        workspace, "manchester/dft"
    )
    webtris_accepted = _workspace_has_accepted(
        workspace, "evidence/webtris"
    ) or _workspace_has_accepted(workspace, "manchester/webtris")
    tfgm_accepted = _workspace_has_accepted(workspace, "evidence/tfgm") or _workspace_has_accepted(
        workspace, "manchester/tfgm"
    )

    # Four-state separation:
    # SOFTWARE SUPPORT = client/parser implemented?
    # ACQUISITION READINESS = credentials/config present?
    # LOCAL EVIDENCE = accepted snapshot present?
    # SCIENTIFIC ACCEPTANCE = owner/scientific decision present? (always BLOCKED in M1)

    return [
        ManchesterSourceReadiness(
            source_id="bods",
            display_name="BODS bus positions",
            source_role="Live/recent BUS positions — bus-only",
            evidence_type="live_vehicle",
            evidence_ceiling=(
                "Live/recent BUS-only vehicle positions only; never general road traffic"
            ),
            coverage_scope="Bus positions only — NOT general private-vehicle traffic, NOT Manchester-wide road flow",  # noqa: E501
            freshness_state="live_vehicle" if bods_configured else "unavailable",
            software_support_state="AVAILABLE — BODS live control client implemented",
            configuration_state="Configured"
            if bods_configured
            else "Not configured (BODS_API_KEY unavailable)",
            local_evidence_state="Live control available"
            if bods_configured
            else "No live evidence",
            acquisition_readiness="Acquisition-ready (BODS live control)"
            if bods_configured
            else "Not ready — credential unavailable",
            rights_retention_state="NOT_RECORDED / OWNER_DECISION_REQUIRED",
            scientific_gate_state="BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED — BODS retention, privacy, licence",  # noqa: E501
            last_receipt_summary="BODS live control state" if bods_configured else None,
            blockers=[] if bods_configured else ["BODS_API_KEY not configured"],
            next_action="Configure BODS_API_KEY and open Manchester Operations for BODS live control"  # noqa: E501
            if not bods_configured
            else "Open Manchester Operations for BODS live scene",
            limitations=[
                "BODS is bus-only; NOT general private-vehicle traffic",
                "Live/recent only when configured; not Manchester-wide flow",
            ],
        ),
        ManchesterSourceReadiness(
            source_id="dft",
            display_name="DfT traffic counts",
            source_role="Historical traffic count evidence",
            evidence_type="historical",
            evidence_ceiling="Historical DfT survey evidence only; never live",
            coverage_scope="DfT count points (survey, not live)",
            freshness_state="historical",
            software_support_state="AVAILABLE — DfT catalogue client implemented (offline, no credential)",  # noqa: E501
            configuration_state="Ready (historical snapshot catalogue — code available)",
            local_evidence_state="Accepted local evidence available"
            if dft_accepted
            else "No accepted local evidence",
            acquisition_readiness="READY — historical snapshot catalogue (no credential required)",
            rights_retention_state="NOT_RECORDED / OWNER_DECISION_REQUIRED",
            scientific_gate_state="BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED — map matching, road-class, ambiguity threshold",  # noqa: E501
            last_receipt_summary="Accepted DfT snapshot" if dft_accepted else None,
            blockers=[] if dft_accepted else ["No accepted DfT snapshot catalogue"],
            next_action="Open Manchester Operations for DfT catalogue"
            if dft_accepted
            else "Acquire DfT snapshot via Manchester Operations",
            limitations=[
                "Historical evidence only; NOT live traffic",
                "Survey denominator, not instantaneous SUMO demand",
            ],
        ),
        ManchesterSourceReadiness(
            source_id="manual_incident",
            display_name="Manual incident / authored scenario",
            source_role="AUTHORED SCENARIO INPUT — not an observation",
            evidence_type="authored_input",
            evidence_ceiling="Authored scenario input only; never observed evidence",
            coverage_scope="Manually entered incident changes scenario definition only",
            freshness_state="synthetic",
            software_support_state="AVAILABLE — authoring via Scenario Builder",
            configuration_state="Available via Scenario Builder",
            local_evidence_state="Authored input available",
            acquisition_readiness="READY — authoring via Scenario Builder",
            rights_retention_state="NOT_RECORDED / OWNER_DECISION_REQUIRED",
            scientific_gate_state="NOT_APPLICABLE — authored input, not evidence",
            last_receipt_summary="Scenario Builder authored incident",
            blockers=[],
            next_action="Open Scenario Builder to author incident/event",
            limitations=[
                "Manually entered incident does NOT become observed Manchester evidence",
                "Changes scenario definition only",
            ],
        ),
        ManchesterSourceReadiness(
            source_id="national_highways",
            display_name="National Highways",
            source_role="Strategic-road operational evidence",
            evidence_type="near_live",
            evidence_ceiling="Strategic-road operational evidence only; never Manchester city-wide road coverage",  # noqa: E501
            coverage_scope="Strategic road network only — NOT general Manchester city-road coverage",  # noqa: E501
            freshness_state="near_live" if nh_configured else "unavailable",
            software_support_state="AVAILABLE — National Highways live control client implemented",
            configuration_state="Configured"
            if nh_configured
            else "Not configured (NATIONAL_HIGHWAYS_API_KEY unavailable)",
            local_evidence_state="Live control available" if nh_configured else "No live evidence",
            acquisition_readiness="Acquisition-ready (National Highways live control)"
            if nh_configured
            else "Not ready — credential unavailable",
            rights_retention_state="NOT_RECORDED / OWNER_DECISION_REQUIRED",
            scientific_gate_state="BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED — National Highways retention, licence",  # noqa: E501
            last_receipt_summary="National Highways live control state" if nh_configured else None,
            blockers=[] if nh_configured else ["NATIONAL_HIGHWAYS_API_KEY not configured"],
            next_action="Configure NATIONAL_HIGHWAYS_API_KEY and open Manchester Operations"
            if not nh_configured
            else "Open Manchester Operations for National Highways scene",
            limitations=[
                "Strategic-road operational evidence only; NOT Manchester city-road coverage",
                "Near-live per provider contract",
            ],
        ),
        ManchesterSourceReadiness(
            source_id="social_media",
            display_name="Social media",
            source_role="Deferred — no ingestion",
            evidence_type="deferred",
            evidence_ceiling="No evidence ceiling — ingestion deferred, must not be added",
            coverage_scope="Deferred social media source",
            freshness_state="unavailable",
            software_support_state="DEFERRED — no adapter implemented",
            configuration_state="Deferred",
            local_evidence_state="Unavailable — no ingestion",
            acquisition_readiness="UNAVAILABLE — deferred per design",
            rights_retention_state="NOT_RECORDED / OWNER_DECISION_REQUIRED",
            scientific_gate_state="BLOCKED / DEFERRED",
            last_receipt_summary=None,
            blockers=["Social media ingestion deferred per V2 design"],
            next_action="No action — deferred",
            limitations=["No social media ingestion; do not add"],
        ),
        ManchesterSourceReadiness(
            source_id="static_boundaries",
            display_name="Static ONS Manchester boundaries",
            source_role="Geographic context only",
            evidence_type="geographic_context",
            evidence_ceiling="Static geographic context only; never traffic evidence",
            coverage_scope="Greater Manchester boundary (ONS BGC 20m, E47000001/E08000003)",
            freshness_state="unavailable",
            software_support_state="AVAILABLE — static asset bundled (no acquisition)",
            configuration_state="Static asset available",
            local_evidence_state="Accepted local evidence (static boundary)",
            acquisition_readiness="READY — static asset, no acquisition required",
            rights_retention_state="RECORDED — OGL-3.0, Contains OS data © Crown copyright 2025",
            scientific_gate_state="NOT_APPLICABLE — geographic context only",
            last_receipt_summary="Static ONS boundary asset",
            blockers=[],
            next_action="View on Home Manchester context map",
            limitations=["Geographic context only; NOT traffic evidence", "Static, not live"],
        ),
        ManchesterSourceReadiness(
            source_id="tfgm",
            display_name="TfGM infrastructure",
            source_role="Infrastructure/reference information",
            evidence_type="infrastructure",
            evidence_ceiling="Infrastructure metadata only; no traffic telemetry unless supplied and accepted",  # noqa: E501
            coverage_scope="TfGM signal locations — reference layer, NOT traffic telemetry",
            freshness_state="unavailable",
            software_support_state="AVAILABLE — TfGM signal catalogue client implemented",
            configuration_state="Ready (TfGM catalogue code available)"
            if tfgm_accepted
            else "Ready (TfGM catalogue code available; no accepted snapshot)",
            local_evidence_state="Accepted local evidence available"
            if tfgm_accepted
            else "No accepted local evidence",
            acquisition_readiness="READY — TfGM snapshot catalogue (no credential required)",
            rights_retention_state="NOT_RECORDED / OWNER_DECISION_REQUIRED",
            scientific_gate_state="BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED — infrastructure vs telemetry distinction",  # noqa: E501
            last_receipt_summary="Accepted TfGM snapshot" if tfgm_accepted else None,
            blockers=[] if tfgm_accepted else ["No accepted TfGM snapshot"],
            next_action="Open Manchester Operations for TfGM catalogue",
            limitations=[
                "Infrastructure is NOT telemetry; TfGM metadata is reference unless telemetry supplied and accepted",  # noqa: E501
                "No live traffic telemetry from infrastructure alone",
            ],
        ),
        ManchesterSourceReadiness(
            source_id="tfgm_ntis_measured_traffic",
            display_name="TfGM/NTIS measured traffic",
            source_role="Measured road-traffic telemetry — UNAVAILABLE pending provider contract",
            evidence_type="measured_traffic",
            evidence_ceiling="No measured Manchester traffic without provider contract and adapter",
            coverage_scope="Provider-restricted measured traffic (TfGM SCOOT/UTC/UTMC/counter or NTIS) — unavailable",  # noqa: E501
            freshness_state="unavailable",
            software_support_state="UNAVAILABLE — adapter not implemented pending provider contract",  # noqa: E501
            configuration_state="UNAVAILABLE — provider contract required",
            local_evidence_state="Unavailable — no ingestion; adapter not implemented",
            acquisition_readiness="UNAVAILABLE — provider contract required; no acquisition implemented",  # noqa: E501
            rights_retention_state="PROVIDER_CONTRACT_REQUIRED",
            scientific_gate_state="BLOCKED / PROVIDER CONTRACT REQUIRED — no measured traffic without independent provider contract",  # noqa: E501
            last_receipt_summary=None,
            blockers=[
                "TfGM/NTIS measured traffic requires independent provider contract; no adapter implemented"  # noqa: E501
            ],
            next_action="Await provider contract; no acquisition available",
            limitations=[
                "No TfGM/NTIS measured traffic without provider contract and approved adapter",
                "Infrastructure reference must not be treated as telemetry",
            ],
        ),
        ManchesterSourceReadiness(
            source_id="webtris",
            display_name="WebTRIS",
            source_role="Historical/latest WebTRIS evidence (per accepted contract)",
            evidence_type="historical",
            evidence_ceiling="Historical/latest-available only per accepted contract; never live city-road traffic",  # noqa: E501
            coverage_scope="Strategic road network (WebTRIS sites, not Manchester city roads)",
            freshness_state="historical",
            software_support_state="AVAILABLE — WebTRIS catalogue client implemented (offline, no credential)",  # noqa: E501
            configuration_state="Ready (historical snapshot catalogue — code available)",
            local_evidence_state="Accepted local evidence available"
            if webtris_accepted
            else "No accepted local evidence",
            acquisition_readiness="READY — accepted snapshot catalogue (no credential required)",
            rights_retention_state="NOT_RECORDED / OWNER_DECISION_REQUIRED",
            scientific_gate_state="BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED — calibration objective, parameter bounds",  # noqa: E501
            last_receipt_summary="Accepted WebTRIS snapshot" if webtris_accepted else None,
            blockers=[] if webtris_accepted else ["No accepted WebTRIS snapshot catalogue"],
            next_action="Open Manchester Operations for WebTRIS catalogue",
            limitations=[
                "Historical/latest only per accepted contract; do not call live",
                "Strategic road network only",
            ],
        ),
    ]


def build_manchester_hub_view(
    workspace: Path | None = None,
) -> ManchesterEvidenceHubView:
    """Build deterministic hub view without network calls and without secrets."""

    sources = _source_definitions(workspace)
    sources_sorted = sorted(sources, key=lambda s: s.source_id)
    # Precise counts — do not conflate known vs accepted vs acquisition-ready
    known = len(sources_sorted)
    accepted = sum(1 for s in sources_sorted if "Accepted local evidence" in s.local_evidence_state)
    # Acquisition-ready: explicit READY/acquisition-ready states, not merely local evidence
    available = sum(
        1
        for s in sources_sorted
        if s.acquisition_readiness.startswith("READY")
        or "Acquisition-ready" in s.acquisition_readiness
        or s.acquisition_readiness.startswith("READY — static")
    )
    # For live sources, available is credential-configured; for historical, always READY
    # Recompute blocked as sources with non-empty blockers
    blocked = sum(1 for s in sources_sorted if s.blockers)
    # Unavailable: sources lacking accepted/live evidence
    # Unavailable distinct: freshness unavailable and no accepted evidence
    unavailable = sum(
        1
        for s in sources_sorted
        if s.local_evidence_state.startswith("Unavailable")
        or s.local_evidence_state.startswith("No accepted")
        or s.local_evidence_state.startswith("No live")
    )
    # Unavailable is informational; ensure non-negative
    # For hub semantics, unavailable is just for information; ensure non-negative
    if unavailable < 0:
        unavailable = 0
    workspace_state = (
        "Workspace configured"
        if workspace and workspace.exists()
        else "No workspace — provider evidence unavailable"
    )
    warnings: list[str] = []
    warnings.append("BODS is bus-only; not general private-vehicle traffic")
    warnings.append("National Highways is strategic-road only; not Manchester city-road coverage")
    warnings.append(
        "DfT is historical; WebTRIS is historical per accepted contract; TfGM is infrastructure reference"  # noqa: E501
    )
    if not any(
        s.source_id == "bods" and s.configuration_state.startswith("Configured")
        for s in sources_sorted
    ):
        warnings.append("BODS live evidence requires BODS_API_KEY")
    if not any(
        s.source_id == "national_highways" and s.configuration_state.startswith("Configured")
        for s in sources_sorted
    ):
        warnings.append("National Highways live evidence requires NATIONAL_HIGHWAYS_API_KEY")
    warnings.append(
        "TfGM/NTIS measured traffic unavailable until provider contract and adapter exist"
    )

    # Fingerprint binds substantive displayed state, no secrets, no paths, no wall clock
    payload = {
        "sources": [
            {
                "source_id": s.source_id,
                "source_role": s.source_role,
                "evidence_type": s.evidence_type,
                "evidence_ceiling": s.evidence_ceiling,
                "coverage_scope": s.coverage_scope,
                "freshness_state": s.freshness_state,
                "software_support_state": s.software_support_state,
                "acquisition_readiness": s.acquisition_readiness,
                "local_evidence_state": s.local_evidence_state,
                "rights_retention_state": s.rights_retention_state,
                "scientific_gate_state": s.scientific_gate_state,
                "blockers": sorted(s.blockers),
                "next_action": s.next_action,
            }
            for s in sources_sorted
        ],
        "workspace_state": workspace_state,
        "warnings": sorted(warnings),
        "known_source_count": known,
        "accepted_evidence_count": accepted,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()
    return ManchesterEvidenceHubView(
        sources=sources_sorted,
        available_count=available,
        blocked_count=blocked,
        unavailable_count=unavailable,
        accepted_evidence_count=accepted,
        known_source_count=known,
        warnings=warnings,
        workspace_state=workspace_state,
        fingerprint=fingerprint,
        generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )
