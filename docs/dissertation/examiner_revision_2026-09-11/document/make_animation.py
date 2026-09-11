"""Create an explicitly constructed dispatch illustration, not research evidence."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter, FuncAnimation

HERE = Path(__file__).resolve().parents[1]
common = np.zeros(9)
causal = np.zeros(9)
snapshots = [(common.copy(), causal.copy(), 0, 0)]
for step in range(5):
    target = int(np.argmin(common))
    for task in range(18):
        common[target] += 10
        causal[int(np.argmin(causal))] += 10
        snapshots.append((common.copy(), causal.copy(), step + 1, task + 1))
snapshots.extend([snapshots[-1]] * 45)
assert np.count_nonzero(common) == 5 and np.count_nonzero(causal) == 9
assert common.sum() == causal.sum() == 900
fig, ax = plt.subplots(figsize=(12.8, 7.2), layout="constrained")
x = np.arange(9)
first = ax.bar(x - 0.2, common * 0, 0.38, label="Common target per substep")
second = ax.bar(x + 0.2, causal * 0, 0.38, label="Causal per-task reselection")
ax.set_xticks(x, [f"RSU {i}" for i in x])
ax.set_ylim(0, 250)
ax.set_ylabel("Reserved service work (ms)")
ax.set_title("Constructed illustration: five substeps, nine RSUs", fontsize=18)
ax.legend(loc="upper left", frameon=False)
status = ax.text(0.98, 0.94, "", transform=ax.transAxes, ha="right", fontsize=12)
ax.text(
    0.5,
    -0.13,
    "ILLUSTRATION — 18 × 10 ms tasks per substep; no intervening drain; "
    "all admitted. Not measured trajectories.",
    transform=ax.transAxes,
    ha="center",
    fontsize=10,
)
ax.grid(axis="y", alpha=0.2)


def update(frame: int) -> list[object]:
    common_state, causal_state, substep, item = snapshots[frame]
    for bar, height in zip(first, common_state, strict=True):
        bar.set_height(height)
    for bar, height in zip(second, causal_state, strict=True):
        bar.set_height(height)
    status.set_text(
        f"Substep {substep}/5 · proposal {item}/18\n"
        f"Occupied: {np.count_nonzero(common_state)} vs "
        f"{np.count_nonzero(causal_state)} of 9 RSUs"
    )
    return [*first, *second, status]


movie = FuncAnimation(fig, update, frames=len(snapshots), interval=1000 / 15)
movie.save(
    HERE / "video/dispatch_illustration.mp4", writer=FFMpegWriter(fps=15, bitrate=2200), dpi=120
)
plt.close(fig)
