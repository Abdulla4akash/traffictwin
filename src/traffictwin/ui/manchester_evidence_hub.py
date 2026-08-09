"""Deterministic Manchester Evidence Hub projection — hardened M1 with typed readiness."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, computed_field

from traffictwin.integration.manchester.freshness import FreshnessTruthState


class SoftwareSupportState(StrEnum):
    """Machine-typed software support standing."""

    AVAILABLE = "available"
    UNAVAILABLE_PROVIDER_CONTRACT = "unavailable_provider_contract"
    DEFERRED = "deferred"


class AcquisitionReadinessState(StrEnum):
    """Machine-typed acquisition/config standing."""

    READY = "ready"
    NOT_READY_CREDENTIAL_MISSING = "not_ready_credential_missing"
    UNAVAILABLE_PROVIDER_CONTRACT = "unavailable_provider_contract"
    UNAVAILABLE_DEFERRED = "unavailable_deferred"


class LocalEvidenceState(StrEnum):
    """Machine-typed local evidence standing."""

    ACCEPTED_AVAILABLE = "accepted_available"
    NOT_ACCEPTED = "not_accepted"
    LIVE_AVAILABLE = "live_available"
    NO_LIVE = "no_live"
    STATIC_AVAILABLE = "static_available"
    AUTHORED_AVAILABLE = "authored_available"
    UNAVAILABLE = "unavailable"


class RightsRetentionState(StrEnum):
    """Machine-typed rights/retention standing."""

    NOT_RECORDED = "not_recorded"
    PROVIDER_CONTRACT_REQUIRED = "provider_contract_required"
    RECORDED = "recorded"


class ScientificGateState(StrEnum):
    """Machine-typed scientific gate standing."""

    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED_PROVIDER_CONTRACT = "blocked_provider_contract"
    BLOCKED_DEFERRED = "blocked_deferred"


def format_software_support(state: SoftwareSupportState) -> str:
    """Authoritative formatter for software support state."""
    mapping = {
        SoftwareSupportState.AVAILABLE: "AVAILABLE",
        SoftwareSupportState.UNAVAILABLE_PROVIDER_CONTRACT: "UNAVAILABLE — adapter not implemented pending provider contract",  # noqa: E501
        SoftwareSupportState.DEFERRED: "DEFERRED — no adapter implemented",
    }
    return mapping[state]


def format_acquisition_readiness(state: AcquisitionReadinessState) -> str:
    """Authoritative formatter for acquisition readiness."""
    mapping = {
        AcquisitionReadinessState.READY: "READY",
        AcquisitionReadinessState.NOT_READY_CREDENTIAL_MISSING: "NOT READY — credential unavailable",  # noqa: E501
        AcquisitionReadinessState.UNAVAILABLE_PROVIDER_CONTRACT: "UNAVAILABLE — provider contract required",  # noqa: E501
        AcquisitionReadinessState.UNAVAILABLE_DEFERRED: "UNAVAILABLE — deferred per design",
    }
    return mapping[state]


def format_local_evidence(state: LocalEvidenceState) -> str:
    """Authoritative formatter for local evidence state."""
    mapping = {
        LocalEvidenceState.ACCEPTED_AVAILABLE: "Accepted local evidence available",
        LocalEvidenceState.NOT_ACCEPTED: "No accepted local evidence",
        LocalEvidenceState.LIVE_AVAILABLE: "Live control available",
        LocalEvidenceState.NO_LIVE: "No live evidence",
        LocalEvidenceState.STATIC_AVAILABLE: "Accepted local evidence (static boundary)",
        LocalEvidenceState.AUTHORED_AVAILABLE: "Authored input available",
        LocalEvidenceState.UNAVAILABLE: "Unavailable — no ingestion",
    }
    return mapping[state]


def format_rights_retention(state: RightsRetentionState) -> str:
    """Authoritative formatter for rights/retention."""
    mapping = {
        RightsRetentionState.NOT_RECORDED: "NOT_RECORDED / OWNER_DECISION_REQUIRED",
        RightsRetentionState.PROVIDER_CONTRACT_REQUIRED: "PROVIDER_CONTRACT_REQUIRED",
        RightsRetentionState.RECORDED: "RECORDED",
    }
    return mapping[state]


def format_scientific_gate(state: ScientificGateState) -> str:
    """Authoritative formatter for scientific gate."""
    mapping = {
        ScientificGateState.BLOCKED: "BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED",
        ScientificGateState.NOT_APPLICABLE: "NOT_APPLICABLE",
        ScientificGateState.BLOCKED_PROVIDER_CONTRACT: "BLOCKED / PROVIDER CONTRACT REQUIRED",
        ScientificGateState.BLOCKED_DEFERRED: "BLOCKED / DEFERRED",
    }
    return mapping[state]


class ManchesterSourceReadiness(BaseModel):
    """One source readiness row with six-dimension separation and typed machine state.

    Typed states are primary; presentation labels are derived via authoritative
    formatters and cannot be supplied independently. Contradictory prose is
    impossible to inject — extra state-display inputs are rejected as unknown.
    Source-specific explanation lives in blockers/limitations/next_action and
    optionally scientific_gate_reasons, not in the state label.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    evidence_ceiling: str = Field(min_length=1)
    coverage_scope: str = Field(min_length=1)
    freshness_state: FreshnessTruthState = Field()
    # Typed machine state — primary identity for counts/filters/fingerprint
    software_support_typed: SoftwareSupportState = Field()
    acquisition_typed: AcquisitionReadinessState = Field()
    local_evidence_typed: LocalEvidenceState = Field()
    rights_typed: RightsRetentionState = Field()
    scientific_gate_typed: ScientificGateState = Field()
    configuration_state: str = Field(min_length=1)
    last_receipt_summary: str | None = None
    blockers: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    scientific_gate_reasons: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def software_support_state(self) -> str:
        return format_software_support(self.software_support_typed)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def acquisition_readiness(self) -> str:
        return format_acquisition_readiness(self.acquisition_typed)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def local_evidence_state(self) -> str:
        return format_local_evidence(self.local_evidence_typed)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rights_retention_state(self) -> str:
        return format_rights_retention(self.rights_typed)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def scientific_gate_state(self) -> str:
        return format_scientific_gate(self.scientific_gate_typed)


class ManchesterEvidenceHubView(BaseModel):
    """Aggregated hub view with typed-derived counts.

    Counts are derived ONLY from typed machine state, never from display prose.

    Definitions:
    - blocked: scientific_gate_typed in {BLOCKED, BLOCKED_PROVIDER_CONTRACT,
      BLOCKED_DEFERRED} — explicit blocking of scientific/provider contract.
    - unavailable: local_evidence_typed in {NOT_ACCEPTED, NO_LIVE, UNAVAILABLE}
      — qualifying evidence/acquisition unavailable under current projection.
      A source may be both blocked AND unavailable; union counts unique ids.
    - manual_incident (AUTHORED_AVAILABLE/NOT_APPLICABLE) and static_boundaries
      (STATIC_AVAILABLE/NOT_APPLICABLE) are geographic/authored context, never
      counted as Manchester traffic available.
    """

    model_config = ConfigDict(extra="forbid")

    sources: list[ManchesterSourceReadiness] = Field(default_factory=list)
    available_count: int = Field(
        default=0,
        description="Deprecated alias for acquisition_ready_count — acquisition-ready sources",
    )
    acquisition_ready_count: int = Field(
        default=0, description="Acquisition-ready sources (typed READY)"
    )
    blocked_count: int = 0
    unavailable_count: int = 0
    accepted_evidence_count: int = 0
    known_source_count: int = 0
    blocked_unavailable_union_count: int = 0
    # Backward compat alias: blocked_or_unavailable is preferred display label,
    # but both union fields stay in sync.
    blocked_or_unavailable_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    workspace_state: str = Field(min_length=1)
    fingerprint: str = ""
    generated_at: str = ""

    @property
    def blocked_or_unavailable(self) -> int:
        """Alias for blocked_unavailable_union_count."""
        return self.blocked_unavailable_union_count

    def to_portable_dict(self) -> dict[str, object]:
        """Publication-safe substantive payload (no secrets, paths, wall clock)."""
        return {
            "sources": [
                {
                    "source_id": s.source_id,
                    "source_role": s.source_role,
                    "evidence_type": s.evidence_type,
                    "evidence_ceiling": s.evidence_ceiling,
                    "coverage_scope": s.coverage_scope,
                    "freshness_state": str(s.freshness_state),
                    "software_support_typed": s.software_support_typed.value,
                    "acquisition_typed": s.acquisition_typed.value,
                    "local_evidence_typed": s.local_evidence_typed.value,
                    "rights_typed": s.rights_typed.value,
                    "scientific_gate_typed": s.scientific_gate_typed.value,
                    "blockers": sorted(s.blockers),
                    "next_action": s.next_action,
                }
                for s in sorted(self.sources, key=lambda x: x.source_id)
            ],
            "workspace_state": self.workspace_state,
            "warnings": sorted(self.warnings),
            "known_source_count": self.known_source_count,
            "accepted_evidence_count": self.accepted_evidence_count,
            "acquisition_ready_count": self.acquisition_ready_count,
            "blocked_count": self.blocked_count,
            "unavailable_count": self.unavailable_count,
            "blocked_unavailable_union_count": self.blocked_unavailable_union_count,
        }

    def to_canonical_bytes(self) -> bytes:
        """Canonical bytes for fingerprinting (excludes generated_at)."""
        return json.dumps(self.to_portable_dict(), sort_keys=True, default=str).encode()


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
            software_support_typed=SoftwareSupportState.AVAILABLE,
            configuration_state="Configured"
            if bods_configured
            else "Not configured (BODS_API_KEY unavailable)",
            local_evidence_typed=LocalEvidenceState.LIVE_AVAILABLE
            if bods_configured
            else LocalEvidenceState.NO_LIVE,
            acquisition_typed=AcquisitionReadinessState.READY
            if bods_configured
            else AcquisitionReadinessState.NOT_READY_CREDENTIAL_MISSING,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.BLOCKED,
            scientific_gate_reasons=[
                "BODS retention",
                "privacy",
                "licence",
            ],
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
            software_support_typed=SoftwareSupportState.AVAILABLE,
            configuration_state="Ready (historical snapshot catalogue — code available)",
            local_evidence_typed=LocalEvidenceState.ACCEPTED_AVAILABLE
            if dft_accepted
            else LocalEvidenceState.NOT_ACCEPTED,
            acquisition_typed=AcquisitionReadinessState.READY,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.BLOCKED,
            scientific_gate_reasons=[
                "map matching",
                "road-class",
                "ambiguity threshold",
            ],
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
            software_support_typed=SoftwareSupportState.AVAILABLE,
            configuration_state="Available via Scenario Builder",
            local_evidence_typed=LocalEvidenceState.AUTHORED_AVAILABLE,
            acquisition_typed=AcquisitionReadinessState.READY,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.NOT_APPLICABLE,
            scientific_gate_reasons=["authored input, not evidence"],
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
            software_support_typed=SoftwareSupportState.AVAILABLE,
            configuration_state="Configured"
            if nh_configured
            else "Not configured (NATIONAL_HIGHWAYS_API_KEY unavailable)",
            local_evidence_typed=LocalEvidenceState.LIVE_AVAILABLE
            if nh_configured
            else LocalEvidenceState.NO_LIVE,
            acquisition_typed=AcquisitionReadinessState.READY
            if nh_configured
            else AcquisitionReadinessState.NOT_READY_CREDENTIAL_MISSING,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.BLOCKED,
            scientific_gate_reasons=["National Highways retention", "licence"],
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
            software_support_typed=SoftwareSupportState.DEFERRED,
            configuration_state="Deferred",
            local_evidence_typed=LocalEvidenceState.UNAVAILABLE,
            acquisition_typed=AcquisitionReadinessState.UNAVAILABLE_DEFERRED,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.BLOCKED_DEFERRED,
            scientific_gate_reasons=["deferred per V2 design"],
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
            software_support_typed=SoftwareSupportState.AVAILABLE,
            configuration_state="Static asset available",
            local_evidence_typed=LocalEvidenceState.STATIC_AVAILABLE,
            acquisition_typed=AcquisitionReadinessState.READY,
            rights_typed=RightsRetentionState.RECORDED,
            scientific_gate_typed=ScientificGateState.NOT_APPLICABLE,
            scientific_gate_reasons=["geographic context only"],
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
            software_support_typed=SoftwareSupportState.AVAILABLE,
            configuration_state="Ready (TfGM catalogue code available)"
            if tfgm_accepted
            else "Ready (TfGM catalogue code available; no accepted snapshot)",
            local_evidence_typed=LocalEvidenceState.ACCEPTED_AVAILABLE
            if tfgm_accepted
            else LocalEvidenceState.NOT_ACCEPTED,
            acquisition_typed=AcquisitionReadinessState.READY,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.BLOCKED,
            scientific_gate_reasons=["infrastructure vs telemetry distinction"],
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
            software_support_typed=SoftwareSupportState.UNAVAILABLE_PROVIDER_CONTRACT,
            configuration_state="UNAVAILABLE — provider contract required",
            local_evidence_typed=LocalEvidenceState.UNAVAILABLE,
            acquisition_typed=AcquisitionReadinessState.UNAVAILABLE_PROVIDER_CONTRACT,
            rights_typed=RightsRetentionState.PROVIDER_CONTRACT_REQUIRED,
            scientific_gate_typed=ScientificGateState.BLOCKED_PROVIDER_CONTRACT,
            scientific_gate_reasons=["no measured traffic without independent provider contract"],
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
            software_support_typed=SoftwareSupportState.AVAILABLE,
            configuration_state="Ready (historical snapshot catalogue — code available)",
            local_evidence_typed=LocalEvidenceState.ACCEPTED_AVAILABLE
            if webtris_accepted
            else LocalEvidenceState.NOT_ACCEPTED,
            acquisition_typed=AcquisitionReadinessState.READY,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.BLOCKED,
            scientific_gate_reasons=["calibration objective", "parameter bounds"],
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
    known = len(sources_sorted)
    # Typed-derived counts — not substring parsing
    accepted = sum(
        1
        for s in sources_sorted
        if s.local_evidence_typed
        in (LocalEvidenceState.ACCEPTED_AVAILABLE, LocalEvidenceState.STATIC_AVAILABLE)
    )
    available = sum(
        1 for s in sources_sorted if s.acquisition_typed == AcquisitionReadinessState.READY
    )
    blocked = sum(
        1
        for s in sources_sorted
        if s.scientific_gate_typed
        in (
            ScientificGateState.BLOCKED,
            ScientificGateState.BLOCKED_PROVIDER_CONTRACT,
            ScientificGateState.BLOCKED_DEFERRED,
        )
    )
    unavailable = sum(
        1
        for s in sources_sorted
        if s.local_evidence_typed
        in (
            LocalEvidenceState.NOT_ACCEPTED,
            LocalEvidenceState.NO_LIVE,
            LocalEvidenceState.UNAVAILABLE,
        )
    )
    # Honest union — unique sources that are blocked OR unavailable
    blocked_ids = {
        s.source_id
        for s in sources_sorted
        if s.scientific_gate_typed
        in (
            ScientificGateState.BLOCKED,
            ScientificGateState.BLOCKED_PROVIDER_CONTRACT,
            ScientificGateState.BLOCKED_DEFERRED,
        )
    }
    unavailable_ids = {
        s.source_id
        for s in sources_sorted
        if s.local_evidence_typed
        in (
            LocalEvidenceState.NOT_ACCEPTED,
            LocalEvidenceState.NO_LIVE,
            LocalEvidenceState.UNAVAILABLE,
        )
    }
    union_count = len(blocked_ids | unavailable_ids)
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
    # Use typed state, not display prose, to decide warnings
    if not any(
        s.source_id == "bods" and s.acquisition_typed == AcquisitionReadinessState.READY
        for s in sources_sorted
    ):
        warnings.append("BODS live evidence requires BODS_API_KEY")
    if not any(
        s.source_id == "national_highways"
        and s.acquisition_typed == AcquisitionReadinessState.READY
        for s in sources_sorted
    ):
        warnings.append("National Highways live evidence requires NATIONAL_HIGHWAYS_API_KEY")
    warnings.append(
        "TfGM/NTIS measured traffic unavailable until provider contract and adapter exist"
    )

    # Fingerprint binds substantive typed state — use portable payload
    # Construct view without fingerprint first to reuse portable dict logic
    tmp_view = ManchesterEvidenceHubView(
        sources=sources_sorted,
        available_count=available,
        acquisition_ready_count=available,
        blocked_count=blocked,
        unavailable_count=unavailable,
        accepted_evidence_count=accepted,
        known_source_count=known,
        blocked_unavailable_union_count=union_count,
        blocked_or_unavailable_count=union_count,
        warnings=warnings,
        workspace_state=workspace_state,
        fingerprint="",
        generated_at="",
    )
    fingerprint = hashlib.sha256(tmp_view.to_canonical_bytes()).hexdigest()
    return ManchesterEvidenceHubView(
        sources=sources_sorted,
        available_count=available,
        acquisition_ready_count=available,
        blocked_count=blocked,
        unavailable_count=unavailable,
        accepted_evidence_count=accepted,
        known_source_count=known,
        blocked_unavailable_union_count=union_count,
        blocked_or_unavailable_count=union_count,
        warnings=warnings,
        workspace_state=workspace_state,
        fingerprint=fingerprint,
        generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
    )
