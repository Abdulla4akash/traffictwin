#!/usr/bin/env python3
"""Generate the public academic figures from committed compact CSV files."""

from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
NAVY = "#17324D"
BLUE = "#2F6B9A"
TEAL = "#2A9D8F"
ORANGE = "#E69F00"
RED = "#C44536"
GRAY = "#6B7280"


def configure() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 10,
            "axes.edgecolor": "#334155",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": "#CBD5E1",
            "grid.linewidth": 0.7,
            "grid.alpha": 0.6,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def read_csv(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def save(fig: Figure, name: str, *, pdf: bool = False) -> None:
    fig.savefig(FIGURES / f"{name}.png", dpi=220, bbox_inches="tight")
    if pdf:
        frozen_time = datetime(2026, 8, 12, tzinfo=UTC)
        fig.savefig(
            FIGURES / f"{name}.pdf",
            bbox_inches="tight",
            metadata={
                "Creator": "TrafficTwin public research figure generator",
                "CreationDate": frozen_time,
                "ModDate": frozen_time,
            },
        )
    plt.close(fig)


def add_zero_line(ax: Axes) -> None:
    ax.axhline(0, color=NAVY, linewidth=1.2, zorder=1)


def research_timeline() -> None:
    stages = ["E0", "E1", "E2", "E2b", "E2c", "E2d"]
    titles = [
        "Accounting\nvalidated",
        "Queue-cap primary\ninconclusive",
        "Balance ≠\ndeadline benefit",
        "Admission separated\nfrom placement",
        "Common-target\n−2.12 pp",
        "Per-task\n+0.53 pp",
    ]
    colors = [NAVY, GRAY, ORANGE, BLUE, RED, TEAL]
    x = np.arange(len(stages), dtype=float)
    fig, ax = plt.subplots(figsize=(13.2, 3.7))
    ax.set_xlim(-0.55, len(stages) - 0.45)
    ax.set_ylim(-1.0, 1.15)
    ax.axis("off")
    ax.plot(x, np.zeros_like(x), color="#94A3B8", linewidth=2.0, zorder=1)
    for index in range(len(stages) - 1):
        ax.annotate(
            "",
            xy=(x[index + 1] - 0.13, 0),
            xytext=(x[index] + 0.13, 0),
            arrowprops={"arrowstyle": "->", "color": "#64748B", "lw": 1.4},
        )
    for idx, (stage, title, color) in enumerate(zip(stages, titles, colors, strict=True)):
        ax.scatter(x[idx], 0, s=900, color=color, edgecolor="white", linewidth=2.5, zorder=3)
        ax.text(x[idx], 0, stage, color="white", ha="center", va="center", weight="bold", size=11)
        offset = 0.55 if idx % 2 == 0 else -0.58
        ax.text(
            x[idx],
            offset,
            title,
            ha="center",
            va="center",
            color=NAVY,
            weight="semibold" if idx in {4, 5} else "normal",
            linespacing=1.25,
        )
    ax.set_title(
        "TrafficTwin research progression: validity → intervention → decomposition → falsification",
        color=NAVY,
        weight="bold",
        pad=8,
    )
    fig.text(
        0.5,
        0.015,
        "Each stage was motivated by a specific unresolved question in the previous stage.",
        ha="center",
        color=GRAY,
        size=9,
    )
    save(fig, "research_timeline", pdf=True)


def e1_capacity() -> None:
    rows = read_csv("experiments/E1/data/e1_capacity_aggregate.csv")
    labels = [row["cap_label"] for row in rows]
    admitted = np.array([float(row["mean_admitted_tasks"]) / 1e6 for row in rows])
    latency = np.array([float(row["mean_admitted_latency_ms"]) / 1000 for row in rows])
    offered = np.array([float(row["mean_offered_deadline_attainment"]) * 100 for row in rows])
    x = np.arange(len(labels))
    colors = ["#94A3B8", BLUE, ORANGE]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2))
    panels: list[tuple[Axes, np.ndarray, str, str]] = [
        (axes[0], admitted, "Mean admitted tasks", "million tasks"),
        (axes[1], latency, "Mean admitted latency", "seconds"),
        (axes[2], offered, "Mean offered deadline attainment", "% offered tasks"),
    ]
    for ax, values, title, ylabel in panels:
        bars = ax.bar(x, values, color=colors, width=0.64, zorder=2)
        ax.set_xticks(x, labels)
        ax.set_title(title, color=NAVY, weight="semibold")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y")
        baseline = min(values) if title == "Mean offered deadline attainment" else 0
        if baseline:
            ax.set_ylim(baseline - 0.015, max(values) + 0.015)
        for bar, value in zip(bars, values, strict=True):
            if title == "Mean offered deadline attainment":
                label = f"{value:.3f}%"
            elif title == "Mean admitted tasks":
                label = f"{value:.3f}M"
            else:
                label = f"{value:.1f}s"
            ax.text(
                bar.get_x() + bar.get_width() / 2, bar.get_height(), label, ha="center", va="bottom", size=9
            )
    fig.suptitle(
        "E1: larger waiting rooms admit more work but do not add service", color=NAVY, weight="bold", size=15
    )
    fig.text(
        0.5,
        0.01,
        "Five-draw descriptive means. Primary 40×−0.75× offered-attainment 95% CI "
        "included zero; no significance claim.",
        ha="center",
        color=GRAY,
        size=8.8,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.91))
    save(fig, "e1_capacity_result")


def e2b_factorial() -> None:
    cells = {
        row["arm"]: float(row["offered_deadline_attainment"]) * 100
        for row in read_csv("experiments/E2b/data/e2b_factorial.csv")
    }
    x = np.array([0, 1])
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    ax.plot(
        x,
        [cells["off"], cells["ingress_dla"]],
        marker="o",
        markersize=8,
        linewidth=2.3,
        color=BLUE,
        label="Strongest-link execution",
    )
    ax.plot(
        x,
        [cells["jsq"], cells["dla"]],
        marker="o",
        markersize=8,
        linewidth=2.3,
        color=ORANGE,
        label="Inherited least-busy",
    )
    ax.set_xticks(x, ["Ordinary admission", "Deadline-aware admission"])
    ax.set_ylabel("Offered-task deadline attainment (%)")
    ax.set_title("E2b: placement × admission mechanism decomposition", color=NAVY, weight="bold")
    ax.grid(axis="y")
    ax.legend(frameon=False, loc="lower right")
    for xpos, values in zip(
        x, ([cells["off"], cells["jsq"]], [cells["ingress_dla"], cells["dla"]]), strict=True
    ):
        for value in values:
            ax.text(xpos, value + 0.18, f"{value:.2f}%", ha="center", color=NAVY, size=9)
    fig.text(
        0.5,
        0.02,
        "One draw; hypothesis-generating mechanism decomposition",
        ha="center",
        color=GRAY,
        size=8.7,
    )
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save(fig, "e2b_factorial")


def e2c_replication() -> None:
    rows = read_csv("experiments/E2c/data/e2c_paired_results.csv")
    seeds = [row["fleet_seed"] for row in rows]
    values = np.array([float(row["dla_minus_ingress_dla"]) * 100 for row in rows])
    mean = -2.1222260935
    lower = -2.2335254070
    upper = -2.0109267800
    fig, ax = plt.subplots(figsize=(8.3, 4.8))
    x = np.arange(len(seeds))
    ax.bar(x, values, color=RED, width=0.62, zorder=2)
    add_zero_line(ax)
    ax.axhline(mean, color=NAVY, linestyle="--", linewidth=1.4, label=f"Mean {mean:.2f} pp")
    ax.fill_between([-0.45, 3.45], lower, upper, color=RED, alpha=0.11, label="95% t interval for mean")
    ax.set_xticks(x, [f"Seed {seed}" for seed in seeds])
    ax.set_ylabel("DLA − ingress-DLA (percentage points)")
    ax.set_title(
        "E2c: common-target placement differences were negative in all new draws", color=NAVY, weight="bold"
    )
    ax.grid(axis="y")
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.01))
    for xpos, value in zip(x, values, strict=True):
        ax.text(
            float(xpos),
            value + 0.08,
            f"{value:.2f}",
            ha="center",
            va="bottom",
            color="white",
            weight="bold",
            size=9,
        )
    fig.tight_layout(rect=(0, 0.11, 1, 1))
    save(fig, "e2c_replication")


def e2d_reversal() -> None:
    rows = read_csv("experiments/E2d/data/e2d_paired_results.csv")
    seeds = [row["fleet_seed"] for row in rows]
    common = np.array([float(row["per_task_minus_common_target"]) for row in rows])
    primary = np.array([float(row["per_task_minus_ingress"]) for row in rows])
    # Recover common-target minus ingress from the two committed contrasts.
    e2c = primary - common
    x = np.arange(len(seeds))
    width = 0.34
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    bars_a = ax.bar(
        x - width / 2, e2c * 100, width, color=RED, label="E2c common-target − strongest-link", zorder=2
    )
    bars_b = ax.bar(
        x + width / 2, primary * 100, width, color=TEAL, label="E2d per-task − strongest-link", zorder=2
    )
    add_zero_line(ax)
    ax.set_xticks(x, [f"Seed {seed}" for seed in seeds])
    ax.set_ylabel("Offered-attainment difference (percentage points)")
    ax.set_title(
        "Dispatch granularity reversed the observed placement direction", color=NAVY, weight="bold", size=15
    )
    ax.grid(axis="y")
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 0.01))
    for bars in (bars_a, bars_b):
        for bar in bars:
            value = bar.get_height()
            va = "bottom" if value >= 0 else "top"
            offset = 0.05 if value >= 0 else -0.05
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + offset,
                f"{value:+.2f}",
                ha="center",
                va=va,
                size=8.7,
                weight="semibold",
            )
    fig.text(
        0.5,
        0.075,
        "Four matched fleet draws; same deadline-aware admission gate",
        ha="center",
        color=GRAY,
        size=9,
    )
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    save(fig, "e2d_direction_reversal")


def execution_balance() -> None:
    rows = read_csv("experiments/E2d/data/e2d_mechanism_summary.csv")
    labels = ["Strongest-link\n(ingress-DLA)", "Common-target\nleast-busy", "Per-task sequential\nleast-busy"]
    arms = ["ingress_dla", "common_target_dla", "per_task_dla"]
    colors = [BLUE, RED, TEAL]
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for xpos, (arm, color) in enumerate(zip(arms, colors, strict=True)):
        values = [float(row["execution_share_range"]) for row in rows if row["arm"] == arm]
        jitter = np.array([-0.09, -0.03, 0.03, 0.09])
        ax.scatter(
            np.full(len(values), xpos) + jitter,
            values,
            s=68,
            color=color,
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
        )
        ax.hlines(np.mean(values), xpos - 0.22, xpos + 0.22, color=NAVY, linewidth=2.1, zorder=2)
    ax.set_xticks(np.arange(3), labels)
    ax.set_yscale("log")
    ax.set_ylabel("Execution-share range (log scale; lower is more balanced)")
    ax.set_title(
        "Execution balance changed substantially with placement semantics", color=NAVY, weight="bold"
    )
    ax.grid(axis="y", which="both")
    ax.text(
        0.02,
        0.04,
        "Points are fleet seeds 1–4; line is the mean",
        transform=ax.transAxes,
        color=GRAY,
        size=8.8,
    )
    fig.tight_layout()
    save(fig, "execution_balance_comparison")


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    configure()
    generators: list[tuple[str, Callable[[], None]]] = [
        ("research_timeline", research_timeline),
        ("e1_capacity_result", e1_capacity),
        ("e2b_factorial", e2b_factorial),
        ("e2c_replication", e2c_replication),
        ("e2d_direction_reversal", e2d_reversal),
        ("execution_balance_comparison", execution_balance),
    ]
    for name, generator in generators:
        generator()
        print(f"generated {name}")


if __name__ == "__main__":
    main()
