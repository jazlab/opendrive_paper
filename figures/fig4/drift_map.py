"""Reproduce Figure 4 drift maps from the supplied detected-peak arrays."""
import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RECORDINGS = [
    ("LIP", "20260723_B_DN_TH2_LIP_g0", "imec2", 30_000),
    ("Thalamus", "20260721_B_DN_TH2_LIP_g0", "imec0", 30_000.11011235955),
    ("DN", "20260721_B_DN_TH2_LIP_g0", "imec3", 30_000),
]

def plot_drift(peaks, peak_locations, sampling_frequency, region):
    assert len(peaks) == len(peak_locations), "The arrays must contain the same peaks."
    if "segment_index" in peaks.dtype.names:
        assert np.unique(peaks["segment_index"]).size == 1, "Use a single recording segment."

    # Keep signed amplitudes above the 25th percentile, then plot every 30th peak.
    amplitudes = peaks["amplitude"]
    keep = amplitudes > np.quantile(amplitudes, 0.25)
    times = (peaks["sample_index"][keep] / sampling_frequency).astype(np.float32)[::30]
    depths = peak_locations["y"][keep][::30]
    amplitudes = amplitudes[keep][::30]

    # Color the plotted peaks by amplitude rank.
    amplitude_ranks = np.argsort(np.argsort(amplitudes)) / len(amplitudes)
    colors = plt.get_cmap("winter")(amplitude_ranks)

    fig, ax = plt.subplots(figsize=(4.41, 10))
    ax.scatter(times, depths, s=1, c=colors, alpha=0.75)
    ax.set_xlabel("time (s)", fontsize=12)
    ax.set_ylabel(r"depth from probe tip ($\mu$m)", fontsize=12)
    ax.set_title(region)
    fig.tight_layout()
    return fig


def make_figures(data_folder=ROOT / "data", output_dir=ROOT / "results", show=False):
    data_folder, output_dir = Path(data_folder), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for region, session, probe, sampling_frequency in RECORDINGS:
        folder = data_folder / f"{region}_{session}_{probe}"
        peaks = np.load(folder / "peaks.npy", mmap_mode="r", allow_pickle=False)
        peak_locations = np.load(folder / "peak_locations.npy", mmap_mode="r", allow_pickle=False)
        fig = plot_drift(peaks, peak_locations, sampling_frequency, region)
        output = output_dir / f"{region}_drift_map.png"
        fig.savefig(output, dpi=100)
        print(f"Saved {output}", flush=True)
        if show:
            plt.show()
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    make_figures(args.data_dir, args.output_dir)
