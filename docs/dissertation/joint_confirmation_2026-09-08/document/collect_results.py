"""Package the sealed analysis and compact execution records; no simulations.
The primary calculations remain in the pre-outcome sealed analyse.py.
"""
from pathlib import Path
import argparse,csv,json,shutil,sys,time
from datetime import datetime
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parent
sys.path.insert(0,str(PACKAGE/'confirmation'))
import runner as r
import analyse

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args();root=a.root;out=PACKAGE/'evidence';d=r.check_seal()
 started=r.now();t=time.monotonic();results=analyse.analyse(root,d);elapsed=time.monotonic()-t
 results.update(status='completed_primary_confirmation',created_at=r.now(),seal_sha256=r.sha(r.SEAL),analysis_elapsed_s=elapsed,analysis_started_at=started,analysis_source_sha256=r.sha(PACKAGE/'confirmation/analyse.py'),analysis_runtime=dict(python=sys.version.split()[0],numpy=analyse.np.__version__,scipy=__import__('scipy').__version__))
 r.write_once(out/'ANALYSIS.json',results)
 cells=[];blocks=[];inventory=[];files=0;bytes_total=0
 for b in d['blocks']:
  br=r.load(root/f"BLOCK_{b['block']:02d}.json");blocks.append(br)
  for arm in b['arm_order']:
   dest=root/f"block_{b['block']:02d}_{arm}"/'attempt_001';rec=r.load(dest/'VALIDATED.json');s=r.load(dest/'summary.json')
   row={k:rec[k] for k in ['offered','admitted','successes','terminal_failures','simulation_process_s','validation_s','total_wall_s','started_at','finished_at','max_service_conservation_error_ms','max_vehicle_service_conservation_error_ms']}
   row.update(block=b['block'],fleet_seed=b['fleet_seed'],evaluator_seed=b['evaluator_seed'],arm=arm,attainment_pct=100*rec['successes']/rec['offered'],admitted_misses=rec['outcome_counts'][2],gate_rejected=rec['outcome_counts'][3],capacity_rejected=rec['outcome_counts'][4],local_rejected=rec['outcome_counts'][5],v2v_rejected=rec['outcome_counts'][6],v2i_unavailable=rec['outcome_counts'][7],v2v_unavailable=rec['outcome_counts'][8],evaluator_scan_wall_s=s['wall_s'])
   cells.append(row)
   compact=out/'cells'/f"block_{b['block']:02d}_{arm}";compact.mkdir(parents=True)
   for name in ['summary.json','COMMAND.json','STARTED.json','VALIDATED.json','stdout.log','stderr.log']:
    shutil.copyfile(dest/name,compact/name)
   for path in sorted(dest.iterdir()):
    if path.is_file():
     size=path.stat().st_size;inventory.append(dict(path=str(path.relative_to(root)),bytes=size,sha256=r.sha(path)));files+=1;bytes_total+=size
 launch=out/'launch';launch.mkdir()
 for path in sorted(root.iterdir()):
  if path.is_file():
   size=path.stat().st_size;inventory.append(dict(path=path.name,bytes=size,sha256=r.sha(path)));files+=1;bytes_total+=size
   if path.name.startswith('PREFLIGHT_'):shutil.copyfile(path,launch/path.name)
 r.write_once(out/'BLOCK_CONTROLS.json',blocks);r.write_once(out/'CELL_RESULTS.json',cells)
 with (out/'CELL_RESULTS.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(cells[0]));w.writeheader();w.writerows(cells)
 effects=[]
 for c in results['primary']:
  for b,e in zip(d['blocks'],c['effects_pp']):effects.append(dict(block=b['block'],fleet_seed=b['fleet_seed'],evaluator_seed=b['evaluator_seed'],contrast=c['contrast'],effect_pp=e))
 with (out/'PAIRED_EFFECTS.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(effects[0]));w.writeheader();w.writerows(effects)
 r.write_once(out/'RAW_INVENTORY.json',dict(raw_root=str(root),files=inventory,file_count=files,total_bytes=bytes_total,off_machine_backup='No approved destination; not transferred',qualification_raw_root=d['qualification']['raw_root'],qualification_source_snapshot=str(Path(d['qualification']['raw_root'])/'source_snapshot')))
 timing=dict(full_attempts=len(cells),valid_blocks=len(blocks),full_simulation_process_s=sum(x['simulation_process_s'] for x in cells),cell_validation_s=sum(x['validation_s'] for x in cells),block_validation_s=sum(x['validation_s'] for x in blocks),analysis_with_completion_checks_s=elapsed,evaluator_reported_scan_s=sum(x['evaluator_scan_wall_s'] for x in cells),qualification_simulation_process_s=sum(x['simulation_process_s'] for x in r.load(out/'QUALIFICATION.json')['attempts']),qualification_cell_validation_s=sum(x['validation_s'] for x in r.load(out/'QUALIFICATION.json')['attempts']),started_at=min(x['started_at'] for x in cells),last_cell_finished_at=max(x['finished_at'] for x in cells),interpretation='Process time includes startup, compilation, evaluation and compressed output writing; evaluator scan time includes JIT/scan synchronisation. Validation and analysis are separate; no new scheduler benchmark.')
 timing['campaign_finished_at']=r.load(root/'COMPLETE.json')['finished_at']
 timing['campaign_elapsed_wall_s']=(datetime.fromisoformat(timing['campaign_finished_at'])-datetime.fromisoformat(timing['started_at'])).total_seconds()
 timing['other_campaign_overhead_s']=timing['campaign_elapsed_wall_s']-timing['full_simulation_process_s']-timing['cell_validation_s']-timing['block_validation_s']
 r.write_once(out/'TIMING.json',timing)
 for name in ['RUNTIME_ESTIMATE.json','COMPLETE.json']:shutil.copyfile(root/name,out/name)
 print(json.dumps({'primary':results['primary'],'timing':timing,'raw_gib':bytes_total/2**30},indent=2))
if __name__=='__main__':main()
