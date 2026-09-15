"""Reproduce the compact results packet from exact, tracked historical bytes.

This reads Git objects and writes only the two packaged research resources. It
does not run an evaluator, edit evidence, or inspect private raw arrays.
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

SOURCE_COMMIT = "1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8"
STUDY_ID = "joint_confirmation_2026-09-08"
ARMS = ("ingress_dla", "dla", "per_task_dla", "causal_round_robin")


def main() -> None:
    """Write deterministic original-byte resources from the frozen Git objects."""
    root = Path(__file__).resolve().parents[1]
    names = [
        "confirmation/SEALED_EXECUTION.json",
        *(
            f"evidence/{name}"
            for name in (
                "ANALYSIS.json",
                "BLOCK_CONTROLS.json",
                "CELL_RESULTS.csv",
                "CELL_RESULTS.json",
                "PAIRED_EFFECTS.csv",
                "CLEAN_VERIFICATION.json",
                "COMPLETE.json",
            )
        ),
        *(
            f"evidence/cells/block_{block:02d}_{arm}/{name}"
            for block in range(8)
            for arm in ARMS
            for name in ("VALIDATED.json", "summary.json")
        ),
    ]
    files = {
        name: subprocess.run(  # noqa: S603 — fixed Git executable/commit; no shell
            ["git", "show", f"{SOURCE_COMMIT}:docs/dissertation/{STUDY_ID}/{name}"],  # noqa: S607
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        for name in sorted(names)
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    packet = buffer.getvalue()
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    manifest = {
        "schema": "traffictwin_frozen_dissertation_results_v1",
        "study_id": STUDY_ID,
        "source_commit": SOURCE_COMMIT,
        "seal_sha256": hashes["confirmation/SEALED_EXECUTION.json"],
        "packet_sha256": hashlib.sha256(packet).hexdigest(),
        "files": hashes,
        "validation_scope": (
            "Original compact evidence bytes; raw arrays are not included or checked"
        ),
    }
    destination = root / "src/traffictwin/resources/research"
    (destination / "joint_confirmation_results.zip").write_bytes(packet)
    (destination / "joint_confirmation_results_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(files)} original files, {len(packet)} packet bytes")


if __name__ == "__main__":
    main()
