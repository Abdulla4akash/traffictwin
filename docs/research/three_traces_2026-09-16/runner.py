"""Trace-configured follow-up runner; unchanged evaluator and scientific checks.

Reuses the guarded follow-up environment, preflight, command construction,
receipt/hash checks and prefix comparison. Orchestration is scoped to the
owner's three traces; scientific validators differ only in configured N/R
and the evaluator's existing entry-channel convention.
"""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import time

import numpy as np

from checks import matched, validate
from validation import FILES, need, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEGACY = ROOT / 'docs/dissertation/followups_2026-09-15'
OLD = ROOT / 'docs/dissertation/joint_confirmation_2026-09-08'
DESIGN = json.loads((HERE / 'CONFIG.json').read_text())
ARMS = DESIGN['arms']
PYTHON = Path(DESIGN['runtime']['python'])
RUNTIME = Path('/Users/akashx/Downloads/diss_mat/vec_env-state-delay-run')
ACTORDIR = Path('/Users/akashx/Downloads/diss_mat/tos-data-full/checkpoints')
ACTORS = {'original': ACTORDIR / 'mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz'}
ACTOR_HASHES = {'original': DESIGN['controls']['actor_sha256']}
ENVIRONMENT = json.loads((OLD / 'confirmation/SEALED_EXECUTION.json').read_text())['execution_environment']
RAW_PARENT = Path(DESIGN['execution']['raw_root'])
STUDIES = {t: {'arms': ARMS, 'actor': 'original', 'service_mult': 1.} for t in DESIGN['traces']}
TRACE_ID = TRACE = TRACE_HASH = RAW = EVIDENCE = None


def select(trace):
    global TRACE_ID, TRACE, TRACE_HASH, RAW, EVIDENCE
    need(trace in DESIGN['traces'], 'Undeclared trace')
    TRACE_ID = trace
    TRACE = Path(DESIGN['traces'][trace]['path'])
    TRACE_HASH = DESIGN['traces'][trace]['sha256']
    RAW = RAW_PARENT / trace
    EVIDENCE = HERE / 'evidence' / trace
    RAW.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)


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
    paths += [HERE / 'CONFIG.json', HERE / 'TRACE_INVENTORY.json', HERE / 'OWNER_AMENDMENT.md']
    paths += list(LEGACY.glob('*.py')) + [LEGACY / 'PROTOCOL.md', LEGACY / 'GUARD_AMENDMENT.md']
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
    vendor = load(ROOT / 'docs/dissertation/empirical_extension_2026-09-08/experimental/vendor/SOURCE_BINDINGS.json')
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


def config(study, block, arm, seal_path, *, steps=None, pilot=False, frozen=False, name=None):
    steps = DESIGN['traces'][study]['T'] if steps is None else steps
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
            'trace_dimensions': {k: DESIGN['traces'][study][k] for k in ['N', 'R', 'entry_channel_present']},
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


def reserve_slot():
    """Global evaluator concurrency, reducing future starts without killing work."""
    while True:
        limit = 2 if (RAW_PARENT / 'REDUCE_CONCURRENCY.json').exists() else 3
        for index in range(limit):
            stream = (RAW_PARENT / f'SLOT_{index}.lock').open('a+')
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                stream.close()
                continue
            # Recheck after acquiring: another trace may just have lowered limit.
            if index == 2 and (RAW_PARENT / 'REDUCE_CONCURRENCY.json').exists():
                stream.close()
                continue
            return stream
        time.sleep(1)


def memory_receipt(dest):
    log = (dest / 'stderr.log').read_text()
    matches = re.findall(r'^\s*(\d+)\s+maximum resident set size\s*$', log, re.M)
    need(len(matches) == 1, 'Missing evaluator peak-RSS measurement')
    peak = int(matches[0])  # Darwin time(1) and getrusage report bytes.
    validation_peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    receipt = {'evaluator_peak_rss_bytes': peak,
               'runner_process_high_water_rss_bytes': validation_peak,
               'limit_bytes': DESIGN['execution']['peak_rss_limit_bytes'],
               'method': '/usr/bin/time -l evaluator; getrusage runner cumulative high-water'}
    if max(peak, validation_peak) > receipt['limit_bytes']:
        try:
            write_once(RAW_PARENT / 'REDUCE_CONCURRENCY.json',
                       {'created_at': now(), 'trigger_output': str(dest), **receipt})
        except FileExistsError:
            pass
    return receipt


def attempt(c, seal):
    """Original attempt guards/accounting with configured storage and RSS logging."""
    dest = Path(c['output'])
    # Incomplete attempts cannot be resumed or retried.
    if dest.exists():
        return verify_completed(c)
    with reserve_slot():
        check_bindings(seal['sources'])
        need(sha(TRACE) == TRACE_HASH and sha(c['inputs']['actor']) == c['inputs']['actor_sha256'], 'Input changed before launch')
        need(sha(c['seal_path']) == c['seal_sha256'], 'Attempt seal changed')
        need(shutil.disk_usage(RAW).free >= DESIGN['execution']['attempt_free_space_bytes'], 'Storage floor reached')
        dest.mkdir(parents=True)
        write_once(dest / 'COMMAND.json', c)
        started = now(); start = time.monotonic(); phase = 'simulation'
        write_once(dest / 'STARTED.json', {'started_at': started, 'runner_pid': os.getpid(),
                                         'seal_sha256': c['seal_sha256'],
                                         'measurement_prefix': ['/usr/bin/time', '-l']})
        print(f"START {TRACE_ID} block={c['block']} arm={c['arm']} steps={c['steps']} {started}", flush=True)
        proc = None
        try:
            with (dest / 'stdout.log').open('x') as out, (dest / 'stderr.log').open('x') as err:
                proc = subprocess.Popen(['/usr/bin/time', '-l', *c['command']],
                                        env=environment(c['service_mult']), stdout=out,
                                        stderr=err, start_new_session=True)
                try:
                    code = proc.wait(timeout=DESIGN['execution']['timeout_seconds'])
                except BaseException:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    raise
                need(code == 0, f'Evaluator exit status {code}')
            simulation = time.monotonic() - start
            phase = 'validation'; validation_start = time.monotonic()
            r = validate(dest, c)
            require_schema(r)
            r.update(started_at=started, finished_at=now(), simulation_process_s=simulation,
                     validation_s=time.monotonic() - validation_start,
                     total_wall_s=time.monotonic() - start, memory=memory_receipt(dest))
            write_once(dest / 'VALIDATED.json', r)
            print(f"VALIDATED {TRACE_ID} block={c['block']} arm={c['arm']} simulation_s={simulation:.1f}", flush=True)
            return r
        except BaseException as exc:
            write_once(dest / 'FAILED.json', {'status': 'failed', 'phase': phase,
                                             'error': repr(exc), 'started_at': started,
                                             'finished_at': now(),
                                             'elapsed_s': time.monotonic() - start, 'retained': True})
            raise


def require_schema(record):
    expected = DESIGN['qualification']['expected_array_fields']
    need(set(record['field_contract']) == set(expected), 'Array file schema changed')
    for kind, fields in expected.items():
        need(set(record['field_contract'][kind]) == set(fields), f'Exact {kind} array field set changed')


def qualify():
    sp = EVIDENCE / 'QUALIFICATION_SEAL.json'
    need(not sp.exists(), 'Qualification already started; no retries')
    pre = preflight()
    need(pre['free_gib'] * (1 << 30) >= DESIGN['execution']['initial_free_space_bytes'], 'Initial storage floor')
    need(not (RAW / TRACE_ID).exists(), 'Full outcomes already exist')
    seal = {'created_at': now(), 'sources': source_bindings(), 'preflight': pre,
            'trace': TRACE_ID, 'protocol_sha256': sha(HERE / 'PROTOCOL.md'),
            'config_sha256': sha(HERE / 'CONFIG.json'), 'max_short_attempts': 6,
            'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    write_once(sp, seal)
    records = {}
    for index, arm in enumerate(ARMS, 1):
        c = config(TRACE_ID, 0, arm, sp, steps=300, pilot=True, name=f'{index:02d}_{arm}')
        records[arm] = attempt(c, seal)
    controls = {arm: matched(records['ingress_dla'], records[arm]) for arm in ARMS}
    need(all(len(r['shared_input_hashes']) == 14 for r in records.values()), 'Shared-input schema changed')
    for r in records.values():
        require_schema(r)
    restart = attempt(config(TRACE_ID, 0, 'per_task_dla', sp, steps=150,
                             pilot=True, name='06_per_task_dla_prefix'), seal)
    prefix = shared_arrays(records['per_task_dla']['configuration']['output'],
                           restart['configuration']['output'], prefix=150)
    need(sum(map(len, prefix.values())) == 59, 'Incomplete restart schema')
    receipt = {'status': 'passed', 'completed_at': now(), 'trace': TRACE_ID,
               'qualification_seal_sha256': sha(sp), 'within_trace': controls,
               'shared_input_field_count': 14, 'restart': prefix, 'restart_array_count': 59,
               'short_attempts': 6, 'attempt_receipts': {
                   str(p): sha(p) for p in sorted((RAW / 'qualification').rglob('VALIDATED.json'))}}
    need(len(receipt['attempt_receipts']) == 6, 'Qualification attempt budget mismatch')
    write_once(EVIDENCE / 'QUALIFICATION.json', receipt)
    print(f'QUALIFICATION PASSED {TRACE_ID}', flush=True)


def seal_execution():
    qpath = EVIDENCE / 'QUALIFICATION.json'; q = load(qpath)
    qsp = EVIDENCE / 'QUALIFICATION_SEAL.json'; qs = load(qsp)
    need(q['status'] == 'passed' and sha(qsp) == q['qualification_seal_sha256'], 'Qualification parent changed')
    check_bindings(qs['sources']); check_bindings(q['attempt_receipts'])
    need(qs['sources'] == source_bindings(), 'Qualified source set changed')
    review_path = HERE / 'evidence/SOURCE_REVIEW.json'; review = load(review_path)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    need(review['verdict'] == 'APPROVE' and review['source_commit'] == head == qs['source_commit'], 'Exact-source review missing')
    pre = preflight()
    for key in ['runtime', 'python_sha256', 'numerical_environment']:
        need(pre[key] == qs['preflight'][key], 'Qualified runtime changed')
    # All three qualification decisions precede full execution.
    for trace in DESIGN['traces']:
        folder = HERE / 'evidence' / trace
        need((folder / 'QUALIFICATION.json').exists() or (folder / 'STOPPED.json').exists(), 'Trace qualification decision missing')
    need(not (RAW / TRACE_ID).exists(), 'Full outcomes already exist')
    seal = {'authorised': True, 'sealed_at': now(), 'source_commit': head,
            'trace': TRACE_ID, 'sources': source_bindings(), 'config_sha256': sha(HERE / 'CONFIG.json'),
            'protocol_sha256': sha(HERE / 'PROTOCOL.md'), 'qualification_sha256': sha(qpath),
            'qualification_seal_sha256': sha(qsp), 'review_sha256': sha(review_path),
            'preflight': pre, 'output_root': str(RAW), 'full_attempts': 40,
            'paired_blocks': 8, 'new_full_outcomes_before_seal': 0}
    write_once(EVIDENCE / 'EXECUTION_SEAL.json', seal)
    print(f'EXECUTION SEALED {TRACE_ID}', flush=True)


def check_execution():
    seal = load(EVIDENCE / 'EXECUTION_SEAL.json')
    need(seal['authorised'] is True and seal['trace'] == TRACE_ID
         and seal['output_root'] == str(RAW) and seal['full_attempts'] == 40, 'Execution design mismatch')
    check_bindings(seal['sources'])
    for path, key in [(HERE / 'CONFIG.json', 'config_sha256'),
                      (EVIDENCE / 'QUALIFICATION.json', 'qualification_sha256'),
                      (EVIDENCE / 'QUALIFICATION_SEAL.json', 'qualification_seal_sha256'),
                      (HERE / 'evidence/SOURCE_REVIEW.json', 'review_sha256')]:
        need(sha(path) == seal[key], f'Changed evidence: {path}')
    q = load(EVIDENCE / 'QUALIFICATION.json'); check_bindings(q['attempt_receipts'])
    return seal


def run():
    sp = EVIDENCE / 'EXECUTION_SEAL.json'; seal = check_execution()
    pre = preflight()
    for key in ['runtime', 'python_sha256', 'numerical_environment']:
        need(pre[key] == seal['preflight'][key], 'Sealed runtime changed')
    write_once(RAW / 'FULL_STARTED.json', {'started_at': now(), 'preflight': pre, 'seal_sha256': sha(sp)})
    start = time.monotonic()
    for block in range(8):
        order = ARMS[block % 5:] + ARMS[:block % 5]
        records = {}
        for arm in order:
            need(len(list((RAW / TRACE_ID).glob('*/attempt_*'))) < 40, 'Full attempt budget exhausted')
            records[arm] = attempt(config(TRACE_ID, block, arm, sp), seal)
        controls = {arm: matched(records['ingress_dla'], records[arm]) for arm in ARMS}
        receipt = {'status': 'passed', 'trace': TRACE_ID, 'block': block,
                   'fleet_seed': 100 + block, 'evaluator_seed': 200 + block,
                   'arm_order': order, 'seal_sha256': sha(sp), 'within_trace': controls,
                   'cell_receipts': {arm: sha(Path(records[arm]['configuration']['output']) / 'VALIDATED.json') for arm in ARMS}}
        write_once(RAW / TRACE_ID / f'BLOCK_{block:02d}.json', receipt)
        print(f'BLOCK PASSED {TRACE_ID} {block}', flush=True)
    require_complete()
    write_once(RAW / 'COMPLETE.json', {'status': 'complete', 'trace': TRACE_ID,
                                     'finished_at': now(), 'full_cells': 40,
                                     'wall_s': time.monotonic() - start, 'seal_sha256': sha(sp)})
    print(f'TRACE COMPLETE {TRACE_ID}', flush=True)


def require_complete():
    seal = check_execution(); sp = EVIDENCE / 'EXECUTION_SEAL.json'
    for block in range(8):
        br = load(RAW / TRACE_ID / f'BLOCK_{block:02d}.json')
        need(br['status'] == 'passed' and br['block'] == block and br['trace'] == TRACE_ID
             and br['seal_sha256'] == sha(sp) and set(br['cell_receipts']) == set(ARMS), 'Invalid block')
        records = {}
        for arm in ARMS:
            c = config(TRACE_ID, block, arm, sp)
            records[arm] = verify_completed(c)
            need(br['cell_receipts'][arm] == sha(Path(c['output']) / 'VALIDATED.json'), 'Block/cell mismatch')
        need(all(r['shared_input_hashes'] == records['ingress_dla']['shared_input_hashes'] for r in records.values()), 'Block input mismatch')
    need(len(list((RAW / TRACE_ID).glob('*/attempt_*'))) == 40, 'Unexpected full attempt count')
    return seal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['qualify', 'seal', 'run', 'verify'])
    parser.add_argument('trace', choices=list(DESIGN['traces']))
    args = parser.parse_args(); select(args.trace)
    with (RAW / 'STUDY.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            {'qualify': qualify, 'seal': seal_execution, 'run': run, 'verify': require_complete}[args.action]()
        except BaseException as exc:
            if args.action in ['qualify', 'run'] and not (EVIDENCE / 'STOPPED.json').exists():
                write_once(EVIDENCE / 'STOPPED.json', {'status': 'stopped', 'action': args.action,
                                                     'trace': TRACE_ID, 'error': repr(exc), 'at': now(),
                                                     'retry_authorised': False})
            raise


if __name__ == '__main__':
    main()
