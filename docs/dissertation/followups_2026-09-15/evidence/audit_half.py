#!/usr/bin/env python3
"""Read-only audit of explicitly selected completed half-speed blocks."""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

RAW = Path('/Users/akashx/Downloads/diss_mat/traffictwin-followups-raw-2026-09-15')
CHECKOUT = Path('/Users/akashx/scratch/traffictwin-followups-guarded-2026-09-15')
EVIDENCE = CHECKOUT / 'docs/dissertation/followups_2026-09-15/evidence'
SOURCE = '5cbe568c9260c432f3e3ae42b45dcfba7f1a8dbe'
SEAL_HASH = '4ef9c00fd2211703e09a1a0b4ddb1b6ebffc724d27d0bb4604cb3a408d949d65'
BASELINE_HASH = '37a7f1d8aa628f2e74b98855ae8f7e461bc31d7bde6efd7989075d4038c1d482'
ARMS = ['ingress_dla', 'dla', 'per_task_dla', 'causal_round_robin']


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(4 << 20), b''):
            h.update(data)
    return h.hexdigest()


def array_hash(array):
    array = np.ascontiguousarray(array)
    h = hashlib.sha256(str((array.shape, array.dtype.str)).encode())
    h.update(memoryview(array))
    return h.hexdigest()


def need(ok, message):
    if not bool(ok):
        raise ValueError(message)


def run(blocks):
    started = time.monotonic()
    need(len(set(blocks)) == len(blocks) and all(0 <= b < 8 for b in blocks), 'Invalid block selection')
    need(sha(EVIDENCE / 'EXECUTION_SEAL.json') == SEAL_HASH, 'Changed execution seal')
    seal = read(EVIDENCE / 'EXECUTION_SEAL.json')
    need(seal['source_commit'] == SOURCE, 'Source identity')
    for path, digest in seal['sources'].items():
        need(sha(path) == digest, 'Source changed: ' + path)
    need(sha(EVIDENCE / 'BASELINE.json') == BASELINE_HASH == seal['baseline_ledger_sha256'], 'Changed baseline ledger')
    baseline = read(EVIDENCE / 'BASELINE.json')['records']
    # Require every requested block to be closed before inspecting its outcomes.
    for b in blocks:
        path = RAW / '08_half_speed' / f'BLOCK_{b:02d}.json'
        need(path.is_file() and read(path)['status'] == 'passed', 'Requested block is not complete')
    rows, block_bindings = [], {}
    for b in blocks:
        bp = RAW / '08_half_speed' / f'BLOCK_{b:02d}.json'
        br = read(bp)
        need(br['study'] == '08_half_speed' and br['block'] == b and br['seal_sha256'] == SEAL_HASH
             and set(br['cell_receipts']) == set(ARMS), 'Block identity/binding')
        block_bindings[str(bp)] = sha(bp)
        for arm in ARMS:
            dest = RAW / '08_half_speed' / f'block_{b:02d}_{arm}' / 'attempt_001'
            vp = dest / 'VALIDATED.json'
            rec, cfg, summary = read(vp), read(dest / 'COMMAND.json'), read(dest / 'summary.json')
            old = baseline[f'{b}:{arm}']
            olddest = Path(old['configuration']['output'])
            need(sha(vp) == br['cell_receipts'][arm], 'Cell receipt hash')
            need(rec['status'] == 'passed' and rec['configuration'] == cfg
                 and rec['seal_sha256'] == cfg['seal_sha256'] == SEAL_HASH, 'Cell configuration/seal')
            need(read(dest / 'STARTED.json')['seal_sha256'] == SEAL_HASH, 'Launch seal')
            need(list(dest.parent.glob('attempt_*')) == [dest] and not (dest / 'FAILED.json').exists(), 'Unexpected/failed attempt')
            for field, value in {'study': '08_half_speed', 'block': b, 'arm': arm, 'steps': 10800,
                                 'fleet_seed': 100 + b, 'evaluator_seed': 200 + b, 'service_mult': .5,
                                 'actor_id': 'original', 'output': str(dest)}.items():
                need(cfg[field] == value, 'Config: ' + field)
            need(cfg['inputs'] == old['configuration']['inputs'], 'Input file identities')
            need(cfg['environment']['VEC_JAX_RSU_SERVICE_MULT'] == '0.5', 'Service environment')
            need(cfg['command'][cfg['command'].index('--rsu-service-mult') + 1] == '0.5', 'Service command flag')
            for category in ['within_condition', 'historical_matching']:
                match = br[category][arm]
                need(match['status'] == 'passed' and match['exogenous_inputs'] == 'matched'
                     and match['actions_forced'] is False, 'Block matching receipt')
            need(br['historical_matching'][arm]['service_activation'] ==
                 {'rsu_work': 'exactly doubled', 'local_work': 'unchanged'}, 'Service activation receipt')
            for filename, digest in rec['output_sha256'].items():
                need(sha(dest / filename) == digest, 'New output hash: ' + filename)
            for field, value in {'T': 10800, 'maxN': 215, 'k_max': 5, 'n_rsus': 9, 'rsu_lb': arm,
                                 'rsu_service_mult': .5, 'rsu_max_concurrent': 6220, 'fleet_seed': 100 + b,
                                 'evaluator_seed': 200 + b, 'fleet': 'uk2030', 'lambda_arrival': 1.5,
                                 'rsu_backhaul_ms': 0., 'k8s_scale': 'off', 'enter_reset': True,
                                 'reset_soc_on_enter': False, 'substep_queue': 'sequential',
                                 'substep_queue_iterations': 3, 'veh_queue_mode': 'conserved'}.items():
                need(summary[field] == value, 'Summary control: ' + field)
            with np.load(dest / 'per_task.npz', allow_pickle=False) as z:
                active, met, admitted = z['task_active'], z['task_met'], z['task_final_admitted']
                outcome, latency, types = z['task_outcome'], z['task_lat_ms'], z['task_type']
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
                     and abs(summary['completion_admitted'] * admitted_count - successes) < 1e-6, 'Summary success numerator')
                categories = np.bincount(outcome[active], minlength=9).tolist()
                need(categories == rec['outcome_counts'] and sum(categories) == offered
                     and offered - admitted_count == rec['terminal_failures'], 'Terminal count conservation')
                # Hash each recorded shared field directly from the new raw arrays.
                for name, digest in rec['shared_input_hashes'].items():
                    if name.startswith('task/'):
                        need(array_hash(z[name.split('/')[1]]) == digest, 'New raw shared field ' + name)
                with np.load(olddest / 'per_task.npz', allow_pickle=False) as hist:
                    for name in ['task_rsu_service_ms', 'task_local_service_ms']:
                        before, after = hist[name], z[name]
                        need(array_hash(before) == old['shared_input_hashes']['task/' + name], 'Historical service-array identity')
                        need(before.shape == after.shape == (10800, 5, 215)
                             and before.dtype == after.dtype == np.float32, 'Service-array shape/type')
                        if name == 'task_rsu_service_ms':
                            need(np.array_equal(after * np.float32(.5), before), 'RSU service was not exactly doubled')
                        else:
                            need(np.array_equal(after, before), 'Local service changed')
                with np.load(dest / 'per_step.npz', allow_pickle=False) as step:
                    need(step['times'].shape == (10800,) and np.all(np.diff(step['times']) == 1), 'Full time horizon')
                    need(np.array_equal(active, np.arange(5)[None, :, None] < step['veh_k'][:, None, :]), 'Offered mask/count')
                    need(np.array_equal(active.sum(axis=(1, 2)), step['arrivals'])
                         and np.array_equal(deadline_met.sum(axis=(1, 2)), step['done']), 'Per-step counts')
                    for name, digest in rec['shared_input_hashes'].items():
                        if name.startswith('step/'):
                            need(array_hash(step[name.split('/')[1]]) == digest, 'New raw shared field ' + name)
            current, historical = rec['shared_input_hashes'], old['shared_input_hashes']
            need(set(current) == set(historical), 'Shared-input field set')
            for name in historical:
                if name != 'task/task_rsu_service_ms':
                    need(current[name] == historical[name], 'Historical matching hash: ' + name)
            base_arm = read(RAW / '08_half_speed' / f'block_{b:02d}_ingress_dla' / 'attempt_001' / 'VALIDATED.json')
            need(current == base_arm['shared_input_hashes'], 'Within-block exogenous equality')
            row = {'block': b, 'fleet_seed': 100 + b, 'evaluator_seed': 200 + b, 'arm': arm,
                   'steps': 10800, 'offered': offered, 'admitted': admitted_count, 'successes': successes,
                   'receipt_path': str(vp), 'receipt_sha256': sha(vp), 'output_sha256': rec['output_sha256'],
                   'rsu_service_activation': 'exactly doubled in raw float32 arrays',
                   'local_service': 'raw arrays exactly unchanged', 'shared_input_fields_checked': len(current)}
            rows.append(row)
            print(json.dumps({'validated': {k: row[k] for k in ['block', 'arm', 'offered', 'admitted', 'successes']}}), flush=True)
    return {'status': 'passed', 'audit': 'independent completed half-speed raw-data audit',
            'source_commit': SOURCE, 'execution_seal_sha256': SEAL_HASH, 'baseline_ledger_sha256': BASELINE_HASH,
            'blocks': blocks, 'full_cells_validated': len(rows), 'valid_blocks': len(blocks), 'steps_per_cell': 10800,
            'historical_raw_fields_reopened': ['task_rsu_service_ms', 'task_local_service_ms'],
            'new_receipts': rows, 'block_receipt_sha256': block_bindings, 'hypothesis_contrasts_calculated': False,
            'scientific_workloads_launched': 0, 'elapsed_s': time.monotonic() - started}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blocks', type=int, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.blocks)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'full_cells_validated': result['full_cells_validated'],
                      'valid_blocks': result['valid_blocks'], 'receipt': str(args.output),
                      'receipt_sha256': sha(args.output), 'elapsed_s': result['elapsed_s']}), flush=True)
