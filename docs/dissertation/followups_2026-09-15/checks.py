"""Additional condition and native-two-choice checks; no evaluator import."""
import json
from pathlib import Path

import numpy as np

from validation import ah, need, sha, validate_cell


def validate(dest, config):
    rec = validate_cell(dest, config)
    summary = json.loads((Path(dest) / 'summary.json').read_text())
    need(Path(summary['actor']).name == Path(config['inputs']['actor']).name,
         'Actor summary identity mismatch')
    need(sha(config['inputs']['actor']) == config['inputs']['actor_sha256'],
         'Actor input changed')
    with np.load(Path(dest) / 'per_task.npz', allow_pickle=False) as z:
        rec['shared_input_hashes']['task/task_local_service_ms'] = ah(z['task_local_service_ms'])
    if config['arm'] == 'dla_p2c':
        rec['two_choice_replay'] = replay_p2c(dest)
    return rec


def replay_p2c(dest):
    # Use only the pinned PRNG library. Selection/accounting below is NumPy.
    import jax
    import jax.numpy as jnp

    need(jax.__version__ == '0.4.30', 'P2C replay requires pinned JAX')
    with np.load(Path(dest) / 'per_step.npz', allow_pickle=False) as z:
        keys = z['exogenous_keys'][:, 1]
        busy = z['rsu_start_busy_ms'].copy()
        finish = z['rsu_pre_drain_busy_ms']
        actions = z['veh_action']
    with np.load(Path(dest) / 'per_task.npz', allow_pickle=False) as z:
        active = z['task_active']
        proposals = z['task_selected_execution_rsu']
        admitted = z['task_v2i_admitted']
        work = z['task_rsu_service_ms']

    def pair(key):
        a, b = jax.random.split(jax.random.fold_in(key, 97))
        return (jax.random.randint(a, (215,), 0, 9),
                jax.random.randint(b, (215,), 0, 9))

    @jax.jit
    def candidates(batch):
        return jax.vmap(lambda key: jax.vmap(pair)(jax.random.split(key, 5)))(batch)

    first, second = [], []
    for start in range(0, len(keys), 256):
        a, b = candidates(jnp.asarray(keys[start:start + 256]))
        first.append(np.asarray(a)); second.append(np.asarray(b))
    c1, c2 = np.concatenate(first), np.concatenate(second)
    ti = np.arange(len(keys))[:, None]
    checked = 0
    for k in range(5):
        expected = np.where(busy[ti, c1[:, k]] <= busy[ti, c2[:, k]], c1[:, k], c2[:, k])
        attempt = active[:, k] & (actions == 1)
        need(np.array_equal(expected[attempt], proposals[:, k][attempt]),
             f'P2C proposal replay mismatch at substep {k}')
        increment = np.zeros_like(busy)
        np.add.at(increment, (ti, expected), np.where(admitted[:, k], work[:, k], np.float32(0)))
        busy = busy + increment
        checked += int(attempt.sum())
    need(np.array_equal(busy, finish), 'P2C substep workload replay mismatch')
    return {'status': 'passed', 'checked_proposals': checked,
            'candidate_sampling': 'with replacement; first candidate wins ties',
            'reconstructed_final_backlog': 'exact float32'}


def matched(reference, current, half_speed=False):
    """Compare immutable validated records, allowing endogenous state changes."""
    a, b = reference['shared_input_hashes'], current['shared_input_hashes']
    ignored = {'task/task_rsu_service_ms'} if half_speed else set()
    need(set(a) == set(b), 'Shared-input field set differs')
    need(all(a[k] == b[k] for k in a if k not in ignored), 'Matched exogenous inputs differ')
    activation = None
    if half_speed:
        with np.load(Path(reference['configuration']['output']) / 'per_task.npz', allow_pickle=False) as z:
            original = z['task_rsu_service_ms']
        with np.load(Path(current['configuration']['output']) / 'per_task.npz', allow_pickle=False) as z:
            changed = z['task_rsu_service_ms']
        need(np.array_equal(changed * np.float32(.5), original), 'Half-speed service activation mismatch')
        activation = {'rsu_work': 'exactly doubled', 'local_work': 'unchanged'}
    fields = ['veh_action', 'veh_actor_logits', 'veh_observations']
    differences = {}
    with np.load(Path(reference['configuration']['output']) / 'per_step.npz', allow_pickle=False) as x:
        with np.load(Path(current['configuration']['output']) / 'per_step.npz', allow_pickle=False) as y:
            for field in fields:
                aa, bb = x[field], y[field]
                differences[field] = {'identical': bool(np.array_equal(aa, bb)),
                                      'changed_values': int(np.count_nonzero(aa != bb)),
                                      'max_absolute_difference': float(np.max(np.abs(aa.astype(float) - bb)))}
    return {'status': 'passed', 'exogenous_inputs': 'matched',
            'service_activation': activation, 'endogenous_differences': differences,
            'actions_forced': False}
