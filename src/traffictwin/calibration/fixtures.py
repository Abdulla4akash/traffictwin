"""Synthetic demonstration fixtures for calibration workbench.

All fixtures are explicitly labelled as synthetic demonstration evidence.
They are tiny, deterministic, and bounded for tests and UI demo.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from traffictwin.calibration.models import (
    CalibrationAlignmentSpec,
    CalibrationBin,
    CalibrationCandidate,
    CalibrationMetricSpec,
    CalibrationObservedReference,
    CalibrationStudy,
    Direction,
    MissingnessPolicy,
)

# Common deterministic window
_WINDOW_START = datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC)
_WINDOW_END = datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC)
_BIN_WIDTH = 900.0  # 15 min => 4 bins per hour
_SENSORS = ["sensor_A", "sensor_B"]
_METRIC_SPECS: list[CalibrationMetricSpec] = [
    CalibrationMetricSpec(
        metric_key="flow.count",
        metric_version="1.0",
        unit="veh/h",
        denominator="per_sensor_per_hour",
        direction=Direction.LOWER_IS_BETTER,
        weight=0.6,
        alignment_required=True,
        missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
    ),
    CalibrationMetricSpec(
        metric_key="traffic.speed.mean_mps",
        metric_version="1.0",
        unit="m/s",
        denominator="per_sensor_per_window",
        direction=Direction.LOWER_IS_BETTER,
        weight=0.4,
        alignment_required=True,
        missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
    ),
]


def _bin_window(index: int) -> tuple[datetime, datetime]:
    start = _WINDOW_START + timedelta(seconds=index * _BIN_WIDTH)
    end = start + timedelta(seconds=_BIN_WIDTH)
    return start, end


def _fingerprint_for_payload(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_observed_fixture() -> CalibrationObservedReference:
    """Create synthetic observed fixture with complete coverage."""
    bins: list[CalibrationBin] = []
    # 4 windows * 2 sensors * 2 metrics = 16 bins
    # Deterministic values
    flow_values = {
        ("sensor_A", 0): 100.0,
        ("sensor_A", 1): 120.0,
        ("sensor_A", 2): 110.0,
        ("sensor_A", 3): 105.0,
        ("sensor_B", 0): 90.0,
        ("sensor_B", 1): 95.0,
        ("sensor_B", 2): 100.0,
        ("sensor_B", 3): 98.0,
    }
    speed_values = {
        ("sensor_A", 0): 12.5,
        ("sensor_A", 1): 13.0,
        ("sensor_A", 2): 12.8,
        ("sensor_A", 3): 12.6,
        ("sensor_B", 0): 11.0,
        ("sensor_B", 1): 11.2,
        ("sensor_B", 2): 11.5,
        ("sensor_B", 3): 11.3,
    }
    for sensor in _SENSORS:
        for idx in range(4):
            ws, we = _bin_window(idx)
            # flow
            bins.append(
                CalibrationBin(
                    sensor_id=sensor,
                    window_index=idx,
                    window_start_utc=ws,
                    window_end_utc=we,
                    metric_key="flow.count",
                    value=flow_values[(sensor, idx)],
                    unit="veh/h",
                )
            )
            bins.append(
                CalibrationBin(
                    sensor_id=sensor,
                    window_index=idx,
                    window_start_utc=ws,
                    window_end_utc=we,
                    metric_key="traffic.speed.mean_mps",
                    value=speed_values[(sensor, idx)],
                    unit="m/s",
                )
            )
    # fingerprint is stable hash over bins + metadata
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "observed_id": "observed_synthetic_demo",
        "sensor_ids": sorted(_SENSORS),
    }
    fp = _fingerprint_for_payload(payload)
    return CalibrationObservedReference(
        observed_id="observed_synthetic_demo",
        fingerprint=fp,
        evidence_label="Synthetic demonstration evidence — not observed; for calibration workflow demo only",  # noqa: E501
        window_start_utc=_WINDOW_START,
        window_end_utc=_WINDOW_END,
        bin_width_s=_BIN_WIDTH,
        sensor_ids=_SENSORS,
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )


def _make_candidate_bins(
    *,
    flow_values: Mapping[tuple[str, int], float | None],
    speed_values: Mapping[tuple[str, int], float | None],
    flow_unit: str = "veh/h",
    speed_unit: str = "m/s",
    window_start: datetime = _WINDOW_START,
    window_end: datetime = _WINDOW_END,
    bin_width: float = _BIN_WIDTH,
    sensors: list[str] = _SENSORS,
) -> list[CalibrationBin]:
    bins: list[CalibrationBin] = []
    for sensor in sensors:
        for idx in range(4):
            # Recalculate window based on offset from original start
            ws = window_start + timedelta(seconds=idx * bin_width)
            we = ws + timedelta(seconds=bin_width)
            bins.append(
                CalibrationBin(
                    sensor_id=sensor,
                    window_index=idx,
                    window_start_utc=ws,
                    window_end_utc=we,
                    metric_key="flow.count",
                    value=flow_values.get((sensor, idx)),
                    unit=flow_unit,
                )
            )
            bins.append(
                CalibrationBin(
                    sensor_id=sensor,
                    window_index=idx,
                    window_start_utc=ws,
                    window_end_utc=we,
                    metric_key="traffic.speed.mean_mps",
                    value=speed_values.get((sensor, idx)),
                    unit=speed_unit,
                )
            )
    return bins


def make_candidate_good() -> CalibrationCandidate:
    """Compatible good-fit candidate — close to observed."""
    flow_values = {
        ("sensor_A", 0): 102.0,
        ("sensor_A", 1): 118.0,
        ("sensor_A", 2): 111.0,
        ("sensor_A", 3): 106.0,
        ("sensor_B", 0): 91.0,
        ("sensor_B", 1): 96.0,
        ("sensor_B", 2): 101.0,
        ("sensor_B", 3): 99.0,
    }
    speed_values = {
        ("sensor_A", 0): 12.6,
        ("sensor_A", 1): 12.9,
        ("sensor_A", 2): 12.9,
        ("sensor_A", 3): 12.7,
        ("sensor_B", 0): 11.1,
        ("sensor_B", 1): 11.3,
        ("sensor_B", 2): 11.6,
        ("sensor_B", 3): 11.4,
    }
    bins = _make_candidate_bins(flow_values=flow_values, speed_values=speed_values)
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_good_fit",
    }
    fp = _fingerprint_for_payload(payload)
    return CalibrationCandidate(
        candidate_id="candidate_good_fit",
        fingerprint=fp,
        label="Synthetic demonstration — compatible good-fit candidate",
        window_start_utc=_WINDOW_START,
        window_end_utc=_WINDOW_END,
        bin_width_s=_BIN_WIDTH,
        sensor_ids=_SENSORS,
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )


def make_candidate_poor() -> CalibrationCandidate:
    """Compatible poor-fit candidate — far from observed but still compatible."""
    flow_values = {
        ("sensor_A", 0): 150.0,
        ("sensor_A", 1): 80.0,
        ("sensor_A", 2): 200.0,
        ("sensor_A", 3): 60.0,
        ("sensor_B", 0): 130.0,
        ("sensor_B", 1): 70.0,
        ("sensor_B", 2): 180.0,
        ("sensor_B", 3): 50.0,
    }
    speed_values = {
        ("sensor_A", 0): 9.0,
        ("sensor_A", 1): 16.0,
        ("sensor_A", 2): 8.5,
        ("sensor_A", 3): 15.0,
        ("sensor_B", 0): 8.0,
        ("sensor_B", 1): 14.0,
        ("sensor_B", 2): 7.5,
        ("sensor_B", 3): 13.5,
    }
    bins = _make_candidate_bins(flow_values=flow_values, speed_values=speed_values)
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_poor_fit",
    }
    fp = _fingerprint_for_payload(payload)
    return CalibrationCandidate(
        candidate_id="candidate_poor_fit",
        fingerprint=fp,
        label="Synthetic demonstration — compatible poor-fit candidate",
        window_start_utc=_WINDOW_START,
        window_end_utc=_WINDOW_END,
        bin_width_s=_BIN_WIDTH,
        sensor_ids=_SENSORS,
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )


def make_candidate_incompatible() -> CalibrationCandidate:
    """Incompatible/missing candidate — unit mismatch + missing bins."""

    # For temporal misalignment test we shift window by 1 hour.
    # For unit mismatch we use veh/min instead of veh/h.
    # For missing we include None values for half the speed bins.
    flow_values: dict[tuple[str, int], float | None] = {
        ("sensor_A", 0): 100.0,
        ("sensor_A", 1): 120.0,
        ("sensor_A", 2): 110.0,
        ("sensor_A", 3): 105.0,
        ("sensor_B", 0): 90.0,
        ("sensor_B", 1): 95.0,
        ("sensor_B", 2): 100.0,
        ("sensor_B", 3): 98.0,
    }
    # Half missing speed values
    speed_values: dict[tuple[str, int], float | None] = {
        ("sensor_A", 0): 12.5,
        ("sensor_A", 1): None,
        ("sensor_A", 2): None,
        ("sensor_A", 3): 12.6,
        ("sensor_B", 0): None,
        ("sensor_B", 1): 11.2,
        ("sensor_B", 2): None,
        ("sensor_B", 3): 11.3,
    }
    # Use wrong unit for flow to trigger unit mismatch exclusion
    bins = _make_candidate_bins(
        flow_values=flow_values,
        speed_values=speed_values,
        flow_unit="veh/min",
        speed_unit="m/s",
    )
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_incompatible",
    }
    fp = _fingerprint_for_payload(payload)
    return CalibrationCandidate(
        candidate_id="candidate_incompatible",
        fingerprint=fp,
        label="Synthetic demonstration — incompatible/missing candidate (unit mismatch + missing)",
        window_start_utc=_WINDOW_START,
        window_end_utc=_WINDOW_END,
        bin_width_s=_BIN_WIDTH,
        sensor_ids=_SENSORS,
        metric_units={"flow.count": "veh/min", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )


def make_candidate_missing() -> CalibrationCandidate:
    """Compatible but missing evidence — many None values."""

    # Temporally aligned, unit compatible, many missing bins so
    # objective unavailable if missing is large.
    flow_values: dict[tuple[str, int], float | None] = {
        ("sensor_A", 0): 101.0,
        ("sensor_A", 1): None,
        ("sensor_A", 2): None,
        ("sensor_A", 3): None,
        ("sensor_B", 0): None,
        ("sensor_B", 1): None,
        ("sensor_B", 2): None,
        ("sensor_B", 3): None,
    }
    speed_values: dict[tuple[str, int], float | None] = {
        ("sensor_A", 0): 12.5,
        ("sensor_A", 1): 13.0,
        ("sensor_A", 2): 12.8,
        ("sensor_A", 3): 12.6,
        ("sensor_B", 0): 11.0,
        ("sensor_B", 1): 11.2,
        ("sensor_B", 2): 11.5,
        ("sensor_B", 3): 11.3,
    }
    bins = _make_candidate_bins(flow_values=flow_values, speed_values=speed_values)
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_missing_evidence",
    }
    fp = _fingerprint_for_payload(payload)
    return CalibrationCandidate(
        candidate_id="candidate_missing_evidence",
        fingerprint=fp,
        label="Synthetic demonstration — missing-evidence candidate (flow mostly missing)",
        window_start_utc=_WINDOW_START,
        window_end_utc=_WINDOW_END,
        bin_width_s=_BIN_WIDTH,
        sensor_ids=_SENSORS,
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )


def make_candidate_temporal_misaligned() -> CalibrationCandidate:
    """Candidate with temporal misalignment — window shifted by 1 hour."""
    flow_values = {
        ("sensor_A", 0): 100.0,
        ("sensor_A", 1): 120.0,
        ("sensor_A", 2): 110.0,
        ("sensor_A", 3): 105.0,
        ("sensor_B", 0): 90.0,
        ("sensor_B", 1): 95.0,
        ("sensor_B", 2): 100.0,
        ("sensor_B", 3): 98.0,
    }
    speed_values = {
        ("sensor_A", 0): 12.5,
        ("sensor_A", 1): 13.0,
        ("sensor_A", 2): 12.8,
        ("sensor_A", 3): 12.6,
        ("sensor_B", 0): 11.0,
        ("sensor_B", 1): 11.2,
        ("sensor_B", 2): 11.5,
        ("sensor_B", 3): 11.3,
    }
    shifted_start = _WINDOW_START + timedelta(hours=1)
    shifted_end = _WINDOW_END + timedelta(hours=1)
    bins = _make_candidate_bins(
        flow_values=flow_values,
        speed_values=speed_values,
        window_start=shifted_start,
        window_end=shifted_end,
    )
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_temporal_misaligned",
    }
    fp = _fingerprint_for_payload(payload)
    return CalibrationCandidate(
        candidate_id="candidate_temporal_misaligned",
        fingerprint=fp,
        label="Synthetic demonstration — temporally misaligned candidate (shifted 1h)",
        window_start_utc=shifted_start,
        window_end_utc=shifted_end,
        bin_width_s=_BIN_WIDTH,
        sensor_ids=_SENSORS,
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )


def make_default_study() -> CalibrationStudy:
    """Create a default study with observed + 4 candidates (good, poor, incompatible, missing)."""
    observed = make_observed_fixture()
    candidates = [
        make_candidate_good(),
        make_candidate_poor(),
        make_candidate_incompatible(),
        make_candidate_missing(),
    ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=_WINDOW_START,
        window_end_utc=_WINDOW_END,
        bin_width_s=_BIN_WIDTH,
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    return CalibrationStudy(
        study_id="calibration_demo_study",
        study_name="Synthetic Calibration Demo",
        description="Synthetic demonstration study comparing observed to simulation candidates; not observed evidence.",  # noqa: E501
        observed=observed,
        candidates=candidates,
        metric_specs=_METRIC_SPECS,
        alignment_spec=alignment,
    )


def make_three_candidate_study() -> CalibrationStudy:
    """Return study with exactly three candidates as per spec: good, poor, incompatible."""
    observed = make_observed_fixture()
    candidates = [
        make_candidate_good(),
        make_candidate_poor(),
        make_candidate_incompatible(),
    ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=_WINDOW_START,
        window_end_utc=_WINDOW_END,
        bin_width_s=_BIN_WIDTH,
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    return CalibrationStudy(
        study_id="calibration_demo_three",
        study_name="Synthetic Three-Candidate Demo",
        description="Three-candidate synthetic demonstration: good-fit, poor-fit, incompatible/missing.",  # noqa: E501
        observed=observed,
        candidates=candidates,
        metric_specs=_METRIC_SPECS,
        alignment_spec=alignment,
    )


def make_metric_specs_for_test() -> list[CalibrationMetricSpec]:
    return list(_METRIC_SPECS)


def synthetic_window_start() -> datetime:
    return _WINDOW_START


def synthetic_window_end() -> datetime:
    return _WINDOW_END


def synthetic_bin_width() -> float:
    return _BIN_WIDTH


def synthetic_sensors() -> list[str]:
    return list(_SENSORS)
