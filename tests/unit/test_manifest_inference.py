from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.ingestion.manifest_inference import (
    MAX_INFERENCE_SAMPLE_ROWS,
    ConfirmationMode,
    FileSelection,
    ManifestInferenceError,
    ManifestInferenceSelections,
    SuggestionStatus,
    confirm_manifest_inference,
    infer_manifest,
    manifest_inference_contract,
)
from traffictwin.validation.codes import ValidationCode

FIXTURES = Path("tests/fixtures/manifest_inference")


def test_value_patterns_are_bounded_suggestions_not_analysis_input() -> None:
    draft = infer_manifest(FIXTURES / "value_patterns")
    tasks = draft.files[0]
    candidate = tasks.by_kind()["tasks"]
    fields = candidate.by_field()

    assert not draft.analysis_ready
    assert draft.confirmation_required
    assert tasks.status is SuggestionStatus.SUGGESTED
    assert tasks.suggested_kind == "tasks"
    assert fields["task_class"].candidates[0].methods[0].value == "value_pattern"
    assert fields["decision"].suggested_source_column == "PlacementCode"
    assert fields["completed"].suggested_source_column == "FlagCode"
    assert fields["arrival_time"].suggested_unit == "s"


def test_inference_contract_publishes_bounds_and_non_probability_semantics() -> None:
    contract = manifest_inference_contract()

    assert contract.inference_version == "1.0"
    assert contract.limits.max_sample_rows_per_file == 100
    assert [method.precedence for method in contract.methods] == [30, 20, 10]
    assert "not a probability" in contract.score_semantics
    assert "analysis or import of an inference draft" in contract.unsupported


def test_confirmation_is_explicit_and_ambiguity_is_not_silently_resolved() -> None:
    source = FIXTURES / "ambiguous"
    draft = infer_manifest(source)

    with pytest.raises(ManifestInferenceError, match="explicit confirmation"):
        confirm_manifest_inference(draft, source, confirmed_by="analyst")
    with pytest.raises(ManifestInferenceError, match="ambiguous or unresolved"):
        confirm_manifest_inference(
            draft,
            source,
            confirmed_by="analyst",
            accept_suggestions=True,
        )


def test_explicit_edit_can_resolve_an_ambiguous_file() -> None:
    source = FIXTURES / "ambiguous"
    draft = infer_manifest(source)
    selections = ManifestInferenceSelections(
        files={
            "entity.csv": FileSelection(
                kind="traffic_obs",
                units={"timestamp": "s"},
            )
        }
    )

    confirmed = confirm_manifest_inference(
        draft,
        source,
        confirmed_by="analyst",
        selections=selections,
    )

    assert confirmed.analysis_ready
    assert confirmed.confirmation_state is ConfirmationMode.EDITED
    assert confirmed.mappings[0].kind == "traffic_obs"
    assert confirmed.mappings[0].column_map == {
        "sensor_id": "EntityID",
        "timestamp": "TimeSeconds",
    }


def test_optional_suggestion_can_be_explicitly_unmapped() -> None:
    source = FIXTURES / "value_patterns"
    draft = infer_manifest(source)
    selections = ManifestInferenceSelections(
        files={
            "external_tasks.csv": FileSelection(
                unmapped_fields=["completion_time", "latency_ms", "target_id"]
            )
        }
    )

    confirmed = confirm_manifest_inference(
        draft,
        source,
        confirmed_by="analyst",
        accept_suggestions=True,
        selections=selections,
    )

    assert confirmed.confirmation_state is ConfirmationMode.EDITED
    assert "completion_time" not in confirmed.mappings[0].column_map
    assert "latency_ms" not in confirmed.mappings[0].units


def test_source_change_invalidates_the_draft(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(FIXTURES / "value_patterns", source)
    draft = infer_manifest(source)
    csv_path = source / "external_tasks.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(
        ManifestInferenceError, match=ValidationCode.MANIFEST_INFERENCE_STALE_SOURCE
    ):
        confirm_manifest_inference(
            draft,
            source,
            confirmed_by="analyst",
            accept_suggestions=True,
        )


def test_draft_fingerprint_is_independent_of_source_directory_name(tmp_path: Path) -> None:
    first = tmp_path / "first-name"
    second = tmp_path / "another-name"
    shutil.copytree(FIXTURES / "value_patterns", first)
    shutil.copytree(FIXTURES / "value_patterns", second)

    assert infer_manifest(first).draft_fingerprint == infer_manifest(second).draft_fingerprint


def test_tampered_draft_is_rejected_before_confirmation() -> None:
    draft = infer_manifest(FIXTURES / "value_patterns")
    raw = draft.model_dump(mode="json")
    raw["files"][0]["suggested_kind"] = "trips"

    with pytest.raises(ValidationError, match="draft fingerprint"):
        type(draft).model_validate(raw)


def test_sampling_stops_at_published_bound(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    rows = "".join(f"{index},sensor-{index}\n" for index in range(150))
    (source / "traffic.csv").write_text("timestamp,sensor_id\n" + rows, encoding="utf-8")

    draft = infer_manifest(source)

    assert draft.files[0].sampled_rows == MAX_INFERENCE_SAMPLE_ROWS


def test_duplicate_headers_are_reported_without_a_mapping(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "duplicate.csv").write_text("id,id\n1,2\n", encoding="utf-8")

    draft = infer_manifest(source)

    assert not draft.files
    assert ValidationCode.MANIFEST_INFERENCE_CSV_INVALID in {
        finding.code for finding in draft.findings
    }


def test_required_field_tie_emits_stable_ambiguity_code(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "tasks.csv").write_text(
        "task_id,vehicle_id,class_a,class_b,arrival_time_s,deadline_ms,decision,completed\n"
        "job-1,veh-1,T1,T1,0,100,v2i,true\n"
        "job-2,veh-2,T2,T2,1,200,local,false\n",
        encoding="utf-8",
    )

    draft = infer_manifest(source)
    codes = {finding.code for finding in draft.findings}

    assert draft.files[0].status is SuggestionStatus.UNMAPPED
    assert ValidationCode.MANIFEST_INFERENCE_FILE_UNRESOLVED in codes
    assert ValidationCode.MANIFEST_INFERENCE_FIELD_AMBIGUOUS in codes
