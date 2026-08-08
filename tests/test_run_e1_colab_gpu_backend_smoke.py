from __future__ import annotations

from scripts.run_e1_colab_gpu_backend_smoke import _array_hashes_equal, _numeric_differences


def test_numeric_differences_reports_nested_absolute_and_relative_change() -> None:
    report = _numeric_differences(
        {"completion": 0.5, "work": {"offered": 10.0}},
        {"completion": 0.55, "work": {"offered": 10.0}},
    )
    assert len(report) == 1
    assert report[0]["field"] == "completion"
    assert report[0]["colab_minus_cpu"] == 0.050000000000000044
    assert report[0]["relative_difference"] == 0.10000000000000009


def test_array_hash_comparison_reports_missing_and_changed_arrays() -> None:
    report = _array_hashes_equal(
        {"task_active": "same", "task_type": "cpu"},
        {"task_active": "same", "task_type": "gpu", "task_met": "new"},
    )
    assert report == {
        "task_active": True,
        "task_met": False,
        "task_type": False,
    }
