#!/usr/bin/env python3
"""Independent, read-only raw audit of explicit completed second-actor blocks.

No evaluator or campaign module imports. An absent/unpassed requested BLOCK
receipt returns exit 2 before any raw arrays, cell outcomes or baseline counts
are opened. All requested blocks must be complete before the audit starts.
Only the audit receipt named by --output is written, using exclusive creation.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

RAW = Path('/Users/akashx/Downloads/diss_mat/traffictwin-followups-raw-2026-09-15')
CHECKOUT = Path('/Users/akashx/scratch/traffictwin-followups-guarded-2026-09-15')
EVIDENCE = CHECKOUT / 'docs/dissertation/followups_2026-09-15/evidence'
STUDY = '09_second_actor'
SOURCE = '5cbe568c9260c432f3e3ae42b45dcfba7f1a8dbe'
SEAL_HASH = '4ef9c00fd2211703e09a1a0b4ddb1b6ebffc724d27d0bb4604cb3a408d949d65'
BASELINE_HASH = '37a7f1d8aa628f2e74b98855ae8f7e461bc31d7bde6efd7989075d4038c1d482'
ORIGINAL_ACTOR = '93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208'
SECOND_ACTOR = 'b3eca1685245c59d1a3e86bd11ede887300bda1b00ba211a1913e467ad3f5183'
TRACE_HASH = '896aa5ad646d0d6c643de49eaa84373c9442b2d58483ac0e39aab76619c29628'
ARMS = ['ingress_dla', 'dla', 'per_task_dla', 'causal_round_robin']
STEP_SHARED = ['times', 'slot_tier', 'slot_is_ev', 'slot_soc_initial', 'slot_tx_power_w',
               'exogenous_keys', 'observation_task_type', 'observation_task_size', 'veh_k']
TASK_SHARED = ['task_active', 'task_type', 'task_sizes_mb', 'task_rsu_service_ms', 'task_local_service_ms']


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(4 << 20), b''):
            h.update(data)
    return h.hexdigest()


def need(condition, message):
    if not bool(condition):
        raise ValueError(message)


def run(blocks, output):
    started = time.monotonic()
    need(len(set(blocks)) == len(blocks) and all(0 <= b < 8 for b in blocks), 'Invalid block selection')
    # Refuse partial data before importing NumPy or opening any outcome/count data.
    block_records = {}
    incomplete = []
    for block in blocks:
        path = RAW / STUDY / f'BLOCK_{block:02d}.json'
        if not path.is_file():
            incomplete.append({'block': block, 'reason': 'missing completion receipt', 'path': str(path)})
            continue
        record = read(path)
        if not (record.get('status') == 'passed' and record.get('study') == STUDY
                and record.get('block') == block and record.get('seal_sha256') == SEAL_HASH
                and set(record.get('cell_receipts', {})) == set(ARMS)):
            incomplete.append({'block': block, 'reason': 'invalid/unpassed completion receipt', 'path': str(path)})
        else:
            block_records[block] = record
    if incomplete:
        return 2, {'status': 'not_ready', 'requested_blocks': blocks, 'incomplete': incomplete,
                   'outcomes_read': False, 'raw_arrays_opened': False, 'audit_receipt_written': False}
    need(not output.exists(), 'Refusing to overwrite an existing audit receipt')

    import numpy as np

    def ah(array):
        array = np.ascontiguousarray(array)
        h = hashlib.sha256(str((array.shape, array.dtype.str)).encode())
        h.update(memoryview(array))
        return h.hexdigest()

    need(sha(EVIDENCE / 'EXECUTION_SEAL.json') == SEAL_HASH, 'Changed execution seal')
    seal = read(EVIDENCE / 'EXECUTION_SEAL.json')
    need(seal['source_commit'] == SOURCE, 'Source identity')
    for path, digest in seal['sources'].items():
        need(sha(path) == digest, 'Source changed: ' + path)
    need(sha(EVIDENCE / 'BASELINE.json') == BASELINE_HASH == seal['baseline_ledger_sha256'], 'Baseline ledger identity')
    baseline = read(EVIDENCE / 'BASELINE.json')['records']
    rows, block_bindings, inputs_verified = [], {}, set()
    all_shared = {'step/' + n for n in STEP_SHARED} | {'task/' + n for n in TASK_SHARED}
    for block in blocks:
        br = block_records[block]
        bp = RAW / STUDY / f'BLOCK_{block:02d}.json'
        block_bindings[str(bp)] = sha(bp)
        for arm in ARMS:
            dest = RAW / STUDY / f'block_{block:02d}_{arm}' / 'attempt_001'
            vp = dest / 'VALIDATED.json'
            rec, cfg, summary = read(vp), read(dest / 'COMMAND.json'), read(dest / 'summary.json')
            old = baseline[f'{block}:{arm}']
            oldcfg, olddest = old['configuration'], Path(old['configuration']['output'])
            need(sha(vp) == br['cell_receipts'][arm], 'Cell receipt hash')
            need(rec['status'] == 'passed' and rec['configuration'] == cfg
                 and rec['seal_sha256'] == cfg['seal_sha256'] == SEAL_HASH, 'Cell configuration/seal')
            need(read(dest / 'STARTED.json')['seal_sha256'] == SEAL_HASH, 'Launch seal')
            need(list(dest.parent.glob('attempt_*')) == [dest] and not (dest / 'FAILED.json').exists(), 'Unexpected/failed attempt')
            for field, value in {'study': STUDY, 'block': block, 'arm': arm, 'steps': 10800,
                                 'fleet_seed': 100 + block, 'evaluator_seed': 200 + block, 'service_mult': 1.,
                                 'actor_id': 'ukfleet', 'output': str(dest), 'frozen_reference': False}.items():
                need(cfg[field] == value, 'Config: ' + field)
            need(cfg['inputs']['actor_sha256'] == SECOND_ACTOR
                 and oldcfg['inputs']['actor_sha256'] == ORIGINAL_ACTOR
                 and cfg['inputs']['trace_sha256'] == oldcfg['inputs']['trace_sha256'] == TRACE_HASH
                 and cfg['inputs']['trace'] == oldcfg['inputs']['trace'], 'Actor/trace identity')
            for label in ['actor', 'trace']:
                pair = cfg['inputs'][label], cfg['inputs'][label + '_sha256']
                if pair not in inputs_verified:
                    need(sha(pair[0]) == pair[1], 'Actual input-file digest: ' + label)
                    inputs_verified.add(pair)
            need(cfg['environment'] == oldcfg['environment'], 'Numerical environment changed')
            for flag, value in {'--actor': cfg['inputs']['actor'], '--trace': cfg['inputs']['trace'],
                                '--max-steps': '10800', '--seed': str(200 + block), '--fleet-seed': str(100 + block),
                                '--rsu-lb': arm, '--rsu-service-mult': '1.0'}.items():
                need(cfg['command'][cfg['command'].index(flag) + 1] == value, 'Command flag: ' + flag)
            need(summary['actor'] == Path(cfg['inputs']['actor']).name, 'Summary actor name')
            for category in ['within_condition', 'historical_matching']:
                match = br[category][arm]
                need(match['status'] == 'passed' and match['exogenous_inputs'] == 'matched'
                     and match['actions_forced'] is False, 'Block matching receipt')
            need(set(rec['output_sha256']) == {'summary.json', 'per_step.npz', 'per_task.npz'}, 'Output hash set')
            for filename, digest in rec['output_sha256'].items():
                need(sha(dest / filename) == digest, 'New output hash: ' + filename)
            for field, value in {'T': 10800, 'maxN': 215, 'k_max': 5, 'n_rsus': 9, 'rsu_lb': arm,
                                 'rsu_service_mult': 1., 'rsu_max_concurrent': 6220, 'fleet_seed': 100 + block,
                                 'evaluator_seed': 200 + block, 'fleet': 'uk2030', 'lambda_arrival': 1.5,
                                 'rsu_backhaul_ms': 0., 'k8s_scale': 'off', 'enter_reset': True,
                                 'reset_soc_on_enter': False, 'substep_queue': 'sequential',
                                 'substep_queue_iterations': 3, 'veh_queue_mode': 'conserved'}.items():
                need(summary[field] == value, 'Summary control: ' + field)
            need(set(rec['shared_input_hashes']) == set(old['shared_input_hashes']) == all_shared, 'Shared-field contract')
            need(rec['shared_input_hashes'] == old['shared_input_hashes'], 'Matched exogenous hashes')
            with np.load(dest / 'per_task.npz', allow_pickle=False) as newtask:
                active, met, admitted = newtask['task_active'], newtask['task_met'], newtask['task_final_admitted']
                outcome, latency, types = newtask['task_outcome'], newtask['task_lat_ms'], newtask['task_type']
                need(active.shape == met.shape == admitted.shape == outcome.shape == latency.shape == types.shape
                     == (10800, 5, 215), 'Full task-array horizon')
                need(active.dtype == met.dtype == admitted.dtype == np.dtype(bool), 'Count-mask dtypes')
                need(np.all((types >= 0) & (types < 3)) and np.all(np.isfinite(latency)), 'Types/latency domain')
                deadlines = np.array([100, 500, 100], np.float32)[types]
                deadline_met = active & (latency <= deadlines)
                final_admission = active & np.isin(outcome, [1, 2])
                need(np.array_equal(deadline_met, met) and np.array_equal(met, active & (outcome == 1)), 'Inclusive deadline accounting')
                need(np.array_equal(final_admission, admitted) and not np.any(met & ~admitted), 'Final admission accounting')
                need(np.all(latency[active & ~admitted] == (10 * deadlines)[active & ~admitted]), 'Rejected-task latency penalty')
                offered, admitted_count, successes = int(active.sum()), int(final_admission.sum()), int(deadline_met.sum())
                need((offered, admitted_count, successes) == (rec['offered'], rec['admitted'], rec['successes']), 'Raw counts vs receipt')
                need(summary['n_offered'] == summary['total_tasks'] == offered
                     and summary['n_admitted'] == admitted_count, 'Raw counts vs summary')
                need(abs(summary['completion'] * offered - successes) < 1e-6
                     and abs(summary['completion_admitted'] * max(admitted_count, 1) - successes) < 1e-6, 'Summary success numerator')
                categories = np.bincount(outcome[active], minlength=9).tolist()
                need(categories == rec['outcome_counts'] and sum(categories) == offered
                     and offered - admitted_count == rec['terminal_failures'], 'Terminal count conservation')
                with np.load(olddest / 'per_task.npz', allow_pickle=False) as oldtask:
                    for field in TASK_SHARED:
                        before, after = oldtask[field], newtask[field]
                        need(ah(before) == old['shared_input_hashes']['task/' + field]
                             and ah(after) == rec['shared_input_hashes']['task/' + field], 'Task array identity: ' + field)
                        need(before.dtype == after.dtype and np.array_equal(after, before), 'Direct task-array equality: ' + field)
                with np.load(dest / 'per_step.npz', allow_pickle=False) as newstep:
                    need(newstep['times'].shape == (10800,) and np.all(np.diff(newstep['times']) == 1), 'Full time horizon')
                    arrivals = newstep['veh_k']
                    need(np.array_equal(active, np.arange(5)[None, :, None] < arrivals[:, None, :]), 'Offered mask/count')
                    need(np.array_equal(active.sum(axis=(1, 2)), newstep['arrivals'])
                         and np.array_equal(deadline_met.sum(axis=(1, 2)), newstep['done']), 'Per-step counts')
                    with np.load(olddest / 'per_step.npz', allow_pickle=False) as oldstep:
                        for field in STEP_SHARED:
                            before, after = oldstep[field], newstep[field]
                            need(ah(before) == old['shared_input_hashes']['step/' + field]
                                 and ah(after) == rec['shared_input_hashes']['step/' + field], 'Step array identity: ' + field)
                            need(before.dtype == after.dtype and np.array_equal(after, before), 'Direct step-array equality: ' + field)
                        before, after = oldstep['veh_action'], newstep['veh_action']
                        need(before.shape == after.shape == (10800, 215)
                             and before.dtype == after.dtype
                             and np.all((before >= 0) & (before <= 2))
                             and np.all((after >= 0) & (after <= 2)), 'Vehicle-action domain')
                        changed = before != after
                        changed_count = int(np.count_nonzero(changed))
                        changed_with_offers = int(np.count_nonzero(changed & (arrivals > 0)))
                        offered_tasks_with_changed_mode = int(arrivals[changed].sum())
                        recorded_change = br['historical_matching'][arm]['endogenous_differences']['veh_action']
                        need(recorded_change['changed_values'] == changed_count
                             and recorded_change['identical'] == (changed_count == 0), 'Recorded action-difference count')
            row = {'block': block, 'fleet_seed': 100 + block, 'evaluator_seed': 200 + block, 'arm': arm,
                   'steps': 10800, 'offered': offered, 'admitted': admitted_count, 'successes': successes,
                   'receipt_path': str(vp), 'receipt_sha256': sha(vp), 'output_sha256': rec['output_sha256'],
                   'actor_sha256': SECOND_ACTOR, 'historical_actor_sha256': ORIGINAL_ACTOR,
                   'rsu_service': 'raw arrays exactly unchanged', 'local_service': 'raw arrays exactly unchanged',
                   'shared_exogenous_fields_directly_equal': 14, 'action_equality_required': False,
                   'changed_vehicle_seconds_all_slots': changed_count,
                   'changed_vehicle_seconds_with_offered_tasks': changed_with_offers,
                   'offered_tasks_with_changed_vehicle_mode': offered_tasks_with_changed_mode}
            rows.append(row)
            print(json.dumps({'validated': {k: row[k] for k in ['block', 'arm', 'offered', 'admitted', 'successes',
                                                               'changed_vehicle_seconds_all_slots']}}), flush=True)
    result = {'status': 'passed', 'audit': 'independent completed second-actor raw-data audit',
              'source_commit': SOURCE, 'execution_seal_sha256': SEAL_HASH, 'baseline_ledger_sha256': BASELINE_HASH,
              'blocks': blocks, 'full_cells_validated': len(rows), 'valid_blocks': len(blocks), 'steps_per_cell': 10800,
              'new_actor_sha256': SECOND_ACTOR, 'historical_actor_sha256': ORIGINAL_ACTOR,
              'matched_fields_directly_compared': {'step': STEP_SHARED, 'task': TASK_SHARED},
              'new_receipts': rows, 'block_receipt_sha256': block_bindings,
              'action_equality_required_within_or_between_arms': False,
              'hypothesis_contrasts_calculated': False, 'scientific_workloads_launched': 0,
              'elapsed_s': time.monotonic() - started}
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return 0, {'status': result['status'], 'full_cells_validated': len(rows), 'valid_blocks': len(blocks),
               'receipt': str(output), 'receipt_sha256': sha(output), 'elapsed_s': result['elapsed_s']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blocks', type=int, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        code, result = run(args.blocks, args.output)
    except Exception as exc:
        code, result = 1, {'status': 'failed', 'error': type(exc).__name__ + ': ' + str(exc)}
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(code)
