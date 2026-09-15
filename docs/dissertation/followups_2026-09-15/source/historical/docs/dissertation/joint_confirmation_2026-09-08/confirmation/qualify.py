"""Eight-attempt maximum end-to-end qualification; never launches full cells."""
from pathlib import Path
import argparse,fcntl,json,shutil,sys,time
import numpy as np
import runner as r

def compatible(old,new):
 differences=[];fields=0
 a=r.load(old/'summary.json');b=r.load(new/'summary.json')
 for k,v in a.items():
  if k=='wall_s':continue
  fields+=1
  if b.get(k)!=v:differences.append('summary/'+k)
 for filename in ['per_step.npz','per_task.npz']:
  with np.load(old/filename,allow_pickle=False) as a,np.load(new/filename,allow_pickle=False) as b:
   for k in a.files:
    fields+=1
    if k not in b or a[k].dtype!=b[k].dtype or not np.array_equal(a[k],b[k]):differences.append(filename+'/'+k)
 rec=dict(status='passed' if not differences else 'failed',shared_scientific_fields=fields,differences=differences,excluded=['summary/wall_s'])
 r.need(not differences,f'Instrumentation compatibility failure: {differences}')
 return rec

def restart(long,short):
 fields=0
 for name in ['per_step.npz','per_task.npz']:
  with np.load(long/name,allow_pickle=False) as a,np.load(short/name,allow_pickle=False) as b:
   for k in a.files:
    x=a[k];y=b[k];expected=x[:150] if x.shape[0]==300 else x
    r.need(x.dtype==y.dtype and np.array_equal(expected,y),f'Restart prefix mismatch: {name}/{k}');fields+=1
 return dict(status='passed',compared_fields=fields,steps=150,pointer_initialised_to_zero=True)

def negatives(root,c,d,block):
 cases=[];nr=root/'negative_tests';nr.mkdir(exist_ok=False)
 # Corrupt only a new disposable copy of a short output, preserving original files.
 dest=nr/'corrupted_count';dest.mkdir()
 source=Path(c['output'])
 for f in r.FILES:shutil.copyfile(source/f,dest/f)
 bad=r.load(dest/'summary.json');bad['n_offered']+=.5;r.dump(dest/'summary.json',bad)
 try:r.validate_cell(dest,c)
 except ValueError as e:cases.append(dict(case='corrupted_count',refused=True,error=str(e)))
 else:raise ValueError('Corrupted count accepted')
 # Block receipt copies only: a shared input mismatch must fail before reading arrays.
 br=nr/'shared_mismatch';br.mkdir()
 for arm in r.ARMS:
  p=br/f'block_00_{arm}'/'attempt_001';p.mkdir(parents=True)
  rec=r.load(root/'matrix'/f'block_00_{arm}'/'attempt_001/VALIDATED.json')
  if arm=='dla':rec['shared_input_hashes']['task/task_type']='changed'
  r.dump(p/'VALIDATED.json',rec)
 try:r.validate_block(br,block,c['seal_sha256'])
 except ValueError as e:cases.append(dict(case='mismatched_shared_input',refused=True,error=str(e)))
 else:raise ValueError('Shared mismatch accepted')
 # Test the exact completion guard, substituting only its seal authentication
 # because qualification deliberately has no execution-authorised seal yet.
 from unittest.mock import patch
 with patch.object(r,'check_seal',return_value=d),patch.object(r,'SEAL',Path(c['seal_path'])):
  try:r.require_complete(nr,d)
  except ValueError as e:
   r.need('block controls' in str(e),'Wrong missing-block refusal');cases.append(dict(case='missing_block_receipt',refused=True,error=str(e)))
  else:raise ValueError('Missing block receipt accepted')
 # Output drift: valid receipt bound to original bytes, then append whitespace
 # only to copied JSON. A semantically unchanged but altered output must fail.
 hp=nr/'changed_hash';hp.mkdir()
 for f in r.FILES+['VALIDATED.json']:shutil.copyfile(source/f,hp/f)
 with (hp/'summary.json').open('a') as f:f.write(' ')
 try:r.verify_completed(hp,c)
 except ValueError as e:
  r.need('output changed' in str(e),'Wrong changed-output refusal');cases.append(dict(case='changed_output_hash',refused=True,error=str(e)))
 else:raise ValueError('Changed output accepted')
 r.write_once(nr/'RESULTS.json',cases);return cases

def main():
 a=r.args();r.need(not a.execute,'Qualification must not use --execute')
 a.output_root.mkdir(parents=True,exist_ok=True)
 with (a.output_root/'QUALIFY.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  d=r.load(r.PREPARED/'confirmation/SEALED.json');d['sources']=r.source_bindings();d['qualification']=dict(max_attempts=8,pair=[1,0],max_steps=300);d['created_at']=r.now()
  pre=r.preflight(a,d);r.need(pre['free_gib']>=50,'Initial storage floor');d['runtime']=pre
  sp=r.HERE/'QUALIFICATION_SEAL_v1.json';r.write_once(sp,d)
  r.write_once(a.output_root/'PREFLIGHT.json',pre)
  block=dict(block=0,fleet_seed=1,evaluator_seed=0,arm_order=r.ARMS)
  schedule=[('ingress_dla',True,300),('ingress_dla',False,300),('dla',True,300),('dla',False,300),('per_task_dla',True,300),('per_task_dla',False,300),('causal_round_robin',False,300),('causal_round_robin',False,150)]
  records=[];frozen={};new={};matrix=a.output_root/'matrix';matrix.mkdir()
  for i,(arm,old,steps) in enumerate(schedule,1):
   r.need(len(list(a.output_root.glob('attempt_*')))<8,'Qualification budget exhausted')
   dest=a.output_root/f'attempt_{i:02d}_{arm}'
   c=r.configuration(d,block,arm,a,sp,steps,old,dest)
   print(f'QUALIFICATION START {i}/8 {arm} frozen={old} steps={steps}',flush=True)
   try:
    rec=r.run_attempt(c,d,validate=not old)
    records.append(dict(attempt=i,arm=arm,frozen=old,steps=steps,path=str(dest),simulation_process_s=rec['simulation_process_s'],validation_s=rec['validation_s'],receipt_sha256=r.sha(dest/('REFERENCE.json' if old else 'VALIDATED.json'))))
    if old:frozen[arm]=dest
    elif steps==300:
     new[arm]=dest
     if arm in frozen:
      compatibility=compatible(frozen[arm],dest);r.write_once(dest/'COMPATIBILITY.json',compatibility);records[-1]['compatibility']=compatibility
     link=matrix/f'block_00_{arm}'/'attempt_001';link.parent.mkdir();link.symlink_to(dest,target_is_directory=True)
     if arm=='causal_round_robin':
      start=time.monotonic();receipt=r.validate_block(matrix,block,r.sha(sp));receipt['validation_s']=time.monotonic()-start;r.write_once(matrix/'BLOCK_00.json',receipt)
    else:r.write_once(dest/'RESTART.json',restart(new[arm],dest))
   except BaseException as exc:
    r.write_once(a.output_root/'QUALIFICATION_FAILED.json',dict(status='failed',attempt=i,error=repr(exc),finished_at=r.now(),full_attempts=0,completed=records));raise
   print(f'QUALIFICATION PASSED {i}/8 simulation_s={rec["simulation_process_s"]:.2f}',flush=True)
  neg=negatives(a.output_root,c,d,block)
  report=dict(status='passed',created_at=r.now(),qualification_seal_sha256=r.sha(sp),runtime=pre,attempts=records,negative_tests=neg,block_receipt_sha256=r.sha(matrix/'BLOCK_00.json'),full_evaluations_launched=0,qualification_outputs=str(a.output_root),boundary='Eight short runs, not independent fleet replications; no full outcomes inspected')
  r.write_once(r.PACKAGE/'evidence/QUALIFICATION.json',report);r.write_once(a.output_root/'QUALIFICATION.json',report)
  print('QUALIFICATION COMPLETE',flush=True)
if __name__=='__main__':main()
