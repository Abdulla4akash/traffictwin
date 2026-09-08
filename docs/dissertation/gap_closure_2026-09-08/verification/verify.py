#!/usr/bin/env python3
"""Relocatable entry point. Explicit raw root; no implicit machine paths."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tempfile
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--raw-root',type=Path);p.add_argument('--production-python',type=Path);a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
 checks=[]
 for b in json.loads((HERE/'SOURCE_BINDINGS.json').read_text()):
  f=HERE/b['file']
  if not f.is_file():raise SystemExit('Missing compact/source input: '+b['file'])
  if hashlib.sha256(f.read_bytes()).hexdigest()!=b['sha256']:raise SystemExit('Mismatched compact/source input: '+b['file'])
  checks.append(b['file'])
 def run(script,*args,python=None):
  result=subprocess.run([str(python or sys.executable),str(HERE/script),'--output',str(a.output),*map(str,args)],capture_output=True,text=True)
  (a.output/(script+'.log')).write_text(result.stdout+result.stderr)
  if result.returncode:raise SystemExit(script+' failed: '+result.stderr.strip()+'; see output log')
 for script in ['compact_arithmetic.py','historical_receipts.py','scheduling_reference.py']:run(script)
 if a.production_python:run('compare_production.py',python=a.production_python)
 if a.raw_root:
  with tempfile.TemporaryDirectory(prefix='traffictwin-packed-') as td:
   run('raw_audit.py','--raw-root',a.raw_root.resolve(),'--cache',td)
   run('outcome_transitions.py','--cache',td)
 report=dict(status='completed_for_requested_coverage',compact_files_verified=len(checks),compact_arithmetic='central historical/primary tables regenerated; not task-level validation',standalone_kernel='440 cases plus bounded minimisation; no full simulation',production_helper='executed' if a.production_python else 'not requested; requires explicit compatible JAX Python',september_raw='87-file integrity and 19-run audit plus 23 paired transitions executed' if a.raw_root else 'not requested; requires explicit optional raw root with RAW_INPUTS.json layout',historical_raw='not assessable from available records: E0/E1/E2 original raw outputs unavailable; deletion reported by the author; no known backup',other_historical_raw='E2b ingress/E2c/E2d original arrays not established available; deletion not inferred',full_simulation='not executed',physical_validation='not performed',independent_review='not supplied by this verifier')
 (a.output/'VERIFY.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
