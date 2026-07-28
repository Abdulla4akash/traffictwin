#!/usr/bin/env python3
"""Rebuild the Greater Manchester baseline network into a durable location.

The 25-July build lived in a session scratchpad and vanished with it; the
recorded "unrecoverable" source identity turned out to be the decoded XML's
identity stored in the source fields (Phase 105). This script rebuilds the
chain from the verified on-disk extract, refuses every shape that caused the
original loss, and writes into ``data/`` so later phases can depend on it.

Guards applied before anything expensive runs (Phase 106):
  * the destination must not be a session-scoped or temporary path;
  * the extract must match its recorded identity byte-for-byte on disk;
  * the decode's source and derived identities must not collide.

Usage:
    uv run python scripts/rebuild_baseline_network.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from traffictwin.integration.manchester.artifact_integrity import (
    ArtifactIdentity,
    SourceDerivedRecord,
    refuse_ephemeral_dependency,
    refuse_source_derived_collision,
    sha256_file,
    verify_recorded_identity,
)
from traffictwin.integration.manchester.network_acquisition import OsmExtractIdentity
from traffictwin.integration.manchester.network_build import (
    NetworkBuildRequest,
    build_baseline_network,
)
from traffictwin.integration.manchester.network_decode import (
    PINNED_EXTRACT_SHA256,
    PINNED_PROVIDER_MD5,
    decode_pbf_to_osm_xml,
)

# Absolute: the decode runs osmium with cwd set to a private staging directory,
# so a relative input path would not resolve there.
EXTRACT_PATH = Path("data/network-recovery/greater-manchester-260724.osm.pbf").resolve()
BUILD_ROOT = Path("data/network-build").resolve()
DECODED_PATH = BUILD_ROOT / "greater-manchester-260724.osm"
NETWORK_ID = "gm-baseline-20260728"
EXTRACT_BYTES = 50_502_348
RECEIPT_PATH = BUILD_ROOT / "rebuild_receipt.json"


def main() -> int:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    refuse_ephemeral_dependency(BUILD_ROOT)

    source_identity = ArtifactIdentity(
        role="source",
        representation="downloaded Geofabrik pbf",
        byte_size=EXTRACT_BYTES,
        sha256=PINNED_EXTRACT_SHA256,
        md5=PINNED_PROVIDER_MD5,
    )
    verify_recorded_identity(source_identity, EXTRACT_PATH)
    print(f"extract verified: {EXTRACT_BYTES} bytes, sha {PINNED_EXTRACT_SHA256[:16]}…")

    if DECODED_PATH.exists():
        print("decoded artifact already present; reusing it")
    else:
        decode_receipt = decode_pbf_to_osm_xml(
            EXTRACT_PATH, DECODED_PATH, workspace_root=BUILD_ROOT
        )
        print(f"decode status: {decode_receipt.status}")

    derived_identity = ArtifactIdentity(
        role="derived",
        representation="decoded osm xml",
        byte_size=DECODED_PATH.stat().st_size,
        sha256=sha256_file(DECODED_PATH),
    )
    refuse_source_derived_collision(
        SourceDerivedRecord(source=source_identity, derived=derived_identity)
    )
    print(f"decoded: {derived_identity.byte_size} bytes, sha {derived_identity.sha256[:16]}…")
    print("source/derived identity separation verified")

    request = NetworkBuildRequest(
        network_id=NETWORK_ID,
        extract=OsmExtractIdentity(
            extract_sha256=PINNED_EXTRACT_SHA256,
            extract_md5=PINNED_PROVIDER_MD5,
            extract_bytes=EXTRACT_BYTES,
            reference_date=date(2026, 7, 25),
            provider_checksum_verified=True,
            provider_checksum_source="provider_md5_companion",
            synthetic=False,
        ),
        synthetic=False,
    )
    binding = build_baseline_network(BUILD_ROOT, DECODED_PATH, request)
    print(f"network built: {BUILD_ROOT / NETWORK_ID}")

    RECEIPT_PATH.write_text(
        json.dumps(
            {
                "rebuilt_at": "2026-07-28",
                "reason": "Phase 105 established the chain was always rebuildable",
                "source": source_identity.model_dump(mode="json"),
                "derived": derived_identity.model_dump(mode="json"),
                "network_id": NETWORK_ID,
                "binding": binding.model_dump(mode="json"),
                "durable_location": str(BUILD_ROOT),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"receipt written to {RECEIPT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
