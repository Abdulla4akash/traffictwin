"""Standalone release metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from pydantic import BaseModel, ConfigDict


class ReleaseMetadata(BaseModel):
    """Release metadata shown in docs and release checks."""

    model_config = ConfigDict(extra="forbid")

    package_name: str = "traffictwin"
    version: str
    release_label: str = "v0.6.0 research prototype"
    licence_status: str = "Licence not yet specified."
    production_status: str = "Research prototype; not production-ready."


def current_release_metadata() -> ReleaseMetadata:
    """Return installed package metadata with a source-tree fallback."""

    try:
        package_version = version("traffictwin")
    except PackageNotFoundError:
        package_version = "0.6.0"
    return ReleaseMetadata(version=package_version)
