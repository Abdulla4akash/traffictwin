"""Render the validated, predeclared effects; performs no new inference."""
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / 'ANALYSIS.json').read_text())
assert data['status'] == 'complete' and data['new_full_cells'] == 72
titles = {
    '07_two_choice': '7  |  Native two-choice comparison',
    '08_half_speed': '8  |  Half-speed servers',
    '09_second_actor': '9  |  UK-fleet-trained second actor',
}
labels = {
    'per_task_minus_two_choice': 'Per-task − two-choice',
    'two_choice_minus_ingress': 'Two-choice − ingress',
    'two_choice_minus_round_robin': 'Two-choice − round-robin',
    'per_task_dla_minus_ingress_dla': 'Per-task − ingress',
    'dla_minus_ingress_dla': 'Common-target − ingress',
    'per_task_dla_minus_causal_round_robin': 'Per-task − round-robin',
    'change_in_per_task_minus_round_robin_gap': 'Change in per-task/RR gap*',
}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.spines.left': False, 'savefig.facecolor': 'white'})
fig, axes = plt.subplots(3, 1, figsize=(11.5, 10), gridspec_kw={'height_ratios': [3, 4, 3]})
for ax, (study, title), color in zip(axes, titles.items(), ['#18587A', '#14756B', '#66518A']):
    rows = [c for c in data['contrasts'] if c['study'] == study]
    intervals = [r['all_ten_family95'] for r in rows]
    means = np.array([r['mean_pp'] for r in intervals])
    lows = np.array([r['low_pp'] for r in intervals])
    highs = np.array([r['high_pp'] for r in intervals])
    positions = np.arange(len(rows))[::-1]
    ax.axvline(0, color='#818A91', lw=.9, ls='--', zorder=0)
    ax.errorbar(means, positions, xerr=np.vstack([means-lows, highs-means]),
                fmt='o', markersize=6, color=color, elinewidth=1.7, capsize=4)
    ax.set_yticks(positions, [labels[r['contrast']] for r in rows])
    ax.tick_params(axis='y', length=0, pad=12)
    ax.set_ylim(-.7, len(rows)-.3)
    ax.set_title(title, loc='left', fontweight='bold', fontsize=12, pad=12)
    ax.set_xlabel('Difference in deadline attainment (percentage points)', fontsize=9)
    ax.xaxis.grid(True, color='#E8EBED', linewidth=.7)
    ax.set_axisbelow(True)
    xmin, xmax = min(0., float(lows.min())), max(0., float(highs.max()))
    span = max(xmax-xmin, .1)
    ax.set_xlim(xmin-.12*span, xmax+.12*span)
    for y, r in zip(positions, intervals):
        ax.text(1.04, y, f"{r['mean_pp']:+.3f}  [{r['low_pp']:+.3f}, {r['high_pp']:+.3f}]",
                transform=ax.get_yaxis_transform(), va='center', fontsize=9,
                fontfamily='DejaVu Sans Mono', color='#27333B')
fig.suptitle('Three dissertation follow-up studies', x=.025, y=.985,
             ha='left', fontsize=18, fontweight='bold', color='#142C3B')
fig.text(.025, .948, 'Eight matched blocks per study · 72 new full runs · 32 reused controls', fontsize=11)
fig.text(.025, .922, 'Dots: mean paired differences. Bars: 95% intervals adjusted across all ten new contrasts.', fontsize=9, color='#46555F')
fig.subplots_adjust(left=.275, right=.69, top=.86, bottom=.12, hspace=.85)
fig.text(.025, .055, '* Half-speed per-task/round-robin gap minus its normal-speed gap. Each panel has its own x-axis scale.', fontsize=9)
fig.text(.025, .032, 'These follow-ups reuse previously examined seed blocks. The second actor shares the original training seed.', fontsize=9, color='#46555F')
fig.savefig(HERE / 'RESULTS_CHART.png', dpi=180)
fig.savefig(HERE / 'RESULTS_CHART.svg')
print(HERE / 'RESULTS_CHART.png')
