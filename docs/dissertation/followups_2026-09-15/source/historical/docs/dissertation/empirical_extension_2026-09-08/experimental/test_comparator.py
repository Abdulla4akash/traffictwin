"""Bounded hand/reference tests; no traffic evaluator or actor import."""
from pathlib import Path
import hashlib,json
import numpy as np
import jax
import jax.numpy as jnp
from round_robin import causal_round_robin,frozen
HERE=Path(__file__).resolve().parent

def reference(a,radio,d,s,w,q,C,p):
 w=w.copy();q=q.copy();base=w.copy();bq=q.copy();out=[]
 for i in range(len(a)):
  r=p;co=bool(a[i] and radio[i] and bq[r]<C);gate=w[r]<d[i];cap=q[r]<C;adm=co and gate and cap
  out.append([r,adm,co,co and not gate,co and gate and not cap,float(w[r]-base[r]),float(s[i,r]),float(w[r])])
  if adm:w[r]=np.float32(w[r]+s[i,r]);q[r]+=1
  if a[i] and radio[i]:p=(p+1)%len(w)
 return out,w,q,p

def main():
 records=[]
 # Six cases explicitly cover empty/nonempty, radio unavailable, gate/cap,
 # zero-work count capacity, all padding, and pointer carry. No case search.
 cases=[('empty',[0,0],[0,0],3,[1,1,1,1],[1]*4,[100]*4,[20,30,40,50],0),
 ('nonempty_gate',[100,40],[1,1],3,[1]*4,[1]*4,[100,100,500,100],[20]*4,0),
 ('radio_and_padding',[0,0],[0,0],3,[1,0,1,1],[0,1,1,1],[100]*4,[20]*4,1),
 ('capacity',[0,0],[2,1],2,[1]*4,[1]*4,[500]*4,[20]*4,0),
 ('zero_work',[0,0],[0,0],1,[1]*4,[1]*4,[100]*4,[0]*4,0),
 ('no_offered',[0,0],[0,0],3,[0]*4,[1]*4,[100]*4,[20]*4,1)]
 for name,w,q,C,a,radio,d,s,p in cases:
  ar=lambda x,dt:jnp.asarray(x,dt)
  kw=dict(attempts=ar(a,bool),ingress_radio_viable=ar(radio,bool),deadlines_ms=ar(d,jnp.float32),service_work_ms_by_rsu=ar(np.broadcast_to(np.array(s)[:,None],(len(s),len(w))),jnp.float32),base_busy_ms=ar(w,jnp.float32),base_load=ar(q,jnp.int32),capacity=C,pointer=ar(p,jnp.int32))
  f=jax.jit(lambda **k:causal_round_robin(**k,reconciliation_iterations=3))
  res,ptr=f(**kw);one,p1=causal_round_robin(**kw,reconciliation_iterations=1)
  ref,ew,eq,ep=reference(np.array(a),np.array(radio),np.array(d),np.array(kw['service_work_ms_by_rsu']),np.array(w,dtype=np.float32),np.array(q,dtype=np.int32),C,p)
  actual=list(zip(*[np.asarray(res[k]).tolist() for k in [0,1,2,3,4,5,6,9]]))
  np.testing.assert_allclose(actual,ref,rtol=1e-6,atol=1e-3)
  for x,y in zip(res,one):np.testing.assert_array_equal(x,y)
  assert int(ptr)==ep==int(p1)
  np.testing.assert_array_equal(res.effective_busy_ms,ew);np.testing.assert_array_equal(res.effective_load,eq)
  assert int(res.admitted.sum())==int(res.effective_load.sum())-sum(q)
  np.testing.assert_allclose(float(res.effective_busy_ms.sum())-sum(w),float(jnp.where(res.admitted,res.selected_service_work_ms,0.).sum()),atol=1e-3,rtol=1e-6)
  # Second substep/batch receives carried pointer, with no reset on drain.
  kw['pointer']=ptr;res2,p2=f(**kw);assert int(p2)==(ep+sum(bool(x and y) for x,y in zip(a,radio)))%len(w)
  records.append(dict(case=name,selected=np.asarray(res.selected_rsu).tolist(),admitted=np.asarray(res.admitted).tolist(),pointer_after=int(ptr),pointer_after_second=int(p2),status='passed'))
 # With one RSU, target selection has no freedom: every admission/output field
 # must equal the unchanged causal helper, including rejected offsets.
 kw.update(base_busy_ms=jnp.array([90.],jnp.float32),base_load=jnp.array([1],jnp.int32),service_work_ms_by_rsu=jnp.array([[20.],[30.],[0.],[10.]],jnp.float32),attempts=jnp.array([1,1,1,1],bool),ingress_radio_viable=jnp.array([1,0,1,1],bool),deadlines_ms=jnp.array([100.,500.,100.,500.],jnp.float32),capacity=3,pointer=jnp.int32(0))
 rr,_=causal_round_robin(**kw,reconciliation_iterations=3);kw.pop('pointer');old=frozen.per_task_sequential_least_busy(**kw,reconciliation_iterations=3)
 for x,y in zip(rr,old):np.testing.assert_array_equal(x,y)
 out=dict(status='passed',cases=records,one_rsu_original_helper_equality=True,tolerances=dict(atol_ms=.001,rtol=.000001,discrete='exact'),full_evaluations=0,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'round_robin.py']})
 dest=HERE.parent/'analysis/results/COMPARATOR_TESTS.json';dest.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
