"""Topic E: threshold sweep and controlled dropout, with held-out evaluation.

Run from repo root: python -m src.exp_health_sweep
Reuses the supplied starter readers and perturbations; experiment logic is new.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from starter.datasets import list_frames, load_points
from starter.perturb import random_dropout, sector_dropout


def density(points):
    finite = np.isfinite(points).all(axis=1)
    p = points[finite]
    az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
    hist, _ = np.histogram(az, bins=36, range=(-180, 180))
    return len(p), hist, float(1 - finite.mean()) if len(points) else 1.


def health_score(n, hist, reference_n, reference_hist):
    # Compare absolute densities, not histograms normalized by current count:
    # normalizing by current count would hide uniform random dropout.
    supported = reference_hist > 0
    local_deficit = 1 - np.min(hist[supported] / reference_hist[supported]) if supported.any() else 1.
    global_deficit = 1 - n / reference_n if reference_n else 1.
    return float(np.clip(max(global_deficit, local_deficit), 0, 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-roots", nargs="+", default=["data/kitti_mini", "data/nuscenes_mini_subset"])
    ap.add_argument("--thresholds", nargs="+", type=float, default=[.2, .4, .6])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()
    if not args.thresholds or any(not 0 <= x <= 1 for x in args.thresholds):
        ap.error("Thresholds must be in [0,1]")
    records, refs = [], []
    for root in args.data_roots:
        dataset = Path(root).name
        frames = sorted(list_frames(root))
        loaded = {fid: load_points(root, fid) for fid in frames}
        # Split independently within each scene so both conditions are represented.
        splits = {}
        for group in sorted({fid.rsplit('_', 1)[0] if '_' in fid else dataset for fid in frames}):
            group_frames = [fid for fid in frames if (fid.rsplit('_', 1)[0] if '_' in fid else dataset) == group]
            splits.update({fid: 'calibration' if i % 2 == 0 else 'test' for i, fid in enumerate(group_frames)})
        base = {fid: density(pts) for fid, pts in loaded.items()}
        calibration = [base[fid] for fid in frames if splits[fid] == 'calibration']
        reference_n = float(np.median([item[0] for item in calibration]))
        reference_hist = np.median([item[1] for item in calibration], axis=0)
        for i, count in enumerate(reference_hist):
            refs.append(dict(dataset=dataset, az_start_deg=-180 + i * 10,
                             az_end_deg=-170 + i * 10, reference_bin_points=count,
                             reference_n_points=reference_n))
        center = 90. if dataset == 'nuscenes_mini_subset' else 0.
        for fid, pts in loaded.items():
            configs = [('original', 0., pts)]
            configs += [('random_dropout', level, random_dropout(pts, 1 - level, seed=args.seed))
                        for level in (.1, .3, .5)]
            configs += [('sector_dropout', width, sector_dropout(pts, center - width / 2, center + width / 2))
                        for width in (10., 20., 30.)]
            for kind, level, modified in configs:
                n, hist, invalid = density(modified)
                records.append(dict(dataset=dataset, frame=fid,
                                    scene=fid.rsplit('_', 1)[0] if '_' in fid else 'KITTI',
                                    split=splits[fid], perturbation=kind, level=level,
                                    level_unit='fraction_removed' if kind == 'random_dropout' else 'degrees' if kind == 'sector_dropout' else 'none',
                                    seed=args.seed, sector_center_deg=center,
                                    n_points=len(modified), finite_points=n,
                                    invalid_ratio=invalid, empty_azimuth_bins=int((hist == 0).sum()),
                                    density_score=health_score(n, hist, reference_n, reference_hist)))
        print(f"{dataset}: {len(frames)} frames x 7 configurations; reference from calibration only")
    scores = pd.DataFrame(records)
    runs = []
    for threshold in sorted(set(args.thresholds)):
        batch = scores.copy()
        batch['threshold'] = threshold
        batch['flagged'] = batch.density_score > threshold
        batch['warning_reason'] = np.where(batch.flagged, 'density_deficit_exceeds_threshold', '')
        runs.append(batch)
    sweep = pd.concat(runs, ignore_index=True)
    keys = ['dataset', 'split', 'perturbation', 'level', 'level_unit', 'threshold']
    summary = sweep.groupby(keys, sort=True).agg(n_frames=('frame', 'size'),
        flagged_frames=('flagged', 'sum'), flag_rate=('flagged', 'mean'),
        mean_points=('n_points', 'mean'), mean_density_score=('density_score', 'mean')).reset_index()
    # Predeclared selection: smallest threshold whose calibration-original FPR <=10%.
    selected = []
    for dataset, data in summary.groupby('dataset'):
        healthy = data[(data.split == 'calibration') & (data.perturbation == 'original')]
        eligible = healthy[healthy.flag_rate <= .1]
        threshold = float(eligible.threshold.min()) if len(eligible) else float(healthy.threshold.max())
        selection_met = bool(len(eligible))
        for kind, level in [('original', 0.), ('random_dropout', .5), ('sector_dropout', 30.)]:
            row = data[(data.split == 'test') & (data.perturbation == kind)
                       & (data.level == level) & (data.threshold == threshold)].iloc[0]
            selected.append(dict(dataset=dataset, selected_threshold=threshold,
                                 calibration_fpr_target_met=selection_met, perturbation=kind,
                                 level=level, n_test_frames=int(row.n_frames),
                                 flagged_test_frames=int(row.flagged_frames), flag_rate=row.flag_rate,
                                 metric='false_alarm_rate' if kind == 'original' else 'detection_rate'))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in [('health_scores.csv', scores), ('health_threshold_sweep.csv', sweep),
                     ('health_summary.csv', summary), ('health_selected.csv', pd.DataFrame(selected)),
                     ('health_reference.csv', pd.DataFrame(refs))]:
        df.to_csv(out / name, index=False, float_format='%.10g')
    print(pd.DataFrame(selected).to_string(index=False))
    print(f"-> {out} (scores={len(scores)}, threshold rows={len(sweep)})")


if __name__ == '__main__':
    main()
