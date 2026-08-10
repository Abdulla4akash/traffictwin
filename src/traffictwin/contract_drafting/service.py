"""Service layer for Contract Drafting Assistant — consensus, recommendations, handoff.

Business logic lives outside Streamlit. Uses strict typed models,
``extra='forbid'``, deterministic canonical serialization, stable
SHA-256 fingerprinting, no path/wall-clock contamination, explicit
unavailable/refused states, bounded inputs, fail-closed checks, thin UI
rendering, JSON/CSV exports.

Reuses existing Data Contract Workbench safe readers and workspace
containment (inspect_tabular_sample).
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from traffictwin.data_contract.fingerprint import (
    fingerprint_canonical,
    redact_field_name,
    sanitise_for_csv,
)
from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.models import (
    FieldContract,
    LogicalType,
    PublicationClass,
    SourceDataContract,
    TimeBasis,
    TimezoneSemantics,
)

from .models import (
    CategoricalConsensus,
    ContractDraftingRequest,
    ContractDraftReport,
    DraftContractHandoff,
    DraftFieldRecommendation,
    DraftingConfidence,
    DraftingFinding,
    DraftingFindingSeverity,
    FieldConsensus,
    FieldPresenceSummary,
    NumericConsensus,
    SampleProfileReference,
    TimestampConsensus,
    TypeConsensus,
)

MAX_SAMPLES = 20
MIN_SAMPLES = 2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PRIVACY_KEYWORDS = frozenset(
    {
        "email",
        "name",
        "address",
        "phone",
        "ssn",
        "personal",
        "private",
        "user_id",
        "userid",
        "customer",
        "patient",
        "student",
    }
)

# ---------------------------------------------------------------------------
# Helpers — fingerprint helpers
# ---------------------------------------------------------------------------


def _canonical_payload(value: Any) -> dict[str, Any] | list[Any] | Any:  # noqa: ANN401
    """Return canonical sorted representation for fingerprint."""
    if isinstance(value, dict):
        return {k: _canonical_payload(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        # Lists of dicts with field_name should be sorted deterministically
        if value and isinstance(value[0], dict) and "field_name" in value[0]:
            sorted_list = sorted(value, key=lambda x: str(x.get("field_name", "")))
            return [_canonical_payload(v) for v in sorted_list]
        return [_canonical_payload(v) for v in value]
    return value


def _strip_order_dependent_ref(ref: dict[str, Any]) -> dict[str, Any]:
    """Remove sample_index for fingerprint (order-dependent)."""
    return {k: v for k, v in ref.items() if k != "sample_index"}


def _strip_order_dependent_consensus(fc: dict[str, Any]) -> dict[str, Any]:
    """Remove appears_in/missing_in which are index-dependent."""
    out = dict(fc)
    presence = dict(out.get("presence", {}))
    presence.pop("appears_in", None)
    presence.pop("missing_in", None)
    out["presence"] = presence
    return out


def _fingerprint_report_parts(
    request_fingerprint: str,
    sample_refs_canonical: list[dict[str, Any]],
    field_consensus_canonical: list[dict[str, Any]],
    draft_fields_canonical: list[dict[str, Any]],
    findings_canonical: list[dict[str, Any]],
    total_samples: int,
) -> str:
    # Strip order-dependent fields for determinism
    sample_refs_stripped = [_strip_order_dependent_ref(r) for r in sample_refs_canonical]
    field_consensus_stripped = [
        _strip_order_dependent_consensus(fc) for fc in field_consensus_canonical
    ]
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "request_fingerprint": request_fingerprint,
        "total_samples": total_samples,
        "sample_references": sorted(
            sample_refs_stripped, key=lambda x: str(x.get("observation_fingerprint", ""))
        ),
        "field_consensus": sorted(
            field_consensus_stripped, key=lambda x: str(x.get("field_name", ""))
        ),
        "draft_fields": sorted(draft_fields_canonical, key=lambda x: str(x.get("field_name", ""))),
        "findings": sorted(
            findings_canonical,
            key=lambda x: (str(x.get("code", "")), str(x.get("field_name") or "")),
        ),
    }
    return fingerprint_canonical(_canonical_payload(payload))


def fingerprint_drafting_request(request: ContractDraftingRequest) -> str:
    """Deterministic fingerprint for a drafting request (excludes absolute paths)."""
    # Use redacted basename + canonical sort to ensure order independence
    # and no path contamination.
    redacted_paths = sorted([Path(p).name for p in request.sample_paths])
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "sample_paths_redacted": redacted_paths,
        "max_rows": request.max_rows,
        "max_bytes": request.max_bytes,
        "source_id_hint": request.source_id_hint or "",
        "user_unit_suggestions": dict(sorted((request.user_unit_suggestions or {}).items())),
        "authoritative_contract_source_id": request.authoritative_contract_source_id or "",
    }
    return fingerprint_canonical(payload)


# ---------------------------------------------------------------------------
# Sample profiling — reuse safe readers
# ---------------------------------------------------------------------------


def _profile_one_sample(
    path: Path,
    *,
    max_rows: int,
    max_bytes: int,
    sample_index: int,
) -> tuple[SampleProfileReference, Any]:
    """Profile one sample via inspect_tabular_sample (workspace-contained).

    Returns (reference, observation).
    Raises on invalid sample (fail-closed).
    """
    # inspect_tabular_sample validates suffix + workspace containment
    obs = inspect_tabular_sample(
        path,
        max_rows=max_rows,
        max_bytes=max_bytes,
        observation_id=f"draft_obs_{sample_index:03d}",
        source_label=str(path),
    )
    ref = SampleProfileReference(
        sample_index=sample_index,
        observation_fingerprint=obs.fingerprint,
        redacted_label=obs.source_label_redacted,
        total_observed_rows=obs.total_observed_rows,
        field_count=len(obs.field_observations),
        truncated=obs.truncated,
        is_valid=True,
        error_code=None,
    )
    return ref, obs


# ---------------------------------------------------------------------------
# Consensus computation
# ---------------------------------------------------------------------------


def _compute_field_consensus(
    observations: list[Any],
    total_samples: int,
) -> list[FieldConsensus]:
    """Compute consensus per field across observations.

    Deterministic, order-independent (union sorted).
    """
    # Union of field names
    all_fields: set[str] = set()
    for obs in observations:
        for fo in obs.field_observations:
            all_fields.add(fo.field_name)
    sorted_fields = sorted(all_fields)

    consensus_list: list[FieldConsensus] = []
    for field_name in sorted_fields:
        # Presence
        present_indices: list[int] = []
        missing_indices: list[int] = []
        for idx, obs in enumerate(observations):
            names = {fo.field_name for fo in obs.field_observations}
            if field_name in names:
                present_indices.append(idx)
            else:
                missing_indices.append(idx)
        present_count = len(present_indices)
        presence = FieldPresenceSummary(
            field_name=field_name,
            present_in_samples=present_count,
            total_samples=total_samples,
            presence_frequency=present_count / total_samples if total_samples else 0.0,
            is_stable=(present_count == total_samples),
            is_optional=(present_count != total_samples),
            appears_in=sorted(present_indices),
            missing_in=sorted(missing_indices),
        )

        # Type consensus
        observed_types: list[LogicalType] = []
        type_counter: Counter[str] = Counter()
        for obs in observations:
            fm = {fo.field_name: fo for fo in obs.field_observations}
            if field_name in fm:
                lt = fm[field_name].observed_logical_type
                observed_types.append(lt)
                type_counter[lt.value] += 1
        distinct_types = sorted(set(observed_types), key=lambda x: x.value)
        is_conflicting = len(distinct_types) > 1
        # Consensus type: most frequent, deterministic tie-break by sorted value
        consensus_type: LogicalType | None = None
        if distinct_types:
            # Find max count, tie-break by sorted enum value
            max_count = max(type_counter.values())
            candidates = [k for k, v in type_counter.items() if v == max_count]
            chosen = sorted(candidates)[0]
            consensus_type = LogicalType(chosen)
        type_consensus = TypeConsensus(
            field_name=field_name,
            observed_types=distinct_types,
            type_frequencies=dict(type_counter),
            consensus_type=consensus_type,
            is_conflicting=is_conflicting,
            is_unresolved=is_conflicting,
        )

        # Nullable frequency
        nullable_in = 0
        observed_samples_for_field = 0
        for obs in observations:
            fm = {fo.field_name: fo for fo in obs.field_observations}
            if field_name in fm:
                observed_samples_for_field += 1
                if fm[field_name].nullable:
                    nullable_in += 1
        nullable_freq = (
            nullable_in / observed_samples_for_field if observed_samples_for_field else 0.0
        )

        # Timestamp consensus
        timestamp_consensus: TimestampConsensus | None = None
        # Collect parse states for samples where field present
        parse_states: list[str] = []
        state_counter: Counter[str] = Counter()
        for obs in observations:
            fm = {fo.field_name: fo for fo in obs.field_observations}
            if field_name in fm:
                state = fm[field_name].timestamp_parse_state
                if state:
                    parse_states.append(state)
                    state_counter[state] += 1
        # Determine if timestamp-relevant
        is_timestamp_field = consensus_type == LogicalType.TIMESTAMP or any(
            s != "not_timestamp" for s in parse_states
        )
        if is_timestamp_field:
            # Timezone handling: look at states
            has_tz = any(s == "parsed_with_tz" for s in parse_states)
            has_naive = any(s == "parsed_naive" for s in parse_states)
            has_ambiguous = any(s == "parse_ambiguous" for s in parse_states)
            has_failed = any(s == "parse_failed" for s in parse_states)
            is_mixed = has_tz and has_naive
            is_amb = has_ambiguous or has_failed or is_mixed
            # Observed timezones: map parse states to pseudo-timezone labels
            tz_list: list[str] = []
            if has_tz:
                tz_list.append("aware")
            if has_naive:
                tz_list.append("naive")
            if not tz_list:
                tz_list = ["unknown"]
            is_consistent = not is_amb and not is_mixed
            timestamp_consensus = TimestampConsensus(
                field_name=field_name,
                parse_states=sorted(set(parse_states)),
                parse_state_frequencies=dict(state_counter),
                observed_timezones=sorted(set(tz_list)),
                is_mixed_timezone=is_mixed,
                is_ambiguous=is_amb,
                is_consistent=is_consistent,
            )

        # Numeric consensus
        numeric_consensus: NumericConsensus | None = None
        has_numeric = any(
            t in {LogicalType.INTEGER, LogicalType.FLOAT, LogicalType.DECIMAL}
            for t in distinct_types
        ) or (consensus_type in {LogicalType.INTEGER, LogicalType.FLOAT, LogicalType.DECIMAL})
        if has_numeric:
            precisions: list[int] = []
            scales: list[int] = []
            for obs in observations:
                fm = {fo.field_name: fo for fo in obs.field_observations}
                if field_name in fm:
                    fo = fm[field_name]
                    if fo.precision is not None:
                        precisions.append(fo.precision)
                    if fo.scale is not None:
                        scales.append(fo.scale)
            if precisions or scales:
                p_min = min(precisions) if precisions else None
                p_max = max(precisions) if precisions else None
                s_min = min(scales) if scales else None
                s_max = max(scales) if scales else None
                numeric_consensus = NumericConsensus(
                    field_name=field_name,
                    has_numeric_observations=True,
                    precision_min=p_min,
                    precision_max=p_max,
                    scale_min=s_min,
                    scale_max=s_max,
                    precision_range=[p_min, p_max] if p_min is not None else None,
                    scale_range=[s_min, s_max] if s_min is not None else None,
                    is_unavailable=False,
                    observed_min=None,
                    observed_max=None,
                    is_min_max_available=False,
                )
            else:
                numeric_consensus = NumericConsensus(
                    field_name=field_name,
                    has_numeric_observations=False,
                    is_unavailable=True,
                    is_min_max_available=False,
                )
        # Else leave None

        # Categorical consensus
        categorical_consensus: CategoricalConsensus | None = None
        has_categorical = any(
            t in {LogicalType.STRING, LogicalType.CATEGORICAL, LogicalType.BOOLEAN}
            for t in distinct_types
        )
        # Also consider string fields that may have categorical evidence
        if has_categorical or distinct_types == []:
            # Collect distinct counts and hashes
            distinct_counts: list[int] = []
            hashes: list[str] = []
            has_any = False
            for obs in observations:
                fm = {fo.field_name: fo for fo in obs.field_observations}
                if field_name in fm:
                    fo = fm[field_name]
                    if fo.categorical_distinct_count is not None:
                        distinct_counts.append(fo.categorical_distinct_count)
                        has_any = True
                    if fo.categorical_aggregate_hash is not None:
                        hashes.append(fo.categorical_aggregate_hash)
                        has_any = True
            if has_any:
                d_min = min(distinct_counts) if distinct_counts else None
                d_max = max(distinct_counts) if distinct_counts else None
                is_stable = len(set(hashes)) == 1 if hashes else False
                # If hashes vary, not stable
                categorical_consensus = CategoricalConsensus(
                    field_name=field_name,
                    has_categorical_observations=True,
                    distinct_count_min=d_min,
                    distinct_count_max=d_max,
                    distinct_count_range=[d_min, d_max] if d_min is not None else None,
                    aggregate_hashes=sorted(set(hashes)),
                    is_hash_stable=is_stable,
                    is_unavailable=False,
                )
            else:
                categorical_consensus = CategoricalConsensus(
                    field_name=field_name,
                    has_categorical_observations=False,
                    is_unavailable=True,
                    aggregate_hashes=[],
                    is_hash_stable=False,
                )

        # Structural aggregate hashes: collect per-sample?
        # For this field, structural hashes are the categorical hashes (or empty)
        struct_hashes: list[str] = []
        if categorical_consensus and categorical_consensus.aggregate_hashes:
            struct_hashes = list(categorical_consensus.aggregate_hashes)
        # Also include type fingerprint? Not needed.

        # Unresolved if conflicting types or mixed timezone
        is_unresolved = (
            is_conflicting
            or (timestamp_consensus.is_ambiguous if timestamp_consensus else False)
            or (timestamp_consensus.is_mixed_timezone if timestamp_consensus else False)
        )

        fc = FieldConsensus(
            field_name=field_name,
            presence=presence,
            type_consensus=type_consensus,
            timestamp_consensus=timestamp_consensus,
            numeric_consensus=numeric_consensus,
            categorical_consensus=categorical_consensus,
            nullable_frequency=nullable_freq,
            nullable_in_samples=nullable_in,
            total_observed_samples=observed_samples_for_field,
            structural_aggregate_hashes=sorted(set(struct_hashes)),
            is_unresolved=is_unresolved,
        )
        consensus_list.append(fc)

    return consensus_list


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def _privacy_review_required(field_name: str, logical_type: LogicalType) -> bool:
    lower = field_name.lower()
    return any(kw in lower for kw in _PRIVACY_KEYWORDS)


def _build_recommendations(
    field_consensus: list[FieldConsensus],
    user_unit_suggestions: dict[str, str] | None,
    authoritative_contract: SourceDataContract | None,
) -> tuple[list[DraftFieldRecommendation], list[DraftingFinding]]:
    recommendations: list[DraftFieldRecommendation] = []
    findings: list[DraftingFinding] = []

    auth_map: dict[str, FieldContract] = {}
    if authoritative_contract:
        auth_map = {f.field_name: f for f in authoritative_contract.fields}

    for fc in field_consensus:
        field_name = fc.field_name
        presence = fc.presence
        type_cons = fc.type_consensus

        # Required vs optional: present in ALL eligible samples -> required, else optional
        recommended_required = presence.present_in_samples == presence.total_samples

        # Candidate type: consensus_type if exists, else first observed
        candidate_type = type_cons.consensus_type or LogicalType.STRING
        # Nullable: if nullable_frequency > 0 -> nullable true
        recommended_nullable = fc.nullable_frequency > 0

        # Timestamp semantics — conservative, never overstating evidence
        timestamp_contract_dict: dict[str, str | bool | None] | None = None
        if candidate_type == LogicalType.TIMESTAMP and fc.timestamp_consensus:
            tc = fc.timestamp_consensus
            # Conservative contract: requires_timezone=True ONLY if EVERY
            # relevant sample is aware and there is no naive, no ambiguity,
            # no failure, no mixed, and is_consistent.
            if tc.is_mixed_timezone or tc.is_ambiguous or not tc.is_consistent:
                time_basis = TimeBasis.UNKNOWN.value
                timezone = TimezoneSemantics.UNKNOWN.value
                requires_tz = False
            elif set(tc.parse_states) == {"parsed_with_tz"}:
                # All-aware, consistent: allowed to require timezone,
                # but do not claim UTC unless evidence genuinely establishes UTC.
                # Inspection only distinguishes aware vs naive, so use UNKNOWN.
                time_basis = TimeBasis.ISO8601.value
                timezone = TimezoneSemantics.UNKNOWN.value
                requires_tz = True
            elif set(tc.parse_states) == {"parsed_naive"}:
                time_basis = TimeBasis.ISO8601.value
                timezone = TimezoneSemantics.NAIVE_LOCAL.value
                requires_tz = False
            else:
                time_basis = TimeBasis.UNKNOWN.value
                timezone = TimezoneSemantics.UNKNOWN.value
                requires_tz = False
            timestamp_contract_dict = {
                "time_basis": time_basis,
                "timezone": timezone,
                "requires_timezone": requires_tz,
                "format_hint": None,
            }
        elif candidate_type == LogicalType.TIMESTAMP:
            timestamp_contract_dict = {
                "time_basis": TimeBasis.UNKNOWN.value,
                "timezone": TimezoneSemantics.UNKNOWN.value,
                "requires_timezone": False,
                "format_hint": None,
            }

        # Numeric precision/scale
        numeric_precision: int | None = None
        numeric_scale: int | None = None
        if fc.numeric_consensus and not fc.numeric_consensus.is_unavailable:
            # Recommend max observed to accommodate all samples
            numeric_precision = fc.numeric_consensus.precision_max
            numeric_scale = fc.numeric_consensus.scale_max

        # Unit: must remain unknown unless user suggestion or authoritative contract
        unit_val = "unknown"
        if field_name in auth_map and auth_map[field_name].unit is not None:
            # Copy authoritative unit's unit string
            unit_val = auth_map[field_name].unit.unit  # type: ignore[union-attr]
        elif user_unit_suggestions and field_name in user_unit_suggestions:
            unit_val = user_unit_suggestions[field_name]

        privacy_required = _privacy_review_required(field_name, candidate_type)

        # Confidence per field
        confidence = DraftingConfidence.HIGH
        rationale_parts: list[str] = []
        if type_cons.is_conflicting:
            confidence = DraftingConfidence.CONFLICTED
            rationale_parts.append(
                f"conflicting types observed: {sorted(type_cons.type_frequencies.keys())}"
            )
            findings.append(
                DraftingFinding(
                    code="TYPE_CONFLICT",
                    field_name=field_name,
                    severity=DraftingFindingSeverity.WARNING,
                    message=(  # noqa: E501
                        f"Field {field_name!r} has conflicting logical types: "
                        f"{sorted(type_cons.type_frequencies.keys())}"
                    ),
                    details={"observed_types": str(sorted(type_cons.type_frequencies.keys()))},
                )
            )
        if fc.timestamp_consensus and fc.timestamp_consensus.is_mixed_timezone:
            confidence = DraftingConfidence.CONFLICTED
            findings.append(
                DraftingFinding(
                    code="MIXED_TIMEZONE",
                    field_name=field_name,
                    severity=DraftingFindingSeverity.WARNING,
                    message=f"Field {field_name!r} has mixed timezone semantics (aware and naive)",
                    details={"parse_states": str(fc.timestamp_consensus.parse_states)},
                )
            )
            rationale_parts.append("mixed timezone semantics")
        elif fc.timestamp_consensus and fc.timestamp_consensus.is_ambiguous:
            if confidence != DraftingConfidence.CONFLICTED:
                confidence = DraftingConfidence.LOW
            findings.append(
                DraftingFinding(
                    code="TIMESTAMP_AMBIGUOUS",
                    field_name=field_name,
                    severity=DraftingFindingSeverity.WARNING,
                    message=f"Field {field_name!r} has ambiguous timestamp parse states",
                    details={"parse_states": str(fc.timestamp_consensus.parse_states)},
                )
            )
            rationale_parts.append("ambiguous timestamp parse")
        if presence.is_optional:
            # Optional field is expected, not a conflict unless we need to flag
            if confidence == DraftingConfidence.HIGH:
                confidence = DraftingConfidence.MEDIUM
            findings.append(
                DraftingFinding(
                    code="FIELD_INTERMITTENT",
                    field_name=field_name,
                    severity=DraftingFindingSeverity.INFO,
                    message=(
                        f"Field {field_name!r} appears in "
                        f"{presence.present_in_samples}/{presence.total_samples} "
                        "samples; recommended optional"
                    ),
                    details={
                        "present_in_samples": presence.present_in_samples,
                        "total_samples": presence.total_samples,
                    },
                )
            )
            rationale_parts.append(
                f"present in {presence.present_in_samples}/{presence.total_samples} samples"
            )
        else:
            rationale_parts.append(f"present in all {presence.total_samples} samples")

        # Nullability disagreement
        if 0 < fc.nullable_frequency < 1.0:
            findings.append(
                DraftingFinding(
                    code="NULLABILITY_DISAGREEMENT",
                    field_name=field_name,
                    severity=DraftingFindingSeverity.INFO,
                    message=(
                        f"Field {field_name!r} nullable in "
                        f"{fc.nullable_in_samples}/{fc.total_observed_samples} samples"
                    ),
                    details={
                        "nullable_in_samples": fc.nullable_in_samples,
                        "total_observed_samples": fc.total_observed_samples,
                    },
                )
            )
            if confidence == DraftingConfidence.HIGH:
                confidence = DraftingConfidence.MEDIUM
            rationale_parts.append(
                f"nullable in {fc.nullable_in_samples}/{fc.total_observed_samples} samples"
            )
        elif fc.nullable_frequency == 0:
            rationale_parts.append("no nulls observed")
        else:
            rationale_parts.append("nullable in all observed samples")

        if numeric_precision is not None:
            rationale_parts.append(f"precision {numeric_precision}, scale {numeric_scale}")
        if privacy_required:
            rationale_parts.append("privacy review required due to field name")
            findings.append(
                DraftingFinding(
                    code="PRIVACY_REVIEW_REQUIRED",
                    field_name=field_name,
                    severity=DraftingFindingSeverity.INFO,
                    message=(
                        f"Field {field_name!r} may contain personal data; "
                        "manual privacy review required"
                    ),
                    details=None,
                )
            )

        rationale = "; ".join(rationale_parts) if rationale_parts else "stable field"

        rec = DraftFieldRecommendation(
            field_name=field_name,
            recommended_required=recommended_required,
            candidate_logical_type=candidate_type,
            recommended_nullable=recommended_nullable,
            timestamp_semantics=fc.timestamp_consensus,
            timestamp_contract=timestamp_contract_dict,
            numeric_precision=numeric_precision,
            numeric_scale=numeric_scale,
            unit=unit_val,
            privacy_review_required=privacy_required,
            confidence=confidence,
            rationale=rationale,
        )
        recommendations.append(rec)

    # Sort recommendations deterministically
    recommendations = sorted(recommendations, key=lambda x: x.field_name)
    findings = sorted(findings, key=lambda x: (x.code, x.field_name or ""))
    return recommendations, findings


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------


def build_draft_report(
    sample_paths: list[Path],
    *,
    max_rows: int = 5000,
    max_bytes: int = 5_000_000,
    source_id_hint: str | None = None,
    user_unit_suggestions: dict[str, str] | None = None,
    authoritative_contract: SourceDataContract | None = None,
) -> ContractDraftReport:
    """Profile 2-20 samples and produce a reviewable draft report.

    Reuses ``inspect_tabular_sample`` for bounded, workspace-contained reading.
    Deterministic, order-independent fingerprint.

    Raises:
        ValueError: if sample count not in 2-20 or limits invalid
        TabularReadError: if any sample is invalid (fail-closed)
    """
    if not (MIN_SAMPLES <= len(sample_paths) <= MAX_SAMPLES):
        raise ValueError(f"sample_paths must contain 2-20 entries, got {len(sample_paths)}")
    if max_rows < 1 or max_bytes < 1:
        raise ValueError("max_rows and max_bytes must be positive")
    if len(sample_paths) != len({str(p) for p in sample_paths}):
        raise ValueError("sample_paths must be unique")

    # Profile each sample in given order but fingerprint will be order-independent
    observations: list[Any] = []
    sample_refs: list[SampleProfileReference] = []
    for idx, path in enumerate(sample_paths):
        # This will raise TabularReadError or ValueError on invalid sample (fail-closed)
        ref, obs = _profile_one_sample(
            path, max_rows=max_rows, max_bytes=max_bytes, sample_index=idx
        )
        observations.append(obs)
        sample_refs.append(ref)

    total_samples = len(observations)

    # Compute consensus (order-independent via sorted field union)
    field_consensus = _compute_field_consensus(observations, total_samples)

    # Build recommendations
    draft_fields, findings = _build_recommendations(
        field_consensus, user_unit_suggestions, authoritative_contract
    )

    # Overall confidence: if any conflicted -> conflicted, else low/medium/high
    overall = DraftingConfidence.HIGH
    if any(f.confidence == DraftingConfidence.CONFLICTED for f in draft_fields):
        overall = DraftingConfidence.CONFLICTED
    elif any(f.confidence == DraftingConfidence.LOW for f in draft_fields):
        overall = DraftingConfidence.LOW
    elif any(f.confidence == DraftingConfidence.MEDIUM for f in draft_fields):
        overall = DraftingConfidence.MEDIUM

    # Add field appearing/disappearing findings summary
    for fc in field_consensus:
        if fc.is_unresolved and not any(
            fl.field_name == fc.field_name and fl.code in {"TYPE_CONFLICT", "MIXED_TIMEZONE"}
            for fl in findings
        ):
            # Generic unresolved
            if fc.type_consensus.is_conflicting or fc.presence.is_optional:
                continue  # already handled
            findings.append(
                DraftingFinding(
                    code="FIELD_UNRESOLVED",
                    field_name=fc.field_name,
                    severity=DraftingFindingSeverity.INFO,
                    message=f"Field {fc.field_name!r} has unresolved disagreement",
                    details=None,
                )
            )

    # Deterministic fingerprinting
    # Request fingerprint: order-independent via sorted redacted basenames
    # For service-level we compute request fingerprint from dedicated helper
    # Build a synthetic request for fingerprint
    synth_request = ContractDraftingRequest(
        sample_paths=[str(p) for p in sample_paths],
        max_rows=max_rows,
        max_bytes=max_bytes,
        source_id_hint=source_id_hint,
        user_unit_suggestions=user_unit_suggestions,
        authoritative_contract_source_id=(
            authoritative_contract.source_id if authoritative_contract else None
        ),
    )
    request_fp = fingerprint_drafting_request(synth_request)

    # For report fingerprint, use canonical sorted payloads
    # Sort sample refs by fingerprint for determinism
    sample_refs_canonical = [r.model_dump(mode="json") for r in sample_refs]
    field_consensus_canonical = [fc.model_dump(mode="json") for fc in field_consensus]
    draft_fields_canonical = [df.model_dump(mode="json") for df in draft_fields]
    findings_canonical = [f.model_dump(mode="json") for f in findings]

    # Sort canonical lists for fingerprint to ensure sample-order independence
    sample_refs_canonical_sorted = sorted(
        sample_refs_canonical, key=lambda x: str(x.get("observation_fingerprint", ""))
    )
    field_consensus_canonical_sorted = sorted(
        field_consensus_canonical, key=lambda x: str(x.get("field_name", ""))
    )
    draft_fields_canonical_sorted = sorted(
        draft_fields_canonical, key=lambda x: str(x.get("field_name", ""))
    )
    findings_canonical_sorted = sorted(
        findings_canonical, key=lambda x: (str(x.get("code", "")), str(x.get("field_name") or ""))
    )

    # Compute fingerprint via helper with sorted
    # Use the sorted canonical for deterministic hash
    report_fp = _fingerprint_report_parts(
        request_fp,
        sample_refs_canonical_sorted,
        field_consensus_canonical_sorted,
        draft_fields_canonical_sorted,
        findings_canonical_sorted,
        total_samples,
    )
    # Structural hash: hash of all aggregate hashes sorted
    all_hashes: list[str] = []
    for fc in field_consensus:
        all_hashes.extend(fc.structural_aggregate_hashes)
    structural_hash = (
        fingerprint_canonical(sorted(all_hashes)) if all_hashes else fingerprint_canonical([])
    )

    # Order sample_refs deterministically by fingerprint for portable output?
    # Keep original order for display? But to ensure determinism we sort.
    # Choose to sort by fingerprint for portability; display will still be sorted.
    sample_refs_sorted = sorted(sample_refs, key=lambda x: x.observation_fingerprint)
    field_consensus_sorted = sorted(field_consensus, key=lambda x: x.field_name)
    draft_fields_sorted = sorted(draft_fields, key=lambda x: x.field_name)
    findings_sorted = sorted(findings, key=lambda x: (x.code, x.field_name or ""))

    report = ContractDraftReport(
        request_fingerprint=request_fp,
        sample_references=sample_refs_sorted,
        field_consensus=field_consensus_sorted,
        draft_fields=draft_fields_sorted,
        findings=findings_sorted,
        overall_confidence=overall,
        fingerprint=report_fp,
        draft_only=True,
        freeze_executed=False,
        human_review_required=True,
        total_samples=total_samples,
        structural_hash=structural_hash,
    )
    return report


def build_draft_report_from_request(
    request: ContractDraftingRequest,
    *,
    authoritative_contract: SourceDataContract | None = None,
) -> ContractDraftReport:
    """Build report from a ContractDraftingRequest model."""
    paths = [Path(p) for p in request.sample_paths]
    return build_draft_report(
        paths,
        max_rows=request.max_rows,
        max_bytes=request.max_bytes,
        source_id_hint=request.source_id_hint,
        user_unit_suggestions=request.user_unit_suggestions,
        authoritative_contract=authoritative_contract,
    )


def prepare_handoff(
    report: ContractDraftReport,
    *,
    source_id: str | None = None,
    contract_version: str = "1.0.0",
    notes: str | None = None,
) -> DraftContractHandoff:
    """Export a draft compatible with SourceDataContract editing.

    The handoff must state draft_only=True, freeze_executed=False,
    human_review_required=True and must NOT call freeze service.

    Creates a SourceDataContract dict from the draft fields for editing in
    Data Contract Workbench.
    """
    # Build fields for SourceDataContract
    fields: list[dict[str, Any]] = []
    for df in report.draft_fields:
        # Map candidate logical type to FieldContract representation
        # Need timestamp contract if timestamp type
        ts: dict[str, Any] | None = None
        if df.candidate_logical_type == LogicalType.TIMESTAMP:
            # Use timestamp_contract dict to build TimestampContract model-like dict
            tc = df.timestamp_contract or {}
            # Normalize to expected fields
            ts = {
                "time_basis": tc.get("time_basis", TimeBasis.UNKNOWN.value),
                "timezone": tc.get("timezone", TimezoneSemantics.UNKNOWN.value),
                "requires_timezone": bool(tc.get("requires_timezone", False)),
                "format_hint": tc.get("format_hint"),
            }
            # Filter None format_hint? Keep as is.
            if ts.get("format_hint") is None:
                ts.pop("format_hint", None)

        unit: dict[str, Any] | None = None
        if df.unit != "unknown":
            # user supplied or authoritative
            unit = {"unit": df.unit, "dimension": None}

        field_dict: dict[str, Any] = {
            "field_name": df.field_name,
            "required": df.recommended_required,
            "logical_type": df.candidate_logical_type.value,
        }
        if unit:
            field_dict["unit"] = unit
        if ts:
            field_dict["timestamp"] = ts
        # description optional; add rationale as description prefix? Keep None for now
        fields.append(field_dict)

    # Validate fields produce valid SourceDataContract? Use source_id hint or default
    effective_source_id = source_id or "draft_source"
    if report.sample_references and not source_id:
        # Try to hint? Use unknown
        effective_source_id = "draft_source"

    # Ensure source_id valid per pattern
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.\-:]{0,127}", effective_source_id):
        effective_source_id = "draft_source"

    contract_dict: dict[str, Any] = {
        "schema_version": "1.0",
        "source_id": effective_source_id,
        "contract_version": contract_version,
        "fields": sorted(fields, key=lambda x: str(x["field_name"])),
        "rights": {
            "publication_class": PublicationClass.PRIVATE.value,
            "contains_personal_data": any(df.privacy_review_required for df in report.draft_fields),
            "retention_days": None,
            "legal_basis": None,
        },
        "notes": notes
        or "Draft generated by Contract Drafting Assistant; requires human review before freeze.",
    }

    # Validate via model (fail-closed if invalid)
    # This ensures compatibility with SourceDataContract editing
    try:
        _validated = SourceDataContract.model_validate(contract_dict)
    except ValidationError as exc:
        raise ValueError(f"draft contract validation failed: {exc}") from exc
    # Use dumped version to ensure sorted fields and correct serialization
    contract_canonical = _validated.model_dump(mode="json")
    contract_canonical["fields"] = sorted(
        contract_canonical["fields"], key=lambda x: str(x["field_name"])
    )

    # Deterministic handoff fingerprint: canonical JSON of payload without fingerprint
    payload_for_fp: dict[str, Any] = {
        "schema_version": "1.0",
        "report_fingerprint": report.fingerprint,
        "draft_contract": contract_canonical,
        "draft_only": True,
        "freeze_executed": False,
        "human_review_required": True,
        "created_from_samples": report.total_samples,
    }
    fingerprint = fingerprint_canonical(_canonical_payload(payload_for_fp))
    handoff_id = f"handoff_{fingerprint[:12]}"
    handoff = DraftContractHandoff(
        handoff_id=handoff_id,
        report_fingerprint=report.fingerprint,
        draft_contract=contract_canonical,
        draft_only=True,
        freeze_executed=False,
        human_review_required=True,
        fingerprint=fingerprint,
        created_from_samples=report.total_samples,
        notes=notes,
    )
    return handoff


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def export_report_json(report: ContractDraftReport) -> str:
    """Deterministic JSON export for report (no raw values)."""
    data = report.model_dump(mode="json")
    # Ensure sorted keys for determinism
    data["field_consensus"] = sorted(data["field_consensus"], key=lambda x: str(x["field_name"]))
    data["draft_fields"] = sorted(data["draft_fields"], key=lambda x: str(x["field_name"]))
    data["sample_references"] = sorted(
        data["sample_references"], key=lambda x: str(x["observation_fingerprint"])
    )
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2)


def export_report_csv(report: ContractDraftReport) -> str:
    """CSV export for tabular consensus (deterministic, redacted, no raw values)."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(
        [
            "field_name",
            "present_in_samples",
            "total_samples",
            "presence_frequency",
            "consensus_type",
            "is_conflicting",
            "nullable_frequency",
            "is_mixed_timezone",
            "precision_range",
            "scale_range",
            "distinct_count_range",
            "is_hash_stable",
            "recommended_required",
            "recommended_nullable",
            "unit",
            "confidence",
        ]
    )
    for fc in sorted(report.field_consensus, key=lambda x: x.field_name):
        # Find recommendation
        rec = next((r for r in report.draft_fields if r.field_name == fc.field_name), None)
        prec_range = ""
        scale_range = ""
        if fc.numeric_consensus and fc.numeric_consensus.precision_range:
            prec_range = (
                f"{fc.numeric_consensus.precision_min}-{fc.numeric_consensus.precision_max}"
            )
        if fc.numeric_consensus and fc.numeric_consensus.scale_range:
            scale_range = f"{fc.numeric_consensus.scale_min}-{fc.numeric_consensus.scale_max}"
        d_range = ""
        if fc.categorical_consensus and fc.categorical_consensus.distinct_count_range:
            d_range = (  # noqa: E501
                f"{fc.categorical_consensus.distinct_count_min}-"
                f"{fc.categorical_consensus.distinct_count_max}"
            )
        is_mixed = ""
        if fc.timestamp_consensus:
            is_mixed = str(fc.timestamp_consensus.is_mixed_timezone)
        # Apply formula-injection protection and field-name redaction
        field_name_safe = sanitise_for_csv(redact_field_name(fc.field_name))
        consensus_type_safe = sanitise_for_csv(
            fc.type_consensus.consensus_type.value if fc.type_consensus.consensus_type else ""
        )
        is_mixed_safe = sanitise_for_csv(is_mixed)
        prec_range_safe = sanitise_for_csv(prec_range)
        scale_range_safe = sanitise_for_csv(scale_range)
        d_range_safe = sanitise_for_csv(d_range)
        unit_safe = sanitise_for_csv(rec.unit if rec else "unknown")
        confidence_safe = sanitise_for_csv(rec.confidence.value if rec else "")
        hash_stable_safe = sanitise_for_csv(
            str(fc.categorical_consensus.is_hash_stable) if fc.categorical_consensus else ""
        )
        writer.writerow(
            [
                field_name_safe,
                str(fc.presence.present_in_samples),
                str(fc.presence.total_samples),
                f"{fc.presence.presence_frequency:.3f}",
                consensus_type_safe,
                str(fc.type_consensus.is_conflicting),
                f"{fc.nullable_frequency:.3f}",
                is_mixed_safe,
                prec_range_safe,
                scale_range_safe,
                d_range_safe,
                hash_stable_safe,
                str(rec.recommended_required) if rec else "",
                str(rec.recommended_nullable) if rec else "",
                unit_safe,
                confidence_safe,
            ]
        )
    return output.getvalue()


def export_handoff_json(handoff: DraftContractHandoff) -> str:
    """Deterministic JSON export for handoff."""
    data = handoff.model_dump(mode="json")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2)


def draft_report_to_canonical_dict(report: ContractDraftReport) -> dict[str, Any]:
    """Return canonical dict for fingerprint verification (sorted)."""
    data = report.model_dump(mode="json")
    data["field_consensus"] = sorted(data["field_consensus"], key=lambda x: str(x["field_name"]))
    data["draft_fields"] = sorted(data["draft_fields"], key=lambda x: str(x["field_name"]))
    data["sample_references"] = sorted(
        data["sample_references"], key=lambda x: str(x["observation_fingerprint"])
    )
    data["findings"] = sorted(
        data["findings"], key=lambda x: (str(x["code"]), str(x.get("field_name") or ""))
    )
    return dict(sorted(data.items()))


def handoff_to_canonical_dict(handoff: DraftContractHandoff) -> dict[str, Any]:
    """Return canonical dict for handoff."""
    data = handoff.model_dump(mode="json")
    return dict(sorted(data.items()))


def verify_report_fingerprint(report: ContractDraftReport) -> None:
    """Verify report fingerprint matches recomputed canonical value."""
    # Recompute via same logic as build
    # Use stored fields to recompute fingerprint
    # Need to handle sample order independence: sort as in build
    sample_refs_canonical = [r.model_dump(mode="json") for r in report.sample_references]
    field_consensus_canonical = [fc.model_dump(mode="json") for fc in report.field_consensus]
    draft_fields_canonical = [df.model_dump(mode="json") for df in report.draft_fields]
    findings_canonical = [f.model_dump(mode="json") for f in report.findings]
    expected = _fingerprint_report_parts(
        report.request_fingerprint,
        sorted(sample_refs_canonical, key=lambda x: str(x.get("observation_fingerprint", ""))),
        sorted(field_consensus_canonical, key=lambda x: str(x.get("field_name", ""))),
        sorted(draft_fields_canonical, key=lambda x: str(x.get("field_name", ""))),
        sorted(
            findings_canonical,
            key=lambda x: (str(x.get("code", "")), str(x.get("field_name") or "")),
        ),
        report.total_samples,
    )
    if expected != report.fingerprint:
        raise ValueError(
            f"report fingerprint mismatch: expected {expected}, got {report.fingerprint}"
        )


def verify_handoff_fingerprint(handoff: DraftContractHandoff) -> None:
    """Verify handoff fingerprint."""
    payload_for_fp: dict[str, Any] = {
        "schema_version": "1.0",
        "report_fingerprint": handoff.report_fingerprint,
        "draft_contract": handoff.draft_contract,
        "draft_only": True,
        "freeze_executed": False,
        "human_review_required": True,
        "created_from_samples": handoff.created_from_samples,
    }
    expected = fingerprint_canonical(_canonical_payload(payload_for_fp))
    if expected != handoff.fingerprint:
        raise ValueError(
            f"handoff fingerprint mismatch: expected {expected}, got {handoff.fingerprint}"
        )
