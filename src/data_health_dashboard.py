"""First topic E dashboard from the CSV produced by starter.data_health."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="results/data_health.csv", help="Input data-health CSV")
    parser.add_argument("--out", default="results/figures/dashboard_synthetic_cp2.png", help="Output PNG")
    args = parser.parse_args()
    df = pd.read_csv(args.csv, dtype={"frame_id": str})
    if df.empty:
        parser.error("Input CSV has no frames")
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    metrics = [("n_points", "Points per frame", "Points"),
               ("invalid_ratio", "Invalid points", "Percent (%)"),
               ("range_p95", "95th percentile horizontal range", "Meters"),
               ("intensity_mean", "Mean intensity (finite points)", "Intensity")]
    for ax, (column, title, unit) in zip(axes.flat, metrics):
        values = df[column] * (100 if column == "invalid_ratio" else 1)
        ax.bar(df["frame_id"], values, color="#2563eb")
        ax.set(title=title, xlabel="Frame ID", ylabel=unit)
        ax.grid(axis="y", alpha=.25)
        ax.set_axisbelow(True)
    fig.suptitle(f"Data health baseline | {Path(args.csv).name} | {len(df)} frames", fontsize=15)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f"Dashboard: {len(df)} frames, 4 plots -> {out}")


if __name__ == "__main__":
    main()
