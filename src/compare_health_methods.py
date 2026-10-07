"""B1: compare global-count deficit with worst-bin density on the same CP3 rows.

Requires exp_health_sweep outputs. Threshold selection uses calibration controls only.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir', default='results', help='Directory containing CP3 scores and calibration references')
    ap.add_argument('--out-dir', default='results', help='Output directory for comparison CSVs and figures')
    ap.add_argument('--thresholds', nargs='+', type=float, default=[.2, .4, .6], help='Same candidate thresholds for both methods; flag when score > threshold')
    args = ap.parse_args()
    if any(not 0 <= t <= 1 for t in args.thresholds):
        ap.error('Thresholds must be in [0,1]')
    root, out = Path(args.results_dir), Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(root / 'health_scores.csv', dtype={'frame': str})
    reference = pd.read_csv(root / 'health_reference.csv').groupby('dataset').reference_n_points.first()
    global_scores = np.clip(1 - scores.finite_points / scores.dataset.map(reference), 0, 1)
    rows = []
    for method, values in [('global_count', global_scores), ('worst_bin', scores.density_score)]:
        for threshold in sorted(set(args.thresholds)):
            df = scores.copy()
            df['method'], df['threshold'], df['method_score'] = method, threshold, values
            df['flagged'] = df.method_score > threshold
            rows.append(df)
    runs = pd.concat(rows, ignore_index=True)
    summary = runs.groupby(['dataset','method','split','perturbation','level','threshold']).agg(
        n_frames=('frame','size'), flagged_frames=('flagged','sum'), flag_rate=('flagged','mean')).reset_index()
    selected = []
    for (dataset, method), group in summary.groupby(['dataset','method']):
        calibration = group[(group.split == 'calibration') & (group.perturbation == 'original')]
        eligible = calibration[calibration.flag_rate <= .1]
        threshold = float(eligible.threshold.min()) if len(eligible) else float(calibration.threshold.max())
        for _, row in group[(group.split == 'test') & (group.threshold == threshold)].iterrows():
            selected.append(dict(dataset=dataset, method=method, selected_threshold=threshold,
                                 calibration_fpr_target_met=bool(len(eligible)), perturbation=row.perturbation,
                                 level=row.level, n_test_frames=int(row.n_frames),
                                 flagged_frames=int(row.flagged_frames), flag_rate=row.flag_rate))
    selected = pd.DataFrame(selected)
    runs.to_csv(out / 'health_method_runs.csv', index=False, float_format='%.10g')
    summary.to_csv(out / 'health_method_summary.csv', index=False, float_format='%.10g')
    selected.to_csv(out / 'health_method_selected.csv', index=False, float_format='%.10g')
    datasets = sorted(selected.dataset.unique())
    fig, axes = plt.subplots(1, len(datasets), figsize=(12, 4.8), squeeze=False, constrained_layout=True)
    for ax, dataset in zip(axes.flat, datasets):
        for j, method in enumerate(('global_count','worst_bin')):
            data = selected[(selected.dataset == dataset) & (selected.method == method)]
            values = [100 * data[(data.perturbation == kind) & (data.level == level)].flag_rate.iloc[0]
                      for kind, level in [('original',0),('random_dropout',.5),('sector_dropout',30)]]
            label = f"{method} (threshold {data.selected_threshold.iloc[0]:g})"
            if not data.calibration_fpr_target_met.iloc[0]:
                label += ' [fallback]'
            bars = ax.bar(np.arange(3) + (j-.5)*.35, values, width=.35, label=label)
            ax.bar_label(bars, labels=[f'{v:g}%' for v in values], padding=3, fontsize=9)
        ax.set(xticks=np.arange(3), xticklabels=['Original\nfalse alarms','Random 50%\ndetection','Sector 30 deg\ndetection'],
               ylabel='Flagged held-out frames (%)', ylim=(0,118), title=dataset)
        ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True); ax.legend(fontsize=8, loc='upper center', bbox_to_anchor=(.5,-.15))
    fig.suptitle('B1 | Same inputs, split, seed, threshold candidates and evaluation metrics')
    (out / 'figures').mkdir(exist_ok=True)
    fig.savefig(out / 'figures/health_method_comparison.png', dpi=160)
    plt.close(fig)
    print(selected[selected.perturbation.isin(['original']) | ((selected.perturbation == 'random_dropout') & (selected.level == .5)) | ((selected.perturbation == 'sector_dropout') & (selected.level == 30))].to_string(index=False))


if __name__ == '__main__':
    main()
