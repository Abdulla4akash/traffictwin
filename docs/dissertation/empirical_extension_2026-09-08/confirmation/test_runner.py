"""Dry-run guard/configuration tests, without subprocess evaluator execution."""
from pathlib import Path
import argparse,json,sys,tempfile
from unittest.mock import patch
import runner
HERE=Path(__file__).resolve().parent

def main():
 d=runner.check_seal();assert not d['execute_new_confirmation']
 with tempfile.TemporaryDirectory() as td:
  a=argparse.Namespace(python=Path('/explicit/python'),runtime_root=Path('/explicit/runtime'),trace=Path('/explicit/trace'),actor=Path('/explicit/actor'),output_root=Path(td))
  cs=[runner.configuration(d,b,arm,a) for b in d['blocks'] for arm in b['arm_order']]
  assert len(cs)==32 and len({c['output'] for c in cs})==32
  assert len({b['fleet_seed'] for b in d['blocks']})==len({b['evaluator_seed'] for b in d['blocks']})==8
  assert all(set(b['arm_order'])==set(runner.ARMS) for b in d['blocks'])
  for c in cs:
   cmd=c['command'];assert cmd[cmd.index('--max-steps')+1]=='10800' and cmd[cmd.index('--rsu-cap-abs')+1]=='6220'
   assert '--extension-audit' in cmd and '--reset-soc-on-enter' not in cmd and '--ignore-enter' not in cmd
  with patch.object(sys,'argv',['runner.py','--execute']),patch.object(runner.subprocess,'run',side_effect=AssertionError('Unexpected launch')):
   try:runner.main()
   except SystemExit as e:assert 'false' in str(e)
   else:raise AssertionError('False switch did not refuse execution')
  try:runner.validate_cell(Path(td),cs[0])
  except FileNotFoundError:pass
  else:raise AssertionError('Missing outputs passed validation')
  # A complete cell matrix without its final block control receipt must never
  # produce intervals, even when every cell individually has a receipt.
  for c in cs:
   dest=Path(c['output']);dest.mkdir(parents=True);(dest/'VALIDATED.json').write_text('{}')
  try:runner.require_complete(Path(td),d)
  except ValueError as e:assert 'block controls' in str(e)
  else:raise AssertionError('Missing block receipt accepted')
  b=d['blocks'][0];bp=Path(td)/'BLOCK_00.json'
  runner.dump(bp,dict(status='passed',seal_sha256=runner.sha(HERE/'SEALED.json'),shared_exogenous_inputs='identical',cell_receipt_sha256={}))
  try:runner.require_complete(Path(td),d)
  except ValueError as e:assert 'receipt binding' in str(e)
  else:raise AssertionError('Unbound cell receipt accepted')
  helper=runner.ROOT/'docs/evaluation/vec_followup_2026-09-07/frozen_evaluator/eval/e2d_per_task_placement.py'
  original_sha=runner.sha
  with patch.object(runner,'sha',side_effect=lambda p:'changed' if p==helper else original_sha(p)):
   try:runner.check_seal()
   except ValueError as e:assert 'source mismatch' in str(e)
   else:raise AssertionError('Changed imported helper accepted')
 report=dict(status='passed',missing_block_controls_fail=True,unbound_cell_receipt_fails=True,imported_helper_drift_fails=True,configurations=32,distinct_joint_blocks=8,false_switch_refuses_before_launch=True,missing_outputs_fail=True,evaluator_processes_launched=0,limitations='Does not exercise full output accounting on new evaluator records; these remain unavailable because campaign is unrun',seal_sha256=runner.sha(HERE/'SEALED.json'))
 runner.dump(HERE/'RUNNER_TESTS.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
