# Figure 3 — OpenDrive validation analyses

This directory contains the raw measurements, analysis scripts, and reference plots for Figure 3 of the OpenDrive manuscript.

See the [root README](../../README.md#install-and-reproduce) for installation and reproduction commands. The root runner saves these panels to `results/fig3a/` and `results/fig3b/` by default.

For interactive exploration, open [`validation.ipynb`](validation.ipynb) using the [notebook instructions](../../README.md#interactive-notebooks). It runs both existing scripts, displays plots and statistical tables, and provides editable plotting settings. Notebook outputs go to this directory's `results/fig3a/` and `results/fig3b/` folders.

## Analyses

- [`fig3a/lateral_motion_analysis.py`](fig3a/lateral_motion_analysis.py) calculates lateral laser-spot RMS displacement, detrended and stationary measurements, statistical comparisons, and representative XY trajectories.
- [`fig3b/axial_position.py`](fig3b/axial_position.py) calculates signed positioning error, descriptive accuracy and precision statistics, and the inferential comparisons listed below from `fig3b/axial_position_data.csv`.

## Figure 3A input folders

The `fig3a/data/` directory contains three drive subfolders: `memdrive/`, `nandrive/`, and `opendrive/`. The Figure 3A script expects these exact lowercase folder names.

## Figure 3A outputs

- `fig3a_lateral_motion_trajectories.pdf` and `.png`: representative XY trajectories (one moving trial per drive).
- `fig3a_lateral_motion_trial_metrics.csv`: per-trial motion metrics.
- `fig3a_lateral_motion_summary_statistics.csv`: summaries by drive.
- `fig3a_lateral_motion_statistical_tests.csv`: inferential analysis results.
- `fig3a_lateral_motion_report.txt`: readable analysis report.

## Figure 3B outputs

- `fig3b_signed_positioning_error.pdf` and `.png`: signed error from the commanded 10-mm displacement.
- `fig3b_axial_positioning_descriptive_statistics.csv`: displacement and error summaries.
- `fig3b_axial_positioning_welch_anova.csv`: omnibus accuracy test.
- `fig3b_axial_positioning_games_howell_pairwise.csv`: pairwise accuracy comparisons.
- `fig3b_axial_positioning_brown_forsythe_omnibus.csv`: omnibus variability test.
- `fig3b_axial_positioning_brown_forsythe_pairwise_holm.csv`: pairwise variability comparisons.
- `fig3b_axial_positioning_report.txt`: readable analysis report.

## Relationship to the manuscript

These plots reproduce the Figure 3 analyses, but their formatting differs from the manuscript's final figure. Axis presentation, colors, labels, and layout may differ; the underlying data and calculations are unchanged.
