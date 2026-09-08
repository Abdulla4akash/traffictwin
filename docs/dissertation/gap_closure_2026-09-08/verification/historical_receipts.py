"""Extract historical receipt coverage; never labels it fresh raw validation."""
from pathlib import Path
import json,argparse
HERE=Path(__file__).resolve().parent
NA='not assessable from available records'
def main(out):
 rows=[];base=HERE/'sources/legacy'
 for e,pattern in [('E0','*validation*.json'),('E1','*campaign_validation*.json'),('E2','*validation*.json'),('E2b','*validation*.json')]:
  for f in sorted((base/e).rglob(pattern)):
   j=json.loads(f.read_text())
   groups=[('full' if 'full' in f.name or e=='E1' else 'smoke',j['runs'])] if 'runs' in j else [(phase,j[phase+'_validation']['runs']) for phase in ['smoke','full']]
   for phase,runs in groups:
    for i,r in enumerate(runs):
     obs=r.get('observed',{});s=r.get('summary',{})
     if not s:s=r.get('scientific_summary',{})
     cats=obs.get('outcome_counts',{})
     cap=int(cats['4']) if cats else s.get('v2i_cap_rejected')
     offered=obs.get('n_offered',s.get('n_offered'));adm=obs.get('n_admitted',s.get('n_admitted'))
     rawhash=r.get('file_sha256',{}).get('per_task.npz') or r.get('array_sha256',{}).get('per_task')
     checks=[c for c in r['checks'] if any(x in c['name'] for x in ['deadline_met_flag','offered_equals','outcome','v2i_admitted','execution_rsu'])]
     row=dict(study=e,configuration=r.get('arm',r.get('cap_label','off')),phase=phase,seed=r.get('fleet_seed',0),repeat=i+1 if phase=='smoke' else 1,receipt=str(f.relative_to(HERE)),offered_recorded=offered,admitted_recorded=adm,terminal_failures_recorded=(offered-adm) if offered is not None and adm is not None else None,capacity_rejections_recorded=cap,recorded_checks=checks,raw_task_hash_record=rawhash,availability=('original raw outputs unavailable; deletion reported by the author; no known backup' if e in ['E0','E1','E2'] else 'original ingress arrays not located in known study paths; deletion not inferred'),fresh_offered_partition=NA,false_success_discrepancies=NA,latency_discrepancies=NA,fixed_history_rescore=NA,implication='Historical estimate retained; receipt evidence is not a fresh task-level audit.')
     rows.append(row)
 report=dict(date='2026-09-08',status='historical_raw_gap_unresolved',scope='Surviving receipts and summaries only; original E0/E1/E2 deletion reported by author',source_versions={'E0_E1_off':'0f01f4d2082d3e8b735e74a873095ab8eeba37cc','E2_off_jsq_dla':'e11f4445a9cc939a79d4f419c6f48b43ce110664','E2b_new_ingress':'0e5ed2f79b50011fe0475a5c2069978f9fdd778d','E2b_off':'reuses exact E2 off files; not a new run'},reuse=['E1 seed 0 cap 2p5 reuses E0 full','E2b off/jsq/dla reuse E2 full'],runs=rows)
 out.mkdir(parents=True,exist_ok=True);(out/'HISTORICAL_COVERAGE.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Receipt rows',len(rows),'all fresh historical task checks:',NA)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
