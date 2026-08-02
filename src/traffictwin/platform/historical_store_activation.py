"""Preview-first operational activation for the aggregate historical store.

The activation boundary is deliberately narrower than the persistent store:
only two existing, strict aggregate artifact families are adapted; every
source and payload is digest-bound; private paths stay in repr-suppressed
configuration; and the final catalogue appears only through one atomic
rename after a complete-backup restore drill.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from traffictwin.platform.bus_prediction import BusForecastFit, SessionActivityAggregate
from traffictwin.platform.historical_store import (
    AdmissionStatus,
    AuthoritativeSourceRecord,
    CatalogueNamespace,
    CatalogueQuery,
    CitationEntry,
    DatasetRegistrationCandidate,
    DatasetSchemaContract,
    EvidenceRole,
    EvidenceStanding,
    HistoricalDatasetRecord,
    InMemoryHistoricalStore,
    PayloadClass,
    SchemaLiteral,
    SourceBinding,
    SourceKind,
    StoreModel,
    StoreReceipt,
    StoreRefusal,
    SupportCount,
)
from traffictwin.platform.historical_store_sqlite import (
    BackupReceipt,
    LicenceAllowlistPolicy,
    PersistentStoreRefusal,
    RecoveryReport,
    SQLiteHistoricalStore,
    SQLiteStoreConfig,
)

ACTIVATION_METHOD_VERSION: Literal["aggregate-store-activation-1.0"] = (
    "aggregate-store-activation-1.0"
)
ACTIVATION_MARKER_NAME = "activation.json"
MANIFEST_SUFFIX = ".safe-aggregate-import.json"
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_ID_PATTERN = r"^[a-z0-9][a-z0-9._:/-]{0,159}$"
_SAFE_MESSAGE_LIMIT = 220
_MARKER_MAX_BYTES = 2 * 1024 * 1024
_CONFIG_MAX_BYTES = 128 * 1024
_PRIVATE_VALUE_RE = re.compile(
    r"(?:/(?:Users|home|private|tmp|var)(?:/|$)|[A-Za-z]:[\\/]|file://|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]+|"
    r"\b(?:BODS|ANTHROPIC|OPENAI)_API_KEY\s*=|"
    r"\b(?:VehicleRef|OperatorRef|session[_-]?token|participant[_-]?(?:id|code)))",
    re.IGNORECASE,
)
_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "privatekey",
        "salt",
        "secret",
        "token",
        "participant",
        "participantdata",
        "participantid",
        "participantresponse",
        "operatorid",
        "operatorref",
        "rawidentifier",
        "rawpayload",
        "vehicleid",
        "vehicleref",
    }
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_json(value: object) -> str:
    return _digest_bytes(_canonical_json(value).encode("utf-8"))


def _normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON constant forbidden: {value}")


class AggregateImportKind(StrEnum):
    BODS_SESSION_ACTIVITY_AGGREGATE = "bods_session_activity_aggregate"
    BUS_FORECAST_FIT = "bus_forecast_fit"


class ActivationRefusalCode(StrEnum):
    CONFIG_INVALID = "CONFIG_INVALID"
    WORKSPACE_INVALID = "WORKSPACE_INVALID"
    WORKSPACE_INTERSECTS_REPOSITORY = "WORKSPACE_INTERSECTS_REPOSITORY"
    IMPORT_OUTSIDE_WORKSPACE = "IMPORT_OUTSIDE_WORKSPACE"
    UNSAFE_PERMISSIONS = "UNSAFE_PERMISSIONS"
    SYMLINK_FORBIDDEN = "SYMLINK_FORBIDDEN"
    DISCOVERY_LIMIT_EXCEEDED = "DISCOVERY_LIMIT_EXCEEDED"
    EMPTY_IMPORT_SET = "EMPTY_IMPORT_SET"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    HANDLE_INVALID = "HANDLE_INVALID"
    INPUT_UNREADABLE = "INPUT_UNREADABLE"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    PRIVATE_CONTENT_REFUSED = "PRIVATE_CONTENT_REFUSED"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    DOMAIN_SCHEMA_INVALID = "DOMAIN_SCHEMA_INVALID"
    SOURCE_RECORD_INVALID = "SOURCE_RECORD_INVALID"
    SOURCE_CONTRACT_MISMATCH = "SOURCE_CONTRACT_MISMATCH"
    DUPLICATE_DATASET = "DUPLICATE_DATASET"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    STORE_DRY_RUN_REFUSED = "STORE_DRY_RUN_REFUSED"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    PREVIEW_NOT_ACTIVATABLE = "PREVIEW_NOT_ACTIVATABLE"
    PREVIEW_DIGEST_MISMATCH = "PREVIEW_DIGEST_MISMATCH"
    TARGET_CONFLICT = "TARGET_CONFLICT"
    TARGET_CORRUPT = "TARGET_CORRUPT"
    STORE_OPEN_REFUSED = "STORE_OPEN_REFUSED"
    REGISTRATION_REFUSED = "REGISTRATION_REFUSED"
    RECOVERY_REFUSED = "RECOVERY_REFUSED"
    BACKUP_REFUSED = "BACKUP_REFUSED"
    RESTORE_REFUSED = "RESTORE_REFUSED"
    PUBLICATION_REFUSED = "PUBLICATION_REFUSED"
    MARKER_INVALID = "MARKER_INVALID"
    QUERY_INVALID = "QUERY_INVALID"


class ActivationRefusal(StoreModel):
    operation: Literal["load_config", "preview", "activate", "catalogue", "integrity"]
    code: ActivationRefusalCode
    message: str = Field(min_length=1, max_length=_SAFE_MESSAGE_LIMIT)
    subject_id: str = Field(pattern=_ID_PATTERN)
    state_changed: Literal[False] = False
    target_published: Literal[False] = False
    path_exposed: Literal[False] = False
    evidence: Literal[False] = False


class AggregateImportManifest(StoreModel):
    """One local instruction binding safe metadata to two exact input files."""

    record_type: Literal["aggregate_store_import"] = "aggregate_store_import"
    schema_version: Literal["1.0"] = "1.0"
    import_kind: AggregateImportKind
    artifact_handle: str = Field(min_length=1, max_length=300)
    source_record_handle: str = Field(min_length=1, max_length=300)
    expected_artifact_digest: str = Field(pattern=_DIGEST_PATTERN)
    expected_source_file_digest: str = Field(pattern=_DIGEST_PATTERN)
    dataset_id: str = Field(pattern=_ID_PATTERN)
    logical_source_id: str = Field(pattern=_ID_PATTERN)
    created_at_utc: datetime
    licence_class: str = Field(min_length=1, max_length=120)
    citations: tuple[CitationEntry, ...] = Field(min_length=1)
    exclusions: tuple[str, ...] = ()
    refusal_count: int = Field(default=0, ge=0)
    aggregates_only: Literal[True] = True
    contains_private_paths: Literal[False] = False
    contains_credentials: Literal[False] = False

    @field_validator("artifact_handle", "source_record_handle")
    @classmethod
    def validate_relative_handle(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or "\\" in value
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("input handles must be clean relative POSIX paths")
        return value

    @field_validator("created_at_utc")
    @classmethod
    def require_aware_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_distinct_handles(self) -> AggregateImportManifest:
        if self.artifact_handle == self.source_record_handle:
            raise ValueError("artifact and source-record handles must differ")
        if len({item.key for item in self.citations}) != len(self.citations):
            raise ValueError("citation keys must be unique")
        return self


class ImportPreviewFinding(StoreModel):
    import_handle: str = Field(pattern=r"^import:[0-9a-f]{16}$|^discovery$")
    status: Literal["would_register", "would_reuse", "would_refuse"]
    dataset_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    import_kind: AggregateImportKind | None = None
    manifest_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    payload_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    source_file_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    dataset_record_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    refusal_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{2,80}$")


class ActivationPreview(StoreModel):
    method_version: Literal["aggregate-store-activation-1.0"] = ACTIVATION_METHOD_VERSION
    dry_run: Literal[True] = True
    workspace_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,79}$")
    activatable: bool
    target_status: Literal["absent", "exact_activation", "conflict", "corrupt"]
    manifests_discovered: int = Field(ge=0)
    would_register: int = Field(ge=0)
    would_reuse: int = Field(ge=0)
    would_refuse: int = Field(ge=0)
    findings: tuple[ImportPreviewFinding, ...]
    schema_digests: tuple[str, ...]
    licence_policy_digest: str = Field(pattern=_DIGEST_PATTERN)
    source_input_digests_before: tuple[str, ...]
    source_input_digests_after: tuple[str, ...]
    source_bytes_unchanged: bool
    orphan_staging_handles: tuple[str, ...]
    preview_digest: str = Field(pattern=_DIGEST_PATTERN)
    target_changed: Literal[False] = False
    source_records_changed: Literal[False] = False
    evidence: Literal[False] = False


class ExpectedDataset(StoreModel):
    dataset_id: str = Field(pattern=_ID_PATTERN)
    record_digest: str = Field(pattern=_DIGEST_PATTERN)
    payload_digest: str = Field(pattern=_DIGEST_PATTERN)


class ActivationReceipt(StoreModel):
    method_version: Literal["aggregate-store-activation-1.0"] = ACTIVATION_METHOD_VERSION
    preview_digest: str = Field(pattern=_DIGEST_PATTERN)
    workspace_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,79}$")
    activated_at_utc: datetime
    datasets_registered: int = Field(ge=1)
    datasets: tuple[ExpectedDataset, ...] = Field(min_length=1)
    backup: BackupReceipt
    restore_drill_verified: Literal[True] = True
    source_bytes_unchanged: Literal[True] = True
    atomic_publication: Literal[True] = True
    target_published: Literal[True] = True
    idempotent_retry: bool
    evidence: Literal[False] = False
    production_ready: Literal[False] = False


class ActivationMarker(StoreModel):
    record_type: Literal["aggregate_store_activation"] = "aggregate_store_activation"
    method_version: Literal["aggregate-store-activation-1.0"] = ACTIVATION_METHOD_VERSION
    preview_digest: str = Field(pattern=_DIGEST_PATTERN)
    schemas: tuple[DatasetSchemaContract, ...] = Field(min_length=1)
    authoritative_sources: tuple[AuthoritativeSourceRecord, ...] = Field(min_length=1)
    licence_policy: LicenceAllowlistPolicy
    expected_datasets: tuple[ExpectedDataset, ...] = Field(min_length=1)
    receipt: ActivationReceipt
    private_paths_stored: Literal[False] = False
    credentials_stored: Literal[False] = False
    evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_bindings(self) -> ActivationMarker:
        if self.receipt.preview_digest != self.preview_digest:
            raise ValueError("marker and receipt preview digests differ")
        if self.receipt.datasets != self.expected_datasets:
            raise ValueError("marker and receipt dataset bindings differ")
        return self


class ActivationCatalogueReport(StoreModel):
    method_version: Literal["aggregate-store-activation-1.0"] = ACTIVATION_METHOD_VERSION
    marker_digest: str = Field(pattern=_DIGEST_PATTERN)
    query: CatalogueQuery
    datasets: tuple[HistoricalDatasetRecord, ...]
    result_count: int = Field(ge=0)
    paths_exposed: Literal[False] = False
    evidence: Literal[False] = False


class ActivationIntegrityReport(StoreModel):
    method_version: Literal["aggregate-store-activation-1.0"] = ACTIVATION_METHOD_VERSION
    status: Literal["ok", "corrupt", "refused"]
    marker_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    recovery: RecoveryReport | None = None
    expected_dataset_count: int = Field(ge=0)
    reconciled_dataset_count: int = Field(ge=0)
    backup_restore_verified: bool
    orphan_staging_handles: tuple[str, ...]
    refusal_code: ActivationRefusalCode | None = None
    safe_to_use: bool
    automatic_deletion_performed: Literal[False] = False
    paths_exposed: Literal[False] = False
    evidence: Literal[False] = False


@dataclass(frozen=True, repr=False)
class ActivationConfig:
    """Private runtime selection; paths never enter a serialisable result."""

    workspace_id: str
    owner_workspace: Path
    repository_root: Path
    import_roots: tuple[Path, ...]
    licence_policy: LicenceAllowlistPolicy
    max_manifest_bytes: int = 128 * 1024
    max_source_record_bytes: int = 256 * 1024
    max_artifact_bytes: int = 16 * 1024 * 1024
    max_manifests: int = 1_000
    max_discovery_entries: int = 10_000
    max_depth: int = 8


class _LocalConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    workspace_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,79}$")
    owner_workspace: str = Field(min_length=1)
    repository_root: str = Field(min_length=1)
    import_roots: tuple[str, ...] = Field(min_length=1)
    licence_policy: LicenceAllowlistPolicy
    max_manifest_bytes: int = Field(default=128 * 1024, ge=1, le=2 * 1024 * 1024)
    max_source_record_bytes: int = Field(default=256 * 1024, ge=1, le=4 * 1024 * 1024)
    max_artifact_bytes: int = Field(default=16 * 1024 * 1024, ge=1, le=64 * 1024 * 1024)
    max_manifests: int = Field(default=1_000, ge=1, le=10_000)
    max_discovery_entries: int = Field(default=10_000, ge=1, le=100_000)
    max_depth: int = Field(default=8, ge=1, le=32)


@dataclass(frozen=True, repr=False)
class _ResolvedConfig:
    public: ActivationConfig
    owner_workspace: Path
    repository_root: Path
    import_roots: tuple[Path, ...]


@dataclass(frozen=True, repr=False)
class _InputDigest:
    path: Path
    digest: str
    max_bytes: int


@dataclass(frozen=True, repr=False)
class _PreparedImport:
    import_handle: str
    manifest_digest: str
    source_file_digest: str
    candidate: DatasetRegistrationCandidate
    source: AuthoritativeSourceRecord
    import_kind: AggregateImportKind
    input_digests: tuple[_InputDigest, ...]


@dataclass(frozen=True, repr=False)
class _PreparedPreview:
    resolved: _ResolvedConfig
    preview: ActivationPreview
    schemas: tuple[DatasetSchemaContract, ...]
    sources: tuple[AuthoritativeSourceRecord, ...]
    imports: tuple[_PreparedImport, ...]


class _ActivationError(RuntimeError):
    def __init__(self, code: ActivationRefusalCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message[:_SAFE_MESSAGE_LIMIT]


def _refusal(
    operation: Literal["load_config", "preview", "activate", "catalogue", "integrity"],
    code: ActivationRefusalCode,
    message: str,
    *,
    subject_id: str = "historical-store",
) -> ActivationRefusal:
    return ActivationRefusal(
        operation=operation,
        code=code,
        message=message[:_SAFE_MESSAGE_LIMIT],
        subject_id=subject_id,
    )


def _contained(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_owner_mode(path: Path, *, directory: bool) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise _ActivationError(
            ActivationRefusalCode.WORKSPACE_INVALID
            if directory
            else ActivationRefusalCode.INPUT_UNREADABLE,
            "a selected local input is unavailable",
        ) from exc
    if stat.S_ISLNK(details.st_mode):
        raise _ActivationError(
            ActivationRefusalCode.SYMLINK_FORBIDDEN,
            "symbolic links are forbidden at the activation boundary",
        )
    expected_kind = stat.S_ISDIR(details.st_mode) if directory else stat.S_ISREG(details.st_mode)
    if not expected_kind:
        raise _ActivationError(
            ActivationRefusalCode.WORKSPACE_INVALID
            if directory
            else ActivationRefusalCode.INPUT_UNREADABLE,
            "a selected local input has the wrong filesystem type",
        )
    if details.st_uid != os.getuid() or details.st_mode & 0o077:
        raise _ActivationError(
            ActivationRefusalCode.UNSAFE_PERMISSIONS,
            "selected activation inputs must be private and owned by the current user",
        )
    required = stat.S_IRUSR | (stat.S_IWUSR | stat.S_IXUSR if directory else 0)
    if details.st_mode & required != required:
        raise _ActivationError(
            ActivationRefusalCode.UNSAFE_PERMISSIONS,
            "selected activation inputs lack required owner permissions",
        )
    return details


def _validate_repository(path: Path) -> None:
    try:
        details = path.lstat()
    except OSError as exc:
        raise _ActivationError(
            ActivationRefusalCode.WORKSPACE_INVALID,
            "the selected repository root is unavailable",
        ) from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise _ActivationError(
            ActivationRefusalCode.WORKSPACE_INVALID,
            "the selected repository root is not a real directory",
        )


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path.expanduser()))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            if current.is_symlink():
                raise _ActivationError(
                    ActivationRefusalCode.SYMLINK_FORBIDDEN,
                    "symbolic-link path components are forbidden at the activation boundary",
                )
        except OSError as exc:
            raise _ActivationError(
                ActivationRefusalCode.WORKSPACE_INVALID,
                "a selected activation path could not be inspected safely",
            ) from exc


def _validate_path_chain(path: Path, root: Path, *, final_directory: bool) -> None:
    if not _contained(path, root):
        raise _ActivationError(
            ActivationRefusalCode.IMPORT_OUTSIDE_WORKSPACE,
            "an activation input resolves outside the selected owner workspace",
        )
    relative = path.relative_to(root)
    current = root
    _validate_owner_mode(current, directory=True)
    for index, part in enumerate(relative.parts):
        current = current / part
        _validate_owner_mode(
            current,
            directory=final_directory or index < len(relative.parts) - 1,
        )


def _validate_private_tree(root: Path, *, max_entries: int) -> None:
    entries = 0
    _validate_owner_mode(root, directory=True)
    for directory_name, directory_names, file_names in os.walk(root, followlinks=False):
        directory = Path(directory_name)
        _validate_owner_mode(directory, directory=True)
        for name in directory_names:
            entries += 1
            _validate_owner_mode(directory / name, directory=True)
        for name in file_names:
            entries += 1
            _validate_owner_mode(directory / name, directory=False)
        if entries > max_entries:
            raise _ActivationError(
                ActivationRefusalCode.DISCOVERY_LIMIT_EXCEEDED,
                "the activation workspace exceeds its bounded integrity-scan limit",
            )


def _harden_owned_staging_tree(root: Path, *, max_entries: int) -> None:
    entries = 0
    for directory_name, directory_names, file_names in os.walk(root, followlinks=False):
        directory = Path(directory_name)
        for path, expected_directory in (
            (directory, True),
            *((directory / name, True) for name in directory_names),
            *((directory / name, False) for name in file_names),
        ):
            try:
                details = path.lstat()
            except OSError as exc:
                raise _ActivationError(
                    ActivationRefusalCode.WORKSPACE_INVALID,
                    "the staged activation workspace could not be inspected safely",
                ) from exc
            if (
                stat.S_ISLNK(details.st_mode)
                or details.st_uid != os.getuid()
                or (expected_directory and not stat.S_ISDIR(details.st_mode))
                or (not expected_directory and not stat.S_ISREG(details.st_mode))
            ):
                raise _ActivationError(
                    ActivationRefusalCode.SYMLINK_FORBIDDEN,
                    "the staged activation workspace contains an unsafe filesystem entry",
                )
            path.chmod(0o700 if expected_directory else 0o600)
        entries += len(directory_names) + len(file_names)
        if entries > max_entries:
            raise _ActivationError(
                ActivationRefusalCode.DISCOVERY_LIMIT_EXCEEDED,
                "the staged activation workspace exceeds its bounded integrity-scan limit",
            )
    _validate_private_tree(root, max_entries=max_entries)


def _resolve_config(config: ActivationConfig, *, include_imports: bool) -> _ResolvedConfig:
    if re.fullmatch(r"^[a-z][a-z0-9._-]{0,79}$", config.workspace_id) is None:
        raise _ActivationError(
            ActivationRefusalCode.CONFIG_INVALID,
            "workspace_id does not use the safe identifier grammar",
        )
    _reject_symlink_components(config.owner_workspace)
    _reject_symlink_components(config.repository_root)
    owner = config.owner_workspace.expanduser().resolve(strict=True)
    repository = config.repository_root.expanduser().resolve(strict=True)
    _validate_owner_mode(owner, directory=True)
    _validate_repository(repository)
    if _contained(owner, repository) or _contained(repository, owner):
        raise _ActivationError(
            ActivationRefusalCode.WORKSPACE_INTERSECTS_REPOSITORY,
            "the owner workspace and repository must be disjoint",
        )
    roots: list[Path] = []
    if include_imports:
        if not config.import_roots:
            raise _ActivationError(
                ActivationRefusalCode.CONFIG_INVALID,
                "at least one import root is required",
            )
        target = owner / "historical-store"
        for configured in config.import_roots:
            _reject_symlink_components(configured)
            root = configured.expanduser().resolve(strict=True)
            _validate_path_chain(root, owner, final_directory=True)
            if root == owner or _contained(root, target) or _contained(target, root):
                raise _ActivationError(
                    ActivationRefusalCode.IMPORT_OUTSIDE_WORKSPACE,
                    "import roots must be bounded subdirectories separate from the target store",
                )
            roots.append(root)
        if len(set(roots)) != len(roots):
            raise _ActivationError(
                ActivationRefusalCode.CONFIG_INVALID,
                "import roots must be unique",
            )
    limits = (
        config.max_manifest_bytes,
        config.max_source_record_bytes,
        config.max_artifact_bytes,
        config.max_manifests,
        config.max_discovery_entries,
        config.max_depth,
    )
    if any(value <= 0 for value in limits):
        raise _ActivationError(
            ActivationRefusalCode.CONFIG_INVALID,
            "activation discovery limits must be positive",
        )
    return _ResolvedConfig(
        public=config,
        owner_workspace=owner,
        repository_root=repository,
        import_roots=tuple(roots),
    )


def _read_private_file(path: Path, max_bytes: int) -> bytes:
    _validate_owner_mode(path, directory=False)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _ActivationError(
            ActivationRefusalCode.INPUT_UNREADABLE,
            "a selected local input could not be opened safely",
        ) from exc
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid():
            raise _ActivationError(
                ActivationRefusalCode.INPUT_UNREADABLE,
                "a selected local input changed while it was being read",
            )
        if details.st_size > max_bytes:
            raise _ActivationError(
                ActivationRefusalCode.INPUT_TOO_LARGE,
                "a selected local input exceeds its configured byte limit",
            )
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        result = b"".join(chunks)
        if len(result) > max_bytes:
            raise _ActivationError(
                ActivationRefusalCode.INPUT_TOO_LARGE,
                "a selected local input exceeds its configured byte limit",
            )
        return result
    finally:
        os.close(descriptor)


def _screen_safe_metadata(raw: bytes) -> None:
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(text, parse_constant=_reject_nonfinite)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise _ActivationError(
            ActivationRefusalCode.MANIFEST_INVALID,
            "safe metadata must be finite UTF-8 JSON",
        ) from exc
    if _PRIVATE_VALUE_RE.search(text):
        raise _ActivationError(
            ActivationRefusalCode.PRIVATE_CONTENT_REFUSED,
            "private path, credential, identifier or participant-like metadata was refused",
        )

    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if not isinstance(key, str):
                    raise _ActivationError(
                        ActivationRefusalCode.MANIFEST_INVALID,
                        "safe metadata JSON keys must be strings",
                    )
                if _normalise_key(key) in _FORBIDDEN_METADATA_KEYS:
                    raise _ActivationError(
                        ActivationRefusalCode.PRIVATE_CONTENT_REFUSED,
                        "private, credential, identifier or participant metadata was refused",
                    )
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)
        elif isinstance(value, str) and _PRIVATE_VALUE_RE.search(value):
            raise _ActivationError(
                ActivationRefusalCode.PRIVATE_CONTENT_REFUSED,
                "private path, credential, identifier or participant-like metadata was refused",
            )

    walk(parsed)


def _activity_schema() -> DatasetSchemaContract:
    keys = tuple(SessionActivityAggregate.model_fields)
    return DatasetSchemaContract(
        schema_name="bods.session.activity.aggregate",
        schema_version=1,
        payload_class=PayloadClass.AGGREGATE_SESSION_MEASUREMENT,
        required_top_level_keys=keys,
        allowed_top_level_keys=keys,
        required_literals=(
            SchemaLiteral(field="record_type", value="bods_session_activity_aggregate"),
            SchemaLiteral(field="schema_version", value="1.0"),
            SchemaLiteral(field="aggregates_only", value=True),
            SchemaLiteral(field="raw_identifiers_published", value=False),
        ),
    )


def _forecast_schema() -> DatasetSchemaContract:
    keys = tuple(BusForecastFit.model_fields)
    return DatasetSchemaContract(
        schema_name="bods.bus.forecast.fit",
        schema_version=1,
        payload_class=PayloadClass.MODEL_ARTIFACT,
        required_top_level_keys=keys,
        allowed_top_level_keys=keys,
        required_literals=(
            SchemaLiteral(field="schema_version", value="1.0"),
            SchemaLiteral(field="method_version", value="bods-bus-forecast-1.0"),
            SchemaLiteral(field="research_status", value="owner_approved_candidate"),
            SchemaLiteral(field="evidence", value=False),
        ),
    )


def activation_schemas() -> tuple[DatasetSchemaContract, ...]:
    """The complete, closed adapter schema set."""

    return (_activity_schema(), _forecast_schema())


def _schema_for(kind: AggregateImportKind) -> DatasetSchemaContract:
    return (
        _activity_schema()
        if kind is AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE
        else _forecast_schema()
    )


def _validate_source_contract(
    source: AuthoritativeSourceRecord,
    schema: DatasetSchemaContract,
    payload_digest: str,
    kind: AggregateImportKind,
) -> None:
    if (
        source.payload_digest != payload_digest
        or source.schema_name != schema.schema_name
        or source.schema_version != schema.schema_version
        or source.payload_class is not schema.payload_class
        or source.sparse64
        or source.metadata_only
    ):
        raise _ActivationError(
            ActivationRefusalCode.SOURCE_CONTRACT_MISMATCH,
            "the authoritative source record does not bind the exact safe artifact contract",
        )
    if kind is AggregateImportKind.BUS_FORECAST_FIT:
        expected = EvidenceStanding(
            evidence_role=EvidenceRole.FORECAST,
            admission_status=AdmissionStatus.NOT_APPLICABLE,
            evidence=False,
        )
        if source.standing != expected:
            raise _ActivationError(
                ActivationRefusalCode.SOURCE_CONTRACT_MISMATCH,
                "a forecast-fit source must remain forecast, not-applicable and evidence=false",
            )


def _build_candidate(
    manifest: AggregateImportManifest,
    payload: bytes,
    source: AuthoritativeSourceRecord,
) -> DatasetRegistrationCandidate:
    schema = _schema_for(manifest.import_kind)
    payload_digest = _digest_bytes(payload)
    _validate_source_contract(source, schema, payload_digest, manifest.import_kind)
    local_dates: tuple[str, ...]
    support: tuple[SupportCount, ...]
    timezone: str | None
    if manifest.import_kind is AggregateImportKind.BODS_SESSION_ACTIVITY_AGGREGATE:
        try:
            artifact = SessionActivityAggregate.model_validate_json(payload, strict=True)
        except ValidationError as exc:
            raise _ActivationError(
                ActivationRefusalCode.DOMAIN_SCHEMA_INVALID,
                "the activity artifact failed its existing strict domain schema",
            ) from exc
        standing = source.standing
        local_dates = (artifact.session_date_local,)
        timezone = "Europe/London"
        support = (
            SupportCount(name="snapshots", value=artifact.snapshot_count),
            SupportCount(name="progression_rows", value=len(artifact.hourly_progression)),
        )
    else:
        try:
            fit = BusForecastFit.model_validate_json(payload, strict=True)
        except ValidationError as exc:
            raise _ActivationError(
                ActivationRefusalCode.DOMAIN_SCHEMA_INVALID,
                "the forecast-fit artifact failed its existing strict domain schema",
            ) from exc
        standing = EvidenceStanding(
            evidence_role=EvidenceRole.FORECAST,
            admission_status=AdmissionStatus.NOT_APPLICABLE,
            evidence=False,
        )
        local_dates = tuple(fit.fit_dates)
        timezone = "Europe/London" if local_dates else None
        support = (
            SupportCount(name="source_sessions", value=len(fit.sources)),
            SupportCount(name="fit_dates", value=len(fit.fit_dates)),
            SupportCount(name="cells", value=len(fit.cells)),
        )
    record = HistoricalDatasetRecord(
        dataset_id=manifest.dataset_id,
        logical_source_id=manifest.logical_source_id,
        payload_class=schema.payload_class,
        schema_name=schema.schema_name,
        schema_version=schema.schema_version,
        schema_digest=schema.fingerprint(),
        payload_digest=payload_digest,
        payload_handle=f"sha256:{payload_digest}",
        source_bindings=(
            SourceBinding(
                source_kind=SourceKind.AUTHORITATIVE_RECORD,
                source_id=source.source_record_id,
                expected_record_digest=source.record_digest,
                expected_payload_digest=source.payload_digest,
            ),
        ),
        created_at_utc=manifest.created_at_utc,
        local_service_dates=local_dates,
        timezone=timezone,
        support=support,
        exclusions=manifest.exclusions,
        refusal_count=manifest.refusal_count,
        standing=standing,
        citation_bundle=manifest.citations,
        licence_class=manifest.licence_class,
        namespace=CatalogueNamespace.GENERAL,
    )
    return DatasetRegistrationCandidate(record=record, payload=payload)


def _opaque_import_handle(relative: str) -> str:
    return f"import:{_digest_bytes(relative.encode('utf-8'))[:16]}"


def _resolve_input_handle(manifest_path: Path, root: Path, handle: str) -> Path:
    candidate = manifest_path.parent.joinpath(*PurePosixPath(handle).parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise _ActivationError(
            ActivationRefusalCode.INPUT_UNREADABLE,
            "a manifest-bound input is unavailable",
        ) from exc
    _validate_path_chain(resolved, root, final_directory=False)
    return resolved


def _discover_manifests(config: _ResolvedConfig) -> tuple[tuple[Path, Path], ...]:
    discovered: list[tuple[Path, Path]] = []
    entries = 0
    for root in config.import_roots:
        for directory_name, directory_names, file_names in os.walk(root, followlinks=False):
            directory = Path(directory_name)
            depth = len(directory.relative_to(root).parts)
            if depth > config.public.max_depth:
                raise _ActivationError(
                    ActivationRefusalCode.DISCOVERY_LIMIT_EXCEEDED,
                    "import discovery exceeded the configured depth limit",
                )
            _validate_path_chain(directory, root, final_directory=True)
            for name in sorted(directory_names):
                entries += 1
                _validate_owner_mode(directory / name, directory=True)
            for name in sorted(file_names):
                entries += 1
                path = directory / name
                _validate_owner_mode(path, directory=False)
                if name.endswith(MANIFEST_SUFFIX):
                    discovered.append((root, path))
            if entries > config.public.max_discovery_entries:
                raise _ActivationError(
                    ActivationRefusalCode.DISCOVERY_LIMIT_EXCEEDED,
                    "import discovery exceeded the configured entry limit",
                )
            if len(discovered) > config.public.max_manifests:
                raise _ActivationError(
                    ActivationRefusalCode.DISCOVERY_LIMIT_EXCEEDED,
                    "import discovery exceeded the configured manifest limit",
                )
    return tuple(sorted(discovered, key=lambda item: str(item[1])))


def _prepare_one(config: _ResolvedConfig, root: Path, path: Path) -> _PreparedImport:
    relative = path.relative_to(root).as_posix()
    import_handle = _opaque_import_handle(relative)
    manifest_bytes = _read_private_file(path, config.public.max_manifest_bytes)
    _screen_safe_metadata(manifest_bytes)
    try:
        manifest = AggregateImportManifest.model_validate_json(manifest_bytes, strict=True)
    except ValidationError as exc:
        raise _ActivationError(
            ActivationRefusalCode.MANIFEST_INVALID,
            "an import manifest failed its strict schema",
        ) from exc
    artifact_path = _resolve_input_handle(path, root, manifest.artifact_handle)
    source_path = _resolve_input_handle(path, root, manifest.source_record_handle)
    if artifact_path in (path, source_path) or source_path == path:
        raise _ActivationError(
            ActivationRefusalCode.HANDLE_INVALID,
            "manifest, artifact and source-record inputs must be distinct",
        )
    payload = _read_private_file(artifact_path, config.public.max_artifact_bytes)
    source_bytes = _read_private_file(source_path, config.public.max_source_record_bytes)
    manifest_digest = _digest_bytes(manifest_bytes)
    payload_digest = _digest_bytes(payload)
    source_file_digest = _digest_bytes(source_bytes)
    if (
        payload_digest != manifest.expected_artifact_digest
        or source_file_digest != manifest.expected_source_file_digest
    ):
        raise _ActivationError(
            ActivationRefusalCode.DIGEST_MISMATCH,
            "a manifest-bound source or artifact digest does not match",
        )
    _screen_safe_metadata(source_bytes)
    try:
        source = AuthoritativeSourceRecord.model_validate_json(source_bytes, strict=True)
    except ValidationError as exc:
        raise _ActivationError(
            ActivationRefusalCode.SOURCE_RECORD_INVALID,
            "an authoritative source record failed its strict schema",
        ) from exc
    candidate = _build_candidate(manifest, payload, source)
    return _PreparedImport(
        import_handle=import_handle,
        manifest_digest=manifest_digest,
        source_file_digest=source_file_digest,
        candidate=candidate,
        source=source,
        import_kind=manifest.import_kind,
        input_digests=(
            _InputDigest(
                path=path,
                digest=manifest_digest,
                max_bytes=config.public.max_manifest_bytes,
            ),
            _InputDigest(
                path=artifact_path,
                digest=payload_digest,
                max_bytes=config.public.max_artifact_bytes,
            ),
            _InputDigest(
                path=source_path,
                digest=source_file_digest,
                max_bytes=config.public.max_source_record_bytes,
            ),
        ),
    )


def _orphan_handles(
    owner_workspace: Path,
    current_preview_digest: str | None = None,
) -> tuple[str, ...]:
    handles: list[str] = []
    prefixes = (".historical-store-activation-", ".historical-store-restore-")
    for path in sorted(owner_workspace.iterdir()):
        if not any(path.name.startswith(prefix) for prefix in prefixes):
            continue
        if (
            current_preview_digest is not None
            and path.name == f".historical-store-activation-{current_preview_digest[:16]}"
        ):
            continue
        handles.append(f"orphan:{_digest_bytes(path.name.encode('utf-8'))[:16]}")
    return tuple(handles)


def _read_marker(root: Path) -> tuple[ActivationMarker, str]:
    marker_path = root / ACTIVATION_MARKER_NAME
    marker_bytes = _read_private_file(marker_path, _MARKER_MAX_BYTES)
    try:
        marker = ActivationMarker.model_validate_json(marker_bytes, strict=True)
    except ValidationError as exc:
        raise _ActivationError(
            ActivationRefusalCode.MARKER_INVALID,
            "the activation marker failed strict validation",
        ) from exc
    return marker, _digest_bytes(marker_bytes)


def _target_status(owner_workspace: Path, preview_digest: str, max_entries: int) -> str:
    target = owner_workspace / "historical-store"
    if not target.exists() and not target.is_symlink():
        return "absent"
    try:
        _validate_private_tree(target, max_entries=max_entries)
        marker, _ = _read_marker(target)
    except _ActivationError:
        return "corrupt"
    return "exact_activation" if marker.preview_digest == preview_digest else "conflict"


def _source_digests(imports: Sequence[_PreparedImport]) -> tuple[str, ...]:
    return tuple(sorted(digest.digest for prepared in imports for digest in prepared.input_digests))


def _recheck_source_inputs(imports: Sequence[_PreparedImport]) -> tuple[str, ...]:
    observed: list[str] = []
    for prepared in imports:
        for expected in prepared.input_digests:
            raw = _read_private_file(expected.path, expected.max_bytes)
            digest = _digest_bytes(raw)
            observed.append(digest)
            if digest != expected.digest:
                raise _ActivationError(
                    ActivationRefusalCode.SOURCE_CHANGED,
                    "a selected source changed after preview",
                )
    return tuple(sorted(observed))


def _preview_identity(
    *,
    config: ActivationConfig,
    schemas: Sequence[DatasetSchemaContract],
    imports: Sequence[_PreparedImport],
    findings: Sequence[ImportPreviewFinding],
) -> str:
    return _digest_json(
        {
            "method_version": ACTIVATION_METHOD_VERSION,
            "workspace_id": config.workspace_id,
            "schema_digests": sorted(schema.fingerprint() for schema in schemas),
            "licence_policy_digest": config.licence_policy.policy_digest,
            "imports": [
                {
                    "import_handle": item.import_handle,
                    "manifest_digest": item.manifest_digest,
                    "source_file_digest": item.source_file_digest,
                    "payload_digest": item.candidate.record.payload_digest,
                    "record_digest": item.candidate.record.fingerprint(),
                }
                for item in sorted(imports, key=lambda entry: entry.import_handle)
            ],
            "findings": [
                item.model_dump(mode="json")
                for item in sorted(findings, key=lambda entry: entry.import_handle)
            ],
        }
    )


def _prepare_preview(config: ActivationConfig) -> _PreparedPreview:
    resolved = _resolve_config(config, include_imports=True)
    schemas = activation_schemas()
    manifests = _discover_manifests(resolved)
    prepared: list[_PreparedImport] = []
    findings: list[ImportPreviewFinding] = []
    for root, path in manifests:
        handle = _opaque_import_handle(path.relative_to(root).as_posix())
        try:
            item = _prepare_one(resolved, root, path)
        except _ActivationError as exc:
            findings.append(
                ImportPreviewFinding(
                    import_handle=handle,
                    status="would_refuse",
                    refusal_code=exc.code.value,
                )
            )
        else:
            prepared.append(item)
    if not manifests:
        findings.append(
            ImportPreviewFinding(
                import_handle="discovery",
                status="would_refuse",
                refusal_code=ActivationRefusalCode.EMPTY_IMPORT_SET.value,
            )
        )

    duplicate_ids = {
        dataset_id for dataset_id, items in _group_by_dataset(prepared).items() if len(items) > 1
    }
    source_groups: dict[str, list[_PreparedImport]] = defaultdict(list)
    for item in prepared:
        source_groups[item.source.source_record_id].append(item)
    conflicting_sources = {
        source_id
        for source_id, items in source_groups.items()
        if len({entry.source.fingerprint() for entry in items}) > 1
    }
    eligible: list[_PreparedImport] = []
    for item in prepared:
        code: ActivationRefusalCode | None = None
        if item.candidate.record.dataset_id in duplicate_ids:
            code = ActivationRefusalCode.DUPLICATE_DATASET
        elif item.source.source_record_id in conflicting_sources:
            code = ActivationRefusalCode.SOURCE_CONFLICT
        if code is not None:
            findings.append(
                ImportPreviewFinding(
                    import_handle=item.import_handle,
                    status="would_refuse",
                    dataset_id=item.candidate.record.dataset_id,
                    import_kind=item.import_kind,
                    manifest_digest=item.manifest_digest,
                    payload_digest=item.candidate.record.payload_digest,
                    source_file_digest=item.source_file_digest,
                    dataset_record_digest=item.candidate.record.fingerprint(),
                    refusal_code=code.value,
                )
            )
        else:
            eligible.append(item)
    sources = tuple(
        sorted(
            {item.source.source_record_id: item.source for item in eligible}.values(),
            key=lambda source: source.source_record_id,
        )
    )
    if eligible:
        core = InMemoryHistoricalStore(
            schemas=schemas,
            authoritative_sources=sources,
            licence_allowlist=frozenset(config.licence_policy.allowed_classes),
        )
        dry_run = core.dry_run_migration([item.candidate for item in eligible])
        by_dataset = {item.candidate.record.dataset_id: item for item in eligible}
        for outcome in dry_run.findings:
            item = by_dataset[outcome.dataset_id]
            status: Literal["would_register", "would_reuse", "would_refuse"] = outcome.status
            findings.append(
                ImportPreviewFinding(
                    import_handle=item.import_handle,
                    status=status,
                    dataset_id=outcome.dataset_id,
                    import_kind=item.import_kind,
                    manifest_digest=item.manifest_digest,
                    payload_digest=item.candidate.record.payload_digest,
                    source_file_digest=item.source_file_digest,
                    dataset_record_digest=item.candidate.record.fingerprint(),
                    refusal_code=(
                        None
                        if outcome.refusal_code is None
                        else f"STORE_{outcome.refusal_code.value}"
                    ),
                )
            )
    before = _source_digests(prepared)
    try:
        after = _recheck_source_inputs(prepared)
        unchanged = before == after
    except _ActivationError:
        after = ()
        unchanged = False
        findings.append(
            ImportPreviewFinding(
                import_handle="discovery",
                status="would_refuse",
                refusal_code=ActivationRefusalCode.SOURCE_CHANGED.value,
            )
        )
    findings_tuple = tuple(sorted(findings, key=lambda item: item.import_handle))
    preview_digest = _preview_identity(
        config=config,
        schemas=schemas,
        imports=eligible,
        findings=findings_tuple,
    )
    target_status = _target_status(
        resolved.owner_workspace,
        preview_digest,
        config.max_discovery_entries,
    )
    if target_status in {"conflict", "corrupt"}:
        findings_tuple = (
            *findings_tuple,
            ImportPreviewFinding(
                import_handle="discovery",
                status="would_refuse",
                refusal_code=(
                    ActivationRefusalCode.TARGET_CONFLICT.value
                    if target_status == "conflict"
                    else ActivationRefusalCode.TARGET_CORRUPT.value
                ),
            ),
        )
    would_register = sum(item.status == "would_register" for item in findings_tuple)
    would_reuse = sum(item.status == "would_reuse" for item in findings_tuple)
    would_refuse = sum(item.status == "would_refuse" for item in findings_tuple)
    activatable = (
        bool(eligible)
        and would_refuse == 0
        and unchanged
        and target_status in {"absent", "exact_activation"}
    )
    preview = ActivationPreview(
        workspace_id=config.workspace_id,
        activatable=activatable,
        target_status=cast(
            Literal["absent", "exact_activation", "conflict", "corrupt"],
            target_status,
        ),
        manifests_discovered=len(manifests),
        would_register=would_register,
        would_reuse=would_reuse,
        would_refuse=would_refuse,
        findings=findings_tuple,
        schema_digests=tuple(sorted(schema.fingerprint() for schema in schemas)),
        licence_policy_digest=config.licence_policy.policy_digest,
        source_input_digests_before=before,
        source_input_digests_after=after,
        source_bytes_unchanged=unchanged,
        orphan_staging_handles=_orphan_handles(resolved.owner_workspace, preview_digest),
        preview_digest=preview_digest,
    )
    return _PreparedPreview(
        resolved=resolved,
        preview=preview,
        schemas=schemas,
        sources=sources,
        imports=tuple(sorted(eligible, key=lambda item: item.import_handle)),
    )


def _group_by_dataset(
    imports: Sequence[_PreparedImport],
) -> dict[str, list[_PreparedImport]]:
    grouped: dict[str, list[_PreparedImport]] = defaultdict(list)
    for item in imports:
        grouped[item.candidate.record.dataset_id].append(item)
    return grouped


def preview_activation(config: ActivationConfig) -> ActivationPreview | ActivationRefusal:
    """Validate and dry-run every selected import without creating the target."""

    try:
        return _prepare_preview(config).preview
    except _ActivationError as exc:
        return _refusal("preview", exc.code, exc.safe_message)
    except Exception:
        return _refusal(
            "preview",
            ActivationRefusalCode.CONFIG_INVALID,
            "activation preview failed closed before any target change",
        )


def _write_json_durable(path: Path, value: StoreModel) -> None:
    payload = (value.canonical_json() + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _copy_backup_for_restore(source: Path, drill_root: Path) -> None:
    drill_root.mkdir(mode=0o700, parents=True)
    for directory in (
        drill_root / "payloads",
        drill_root / "payloads" / "sha256",
        drill_root / "staging",
        drill_root / "backups",
    ):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copy2(source / "catalogue.sqlite", drill_root / "catalogue.sqlite")
    (drill_root / "catalogue.sqlite").chmod(0o600)
    source_payloads = source / "payloads" / "sha256"
    for payload in source_payloads.rglob("*.json"):
        relative = payload.relative_to(source_payloads)
        destination = drill_root / "payloads" / "sha256" / relative
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(payload, destination)
        destination.chmod(0o600)


def _verify_restore_drill(
    prepared: _PreparedPreview,
    backup: BackupReceipt,
    staged_root: Path,
) -> None:
    backup_root = staged_root / backup.backup_handle
    with tempfile.TemporaryDirectory(
        prefix=".historical-store-restore-",
        dir=prepared.resolved.owner_workspace,
    ) as temporary_name:
        drill_workspace = Path(temporary_name)
        drill_workspace.chmod(0o700)
        drill_root = drill_workspace / "historical-store"
        _copy_backup_for_restore(backup_root, drill_root)
        opened = SQLiteHistoricalStore.open(
            config=SQLiteStoreConfig(
                owner_workspace=drill_workspace,
                repository_root=prepared.resolved.repository_root,
            ),
            schemas=prepared.schemas,
            authoritative_sources=prepared.sources,
            licence_policy=prepared.resolved.public.licence_policy,
        )
        if isinstance(opened, PersistentStoreRefusal):
            raise _ActivationError(
                ActivationRefusalCode.RESTORE_REFUSED,
                "the isolated backup restore could not be opened safely",
            )
        try:
            recovery = opened.recovery_report()
            if not recovery.safe_to_open:
                raise _ActivationError(
                    ActivationRefusalCode.RESTORE_REFUSED,
                    "the isolated backup restore failed its recovery report",
                )
            for item in prepared.imports:
                expected = item.candidate.record
                observed = opened.get_dataset(expected.dataset_id, expected.payload_digest)
                if isinstance(observed, StoreRefusal) or observed != expected:
                    raise _ActivationError(
                        ActivationRefusalCode.RESTORE_REFUSED,
                        "the isolated backup restore did not reconcile every dataset",
                    )
        finally:
            opened.close()


def _verify_marker_backup(
    resolved: _ResolvedConfig,
    marker: ActivationMarker,
    activated_root: Path,
) -> None:
    backup_root = activated_root / marker.receipt.backup.backup_handle
    try:
        manifest_bytes = _read_private_file(backup_root / "manifest.json", _MARKER_MAX_BYTES)
        manifest = json.loads(manifest_bytes, parse_constant=_reject_nonfinite)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise _ActivationError(
            ActivationRefusalCode.RESTORE_REFUSED,
            "the marker-bound backup manifest could not be verified",
        ) from exc
    if (
        not isinstance(manifest, dict)
        or _digest_bytes(manifest_bytes) != marker.receipt.backup.backup_digest
        or manifest.get("catalogue_digest") != marker.receipt.backup.catalogue_digest
        or not isinstance(manifest.get("payloads"), list)
        or len(manifest["payloads"]) != marker.receipt.backup.payload_count
    ):
        raise _ActivationError(
            ActivationRefusalCode.RESTORE_REFUSED,
            "the marker-bound backup manifest conflicts with its activation receipt",
        )
    with tempfile.TemporaryDirectory(
        prefix=".historical-store-restore-",
        dir=resolved.owner_workspace,
    ) as temporary_name:
        drill_workspace = Path(temporary_name)
        drill_workspace.chmod(0o700)
        drill_root = drill_workspace / "historical-store"
        try:
            _copy_backup_for_restore(backup_root, drill_root)
        except OSError as exc:
            raise _ActivationError(
                ActivationRefusalCode.RESTORE_REFUSED,
                "the marker-bound backup could not be restored safely",
            ) from exc
        opened = SQLiteHistoricalStore.open(
            config=SQLiteStoreConfig(
                owner_workspace=drill_workspace,
                repository_root=resolved.repository_root,
            ),
            schemas=marker.schemas,
            authoritative_sources=marker.authoritative_sources,
            licence_policy=marker.licence_policy,
        )
        if isinstance(opened, PersistentStoreRefusal):
            raise _ActivationError(
                ActivationRefusalCode.RESTORE_REFUSED,
                "the marker-bound backup failed isolated catalogue replay",
            )
        try:
            recovery = opened.recovery_report()
            if not recovery.safe_to_open:
                raise _ActivationError(
                    ActivationRefusalCode.RESTORE_REFUSED,
                    "the marker-bound backup failed its recovery report",
                )
            for expected in marker.expected_datasets:
                observed = opened.get_dataset(expected.dataset_id, expected.payload_digest)
                if (
                    isinstance(observed, StoreRefusal)
                    or observed.fingerprint() != expected.record_digest
                ):
                    raise _ActivationError(
                        ActivationRefusalCode.RESTORE_REFUSED,
                        "the marker-bound backup failed dataset reconciliation",
                    )
        finally:
            opened.close()


def _stored_exact_retry(
    prepared: _PreparedPreview,
) -> ActivationReceipt | ActivationRefusal | None:
    target = prepared.resolved.owner_workspace / "historical-store"
    if not target.exists() and not target.is_symlink():
        return None
    try:
        _validate_private_tree(
            target,
            max_entries=prepared.resolved.public.max_discovery_entries,
        )
        marker, _ = _read_marker(target)
    except _ActivationError as exc:
        return _refusal("activate", exc.code, exc.safe_message)
    if marker.preview_digest != prepared.preview.preview_digest:
        return _refusal(
            "activate",
            ActivationRefusalCode.TARGET_CONFLICT,
            "an existing target belongs to a different activation",
        )
    expected = tuple(
        ExpectedDataset(
            dataset_id=item.candidate.record.dataset_id,
            record_digest=item.candidate.record.fingerprint(),
            payload_digest=item.candidate.record.payload_digest,
        )
        for item in prepared.imports
    )
    if (
        marker.schemas != prepared.schemas
        or marker.authoritative_sources != prepared.sources
        or marker.licence_policy != prepared.resolved.public.licence_policy
        or marker.expected_datasets != expected
    ):
        return _refusal(
            "activate",
            ActivationRefusalCode.TARGET_CORRUPT,
            "the existing activation marker conflicts with the confirmed import contracts",
        )
    opened = SQLiteHistoricalStore.open(
        config=SQLiteStoreConfig(
            owner_workspace=prepared.resolved.owner_workspace,
            repository_root=prepared.resolved.repository_root,
        ),
        schemas=marker.schemas,
        authoritative_sources=marker.authoritative_sources,
        licence_policy=marker.licence_policy,
    )
    if isinstance(opened, PersistentStoreRefusal):
        return _refusal(
            "activate",
            ActivationRefusalCode.TARGET_CORRUPT,
            "the existing exact activation failed catalogue integrity validation",
        )
    try:
        recovery = opened.recovery_report()
        if not recovery.safe_to_open:
            return _refusal(
                "activate",
                ActivationRefusalCode.TARGET_CORRUPT,
                "the existing exact activation failed its recovery report",
            )
        for item in prepared.imports:
            expected_record = item.candidate.record
            observed = opened.get_dataset(
                expected_record.dataset_id,
                expected_record.payload_digest,
            )
            if isinstance(observed, StoreRefusal) or observed != expected_record:
                return _refusal(
                    "activate",
                    ActivationRefusalCode.TARGET_CORRUPT,
                    "the existing exact activation failed dataset reconciliation",
                )
    finally:
        opened.close()
    try:
        _verify_marker_backup(prepared.resolved, marker, target)
    except Exception:
        return _refusal(
            "activate",
            ActivationRefusalCode.TARGET_CORRUPT,
            "the existing exact activation failed backup restore verification",
        )
    return marker.receipt.model_copy(update={"idempotent_retry": True})


def activate_store(
    config: ActivationConfig,
    *,
    expected_preview_digest: str,
    clock: Callable[[], datetime] | None = None,
    fault_hook: Callable[[str], None] | None = None,
) -> ActivationReceipt | ActivationRefusal:
    """Publish the exact confirmed preview after backup and restore verification."""

    try:
        prepared = _prepare_preview(config)
    except _ActivationError as exc:
        return _refusal("activate", exc.code, exc.safe_message)
    except Exception:
        return _refusal(
            "activate",
            ActivationRefusalCode.CONFIG_INVALID,
            "activation failed closed before target publication",
        )
    if expected_preview_digest != prepared.preview.preview_digest:
        return _refusal(
            "activate",
            ActivationRefusalCode.PREVIEW_DIGEST_MISMATCH,
            "owner confirmation does not match the current activation preview",
        )
    if not prepared.preview.activatable:
        return _refusal(
            "activate",
            ActivationRefusalCode.PREVIEW_NOT_ACTIVATABLE,
            "the current preview contains one or more refusals",
        )
    retry = _stored_exact_retry(prepared)
    if retry is not None:
        return retry
    owner = prepared.resolved.owner_workspace
    stage_workspace = owner / f".historical-store-activation-{prepared.preview.preview_digest[:16]}"
    target = owner / "historical-store"
    opened: SQLiteHistoricalStore | None = None
    try:
        try:
            stage_workspace.mkdir(mode=0o700, parents=False, exist_ok=False)
        except FileExistsError:
            pass
        else:
            stage_workspace.chmod(0o700)
        _harden_owned_staging_tree(
            stage_workspace,
            max_entries=config.max_discovery_entries,
        )
        opened_result = SQLiteHistoricalStore.open(
            config=SQLiteStoreConfig(
                owner_workspace=stage_workspace,
                repository_root=prepared.resolved.repository_root,
            ),
            schemas=prepared.schemas,
            authoritative_sources=prepared.sources,
            licence_policy=config.licence_policy,
        )
        if isinstance(opened_result, PersistentStoreRefusal):
            raise _ActivationError(
                ActivationRefusalCode.STORE_OPEN_REFUSED,
                "the staged aggregate catalogue could not be opened safely",
            )
        opened = opened_result
        _harden_owned_staging_tree(
            stage_workspace,
            max_entries=config.max_discovery_entries,
        )
        for item in prepared.imports:
            result = opened.register_dataset(item.candidate)
            if not isinstance(result, StoreReceipt):
                raise _ActivationError(
                    ActivationRefusalCode.REGISTRATION_REFUSED,
                    "a previewed dataset was refused during staged registration",
                )
        recovery = opened.recovery_report()
        if not recovery.safe_to_open or recovery.staged_file_count:
            raise _ActivationError(
                ActivationRefusalCode.RECOVERY_REFUSED,
                "the staged catalogue failed its clean recovery gate",
            )
        backup_result = opened.create_verified_backup("activation-baseline")
        if isinstance(backup_result, PersistentStoreRefusal):
            raise _ActivationError(
                ActivationRefusalCode.BACKUP_REFUSED,
                "the complete verified activation backup could not be created",
            )
        backup = backup_result
        staged_root = stage_workspace / "historical-store"
        _harden_owned_staging_tree(
            stage_workspace,
            max_entries=config.max_discovery_entries,
        )
        _verify_restore_drill(prepared, backup, staged_root)
        after = _recheck_source_inputs(prepared.imports)
        if after != prepared.preview.source_input_digests_before:
            raise _ActivationError(
                ActivationRefusalCode.SOURCE_CHANGED,
                "a selected source changed before target publication",
            )
        expected = tuple(
            ExpectedDataset(
                dataset_id=item.candidate.record.dataset_id,
                record_digest=item.candidate.record.fingerprint(),
                payload_digest=item.candidate.record.payload_digest,
            )
            for item in prepared.imports
        )
        now = (clock or (lambda: datetime.now(UTC)))()
        if now.tzinfo is None or now.utcoffset() is None:
            raise _ActivationError(
                ActivationRefusalCode.PUBLICATION_REFUSED,
                "the activation clock must return a timezone-aware timestamp",
            )
        receipt = ActivationReceipt(
            preview_digest=prepared.preview.preview_digest,
            workspace_id=config.workspace_id,
            activated_at_utc=now,
            datasets_registered=len(expected),
            datasets=expected,
            backup=backup,
            idempotent_retry=False,
        )
        marker = ActivationMarker(
            preview_digest=prepared.preview.preview_digest,
            schemas=prepared.schemas,
            authoritative_sources=prepared.sources,
            licence_policy=config.licence_policy,
            expected_datasets=expected,
            receipt=receipt,
        )
        _write_json_durable(staged_root / ACTIVATION_MARKER_NAME, marker)
        opened.close()
        opened = None
        if fault_hook is not None:
            fault_hook("before_publication")
        if target.exists() or target.is_symlink():
            raise _ActivationError(
                ActivationRefusalCode.TARGET_CONFLICT,
                "the final target appeared before atomic publication",
            )
        os.replace(staged_root, target)
        owner_descriptor = os.open(owner, os.O_RDONLY)
        try:
            os.fsync(owner_descriptor)
        finally:
            os.close(owner_descriptor)
        with suppress(OSError):
            stage_workspace.rmdir()
        return receipt
    except _ActivationError as exc:
        return _refusal("activate", exc.code, exc.safe_message)
    except Exception:
        return _refusal(
            "activate",
            ActivationRefusalCode.PUBLICATION_REFUSED,
            "activation stopped before atomic target publication",
        )
    finally:
        if opened is not None:
            opened.close()


def _open_activated_store(
    config: ActivationConfig,
) -> tuple[SQLiteHistoricalStore, ActivationMarker, str, _ResolvedConfig] | ActivationRefusal:
    try:
        resolved = _resolve_config(config, include_imports=False)
        target = resolved.owner_workspace / "historical-store"
        _validate_private_tree(target, max_entries=config.max_discovery_entries)
        marker, marker_digest = _read_marker(target)
        opened = SQLiteHistoricalStore.open(
            config=SQLiteStoreConfig(
                owner_workspace=resolved.owner_workspace,
                repository_root=resolved.repository_root,
            ),
            schemas=marker.schemas,
            authoritative_sources=marker.authoritative_sources,
            licence_policy=marker.licence_policy,
        )
        if isinstance(opened, PersistentStoreRefusal):
            return _refusal(
                "catalogue",
                ActivationRefusalCode.STORE_OPEN_REFUSED,
                "the activated catalogue could not be opened safely",
            )
        return opened, marker, marker_digest, resolved
    except _ActivationError as exc:
        return _refusal("catalogue", exc.code, exc.safe_message)


def catalogue_report(
    config: ActivationConfig,
    query: CatalogueQuery,
) -> ActivationCatalogueReport | ActivationRefusal:
    """Run one allowlisted catalogue query without exposing local paths."""

    result = _open_activated_store(config)
    if isinstance(result, ActivationRefusal):
        return result
    opened, _, marker_digest, _ = result
    try:
        datasets = opened.query_catalogue(query)
        return ActivationCatalogueReport(
            marker_digest=marker_digest,
            query=query,
            datasets=datasets,
            result_count=len(datasets),
        )
    except Exception:
        return _refusal(
            "catalogue",
            ActivationRefusalCode.QUERY_INVALID,
            "the allowlisted catalogue query failed closed",
        )
    finally:
        opened.close()


def integrity_report(config: ActivationConfig) -> ActivationIntegrityReport:
    """Reconcile marker, SQLite recovery and every expected dataset binding."""

    result = _open_activated_store(config)
    if isinstance(result, ActivationRefusal):
        try:
            resolved = _resolve_config(config, include_imports=False)
            orphans = _orphan_handles(resolved.owner_workspace)
        except _ActivationError:
            orphans = ()
        return ActivationIntegrityReport(
            status="refused",
            expected_dataset_count=0,
            reconciled_dataset_count=0,
            backup_restore_verified=False,
            orphan_staging_handles=orphans,
            refusal_code=result.code,
            safe_to_use=False,
        )
    opened, marker, marker_digest, resolved = result
    recovery: RecoveryReport | None = None
    reconciled = 0
    backup_verified = False
    refusal_code: ActivationRefusalCode | None = None
    try:
        recovery = opened.recovery_report()
        for expected in marker.expected_datasets:
            observed = opened.get_dataset(expected.dataset_id, expected.payload_digest)
            if (
                isinstance(observed, StoreRefusal)
                or observed.fingerprint() != expected.record_digest
            ):
                refusal_code = ActivationRefusalCode.RECOVERY_REFUSED
                break
            reconciled += 1
        if refusal_code is None:
            try:
                _verify_marker_backup(
                    resolved, marker, resolved.owner_workspace / "historical-store"
                )
            except _ActivationError:
                refusal_code = ActivationRefusalCode.BACKUP_REFUSED
            else:
                backup_verified = True
        safe = (
            recovery.safe_to_open
            and reconciled == len(marker.expected_datasets)
            and backup_verified
            and refusal_code is None
        )
        return ActivationIntegrityReport(
            status="ok" if safe else "corrupt",
            marker_digest=marker_digest,
            recovery=recovery,
            expected_dataset_count=len(marker.expected_datasets),
            reconciled_dataset_count=reconciled,
            backup_restore_verified=backup_verified,
            orphan_staging_handles=_orphan_handles(resolved.owner_workspace),
            refusal_code=refusal_code,
            safe_to_use=safe,
        )
    finally:
        opened.close()


def load_activation_config(path: Path) -> ActivationConfig | ActivationRefusal:
    """Load one private, uncommitted CLI configuration without echoing paths."""

    try:
        _reject_symlink_components(path)
        raw = _read_private_file(path.expanduser().resolve(strict=True), _CONFIG_MAX_BYTES)
        local = _LocalConfigModel.model_validate_json(raw, strict=True)
        config = ActivationConfig(
            workspace_id=local.workspace_id,
            owner_workspace=Path(local.owner_workspace),
            repository_root=Path(local.repository_root),
            import_roots=tuple(Path(value) for value in local.import_roots),
            licence_policy=local.licence_policy,
            max_manifest_bytes=local.max_manifest_bytes,
            max_source_record_bytes=local.max_source_record_bytes,
            max_artifact_bytes=local.max_artifact_bytes,
            max_manifests=local.max_manifests,
            max_discovery_entries=local.max_discovery_entries,
            max_depth=local.max_depth,
        )
        repository = config.repository_root.expanduser().resolve(strict=True)
        config_path = path.expanduser().resolve(strict=True)
        if _contained(config_path, repository):
            raise _ActivationError(
                ActivationRefusalCode.CONFIG_INVALID,
                "the private activation config must remain outside the repository",
            )
        return config
    except _ActivationError as exc:
        return _refusal("load_config", exc.code, exc.safe_message)
    except (OSError, ValidationError, ValueError):
        return _refusal(
            "load_config",
            ActivationRefusalCode.CONFIG_INVALID,
            "the private activation config failed strict validation",
        )
