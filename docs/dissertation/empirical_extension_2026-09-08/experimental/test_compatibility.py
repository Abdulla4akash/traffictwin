"""Source/route and scheduler-boundary checks, not full evaluator qualification."""
from pathlib import Path
import ast,hashlib,json,tempfile
import numpy as np
import jax.numpy as jnp
from build_evaluator import generate,SOURCE
from evaluator_entry import plan
from round_robin import causal_round_robin
from kernels import batch_kernel
HERE=Path(__file__).resolve().parent

def main():
 assert (HERE/'evaluator_v1.py').read_text()==generate()
 modes=['off','jsq','p2c','dla','dla_p2c','ingress_dla','per_task_dla'];checks=[]
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);(root/'eval').mkdir();(root/'eval/eval_sumo_stage1_mc.py').write_bytes(SOURCE.read_bytes())
  for mode in modes:
   for extra in [[],['--substep-queue','sequential','--rsu-cap-mode','reject'],['--k8s-scale','reactive'],['--rsu-state-delay-ms','100']]:
    flags=['--trace','dummy','--actor','dummy','--rsu-lb',mode]+extra
    cmd=plan(['--runtime-root',str(root)]+flags)
    assert cmd[2]==str(root/'eval/eval_sumo_stage1_mc.py') and cmd[3:]==flags
   checks.append(dict(mode=mode,unchanged_entry_and_arguments=True))
  try:plan(['--runtime-root',str(root),'--rsu-lb','causal_round_robin'])
  except ValueError:pass
  else:raise AssertionError('Silent new mode')
 # Bite a pointer triple-advance/reset error: R=3, two viable attempts per
 # substep, two substeps, then a second batch. Draining must not reset pointer.
 args=(jnp.zeros(3,jnp.float32),jnp.zeros(3,jnp.int32),jnp.int32(0),jnp.array([[1,1,1],[1,1,1]],bool),jnp.array([[1,0,1],[1,0,1]],bool),jnp.full((2,3),100.,jnp.float32),jnp.full((2,3),20.,jnp.float32),jnp.zeros((2,3),jnp.int32))
 kernel=batch_kernel('causal_round_robin');final,out=kernel(*args)
 np.testing.assert_array_equal(out[0],[[0,1,1],[2,0,0]]);assert int(final[2])==1
 second,_=kernel(*final,*args[3:]);assert int(second[2])==2
 # Same one-RSU workload/admission rules agree with the frozen causal helper
 # at batch boundary; offered masks and work arrays are literally identical.
 one=(jnp.zeros(1,jnp.float32),jnp.zeros(1,jnp.int32),jnp.int32(0),*args[3:])
 x=batch_kernel('per_task_dla')(*one);y=batch_kernel('causal_round_robin')(*one)
 for xx,yy in zip(x[1],y[1]):np.testing.assert_array_equal(xx,yy)
 result=dict(status='passed',old_mode_routes=checks,config_routes_checked=28,generated_copy_reproducible=True,pointer_across_substeps_and_drained_batches=True,one_rsu_batch_same_inputs_equality=True,full_evaluator_compatibility='not executed; old routes delegate exact original, new instrumented full path awaits authorised qualification',full_evaluations=0,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'evaluator_entry.py',HERE/'evaluator_v1.py',HERE/'build_evaluator.py']})
 (HERE.parent/'analysis/results/COMPATIBILITY_TESTS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
