"""Directory and ZIP bundle loading."""

from __future__ import annotations

import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


class BundleLoadError(ValueError):
    """Raised when a bundle cannot be loaded safely."""


@dataclass
class BundleWorkspace:
    """A temporary or direct workspace for an imported bundle."""

    root: Path
    source: Path
    is_temporary: bool = False
    _temporary_directory: tempfile.TemporaryDirectory[str] | None = None

    def cleanup(self) -> None:
        """Clean up temporary extracted files."""

        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()

    def __enter__(self) -> BundleWorkspace:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.cleanup()


def open_bundle(path: str | Path, *, max_uncompressed_bytes: int = 10_000_000) -> BundleWorkspace:
    """Open a directory or ZIP bundle."""

    source = Path(path)
    if source.is_dir():
        return BundleWorkspace(root=source, source=source)
    if source.is_file() and source.suffix.lower() == ".zip":
        return _open_zip_bundle(source, max_uncompressed_bytes=max_uncompressed_bytes)
    msg = f"bundle path must be a directory or .zip archive: {source}"
    raise BundleLoadError(msg)


def _open_zip_bundle(source: Path, *, max_uncompressed_bytes: int) -> BundleWorkspace:
    temporary_directory = tempfile.TemporaryDirectory(prefix="traffictwin-bundle-")
    destination = Path(temporary_directory.name)
    try:
        with zipfile.ZipFile(source) as archive:
            total_size = 0
            for info in archive.infolist():
                _validate_zip_member(info)
                total_size += info.file_size
                if total_size > max_uncompressed_bytes:
                    raise BundleLoadError("zip bundle exceeds maximum uncompressed size")
            for info in archive.infolist():
                target = destination / info.filename
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source_file, target.open("wb") as target_file:
                    shutil.copyfileobj(source_file, target_file)
    except Exception:
        temporary_directory.cleanup()
        raise
    _remove_zip_directory_entries(destination)
    return BundleWorkspace(
        root=destination,
        source=source,
        is_temporary=True,
        _temporary_directory=temporary_directory,
    )


def _validate_zip_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    path = Path(name)
    if path.is_absolute() or name.startswith("/") or ".." in path.parts:
        msg = f"unsafe zip path: {name}"
        raise BundleLoadError(msg)
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        msg = f"zip symlink entries are not supported: {name}"
        raise BundleLoadError(msg)


def _remove_zip_directory_entries(destination: Path) -> None:
    for path in sorted(destination.rglob("__MACOSX"), reverse=True):
        if path.is_dir():
            shutil.rmtree(path)
