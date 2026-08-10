"""High-level service for the Data Contract workbench.

Provides:
- Bounded observation
- Contract authoring and freezing (immutability + lineage)
- Deterministic fingerprinting
- Drift comparison
- Portable exports
- Handoff preparation toward Manifest Inference / Bundle Import (no auto-import)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from traffictwin.data_contract.drift import compare_contracts, compare_observation_to_contract
from traffictwin.data_contract.exports import contract_to_canonical_dict
from traffictwin.data_contract.fingerprint import fingerprint_canonical
from traffictwin.data_contract.inspection import inspect_tabular_sample
from traffictwin.data_contract.models import (
    SchemaDriftReport,
    SchemaObservation,
    SourceContractVersion,
    SourceDataContract,
)


def fingerprint_source_contract(contract: SourceDataContract) -> str:
    """Return deterministic fingerprint for a source contract (excludes wall clock/path)."""
    canonical = contract_to_canonical_dict(contract)
    return fingerprint_canonical(canonical)


def _version_lineage_fingerprint(
    contract: SourceDataContract,
    version: str,
    parent_fingerprint: str | None,
    amendment_reason: str | None,
) -> str:
    fingerprint = fingerprint_source_contract(contract)
    payload: dict[str, Any] = {
        "contract_fingerprint": fingerprint,
        "version": version,
        "source_id": contract.source_id,
    }
    if parent_fingerprint is not None:
        assert amendment_reason is not None
        payload["parent_fingerprint"] = parent_fingerprint
        payload["amendment_reason"] = amendment_reason.strip()
    return fingerprint_canonical(payload)


def verify_contract_version(version: SourceContractVersion) -> None:
    """Verify stored fingerprint matches computed lineage; raise ValueError on mismatch."""
    # Also verify version matches contract_version for integrity
    if version.version != version.contract.contract_version:
        raise ValueError(
            f"version mismatch: wrapper {version.version!r} != contract {version.contract.contract_version!r}"  # noqa: E501
        )
    expected = _version_lineage_fingerprint(
        version.contract, version.version, version.parent_fingerprint, version.amendment_reason
    )
    if expected != version.fingerprint:
        raise ValueError(
            f"frozen contract fingerprint mismatch: expected {expected}, got {version.fingerprint}"
        )


def create_frozen_version(
    contract: SourceDataContract,
    *,
    parent_version: SourceContractVersion | None = None,
    amendment_reason: str | None = None,
) -> SourceContractVersion:
    """Create a frozen SourceContractVersion with deterministic fingerprint.

    When *parent_version* is provided, *amendment_reason* must be non-empty and
    the new version's ``parent_fingerprint`` is set to the parent's fingerprint.
    The version number is taken from ``contract.contract_version``.
    """
    if parent_version is not None:
        if amendment_reason is None or not amendment_reason.strip():
            raise ValueError("amendment_reason required when parent_version is provided")
    elif amendment_reason is not None:
        raise ValueError("amendment_reason requires parent_version")

    version_fingerprint = _version_lineage_fingerprint(
        contract,
        contract.contract_version,
        parent_version.fingerprint if parent_version else None,
        amendment_reason.strip() if amendment_reason else None,
    )

    version = SourceContractVersion(
        version=contract.contract_version,
        contract=contract,
        parent_fingerprint=parent_version.fingerprint if parent_version else None,
        amendment_reason=amendment_reason.strip() if amendment_reason else None,
        fingerprint=version_fingerprint,
        is_frozen=True,
    )
    return version


def create_new_version_from_parent(
    parent: SourceContractVersion,
    updated_contract: SourceDataContract,
    amendment_reason: str,
) -> SourceContractVersion:
    """Create a new version linked to *parent* with bumped version and reason."""
    if not parent.is_frozen:
        raise ValueError("parent must be frozen")
    if not amendment_reason.strip():
        raise ValueError("amendment_reason must be non-empty")
    if updated_contract.contract_version == parent.contract.contract_version:
        raise ValueError("updated contract_version must differ from parent version")
    return create_frozen_version(
        updated_contract, parent_version=parent, amendment_reason=amendment_reason
    )


def observe_sample(
    path: Path,
    *,
    max_rows: int = 5000,
    max_bytes: int = 5_000_000,
    observation_id: str = "obs_001",
    source_label: str = "local_sample",
) -> SchemaObservation:
    """Bounded observation facade (reuses inspection module)."""
    return inspect_tabular_sample(
        path,
        max_rows=max_rows,
        max_bytes=max_bytes,
        observation_id=observation_id,
        source_label=source_label,
    )


def compare_for_drift(
    frozen: SourceContractVersion,
    observation: SchemaObservation,
    candidate_contract: SourceDataContract | None = None,
) -> SchemaDriftReport:
    """Compare an observation (and optional candidate contract) to a frozen contract."""
    verify_contract_version(frozen)
    if candidate_contract is not None:
        return compare_contracts(frozen, candidate_contract, candidate_observation=observation)
    return compare_observation_to_contract(frozen, observation, candidate_contract=None)


def prepare_handoff_to_manifest(
    contract_version: SourceContractVersion,
    observation: SchemaObservation | None = None,
) -> dict[str, Any]:
    """Prepare a handoff payload toward Manifest Inference / Bundle Import.

    This does NOT import automatically. It returns a deterministic dict that
    a caller can use to pre-populate the manifest wizard or bundle import
    workflow. The payload is redacted and excludes raw values/paths.
    """
    verify_contract_version(contract_version)
    contract = contract_version.contract
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "purpose": "handoff_to_manifest_inference",
        "source_id": contract.source_id,
        "contract_version": contract.contract_version,
        "contract_fingerprint": contract_version.fingerprint,
        "fields": [
            {
                "field_name": f.field_name,
                "required": f.required,
                "logical_type": f.logical_type.value,
                "unit": f.unit.model_dump(mode="json") if f.unit else None,
                "timestamp": f.timestamp.model_dump(mode="json") if f.timestamp else None,
            }
            for f in sorted(contract.fields, key=lambda x: x.field_name)
        ],
        "rights": contract.rights.model_dump(mode="json"),
        "import_auto_executed": False,
        "note": "Prepared for Manifest Inference Wizard; import not executed automatically.",
    }
    if observation is not None:
        payload["observation_fingerprint"] = observation.fingerprint
        payload["observation_id"] = observation.observation_id
    payload["handoff_fingerprint"] = fingerprint_canonical(
        {k: v for k, v in payload.items() if k != "handoff_fingerprint"}
    )
    return payload
