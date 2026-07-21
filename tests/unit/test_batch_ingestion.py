from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import traffictwin.ingestion.batch as batch_module
from tests.helpers import FIXTURES
from traffictwin.ingestion.batch import (
    BatchImportState,
    BatchIssueCode,
    BatchOverallStatus,
    batch_summary_to_csv,
    import_bundle_batch,
    validate_bundle_batch,
)
from traffictwin.ingestion.bundle import BundleValidationResult, import_bundle
from traffictwin.storage.registry import Registry


def test_batch_validation_is_sorted_deduplicated_and_consolidated() -> None:
    baseline = FIXTURES / "baseline_valid"
    summary = validate_bundle_batch(
        [baseline, FIXTURES / "variation_valid", "tests/fixtures/bundles/baseline_*"]
    )

    assert summary.overall_status is BatchOverallStatus.COMPLETE
    assert summary.matched_bundle_count == 2
    assert summary.processed_bundle_count == 2
    assert summary.accepted_count == 2
    assert summary.rejected_count == 0
    assert [Path(result.source).name for result in summary.results] == [
        "baseline_valid",
        "variation_valid",
    ]
    assert len(summary.results[0].matched_by) == 2


def test_unmatched_glob_does_not_hide_valid_neighbour() -> None:
    summary = validate_bundle_batch(
        [FIXTURES / "baseline_valid", "tests/fixtures/bundles/does-not-exist-*"]
    )

    assert summary.overall_status is BatchOverallStatus.PARTIAL
    assert summary.accepted_count == 1
    assert summary.input_issues[0].code is BatchIssueCode.GLOB_UNMATCHED


def test_missing_literal_is_an_individual_rejected_candidate(tmp_path: Path) -> None:
    summary = validate_bundle_batch([FIXTURES / "baseline_valid", tmp_path / "missing"])

    assert summary.overall_status is BatchOverallStatus.PARTIAL
    assert summary.accepted_count == 1
    assert summary.rejected_count == 1
    rejected = next(result for result in summary.results if not result.may_import)
    assert Path(rejected.source).name == "missing"
    assert rejected.error_count == 1


def test_malformed_zip_is_isolated_from_valid_neighbour(tmp_path: Path) -> None:
    malformed = tmp_path / "a-malformed.zip"
    malformed.write_bytes(b"not a zip archive")
    valid = tmp_path / "z-valid"
    shutil.copytree(FIXTURES / "baseline_valid", valid)

    summary = validate_bundle_batch([malformed, valid])

    assert summary.overall_status is BatchOverallStatus.PARTIAL
    assert summary.rejected_count == 1
    assert summary.accepted_count == 1
    assert Path(summary.results[0].source).name == "a-malformed.zip"
    assert "before a report was produced" in summary.results[0].message
    assert Path(summary.results[1].source).name == "z-valid"


def test_batch_limit_rejects_before_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(batch_module, "MAX_BATCH_INPUTS", 1)

    summary = validate_bundle_batch([FIXTURES / "baseline_valid", FIXTURES / "variation_valid"])

    assert summary.overall_status is BatchOverallStatus.FAILED
    assert summary.processed_bundle_count == 0
    assert summary.input_issues[0].code is BatchIssueCode.INPUT_LIMIT_EXCEEDED
    assert summary.max_inputs == 1


def test_empty_batch_returns_typed_input_failure() -> None:
    summary = validate_bundle_batch([])

    assert summary.overall_status is BatchOverallStatus.FAILED
    assert summary.processed_bundle_count == 0
    assert summary.input_issues[0].code is BatchIssueCode.INPUT_REQUIRED


def test_candidate_limit_rejects_before_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(batch_module, "MAX_BATCH_BUNDLES", 1)

    summary = validate_bundle_batch([FIXTURES / "baseline_valid", FIXTURES / "variation_valid"])

    assert summary.overall_status is BatchOverallStatus.FAILED
    assert summary.processed_bundle_count == 0
    assert summary.input_issues[0].code is BatchIssueCode.BUNDLE_LIMIT_EXCEEDED
    assert summary.max_bundles == 1


def test_batch_import_keeps_rejected_bundle_out_of_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"

    summary = import_bundle_batch(
        [
            FIXTURES / "baseline_valid",
            FIXTURES / "invalid_manifest",
            FIXTURES / "variation_valid",
        ],
        registry_path,
    )

    assert summary.overall_status is BatchOverallStatus.PARTIAL
    assert summary.created_count == 2
    assert summary.rejected_count == 1
    assert Registry(registry_path).inspect().bundle_import_count == 2

    repeated = import_bundle_batch(
        [FIXTURES / "baseline_valid", FIXTURES / "variation_valid"],
        registry_path,
    )
    assert repeated.overall_status is BatchOverallStatus.COMPLETE
    assert repeated.idempotent_count == 2
    assert all(result.import_state is BatchImportState.IDEMPOTENT for result in repeated.results)


def test_registry_conflict_is_isolated_from_later_bundle(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    import_bundle(FIXTURES / "baseline_valid", registry_path)
    conflict = tmp_path / "a-conflict"
    valid = tmp_path / "z-valid"
    shutil.copytree(FIXTURES / "baseline_valid", conflict)
    shutil.copytree(FIXTURES / "variation_valid", valid)
    manifest = conflict / "manifest.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "Synthetic baseline bundle",
            "Synthetic changed-content conflict",
        ),
        encoding="utf-8",
    )

    summary = import_bundle_batch([conflict, valid], registry_path)

    assert summary.overall_status is BatchOverallStatus.PARTIAL
    assert summary.conflict_count == 1
    assert summary.created_count == 1
    assert summary.results[0].import_state is BatchImportState.CONFLICT
    assert summary.results[1].import_state is BatchImportState.CREATED
    assert Registry(registry_path).inspect().bundle_import_count == 2


def test_batch_import_validates_each_candidate_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = batch_module._validate_one
    validated: list[Path] = []

    def counting_validate(path: Path) -> BundleValidationResult:
        validated.append(path)
        return original(path)

    monkeypatch.setattr(batch_module, "_validate_one", counting_validate)

    summary = import_bundle_batch([FIXTURES / "baseline_valid"], tmp_path / "registry.sqlite")

    assert summary.created_count == 1
    assert len(validated) == 1


def test_batch_csv_export_has_one_row_per_candidate() -> None:
    summary = validate_bundle_batch([FIXTURES / "baseline_valid", FIXTURES / "invalid_manifest"])
    payload = batch_summary_to_csv(summary)

    assert payload.count("\n") == 3
    assert "validation_status" in payload.splitlines()[0]
    assert "baseline_valid" in payload
    assert "invalid_manifest" in payload
