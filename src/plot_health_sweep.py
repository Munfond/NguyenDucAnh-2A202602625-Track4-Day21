"""Plot topic E threshold trade-offs and mean density-score response."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir', default='results')
    ap.add_argument('--out', default='results/figures/health_threshold_sweep.png')
    args = ap.parse_args()
    root = Path(args.results_dir)
    summary = pd.read_csv(root / 'health_summary.csv')
    summary = summary[summary.split == 'test']
    datasets = sorted(summary.dataset.unique())
    fig, axes = plt.subplots(len(datasets), 2, figsize=(12, 4 * len(datasets)), squeeze=False, constrained_layout=True)
    for i, dataset in enumerate(datasets):
        sub = summary[summary.dataset == dataset]
        for kind, level, label in [('original', 0., 'Original: false alarms'),
                                  ('random_dropout', .5, 'Random dropout 50%: detection'),
                                  ('sector_dropout', 30., 'Sector loss 30 deg: detection')]:
            data = sub[(sub.perturbation == kind) & (sub.level == level)].sort_values('threshold')
            axes[i, 0].plot(data.threshold, 100 * data.flag_rate, marker='o', label=label)
        axes[i, 0].set(title=dataset + ' | held-out threshold trade-off', xlabel='Density-deficit threshold (0-1)', ylabel='Flagged test frames (%)', ylim=(0, 105))
        unique = sub[sub.threshold == sub.threshold.min()]
        for kind, divisor, label in [('random_dropout', .5, 'Random dropout: 0/10/30/50%'),
                                     ('sector_dropout', 30., 'Sector dropout: 0/10/20/30 deg')]:
            data = unique[unique.perturbation == kind].sort_values('level')
            baseline = unique[unique.perturbation == 'original'].mean_density_score.iloc[0]
            axes[i, 1].plot([0, *list(data.level / divisor)], [baseline, *list(data.mean_density_score)], marker='o', label=label)
        axes[i, 1].set(title=dataset + ' | controlled degradation', xlabel='Severity / maximum tested severity (0-1)', ylabel='Mean density-deficit score (0-1)', ylim=(0, 1.05))
        for ax in axes[i]:
            ax.grid(alpha=.25)
            ax.legend(fontsize=8)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f'-> {out}')


if __name__ == '__main__':
    main()
