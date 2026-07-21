from __future__ import annotations

import csv
from io import StringIO

import pytest

from traffictwin.provenance.contributions import contribution_report_to_csv
from traffictwin.provenance.query import (
    ProvenanceQueryError,
    build_provenance_context,
    get_metric_contributions,
)


def test_metric_contributions_include_every_candidate_task_row() -> None:
    context = build_provenance_context("tests/fixtures/bundles/baseline_valid")

    report = get_metric_contributions(context, "task.latency.mean_ms")

    assert report.complete_row_ledger is True
    assert report.candidate_row_count == len(context.validation.canonical.tasks)
    assert report.included_row_count + report.excluded_row_count == report.candidate_row_count
    assert all(row.source_file == "tasks.csv" for row in report.rows)
    assert all(row.canonical_values for row in report.rows)

    csv_rows = list(csv.DictReader(StringIO(contribution_report_to_csv(report))))
    assert len(csv_rows) == report.candidate_row_count
    assert {row["included"] for row in csv_rows} <= {"True", "False"}

    p99_report = get_metric_contributions(context, "task.latency.p99_ms")
    assert p99_report.metric_value == 178.8
    assert p99_report.included_row_count == 3
    assert all(row.included for row in p99_report.rows)


def test_metric_contributions_reject_unknown_metric() -> None:
    context = build_provenance_context("tests/fixtures/bundles/baseline_valid")

    with pytest.raises(ProvenanceQueryError, match="not present"):
        get_metric_contributions(context, "not.a.metric")
