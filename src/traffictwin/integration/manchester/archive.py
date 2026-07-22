"""Bounded in-memory decompression for untrusted Manchester source artifacts."""

from __future__ import annotations

import gzip
import io
import stat
import zipfile
from collections.abc import Collection
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, model_validator

_CHUNK_BYTES = 64 * 1024
_NESTED_ARCHIVE_SUFFIXES = {
    ".7z",
    ".bz2",
    ".gz",
    ".rar",
    ".tar",
    ".tgz",
    ".xz",
    ".zip",
}


class ManchesterArchiveError(ValueError):
    """Raised when compressed input violates the accepted archive boundary."""


class ArchivePolicy(BaseModel):
    """Explicit resource and member policy for one compressed source family."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_compressed_bytes: int = Field(gt=0, le=1_000_000_000)
    max_decompressed_bytes: int = Field(gt=0, le=2_000_000_000)
    max_member_bytes: int = Field(gt=0, le=1_000_000_000)
    max_members: int = Field(gt=0, le=10_000)
    max_compression_ratio: float = Field(gt=1.0, le=10_000.0)
    allowed_suffixes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_policy(self) -> ArchivePolicy:
        """Reject internally inconsistent or non-canonical policies."""

        if self.max_member_bytes > self.max_decompressed_bytes:
            raise ValueError("max_member_bytes cannot exceed max_decompressed_bytes")
        normalised = tuple(_normalise_suffix(value) for value in self.allowed_suffixes)
        if len(set(normalised)) != len(normalised):
            raise ValueError("allowed_suffixes must be unique")
        if normalised != self.allowed_suffixes:
            raise ValueError("allowed_suffixes must be lowercase and begin with a dot")
        return self


class ArchiveMember(BaseModel):
    """Verified metadata for one admitted zip member."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str
    compressed_bytes: int = Field(ge=0)
    decompressed_bytes: int = Field(ge=0)
    compression_ratio: float = Field(ge=0)


class BoundedZipContents(BaseModel):
    """Verified selected bytes plus a complete admitted member inventory."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    members: tuple[ArchiveMember, ...]
    selected: dict[str, bytes] = Field(repr=False)


def decompress_gzip(payload: bytes, *, policy: ArchivePolicy) -> bytes:
    """Return bounded gzip output without trusting headers or advertised sizes."""

    _check_compressed_size(payload, policy)
    output = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(payload), mode="rb") as source:
            while chunk := source.read(_CHUNK_BYTES):
                output.extend(chunk)
                _check_output_size(len(output), policy.max_decompressed_bytes)
                _check_ratio(len(output), len(payload), policy.max_compression_ratio)
    except (EOFError, OSError) as exc:
        raise ManchesterArchiveError("gzip payload is malformed or truncated") from exc
    return bytes(output)


def read_bounded_zip(
    payload: bytes,
    *,
    policy: ArchivePolicy,
    selected_members: Collection[str],
) -> BoundedZipContents:
    """Validate a complete zip and return only explicitly selected member bytes."""

    _check_compressed_size(payload, policy)
    selected = {_validated_member_path(value) for value in selected_members}
    if len(selected) != len(selected_members):
        raise ManchesterArchiveError("selected member paths must be unique")

    try:
        archive = zipfile.ZipFile(io.BytesIO(payload), mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ManchesterArchiveError("zip payload is malformed or truncated") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > policy.max_members:
            raise ManchesterArchiveError("zip member count exceeds policy")

        seen: set[str] = set()
        total_declared = 0
        total_actual = 0
        inventory: list[ArchiveMember] = []
        output: dict[str, bytes] = {}

        for info in infos:
            path = _validated_member_path(info.filename)
            if path in seen:
                raise ManchesterArchiveError("zip contains duplicate member paths")
            seen.add(path)
            _reject_special_member(info)
            if info.flag_bits & 0x1:
                raise ManchesterArchiveError("encrypted zip members are not admitted")
            if info.is_dir():
                continue
            _check_member_type(path, policy)
            if info.file_size > policy.max_member_bytes:
                raise ManchesterArchiveError("zip member size exceeds policy")
            total_declared += info.file_size
            _check_output_size(total_declared, policy.max_decompressed_bytes)
            ratio = _compression_ratio(info.file_size, info.compress_size)
            if ratio > policy.max_compression_ratio:
                raise ManchesterArchiveError("zip member compression ratio exceeds policy")

            contents = _read_member(archive, info, policy=policy)
            if len(contents) != info.file_size:
                raise ManchesterArchiveError("zip member size does not match central directory")
            total_actual += len(contents)
            _check_output_size(total_actual, policy.max_decompressed_bytes)
            inventory.append(
                ArchiveMember(
                    path=path,
                    compressed_bytes=info.compress_size,
                    decompressed_bytes=len(contents),
                    compression_ratio=ratio,
                )
            )
            if path in selected:
                output[path] = contents

        missing = selected - output.keys()
        if missing:
            raise ManchesterArchiveError("selected zip member is absent")
        if not inventory:
            raise ManchesterArchiveError("zip contains no admitted file members")
        return BoundedZipContents(
            members=tuple(sorted(inventory, key=lambda member: member.path)),
            selected={key: output[key] for key in sorted(output)},
        )


def _read_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    policy: ArchivePolicy,
) -> bytes:
    output = bytearray()
    try:
        with archive.open(info, mode="r") as source:
            while chunk := source.read(_CHUNK_BYTES):
                output.extend(chunk)
                if len(output) > policy.max_member_bytes:
                    raise ManchesterArchiveError("zip member size exceeds policy")
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ManchesterArchiveError("zip member cannot be read safely") from exc
    return bytes(output)


def _validated_member_path(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise ManchesterArchiveError("archive member path is unsafe")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ManchesterArchiveError("archive member path is unsafe")
    if path.parts[0].endswith(":"):
        raise ManchesterArchiveError("archive member path is unsafe")
    canonical = path.as_posix()
    expected = value[:-1] if value.endswith("/") else value
    if canonical != expected:
        raise ManchesterArchiveError("archive member path is unsafe")
    return canonical


def _reject_special_member(info: zipfile.ZipInfo) -> None:
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if stat.S_ISLNK(mode) or (file_type and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode))):
        raise ManchesterArchiveError("zip contains a special or symbolic-link member")


def _check_member_type(path: str, policy: ArchivePolicy) -> None:
    suffixes = tuple(suffix.lower() for suffix in PurePosixPath(path).suffixes)
    if any(suffix in _NESTED_ARCHIVE_SUFFIXES for suffix in suffixes):
        raise ManchesterArchiveError("nested archives are not admitted")
    if policy.allowed_suffixes and (not suffixes or suffixes[-1] not in policy.allowed_suffixes):
        raise ManchesterArchiveError("zip member type is not admitted")


def _check_compressed_size(payload: bytes, policy: ArchivePolicy) -> None:
    if not payload:
        raise ManchesterArchiveError("compressed payload is empty")
    if len(payload) > policy.max_compressed_bytes:
        raise ManchesterArchiveError("compressed payload exceeds policy")


def _check_output_size(size: int, limit: int) -> None:
    if size > limit:
        raise ManchesterArchiveError("decompressed output exceeds policy")


def _check_ratio(output_size: int, input_size: int, limit: float) -> None:
    if _compression_ratio(output_size, input_size) > limit:
        raise ManchesterArchiveError("compression ratio exceeds policy")


def _compression_ratio(output_size: int, input_size: int) -> float:
    if output_size == 0:
        return 0.0
    if input_size == 0:
        return float("inf")
    return output_size / input_size


def _normalise_suffix(value: str) -> str:
    if not value.startswith("."):
        return f".{value.lower()}"
    return value.lower()
