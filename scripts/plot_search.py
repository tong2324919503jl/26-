"""Optional local benchmark figure (requires matplotlib; not needed to solve)."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main():
    colors = {'development':'#2b6cb0','holdout':'#2f855a','stress':'#c05621'}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for row, problem in enumerate((3,4)):
        folder = ROOT/f'problem{problem}/results'
        data = json.loads((folder/'benchmark_development.json').read_text(encoding='utf-8'))
        variants = ('baseline','adaptive','optical')
        values = [data['summary'][s]['mean_average_clear_time_s'] for s in variants]
        ax = axes[row,0]
        bars = ax.bar(variants, values, color=['#a0aec0','#2b6cb0','#718096'], width=.62)
        for b,v in zip(bars,values):
            ax.text(b.get_x()+b.get_width()/2,v+12,f'{v:.1f}',ha='center',fontsize=10)
        ax.set_ylim(0,max(values)*1.2)
        ax.set_ylabel('Mean virtual seconds / cleared source')
        ax.set_title(f'Problem {problem}: 96 matched development cases')
        ax.yaxis.grid(alpha=.2); ax.set_axisbelow(True)
        ax = axes[row,1]
        for split in ('development','holdout','stress'):
            data = json.loads((folder/f'benchmark_{split}.json').read_text(encoding='utf-8'))
            episodes = [r for r in data['episodes'] if r['strategy']=='adaptive']
            times = sorted(r['average_clear_time_s'] for r in episodes if r['certified_full_clear'])
            ax.step(times,[(i+1)*100/len(episodes) for i in range(len(times))],where='post',
                    label=f'{split} (n={len(episodes)})',color=colors[split],linewidth=1.8)
        threshold = 300 if problem==3 else 500
        ax.axvline(threshold,color='#b83280',linestyle='--',label=f'Preset: {threshold} s/source')
        ax.set_xlabel('Allowed virtual seconds / source')
        ax.set_ylabel('Certified full-clear cases (%)')
        ax.set_ylim(0,102); ax.grid(alpha=.2); ax.legend(fontsize=8,loc='lower right')
        ax.set_title(f'Problem {problem}: fixed adaptive policy')
    fig.suptitle('Synthetic local evaluation - NOT official simulator results',fontsize=15)
    dest=ROOT/'validation/search_comparison.png'
    fig.savefig(dest,dpi=170,facecolor='white'); plt.close(fig)
    print(dest)


if __name__ == '__main__':
    main()
