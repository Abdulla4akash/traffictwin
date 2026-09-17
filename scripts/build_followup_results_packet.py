"""Package original follow-up evidence bytes without executing archived code."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

SOURCE_COMMIT = "fe8c8d9e4f725665508e47e61dc6e3286d005450"
STUDY_ID = "followups_2026-09-15"
NAMES = (
    "ANALYSIS.json",
    "CELL_RESULTS.csv",
    "PAIRED_EFFECTS.csv",
    "RESULTS.md",
    "FINDINGS.md",
    "PROTOCOL.md",
    "GUARD_AMENDMENT.md",
    "evidence/EXECUTION_SEAL.json",
    "evidence/FINAL_ANALYSIS_AUDIT.json",
    "evidence/BASELINE.json",
    "runs/COMPLETE.json",
)


def main() -> None:
    """Reproduce a deterministic packet from the frozen repository identity."""
    root = Path(__file__).resolve().parents[1]
    originals = {
        name: subprocess.run(  # noqa: S603 — fixed Git objects; no shell or research execution
            ["git", "show", f"{SOURCE_COMMIT}:docs/dissertation/{STUDY_ID}/{name}"],  # noqa: S607
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        for name in sorted(NAMES)
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in originals.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    packet = buffer.getvalue()
    manifest = {
        "schema": "traffictwin_frozen_followup_results_v1",
        "study_id": STUDY_ID,
        "repository_commit": SOURCE_COMMIT,
        "execution_source_commit": json.loads(originals["evidence/EXECUTION_SEAL.json"])[
            "source_commit"
        ],
        "packet_sha256": hashlib.sha256(packet).hexdigest(),
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in originals.items()},
        "validation_scope": "Original compact evidence and historical audit; raw arrays excluded",
    }
    destination = root / "src/traffictwin/resources/research"
    (destination / "followup_results.zip").write_bytes(packet)
    (destination / "followup_results_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(originals)} original files, {len(packet)} packet bytes")


if __name__ == "__main__":
    main()
