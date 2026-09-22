"""The ten declared paired contrasts; no evaluator execution or selection."""
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import t

from runner import ARMS, EVIDENCE, RAW, STUDIES, baseline, config, load, require_complete, sha, write_once


def interval(values, family):
    values = np.asarray(values, dtype=float)
    if values.shape != (8,) or not np.isfinite(values).all():
        raise ValueError('Exactly eight finite paired effects required')
    mean = float(values.mean()); sd = float(values.std(ddof=1))
    half = float(t.ppf(1 - .05 / (2 * family), 7)) * sd / math.sqrt(8)
    return {'mean_pp': mean, 'sd_pp': sd, 'low_pp': mean - half, 'high_pp': mean + half,
            'family_size': family, 'df': 7, 'n_blocks': 8}


def contrast(study, name, values, family):
    return {'study': study, 'contrast': name, 'effects_pp': list(map(float, values)),
            'individual95': interval(values, 1), 'study_family95': interval(values, family),
            'all_ten_family95': interval(values, 10)}


def calculate():
    require_complete()
    historical = baseline()['records']; rows = []; scores = {}; timings = []
    for study, condition in {'baseline': {'arms': ARMS}, **STUDIES}.items():
        scores[study] = {}
        for block in range(8):
            scores[study][block] = {}
            for arm in condition['arms']:
                if study == 'baseline':
                    record = historical[f'{block}:{arm}']
                else:
                    c = config(study, block, arm, EVIDENCE / 'EXECUTION_SEAL.json')
                    record = load(Path(c['output']) / 'VALIDATED.json')
                    timings.append(record['total_wall_s'])
                score = 100 * record['successes'] / record['offered']
                scores[study][block][arm] = score
                rows.append({'study': study, 'block': block, 'fleet_seed': block + 100,
                             'evaluator_seed': block + 200, 'arm': arm, 'reused_reference': study == 'baseline',
                             'offered': record['offered'], 'admitted': record['admitted'],
                             'successes': record['successes'], 'attainment_pct': score})
    contrasts = []
    for name, left, right in [
        ('per_task_minus_two_choice', ('baseline', 'per_task_dla'), ('07_two_choice', 'dla_p2c')),
        ('two_choice_minus_ingress', ('07_two_choice', 'dla_p2c'), ('baseline', 'ingress_dla')),
        ('two_choice_minus_round_robin', ('07_two_choice', 'dla_p2c'), ('baseline', 'causal_round_robin')),
    ]:
        contrasts.append(contrast('07_two_choice', name,
                                  [scores[left[0]][b][left[1]] - scores[right[0]][b][right[1]] for b in range(8)], 3))
    for study, family in [('08_half_speed', 4), ('09_second_actor', 3)]:
        for left, right in [('per_task_dla', 'ingress_dla'), ('dla', 'ingress_dla'), ('per_task_dla', 'causal_round_robin')]:
            contrasts.append(contrast(study, left + '_minus_' + right,
                                      [scores[study][b][left] - scores[study][b][right] for b in range(8)], family))
        if study == '08_half_speed':
            changes = [(scores[study][b]['per_task_dla'] - scores[study][b]['causal_round_robin'])
                       - (scores['baseline'][b]['per_task_dla'] - scores['baseline'][b]['causal_round_robin']) for b in range(8)]
            contrasts.append(contrast(study, 'change_in_per_task_minus_round_robin_gap', changes, 4))
    assert len(contrasts) == 10
    means = {study: {arm: float(np.mean([scores[study][b][arm] for b in range(8)])) for arm in condition['arms']}
             for study, condition in {'baseline': {'arms': ARMS}, **STUDIES}.items()}
    return {'status': 'complete', 'execution_seal_sha256': sha(EVIDENCE / 'EXECUTION_SEAL.json'),
            'new_full_cells': 72, 'reused_full_cells': 32, 'blocks_per_study': 8,
            'cells': rows, 'contrasts': contrasts, 'arm_mean_attainment_pct': means,
            'new_cell_wall_hours': sum(timings) / 3600,
            'scope': 'Three follow-ups on the same previously examined blocks; outside original sealed family; no task-level inference.'}


def save_csv(path, rows):
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def report(data):
    lines = ['# Dissertation follow-up results — 15 September 2026', '',
             'All 72 new full cells completed with eight matched blocks per study. The 32 historical controls were reused after identity and raw-accounting verification.', '',
             '## Deadline attainment', '',
             '| Condition | Policy | Mean attainment (%) |', '|---|---|---:|']
    for study, arms in data['arm_mean_attainment_pct'].items():
        for arm, value in arms.items():
            lines.append(f'| {study} | {arm} | {value:.4f} |')
    lines += ['', '## Declared paired contrasts', '',
              'Differences are percentage points. Positive values favour the first policy. The final interval adjusts across all ten new contrasts; the CSV/JSON also retains individual and within-study intervals.', '',
              '| Study | Contrast | Mean difference | Within-study 95% interval | All-ten 95% interval |',
              '|---|---|---:|---|---|']
    for row in data['contrasts']:
        a, b = row['study_family95'], row['all_ten_family95']
        lines.append(f"| {row['study']} | {row['contrast']} | {a['mean_pp']:+.4f} | [{a['low_pp']:+.4f}, {a['high_pp']:+.4f}] | [{b['low_pp']:+.4f}, {b['high_pp']:+.4f}] |")
    lines += ['', '## Interpretation boundaries', '',
              '- These are follow-ups on the existing eight seed pairs, outside the original sealed confirmation family. They do not add independent traces or independent training seeds.',
              '- Native two-choice samples with replacement from the substep backlog snapshot. Its comparison with causal per-task placement includes differences in reservation visibility.',
              '- Half-speed changes RSU service capacity; the declared difference-in-differences tests whether the per-task/round-robin gap grows.',
              '- The second actor was trained on a different fleet distribution with the same training seed. This is a bounded actor sensitivity test.',
              '- Actor weights are frozen within each comparison; endogenous action differences are allowed and recorded.',
              '- Intervals assume independent approximately normal block effects and remain conditional on the selected trace/model. An interval crossing zero is inconclusive, not proof of equivalence.',
              '', '## Evidence', '',
              '- `ANALYSIS.json`: exact block effects, all interval families and arm means.',
              '- `CELL_RESULTS.csv`: all 72 new and 32 reused cells, with offered denominators.',
              '- `PAIRED_EFFECTS.csv`: the ten predeclared contrasts.',
              '- `PROTOCOL.md`, execution seal, qualification and validation receipts: design and provenance.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    result = calculate()
    write_once(EVIDENCE / 'ANALYSIS.json', result)
    save_csv(EVIDENCE / 'CELL_RESULTS.csv', result['cells'])
    flat = []
    for c in result['contrasts']:
        flat.append({'study': c['study'], 'contrast': c['contrast'],
                     **{f'{kind}_{k}': v for kind in ['individual95', 'study_family95', 'all_ten_family95'] for k, v in c[kind].items()}})
    save_csv(EVIDENCE / 'PAIRED_EFFECTS.csv', flat)
    with (EVIDENCE.parent / 'RESULTS.md').open('x') as stream:
        stream.write(report(result))
    print(json.dumps({'status': result['status'], 'cells': result['new_full_cells'], 'contrasts': result['contrasts']}, indent=2))
