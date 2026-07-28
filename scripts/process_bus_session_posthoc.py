#!/usr/bin/env python3
"""Measure one already-captured BODS session without acquiring anything.

The inclusive snapshot-id bounds define the declared session. Every selected
quarantine is verified by the accepted session-identity library, one fresh salt
is generated in process, and only aggregate cadence/progression artifacts plus
a processing receipt are written. The salt, session tokens, and raw vehicle
references are never persisted or printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from pathlib import Path
from typing import Any

from traffictwin.integration.manchester.bods_session_identity import (
    SESSION_IDENTITY_POLICY_ID,
    SessionExtractionResult,
    extract_session_observations,
    measure_session_cadence,
    measure_session_progression,
    measurement_to_json,
)

_SESSION_LABEL = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_BODS_SNAPSHOT_PREFIX = "bods_siri_vm-"
_CADENCE_NAME = "bus_cadence_probe_measurement.json"
_PROGRESSION_NAME = "bus_session_progression_measurement.json"
_RECEIPT_NAME = "posthoc_session_receipt.json"


class PosthocSessionError(RuntimeError):
    """Raised when an already-captured session cannot be reduced safely."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--session-label", required=True)
    parser.add_argument("--first-snapshot-id", required=True)
    parser.add_argument("--last-snapshot-id", required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Defaults to <workspace>/session-records; must stay inside the workspace.",
    )
    arguments = parser.parse_args(argv)
    try:
        output = process_session(
            arguments.workspace,
            session_label=arguments.session_label,
            first_snapshot_id=arguments.first_snapshot_id,
            last_snapshot_id=arguments.last_snapshot_id,
            output_root=arguments.output_root,
        )
    except PosthocSessionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"measured {arguments.session_label}; aggregate workspace view: {output}")
    return 0


def process_session(
    workspace: Path,
    *,
    session_label: str,
    first_snapshot_id: str,
    last_snapshot_id: str,
    output_root: Path | None = None,
) -> Path:
    """Reduce one explicit, already-captured session to aggregate artifacts."""

    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise PosthocSessionError(f"workspace does not exist: {workspace}")
    if _SESSION_LABEL.fullmatch(session_label) is None:
        raise PosthocSessionError(
            "session label must contain only lowercase letters, digits, hyphens"
        )
    root = (workspace / "session-records" if output_root is None else output_root).resolve()
    if not root.is_relative_to(workspace):
        raise PosthocSessionError("output root must stay inside the declared workspace")
    target = root / session_label
    if target.exists():
        raise PosthocSessionError(
            f"session output already exists and will not be overwritten: {target}"
        )

    snapshot_ids = select_snapshot_ids(
        workspace / "quarantine",
        first_snapshot_id=first_snapshot_id,
        last_snapshot_id=last_snapshot_id,
    )
    session_salt = secrets.token_bytes(32)
    results: list[SessionExtractionResult] = [
        extract_session_observations(workspace, snapshot_id, session_salt=session_salt)
        for snapshot_id in snapshot_ids
    ]
    cadence = measure_session_cadence(results)
    progression = measure_session_progression(results)
    cadence_json = measurement_to_json(cadence) + "\n"
    progression_json = _json(progression.model_dump(mode="json")) + "\n"

    manchester = target / "manchester"
    manchester.mkdir(parents=True)
    cadence_path = manchester / _CADENCE_NAME
    progression_path = manchester / _PROGRESSION_NAME
    cadence_path.write_text(cadence_json, encoding="utf-8")
    progression_path.write_text(progression_json, encoding="utf-8")
    promoted = sum((workspace / "accepted" / snapshot_id).is_dir() for snapshot_id in snapshot_ids)
    receipt = {
        "acquisition_performed": False,
        "aggregates_only": True,
        "cadence_sha256": _sha256(cadence_json),
        "first_snapshot_id": snapshot_ids[0],
        "fresh_in_process_salt": True,
        "last_snapshot_id": snapshot_ids[-1],
        "policy_id": SESSION_IDENTITY_POLICY_ID,
        "posthoc_processing": True,
        "progression_sha256": _sha256(progression_json),
        "promoted_snapshot_count": promoted,
        "quarantine_only_snapshot_count": len(snapshot_ids) - promoted,
        "raw_identifiers_published": False,
        "salt_persisted": False,
        "schema_version": "1.0",
        "session_label": session_label,
        "snapshot_count": len(snapshot_ids),
    }
    (target / _RECEIPT_NAME).write_text(_json(receipt) + "\n", encoding="utf-8")
    return target


def select_snapshot_ids(
    quarantine: Path,
    *,
    first_snapshot_id: str,
    last_snapshot_id: str,
) -> tuple[str, ...]:
    """Select an inclusive, exact range from already-present BODS quarantines."""

    if not quarantine.is_dir():
        raise PosthocSessionError(f"quarantine directory does not exist: {quarantine}")
    for label, value in (
        ("first snapshot id", first_snapshot_id),
        ("last snapshot id", last_snapshot_id),
    ):
        if not value.startswith(_BODS_SNAPSHOT_PREFIX) or "/" in value or "\\" in value:
            raise PosthocSessionError(f"{label} is not a safe BODS snapshot id")
    if first_snapshot_id > last_snapshot_id:
        raise PosthocSessionError("first snapshot id must not follow the last snapshot id")
    available = tuple(
        sorted(
            path.name
            for path in quarantine.iterdir()
            if path.is_dir() and path.name.startswith(_BODS_SNAPSHOT_PREFIX)
        )
    )
    if first_snapshot_id not in available or last_snapshot_id not in available:
        raise PosthocSessionError("both exact snapshot bounds must exist in quarantine")
    selected = tuple(
        snapshot_id
        for snapshot_id in available
        if first_snapshot_id <= snapshot_id <= last_snapshot_id
    )
    if len(selected) < 2:
        raise PosthocSessionError("a session needs at least two captured snapshots")
    return selected


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)


if __name__ == "__main__":
    raise SystemExit(main())
