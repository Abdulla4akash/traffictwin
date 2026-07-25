"""Gate-B reconciliation: the DfT hour stays a local clock label.

`GA-DFT-1` is open: the provider does not state the timezone of its raw-count
`hour`, and no offset has been established. The design's response is to type the
hour as a **local clock-hour label** and never convert it.

That decision only holds if nothing quietly assumes UTC downstream. These checks
exist because such an assumption would be invisible: a UTC conversion produces
plausible numbers, shifted by an unknown amount, and nothing would fail.

These are automated candidate checks and do not close `GA-DFT-1`, which needs a
provider answer or an owner decision.
"""

from __future__ import annotations

from pathlib import Path

from traffictwin.integration.manchester.dft_temporal_profile import (
    DftTemporalProfilePolicy,
    simulation_interval_for_hour,
)

_PROFILE_MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "traffictwin"
    / "integration"
    / "manchester"
    / "dft_temporal_profile.py"
)


class TestTheHourIsALocalClockLabel:
    def test_the_policy_declares_a_local_clock_basis(self) -> None:
        assert DftTemporalProfilePolicy().time_basis == "local_clock_hour"

    def test_the_basis_is_fixed_and_cannot_be_reconfigured(self) -> None:
        # A configurable basis would let a caller select UTC and leave no trace.
        field = DftTemporalProfilePolicy.model_fields["time_basis"]
        assert "local_clock_hour" in str(field.annotation)
        assert "utc" not in str(field.annotation).lower()

    def test_the_module_performs_no_timezone_conversion(self) -> None:
        source = _PROFILE_MODULE.read_text(encoding="utf-8")
        for forbidden in ("astimezone(", "ZoneInfo(", "pytz", "utcoffset("):
            assert forbidden not in source, (
                f"the profile module must not convert timezones; found {forbidden}"
            )


class TestTheSimulationMappingIsAnOffsetNotAConversion:
    def test_the_window_origin_maps_to_zero(self) -> None:
        # Local 07:00 is simulation second 0 by declaration, not by timezone maths.
        assert simulation_interval_for_hour(7) == (0, 3600)

    def test_hours_advance_by_exact_half_open_windows(self) -> None:
        assert simulation_interval_for_hour(8) == (3600, 7200)
        assert simulation_interval_for_hour(18) == (39600, 43200)

    def test_every_window_is_exactly_one_hour(self) -> None:
        for hour in range(7, 19):
            start, end = simulation_interval_for_hour(hour)
            assert end - start == 3600

    def test_windows_are_contiguous_and_non_overlapping(self) -> None:
        previous_end = 0
        for hour in range(7, 19):
            start, end = simulation_interval_for_hour(hour)
            assert start == previous_end, "a gap or overlap would silently drop or double-count"
            previous_end = end


class TestTheOpenBlockerStaysVisible:
    def test_the_module_records_why_the_hour_is_not_utc(self) -> None:
        source = _PROFILE_MODULE.read_text(encoding="utf-8").lower()
        assert "local_clock_hour" in source
        # The reason must travel with the code, not only with a document.
        assert "adr-055" in source or "timezone" in source
