"""Tests for the descriptive bus-versus-DfT hourly shape comparison (B2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.integration.manchester.bods_session_identity import (
    SessionProgressionMeasurement,
)
from traffictwin.integration.manchester.bus_profile_comparison import (
    compare_bus_progression_to_dft_shape,
    load_dft_hourly_shape,
)

EDGEDATA = (
    Path(__file__).parents[2]
    / "docs"
    / "integration"
    / "evidence"
    / "manchester_edgedata_counts_option_a.xml"
)


def _progression(
    hours_utc: tuple[int, ...],
    speeds: tuple[float, ...],
    segments: tuple[int, ...],
) -> SessionProgressionMeasurement:
    return SessionProgressionMeasurement(
        snapshot_ids=("snap-a", "snap-b"),
        hour_utc=hours_utc,
        segment_count_by_hour=segments,
        speed_mps_median_by_hour=speeds,
        speed_mps_p90_by_hour=tuple(speed * 1.5 for speed in speeds),
        vehicles_contributing_by_hour=tuple(max(1, s // 10) for s in segments),
    )


def test_surviving_edgedata_reduces_to_the_recorded_hourly_shape() -> None:
    shape = load_dft_hourly_shape(EDGEDATA)

    assert len(shape.hour_local_labels) == 12
    assert shape.hour_local_labels == tuple(range(7, 19))
    # Measured from the surviving file: 2,027,275 — a +3,152 delta against the
    # demand record's 2,024,123 observed vehicles, plausibly integer rounding of
    # fractional per-cell counts at write time. Recorded as an open
    # reconciliation note for the demand-rebuild signing, not silently adopted.
    assert shape.total_entered == 2_027_275
    assert abs(sum(shape.share_by_hour) - 1.0) < 1e-9
    assert shape.hours_are_local_clock_labels is True
    assert shape.ga_dft_1_unresolved is True


def test_comparison_aligns_supports_and_correlates_descriptively() -> None:
    shape = load_dft_hourly_shape(EDGEDATA)
    # Local hours 8..13 (UTC 7..12 at +1): engineered inverse pattern — higher
    # demand share, slower buses — plus one under-supported hour to exclude.
    progression = _progression(
        hours_utc=(7, 8, 9, 10, 11, 12),
        speeds=(4.0, 5.5, 6.5, 7.0, 7.5, 8.0),
        segments=(400, 350, 300, 250, 10, 200),
    )

    comparison = compare_bus_progression_to_dft_shape(
        progression, shape, utc_to_local_offset_hours=1
    )

    assert comparison.hours_excluded_for_support == (12,)
    assert comparison.aligned_hour_local_labels == (8, 9, 10, 11, 13)
    assert comparison.spearman_pair_count == 5
    assert comparison.spearman_rho is not None
    assert comparison.descriptive_non_causal is True
    assert comparison.dft_comparison_performed is True
    assert comparison.bus_speed_is_not_road_speed is True
    rendered = comparison.canonical_json()
    assert "session_token" not in rendered


def test_too_few_aligned_hours_yields_no_correlation() -> None:
    shape = load_dft_hourly_shape(EDGEDATA)
    progression = _progression(hours_utc=(7, 8), speeds=(5.0, 6.0), segments=(100, 100))

    comparison = compare_bus_progression_to_dft_shape(
        progression, shape, utc_to_local_offset_hours=1
    )

    assert comparison.spearman_rho is None
    assert comparison.spearman_pair_count == 0
    assert len(comparison.aligned_hour_local_labels) == 2


def test_missing_edgedata_refuses(tmp_path: Path) -> None:
    from traffictwin.integration.manchester.bods_session_identity import (
        BodsSessionIdentityError,
    )

    with pytest.raises(BodsSessionIdentityError, match="EDGEDATA_MISSING"):
        load_dft_hourly_shape(tmp_path / "absent.xml")
