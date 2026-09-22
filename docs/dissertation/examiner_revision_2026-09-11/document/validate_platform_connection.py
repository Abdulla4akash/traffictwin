"""Authenticate the four authorised platform/abstract edits before older checks."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = "docs/dissertation/examiner_revision_2026-09-11"
PLATFORM_BASELINE = "b3b8dbceb07bd28f6743cf3595edacdfb61facdc"
PLATFORM_BASELINE_SHA256 = "5fe0b6dc38c3fde1282affb502ea72d650ef0ea59f59c741086a333a962258cc"
PLATFORM_INTEGRATION_BASE = "bdab52af92546658d3253e6ae11855e85342df0f"
PLATFORM_LEDGER_SHA256 = "9290b8653aaec22cf15cb33065e3e2303f09cda898c05b72bf45f78bb4aa5aef"
PACKET_SHA256 = "b99351b9ced2bb0cb3bb509c3ada32250b9450028893cc29e24f01a26c6b4d51"
PINNED_FILES = {
    "assets/traffictwin_results_workflow.png": (
        "3d0a0142cbc1dab5de8bf594239b0d18351ebe60f2459f9dfd66e91e0e5af606"
    ),
    "evidence/PLATFORM_RESULTS_CAPTURE.json": (
        "3ff41bb6d2ee11f5dfac2f5e8bcfb4c827faa4024de3d0367bb56d10f9479849"
    ),
    "evidence/TRAFFICTWIN_IMPORT_CHECK.json": (
        "c134fe18706878a2852f312978567a8c8f13a740bec950bb070778ba6093ea3c"
    ),
    "evidence/ABSTRACT_SCALE_UPDATE.json": (
        "d7c3be27b5077d2c94d4acfa3b6856534ee9f6520ea2c0f0a13bf5447b4b8e78"
    ),
    "evidence/BROWSER_CHECK.json": (
        "155ec318c5181c047bc8e40868cf75c550a8173c5244f8b0f466477e93cd67f5"
    ),
}


def restore_platform_connection(
    root: Path, here: Path, revised: str, *, historical_counts: dict | None = None
) -> tuple[str, dict[str, bool]]:
    """Recover b3b8dbc exactly; do not relax any earlier manuscript protections."""
    baseline = subprocess.check_output(  # noqa: S603 -- fixed read-only Git arguments
        [
            "/usr/bin/git",
            "show",
            f"{PLATFORM_BASELINE}:{PACKAGE}/TrafficTwin_Dissertation.md",
        ],
        cwd=root,
        text=True,
    )
    ledger = (here / "evidence/PLATFORM_CONNECTION_OPERATIONS.json").read_bytes()
    operations = json.loads(ledger)
    checks = {
        "platform_connection_baseline_hash": hashlib.sha256(baseline.encode()).hexdigest()
        == PLATFORM_BASELINE_SHA256,
        "platform_connection_four_operation_ledger_pinned": (
            hashlib.sha256(ledger).hexdigest() == PLATFORM_LEDGER_SHA256 and len(operations) == 4
        ),
    }
    restored = revised
    reversible = True
    for operation in reversed(operations):
        if not operation["new"] or restored.count(operation["new"]) != 1:
            reversible = False
            break
        restored = restored.replace(operation["new"], operation["old"], 1)
    checks["platform_connection_only_four_authorised_manuscript_changes"] = (
        reversible and restored == baseline
    )
    for name, expected in PINNED_FILES.items():
        path = here / name
        checks[f"platform_connection_pinned_{Path(name).stem.lower()}"] = (
            path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected
        )
    packet = root / "src/traffictwin/resources/research/joint_confirmation_results.zip"
    checks["platform_connection_bundled_packet_matches_capture"] = (
        packet.is_file() and hashlib.sha256(packet.read_bytes()).hexdigest() == PACKET_SHA256
    )
    imported = json.loads((here / "evidence/TRAFFICTWIN_IMPORT_CHECK.json").read_text())
    checks["platform_connection_preserves_historical_validation_boundary"] = (
        imported["raw_arrays_checked"] is False
        and imported["task_level_validation_repeated"] is False
        and imported["research_workloads_launched"] == 0
        and imported["cells"] == 32
        and imported["paired_blocks"] == 8
        and imported["primary_contrasts"] == 3
        and imported["packet_sha256"] == PACKET_SHA256
    )
    counts = (
        historical_counts
        if historical_counts is not None
        else json.loads((here / "document/WORD_COUNT.json").read_text())
    )
    checks["platform_connection_exact_authorised_counts"] = (
        counts["words"] == 8984 and counts["prose_only_words"] == 7784
    )
    return restored, checks
