"""Five declared paired contrasts per trace; no evaluator execution."""
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import t

import runner as r


def interval(values, family):
    values = np.asarray(values, dtype=float)
    if values.shape != (8,) or not np.isfinite(values).all():
        raise ValueError('Exactly eight finite paired effects required')
    mean = float(values.mean()); sd = float(values.std(ddof=1))
    half = float(t.ppf(1 - .05 / (2 * family), 7)) * sd / math.sqrt(8)
    return {'mean_pp': mean, 'sd_pp': sd, 'low_pp': mean - half, 'high_pp': mean + half,
            'family_size': family, 'df': 7, 'n_blocks': 8}


def calculate():
    rows = []; scores = {}; timings = {}; seals = {}
    for trace in r.DESIGN['traces']:
        r.select(trace); r.require_complete()
        complete = r.load(r.RAW / 'COMPLETE.json')
        r.need(complete['status'] == 'complete' and complete['full_cells'] == 40, 'Trace incomplete')
        sp = r.EVIDENCE / 'EXECUTION_SEAL.json'
        seals[trace] = r.sha(sp); timings[trace] = complete['wall_s']; scores[trace] = {}
        for block in range(8):
            scores[trace][block] = {}
            for arm in r.ARMS:
                c = r.config(trace, block, arm, sp)
                record = r.load(Path(c['output']) / 'VALIDATED.json')
                score = 100 * record['successes'] / record['offered']
                scores[trace][block][arm] = score
                rows.append({'trace': trace, 'block': block, 'fleet_seed': 100 + block,
                             'evaluator_seed': 200 + block, 'arm': arm,
                             'offered': record['offered'], 'admitted': record['admitted'],
                             'successes': record['successes'], 'attainment_pct': score})
    contrasts = []
    for trace in r.DESIGN['traces']:
        for left, right in r.DESIGN['analysis']['contrasts']:
            effects = [scores[trace][b][left] - scores[trace][b][right] for b in range(8)]
            contrasts.append({'trace': trace, 'contrast': left + '_minus_' + right,
                              'effects_pp': effects, 'individual95': interval(effects, 1),
                              'trace_family95': interval(effects, 5),
                              'all_fifteen_family95': interval(effects, 15)})
    r.need(len(rows) == 120 and len(contrasts) == 15, 'Analysis design mismatch')
    means = {trace: {arm: float(np.mean([scores[trace][b][arm] for b in range(8)]))
                     for arm in r.ARMS} for trace in r.DESIGN['traces']}
    return {'status': 'complete', 'new_full_cells': 120, 'new_blocks': 24,
            'blocks_per_trace': 8, 'execution_seal_sha256': seals,
            'config_sha256': r.sha(r.HERE / 'CONFIG.json'), 'cells': rows,
            'contrasts': contrasts, 'arm_mean_attainment_pct': means,
            'wall_s_per_trace': timings, 'failures': 0,
            'scope': 'Conditional trace-specific paired block inference; no pooling or task-level tests.'}


def save_csv(path, rows):
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def descriptive_baseline():
    """Read archived points only; preserve absent incident round-robin evidence."""
    inventory = r.load(r.HERE / 'TRACE_INVENTORY.json')
    morning_file = r.OLD / 'evidence/CELL_RESULTS.csv'
    incident_file = r.ROOT / 'docs/evaluation/vec_followup_2026-09-07/historical_e0_e2d/experiments/E2d/data/e2d_paired_results.csv'
    with morning_file.open() as stream:
        morning = list(csv.DictReader(stream))
    with incident_file.open() as stream:
        incident = list(csv.DictReader(stream))
    r.need(len(morning) == 32 and len(incident) == 4, 'Archived design changed')
    scores = {(int(row['block']), row['arm']): 100 * int(row['successes']) / int(row['offered']) for row in morning}
    candidates = inventory['candidates']
    inc = next(x for x in candidates if x['path'].endswith('trace_inc_fullrsu.npz'))
    am = next(x for x in candidates if x['path'].endswith('trace_wd_am_wdrsu.npz'))
    result = []
    for trace, density, left, right, values, source in [
        ('inc', inc, 'per_task_dla', 'ingress_dla',
         [100 * float(row['per_task_minus_ingress']) for row in incident], incident_file),
        ('wd_am', am, 'per_task_dla', 'ingress_dla',
         [scores[b, 'per_task_dla'] - scores[b, 'ingress_dla'] for b in range(8)], morning_file),
        ('wd_am', am, 'per_task_dla', 'causal_round_robin',
         [scores[b, 'per_task_dla'] - scores[b, 'causal_round_robin'] for b in range(8)], morning_file),
    ]:
        result.append({'trace': trace, 'contrast': left + '_minus_' + right,
                       'mean_active_vehicles_per_second': density['mean_active_vehicles_per_second'],
                       'mean_pp': float(np.mean(values)), 'effects_pp': values,
                       'n_blocks': len(values), 'status': 'archived_descriptive',
                       'source_path': str(source.relative_to(r.ROOT)), 'source_sha256': r.sha(source),
                       'trace_sha256': density['sha256'], 'R': density['R'],
                       'entry_channel_present': density['entry_channel_present']})
    result.append({'trace': 'inc', 'contrast': 'per_task_dla_minus_causal_round_robin',
                   'mean_active_vehicles_per_second': inc['mean_active_vehicles_per_second'],
                   'mean_pp': None, 'status': 'unavailable',
                   'reason': 'E2c/E2d did not include a round-robin arm; no new incident run authorised.'})
    return result


def save_reports(data):
    lines = ['# Three-trace generalisation results', '',
             'All 120 full cells and 24 blocks passed, following 18 qualification attempts. No failures or retries. The design was proposed by Claude and authorised by the owner. These are paper-study results; no manuscript was edited.', '',
             '## Scenarios and timing', '',
             '| Trace | N | R | Entry channel | Elapsed hours |', '|---|---:|---:|---|---:|']
    for trace, cfg in r.DESIGN['traces'].items():
        lines.append(f"| {trace} | {cfg['N']} | {cfg['R']} | {cfg['entry_channel_present']} | {data['wall_s_per_trace'][trace]/3600:.3f} |")
    lines += ['', 'Trace elapsed times include serial cells and validation and may overlap across traces.', '',
              '## Deadline attainment', '', '| Trace | Arm | Mean attainment (%) |', '|---|---|---:|']
    for trace, means in data['arm_mean_attainment_pct'].items():
        for arm, mean in means.items():
            lines.append(f'| {trace} | {arm} | {mean:.6f} |')
    lines += ['', '## All declared contrasts', '',
              'Percentage-point differences from eight equally weighted paired blocks; Student-t, df=7. Positive values favour the first arm. The last column adjusts for all 15 new contrasts.', '',
              '| Trace | Contrast | Mean | Individual 95% | Within-trace 95% | All-15 95% |',
              '|---|---|---:|---|---|---|']
    findings = ['# Findings', '', 'All statements below use the predeclared all-15 simultaneous intervals. They are conditional on the selected traces, actor and seed-block model.', '']
    for row in data['contrasts']:
        intervals = [row[key] for key in ['individual95', 'trace_family95', 'all_fifteen_family95']]
        labels = [f"[{x['low_pp']:+.6f}, {x['high_pp']:+.6f}]" for x in intervals]
        lines.append(f"| {row['trace']} | {row['contrast']} | {intervals[0]['mean_pp']:+.6f} | {' | '.join(labels)} |")
        overall = intervals[-1]
        result = ('positive under the all-15 interval' if overall['low_pp'] > 0 else
                  'negative under the all-15 interval' if overall['high_pp'] < 0 else
                  'inconclusive; the all-15 interval includes zero')
        findings.append(f"- **{row['trace']} / {row['contrast']}**: {overall['mean_pp']:+.4f} pp, {labels[-1]}; {result}.")
    boundaries = ['The primary denominator is all offered tasks, including rejected tasks.',
                  'PM and event use legacy mask-only entry conventions; immediate slot reuse can carry vehicle queue backlog. Weekend and morning have explicit entry resets.',
                  'RSU counts, trace density, slot assignment and queue convention differ by scenario. The descriptive density plot cannot isolate a density effect.',
                  'Incident E2c/E2d contribute four archived fleet draws; morning contributes eight joint-seed blocks. Incident round-robin is unavailable and is not imputed.',
                  'No trace pooling, cross-trace tests, task-level tests, equivalence claims, seed replacements or outcome-based exclusions were used.',
                  'Frozen actor weights do not imply identical observations, logits or actions; matched exogenous inputs and conservation are checked separately.',
                  'Native two-choice and per-task placement differ in candidate sampling and reservation visibility; this is a comparison of complete implementations.']
    lines += ['', '## Limits', ''] + ['- ' + item for item in boundaries]
    findings += ['', '## Interpretation limits', ''] + ['- ' + item for item in boundaries]
    for name, content in [('RESULTS.md', lines), ('FINDINGS.md', findings)]:
        with (r.HERE / name).open('x') as stream:
            stream.write('\n'.join(content) + '\n')


def main():
    data = calculate()
    r.write_once(r.HERE / 'ANALYSIS.json', data)
    save_csv(r.HERE / 'CELL_RESULTS.csv', data['cells'])
    flat = []
    for row in data['contrasts']:
        flat.append({'trace': row['trace'], 'contrast': row['contrast'],
                     **{f'block_{b:02d}_effect_pp': v for b, v in enumerate(row['effects_pp'])},
                     **{f'{kind}_{key}': value for kind in ['individual95', 'trace_family95', 'all_fifteen_family95']
                        for key, value in row[kind].items()}})
    save_csv(r.HERE / 'PAIRED_EFFECTS.csv', flat)
    density = descriptive_baseline()
    for row in data['contrasts']:
        if row['contrast'] in ['per_task_dla_minus_ingress_dla', 'per_task_dla_minus_causal_round_robin']:
            cfg = r.DESIGN['traces'][row['trace']]
            density.append({'trace': row['trace'], 'contrast': row['contrast'],
                            'mean_active_vehicles_per_second': cfg['mean_active_vehicles_per_second'],
                            'mean_pp': row['individual95']['mean_pp'], 'n_blocks': 8,
                            'effects_pp': row['effects_pp'], 'status': 'new_descriptive',
                            'trace_sha256': cfg['sha256'], 'R': cfg['R'],
                            'entry_channel_present': cfg['entry_channel_present']})
    r.write_once(r.HERE / 'DENSITY_POINTS.json', density)
    save_reports(data)
    print(json.dumps({'status': data['status'], 'cells': 120, 'contrasts': 15}))


if __name__ == '__main__':
    main()
