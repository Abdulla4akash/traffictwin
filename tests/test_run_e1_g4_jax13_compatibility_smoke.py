from __future__ import annotations

import numpy as np
from scripts.run_e1_g4_jax13_compatibility_smoke import _compare_array, _scientific_close


def test_cross_backend_float_array_can_be_close_without_byte_identity() -> None:
    cpu = np.array([1.0, 2.0], dtype=np.float32)
    g4 = np.array([1.0, 2.000001], dtype=np.float32)

    result = _compare_array(cpu, g4, rtol=1e-6, atol=1e-5)

    assert result["exact"] is False
    assert result["allclose"] is True
    assert result["differing_elements"] == 1
    assert result["max_absolute_difference"] > 0.0


def test_cross_backend_discrete_array_reports_nonidentity() -> None:
    cpu = np.array([1, 2, 3], dtype=np.int8)
    g4 = np.array([1, 2, 4], dtype=np.int8)

    result = _compare_array(cpu, g4, rtol=1e-6, atol=1e-5)

    assert result["exact"] is False
    assert result["differing_elements"] == 1


def test_scientific_comparison_reports_tolerated_numeric_difference() -> None:
    passed, differences = _scientific_close(
        {"completion": 0.5, "n_offered": 10},
        {"completion": 0.5000001, "n_offered": 10},
        rtol=1e-6,
        atol=1e-5,
    )

    assert passed is True
    assert differences == [
        {
            "field": "completion",
            "cpu": 0.5,
            "g4": 0.5000001,
            "g4_minus_cpu": 9.999999994736442e-08,
            "relative_difference": 1.9999999989472883e-07,
            "within_tolerance": True,
        }
    ]
