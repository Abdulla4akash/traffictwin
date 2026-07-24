"""Operator clean-checkout attestation for v0.6 registry provenance (ADR-058).

A registry cannot prove its producing package by itself. The accepted policy
lets an operator attest that a registry was produced or re-verified by running
the immutable ``v0.6.0`` tag from a clean checkout. TrafficTwin only verifies
the typed artifact against the current registry bytes; it never manufactures
provenance, and a verified attestation approves no migration, activation,
rollback, or capability.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

V06_ATTESTATION_SCHEMA_VERSION = "traffictwin.v06-producer-attestation.v1"
V06_RELEASE_TAG = "v0.6.0"
V06_RELEASE_COMMIT = "1c50a25246426128ac6e8530240eff362d16be02"
V06_PACKAGE_VERSION = "0.6.0"
OPERATOR_STATEMENT = (
    "I ran the immutable v0.6.0 tag from a clean checkout against this exact registry and "
    "confirm it as the producing or re-verifying release."
)
MAX_ATTESTATION_BYTES = 64 * 1024

VerificationFailure = Literal[
    "REGISTRY_MISSING_OR_UNSAFE",
    "REGISTRY_BYTES_CHANGED_SINCE_ATTESTATION",
]


class V06AttestationError(ValueError):
    """Typed refusal for invalid attestation artifacts or targets."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class V06ProducerAttestation(BaseModel):
    """One explicit operator attestation binding one exact registry state."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    schema_version: Literal["traffictwin.v06-producer-attestation.v1"] = (
        "traffictwin.v06-producer-attestation.v1"
    )
    attested_tag: Literal["v0.6.0"] = "v0.6.0"
    attested_tag_commit: Literal["1c50a25246426128ac6e8530240eff362d16be02"] = (
        "1c50a25246426128ac6e8530240eff362d16be02"
    )
    producer_package_version: Literal["0.6.0"] = "0.6.0"
    registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_size_bytes: int = Field(ge=1)
    attested_at: datetime
    operator_name: str = Field(min_length=1, max_length=200)
    operator_statement: Literal[
        "I ran the immutable v0.6.0 tag from a clean checkout against this exact registry and "
        "confirm it as the producing or re-verifying release."
    ] = (
        "I ran the immutable v0.6.0 tag from a clean checkout against this exact registry and "
        "confirm it as the producing or re-verifying release."
    )
    clean_checkout: Literal[True] = True
    basis: Literal["operator_clean_checkout_run"] = "operator_clean_checkout_run"
    migration_approved: Literal[False] = False
    activation_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_time(self) -> V06ProducerAttestation:
        """Refuse naive timestamps so the instant stays machine-comparable."""

        if self.attested_at.tzinfo is None or self.attested_at.utcoffset() is None:
            raise ValueError("attested_at must include a timezone")
        return self

    def canonical_json(self) -> str:
        """Return byte-stable JSON for this attestation."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Return the SHA-256 identity of this exact attestation."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class V06AttestationVerification(BaseModel):
    """Deterministic outcome of re-binding one attestation to current bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    schema_version: Literal["traffictwin.v06-producer-attestation.v1"] = (
        "traffictwin.v06-producer-attestation.v1"
    )
    verified: bool
    failure: VerificationFailure | None
    attestation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_sha256_now: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_product_version: str | None
    migration_approved: Literal[False] = False
    activation_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_outcome(self) -> V06AttestationVerification:
        """Keep success, failure, and provenance claims mutually consistent."""

        if self.verified == (self.failure is not None):
            raise ValueError("verified and failure must be mutually exclusive")
        expected_version = V06_PACKAGE_VERSION if self.verified else None
        if self.source_product_version != expected_version:
            raise ValueError("source_product_version must follow the verification outcome")
        return self


def build_v06_producer_attestation(
    registry_path: str | Path,
    *,
    operator_name: str,
    attested_at: datetime,
) -> V06ProducerAttestation:
    """Bind the operator's clean-checkout statement to the exact current bytes.

    The caller is the operator: calling this function is the recorded statement
    that the clean-checkout run described in ADR-058 actually happened.
    TrafficTwin cannot and does not verify that human step.
    """

    registry = _safe_registry(Path(registry_path))
    payload = registry.read_bytes()
    return V06ProducerAttestation(
        registry_sha256=hashlib.sha256(payload).hexdigest(),
        registry_size_bytes=len(payload),
        attested_at=attested_at,
        operator_name=operator_name,
    )


def load_v06_producer_attestation(path: str | Path) -> V06ProducerAttestation:
    """Load one bounded attestation artifact, failing closed on any drift."""

    artifact = Path(path)
    if artifact.is_symlink() or not artifact.is_file():
        raise V06AttestationError(
            "ATTESTATION_MISSING_OR_UNSAFE",
            f"attestation must be a regular non-symlinked file: {artifact}",
        )
    if artifact.stat().st_size > MAX_ATTESTATION_BYTES:
        raise V06AttestationError(
            "ATTESTATION_OVERSIZED", "attestation exceeds the bounded artifact size"
        )
    try:
        return V06ProducerAttestation.model_validate_json(artifact.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise V06AttestationError("ATTESTATION_INVALID", str(exc)) from exc


def verify_v06_producer_attestation(
    attestation: V06ProducerAttestation,
    registry_path: str | Path,
) -> V06AttestationVerification:
    """Re-hash the current registry bytes against one attestation."""

    registry = Path(registry_path)
    if registry.is_symlink() or not registry.is_file():
        return V06AttestationVerification(
            verified=False,
            failure="REGISTRY_MISSING_OR_UNSAFE",
            attestation_fingerprint=attestation.fingerprint(),
            registry_sha256_now=None,
            source_product_version=None,
        )
    payload = registry.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != attestation.registry_sha256 or len(payload) != attestation.registry_size_bytes:
        return V06AttestationVerification(
            verified=False,
            failure="REGISTRY_BYTES_CHANGED_SINCE_ATTESTATION",
            attestation_fingerprint=attestation.fingerprint(),
            registry_sha256_now=digest,
            source_product_version=None,
        )
    return V06AttestationVerification(
        verified=True,
        failure=None,
        attestation_fingerprint=attestation.fingerprint(),
        registry_sha256_now=digest,
        source_product_version=V06_PACKAGE_VERSION,
    )


def _safe_registry(registry: Path) -> Path:
    if registry.is_symlink() or not registry.is_file():
        raise V06AttestationError(
            "REGISTRY_MISSING_OR_UNSAFE",
            f"registry must be a regular non-symlinked file: {registry}",
        )
    for suffix in ("-wal", "-shm", "-journal"):
        if registry.with_name(registry.name + suffix).exists():
            raise V06AttestationError(
                "REGISTRY_NOT_CHECKPOINTED",
                "attestation requires a closed, checkpointed registry without sidecars",
            )
    return registry
