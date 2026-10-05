"""Render the completed Pi matrix from audited, committed-task aggregates."""
import os
import argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.local/matplotlib'))
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--corrected',action='store_true');args=parser.parse_args()
    data = json.loads((ROOT / ('records/corrected-efficiency-analysis.json' if args.corrected else 'records/efficiency-analysis.json')).read_text(encoding='utf-8'))
    methods = ['pi_none', 'pi_notepad', 'pi_jaccard']
    labels = ['No Memory', 'Notepad', 'Jaccard top-3']
    colors = ['#738397', '#17817a', '#cb7640']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.spines.top': False,
                        'axes.spines.right': False, 'axes.titleweight': 'bold',
                        'svg.fonttype': 'none', 'svg.hashsalt': 'clbench-pi-r1'})
    fig, axes = plt.subplots(2, 3, figsize=(13, 8))
    for row, env in enumerate(['database_exploration', 'codebase_adaptation']):
        stats = [next(s['stats'] for s in data['streams'] if s['method'] == m and s['environment'] == env) for m in methods]
        for col, (metric, title, scale) in enumerate([
            ('correct', 'Correct tasks', 1), ('actions', 'Official business actions', 1),
            ('total_tokens_known', 'Reported tokens (millions)', 1e6),
        ]):
            ax = axes[row, col]
            values = [s[metric] / scale for s in stats]
            bars = ax.bar(labels, values, color=colors, width=.63)
            ax.set_ylim(0, max(values) * 1.24)
            ax.set_title(title)
            ax.grid(axis='y', alpha=.15)
            ax.set_axisbelow(True)
            for i, (bar, value) in enumerate(zip(bars, values)):
                label = f'{value:.3f}' if scale > 1 else str(int(value))
                if metric == 'correct': label += '/40' if row == 0 else '/19'
                if metric == 'total_tokens_known' and stats[i]['total_tokens_unknown_attempts']: label += '*'
                ax.text(bar.get_x() + bar.get_width()/2, value + max(values)*.025, label, ha='center', fontsize=11)
            if col == 0: ax.set_ylabel('Database' if row == 0 else 'Codebase', fontweight='bold')
    fig.suptitle('CL-Bench | Pi system comparison | GLM-5.3-Flash high | R=1', fontsize=16, y=.98)
    notice=('Three Codebase targets use authorized reruns with 64k output; other results retain their original budgets.\n'
            if args.corrected else 'Codebase has 3 extra recovery notices; full rows are descriptive, pending the protocol decision.\n')
    fig.text(.055, .02, notice+
             '* One failed No Memory Codebase HTTP attempt has unknown usage. Tokens shown are reported sums.\n'
             '177 completed tasks; fresh session per task; independent memory per environment. No causal or stable-ranking claim.', fontsize=10)
    fig.tight_layout(rect=(0, .10, 1, .95))
    target = ROOT / 'figures'; target.mkdir(exist_ok=True)
    stem='pi-comparison-corrected' if args.corrected else 'pi-comparison'
    fig.savefig(target / f'{stem}.png', dpi=180)
    svg = target / f'{stem}.svg'
    fig.savefig(svg, metadata={'Date': None})
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    plt.close(fig)
    print(str(target / f'{stem}.png'))


if __name__ == '__main__': main()
