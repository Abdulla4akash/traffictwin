"""Deterministic Manchester Evidence Hub projection."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.metrics.results import JsonScalar


class ManchesterSourceReadiness(BaseModel):
    """One source readiness row."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    coverage_scope: str = Field(min_length=1)
    freshness_state: str = Field(min_length=1)
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
    # Check for accepted snapshot catalogue or evidence directory
    target = workspace / subpath
    return target.exists()


def _source_definitions(workspace: Path | None) -> list[ManchesterSourceReadiness]:
    bods_configured = _env_configured("BODS_API_KEY")
    nh_configured = _env_configured("NATIONAL_HIGHWAYS_API_KEY")
    # DfT and WebTRIS are file-based historical, check workspace for accepted snapshots
    dft_accepted = _workspace_has_accepted(workspace, "evidence/dft") or _workspace_has_accepted(workspace, "manchester/dft")
    webtris_accepted = _workspace_has_accepted(workspace, "evidence/webtris") or _workspace_has_accepted(workspace, "manchester/webtris")
    tfgm_accepted = _workspace_has_accepted(workspace, "evidence/tfgm") or _workspace_has_accepted(workspace, "manchester/tfgm")

    return [
        ManchesterSourceReadiness(
            source_id="dft",
            display_name="DfT traffic counts",
            source_role="Historical traffic count evidence",
            evidence_type="historical",
            coverage_scope="DfT count points (survey, not live)",
            freshness_state="historical",
            configuration_state="Configured" if dft_accepted else "Not configured (no accepted snapshot)",
            local_evidence_state="Accepted local evidence available" if dft_accepted else "No accepted local evidence",
            acquisition_readiness="Ready (historical snapshot catalogue)" if dft_accepted else "Not ready — no accepted snapshot",
            rights_retention_state="NOT RECORDED / OWNER DECISION REQUIRED",
            scientific_gate_state="BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED — map matching, road-class, ambiguity threshold",
            last_receipt_summary="Accepted DfT snapshot" if dft_accepted else None,
            blockers=[] if dft_accepted else ["No accepted DfT snapshot catalogue"],
            next_action="Open Manchester Operations for DfT catalogue" if dft_accepted else "Acquire DfT snapshot via Manchester Operations",
            limitations=["Historical evidence only; NOT live traffic", "Survey denominator, not instantaneous SUMO demand"],
        ),
        ManchesterSourceReadiness(
            source_id="webtris",
            display_name="WebTRIS",
            source_role="Historical/latest WebTRIS evidence (per accepted contract)",
            evidence_type="historical/latest",
            coverage_scope="Strategic road network (WebTRIS sites, not Manchester city roads)",
            freshness_state="historical/latest",
            configuration_state="Configured" if webtris_accepted else "Not configured (no accepted snapshot)",
            local_evidence_state="Accepted local evidence available" if webtris_accepted else "No accepted local evidence",
            acquisition_readiness="Ready (accepted snapshot catalogue)" if webtris_accepted else "Not ready — no accepted snapshot",
            rights_retention_state="NOT RECORDED / OWNER DECISION REQUIRED",
            scientific_gate_state="BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED — calibration objective, parameter bounds",
            last_receipt_summary="Accepted WebTRIS snapshot" if webtris_accepted else None,
            blockers=[] if webtris_accepted else ["No accepted WebTRIS snapshot catalogue"],
            next_action="Open Manchester Operations for WebTRIS catalogue",
            limitations=["Historical/latest only per accepted contract; do not call live", "Strategic road network only"],
        ),
        ManchesterSourceReadiness(
            source_id="bods",
            display_name="BODS bus positions",
            source_role="Live/recent BUS positions — bus-only",
            evidence_type="live_vehicle",
            coverage_scope="Bus positions only — NOT general private-vehicle traffic, NOT Manchester-wide road flow",
            freshness_state="live_vehicle" if bods_configured else "unavailable",
            configuration_state="Configured" if bods_configured else "Not configured (BODS_API_KEY unavailable)",
            local_evidence_state="Live control available" if bods_configured else "No live evidence",
            acquisition_readiness="Acquisition-ready (BODS live control)" if bods_configured else "Not ready — credential unavailable",
            rights_retention_state="NOT RECORDED / OWNER DECISION REQUIRED",
            scientific_gate_state="BLOCKED / PROVIDER REQUIRED — BODS retention, privacy, licence",
            last_receipt_summary="BODS live control state" if bods_configured else None,
            blockers=[] if bods_configured else ["BODS_API_KEY not configured"],
            next_action="Configure BODS_API_KEY and open Manchester Operations for BODS live control" if not bods_configured else "Open Manchester Operations for BODS live scene",
            limitations=["BODS is bus-only; NOT general private-vehicle traffic", "Live/recent only when configured; not Manchester-wide flow"],
        ),
        ManchesterSourceReadiness(
            source_id="national_highways",
            display_name="National Highways",
            source_role="Strategic-road operational evidence",
            evidence_type="near_live",
            coverage_scope="Strategic road network only — NOT general Manchester city-road coverage",
            freshness_state="near_live" if nh_configured else "unavailable",
            configuration_state="Configured" if nh_configured else "Not configured (NATIONAL_HIGHWAYS_API_KEY unavailable)",
            local_evidence_state="Live control available" if nh_configured else "No live evidence",
            acquisition_readiness="Acquisition-ready (National Highways live control)" if nh_configured else "Not ready — credential unavailable",
            rights_retention_state="NOT RECORDED / OWNER DECISION REQUIRED",
            scientific_gate_state="BLOCKED / PROVIDER REQUIRED — National Highways retention, licence",
            last_receipt_summary="National Highways live control state" if nh_configured else None,
            blockers=[] if nh_configured else ["NATIONAL_HIGHWAYS_API_KEY not configured"],
            next_action="Configure NATIONAL_HIGHWAYS_API_KEY and open Manchester Operations" if not nh_configured else "Open Manchester Operations for National Highways scene",
            limitations=["Strategic-road operational evidence only; NOT Manchester city-road coverage", "Near-live per provider contract"],
        ),
        ManchesterSourceReadiness(
            source_id="tfgm",
            display_name="TfGM infrastructure",
            source_role="Infrastructure/reference information",
            evidence_type="infrastructure",
            coverage_scope="TfGM signal locations — reference layer, NOT traffic telemetry",
            freshness_state="historical" if tfgm_accepted else "unavailable",
            configuration_state="Configured" if tfgm_accepted else "Not configured (no accepted TfGM snapshot)",
            local_evidence_state="Accepted local evidence available" if tfgm_accepted else "No accepted local evidence",
            acquisition_readiness="Ready (TfGM snapshot catalogue)" if tfgm_accepted else "Not ready — no accepted snapshot",
            rights_retention_state="NOT RECORDED / OWNER DECISION REQUIRED",
            scientific_gate_state="BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED — infrastructure vs telemetry distinction",
            last_receipt_summary="Accepted TfGM snapshot" if tfgm_accepted else None,
            blockers=[] if tfgm_accepted else ["No accepted TfGM snapshot"],
            next_action="Open Manchester Operations for TfGM catalogue",
            limitations=["Infrastructure is NOT telemetry; TfGM metadata is reference unless telemetry supplied and accepted", "No live traffic telemetry from infrastructure alone"],
        ),
        ManchesterSourceReadiness(
            source_id="static_boundaries",
            display_name="Static ONS Manchester boundaries",
            source_role="Geographic context only",
            evidence_type="geographic_context",
            coverage_scope="Greater Manchester boundary (ONS BGC 20m, E47000001/E08000003)",
            freshness_state="historical",
            configuration_state="Static asset available",
            local_evidence_state="Accepted local evidence (static boundary)",
            acquisition_readiness="Ready (static asset, no acquisition)",
            rights_retention_state="OGL-3.0, Contains OS data © Crown copyright 2025",
            scientific_gate_state="NOT APPLICABLE — geographic context only",
            last_receipt_summary="Static ONS boundary asset",
            blockers=[],
            next_action="View on Home Manchester context map",
            limitations=["Geographic context only; NOT traffic evidence", "Static, not live"],
        ),
        ManchesterSourceReadiness(
            source_id="manual_incident",
            display_name="Manual incident / authored scenario",
            source_role="AUTHORED SCENARIO INPUT — not an observation",
            evidence_type="authored_input",
            coverage_scope="Manually entered incident changes scenario definition only",
            freshness_state="synthetic",
            configuration_state="Available via Scenario Builder",
            local_evidence_state="Authored input available",
            acquisition_readiness="Ready (authoring via Scenario Builder)",
            rights_retention_state="NOT RECORDED / OWNER DECISION REQUIRED",
            scientific_gate_state="NOT APPLICABLE — authored input, not evidence",
            last_receipt_summary="Scenario Builder authored incident",
            blockers=[],
            next_action="Open Scenario Builder to author incident/event",
            limitations=["Manually entered incident does NOT become observed Manchester evidence", "Changes scenario definition only"],
        ),
        ManchesterSourceReadiness(
            source_id="social_media",
            display_name="Social media",
            source_role="Deferred — no ingestion",
            evidence_type="deferred",
            coverage_scope="Deferred social media source",
            freshness_state="unavailable",
            configuration_state="Deferred",
            local_evidence_state="Unavailable — no ingestion",
            acquisition_readiness="Unavailable — deferred per design",
            rights_retention_state="NOT RECORDED / OWNER DECISION REQUIRED",
            scientific_gate_state="BLOCKED / DEFERRED",
            last_receipt_summary=None,
            blockers=["Social media ingestion deferred per V2 design"],
            next_action="No action — deferred",
            limitations=["No social media ingestion; do not add"],
        ),
    ]


def build_manchester_hub_view(
    workspace: Path | None = None,
) -> ManchesterEvidenceHubView:
    """Build deterministic hub view without network calls and without secrets."""

    import datetime

    sources = _source_definitions(workspace)
    # Stable ordering by source_id
    sources_sorted = sorted(sources, key=lambda s: s.source_id)
    available = sum(1 for s in sources_sorted if "Available" in s.local_evidence_state and "No " not in s.local_evidence_state)
    blocked = sum(1 for s in sources_sorted if s.blockers)
    unavailable = len(sources_sorted) - available - blocked
    if unavailable < 0:
        unavailable = 0
    accepted = sum(1 for s in sources_sorted if "Accepted local evidence" in s.local_evidence_state)
    workspace_state = "Workspace configured" if workspace and workspace.exists() else "No workspace — provider evidence unavailable"
    warnings: list[str] = []
    # Source-specific warnings to ensure truthfulness
    warnings.append("BODS is bus-only; not general private-vehicle traffic")
    warnings.append("National Highways is strategic-road only; not Manchester city-road coverage")
    warnings.append("DfT is historical; WebTRIS is historical/latest per contract; TfGM is infrastructure reference")
    if not any(s.source_id == "bods" and s.configuration_state.startswith("Configured") for s in sources_sorted):
        warnings.append("BODS live evidence requires BODS_API_KEY")
    if not any(s.source_id == "national_highways" and s.configuration_state.startswith("Configured") for s in sources_sorted):
        warnings.append("National Highways live evidence requires NATIONAL_HIGHWAYS_API_KEY")

    # Fingerprint binds substantive displayed state, no secrets
    payload = {
        "sources": [
            {
                "source_id": s.source_id,
                "evidence_type": s.evidence_type,
                "freshness_state": s.freshness_state,
                "configuration_state": s.configuration_state,
                "local_evidence_state": s.local_evidence_state,
                "acquisition_readiness": s.acquisition_readiness,
                "blockers": sorted(s.blockers),
                "next_action": s.next_action,
            }
            for s in sources_sorted
        ],
        "workspace_state": workspace_state,
        "warnings": sorted(warnings),
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return ManchesterEvidenceHubView(
        sources=sources_sorted,
        available_count=available,
        blocked_count=blocked,
        unavailable_count=unavailable,
        accepted_evidence_count=accepted,
        warnings=warnings,
        workspace_state=workspace_state,
        fingerprint=fingerprint,
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

