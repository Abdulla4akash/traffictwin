from __future__ import annotations

from scripts.build_e1_multidraw_final_records import _mechanism_checks, _runtime


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for seed in range(5):
        for cap, admitted, rejected, admitted_attainment, offered_latency, offered in (
            ("0p75", 80, 20, 0.75, 100.0, 0.6),
            ("2p5", 85, 15, 0.72, 200.0, 0.59),
            ("40x", 90, 10, 0.70, 300.0, 0.59),
        ):
            rows.append(
                {
                    "fleet_seed": seed,
                    "cap_label": cap,
                    "admitted_tasks": admitted,
                    "rejected_or_unavailable_tasks": rejected,
                    "deadline_attainment_admitted": admitted_attainment,
                    "deadline_attainment_offered": offered,
                    "penalty_inclusive_latency_ms_per_offered_task": offered_latency,
                    "rejection_counts": {"v2i_cap_rejected": 1},
                    "wall_s": 3600.0,
                }
            )
    return rows


def test_mechanism_checks_are_calculated_across_fleet_draws() -> None:
    result = _mechanism_checks(_rows())

    assert all(result.values())


def test_runtime_excludes_reused_seed0_and_counts_remaining_cells() -> None:
    result = _runtime(_rows())

    assert result["twelve_new_full_cells_hours"] == 12.0
    assert result["nine_cells_executed_in_final_continuation_hours"] == 9.0
    assert result["within_authorised_budget"] is True
