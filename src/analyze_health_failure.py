"""CP4: reproduce a control-frame alarm and a controlled-dropout miss.

Uses CP3 calibration references unchanged; no threshold fitting on failure cases.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from starter.datasets import load_points
from starter.perturb import random_dropout
from src.exp_health_sweep import density, health_score


def inspect(points, ref, dataset, frame, kind, threshold):
    n, hist, invalid = density(points)
    reference_hist = ref.reference_bin_points.to_numpy()
    supported = reference_hist > 0
    ratios = np.full(36, np.inf)
    ratios[supported] = hist[supported] / reference_hist[supported]
    worst = int(ratios.argmin())
    score = health_score(n, hist, ref.reference_n_points.iloc[0], reference_hist)
    return hist, dict(dataset=dataset, frame=frame, perturbation=kind,
                     threshold=threshold, score=score, flagged=score > threshold,
                     n_points=len(points), finite_points=n, invalid_ratio=invalid,
                     empty_azimuth_bins=int((hist == 0).sum()),
                     reference_n_points=ref.reference_n_points.iloc[0],
                     global_deficit=max(0., 1 - n / ref.reference_n_points.iloc[0]),
                     worst_az_start_deg=ref.az_start_deg.iloc[worst],
                     worst_az_end_deg=ref.az_end_deg.iloc[worst],
                     worst_bin_points=hist[worst], worst_bin_reference=reference_hist[worst],
                     local_deficit=1 - ratios[worst])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir', default='results')
    args = ap.parse_args()
    root = Path(args.results_dir)
    reference = pd.read_csv(root / 'health_reference.csv')
    saved = pd.read_csv(root / 'health_scores.csv', dtype={'frame': str})
    out = root / 'figures'
    out.mkdir(parents=True, exist_ok=True)
    records = []
    dataset, fid = 'nuscenes_mini_subset', 'scene-0103_035'
    ref = reference[reference.dataset == dataset].sort_values('az_start_deg')
    points = load_points('data/' + dataset, fid)
    hist, rec = inspect(points, ref, dataset, fid, 'original', .6)
    original = saved[(saved.dataset == dataset) & (saved.frame == fid) & (saved.perturbation == 'original')].iloc[0]
    assert np.isclose(rec['score'], original.density_score, atol=1e-9)
    assert rec['flagged'] and rec['invalid_ratio'] == 0 and rec['empty_azimuth_bins'] == 0
    records.append(rec)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    az = ref.az_start_deg.to_numpy() + 5
    axes[0].plot(az, ref.reference_bin_points, 'o-', label='Calibration median reference', color='#2563eb')
    axes[0].plot(az, hist, 'o-', label='Unmodified test frame', color='#ea580c')
    worst = int(np.argmin(hist / ref.reference_bin_points.to_numpy()))
    axes[0].axvspan(az[worst] - 5, az[worst] + 5, color='red', alpha=.15)
    axes[0].annotate(f"Worst bin: {int(rec['worst_bin_points'])}/{rec['worst_bin_reference']:.0f} points",
                     (az[worst], hist[worst]), xytext=(-170, 3400), arrowprops={'arrowstyle': '->'})
    axes[0].set(title='A local density difference drives the alarm', xlabel='Sensor azimuth (degrees; 0 = right)', ylabel='Points per 10-degree bin', ylim=(0, None))
    axes[1].bar(['Global count deficit', 'Worst-bin deficit', 'Combined score'],
                [rec['global_deficit'], rec['local_deficit'], rec['score']], color=['#2563eb', '#ea580c', '#dc2626'])
    axes[1].axhline(.6, linestyle='--', color='black', label='Fallback threshold = 0.6')
    axes[1].set(title=f"ALARM on original control: score={rec['score']:.3f}", ylabel='Density deficit (0-1)', ylim=(0, 1.1))
    axes[1].text(.03, .94, f"Total: {len(points):,} = reference {rec['reference_n_points']:,.0f}\nInvalid: 0 | Empty bins: 0\nOriginal control is not proof of a healthy sensor", transform=axes[1].transAxes, va='top', fontsize=9)
    fig.suptitle(f'Failure 01 | {fid} | alarm on an unmodified control', fontsize=14)
    for ax in axes:
        ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.savefig(out / 'fail_01_nusc_control_alarm.png', dpi=160)
    plt.close(fig)

    dataset, fid = 'kitti_mini', '000021'
    ref = reference[reference.dataset == dataset].sort_values('az_start_deg')
    points = load_points('data/' + dataset, fid)
    dropped = random_dropout(points, keep_ratio=.5, seed=42)
    before, original_rec = inspect(points, ref, dataset, fid, 'original', .6)
    after, rec = inspect(dropped, ref, dataset, fid, 'random_dropout_50pct', .6)
    saved_row = saved[(saved.dataset == dataset) & (saved.frame == fid)
                      & (saved.perturbation == 'random_dropout') & (saved.level == .5)].iloc[0]
    assert np.isclose(rec['score'], saved_row.density_score, atol=1e-9)
    assert not rec['flagged'] and len(dropped) < .51 * len(points)
    records += [original_rec, rec]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    az = ref.az_start_deg.to_numpy() + 5
    axes[0].plot(az, before, 'o-', label=f'Original: {len(points):,} points')
    axes[0].plot(az, after, 'o-', label=f'Dropout 50%, seed 42: {len(dropped):,} points')
    axes[0].set(title='Known loss: roughly half the points removed', xlabel='Sensor azimuth (degrees; 0 = forward)', ylabel='Points per 10-degree bin', ylim=(0, None))
    axes[1].bar(['Original', 'Dropout 50%'], [original_rec['score'], rec['score']], color=['#2563eb', '#ea580c'])
    axes[1].axhline(.6, color='red', linestyle='--', label='Threshold 0.6: MISSED')
    axes[1].axhline(.4, color='green', linestyle=':', label='CP3 selected threshold 0.4: detected')
    axes[1].set(title=f"NO ALARM at 0.6: score={rec['score']:.3f}", ylabel='Density-deficit score (0-1)', ylim=(0, 1))
    axes[1].text(.03, .92, f"Actual removed: {100*(1-len(dropped)/len(points)):.2f}%\nFlag condition: score > threshold", transform=axes[1].transAxes, va='top')
    fig.suptitle(f'Failure 02 | KITTI {fid} | controlled dropout missed at a loose threshold', fontsize=14)
    for ax in axes:
        ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.savefig(out / 'fail_02_kitti_dropout_missed.png', dpi=160)
    plt.close(fig)
    pd.DataFrame(records).to_csv(root / 'health_failure_details.csv', index=False, float_format='%.10g')
    print(pd.DataFrame(records).to_string(index=False))
    print('-> two fail_*.png figures and health_failure_details.csv')


if __name__ == '__main__':
    main()
