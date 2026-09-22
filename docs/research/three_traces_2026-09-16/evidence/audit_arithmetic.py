#!/usr/bin/env python3
"""Independent final arithmetic audit; never imports or runs campaign code.

Standard-library arithmetic; SciPy supplies only Student-t critical values.
Every bound output is rehashed, including NPZ files. Arrays are not opened:
conservation and restart execution remain claims of the bound qualification
and cell validators. This audit is not source approval or an Opus review.
JSON is always emitted. Exit 0 means passed, 1 invalid, 2 missing prerequisites.
--output creates a new report, including failure reports, and never overwrites.
"""

import argparse
import csv
import datetime
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path


RELATIVE = Path('docs/research/three_traces_2026-09-16')
TRACES = ('we', 'wd_pm', 'ev')
DIMENSIONS = {'we': (32400, 139, 9, True), 'wd_pm': (25200, 163, 10, False),
              'ev': (23400, 175, 12, False)}
TRACE_HASHES = {
    'we': '8bb0a05e9e494041943a9d99efbcfc6fce7bc529b348230593a9155580b0d976',
    'wd_pm': '848ba3cf278515f6a628bfb575892373454fae60ea6edf717da3b7683051ba9f',
    'ev': '70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208',
}
ACTOR_HASH = '93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208'
ARMS = ('ingress_dla', 'dla', 'per_task_dla', 'causal_round_robin', 'dla_p2c')
CONTRASTS = (('per_task_dla', 'ingress_dla'), ('dla', 'ingress_dla'),
             ('per_task_dla', 'causal_round_robin'), ('per_task_dla', 'dla_p2c'),
             ('dla_p2c', 'causal_round_robin'))
INTERVAL_KINDS = ('individual95', 'trace_family95', 'all_fifteen_family95')
INTERVAL_FIELDS = ('mean_pp', 'sd_pp', 'low_pp', 'high_pp', 'family_size', 'df', 'n_blocks')
CELL_FIELDS = ('trace', 'block', 'fleet_seed', 'evaluator_seed', 'arm',
               'offered', 'admitted', 'successes', 'attainment_pct')
OUTPUTS = {'summary.json', 'per_step.npz', 'per_task.npz'}
STEP_FIELDS = set(('active arrivals done exogenous_keys lat_sum n_local n_v2i n_v2v '
    'observation_task_size observation_task_type rr_pointer_after rr_pointer_before '
    'rsu_busy_ms rsu_load rsu_pre_drain_busy_ms rsu_pre_drain_load rsu_start_busy_ms '
    'rsu_start_load slot_is_ev slot_soc_initial slot_tier slot_tx_power_w times '
    'veh_action veh_actor_logits veh_best_rsu veh_best_v2v veh_done veh_energy_j '
    'veh_k veh_load veh_observations veh_pre_drain_busy_ms veh_pre_drain_load '
    'veh_queue_ms veh_soc_after veh_soc_before veh_start_busy_ms veh_start_load '
    'veh_v2i_capacity_mbps veh_v2i_quality veh_v2v_radio_viable veh_v2v_target').split())
TASK_FIELDS = set(('task_active task_execution_rsu task_final_admitted task_forwarded '
    'task_forwarding_latency_ms task_ingress_rsu task_lat_ms task_local_service_ms '
    'task_met task_outcome task_rsu_service_ms task_selected_execution_rsu task_sizes_mb '
    'task_type task_v2i_admitted task_v2v_service_ms').split())
SHARED_FIELDS = {f'step/{x}' for x in ('times slot_tier slot_is_ev slot_soc_initial '
    'slot_tx_power_w exogenous_keys observation_task_type observation_task_size veh_k').split()}
SHARED_FIELDS |= {f'task/{x}' for x in ('task_active task_type task_sizes_mb '
    'task_rsu_service_ms task_local_service_ms').split()}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, f'Duplicate JSON key {key!r} in {path}')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f'Nonfinite JSON constant {value} in {path}')
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=reject_constant)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            result.update(chunk)
    return result.hexdigest()


def is_digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def finite(value, label):
    need(type(value) in (int, float) and math.isfinite(value), label + ': expected finite number')
    return value


def count(value, label):
    need(type(value) is int and value >= 0, label + ': expected nonnegative integer')
    return value


def near(value, expected, label):
    finite(value, label)
    need(math.isclose(value, expected, abs_tol=5e-12, rel_tol=0),
         f'{label}: {value!r} != {expected!r}')


def timestamp(value):
    result = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(result.tzinfo is not None, 'Timestamp lacks timezone: ' + value)
    return result


def interval(values, family, student_t):
    need(len(values) == 8, 'Exactly eight paired block effects required')
    for value in values:
        finite(value, 'Paired effect')
    mean = math.fsum(values) / 8
    sd = statistics.stdev(values)
    critical = float(student_t.ppf(1 - .05 / (2 * family), df=7))
    width = critical * sd / math.sqrt(8)
    return dict(mean_pp=mean, sd_pp=sd, low_pp=mean-width, high_pp=mean+width,
                family_size=family, df=7, n_blocks=8)


class Audit:
    def __init__(self, checkout, raw):
        self.checkout, self.raw = checkout, raw
        self.here = checkout / RELATIVE
        self.bindings = {}
        self.source_sets = []
        self.seals = {}
        self.qualification = {}
        self.records = {}
        self.cells = {}
        self.wall = {}
        self.checked_outputs = 0
        self.gate_passed = False

    def bind(self, path, expected=None):
        path = Path(path)
        actual = digest(path)
        if expected is not None:
            need(is_digest(expected) and expected == actual, 'File hash mismatch: ' + str(path))
        if str(path) in self.bindings:
            need(self.bindings[str(path)] == actual, 'File changed during audit: ' + str(path))
        self.bindings[str(path)] = actual
        return actual

    def bound_json(self, path, expected=None):
        self.bind(path, expected)
        return read_json(path)

    def sources(self, seal):
        bindings = seal['sources']
        need(isinstance(bindings, dict) and bindings, 'Empty source bindings')
        must_bind = [self.here / p for p in ('CONFIG.json', 'PROTOCOL.md', 'TRACE_INVENTORY.json',
                                             'OWNER_AMENDMENT.md', 'runner.py', 'checks.py', 'validation.py')]
        need(set(map(str, must_bind)) <= set(bindings), 'Required source/configuration binding missing')
        source = seal['source_commit']
        need(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source), 'Invalid source commit')
        for path, expected in bindings.items():
            self.bind(path, expected)
            relative = Path(path).relative_to(self.checkout)
            committed = subprocess.check_output(['git', '-C', str(self.checkout), 'show',
                                                  f'{source}:{relative.as_posix()}'], stderr=subprocess.PIPE)
            need(hashlib.sha256(committed).hexdigest() == expected,
                 f'Source is not the sealed commit version: {path}')
        self.source_sets.append(bindings)

    def design(self):
        config = self.bound_json(self.here / 'CONFIG.json')
        self.config = config
        need(set(config['traces']) == set(TRACES) and tuple(config['arms']) == ARMS, 'Configured traces/arms')
        need(config['total_full_cells'] == 120 and config['full_cells_per_trace'] == 40, 'Configured cell budget')
        need(config['execution']['raw_root'] == str(self.raw), 'Configured raw root')
        need(config['execution']['retries'] == config['execution']['seed_substitutions'] == 0, 'No retry/substitution contract')
        qualification = config['qualification']
        need(qualification['fleet_seed'] == 1 and qualification['evaluator_seed'] == 0
             and qualification['total_short_attempts'] == 18, 'Qualification seed/budget design')
        need(qualification['amended_contract'] == dict(shared_exogenous_field_count=14,
             restart_array_count=59, endogenous_equality_required=False), 'Amended qualification contract')
        need(set(qualification['expected_array_fields']['step']) == STEP_FIELDS
             and set(qualification['expected_array_fields']['task']) == TASK_FIELDS,
             'Configured complete array field sets')
        reference = qualification['field_schema_reference']
        archived = self.bound_json(reference['path'], reference['sha256'])
        need(set(archived['field_contract']['step']) == STEP_FIELDS
             and set(archived['field_contract']['task']) == TASK_FIELDS, 'Archived array schema binding')
        self.bind(self.here / 'TRACE_INVENTORY.json', config['trace_inventory_sha256'])
        expected_blocks = []
        for block in range(8):
            shift = block % 5
            expected_blocks.append(dict(block=block, fleet_seed=100+block, evaluator_seed=200+block,
                                        arm_order=list(ARMS[shift:] + ARMS[:shift])))
        need(config['blocks'] == expected_blocks, 'Block seeds/order differ from fixed design')
        analysis = config['analysis']
        need(tuple(map(tuple, analysis['contrasts'])) == CONTRASTS and analysis['blocks'] == 8
             and analysis['degrees_of_freedom'] == 7 and analysis['family_sizes'] == [1, 5, 15], 'Analysis design')
        need(analysis['denominator'] == 'all offered tasks' and analysis['task_level_tests'] is False
             and analysis['cross_trace_tests'] is False and analysis['pool_across_traces'] is False,
             'Statistical unit/denominator contract')
        controls = config['controls']
        expected = dict(actor_sha256=ACTOR_HASH, fleet='uk2030', lambda_arrival=1.5,
                        rsu_cap_abs=6220, rsu_service_mult=1., rsu_backhaul_ms=0,
                        k8s_scale='off', substep_queue='sequential', substep_queue_iters=3,
                        rsu_cap_mode='reject', veh_queue='conserved', ignore_enter=False,
                        reset_soc_on_enter=False, K=5)
        need(all(controls[k] == v for k, v in expected.items()), 'Configured fixed controls')
        self.bind(controls['actor'], ACTOR_HASH)
        for trace in TRACES:
            tr = config['traces'][trace]
            need(tuple(tr[k] for k in ('T', 'N', 'R', 'entry_channel_present')) == DIMENSIONS[trace],
                 'Trace dimensions/convention: ' + trace)
            need(tr['sha256'] == TRACE_HASHES[trace], 'Selected trace identity: ' + trace)
            self.bind(tr['path'], TRACE_HASHES[trace])

    def matched(self, mappings):
        need(set(mappings) == set(ARMS), 'Matching receipt arm set')
        for arm, rec in mappings.items():
            need(rec['status'] == 'passed' and rec['exogenous_inputs'] == 'matched'
                 and rec['actions_forced'] is False, 'Cross-arm matching receipt: ' + arm)

    def cell(self, dest, trace, block, arm, steps, seal_path, pilot):
        need(dest.is_dir() and set(dest.parent.glob('attempt_*')) == {dest}, 'Missing/extra attempt: ' + str(dest))
        need(not (dest / 'FAILED.json').exists(), 'Retained failed attempt: ' + str(dest))
        rec = self.bound_json(dest / 'VALIDATED.json')
        cfg = self.bound_json(dest / 'COMMAND.json')
        start = self.bound_json(dest / 'STARTED.json')
        sh = self.bind(seal_path)
        need(rec['status'] == 'passed' and rec['configuration'] == cfg, 'Validated command binding')
        need(rec['seal_sha256'] == cfg['seal_sha256'] == start['seal_sha256'] == sh, 'Attempt seal chain')
        fleet, evaluator = (1, 0) if pilot else (100+block, 200+block)
        expected = dict(study=trace, block=block, arm=arm, steps=steps, fleet_seed=fleet,
                        evaluator_seed=evaluator, actor_id='original', service_mult=1.,
                        frozen_reference=False, output=str(dest), seal_path=str(seal_path))
        need(all(cfg[k] == v for k, v in expected.items()), 'Attempt design: ' + str(dest))
        tr = self.config['traces'][trace]
        need(cfg['trace_dimensions'] == {k: tr[k] for k in ('N', 'R', 'entry_channel_present')}, 'Attempt trace dimensions')
        need(cfg['inputs'] == dict(trace=tr['path'], actor=self.config['controls']['actor'],
                                  trace_sha256=TRACE_HASHES[trace], actor_sha256=ACTOR_HASH), 'Attempt input identities')
        need(cfg['environment'] == self.config['runtime']['environment'], 'Attempt numerical environment')
        cmd = cfg['command']
        need(isinstance(cmd, list) and '--extension-audit' in cmd and '--ignore-enter' not in cmd
             and '--reset-soc-on-enter' not in cmd, 'Instrumentation/entry flags')
        flags = {'--trace': tr['path'], '--actor': cfg['inputs']['actor'], '--max-steps': str(steps),
                 '--seed': str(evaluator), '--fleet-seed': str(fleet), '--fleet': 'uk2030',
                 '--rsu-lb': arm, '--rsu-cap-abs': '6220', '--lambda-arrival': '1.5',
                 '--rsu-service-mult': '1.0', '--rsu-backhaul-ms': '0', '--k8s-scale': 'off',
                 '--substep-queue': 'sequential', '--substep-queue-iters': '3',
                 '--rsu-cap-mode': 'reject', '--veh-queue': 'conserved',
                 '--out-json': str(dest/'summary.json'), '--per-step-out': str(dest/'per_step.npz'),
                 '--per-task-out': str(dest/'per_task.npz')}
        for flag, value in flags.items():
            need(cmd.count(flag) == 1 and cmd[cmd.index(flag)+1] == value, 'Command flag: ' + flag)
        need(cmd[:3] == [self.config['runtime']['python'], '-u',
                         str(self.checkout/'docs/dissertation/joint_confirmation_2026-09-08/experimental/evaluator_entry.py')],
             'Evaluator executable identity')
        need(set(rec['output_sha256']) == OUTPUTS, 'Output file set')
        for name, expected_hash in rec['output_sha256'].items():
            self.bind(dest / name, expected_hash)
            self.checked_outputs += 1
        need(set(rec['shared_input_hashes']) == SHARED_FIELDS
             and all(is_digest(x) for x in rec['shared_input_hashes'].values()), '14 shared input hashes')
        need(set(rec['field_contract']['step']) == STEP_FIELDS
             and set(rec['field_contract']['task']) == TASK_FIELDS, 'Complete 43/16 array schema receipt')
        offered, admitted, successes = [count(rec[k], str(dest)+'/'+k) for k in ('offered', 'admitted', 'successes')]
        need(0 < offered and successes <= admitted <= offered, 'Offered/admitted/success hierarchy')
        need(count(rec['terminal_failures'], 'terminal_failures') == offered-admitted, 'Rejected denominator')
        categories = rec['outcome_counts']
        need(len(categories) == 9 and all(type(v) is int and v >= 0 for v in categories), 'Terminal outcome counts')
        need(categories[0] == 0 and categories[1] == successes and sum(categories[1:3]) == admitted
             and sum(categories) == offered, 'Terminal count conservation')
        summary = read_json(dest/'summary.json')
        need(summary['n_offered'] == summary['total_tasks'] == offered and summary['n_admitted'] == admitted,
             'Summary denominator/count binding')
        need(abs(finite(summary['completion'], 'completion')*offered-successes) < 1e-6
             and abs(finite(summary['completion_admitted'], 'completion_admitted')*max(admitted, 1)-successes) < 1e-6,
             'Summary success numerator reconstruction')
        summary_controls = dict(T=steps, maxN=tr['N'], n_rsus=tr['R'], fleet_seed=fleet,
            evaluator_seed=evaluator, rsu_lb=arm, rsu_max_concurrent=6220, enter_reset=tr['entry_channel_present'],
            reset_soc_on_enter=False, rsu_service_mult=1., rsu_backhaul_ms=0., k8s_scale='off',
            fleet='uk2030', lambda_arrival=1.5, rsu_cap_mode='reject', substep_queue='sequential',
            veh_queue_mode='conserved', substep_queue_iterations=3, k_max=5, obs_variant='onehot17', model='C')
        need(all(summary[k] == v for k, v in summary_controls.items()), 'Summary scientific controls')
        if arm == 'dla_p2c':
            need(rec['two_choice_replay']['status'] == 'passed'
                 and rec['two_choice_replay']['reconstructed_final_backlog'] == 'exact float32', 'P2C replay receipt')
        need(start['started_at'] == rec['started_at'], 'Start timestamp binding')
        need(timestamp(rec['started_at']) <= timestamp(rec['finished_at']), 'Reversed attempt times')
        for field in ('simulation_process_s', 'validation_s', 'total_wall_s'):
            need(finite(rec[field], field) >= 0, 'Negative wall time')
        row = dict(trace=trace, block=block, fleet_seed=fleet, evaluator_seed=evaluator,
                   arm=arm, offered=offered, admitted=admitted, successes=successes,
                   attainment_pct=100*successes/offered)
        return rec, row

    def chains(self, trace):
        folder = self.here/'evidence'/trace
        qsp, qp, esp = [folder/name for name in ('QUALIFICATION_SEAL.json', 'QUALIFICATION.json', 'EXECUTION_SEAL.json')]
        es = self.bound_json(esp)
        qs = self.bound_json(qsp, es['qualification_seal_sha256'])
        q = self.bound_json(qp, es['qualification_sha256'])
        need(es['authorised'] is True and es['trace'] == qs['trace'] == q['trace'] == trace,
             'Trace execution authority chain')
        need(es['full_attempts'] == 40 and es['paired_blocks'] == 8
             and es['new_full_outcomes_before_seal'] == 0 and es['output_root'] == str(self.raw/trace), 'Sealed full design')
        need(es['source_commit'] == qs['source_commit'] and es['sources'] == qs['sources'], 'Qualified source drift')
        self.sources(es)
        for seal in (qs, es):
            self.bind(self.here/'CONFIG.json', seal['config_sha256'])
            self.bind(self.here/'PROTOCOL.md', seal['protocol_sha256'])
        need(q['status'] == 'passed' and q['qualification_seal_sha256'] == self.bind(qsp)
             and q['short_attempts'] == qs['max_short_attempts'] == 6
             and q['shared_input_field_count'] == 14 and q['restart_array_count'] == 59, 'Qualification contract')
        need(set(q['restart']) == {'per_step.npz', 'per_task.npz'}
             and set(q['restart']['per_step.npz']) == STEP_FIELDS
             and set(q['restart']['per_task.npz']) == TASK_FIELDS
             and len(q['restart']['per_step.npz']) == 43 and len(q['restart']['per_task.npz']) == 16,
             'Complete restart field set')
        self.matched(q['within_trace'])
        review = self.bound_json(self.here/'evidence/SOURCE_REVIEW.json', es['review_sha256'])
        need(review['verdict'] == 'APPROVE' and review['source_commit'] == es['source_commit'], 'Exact-source review binding')
        need(isinstance(review.get('reviewer'), str) and review['reviewer'].strip(), 'Missing source reviewer identity')
        need(review.get('self_approved') is not True and review.get('independent') is not False
             and review.get('read_only') is not False, 'Source review explicitly lacks independence')
        if review.get('builder') is not None:
            need(review['reviewer'] != review['builder'], 'Builder self-approval claim')
        need(review['reviewer'] != '/root/preparation_audit', 'Arithmetic auditor cannot approve this source')
        need(qs['preflight']['runtime'] == es['preflight']['runtime']
             and qs['preflight']['python_sha256'] == es['preflight']['python_sha256']
             and qs['preflight']['numerical_environment'] == es['preflight']['numerical_environment'], 'Qualified runtime drift')
        need(es['preflight']['trace_sha256'] == TRACE_HASHES[trace], 'Preflight trace identity')
        runtime = es['preflight']['runtime']
        expected_runtime = dict(python='3.11.15', jax='0.4.30', jaxlib='0.4.30',
                                numpy='1.26.4', x64=False, devices=['TFRT_CPU_0'])
        need(all(runtime[k] == value for k, value in expected_runtime.items()), 'Pinned CPU runtime')
        self.bind(self.config['runtime']['python'], es['preflight']['python_sha256'])
        expected = {}
        for index, arm in enumerate(ARMS, 1):
            expected[self.raw/trace/'qualification'/f'{index:02d}_{arm}'/'attempt_001'] = (arm, 300)
        expected[self.raw/trace/'qualification/06_per_task_dla_prefix/attempt_001'] = ('per_task_dla', 150)
        need(set(q['attempt_receipts']) == {str(p/'VALIDATED.json') for p in expected}, 'Qualification attempt chain/set')
        need(set((self.raw/trace/'qualification').glob('*/attempt_*')) == set(expected), 'Extra/missing short attempts')
        original_hashes = None
        for dest, (arm, steps) in expected.items():
            self.bind(dest/'VALIDATED.json', q['attempt_receipts'][str(dest/'VALIDATED.json')])
            rec, _ = self.cell(dest, trace, 0, arm, steps, qsp, True)
            need(timestamp(qs['created_at']) <= timestamp(rec['started_at'])
                 <= timestamp(rec['finished_at']) <= timestamp(q['completed_at']), 'Qualification chronology')
            if steps == 300:
                if original_hashes is None:
                    original_hashes = rec['shared_input_hashes']
                need(rec['shared_input_hashes'] == original_hashes, 'Qualification cross-arm exogenous mismatch')
        need(timestamp(q['completed_at']) <= timestamp(es['sealed_at']), 'Seal precedes qualification completion')
        self.qualification[trace], self.seals[trace] = q, es

    def full_trace(self, trace):
        root = self.raw/trace
        folder = root/trace
        esp = self.here/'evidence'/trace/'EXECUTION_SEAL.json'
        sh = self.bind(esp)
        es = self.seals[trace]
        complete = self.bound_json(root/'COMPLETE.json')
        started = self.bound_json(root/'FULL_STARTED.json')
        need(complete['status'] == 'complete' and complete['trace'] == trace and complete['full_cells'] == 40
             and complete['seal_sha256'] == started['seal_sha256'] == sh, 'Trace completion chain')
        need(timestamp(es['sealed_at']) <= timestamp(started['started_at']) <= timestamp(complete['finished_at']), 'Full trace chronology')
        for q in self.qualification.values():
            need(timestamp(q['completed_at']) <= timestamp(started['started_at']), 'Full outcomes before all qualification decisions')
        need(finite(complete['wall_s'], 'trace wall_s') >= 0, 'Negative trace wall time')
        self.wall[trace] = complete['wall_s']
        expected_dirs = {folder/f'block_{block:02d}_{arm}' for block in range(8) for arm in ARMS}
        need(set(folder.glob('block_*')) == expected_dirs, 'Full cell directory set')
        need(set(folder.glob('BLOCK_*.json')) == {folder/f'BLOCK_{b:02d}.json' for b in range(8)}, 'Full block receipt set')
        previous_finish = timestamp(started['started_at'])
        for block in range(8):
            br = self.bound_json(folder/f'BLOCK_{block:02d}.json')
            order = list(ARMS[block % 5:] + ARMS[:block % 5])
            need(br['status'] == 'passed' and br['trace'] == trace and br['block'] == block
                 and br['fleet_seed'] == 100+block and br['evaluator_seed'] == 200+block
                 and br['arm_order'] == order and br['seal_sha256'] == sh
                 and set(br['cell_receipts']) == set(ARMS), 'Block identity/order/seeds')
            self.matched(br['within_trace'])
            shared = None
            for arm in order:
                dest = folder/f'block_{block:02d}_{arm}'/'attempt_001'
                self.bind(dest/'VALIDATED.json', br['cell_receipts'][arm])
                rec, row = self.cell(dest, trace, block, arm, DIMENSIONS[trace][0], esp, False)
                need(previous_finish <= timestamp(rec['started_at']), 'Trace execution is not serial/in declared order')
                previous_finish = timestamp(rec['finished_at'])
                need(previous_finish <= timestamp(complete['finished_at']), 'Completion precedes cell finish')
                if shared is None:
                    shared = rec['shared_input_hashes']
                need(rec['shared_input_hashes'] == shared, 'Block cross-arm exogenous mismatch')
                self.records[trace, block, arm], self.cells[trace, block, arm] = rec, row
        need(len(list(folder.glob('*/attempt_*'))) == 40, 'Full attempt budget')

    def analysis(self):
        from scipy.stats import t as student_t
        path = self.here/'ANALYSIS.json'
        analysis = self.bound_json(path)
        need(analysis['status'] == 'complete' and analysis['new_full_cells'] == 120, 'Analysis completeness')
        need(analysis['new_blocks'] == 24 and analysis['blocks_per_trace'] == 8
             and analysis['failures'] == 0, 'Analysis complete design counts')
        self.bind(self.here/'CONFIG.json', analysis['config_sha256'])
        need(set(analysis['execution_seal_sha256']) == set(TRACES), 'Analysis execution seal set')
        for trace in TRACES:
            self.bind(self.here/'evidence'/trace/'EXECUTION_SEAL.json', analysis['execution_seal_sha256'][trace])
            near(analysis['wall_s_per_trace'][trace], self.wall[trace], 'Analysis trace wall time')
        need(len(analysis['cells']) == 120 and len(analysis['contrasts']) == 15, 'Analysis row counts')
        saved = {}
        for row in analysis['cells']:
            need(set(row) == set(CELL_FIELDS), 'Saved cell schema')
            identity = row['trace'], count(row['block'], 'block'), row['arm']
            need(identity not in saved, 'Duplicate analysis cell')
            saved[identity] = row
        need(set(saved) == set(self.cells), 'Analysis cell set')
        for identity, expected in self.cells.items():
            row = saved[identity]
            for field in CELL_FIELDS:
                if field == 'attainment_pct':
                    near(row[field], expected[field], f'{identity}/{field}')
                else:
                    need(type(row[field]) is type(expected[field]) and row[field] == expected[field], 'Analysis cell binding: '+str(identity))
        need(set(analysis['arm_mean_attainment_pct']) == set(TRACES), 'Analysis arm mean trace set')
        for trace in TRACES:
            need(set(analysis['arm_mean_attainment_pct'][trace]) == set(ARMS), 'Analysis arm mean set')
            for arm in ARMS:
                near(analysis['arm_mean_attainment_pct'][trace][arm],
                     math.fsum(self.cells[trace,b,arm]['attainment_pct'] for b in range(8))/8,
                     'Equal-block-weight arm mean')
        contrasts = {}
        for row in analysis['contrasts']:
            identity = row['trace'], row['contrast']
            need(identity not in contrasts, 'Duplicate contrast')
            contrasts[identity] = row
        expected_set = {(tr, left+'_minus_'+right) for tr in TRACES for left, right in CONTRASTS}
        need(set(contrasts) == expected_set, 'Missing/extra contrasts')
        recomputed = []
        for trace in TRACES:
            for left, right in CONTRASTS:
                name = left+'_minus_'+right
                effects = [self.cells[trace,b,left]['attainment_pct']-self.cells[trace,b,right]['attainment_pct'] for b in range(8)]
                actual = contrasts[trace,name]
                need(len(actual['effects_pp']) == 8, 'Saved block effects count')
                for block, effect in enumerate(effects):
                    near(actual['effects_pp'][block], effect, f'{trace}/{name}/block{block}')
                independent = dict(trace=trace, contrast=name, effects_pp=effects)
                for kind, family in zip(INTERVAL_KINDS, (1,5,15)):
                    expected = interval(effects, family, student_t)
                    need(set(actual[kind]) == set(INTERVAL_FIELDS), 'Interval schema')
                    for field, value in expected.items():
                        if field in ('family_size','df','n_blocks'):
                            need(type(actual[kind][field]) is int and actual[kind][field] == value, 'Interval design '+field)
                        else:
                            near(actual[kind][field], value, f'{trace}/{name}/{kind}/{field}')
                    independent[kind] = expected
                recomputed.append(independent)
        self.csv_checks(recomputed)
        return recomputed

    def csv_checks(self, contrasts):
        # Deliverable CSVs are checked when present; ANALYSIS.json is mandatory.
        for filename in ('CELL_RESULTS.csv','PAIRED_EFFECTS.csv'):
            path = self.here/filename
            if not path.exists():
                continue
            self.bind(path)
            with path.open(newline='') as stream:
                reader = csv.DictReader(stream)
                names, rows = reader.fieldnames, list(reader)
            need(names is not None and len(names) == len(set(names)), 'Duplicate/missing CSV columns')
            need(all(None not in row and None not in row.values() for row in rows), 'Malformed CSV row')
            if filename == 'CELL_RESULTS.csv':
                need(set(names) == set(CELL_FIELDS) and len(rows) == 120, 'Cell CSV schema/count')
                expected = self.cells
                found = set()
                for row in rows:
                    identity = row['trace'], int(row['block']), row['arm']
                    need(identity not in found and identity in expected, 'Cell CSV duplicate/undeclared row')
                    found.add(identity)
                    for field in CELL_FIELDS:
                        value = expected[identity][field]
                        if field == 'attainment_pct':
                            near(float(row[field]), value, 'CSV attainment')
                        elif type(value) is int:
                            need(re.fullmatch(r'0|[1-9][0-9]*', row[field]) and int(row[field]) == value, 'CSV integer '+field)
                        else:
                            need(row[field] == value, 'CSV cell '+field)
            else:
                expected = {(r['trace'],r['contrast']):r for r in contrasts}
                columns = {'trace','contrast'} | {f'block_{b:02d}_effect_pp' for b in range(8)}
                columns |= {f'{kind}_{field}' for kind in INTERVAL_KINDS for field in INTERVAL_FIELDS}
                need(set(names) == columns and len(rows) == 15, 'Paired CSV schema/count')
                found = set()
                for row in rows:
                    identity = row['trace'], row['contrast']
                    need(identity not in found and identity in expected, 'Paired CSV duplicate/undeclared row')
                    found.add(identity)
                    for block, effect in enumerate(expected[identity]['effects_pp']):
                        near(float(row[f'block_{block:02d}_effect_pp']), effect, 'Paired CSV block effect')
                    for kind in INTERVAL_KINDS:
                        for field in INTERVAL_FIELDS:
                            near(float(row[kind+'_'+field]), expected[identity][kind][field], 'Paired CSV interval')

    def run(self):
        # Do not inspect outcomes until every trace and the declared analysis exist.
        required = [self.here/'CONFIG.json', self.here/'ANALYSIS.json', self.here/'evidence/SOURCE_REVIEW.json']
        required += [self.raw/t/'COMPLETE.json' for t in TRACES]
        required += [self.here/'evidence'/t/n for t in TRACES for n in
                     ('QUALIFICATION_SEAL.json','QUALIFICATION.json','EXECUTION_SEAL.json')]
        missing = [str(p) for p in required if not p.is_file()]
        if missing:
            return 2, dict(status='not_ready', missing=missing, outcomes_read=False)
        self.gate_passed = True
        failures = list(self.raw.rglob('FAILED.json')) + list((self.here/'evidence').rglob('STOPPED.json'))
        need(not failures, 'Retained campaign failures/stops: '+', '.join(map(str,failures)))
        self.design()
        for trace in TRACES:
            self.chains(trace)
        need(len({s['source_commit'] for s in self.seals.values()}) == 1, 'Trace source commits differ')
        need(all(s == self.source_sets[0] for s in self.source_sets), 'Trace source/configuration bindings differ')
        for trace in TRACES:
            self.full_trace(trace)
        need(len(self.cells) == 120, 'Total full cell count')
        contrasts = self.analysis()
        # Detect changes to small receipts/configuration during a long NPZ-hash audit.
        for path, expected in list(self.bindings.items()):
            if not path.endswith('.npz'):
                self.bind(path, expected)
        return 0, dict(status='passed', source_commit=self.seals['we']['source_commit'],
            new_full_cells_checked=120, qualification_attempts_checked=18, blocks_checked=24,
            contrasts_checked=15, output_files_rehashed=self.checked_outputs, failures=0,
            wall_seconds_per_trace=self.wall, independently_recomputed_contrasts=contrasts,
            bindings=self.bindings, outcomes_read=True,
            scope='Independent receipt/hash and counts-derived arithmetic audit; arrays not opened.',
            limitations=['Conservation and restart execution are checked through immutable validator receipts.',
                         'Source review identity/verdict is bound; its actual independence is not inferred from a label.',
                         'This result is not source approval or an Opus review.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    audit = Audit(args.checkout.expanduser().resolve(), args.raw.expanduser().resolve())
    try:
        code, result = audit.run()
    except FileNotFoundError as exc:
        code, result = 2, dict(status='not_ready', error=str(exc), outcomes_read=audit.gate_passed)
    except Exception as exc:
        code, result = 1, dict(status='failed', error=f'{type(exc).__name__}: {exc}', outcomes_read=audit.gate_passed)
    result.update(audit_identity='Codex independent arithmetic implementation, /root/preparation_audit',
                  auditor_script_sha256=digest(__file__), source_approval=False, opus_review=False,
                  scientific_workloads_launched=0, raw_files_modified=False)
    if args.output is not None:
        try:
            with args.output.expanduser().open('x') as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
                stream.write('\n')
        except OSError as exc:
            result['report_write_error'] = str(exc)
            code = 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
