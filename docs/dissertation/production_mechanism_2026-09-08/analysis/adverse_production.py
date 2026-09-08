"""Inspect the already tested nominal coupled adverse case with frozen helpers."""
import copy,csv,json,hashlib
import diagnostics as dg
OUT=dg.HERE/'results'
data=json.loads((OUT/'ADVERSE_CASE.json').read_text())
chosen=next(r for r in data['transfers'] if r['form']=='reduced' and r['xi']==1. and r['input']['C']==6220)
c=chosen['input'];result=dg.old.run(c)
assert result['totals']==chosen['totals']
# Use the remaining predeclared adverse minimisation allowance on this same
# explanatory transfer, not an expanded parameter search.
trials=[]
short=copy.deepcopy(c);short['K']=1
variants=[('one_substep',short)]
for i in range(len(c['s'])):
 t=copy.deepcopy(c)
 for k in ['s','d','a','radio']:t[k].pop(i)
 variants.append((f'delete_position_{i}',t))
for name,t in variants:
 rr=dg.old.run(t);trials.append(dict(name=name,input=t,totals=rr['totals'],retains_loss=rr['totals']['C']['successes']<rr['totals']['B']['successes']))
assert not any(t['retains_loss'] for t in trials)
assert data['minimisation_inputs']+data['transfer_inputs']+len(trials)<=120
rows=[];agreements=[]
for k,step in enumerate(result['steps']):
 a=step['A'];b=step['B'];cc=step['C'];n=len(c['s'])
 s=dg.jnp.array(c['s'],dg.jnp.float32);d=dg.jnp.array(c['d'],dg.jnp.float32);e=dg.jnp.array(c['radio'])
 ret,trace,_=dg.production(dg.jnp.array(a['base_work'],dg.jnp.float32),dg.jnp.array(a['base_load'],dg.jnp.int32),s,d,e,dg.jnp.array(a['selected'],dg.jnp.int32),dg.jnp.int32(c['C']))
 pr=dg.cp.per_task_sequential_least_busy(attempts=dg.jnp.ones(n,bool),ingress_radio_viable=e,deadlines_ms=d,service_work_ms_by_rsu=dg.jnp.repeat(s[:,None],2,axis=1),base_busy_ms=dg.jnp.array(cc['base_work'],dg.jnp.float32),base_load=dg.jnp.array(cc['base_load'],dg.jnp.int32),capacity=dg.jnp.int32(c['C']),reconciliation_iterations=3)
 assert list(map(bool,ret[1]))==a['admitted']==b['admitted']
 assert list(map(bool,pr.admitted))==cc['admitted'] and list(map(int,pr.selected_rsu))==cc['selected']
 # Each substep has no admission disagreement: numeric state differences are
 # reported, not substituted into the source-backed scalar illustration.
 maxerr=max(abs(float(x)-y) for x,y in zip(ret[0],a['offsets']))
 cerr=max(abs(float(x)-y) for x,y in zip(pr.queue_offset_ms,cc['offsets']))
 assert max(maxerr,cerr)<=.001
 agreements.append(dict(substep=k+1,A_masks_agree=True,C_masks_and_targets_agree=True,A_max_offset_error_ms=maxerr,C_max_offset_error_ms=cerr))
 for i,(s0,d0) in enumerate(zip(c['s'],c['d'])):
  row=dict(substep=k+1,candidate=i+1,task_type=chosen['types'][i]+1,deadline=d0,service=s0)
  for arm in ['B','C']:
   v=step[arm];r=v['selected'][i];before=v['base_work'][r]+v['offsets'][i]
   row.update({arm+'_target':r,arm+'_before':before,arm+'_admitted':v['admitted'][i],arm+'_completion':before+s0 if v['admitted'][i] else None,arm+'_met':v['met'][i]})
  rows.append(row)
report=dict(input=c,task_types=[t+1 for t in chosen['types']],result=result,hand_table=rows,additional_minimisation_inputs=len(trials),deletion_trials=trials,production_helper_agreement=agreements,script_sha256=hashlib.sha256(open(__file__,'rb').read()).hexdigest(),scope='Nominal service noise1, production deadlines and C6220; explicit two-RSU/two-substep configuration. K and R are diagnostic sizes, not the historical5-slot/9-or10-RSU configuration. Local service/deadline/capacity compatibility is established; full trajectory reachability and observed frequency are not.')
(OUT/'ADVERSE_PRODUCTION.json').write_text(json.dumps(report,indent=2)+'\n')
with (OUT/'ADVERSE_PRODUCTION.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({'additional_inputs':len(trials),'B_successes':result['totals']['B']['successes'],'C_successes':result['totals']['C']['successes'],'helpers':agreements},indent=2))
