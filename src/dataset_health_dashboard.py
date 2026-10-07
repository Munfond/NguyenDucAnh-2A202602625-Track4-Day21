"""Topic E: range/intensity distributions, angular density, time gaps and review ranking."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from starter.datasets import dataset_type, list_frames, load_frame, load_points
from starter.data_health import point_stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-roots', nargs='+', default=['data/synthetic','data/kitti_mini','data/nuscenes_mini_subset'], help='KITTI/nuScenes roots for dashboards')
    ap.add_argument('--results-dir', default='results', help='CP3 scores/selected thresholds and output directory')
    args = ap.parse_args()
    out = Path(args.results_dir)
    (out/'figures').mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(out/'health_scores.csv', dtype={'frame':str})
    scores = scores[scores.perturbation == 'original']
    thresholds = pd.read_csv(out/'health_selected.csv').groupby('dataset').selected_threshold.first()
    all_rows, bins = [], []
    edges = {'range':np.linspace(0,100,41), 'intensity':np.linspace(0,1,41),
             'azimuth':np.linspace(-180,180,37), 'elevation':np.linspace(-90,90,37)}
    for root in args.data_roots:
        dataset = Path(root).name
        nuscenes = dataset_type(root) == 'nuscenes'
        previous = {}
        frame_ids = sorted(list_frames(root))
        timestamp_file = Path(root)/'training/timestamps.txt'
        numeric_timestamps = None
        expected_gap = .5 if nuscenes else np.nan
        if not nuscenes and timestamp_file.exists():
            numeric_timestamps = np.atleast_1d(np.loadtxt(timestamp_file))
            if len(numeric_timestamps) != len(frame_ids):
                ap.error(f'{timestamp_file}: timestamp count must match sorted frames')
            expected_gap = float(np.median(np.diff(numeric_timestamps)))
        rows = []
        totals = {key:np.zeros(len(edge)-1,dtype=np.int64) for key,edge in edges.items()}
        for index, fid in enumerate(frame_ids):
            pts = load_points(root,fid)
            valid = pts[np.isfinite(pts).all(axis=1)]
            ranges = np.linalg.norm(valid[:,:2],axis=1)
            values = {'range':ranges, 'intensity':valid[:,3],
                      'azimuth':np.degrees(np.arctan2(valid[:,1],valid[:,0])),
                      'elevation':np.degrees(np.arctan2(valid[:,2],ranges))}
            for key,edge in edges.items():
                totals[key] += np.histogram(values[key],bins=edge)[0]
            scene = fid.rsplit('_',1)[0] if nuscenes else dataset
            gap, sync = np.nan, np.nan
            if nuscenes:
                frame = load_frame(root,fid)
                timestamp = frame['timestamp_lidar_us']
                if scene in previous:
                    gap = (timestamp-previous[scene])/1e6
                previous[scene] = timestamp
                sync = (frame['timestamp_camera_us']-timestamp)/1000
            elif numeric_timestamps is not None and index:
                gap = float(numeric_timestamps[index]-numeric_timestamps[index-1])
            matched = scores[(scores.dataset==dataset)&(scores.frame==fid)]
            score = float(matched.density_score.iloc[0]) if len(matched) else np.nan
            threshold = float(thresholds[dataset]) if dataset in thresholds else np.nan
            stats = point_stats(pts)
            reasons = []
            if stats['invalid_ratio'] > .005: reasons.append('invalid_gt_0.5pct')
            if stats['empty_azimuth_bins'] > 0: reasons.append('empty_azimuth_bin')
            if np.isfinite(gap) and not .8*expected_gap <= gap <= 1.2*expected_gap:
                reasons.append('time_gap_outside_expected_plus_minus_20pct')
            if np.isfinite(score) and score > threshold: reasons.append('density_review')
            rows.append(dict(dataset=dataset,frame=fid,scene=scene,**stats,
                             time_gap_s=gap, expected_time_gap_s=expected_gap, camera_minus_lidar_ms=sync,
                             density_score=score, density_threshold=threshold,
                             flagged=bool(reasons), reasons=';'.join(reasons),
                             range_gt_100m_ratio=float((ranges>100).mean()),
                             intensity_outside_0_1_ratio=float(((valid[:,3]<0)|(valid[:,3]>1)).mean())))
        df = pd.DataFrame(rows)
        all_rows += rows
        fig, axes = plt.subplots(2,3,figsize=(14,7),constrained_layout=True)
        axes[0,0].plot(np.arange(len(df)),df.n_points,'o-',markersize=3)
        axes[0,0].set(title='Points per frame',xlabel='Sorted frame index',ylabel='Points',ylim=(0,None))
        axes[0,1].plot(np.arange(len(df)),100*df.invalid_ratio,'o-',markersize=3)
        axes[0,1].axhline(.5,color='red',linestyle='--',label='Warning threshold 0.5%')
        axes[0,1].set(title='Invalid ratio',xlabel='Sorted frame index',ylabel='Invalid points (%)',ylim=(0,None))
        axes[0,1].legend(fontsize=8)
        for ax,key,label in [(axes[0,2],'range','Horizontal range (m; >100m recorded in CSV)'),
                              (axes[1,0],'intensity','Intensity (0-1; overflow recorded in CSV)'),
                              (axes[1,1],'azimuth','Azimuth (degrees; native sensor axes)'),
                              (axes[1,2],'elevation','Elevation (degrees)')]:
            edge = edges[key]; total = totals[key]
            # Angular density is mean absolute count per frame, not normalized by current total.
            normalized = total/len(df) if key in ('azimuth','elevation') else 100*total/max(1,total.sum())
            ax.bar((edge[:-1]+edge[1:])/2,normalized,width=np.diff(edge)*.9)
            ax.set(title=key.capitalize()+' distribution',xlabel=label,
                   ylabel='Mean points/bin/frame' if key in ('azimuth','elevation') else 'In-range finite points (%)',ylim=(0,None))
            bins += [dict(dataset=dataset,metric=key,bin_start=edge[i],bin_end=edge[i+1],n_points=int(n)) for i,n in enumerate(total)]
        for ax in axes.flat: ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
        fig.suptitle(f'Topic E | {dataset} | {len(df)} frames')
        fig.savefig(out/f'figures/dashboard_{dataset}_final.png',dpi=150)
        plt.close(fig)
        print(f'{dataset}: {len(df)} frames, {int(df.flagged.sum())} review flags')
    frames = pd.DataFrame(all_rows)
    frames.to_csv(out/'dataset_health_frames.csv',index=False,float_format='%.10g')
    pd.DataFrame(bins).to_csv(out/'dataset_health_histograms.csv',index=False,float_format='%.10g')
    ranking = frames[frames.density_score.notna()].sort_values(['dataset','density_score','frame'],ascending=[True,False,True]).copy()
    ranking['review_rank'] = ranking.groupby('dataset').cumcount()+1
    ranking.to_csv(out/'frame_review_ranking.csv',index=False,float_format='%.10g')
    scenes = frames.groupby(['dataset','scene']).agg(n_frames=('frame','size'), median_points=('n_points','median'),
        mean_intensity=('intensity_mean','mean'), mean_range_p95=('range_p95','mean'),
        median_time_gap_s=('time_gap_s','median'), min_camera_minus_lidar_ms=('camera_minus_lidar_ms','min'),
        max_camera_minus_lidar_ms=('camera_minus_lidar_ms','max'), flagged_frames=('flagged','sum')).reset_index()
    scenes.to_csv(out/'dataset_scene_summary.csv',index=False,float_format='%.10g')
    print(scenes.to_string(index=False))


if __name__ == '__main__':
    main()
