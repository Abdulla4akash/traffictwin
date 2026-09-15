"""Scheduler-only boundary around unchanged frozen compiled helpers.

The seq_offsets function's AST is executed unmodified. Its service provider is
injected to return explicit candidate work; indices address candidate-specific
work/deadline arrays. This omits PRNG/service generation after compiler DCE,
without changing any prefix, admission, precision or reconciliation operation.
The same explicit service arrays enter causal policies. No actor/evaluator run.
"""
from pathlib import Path
import ast, hashlib, types
import jax
import jax.numpy as jnp
from round_robin import FROZEN, frozen, causal_round_robin
SOURCE=FROZEN/'eval/eval_sumo_stage1_mc.py'
EXPECTED='2824d9c2ef09e7748cd420d1ab2f0526d28157b8986605dc831397b6c618c07e'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED
NODE=next(n for n in ast.walk(ast.parse(SOURCE.read_text())) if isinstance(n,ast.FunctionDef) and n.name=='seq_offsets')

def batch_kernel(policy,capacity=6220):
 assert policy in ['ingress_dla','dla','per_task_dla','causal_round_robin']
 def batch(busy,load,pointer,attempts,radio,deadlines,work,ingress):
  N=attempts.shape[1];R=busy.shape[0]
  def sub(carry,inputs):
   rb,rl,ptr=carry;att,rad,dl,s,ing=inputs
   if policy in ['per_task_dla','causal_round_robin']:
    kw=dict(attempts=att,ingress_radio_viable=rad,deadlines_ms=dl,
     service_work_ms_by_rsu=jnp.broadcast_to(s[:,None],(N,R)),base_busy_ms=rb,base_load=rl,capacity=capacity,reconciliation_iterations=3)
    if policy=='per_task_dla':res=frozen.per_task_sequential_least_busy(**kw)
    else:res,ptr=causal_round_robin(**kw,pointer=ptr)
    target=res.selected_rsu;adm=res.admitted;offset=res.queue_offset_ms
    gf=res.gate_rejected;cf=res.cap_rejected
   else:
    target=ing if policy=='ingress_dla' else jnp.full((N,),jnp.argmin(rb),jnp.int32)
    ns=dict(jax=jax,jnp=jnp,CAP_REJECT=True,args=types.SimpleNamespace(substep_queue_iters=3),_R_IDX=jnp.arange(R),V=types.SimpleNamespace(compute_time_ms=lambda key,idx,tier:s[idx],RSU_TIER_IDX=0,TASK_DEADLINE_MS=dl,RSU_MAX_CONCURRENT=capacity))
    exec(compile(ast.Module(body=[NODE],type_ignores=[]),str(SOURCE),'exec'),ns)
    offset,adm,_,_,gf,_,_=ns['seq_offsets'](jax.random.split(jax.random.PRNGKey(0),N),jnp.ones(N,jnp.int32),jnp.arange(N),target,rad&(rl[target]<capacity),rb,rl,att,None,True)
    coarse=att&rad&(rl[target]<capacity);cf=coarse&~adm&~gf
   # Use evaluator scatter enqueue, not the helper's internal accumulated state.
   rb=rb+jnp.zeros(R,jnp.float32).at[target].add(jnp.where(adm,s,0.))
   rl=rl+jnp.zeros(R,jnp.int32).at[target].add(adm.astype(jnp.int32))
   return (rb,rl,ptr),(target,adm,offset,gf,cf)
  (rb,rl,ptr),out=jax.lax.scan(sub,(busy,load,pointer),(attempts,radio,deadlines,work,ingress))
  rdr=jnp.minimum(rb,1000.);new=rb-rdr
  frac=jnp.where(rb>0,rdr/jnp.maximum(rb,1e-6),0.)
  tdr=jnp.where(new<=0,rl,jnp.floor(rl.astype(jnp.float32)*frac).astype(jnp.int32))
  q=jnp.maximum(rl-tdr,0);q=jnp.where((new>0)&(q==0),1,q)
  return (new,q,ptr),out
 return jax.jit(batch)
