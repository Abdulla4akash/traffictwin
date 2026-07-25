"""Evidence for the controlled Manchester SUMO run boundary.

The lead's sumo_execution service is synthetic-only by construction. This
boundary exists beside it, and must not quietly acquire the authority that
service withholds.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.sumo_run import (
    MAX_FCD_BYTES,
    MAX_WINDOW_S,
    SUMO_FIXED_ARGUMENTS,
    ManchesterSumoRunError,
    SumoRunObservations,
    SumoRunReceipt,
    SumoRunRequest,
    SumoToolIdentity,
    preflight_run,
    projected_fcd_bytes,
    read_run_observations,
)

DIGEST = "a" * 64


def _request(**changes: object) -> SumoRunRequest:
    payload: dict[str, Any] = {
        "run_id": "manchester-pilot",
        "network_sha256": DIGEST,
        "demand_sha256": "b" * 64,
        "begin_s": 0,
        "end_s": 43200,
        "seed": 42,
        "confirmed_by_operator": True,
    }
    payload.update(changes)
    return SumoRunRequest(**payload)


class TestTheCommandIsFrozen:
    def test_one_second_step_and_one_second_fcd(self) -> None:
        joined = " ".join(SUMO_FIXED_ARGUMENTS)
        assert "--step-length 1" in joined
        assert "--fcd-output.period 1" in joined

    def test_the_vector_carries_no_concrete_path(self) -> None:
        for item in SUMO_FIXED_ARGUMENTS:
            assert not item.startswith("/"), "paths are substituted at run time, never frozen in"

    def test_tripinfo_and_summary_are_requested(self) -> None:
        joined = " ".join(SUMO_FIXED_ARGUMENTS)
        assert "--tripinfo-output" in joined
        assert "--summary-output" in joined

    def test_a_receipt_recording_a_different_vector_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exact frozen argument vector"):
            SumoRunReceipt(
                request=_request(),
                tool=SumoToolIdentity(reported_version="1.27.1", executable_sha256=DIGEST),
                argument_shape=("--net-file", "<net>", "--fcd-output.period", "60"),
                exit_code=0,
                started_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                completed_at_utc=datetime(2026, 7, 25, tzinfo=UTC),
                duration_s=Decimal("1"),
                outcome="failed",
                fcd_bytes=0,
            )


class TestRunAuthorisationAndBounds:
    def test_a_run_must_be_operator_confirmed(self) -> None:
        with pytest.raises(ValidationError):
            _request(confirmed_by_operator=False)

    def test_a_non_positive_window_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="window must be positive"):
            _request(begin_s=100, end_s=100)

    def test_a_window_beyond_the_bound_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exceeds the reviewed bound"):
            _request(begin_s=0, end_s=MAX_WINDOW_S + 1)

    def test_a_version_outside_the_reviewed_toolchain_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="reviewed 1.27.x"):
            SumoToolIdentity(reported_version="1.26.0", executable_sha256=DIGEST)


class TestFcdProjectionIsAFloor:
    def test_the_measured_pilot_projects_the_recorded_figure(self) -> None:
        # 509 MB for the first 600 simulated seconds, measured on the real
        # artifacts, projected across the 12-hour window.
        projected = projected_fcd_bytes(508_816_400, 600, 43_200)
        assert projected == pytest.approx(36_634_780_800, rel=1e-6)

    def test_a_projection_over_the_bound_refuses_before_anything_runs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A per-second rate large enough to blow the bound must stop at
        # preflight, not after gigabytes have been written.
        monkeypatch.setattr(
            "traffictwin.integration.manchester.sumo_run.discover_sumo",
            lambda: pytest.fail("the toolchain must not be probed after the size refusal"),
        )
        rate = (MAX_FCD_BYTES // 43_200) + 1_000
        with pytest.raises(ManchesterSumoRunError, match="FCD_PROJECTION_EXCEEDS_BOUND"):
            preflight_run(_request(), measured_fcd_rate=rate)

    def test_a_zero_window_projection_is_refused(self) -> None:
        with pytest.raises(ManchesterSumoRunError, match="PROJECTION_WINDOW_REFUSED"):
            projected_fcd_bytes(1_000, 0, 43_200)


class TestRunQualityIsRecordedNotCorrected:
    def _summary(self, tmp_path: Path, steps: list[tuple[int, int, int]]) -> Path:
        body = "\n".join(
            f'  <step time="{t}.00" running="{r}" halting="{h}" inserted="{r}" teleports="7"/>'
            for t, r, h in steps
        )
        target = tmp_path / "summary.xml"
        target.write_text(f"<summary>\n{body}\n</summary>\n", encoding="utf-8")
        return target

    def test_a_filling_network_is_reported_as_not_steady(self, tmp_path: Path) -> None:
        # The real pilot grew 2,779 -> 10,715 across its window.
        path = self._summary(
            tmp_path, [(0, 1, 0), (150, 2779, 612), (450, 8129, 3859), (599, 10715, 5349)]
        )
        observations = read_run_observations(path)
        assert observations is not None
        assert observations.reached_steady_state is False
        assert observations.vehicles_running_final == 10715

    def test_the_halting_share_is_measured(self, tmp_path: Path) -> None:
        path = self._summary(tmp_path, [(0, 1, 0), (150, 100, 10), (450, 100, 40), (599, 100, 50)])
        observations = read_run_observations(path)
        assert observations is not None
        assert observations.halting_share_final == Decimal("0.5000")

    def test_a_missing_summary_reports_nothing_rather_than_guessing(self, tmp_path: Path) -> None:
        assert read_run_observations(tmp_path / "absent.xml") is None

    def test_observations_do_not_gate_acceptance(self) -> None:
        # Congestion is a finding about the demand, not a reason to rewrite it.
        observations = SumoRunObservations(
            steps_recorded=600,
            vehicles_inserted=10968,
            vehicles_running_final=10715,
            vehicles_halting_final=5349,
            teleports=102,
            reached_steady_state=False,
            halting_share_final=Decimal("0.4992"),
        )
        assert observations.halting_share_final is not None
        assert observations.halting_share_final > Decimal("0.4")


class TestTheRunClaimsNothingBeyondSimulation:
    def _receipt(self, **changes: object) -> SumoRunReceipt:
        payload: dict[str, Any] = {
            "request": _request(),
            "tool": SumoToolIdentity(reported_version="1.27.1", executable_sha256=DIGEST),
            "argument_shape": SUMO_FIXED_ARGUMENTS,
            "exit_code": 0,
            "started_at_utc": datetime(2026, 7, 25, tzinfo=UTC),
            "completed_at_utc": datetime(2026, 7, 25, tzinfo=UTC),
            "duration_s": Decimal("1"),
            "outcome": "accepted",
            "fcd_bytes": 1000,
            "fcd_sha256": DIGEST,
        }
        payload.update(changes)
        return SumoRunReceipt(**payload)

    def test_a_run_is_never_observed_traffic(self) -> None:
        receipt = self._receipt()
        assert receipt.observed_traffic is False
        assert receipt.calibration_performed is False
        assert receipt.comparison_performed is False
        assert receipt.scientifically_validated is False
        assert receipt.supervisor_approved is False

    def test_the_candidate_acceptance_basis_carries_forward(self) -> None:
        assert self._receipt().acceptance_basis == "owner_policy_accepted_candidate"

    def test_a_forged_observed_traffic_claim_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(self._receipt().canonical_json())
        payload["observed_traffic"] = True
        with pytest.raises(ValidationError):
            SumoRunReceipt.model_validate_json(json.dumps(payload))

    def test_an_accepted_run_must_have_exited_zero(self) -> None:
        with pytest.raises(ValidationError, match="must have exited zero"):
            self._receipt(exit_code=1)

    def test_an_accepted_run_must_have_digested_its_fcd(self) -> None:
        with pytest.raises(ValidationError, match="digested FCD artifact"):
            self._receipt(fcd_sha256=None)

    def test_a_receipt_carrying_a_private_path_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="private paths"):
            self._receipt(warning_lines=("Warning: could not read /Users/someone/net.xml",))
