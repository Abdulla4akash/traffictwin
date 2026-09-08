"""Authenticated read-only September audit. Never runs a simulator."""
from pathlib import Path
import argparse, gc, hashlib, json
import numpy as np
HERE=Path(__file__).resolve().parent

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def ah(a):
 a=np.ascontiguousarray(a);h=hashlib.sha256(str((a.shape,a.dtype.str)).encode());h.update(memoryview(a).cast('B'));return h.hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def inventory(root,out):
 entries=json.loads((HERE/'RAW_INPUTS.json').read_text())['raw_files']; rows=[]
 for f in entries:
  path=root/f['path'];r=dict(path=f['path'],expected_sha256=f['sha256'],expected_bytes=f['bytes'])
  if not path.is_file():r['status']='missing'
  else:
   r.update(actual_bytes=path.stat().st_size,actual_sha256=sha(path));r['status']='verified' if r['actual_bytes']==f['bytes'] and r['actual_sha256']==f['sha256'] else 'mismatch'
  rows.append(r)
 report=dict(date='2026-09-08',raw_root_supplied=str(root),files=rows,verified=sum(x['status']=='verified' for x in rows),bytes_verified=sum(x.get('actual_bytes',0) for x in rows if x['status']=='verified'),status='verified' if all(x['status']=='verified' for x in rows) else 'incomplete_or_mismatch')
 dump(out/'INVENTORY_CHECK.json',report)
 if report['status']!='verified':raise SystemExit('Raw inventory missing/mismatched: see INVENTORY_CHECK.json (no task analysis performed).')
 return {x['path']:x for x in rows}
def audit(run,root,cache):
 s=json.loads((HERE/run['summary']).read_text());tp=root/run['files']['per_task.npz'];sp=root/run['files']['per_step.npz']
 identities={};checks={}
 with np.load(sp,allow_pickle=False) as z:
  action=z['veh_action'][:,None,:];ks=z['veh_k'];times=z['times'];done=z['done'];arr=z['arrivals'];stepactive=z['active']
  for k in ['times','slot_tier','slot_is_ev','veh_action','veh_k','veh_best_rsu']:
   identities['step_'+k]=ah(z[k])
  # Logits can differ with later SoC; actions are the recorded control check.
  identities['step_veh_actor_logits']=ah(z['veh_actor_logits'])
 with np.load(tp,allow_pickle=False) as z:
  active=z['task_active'];met=z['task_met'];oc=z['task_outcome'];v2i=z['task_v2i_admitted'];lat=z['task_lat_ms'];typ=z['task_type'];ex=z['task_execution_rsu']
  v2iattempt=active & (action==1)
  admitted=(v2iattempt & v2i) | (active & (action!=1) & ~np.isin(oc,[5,6,8]))
  terminal=active & ~admitted
  cats=[int(np.count_nonzero(active&(oc==i))) for i in range(9)]
  offered=int(active.sum());admn=int(admitted.sum());success=int((active&met).sum());declared_failed=int(np.count_nonzero(active&(oc>=3)))
  dl=np.array([100.,500.,100.],dtype=np.float32)[typ]
  latency_dis=int(np.count_nonzero(terminal & np.isfinite(lat) & (lat!=10*dl)))
  false=int(np.count_nonzero(terminal&met))
  checks['offered_partition']=offered==admn+int(terminal.sum())
  checks['declared_partition']=offered==cats[1]+cats[2]+sum(cats[3:])
  checks['actual_admission_matches_declared']=int(np.count_nonzero(active & (admitted != ((oc==1)|(oc==2)))))==0
  checks['execution_matches_v2i_enqueue']=bool(np.array_equal(ex>=0,v2i))
  checks['inactive_records']=bool(np.all(oc[~active]==0) and not met[~active].any() and not v2i[~active].any())
  checks['offer_mask_matches_arrivals']=bool(np.array_equal(active, np.arange(active.shape[1])[None,:,None]<ks[:,None,:]))
  checks['deadline_flag_matches_outcome_1']=bool(np.array_equal(met,oc==1))
  checks['deadline_flag_matches_latency']=bool(np.array_equal(met,active & (lat<=dl)))
  checks['summary_offered']=offered==int(s['n_offered'])
  checks['summary_admitted']=admn==int(s['n_admitted'])
  checks['summary_successes']=abs(s['completion']*offered-success)<1e-6
  checks['per_step_done']=bool(np.array_equal(met.sum(axis=(1,2)),done))
  # Reconcile terminal categories with exactly their archived counters.
  names=['v2i_gate_rejected','v2i_cap_rejected','local_mqd_rejected','v2v_mqd_rejected','v2i_unavailable','v2v_unavailable']
  checks['summary_categories']=all(cats[i]==int(s[k]) for i,k in enumerate(names,3))
  for k in ['task_active','task_type','task_ingress_rsu']:identities[k]=ah(z[k])
  key=hashlib.sha256(run['id'].encode()).hexdigest()[:16]
  np.savez(cache/(key+'.npz'),shape=np.array(active.shape),active=np.packbits(active),met=np.packbits(active&met),admitted=np.packbits(admitted),gate=np.packbits(active&(oc==3)),cap=np.packbits(active&(oc==4)),other_terminal=np.packbits(active&(oc>=5)))
  result=dict(id=run['id'],group=run['group'],mode=s['rsu_lb'],fleet_seed=s['fleet_seed'],trace=s['trace'],shape=list(active.shape),offered=offered,admitted=admn,terminal_failures=int(terminal.sum()),explicit_rejections=sum(cats[3:7]),unavailability=sum(cats[7:]),successes=success,outcome_counts=cats,false_success_discrepancies=false,rejected_finite_nonpenalty_latency=latency_dis,rejected_nonfinite_latency=int(np.count_nonzero(terminal&~np.isfinite(lat))),rejected_penalty_equal_latency=int(np.count_nonzero(terminal&(lat==10*dl))),admission_category_discrepancies=int(np.count_nonzero(active & (admitted != ((oc==1)|(oc==2))))),fixed_history=dict(archived_score=success/offered,admission_consistent_score=(success-false)/offered,difference_pp=-100*false/offered,scope='fixed recorded history only'),checks=checks,identities=identities,cache_key=key)
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--raw-root',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--cache',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);a.cache.mkdir(parents=True,exist_ok=True)
 verified=inventory(a.raw_root,a.output);print('Inventory verified:',len(verified),flush=True)
 results=[]
 for run in json.loads((HERE/'RUNS.json').read_text()):
  r=audit(run,a.raw_root,a.cache);results.append(r);dump(a.output/'RAW_AUDIT.json',dict(date='2026-09-08',scope='19 September full runs; no historical E0/E1/E2 raw validation',runs=results));gc.collect()
  print(run['id'],r['offered'],r['false_success_discrepancies'],r['rejected_finite_nonpenalty_latency'],[k for k,v in r['checks'].items() if not v],flush=True)
 if any(not all(r['checks'].values()) for r in results):raise SystemExit('One or more audit disagreements; retained in RAW_AUDIT.json')
if __name__=='__main__':main()
