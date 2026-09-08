"""Sealed serial runner. Delivered switch is false: dry-run only.

No evaluator import. Execution requires a separately authorised reseal. Failed
attempts remain in place and cannot be silently retried or overwritten.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,time
import numpy as np
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parent;ROOT=PACKAGE.parents[2]
ARMS=['ingress_dla','dla','per_task_dla','causal_round_robin']
TRACE_SHA='896aa5ad646d0d6c643de49eaa84373c9442b2d58483ac0e39aab76619c29628'
ACTOR_SHA='93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def ah(a):
 a=np.ascontiguousarray(a);h=hashlib.sha256(str((a.shape,a.dtype.str)).encode());h.update(a.tobytes());return h.hexdigest()
def dump(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def source_files():
 frozen=ROOT/'docs/evaluation/vec_followup_2026-09-07/frozen_evaluator/eval'
 return sorted([p for folder in [PACKAGE/'experimental',HERE] for p in folder.rglob('*.py')]+[frozen/name for name in ['eval_sumo_stage1_mc.py','e2d_per_task_placement.py','rsu_state_delay.py']]+[HERE/'PROTOCOL.md',PACKAGE/'analysis/PROTOCOL.md',PACKAGE/'analysis/results/COMPARATOR_TESTS.json',PACKAGE/'analysis/results/COMPATIBILITY_TESTS.json'])
def seal():
 assert not (HERE/'SEALED.json').exists(),'Do not replace an existing seal'
 manifests=sorted((ROOT/'docs/evaluation').rglob('*manifest*.json'));used_f=set();used_e=set();bindings=[]
 def inspect(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in ['fleet_seed','fleet_seeds']:
     for n in v if isinstance(v,list) else [v]:
      if isinstance(n,int):used_f.add(n)
    if k in ['seed','evaluator_seed','task_seed','task_stream_seed'] and isinstance(v,int):used_e.add(v)
    inspect(v)
  elif isinstance(x,list):
   for v in x:inspect(v)
 for p in manifests:
  try:d=json.loads(p.read_text())
  except (ValueError,UnicodeDecodeError):continue
  inspect(d);bindings.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p)))
 fresh=lambda start,used:[n for n in range(start,start+10000) if n not in used][:8]
 fs=fresh(100,used_f);es=fresh(200,used_e)
 d=dict(schema='morning_joint_seed_rr_v1',date='2026-09-08',execute_new_confirmation=False,status='sealed_not_executed',arms=ARMS,blocks=[dict(block=i,fleet_seed=f,evaluator_seed=e,arm_order=ARMS[i%4:]+ARMS[:i%4]) for i,(f,e) in enumerate(zip(fs,es))],controls=dict(T=10800,N=215,R=9,K=5,capacity_tasks=6220,fleet='uk2030',service=1.,forwarding_ms=0.,entry_queue_reset=True,soc_reset=False),seed_inventory=dict(rule='first absent fleet integers >=100 and evaluator integers >=200, zipped ascending; source scope is surviving evaluation manifests',observed_fleet_seeds=sorted(used_f),observed_evaluator_seeds=sorted(used_e),manifests=bindings),inputs=dict(trace_sha256=TRACE_SHA,actor_sha256=ACTOR_SHA),sources={str(p.relative_to(ROOT)):sha(p) for p in source_files()},budget=dict(max_attempts=32,max_seconds_per_attempt=10800,min_initial_free_gib=50,min_cell_free_gib=20),execution_environment={"JAX_ENABLE_X64":"false","JAX_PLATFORMS":"cpu","PYTHONHASHSEED":"0","VEC_JAX_K_MAX":"5","VEC_JAX_K_MIN":"0","VEC_JAX_LAMBDA_ARRIVAL":"1.5","VEC_JAX_MODEL_C":"1","VEC_JAX_PRIORITY_ALPHA":"0","VEC_JAX_RSU_SERVICE_MULT":"1.0","VEC_JAX_STRESS_ARRIVAL":"1","VEC_JAX_STRESS_LANES":"0","VEC_JAX_STRESS_SPEED":"0"})
 dump(HERE/'SEALED.json',d);return d

def check_seal():
 d=json.loads((HERE/'SEALED.json').read_text())
 assert len(d['blocks'])==8 and d['arms']==ARMS
 for rel,expected in d['sources'].items():
  if not (ROOT/rel).is_file() or sha(ROOT/rel)!=expected:raise ValueError(f'Sealed source mismatch: {rel}')
 for b in d['seed_inventory']['manifests']:
  if sha(ROOT/b['path'])!=b['sha256']:raise ValueError('Seed inventory changed')
 return d

def configuration(d,block,arm,a):
 dest=a.output_root/f"block_{block['block']:02d}_{arm}"/'attempt_001'
 cmd=[str(a.python),'-u',str(PACKAGE/'experimental/evaluator_entry.py'),'--runtime-root',str(a.runtime_root),'--extension-audit','--trace',str(a.trace),'--actor',str(a.actor),'--max-steps','10800','--seed',str(block['evaluator_seed']),'--fleet','uk2030','--fleet-seed',str(block['fleet_seed']),'--rsu-cap-abs','6220','--lambda-arrival','1.5','--rsu-service-mult','1.0','--rsu-lb',arm,'--rsu-backhaul-ms','0','--k8s-scale','off','--substep-queue','sequential','--substep-queue-iters','3','--rsu-cap-mode','reject','--veh-queue','conserved','--out-json',str(dest/'summary.json'),'--per-step-out',str(dest/'per_step.npz'),'--per-task-out',str(dest/'per_task.npz')]
 return dict(block=block['block'],fleet_seed=block['fleet_seed'],evaluator_seed=block['evaluator_seed'],arm=arm,command=cmd,output=str(dest),seal_sha256=sha(HERE/'SEALED.json'),environment=d['execution_environment'])

def validate_cell(dest,config):
 """New-study checks only; never called on archived studies."""
 s=json.loads((dest/'summary.json').read_text());step=np.load(dest/'per_step.npz',allow_pickle=False);task=np.load(dest/'per_task.npz',allow_pickle=False)
 try:
  act=task['task_active'];oc=task['task_outcome'];met=task['task_met'];v2i=task['task_v2i_admitted'];lat=task['task_lat_ms'];typ=task['task_type'];actions=step['veh_action'][:,None,:]
  assert act.shape==(10800,5,215)
  assert s['T']==10800 and s['maxN']==215 and s['rsu_max_concurrent']==6220 and s['rsu_lb']==config['arm']
  assert s['fleet_seed']==config['fleet_seed'] and s['evaluator_seed']==config['evaluator_seed']
  assert s['enter_reset'] and not s['reset_soc_on_enter'] and s['rsu_service_mult']==1 and s['rsu_backhaul_ms']==0 and s['k8s_scale']=='off'
  assert np.array_equal(act,np.arange(5)[None,:,None]<step['veh_k'][:,None,:])
  admitted=(act&(actions==1)&v2i)|(act&(actions!=1)&~np.isin(oc,[5,6,8]))
  assert np.array_equal(admitted,act&np.isin(oc,[1,2]))
  assert np.array_equal(met,act&(oc==1)) and not np.any(met&~admitted)
  deadlines=np.array([100,500,100],np.float32)[typ]
  assert np.array_equal(met,act&(lat<=deadlines))
  assert np.all(lat[act&~admitted]==(10*deadlines)[act&~admitted])
  assert int(act.sum())==int(s['n_offered'])==int(step['arrivals'].sum())
  assert int(admitted.sum())==int(s['n_admitted']) and abs(s['completion']*act.sum()-met.sum())<1e-6
  assert int(met.sum())==int(step['done'].sum())
  cats=[int(np.count_nonzero(act&(oc==i))) for i in range(9)]
  for i,key in enumerate(['v2i_gate_rejected','v2i_cap_rejected','local_mqd_rejected','v2v_mqd_rejected','v2i_unavailable','v2v_unavailable'],3):assert cats[i]==int(s[key])
  assert sum(cats[1:])==int(act.sum())
  # Service conservation is checked per second and per RSU using recorded
  # admitted work, with declared float32 tolerance; count enqueue is exact.
  ex=task['task_execution_rsu'];work=task['task_rsu_service_ms'];assert np.array_equal(ex>=0,v2i)
  enqueued=np.zeros((10800,9),np.float64);counts=np.zeros((10800,9),np.int64)
  for r in range(9):
   mask=v2i&(ex==r);enqueued[:,r]=np.where(mask,work,0.).sum(axis=(1,2),dtype=np.float64);counts[:,r]=mask.sum(axis=(1,2))
  err=step['rsu_pre_drain_busy_ms'].astype(np.float64)-step['rsu_start_busy_ms']-enqueued
  assert np.allclose(err,0,atol=.01,rtol=0),float(np.max(np.abs(err)))
  assert np.array_equal(step['rsu_pre_drain_load']-step['rsu_start_load'],counts)
  assert np.allclose(step['rsu_busy_ms'],np.maximum(step['rsu_pre_drain_busy_ms']-1000,0),atol=1e-3,rtol=1e-6)
  expected_start=np.vstack([np.zeros((1,9),np.float32),step['rsu_busy_ms'][:-1]])
  assert np.array_equal(step['rsu_start_busy_ms'],expected_start)
  shared={f'step/{k}':ah(step[k]) for k in ['times','slot_tier','slot_is_ev','slot_soc_initial','slot_tx_power_w','exogenous_keys','observation_task_type','observation_task_size','veh_k']}
  shared.update({f'task/{k}':ah(task[k]) for k in ['task_active','task_type','task_sizes_mb','task_rsu_service_ms']})
  rec=dict(status='passed',seal_sha256=config['seal_sha256'],configuration=config,output_sha256={k:sha(dest/k) for k in ['summary.json','per_step.npz','per_task.npz']},shared_input_hashes=shared,offered=int(act.sum()),admitted=int(admitted.sum()),successes=int(met.sum()),max_service_conservation_error_ms=float(np.max(np.abs(err))),control_interpretation='frozen weights; observation/logit/action changes allowed and reported by block')
  return rec
 finally:step.close();task.close()

def validate_block(root,b):
 records={arm:json.loads((root/f"block_{b['block']:02d}_{arm}"/'attempt_001/VALIDATED.json').read_text()) for arm in ARMS}
 baseline=records['ingress_dla']['shared_input_hashes']
 assert all(x['shared_input_hashes']==baseline for x in records.values()),'Shared exogenous input mismatch'
 rows=[]
 basepath=root/f"block_{b['block']:02d}_ingress_dla"/'attempt_001/per_step.npz'
 with np.load(basepath,allow_pickle=False) as z:
  base={k:z[k] for k in ['veh_observations','veh_actor_logits','veh_action']}
 for arm in ARMS:
  with np.load(root/f"block_{b['block']:02d}_{arm}"/'attempt_001/per_step.npz',allow_pickle=False) as z:
   row=dict(arm=arm)
   for k in base:
    x=z[k];row[k+'_identical']=bool(np.array_equal(x,base[k]));row[k+'_max_abs']=float(np.max(np.abs(x.astype(np.float64)-base[k])))
    if k=='veh_action':row['changed_vehicle_seconds']=int(np.count_nonzero(x!=base[k]))
   rows.append(row)
 return dict(status='passed',block=b['block'],seal_sha256=sha(HERE/'SEALED.json'),cell_receipt_sha256={arm:sha(root/f"block_{b['block']:02d}_{arm}"/'attempt_001/VALIDATED.json') for arm in ARMS},shared_exogenous_inputs='identical',policy_controls=rows,actions_forced=False)

def require_complete(root,d):
 """Fail closed before analysis, including after final-block control failure."""
 if d!=check_seal():raise ValueError('Analysis seal mismatch')
 sh=sha(HERE/'SEALED.json')
 for b in d['blocks']:
  bp=root/f"BLOCK_{b['block']:02d}.json"
  if not bp.is_file():raise ValueError(f'Missing passed block controls: {bp}')
  block=json.loads(bp.read_text())
  if block.get('status')!='passed' or block.get('seal_sha256')!=sh or block.get('shared_exogenous_inputs')!='identical':raise ValueError('Invalid block receipt')
  shared=None
  for arm in ARMS:
   dest=root/f"block_{b['block']:02d}_{arm}"/'attempt_001';vp=dest/'VALIDATED.json'
   if not vp.is_file() or block.get('cell_receipt_sha256',{}).get(arm)!=sha(vp):raise ValueError('Cell receipt binding mismatch')
   rec=json.loads(vp.read_text());config=rec['configuration']
   if rec.get('status')!='passed' or rec['seal_sha256']!=sh:raise ValueError('Invalid cell status/seal')
   if any(config[k]!=v for k,v in dict(block=b['block'],arm=arm,fleet_seed=b['fleet_seed'],evaluator_seed=b['evaluator_seed'],seal_sha256=sh).items()):raise ValueError('Cell configuration mismatch')
   for name,h in rec['output_sha256'].items():
    if not (dest/name).is_file() or sha(dest/name)!=h:raise ValueError('Completed output changed')
   if shared is None:shared=rec['shared_input_hashes']
   elif rec['shared_input_hashes']!=shared:raise ValueError('Shared exogenous identities differ')
 return True

def main():
 p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');p.add_argument('--dry-run',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--python',type=Path);p.add_argument('--runtime-root',type=Path);p.add_argument('--trace',type=Path);p.add_argument('--actor',type=Path);p.add_argument('--output-root',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args()
 if a.seal:seal();return
 d=check_seal()
 if a.execute and not d['execute_new_confirmation']:raise SystemExit('EXECUTE_NEW_CONFIRMATION=false: no full evaluations authorised; no process launched')
 if a.execute==a.dry_run:raise SystemExit('Choose exactly --dry-run or --execute')
 for name in ['python','runtime_root','trace','actor','output_root']:
  if getattr(a,name) is None:raise SystemExit(f'Explicit --{name.replace("_","-")} required')
 for path,expected in [(a.trace,TRACE_SHA),(a.actor,ACTOR_SHA),(a.runtime_root/'eval/eval_sumo_stage1_mc.py','2824d9c2ef09e7748cd420d1ab2f0526d28157b8986605dc831397b6c618c07e')]:
  if not path.is_file() or sha(path)!=expected:raise SystemExit(f'Input/source mismatch: {path}')
 with np.load(a.trace,allow_pickle=False) as z:
  assert z['pos_x'].shape==(10800,215) and z['rsu_xy'].shape==(9,2) and 'enter' in z
 if not a.python.is_file():raise SystemExit('Runtime interpreter absent')
 # Only a version query, no actor/environment/evaluator import.
 runtime=json.loads(subprocess.check_output([str(a.python),'-c','import json,jax,jaxlib,numpy,sys;print(json.dumps(dict(python=sys.version.split()[0],jax=jax.__version__,jaxlib=jaxlib.__version__,numpy=numpy.__version__)))'],text=True))
 assert runtime==dict(python='3.11.15',jax='0.4.30',jaxlib='0.4.30',numpy='1.26.4'),runtime
 parent=a.output_root
 while not parent.exists():parent=parent.parent
 free=shutil.disk_usage(parent).free/(1<<30)
 configs=[configuration(d,b,arm,a) for b in d['blocks'] for arm in b['arm_order']];assert len(configs)==32 and len({x['output'] for x in configs})==32
 if a.dry_run:
  receipt=dict(status='dry_run_only',full_evaluations_launched=0,source_and_input_hash_checks='passed',runtime=runtime,available_gib=free,initial_storage_requirement_met=free>=50,seal_sha256=sha(HERE/'SEALED.json'),configurations=configs,qualification_boundary='configuration/source/kernel checks only; full instrumented evaluator and cross-arm checks unexecuted')
  if a.receipt:dump(a.receipt,receipt)
  print(json.dumps({k:v for k,v in receipt.items() if k!='configurations'},indent=2));return
 if free<50:raise SystemExit('Insufficient initial storage; no evaluation launched')
 a.output_root.mkdir(parents=True,exist_ok=True)
 env={k:v for k,v in os.environ.items() if not k.startswith(('VEC_JAX_','JAX_','XLA_'))};env.update(d['execution_environment'])
 for config in configs:
  dest=Path(config['output']);valid=dest/'VALIDATED.json'
  if dest.exists():
   if not valid.exists():raise SystemExit(f'Incomplete attempt retained; no automatic retry: {dest}')
   old=json.loads(valid.read_text());assert old['configuration']==config and old['seal_sha256']==sha(HERE/'SEALED.json')
   for name,h in old['output_sha256'].items():assert sha(dest/name)==h
  else:
   if len(list(a.output_root.glob('block_*/attempt_*')))>=32:raise SystemExit('32-attempt budget exhausted')
   if shutil.disk_usage(a.output_root).free/(1<<30)<20:raise SystemExit('Storage floor reached')
   check_seal();dest.mkdir(parents=True);dump(dest/'COMMAND.json',config)
   with (dest/'stdout.log').open('w') as out,(dest/'stderr.log').open('w') as err:
    start=time.time()
    try:
     r=subprocess.run(config['command'],env=env,stdout=out,stderr=err,timeout=10800,check=True)
     rec=validate_cell(dest,config);rec['wall_s']=time.time()-start;dump(valid,rec)
    except Exception as e:
     dump(dest/'FAILED.json',dict(error=repr(e),wall_s=time.time()-start,retained=True));raise
  b=d['blocks'][config['block']]
  if config['arm']==b['arm_order'][-1]:dump(a.output_root/f"BLOCK_{b['block']:02d}.json",validate_block(a.output_root,b))
 print('32 authorised evaluations complete; run predeclared analyse.py separately')
if __name__=='__main__':main()
