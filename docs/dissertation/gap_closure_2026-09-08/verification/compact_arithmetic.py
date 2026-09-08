"""Recalculate archived summary arithmetic only. Never loads raw NPZ or the evaluator."""
from pathlib import Path
import csv, json, math, statistics as st, hashlib
from scipy.stats import t
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
ROOT=parser.parse_args().output;ROOT.mkdir(parents=True,exist_ok=True)
REPO=Path(__file__).resolve().parent/'sources'
ARC=REPO/'vec_followup_2026-09-07'
sources={}
def read(p):
 p=Path(p); sources[str(p.relative_to(REPO))]=hashlib.sha256(p.read_bytes()).hexdigest()
 if p.suffix=='.csv':return list(csv.DictReader(p.open()))
 return json.loads(p.read_text())
def interval(x,m=1):
 n=len(x); mean=st.mean(x); sd=st.stdev(x); h=t.ppf(1-.05/(2*m),n-1)*sd/math.sqrt(n)
 return dict(mean_pp=mean,sd_pp=sd,low_pp=mean-h,high_pp=mean+h,n=n)
def near(a,b,tol=1e-8):assert abs(float(a)-float(b))<=tol,(a,b)
e1=read(ARC/'historical_e0_e2d/experiments/E1/evidence/e1_multidraw_physical_campaign_comparison_v1.json')
e1calc=interval([100*e1['per_seed_higher_cap_minus_lower_cap'][str(i)]['40x_minus_0p75']['deadline_attainment_offered'] for i in range(5)])
near(e1calc['mean_pp'],100*e1['primary_estimand']['mean'])
near(e1calc['low_pp'],100*e1['primary_estimand']['confidence_interval']['lower'])
near(e1calc['high_pp'],100*e1['primary_estimand']['confidence_interval']['upper'])
e2b=read(ARC/'historical_e0_e2d/experiments/E2b/evidence/e2b_placement_admission_factorial_comparison_v1_public_sanitized.json')
vals={k:100*v['deadline_met_tasks']/v['offered_tasks'] for k,v in e2b['arms'].items()}
for k,v in e2b['arms'].items():near(vals[k],100*v['offered_task_deadline_attainment'])
e2bcalc={'arm_percentages':vals,'strongest_link_contrast_pp':vals['ingress_dla']-vals['off'],'common_target_contrast_pp':vals['dla']-vals['jsq'],'interaction_pp':vals['dla']-vals['jsq']-(vals['ingress_dla']-vals['off'])}
inc=read(ARC/'historical_e0_e2d/experiments/E2d/data/e2d_paired_results.csv')
contrasts={'per_task_minus_ingress':('per_task','ingress'),'common_target_minus_ingress':('common_target','ingress'),'per_task_minus_common_target':('per_task','common_target')}
ic={name:interval([100*(float(r[a+'_dla_offered_attainment'])-float(r[b+'_dla_offered_attainment'])) for r in inc]) for name,(a,b) in contrasts.items()}
morning=read(ARC/'generalisation-replication-2026-09-07/runs.csv')
assert set(int(r['fleet_seed']) for r in morning)=={0,2,3,4}
assert len(morning)==12
lookup={(int(r['fleet_seed']),r['arm']):r for r in morning}
for r in morning:
 near(100*int(r['deadline_met'])/int(r['offered']),r['attainment_pct'])
 assert int(r['offered'])==int(r['admitted'])+sum(int(r[k]) for k in ['gate_rejected','cap_rejected','local_mqd_rejected','v2v_mqd_rejected','v2i_unavailable','v2v_unavailable'])
archived=read(ARC/'generalisation-replication-2026-09-07/paired_intervals.csv')
mc={}
for name,(a,b) in contrasts.items():
 diffs=[float(lookup[i,a]['attainment_pct'])-float(lookup[i,b]['attainment_pct']) for i in [0,2,3,4]]
 v=interval(diffs); family=interval(diffs,3); ar=next(r for r in archived if r['contrast']==name)
 for key,expected in [('mean_pp',v['mean_pp']),('sd_pp',v['sd_pp']),('ci95_low_pp',v['low_pp']),('ci95_high_pp',v['high_pp']),('family95_low_pp',family['low_pp']),('family95_high_pp',family['high_pp'])]:near(ar[key],expected)
 mc[name]={'individual':v,'simultaneous':family,'mean_additional_successes_per_draw':st.mean(int(lookup[i,a]['deadline_met'])-int(lookup[i,b]['deadline_met']) for i in [0,2,3,4])}
means={a:st.mean(float(r['attainment_pct']) for r in morning if r['arm']==a) for a in ['ingress','common_target','per_task']}
incmeans={a:st.mean(100*float(r[a+'_dla_offered_attainment']) for r in inc) for a in ['ingress','common_target','per_task']}
practical={'incident':{'arm_mean_pct':incmeans,'pp':ic['per_task_minus_ingress']['mean_pp'],'relative_success_increase_pct':100*ic['per_task_minus_ingress']['mean_pp']/incmeans['ingress'],'extra_successes_per_10000_offered':100*ic['per_task_minus_ingress']['mean_pp']},'morning':{'arm_mean_pct':means,'pp':mc['per_task_minus_ingress']['individual']['mean_pp'],'relative_success_increase_pct':100*mc['per_task_minus_ingress']['individual']['mean_pp']/means['ingress'],'extra_successes_per_10000_offered':100*mc['per_task_minus_ingress']['individual']['mean_pp']}}
forward=read(ARC/'forwarding-sensitivity-2026-09-07/forwarding_sensitivity.csv')
for r in forward:
 near(int(r['deadline_met'])/int(r['n_offered']),r['deadline_attainment'])
 near(100*(int(r['deadline_met'])-int(r['ingress_deadline_met']))/int(r['n_offered']),r['difference_from_ingress_pp'])
 assert int(r['additional_deadline_misses'])==int(forward[0]['deadline_met'])-int(r['deadline_met'])
delay=read(ARC/'state-delay-pilot-2026-09-07/comparison.csv')
for r in delay:
 near(100*(float(r['deadline_attainment'])-float(delay[0]['deadline_attainment'])),r['difference_from_fresh_pp'])
# Additional descriptive checks from compact records, not raw-task reanalysis.
e1lat={label:st.mean(float(r['latency_ms_per_admitted_task']) for r in e1['rows'] if r['cap_label']==label) for label in ['0p75','2p5','40x']}
for r in e1['rows']:near(int(r['deadline_met_tasks'])/int(r['offered_tasks']),r['deadline_attainment_offered'])
audit=read(REPO/'common_target_mechanism_audit_2026-09-07/evidence/audit_results.json')
ds=audit['draws']; ac={'observed_targets':sum(d['observed_target_substeps'] for d in ds),'unobserved_substeps':sum(d['substeps_without_observable_v2i_target'] for d in ds),'all_five_seconds':sum(d['per_second_execution_rsu_count_histogram']['5'] for d in ds),'gate_rejections':sum(d['gate_rejected_tasks'] for d in ds),'cap_rejections':sum(d['capacity_rejected_tasks'] for d in ds),'endpoint_entries_per_field':sum(d['seconds']*9 for d in ds),'max_workload_range_ms':[min(d['maximum_reconstructed_pre_drain_workload_ms'] for d in ds),max(d['maximum_reconstructed_pre_drain_workload_ms'] for d in ds)],'minimum_other_idle_rsus':min(d['minimum_other_idle_rsus_in_rejecting_substeps'] for d in ds)}
assert ac['observed_targets']==179427 and ac['unobserved_substeps']==36573 and ac['all_five_seconds']==15803
assert ac['gate_rejections']==511684 and ac['cap_rejections']==0 and ac['minimum_other_idle_rsus']==5
work=read(ARC/'generalisation-replication-2026-09-07/rsu_workload_distribution.csv')
shares={a:[100*st.mean(float(r['admitted_work_share_per_rsu']) for r in work if r['arm']==a and int(r['rsu'])==i) for i in range(9)] for a in ['ingress','common_target','per_task']}
for v in shares.values():near(sum(v),100)
pilot=read(ARC/'generalisation-pilot-2026-09-07/metrics.csv')
pilot_by={r['condition']:r for r in pilot}
for r in pilot:near(int(r['deadline_met'])/int(r['offered']),r['deadline_attainment'])
pilot_diff=int(pilot_by['fresh']['deadline_met'])-int(pilot_by['ingress']['deadline_met'])
assert pilot_diff==51503
near(100*pilot_diff/int(pilot_by['fresh']['offered']),pilot_by['fresh']['difference_from_ingress_pp'])
delay_audit=read(ARC/'state-delay-pilot-2026-09-07/mechanism_audit.json')
# Dimensional simplification of the inspected homogeneous RSU constants, not
# an evaluator execution or new service measurement.
service=[c/(2.2*1.5*min(12,p)*.9*min(5,g)) for c,p,g in zip([1254,2100,15],[4,4,2],[40,5,1])]
for value,display in zip(service,[21.111,35.354,2.525]):near(value,display,.000501)
report={'status':'passed','scope':'Archived summary counts, rates and original paired t/Bonferroni intervals recalculated; no new tests, simulations or raw-task reanalysis. E1/E2d rounded archived inputs limit precision.','sources_sha256':sources,'e1':e1calc,'e1_mean_admitted_latency_ms':e1lat,'mechanism_compact_totals':ac,'mean_work_shares_pct':shares,'pilot_archived_metrics':pilot,'e2b':e2bcalc,'incident':ic,'morning':mc,'practical_scale':practical,'delay_pct':{r['condition']:100*float(r['deadline_attainment']) for r in delay},'forwarding_pct':{r['forwarding_ms']:100*float(r['deadline_attainment']) for r in forward}}
report.update({'pilot_extra_successes':pilot_diff,'rsu_service_before_noise_ms':service,'report_state_audit_inspected':delay_audit})
(ROOT/'ARITHMETIC.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'e1':e1calc,'e2b':e2bcalc,'practical_scale':practical,'status':'passed'},indent=2))

with (ROOT/'CENTRAL_TABLES.csv').open('w',newline='') as f:
 writer=csv.writer(f);writer.writerow(['study','contrast','n','mean_pp','low_pp','high_pp','interval_family'])
 writer.writerow(['E1','40x_minus_0p75',5,e1calc['mean_pp'],e1calc['low_pp'],e1calc['high_pp'],'individual 95% historical score'])
 for name,v in ic.items():writer.writerow(['incident E2d',name,4,v['mean_pp'],v['low_pp'],v['high_pp'],'individual 95% adaptive extension'])
 for name,v in mc.items():
  w=v['simultaneous'];writer.writerow(['morning primary',name,4,w['mean_pp'],w['low_pp'],w['high_pp'],'Bonferroni simultaneous 95% three contrasts'])
