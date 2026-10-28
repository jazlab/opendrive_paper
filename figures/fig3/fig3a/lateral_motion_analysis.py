#!/usr/bin/env python3
"""Publication analysis for MonkeyDrive lateral-motion validation.

This script:
1. Loads the three moving trials for MonkeyDrive, NAN Drive, and MEM Drive.
2. Calculates two-dimensional radial RMS displacement for each trial.
3. Repeats the calculation after linear detrending of X and Y versus time.
4. Calculates the stationary radial RMS measurement for each drive.
5. Performs Welch's one-way ANOVA and Holm-adjusted pairwise Welch t-tests.
6. Reproduces the one-trial XY trajectory figure with a white background.
7. Writes publication-ready PNG/PDF figures and CSV/text result files.

The trajectory plot uses a 10-sample rolling mean for visualization only.
All numerical analyses use the unsmoothed valid samples.

Usage
-----
    python lateral_motion_analysis.py \
        data \
        --output-dir analysis_output

The first argument may also be the ZIP archive containing the dataset.
"""

from __future__ import annotations

import argparse
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


DRIVE_ORDER = ("MEM Drive", "NAN Drive", "MonkeyDrive")
COLORS = {
    "MEM Drive": "#1f77b4",
    "NAN Drive": "#ff7f0e",
    "MonkeyDrive": "#2ca02c",
}


@dataclass(frozen=True)
class DriveFiles:
    moving: tuple[Path, ...]
    stationary: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "data_path",
        type=Path,
        help="Path to the extracted dataset folder or its ZIP archive.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("lateral_motion_results"),
        help="Directory for figures and result tables (default: lateral_motion_results).",
    )
    parser.add_argument(
        "--rolling-window",
        type=int,
        default=10,
        help="Rolling-mean window used only for trajectory visualization (default: 10).",
    )
    return parser.parse_args()


def resolve_dataset_root(data_path: Path, temporary_directory: Path) -> Path:
    """Return the folder that directly contains the drive subfolders."""
    data_path = data_path.expanduser().resolve()

    if data_path.is_file() and data_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(data_path) as archive:
            archive.extractall(temporary_directory)
        search_root = temporary_directory
    elif data_path.is_dir():
        search_root = data_path
    else:
        raise FileNotFoundError(f"Dataset path does not exist: {data_path}")

    candidates = [search_root, *search_root.rglob("data")]
    for candidate in candidates:
        if (
            (candidate / "memdrive").is_dir()
            and (candidate / "nandrive").is_dir()
            and (candidate / "monkeydrive").is_dir()
        ):
            return candidate

    raise FileNotFoundError(
        "Could not find the expected 'memdrive', 'nandrive', and "
        "'monkeydrive' folders beneath the supplied path."
    )


def natural_sort_key(path: Path) -> tuple:
    """Sort paths by embedded integers so trials 1, 2, 3 remain ordered."""
    parts = re.split(r"(\d+)", path.name.lower())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def require_files(paths: Iterable[Path], expected: int, description: str) -> tuple[Path, ...]:
    files = tuple(sorted(paths, key=natural_sort_key))
    if len(files) != expected:
        listed = "\n".join(f"  - {file}" for file in files) or "  (none found)"
        raise FileNotFoundError(
            f"Expected {expected} {description} file(s), found {len(files)}:\n{listed}"
        )
    return files


def locate_files(root: Path) -> dict[str, DriveFiles]:
    mem_dir = root / "memdrive"
    nan_dir = root / "nandrive"
    monkey_dir = root / "monkeydrive"

    mem_moving = require_files(mem_dir.glob("*_moving_t*.csv"), 3, "MEM moving")
    nan_moving = require_files(nan_dir.glob("*_moving_t*.csv"), 3, "NAN moving")
    monkey_moving = require_files(monkey_dir.glob("*_moving_t*.csv"), 3, "MonkeyDrive moving")

    mem_static = require_files(mem_dir.glob("*_static_t*.csv"), 1, "MEM stationary")[0]
    nan_static = require_files(nan_dir.glob("*_static_t*.csv"), 1, "NAN stationary")[0]
    monkey_static = require_files(monkey_dir.glob("*_static_t*.csv"), 1, "MonkeyDrive stationary")[0]

    return {
        "MEM Drive": DriveFiles(mem_moving, mem_static),
        "NAN Drive": DriveFiles(nan_moving, nan_static),
        "MonkeyDrive": DriveFiles(monkey_moving, monkey_static),
    }


def load_valid_samples(path: Path) -> pd.DataFrame:
    required_columns = {
        "host_read_midpoint_elapsed_s",
        "x_position_mm",
        "y_position_mm",
        "valid",
    }
    data = pd.read_csv(path)
    missing = required_columns.difference(data.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")

    data = data.loc[data["valid"].eq(1)].copy()
    data = data.dropna(
        subset=["host_read_midpoint_elapsed_s", "x_position_mm", "y_position_mm"]
    )
    if data.empty:
        raise ValueError(f"No valid position samples found in {path}")
    return data


def centered_or_detrended_xy_um(data: pd.DataFrame, detrend: bool) -> tuple[np.ndarray, np.ndarray]:
    """Return centered XY values in micrometers.

    Raw analysis subtracts each trial's mean X and mean Y.
    Detrended analysis removes a least-squares linear trend versus elapsed
    time separately from X and Y, then centers the residuals numerically.
    """
    time_s = data["host_read_midpoint_elapsed_s"].to_numpy(dtype=float)
    x_um = data["x_position_mm"].to_numpy(dtype=float) * 1000.0
    y_um = data["y_position_mm"].to_numpy(dtype=float) * 1000.0

    if detrend:
        x_fit = np.polyfit(time_s, x_um, deg=1)
        y_fit = np.polyfit(time_s, y_um, deg=1)
        x_um = x_um - np.polyval(x_fit, time_s)
        y_um = y_um - np.polyval(y_fit, time_s)

    x_um = x_um - np.mean(x_um)
    y_um = y_um - np.mean(y_um)
    return x_um, y_um


def radial_rms_um(path: Path, detrend: bool = False) -> float:
    """Two-dimensional RMS displacement from the trial mean XY position."""
    data = load_valid_samples(path)
    x_um, y_um = centered_or_detrended_xy_um(data, detrend=detrend)
    return float(np.sqrt(np.mean(x_um**2 + y_um**2)))


def welch_anova(groups: dict[str, np.ndarray]) -> dict[str, float]:
    """Welch's heteroscedastic one-way ANOVA.

    Formula follows the standard Welch ANOVA correction and returns F,
    numerator df, denominator df, and the upper-tail p-value.
    """
    arrays = [np.asarray(groups[name], dtype=float) for name in groups]
    k = len(arrays)
    n = np.array([len(array) for array in arrays], dtype=float)
    means = np.array([np.mean(array) for array in arrays], dtype=float)
    variances = np.array([np.var(array, ddof=1) for array in arrays], dtype=float)

    if np.any(n < 2):
        raise ValueError("Welch's ANOVA requires at least two observations per group.")
    if np.any(variances <= 0):
        raise ValueError("Welch's ANOVA requires nonzero within-group variance.")

    weights = n / variances
    weight_sum = np.sum(weights)
    weighted_mean = np.sum(weights * means) / weight_sum

    correction_sum = np.sum(((1.0 - weights / weight_sum) ** 2) / (n - 1.0))
    numerator = np.sum(weights * (means - weighted_mean) ** 2) / (k - 1.0)
    denominator = 1.0 + (2.0 * (k - 2.0) / (k**2 - 1.0)) * correction_sum

    f_value = numerator / denominator
    df_num = k - 1.0
    df_den = (k**2 - 1.0) / (3.0 * correction_sum)
    p_value = stats.f.sf(f_value, df_num, df_den)

    return {"F": float(f_value), "df_num": float(df_num), "df_den": float(df_den), "p": float(p_value)}


def holm_adjust(p_values: np.ndarray) -> np.ndarray:
    """Holm family-wise-error correction, preserving original order."""
    p_values = np.asarray(p_values, dtype=float)
    order = np.argsort(p_values)
    adjusted = np.empty_like(p_values)
    running_max = 0.0
    number = len(p_values)

    for rank, index in enumerate(order):
        candidate = (number - rank) * p_values[index]
        running_max = max(running_max, candidate)
        adjusted[index] = min(1.0, running_max)
    return adjusted


def pairwise_welch_tests(groups: dict[str, np.ndarray], analysis: str) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    names = list(groups)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            result = stats.ttest_ind(groups[first], groups[second], equal_var=False)
            rows.append(
                {
                    "analysis": analysis,
                    "comparison": f"{first} vs {second}",
                    "t": float(result.statistic),
                    "p_unadjusted": float(result.pvalue),
                }
            )

    table = pd.DataFrame(rows)
    table["p_holm"] = holm_adjust(table["p_unadjusted"].to_numpy())
    return table


def calculate_results(files: dict[str, DriveFiles]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trial_rows: list[dict[str, float | int | str]] = []

    for drive in DRIVE_ORDER:
        for trial_number, path in enumerate(files[drive].moving, start=1):
            trial_rows.append(
                {
                    "drive": drive,
                    "trial": trial_number,
                    "raw_radial_rms_um": radial_rms_um(path, detrend=False),
                    "detrended_radial_rms_um": radial_rms_um(path, detrend=True),
                    "source_file": path.name,
                }
            )

    trial_table = pd.DataFrame(trial_rows)

    summary_rows: list[dict[str, float | int | str]] = []
    for drive in DRIVE_ORDER:
        drive_trials = trial_table.loc[trial_table["drive"].eq(drive)]
        summary_rows.append(
            {
                "drive": drive,
                "n_moving_trials": len(drive_trials),
                "raw_mean_um": drive_trials["raw_radial_rms_um"].mean(),
                "raw_sd_um": drive_trials["raw_radial_rms_um"].std(ddof=1),
                "detrended_mean_um": drive_trials["detrended_radial_rms_um"].mean(),
                "detrended_sd_um": drive_trials["detrended_radial_rms_um"].std(ddof=1),
                "stationary_radial_rms_um": radial_rms_um(files[drive].stationary, detrend=False),
            }
        )
    summary_table = pd.DataFrame(summary_rows)

    test_tables: list[pd.DataFrame] = []
    for column, analysis_name in (
        ("raw_radial_rms_um", "Raw radial RMS"),
        ("detrended_radial_rms_um", "Detrended radial RMS"),
    ):
        groups = {
            drive: trial_table.loc[trial_table["drive"].eq(drive), column].to_numpy()
            for drive in DRIVE_ORDER
        }
        anova = welch_anova(groups)
        anova_row = pd.DataFrame(
            [
                {
                    "analysis": analysis_name,
                    "comparison": "Welch one-way ANOVA",
                    "t": np.nan,
                    "F": anova["F"],
                    "df_num": anova["df_num"],
                    "df_den": anova["df_den"],
                    "p_unadjusted": anova["p"],
                    "p_holm": np.nan,
                }
            ]
        )
        pairwise = pairwise_welch_tests(groups, analysis_name)
        pairwise["F"] = np.nan
        pairwise["df_num"] = np.nan
        pairwise["df_den"] = np.nan
        pairwise = pairwise[
            ["analysis", "comparison", "t", "F", "df_num", "df_den", "p_unadjusted", "p_holm"]
        ]
        test_tables.extend([anova_row, pairwise])

    test_table = pd.concat(test_tables, ignore_index=True)
    return trial_table, summary_table, test_table


def plot_one_trial(
    files: dict[str, DriveFiles],
    output_dir: Path,
    rolling_window: int,
) -> None:
    """Plot the first moving trial for each drive."""
    if rolling_window < 1:
        raise ValueError("rolling_window must be at least 1")

    fig, ax = plt.subplots(figsize=(8.5, 6.2), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for drive in DRIVE_ORDER:
        data = load_valid_samples(files[drive].moving[0])
        x_mm = data["x_position_mm"].rolling(rolling_window, min_periods=1).mean().to_numpy()
        y_mm = data["y_position_mm"].rolling(rolling_window, min_periods=1).mean().to_numpy()
        x_mm = x_mm - np.mean(x_mm)
        y_mm = y_mm - np.mean(y_mm)

        ax.plot(
            x_mm,
            y_mm,
            color=COLORS[drive],
            linewidth=2.0,
            alpha=0.90,
            label=drive,
        )

    ax.set_xlabel("Mean-centered X position (mm)", fontsize=20)
    ax.set_ylabel("Mean-centered Y position (mm)", fontsize=20)
    ax.tick_params(axis="both", labelsize=18, width=1.2, length=6, color="black")
    ax.grid(True, color="#d9d9d9", linewidth=1.0)

    for spine in ax.spines.values():
        spine.set_color("black")
        spine.set_linewidth(1.2)

    ax.legend(loc="upper left", fontsize=15, frameon=True, title=None)
    fig.tight_layout()

    png_path = output_dir / "fig3a_lateral_motion_trajectories.png"
    pdf_path = output_dir / "fig3a_lateral_motion_trajectories.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def format_p(value: float) -> str:
    if value < 0.001:
        return f"{value:.3e}"
    return f"{value:.4f}"


def write_report(
    output_dir: Path,
    summary: pd.DataFrame,
    tests: pd.DataFrame,
) -> None:
    indexed = summary.set_index("drive")
    monkey = indexed.loc["MonkeyDrive"]
    nan = indexed.loc["NAN Drive"]
    mem = indexed.loc["MEM Drive"]

    reduction_nan = 100.0 * (1.0 - monkey["raw_mean_um"] / nan["raw_mean_um"])
    reduction_mem = 100.0 * (1.0 - monkey["raw_mean_um"] / mem["raw_mean_um"])

    lines = [
        "LATERAL MOTION ANALYSIS",
        "=======================",
        "",
        "Moving trials: two-dimensional radial RMS about each trial's mean XY position",
    ]
    for drive in ("MonkeyDrive", "NAN Drive", "MEM Drive"):
        row = indexed.loc[drive]
        lines.append(
            f"  {drive}: {row['raw_mean_um']:.2f} ± {row['raw_sd_um']:.2f} µm "
            f"(mean ± SD; n={int(row['n_moving_trials'])})"
        )

    lines.extend(
        [
            "",
            f"MonkeyDrive reduction relative to NAN Drive: {reduction_nan:.1f}%",
            f"MonkeyDrive reduction relative to MEM Drive: {reduction_mem:.1f}%",
            "",
            "Stationary recordings: radial RMS about the mean XY position",
        ]
    )
    for drive in ("MonkeyDrive", "NAN Drive", "MEM Drive"):
        row = indexed.loc[drive]
        lines.append(f"  {drive}: {row['stationary_radial_rms_um']:.2f} µm")

    lines.extend(["", "Linearly detrended moving trials"])
    for drive in ("MonkeyDrive", "NAN Drive", "MEM Drive"):
        row = indexed.loc[drive]
        lines.append(
            f"  {drive}: {row['detrended_mean_um']:.2f} ± "
            f"{row['detrended_sd_um']:.2f} µm (mean ± SD; n={int(row['n_moving_trials'])})"
        )

    lines.extend(["", "Inferential tests (trial treated as the replicate)"])
    for _, row in tests.iterrows():
        if row["comparison"] == "Welch one-way ANOVA":
            lines.append(
                f"  {row['analysis']}: Welch's ANOVA, "
                f"F({row['df_num']:.0f}, {row['df_den']:.2f})={row['F']:.2f}, "
                f"p={format_p(row['p_unadjusted'])}"
            )
        else:
            lines.append(
                f"  {row['analysis']}, {row['comparison']}: "
                f"Welch t={row['t']:.2f}, unadjusted p={format_p(row['p_unadjusted'])}, "
                f"Holm-adjusted p={format_p(row['p_holm'])}"
            )

    lines.extend(
        [
            "",
            "Interpretive note:",
            "  The inferential tests treat the three repeated trials as replicates. Because only one",
            "  physical unit of each drive model was tested, these p-values quantify repeatability of",
            "  the separation among the tested units and should not be interpreted as a population-level",
            "  comparison among all devices of each model.",
        ]
    )

    (output_dir / "fig3a_lateral_motion_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lateral_motion_") as temporary:
        root = resolve_dataset_root(args.data_path, Path(temporary))
        files = locate_files(root)
        trial_table, summary_table, test_table = calculate_results(files)
        plot_one_trial(files, args.output_dir, args.rolling_window)

    trial_table.to_csv(args.output_dir / "fig3a_lateral_motion_trial_metrics.csv", index=False)
    summary_table.to_csv(args.output_dir / "fig3a_lateral_motion_summary_statistics.csv", index=False)
    test_table.to_csv(args.output_dir / "fig3a_lateral_motion_statistical_tests.csv", index=False)
    write_report(args.output_dir, summary_table, test_table)

    print((args.output_dir / "fig3a_lateral_motion_report.txt").read_text(encoding="utf-8"))
    print(f"Outputs written to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
