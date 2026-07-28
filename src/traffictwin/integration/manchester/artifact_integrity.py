"""Structural guards against the 25-July artifact-identity defect.

Two independent failures let a wrong network identity propagate for two days
and made a recoverable chain look destroyed:

1. a derived artifact's identity (the decoded XML's size and hash) was stored in
   an evidence record's *source* fields, so the recorded source checksum was
   compared against the provider's checksum for a different representation and
   could never reconcile; and
2. the resulting mismatch was rationalised as a provider warning rather than
   refused, and the durable products of that build lived only in a
   session-scoped directory that later vanished.

This module refuses both shapes. It performs no acquisition, no decode, and no
network access: it reads recorded identities and on-disk files and fails closed.
Nothing here relabels evidence, and a passing audit is not an admission.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

#: Directory fragments whose contents do not survive a session or a reboot.
EPHEMERAL_PATH_FRAGMENTS: tuple[str, ...] = (
    "/tmp/",  # noqa: S108 - matched as a refusal pattern, never used as a path
    "/var/folders/",
    "/scratchpad/",
    "/private/tmp/",
)

_CHUNK_BYTES = 1024 * 1024


class ArtifactIntegrityError(RuntimeError):
    """Raised when a recorded identity is unsafe to trust or to depend on."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class ArtifactIdentity(ManchesterSnapshotModel):
    """One artifact's recorded identity, in exactly one representation."""

    role: Literal["source", "derived"]
    #: Free-form label such as "downloaded pbf" or "decoded osm xml".
    representation: str = Field(min_length=1, max_length=120)
    byte_size: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    md5: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class SourceDerivedRecord(ManchesterSnapshotModel):
    """A source identity paired with the artifact derived from it."""

    source: ArtifactIdentity
    derived: ArtifactIdentity

    @model_validator(mode="after")
    def validate_roles(self) -> SourceDerivedRecord:
        if self.source.role != "source" or self.derived.role != "derived":
            raise ValueError("the source and derived identities must carry their own roles")
        return self


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 of a file, read in bounded chunks."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: str | Path) -> str:
    """Return the MD5 of a file, for provider-checksum reconciliation only."""

    digest = hashlib.md5(usedforsecurity=False)
    with Path(path).open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def refuse_source_derived_collision(record: SourceDerivedRecord) -> None:
    """Refuse a record whose source identity is really its derived identity.

    This is the exact 25-July defect: a decode's output size and hash were
    written into the source fields, so the record described one artifact twice.
    A byte size or digest shared by both roles cannot be a coincidence for a
    real compression or transformation boundary, so it fails closed.
    """

    if record.source.sha256 == record.derived.sha256:
        raise ArtifactIntegrityError(
            "SOURCE_DERIVED_IDENTITY_COLLISION",
            "the recorded source and derived SHA-256 are identical, so the record "
            "describes one artifact in both roles",
        )
    if record.source.byte_size == record.derived.byte_size:
        raise ArtifactIntegrityError(
            "SOURCE_DERIVED_SIZE_COLLISION",
            "the recorded source and derived byte sizes are identical, which a "
            "decode or decompression boundary cannot produce",
        )
    if record.source.md5 is not None and record.source.md5 == record.derived.md5:
        raise ArtifactIntegrityError(
            "SOURCE_DERIVED_IDENTITY_COLLISION",
            "the recorded source and derived MD5 are identical, so the record "
            "describes one artifact in both roles",
        )


def verify_recorded_identity(identity: ArtifactIdentity, path: str | Path) -> None:
    """Refuse unless an on-disk file matches its recorded identity exactly."""

    file_path = Path(path)
    if file_path.is_symlink() or not file_path.is_file():
        raise ArtifactIntegrityError(
            "ARTIFACT_MISSING", "the recorded artifact is absent or is not a regular file"
        )
    observed_bytes = file_path.stat().st_size
    if observed_bytes != identity.byte_size:
        raise ArtifactIntegrityError(
            "ARTIFACT_SIZE_MISMATCH",
            f"recorded {identity.byte_size} bytes but the file holds {observed_bytes}",
        )
    if sha256_file(file_path) != identity.sha256:
        raise ArtifactIntegrityError(
            "ARTIFACT_HASH_MISMATCH", "the file does not match its recorded SHA-256"
        )
    if identity.md5 is not None and md5_file(file_path) != identity.md5:
        raise ArtifactIntegrityError(
            "ARTIFACT_CHECKSUM_MISMATCH", "the file does not match its recorded MD5"
        )


def refuse_ephemeral_dependency(path: str | Path) -> None:
    """Refuse a path that later phases must not depend on.

    A build product that a later phase consumes has to survive the session that
    produced it. Session scratchpads and system temporary directories do not.
    """

    resolved = str(Path(path).expanduser().resolve())
    probe = resolved if resolved.endswith("/") else resolved + "/"
    for fragment in EPHEMERAL_PATH_FRAGMENTS:
        if fragment in probe:
            raise ArtifactIntegrityError(
                "EPHEMERAL_DEPENDENCY_REFUSED",
                f"a later phase would depend on {fragment!r}, which does not survive "
                "the producing session; build into a durable location instead",
            )
