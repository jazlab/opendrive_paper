"""Reproduce OpenDrive Figures 3 and 4 with the current Python environment."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

from verify_data import ROOT, verify_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", choices=["all", "3", "4"], default="all")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    verify_data(args.figure)
    destination = args.output_dir.expanduser().resolve()
    env = dict(os.environ, MPLBACKEND="Agg")
    commands = []
    if args.figure in ("all", "3"):
        commands.extend([
            ["figures/fig3/fig3a/lateral_motion_analysis.py", "figures/fig3/fig3a/data",
             "--output-dir", str(destination / "fig3a")],
            ["figures/fig3/fig3b/axial_position.py", "figures/fig3/fig3b/axial_position_data.csv",
             "--output-dir", str(destination / "fig3b")],
        ])
    if args.figure in ("all", "4"):
        commands.append(["figures/fig4/drift_map.py", "--output-dir", str(destination / "fig4")])
    for command in commands:
        subprocess.run([sys.executable, *command], cwd=ROOT, env=env, check=True)
    print(f"Reproduction complete. Outputs: {destination}")


if __name__ == "__main__":
    main()
