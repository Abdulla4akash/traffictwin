"""Document-only redraw from archived CSV summaries; originals remain unchanged."""
from pathlib import Path
import csv, statistics as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
ROOT=Path(__file__).resolve().parent
ARC=ROOT.parents[2]/'docs/evaluation/vec_followup_2026-09-07/generalisation-replication-2026-09-07'
def rows(name):return list(csv.DictReader((ARC/name).open()))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,'axes.titlesize':10,'legend.fontsize':8.5,'xtick.labelsize':8.5,'ytick.labelsize':8.5,'svg.fonttype':'path'})
seeds=[0,2,3,4]; colors=['#0072B2','#D55E00','#009E73','#8064A2']; arms=['ingress','common_target','per_task']
runs=rows('runs.csv'); lookup={(int(r['fleet_seed']),r['arm']):float(r['attainment_pct']) for r in runs}
fig,ax=plt.subplots(1,2,figsize=(6.55,3.45),gridspec_kw={'width_ratios':[1,1.1]},layout='constrained')
for seed,col in zip(seeds,colors):ax[0].plot(range(3),[lookup[seed,a] for a in arms],'-o',lw=1,ms=4,color=col,label=str(seed))
ax[0].set_xticks(range(3),['Ingress','Common\ntarget','Per-task']);ax[0].set_ylabel('Offered-task attainment (%)');ax[0].set_ylim(82.7,94.4);ax[0].set_title('(a) Matched fleet draws',loc='left');ax[0].legend(title='Fleet seed',ncol=2,frameon=False,loc='upper left',title_fontsize=8.5)
ints=rows('paired_intervals.csv')
for k,(r,(a,b)) in enumerate(zip(ints,[('per_task','ingress'),('common_target','ingress'),('per_task','common_target')])):
 mean=float(r['mean_pp']);lo=float(r['family95_low_pp']);hi=float(r['family95_high_pp'])
 ax[1].errorbar(mean,k,xerr=[[mean-lo],[hi-mean]],fmt='D',color='#243746',ms=4,capsize=3,lw=1.2)
 for seed,col,j in zip(seeds,colors,range(4)):ax[1].plot(lookup[seed,a]-lookup[seed,b],k+(j-1.5)*.065,'o',ms=3,color=col)
ax[1].set_yticks([0,1,2],['Per-task −\ningress','Common −\ningress','Per-task −\ncommon']);ax[1].invert_yaxis();ax[1].set_ylim(2.55,-.55);ax[1].set_xlim(-5.2,10.5);ax[1].set_xlabel('Paired difference (pp)');ax[1].set_title('(b) Simultaneous 95% CIs',loc='left');ax[1].axvline(0,color='#777777',lw=.7,ls='--')
for a in ax:
 a.grid(axis='x' if a is ax[1] else 'y',color='#dedede',lw=.5);a.spines[['top','right']].set_visible(False)
fig.savefig(ROOT/'assets/primary_replication.svg');plt.close(fig)
work=rows('rsu_workload_distribution.csv');fig,ax=plt.subplots(figsize=(6.55,3.15),layout='constrained')
for j,(arm,col,label) in enumerate(zip(arms,['#26748b','#bc693c','#8064A2'],['Ingress','Common-target','Per-task'])):
 values=[[100*float(r['admitted_work_share_per_rsu']) for r in work if r['arm']==arm and int(r['rsu'])==i] for i in range(9)]
 mean=np.array([st.mean(v) for v in values]);lo=np.array([min(v) for v in values]);hi=np.array([max(v) for v in values])
 ax.bar(np.arange(9)+(j-1)*.25,mean,.24,label=label,color=col,yerr=[mean-lo,hi-mean],capsize=1.5,error_kw={'lw':.6})
ax.axhline(100/9,color='#777777',ls='--',lw=.8,label='Equal share');ax.set_xticks(range(9));ax.set_xlabel('Canonical RSU index');ax.set_ylabel('Admitted service-work share (%)');ax.set_ylim(0,54);ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,1.16),frameon=False,columnspacing=1);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',color='#dedede',lw=.5);ax.set_axisbelow(True)
fig.savefig(ROOT/'assets/rsu_workload_distribution.svg');plt.close(fig)
print('Redrew two figures from archived CSVs.')
