"""Sealed, serial execution of the owner's three additive follow-up studies."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

from checks import matched, validate
from validation import ARMS, FILES, need, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = HERE.parent / 'joint_confirmation_2026-09-08'
PYTHON = Path('/Users/akashx/Downloads/diss_mat/vec_env-state-delay/.venv/bin/python')
RUNTIME = Path('/Users/akashx/Downloads/diss_mat/vec_env-state-delay-run')
TRACE = RUNTIME / 'eval/data/manchester_workingday/trace_wd_am_wdrsu.npz'
ACTORDIR = Path('/Users/akashx/Downloads/diss_mat/tos-data-full/checkpoints')
ACTORS = {
    'original': ACTORDIR / 'mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz',
    'ukfleet': ACTORDIR / 'mappo_modelc_17dim_ukfleet2030__envs128__lr3e-3__seed100_actor_params.npz',
}
ACTOR_HASHES = {
    'original': '93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208',
    'ukfleet': 'b3eca1685245c59d1a3e86bd11ede887300bda1b00ba211a1913e467ad3f5183',
}
TRACE_HASH = '896aa5ad646d0d6c643de49eaa84373c9442b2d58483ac0e39aab76619c29628'
BASELINE = Path('/Users/akashx/Downloads/diss_mat/traffictwin-joint-confirmation-raw-2026-09-08/campaign')
RAW = Path('/Users/akashx/Downloads/diss_mat/traffictwin-followups-raw-2026-09-15')
EVIDENCE = HERE / 'evidence'
ENVIRONMENT = json.loads((OLD / 'confirmation/SEALED_EXECUTION.json').read_text())['execution_environment']
STUDIES = {
    '07_two_choice': {'arms': ['dla_p2c'], 'actor': 'original', 'service_mult': 1.},
    '08_half_speed': {'arms': ARMS, 'actor': 'original', 'service_mult': .5},
    '09_second_actor': {'arms': ARMS, 'actor': 'ukfleet', 'service_mult': 1.},
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load(path):
    return json.loads(Path(path).read_text())


def write_once(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def environment(service):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('VEC_JAX_', 'JAX_', 'XLA_'))
           and k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE')}
    env.update(ENVIRONMENT)
    env['VEC_JAX_RSU_SERVICE_MULT'] = str(service)
    return env


def source_bindings():
    paths = list(HERE.glob('*.py')) + [HERE / 'PROTOCOL.md']
    paths += list((OLD / 'experimental').rglob('*.py'))
    frozen = ROOT / 'docs/evaluation/vec_followup_2026-09-07/frozen_evaluator/eval'
    paths += [frozen / n for n in ['e2d_per_task_placement.py', 'rsu_state_delay.py']]
    paths += [OLD / 'confirmation/validation.py', OLD / 'confirmation/SEALED_EXECUTION.json']
    return {str(p): sha(p) for p in sorted(set(paths))}


def check_bindings(bindings):
    for path, digest in bindings.items():
        need(Path(path).is_file() and sha(path) == digest, f'Bound file changed: {path}')


def preflight():
    need(sha(TRACE) == TRACE_HASH, 'Trace mismatch')
    for actor, path in ACTORS.items():
        need(sha(path) == ACTOR_HASHES[actor], 'Actor mismatch')
    old = load(OLD / 'confirmation/SEALED_EXECUTION.json')
    check_bindings({str(ROOT / p): h for p, h in old['sources'].items()})
    old_evaluator = RUNTIME / 'eval/eval_sumo_stage1_mc.py'
    need(sha(old_evaluator) == '2824d9c2ef09e7748cd420d1ab2f0526d28157b8986605dc831397b6c618c07e', 'Runtime evaluator mismatch')
    vendor = load(HERE.parent / 'empirical_extension_2026-09-08/experimental/vendor/SOURCE_BINDINGS.json')
    check_bindings({str(RUNTIME / x['runtime_relative_path']): x['sha256'] for x in vendor['sources']})
    for name in ['e2d_per_task_placement.py', 'rsu_state_delay.py']:
        need(sha(RUNTIME / 'eval' / name) == sha(ROOT / 'docs/evaluation/vec_followup_2026-09-07/frozen_evaluator/eval' / name), 'Runtime helper mismatch')
    code = 'import sys,json,jax,jaxlib,numpy,scipy;print(json.dumps(dict(python=sys.version.split()[0],jax=jax.__version__,jaxlib=jaxlib.__version__,numpy=numpy.__version__,scipy=scipy.__version__,x64=jax.config.jax_enable_x64,devices=[str(d) for d in jax.devices()])))'
    actual = json.loads(subprocess.check_output([str(PYTHON), '-c', code], env=environment(1.), text=True))
    for key, expected in dict(python='3.11.15', jax='0.4.30', jaxlib='0.4.30', numpy='1.26.4', x64=False, devices=['TFRT_CPU_0']).items():
        need(actual[key] == expected, f'Runtime mismatch: {key}')
    return {'timestamp': now(), 'runtime': actual, 'python_sha256': sha(PYTHON),
            'trace_sha256': sha(TRACE), 'actor_sha256': ACTOR_HASHES,
            'free_gib': shutil.disk_usage(RAW.parent).free / (1 << 30),
            'numerical_environment': {k: environment(1.).get(k) for k in sorted(set(ENVIRONMENT) | {'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'XLA_FLAGS'})}}


def config(study, block, arm, seal_path, *, steps=10800, pilot=False, frozen=False, name=None):
    condition = STUDIES[study] if study in STUDIES else {'actor': 'original', 'service_mult': 1.}
    actor = condition['actor']; service = condition['service_mult']
    fleet, evaluator = (1, 0) if pilot else (100 + block, 200 + block)
    dest = RAW / ('qualification' if pilot else study) / (name or f'block_{block:02d}_{arm}') / 'attempt_001'
    command = [str(PYTHON), '-u', str(OLD / 'experimental/evaluator_entry.py'), '--runtime-root', str(RUNTIME)]
    if not frozen:
        command += ['--extension-audit']
    command += ['--trace', str(TRACE), '--actor', str(ACTORS[actor]), '--max-steps', str(steps),
                '--seed', str(evaluator), '--fleet', 'uk2030', '--fleet-seed', str(fleet),
                '--rsu-cap-abs', '6220', '--lambda-arrival', '1.5', '--rsu-service-mult', str(service),
                '--rsu-lb', arm, '--rsu-backhaul-ms', '0', '--k8s-scale', 'off',
                '--substep-queue', 'sequential', '--substep-queue-iters', '3', '--rsu-cap-mode', 'reject',
                '--veh-queue', 'conserved', '--out-json', str(dest / 'summary.json'),
                '--per-step-out', str(dest / 'per_step.npz'), '--per-task-out', str(dest / 'per_task.npz')]
    return {'study': study, 'block': block, 'fleet_seed': fleet, 'evaluator_seed': evaluator,
            'arm': arm, 'steps': steps, 'service_mult': service, 'actor_id': actor,
            'frozen_reference': frozen, 'command': command, 'output': str(dest),
            'seal_path': str(seal_path), 'seal_sha256': sha(seal_path),
            'environment': {**ENVIRONMENT, 'VEC_JAX_RSU_SERVICE_MULT': str(service)},
            'inputs': {'trace': str(TRACE), 'actor': str(ACTORS[actor]),
                       'trace_sha256': TRACE_HASH, 'actor_sha256': ACTOR_HASHES[actor]}}


def verify_completed(c):
    dest = Path(c['output']); record = load(dest / 'VALIDATED.json')
    need(record['status'] == 'passed' and record['configuration'] == c,
         f'Completed configuration mismatch: {dest}')
    need(record['seal_sha256'] == c['seal_sha256'], 'Receipt seal mismatch')
    need(set(record['output_sha256']) == set(FILES), 'Incomplete output bindings')
    check_bindings({str(dest / n): h for n, h in record['output_sha256'].items()})
    return record


def attempt(c, seal):
    dest = Path(c['output'])
    if dest.exists():
        if c['frozen_reference']:
            r = load(dest / 'REFERENCE.json')
            need(r['configuration'] == c, 'Reference config mismatch')
            check_bindings({str(dest / n): h for n, h in r['output_sha256'].items()})
            return r
        return verify_completed(c)
    check_bindings(seal['sources'])
    need(sha(TRACE) == TRACE_HASH and sha(c['inputs']['actor']) == c['inputs']['actor_sha256'], 'Input changed before launch')
    need(shutil.disk_usage(RAW).free / (1 << 30) >= 20, 'Storage floor reached')
    dest.mkdir(parents=True)
    write_once(dest / 'COMMAND.json', c)
    started = now(); start = time.monotonic(); phase = 'simulation'
    write_once(dest / 'STARTED.json', {'started_at': started, 'runner_pid': os.getpid(), 'seal_sha256': c['seal_sha256']})
    print(f"START {c['study']} block={c['block']} arm={c['arm']} steps={c['steps']} {started}", flush=True)
    try:
        with (dest / 'stdout.log').open('x') as out, (dest / 'stderr.log').open('x') as err:
            subprocess.run(c['command'], env=environment(c['service_mult']), stdout=out, stderr=err,
                           timeout=10800, check=True)
        simulation = time.monotonic() - start
        phase = 'validation'; validation_start = time.monotonic()
        if c['frozen_reference']:
            r = {'status': 'reference_completed', 'configuration': c,
                 'output_sha256': {n: sha(dest / n) for n in FILES}}
        else:
            r = validate(dest, c)
        r.update(started_at=started, finished_at=now(), simulation_process_s=simulation,
                 validation_s=time.monotonic() - validation_start, total_wall_s=time.monotonic() - start)
        write_once(dest / ('REFERENCE.json' if c['frozen_reference'] else 'VALIDATED.json'), r)
        print(f"VALIDATED {c['study']} block={c['block']} arm={c['arm']} simulation_s={simulation:.1f}", flush=True)
        return r
    except BaseException as exc:
        write_once(dest / 'FAILED.json', {'status': 'failed', 'phase': phase, 'error': repr(exc),
                                         'started_at': started, 'finished_at': now(),
                                         'elapsed_s': time.monotonic() - start, 'retained': True})
        raise


def baseline(revalidate=False):
    ledger_path = EVIDENCE / 'BASELINE.json'
    if ledger_path.exists():
        ledger = load(ledger_path)
        check_bindings(ledger['bindings'])
        return ledger
    need(revalidate, 'Baseline qualification missing')
    old_seal = OLD / 'confirmation/SEALED_EXECUTION.json'
    need(load(BASELINE / 'COMPLETE.json')['seal_sha256'] == sha(old_seal), 'Historical completion seal mismatch')
    bindings = {str(old_seal): sha(old_seal), str(BASELINE / 'COMPLETE.json'): sha(BASELINE / 'COMPLETE.json')}
    records = {}
    for block in range(8):
        bp = BASELINE / f'BLOCK_{block:02d}.json'; br = load(bp); bindings[str(bp)] = sha(bp)
        need(br['status'] == 'passed' and br['seal_sha256'] == sha(old_seal), 'Historical block invalid')
        for arm in ARMS:
            dest = BASELINE / f'block_{block:02d}_{arm}/attempt_001'; vp = dest / 'VALIDATED.json'
            need(br['cell_receipt_sha256'][arm] == sha(vp), 'Historical block/cell binding mismatch')
            old = load(vp); c = old['configuration']; verify_completed(c)
            need(c['block'] == block and c['arm'] == arm and c['steps'] == 10800
                 and c['fleet_seed'] == 100 + block and c['evaluator_seed'] == 200 + block
                 and c['seal_sha256'] == sha(old_seal), 'Historical design mismatch')
            r = validate(dest, c)
            need(all(r[k] == old[k] for k in ['offered', 'admitted', 'successes', 'output_sha256']), 'Historical revalidation mismatch')
            records[f'{block}:{arm}'] = r
            bindings[str(vp)] = sha(vp)
            bindings.update({str(dest / n): h for n, h in r['output_sha256'].items()})
        print(f'BASELINE REVALIDATED block={block}', flush=True)
    ledger = {'status': 'passed', 'created_at': now(), 'bindings': bindings, 'records': records}
    write_once(ledger_path, ledger)
    return ledger


def shared_arrays(a, b, prefix=None):
    comparisons = {}
    for name in ['per_step.npz', 'per_task.npz']:
        with np.load(Path(a) / name, allow_pickle=False) as x, np.load(Path(b) / name, allow_pickle=False) as y:
            common = sorted(set(x.files) & set(y.files)); need(common, 'No shared scientific fields')
            for field in common:
                aa, bb = x[field], y[field]
                if prefix is not None and aa.ndim and aa.shape[0] == 300:
                    aa = aa[:prefix]
                need(aa.dtype == bb.dtype and np.array_equal(aa, bb), f'Compatibility mismatch: {name}/{field}')
            comparisons[name] = common
    return comparisons


def qualify():
    EVIDENCE.mkdir(exist_ok=True); RAW.mkdir(exist_ok=True)
    seal_path = EVIDENCE / 'QUALIFICATION_SEAL.json'
    if not seal_path.exists():
        pre = preflight(); need(pre['free_gib'] >= 50, 'Insufficient initial storage')
        write_once(seal_path, {'created_at': now(), 'sources': source_bindings(), 'preflight': pre,
                               'max_short_attempts': 16, 'max_steps': 300, 'protocol_sha256': sha(HERE / 'PROTOCOL.md')})
    seal = load(seal_path); check_bindings(seal['sources'])
    base = baseline(revalidate=True)
    runs = {}; number = 0
    plan = [('normal', arm, False) for arm in ARMS]
    plan += [('07_two_choice', 'dla_p2c', False), ('07_two_choice', 'dla_p2c', True)]
    plan += [(s, arm, False) for s in ['08_half_speed', '09_second_actor'] for arm in ARMS]
    for study, arm, frozen in plan:
        number += 1
        need(len(list((RAW / 'qualification').glob('*/attempt_*'))) <= 16, 'Qualification budget exceeded')
        c = config(study, 0, arm, seal_path, steps=300, pilot=True, frozen=frozen,
                   name=f'{number:02d}_{study}_{arm}')
        runs[f'{study}:{arm}:{frozen}'] = attempt(c, seal)
    original_pilots = RAW.parent / 'traffictwin-joint-confirmation-raw-2026-09-08/qualification'
    # Resolve prior 300-step instrumented pilots by their recorded configuration.
    pilot_records = {}
    for vp in sorted(original_pilots.glob('attempt_*/VALIDATED.json')):
        r = load(vp); c = r.get('configuration', {})
        if c.get('steps') == 300 and c.get('fleet_seed') == 1 and c.get('evaluator_seed') == 0:
            pilot_records.setdefault(c['arm'], []).append((vp.parent, r))
    compatibility = {}
    for arm in ARMS:
        need(arm in pilot_records, f'Preserved pilot missing: {arm}')
        prior, oldrec = pilot_records[arm][0]
        check_bindings({str(prior / n): h for n, h in oldrec['output_sha256'].items()})
        compatibility[arm] = shared_arrays(prior, runs[f'normal:{arm}:False']['configuration']['output'])
    p2c = runs['07_two_choice:dla_p2c:False']; ref = runs['07_two_choice:dla_p2c:True']
    compatibility['p2c_frozen'] = shared_arrays(p2c['configuration']['output'], ref['configuration']['output'])
    groups = {}
    for study in ['normal', '08_half_speed', '09_second_actor']:
        ingress = runs[f'{study}:ingress_dla:False']
        groups[study] = [matched(ingress, runs[f'{study}:{arm}:False']) for arm in ARMS]
    cross = {}
    for study in ['08_half_speed', '09_second_actor']:
        cross[study] = [matched(runs[f'normal:{arm}:False'], runs[f'{study}:{arm}:False'], study == '08_half_speed') for arm in ARMS]
    cross['p2c'] = matched(runs['normal:ingress_dla:False'], p2c)
    restart = attempt(config('07_two_choice', 0, 'dla_p2c', seal_path, steps=150, pilot=True,
                             name='15_p2c_prefix'), seal)
    compatibility['p2c_prefix'] = shared_arrays(p2c['configuration']['output'], restart['configuration']['output'], prefix=150)
    receipt = {'status': 'passed', 'completed_at': now(), 'qualification_seal_sha256': sha(seal_path),
               'baseline_ledger_sha256': sha(EVIDENCE / 'BASELINE.json'), 'compatibility': compatibility,
               'within_condition': groups, 'cross_condition': cross,
               'attempt_receipts': {str(p): sha(p) for p in sorted((RAW / 'qualification').rglob('VALIDATED.json'))},
               'reference_receipts': {str(p): sha(p) for p in sorted((RAW / 'qualification').rglob('REFERENCE.json'))},
               'short_attempts': len(list((RAW / 'qualification').glob('*/attempt_*')))}
    write_once(EVIDENCE / 'QUALIFICATION.json', receipt)
    print('QUALIFICATION PASSED', flush=True)


def seal_execution():
    q = load(EVIDENCE / 'QUALIFICATION.json'); need(q['status'] == 'passed', 'Qualification missing')
    check_bindings(load(EVIDENCE / 'QUALIFICATION_SEAL.json')['sources'])
    check_bindings(q['attempt_receipts']); check_bindings(q['reference_receipts'])
    review = load(EVIDENCE / 'SOURCE_REVIEW.json')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    need(review['verdict'] == 'APPROVE' and review['source_commit'] == head, 'Independent exact-source review missing')
    pre = preflight(); initial = load(EVIDENCE / 'QUALIFICATION_SEAL.json')['preflight']
    for key in ['runtime', 'python_sha256', 'numerical_environment']:
        need(pre[key] == initial[key], 'Qualified runtime changed')
    seal = {'authorised': True, 'sealed_at': now(), 'source_commit': head, 'sources': source_bindings(),
            'protocol_sha256': sha(HERE / 'PROTOCOL.md'), 'studies': STUDIES,
            'qualification_sha256': sha(EVIDENCE / 'QUALIFICATION.json'),
            'review_sha256': sha(EVIDENCE / 'SOURCE_REVIEW.json'),
            'baseline_ledger_sha256': sha(EVIDENCE / 'BASELINE.json'), 'preflight': pre,
            'output_root': str(RAW), 'full_attempts': 72, 'paired_blocks': 8,
            'new_full_outcomes_before_seal': 0}
    need(not any((RAW / s).exists() for s in STUDIES), 'Full outcomes already exist')
    write_once(EVIDENCE / 'EXECUTION_SEAL.json', seal)
    print('EXECUTION SEALED', flush=True)


def check_execution():
    seal = load(EVIDENCE / 'EXECUTION_SEAL.json')
    need(seal['authorised'] is True and seal['studies'] == STUDIES and seal['output_root'] == str(RAW), 'Execution design mismatch')
    check_bindings(seal['sources'])
    for file, key in [('QUALIFICATION.json', 'qualification_sha256'), ('SOURCE_REVIEW.json', 'review_sha256'), ('BASELINE.json', 'baseline_ledger_sha256')]:
        need(sha(EVIDENCE / file) == seal[key], f'Changed evidence: {file}')
    return seal


def run():
    seal_path = EVIDENCE / 'EXECUTION_SEAL.json'; seal = check_execution()
    pre = preflight()
    for key in ['runtime', 'python_sha256', 'numerical_environment']:
        need(pre[key] == seal['preflight'][key], 'Sealed runtime changed')
    base = baseline()
    write_once(RAW / f'PREFLIGHT_{time.time_ns()}.json', pre)
    for study, condition in STUDIES.items():
        for block in range(8):
            arms = condition['arms']; order = arms[block % len(arms):] + arms[:block % len(arms)]
            records = {}
            for arm in order:
                attempts = sum(len(list((RAW / s).glob('*/attempt_*'))) for s in STUDIES)
                c = config(study, block, arm, seal_path)
                need(attempts < 72 or Path(c['output']).exists(), 'Full-attempt budget exhausted')
                records[arm] = attempt(c, seal)
            controls = {}; cross = {}
            reference = records.get('ingress_dla', base['records'][f'{block}:ingress_dla'])
            for arm in arms:
                controls[arm] = matched(reference, records[arm])
                original = base['records'][f'{block}:{arm if arm in ARMS else "ingress_dla"}']
                cross[arm] = matched(original, records[arm], study == '08_half_speed')
            receipt = {'status': 'passed', 'study': study, 'block': block, 'seal_sha256': sha(seal_path),
                       'cell_receipts': {arm: sha(Path(records[arm]['configuration']['output']) / 'VALIDATED.json') for arm in arms},
                       'within_condition': controls, 'historical_matching': cross}
            path = RAW / study / f'BLOCK_{block:02d}.json'
            if path.exists():
                need(load(path) == receipt, 'Completed block changed')
            else:
                write_once(path, receipt)
            print(f'BLOCK PASSED {study} {block}', flush=True)
        path = RAW / study / 'COMPLETE.json'
        if not path.exists():
            write_once(path, {'status': 'complete', 'study': study, 'completed_at': now(),
                              'full_cells': 8 * len(arms), 'seal_sha256': sha(seal_path)})
    require_complete()
    write_once(RAW / 'COMPLETE.json', {'status': 'complete', 'finished_at': now(), 'full_cells': 72,
                                     'seal_sha256': sha(seal_path)})
    print('ALL THREE STUDIES COMPLETE', flush=True)


def require_complete():
    seal = check_execution(); baseline()
    sp = EVIDENCE / 'EXECUTION_SEAL.json'
    for study, condition in STUDIES.items():
        for block in range(8):
            bp = RAW / study / f'BLOCK_{block:02d}.json'; br = load(bp)
            need(br['status'] == 'passed' and br['study'] == study and br['block'] == block
                 and br['seal_sha256'] == sha(sp), 'Incomplete/invalid block')
            for arm in condition['arms']:
                c = config(study, block, arm, sp); vp = Path(c['output']) / 'VALIDATED.json'
                verify_completed(c)
                need(br['cell_receipts'][arm] == sha(vp), 'Block/cell binding mismatch')
    return seal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['qualify', 'seal', 'run', 'verify'])
    a = parser.parse_args(); RAW.mkdir(exist_ok=True); EVIDENCE.mkdir(exist_ok=True)
    with (RAW / 'STUDY.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'qualify': qualify, 'seal': seal_execution, 'run': run, 'verify': require_complete}[a.action]()


if __name__ == '__main__':
    main()
