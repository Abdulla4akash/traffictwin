"""Admission/input/work validation for new records only; no evaluator imports.

Extends the prepared runner's validator without changing its tolerances.
Final admission is recorded from active & ~notadm, before and independently
of deadline success; categories alone are not used to infer admission.
"""
from pathlib import Path
import hashlib,json
import numpy as np

ARMS=['ingress_dla','dla','per_task_dla','causal_round_robin']
FILES=['summary.json','per_step.npz','per_task.npz']

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def ah(a):
 a=np.ascontiguousarray(a);h=hashlib.sha256(str((a.shape,a.dtype.str)).encode());h.update(a.tobytes());return h.hexdigest()
def need(ok,message):
 if not bool(ok):raise ValueError(message)
def exact_count(value,expected,name):
 need(np.isfinite(value) and value==expected,f'Integer count mismatch: {name}: {value} != {expected}')
def carry_count(w,q):
 # Match the declared float32 drain/floor operations, including positive-work carry.
 drain=np.minimum(w,np.float32(1000));remaining=w-drain
 frac=np.where(w>0,drain/np.maximum(w,np.float32(1e-6)),np.float32(0))
 departed=np.where(remaining<=0,q,np.floor(q.astype(np.float32)*frac).astype(np.int32))
 count=np.maximum(q-departed,0)
 return np.where((remaining>0)&(count==0),1,count)

def validate_cell(dest,config):
 dest=Path(dest);s=json.loads((dest/'summary.json').read_text())
 with np.load(dest/'per_step.npz',allow_pickle=False) as z:step={k:z[k] for k in z.files}
 with np.load(dest/'per_task.npz',allow_pickle=False) as z:task={k:z[k] for k in z.files}
 T=config['steps'];N=215;R=9;K=5;shape=(T,K,N)
 bools=['task_active','task_met','task_v2i_admitted','task_forwarded','task_final_admitted']
 floats=['task_lat_ms','task_sizes_mb','task_rsu_service_ms','task_local_service_ms','task_v2v_service_ms','task_forwarding_latency_ms']
 ints={'task_type':np.int8,'task_outcome':np.int8,'task_ingress_rsu':np.int16,'task_selected_execution_rsu':np.int16,'task_execution_rsu':np.int16}
 for k in bools+floats+list(ints):
  need(k in task,f'Missing task field {k}');a=task[k]
  need(a.shape==shape,f'Task shape {k}: {a.shape}')
  need(a.dtype==np.dtype(bool if k in bools else np.float32 if k in floats else ints[k]),f'Task dtype {k}: {a.dtype}')
  need(np.all(np.isfinite(a)),f'Nonfinite task field {k}')
 step_shapes={
  'arrivals':(T,),'done':(T,),'active':(T,),'n_local':(T,),'n_v2i':(T,),'n_v2v':(T,),
  'veh_action':(T,N),'veh_k':(T,N),'veh_done':(T,N),'veh_actor_logits':(T,N,3),'veh_observations':(T,N,17),
  'exogenous_keys':(T,6,2),'observation_task_type':(T,N),'observation_task_size':(T,N),
  'slot_tier':(N,),'slot_is_ev':(N,),'slot_soc_initial':(N,),'slot_tx_power_w':(N,),'times':(T,),
  'rr_pointer_before':(T,),'rr_pointer_after':(T,),
 }
 for k in ['rsu_start_busy_ms','rsu_pre_drain_busy_ms','rsu_busy_ms','rsu_start_load','rsu_pre_drain_load','rsu_load']:step_shapes[k]=(T,R)
 for k in ['veh_queue_ms','veh_start_busy_ms','veh_pre_drain_busy_ms','veh_start_load','veh_pre_drain_load','veh_load','veh_v2v_target','veh_v2v_radio_viable','veh_v2i_quality','veh_v2i_capacity_mbps','veh_soc_before','veh_soc_after','veh_energy_j']:step_shapes[k]=(T,N)
 for k,sp in step_shapes.items():
  need(k in step,f'Missing step field {k}');need(step[k].shape==sp,f'Step shape {k}: {step[k].shape}');need(np.all(np.isfinite(step[k])),f'Nonfinite step field {k}')
 for k in ['veh_observations','veh_actor_logits','rsu_busy_ms','rsu_start_busy_ms','rsu_pre_drain_busy_ms','veh_queue_ms','veh_soc_before','veh_soc_after','veh_energy_j']:need(step[k].dtype==np.float32,f'Float32 required: {k}')
 for k in ['rsu_load','rsu_start_load','rsu_pre_drain_load','veh_load','veh_start_load','veh_pre_drain_load','rr_pointer_before','rr_pointer_after']:need(step[k].dtype==np.int32,f'Int32 required: {k}')
 need(step['exogenous_keys'].dtype==np.uint32,'PRNG key dtype')
 controls=dict(T=T,maxN=N,rsu_max_concurrent=6220,rsu_lb=config['arm'],fleet_seed=config['fleet_seed'],evaluator_seed=config['evaluator_seed'],enter_reset=True,reset_soc_on_enter=False,rsu_service_mult=1.,rsu_backhaul_ms=0.,k8s_scale='off',fleet='uk2030',lambda_arrival=1.5,rsu_cap_mode='reject',substep_queue='sequential',veh_queue_mode='conserved',substep_queue_iterations=3,k_max=K,n_rsus=R,obs_variant='onehot17',model='C')
 for k,v in controls.items():need(s.get(k)==v,f'Control mismatch: {k}: {s.get(k)} != {v}')
 a=task['task_active'];oc=task['task_outcome'];met=task['task_met'];adm=task['task_final_admitted'];v2i=task['task_v2i_admitted'];lat=task['task_lat_ms'];ty=task['task_type'];actions=step['veh_action'][:,None,:]
 need(np.all((ty>=0)&(ty<3)),'Operational type range');need(np.all((step['veh_action']>=0)&(step['veh_action']<=2)),'Action range')
 need(np.all((step['veh_k']>=0)&(step['veh_k']<=K)),'Arrival count range')
 need(np.array_equal(a,np.arange(K)[None,:,None]<step['veh_k'][:,None,:]),'Offered mask/count mismatch')
 need(np.array_equal(adm,a&np.isin(oc,[1,2])),'Final admission/category mismatch')
 need(np.array_equal(v2i,adm&(actions==1)),'V2I final admission mismatch')
 need(np.array_equal(met,a&(oc==1)) and not np.any(met&~adm),'Non-admitted success/category mismatch')
 dl=np.array([100,500,100],np.float32)[ty]
 need(np.array_equal(met,a&(lat<=dl)),'Inclusive latency/deadline mismatch')
 need(np.all(lat[a&~adm]==(10*dl)[a&~adm]),'Rejected latency penalty mismatch')
 need(np.all(lat[~a]==0) and np.all(oc[~a]==0),'Inactive outcome mismatch')
 need(np.all((oc[a]>=1)&(oc[a]<=8)),'Terminal outcome range')
 cats=[int(np.count_nonzero(a&(oc==i))) for i in range(9)];off=int(a.sum());ad=int(adm.sum());success=int(met.sum())
 exact_count(s['n_offered'],off,'n_offered');exact_count(s['total_tasks'],off,'total_tasks');exact_count(s['n_admitted'],ad,'n_admitted')
 need(off==ad+sum(cats[3:]),'Offered/admitted/terminal conservation')
 need(abs(s['completion']*off-success)<1e-6,'Score numerator mismatch')
 need(abs(s['completion_admitted']*max(ad,1)-success)<1e-6,'Admitted score numerator mismatch')
 type_counts=[]
 for ti in range(3):
  offered_type=int(np.count_nonzero(a&(ty==ti)));met_type=int(np.count_nonzero(met&(ty==ti)))
  need(abs(s[f't{ti+1}_share']*off-offered_type)<1e-6,f'Type offered summary mismatch: {ti+1}')
  need(abs(s[f't{ti+1}_completion']*max(offered_type,1)-met_type)<1e-6,f'Type success summary mismatch: {ti+1}')
  type_counts.append(dict(type=ti+1,offered=offered_type,successes=met_type))
 need(np.array_equal(a.sum(axis=(1,2)),step['arrivals']),'Step arrivals mismatch');need(np.array_equal(met.sum(axis=(1,2)),step['done']),'Step successes mismatch');need(np.array_equal(met.sum(axis=1),step['veh_done']),'Vehicle successes mismatch')
 for i,key in enumerate(['v2i_gate_rejected','v2i_cap_rejected','local_mqd_rejected','v2v_mqd_rejected','v2i_unavailable','v2v_unavailable'],3):exact_count(s[key],cats[i],key)
 for i,key in enumerate(['n_local','n_v2i','n_v2v']):need(np.array_equal((a&(actions==i)).sum(axis=(1,2)),step[key]),f'Mode offered mismatch {key}')
 proposal=task['task_selected_execution_rsu'];ingress=task['task_ingress_rsu'];ex=task['task_execution_rsu'];attempt=a&(actions==1)
 for name,x in [('proposal',proposal),('ingress',ingress)]:
  need(np.all((x[attempt]>=0)&(x[attempt]<R)) and np.all(x[~attempt]==-1),f'{name} range/mask mismatch')
 need(np.array_equal(ex,np.where(v2i,proposal,-1)),'Execution/proposal/admission mismatch')
 need(np.array_equal(task['task_forwarded'],v2i&(ex!=ingress)),'Forwarding relationship mismatch');need(np.all(task['task_forwarding_latency_ms']==0),'Nonzero forwarding cost')
 if config['arm']=='ingress_dla':need(np.array_equal(proposal,ingress),'Ingress policy proposal mismatch')
 radio=step['veh_v2i_quality'][:,None,:]>0
 need(not np.any(v2i&~radio),'Unavailable radio admitted')
 need(not np.any(a&np.isin(oc,[3,4,7])&(actions!=1)),'V2I category assigned to other mode')
 need(not np.any(a&(oc==5)&(actions!=0)) and not np.any(a&np.isin(oc,[6,8])&(actions!=2)),'Vehicle category/mode mismatch')
 work=task['task_rsu_service_ms'];need(np.all(work>=0),'Negative service')
 enqueued=np.zeros((T,R),np.float64);counts=np.zeros((T,R),np.int64)
 for r in range(R):
  m=v2i&(ex==r);enqueued[:,r]=np.where(m,work,0).sum(axis=(1,2),dtype=np.float64);counts[:,r]=m.sum(axis=(1,2))
 err=step['rsu_pre_drain_busy_ms'].astype(np.float64)-step['rsu_start_busy_ms']-enqueued
 need(np.allclose(err,0,atol=.01,rtol=0),f'RSU service conservation: {np.max(np.abs(err))}')
 need(np.array_equal(step['rsu_pre_drain_load']-step['rsu_start_load'],counts),'RSU enqueue count mismatch')
 need(np.all((step['rsu_pre_drain_load']>=0)&(step['rsu_pre_drain_load']<=6220)),'RSU capacity boundary')
 need(np.allclose(step['rsu_busy_ms'],np.maximum(step['rsu_pre_drain_busy_ms']-1000,0),atol=.001,rtol=1e-6),'RSU drain mismatch')
 need(np.array_equal(step['rsu_load'],carry_count(step['rsu_pre_drain_busy_ms'],step['rsu_pre_drain_load'])),'RSU task-count carry mismatch')
 need(np.array_equal(step['rsu_start_busy_ms'],np.vstack([np.zeros((1,R),np.float32),step['rsu_busy_ms'][:-1]])),'RSU service carry mismatch')
 need(np.array_equal(step['rsu_start_load'],np.vstack([np.zeros((1,R),np.int32),step['rsu_load'][:-1]])),'RSU count carry mismatch')
 # Vehicle services use actual local/peer compute draws and independent final admission.
 loc=adm&(actions==0);peer=adm&(actions==2);targets=step['veh_v2v_target']
 inc=np.where(loc,task['task_local_service_ms'],0).sum(axis=1,dtype=np.float64);cnt=loc.sum(axis=1,dtype=np.int64)
 peerwork=np.where(peer,task['task_v2v_service_ms'],0).sum(axis=1,dtype=np.float64);peercount=peer.sum(axis=1,dtype=np.int64)
 ix=np.arange(T)[:,None];np.add.at(inc,(ix,targets),peerwork);np.add.at(cnt,(ix,targets),peercount)
 verr=step['veh_pre_drain_busy_ms'].astype(np.float64)-step['veh_start_busy_ms']-inc
 need(np.allclose(verr,0,atol=.01,rtol=0),f'Vehicle service conservation: {np.max(np.abs(verr))}')
 need(np.array_equal(step['veh_pre_drain_load']-step['veh_start_load'],cnt),'Vehicle enqueue count mismatch')
 need(np.all((step['veh_pre_drain_load']>=0)&(step['veh_pre_drain_load']<=s['max_vehicle_queue_depth'])),'Vehicle count capacity')
 need(np.allclose(step['veh_queue_ms'],np.maximum(step['veh_pre_drain_busy_ms']-1000,0),atol=.001,rtol=1e-6),'Vehicle drain mismatch')
 need(np.array_equal(step['veh_load'],carry_count(step['veh_pre_drain_busy_ms'],step['veh_pre_drain_load'])),'Vehicle count carry mismatch')
 with np.load(config['inputs']['trace'],allow_pickle=False) as tr:
  keep=tr['mask'][:T]&~tr['enter'][:T]
  need(np.array_equal(step['active'],tr['mask'][:T].sum(axis=1)),'Trace active count mismatch')
  need(np.array_equal(step['times'],tr['times'][:T]),'Trace timestamp mismatch')
  need(np.all(step['veh_k'][~tr['mask'][:T]]==0),'Arrivals on inactive vehicle')
  need(np.array_equal(step['veh_start_busy_ms'],np.where(keep,np.vstack([np.zeros((1,N),np.float32),step['veh_queue_ms'][:-1]]),0)),'Vehicle queue reset/carry mismatch')
  need(np.array_equal(step['veh_start_load'],np.where(keep,np.vstack([np.zeros((1,N),np.int32),step['veh_load'][:-1]]),0)),'Vehicle count reset/carry mismatch')
 # No SoC reset: feedback is measured rather than forced common.
 need(np.array_equal(step['veh_soc_before'],np.vstack([step['slot_soc_initial'][None,:],step['veh_soc_after'][:-1]])),'SoC carry/reset mismatch')
 ptrcoverage=None
 if config['arm']=='causal_round_robin':
  advances=attempt&radio;flat=advances.reshape(T,K*N)
  expected_before=np.concatenate([np.array([0],np.int64),np.cumsum(flat.sum(axis=1),dtype=np.int64)[:-1]])%R
  need(np.array_equal(step['rr_pointer_before'],expected_before),'Cyclic pointer start/carry mismatch')
  offsets=np.cumsum(flat,axis=1,dtype=np.int64)-flat
  selected=((expected_before[:,None]+offsets)%R).reshape(shape)
  need(np.array_equal(proposal[attempt],selected[attempt]),'Cyclic proposal/advancement mismatch')
  expected_after=(expected_before+flat.sum(axis=1))%R
  need(np.array_equal(step['rr_pointer_after'],expected_after),'Cyclic final pointer mismatch');exact_count(s['round_robin_pointer_final'],int(expected_after[-1]),'pointer final')
  ptrcoverage=dict(advances=int(advances.sum()),advanced_then_rejected=int(np.count_nonzero(advances&~adm)),unavailable_attempts=int(np.count_nonzero(attempt&~radio)),start=0,final=int(expected_after[-1]))
 else:need(np.all(step['rr_pointer_before']==-1)&np.all(step['rr_pointer_after']==-1),'Old arm acquired cyclic state')
 shared={f'step/{k}':ah(step[k]) for k in ['times','slot_tier','slot_is_ev','slot_soc_initial','slot_tx_power_w','exogenous_keys','observation_task_type','observation_task_size','veh_k']}
 shared.update({f'task/{k}':ah(task[k]) for k in ['task_active','task_type','task_sizes_mb','task_rsu_service_ms']})
 return dict(status='passed',seal_sha256=config['seal_sha256'],configuration=config,output_sha256={k:sha(dest/k) for k in FILES},shared_input_hashes=shared,offered=off,admitted=ad,successes=success,terminal_failures=off-ad,outcome_counts=cats,type_counts=type_counts,max_service_conservation_error_ms=float(np.max(np.abs(err))),max_vehicle_service_conservation_error_ms=float(np.max(np.abs(verr))),pointer=ptrcoverage,field_contract={kind:{k:dict(shape=list(v.shape),dtype=str(v.dtype)) for k,v in arrays.items()} for kind,arrays in [('step',step),('task',task)]},control_interpretation='frozen weights; endogenous observation/logit/action differences allowed')

def validate_block(root,b,seal_sha):
 root=Path(root);records={arm:json.loads((root/f"block_{b['block']:02d}_{arm}"/'attempt_001/VALIDATED.json').read_text()) for arm in ARMS}
 baseline=records['ingress_dla']['shared_input_hashes']
 need(all(x['status']=='passed' and x['shared_input_hashes']==baseline and x['seal_sha256']==seal_sha for x in records.values()),'Shared exogenous input or cell seal mismatch')
 names=['veh_observations','veh_actor_logits','veh_action','veh_soc_before','veh_v2i_quality','veh_v2i_capacity_mbps','veh_v2v_target']
 with np.load(root/f"block_{b['block']:02d}_ingress_dla"/'attempt_001/per_step.npz',allow_pickle=False) as z:base={k:z[k] for k in names}
 rows=[]
 for arm in ARMS:
  with np.load(root/f"block_{b['block']:02d}_{arm}"/'attempt_001/per_step.npz',allow_pickle=False) as z:
   row=dict(arm=arm)
   for k in names:
    x=z[k];row[k+'_identical']=bool(np.array_equal(x,base[k]));row[k+'_max_abs']=float(np.max(np.abs(x.astype(np.float64)-base[k])))
    if k=='veh_action':row['changed_vehicle_seconds']=int(np.count_nonzero(x!=base[k]))
   rows.append(row)
 return dict(status='passed',block=b['block'],seal_sha256=seal_sha,cell_receipt_sha256={arm:sha(root/f"block_{b['block']:02d}_{arm}"/'attempt_001/VALIDATED.json') for arm in ARMS},shared_exogenous_inputs='identical',policy_controls=rows,actions_forced=False,selected_radio_quantities='endogenous; equality reported, not required')
