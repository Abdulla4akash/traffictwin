"""Reduce the already selected adverse case; reuse saved empirical accounting."""
from pathlib import Path
import copy,csv,hashlib,itertools,json,subprocess
import diagnostics as dg
HERE=Path(__file__).resolve().parent
OUT=HERE/'results'
BASE='1b6a8555c27901ec95ad8b123c413453ecdb5620'
REPO=HERE.parents[3]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bound_to_base(p):
 data=subprocess.check_output(['git','show',BASE+':'+str(p.relative_to(REPO))],cwd=REPO)
 assert data==p.read_bytes(),p
 return dict(path=str(p.relative_to(REPO)),commit=BASE,sha256=digest(p))

def adverse():
 source=dg.OLD/'results/KERNEL_RESULTS.json';data=json.loads(source.read_text())
 start=next(r for r in data['results'] if r['totals']['C']['successes']<r['totals']['B']['successes'])
 trial=[]
 def run(c,reason):
  assert len(trial)<80
  r=dg.old.run(c);keep=r['totals']['C']['successes']<r['totals']['B']['successes']
  trial.append(dict(reason=reason,input=copy.deepcopy(c),retains_loss=keep,totals=r['totals']))
  return r,keep
 c=copy.deepcopy(start['input']);r,_=run(c,'recheck selected archived input');assert r==start
 for K in range(1,c['K']):
  t=copy.deepcopy(c);t['K']=K;rr,keep=run(t,'reduce repeated substeps')
  if keep:c=t;r=rr;break
 changed=True
 while changed and len(trial)<80:
  changed=False
  for i in range(len(c['s'])):
   if len(c['s'])<=1 or len(trial)>=80:break
   t=copy.deepcopy(c)
   for field in ['s','d','a','radio']:t[field].pop(i)
   rr,keep=run(t,'delete candidate position '+str(i))
   if keep:c=t;r=rr;changed=True;break
 # Declared finite transfers, not a new adverse search.
 transfers=[]
 for form,original in [('original',start['input']),('reduced',c)]:
  small=min(original['d']);large=max(original['d'])
  for xi,cap in itertools.product([.91,1.,1.09],[original['C'],6220]):
   t=copy.deepcopy(original);types_=[]
   for s,d in zip(t['s'],t['d']):
    options=[0,2] if d==small else [1]
    # Choose the nearest service interval for the mapped deadline, ties by type.
    def distance(k):
     lo=float(dg.BASE[k])*.9;hi=float(dg.BASE[k])*1.1
     return (max(lo-s,0,s-hi),k)
    types_.append(min(options,key=distance))
   t['d']=[dg.DEAD[k] for k in types_];t['s']=dg.service(types_,xi);t['C']=cap
   rr=dg.old.run(t);transfers.append(dict(form=form,xi=xi,types=types_,input=t,totals=rr['totals'],retains_loss=rr['totals']['C']['successes']<rr['totals']['B']['successes']))
 assert len(trial)+len(transfers)<=120
 rows=[]
 for k,step in enumerate(r['steps']):
  for i,(s,d) in enumerate(zip(c['s'],c['d'])):
   row=dict(substep=k+1,candidate=i+1,deadline=d,service=s)
   for arm in ['B','C']:
    a=step[arm];target=a['selected'][i];before=a['base_work'][target]+a['offsets'][i]
    row.update({arm+'_target':target,arm+'_before':before,arm+'_admitted':a['admitted'][i],arm+'_completion':before+s if a['admitted'][i] else None,arm+'_met':a['met'][i]})
   rows.append(row)
 report=dict(source=bound_to_base(source),selected_id=start['input']['id'],minimisation_inputs=len(trial),transfer_inputs=len(transfers),trials=trial,minimal_under_checked_deletions=not changed,reduced=r,hand_table=rows,transfers=transfers,scope='General synthetic case; production-coupled transfers are separate, all retained. B replays A targets; no optimisation or different offered populations.')
 (OUT/'ADVERSE_CASE.json').write_text(json.dumps(report,indent=2)+'\n')
 with (OUT/'ADVERSE_CASE.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 return report

def numerical():
 data=json.loads((OUT/'DIAGNOSTICS.json').read_text())
 unstable=next(r for r in data['results'] if r['input']['id'].startswith('near') and r['production_fourth_changes'])
 c=copy.deepcopy(unstable['input']);c['q']=[4];c['id']='near_unstable_count4';r=dg.checked(c)
 prefix=dg.fixture('local_prefix_four_type1',[c['w'][0]/4]*4,[100]*4,0,0,types_=[0]*4)
 pr=dg.checked(prefix)
 assert all(pr['production_mask'])
 assert sum(prefix['s'])==c['w'][0]
 # At four identical binary values the source's tree sum has the same result.
 arr=lambda k,typ:dg.jnp.array(prefix[k],typ)
 returned,_,_=dg.production(arr('w',dg.jnp.float32),arr('q',dg.jnp.int32),arr('s',dg.jnp.float32),arr('d',dg.jnp.float32),arr('e',bool),arr('target',dg.jnp.int32),dg.jnp.int32(prefix['C']))
 assert float(returned[6])==c['w'][0]
 xi=prefix['s'][0]/float(dg.BASE[0]);assert .9<=xi<1.1
 first=next(x for x in data['results'] if x['input']['id'].startswith('near') and x['production_vs_exact'])
 trials=[]
 for i in range(len(first['input']['s'])):
  t=copy.deepcopy(first['input']);t['id']=f'near_first_delete_{i}'
  for k in ['s','d','target','e','task_types']:t[k].pop(i)
  trials.append(dg.checked(t))
 assert 2+len(trials)<=9
 report=dict(protocol_sha256=digest(HERE/'FOLLOWUP_PROTOCOL.md'),initial_diagnostics_sha256=digest(OUT/'DIAGNOSTICS.json'),additional_inputs=2+len(trials),original_unstable_id=unstable['input']['id'],count_compatible=r,prefix_construction=pr,prefix_noise_multiplier=xi,first_discrepancy_id=first['input']['id'],deletion_trials=trials,scope='Explicit service arrays establish local two-substep kernel compatibility. No exact PRNG/actor/traffic reachability or empirical frequency established.')
 (OUT/'NUMERICAL_FOLLOWUP.json').write_text(json.dumps(report,indent=2)+'\n');return report

def accounting():
 source=dg.OLD/'results/OUTCOME_TRANSITIONS.json';data=json.loads(source.read_text());rr=[r for r in data['pairs'] if 'replication' in r['group'] and '_ingress/' in r['A'] and '_per_task/' in r['B']]
 assert [r['seed'] for r in rr]==[0,2,3,4]
 rows=[]
 for r in rr:
  c=r['transition_categories'];row=dict(seed=r['seed'],offered=r['offered'],gain_gate=c['gate_rejection_to_success'],gain_admitted_miss=c['admitted_miss_to_success'],loss_terminal=c['success_to_rejection_or_unavailability'],loss_admitted_miss=c['success_to_admitted_miss'],gains=r['failure_to_success'],losses=r['success_to_failure'],net=r['net_successes'])
  assert row['gain_gate']+row['gain_admitted_miss']==row['gains']
  assert row['loss_terminal']+row['loss_admitted_miss']==row['losses']
  assert row['gains']-row['losses']==row['net']
  assert r['success_both']+r['failure_both']+row['gains']+row['losses']==row['offered']==1744116
  rows.append(row)
 totals={k:sum(r[k] for r in rows) for k in rows[0] if k!='seed'}
 expected=dict(gains=284821,losses=12842,net=271979,gain_gate=211734,gain_admitted_miss=73087,loss_terminal=1044,loss_admitted_miss=11798)
 assert all(totals[k]==v for k,v in expected.items())
 report=dict(source=bound_to_base(source),rows=rows,totals=totals,scope='Re-extraction/arithmetic of existing authenticated paired outcomes. No new raw audit or joins; four fleet draws remain replications; later queue divergence prevents decision-level causal attribution.')
 (OUT/'OUTCOME_ACCOUNTING.json').write_text(json.dumps(report,indent=2)+'\n')
 with (OUT/'OUTCOME_ACCOUNTING.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 return report

if __name__=='__main__':
 a=adverse();n=numerical();o=accounting();total=671+a['minimisation_inputs']+a['transfer_inputs']+n['additional_inputs'];assert total<=800
 summary=dict(additional_input_budget=800,additional_inputs_executed=total,adverse_minimisation_inputs=a['minimisation_inputs'],adverse_transfer_inputs=a['transfer_inputs'],numeric_followup_inputs=n['additional_inputs'],adverse_reduced_input=a['reduced']['input'],adverse_reduced_totals=a['reduced']['totals'],production_transfer_losses=sum(x['retains_loss'] for x in a['transfers']),morning_counts=o['totals'],script_sha256=digest(Path(__file__)))
 (OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
