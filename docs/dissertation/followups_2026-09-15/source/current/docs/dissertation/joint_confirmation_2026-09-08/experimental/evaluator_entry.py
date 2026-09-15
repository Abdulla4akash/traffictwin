"""Explicit routing: old configurations execute their unchanged evaluator.

--extension-audit selects the new instrumented copy. Never inferred from an
existing flag. RR requires it. This wrapper itself does not qualify a full run.
"""
from pathlib import Path
import argparse,hashlib,os,sys
HERE=Path(__file__).resolve().parent
EXPECTED='2824d9c2ef09e7748cd420d1ab2f0526d28157b8986605dc831397b6c618c07e'
def plan(argv,python=sys.executable):
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--runtime-root',type=Path,required=True);p.add_argument('--extension-audit',action='store_true');a,rest=p.parse_known_args(argv)
 old=a.runtime_root/'eval/eval_sumo_stage1_mc.py'
 if not old.is_file() or hashlib.sha256(old.read_bytes()).hexdigest()!=EXPECTED:raise ValueError('Original evaluator missing or source mismatch')
 mode=rest[rest.index('--rsu-lb')+1] if '--rsu-lb' in rest else 'off'
 if mode=='causal_round_robin' and not a.extension_audit:raise ValueError('RR requires explicit --extension-audit')
 target=HERE/'evaluator_v2.py' if a.extension_audit else old
 return [python,'-u',str(target),*rest]
if __name__=='__main__':
 command=plan(sys.argv[1:]);os.execv(command[0],command)
