"""B3: CPU feature-extraction + decision latency, excluding I/O and plotting.

For each dataset/method: one warmup discarded, then at least 20 timed iterations.
Calibration reference and original points are loaded before starting the timer.
"""
import argparse
import json
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from starter.datasets import load_points
from src.exp_health_sweep import density, health_score


def hardware():
    if platform.system() == 'Windows':
        command = "$benchCpu=(Get-CimInstance Win32_Processor).Name; $benchRam=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; $benchGpu=@((Get-CimInstance Win32_VideoController).Name); [pscustomobject]@{cpu=$benchCpu;ram_gb=[math]::Round($benchRam/1GB,2);gpu=$benchGpu}|ConvertTo-Json -Compress"
        result = subprocess.run(['powershell','-NoProfile','-Command',command], capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
    else:
        info = {'cpu':platform.processor(), 'ram_gb':None, 'gpu':None}
    return {**info, 'os':platform.platform(), 'python':platform.python_version(), 'numpy':np.__version__,
            'execution_device':'CPU', 'scope':'original points in RAM -> finite filter/count + histogram for worst_bin + score + flag; no disk I/O, perturbation, reference fitting or plots'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir', default='results', help='Directory containing CP3 reference and B1 selected thresholds')
    ap.add_argument('--out-dir', default='results', help='Output directory for raw latency, summary and hardware JSON')
    ap.add_argument('--repeats', type=int, default=30, help='Timed iterations per dataset/method after one discarded warmup; minimum 20')
    args = ap.parse_args()
    if args.repeats < 20:
        ap.error('At least 20 measured repeats are required')
    root, out = Path(args.results_dir), Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    references = pd.read_csv(root / 'health_reference.csv')
    selected = pd.read_csv(root / 'health_method_selected.csv')
    records = []
    for dataset, fid in [('kitti_mini','000011'),('nuscenes_mini_subset','scene-0103_010')]:
        pts = load_points('data/' + dataset, fid)
        ref = references[references.dataset == dataset].sort_values('az_start_deg')
        reference_n, reference_hist = ref.reference_n_points.iloc[0], ref.reference_bin_points.to_numpy()
        for method in ('global_count','worst_bin'):
            threshold = selected[(selected.dataset == dataset) & (selected.method == method)].selected_threshold.iloc[0]
            for i in range(args.repeats + 1):
                start = perf_counter()
                if method == 'global_count':
                    n = int(np.isfinite(pts).all(axis=1).sum())
                    score = float(np.clip(1 - n / reference_n, 0, 1))
                else:
                    n, hist, _ = density(pts)
                    score = health_score(n, hist, reference_n, reference_hist)
                flagged = score > threshold
                elapsed = (perf_counter() - start) * 1000
                if i:  # warmup is neither saved nor included in percentiles
                    records.append(dict(dataset=dataset, frame=fid, method=method, iteration=i,
                                        n_points=len(pts), threshold=threshold, score=score,
                                        flagged=flagged, elapsed_ms=elapsed))
    timings = pd.DataFrame(records)
    timings.to_csv(out / 'health_latency.csv', index=False, float_format='%.10g')
    summary = timings.groupby(['dataset','frame','method']).elapsed_ms.agg(
        repeats='size', p50_ms=lambda x:np.percentile(x,50), p95_ms=lambda x:np.percentile(x,95)).reset_index()
    summary.to_csv(out / 'health_latency_summary.csv', index=False, float_format='%.10g')
    (out / 'health_latency_hardware.json').write_text(json.dumps(hardware(), ensure_ascii=False, indent=2), encoding='utf-8')
    print(summary.to_string(index=False))


if __name__ == '__main__':
    main()
