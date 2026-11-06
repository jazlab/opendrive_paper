# Figure 4: OpenDrive drift maps

The three example recordings come from thalamus, lateral intraparietal area (LIP),
and cerebellar dentate nucleus (DN).

| Region | Session | Probe | Sampling frequency (Hz) |
| --- | --- | --- | --- |
| LIP | 20260723_B_DN_TH2_LIP_g0 | imec2 | 30000 |
| Thalamus | 20260721_B_DN_TH2_LIP_g0 | imec0 | 30000.11011235955 |
| DN | 20260721_B_DN_TH2_LIP_g0 | imec3 | 30000 |

See the [root README](../../README.md#install-and-reproduce) for installation,
command-line reproduction, and interactive notebook instructions. The notebook
and command-line entry point share [`drift_map.py`](drift_map.py).

## Outputs

The analysis produces `LIP_drift_map.png`, `Thalamus_drift_map.png`, and
`DN_drift_map.png`. The root runner saves them to the repository's `results/fig4/`
by default; the notebook saves them to this directory's `results/`.
Reference PNGs are included in this directory's `figures/`.

## Data and calculation

The data release contains six original NumPy arrays, about 1.17 GB total, which the
download script installs in `data/`.
See the root README for data download instructions. Each recording has paired
`peaks.npy` and `peak_locations.npy` arrays in matching peak order.
The plot uses `sample_index` and signed `amplitude` from peaks, and `y` (micrometers
from the probe tip) from peak locations. Sampling frequencies came from the
corresponding SpikeGLX AP recording metadata.

The calculation retains signed amplitudes strictly above their 25th
percentile, plots every 30th retained peak, and colors plotted peaks by signed
amplitude rank using the `winter` colormap. Plots show uncorrected peak depths;
no motion correction or spike sorting is performed here. Arrays are memory-mapped
for loading, though filtering and plotting still allocate memory.

The root [data manifest](../../data_manifest.json) records the SHA-256
checksums for the six arrays and recording identifiers alongside the Figure 3 inputs.

## Relationship to the manuscript

The plots reproduce the Figure 4 recordings with different formatting from the
assembled manuscript figure, including colors, layout, axis limits, and depth
units (micrometers here versus millimeters in the manuscript).
