"""Fixed-source, read-only service for the Manchester Gate-D page."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import Field

from traffictwin.integration.manchester.gate_d_integration import (
    AnalystReviewReadiness,
    GateDModel,
    GateDSourceBinding,
    ManchesterGateDIntegrationPacket,
    MappingPolicySummary,
    TemporalPartitionSummary,
    TemporalProfileSummary,
    build_gate_d_packet,
    packet_text,
)

SOURCE_BASE = "https://github.com/Abdulla4akash/traffictwin/blob/main/"
SOURCE_REFS = (
    "docs/integration/manchester_map_matching_decision_worksheet.md",
    "docs/integration/evidence/manchester_map_match_candidates_20260725.json",
    "docs/integration/evidence/manchester_map_match_policy_v11_20260725.json",
    "docs/integration/evidence/manchester_dft_temporal_profile_20260725.json",
    "docs/integration/evidence/manchester_chain_restoration_20260728.json",
)
_MAX_SOURCE_BYTES = 2_000_000
_PRIVATE_MARKERS = (
    "/users/",
    "/home/",
    "\\users\\",
    "password",
    "credential",
    "api_key",
    "participant_id",
    "vehicle_id",
)


class ManchesterGateDConsoleError(RuntimeError):
    """Fixed-source console refusal without echoing source content."""


class GateDSourceLink(GateDModel):
    label: str = Field(min_length=3, max_length=120)
    url: str = Field(min_length=10, max_length=400)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: str = Field(min_length=3, max_length=100)


class ManchesterGateDConsole(GateDModel):
    packet: ManchesterGateDIntegrationPacket
    source_links: tuple[GateDSourceLink, ...]
    read_only: bool = True
    external_requests: bool = False
    private_artifact_access: bool = False
    creates_evidence: bool = False


def _read_fixed_source(repository_root: Path, relative: str) -> tuple[bytes, str]:
    root = repository_root.resolve()
    target = repository_root / relative
    if target.is_symlink() or not target.is_file():
        raise ManchesterGateDConsoleError("SOURCE_UNAVAILABLE")
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ManchesterGateDConsoleError("SOURCE_OUTSIDE_REPOSITORY") from error
    size = resolved.stat().st_size
    if size <= 0 or size > _MAX_SOURCE_BYTES:
        raise ManchesterGateDConsoleError("SOURCE_SIZE_REFUSED")
    content = resolved.read_bytes()
    return content, hashlib.sha256(content).hexdigest()


def _parse_json(content: bytes) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManchesterGateDConsoleError("SOURCE_JSON_INVALID") from error
    if not isinstance(value, dict):
        raise ManchesterGateDConsoleError("SOURCE_JSON_SHAPE_INVALID")
    return value


def _mapping_summary(v1: dict[str, Any], v11: dict[str, Any]) -> MappingPolicySummary:
    try:
        base_policy = v1["policy"]
        policy = v11["policy"]
        reconciliation = v11["reconciliation_v1_0_versus_v1_1"]
        current = reconciliation["v1_1"]
        paths = reconciliation["acceptance_paths"]
        denominators = v11["readmission_versus_application"]["denominators"]
        return MappingPolicySummary(
            policy_id=policy["policy_id"],
            policy_fingerprint=policy["policy_fingerprint"],
            outer_search_radius_m=base_policy["outer_search_radius_m"],
            native_eligibility_m=base_policy["native_eligibility_m"],
            fallback_eligibility_m=base_policy["fallback_eligibility_m"],
            strict_clear_native_m=base_policy["clear_native_m"],
            strict_clear_fallback_m=base_policy["clear_fallback_m"],
            direction_tolerance_degrees=base_policy["direction_tolerance_degrees"],
            exact_reference_override_m=policy["override"]["max_distance_m"],
            observations=reconciliation["observations_total"],
            owner_policy_accepted=current["owner_policy_accepted_candidate"],
            awaiting_manual_review=current["awaiting_manual_review"],
            no_suitable_candidate=current["no_suitable_candidate"],
            unavailable_missing_evidence=current["unavailable_missing_evidence"],
            strict_acceptances=paths["strict_v1_0_clear"],
            override_acceptances=paths["exact_reference_family_override"],
            override_applied_edges=denominators["override_applied_candidate_edges"],
            readmitted_edges=denominators["candidates_readmitted_edges"],
            refused_edges=denominators["candidates_refused_edges"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ManchesterGateDConsoleError("MAP_POLICY_SOURCE_REFUSED") from error


def _review_summary(
    restoration: dict[str, Any], mapping: MappingPolicySummary
) -> AnalystReviewReadiness:
    try:
        surface = restoration["step_5_review_surface_restored"]
        return AnalystReviewReadiness(
            queue_total=surface["queued_total"],
            decided_total=surface["decided_total"],
            pending_total=surface["pending_total"],
            awaiting_manual_review=mapping.awaiting_manual_review,
            no_candidate_preserved_total=surface["no_candidate_preserved_total"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ManchesterGateDConsoleError("REVIEW_SOURCE_REFUSED") from error


def _temporal_summary(source: dict[str, Any]) -> TemporalProfileSummary:
    try:
        policy = source["policy"]
        binding = source["source_binding"]
        outcome = source["outcome"]
        partitions = source["partitions"]
        rows = tuple(
            TemporalPartitionSummary(
                partition=name,
                sites=partitions[name]["sites"],
                series=partitions[name]["series"],
                expected_cells=partitions[name]["expected_cells"],
                observed_cells=partitions[name]["observed_cells"],
                missing_cells=partitions[name]["missing_cells"],
                excluded_cells=partitions[name]["excluded_cells"],
                measured_zero_cells=partitions[name]["measured_zero_cells"],
                coverage=Decimal(partitions[name]["coverage"]),
                meets_minimum_coverage=partitions[name]["meets_minimum_coverage"],
            )
            for name in ("development", "held_out")
        )
        return TemporalProfileSummary(
            policy_id=policy["policy_id"],
            policy_fingerprint=policy["policy_fingerprint"],
            source_snapshot_id=binding["snapshot_id"],
            source_raw_fingerprint=binding["raw_fingerprint"],
            time_basis=policy["time_basis"],
            utc_instant_available=policy["utc_projection_available"],
            simulation_origin_local_hour=7,
            interval_seconds=policy["interval_seconds"],
            missing_as_zero=policy["missing_as_zero"],
            offered_rows=outcome["offered_rows"],
            admitted_rows=outcome["admitted_rows"],
            excluded_rows=outcome["excluded_rows"],
            sites=outcome["sites"],
            series=outcome["series"],
            expected_cells=outcome["expected_cells"],
            observed_cells=outcome["observed_cells"],
            missing_cells=outcome["missing_cells"],
            measured_zero_cells=outcome["measured_zero_cells"],
            coverage=Decimal(outcome["coverage"]),
            partitions=rows,
            dft_time_semantics_blocker=policy["dft_hour_timezone_blocker"],
            webtris_time_semantics_blocker=policy["webtris_blocker"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ManchesterGateDConsoleError("TEMPORAL_SOURCE_REFUSED") from error


def _source_bindings(digests: dict[str, str]) -> tuple[GateDSourceBinding, ...]:
    return (
        GateDSourceBinding(
            source_id="map_matching_worksheet",
            repository_ref=SOURCE_REFS[0],
            sha256=digests[SOURCE_REFS[0]],
            role="decision_worksheet",
            evidence_class="measured_decision_support",
            support_scope="Measured candidate-count sensitivity and policy rationale.",
            limitation=(
                "Decision support only; it does not select or scientifically validate a threshold."
            ),
        ),
        GateDSourceBinding(
            source_id="map_match_v1_measurement",
            repository_ref=SOURCE_REFS[1],
            sha256=digests[SOURCE_REFS[1]],
            role="candidate_measurement",
            evidence_class="exploratory_candidate_software_evidence",
            support_scope="Exact v1.0 policy values and 305-site candidate reconciliation.",
            limitation="Candidate generation is not analyst acceptance, calibration or a baseline.",
        ),
        GateDSourceBinding(
            source_id="map_match_v11_measurement",
            repository_ref=SOURCE_REFS[2],
            sha256=digests[SOURCE_REFS[2]],
            role="candidate_measurement",
            evidence_class="exploratory_candidate_software_evidence",
            support_scope=(
                "Exact v1.1 policy fingerprint, dispositions, transitions and override ledger."
            ),
            limitation="Owner-policy acceptance is not human, analyst or supervisor acceptance.",
        ),
        GateDSourceBinding(
            source_id="dft_temporal_profile_measurement",
            repository_ref=SOURCE_REFS[3],
            sha256=digests[SOURCE_REFS[3]],
            role="accepted_source_derived_candidate",
            evidence_class="accepted_real_snapshot_derived_candidate",
            support_scope=(
                "Real DfT snapshot lineage and complete local-clock-hour profile accounting."
            ),
            limitation=(
                "Profile completeness does not establish representativeness, calibration or "
                "realism."
            ),
        ),
        GateDSourceBinding(
            source_id="chain_restoration_receipt",
            repository_ref=SOURCE_REFS[4],
            sha256=digests[SOURCE_REFS[4]],
            role="restoration_receipt",
            evidence_class="exploratory_candidate_software_evidence",
            support_scope="Regeneration and empty-ledger review-surface reconciliation.",
            limitation=(
                "Restoration proves pipeline reproducibility, not policy correctness or review."
            ),
        ),
    )


def _screen_console(console: ManchesterGateDConsole) -> None:
    material = packet_text(console.packet)
    material += " " + " ".join(link.url for link in console.source_links)
    lowered = material.lower()
    if any(marker in lowered for marker in _PRIVATE_MARKERS):
        raise ManchesterGateDConsoleError("PRIVATE_CONTENT_REFUSED")


def load_manchester_gate_d_console(repository_root: Path) -> ManchesterGateDConsole:
    """Load five exact committed records and build one immutable Gate-D packet."""

    contents: dict[str, bytes] = {}
    digests: dict[str, str] = {}
    for relative in SOURCE_REFS:
        content, digest = _read_fixed_source(repository_root, relative)
        contents[relative] = content
        digests[relative] = digest
    v1 = _parse_json(contents[SOURCE_REFS[1]])
    v11 = _parse_json(contents[SOURCE_REFS[2]])
    temporal = _parse_json(contents[SOURCE_REFS[3]])
    restoration = _parse_json(contents[SOURCE_REFS[4]])
    mapping = _mapping_summary(v1, v11)
    packet = build_gate_d_packet(
        source_bindings=_source_bindings(digests),
        mapping_policy=mapping,
        analyst_review=_review_summary(restoration, mapping),
        temporal_profile=_temporal_summary(temporal),
    )
    labels = (
        "Map-matching decision worksheet",
        "Map-match v1 candidate measurement",
        "Map-match v1.1 reconciliation",
        "DfT temporal-profile candidate measurement",
        "Manchester chain-restoration receipt",
    )
    console = ManchesterGateDConsole(
        packet=packet,
        source_links=tuple(
            GateDSourceLink(
                label=label,
                url=f"{SOURCE_BASE}{relative}",
                sha256=digests[relative],
                role=packet.source_bindings[index].role,
            )
            for index, (relative, label) in enumerate(zip(SOURCE_REFS, labels, strict=True))
        ),
    )
    _screen_console(console)
    return console


__all__ = [
    "ManchesterGateDConsole",
    "ManchesterGateDConsoleError",
    "SOURCE_REFS",
    "load_manchester_gate_d_console",
]
