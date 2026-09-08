"""Predeclared block analysis and precision sensitivity; no evaluator import."""
from pathlib import Path
import argparse,json,math
import numpy as np
from scipy.stats import t,nct
HERE=Path(__file__).resolve().parent
CONTRASTS=[('per_task_dla','ingress_dla'),('dla','ingress_dla'),('per_task_dla','causal_round_robin')]
def precision():
 c=float(t.ppf(1-.05/6,7))
 return dict(n=8,df=7,family_size=3,critical=c,assumptions='independent approximately normal paired joint-block effects; variance unknown',half_widths=[dict(assumed_sd_pp=s,half_width_pp=c*s/math.sqrt(8)) for s in [.25,.5,1,2,4]],power=[dict(effect_over_sd=d,power=float(nct.cdf(-c,7,d*math.sqrt(8))+nct.sf(c,7,d*math.sqrt(8)))) for d in [0,.25,.5,1,1.5,2]],observed_power=False)
def analyse(root,seal):
 from runner import require_complete
 require_complete(root,seal)
 rows=[]
 for b in seal['blocks']:
  d={}
  for arm in seal['arms']:
   cell=root/f"block_{b['block']:02d}_{arm}"/'attempt_001'
   if not (cell/'VALIDATED.json').is_file():raise ValueError(f'Incomplete validated block: {cell}')
   rec=json.loads((cell/'VALIDATED.json').read_text());d[arm]=100*rec['successes']/rec['offered']
  rows.append(dict(block=b['block'],fleet_seed=b['fleet_seed'],evaluator_seed=b['evaluator_seed'],attainment_pct=d))
 results=[];c=precision()['critical']
 for b,a in CONTRASTS:
  effects=np.array([x['attainment_pct'][b]-x['attainment_pct'][a] for x in rows]);mean=float(effects.mean());sd=float(effects.std(ddof=1));half=c*sd/math.sqrt(8)
  results.append(dict(contrast=b+' minus '+a,effects_pp=effects.tolist(),mean_pp=mean,sd_pp=sd,family95_low_pp=mean-half,family95_high_pp=mean+half))
 return dict(blocks=rows,primary=results,critical_value=c,df=7,equal_block_weighting=True,scope='new joint-randomness study only; not pooled with prior evidence')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 data=analyse(a.root,json.loads((HERE/'SEALED_EXECUTION.json').read_text())) if a.root else precision()
 a.output.write_text(json.dumps(data,indent=2)+'\n')
