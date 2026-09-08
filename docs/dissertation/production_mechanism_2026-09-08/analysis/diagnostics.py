"""Bounded explicit-input diagnostics. No actor or full evaluator import."""
from pathlib import Path
from fractions import Fraction as F
import argparse, ast, hashlib, importlib.util, itertools, json, os, sys, types
os.environ['JAX_PLATFORMS']='cpu'
os.environ['JAX_ENABLE_X64']='false'
import numpy as np
import jax
import jax.numpy as jnp

HERE=Path(__file__).resolve().parent
OLD=HERE.parents[1]/'gap_closure_2026-09-08'/ 'verification'
PROD=OLD/'sources/production/eval_sumo_stage1_mc.py'
def imported(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
old=imported('prior_reference',OLD/'scheduling_reference.py')
cp=imported('frozen_causal',OLD/'sources/production/e2d_per_task_placement.py')
node=next(n for n in ast.walk(ast.parse(PROD.read_text())) if isinstance(n,ast.FunctionDef) and n.name=='seq_offsets')
ns={'jax':jax,'jnp':jnp,'CAP_REJECT':True,'args':types.SimpleNamespace(substep_queue_iters=3)}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(PROD),'exec'),ns)

@jax.jit
def production(w,q,s,d,e,target,capacity):
 n=s.shape[0];R=w.shape[0]
 ns['V']=types.SimpleNamespace(compute_time_ms=lambda key,idx,tier:s[idx],RSU_TIER_IDX=0,TASK_DEADLINE_MS=d,RSU_MAX_CONCURRENT=capacity)
 ns['_R_IDX']=jnp.arange(R)
 ret=ns['seq_offsets'](jax.random.split(jax.random.PRNGKey(0),n),jnp.ones(n,jnp.int32),jnp.arange(n),target,e,w,q,jnp.ones(n,bool),None,True)
 # Diagnostic mirror: original helper returns only final fields, not masks.
 onehot=target[:,None]==jnp.arange(R)[None,:]
 def values(m):
  a=jnp.where(m,s,0.)[:,None]*onehot;h=m.astype(jnp.float32)[:,None]*onehot
  o=jnp.sum((jnp.cumsum(a,axis=0)-a)*onehot,axis=1)
  rank=jnp.sum((jnp.cumsum(h,axis=0)-h)*onehot,axis=1)
  return o,rank
 masks=[e]
 for _ in range(4):
  o,h=values(masks[-1]);masks.append(e & (w[target]+o<d) & (h<(capacity-q)[target]))
 return ret,jnp.stack(masks),values(masks[3])

@jax.jit
def production_scan(w,q,s,d,e,capacity):
 return cp.per_task_sequential_least_busy(attempts=jnp.ones_like(e),ingress_radio_viable=e,deadlines_ms=d,service_work_ms_by_rsu=s[:,None],base_busy_ms=w,base_load=q,capacity=capacity,reconciliation_iterations=3)

def rat(x):return F(float(x))
def exact(c):
 n=len(c['s']);s=list(map(rat,c['s']));w=list(map(rat,c['w']));d=list(map(rat,c['d']));q=c['q'];C=c['C'];t=c['target'];E=c['e']
 def values(m):
  work=[F(0)]*len(w);count=[0]*len(w);o=[];h=[]
  for i,r in enumerate(t):
   o.append(work[r]);h.append(count[r])
   if m[i]:work[r]+=s[i];count[r]+=1
  return o,h
 def replace(m):
  o,h=values(m);return [E[i] and w[r]+o[i]<d[i] and q[r]+h[i]<C for i,r in enumerate(t)]
 b=[False]*n
 for i in range(n):b[i]=replace(b)[i]
 count=max((sum(E[i] and t[i]==r for i in range(n)) for r in range(len(w))),default=0)
 bound=max((min(sum(E[i] and t[i]==r for i in range(n)),2*len({d[i] for i in range(n) if E[i] and t[i]==r})-1) for r in range(len(w)) if any(E[i] and t[i]==r for i in range(n))),default=0)
 masks=[E]
 for _ in range(max(count,4)):masks.append(replace(masks[-1]))
 assert masks[bound]==b,(c['id'],'bound',bound)
 first=next(k for k,m in enumerate(masks) if m==b)
 o,h=values(b)
 return dict(mask=b,masks=masks[:5],fixed_by=first,bound=bound,offsets=list(map(float,o)),ranks=h,gate=[E[i] and w[r]+o[i]>=d[i] for i,r in enumerate(t)],met=[b[i] and w[r]+o[i]+s[i]<=d[i] for i,r in enumerate(t)],gate_margin=[float(d[i]-w[r]-o[i]) for i,r in enumerate(t)])

def fixture(name,s,d,W=0,Q=0,C=6220,pattern=0,e=None,types_=None):
 R=[1,2,3][pattern];target=[0]*len(s) if pattern==0 else [i%2 for i in range(len(s))] if pattern==1 else [1]*len(s)
 E=e if e is not None else [True]*len(s)
 return dict(id=name,s=[float(np.float32(v)) for v in s],d=list(map(float,d)),w=[float(np.float32(W))]*R,q=[Q]*R,C=C,target=target,e=[v and Q<C for v in E],task_types=types_)

BASE=[F(1254)*F(10,1)/(F(22)*F(3,2)*4*F(9,10)*5),F(2100)*10/(22*F(3,2)*4*F(9,10)*5),F(15)*10/(22*F(3,2)*2*F(9,10))]
DEAD=[100,500,100]
def service(types_,xi):return [float(np.float32(float(BASE[t])*xi)) for t in types_]
def cases():
 out=[]
 ds=[[100]*8,[500]*8,[100,500]*4,[500,100]*4,[100]*4+[500]*4,[500]*4+[100]*4,[1,1,41,41,81,81,81,81],[500,500,100,100,20,20,20,20]]
 ss=[[0]*8,[40]*8,[0,20]*4,list(range(1,9))]
 for k,(di,si,wi) in enumerate(itertools.product(range(8),range(4),range(4))):
  C,Q=[(4,0),(2,1),(4,0),(4,4)][k%4]
  out.append(fixture(f'math_{k:03}',ss[si],ds[di],[0,20,100,500][wi],Q,C,k%2,e=[i%5!=4 for i in range(8)]))
 orders=[[0]*24,[1]*24,[2]*24,[0,1,2]*8,[0,1]*12,[2,1,0]*8]
 for k,(ti,xi,wi,pat,ei) in enumerate(itertools.product(range(6),[.91,1.,1.09],range(3),range(3),range(2))):
  ts=orders[ti];out.append(fixture(f'coupled_{k:03}',service(ts,xi),[DEAD[t] for t in ts],[0,90,490][wi],[0,4,20][wi],6220,pat,e=[ei==0 or i%4!=3 for i in range(24)],types_=ts))
 configurations=list(itertools.product([2,3,8],range(3),[.91,1.,1.09]))+[(24,0,xi) for xi in [.91,1.,1.09]]
 for k,(n,pat,xi) in enumerate(configurations):
  ts=([2]*(n-1)+[0] if pat==0 else [2]*(n-1)+[1] if pat==1 else [0]*(n-1)+[1]);s=service(ts,xi)
  central=np.float32(float(F(DEAD[ts[-1]])-sum(map(rat,s[:-1]))));assert central>=0
  for ulp in range(-3,4):
   W=central
   for _ in range(abs(ulp)):W=np.nextafter(W,np.float32(-np.inf if ulp<0 else np.inf))
   out.append(fixture(f'near_{k:03}_{ulp:+d}',s,[DEAD[t] for t in ts],W,1,types_=ts))
 for t,ulp in itertools.product(range(3),range(-1,2)):
  s=service([t],1.);W=np.float32(DEAD[t]-s[0])
  if ulp:W=np.nextafter(W,np.float32(-np.inf if ulp<0 else np.inf))
  out.append(fixture(f'completion_{t}_{ulp:+d}',s,[DEAD[t]],W,1,types_=[t]))
 assert len(out)==671
 return out

def checked(c):
 ref=exact(c);a=lambda k,dtype:jnp.array(c[k],dtype)
 ret,trace,ov=production(a('w',jnp.float32),a('q',jnp.int32),a('s',jnp.float32),a('d',jnp.float32),a('e',bool),a('target',jnp.int32),jnp.int32(c['C']))
 off,mask,ng,nc,gf,wo,wa=[np.asarray(x).tolist() for x in ret];trace=np.asarray(trace).tolist()
 assert mask==trace[3] and np.array_equal(np.asarray(off),np.asarray(ov[0])),c['id']
 assert gf==[e and not bool(np.float32(c['w'][r])+np.float32(off[i])<c['d'][i]) for i,(e,r) in enumerate(zip(c['e'],c['target']))]
 assert ng==sum(gf) and nc==sum(e and not m and not g for e,m,g in zip(c['e'],mask,gf))
 pscan=[False]*len(c['s']);ps_offsets=[0.]*len(pscan);oldmask=[False]*len(pscan);oldoffset=[0.]*len(pscan)
 for r in range(len(c['w'])):
  ids=[i for i,t in enumerate(c['target']) if t==r]
  if not ids:continue
  batch=dict(s=[c['s'][i] for i in ids],d=[c['d'][i] for i in ids],a=[True]*len(ids),radio=[c['e'][i] for i in ids],C=c['C'])
  prior=old.common(batch,[c['w'][r]],[c['q'][r]],0)
  cr=production_scan(jnp.array([c['w'][r]],jnp.float32),jnp.array([c['q'][r]],jnp.int32),jnp.array(batch['s'],jnp.float32),jnp.array(batch['d'],jnp.float32),jnp.array(batch['radio']),jnp.int32(c['C']))
  for j,i in enumerate(ids):pscan[i]=bool(cr.admitted[j]);ps_offsets[i]=float(cr.queue_offset_ms[j]);oldmask[i]=prior['admitted'][j];oldoffset[i]=prior['offsets'][j]
 fd=[i for i,(x,y) in enumerate(zip(mask,ref['mask'])) if x!=y]
 cd=[i for i,(x,y) in enumerate(zip(mask,pscan)) if x!=y]
 maxerr=max(abs(x-y) for x,y in zip(off,ref['offsets']))
 return dict(input=c,exact=ref,production_mask=mask,production_offsets=off,production_gate=gf,production_gate_count=ng,production_capacity_count=nc,production_trace_mirror=trace,production_fourth_changes=trace[4]!=trace[3],causal_float32_mask=pscan,causal_float32_offsets=ps_offsets,prior_scalar_mask=oldmask,prior_scalar_offsets=oldoffset,production_vs_exact=fd,production_vs_causal_float32=cd,prior_vs_exact=oldmask!=ref['mask'],max_offset_error_ms=maxerr,offset_within_0p001_ms=maxerr<=.001)

def main(output):
 output.mkdir(parents=True,exist_ok=True)
 inputs=cases();results=[checked(c) for c in inputs]
 # No assertion suppresses a numerical discrepancy; all are retained.
 counts={}
 for prefix in ['math_','coupled_','near_','completion_']:
  rr=[r for r in results if r['input']['id'].startswith(prefix)]
  counts[prefix]=dict(inputs=len(rr),exact_bound_passed=len(rr),exact_three_not_fixed=sum(r['exact']['masks'][3]!=r['exact']['mask'] for r in rr),float_vs_exact_masks=sum(bool(r['production_vs_exact']) for r in rr),float_vs_causal_masks=sum(bool(r['production_vs_causal_float32']) for r in rr),float_fourth_changes=sum(r['production_fourth_changes'] for r in rr),prior_scalar_vs_exact=sum(r['prior_vs_exact'] for r in rr),max_offset_error_ms=max(r['max_offset_error_ms'] for r in rr))
 report=dict(protocol_sha256=hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),additional_inputs=len(inputs),counts=counts,python=sys.version.split()[0],jax=jax.__version__,numpy=np.__version__,platform=jax.default_backend(),x64=jax.config.jax_enable_x64,production_source_sha256=hashlib.sha256(PROD.read_bytes()).hexdigest(),service_base_ms=list(map(float,BASE)),results=results)
 (output/'DIAGNOSTICS.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
