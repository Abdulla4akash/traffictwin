"""Test helpers for equivalent generic tabular bundle representations."""

from __future__ import annotations

import csv
import gzip
import shutil
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from traffictwin.ingestion.hashes import sha256_file


def write_equivalent_bundle(source: Path, destination: Path, representation: str) -> Path:
    """Copy a CSV bundle and convert every declared table without changing logical rows."""

    shutil.copytree(source, destination)
    manifest_path = destination / "manifest.yaml"
    manifest = cast(dict[str, Any], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    declarations = cast(dict[str, dict[str, Any]], manifest["files"])
    for declaration in declarations.values():
        source_path = destination / str(declaration["path"])
        if representation == "gzip":
            target = source_path.with_suffix(source_path.suffix + ".gz")
            with (
                source_path.open("rb") as source_handle,
                target.open("wb") as target_handle,
                gzip.GzipFile(fileobj=target_handle, mode="wb", mtime=0) as gzip_handle,
            ):
                shutil.copyfileobj(source_handle, gzip_handle)
            declaration["format"] = "csv"
            declaration["compression"] = "gzip"
        elif representation == "parquet":
            target = source_path.with_suffix(".parquet")
            with source_path.open(newline="", encoding="utf-8-sig") as handle:
                rows = [dict(row) for row in csv.DictReader(handle)]
            pq.write_table(
                pa.Table.from_pylist(rows),
                target,
                compression="NONE",
                write_statistics=False,
            )
            declaration["format"] = "parquet"
            declaration.pop("compression", None)
        else:
            raise ValueError(f"unsupported test representation: {representation}")
        source_path.unlink()
        declaration["path"] = target.name
        declaration["checksum_sha256"] = sha256_file(target)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return destination


def canonical_semantic_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove only physical source-file paths from canonical-table JSON."""

    projected = payload.copy()
    for rows in projected.values():
        for row in cast(list[dict[str, Any]], rows):
            row.pop("source_file", None)
    return projected
