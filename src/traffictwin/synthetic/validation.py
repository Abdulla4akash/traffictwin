"""Standalone synthetic bundle verification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from traffictwin.ingestion.bundle import validate_bundle


@dataclass(frozen=True)
class SyntheticVerificationResult:
    """Result of checking generated synthetic artifacts."""

    path: Path
    checked_bundle_count: int
    accepted_bundle_count: int
    rejected_bundle_count: int
    messages: list[str]

    @property
    def ok(self) -> bool:
        """Return whether every discovered bundle is accepted."""

        return self.checked_bundle_count > 0 and self.rejected_bundle_count == 0


def verify_synthetic_path(path: str | Path) -> SyntheticVerificationResult:
    """Validate one synthetic bundle or every bundle under a directory."""

    root = Path(path)
    bundle_dirs = _bundle_dirs(root)
    checked = 0
    accepted = 0
    rejected = 0
    messages: list[str] = []
    for bundle in bundle_dirs:
        result = validate_bundle(bundle)
        checked += 1
        status = result.report.status.value
        if result.report.may_import:
            accepted += 1
        else:
            rejected += 1
        synthetic = result.manifest is not None and result.manifest.environment.name == "synthetic"
        if not synthetic:
            rejected += 1 if result.report.may_import else 0
            accepted -= 1 if result.report.may_import else 0
            messages.append(f"{bundle}: environment is not labelled synthetic")
        messages.append(f"{bundle}: {status}")
    return SyntheticVerificationResult(
        path=root,
        checked_bundle_count=checked,
        accepted_bundle_count=accepted,
        rejected_bundle_count=rejected,
        messages=messages,
    )


def _bundle_dirs(root: Path) -> list[Path]:
    if (root / "manifest.yaml").exists():
        return [root]
    if (root / "bundles").exists():
        return sorted(path.parent for path in (root / "bundles").rglob("manifest.yaml"))
    return sorted(path.parent for path in root.rglob("manifest.yaml"))
