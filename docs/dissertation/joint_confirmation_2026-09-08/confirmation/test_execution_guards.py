"""Focused review regressions and validation of existing qualification outputs.
No evaluator process is launched; mocked attempts are explicitly labelled.
"""
import argparse,fcntl,subprocess,tempfile,time
from pathlib import Path
from unittest.mock import patch
import runner as r

def main():
 q=Path('/Users/akashx/Downloads/diss_mat/traffictwin-joint-confirmation-raw-2026-09-08/qualification')
 report=[]
 for p in sorted(q.glob('attempt_*/VALIDATED.json')):
  old=r.load(p);rec=r.validate_cell(p.parent,old['configuration'])
  r.need(rec['output_sha256']==old['output_sha256'],'Qualification output drift')
  report.append(dict(attempt=p.parent.name,status='passed',original_receipt_sha256=r.sha(p),type_counts=rec['type_counts'],outcome_counts=rec['outcome_counts'],pointer=rec['pointer']))
 with tempfile.TemporaryDirectory(prefix='tt-guard-',dir=q) as td:
  root=Path(td);a=argparse.Namespace(output_root=root/'another_root');d=dict(output_root=str(root/'sealed_root'))
  try:r.require_output_root(a,d)
  except ValueError as e:r.need('sealed study root' in str(e),'Wrong output-root refusal')
  else:raise ValueError('Alternate output root accepted')
  # Independent file descriptions contend for the identical study-wide lock.
  with (root/'study.lock').open('a+') as one,(root/'study.lock').open('a+') as two:
   fcntl.flock(one,fcntl.LOCK_EX|fcntl.LOCK_NB)
   try:fcntl.flock(two,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:pass
   else:raise ValueError('Overlapping study lock accepted')
  old=r.load(next(q.glob('attempt_*/VALIDATED.json')));c=old['configuration'].copy();c['output']=str(root/'mock_failed_attempt')
  d=r.load(r.HERE/'QUALIFICATION_SEAL_v1.json');d['sources']=r.source_bindings()
  def failure(*args,**kwargs):time.sleep(.01);raise subprocess.CalledProcessError(9,['MOCK_ONLY'])
  with patch.object(r.subprocess,'run',side_effect=failure):
   try:r.run_attempt(c,d)
   except subprocess.CalledProcessError:pass
   else:raise ValueError('Mock failure did not fail')
  fail=r.load(root/'mock_failed_attempt/FAILED.json');r.need(fail['failed_phase']=='simulation' and fail['simulation_process_s']>0 and fail['validation_s']==0,'Failure timing not truthful')
 result=dict(status='passed',created_at=r.now(),evaluator_processes_launched=0,existing_short_records_revalidated=report,alternate_output_root_refused=True,overlapping_lock_refused=True,mocked_failure_phase_timing=fail,qualification_source_snapshot=str(q/'source_snapshot'),sources=r.source_bindings(),interpretation='Additive type-summary assertions and launch/receipt safeguards; no changed scheduler, numerical tolerance or simulation output. Original qualification sources/receipts retained.')
 r.write_once(r.PACKAGE/'evidence/QUALIFICATION_FOLLOWUP.json',result)
 print('Focused guards and five existing short-record checks passed; no evaluator launched')
if __name__=='__main__':main()
