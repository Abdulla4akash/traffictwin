"""Call bound unmodified helpers on explicit arrays; never import evaluator main."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,sys,types
import numpy as np
import jax,jax.numpy as jnp
HERE=Path(__file__).resolve().parent
src=HERE/'sources/production/eval_sumo_stage1_mc.py'
node=next(n for n in ast.walk(ast.parse(src.read_text())) if isinstance(n,ast.FunctionDef) and n.name=='seq_offsets')
namespace={'jax':jax,'jnp':jnp,'CAP_REJECT':True,'args':types.SimpleNamespace(substep_queue_iters=3)}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(src),'exec'),namespace)
helper=namespace['seq_offsets']
@jax.jit
def common(w,q,s,d,attempt,radio,target,capacity):
 n=s.shape[0];r=w.shape[0]
 # Substitution is at the service provider boundary only. The bound helper
 # body (including three replacements) is unchanged.
 namespace['V']=types.SimpleNamespace(compute_time_ms=lambda key,idx,tier:s[idx],RSU_TIER_IDX=0,TASK_DEADLINE_MS=d,RSU_MAX_CONCURRENT=capacity)
 namespace['_R_IDX']=jnp.arange(r)
 return helper(jax.random.split(jax.random.PRNGKey(0),n),jnp.ones(n,jnp.int32),jnp.arange(n),jnp.full((n,),target),radio & (q[target]<capacity),w,q,attempt,None,True)
cp=HERE/'sources/production/e2d_per_task_placement.py';spec=importlib.util.spec_from_file_location('tt_bound_placement',cp);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
@jax.jit
def causal(w,q,s,d,attempt,radio,capacity):
 return mod.per_task_sequential_least_busy(attempts=attempt,ingress_radio_viable=radio,deadlines_ms=d,service_work_ms_by_rsu=jnp.repeat(s[:,None],w.shape[0],axis=1),base_busy_ms=w,base_load=q,capacity=capacity,reconciliation_iterations=3)
def main(out):
 data=json.loads((out/'KERNEL_RESULTS.json').read_text());checked=0;fails=[]
 trials=data['results']+[data['minimisation']['result']]
 for result in trials:
  c=result['input'];s=jnp.array(c['s'],jnp.float32);d=jnp.array(c['d'],jnp.float32);a=jnp.array(c['a']);radio=jnp.array(c['radio'])
  for step in result['steps']:
   ra=step['A'];rr=common(jnp.array(ra['base_work'],jnp.float32),jnp.array(ra['base_load'],jnp.int32),s,d,a,radio,jnp.int32(ra['selected'][0]),jnp.int32(c['C']))
   rc=step['C'];cr=causal(jnp.array(rc['base_work'],jnp.float32),jnp.array(rc['base_load'],jnp.int32),s,d,a,radio,jnp.int32(c['C']))
   tests={'A_offset':(rr[0],ra['offsets']),'A_admission':(rr[1],ra['admitted']),'A_gate_count':(rr[2],sum(ra['gate'])),'A_cap_count':(rr[3],sum(ra['cap'])),'A_gate_mask':(rr[4],ra['gate']),'A_offered_work':(rr[5],sum(v for v,b in zip(c['s'],c['a']) if b)),'A_admitted_work':(rr[6],sum(v for v,b in zip(c['s'],ra['admitted']) if b))}
   for prod,key in [('selected_rsu','selected'),('admitted','admitted'),('coarse_candidate','coarse'),('gate_rejected','gate'),('cap_rejected','cap'),('queue_offset_ms','offsets'),('effective_busy_ms','work'),('effective_load','load')]:tests['C_'+key]=(getattr(cr,prod),rc[key])
   for name,(x,y) in tests.items():
    if not np.array_equal(np.asarray(x),np.asarray(y)):fails.append(dict(id=c['id'],check=name,production=np.asarray(x).tolist(),reference=y))
   checked+=1
 report=dict(status='passed' if not fails else 'disagreements',python=sys.version.split()[0],jax=jax.__version__,numpy=np.__version__,primary_cases=440,minimised_cases=1,substeps_compared=checked,source_sha256={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [src,cp]},failures=fails,scope='Exact returned masks/targets/offsets/counts/work agreement for A and C. A uses an explicit-array service/deadline provider; no physical model/RNG/actor/full evaluator validation. Intermediate A masks are reference diagnostics; original helper returns final fields only.')
 (out/'PRODUCTION_AGREEMENT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert not fails
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);main(p.parse_args().output)
