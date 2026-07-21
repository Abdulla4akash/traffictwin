from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from tests.format_helpers import canonical_semantic_projection, write_equivalent_bundle
from tests.helpers import FIXTURES, fixed_clock, metric_projection

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.provenance.models import ProvenanceStatus
from traffictwin.provenance.source_rows import get_source_row


@pytest.mark.parametrize("representation", ["gzip", "parquet"])
def test_declared_format_has_csv_equivalent_canonical_metrics_and_provenance(
    tmp_path: Path,
    representation: str,
) -> None:
    csv_result = validate_bundle(FIXTURES / "baseline_valid")
    converted_path = write_equivalent_bundle(
        FIXTURES / "baseline_valid",
        tmp_path / representation,
        representation,
    )
    converted = validate_bundle(converted_path)
    archive = tmp_path / f"{representation}.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        for path in sorted(converted_path.rglob("*")):
            if path.is_file():
                zip_file.write(path, path.relative_to(converted_path).as_posix())
    archived = validate_bundle(archive)

    assert converted.report.may_import
    assert archived.report.may_import
    assert archived.fingerprint == converted.fingerprint
    assert converted.report.canonical_record_counts == csv_result.report.canonical_record_counts
    assert converted.fingerprint != csv_result.fingerprint
    assert canonical_semantic_projection(converted.canonical.model_dump(mode="json")) == (
        canonical_semantic_projection(csv_result.canonical.model_dump(mode="json"))
    )
    assert archived.canonical == converted.canonical

    csv_metrics = compute_metrics_for_bundle(csv_result, clock=fixed_clock)
    converted_metrics = compute_metrics_for_bundle(converted, clock=fixed_clock)
    keys = list(csv_metrics.by_key())
    assert metric_projection(converted_metrics, keys) == metric_projection(csv_metrics, keys)

    assert converted.manifest is not None
    task_file = converted.manifest.files["tasks"].path
    preview = get_source_row(
        converted_path,
        task_file,
        2,
        canonical_tables=converted.canonical,
        validation_report=converted.report,
        manifest=converted.manifest,
    )
    assert preview.status is ProvenanceStatus.AVAILABLE
    assert preview.raw_values["task_id"] == "t1"
    assert preview.canonical_record_type == "TaskRecord"
    assert preview.conversions["format"] == ("parquet" if representation == "parquet" else "csv")
    assert preview.conversions["compression"] == ("gzip" if representation == "gzip" else None)
