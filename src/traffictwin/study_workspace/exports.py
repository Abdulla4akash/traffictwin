"""Portable export helpers for the Study Workspace manifest.

No local paths or secrets are included in portable artifacts.
"""

from __future__ import annotations

import csv
import io
import json

from traffictwin.study_workspace.models import StudyWorkspaceManifest, WorkspaceArtifactRef
from traffictwin.study_workspace.service import fingerprint_manifest


def export_workspace_json(manifest: StudyWorkspaceManifest) -> str:
    """Return canonical portable JSON for one workspace manifest."""
    # Use canonical_dict to ensure deterministic, path-free export.
    canonical = manifest.canonical_dict()
    # Add fingerprint as explicit field for convenience (not part of canonical identity)
    canonical_copy = dict(canonical)
    canonical_copy["workspace_fingerprint"] = fingerprint_manifest(manifest)
    return json.dumps(
        canonical_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def export_workspace_pretty_json(manifest: StudyWorkspaceManifest) -> str:
    """Return pretty JSON for human review."""
    payload = manifest.canonical_dict()
    payload["workspace_fingerprint"] = fingerprint_manifest(manifest)
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def export_artifacts_csv(manifest: StudyWorkspaceManifest) -> str:
    """Return CSV export of artifact inventory (tabular, meaningful)."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

    header = [
        "fingerprint",
        "kind",
        "label",
        "schema_version",
        "standing",
        "compatibility_standing",
        "availability",
        "parent_fingerprint",
        "reason",
    ]
    # Sanitise header already safe
    writer.writerow(header)

    for art in sorted(manifest.artifacts, key=lambda a: a.fingerprint):
        # Sanitise formula injection: prefix with single quote if starts with = + - @
        row = [
            _csv_safe(art.fingerprint),
            _csv_safe(art.kind.value),
            _csv_safe(art.label),
            _csv_safe(art.schema_version),
            _csv_safe(art.standing.value),
            _csv_safe(art.compatibility_standing.value),
            _csv_safe(art.availability.value),
            _csv_safe(art.parent_fingerprint or ""),
            _csv_safe(art.reason or ""),
        ]
        writer.writerow(row)

    return output.getvalue()


def _csv_safe(value: str) -> str:
    stripped = value.lstrip()
    if stripped and stripped[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def export_lineage_csv(manifest: StudyWorkspaceManifest) -> str:
    """Return bounded relation table of parent linkages."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    header = [  # noqa: E501 - tabular header list, keep one line per logical column
        "child_fingerprint",
        "child_kind",
        "child_label",
        "parent_fingerprint",
        "parent_kind",
        "parent_label",
    ]
    writer.writerow(header)

    fp_to_ref: dict[str, WorkspaceArtifactRef] = {a.fingerprint: a for a in manifest.artifacts}

    for art in sorted(manifest.artifacts, key=lambda a: a.fingerprint):
        if art.parent_fingerprint is None:
            continue
        parent = fp_to_ref.get(art.parent_fingerprint)
        parent_kind = parent.kind.value if parent else "unknown"
        parent_label = parent.label if parent else "unavailable"
        writer.writerow(
            [
                _csv_safe(art.fingerprint),
                _csv_safe(art.kind.value),
                _csv_safe(art.label),
                _csv_safe(art.parent_fingerprint),
                _csv_safe(parent_kind),
                _csv_safe(parent_label),
            ]
        )

    return output.getvalue()
