"""Publication/export figures from validated result tables; no simulation."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent/"state-delay-pilot-2026-09-07"
OUT=ROOT/"figures"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,
                     "axes.spines.top":False,"axes.spines.right":False,
                     "axes.titleweight":"bold","axes.labelcolor":"#203040",
                     "text.color":"#203040","xtick.color":"#203040","ytick.color":"#203040",
                     "svg.fonttype":"none","savefig.facecolor":"white"})
BLUE="#156584";ORANGE="#c46628";GRAY="#637181"


def save(fig,name):
    fig.savefig(OUT/f"{name}.png",dpi=220,bbox_inches="tight")
    fig.savefig(OUT/f"{name}.svg",bbox_inches="tight")
    plt.close(fig)


with (ROOT/"forwarding_sensitivity.csv").open() as f:
    rows=list(csv.DictReader(f))
x=np.array([float(r["forwarding_ms"]) for r in rows])
effect=np.array([float(r["difference_from_ingress_pp"]) for r in rows])
loss=np.array([int(r["additional_deadline_misses"]) for r in rows])
fig,axs=plt.subplots(1,2,figsize=(10.8,4.4))
fig.subplots_adjust(top=.81,bottom=.24,wspace=.31)
fig.suptitle("Forwarding-cost sensitivity",fontsize=16,x=.08,ha="left")
fig.text(.08,.875,"Manchester incident · fleet seed 1 · 13,076,234 offered tasks",fontsize=10,color=GRAY)
axs[0].plot(x,effect,"o-",color=BLUE,lw=2,ms=6)
axs[0].axhline(0,color=GRAY,ls="--",lw=1)
axs[0].set(xlabel="Added forwarding latency (ms)",ylabel="Advantage over ingress (percentage points)",
           xticks=x,ylim=(min(0,float(effect.min())-.03),max(.5,float(effect.max())+.06)))
axs[0].annotate(f"{effect[-1]:+.3f} pp",(x[-1],effect[-1]),xytext=(-10,14),textcoords="offset points",ha="right",color=BLUE)
axs[1].plot(x,loss,"o-",color=ORANGE,lw=2,ms=6)
axs[1].set(xlabel="Added forwarding latency (ms)",ylabel="Additional deadline misses versus 0 ms",xticks=x,ylim=(0,max(loss)*1.2))
axs[1].ticklabel_format(axis="y",style="plain")
axs[1].annotate(f"{loss[-1]:,}",(x[-1],loss[-1]),xytext=(-10,14),textcoords="offset points",ha="right",color=ORANGE)
for ax in axs:ax.grid(axis="y",alpha=.2);ax.set_axisbelow(True)
fig.text(.08,.08,"Single-draw qualified counterfactual; points show tested costs. Admission, queues and energy stay fixed.",fontsize=9,color=GRAY)
fig.text(.08,.035,"No inference beyond the tested 0–10 ms range; no physical backhaul congestion is modeled.",fontsize=9,color=GRAY)
save(fig,"forwarding_sensitivity")

audit=json.loads((PILOT/"mechanism_audit.json").read_text())
B=audit["rows"][0]["maximum_post_admission_workload_ms"]
t=np.linspace(0,1000,1001);w=np.maximum(B-t,0)
fig,ax=plt.subplots(figsize=(10.5,4.7));fig.subplots_adjust(top=.79,bottom=.22,left=.09,right=.95)
fig.suptitle("Why the 100 ms report matches fresh state",x=.09,ha="left",fontsize=16)
fig.text(.09,.865,f"Illustration using the observed maximum post-admission workload: {B:.2f} ms",fontsize=10,color=GRAY)
ax.plot(t,w,color=BLUE,lw=2.5)
ax.fill_between(t,w,alpha=.08,color=BLUE)
samples=[(0,B,"1-second-old report",(18,-5)),(500,max(B-500,0),"500 ms-old report",(-75,38)),
         (900,0,"100 ms-old report",(-102,78)),(1000,0,"Fresh report",(-50,32))]
for xx,yy,label,offset in samples:
    ax.scatter([xx],[yy],color=ORANGE,s=40,zorder=4)
    ax.annotate(f"{label}\n{yy:.2f} ms",(xx,yy),xytext=offset,textcoords="offset points",
                arrowprops={"arrowstyle":"-","color":GRAY},fontsize=10)
ax.axvline(B,color=GRAY,ls=":",lw=1)
ax.set(xlabel="Service time elapsed since the previous admission batch (ms)",ylabel="Remaining compute workload (ms)",
       xlim=(-15,1030),ylim=(-30,650),xticks=[0,500,900,1000])
ax.grid(axis="y",alpha=.2)
fig.text(.09,.065,"All tasks in a batch arrive before service drains the queue. No new admissions occur between batches.",fontsize=9,color=GRAY)
fig.text(.09,.025,"This illustrates the model’s timing convention; it is not a measured real-world arrival process.",fontsize=9,color=GRAY)
save(fig,"state_delay_timing")

with (PILOT/"comparison.csv").open() as f:state=list(csv.DictReader(f))
state=state[:4]
age=np.array([0,100,500,1000]);att=np.array([float(r["difference_from_ingress_pp"]) for r in state])
fig,ax=plt.subplots(figsize=(8,4.2));fig.subplots_adjust(top=.78,bottom=.24,left=.12,right=.94)
fig.suptitle("Placement performance with older workload reports",x=.12,ha="left",fontsize=14)
fig.text(.12,.85,"Manchester incident · one fleet draw · live admission and immediate acknowledgements",fontsize=9,color=GRAY)
ax.plot(age,att,"o-",color=BLUE,lw=2,ms=6)
ax.axhline(0,color=GRAY,ls="--",lw=1)
ax.set(xlabel="Workload-report age (ms)",ylabel="Advantage over ingress (pp)",xticks=age,ylim=(0,.55))
for xx,yy in zip(age,att):
    offset=(0,12) if xx!=100 else (10,-20)
    ax.annotate(f"{yy:.4f}",(xx,yy),xytext=offset,textcoords="offset points",ha="center",fontsize=9)
ax.grid(axis="y",alpha=.2)
fig.text(.12,.07,"The 100 ms arm received identical workload values to fresh state. Differences are descriptive.",fontsize=9,color=GRAY)
save(fig,"state_delay_outcomes")
print("Saved PNG and SVG figures:",", ".join(p.name for p in OUT.iterdir()))
