"""Bounded atomic publication for local Manchester map scenes.

Historical/latest publication consumes only explicit MAN-08 layer requests and performs
no acquisition, parsing, projection, joining, metric calculation, or network access.
The shared file boundary also admits an already-built live scene, allowing MAN-05 to
reuse one path/size/symlink/atomicity implementation.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.map_layers import (
    ManchesterMapScene,
    MapLayerRequest,
    MapLayerStatus,
    MapMode,
    build_map_layer,
    build_map_scene,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterSnapshotModel,
    sha256_hex,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

MANCHESTER_SCENE_PUBLICATION_SCHEMA_VERSION = "1.0"
MANCHESTER_SCENE_PUBLICATION_METHOD_VERSION = "manchester-scene-publication-1.0"
MANCHESTER_SCENE_PUBLICATION_CAPABILITY_ID = "MAN-08"
MANCHESTER_SCENE_MAX_BYTES = 8 * 1024 * 1024

HistoricalSceneMode: TypeAlias = Literal["historical_replay", "latest_available"]
SceneRelativePath: TypeAlias = Literal[
    "manchester/scenes/historical_replay.json",
    "manchester/scenes/latest_available.json",
    "manchester/scenes/live_vehicles.json",
]

_SCENE_RELATIVE_PATHS: dict[MapMode, Path] = {
    "historical_replay": Path("manchester/scenes/historical_replay.json"),
    "latest_available": Path("manchester/scenes/latest_available.json"),
    "live_vehicles": Path("manchester/scenes/live_vehicles.json"),
}


class ManchesterScenePublicationError(RuntimeError):
    """Display-safe local scene-publication failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterScenePublicationRequest(ManchesterSnapshotModel):
    """Canonical historical/latest layer inventory; no arbitrary path or URL."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-scene-publication-1.0"] = "manchester-scene-publication-1.0"
    mode: HistoricalSceneMode
    layer_requests: tuple[MapLayerRequest, ...] = Field(min_length=1, max_length=12)
    publication_target: Literal["isolated_v0_7_local_workspace"] = "isolated_v0_7_local_workspace"
    replacement_policy: Literal["atomic_replace_after_complete_validation"] = (
        "atomic_replace_after_complete_validation"
    )
    source_fusion_performed: Literal[False] = False
    external_network_required: Literal[False] = False
    public_export_requested: Literal[False] = False

    @model_validator(mode="after")
    def validate_request(self) -> ManchesterScenePublicationRequest:
        layer_ids = [request.layer_id for request in self.layer_requests]
        if layer_ids != sorted(set(layer_ids)):
            raise ValueError("layer requests must have sorted unique IDs")
        if any(request.mode != self.mode for request in self.layer_requests):
            raise ValueError("every layer request must match the scene mode")
        if any(request.source == "bods_siri_vm" for request in self.layer_requests):
            raise ValueError("BODS vehicle positions use the controlled live-scene workflow")
        return self


class ManchesterSceneFilePublication(ManchesterSnapshotModel):
    """Filesystem evidence returned by the single atomic scene boundary."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-scene-publication-1.0"] = "manchester-scene-publication-1.0"
    mode: MapMode
    relative_path: SceneRelativePath
    scene_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=1, le=MANCHESTER_SCENE_MAX_BYTES)
    replaced_existing: bool
    atomic_replace_completed: Literal[True] = True
    local_file_mode: Literal["0600"] = "0600"
    symlink_followed: Literal[False] = False
    public_export_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_publication(self) -> ManchesterSceneFilePublication:
        if self.relative_path != _relative_path_text(self.mode):
            raise ValueError("scene publication path must match its mode")
        return self


class ManchesterScenePublicationReceipt(ManchesterSnapshotModel):
    """Self-validating request-to-scene-to-file publication receipt."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-scene-publication-1.0"] = "manchester-scene-publication-1.0"
    request: ManchesterScenePublicationRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scene: ManchesterMapScene
    scene_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_publication: ManchesterSceneFilePublication
    layer_count: int = Field(ge=1, le=12)
    visible_layer_count: int = Field(ge=0, le=12)
    scene_status: MapLayerStatus
    private_layer_present: bool
    cross_source_join_performed: Literal[False] = False
    cross_scope_totals_available: Literal[False] = False
    public_export_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_receipt(self) -> ManchesterScenePublicationReceipt:
        expected_scene = _build_scene(self.request)
        scene_bytes = expected_scene.canonical_json().encode("utf-8")
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint must bind the embedded request")
        if self.scene != expected_scene or self.scene_fingerprint != expected_scene.fingerprint():
            raise ValueError("scene and fingerprint must be re-derived from the request")
        if self.file_publication.mode != self.request.mode:
            raise ValueError("file publication mode must match the request")
        if self.file_publication.scene_fingerprint != expected_scene.fingerprint():
            raise ValueError("file publication must bind the derived scene")
        if self.file_publication.file_sha256 != sha256_hex(scene_bytes):
            raise ValueError("file hash must bind the canonical scene bytes")
        if self.file_publication.byte_size != len(scene_bytes):
            raise ValueError("file size must match the canonical scene bytes")
        if self.layer_count != len(expected_scene.layers):
            raise ValueError("layer count must match the derived scene")
        if self.visible_layer_count != len(expected_scene.visible_layer_ids):
            raise ValueError("visible-layer count must match the derived scene")
        if self.scene_status != expected_scene.status:
            raise ValueError("scene status must match the derived scene")
        expected_private = any(
            layer.request.publication_class == ManchesterPublicationClass.PRIVATE
            for layer in expected_scene.layers
        )
        if self.private_layer_present != expected_private:
            raise ValueError("private-layer flag must match the scene inventory")
        return self


def publish_historical_scene(
    workspace_root: str | Path,
    request: ManchesterScenePublicationRequest,
) -> ManchesterScenePublicationReceipt:
    """Build and atomically publish one historical/latest local scene."""

    scene = _build_scene(request)
    publication = publish_map_scene_file(workspace_root, scene)
    return ManchesterScenePublicationReceipt(
        request=request,
        request_fingerprint=request.fingerprint(),
        scene=scene,
        scene_fingerprint=scene.fingerprint(),
        file_publication=publication,
        layer_count=len(scene.layers),
        visible_layer_count=len(scene.visible_layer_ids),
        scene_status=scene.status,
        private_layer_present=any(
            layer.request.publication_class == ManchesterPublicationClass.PRIVATE
            for layer in scene.layers
        ),
    )


def publish_map_scene_file(
    workspace_root: str | Path,
    scene: ManchesterMapScene,
) -> ManchesterSceneFilePublication:
    """Publish canonical bytes for one already-validated scene of any MAN-08 mode."""

    workspace = _validated_v07_workspace(workspace_root)
    payload = scene.canonical_json().encode("utf-8")
    if not payload or len(payload) > MANCHESTER_SCENE_MAX_BYTES:
        raise ManchesterScenePublicationError(
            "SCENE_SIZE_REFUSED",
            "the scene is empty or exceeds the bounded local display size",
        )
    scene_directory = _prepare_scene_directory(workspace)
    target = scene_directory / _SCENE_RELATIVE_PATHS[scene.mode].name
    _validate_target(workspace, target)
    replaced_existing = target.exists()
    _atomic_replace(target, payload)
    return ManchesterSceneFilePublication(
        mode=scene.mode,
        relative_path=_relative_path_text(scene.mode),
        scene_fingerprint=scene.fingerprint(),
        file_sha256=sha256_hex(payload),
        byte_size=len(payload),
        replaced_existing=replaced_existing,
    )


def _build_scene(request: ManchesterScenePublicationRequest) -> ManchesterMapScene:
    layers = tuple(build_map_layer(layer_request) for layer_request in request.layer_requests)
    return build_map_scene(request.mode, layers)


def _validated_v07_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise ManchesterScenePublicationError(
            "WORKSPACE_INVALID",
            "configure a valid isolated v0.7 workspace before publishing a scene",
        ) from exc
    return workspace.resolve(strict=True)


def _validate_target(workspace: Path, target: Path) -> None:
    scene_directory = target.parent
    if scene_directory.is_symlink() or not scene_directory.is_dir():
        raise ManchesterScenePublicationError(
            "SCENE_PATH_REFUSED",
            "the scene directory is not a safe local workspace directory",
        )
    try:
        resolved_directory = scene_directory.resolve(strict=True)
    except OSError as exc:
        raise ManchesterScenePublicationError(
            "SCENE_PATH_REFUSED",
            "the scene directory could not be resolved safely",
        ) from exc
    if not resolved_directory.is_relative_to(workspace):
        raise ManchesterScenePublicationError(
            "SCENE_PATH_REFUSED",
            "the scene directory escaped the configured workspace",
        )
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ManchesterScenePublicationError(
            "SCENE_PATH_REFUSED",
            "the scene target is not a safe regular file",
        )


def _prepare_scene_directory(workspace: Path) -> Path:
    current = workspace
    for name in ("manchester", "scenes"):
        candidate = current / name
        if candidate.is_symlink():
            raise ManchesterScenePublicationError(
                "SCENE_PATH_REFUSED",
                "the scene directory is not a safe local workspace directory",
            )
        if candidate.exists():
            if not candidate.is_dir():
                raise ManchesterScenePublicationError(
                    "SCENE_PATH_REFUSED",
                    "the scene directory is not a safe local workspace directory",
                )
        else:
            try:
                candidate.mkdir(mode=0o700)
            except OSError as exc:
                raise ManchesterScenePublicationError(
                    "SCENE_PATH_REFUSED",
                    "the scene directory could not be created safely",
                ) from exc
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ManchesterScenePublicationError(
                "SCENE_PATH_REFUSED",
                "the scene directory could not be resolved safely",
            ) from exc
        if not resolved.is_relative_to(workspace):
            raise ManchesterScenePublicationError(
                "SCENE_PATH_REFUSED",
                "the scene directory escaped the configured workspace",
            )
        current = candidate
    return current


def _atomic_replace(target: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.stem}-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, target)
        directory_descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError as exc:
        raise ManchesterScenePublicationError(
            "SCENE_PUBLICATION_FAILED",
            "the validated scene could not be published atomically",
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)


def _relative_path_text(mode: MapMode) -> SceneRelativePath:
    value = _SCENE_RELATIVE_PATHS[mode].as_posix()
    if value == "manchester/scenes/historical_replay.json":
        return "manchester/scenes/historical_replay.json"
    if value == "manchester/scenes/latest_available.json":
        return "manchester/scenes/latest_available.json"
    return "manchester/scenes/live_vehicles.json"
