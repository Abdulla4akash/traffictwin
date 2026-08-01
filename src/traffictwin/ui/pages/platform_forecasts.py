"""Forecasts page: the bus prediction layer rendered honestly.

Climatology per (day-type, local hour) with support counts on every cell;
``insufficient_support`` cells shown as exactly that; the progression-speed
target shown as unavailable rather than derived from cadence. The banners are
load-bearing: a forecast is never evidence, and bus progression is never road
speed.
"""

from __future__ import annotations

import streamlit as st

from traffictwin.platform.bus_prediction import (
    ALL_TARGETS,
    TARGET_PROGRESSION_SPEED,
    BuildRules,
    BusPredictionError,
    fit_bus_forecast,
    forecast_climatology,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.platform_services import load_forecast_context
from traffictwin.ui.state import UiConfig

_TARGET_TITLES = {
    "concurrency_median": "Fleet concurrency (median live vehicles per snapshot)",
    "concurrency_max": "Fleet concurrency (max live vehicles per snapshot)",
    TARGET_PROGRESSION_SPEED: "Bus progression speed (m/s)",
}


def render(config: UiConfig) -> None:
    st.title("Forecasts")
    badge_row(["FORECAST — NOT EVIDENCE", "BUS PROGRESSION — NOT ROAD SPEED"])
    st.caption(
        "What this page claims: climatology summaries of this project's own "
        "aggregate bus-session measurements, with support counts. What it does "
        "not claim: evidence, causality, general road traffic, transfer beyond "
        "the fixed Greater Manchester box, or a validated model — the held-out "
        "validation has not run and its predeclaration is unsigned."
    )
    context = load_forecast_context(config.workspace_path)
    if context.load_refusal is not None:
        st.info(
            f"No forecast can be shown: {context.load_refusal}. An empty state "
            "here is designed honesty — nothing is estimated or filled in."
        )
        return

    readiness = context.readiness
    st.caption(
        f"Sources: {context.source_count} aggregate session artifact(s); "
        f"eligible {readiness.get('sources_eligible', 0)} of "
        f"{readiness.get('sources_total', 0)}. Readiness is counted in eligible "
        "distinct local service dates, never wall-clock days."
    )
    dates = readiness.get("eligible_dates_by_day_type")
    if isinstance(dates, dict):
        st.dataframe(
            [
                {"day type": day_type, "eligible dates": len(day_list)}
                for day_type, day_list in sorted(dates.items())
            ],
            hide_index=True,
            width="stretch",
        )

    progression_available = bool(readiness.get("progression_target_available"))
    targets = tuple(
        target
        for target in ALL_TARGETS
        if progression_available or target != TARGET_PROGRESSION_SPEED
    )
    rules = BuildRules()
    try:
        fit = fit_bus_forecast(
            context.aggregates,
            rules,
            generated_at_utc="rendered-live",
            targets=targets,
        )
    except BusPredictionError as error:
        st.info(
            f"No fit is possible yet: {error}. The cells below stay empty rather "
            "than borrowing or smoothing."
        )
        return

    for target in targets:
        st.subheader(_TARGET_TITLES.get(target, target))
        rows = []
        for day_type in ("weekday", "weekend"):
            for hour in range(24):
                record = forecast_climatology(fit, target, day_type, hour, rules=rules)
                if record.value is None and record.support_dates == 0:
                    continue
                rows.append(
                    {
                        "day type": day_type,
                        "hour (local)": hour,
                        "climatology": (
                            "insufficient_support"
                            if record.value is None
                            else round(record.value, 2)
                        ),
                        "interval": (
                            f"[{record.interval_low:.2f}, {record.interval_high:.2f}]"
                            if record.interval_low is not None and record.interval_high is not None
                            else "insufficient_support"
                        ),
                        "support (dates)": record.support_dates,
                    }
                )
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("No cell has any support yet; nothing is shown for this target.")
    if not progression_available:
        st.subheader(_TARGET_TITLES[TARGET_PROGRESSION_SPEED])
        st.warning(
            "**unavailable** — no eligible source carries hourly progression rows "
            "yet; this target is never derived from cadence measurements."
        )
    st.caption(
        f"Fit digest and provenance: forecasts are typed forecast=true / "
        f"evidence=false / causal=false; aggregate schema 1.0; "
        f"{len(fit.fit_dates)} source date(s). Measured aggregates and forecasts "
        "are separate series — proximity on a chart is not validation. The DfT "
        "demand profile is a separate historical road series and is never ground "
        "truth for this bus forecast."
    )
