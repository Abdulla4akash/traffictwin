"""Version 1 causal cyclic placement; AI-assisted retrospective comparator.

Admission and result fields are derived from the frozen E2d causal helper.
Only destination selection and its persistent pointer differ. No random draws.
The caller commits pointer once per substep and carries it between batches.
"""
from pathlib import Path
import importlib.util
import jax
import jax.numpy as jnp
FROZEN=Path(__file__).resolve().parent/'vendor'
spec=importlib.util.spec_from_file_location('extension_frozen_causal',FROZEN/'e2d_per_task_placement.py')
frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
PerTaskPlacement=frozen.PerTaskPlacement

def causal_round_robin(*, attempts, ingress_radio_viable, deadlines_ms,
 service_work_ms_by_rsu, base_busy_ms, base_load, capacity,
 reconciliation_iterations, pointer):
 """Advance on attempted V2I with q>0, before capacity/gate; never retry.

 As in the original causal helper, each repeated pass starts from exactly the
 same initial state, including the pointer. Padding/unavailable radio does not
 advance it. Selected fields for inactive candidates have no execution meaning.
 """
 def one_pass():
  def place(carry,candidate):
   busy,load,ptr=carry
   attempt,radio,deadline,service=candidate
   target=ptr
   before=busy[target];work=service[target]
   offset=busy[target]-base_busy_ms[target]
   coarse=attempt & radio & (base_load[target]<jnp.int32(capacity))
   gate=busy[target]<deadline;cap=load[target]<jnp.int32(capacity)
   rejected_gate=coarse & ~gate;rejected_cap=coarse & gate & ~cap
   admitted=coarse & gate & cap
   busy=busy.at[target].add(jnp.where(admitted,work,jnp.float32(0)))
   load=load.at[target].add(admitted.astype(jnp.int32))
   ptr=jnp.where(attempt & radio,(ptr+1)%base_busy_ms.shape[0],ptr).astype(jnp.int32)
   return (busy,load,ptr),(target,admitted,coarse,rejected_gate,rejected_cap,offset,work,before)
  final,out=jax.lax.scan(place,(base_busy_ms,base_load,pointer),
   (attempts,ingress_radio_viable,deadlines_ms,service_work_ms_by_rsu))
  return PerTaskPlacement(out[0],out[1],out[2],out[3],out[4],out[5],out[6],final[0],final[1],out[7]),final[2]
 result=None
 for _ in range(max(reconciliation_iterations,1)):result=one_pass()
 return result
