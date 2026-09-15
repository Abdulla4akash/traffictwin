#!/usr/bin/env python3
"""Independent, read-only final analysis audit; no runner/evaluator imports.

Run with the campaign's pinned Python only after all full cells and analysis
exist. Arithmetic uses the standard library; scipy supplies only Student-t
critical values. No NPZ arrays are opened or scientific workloads launched.
The result is JSON on stdout. Failures return 1; incomplete prerequisites 2.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path


CHECKOUT = Path('/Users/akashx/scratch/traffictwin-followups-guarded-2026-09-15')
RAW = Path('/Users/akashx/Downloads/diss_mat/traffictwin-followups-raw-2026-09-15')
SOURCE = '5cbe568c9260c432f3e3ae42b45dcfba7f1a8dbe'
SEAL_HASH = '4ef9c00fd2211703e09a1a0b4ddb1b6ebffc724d27d0bb4604cb3a408d949d65'
BASELINE_HASH = '37a7f1d8aa628f2e74b98855ae8f7e461bc31d7bde6efd7989075d4038c1d482'
PROTOCOL_HASH = '68283ca97c24edadb31b177c0fd4b47b9a86b55eed1bd0ddf33e9ac95388ef52'
ANALYSE_HASH = '2bd83fad5a7f4b42be5253aab40dcc4497a713eadb289456fd2b46124cb28d0d'
TRACE_HASH = '896aa5ad646d0d6c643de49eaa84373c9442b2d58483ac0e39aab76619c29628'
ACTORS = {
    'original': '93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208',
    'ukfleet': 'b3eca1685245c59d1a3e86bd11ede887300bda1b00ba211a1913e467ad3f5183',
}
ARMS = ('ingress_dla', 'dla', 'per_task_dla', 'causal_round_robin')
DESIGN = {
    'baseline': (ARMS, 'original', 1.0),
    '07_two_choice': (('dla_p2c',), 'original', 1.0),
    '08_half_speed': (ARMS, 'original', 0.5),
    '09_second_actor': (ARMS, 'ukfleet', 1.0),
}
CELL_FIELDS = ['study', 'block', 'fleet_seed', 'evaluator_seed', 'arm',
               'reused_reference', 'offered', 'admitted', 'successes', 'attainment_pct']
INTERVAL_KINDS = ('individual95', 'study_family95', 'all_ten_family95')
INTERVAL_FIELDS = ('mean_pp', 'sd_pp', 'low_pp', 'high_pp', 'family_size', 'df', 'n_blocks')
COUNTS = ('offered', 'admitted', 'successes')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    # Repeated JSON members would make bindings ambiguous, so reject them.
    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out, 'Repeated JSON key: ' + key)
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def near(actual, expected, context):
    need(isinstance(actual, (int, float)) and not isinstance(actual, bool), context + ': nonnumeric')
    need(math.isfinite(actual) and math.isfinite(expected), context + ': nonfinite')
    need(math.isclose(actual, expected, rel_tol=0, abs_tol=5e-12),
         f'{context}: {actual!r} != {expected!r}')


def count(value, context):
    need(type(value) is int and value >= 0, context + ': expected a nonnegative integer')
    return value


def csv_integer(value, context):
    need(isinstance(value, str) and re.fullmatch(r'0|[1-9][0-9]*', value) is not None,
         context + ': expected integer text')
    return int(value)


def load_csv(path, expected_fields):
    with Path(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames == expected_fields, str(path) + ': CSV schema mismatch')
        rows = list(reader)
    need(all(set(row) == set(expected_fields) and None not in row.values() for row in rows),
         str(path) + ': malformed CSV row')
    return rows


def key(row):
    return row['study'], row['block'], row['arm']


def interval(values, family, student_t):
    need(len(values) == 8 and all(math.isfinite(x) for x in values), 'Expected eight finite block effects')
    mean = math.fsum(values) / 8
    sd = statistics.stdev(values)
    critical = float(student_t.ppf(1 - 0.05 / (2 * family), df=7))
    width = critical * sd / math.sqrt(8)
    return {'mean_pp': mean, 'sd_pp': sd, 'low_pp': mean - width,
            'high_pp': mean + width, 'family_size': family, 'df': 7, 'n_blocks': 8}


def audit(checkout, raw):
    evidence = checkout / 'docs/dissertation/followups_2026-09-15/evidence'
    # This gate precedes EVERY read of campaign outcomes or validation counts.
    required = [raw / 'COMPLETE.json', evidence / 'ANALYSIS.json']
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        return 2, {'status': 'not_ready', 'missing': missing,
                   'outcomes_read': False, 'reason': 'All 72 cells and final analysis are required.'}

    from scipy.stats import t as student_t

    seal_path = evidence / 'EXECUTION_SEAL.json'
    need(digest(seal_path) == SEAL_HASH, 'Execution seal identity changed')
    seal = read_json(seal_path)
    need(seal['source_commit'] == SOURCE and seal['full_attempts'] == 72
         and seal['paired_blocks'] == 8 and seal['output_root'] == str(raw), 'Sealed design identity')
    need(digest(evidence.parent / 'PROTOCOL.md') == PROTOCOL_HASH == seal['protocol_sha256'], 'Protocol identity')
    need(digest(evidence.parent / 'analyse.py') == ANALYSE_HASH, 'Analysis source identity')
    need(digest(evidence / 'BASELINE.json') == BASELINE_HASH == seal['baseline_ledger_sha256'], 'Baseline ledger identity')
    for filename, field in [('QUALIFICATION.json', 'qualification_sha256'), ('SOURCE_REVIEW.json', 'review_sha256')]:
        need(digest(evidence / filename) == seal[field], filename + ' seal binding')
    review = read_json(evidence / 'SOURCE_REVIEW.json')
    need(review['verdict'] == 'APPROVE' and review['source_commit'] == SOURCE, 'Exact source approval')
    complete = read_json(raw / 'COMPLETE.json')
    need(complete['status'] == 'complete' and complete['full_cells'] == 72
         and complete['seal_sha256'] == SEAL_HASH, 'Root completeness binding')
    analysis = read_json(evidence / 'ANALYSIS.json')
    need(analysis['status'] == 'complete' and analysis['execution_seal_sha256'] == SEAL_HASH
         and analysis['new_full_cells'] == 72 and analysis['reused_full_cells'] == 32
         and analysis['blocks_per_study'] == 8, 'Analysis completeness identity')
    ledger = read_json(evidence / 'BASELINE.json')
    need(ledger['status'] == 'passed', 'Baseline qualification status')
    expected = {(study, b, arm) for study, (arms, _, _) in DESIGN.items()
                for b in range(8) for arm in arms}
    need(len(expected) == 104 and set(ledger['records']) == {f'{b}:{a}' for b in range(8) for a in ARMS},
         'Historical design has extra/missing cells')

    csv_rows = load_csv(evidence / 'CELL_RESULTS.csv', CELL_FIELDS)
    need(len(csv_rows) == len(analysis['cells']) == 104, 'Expected exactly 104 cell rows')
    cells = {}
    for text_row in csv_rows:
        row = dict(text_row)
        for field in ('block', 'fleet_seed', 'evaluator_seed', *COUNTS):
            row[field] = csv_integer(row[field], 'CELL_RESULTS/' + field)
        need(row['reused_reference'] in ('True', 'False'), 'CSV reused_reference is not boolean')
        row['reused_reference'] = row['reused_reference'] == 'True'
        row['attainment_pct'] = float(row['attainment_pct'])
        identity = key(row)
        need(identity not in cells, 'Duplicate CSV cell ' + str(identity))
        cells[identity] = row
    need(set(cells) == expected, 'CSV cells differ from declared design')
    json_cells = {}
    for row in analysis['cells']:
        need(set(row) == set(CELL_FIELDS), 'ANALYSIS cell schema')
        for field in ('block', 'fleet_seed', 'evaluator_seed', *COUNTS):
            count(row[field], 'ANALYSIS/' + field)
        need(type(row['reused_reference']) is bool, 'ANALYSIS reused_reference is not boolean')
        identity = key(row)
        need(identity not in json_cells, 'Duplicate ANALYSIS cell')
        json_cells[identity] = row
    need(set(json_cells) == expected, 'ANALYSIS cells differ from declared design')
    for identity, row in cells.items():
        for field in CELL_FIELDS:
            if field == 'attainment_pct':
                near(json_cells[identity][field], row[field], str(identity) + '/' + field)
            else:
                need(json_cells[identity][field] == row[field], 'CSV/ANALYSIS cell mismatch ' + str(identity))

    records = {}
    receipt_bindings = {}
    wall_seconds = []
    for study, (arms, actor, service) in DESIGN.items():
        if study != 'baseline':
            condition_complete = read_json(raw / study / 'COMPLETE.json')
            need(condition_complete['status'] == 'complete' and condition_complete['study'] == study
                 and condition_complete['full_cells'] == 8 * len(arms)
                 and condition_complete['seal_sha256'] == SEAL_HASH, 'Study completion ' + study)
            need({p.name for p in (raw / study).glob('block_*')} == {f'block_{b:02d}_{a}' for b in range(8) for a in arms},
                 'Extra/missing new study cells ' + study)
        for block in range(8):
            if study != 'baseline':
                block_path = raw / study / f'BLOCK_{block:02d}.json'
                br = read_json(block_path)
                need(br['status'] == 'passed' and br['study'] == study and br['block'] == block
                     and br['seal_sha256'] == SEAL_HASH and set(br['cell_receipts']) == set(arms), 'Block receipt identity')
                receipt_bindings[str(block_path)] = digest(block_path)
            for arm in arms:
                identity = study, block, arm
                row = cells[identity]
                need(row['fleet_seed'] == 100 + block and row['evaluator_seed'] == 200 + block
                     and row['reused_reference'] == (study == 'baseline'), 'Cell seed/reference design')
                if study == 'baseline':
                    record = ledger['records'][f'{block}:{arm}']
                    dest = Path(record['configuration']['output'])
                    original = read_json(dest / 'VALIDATED.json')
                    need(digest(dest / 'VALIDATED.json') == ledger['bindings'][str(dest / 'VALIDATED.json')], 'Historical receipt hash')
                    need(original['configuration'] == record['configuration'] and original['status'] == 'passed'
                         and original['output_sha256'] == record['output_sha256'], 'Historical revalidation binding')
                    for field in COUNTS:
                        need(original[field] == record[field], 'Historical validated count mismatch')
                else:
                    dest = raw / study / f'block_{block:02d}_{arm}' / 'attempt_001'
                    need(list(dest.parent.glob('attempt_*')) == [dest], 'Extra new full attempt')
                    need(not (dest / 'FAILED.json').exists(), 'Failed full-cell attempt')
                    record = read_json(dest / 'VALIDATED.json')
                    need(digest(dest / 'VALIDATED.json') == br['cell_receipts'][arm], 'Block/cell receipt hash')
                    need(record['seal_sha256'] == SEAL_HASH, 'New receipt seal')
                    wall = record['total_wall_s']
                    need(isinstance(wall, (int, float)) and math.isfinite(wall) and wall >= 0, 'Invalid cell wall time')
                    wall_seconds.append(wall)
                    for category in ('within_condition', 'historical_matching'):
                        matched = br[category][arm]
                        need(matched['status'] == 'passed' and matched['exogenous_inputs'] == 'matched'
                             and matched['actions_forced'] is False, 'Matched-input block validation')
                    if study == '08_half_speed':
                        need(br['historical_matching'][arm]['service_activation'] ==
                             {'rsu_work': 'exactly doubled', 'local_work': 'unchanged'}, 'Half-speed activation receipt')
                    if study == '07_two_choice':
                        need(record['two_choice_replay']['status'] == 'passed'
                             and record['two_choice_replay']['reconstructed_final_backlog'] == 'exact float32', 'P2C replay receipt')
                need(record['status'] == 'passed', 'Cell validation status')
                cfg = record['configuration']
                need(read_json(dest / 'COMMAND.json') == cfg, 'Command/configuration binding')
                need(cfg['block'] == block and cfg['fleet_seed'] == 100 + block
                     and cfg['evaluator_seed'] == 200 + block and cfg['steps'] == 10800
                     and cfg['arm'] == arm and cfg['output'] == str(dest), 'Receipt cell design')
                need(cfg['inputs']['actor_sha256'] == ACTORS[actor]
                     and cfg['inputs']['trace_sha256'] == TRACE_HASH, 'Actor/trace identity')
                if study != 'baseline':
                    need(cfg['study'] == study and cfg['actor_id'] == actor
                         and cfg['service_mult'] == service and cfg['seal_sha256'] == SEAL_HASH, 'Intervention identity')
                need(set(record['output_sha256']) == {'summary.json', 'per_step.npz', 'per_task.npz'}, 'Output binding set')
                # Raw-array hashes were verified by campaign admission and the data audit.
                # This bounded analysis audit rehashes only the small summary/receipt files.
                need(digest(dest / 'summary.json') == record['output_sha256']['summary.json'], 'Summary digest')
                summary = read_json(dest / 'summary.json')
                for field in COUNTS:
                    count(record[field], 'Receipt/' + field)
                    need(row[field] == record[field], 'CSV count/receipt binding ' + str(identity))
                offered, admitted, successes = (row[f] for f in COUNTS)
                need(0 < offered and 0 <= successes <= admitted <= offered, 'Count denominator hierarchy')
                need(record['terminal_failures'] == offered - admitted, 'Rejected tasks missing from denominator')
                need(summary['n_offered'] == summary['total_tasks'] == offered
                     and summary['n_admitted'] == admitted, 'Summary offered/admitted denominator')
                need(abs(summary['completion'] * offered - successes) < 1e-6
                     and abs(summary['completion_admitted'] * max(admitted, 1) - successes) < 1e-6, 'Summary numerator reconstruction')
                near(row['attainment_pct'], 100 * successes / offered, 'CSV attainment denominator')
                need(summary['T'] == 10800 and summary['fleet_seed'] == 100 + block
                     and summary['evaluator_seed'] == 200 + block and summary['rsu_lb'] == arm
                     and summary['rsu_service_mult'] == service, 'Summary design controls')
                records[identity] = record
                receipt_bindings[str(dest / 'VALIDATED.json')] = digest(dest / 'VALIDATED.json')

    # Check exogenous matching without opening raw arrays or imposing action equality.
    for (study, block, arm), record in records.items():
        if study == 'baseline':
            continue
        reference_arm = arm if arm in ARMS else 'ingress_dla'
        historical = records['baseline', block, reference_arm]['shared_input_hashes']
        current = record['shared_input_hashes']
        need(set(historical) == set(current), 'Shared-input contract')
        for field in historical:
            if not (study == '08_half_speed' and field == 'task/task_rsu_service_ms'):
                need(historical[field] == current[field], 'Matched input differs: ' + field)

    scores = {identity: 100 * row['successes'] / row['offered'] for identity, row in cells.items()}
    def score(study, block, arm):
        return scores[study, block, arm]
    declared = []
    for name, left, right in [
        ('per_task_minus_two_choice', ('baseline', 'per_task_dla'), ('07_two_choice', 'dla_p2c')),
        ('two_choice_minus_ingress', ('07_two_choice', 'dla_p2c'), ('baseline', 'ingress_dla')),
        ('two_choice_minus_round_robin', ('07_two_choice', 'dla_p2c'), ('baseline', 'causal_round_robin')),
    ]:
        declared.append(('07_two_choice', name, 3,
                         [score(left[0], b, left[1]) - score(right[0], b, right[1]) for b in range(8)]))
    for study, family in [('08_half_speed', 4), ('09_second_actor', 3)]:
        for left, right in [('per_task_dla', 'ingress_dla'), ('dla', 'ingress_dla'), ('per_task_dla', 'causal_round_robin')]:
            declared.append((study, left + '_minus_' + right, family,
                             [score(study, b, left) - score(study, b, right) for b in range(8)]))
        if study == '08_half_speed':
            declared.append((study, 'change_in_per_task_minus_round_robin_gap', family, [
                (score(study, b, 'per_task_dla') - score(study, b, 'causal_round_robin'))
                - (score('baseline', b, 'per_task_dla') - score('baseline', b, 'causal_round_robin'))
                for b in range(8)]))
    need(len(declared) == len(analysis['contrasts']) == 10, 'Exactly ten declared contrasts required')
    analysis_contrasts = {(r['study'], r['contrast']): r for r in analysis['contrasts']}
    expected_contrasts = {(s, n) for s, n, _, _ in declared}
    need(set(analysis_contrasts) == expected_contrasts, 'Missing/duplicate/unplanned ANALYSIS contrasts')
    paired_fields = ['study', 'contrast'] + [f'{kind}_{field}' for kind in INTERVAL_KINDS for field in INTERVAL_FIELDS]
    paired_csv = load_csv(evidence / 'PAIRED_EFFECTS.csv', paired_fields)
    need(len(paired_csv) == 10, 'Expected ten paired CSV rows')
    paired = {(r['study'], r['contrast']): r for r in paired_csv}
    need(set(paired) == expected_contrasts, 'Missing/duplicate/unplanned paired CSV contrasts')
    recomputed = []
    for study, name, family, effects in declared:
        actual = analysis_contrasts[study, name]
        need(len(actual['effects_pp']) == 8, 'Expected eight saved paired effects')
        for block, expected_effect in enumerate(effects):
            near(actual['effects_pp'][block], expected_effect, f'{study}/{name}/block{block}')
        independent = {'study': study, 'contrast': name, 'effects_pp': effects}
        for kind, size in zip(INTERVAL_KINDS, (1, family, 10)):
            expected_interval = interval(effects, size, student_t)
            need(set(actual[kind]) == set(INTERVAL_FIELDS), 'Interval schema')
            for field, value in expected_interval.items():
                label = f'{study}/{name}/{kind}/{field}'
                near(actual[kind][field], value, 'ANALYSIS/' + label)
                near(float(paired[study, name][kind + '_' + field]), value, 'PAIRED_EFFECTS/' + label)
            independent[kind] = expected_interval
        recomputed.append(independent)
    need(set(analysis['arm_mean_attainment_pct']) == set(DESIGN), 'Mean study set')
    for study, (arms, _, _) in DESIGN.items():
        need(set(analysis['arm_mean_attainment_pct'][study]) == set(arms), 'Mean arm set')
        for arm in arms:
            near(analysis['arm_mean_attainment_pct'][study][arm],
                 math.fsum(score(study, b, arm) for b in range(8)) / 8,
                 'Equal-block-weight mean ' + study + '/' + arm)
    near(analysis['new_cell_wall_hours'], math.fsum(wall_seconds) / 3600, 'New-cell timing sum')
    return 0, {
        'status': 'passed', 'source_commit': SOURCE, 'execution_seal_sha256': SEAL_HASH,
        'root_complete_sha256': digest(raw / 'COMPLETE.json'),
        'analysis_sha256': digest(evidence / 'ANALYSIS.json'),
        'cell_results_csv_sha256': digest(evidence / 'CELL_RESULTS.csv'),
        'paired_effects_csv_sha256': digest(evidence / 'PAIRED_EFFECTS.csv'),
        'baseline_ledger_sha256': BASELINE_HASH, 'new_cells': 72, 'reused_cells': 32,
        'cell_rows_checked': 104, 'contrasts_checked': 10, 'block_effects_checked': 80,
        'interval_sets_checked': 30, 'df': 7, 'blocks_per_study': 8,
        'numeric_absolute_tolerance': 5e-12,
        'method': 'Receipt-bound offered denominators; standard-library fsum/stdev; scipy Student-t quantiles.',
        'raw_arrays_reopened': False, 'scientific_workloads_launched': 0,
        'receipt_bindings': receipt_bindings, 'independently_recomputed_contrasts': recomputed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, default=CHECKOUT)
    parser.add_argument('--raw', type=Path, default=RAW)
    args = parser.parse_args()
    try:
        code, result = audit(args.checkout, args.raw)
    except Exception as exc:
        code, result = 1, {'status': 'failed', 'error': type(exc).__name__ + ': ' + str(exc)}
    print(json.dumps(result, indent=2, allow_nan=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
