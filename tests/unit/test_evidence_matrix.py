"""Experiment evidence matrix (post-v1 E-1, design §8 verification list).

The matrix is provenance and coverage, never authority: rows bind to the
committed records they derive from, completion stays distinct from admission,
distinct unknown-values stay distinct from zero, grouping defaults to
separation, and the confirmed comparison can never shed its sign-test floor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.platform.evidence_matrix import (
    NOT_TESTED,
    SIGN_TEST_FLOOR_NOTE,
    CompatibilityRule,
    EvidenceMatrix,
    EvidenceMatrixError,
    build_evidence_matrix,
    explain_cell,
    filter_rows,
    group_rows,
    matrix_to_json,
    registered_row_ids,
    summarise_coverage,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def matrix() -> EvidenceMatrix:
    return build_evidence_matrix(REPO_ROOT)


def test_every_row_binds_to_existing_committed_sources(matrix: EvidenceMatrix) -> None:
    assert len(matrix.rows) == len(registered_row_ids())
    for row in matrix.rows:
        assert row.sources, row.design_id
        for binding in row.sources:
            assert (REPO_ROOT / binding.path).is_file()
            assert len(binding.sha256) == 64
    assert matrix.evidence is False
    assert matrix.build_digest


def test_builds_are_deterministic_for_the_same_source_digests(
    matrix: EvidenceMatrix,
) -> None:
    again = build_evidence_matrix(REPO_ROOT)
    assert matrix_to_json(again) == matrix_to_json(matrix)
    assert again.build_digest == matrix.build_digest


def test_missing_source_records_refuse(tmp_path: Path) -> None:
    with pytest.raises(EvidenceMatrixError) as excinfo:
        build_evidence_matrix(tmp_path)
    assert excinfo.value.code == "SOURCE_RECORD_MISSING"


def test_changed_source_bytes_refuse_instead_of_accepting_stale_rows(tmp_path: Path) -> None:
    source = REPO_ROOT / "docs/evaluation/experiment_catalogue_20260730.md"
    target = tmp_path / "docs/evaluation/experiment_catalogue_20260730.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes() + b"\nchanged\n")
    with pytest.raises(EvidenceMatrixError) as excinfo:
        build_evidence_matrix(tmp_path)
    assert excinfo.value.code == "DIGEST_MISMATCH"


def test_completion_is_not_admission_for_the_sparse64_rows(
    matrix: EvidenceMatrix,
) -> None:
    non_admitted = [row for row in matrix.rows if row.status == "non_admitted"]
    assert {row.design_id for row in non_admitted} == {
        "bbus-sparse64-homecoming",
        "bbus-sparse64-clean-rerun",
    }
    for row in non_admitted:
        assert row.execution_deviation
        assert row.exclusion_reason
    # Default selections exclude them entirely.
    default_selection = filter_rows(matrix)
    assert not any(row.status == "non_admitted" for row in default_selection.rows)
    # And requesting admitted standing plus non-admitted rows is a promotion.
    with pytest.raises(EvidenceMatrixError) as excinfo:
        filter_rows(matrix, status="admitted", include_non_admitted=True)
    assert excinfo.value.code == "NON_ADMITTED_PROMOTION"


def test_unknown_values_are_distinct_from_zero(matrix: EvidenceMatrix) -> None:
    proposed = next(row for row in matrix.rows if row.status == "proposed")
    assert proposed.seed_set == "not_recorded"
    assert proposed.design_id == "vec-fleet-composition-prediction"
    # A not_recorded seed set contributes NO seeds — removing the proposed
    # row leaves the seed inventory identical, because unknown is not zero.
    with_proposed = summarise_coverage(filter_rows(matrix))
    without_proposed = summarise_coverage(filter_rows(matrix, status="admitted"))
    assert set(with_proposed.unique_seeds) == set(without_proposed.unique_seeds)


def test_grouping_defaults_to_separation(matrix: EvidenceMatrix) -> None:
    mixed = filter_rows(matrix, trace_family="inc")
    with pytest.raises(EvidenceMatrixError) as excinfo:
        group_rows(mixed)
    assert excinfo.value.code in {"EVIDENCE_ROLE_MIXED", "INCOMPATIBLE_GROUPING"}
    rule = CompatibilityRule(
        rule_id="inc-family-view",
        version="1.0",
        allows_roles=("protocol_confirmed", "exploratory", "prediction"),
        allows_statuses=("admitted", "proposed"),
        rationale="capacity-family coverage view; counts only, no pooling",
    )
    grouped = group_rows(mixed, rule)
    assert grouped == mixed.rows
    narrow = CompatibilityRule(
        rule_id="narrow",
        version="1.0",
        allows_roles=("exploratory",),
        allows_statuses=("admitted",),
        rationale="deliberately too narrow",
    )
    with pytest.raises(EvidenceMatrixError) as refused:
        group_rows(mixed, narrow)
    assert refused.value.code == "INCOMPATIBLE_GROUPING"


def test_the_confirmed_row_carries_the_sign_test_floor(matrix: EvidenceMatrix) -> None:
    confirmed = next(row for row in matrix.rows if row.design_id == "vec-capacity-confirmatory")
    assert confirmed.evidence_role == "protocol_confirmed"
    assert confirmed.significance_note == SIGN_TEST_FLOOR_NOTE
    assert "p=0.0625" in str(confirmed.significance_note)
    summary = summarise_coverage(filter_rows(matrix, trace_family="inc"))
    assert any("p=0.0625" in note for note in summary.significance_notes)


def test_summaries_are_counts_with_row_ids_and_digest(matrix: EvidenceMatrix) -> None:
    selection = filter_rows(matrix)
    summary = summarise_coverage(selection)
    assert summary.row_count == len(selection.rows)
    assert summary.row_ids == selection.row_ids
    assert summary.build_digest == matrix.build_digest
    assert "we" in summary.unique_traces
    assert {10, 11, 12, 13, 14} <= set(summary.unique_seeds)
    assert summary.statuses["admitted"] >= 8


def test_explain_cell_names_gaps_and_non_admitted_isolation(
    matrix: EvidenceMatrix,
) -> None:
    untested = explain_cell(
        matrix,
        trace_family="wd_am",
        actor_family="baseline (audited checkpoint model_c_17 family)",
    )
    assert NOT_TESTED in untested
    assert "coverage gap, not a zero" in untested
    gpu = explain_cell(
        matrix,
        trace_family="derived bus (Sparse-64)",
        actor_family="GPU-track training returns",
    )
    assert "non-admitted" in gpu
    assert "excluded from admitted views" in gpu


def test_filters_never_mutate_row_standing(matrix: EvidenceMatrix) -> None:
    before = matrix_to_json(matrix)
    filter_rows(matrix, trace_family="inc", include_non_admitted=True)
    summarise_coverage(filter_rows(matrix))
    assert matrix_to_json(matrix) == before
