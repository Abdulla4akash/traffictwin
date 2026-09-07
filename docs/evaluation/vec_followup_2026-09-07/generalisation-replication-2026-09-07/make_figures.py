"""Export primary replication figures after the declared analysis completes."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT/"figures"
OUT.mkdir(exist_ok=True)
result = json.loads((ROOT/"analysis_validation.json").read_text())
assert result["status"] == "passed" and result["primary_seeds"] == [0, 2, 3, 4]
plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10,
    "axes.spines.top":False, "axes.spines.right":False,
    "text.color":"#203040", "axes.labelcolor":"#203040",
    "xtick.color":"#203040", "ytick.color":"#203040", "svg.fonttype":"none"})
COLORS = ["#176582", "#b75c2a", "#6e5ba7", "#48803b"]
GRAY = "#687685"


def save(fig, name):
    fig.savefig(OUT/f"{name}.png", dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT/f"{name}.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


fig, axes = plt.subplots(1, 2, figsize=(12.3, 5.2), gridspec_kw={"width_ratios":[1, 1.15]})
fig.subplots_adjust(top=.78, bottom=.23, left=.08, right=.97, wspace=.59)
fig.suptitle("Three-arm replication across four new fleets", x=.08, ha="left", fontsize=17)
fig.text(.08, .87, "Manchester working-day morning · fleet seeds 0, 2, 3, 4 · pilot seed 1 excluded", color=GRAY)
for color, row in zip(COLORS, result["primary_paired"]):
    values = [row[k] for k in ("ingress_pct", "common_target_pct", "per_task_pct")]
    axes[0].plot(range(3), values, "o-", color=color, alpha=.85, lw=1.5, label=f"Seed {row['fleet_seed']}")
axes[0].set(xticks=range(3), xticklabels=["Ingress", "Common-target", "Per-task"], ylabel="Offered-task deadline attainment (%)")
axes[0].legend(frameon=False, ncol=2, fontsize=9, loc="lower center", bbox_to_anchor=(.5, 1.0))
axes[0].grid(axis="y", alpha=.2)
contrast_labels = ["Per-task − ingress", "Common − ingress", "Per-task − common"]
for index, contrast in enumerate(result["primary_contrasts"]):
    mean, low, high = (contrast[k] for k in ("mean_pp", "family95_low_pp", "family95_high_pp"))
    y = 2-index
    axes[1].errorbar(mean, y, xerr=np.array([[mean-low],[high-mean]]), fmt="D", color="#203040", ms=6, lw=2, capsize=5)
    key = contrast["contrast"]+"_pp"
    for offset, color, row in zip([-.12,-.04,.04,.12], COLORS, result["primary_paired"]):
        axes[1].scatter(row[key], y+offset, color=color, s=18, alpha=.85, zorder=3)
    axes[1].annotate(f"{mean:+.3f} pp", (mean,y), xytext=(0,16), textcoords="offset points", ha="center", fontsize=9)
axes[1].axvline(0, color=GRAY, ls="--", lw=1)
axes[1].set(yticks=[2,1,0], yticklabels=contrast_labels, ylim=(-.45,2.55), xlabel="Paired attainment difference (percentage points)")
axes[1].grid(axis="x", alpha=.2)
fig.text(.08,.09,"Left: lines connect the three arms within each fleet draw. Right: diamonds show mean paired differences.",color=GRAY,fontsize=9)
fig.text(.08,.045,"Whiskers: simultaneous 95% t intervals (Bonferroni, 3 contrasts, n=4 draws). Coloured points: individual draw differences.",color=GRAY,fontsize=9)
save(fig,"primary_replication")

with (ROOT/"rsu_workload_distribution.csv").open() as handle:
    rows = list(csv.DictReader(handle))
fig, ax = plt.subplots(figsize=(11.1, 4.8))
fig.subplots_adjust(top=.78,bottom=.23,left=.08,right=.97)
fig.suptitle("How admitted compute work is distributed across RSUs", x=.08, ha="left", fontsize=16)
fig.text(.08,.875,"Same four new fleet draws · fixed capacity 6,220 tasks/RSU · service 1× · forwarding 0 ms",color=GRAY,fontsize=10)
for offset, arm, label, color in zip([-.25,0,.25], ["ingress","common_target","per_task"],
                                    ["Ingress","Common-target","Per-task"], COLORS[:3]):
    samples = np.array([[100*float(next(r["admitted_work_share_per_rsu"] for r in rows
                                     if int(r["fleet_seed"])==seed and r["arm"]==arm and int(r["rsu"])==rsu))
                         for rsu in range(9)] for seed in result["primary_seeds"]])
    mean = samples.mean(axis=0)
    err = np.vstack([mean-samples.min(axis=0), samples.max(axis=0)-mean])
    ax.bar(np.arange(9)+offset,mean,width=.23,label=label,color=color,alpha=.9,yerr=err,
           error_kw={"elinewidth":1,"capsize":2,"capthick":1})
ax.axhline(100/9,color=GRAY,ls="--",lw=1,label="Equal share")
ax.set(xticks=range(9),xlabel="Canonical RSU index",ylabel="Share of admitted RSU service work (%)",ylim=(0,None))
ax.legend(frameon=False,ncol=4,fontsize=9,loc="lower center",bbox_to_anchor=(.5,1.0))
ax.grid(axis="y",alpha=.2);ax.set_axisbelow(True)
fig.text(.08,.09,"Bars: mean share across fleet draws. Whiskers: observed minimum–maximum across those four draws.",color=GRAY,fontsize=9)
fig.text(.08,.045,"Work shares describe placement; the replication unit remains the fleet draw. RSUs and individual tasks are not replications.",color=GRAY,fontsize=9)
save(fig,"rsu_workload_distribution")
print("Saved primary-replication and RSU-workload figures as PNG and SVG.")
