"""Adapters turning existing V3 artifacts into generic workspace references.

Adapters return ``WorkspaceArtifactRef`` records without copying payloads
or silently modifying them.
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
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _safe_label(value: str, fallback: str) -> str:
    s = value.strip()
    if not s:
        return fallback
    return s


# ---------------------------------------------------------------------------
# StudyPlan adapter
# ---------------------------------------------------------------------------


def study_plan_to_ref(plan: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    """Adapt a preregistration ``StudyPlan`` to a workspace reference."""
    try:
        fingerprint = getattr(plan, "fingerprint", None)
        if (
            isinstance(fingerprint, str)
            and len(fingerprint) == 64
            and all(c in "0123456789abcdef" for c in fingerprint.lower())
        ):
            fp = fingerprint.lower()
        else:
            fp = None
            compute = getattr(plan, "compute_fingerprint", None)
            if callable(compute):
                try:
                    candidate = compute()
                    if isinstance(candidate, str) and len(candidate) == 64:
                        fp = candidate.lower()
                except Exception:
                    fp = None
            if fp is None:
                canonical = None
                if hasattr(plan, "canonical_payload") and callable(plan.canonical_payload):
                    try:
                        payload = plan.canonical_payload()
                        canonical = _hex64_of_canonical(payload)
                    except Exception:
                        canonical = None
                if (
                    canonical is None
                    and hasattr(plan, "canonical_json")
                    and callable(plan.canonical_json)
                ):
                    try:
                        j = plan.canonical_json()
                        if isinstance(j, str):
                            fp = hashlib.sha256(j.encode("utf-8")).hexdigest()
                        else:
                            canonical = None
                    except Exception:
                        canonical = None
                if fp is None and canonical is not None:
                    fp = canonical
            if fp is None and hasattr(plan, "model_dump"):
                try:
                    dump = plan.model_dump(mode="json")
                    fp = _hex64_of_canonical(dump)
                except Exception:
                    fp = None
            if fp is None:
                raise ValueError(
                    "StudyPlan has no authoritative fingerprint and no "
                    "deterministic content representation"
                )

        schema_version = getattr(plan, "schema_version", "1.0")
        status = getattr(plan, "status", None)
        status_str = str(status).lower() if status is not None else "draft"
        if "frozen" in status_str or "evidence_attached" in status_str or "decided" in status_str:
            availability = WorkspaceAvailabilityState.AVAILABLE
        elif "draft" in status_str:
            availability = WorkspaceAvailabilityState.PENDING_REVIEW
        else:
            availability = WorkspaceAvailabilityState.AVAILABLE

        standing = WorkspaceArtifactStanding.AUTHORED_CONFIGURATION
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
            fingerprint=str(fp).lower(),
            schema_version=str(schema_version),
            label=label,
            standing=standing,
            compatibility_standing=compat,
            parent_fingerprint=parent_fp,
            availability=availability,
            reason=(
                None
                if availability is WorkspaceAvailabilityState.AVAILABLE
                else "plan is in draft/pending review"
            ),
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
        try:
            if hasattr(contract, "model_dump"):
                dump = contract.model_dump(mode="json")
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
            raise ValueError("contract has no deterministic representation")
        except Exception as exc:
            raise ValueError(f"source_data_contract adapter failed: {exc}") from exc


# ---------------------------------------------------------------------------
# EventAlignedReport adapter
# ---------------------------------------------------------------------------


def event_aligned_report_to_ref(
    report: Any,  # noqa: ANN401
    *,
    standing: WorkspaceArtifactStanding,
) -> WorkspaceArtifactRef:
    """Adapt an ``EventAlignedReport`` to a workspace reference."""
    try:
        fingerprint = getattr(report, "fingerprint", None)
        if isinstance(fingerprint, str) and len(fingerprint) == 64:
            fp = fingerprint.lower()
        else:
            computed = getattr(report, "computed_fingerprint", None)
            if callable(computed):
                fp = str(computed()).lower()
            elif hasattr(report, "canonical_json") and callable(report.canonical_json):
                fp = hashlib.sha256(report.canonical_json().encode()).hexdigest()
            elif hasattr(report, "model_dump"):
                dump = report.model_dump(mode="json")
                fp = _hex64_of_canonical(dump)
            else:
                raise ValueError("EventAlignedReport has no deterministic fingerprint")
            if not isinstance(fp, str) or len(fp) != 64:
                raise ValueError("EventAlignedReport fingerprint invalid")

        schema_version = getattr(report, "schema_version", "1.0")
        report_id = getattr(report, "report_id", "event-aligned-report")
        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.EVENT_ALIGNED_REPORT,
            fingerprint=fp,
            schema_version=str(schema_version),
            label=_safe_label(str(report_id), "event-aligned-report"),
            standing=standing,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception as exc:
        raise ValueError(f"event_aligned_report adapter failed: {exc}") from exc


# ---------------------------------------------------------------------------
# ResourceStrategyReport adapter
# ---------------------------------------------------------------------------


def resource_strategy_report_to_ref(
    report: Any,  # noqa: ANN401
    *,
    standing: WorkspaceArtifactStanding,
) -> WorkspaceArtifactRef:
    """Adapt a ``ResourceStrategyReport`` to a workspace reference."""
    try:
        fp = getattr(report, "report_fingerprint", None)
        if not isinstance(fp, str) or len(fp) != 64:
            maybe = getattr(report, "fingerprint", None)
            if isinstance(maybe, str) and len(maybe) == 64:
                fp = maybe
            elif hasattr(report, "model_dump"):
                dump = report.model_dump(mode="json")
                fp = _hex64_of_canonical(dump)
            else:
                raise ValueError("ResourceStrategyReport has no deterministic fingerprint")
        fp = str(fp).lower()
        if len(fp) != 64:
            raise ValueError("ResourceStrategyReport fingerprint invalid")
        schema_version = getattr(report, "schema_version", None) or getattr(
            report, "report_version", "1.0"
        )
        study_id = getattr(report, "study_id", "resource-strategy-study")
        return WorkspaceArtifactRef(
            kind=WorkspaceArtifactKind.RESOURCE_STRATEGY_REPORT,
            fingerprint=fp,
            schema_version=str(schema_version),
            label=_safe_label(str(study_id), "resource-strategy-report"),
            standing=standing,
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
            meth = getattr(manifest, "fingerprint", None)
            if callable(meth):
                fp = meth()
            elif hasattr(manifest, "model_dump"):
                dump = manifest.model_dump(mode="json")
                fp = _hex64_of_canonical(dump)
            else:
                raise ValueError("StudyCapsuleManifest has no deterministic fingerprint")
        fp = str(fp).lower()
        if len(fp) != 64:
            raise ValueError("StudyCapsuleManifest fingerprint invalid")
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
            if hasattr(receipt, "model_dump"):
                dump = receipt.model_dump(mode="json")
                fp = _hex64_of_canonical(dump)
            else:
                raise ValueError("StudyCapsuleReceipt has no deterministic fingerprint")
        fp = str(fp).lower()
        if len(fp) != 64:
            raise ValueError("StudyCapsuleReceipt fingerprint invalid")
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
    standing: WorkspaceArtifactStanding,
) -> WorkspaceArtifactRef:
    """Adapt any model with a deterministic fingerprint to a generic reference."""
    try:
        fp_val: str | None = None
        # 1. existing valid stored fingerprint
        fp = getattr(report, "fingerprint", None)
        if isinstance(fp, str) and len(fp) == 64 and all(c in "0123456789abcdefABCDEF" for c in fp):
            fp_val = fp.lower()
        else:
            # 2. computed_fingerprint()
            comp = getattr(report, "computed_fingerprint", None)
            if callable(comp):
                try:
                    candidate = comp()
                    if isinstance(candidate, str) and len(candidate) == 64:
                        fp_val = candidate.lower()
                except Exception:
                    fp_val = None
            # 3. canonical_json / canonical_payload
            if (
                fp_val is None
                and hasattr(report, "canonical_json")
                and callable(report.canonical_json)
            ):
                try:
                    j = report.canonical_json()
                    if isinstance(j, str):
                        fp_val = hashlib.sha256(j.encode("utf-8")).hexdigest()
                except Exception:
                    fp_val = None
            if (
                fp_val is None
                and hasattr(report, "canonical_payload")
                and callable(report.canonical_payload)
            ):
                try:
                    payload = report.canonical_payload()
                    fp_val = _hex64_of_canonical(payload)
                except Exception:
                    fp_val = None
            # 4. model_dump(mode="json")
            if fp_val is None and hasattr(report, "model_dump"):
                try:
                    dump = report.model_dump(mode="json")
                    fp_val = _hex64_of_canonical(dump)
                except Exception:
                    fp_val = None
            # 5. structured dict/list payload fallback (explicitly supported)
            if fp_val is None and isinstance(report, (dict, list)):
                try:
                    fp_val = _hex64_of_canonical(report)
                except Exception:
                    fp_val = None
            # 6. Fail closed if no deterministic representation
            if fp_val is None or not isinstance(fp_val, str) or len(fp_val) != 64:
                raise ValueError(
                    "generic report has no deterministic fingerprint; provide "
                    "a valid fingerprint, computed_fingerprint, canonical_json, "
                    "or model_dump"
                )

        schema_version = getattr(report, "schema_version", "1.0")
        report_label = label
        if label == "generic-report":
            candidate_label = getattr(
                report,
                "report_id",
                getattr(report, "trace_id", getattr(report, "label", None)),
            )
            if isinstance(candidate_label, str) and candidate_label.strip():
                report_label = candidate_label

        return WorkspaceArtifactRef(
            kind=kind,
            fingerprint=fp_val.lower(),
            schema_version=str(schema_version),
            label=_safe_label(str(report_label), label),
            standing=standing,
            compatibility_standing=WorkspaceCompatibilityStanding.COMPATIBLE,
            availability=WorkspaceAvailabilityState.AVAILABLE,
        )
    except Exception as exc:
        raise ValueError(f"generic_report adapter failed: {exc}") from exc


def provenance_trace_to_ref(trace: Any) -> WorkspaceArtifactRef:  # noqa: ANN401
    return generic_report_to_ref(
        trace,
        kind=WorkspaceArtifactKind.PROVENANCE_TRACE,
        label="provenance-trace",
        standing=WorkspaceArtifactStanding.NOT_APPLICABLE,
    )
