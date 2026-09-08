"""Twelve final dimension transfers; no adaptive search or full evaluator."""
import copy,hashlib,json
import diagnostics as dg
out=dg.HERE/'results'
old=json.loads((out/'ADVERSE_CASE.json').read_text())
results=[]
for x in old['transfers']:
 if x['input']['C']!=6220:continue
 for R in [9,10]:
  c=copy.deepcopy(x['input']);c['w']=[0]*R;c['q']=[0]*R;c['K']=5
  r=dg.old.run(c)
  results.append(dict(form=x['form'],xi=x['xi'],R=R,input=c,totals=r['totals'],B_targets=[s['B']['selected'][0] for s in r['steps']],retains_loss=r['totals']['C']['successes']<r['totals']['B']['successes']))
assert len(results)==12
report=dict(additional_inputs=12,followup_protocol_sha256=hashlib.sha256((dg.HERE/'FOLLOWUP_PROTOCOL.md').read_bytes()).hexdigest(),results=results,scope='Production task/deadline/range and R/K/capacity parameters, explicit synthetic arrays. No actor/task-generator execution, observed frequency or full-trajectory reachability claim.')
(out/'DIMENSION_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps([dict(form=r['form'],xi=r['xi'],R=r['R'],B=r['totals']['B']['successes'],C=r['totals']['C']['successes'],loss=r['retains_loss']) for r in results],indent=2))
