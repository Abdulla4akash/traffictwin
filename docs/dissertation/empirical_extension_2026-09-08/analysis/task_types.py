"""New type aggregation of eight authenticated September files, one at a time.
No actor, evaluator, task join, inferential test or historical output recovery.
"""
from pathlib import Path
import argparse, csv, hashlib, json
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OLD=ROOT/'docs/dissertation/gap_closure_2026-09-08/verification'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''): h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--raw-root',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 inv={x['path']:x for x in json.loads((OLD/'RAW_INPUTS.json').read_text())['raw_files']}
 runs=json.loads((OLD/'RUNS.json').read_text());rows=[];bindings=[]
 for seed in [0,2,3,4]:
  for arm in ['ingress','per_task']:
   rid=f'generalisation-replication-2026-09-07/cells/seed_{seed}_{arm}/attempt_001'
   run=next(x for x in runs if x['id']==rid);rel=run['files']['per_task.npz'];path=a.raw_root/rel;expected=inv[rel]
   if not path.is_file():raise SystemExit(f'Missing explicitly listed September input: {rel}')
   actual=sha(path)
   if actual!=expected['sha256'] or path.stat().st_size!=expected['bytes']:raise SystemExit(f'Input mismatch: {rel}')
   sp=OLD/run['summary'];s=json.loads(sp.read_text());local=[]
   with np.load(path,allow_pickle=False) as z:
    typ=z['task_type'];active=z['task_active'];outcome=z['task_outcome'];met=z['task_met']
    if not np.all(np.isin(typ[active],[0,1,2])):raise ValueError('Unknown active task type')
    for t in range(3):
     mask=active&(typ==t);oc=outcome[mask];n=int(mask.sum());success=int(met[mask].sum());adm=int(np.isin(oc,[1,2]).sum());gate=int((oc==3).sum());miss=int((oc==2).sum());other=int((oc>=4).sum())
     assert n==adm+gate+other and success==int((oc==1).sum()) and adm==success+miss
     row=dict(seed=seed,arm=arm,type=t+1,deadline_ms=[100,500,100][t],offered=n,successes=success,attainment_pct=100*success/n,admitted=adm,gate_rejected=gate,admitted_misses=miss,other_terminal=other);rows.append(row);local.append(row)
   totals={k:sum(x[k] for x in local) for k in ['offered','successes','admitted','gate_rejected','admitted_misses','other_terminal']}
   assert totals['offered']==s['n_offered'] and totals['admitted']==s['n_admitted'] and totals['gate_rejected']==s['v2i_gate_rejected']
   assert abs(totals['successes']-s['completion']*s['n_offered'])<1e-6
   bindings.append(dict(run=rid,path=rel,sha256=actual,bytes=path.stat().st_size,summary_sha256=sha(sp),totals=totals))
   print(f'Aggregated {seed} {arm}',flush=True)
 paired=[]
 for seed in [0,2,3,4]:
  for t in [1,2,3]:
   x=next(x for x in rows if (x['seed'],x['arm'],x['type'])==(seed,'ingress',t));y=next(x for x in rows if (x['seed'],x['arm'],x['type'])==(seed,'per_task',t));assert x['offered']==y['offered']
   paired.append(dict(seed=seed,type=t,offered=x['offered'],ingress_successes=x['successes'],per_task_successes=y['successes'],net_successes=y['successes']-x['successes'],difference_pp=y['attainment_pct']-x['attainment_pct'],gate_change=y['gate_rejected']-x['gate_rejected'],admitted_miss_change=y['admitted_misses']-x['admitted_misses'],other_terminal_change=y['other_terminal']-x['other_terminal']))
 transitions=json.loads((OLD/'results/OUTCOME_TRANSITIONS.json').read_text())
 for seed in [0,2,3,4]:
  r=next(x for x in transitions['pairs'] if x['seed']==seed and x['A'].endswith('_ingress/attempt_001') and x['B'].endswith('_per_task/attempt_001'))
  assert sum(x['net_successes'] for x in paired if x['seed']==seed)==r['net_successes']
 a.output.mkdir(parents=True,exist_ok=True)
 result=dict(status='completed',date='2026-09-08',scope='8 September per-task files, 4 primary morning fleet draws; type aggregation only',script_sha256=sha(Path(__file__)),source_inventory_sha256=sha(OLD/'RAW_INPUTS.json'),previous_transitions_sha256=sha(OLD/'results/OUTCOME_TRANSITIONS.json'),admission_definition='outcome 1 or 2; independence from success established by previous 19-run audit, not re-established by this category aggregation',bindings=bindings,rows=rows,paired=paired,task_joins_rerun=0,inferential_tests=0)
 (a.output/'TASK_TYPES.json').write_text(json.dumps(result,indent=2)+'\n')
 for name,data in [('TASK_TYPES.csv',rows),('TASK_TYPE_CHANGES.csv',paired)]:
  with (a.output/name).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
if __name__=='__main__':main()
