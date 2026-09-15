"""Add records to the prepared v1 evaluator, without changing its calculations."""
from pathlib import Path
import ast, hashlib

HERE = Path(__file__).resolve().parent
PREPARED = HERE.parent.parent / 'empirical_extension_2026-09-08/experimental/evaluator_v1.py'

def generate():
    s = PREPARED.read_text()
    def replace(old, new):
        nonlocal s
        assert s.count(old) == 1, (old[:80], s.count(old))
        s = s.replace(old, new)
    replace('            rr_pointer = carry[-1]', '            rr_pointer = carry[-1]\n            rr_pointer_before = rr_pointer')
    replace('ys_sub += (slot_sizes.astype(jnp.float32), rsu_cms.astype(jnp.float32))',
            'ys_sub += (slot_sizes.astype(jnp.float32), rsu_cms.astype(jnp.float32),\n'
            '                           (active & ~notadm), local_cms.astype(jnp.float32),\n'
            '                           target_cms.astype(jnp.float32))')
    replace('ys.update(task_sizes_mb=sub_ys[-2], task_rsu_service_ms=sub_ys[-1])',
            'ys.update(task_sizes_mb=sub_ys[-5], task_rsu_service_ms=sub_ys[-4],\n'
            '                      task_final_admitted=sub_ys[-3],\n'
            '                      task_local_service_ms=sub_ys[-2],\n'
            '                      task_v2v_service_ms=sub_ys[-1])')
    replace('                veh_soc_before=soc,', '''                veh_soc_before=soc,
                veh_soc_after=soc_new,
                veh_energy_j=per_veh_e,
                veh_v2i_quality=v2i_q,
                veh_v2i_capacity_mbps=v2i_cap,
                veh_v2v_radio_viable=best_v2v_ok,
                veh_v2v_target=best_v2v_idx,
                veh_start_busy_ms=q_busy,
                veh_pre_drain_busy_ms=qb,
                veh_start_load=q_depth,
                veh_pre_drain_load=qd,
                veh_load=q_depth_new,
                rr_pointer_before=rr_pointer_before if ROUND_ROBIN else jnp.int32(-1),
                rr_pointer_after=rr_pointer if ROUND_ROBIN else jnp.int32(-1),''')
    replace('"rsu_start_load", "rsu_pre_drain_load", "veh_soc_before"]',
            '''"rsu_start_load", "rsu_pre_drain_load", "veh_soc_before",
                         "veh_soc_after", "veh_energy_j", "veh_v2i_quality",
                         "veh_v2i_capacity_mbps", "veh_v2v_radio_viable", "veh_v2v_target",
                         "veh_start_busy_ms", "veh_pre_drain_busy_ms", "veh_start_load",
                         "veh_pre_drain_load", "veh_load", "rr_pointer_before", "rr_pointer_after"]''')
    replace('task_rsu_service_ms=ys_np["task_rsu_service_ms"],',
            '''task_rsu_service_ms=ys_np["task_rsu_service_ms"],
                                task_final_admitted=ys_np["task_final_admitted"],
                                task_local_service_ms=ys_np["task_local_service_ms"],
                                task_v2v_service_ms=ys_np["task_v2v_service_ms"],''')
    replace('out["extension_schema"] = "joint_seed_cyclic_v1"',
            'out["extension_schema"] = "joint_seed_cyclic_v2_records"\n'
            '    out["substep_queue_iterations"] = args.substep_queue_iters\n'
            '    out["k_max"] = int(KMAX)\n'
            '    out["n_rsus"] = int(R)\n'
            '    out["max_vehicle_queue_depth"] = int(MQD)')
    ast.parse(s)
    return s

if __name__ == '__main__':
    path = HERE / 'evaluator_v2.py'
    assert not path.exists(), 'Never silently replace a used evaluator version'
    path.write_text(generate())
    print(hashlib.sha256(path.read_bytes()).hexdigest())
