# ruff: noqa: E501
"""Adapters turning existing V3 artifacts into generic workspace references.

Adapters return ``WorkspaceArtifactRef`` records without copying payloads
or silently modifying them. They handle only interfaces present on main.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from traffictwin.study_workspace.models import (
    WorkspaceArtifactKind,
    WorkspaceArtifactRef,
    WorkspaceArtifactStanding,
    WorkspaceAvailabilityState,
    WorkspaceCompatibilityStanding,
)


def _hex64_of_canonical(value: object) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _safe_label(value: str, fallback: str) -> str:
    s = value.strip()
    if not s:
        return fallback
    # Redact absolute path fragments if ever present (adapters should not be given local paths).
    return s


# ---------------------------------------------------------------------------
# StudyPlan adapter
# ---------------------------------------------------------------------------


def study_plan_to_ref(plan: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    """Adapt a preregistration ``StudyPlan`` to a workspace reference."""
    # Import lazily to avoid hard dependency if plan schema evolves.
    try:
        fingerprint = getattr(plan, "fingerprint", None)
        if fingerprint is None:
            # Try compute method if available
            compute = getattr(plan, "compute_fingerprint", None)
            if callable(compute):
                fingerprint = compute()
            else:
                fingerprint = getattr(plan, "plan_id", "unknown")
                # Derive deterministic fingerprint from plan_id if no real fingerprint
                fingerprint = hashlib.sha256(str(fingerprint).encode()).hexdigest()
        else:
            # If fingerprint is set but empty, compute
            if not isinstance(fingerprint, str) or len(fingerprint) != 64:
                fingerprint = hashlib.sha256(str(fingerprint).encode()).hexdigest()

        schema_version = getattr(plan, "schema_version", "1.0")
        # Evidence mode and status drive standing and availability
        status = getattr(plan, "status", None)
        status_str = str(status).lower() if status is not None else "draft"

        if "frozen" in status_str or "evidence_attached" in status_str or "decided" in status_str:
            availability = WorkspaceAvailabilityState.AVAILABLE
        elif "draft" in status_str:
            availability = WorkspaceAvailabilityState.PENDING_REVIEW
        else:
            availability = WorkspaceAvailabilityState.AVAILABLE

        # Standing: authored configuration for plans (they are governance)
        standing = WorkspaceArtifactStanding.AUTHORED_CONFIGURATION

        # Compatibility: assume compatible if schema is 1.0
        compat = (
            WorkspaceCompatibilityStanding.COMPATIBLE
            if str(schema_version) == "1.0"
            else WorkspaceCompatibilityStanding.UNKNOWN
        )

        plan_id = getattr(plan, "plan_id", "plan")
        label = _safe_label(str(plan_id), "preregistration-plan")

        parent_fp = getattr(plan, "parent_fingerprint", None)
        if isinstance(parent_fp, str):
            parent_fp = parent_fp.lower()
            if len(parent_fp) != 64 or not parent_fp.isalnum():
                parent_fp = None
        else:
            parent_fp = None

        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.PREREGISTRATION_PLAN,
            fingerprint=str(fingerprint).lower(),
            schema_version=str(schema_version),
            label=label,
            standing=standing,
            compatibility_standing=compat,
            parent_fingerprint=parent_fp,
            availability=availability,
            reason=None
            if availability is WorkspaceAvailabilityState.AVAILABLE
            else "plan is in draft/pending review",
        )
    except Exception as exc:  # pragma: no cover - fail-closed adapter
        raise ValueError(f"study_plan adapter failed: {exc}") from exc


# ---------------------------------------------------------------------------
# SourceContractVersion adapter
# ---------------------------------------------------------------------------


def source_contract_to_ref(version: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    """Adapt a ``SourceContractVersion`` to a workspace reference."""
    try:
        fingerprint = getattr(version, "fingerprint", None)
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("SourceContractVersion requires fingerprint")

        schema_version = getattr(version, "schema_version", "1.0")
        contract = getattr(version, "contract", None)
        source_id = "source-contract"
        if contract is not None:
            source_id = getattr(contract, "source_id", source_id)

        standing = WorkspaceArtifactStanding.AUTHORED_CONFIGURATION

        fingerprint_val = str(fingerprint).lower()
        parent_fp = getattr(version, "parent_fingerprint", None)
        if isinstance(parent_fp, str):
            parent_fp = parent_fp.lower()
            if len(parent_fp) != 64:
                parent_fp = None
        else:
            parent_fp = None

        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.SOURCE_CONTRACT_VERSION,
            fingerprint=fingerprint_val,
            schema_version=str(schema_version),
            label=_safe_label(str(source_id), "source-contract"),
            standing=standing,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            parent_fingerprint=parent_fp,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception as exc:
        raise ValueError(f"source_contract adapter failed: {exc}") from exc


def source_data_contract_to_ref(contract: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    """Adapt a ``SourceDataContract`` (unversioned) to a workspace reference."""
    try:
        # Derive fingerprint deterministically from contract content
        from traffictwin.data_contract.fingerprint import fingerprint_contract

        fp = fingerprint_contract(contract)
        schema_version = getattr(contract, "schema_version", "1.0")
        source_id = getattr(contract, "source_id", "source-contract")
        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.SOURCE_CONTRACT,
            fingerprint=str(fp).lower(),
            schema_version=str(schema_version),
            label=_safe_label(str(source_id), "source-contract"),
            standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception:
        # Fallback: hash the JSON dump
        try:
            dump = (
                contract.model_dump(mode="json")
                if hasattr(contract, "model_dump")
                else str(contract)
            )
            fp = _hex64_of_canonical(dump)
            schema_version = getattr(contract, "schema_version", "1.0")
            source_id = getattr(contract, "source_id", "source-contract")
            return WorkspaceArtifactRef(
                kind=WorkspaceArtifactKind.SOURCE_CONTRACT,
                fingerprint=fp,
                schema_version=str(schema_version),
                label=_safe_label(str(source_id), "source-contract"),
                standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
                compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
                availability=WorkspaceAvailabilityState.AVAILABLE,
            )
        except Exception as exc:
            raise ValueError(f"source_data_contract adapter failed: {exc}") from exc


# ---------------------------------------------------------------------------
# EventAlignedReport adapter
# ---------------------------------------------------------------------------


def event_aligned_report_to_ref(report: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    """Adapt an ``EventAlignedReport`` to a workspace reference."""
    try:
        fingerprint = getattr(report, "fingerprint", None)
        if isinstance(fingerprint, str) and len(fingerprint) == 64:
            fp = fingerprint.lower()
        else:
            # Use computed fingerprint if available
            computed = getattr(report, "computed_fingerprint", None)
            if callable(computed):
                fp = str(computed()).lower()
            elif hasattr(report, "canonical_json"):
                fp = hashlib.sha256(report.canonical_json().encode()).hexdigest()
            else:
                dump = (
                    report.model_dump(mode="json") if hasattr(report, "model_dump") else str(report)
                )
                fp = _hex64_of_canonical(dump)

        schema_version = getattr(report, "schema_version", "1.0")
        report_id = getattr(report, "report_id", "event-aligned-report")

        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.EVENT_ALIGNED_REPORT,
            fingerprint=fp,
            schema_version=str(schema_version),
            label=_safe_label(str(report_id), "event-aligned-report"),
            standing=WorkspaceArtifactStanding.SYNTHETIC_EVIDENCE,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception as exc:
        raise ValueError(f"event_aligned_report adapter failed: {exc}") from exc


# ---------------------------------------------------------------------------
# ResourceStrategyReport adapter
# ---------------------------------------------------------------------------


def resource_strategy_report_to_ref(report: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    """Adapt a ``ResourceStrategyReport`` to a workspace reference."""
    try:
        # ResourceStrategyReport has report_fingerprint and study_fingerprint
        fp = getattr(report, "report_fingerprint", None)
        if not isinstance(fp, str) or len(fp) != 64:
            # Fallback to generic fingerprint
            maybe = getattr(report, "fingerprint", None)
            if isinstance(maybe, str) and len(maybe) == 64:
                fp = maybe
            else:
                dump = (
                    report.model_dump(mode="json") if hasattr(report, "model_dump") else str(report)
                )
                fp = _hex64_of_canonical(dump)
        fp = str(fp).lower()

        # Schema or report version binding
        schema_version = getattr(report, "schema_version", None) or getattr(
            report, "report_version", "1.0"
        )
        # Study id
        study_id = getattr(report, "study_id", "resource-strategy-study")

        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.RESOURCE_STRATEGY_REPORT,
            fingerprint=fp,
            schema_version=str(schema_version),
            label=_safe_label(str(study_id), "resource-strategy-report"),
            standing=WorkspaceArtifactStanding.SYNTHETIC_EVIDENCE,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception as exc:
        raise ValueError(f"resource_strategy adapter failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Study Capsule adapter
# ---------------------------------------------------------------------------


def study_capsule_manifest_to_ref(manifest: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    """Adapt a ``StudyCapsuleManifest`` to a workspace reference."""
    try:
        fp = getattr(manifest, "manifest_fingerprint", None)
        if not isinstance(fp, str) or len(fp) != 64:
            # Try fingerprint method
            meth = getattr(manifest, "fingerprint", None)
            if callable(meth):
                fp = meth()
            else:
                dump = (
                    manifest.model_dump(mode="json")
                    if hasattr(manifest, "model_dump")
                    else str(manifest)
                )
                fp = _hex64_of_canonical(dump)
        fp = str(fp).lower()

        schema_version = getattr(manifest, "schema_version", "1.0")
        capsule_title = getattr(manifest, "capsule_title", "study-capsule")

        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.STUDY_CAPSULE_MANIFEST,
            fingerprint=fp,
            schema_version=str(schema_version),
            label=_safe_label(str(capsule_title), "study-capsule"),
            standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception as exc:
        raise ValueError(f"study_capsule adapter failed: {exc}") from exc


def study_capsule_receipt_to_ref(receipt: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    """Adapt a ``StudyCapsuleReceipt`` to a workspace reference."""
    try:
        fp = getattr(receipt, "manifest_fingerprint", None)
        if not isinstance(fp, str) or len(fp) != 64:
            dump = (
                receipt.model_dump(mode="json") if hasattr(receipt, "model_dump") else str(receipt)
            )
            fp = _hex64_of_canonical(dump)
        fp = str(fp).lower()

        capsule_id = getattr(receipt, "capsule_id", "study-capsule-receipt")

        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.STUDY_CAPSULE_RECEIPT,
            fingerprint=fp,
            schema_version="1.0",
            label=_safe_label(str(capsule_id), "study-capsule-receipt"),
            standing=WorkspaceArtifactStanding.AUTHORED_CONFIGURATION,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception as exc:
        raise ValueError(f"study_capsule_receipt adapter failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Generic / provenance adapters
# ---------------------------------------------------------------------------


def generic_report_to_ref(
    report: Any,  # noqa: ANN401
    *,
    kind: WorkspaceArtifactKind = WorkspaceArtifactKind.GENERIC_REPORT,
    label: str = "generic-report",
) -> WorkspaceArtifactRef:
    """Adapt any model with a fingerprint or dump to a generic reference."""
    try:
        fp = getattr(report, "fingerprint", None)
        if isinstance(fp, str) and len(fp) == 64:
            fp_val = fp.lower()
        else:
            # Try computed
            comp = getattr(report, "computed_fingerprint", None)
            if callable(comp):
                fp_val = str(comp()).lower()
            elif hasattr(report, "model_dump"):
                dump = report.model_dump(mode="json")
                fp_val = _hex64_of_canonical(dump)
            else:
                fp_val = hashlib.sha256(str(report).encode()).hexdigest()

        schema_version = getattr(report, "schema_version", "1.0")
        report_label = getattr(report, "report_id", getattr(report, "trace_id", label))

        return WorkspaceArtifactRef(
            kind=kind,
            fingerprint=fp_val,
            schema_version=str(schema_version),
            label=_safe_label(str(report_label), label),
            standing=WorkspaceArtifactStanding.SYNTHETIC_EVIDENCE,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception as exc:
        raise ValueError(f"generic_report adapter failed: {exc}") from exc


def provenance_trace_to_ref(trace: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    return generic_report_to_ref(
        trace, kind=WorkspaceArtifactKind.PROVENANCE_TRACE, label="provenance-trace"
    )
