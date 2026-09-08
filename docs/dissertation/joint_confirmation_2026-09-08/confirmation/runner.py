"""Versioned execution of the prepared study; serial, sealed and fail closed.

Configuration/order/inference are inherited from the disabled prepared runner.
Adds bounded qualification, attempt locking and independently timed validation.
"""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,os,platform,shutil,subprocess,sys,time
import numpy as np
from validation import ARMS,FILES,sha,ah,need,validate_cell,validate_block
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parent;ROOT=PACKAGE.parents[2]
PREPARED=PACKAGE.parent/'empirical_extension_2026-09-08'
SEAL=HERE/'SEALED_EXECUTION.json'
TRACE_SHA='896aa5ad646d0d6c643de49eaa84373c9442b2d58483ac0e39aab76619c29628'
ACTOR_SHA='93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,d):Path(p).write_text(json.dumps(d,indent=2)+'\n')
def load(p):return json.loads(Path(p).read_text())
def write_once(p,d):
 with Path(p).open('x') as f:json.dump(d,f,indent=2);f.write('\n')
def environment(d):
 # Record numerical settings; never include credentials in an evidence manifest.
 env={k:v for k,v in os.environ.items() if not k.startswith(('VEC_JAX_','JAX_','XLA_')) and k not in ('PYTHONPATH','PYTHONHOME','PYTHONOPTIMIZE','JAX_COMPILATION_CACHE_DIR')}
 env.update(d['execution_environment']);return env

def source_bindings():
 paths=[p for folder in [HERE,PACKAGE/'experimental'] for p in folder.rglob('*.py')]
 paths += [HERE/'EXECUTION_AMENDMENT.md',PREPARED/'confirmation/PROTOCOL.md',PREPARED/'confirmation/SEALED.json',PREPARED/'experimental/evaluator_v1.py']
 old=load(PREPARED/'confirmation/SEALED.json')
 paths += [ROOT/p for p in old['sources']]
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}
def check_sources(d):
 for rel,h in d['sources'].items():need((ROOT/rel).is_file() and sha(ROOT/rel)==h,f'Sealed source mismatch: {rel}')
def check_seal():
 d=load(SEAL);check_sources(d)
 need(d['execute_new_confirmation'] is True and d['qualification']['status']=='passed','Execution not qualified/authorised')
 need(sha(ROOT/d['qualification']['path'])==d['qualification']['sha256'],'Qualification receipt changed')
 old=load(PREPARED/'confirmation/SEALED.json');need(d['blocks']==old['blocks'] and d['arms']==old['arms'],'Sealed design drift')
 return d

def preflight(a,d):
 for p,h in [(a.trace,TRACE_SHA),(a.actor,ACTOR_SHA),(a.runtime_root/'eval/eval_sumo_stage1_mc.py','2824d9c2ef09e7748cd420d1ab2f0526d28157b8986605dc831397b6c618c07e')]:need(p.is_file() and sha(p)==h,f'Input/source mismatch: {p}')
 bindings=load(PREPARED/'experimental/vendor/SOURCE_BINDINGS.json')['sources']
 for b in bindings:need(sha(a.runtime_root/b['runtime_relative_path'])==b['sha256'],'Frozen runtime dependency mismatch')
 frozen=ROOT/'docs/evaluation/vec_followup_2026-09-07/frozen_evaluator/eval'
 for name in ['e2d_per_task_placement.py','rsu_state_delay.py']:need(sha(a.runtime_root/'eval'/name)==sha(frozen/name),f'Frozen helper runtime mismatch: {name}')
 with np.load(a.trace,allow_pickle=False) as z:need(z['pos_x'].shape==(10800,215) and z['rsu_xy'].shape==(9,2) and z['enter'].shape==(10800,215),'Canonical trace dimensions')
 code='import sys,json,platform,os,jax,jaxlib,numpy,subprocess;print(json.dumps(dict(python=sys.version.split()[0],jax=jax.__version__,jaxlib=jaxlib.__version__,numpy=numpy.__version__,x64=jax.config.jax_enable_x64,devices=[str(x) for x in jax.devices()],platform=platform.platform(),processor=subprocess.check_output(["sysctl","-n","machdep.cpu.brand_string"],text=True).strip(),cpu_count=os.cpu_count())))'
 env=environment(d);actual=json.loads(subprocess.check_output([str(a.python),'-c',code],env=env,text=True))
 for k,v in dict(python='3.11.15',jax='0.4.30',jaxlib='0.4.30',numpy='1.26.4',x64=False).items():need(actual[k]==v,f'Runtime mismatch: {k}')
 need(actual['devices']==['TFRT_CPU_0'],'CPU device required')
 numeric={k:env.get(k) for k in sorted(set(d['execution_environment'])|{'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','XLA_FLAGS','JAX_COMPILATION_CACHE_DIR','PYTHONPATH','PYTHONHOME','PYTHONOPTIMIZE'})}
 return dict(timestamp=now(),runtime=actual,python=str(a.python),python_binary_sha256=sha(a.python),runtime_root=str(a.runtime_root),trace=str(a.trace),actor=str(a.actor),trace_sha256=TRACE_SHA,actor_sha256=ACTOR_SHA,execution_environment=numeric,free_gib=shutil.disk_usage(a.output_root.parent).free/(1<<30))

def configuration(d,b,arm,a,seal_path=SEAL,steps=10800,frozen=False,dest=None):
 dest=dest or a.output_root/f"block_{b['block']:02d}_{arm}"/'attempt_001'
 cmd=[str(a.python),'-u',str(PACKAGE/'experimental/evaluator_entry.py'),'--runtime-root',str(a.runtime_root)]
 if not frozen:cmd+=['--extension-audit']
 cmd+=['--trace',str(a.trace),'--actor',str(a.actor),'--max-steps',str(steps),'--seed',str(b['evaluator_seed']),'--fleet','uk2030','--fleet-seed',str(b['fleet_seed']),'--rsu-cap-abs','6220','--lambda-arrival','1.5','--rsu-service-mult','1.0','--rsu-lb',arm,'--rsu-backhaul-ms','0','--k8s-scale','off','--substep-queue','sequential','--substep-queue-iters','3','--rsu-cap-mode','reject','--veh-queue','conserved','--out-json',str(dest/'summary.json'),'--per-step-out',str(dest/'per_step.npz'),'--per-task-out',str(dest/'per_task.npz')]
 return dict(block=b['block'],fleet_seed=b['fleet_seed'],evaluator_seed=b['evaluator_seed'],arm=arm,steps=steps,frozen_reference=frozen,command=cmd,output=str(dest),seal_path=str(seal_path),seal_sha256=sha(seal_path),environment=d['execution_environment'],inputs=dict(trace=str(a.trace),actor=str(a.actor),trace_sha256=TRACE_SHA,actor_sha256=ACTOR_SHA))

def run_attempt(config,d,validate=True):
 dest=Path(config['output']);need(not dest.exists(),f'Existing attempt retained: {dest}')
 need(shutil.disk_usage(dest.parent if dest.parent.exists() else dest.parent.parent).free/(1<<30)>=20,'Storage floor reached')
 check_sources(d)
 for k,h in [('trace',TRACE_SHA),('actor',ACTOR_SHA)]:need(sha(config['inputs'][k])==h,f'Input changed: {k}')
 dest.mkdir(parents=True);write_once(dest/'COMMAND.json',config)
 start=time.monotonic();start_at=now();write_once(dest/'STARTED.json',dict(started_at=start_at,pid=os.getpid(),seal_sha256=config['seal_sha256']))
 simulation_s=0.;validation_s=0.;phase='simulation'
 try:
  try:
   with (dest/'stdout.log').open('x') as out,(dest/'stderr.log').open('x') as err:
    subprocess.run(config['command'],env=environment(d),stdout=out,stderr=err,check=True,timeout=10800)
  finally:simulation_s=time.monotonic()-start;simulation_end=now()
  phase='validation';vstart=time.monotonic()
  try:rec=validate_cell(dest,config) if validate else dict(status='reference_completed',output_sha256={k:sha(dest/k) for k in FILES})
  finally:validation_s=time.monotonic()-vstart
  rec.update(started_at=start_at,simulation_finished_at=simulation_end,finished_at=now(),simulation_process_s=simulation_s,validation_s=validation_s,total_wall_s=time.monotonic()-start)
  write_once(dest/('VALIDATED.json' if validate else 'REFERENCE.json'),rec)
  return rec
 except BaseException as exc:
  write_once(dest/'FAILED.json',dict(error=repr(exc),failed_phase=phase,started_at=start_at,finished_at=now(),simulation_process_s=simulation_s,validation_s=validation_s,elapsed_s=time.monotonic()-start,retained=True,partial_output_sha256={k:sha(dest/k) for k in FILES if (dest/k).is_file()}))
  raise

def verify_completed(dest,config):
 p=dest/'VALIDATED.json';need(p.is_file(),f'Incomplete attempt retained: {dest}')
 rec=load(p);need(rec['status']=='passed' and rec['configuration']==config and rec['seal_sha256']==config['seal_sha256'],'Completed configuration/seal mismatch')
 need(set(rec['output_sha256'])==set(FILES),'Missing output bindings')
 for name,h in rec['output_sha256'].items():need((dest/name).is_file() and sha(dest/name)==h,'Completed output changed')
 return rec

def require_complete(root,d):
 need(d==check_seal(),'Analysis seal mismatch');sh=sha(SEAL)
 for b in d['blocks']:
  bp=root/f"BLOCK_{b['block']:02d}.json";need(bp.is_file(),f'Missing passed block controls: {bp}');block=load(bp)
  need(block.get('status')=='passed' and block.get('seal_sha256')==sh and block.get('shared_exogenous_inputs')=='identical','Invalid block receipt')
  shared=None
  for arm in ARMS:
   dest=root/f"block_{b['block']:02d}_{arm}"/'attempt_001';vp=dest/'VALIDATED.json'
   need(vp.is_file() and block.get('cell_receipt_sha256',{}).get(arm)==sha(vp),'Cell receipt binding mismatch')
   rec=load(vp);config=rec['configuration'];verify_completed(dest,config)
   need(all(config[k]==v for k,v in dict(block=b['block'],arm=arm,fleet_seed=b['fleet_seed'],evaluator_seed=b['evaluator_seed'],seal_sha256=sh,steps=10800).items()),'Cell configuration mismatch')
   if shared is None:shared=rec['shared_input_hashes']
   else:need(shared==rec['shared_input_hashes'],'Shared exogenous identities differ')
 return True

def args():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--python',type=Path,required=True);p.add_argument('--runtime-root',type=Path,required=True);p.add_argument('--trace',type=Path,required=True);p.add_argument('--actor',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);return p.parse_args()
def require_output_root(a,d):
 need(a.output_root.resolve()==Path(d['output_root']).resolve(),'Output root differs from the single sealed study root')
def main():
 a=args();need(a.execute,'Explicit --execute required');d=check_seal();require_output_root(a,d);a.output_root.mkdir(parents=True,exist_ok=True)
 with Path(d['study_lock']).open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  pre=preflight(a,d);need(pre['runtime']==d['runtime']['runtime'] and pre['execution_environment']==d['runtime']['execution_environment'] and pre['python_binary_sha256']==d['runtime']['python_binary_sha256'],'Qualified runtime changed')
  existing=list(a.output_root.glob('block_*/attempt_*'))
  if not existing:need(pre['free_gib']>=50,'Insufficient initial storage')
  else:need(pre['free_gib']>=20,'Insufficient resume storage')
  write_once(a.output_root/f'PREFLIGHT_{time.time_ns()}.json',pre)
  for b in d['blocks']:
   for arm in b['arm_order']:
    c=configuration(d,b,arm,a);dest=Path(c['output'])
    if dest.exists():rec=verify_completed(dest,c);print(f"RESUME verified block={b['block']} arm={arm}",flush=True)
    else:
     need(len(list(a.output_root.glob('block_*/attempt_*')))<32,'Attempt budget exhausted')
     print(f"START block={b['block']} arm={arm} at {now()}",flush=True)
     rec=run_attempt(c,d);print(f"VALIDATED block={b['block']} arm={arm} simulation_s={rec['simulation_process_s']:.2f} validation_s={rec['validation_s']:.2f}",flush=True)
   bp=a.output_root/f"BLOCK_{b['block']:02d}.json";vstart=time.monotonic();block=validate_block(a.output_root,b,sha(SEAL));block['validation_s']=time.monotonic()-vstart;block['validated_at']=now()
   if bp.exists():
    previous=load(bp);need(previous['cell_receipt_sha256']==block['cell_receipt_sha256'] and previous['policy_controls']==block['policy_controls'],'Changed completed block receipt')
   else:write_once(bp,block)
   print(f"BLOCK PASSED {b['block']} controls_s={block['validation_s']:.2f}",flush=True)
   if b['block']==0:
    cells=[load(a.output_root/f'block_00_{arm}'/'attempt_001/VALIDATED.json') for arm in ARMS]
    estimate=dict(after_block=0,simulation_s=sum(x['simulation_process_s'] for x in cells),cell_validation_s=sum(x['validation_s'] for x in cells),block_validation_s=block['validation_s'],remaining_blocks=7,remaining_seconds_estimate=7*(sum(x['total_wall_s'] for x in cells)+block['validation_s']),uses_outcome_values=False)
    if not (a.output_root/'RUNTIME_ESTIMATE.json').exists():write_once(a.output_root/'RUNTIME_ESTIMATE.json',estimate)
    print('RUNTIME ESTIMATE '+json.dumps(estimate),flush=True)
  require_complete(a.output_root,d);write_once(a.output_root/'COMPLETE.json',dict(status='complete',finished_at=now(),seal_sha256=sha(SEAL),full_attempts=32,valid_blocks=8))
if __name__=='__main__':main()
