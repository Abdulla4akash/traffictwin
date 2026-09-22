"""Publication figures rendered only from sealed analysis and descriptive points."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
NAMES = {'we': '10 | Weekend', 'wd_pm': '11 | PM peak', 'ev': '12 | Event night'}
COLORS = {'we': '#1c6281', 'wd_pm': '#17847a', 'ev': '#75609a'}
LABELS = {'per_task_dla_minus_ingress_dla': 'Per-task − ingress',
          'dla_minus_ingress_dla': 'Common-target − ingress',
          'per_task_dla_minus_causal_round_robin': 'Per-task − round-robin',
          'per_task_dla_minus_dla_p2c': 'Per-task − two-choice',
          'dla_p2c_minus_causal_round_robin': 'Two-choice − round-robin'}


def main():
    data = json.loads((HERE / 'ANALYSIS.json').read_text())
    assert data['status'] == 'complete' and len(data['contrasts']) == 15
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(3, 1, figsize=(14, 14))
    fig.subplots_adjust(left=.27, right=.72, top=.87, bottom=.085, hspace=.65)
    fig.text(.03, .969, 'Three-trace generalisation study', fontsize=23, weight='bold', color='#193341')
    fig.text(.03, .94, 'Eight paired blocks per trace · 120 full cells · five scheduler arms', fontsize=14)
    fig.text(.03, .909, 'Dots: mean differences. Bars: 95% intervals adjusted across all 15 new contrasts.', color='#53646e')
    for ax, trace in zip(axes, NAMES):
        rows = [row for row in data['contrasts'] if row['trace'] == trace]
        means = np.array([row['all_fifteen_family95']['mean_pp'] for row in rows])
        lows = np.array([row['all_fifteen_family95']['low_pp'] for row in rows])
        highs = np.array([row['all_fifteen_family95']['high_pp'] for row in rows])
        y = np.arange(5)
        ax.errorbar(means, y, xerr=[means-lows, highs-means], fmt='o', color=COLORS[trace],
                    capsize=5, markersize=7, linewidth=2)
        ax.axvline(0, linestyle='--', color='#aebac3', linewidth=1, zorder=0)
        ax.set_yticks(y, [LABELS[row['contrast']] for row in rows])
        ax.set_ylim(4.7, -.7)
        ax.set_title(NAMES[trace], loc='left', pad=16, weight='bold', fontsize=15)
        ax.set_xlabel('Difference in deadline attainment (percentage points)')
        ax.grid(axis='x', color='#e6ebef', zorder=0)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y', length=0, pad=12)
        for idx, row in enumerate(rows):
            val = row['all_fifteen_family95']
            ax.text(1.04, idx, f"{val['mean_pp']:+.3f}  [{val['low_pp']:+.3f}, {val['high_pp']:+.3f}]",
                    transform=ax.get_yaxis_transform(), va='center', family='monospace', fontsize=10)
    fig.text(.03, .034, 'Each panel has its own x scale. PM and event retain the legacy mask-only queue convention.', fontsize=10)
    fig.text(.03, .016, 'Conditional trace-specific comparisons; no pooling or cross-trace test.', color='#53646e', fontsize=10)
    for ext in ['png', 'svg']:
        fig.savefig(HERE / f'RESULTS_CHART.{ext}', dpi=180, facecolor='white')
    plt.close(fig)

    points = json.loads((HERE / 'DENSITY_POINTS.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.7), sharex=True)
    fig.subplots_adjust(left=.075, right=.96, top=.79, bottom=.23, wspace=.25)
    for ax, contrast in zip(axes, ['per_task_dla_minus_ingress_dla', 'per_task_dla_minus_causal_round_robin']):
        for point in points:
            if point['contrast'] != contrast or point['mean_pp'] is None:
                continue
            trace = point['trace']; x = point['mean_active_vehicles_per_second']; y = point['mean_pp']
            ax.scatter(x, y, s=65, marker='s' if point['status'] == 'archived_descriptive' else 'o',
                       color=COLORS.get(trace, '#526571'), zorder=3)
            # Label offsets distinguish the nearby event/weekend points.
            offset = {'ev': (-6, -20), 'we': (-6, 10), 'wd_pm': (7, 1), 'wd_am': (7, 1), 'inc': (-30, 9)}[trace]
            ax.annotate(trace, (x, y), xytext=offset, textcoords='offset points', fontsize=10)
        ax.axhline(0, color='#aebac3', linestyle='--', linewidth=1)
        ax.set_title(LABELS[contrast], weight='bold')
        ax.set_xscale('log')
        ax.set_xlabel('Mean active vehicles per second (log scale)')
        ax.set_ylabel('Mean paired margin (percentage points)')
        ax.grid(color='#e9edf0')
    fig.suptitle('Scheduler margins across five Manchester scenarios', x=.075, ha='left', fontsize=18, weight='bold', color='#193341')
    fig.text(.075, .855, 'Descriptive only · circles: new traces · squares: archived values · no fitted trend or cross-trace test', fontsize=11)
    fig.text(.075, .115, 'Incident round-robin is unavailable in E2c/E2d; no point is imputed. Incident uses four fleet draws; other traces use eight paired blocks.', fontsize=9)
    fig.text(.075, .068, 'Density is not isolated: RSU count, queue-entry convention, trace duration and slot assignment also vary.', fontsize=10, color='#53646e')
    for ext in ['png', 'svg']:
        fig.savefig(HERE / f'DENSITY_PLOT.{ext}', dpi=180, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
