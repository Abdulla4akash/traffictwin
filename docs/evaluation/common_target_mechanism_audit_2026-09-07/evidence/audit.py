"""Read-only analysis of archived morning runs; writes only this new audit directory.

No evaluator invocation, new task generation, admission change or simulation run.
The existing workload replay reconstructs work from already recorded admissions.
"""
import csv
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('JAX_PLATFORMS', 'cpu')
os.environ.setdefault('JAX_ENABLE_X64', 'false')
sys.dont_write_bytecode = True
import jax.numpy as jnp
import numpy as np

OUT = Path(__file__).resolve().parent
SOURCE = OUT.parent / 'generalisation-replication-2026-09-07'
CODE = OUT.parent / 'vec_env-state-delay-run'
SEEDS = [0, 2, 3, 4]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def write_csv(path, rows):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'wt', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    inputs = [SOURCE / 'manifest.json', SOURCE / 'workload_checks.py', SOURCE / 'service_reference.npz']
    require(sha(inputs[0]) == '53327aa7f015d595c17d21f598d4bb1b2cdd21cb1511c2dec706dfc258360fc7', 'Manifest identity')
    for name in ['workload_checks.py', 'service_reference.npz']:
        require(sha(SOURCE / name) == manifest['campaign_files_sha256'][name], name)
    for name, expected in manifest['source_sha256'].items():
        require(sha(CODE / name) == expected, name)
        inputs.append(CODE / name)
    for seed in SEEDS:
        for arm in ['common_target', 'per_task']:
            d = SOURCE / 'cells' / f'seed_{seed}_{arm}' / 'attempt_001'
            receipt = json.loads((d / 'validation.json').read_text())
            require(receipt['status'] == 'passed', 'Run validation')
            inputs.append(d / 'validation.json')
            for name, expected in receipt['sha256'].items():
                require(sha(d / name) == expected, f'Original receipt: {d / name}')
                inputs.append(d / name)
    before = {str(p): sha(p) for p in inputs}
    spec = importlib.util.spec_from_file_location('recorded_workload_replay', SOURCE / 'workload_checks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with np.load(SOURCE / 'service_reference.npz') as z:
        work, reference_types = z['service_ms'], z['task_type']
    require(work.shape == (10800, 5, 215) and np.all(work > 0), 'Service reference shape/positivity')
    draws, substeps, examples, seconds = [], [], [], []
    for seed in SEEDS:
        d = SOURCE / 'cells' / f'seed_{seed}_common_target' / 'attempt_001'
        with np.load(d / 'per_task.npz') as z:
            selected = z['task_selected_execution_rsu']
            executed = z['task_execution_rsu']
            admitted = z['task_v2i_admitted']
            outcome = z['task_outcome']
            active = z['task_active']
            require(np.array_equal(z['task_type'], reference_types), 'Task type stream')
            field_names_task = z.files
        with np.load(d / 'per_step.npz') as z:
            recorded_end, recorded_load, times = z['rsu_busy_ms'], z['rsu_load'], z['times']
            field_names_step = z.files
        require(np.all(np.diff(times) == 1), 'One-second times')
        has_selected = (selected >= 0).any(axis=2)
        chosen = selected.max(axis=2)
        minimum_selected = np.where(selected >= 0, selected, 32767).min(axis=2)
        require(np.array_equal(chosen[has_selected], minimum_selected[has_selected]), 'One target per substep')
        require(np.array_equal(executed >= 0, admitted), 'Admission/execution identity')
        require(np.array_equal(executed[admitted], selected[admitted]), 'Selected/execution identity')
        gate_rej = active & (outcome == 3)
        cap_rej = active & (outcome == 4)
        require(not np.any(gate_rej & admitted), 'Recorded gate-rejection/admission overlap')
        summary = json.loads((d / 'summary.json').read_text())
        require(int(gate_rej.sum()) == summary['v2i_gate_rejected'], 'Gate count')
        require(int(cap_rej.sum()) == summary['v2i_cap_rejected'], 'Cap count')
        # This is reconstruction from saved outcomes, not an admission-policy rerun.
        replay = module.replay(jnp.asarray(work), jnp.asarray(admitted), jnp.asarray(executed))
        start, pre, remaining, load, served, substart, increments = [np.asarray(a) for a in replay]
        require(np.array_equal(remaining, recorded_end), 'Exact reconstructed workload endpoints')
        require(np.array_equal(load, recorded_load), 'Exact reconstructed task-count endpoints')
        argmin = substart.argmin(axis=2)
        require(np.array_equal(chosen[has_selected], argmin[has_selected]), 'Lowest-index minimum selection')
        positive = increments.sum(axis=2) > 0
        filled_before = np.cumsum(positive.astype(np.int32), axis=1) - positive
        require(np.array_equal(argmin, filled_before), 'First-unused-index derivation')
        ties = substart == substart.min(axis=2, keepdims=True)
        tie_count = ties.sum(axis=2)
        count_inc = np.stack([(admitted & (executed == r)).sum(axis=2) for r in range(9)], axis=2)
        initial_count = np.concatenate([np.zeros((1, 9), np.int32), recorded_load[:-1]], axis=0)
        subload = initial_count[:, None, :] + np.cumsum(count_inc, axis=1) - count_inc
        other_idle = ((substart == 0) & (subload < 6220)
                      & (np.arange(9) != argmin[..., None]))
        other_idle_count = other_idle.sum(axis=2)
        gate_counts = gate_rej.sum(axis=2)
        rejected_slots = gate_counts > 0
        all_unused_idle = np.all((substart[:, :, 5:] == 0) & (subload[:, :, 5:] == 0), axis=2)
        require(np.all(all_unused_idle), 'RSUs 5–8 idle at every substep')
        require(np.all(other_idle_count[rejected_slots] >= 4), 'Idle alternatives for rejected tasks')
        require(np.all(pre < 1000), 'Reconstructed workload clears within one second')
        require(np.all(start == 0) and np.all(recorded_end == 0), 'Empty batch boundaries')
        with np.load(SOURCE / 'cells' / f'seed_{seed}_per_task' / 'attempt_001/per_task.npz') as z:
            per_task_rsus = np.unique(z['task_execution_rsu'][z['task_v2i_admitted']]).tolist()
        counts = admitted.sum(axis=2)
        attempts = (selected >= 0).sum(axis=2)
        distinct_executed = np.stack([(admitted & (executed == r)).any(axis=(1, 2)) for r in range(9)], axis=1).sum(axis=1)
        per_draw = {
            'fleet_seed': seed, 'seconds': 10800, 'substeps': 54000,
            'observed_target_substeps': int(has_selected.sum()),
            'substeps_without_observable_v2i_target': int((~has_selected).sum()),
            'single_target_per_observed_substep': True,
            'lowest_index_argmin_mismatches': int((chosen[has_selected] != argmin[has_selected]).sum()),
            'target_differs_from_substep_index': int(((chosen != np.arange(5)) & has_selected).sum()),
            'target_matches_prior_positive_admission_substeps': True,
            'observed_selected_rsus': np.unique(selected[selected >= 0]).tolist(),
            'observed_execution_rsus': np.unique(executed[admitted]).tolist(),
            'per_task_control_execution_rsus': per_task_rsus,
            'observed_nonzero_end_workload_entries': int(np.count_nonzero(recorded_end)),
            'observed_nonzero_end_load_entries': int(np.count_nonzero(recorded_load)),
            'reconstructed_nonzero_start_workload_entries': int(np.count_nonzero(start)),
            'maximum_reconstructed_pre_drain_workload_ms': float(pre.max()),
            'minimum_unused_service_time_before_next_batch_ms': float(1000-pre.max()),
            'maximum_reconstructed_post_batch_tasks_per_rsu': int((initial_count + count_inc.sum(axis=1)).max()),
            'maximum_workload_endpoint_error_ms': float(np.max(np.abs(remaining-recorded_end))),
            'task_count_endpoint_exact': bool(np.array_equal(load, recorded_load)),
            'observed_tie_size_minimum': int(tie_count[has_selected].min()),
            'observed_tie_size_maximum': int(tie_count[has_selected].max()),
            'gate_rejected_tasks': int(gate_rej.sum()), 'capacity_rejected_tasks': int(cap_rej.sum()),
            'seconds_with_gate_rejection': int(rejected_slots.any(axis=1).sum()),
            'substeps_with_gate_rejection': int(rejected_slots.sum()),
            'gate_rejections_with_four_completely_unused_rsus_idle': int((gate_rej & all_unused_idle[..., None]).sum()),
            'minimum_other_idle_rsus_in_rejecting_substeps': int(other_idle_count[rejected_slots].min()),
            'maximum_other_idle_rsus_in_rejecting_substeps': int(other_idle_count[rejected_slots].max()),
            'per_second_execution_rsu_count_histogram': {str(i):int((distinct_executed == i).sum()) for i in range(6)},
        }
        draws.append(per_draw)
        for slot in range(5):
            substeps.append({'fleet_seed': seed, 'task_substep': slot,
                'observed_target_substeps': int(has_selected[:, slot].sum()),
                'no_observable_target_substeps': int((~has_selected[:, slot]).sum()),
                'v2i_attempts': int(attempts[:, slot].sum()), 'v2i_admitted': int(counts[:, slot].sum()),
                'gate_rejected': int(gate_counts[:, slot].sum()),
                'target_matches_slot_index': int(((chosen[:, slot] == slot) & has_selected[:, slot]).sum()),
                'target_below_slot_index': int(((chosen[:, slot] < slot) & has_selected[:, slot]).sum()),
                'min_tied_rsus': int(tie_count[:, slot][has_selected[:, slot]].min()),
                'max_reconstructed_post_slot_workload_ms': float((substart + increments)[:, slot].max())})
        # A deterministic example, selected by first recorded rejection, not effect size.
        t0, k0, vehicle = np.argwhere(gate_rej)[0]
        for slot in range(5):
            examples.append({'fleet_seed': seed, 'example_step': int(t0), 'trace_timestamp_s': float(times[t0]),
                'task_substep': slot, 'observed_target': int(chosen[t0, slot]),
                'argmin_from_reconstruction': int(argmin[t0, slot]),
                'workload_before_ms': substart[t0, slot].tolist(),
                'admitted_work_increment_ms': increments[t0, slot].tolist(),
                'admitted_tasks': int(counts[t0, slot]), 'gate_rejections': int(gate_counts[t0, slot]),
                'other_idle_rsus_with_capacity': np.flatnonzero(other_idle[t0, slot]).tolist()})
        for second in range(10800):
            row = {'fleet_seed':seed, 'step':second, 'trace_timestamp_s':float(times[second]),
                   'observed_end_max_workload_ms':float(recorded_end[second].max()),
                   'observed_end_max_load':int(recorded_load[second].max()),
                   'reconstructed_start_max_workload_ms':float(start[second].max()),
                   'reconstructed_pre_drain_max_workload_ms':float(pre[second].max()),
                   'distinct_execution_rsus':int(distinct_executed[second])}
            for slot in range(5):
                row.update({f'k{slot}_observed_target':int(chosen[second, slot]),
                            f'k{slot}_predicted_argmin':int(argmin[second, slot]),
                            f'k{slot}_tied_rsus':int(tie_count[second, slot]),
                            f'k{slot}_v2i_attempts':int(attempts[second, slot]),
                            f'k{slot}_v2i_admitted':int(counts[second, slot]),
                            f'k{slot}_gate_rejected':int(gate_counts[second, slot]),
                            f'k{slot}_other_idle_rsus':int(other_idle_count[second, slot])})
            seconds.append(row)
        print(json.dumps(per_draw), flush=True)
    after = {str(p): sha(p) for p in inputs}
    require(before == after, 'Inputs changed during read-only audit')
    result = {
        'status':'passed', 'analysis_standing':'post-hoc read-only mechanism audit',
        'new_simulation_runs':0, 'fleet_seeds':SEEDS, 'seconds_audited':43200,
        'task_substeps_audited':216000, 'original_inputs_unchanged':True,
        'source_commit':manifest['code_commit'], 'audit_script_sha256':sha(Path(__file__)),
        'original_input_sha256':before, 'draws':draws,
        'gate_rejected_tasks_across_draws':sum(d['gate_rejected_tasks'] for d in draws),
        'all_rejections_had_at_least_four_other_idle_rsus':True,
        'available_task_fields':field_names_task, 'available_step_fields':field_names_step,
        'not_directly_recorded':[
            'common-target substep-start and pre-drain workload (reconstructed from recorded admissions and bound service reference)',
            'argmin calls in substeps with no V2I attempts (inferred only; stored target remains -1)',
            'candidate-level admission working offsets and intermediate three-pass admission masks',
            'separate operational radio viability values; unavailable outcomes cannot independently reconstruct radio samples',
            'outcomes under a changed tie-break, persistent queues, or alternative dispatch; no such counterfactual was run'],
    }
    (OUT/'audit_results.json').write_text(json.dumps(result,indent=2)+'\n')
    write_csv(OUT/'per_substep_summary.csv',substeps)
    write_csv(OUT/'per_second_targets.csv.gz',seconds)
    (OUT/'worked_examples.json').write_text(json.dumps(examples,indent=2)+'\n')
    print(json.dumps({'status':'passed','seconds':len(seconds),'gate_rejections':result['gate_rejected_tasks_across_draws']}))


if __name__ == '__main__':
    main()
