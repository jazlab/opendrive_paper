#!/usr/bin/env python3
"""Reproduce the OpenDrive axial accuracy and precision statistics and figure.

This script analyzes repeated 10-mm displacement measurements for three
microdrives. It reproduces the descriptive statistics and inferential tests
reported for axial positioning accuracy and precision and generates the signed
positioning-error figure used for the manuscript.

Analyses produced:
1. Mean and sample SD of measured displacement and absolute positioning error.
2. Welch's one-way ANOVA on absolute positioning error.
3. Games-Howell pairwise comparisons after Welch's ANOVA.
4. Median-centered Levene test (Brown-Forsythe test) of variability.
5. Pairwise Brown-Forsythe tests with Holm correction.
6. Plot of signed error by drive, showing individual trials, mean, and ±1 SD.

Expected input columns:
    Trial, MEM Drive, Nan Drive, OpenDrive

Rows whose Trial value is not numeric (for example, precomputed "Mean" and
"Std" rows) are ignored so that all statistics are calculated from the raw
trial measurements.

Example:
    python axial_position.py \
        axial_position_data.csv \
        --output-dir axial_accuracy_results

Dependencies:
    numpy, pandas, scipy, statsmodels, matplotlib
"""

from __future__ import annotations

import argparse
import platform
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Mapping

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np
import pandas as pd
import scipy
from scipy import stats
import statsmodels
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.oneway import anova_oneway


COMMAND_DISTANCE_MM = 10.0
MICRONS_PER_MM = 1000.0

# Input-column names mapped to the display names used in the manuscript.
DRIVE_COLUMNS: Mapping[str, str] = {
    "OpenDrive": "OpenDrive",
    "Nan Drive": "NAN Drive",
    "MEM Drive": "MEM Drive",
}

# Order used in the figure.
PLOT_ORDER = ["MEM Drive", "NAN Drive", "OpenDrive"]


@dataclass(frozen=True)
class GamesHowellResult:
    group_1: str
    group_2: str
    mean_difference_mm: float
    standard_error_mm: float
    q_statistic: float
    degrees_of_freedom: float
    p_value: float
    ci_low_mm: float
    ci_high_mm: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce OpenDrive axial accuracy and precision statistics."
    )
    parser.add_argument(
        "input_csv",
        type=Path,
        help="CSV containing Trial, MEM Drive, Nan Drive, and OpenDrive columns.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("axial_accuracy_results"),
        help="Directory for generated statistics tables, report, and figure.",
    )
    parser.add_argument(
        "--command-distance-mm",
        type=float,
        default=COMMAND_DISTANCE_MM,
        help="Commanded displacement in millimeters (default: 10.0).",
    )
    parser.add_argument(
        "--plot-width",
        type=float,
        default=4.0,
        help="Plot width in inches (default: 4.0).",
    )
    parser.add_argument(
        "--plot-height",
        type=float,
        default=6.0,
        help="Plot height in inches (default: 6.0).",
    )
    parser.add_argument(
        "--plot-font-size",
        type=float,
        default=12.0,
        help="Font size for drive labels and y-axis label (default: 12.0).",
    )
    parser.add_argument(
        "--plot-dpi",
        type=int,
        default=300,
        help="Resolution of saved PNG figure (default: 300).",
    )
    return parser.parse_args()


def load_raw_trials(csv_path: Path) -> pd.DataFrame:
    """Load the CSV and retain only rows representing individual trials."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {csv_path}")

    data = pd.read_csv(csv_path)
    required = {"Trial", *DRIVE_COLUMNS.keys()}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            "Input CSV is missing required column(s): " + ", ".join(sorted(missing))
        )

    # Excludes spreadsheet summary rows such as "Mean" and "Std".
    numeric_trial = pd.to_numeric(data["Trial"], errors="coerce")
    data = data.loc[numeric_trial.notna(), list(required)].copy()
    data["Trial"] = numeric_trial.loc[numeric_trial.notna()].astype(int)

    for column in DRIVE_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="raise")

    if data.empty:
        raise ValueError("No numeric trial rows were found in the input CSV.")

    return data.sort_values("Trial").reset_index(drop=True)


def calculate_descriptive_statistics(
    raw: pd.DataFrame, command_distance_mm: float
) -> tuple[pd.DataFrame, dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Calculate displacement, signed-error, and absolute-error summaries."""
    signed_errors: dict[str, np.ndarray] = {}
    absolute_errors: dict[str, np.ndarray] = {}
    rows: list[dict[str, float | int | str]] = []

    for input_column, display_name in DRIVE_COLUMNS.items():
        displacement = raw[input_column].to_numpy(dtype=float)
        signed_error = displacement - command_distance_mm
        absolute_error = np.abs(signed_error)

        signed_errors[display_name] = signed_error
        absolute_errors[display_name] = absolute_error

        rows.append(
            {
                "drive": display_name,
                "n": displacement.size,
                "mean_displacement_mm": displacement.mean(),
                "sd_displacement_mm": displacement.std(ddof=1),
                "mean_signed_error_mm": signed_error.mean(),
                "sd_signed_error_mm": signed_error.std(ddof=1),
                "mean_absolute_error_mm": absolute_error.mean(),
                "sd_absolute_error_mm": absolute_error.std(ddof=1),
            }
        )

    return pd.DataFrame(rows), signed_errors, absolute_errors


def games_howell(
    groups: Mapping[str, np.ndarray], alpha: float = 0.05
) -> pd.DataFrame:
    """Perform all Games-Howell pairwise comparisons."""
    k = len(groups)
    if k < 2:
        raise ValueError("Games-Howell requires at least two groups.")

    results: list[GamesHowellResult] = []

    for group_1, group_2 in combinations(groups, 2):
        x = np.asarray(groups[group_1], dtype=float)
        y = np.asarray(groups[group_2], dtype=float)
        n_1, n_2 = x.size, y.size
        var_1, var_2 = x.var(ddof=1), y.var(ddof=1)
        mean_difference = x.mean() - y.mean()

        variance_of_difference = var_1 / n_1 + var_2 / n_2
        standard_error = np.sqrt(variance_of_difference)
        q_statistic = abs(mean_difference) / np.sqrt(0.5 * variance_of_difference)

        degrees_of_freedom = variance_of_difference**2 / (
            (var_1 / n_1) ** 2 / (n_1 - 1)
            + (var_2 / n_2) ** 2 / (n_2 - 1)
        )

        p_value = stats.studentized_range.sf(
            q_statistic, k, degrees_of_freedom
        )
        critical_q = stats.studentized_range.ppf(
            1.0 - alpha, k, degrees_of_freedom
        )
        margin = critical_q * np.sqrt(0.5 * variance_of_difference)

        results.append(
            GamesHowellResult(
                group_1=group_1,
                group_2=group_2,
                mean_difference_mm=mean_difference,
                standard_error_mm=standard_error,
                q_statistic=q_statistic,
                degrees_of_freedom=degrees_of_freedom,
                p_value=p_value,
                ci_low_mm=mean_difference - margin,
                ci_high_mm=mean_difference + margin,
            )
        )

    return pd.DataFrame([result.__dict__ for result in results])


def brown_forsythe_analysis(
    groups: Mapping[str, np.ndarray], alpha: float = 0.05
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run omnibus and Holm-adjusted pairwise Brown-Forsythe tests."""
    group_names = list(groups)
    arrays = [np.asarray(groups[name], dtype=float) for name in group_names]

    omnibus = stats.levene(*arrays, center="median")
    omnibus_table = pd.DataFrame(
        [
            {
                "test": "Brown-Forsythe (median-centered Levene)",
                "statistic_F": omnibus.statistic,
                "df_numerator": len(arrays) - 1,
                "df_denominator": sum(array.size for array in arrays) - len(arrays),
                "p_value": omnibus.pvalue,
            }
        ]
    )

    pairwise_rows: list[dict[str, float | str | bool]] = []
    raw_p_values: list[float] = []

    for group_1, group_2 in combinations(group_names, 2):
        result = stats.levene(groups[group_1], groups[group_2], center="median")
        raw_p_values.append(float(result.pvalue))
        pairwise_rows.append(
            {
                "group_1": group_1,
                "group_2": group_2,
                "statistic_F": result.statistic,
                "df_numerator": 1,
                "df_denominator": len(groups[group_1]) + len(groups[group_2]) - 2,
                "p_value_raw": result.pvalue,
            }
        )

    reject, adjusted_p, _, _ = multipletests(
        raw_p_values, alpha=alpha, method="holm"
    )
    for row, is_significant, p_adjusted in zip(
        pairwise_rows, reject, adjusted_p, strict=True
    ):
        row["p_value_holm"] = p_adjusted
        row["reject_at_alpha_0.05"] = bool(is_significant)

    return omnibus_table, pd.DataFrame(pairwise_rows)


def create_signed_error_plot(
    signed_errors: Mapping[str, np.ndarray],
    output_dir: Path,
    width: float = 4.0,
    height: float = 6.0,
    font_size: float = 12.0,
    dpi: int = 300,
) -> tuple[Path, Path]:
    """Create the narrow publication plot of signed positioning error.

    Individual trials are shown as lightly transparent circles. The group mean
    is shown as a diamond, with a vertical error bar representing ±1 sample SD.
    The figure has no title, legend, or explanatory inset.
    """
    fig, ax = plt.subplots(figsize=(width, height))
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    # Use exactly the same font properties for the x-axis drive labels and
    # y-axis description.
    shared_label_font = FontProperties(
        family="DejaVu Sans",
        style="normal",
        weight="normal",
        size=font_size,
    )

    for position, drive_name in enumerate(PLOT_ORDER, start=1):
        values_um = (
            np.asarray(signed_errors[drive_name], dtype=float)
            * MICRONS_PER_MM
        )
        mean_um = values_um.mean()
        sd_um = values_um.std(ddof=1)

        # Fixed deterministic jitter keeps the figure reproducible across runs.
        jitter = (
            np.array([0.0])
            if values_um.size == 1
            else np.linspace(-0.10, 0.10, values_um.size)
        )

        color = colors[(position - 1) % len(colors)]

        # Individual trials.
        ax.scatter(
            np.full(values_um.shape, position, dtype=float) + jitter,
            values_um,
            s=34,
            alpha=0.50,
            color=color,
            zorder=2,
        )

        # Mean ± 1 sample SD.
        ax.errorbar(
            position,
            mean_um,
            yerr=sd_um,
            fmt="D",
            markersize=8,
            capsize=6,
            elinewidth=1.8,
            capthick=1.8,
            linewidth=0,
            color=color,
            zorder=3,
        )

    # Zero error corresponds to exactly 10 mm of measured movement.
    ax.axhline(
        0,
        linestyle=":",
        linewidth=1.6,
        color="red",
        zorder=1,
    )

    ax.set_xticks(range(1, len(PLOT_ORDER) + 1))
    ax.set_xticklabels(
        PLOT_ORDER,
        fontproperties=shared_label_font,
    )

    ax.set_ylabel(
        "Signed error from 10 mm command (µm)",
        fontproperties=shared_label_font,
    )

    ax.set_xlabel("")
    ax.set_title("")
    ax.grid(True, axis="y", alpha=0.25)

    # Only the numeric y-axis tick labels are slightly smaller.
    ax.tick_params(axis="y", labelsize=font_size - 1)

    all_values_um = np.concatenate(
        [
            np.asarray(signed_errors[name], dtype=float) * MICRONS_PER_MM
            for name in PLOT_ORDER
        ]
    )
    data_range = all_values_um.max() - all_values_um.min()
    padding = max(5.0, 0.08 * data_range)
    ax.set_ylim(
        all_values_um.min() - padding,
        max(2.0, all_values_um.max() + padding),
    )

    fig.tight_layout()

    png_path = output_dir / "fig3b_signed_positioning_error.png"
    pdf_path = output_dir / "fig3b_signed_positioning_error.pdf"

    fig.savefig(
        png_path,
        dpi=dpi,
        bbox_inches="tight",
    )
    fig.savefig(
        pdf_path,
        bbox_inches="tight",
    )

    plt.close(fig)
    return png_path, pdf_path


def format_p(p_value: float) -> str:
    """Format p values compactly without reporting p as zero."""
    if p_value < 0.001:
        return f"{p_value:.3e}"
    return f"{p_value:.4f}"


def build_report(
    input_csv: Path,
    command_distance_mm: float,
    descriptive: pd.DataFrame,
    welch_result: object,
    games_howell_table: pd.DataFrame,
    bf_omnibus: pd.DataFrame,
    bf_pairwise: pd.DataFrame,
    plot_png_path: Path,
    plot_pdf_path: Path,
) -> str:
    """Create a plain-text record of all reported analyses."""
    lines: list[str] = [
        "OpenDrive axial accuracy and precision analysis",
        "=" * 51,
        f"Input file: {input_csv.resolve()}",
        f"Commanded displacement: {command_distance_mm:.6f} mm",
        "",
        "Software versions",
        "-----------------",
        f"Python: {platform.python_version()}",
        f"NumPy: {np.__version__}",
        f"pandas: {pd.__version__}",
        f"SciPy: {scipy.__version__}",
        f"statsmodels: {statsmodels.__version__}",
        f"matplotlib: {plt.matplotlib.__version__}",
        "",
        "Generated figure files",
        "----------------------",
        f"PNG: {plot_png_path.resolve()}",
        f"PDF: {plot_pdf_path.resolve()}",
        "",
        "Descriptive statistics (mean and sample SD)",
        "-------------------------------------------",
    ]

    for row in descriptive.itertuples(index=False):
        lines.append(
            f"{row.drive}: n={row.n}; displacement="
            f"{row.mean_displacement_mm:.6f} ± {row.sd_displacement_mm:.6f} mm; "
            f"absolute error={row.mean_absolute_error_mm:.6f} ± "
            f"{row.sd_absolute_error_mm:.6f} mm"
        )

    df_num, df_den = welch_result.df
    lines.extend(
        [
            "",
            "Accuracy: Welch's one-way ANOVA on absolute error",
            "-------------------------------------------------",
            f"F({df_num:.0f}, {df_den:.6f}) = {welch_result.statistic:.9f}, "
            f"p = {welch_result.pvalue:.12g}",
            "",
            "Games-Howell pairwise comparisons",
            "-----------------------------------",
        ]
    )

    for row in games_howell_table.itertuples(index=False):
        lines.append(
            f"{row.group_1} vs {row.group_2}: mean difference="
            f"{row.mean_difference_mm:.9f} mm; q={row.q_statistic:.9f}; "
            f"df={row.degrees_of_freedom:.9f}; p={row.p_value:.12g}; "
            f"95% simultaneous CI=[{row.ci_low_mm:.9f}, "
            f"{row.ci_high_mm:.9f}] mm"
        )

    bf_row = bf_omnibus.iloc[0]
    lines.extend(
        [
            "",
            "Precision: Brown-Forsythe test of variability",
            "----------------------------------------------",
            f"F({int(bf_row['df_numerator'])}, {int(bf_row['df_denominator'])}) = "
            f"{bf_row['statistic_F']:.9f}, p = {bf_row['p_value']:.12g}",
            "",
            "Pairwise Brown-Forsythe tests with Holm correction",
            "--------------------------------------------------",
        ]
    )

    for row in bf_pairwise.itertuples(index=False):
        lines.append(
            f"{row.group_1} vs {row.group_2}: F({int(row.df_numerator)}, "
            f"{int(row.df_denominator)})={row.statistic_F:.9f}; "
            f"raw p={row.p_value_raw:.12g}; Holm-adjusted "
            f"p={row.p_value_holm:.12g}"
        )

    lines.extend(
        [
            "",
            "Manuscript-rounded values",
            "-------------------------",
            f"Welch ANOVA: F(2, {df_den:.2f}) = {welch_result.statistic:.2f}, "
            f"p = {welch_result.pvalue:.3g}",
            "Games-Howell:",
        ]
    )
    for row in games_howell_table.itertuples(index=False):
        lines.append(
            f"  {row.group_1} vs {row.group_2}: p = {format_p(row.p_value)}"
        )
    lines.append(
        f"Brown-Forsythe: F({int(bf_row['df_numerator'])}, "
        f"{int(bf_row['df_denominator'])}) = {bf_row['statistic_F']:.2f}, "
        f"p = {bf_row['p_value']:.4f}"
    )
    lines.append("Pairwise Brown-Forsythe, Holm-adjusted:")
    for row in bf_pairwise.itertuples(index=False):
        lines.append(
            f"  {row.group_1} vs {row.group_2}: "
            f"adjusted p = {format_p(row.p_value_holm)}"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    raw = load_raw_trials(args.input_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    descriptive, signed_errors, absolute_errors = calculate_descriptive_statistics(
        raw, args.command_distance_mm
    )

    # Accuracy analysis: absolute deviation from the commanded 10-mm movement.
    welch_result = anova_oneway(
        list(absolute_errors.values()),
        use_var="unequal",
        welch_correction=True,
    )
    games_howell_table = games_howell(absolute_errors)

    # Precision analysis: variability in repeated measured displacements.
    # Variability is unchanged by subtracting a constant; measured displacement
    # is used here because that matches the manuscript's definition of precision.
    displacement_groups = {
        display_name: raw[input_column].to_numpy(dtype=float)
        for input_column, display_name in DRIVE_COLUMNS.items()
    }
    bf_omnibus, bf_pairwise = brown_forsythe_analysis(displacement_groups)

    # Publication figure.
    plot_png_path, plot_pdf_path = create_signed_error_plot(
        signed_errors=signed_errors,
        output_dir=args.output_dir,
        width=args.plot_width,
        height=args.plot_height,
        font_size=args.plot_font_size,
        dpi=args.plot_dpi,
    )

    # Save statistical output tables.
    descriptive.to_csv(args.output_dir / "fig3b_axial_positioning_descriptive_statistics.csv", index=False)
    pd.DataFrame(
        [
            {
                "test": "Welch one-way ANOVA",
                "outcome": "absolute positioning error (mm)",
                "statistic_F": welch_result.statistic,
                "df_numerator": welch_result.df[0],
                "df_denominator": welch_result.df[1],
                "p_value": welch_result.pvalue,
            }
        ]
    ).to_csv(args.output_dir / "fig3b_axial_positioning_welch_anova.csv", index=False)
    games_howell_table.to_csv(
        args.output_dir / "fig3b_axial_positioning_games_howell_pairwise.csv", index=False
    )
    bf_omnibus.to_csv(
        args.output_dir / "fig3b_axial_positioning_brown_forsythe_omnibus.csv", index=False
    )
    bf_pairwise.to_csv(
        args.output_dir / "fig3b_axial_positioning_brown_forsythe_pairwise_holm.csv", index=False
    )

    # Save a plain-text report.
    report = build_report(
        input_csv=args.input_csv,
        command_distance_mm=args.command_distance_mm,
        descriptive=descriptive,
        welch_result=welch_result,
        games_howell_table=games_howell_table,
        bf_omnibus=bf_omnibus,
        bf_pairwise=bf_pairwise,
        plot_png_path=plot_png_path,
        plot_pdf_path=plot_pdf_path,
    )
    report_path = args.output_dir / "fig3b_axial_positioning_report.txt"
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"Saved results to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
