"""Descriptive joins of authenticated September task coordinates; no new tests."""
from pathlib import Path
import argparse,hashlib,itertools,json
import numpy as np
HERE=Path(__file__).resolve().parent

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command_contract(r):
 c=json.loads((HERE/'sources/compact'/r['id']/'command.json').read_text());mf=HERE/'sources/compact'/r['group']/'manifest.json';m=json.loads(mf.read_text());assert digest(mf)==c['manifest_sha256']
 av=c['argv'];value=lambda flag:av[av.index(flag)+1]
 assert int(value('--seed'))==m['evaluator_seed']==0
 return {'manifest_sha256':digest(mf),'trace_sha256':m['trace']['sha256'],'actor_sha256':m['actor']['sha256'],'sources':m['source_sha256'],'evaluator_seed':int(value('--seed')),'fleet_seed':int(value('--fleet-seed')),'environment':c['environment']}
def order(r):
 cell=r['id'].split('/')[2]
 if 'ingress' in cell:return 0
 if 'common_target' in cell:return 1
 if 'fresh' in cell or 'per_task' in cell:return 2
 if '1000' in cell:return 5
 if '500' in cell:return 4
 return 3

def main(out,cache):
 raw=json.loads((out/'RAW_AUDIT.json').read_text());rs=raw['runs'];pairs=[]
 for a,b in itertools.combinations(sorted(rs,key=lambda r:(r['group'],r['fleet_seed'],order(r))),2):
  if a['group']!=b['group'] or a['fleet_seed']!=b['fleet_seed']:continue
  ca,cb=command_contract(a),command_contract(b);assert ca==cb
  identity_keys=[k for k in a['identities'] if k!='step_veh_actor_logits'];assert all(a['identities'][k]==b['identities'][k] for k in identity_keys)
  assert a['offered']==b['offered'] and a['shape']==b['shape'] and all(a['checks'].values()) and all(b['checks'].values())
  def read(r):
   path=cache/(r['cache_key']+'.npz');z=np.load(path,allow_pickle=False);n=int(np.prod(z['shape']));return {k:np.unpackbits(z[k],count=n).astype(bool) for k in z.files if k!='shape'}
  aa,bb=read(a),read(b);assert np.array_equal(aa['active'],bb['active']);active=aa['active'];gain=active&~aa['met']&bb['met'];loss=active&aa['met']&~bb['met'];g=int(gain.sum());l=int(loss.sum());both=int((aa['met']&bb['met']).sum());neither=int((active&~aa['met']&~bb['met']).sum())
  parts={'rejection_or_unavailability_to_success':int((gain&~aa['admitted']).sum()),'admitted_miss_to_success':int((gain&aa['admitted']).sum()),'gate_rejection_to_success':int((gain&aa['gate']).sum()),'capacity_rejection_to_success':int((gain&aa['cap']).sum()),'other_terminal_to_success':int((gain&aa['other_terminal']).sum()),'success_to_rejection_or_unavailability':int((loss&~bb['admitted']).sum()),'success_to_admitted_miss':int((loss&bb['admitted']).sum())}
  assert g-l==b['successes']-a['successes'];assert g+l+both+neither==a['offered'];assert parts['rejection_or_unavailability_to_success']+parts['admitted_miss_to_success']==g;assert sum(parts[k] for k in ['gate_rejection_to_success','capacity_rejection_to_success','other_terminal_to_success'])==parts['rejection_or_unavailability_to_success']
  pairs.append(dict(A=a['id'],B=b['id'],group=a['group'],seed=a['fleet_seed'],offered=a['offered'],failure_to_success=g,success_to_failure=l,success_both=both,failure_both=neither,net_successes=g-l,difference_pp=100*(g-l)/a['offered'],transition_categories=parts,identity_fields_checked=identity_keys,logits_byte_identical=a['identities']['step_veh_actor_logits']==b['identities']['step_veh_actor_logits'],input_contract=ca,net_identity_passed=True))
 report=dict(date='2026-09-08',pairs=pairs,coverage='All 23 within-study/same-seed pairs among the 19 audited September full cells: 12 morning primary pairs, 1 excluded morning pilot pair, 10 incident sensitivity pilot pairs. No historical E0/E1/E2/E2c/E2d task transitions recovered.',join='Same trace/seed/slot/substep coordinate; active/type/arrivals/times/fleet/actions/ingress hashes agree. Task sizes and service draws are not saved independently: stream correspondence follows the manifest-bound arm-independent key schedule. Logit byte identity is diagnostic, actual action identity is required.',interpretation='Descriptive fixed-history accounting. Later queue states differ; no individual-decision causal attribution or task-level intervals. No pooling of scenarios or pilot into primary inference.')
 (out/'OUTCOME_TRANSITIONS.json').write_text(json.dumps(report,indent=2)+'\n');print('Pairs checked:',len(pairs))
 for p in pairs:
  if 'replication' in p['group'] and '_ingress/' in p['A'] and '_per_task/' in p['B']:print(p['seed'],p['failure_to_success'],p['success_to_failure'],p['net_successes'],p['transition_categories'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--cache',required=True,type=Path);a=p.parse_args();main(a.output,a.cache)
