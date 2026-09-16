"""Read-only trace inventory; never runs SUMO or the VEC evaluator."""
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = Path('/Users/akashx/Downloads/diss_mat')
VEC = DATA / 'vec_env-state-delay-run'
TOS = DATA / 'tos-data-full'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def array_sha(a):
    a = np.ascontiguousarray(a)
    h = hashlib.sha256(str((a.shape, a.dtype.str)).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-C', str(VEC), *args])


def inspect(path):
    with np.load(path, allow_pickle=False) as z:
        mask = z['mask']
        t, n = mask.shape
        entry = z['enter'] if 'enter' in z.files else None
        assert z['pos_x'].shape == z['pos_y'].shape == (t, n)
        assert int(z['T']) == t and int(z['maxN']) == n
        assert mask.dtype == bool
        assert entry is None or (entry.shape == mask.shape and entry.dtype == bool)
        assert entry is None or not np.any(entry & ~mask)
        assert np.all(np.diff(z['times']) == 1)
        fields = {k: {'shape': list(z[k].shape), 'dtype': str(z[k].dtype),
                      'array_sha256': array_sha(z[k])} for k in z.files}
        return {
            'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size,
            'T': t, 'N': n, 'R': int(z['rsu_xy'].shape[0]),
            'entry_channel_present': entry is not None,
            'entry_channel': 'enter' if entry is not None else None,
            'entry_events': int(entry.sum()) if entry is not None else None,
            'queue_convention': 'per-visit entry reset' if entry is not None else 'legacy mask-only reset',
            'embedded_window': str(z['window'].item()),
            'embedded_sumo_seed': int(z['sumo_seed']),
            'first_time': float(z['times'][0]), 'last_time': float(z['times'][-1]),
            'dt': float(z['dt']), 'vehicle_seconds': int(mask.sum()),
            'mean_active_vehicles_per_second': float(mask.sum() / t),
            'peak_active_vehicles': int(mask.sum(axis=1).max()), 'fields': fields,
        }


def compare(left, right):
    result = {'left': str(left), 'right': str(right),
              'file_sha256_equal': sha(left) == sha(right), 'fields': {}}
    with np.load(left, allow_pickle=False) as a, np.load(right, allow_pickle=False) as b:
        result['only_left'] = sorted(set(a.files) - set(b.files))
        result['only_right'] = sorted(set(b.files) - set(a.files))
        for field in sorted(set(a.files) & set(b.files)):
            x, y = a[field], b[field]
            same_shape, same_dtype = x.shape == y.shape, x.dtype == y.dtype
            equal = same_shape and same_dtype and np.array_equal(x, y)
            record = {'equal': bool(equal), 'same_shape': same_shape, 'same_dtype': same_dtype}
            if same_shape and not equal:
                record['changed_elements'] = int(np.count_nonzero(x != y))
                if np.issubdtype(x.dtype, np.number) and np.issubdtype(y.dtype, np.number):
                    record['max_absolute_difference'] = float(np.abs(x.astype(float) - y.astype(float)).max())
                record['first_differing_indices'] = np.argwhere(x != y)[:10].tolist()
            result['fields'][field] = record
        result['all_common_arrays_equal'] = all(x['equal'] for x in result['fields'].values())
        result['array_level_equal'] = (result['all_common_arrays_equal']
                                       and not result['only_left'] and not result['only_right'])
    return result


def main():
    candidates = sorted(p for p in (VEC / 'eval/data').glob('*/trace_*.npz')
                        if p.name.endswith(('_wdrsu.npz', '_fullrsu.npz')))
    candidates += sorted((TOS / 'traces').glob('trace_*_fullrsu.npz'))
    records = [inspect(p) for p in candidates]
    remote_head = git('rev-parse', 'github/main').decode().strip()
    remote_files = git('ls-tree', '-r', '--name-only', remote_head, 'eval/data').decode().splitlines()
    remote_files = [p for p in remote_files if Path(p).name.startswith('trace_')
                    and p.endswith(('_wdrsu.npz', '_fullrsu.npz'))]
    remote = []
    for relative in remote_files:
        blob = git('show', f'{remote_head}:{relative}')
        digest = hashlib.sha256(blob).hexdigest()
        path = VEC / relative
        assert path in candidates and sha(path) == digest
        remote.append({'git_path': relative, 'blob_sha256': digest,
                       'local_path': str(path), 'local_file_identical': True})
    chosen = {}
    dates = {'we': ('2024-09-15', '12:00–21:00', 32400),
             'wd_pm': ('2024-10-15', '14:00–21:00', 25200),
             'ev': ('2024-09-18', '17:30–24:00', 23400)}
    for key, (date, window, steps) in dates.items():
        options = [r for r in records if Path(r['path']).name in
                   [f'trace_{key}_wdrsu.npz', f'trace_{key}_fullrsu.npz']]
        def rank(r):
            if r['entry_channel_present']:
                return 1 if r['path'].endswith('_wdrsu.npz') else 2
            return 3 if r['path'].endswith('_fullrsu.npz') else 4
        options.sort(key=lambda r: (rank(r), r['path']))
        pick = options[0]
        assert rank(pick) <= 3 and pick['T'] == steps
        chosen[key] = {k: v for k, v in pick.items() if k != 'fields'}
        chosen[key].update(preference_rank=rank(pick), source_date=date, local_window=window)
    morning = compare(TOS / 'traces/trace_wd_am_fullrsu.npz',
                      VEC / 'eval/data/manchester_workingday/trace_wd_am_wdrsu.npz')
    output = {
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status': 'inventory_complete_no_evaluator_runs', 'candidate_count': len(records),
        'vec_origin_main_cached_head': git('rev-parse', 'origin/main').decode().strip(),
        'vec_github_main_fetched_head': remote_head,
        'remote_main_candidates': remote, 'candidates': records, 'selected': chosen,
        'morning_identity': morning,
        'provenance_documents': {str(p): sha(p) for p in
                                 [VEC / 'eval/data/README.md', TOS / 'traces/PROVENANCE.md']},
        'trace_files_modified': False, 'morning_rerun': False,
    }
    with (HERE / 'TRACE_INVENTORY.json').open('x') as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'candidate_count': len(records), 'selected': chosen,
                      'morning_identity': morning}, indent=2))


if __name__ == '__main__':
    main()
