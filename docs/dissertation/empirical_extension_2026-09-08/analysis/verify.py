"""Relocatable compact verification; optional NEW type reaggregation only.

Default never opens raw arrays, imports JAX, times kernels or runs an evaluator.
"""
from pathlib import Path
import argparse,csv,hashlib,json,subprocess,sys
import numpy as np
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parent;ROOT=PACKAGE.parents[2]
OLD=ROOT/'docs/evaluation/vec_followup_2026-09-07'
BASE='ee6a4b151d92329f9c26e3f344d87b70b84fc31e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def csvrows(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def run(output,raw_root=None):
 output.mkdir(parents=True,exist_ok=True)
 b=read(HERE/'SOURCE_BINDINGS.json')
 for row in b:
  p=ROOT/row['path']
  if not p.is_file() or sha(p)!=row['sha256']:raise ValueError(f'Missing/mismatched binding: {row["path"]}')
 types=read(HERE/'results/TASK_TYPES.json');rows=types['rows'];pairs=types['paired']
 assert types['script_sha256']==sha(HERE/'task_types.py') and len(rows)==24 and len(pairs)==12
 for r in rows:
  assert r['offered']==r['admitted']+r['gate_rejected']+r['other_terminal']
  assert r['admitted']==r['successes']+r['admitted_misses']
  assert abs(r['attainment_pct']-100*r['successes']/r['offered'])<1e-12
 for p in pairs:
  x=next(r for r in rows if (r['seed'],r['type'],r['arm'])==(p['seed'],p['type'],'ingress'));y=next(r for r in rows if (r['seed'],r['type'],r['arm'])==(p['seed'],p['type'],'per_task'))
  assert x['offered']==y['offered']==p['offered'] and y['successes']-x['successes']==p['net_successes']
  assert abs(y['attainment_pct']-x['attainment_pct']-p['difference_pp'])<1e-12
  assert p['net_successes']==-p['gate_change']-p['admitted_miss_change']-p['other_terminal_change']
 for binding in types['bindings']:
  seed=int(binding['run'].split('seed_')[1].split('_')[0]);arm='per_task' if '_per_task/' in binding['run'] else 'ingress'
  for key,val in binding['totals'].items():assert sum(r[key] for r in rows if (r['seed'],r['arm'])==(seed,arm))==val
  summary=OLD/binding['run']/'summary.json';assert sha(summary)==binding['summary_sha256']
  s=read(summary);assert abs(s['completion']*s['n_offered']-binding['totals']['successes'])<1e-6
 bench=read(HERE/'results/BENCHMARK.json');durations=csvrows(HERE/'results/BENCHMARK_TIMES.csv');assert len(durations)==1600
 for r in bench['rows']:
  ts=np.array([float(x['milliseconds']) for x in durations if (int(x['N']),x['fixture'],x['policy'])==(r['N'],r['fixture'],r['policy'])]);assert len(ts)==100
  for key,q in [('median_ms',50),('q25_ms',25),('q75_ms',75),('p95_ms',95)]:assert abs(float(np.percentile(ts,q))-r[key])<1e-12
 for rel,h in bench['sources'].items():assert sha(PACKAGE/rel)==h
 sys.path.insert(0,str(PACKAGE/'confirmation'))
 import runner
 sealed=runner.check_seal();assert not sealed['execute_new_confirmation']
 assert read(PACKAGE/'confirmation/DRY_RUN.json')['seal_sha256']==sha(PACKAGE/'confirmation/SEALED.json')
 from analyse import precision
 assert precision()==read(PACKAGE/'confirmation/PRECISION.json')
 # Recreate central table inputs from unchanged compact files, no extra tests.
 central=dict(incident=csvrows(OLD/'historical_e0_e2d/experiments/E2d/data/e2d_paired_results.csv'),morning=csvrows(OLD/'generalisation-replication-2026-09-07/runs.csv'),morning_intervals=csvrows(OLD/'generalisation-replication-2026-09-07/paired_intervals.csv'),task_types=rows,type_changes=pairs,benchmark=bench['rows'])
 (output/'CENTRAL_TABLES.json').write_text(json.dumps(central,indent=2)+'\n')
 for name,data in [('TASK_TYPES.csv',rows),('TASK_TYPE_CHANGES.csv',pairs)]:
  with (output/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 raw_status='not requested; compact checks do not revalidate raw task outcomes'
 if raw_root is not None:
  subprocess.run([sys.executable,str(HERE/'task_types.py'),'--raw-root',str(raw_root),'--output',str(output/'raw_type_aggregation')],check=True)
  assert read(output/'raw_type_aggregation/TASK_TYPES.json')['rows']==rows
  raw_status='eight specified September files authenticated and type-aggregated; prior 19-run audit/23 joins not rerun'
 report=dict(status='passed',source_bindings=len(b),task_type_rows=24,paired_type_rows=12,benchmark_calls_checked=1600,full_evaluations=0,raw_record_check=raw_status,missing_private_inputs='Historical E0/E1/E2 originals unavailable: not assessable. Optional September raw aggregation requires explicit root; actor/trace required only for future campaign preflight.',seal_sha256=sha(PACKAGE/'confirmation/SEALED.json'))
 (output/'COMPACT_CHECKS.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--raw-root',type=Path);a=p.parse_args();run(a.output,a.raw_root)
