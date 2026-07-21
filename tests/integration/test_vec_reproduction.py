from __future__ import annotations

from pathlib import Path

from traffictwin.integration.vec_reproduction import (
    PINNED_EXPECTED_FILES,
    VecReproductionGrade,
    VecReproductionReport,
)

ROOT = Path(__file__).parents[2]
REPORT = ROOT / "docs" / "reference" / "generated" / "vec_reproduction_report.json"


def test_published_vec08_report_is_permission_safe_and_evidence_consistent() -> None:
    raw = REPORT.read_text(encoding="utf-8")
    report = VecReproductionReport.model_validate_json(raw)

    assert report.grade is VecReproductionGrade.NUMERICALLY_EQUIVALENT
    assert report.summary.model_dump() == {
        "exact": 61,
        "within_tolerance": 2,
        "mismatch": 0,
        "excluded": 1,
        "unavailable": 1,
    }
    assert report.repeat_run is not None
    assert report.repeat_run.same_execution_controls is True
    assert report.repeat_run.scientific_json_exact is True
    assert report.repeat_run.perstep_arrays_exact is True
    assert report.repeat_run.pertask_arrays_exact is True
    assert report.direct_launch_supported is False
    assert {item.path: item.sha256 for item in report.expected_sources} == PINNED_EXPECTED_FILES
    assert report.external_repositories_modified is False
    assert report.raw_inputs_modified is False
    assert "/Users/" not in raw
    assert "/private/" not in raw
    assert "akash" not in raw.lower()
    assert "hostname" not in raw.lower()


def test_published_vec08_report_records_only_the_two_declared_numeric_differences() -> None:
    report = VecReproductionReport.model_validate_json(REPORT.read_text(encoding="utf-8"))
    tolerated = {
        (check.artifact, check.field): check
        for check in report.checks
        if check.status.value == "within_tolerance"
    }

    assert set(tolerated) == {
        ("run.json", "avg_energy_j_per_task"),
        ("per-step.npz", "lat_sum"),
    }
    assert tolerated[("run.json", "avg_energy_j_per_task")].max_absolute_error == (
        6.030117782884759e-08
    )
    latency = tolerated[("per-step.npz", "lat_sum")]
    assert latency.max_absolute_error == 0.00390625
    assert latency.max_ulp_error == 3
    assert latency.note == "Raw unequal element count: 9536."
