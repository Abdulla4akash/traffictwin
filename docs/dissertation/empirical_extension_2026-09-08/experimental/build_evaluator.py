"""Deterministically create a separately versioned evaluator; never edit frozen code.

Only new copy changes: RR target/pointer, additive control records, relocatable
imports. Source hash and replacement cardinality checks fail closed on drift.
"""
from pathlib import Path
import ast,hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
FROZEN=ROOT/'docs/evaluation/vec_followup_2026-09-07/frozen_evaluator/eval'
SOURCE=FROZEN/'eval_sumo_stage1_mc.py'
EXPECTED='2824d9c2ef09e7748cd420d1ab2f0526d28157b8986605dc831397b6c618c07e'
def generate():
 s=SOURCE.read_text();assert hashlib.sha256(s.encode()).hexdigest()==EXPECTED
 def replace(old,new,n=1):
  nonlocal s
  assert s.count(old)==n,(old[:70],s.count(old),n)
  s=s.replace(old,new)
 replace('from e2_path_instrumentation import summarise_v2i_paths', '''from pathlib import Path
EXTENSION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXTENSION_DIR / "vendor"))
sys.path.insert(0, str(EXTENSION_DIR.parents[3] / "docs/evaluation/vec_followup_2026-09-07/frozen_evaluator/eval"))
from round_robin import causal_round_robin
from e2_path_instrumentation import summarise_v2i_paths''')
 replace('REPO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jaxmarl", "env")','REPO = str(EXTENSION_DIR / "vendor")')
 replace('"ingress_dla", "per_task_dla"],','"ingress_dla", "per_task_dla", "causal_round_robin"],')
 replace('    VEHC = SEQQ and CAP_REJECT and args.veh_queue == "conserved"','''    ROUND_ROBIN = args.rsu_lb == "causal_round_robin"
    if ROUND_ROBIN and not (SEQQ and CAP_REJECT and args.veh_queue == "conserved"
                           and K8S == "off" and not STATE_STUDY):
        raise SystemExit("causal_round_robin v1 requires sequential/reject/conserved, scaling off, no state-delay study")
    VEHC = SEQQ and CAP_REJECT and args.veh_queue == "conserved"''')
 # A parallel offsets wrapper reuses the original service-key derivation and
 # accounting; only causal helper call adds pointer argument and return.
 tree=ast.parse(s);node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='per_task_offsets')
 lines=s.splitlines();wrapper='\n'.join(lines[node.lineno-1:node.end_lineno])
 rr=wrapper.replace('per_task_offsets(', 'round_robin_offsets(').replace('placement_busy_ms=None):','pointer):').replace('result = per_task_sequential_least_busy(', 'result, next_pointer = causal_round_robin(').replace('placement_busy_ms=placement_busy_ms,','pointer=pointer,').replace('            result.placement_busy_before_ms,','            result.placement_busy_before_ms,\n            next_pointer,')
 rr=rr.replace('Causal per-task placement and admission for ``per_task_dla``.','Causal round-robin version 1; original service draws and admission fields.')
 replace(wrapper,wrapper+'\n\n'+rr)
 replace('    def step(carry, xs):\n','    def step(carry, xs):\n        if ROUND_ROBIN:\n            rr_pointer = carry[-1]\n            carry = carry[:-1]\n')
 replace('        def sub_step(c, sub_idx):\n','        def sub_step(c, sub_idx):\n            if ROUND_ROBIN:\n                pointer = c[-1]\n                c = c[:-1]\n')
 replace('                else:  # p2c / dla_p2c — per-vehicle two random candidates','''                elif ROUND_ROBIN:
                    (rsu_extra, rsu_ok, n_grej, n_crej, gate_fail_m,
                     w_off_v2i, w_adm_v2i, exec_idx, rsu_ok_pre,
                     placement_busy_before_ms, pointer) = round_robin_offsets(
                        sub_keys, actions, slot_types, v2i_q > 0.0, rb, rl,
                        active, None, pointer)
                else:  # p2c / dla_p2c — per-vehicle two random candidates''')
 replace('if args.rsu_lb != "per_task_dla":','if args.rsu_lb not in ("per_task_dla", "causal_round_robin"):')
 replace('if SEQQ and args.rsu_lb != "per_task_dla":','if SEQQ and args.rsu_lb not in ("per_task_dla", "causal_round_robin"):')
 replace('            return c2, ys_sub','''            if ROUND_ROBIN:
                c2 += (pointer,)
            if PERTASK:
                ys_sub += (slot_sizes.astype(jnp.float32), rsu_cms.astype(jnp.float32))
            return c2, ys_sub''')
 replace('''            (qb, qd, rb, rl, e_src, e_tgt_src, done_n, ttype_tot, ttype_done,
             lat_sum, rej_step), sub_ys = jax.lax.scan(
                sub_step, c0, jnp.arange(KMAX))''','''            if ROUND_ROBIN:
                c0 += (rr_pointer,)
            sub_final, sub_ys = jax.lax.scan(sub_step, c0, jnp.arange(KMAX))
            if ROUND_ROBIN:
                rr_pointer = sub_final[-1]
                sub_final = sub_final[:-1]
            (qb, qd, rb, rl, e_src, e_tgt_src, done_n, ttype_tot, ttype_done,
             lat_sum, rej_step) = sub_final''')
 replace('                veh_actor_logits=actor_logits.astype(jnp.float32),','''                veh_actor_logits=actor_logits.astype(jnp.float32),
                veh_observations=obs.astype(jnp.float32),
                exogenous_keys=jnp.stack([kt, ka, kl, ko, kp, kslots]),
                observation_task_type=obs_type,
                observation_task_size=obs_size,
                rsu_start_busy_ms=rsu_busy,
                rsu_pre_drain_busy_ms=rb,
                rsu_start_load=rsu_load,
                rsu_pre_drain_load=rl,
                veh_soc_before=soc,''')
 replace('            ys.update(task_type=sub_ys[0], task_lat_ms=sub_ys[1],','''            ys.update(task_sizes_mb=sub_ys[-2], task_rsu_service_ms=sub_ys[-1])
            ys.update(task_type=sub_ys[0], task_lat_ms=sub_ys[1],''')
 replace('        return next_carry, (ys or None)','        if ROUND_ROBIN:\n            next_carry += (rr_pointer,)\n        return next_carry, (ys or None)')
 replace('    if HAS_ENTER:\n        xs =','    if ROUND_ROBIN:\n        init += (jnp.int32(0),)\n    if HAS_ENTER:\n        xs =')
 replace('                         "veh_best_v2v", "rsu_busy_ms", "rsu_load"]','''                         "veh_best_v2v", "rsu_busy_ms", "rsu_load",
                         "veh_observations", "exogenous_keys", "observation_task_type",
                         "observation_task_size", "rsu_start_busy_ms", "rsu_pre_drain_busy_ms",
                         "rsu_start_load", "rsu_pre_drain_load", "veh_soc_before"]''')
 replace('                                slot_is_ev=np.asarray(is_ev),','                                slot_is_ev=np.asarray(is_ev),\n                                slot_soc_initial=np.asarray(soc0),\n                                slot_tx_power_w=np.asarray(txw),')
 replace('                                task_type=ys_np["task_type"],','''                                task_type=ys_np["task_type"],
                                task_sizes_mb=ys_np["task_sizes_mb"],
                                task_rsu_service_ms=ys_np["task_rsu_service_ms"],''')
 replace('    print(json.dumps(out, indent=2))','''    out["extension_schema"] = "joint_seed_cyclic_v1"
    out["evaluator_seed"] = args.seed
    out["round_robin_pointer_final"] = int(carry[-1]) if ROUND_ROBIN else None
    print(json.dumps(out, indent=2))''')
 ast.parse(s)
 return s
if __name__=='__main__':
 out=HERE/'evaluator_v1.py';out.write_text(generate());print(out)
